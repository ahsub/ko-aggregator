"""
dsr_check.py

Deflated-Sharpe-Ratio-Check fuer alle drei Regime-Modelle, mit echter,
gezaehlter n_trials=3 (regime_v1/regime_v2/regime_5f) statt einer Schaetzung
(s. Kritikpunkt aus Backlog-marketstate-2026-08-18.md, Eintrag 4). Nutzt
compute_dsr() aus ../deflated_sharpe_ratio.py (Bailey & Lopez de Prado 2014).

Strategie (bewusst simpel, dient nur dem Modellvergleich, nicht als
Produktionsstrategie-Vorschlag): Long im SPX-Preis ausser an Tagen, an denen
das jeweilige Modell STRESS_UNSTABLE meldet (Entscheidung auf Basis des
VORTAGS-Regimes, kein Lookahead). Referenz: Buy & Hold (n_trials=1).

Ergebnis dieser Session (23.08.2026, s. Nachtrag REGIME-BACKTEST-
VALIDIERUNG.md): keines der drei Modelle statistisch robust gegenueber
Buy & Hold nach Mehrfachtest-Korrektur -- regime_v2 hat aber die hoechste
rohe Sharpe Ratio der drei gegateten Strategien (0.80 vs. 0.76 [v1] vs.
0.62 [5-Faktor]).

KORREKTUR v2.0 (26.09.2026, Claude + Axel):
  Die DSR-Werte vom 23.08.2026 (Gates ~0, Buy & Hold 1,0) waren ein
  Rechenartefakt von deflated_sharpe_ratio.py v1 (Einheitenfehler im
  Standardfehler + unrealistischer Default sr_std_across_trials = 1,0, s.
  dortiger CHANGELOG). Die rohen Sharpe Ratios (0,76/0,80/0,62) waren
  korrekt. Die Aussage "nicht robust gegenueber Buy & Hold" war mit der DSR
  ohnehin nicht pruefbar (DSR testet "Sharpe > 0", nicht "besser als
  Benchmark"). Seit v2.0 wird deshalb zusaetzlich der Test der taeglichen
  Differenzrendite Modell minus Buy & Hold ausgegeben (HAUPTKENNZAHL, wie in
  ../regime_gate_backtest_v2.py v2.2) und die DSR mit der tatsaechlich
  beobachteten Streuung der drei Sharpe Ratios berechnet.

  Ergebnis v2.0 (Lauf 26.09.2026): siehe dsr_result.json bzw. UIQ-Suite
  SUITE.md 4.33, Backlog №34.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # fuer deflated_sharpe_ratio.py / regime_gate_backtest_v2.py

from build_panel import build_unified_panel
from classify import classify_v1_v2, classify_5factor
from deflated_sharpe_ratio import compute_dsr, sharpe_ratio, sr_std_from_trials
from regime_gate_backtest_v2 import excess_test

N_TRIALS = 3  # regime_v1 (Baseline), regime_v2, regime_5f -- echt gezaehlt, nicht geschaetzt


def strategy_returns(panel, daily_ret, regime_col):
    """Long ausser an Tagen mit STRESS_UNSTABLE. Entscheidung basiert auf dem
    VORTAGES-Regime (shift(1)), damit keine Lookahead-Information einfliesst."""
    in_market = (panel[regime_col] != "STRESS_UNSTABLE").shift(1).fillna(True)
    return (daily_ret * in_market).dropna()


def main():
    panel = build_unified_panel()
    panel = classify_v1_v2(panel)
    panel = classify_5factor(panel)
    daily_ret = panel["price"].pct_change()

    rets, results = {}, {}
    for model in ("regime_v1", "regime_v2", "regime_5f"):
        valid = panel.dropna(subset=[model]) if model == "regime_5f" else panel
        rets[model] = strategy_returns(valid, daily_ret, model).reindex(valid.index).dropna()

    # Streuung der Sharpe Ratios ueber die Familie (v2.0: Pflichtparameter, kein Default)
    sd_fam = sr_std_from_trials([sharpe_ratio(r.values) for r in rets.values()])

    for model, ret in rets.items():
        valid = panel.dropna(subset=[model]) if model == "regime_5f" else panel
        bh = daily_ret.reindex(ret.index)
        r = {
            "vergleich_buy_and_hold": excess_test(ret, bh),          # HAUPTKENNZAHL
            "dsr_nebeninformation": compute_dsr(ret.values, n_trials=N_TRIALS,
                                                sr_std_across_trials_ann=sd_fam),
            "pct_days_long": round(100 * float((valid.loc[ret.index, model] != "STRESS_UNSTABLE").mean()), 1),
        }
        results[model] = r

    bh_all = daily_ret.dropna()
    results["buy_and_hold"] = {"sharpe_ann": round(sharpe_ratio(bh_all.values), 4), "n_obs": int(len(bh_all))}
    results["meta"] = {"version": "v2.0 (26.09.2026)", "n_trials": N_TRIALS,
                       "sr_std_across_trials_ann": round(sd_fam, 4),
                       "hinweis": "DSR prueft 'Sharpe > 0', der Buy-&-Hold-Vergleich prueft den Vorsprung."}

    with open("dsr_result.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
