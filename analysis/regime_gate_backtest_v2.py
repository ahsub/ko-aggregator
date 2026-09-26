#!/usr/bin/env python3
"""
regime_gate_backtest_v2.py — Korrigierter Regime-Gate-Backtest (Backlog №34 / Go-Kriterium 2)
=============================================================================================
Version: v2.1 (26.09.2026, Claude + Axel) — FORSCHUNGSFASSUNG, kein Produktionscode.

CHANGELOG
  v2.1 (26.09.2026): Reviewer-Anforderungen ergaenzt — expliziter Look-ahead-
       Selbsttest (Perturbationstest, bricht bei Verletzung ab), Turnover,
       dokumentierte Fehldaten-Politik inkl. Zaehlung, Testfamilie fuer DSR als
       Liste statt Zahl, Signal-/Handelszeitpunkt im Kopf dokumentiert.
  v2.0 (26.09.2026): Erstfassung — Lag-Korrektur, Wechselkosten, DSR.

ANLASS
  Das Vorgaengerskript refundex/engine/backtest_2007_2026.py (07.08.2026) enthaelt
  einen Look-ahead-Fehler:
      data['strat_A_ret'] = data['spy_ret'] * data['in_market_A']
  Das Regime wird aus den VIX/VIX3M-SCHLUSSKURSEN von Tag t bestimmt und auf die
  Rendite DESSELBEN Tages t (Schluss t-1 -> Schluss t) angewendet. Da der VIX an
  Verlusttagen steigt, "kennt" das Gate den Tagesverlust, den es angeblich meidet.
  Korrekte Form (so bereits in analysis/regime_compare/dsr_check.py, 23.08.2026):
  Regime aus Schlusskursen von t -> Position fuer die Rendite von t+1.

SIGNAL- UND HANDELSZEITPUNKT (Modellannahme)
  - Signal: nach Handelsschluss von Tag t aus VIX- und VIX3M-Schlusskurs (CBOE).
  - Handel: zum Schlusskurs von t (Annahme "Market-on-Close", idealisiert; in der
    Praxis Ausfuehrung frühestens zur Eroeffnung t+1 -> leicht optimistisch).
  - Rendite: Position ab Schluss t erhaelt die Indexrendite Schluss t -> Schluss t+1.
  - Kosten: pauschal COST_BP je Positionswechsel (Default 5 bp, deckt Spread und
    Slippage fuer einen liquiden Index-ETF grob ab; per --cost-bp variierbar).

DATEN UND FEHLDATEN-POLITIK
  - data/raw_data/VIX_History.csv (vix_close), VIX3M_History.csv (CLOSE) — CBOE.
  - data/raw_data/DIX_GEX_History.csv, Spalte "price" = S&P 500 Index OHNE
    Dividenden (SqueezeMetrics-Historie) -> Zeitraum ab 2011-05-02.
  - Zusammenfuehrung per Inner Join auf Handelstage; KEIN Forward-Fill. Tage ohne
    vollstaendige Daten werden verworfen und im Ergebnis gezaehlt ("fehldaten").
    Stand 26.09.2026: 34 verworfene Tage — fast ausschliesslich US-Boersenfeiertage
    (z. B. 2022-07-04, 2023-11-23, 2025-01-09), an denen die CBOE-Dateien Zeilen
    fuehren, der Index aber nicht gehandelt wurde. Verwerfen ist dort korrekt;
    die Preisreihe selbst hat im Zeitraum keine Luecken an Handelstagen.
  - Alle Varianten und Buy & Hold nutzen exakt denselben Zeitraum.

EINSCHRAENKUNGEN (bewusst nicht geglaettet)
  - Ohne Dividenden: CAGR aller Varianten ~1,5–2 %/Jahr zu niedrig. Cash-Tage mit
    0 % statt Geldmarktzins (leicht zu Ungunsten der Gates).
  - Finanzkrise 2008/09 nicht enthalten (Preisreihe ab 05/2011).
  - Nur Long/Flat-Gate, keine Strategie-spezifische Renditequelle.

TESTFAMILIE (fuer DSR, ehrlich gezaehlt ueber das Projekt)
  Gate A und Gate B (07.08./26.08.2026), regime_v1, regime_v2, regime_5f
  (23.08.2026, dsr_check.py) -> N_TRIALS = 5. Die Wechselkosten-Variation ueber
  --cost-bp ist eine Sensitivitaetsanalyse, keine zusaetzliche Selektion.

AUSFUEHRUNG
  cd analysis && python3 regime_gate_backtest_v2.py [--cost-bp 5]
  -> Konsole + regime_gate_backtest_v2_result.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from deflated_sharpe_ratio import compute_dsr

RAW = Path(__file__).resolve().parent.parent / "data" / "raw_data"

STRESS_THR = 0.98
BULL_THR = 1.05
VIX_FRAGILE = 25.0

TRIAL_FAMILY = ["gate_A", "gate_B", "regime_v1", "regime_v2", "regime_5f"]
N_TRIALS = len(TRIAL_FAMILY)


def load_panel():
    vix = pd.read_csv(RAW / "VIX_History.csv", parse_dates=["date"]).set_index("date")["vix_close"].rename("vix")
    v3 = pd.read_csv(RAW / "VIX3M_History.csv")
    v3["DATE"] = pd.to_datetime(v3["DATE"], format="%m/%d/%Y")
    vix3m = v3.set_index("DATE")["CLOSE"].rename("vix3m")
    px = pd.read_csv(RAW / "DIX_GEX_History.csv", parse_dates=["date"]).set_index("date")["price"].rename("price")
    outer = pd.concat([vix, vix3m, px], axis=1).sort_index()
    outer = outer[outer.index >= px.index.min()]
    outer = outer[outer.index <= px.index.max()]
    panel = outer.dropna()
    panel = panel[(panel[["vix", "vix3m", "price"]] > 0).all(axis=1)]
    dropped = int(len(outer) - len(panel))
    return panel, dropped


def classify(ratio: float, vix: float) -> str:
    """Identisch zu classify_regime() in refundex/engine/backtest_2007_2026.py."""
    if ratio < STRESS_THR:
        return "STRESS_UNSTABLE"
    if ratio < BULL_THR:
        return "POST_PANIC_REVERSION"
    return "BULL_FRAGILE" if vix > VIX_FRAGILE else "BULL_QUIET"


def regimes(panel: pd.DataFrame) -> pd.Series:
    return pd.Series([classify(r, v) for r, v in zip(panel["vix3m"] / panel["vix"], panel["vix"])],
                     index=panel.index)


def positions(reg: pd.Series, gate: str, lagged: bool) -> pd.Series:
    """Position fuer die Rendite von Tag t (1 = investiert). lagged=True: Regime von t-1."""
    sig = (reg != "STRESS_UNSTABLE") if gate == "A" else (reg == "BULL_QUIET")
    if lagged:
        sig = sig.shift(1, fill_value=bool(sig.iloc[0]))
    return sig.astype(float)


def strategy_returns(ret: pd.Series, pos: pd.Series, cost_bp: float) -> pd.Series:
    switches = pos.diff().abs().fillna(0.0)
    return ret * pos - switches * cost_bp / 10_000.0


def metrics(r: pd.Series, pos: pd.Series) -> dict:
    cum = (1 + r).cumprod()
    years = len(r) / 252
    switches = float(pos.diff().abs().fillna(0.0).sum())
    return {
        "sharpe": round(float(r.mean() / r.std() * np.sqrt(252)), 3) if r.std() > 0 else None,
        "cagr_pct": round(float((cum.iloc[-1] ** (1 / years) - 1) * 100), 2),
        "max_dd_pct": round(float((cum / cum.cummax() - 1).min() * 100), 2),
        "pct_invested": round(float(pos.mean() * 100), 1),
        "wechsel_gesamt": int(switches),
        "wechsel_pro_jahr": round(switches / years, 1),
        "n_days": int(len(r)),
    }


def lookahead_selftest(panel: pd.DataFrame) -> dict:
    """Perturbationstest: Werden die Daten ab Tag k veraendert, darf sich die
    Position fuer Tage <= k NICHT aendern (lagged). Die fehlerhafte Variante muss
    diesen Test verletzen (Nachweis, dass der Test greift). Bricht bei Verletzung
    der korrekten Variante mit AssertionError ab."""
    reg = regimes(panel)
    out = {}
    rng = np.random.default_rng(42)
    ks = rng.choice(np.arange(50, len(panel) - 50), size=25, replace=False)
    viol = {"lagged": 0, "lookahead": 0}
    for k in ks:
        pert = panel.copy()
        pert.iloc[k:, pert.columns.get_loc("vix")] *= 3.0   # erzwingt STRESS ab Tag k
        reg_p = regimes(pert)
        for mode, lagged in (("lagged", True), ("lookahead", False)):
            a = positions(reg, "A", lagged).iloc[: k + 1]
            b = positions(reg_p, "A", lagged).iloc[: k + 1]
            if not a.equals(b):
                viol[mode] += 1
    assert viol["lagged"] == 0, f"Look-ahead in korrekter Variante: {viol['lagged']} Verletzungen"
    out["stichproben"] = int(len(ks))
    out["verletzungen_lagged"] = viol["lagged"]
    out["verletzungen_lookahead_erwartet_gt_0"] = viol["lookahead"]
    out["bestanden"] = viol["lagged"] == 0 and viol["lookahead"] > 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-bp", type=float, default=5.0, help="Kosten je Positionswechsel in Basispunkten")
    args = ap.parse_args()

    panel, dropped = load_panel()
    reg = regimes(panel)
    ret = panel["price"].pct_change().fillna(0.0)
    ones = pd.Series(1.0, index=panel.index)

    res = {
        "meta": {
            "version": "v2.1",
            "zeitraum": f"{panel.index[0].date()} bis {panel.index[-1].date()}",
            "preisreihe": "S&P 500 Index ohne Dividenden (DIX_GEX_History.csv, Spalte price)",
            "fehldaten_verworfene_tage": dropped,
            "wechselkosten_bp": args.cost_bp,
            "dsr_testfamilie": TRIAL_FAMILY,
            "n_trials_dsr": N_TRIALS,
        },
        "lookahead_selbsttest": lookahead_selftest(panel),
        "buy_and_hold": {**metrics(ret, ones), "dsr": compute_dsr(ret.values, n_trials=1)},
    }
    for gate, name in (("A", "gate_A_kein_STRESS"), ("B", "gate_B_nur_BULL_QUIET")):
        pos_look = positions(reg, gate, lagged=False)
        pos_lag = positions(reg, gate, lagged=True)
        r_look = strategy_returns(ret, pos_look, args.cost_bp)
        r_lag = strategy_returns(ret, pos_lag, args.cost_bp)
        res[name] = {
            "lookahead_FEHLERHAFT_nur_zur_doku": metrics(r_look, pos_look),
            "lagged_korrekt": metrics(r_lag, pos_lag),
            "dsr_lagged": compute_dsr(r_lag.values, n_trials=N_TRIALS),
        }

    stress = reg == "STRESS_UNSTABLE"
    res["diagnose"] = {
        "mittlere_tagesrendite_pct_an_STRESS_tagen_gleicher_tag": round(float(ret[stress].mean() * 100), 3),
        "mittlere_tagesrendite_pct_an_STRESS_tagen_folgetag": round(float(ret.shift(-1)[stress].mean() * 100), 3),
        "anteil_STRESS_tage_pct": round(float(stress.mean() * 100), 1),
    }

    out = Path(__file__).resolve().parent / "regime_gate_backtest_v2_result.json"
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
