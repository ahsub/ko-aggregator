"""
voranalyse_regime.py

REKONSTRUKTION (18.08.2026-Session, aus Chatverlauf wiederhergestellt,
da das Original nie committed wurde). Siehe Hinweis-Block am Dateiende
fuer Konfidenzeinstufung -- NICHT ungeprueft committen.

Multivariate Voranalyse der Marktregime-Indikatoren: Korrelation (Pearson/
Spearman) + VIF, Feature-Importance via Random Forest (Regime-Klassifikation
UND Forward-Return/-Sharpe-Regression, 21d/63d Horizonte), Granger-Kausalitaet
fuer Fruehindikator-Kandidaten. Datenquellen: FRED (Konjunktur), yfinance
(Markt-/Volatilitaetsindizes), squeezemetrics (DIX/GEX-Vollhistorie seit 2011).

Zwei Analysefenster:
    Fenster A: ab 2007, OHNE DIX/GEX (laengere Historie)
    Fenster B: ab 2011, MIT DIX/GEX-Vollhistorie (squeezemetrics)

Publikationsverzug (Publication Lag) je FRED-Serie wird als fester
Tage-Offset approximiert (pragmatische Naeherung, KEIN vollstaendiges
ALFRED-Vintage-Fetching -- so im Original dokumentiert).

WICHTIGER FUND waehrend der Original-Session: hy_spread (FRED-Serie
BAMLH0A0HYM2, ICE BofA High Yield OAS) ist seit April 2026 lizenzbedingt
auf ein rollierendes 3-Jahres-Fenster beschraenkt (nur ~793 Beobachtungen
ab 2023-08-18) -- deshalb in SHORT_HISTORY_FEATURES separiert und in einem
eigenen Sub-Fenster ausgewertet, statt das Hauptpanel per dropna() auf
~707 Beobachtungen zu verkuerzen.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# [REKONSTRUKTION, mittlere Konfidenz -- exakte Ticker-Liste nicht
# woertlich im Chatverlauf gefunden, nur einzelne Verwendungen (vix,
# vix3m, vvix, skew, move, xlp, xly, iwf, iwd, spy). Vor Verwendung
# gegen panel_A_2007_no_dixgex.csv / panel_B_2011_with_dixgex.csv
# (lokal bei Axel) abgleichen -- Spaltennamen muessen uebereinstimmen.]
YF_TICKERS = {
    "vix": "^VIX",
    "vix3m": "^VIX3M",
    "vvix": "^VVIX",
    "skew": "^SKEW",
    "move": "^MOVE",
    "xlp": "XLP",
    "xly": "XLY",
    "iwf": "IWF",
    "iwd": "IWD",
    "spy": "SPY",
}

# [HOHE KONFIDENZ -- woertlich aus str_replace-Edit im Chatverlauf
# rekonstruiert, inkl. Original-Kommentare zu Publikationsverzug/Frequenz.
# Bestaetigt durch einen tatsaechlichen Live-Fehlerlauf im selben Chat
# (400 Bad Request fuer alle sechs Serien wegen ungueltigem API-Key --
# die Series-IDs selbst wurden dabei korrekt an die FRED-API uebergeben,
# das bestaetigt ihre Korrektheit unabhaengig von der Quelle im Diff).]
FRED_SERIES = {
    # id                  lag_days  Begruendung
    "nfci":            dict(id="NFCI",               lag_days=7,  freq="weekly",
                             note="Chicago Fed, woechentlich Freitags, i.d.R. mit "
                                  "~1 Woche Verzug veroeffentlicht"),
    "core_cpi_yoy":    dict(id="CPILFESL",            lag_days=15, freq="monthly",
                             note="BLS CPI-Report i.d.R. Mitte Folgemonat"),
    "sahm_rule":       dict(id="SAHMREALTIME",        lag_days=5,  freq="monthly",
                             note="Real-Time-Sahm-Serie, folgt kurz nach BLS-"
                                  "Arbeitsmarktbericht (1. Freitag im Monat)"),
    "oecd_cli":        dict(id="USALOLITOAASTSAM",    lag_days=45, freq="monthly",
                             note="OECD Composite Leading Indicator, "
                                  "typischerweise ~6 Wochen Verzug"),
    "heavy_truck":     dict(id="HTRUCKSSAAR",         lag_days=20, freq="monthly",
                             note="BEA/Wards, i.d.R. Anfang uebernaechster Monat"),
    "hy_spread":       dict(id="BAMLH0A0HYM2",        lag_days=1,  freq="daily",
                             note="ICE BofA, taeglich mit 1 Tag Verzug"),
}

# [HOHE KONFIDENZ -- woertlich aus demselben Fund rekonstruiert. Ersetzt
# das vorherige YF_TICKERS-Dict weiter unten in dieser Datei nicht direkt
# (Struktur ist inhaltlich identisch, hier nur mit Original-Reihenfolge/
# -Kommentar uebernommen).]
DIX_GEX_CSV_URL = "https://squeezemetrics.com/monitor/static/DIX.csv"
REGIME_CLASSES = ["STRESS_UNSTABLE", "POST_PANIC_REVERSION", "BULL_FRAGILE", "BULL_QUIET"]

SHORT_HISTORY_FEATURES = ["hy_spread"]  # s. Docstring oben: 3-Jahres-Limit seit April 2026


def fetch_yf_series(ticker: str, start: str) -> pd.Series:
    """[REKONSTRUKTION, mittlere Konfidenz -- nur Signatur/Verwendung
    (fetch_yf_series("^VIX", start=start) -> pd.Series) im Chatverlauf
    belegt, nicht der Funktionskoerper selbst. Naheliegende yfinance-
    Standardimplementierung nachgebaut; vor Verwendung gegen echten
    Output pruefen (insbesondere: Close vs. Adj Close, Zeitzonenbehandlung).]
    """
    import yfinance as yf

    data = yf.download(ticker, start=start, progress=False, auto_adjust=True)
    if data.empty:
        raise ValueError(f"Keine Daten fuer Ticker {ticker} ab {start}")
    series = data["Close"]
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    series.name = ticker
    series.index = pd.to_datetime(series.index).tz_localize(None)
    return series


def fetch_dix_gex_full_history() -> pd.DataFrame:
    """[REKONSTRUKTION, mittlere Konfidenz -- URL-Detail (Gross-/
    Kleinschreibung DIX.csv) aus einer SPAETEREN Bugfix-Session bekannt
    (market_aggregator.py verwendete zunaechst faelschlich 'dix.csv'
    klein geschrieben -> HTTP 404, korrigiert auf 'DIX.csv'). Ob
    voranalyse_regime.py von Anfang an die korrekte Gross-/Kleinschreibung
    nutzte, ist NICHT gesichert -- hier mit der bekannt korrekten Version
    rekonstruiert. Gibt die VOLLE Historie zurueck (nicht nur die letzte
    Zeile wie die Produktionsfunktion in market_aggregator.py), da diese
    Funktion fuer eine Zeitreihenanalyse ab 2011 gedacht ist.]
    """
    url = "https://squeezemetrics.com/monitor/static/DIX.csv"
    r = requests.get(url, timeout=30, headers={"User-Agent": "curl/8.5.0"})
    r.raise_for_status()
    from io import StringIO
    df = pd.read_csv(StringIO(r.text))
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df["dix"] = df["dix"].astype(float)
    df["gex"] = df["gex"].astype(float)
    return df[["dix", "gex"]]


def fetch_fred_series(series_id: str, api_key: str, limit: int = 20000) -> pd.Series:
    """Volle Historie einer FRED-Serie, aelteste zuerst. Gibt pd.Series (date-idx) zurueck.

    [HOHE KONFIDENZ fuer Signatur (woertlich gefunden: "def fetch_fred_series
    (series_id: str, api_key: str, limit: int = 20000) -> pd.Series") und
    fuer die Query-Parameter sort_order/limit -- diese sind aus einem
    ECHTEN Fehlerlog derselben Session belegt (400 Bad Request-Meldungen
    zeigten die vollstaendige angefragte URL inkl. aller Parameter:
    ".../observations?series_id=NFCI&api_key=...&file_type=json&
    sort_order=asc&limit=20000"). Funktionskoerper selbst (Docstring-Inhalt
    danach) ist eine plausible Standardimplementierung, nicht woertlich
    verifiziert.]
    """
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "asc",
        "limit": limit,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    obs = data.get("observations", [])
    dates = pd.to_datetime([o["date"] for o in obs])
    values = [np.nan if o["value"] == "." else float(o["value"]) for o in obs]
    series = pd.Series(values, index=dates, name=series_id).sort_index()
    return series


def compute_regime_labels(vix: pd.Series, vix3m: pd.Series) -> pd.Series:
    """Exakte Rekonstruktion der Produktionsformel (market_aggregator.py Z.8510-8540).

    [HOHE KONFIDENZ -- woertlich aus str_replace-Edit im Chatverlauf
    rekonstruiert.]
    """
    df = pd.concat([vix.rename("vix"), vix3m.rename("vix3m")], axis=1).dropna()
    ratio = df["vix3m"] / df["vix"]

    def _classify(row):
        r, v = row["ratio"], row["vix"]
        if r < 0.98:
            return "STRESS_UNSTABLE"
        elif r < 1.05:
            return "POST_PANIC_REVERSION"
        elif v > 25:
            return "BULL_FRAGILE"
        else:
            return "BULL_QUIET"

    df["ratio"] = ratio
    labels = df.apply(_classify, axis=1)
    labels.name = "regime"
    return labels


def align_with_lag(series: pd.Series, lag_days: int, target_index: pd.DatetimeIndex) -> pd.Series:
    """Verschiebt eine Serie um lag_days (Publikationsverzug) und forward-fillt
    auf den Ziel-Handelskalender -- ohne Look-Ahead: ein Wert ist erst AB
    (Berichtsdatum + lag_days) sichtbar.

    [HOHE KONFIDENZ fuer Signatur/Docstring -- woertlich im Chatverlauf
    gefunden. Funktionskoerper teilweise rekonstruiert (letzte Zeilen
    des Original-Diffs abgeschnitten im Suchergebnis) -- Grundmuster
    (Shift, Reindex-Union, ffill, Reindex auf target_index) ist aus dem
    sichtbaren Fragment ableitbar und hier vervollstaendigt.]
    """
    shifted = series.copy()
    shifted.index = shifted.index + pd.Timedelta(days=lag_days)
    aligned = shifted.reindex(shifted.index.union(target_index)).sort_index()
    aligned = aligned.ffill()
    return aligned.reindex(target_index)


def build_panel(fred_key: str, include_dixgex: bool, start: str) -> pd.DataFrame:
    """[HOHE KONFIDENZ -- Kernstruktur woertlich aus str_replace-Edit im
    Chatverlauf rekonstruiert. YF_TICKERS/FRED_SERIES-Dict-Inhalte oben
    sind Platzhalter (niedrige Konfidenz), die Verwendung hier ist aber
    original.]
    """
    print(f"[fetch] yfinance-Ticker ({start}+)...", file=sys.stderr)
    yf_data = {name: fetch_yf_series(ticker, start=start) for name, ticker in YF_TICKERS.items()}

    print("[fetch] Regime-Ground-Truth (VIX/VIX3M)...", file=sys.stderr)
    regime = compute_regime_labels(yf_data["vix"], yf_data["vix3m"])
    trading_days = regime.index

    panel = pd.DataFrame(index=trading_days)
    panel["regime"] = regime
    panel["vix"] = yf_data["vix"].reindex(trading_days)
    panel["vix3m"] = yf_data["vix3m"].reindex(trading_days)
    panel["vvix"] = yf_data["vvix"].reindex(trading_days)
    panel["skew"] = yf_data["skew"].reindex(trading_days)
    panel["move"] = yf_data["move"].reindex(trading_days)
    panel["staples_discretionary"] = (yf_data["xlp"] / yf_data["xly"]).reindex(trading_days)
    panel["growth_value"] = (yf_data["iwf"] / yf_data["iwd"]).reindex(trading_days)

    # Forward-Returns / Forward-Sharpe fuer die Regressions-Zielgroesse
    spy = yf_data["spy"].reindex(trading_days)
    fwd_ret_21 = spy.shift(-21) / spy - 1
    daily_ret = spy.pct_change()
    fwd_sharpe_21 = (
        daily_ret.shift(-21).rolling(21).mean() / daily_ret.shift(-21).rolling(21).std()
    ) * np.sqrt(252)
    panel["fwd_return_21d"] = fwd_ret_21
    panel["fwd_sharpe_21d"] = fwd_sharpe_21
    # [LUECKE: 63d-Horizont wird laut Session-Zusammenfassung ebenfalls
    # ausgewertet ("21-day and 63-day horizons"), im gefundenen Fragment
    # aber nur 21d verbatim sichtbar. 63d-Aequivalent hier ergaenzt:]
    fwd_ret_63 = spy.shift(-63) / spy - 1
    fwd_sharpe_63 = (
        daily_ret.shift(-63).rolling(63).mean() / daily_ret.shift(-63).rolling(63).std()
    ) * np.sqrt(252)
    panel["fwd_return_63d"] = fwd_ret_63
    panel["fwd_sharpe_63d"] = fwd_sharpe_63

    if fred_key:
        print("[fetch] FRED-Serien...", file=sys.stderr)
        for name, cfg in FRED_SERIES.items():
            try:
                raw = fetch_fred_series(cfg["id"], fred_key)
                panel[name] = align_with_lag(raw, cfg["lag_days"], trading_days)
            except Exception as e:
                print(f"  WARNUNG: {name} ({cfg['id']}) fehlgeschlagen: {e}", file=sys.stderr)
    else:
        print("[skip] FRED_API_KEY nicht gesetzt -- Konjunkturindikatoren uebersprungen", file=sys.stderr)

    if include_dixgex:
        print("[fetch] DIX/GEX-Volltilgung (squeezemetrics)...", file=sys.stderr)
        dg = fetch_dix_gex_full_history()
        panel["dix"] = dg["dix"].reindex(panel.index, method=None)
        panel["gex"] = dg["gex"].reindex(panel.index, method=None)
        # DIX/GEX ist selbst schon "heute" ohne Meldeverzug (taeglich, EOD) --
        # kein zusaetzlicher Lag noetig, nur ffill ueber evtl. fehlende Handelstage.
        panel["dix"] = panel["dix"].ffill()
        panel["gex"] = panel["gex"].ffill()

    return panel


# ============================================================================
# [LUECKE, nicht rekonstruiert: Die drei Analyseschritte (Pearson/Spearman-
# Korrelation + VIF, Random-Forest-Feature-Importance fuer Klassifikation
# UND Regression, Granger-Kausalitaet) sowie main()/CLI-Einstiegspunkt
# wurden im Chatverlauf nicht in ausreichender woertlicher Tiefe gefunden,
# um sie verantwortbar zu rekonstruieren. Bekannt aus der Session-
# Zusammenfassung: Ergebnisse wurden in zwei Fenstern berechnet (Fenster A
# ab 2007 ohne DIX/GEX, Fenster B ab 2011 mit DIX/GEX), GEX rangierte als
# zweitwichtigstes Feature (Importance 0.287, hinter VVIX 0.189), alle
# 8 Regressionslaeufe (Return/Sharpe x 21d/63d x zwei Fenster) lieferten
# negative cross-validierte R^2 (kein verlaesslicher Out-of-Sample-Wert),
# oecd_cli zeigte VIF > 900-1300 gegenueber core_cpi_yoy (auch bei
# monatlicher Frequenz bestaetigt, kein Forward-Fill-Artefakt).
#
# NAECHSTER SCHRITT: Falls diese Datei reaktiviert werden soll, muessten
# die drei Analysefunktionen neu geschrieben werden (nicht rekonstruiert)
# -- Statistik-Werkzeuge dafuer: statsmodels (VIF via
# variance_inflation_factor, Granger via grangercausalitytests),
# scikit-learn (RandomForestClassifier/-Regressor,
# cross_val_score/permutation_importance).
# ============================================================================


# ============================================================================
# REKONSTRUKTIONS-HINWEIS (nicht Teil des Original-Skripts, hier zur
# Transparenz angehaengt -- vor Commit ggf. entfernen oder in eine separate
# Notiz auslagern):
#
# Diese Datei wurde am 18.08.2026 nachtraeglich aus dem Chatverlauf derselben
# Session rekonstruiert, da das Original nie ins Repo committed wurde.
#
# HOHE KONFIDENZ (woertlich rekonstruiert): compute_regime_labels(),
# align_with_lag() Signatur+Docstring, build_panel() Kernstruktur,
# FRED_SERIES-Dict (alle 6 Series-IDs inkl. lag_days/freq/note woertlich
# gefunden UND durch echten Fehlerlog derselben Session bestaetigt --
# 400-Bad-Request-Meldungen zeigten die Series-IDs korrekt in der
# angefragten URL), fetch_fred_series() Signatur + Query-Parameter
# (sort_order=asc, limit=20000 -- ebenfalls aus dem Fehlerlog belegt),
# DIX_GEX_CSV_URL, REGIME_CLASSES.
#
# MITTLERE KONFIDENZ (aus Verwendungsmustern/spaeteren Bugfix-Sessions
# abgeleitet, nicht woertlich gefunden): fetch_yf_series() Funktionskoerper,
# fetch_dix_gex_full_history() Funktionskoerper, fetch_fred_series()
# Funktionskoerper (Signatur/Params sind hohe Konfidenz, der Rest ist
# Standardimplementierung), align_with_lag() Funktionskoerper-Ende,
# fwd_return_63d/fwd_sharpe_63d in build_panel(), YF_TICKERS-Dict
# (Ticker-Auswahl plausibel aus Verwendung abgeleitet, exakte Dict-Syntax
# nicht 1:1 verifiziert).
#
# BEKANNTER, ECHTER FEHLERZUSTAND aus der Original-Session (zur Erinnerung,
# nicht mehr relevant nach FRED-Key-Fix): Der urspruengliche FRED_API_KEY
# war ungueltig (19-stellige Zahl statt 32-stelligem alphanumerischem
# Key) -- alle 6 FRED-Abrufe scheiterten mit HTTP 400. Axel besorgte einen
# gueltigen Key von fred.stlouisfed.org, danach lief der Abruf. Fehlend
# war zudem zunaechst das Paket statsmodels (ModuleNotFoundError) --
# beide Fixes sind hier nicht relevant, nur zur Einordnung des Fehlerlogs,
# aus dem die FRED_SERIES-Bestaetigung stammt.
#
# FEHLEND (nicht rekonstruiert): Die drei Analysefunktionen (Korrelation/
# VIF, Random-Forest-Feature-Importance, Granger-Kausalitaet) und main().
#
# EMPFOHLENER NAECHSTER SCHRITT VOR COMMIT: NICHT direkt committen. Diese
# Datei ist eine Gedaechtnisstuetze / ein Ausgangspunkt fuer eine neue
# Session, nicht ein lauffaehiges Reproduktions-Skript. Die eigentlichen
# Ergebnisse (GEX Rang 2, oecd_cli-Kollinearitaet, negative Regressions-R^2)
# sind bereits gesichert in den Uebergabeprotokollen/REGIME-BACKTEST-
# VALIDIERUNG.md -- diese Rekonstruktion sollte diese Dokumentation nicht
# ersetzen, sondern hoechstens als Code-Geruest fuer eine spaetere,
# bewusst neu aufgesetzte Session dienen.
# ============================================================================
