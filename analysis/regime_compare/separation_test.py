"""
separation_test.py

Fairer Kopf-an-Kopf-Vergleich: regime_v1 / regime_v2 / regime_5f auf
demselben Panel, derselben Methodik wie regime_v2_backtest.py::
analysis_b_separation() (bereits bugfixed, s. 18.08.2026-Session) --
jetzt fuer alle drei Modelle statt nur v1/v2.

WICHTIGE EINSCHRAENKUNG (ehrlich vorab benannt): Die urspruengliche
10.08.2026-Validierung nutzte echte CBOE-Strategie-Indizes (PUT/BXM/CLL) als
oekonomischen Massstab -- das ist naeher an der tatsaechlichen
Options-Anwendung als reine Forward-Vol/Drawdown auf den Index-Kurs. Diese
Indizes sind weder im Repo committet noch fuer mich live abrufbar
(cdn.cboe.com steht nicht auf der Netzwerk-Freigabe). Dieser Test nutzt
daher SPX-Forward-Vol/Max-Drawdown als Risikoproxy (Methodik aus
regime_v2_backtest.py) -- das beantwortet "sortiert das Modell Tage nach
tatsaechlichem Risiko", nicht "welches Modell verdient mehr Optionspraemie".
Fuer Letzteres muessten PUT/BXM/CLL nachtraeglich ergaenzt werden.

SPX-Kurs kommt aus DIX_GEX_History.csv (Spalte 'price', SqueezeMetrics-
Datensatz enthaelt den taeglichen SPX-Schlusskurs als Kontext fuer DIX/GEX) --
keine zusaetzliche Quelle noetig.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REGIME_ORDER = ["STRESS_UNSTABLE", "POST_PANIC_REVERSION", "BULL_FRAGILE", "BULL_QUIET", "NEUTRAL"]

ASCENDING_FOR_RISK_DESCENDING = {
    "fwd_vol_21d": False,
    "fwd_vol_63d": False,
    "fwd_maxdd_21d": True,
    "fwd_maxdd_63d": True,
}


def _forward_max_drawdown(price: pd.Series, h: int) -> pd.Series:
    result = pd.Series(index=price.index, dtype=float)
    values = price.values
    n = len(values)
    for i in range(n):
        window = values[i: i + h + 1]
        if len(window) < 2:
            result.iloc[i] = np.nan
            continue
        base = window[0]
        running_min = np.minimum.accumulate(window)
        result.iloc[i] = (running_min / base - 1).min()
    return result


def add_forward_metrics(df: pd.DataFrame, price_col: str = "price") -> pd.DataFrame:
    df = df.copy()
    price = df[price_col]
    daily_ret = price.pct_change()
    for h in (21, 63):
        df[f"fwd_return_{h}d"] = price.shift(-h) / price - 1
        df[f"fwd_vol_{h}d"] = (
            daily_ret.shift(-h).rolling(window=h, min_periods=h // 2)
            .std().shift(-(h - 1)) * np.sqrt(252)
        )
        df[f"fwd_maxdd_{h}d"] = _forward_max_drawdown(price, h)
    return df


def separation_by_model(df: pd.DataFrame, regime_col: str) -> dict:
    result = {}
    for metric in ("fwd_vol_21d", "fwd_vol_63d", "fwd_maxdd_21d", "fwd_maxdd_63d"):
        grp = df.groupby(regime_col)[metric].agg(["mean", "count"])
        grp = grp.reindex(REGIME_ORDER).dropna(how="all")
        result[f"{metric}_by_regime"] = {
            k: {"mean": round(float(v["mean"]), 4), "n": int(v["count"])}
            for k, v in grp.iterrows() if not pd.isna(v["mean"])
        }
        means = grp["mean"].dropna()
        ascending = ASCENDING_FOR_RISK_DESCENDING[metric]
        expected_order = [r for r in REGIME_ORDER if r in means.index]
        actual_sorted = list(means.sort_values(ascending=ascending).index)
        # Monotonie relativ zur Teilmenge tatsaechlich vorhandener Regimes,
        # NEUTRAL zaehlt als "am wenigsten riskant nach BULL_QUIET" fuer
        # Modelle, die es kennen (5f) -- fuer v1/v2 kommt es nie vor.
        result[f"{metric}_monotonic_as_expected"] = (
            list(means.index) == actual_sorted
        )
    return result


def n_trials_estimate() -> int:
    """Ehrliche Zaehlung statt Schaetzung (Backlog-Kritikpunkt vom 18.08.):
    Anzahl tatsaechlich getesteter Modellvarianten in dieser Session."""
    return 3  # regime_v1 (Referenz/Baseline), regime_v2, regime_5f


if __name__ == "__main__":
    from build_panel import build_unified_panel
    from classify import classify_v1_v2, classify_5factor
    import json

    p = build_unified_panel()
    p = classify_v1_v2(p)
    p = classify_5factor(p)
    p = add_forward_metrics(p)

    out = {
        "panel_info": {
            "n_days": len(p),
            "start": str(p.index.min().date()),
            "end": str(p.index.max().date()),
        },
        "regime_v1": separation_by_model(p, "regime_v1"),
        "regime_v2": separation_by_model(p, "regime_v2"),
        "regime_5f": separation_by_model(p.dropna(subset=["regime_5f"]), "regime_5f"),
    }

    with open("separation_result.json", "w") as f:
        json.dump(out, f, indent=2)

    print(json.dumps(out, indent=2))
