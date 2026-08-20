"""
cboe_backfill.py

Zweck: CBOE-Rohdaten (data/raw_data/*.csv, siehe CBOE_DATA_SOURCES.md) als
bevorzugte, langfristig stabile Quelle für VIX/VVIX/SKEW im Research-/Backtest-
Kontext (voranalyse_regime.py) nutzen — mit Fallback auf fetch_yf_series(),
falls die CBOE-Datei fehlt.

WARUM NICHT market_aggregator.py::fetch_mse_history() ANFASSEN:
Diese Funktion lief seit dem 17.07.2026 auf eingefrorenen Daten (yf.download()-
Bug bei ^VIX3M/^VVIX/^SKEW), wurde aber am 18.-19.08.2026 bereits auf
yf.Ticker().history() umgestellt und dabei live bestätigt (siehe Changelog
v5.36.7-v5.36.9 in market_aggregator.py). Der Live-Pfad funktioniert also
wieder — PFLICHT-HEADER-Grundsatz "committed != deployed" hier andersherum
angewendet: bereits funktionierenden Live-Code NICHT anfassen, nur weil eine
alternative Quelle jetzt verfügbar ist. Das Risiko, den gerade erst reparierten
Live-Betrieb erneut zu brechen, überwiegt den Nutzen.

WAS STATTDESSEN GELÖST WIRD:
1. Der Backtest/Research-Pfad (voranalyse_regime.py) braucht KEINE Live-API,
   sondern eine möglichst lange, stabile Historie — dafür ist CBOE-CDN direkt
   besser geeignet als yfinance (keine Abhängigkeit von Yahoo-API-Launen,
   Historie bis 1990/2006 statt was yfinance gerade liefert).
2. Die eingefrorene Periode 2026-07-17 bis zum Live-Fix (~19.08.2026) bleibt
   in allem, was VOR diesem Patch aus yfinance geladen/gespeichert wurde,
   potenziell verfälscht (konstante Werte VVIX 104.87/SKEW 147.28 für diesen
   ganzen Zeitraum). Diese Datei stellt eine Cross-Check-Funktion bereit, um
   das zu erkennen (siehe check_frozen_window_contamination()).

Nutzung in voranalyse_regime.py:
    from cboe_backfill import fetch_cboe_or_yf_series
    vix_series = fetch_cboe_or_yf_series("vix", start="2007-01-01")
"""

from pathlib import Path
import pandas as pd
import logging

log = logging.getLogger("cboe_backfill")

RAW_DIR = Path("data/raw_data")

# Mapping auf dieselben Kurz-Keys wie YF_TICKERS in voranalyse_regime.py,
# damit fetch_cboe_or_yf_series() als Drop-in-Alternative zu fetch_yf_series()
# fungieren kann.
CBOE_FILES = {
    "vix": (RAW_DIR / "VIX_History.csv", "vix_close"),
    "vvix": (RAW_DIR / "VVIX_History.csv", "vvix_close"),
    "skew": (RAW_DIR / "SKEW_History.csv", "skew_close"),
}

FROZEN_WINDOW_START = "2026-07-17"
KNOWN_FROZEN_VALUES = {"vvix": 104.87, "skew": 147.28}  # aus market_aggregator.py-Changelog


def fetch_cboe_series(key: str, start: str = None) -> pd.Series | None:
    """Lädt eine VIX/VVIX/SKEW-Reihe aus den lokalen CBOE-Rohdaten.
    Gibt None zurück, wenn die Datei fehlt (Aufrufer soll dann auf
    fetch_yf_series() zurückfallen)."""
    if key not in CBOE_FILES:
        return None
    path, _ = CBOE_FILES[key]
    if not path.exists():
        log.info(f"  CBOE-Datei {path} nicht gefunden, kein Fallback moeglich")
        return None

    df = pd.read_csv(path)
    # VIX_History.csv hat OHLC-Spalten, VVIX/SKEW nur Close — beide Formate
    # kommen aus cboe_vol_loader.py bereits mit DATE/date-Spalte
    date_col = "date" if "date" in df.columns else "DATE"
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).set_index(date_col)

    close_col = "vix_close" if key == "vix" else f"{key}_close"
    if close_col not in df.columns:
        # Rohformat (noch nicht durch cboe_vol_loader.py bereinigt) —
        # Standardspalten CLOSE/DATE aus dem direkten CBOE-Download
        close_col = "CLOSE" if "CLOSE" in df.columns else key.upper()
    if close_col not in df.columns:
        log.warning(f"  CBOE-Datei {path}: Spalte fuer {key} nicht gefunden "
                    f"(verfuegbar: {list(df.columns)})")
        return None

    s = df[close_col].astype(float)
    if start:
        s = s[s.index >= pd.Timestamp(start)]
    return s


def fetch_cboe_or_yf_series(key: str, start: str, fetch_yf_series_fn=None) -> pd.Series:
    """Bevorzugt CBOE-Rohdaten, faellt auf fetch_yf_series() zurueck falls
    nicht vorhanden. fetch_yf_series_fn wird durchgereicht, um keinen
    zirkulaeren Import zwischen diesem Modul und voranalyse_regime.py zu
    erzeugen (dort einfach die eigene fetch_yf_series-Funktion uebergeben)."""
    cboe_series = fetch_cboe_series(key, start=start)
    if cboe_series is not None and len(cboe_series) > 0:
        log.info(f"  {key}: CBOE-Quelle genutzt ({len(cboe_series)} Tage, "
                 f"{cboe_series.index.min().date()} - {cboe_series.index.max().date()})")
        return cboe_series
    if fetch_yf_series_fn is not None:
        log.info(f"  {key}: CBOE-Datei nicht verfuegbar, Fallback auf yfinance")
        return fetch_yf_series_fn(key, start)
    raise FileNotFoundError(
        f"Keine CBOE-Datei fuer '{key}' gefunden und kein yfinance-Fallback uebergeben."
    )


def check_frozen_window_contamination(existing_series: pd.Series, key: str) -> dict:
    """Cross-Check: prueft, ob eine bereits vorhandene (z.B. gecachte oder aus
    einem frueheren Lauf gespeicherte) VVIX/SKEW-Reihe im Fenster ab
    2026-07-17 auffaellig konstant ist -- Symptom des bekannten yfinance-Bugs.
    Gibt KEINE automatische Korrektur, nur einen Befund zum manuellen Review
    (PFLICHT-HEADER: verifizieren, nicht automatisch uebernehmen)."""
    if key not in KNOWN_FROZEN_VALUES:
        return {"checked": False, "reason": f"kein bekannter Frozen-Wert fuer '{key}'"}

    window = existing_series[existing_series.index >= pd.Timestamp(FROZEN_WINDOW_START)]
    if len(window) == 0:
        return {"checked": True, "contaminated": False, "reason": "kein Datum im Fenster vorhanden"}

    known_val = KNOWN_FROZEN_VALUES[key]
    n_matching = (window.round(2) == known_val).sum()
    contaminated = n_matching > 1  # ein zufaelliger Treffer ist plausibel, viele nicht

    return {
        "checked": True,
        "contaminated": bool(contaminated),
        "window_start": FROZEN_WINDOW_START,
        "window_len": len(window),
        "n_matching_frozen_value": int(n_matching),
        "known_frozen_value": known_val,
        "recommendation": (
            f"Vermutlich kontaminiert — {n_matching}/{len(window)} Werte im Fenster "
            f"entsprechen dem bekannten eingefrorenen Wert {known_val}. Diese Periode "
            f"sollte mit fetch_cboe_series('{key}') neu geladen und ersetzt werden."
            if contaminated else
            "Keine auffaellige Haeufung des bekannten Frozen-Werts gefunden."
        ),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for k in ["vix", "vvix", "skew"]:
        s = fetch_cboe_series(k)
        if s is not None:
            print(f"{k}: {len(s)} Tage, {s.index.min().date()} - {s.index.max().date()}, "
                  f"letzter Wert: {s.iloc[-1]}")
        else:
            print(f"{k}: keine CBOE-Datei gefunden unter {CBOE_FILES[k][0]}")
