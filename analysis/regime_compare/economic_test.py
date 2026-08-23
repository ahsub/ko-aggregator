"""
economic_test.py

Reproduziert die Methodik aus REGIME-BACKTEST-VALIDIERUNG.md (10.08.2026,
Ergebnis 2): Sharpe-artige Kennzahl (Mittelwert/Standardabweichung der
Vorwaertsrendite, annualisiert mit sqrt(252/h)) je Regime und Horizont
(5/10/21 Handelstage), auf Basis echter CBOE-Strategie-Indizes:

    PUT  -- CBOE S&P 500 PutWrite Index   (CSP/Wheel-Proxy)
    BXM  -- CBOE S&P 500 BuyWrite Index   (Covered-Call-Proxy)
    CLL  -- CBOE S&P 500 95-110 Collar Index (Collar/Protective-Put-Proxy)

Diesmal fuer regime_v1, regime_v2 UND das 5-Faktor-Modell auf demselben
Panel/Zeitraum -- die 10.08.-Validierung hat nur das 5-Faktor-Modell
getestet, dieser Lauf schliesst die Luecke fuer v1/v2 mit identischer
Methodik.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).parent.parent.parent / "data" / "raw_data"
HORIZONS = (5, 10, 21)


def _load_cboe_index(fname: str, col: str) -> pd.Series:
    df = pd.read_csv(RAW_DIR / fname)
    df["date"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y")
    s = df.set_index("date")[col].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def load_strategy_indices() -> pd.DataFrame:
    put = _load_cboe_index("PUT_History.csv", "PUT")
    bxm = _load_cboe_index("BXM_History.csv", "BXM")
    cll = _load_cboe_index("CLL_History.csv", "CLL")
    return pd.DataFrame({"PUT": put, "BXM": bxm, "CLL": cll})


def add_strategy_forward_returns(panel: pd.DataFrame, idx: pd.DataFrame) -> pd.DataFrame:
    df = panel.copy()
    aligned = idx.reindex(df.index)
    for name in ("PUT", "BXM", "CLL"):
        for h in HORIZONS:
            df[f"fwd_{name}_{h}d"] = aligned[name].shift(-h) / aligned[name] - 1
    return df


def sharpe_table(df: pd.DataFrame, regime_col: str) -> dict:
    result = {}
    for name in ("PUT", "BXM", "CLL"):
        for h in HORIZONS:
            col = f"fwd_{name}_{h}d"
            grp = df.groupby(regime_col)[col].agg(["mean", "std", "count"])
            for regime, row in grp.iterrows():
                if row["count"] < 20 or row["std"] == 0 or pd.isna(row["std"]):
                    continue
                sharpe = (row["mean"] / row["std"]) * np.sqrt(252 / h)
                result.setdefault(regime, {}).setdefault(name, {})[f"h{h}"] = round(float(sharpe), 2)
    return result


if __name__ == "__main__":
    import json
    from build_panel import build_unified_panel
    from classify import classify_v1_v2, classify_5factor

    p = build_unified_panel()
    p = classify_v1_v2(p)
    p = classify_5factor(p)

    idx = load_strategy_indices()
    print("[strategy indices]")
    for name in ("PUT", "BXM", "CLL"):
        s = idx[name].dropna()
        print(f"  {name}: {len(s)} Punkte, {s.index.min().date()} bis {s.index.max().date()}, "
              f"Abdeckung im Panel: {idx[name].reindex(p.index).notna().sum()}/{len(p)} Tage")

    p = add_strategy_forward_returns(p, idx)

    out = {
        "panel_info": {"n_days": len(p), "start": str(p.index.min().date()), "end": str(p.index.max().date())},
        "regime_v1": sharpe_table(p, "regime_v1"),
        "regime_v2": sharpe_table(p, "regime_v2"),
        "regime_5f": sharpe_table(p.dropna(subset=["regime_5f"]), "regime_5f"),
    }
    with open("economic_result.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
