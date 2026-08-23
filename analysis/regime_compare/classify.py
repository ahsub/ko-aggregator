"""
classify.py

Beide Regime-Modelle auf demselben Panel (build_panel.py), fuer einen
fairen Vergleich statt der bisherigen Aepfel-Birnen-Situation (verschiedene
Datenquellen, verschiedene Zeitraeume, verschiedene Methodik).

Modell A / regime_v1 (market_aggregator.py, Z. ~8510-8540, produktiv):
    ratio = vix3m / vix
    ratio < 0.98            -> STRESS_UNSTABLE
    0.98 <= ratio < 1.05     -> POST_PANIC_REVERSION
    ratio >= 1.05, vix > 25  -> BULL_FRAGILE
    ratio >= 1.05, vix <= 25 -> BULL_QUIET

regime_v2 = regime_v1 + GEX<0-Override (nur wenn v1 BULL_*):
    ratio >= 1.05 (v1 sagt BULL_*) UND gex < 0 -> STRESS_UNSTABLE (ueberschreibt)

5-Faktor-Modell (ko-market-state.js::determineRegime(), 1:1 portiert,
inkl. Reihenfolge-Prioritaet und der Besonderheit, dass der aktuelle Tag
Teil seines eigenen Z-Score-Fensters ist, s. addDataPoint() VOR
normalizeMetrics() in analyze()):
    Rolling-Window 20 Tage (kuerzer falls Historie < 20), inkl. aktuellem Tag.
    zScore: (x - mean) / population_std, gerundet auf 2 Nachkommastellen.
    percentileRank: Anteil der Fensterwerte <= aktuellem Wert, in %, gerundet.
    term_structure: ratio > 1.05 -> CONTANGO, ratio < 0.98 -> BACKWARDATION,
                     sonst FLAT.
    Prioritaet (erste zutreffende Regel gewinnt):
      1. STRESS_UNSTABLE:      term=BACKWARDATION ODER (vvix_z>1.5 UND gex_z<-1.0)
      2. POST_PANIC_REVERSION: term=FLAT UND dix_z>0.5 UND vvix_z<0
      3. BULL_FRAGILE:         term=CONTANGO UND skew_pct>80 UND vvix_z>0.8
      4. BULL_QUIET:           term=CONTANGO UND gex_z>0 UND dix_z>=-0.5
      5. sonst: NEUTRAL
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LOOKBACK = 20

THRESHOLDS = dict(
    vixTermContango=1.05,
    vixTermFlat=0.98,
    vvixHighStress=1.5,
    gexShortGamma=-1.0,
    dixAccumulation=0.5,
    skewHighHedging=80,
)


def classify_v1_v2(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.copy()
    ratio = df["vix3m"] / df["vix"]
    df["ratio"] = ratio

    def _v1(r, vix):
        if r < 0.98:
            return "STRESS_UNSTABLE"
        if r < 1.05:
            return "POST_PANIC_REVERSION"
        return "BULL_FRAGILE" if vix > 25 else "BULL_QUIET"

    df["regime_v1"] = [
        _v1(r, v) for r, v in zip(df["ratio"], df["vix"])
    ]

    is_bull = df["regime_v1"].isin(["BULL_FRAGILE", "BULL_QUIET"])
    override = is_bull & (df["gex"] < 0)
    df["regime_v2"] = df["regime_v1"]
    df.loc[override, "regime_v2"] = "STRESS_UNSTABLE"
    df["v2_overrode_v1"] = override
    return df


def _rolling_zscore(values: np.ndarray, lookback: int = LOOKBACK) -> np.ndarray:
    """Inklusive des aktuellen Punkts im Fenster (s. Docstring: addDataPoint()
    laeuft in der JS-Produktion VOR normalizeMetrics()). Population-Std
    (ddof=0), gerundet auf 2 Nachkommastellen, identisch zu Math.round(...*100)/100."""
    n = len(values)
    out = np.full(n, np.nan)
    for i in range(n):
        lo = max(0, i - lookback + 1)
        window = values[lo:i + 1]
        if len(window) < 3:
            continue
        mean = window.mean()
        std = window.std(ddof=0)
        out[i] = 0.0 if std == 0 else round((values[i] - mean) / std, 2)
    return out


def _rolling_percentile(values: np.ndarray, lookback: int = LOOKBACK) -> np.ndarray:
    n = len(values)
    out = np.full(n, np.nan)
    for i in range(n):
        lo = max(0, i - lookback + 1)
        window = values[lo:i + 1]
        if len(window) < 3:
            continue
        below = (window <= values[i]).sum()
        out[i] = round(100 * below / len(window))
    return out


def classify_5factor(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.copy()
    T = THRESHOLDS

    df["vvix_z20"] = _rolling_zscore(df["vvix"].values)
    df["gex_z20"] = _rolling_zscore(df["gex"].values)
    df["dix_z20"] = _rolling_zscore(df["dix"].values)
    df["skew_pct20"] = _rolling_percentile(df["skew"].values)

    ratio = df["vix3m"] / df["vix"]
    term = np.where(ratio > T["vixTermContango"], "CONTANGO",
             np.where(ratio < T["vixTermFlat"], "BACKWARDATION", "FLAT"))
    df["term_structure"] = term

    def _classify(row):
        if pd.isna(row["vvix_z20"]) or pd.isna(row["gex_z20"]) or pd.isna(row["dix_z20"]) or pd.isna(row["skew_pct20"]):
            return None  # Warm-up-Phase, keine 20 Punkte Historie
        if row["term_structure"] == "BACKWARDATION" or (
            row["vvix_z20"] > T["vvixHighStress"] and row["gex_z20"] < T["gexShortGamma"]
        ):
            return "STRESS_UNSTABLE"
        if row["term_structure"] == "FLAT" and row["dix_z20"] > T["dixAccumulation"] and row["vvix_z20"] < 0:
            return "POST_PANIC_REVERSION"
        if row["term_structure"] == "CONTANGO" and row["skew_pct20"] > T["skewHighHedging"] and row["vvix_z20"] > 0.8:
            return "BULL_FRAGILE"
        if row["term_structure"] == "CONTANGO" and row["gex_z20"] > 0 and row["dix_z20"] >= -0.5:
            return "BULL_QUIET"
        return "NEUTRAL"

    df["regime_5f"] = df.apply(_classify, axis=1)
    return df


if __name__ == "__main__":
    from build_panel import build_unified_panel

    p = build_unified_panel()
    p = classify_v1_v2(p)
    p = classify_5factor(p)
    print(p[["regime_v1", "regime_v2", "regime_5f"]].tail(10))
    print()
    print("regime_v1 Verteilung:\n", p["regime_v1"].value_counts())
    print()
    print("regime_v2 Verteilung:\n", p["regime_v2"].value_counts())
    print()
    print("regime_5f Verteilung (inkl. Warm-up=None):\n", p["regime_5f"].value_counts(dropna=False))
    p.to_csv("classified_panel.csv")
