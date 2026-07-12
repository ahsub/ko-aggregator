#!/usr/bin/env python3
"""
UIQ IV-Archiv — Implied Volatility Point-in-Time Sammler (Options-Modul Phase 0)
==================================================================================
Version 1.0 (12.07.2026) | Konzept: SUITE.md #15, STRATEGIE.md #15

ZWECK: IV-Rank und IV-Percentile sind die wichtigste Einzelkennzahl für
Wheel/CSP/CC-Einstiegstiming ("Prämie verkaufen wenn IV-Rank hoch"). Da
historische IV-Zeitreihen nicht rückwirkend beschaffbar sind, archiviert
dieses Modul täglich den ATM-IV-Snapshot pro Ticker — analog dem FIN-Archiv-
Ansatz für Fundamentaldaten. Nach ~30 Tagen: IV-Rank (30T), nach ~63 Tagen:
IV-Percentile (63T), nach 252 Tagen: volles IBD-konformes Ranking.

METHODIK:
  ATM-IV: Front-Month-Optionskette via yfinance (.options + .option_chain()),
  Call- und Put-IV der nächstgelegenen ATM-Strikes gemittelt. Nur US-Aktien
  (kein "." oder "-" im Ticker), nur wenn Optionskette verfügbar und liquide
  (mind. 1 Expiry in den nächsten 60 Tagen).

ABLAUF (täglich, Mo–Fr):
  - ATM-IV pro Ticker → data/iv_history/YYYY-MM-DD.json (Git-Commit)
  - Aus dem wachsenden Archiv: ivRank (0-100) + ivPercentile (0-100)
    werden berechnet und in results[] zurückgeschrieben.
  - Status landet in master["ivArchive"].

FEHLERPHILOSOPHIE: identisch zu fin_layer / tr_layer — bricht den Hauptlauf
niemals. Einzelne Ticker-Fehler werden geloggt, Archiv-Run läuft weiter.

IV-RANK vs. IV-PERCENTILE:
  ivRank       = (aktuelle IV - Min252) / (Max252 - Min252) * 100
                 Wo liegt IV zwischen Extremen? (tastytrade-Standard)
  ivPercentile = Anteil der Tage in 252T-Fenster mit IV < aktueller IV * 100
                 Wie viele Tage war IV niedriger? (IBD/TOS-Standard)
  Beide werden berechnet sobald ≥30 Archiv-Tage vorhanden.
"""

import os
import json
import logging
import glob
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger("aggregator")

IV_SCHEMA_VERSION   = 1
IV_ARCHIVE_DIR      = "data/iv_history"
IV_FETCH_WORKERS    = 8    # parallel Optionsketten-Calls (langsamer als Kursdaten)
IV_MIN_RANK_DAYS    = 30   # Minimum Archiv-Tage für IV-Rank-Ausgabe
IV_FULL_WINDOW_DAYS = 252  # Ziel-Fenster (1 Handelsjahr)


# ── ATM-IV Berechnung ──────────────────────────────────────────────────────────

def _fetch_atm_iv(ticker: str, current_price: float) -> dict | None:
    """
    Holt die ATM-IV für einen Ticker aus der Front-Month-Optionskette (yfinance).
    Gibt None zurück bei Fehler oder fehlender Optionskette.
    Rückgabe: {"iv": float, "expiry": str, "dte": int, "source": "yf_options"}
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        exps = t.options          # Liste verfügbarer Expiries (Strings "YYYY-MM-DD")
        if not exps:
            return None

        today = datetime.now(timezone.utc).date()

        # Front-Month: erste Expiry zwischen 7 und 60 Tagen (kein Weekly-Noise,
        # kein zu weit entferntes Expiry mit thin Bid/Ask)
        target_exp = None
        target_dte = None
        for exp_str in exps:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if 7 <= dte <= 60:
                target_exp = exp_str
                target_dte = dte
                break

        if target_exp is None:
            return None

        chain = t.option_chain(target_exp)
        calls = chain.calls
        puts  = chain.puts

        if calls.empty or puts.empty:
            return None

        # ATM-Strike: nächstgelegener Strike zum aktuellen Kurs
        if "strike" not in calls.columns or "impliedVolatility" not in calls.columns:
            return None

        # Berechne Distanz zum aktuellen Kurs für Calls + Puts
        calls = calls.copy()
        puts  = puts.copy()
        calls["dist"] = (calls["strike"] - current_price).abs()
        puts["dist"]  = (puts["strike"]  - current_price).abs()

        atm_call = calls.nsmallest(1, "dist").iloc[0]
        atm_put  = puts.nsmallest(1, "dist").iloc[0]

        call_iv = float(atm_call["impliedVolatility"])
        put_iv  = float(atm_put["impliedVolatility"])

        # Sanity: yfinance liefert manchmal 0 oder sehr große Werte bei dünnen Märkten
        if call_iv <= 0 or put_iv <= 0 or call_iv > 5.0 or put_iv > 5.0:
            return None

        # Mittelwert Call/Put ATM-IV (Put/Call-Parität → sollten nahe beieinander sein)
        atm_iv = round((call_iv + put_iv) / 2 * 100, 2)  # in Prozent speichern

        return {
            "iv":     atm_iv,
            "expiry": target_exp,
            "dte":    target_dte,
            "source": "yf_options",
        }

    except Exception as e:
        log.debug(f"  [IV] {ticker}: {e}")
        return None


# ── Archiv lesen / schreiben ───────────────────────────────────────────────────

def _load_archive() -> dict:
    """
    Lädt alle täglichen IV-Snapshots aus data/iv_history/*.json.
    Rückgabe: {ticker: [(date_str, iv_float), ...], ...} — chronologisch sortiert.
    """
    archive = {}
    pattern = os.path.join(IV_ARCHIVE_DIR, "*.json")
    files   = sorted(glob.glob(pattern))   # lexikographisch = chronologisch (YYYY-MM-DD)

    for fpath in files:
        try:
            with open(fpath, "r") as f:
                day_data = json.load(f)
            date_str = day_data.get("date", "")
            for sym, info in day_data.get("tickers", {}).items():
                iv = info.get("iv")
                if iv is not None:
                    archive.setdefault(sym, []).append((date_str, iv))
        except Exception as e:
            log.debug(f"  [IV-Archiv] {fpath} übersprungen: {e}")

    return archive


def _calc_iv_rank_percentile(current_iv: float, history: list) -> dict:
    """
    Berechnet IV-Rank und IV-Percentile aus der gespeicherten Geschichte.
    history: [(date_str, iv_float), ...]  — chronologisch
    """
    # Letzten 252 Einträge (ca. 1 Handelsjahr)
    window = [iv for _, iv in history[-IV_FULL_WINDOW_DAYS:]]
    n      = len(window)

    if n < IV_MIN_RANK_DAYS:
        return {"ivRank": None, "ivPercentile": None, "ivArchiveDays": n}

    iv_min = min(window)
    iv_max = max(window)

    # IV-Rank (tastytrade): wo liegt aktuelle IV zwischen Hoch/Tief?
    if iv_max > iv_min:
        iv_rank = round((current_iv - iv_min) / (iv_max - iv_min) * 100, 1)
    else:
        iv_rank = 50.0   # Konstant → kein Signal

    # IV-Percentile (TOS/IBD): Anteil Tage mit niedrigerer IV
    days_below = sum(1 for iv in window if iv < current_iv)
    iv_pct     = round(days_below / n * 100, 1)

    return {
        "ivRank":       max(0.0, min(100.0, iv_rank)),
        "ivPercentile": iv_pct,
        "ivArchiveDays": n,
    }


def _save_day_snapshot(date_str: str, iv_results: dict) -> bool:
    """Schreibt den Tages-Snapshot nach data/iv_history/YYYY-MM-DD.json."""
    try:
        os.makedirs(IV_ARCHIVE_DIR, exist_ok=True)
        fpath = os.path.join(IV_ARCHIVE_DIR, f"{date_str}.json")
        payload = {
            "schema":  IV_SCHEMA_VERSION,
            "date":    date_str,
            "count":   len(iv_results),
            "tickers": iv_results,
        }
        with open(fpath, "w") as f:
            json.dump(payload, f, separators=(",", ":"))
        return True
    except Exception as e:
        log.warning(f"  [IV-Archiv] Snapshot-Schreiben fehlgeschlagen: {e}")
        return False


# ── Haupt-Einstiegspunkt ───────────────────────────────────────────────────────

def run(results: list) -> dict:
    """
    Haupt-Einstiegspunkt — wird von market_aggregator.main() aufgerufen.

    Args:
        results: Liste der Ticker-Dicts aus process_ticker() (mit 'sym', 'price').

    Side-effects:
        - Schreibt data/iv_history/YYYY-MM-DD.json (wird vom Workflow committet)
        - Schreibt results[i]["ivRank"], ["ivPercentile"], ["ivArchiveDays"] zurück

    Returns:
        Status-Dict für master["ivArchive"].
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Nur US-Aktien (kein "." = ausländische Börse, kein "-" = Krypto)
    us_results = [r for r in results
                  if "." not in r.get("sym", "")
                  and "-" not in r.get("sym", "")
                  and r.get("price") and r["price"] > 0]

    log.info(f"  [IV] Starte IV-Archiv-Lauf: {len(us_results)} US-Ticker, Datum {today_str}")

    # ── Schritt 1: ATM-IV parallel fetchen ──────────────────────────────────
    iv_today = {}   # {sym: {"iv": float, "expiry": str, "dte": int, ...}}
    ok_count = 0
    err_count = 0

    def _fetch(r):
        sym   = r["sym"]
        price = r["price"]
        result = _fetch_atm_iv(sym, price)
        return sym, result

    with ThreadPoolExecutor(max_workers=IV_FETCH_WORKERS) as ex:
        futures = {ex.submit(_fetch, r): r["sym"] for r in us_results}
        for fut in as_completed(futures):
            sym, iv_info = fut.result()
            if iv_info is not None:
                iv_today[sym] = iv_info
                ok_count += 1
            else:
                err_count += 1

    log.info(f"  [IV] ATM-IV gefetcht: {ok_count} OK / {err_count} ohne Optionskette")

    # ── Schritt 2: Tages-Snapshot speichern ─────────────────────────────────
    saved = _save_day_snapshot(today_str, iv_today)
    if saved:
        log.info(f"  [IV] Snapshot gespeichert: data/iv_history/{today_str}.json ({ok_count} Ticker)")

    # ── Schritt 3: Archiv laden + IV-Rank/Percentile berechnen ──────────────
    archive = _load_archive()
    ranked_count = 0

    # Lookup: sym → result-Dict (für In-Place-Update)
    sym_to_result = {r["sym"]: r for r in results}

    for sym, iv_info in iv_today.items():
        current_iv  = iv_info["iv"]
        history     = archive.get(sym, [])
        rank_data   = _calc_iv_rank_percentile(current_iv, history)

        r = sym_to_result.get(sym)
        if r is not None:
            r["ivAtm"]         = current_iv
            r["ivExpiry"]      = iv_info.get("expiry")
            r["ivDte"]         = iv_info.get("dte")
            r.update(rank_data)    # ivRank, ivPercentile, ivArchiveDays
            if rank_data.get("ivRank") is not None:
                ranked_count += 1

    # Ticker ohne IV-Daten: Felder auf None setzen (konsistentes Schema)
    for r in results:
        for field in ("ivAtm", "ivExpiry", "ivDte", "ivRank", "ivPercentile", "ivArchiveDays"):
            if field not in r:
                r[field] = None

    log.info(f"  [IV] IV-Rank berechnet für {ranked_count} Ticker "
             f"(min. {IV_MIN_RANK_DAYS} Archiv-Tage nötig)")

    archive_days = len(glob.glob(os.path.join(IV_ARCHIVE_DIR, "*.json")))

    return {
        "ok":           True,
        "date":         today_str,
        "fetched":      ok_count,
        "errors":       err_count,
        "ranked":       ranked_count,
        "archiveDays":  archive_days,
        "minRankDays":  IV_MIN_RANK_DAYS,
        "schema":       IV_SCHEMA_VERSION,
    }
