"""
cboe_vol_loader.py

Lädt VIX/VVIX/SKEW aus lokalen CBOE-CSV-Rohdaten (ahsub/ko-aggregator/data/raw_data/)
und baut/aktualisiert das Master-Panel cboe_vol_panel_daily.csv.

Hintergrund: yfinance-interner Endpoint für VVIX/SKEW war seit 2026-07-17 eingefroren
(siehe UIQ-Blocker "Top of mind"). Diese Daten kommen stattdessen direkt von CBOE.

Quellen (siehe CBOE_DATA_SOURCES.md für Details/Rechercheweg):
  VIX:  https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
  VVIX: https://cdn.cboe.com/api/global/us_indices/daily_prices/VVIX_History.csv
  SKEW: https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv
  SKEW Term Structure: https://cdn.cboe.com/resources/indices/documents/skewtermstructure.csv

PFLICHTHEADER: committed != deployed. Vor Produktivnutzung mit voranalyse_regime.py /
market_aggregator.py verifizieren, dass der Join korrekt greift und keine stillen
NaN-Lücken entstehen (siehe diagnose_coverage()).
"""

from pathlib import Path
import pandas as pd
import numpy as np

RAW_DIR = Path("data/raw_data")
OUT_PANEL = Path("data/cboe_vol_panel_daily.csv")

VIX_FILE = RAW_DIR / "VIX_History.csv"
VVIX_FILE = RAW_DIR / "VVIX_History.csv"
SKEW_FILE = RAW_DIR / "SKEW_History.csv"
SKEW_TERM_FILE = RAW_DIR / "skewtermstructure.csv"


def _load_vix(path: Path = VIX_FILE) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["DATE"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y")
    df = df.sort_values("DATE").reset_index(drop=True)
    df.columns = ["date", "vix_open", "vix_high", "vix_low", "vix_close"]
    return df


def _load_vvix(path: Path = VVIX_FILE) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["DATE"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y")
    df = df.sort_values("DATE").reset_index(drop=True)
    df.columns = ["date", "vvix_close"]
    return df


def _load_skew(path: Path = SKEW_FILE) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["DATE"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y")
    df = df.sort_values("DATE").reset_index(drop=True)
    df.columns = ["date", "skew_close"]
    return df


def _load_skew_term_structure(path: Path = SKEW_TERM_FILE) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = ["date", "expiration", "skew_term_structure"]
    df["date"] = pd.to_datetime(df["date"])
    df["expiration"] = pd.to_datetime(df["expiration"])
    # bekanntes CBOE-Rohdatenproblem: vereinzelt "." statt Zahl
    n_before = len(df)
    df["skew_term_structure"] = pd.to_numeric(df["skew_term_structure"], errors="coerce")
    n_bad = df["skew_term_structure"].isna().sum()
    if n_bad:
        print(f"[cboe_vol_loader] {n_bad}/{n_before} SKEW-Term-Structure-Werte "
              f"waren fehlerhaft ('.') und wurden als NaN behandelt.")
    df = df.dropna(subset=["skew_term_structure"])
    df["dte"] = (df["expiration"] - df["date"]).dt.days
    return df


def _constant_maturity_30d(group: pd.DataFrame, target: int = 30) -> float:
    """Lineare Interpolation der SKEW-Term-Structure auf konstante Restlaufzeit
    (analog zur Standard-VIX-Konstruktionsmethode)."""
    g = group.sort_values("dte")
    below = g[g["dte"] <= target]
    above = g[g["dte"] >= target]
    if len(below) == 0 or len(above) == 0:
        return np.nan
    exact = g[g["dte"] == target]
    if len(exact):
        return exact["skew_term_structure"].iloc[0]
    d1, v1 = below.iloc[-1][["dte", "skew_term_structure"]]
    d2, v2 = above.iloc[0][["dte", "skew_term_structure"]]
    if d1 == d2:
        return v1
    w = (target - d1) / (d2 - d1)
    return v1 + w * (v2 - v1)


def build_panel(
    vix_path: Path = VIX_FILE,
    vvix_path: Path = VVIX_FILE,
    skew_path: Path = SKEW_FILE,
    skew_term_path: Path = SKEW_TERM_FILE,
    target_dte: int = 30,
) -> pd.DataFrame:
    """Baut das gemeinsame Tages-Panel aus den vier CBOE-Rohdateien."""
    vix = _load_vix(vix_path)
    vvix = _load_vvix(vvix_path)
    skew = _load_skew(skew_path)
    sts = _load_skew_term_structure(skew_term_path)

    cm = (
        sts.groupby("date")
        .apply(lambda g: _constant_maturity_30d(g, target_dte), include_groups=False)
        .reset_index()
    )
    cm.columns = ["date", f"skew_cm{target_dte}"]
    cm = cm.dropna()

    panel = (
        vix.merge(vvix, on="date", how="outer")
        .merge(skew, on="date", how="outer")
        .merge(cm, on="date", how="outer")
        .sort_values("date")
        .reset_index(drop=True)
    )
    return panel


def diagnose_coverage(panel: pd.DataFrame, tail_n: int = 30) -> None:
    """Schneller Soll-Ist-Check nach jedem Refresh — vor Produktivnutzung laufen lassen."""
    print(f"Panel: {panel['date'].min().date()} -> {panel['date'].max().date()}, "
          f"{len(panel)} Zeilen")
    print("\nGesamt-Coverage (nicht-NaN je Spalte):")
    print(panel.set_index("date").notna().sum())
    print(f"\nLetzte {tail_n} Zeilen — fehlende Werte je Spalte:")
    print(panel.tail(tail_n).isna().sum())
    gaps = panel["date"].diff().dt.days
    big_gaps = panel.loc[gaps > 5, "date"]
    if len(big_gaps):
        print(f"\nACHTUNG: {len(big_gaps)} Datumslücken > 5 Tage gefunden, z.B.:")
        print(big_gaps.head(10).tolist())


def load_or_build(
    out_path: Path = OUT_PANEL,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    """Einstiegspunkt für market_aggregator.py / voranalyse_regime.py:
    lädt das fertige Panel, falls vorhanden, oder baut es aus den Rohdaten neu."""
    if out_path.exists() and not force_rebuild:
        panel = pd.read_csv(out_path, parse_dates=["date"])
        return panel
    panel = build_panel()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out_path, index=False, date_format="%Y-%m-%d")
    return panel


if __name__ == "__main__":
    panel = build_panel()
    diagnose_coverage(panel)
    OUT_PANEL.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUT_PANEL, index=False, date_format="%Y-%m-%d")
    print(f"\nGespeichert: {OUT_PANEL}")
