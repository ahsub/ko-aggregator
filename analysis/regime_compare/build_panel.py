"""
build_panel.py

Vereinheitlichte Datenbasis fuer den fairen regime_v2- vs. 5-Faktor-Vergleich.
Liest ausschliesslich die am 20.-23.08.2026 committeten CBOE/DIX-GEX-Rohdateien
aus ahsub/ko-aggregator/data/raw_data/ -- keine Live-API-Calls, kein yfinance,
kein squeezemetrics-Live-Fetch. Alle Werte primaerquellenbasiert (CBOE-CDN,
SqueezeMetrics-Bulk-Export), von Axel besorgt und verifiziert (s. Chat
23.08.2026).

Quelle je Datei (data/raw_data/):
    VIX_History.csv    -- date, vix_open/high/low/close        (CBOE, 1990-2026)
    VIX3M_History.csv  -- DATE, OPEN/HIGH/LOW/CLOSE (MM/DD/YYYY)(CBOE, 2009-2026)
    VVIX_History.csv   -- date, vvix_close                      (CBOE, 2006-2026)
    SKEW_History.csv   -- date, skew_close                      (CBOE, 1990-2026)
    SKEW_cm30.csv       -- date, skew_cm30 (30T-konstante Restlaufzeit, interpoliert)
    DIX_GEX_History.csv -- date, price, dix, gex                (SqueezeMetrics, 2011-2026)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).parent.parent.parent / "data" / "raw_data"


def _load_std(fname: str, value_col: str) -> pd.Series:
    df = pd.read_csv(RAW_DIR / fname)
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date")[value_col].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def _load_vix3m() -> pd.Series:
    df = pd.read_csv(RAW_DIR / "VIX3M_History.csv")
    df["date"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y")
    s = df.set_index("date")["CLOSE"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s.name = "vix3m"
    return s


def _load_dixgex() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "DIX_GEX_History.csv")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df[["price", "dix", "gex"]].astype(float)


def build_unified_panel(start: str = "2011-05-02", end: str | None = None) -> pd.DataFrame:
    """Ein gemeinsames Tagespanel, ausschliesslich aus den committeten
    CBOE/DIX-GEX-Rohdateien. Startdatum standardmaessig auf DIX/GEX-
    Verfuegbarkeit begrenzt (2011-05-02), da beide zu vergleichenden Modelle
    GEX brauchen (regime_v2 als Override, das 5-Faktor-Modell als
    gex_z20-Input) -- ein Vergleich ohne GEX waere fuer keins der beiden
    Modelle repraesentativ.
    """
    vix = _load_std("VIX_History.csv", "vix_close")
    vix3m = _load_vix3m()
    vvix = _load_std("VVIX_History.csv", "vvix_close")
    skew = _load_std("SKEW_History.csv", "skew_close")
    dg = _load_dixgex()

    # Handelskalender: Schnittmenge aus VIX und VIX3M (beide fuer die
    # Ratio-Berechnung zwingend), danach auf den DIX/GEX-Zeitraum begrenzt.
    idx = vix.index.intersection(vix3m.index)
    idx = idx[(idx >= start) & (idx <= (end or idx.max()))]
    idx = idx.intersection(dg.index.union(idx))  # DIX/GEX wird geffillt, nicht geschnitten

    panel = pd.DataFrame(index=sorted(idx))
    panel["vix"] = vix.reindex(panel.index)
    panel["vix3m"] = vix3m.reindex(panel.index)
    panel["vvix"] = vvix.reindex(panel.index)
    panel["skew"] = skew.reindex(panel.index)
    # DIX/GEX: ffill ueber Nicht-Handelstage der Quelle (taeglich publiziert,
    # kein struktureller Grund fuer Luecken innerhalb des Handelskalenders)
    panel["dix"] = dg["dix"].reindex(panel.index).ffill()
    panel["gex"] = dg["gex"].reindex(panel.index).ffill()
    panel["price"] = dg["price"].reindex(panel.index).ffill()

    before = len(panel)
    panel = panel.dropna(subset=["vix", "vix3m", "vvix", "skew", "dix", "gex", "price"])
    after = len(panel)
    print(f"[panel] {after} Handelstage vollstaendig ({before - after} wegen fehlender "
          f"Werte verworfen), {panel.index.min().date()} bis {panel.index.max().date()}")

    return panel


if __name__ == "__main__":
    p = build_unified_panel()
    p.to_csv(Path(__file__).parent / "unified_panel.csv")
    print(p.tail(3))
    print(p.describe())
