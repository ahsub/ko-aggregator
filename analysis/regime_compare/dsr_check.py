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
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # fuer deflated_sharpe_ratio.py

from build_panel import build_unified_panel
from classify import classify_v1_v2, classify_5factor
from deflated_sharpe_ratio import compute_dsr

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

    results = {}
    for model in ("regime_v1", "regime_v2", "regime_5f"):
        valid = panel.dropna(subset=[model]) if model == "regime_5f" else panel
        ret = strategy_returns(valid, daily_ret, model).reindex(valid.index).dropna()
        r = compute_dsr(ret.values, n_trials=N_TRIALS)
        r["pct_days_long"] = round(100 * float((valid.loc[ret.index, model] != "STRESS_UNSTABLE").mean()), 1)
        results[model] = r

    # Buy & Hold Referenz (n_trials=1, wie im urspruenglichen Backlog-Test)
    results["buy_and_hold"] = compute_dsr(daily_ret.dropna().values, n_trials=1)

    with open("dsr_result.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
