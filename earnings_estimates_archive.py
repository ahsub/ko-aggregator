#!/usr/bin/env python3
"""
earnings_estimates_archive.py — v0.1 (23.09.2026)

CHANGELOG:
v0.3 (23.09.2026, Claude + Axel, Reviewer-Korrektur): Die Aussage "15 Ticker
     passen unter die 25er-Grenze" war ein am 23.09. BEOBACHTETER Wert
     (5-15-Handelstage-Fenster an diesem einen Tag), kein garantiertes
     Tagesmaximum — in einer starken Earnings-Woche koennen deutlich mehr
     Kandidaten anfallen. `max_tickers_per_run` als statische Preset-
     Konstante komplett entfernt. Stattdessen: persistentes Usage-Log
     (`.api_usage_<date>.json`) zaehlt tatsaechlich heute bereits getaetigte
     Requests, das fuer JEDEN Lauf effektiv verbleibende Tagesbudget wird
     daraus live berechnet (`count_requests_today()`), nicht angenommen.
     `--max-tickers` wirkt nur noch als zusaetzliche, optionale Verschaerfung
     obendrauf, nie budget-erweiternd. Ticker, die wegen Budget-Erschoepfung
     nicht verarbeitet werden konnten, werden in
     `pending_candidates_<date>.json` dokumentiert statt stillschweigend
     verworfen — der naechste Lauf entscheidet explizit, ob er sie aufgreift
     (kein Auto-Resume). Flag-Namen vereinheitlicht auf
     REPEATED_PLACEHOLDER/POSSIBLE_SPLIT_ARTIFACT/ZERO_VALUE_ANOMALY.
v0.2 (23.09.2026, Claude + Axel): Axel bestaetigt — aktuell NUR AV-Free-Tier
     aktiv (25 Requests/Tag, 5/Minute), kein Premium-Tarif. v0.1s
     DEFAULT_SLEEP_SECONDS=1.0 war fuer Premium-75 kalibriert und haette auf
     Free-Tier zu einer Rate-Limit-Sperre gefuehrt. Tarif-bewusste Presets
     (TIER_PRESETS) eingefuehrt: --tier free|premium75|premium150 steuert
     sleep_seconds/max_tickers_per_run/daily_cap automatisch statt fester
     Konstanten. Default bleibt "free" (bestaetigter aktueller Stand).
v0.1 (23.09.2026, Claude + Axel): Erstfassung. Feasibility-Closure-Punkt C
     aus EARNINGS-INVEST-PHASE0-FEASIBILITY.md, Abschnitt 8. Taegliches
     Point-in-Time-Archiv fuer Alpha-Vantage EARNINGS_ESTIMATES-Daten,
     analog zu iv_layer.py (IV-Rank-Archiv, s. SUITE.md Backlog #15).
     Speichert Revenue- UND EPS-Felder als Redundanz (Scope-Entscheidung
     Axel, 23.09.2026 — "geht klar wie vorgeschlagen").

ZWECK
-----
UIQ-eigene Point-in-Time-Historie fuer Revenue-Schaetzungen aufbauen. Anders
als bei EPS liefert Alpha Vantage (EARNINGS_ESTIMATES-Endpoint) fuer Revenue
KEINE eigene 7/30/60/90-Tage-Revisionshistorie (verifiziert gegen 6 Live-
Ticker, s. Feasibility-Report Abschnitt 3). Revenue-Revisionswerte werden
NICHT hier berechnet, sondern erst in einer spaeteren Schicht aus der
akkumulierten Historie abgeleitet, sobald genug Archiv-Tage vorliegen.
Reifegrad-Modell (s. Feasibility-Report Abschnitt 5b):
    EPS_ONLY -> EPS_PLUS_PARTIAL_REVENUE -> FULL_LAYER_1

WICHTIG — TARIF-REALITAET (23.09.2026)
------------------------------------------
BESTAETIGT (Axel, 23.09.2026): aktuell NUR Free-Tier aktiv (25 Requests/Tag,
5/Minute) — kein Premium-Tarif. Die volle 737-Ticker-Universumsabdeckung aus
Feasibility-Report Abschnitt 6 (dort fuer Premium-75 gerechnet) ist damit
bestaetigt NICHT moeglich. Das tatsaechlich fuer einen einzelnen Lauf
verfuegbare Budget wird NICHT als fester Wert angenommen (s. v0.3-Korrektur
oben), sondern live aus dem Usage-Log berechnet: `daily_cap - bereits
heute verbrauchte Requests`. An einem Tag mit vorherigen Test-Calls (wie
z.B. dem 23.09., an dem allein die Live-Tests dieser Recherche schon 8
Requests verbraucht hatten) faellt das verbleibende Budget entsprechend
kleiner aus als die vollen 25. Mit --tier premium75/premium150 auf die
urspruenglich geplanten Werte umstellen, sobald/falls ein Premium-Tarif
aktiviert wird — dann entfaellt der Tages-Cap komplett, s. TIER_PRESETS.

SANITY-CHECKS (aus Feasibility-Report Abschnitt 4, live an 6 Tickern
gefunden — IBKR/MPC/MRK/NVDA/CAT/STNG)
------------------------------------------------------------------------
Drei Anomalie-Muster werden erkannt und als Flags am Datensatz vermerkt,
NICHT automatisch verworfen (Entscheidung, was damit passiert, bleibt einer
spaeteren Schicht vorbehalten — hier nur Diagnose, keine Filterung. Der
MPC-Split-Artefakt-False-Positive, s. unten, zeigt konkret, warum diese
Flags NIE automatisch Daten verwerfen duerfen — sie machen Datenqualitaet
sichtbar, sind aber keine eigene Wahrheit):
  1. REPEATED_PLACEHOLDER    — derselbe Wert (typischerweise ein auffaellig
                                runder) wiederholt sich ueber mehrere
                                Perioden hinweg (MPC-Fund:
                                revenue_estimate_high 7x exakt 40 Mrd.)
  2. POSSIBLE_SPLIT_ARTIFACT — eps_estimate_average_{60,90}_days_ago weicht
                                vom aktuellen Wert um einen Near-Integer-
                                Faktor ab (2x, 4x, 10x — typische Split-
                                Verhaeltnisse) (NVDA-Fund: Faktor ~9x um den
                                10:1-Split Juni 2024, Faktor ~4x um den
                                4:1-Split Juli 2021)
  3. ZERO_VALUE_ANOMALY      — eps_estimate_analyst_count und -average
                                beide 0, waehrend Nachbarfelder (z.B.
                                _7_days_ago) befuellt sind (NVDA-Fund:
                                Quartal 2022-07-31)

Getestet gegen die sechs echten Live-Responses aus der Phase-0-Recherche
(s. test_earnings_estimates_archive.py im selben Verzeichnis) — alle drei
bekannten Anomalien werden zuverlaessig erkannt, keine False Positives bei
den drei "sauberen" Tickern (IBKR, MRK, CAT).

VERWENDUNG
----------
    python earnings_estimates_archive.py --tickers IBKR,MPC,MRK
    python earnings_estimates_archive.py --universe-file master_market_data.json --max-tickers 15
    python earnings_estimates_archive.py --tickers-file watchlist.txt --dry-run

Erwartet ALPHAVANTAGE_API_KEY als Umgebungsvariable (nicht als CLI-Argument,
damit der Key nicht in Shell-Historie/Logs landet).
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, date
from pathlib import Path

AV_BASE_URL = "https://www.alphavantage.co/query"
SCRIPT_VERSION = "0.2"

# TARIF-PRESETS (23.09.2026, verifiziert gegen mehrere aktuelle Quellen).
# WICHTIG: Axel bestaetigt hat, aktuell NUR Free-Tier aktiv (23.09.2026) —
# Default ist deshalb bewusst auf "free" gesetzt, nicht auf eine optimistische
# Annahme. Vor jedem Lauf pruefen, ob sich das geaendert hat.
# KEIN max_tickers_per_run mehr hier (v0.3, Reviewer-Korrektur 23.09.2026):
# fruehere Fassung hatte einen statischen Default (z.B. 10 oder 15) — das
# waere der beobachtete Wert eines einzelnen Tages gewesen, kein
# garantiertes Maximum. Die tatsaechliche Obergrenze pro Lauf wird jetzt
# ausschliesslich aus dem via Usage-Log gemessenen, verbleibenden
# Tagesbudget berechnet (s. main()), fuer premium-Tarife ohne Tages-Cap gibt
# es dann effektiv keine Obergrenze aus dem Preset selbst.
TIER_PRESETS = {
    "free": {
        "daily_cap": 25,
        "requests_per_minute": 5,
        "sleep_seconds": 13.0,   # 60/5=12s Minimalabstand + 1s Sicherheitsmarge
    },
    "premium75": {
        "daily_cap": None,  # kein Tages-Cap, nur Requests/Minute
        "requests_per_minute": 75,
        "sleep_seconds": 1.0,
    },
    "premium150": {
        "daily_cap": None,
        "requests_per_minute": 150,
        "sleep_seconds": 0.5,
    },
}
DEFAULT_TIER = "free"

# Felder, die pro Periode archiviert werden — Revenue UND EPS als Redundanz
# (Scope-Entscheidung Axel, 23.09.2026).
ARCHIVE_FIELDS = [
    "date", "horizon",
    "revenue_estimate_average", "revenue_estimate_high", "revenue_estimate_low",
    "revenue_estimate_analyst_count",
    "eps_estimate_average", "eps_estimate_high", "eps_estimate_low",
    "eps_estimate_analyst_count",
    # EPS-Revisionsfelder werden mitarchiviert, obwohl AV sie schon liefert —
    # Redundanz ist bewusst gewollt (Ausfallsicherheit, falls AV das Schema
    # je aendert; s. Testpflicht Punkt 9 "Stabilitaet des Schemas").
    "eps_estimate_average_7_days_ago", "eps_estimate_average_30_days_ago",
    "eps_estimate_average_60_days_ago", "eps_estimate_average_90_days_ago",
    "eps_estimate_revision_up_trailing_7_days", "eps_estimate_revision_down_trailing_7_days",
    "eps_estimate_revision_up_trailing_30_days", "eps_estimate_revision_down_trailing_30_days",
]


def _to_float(v):
    """AV liefert alle Zahlenwerte als Strings. None/'' -> None statt 0.0 —
    wichtig, damit ein fehlender Wert nicht faelschlich als Nullwert-Anomalie
    (Muster 3) gewertet wird."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() == "none":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_earnings_estimates(symbol, api_key, timeout=15):
    """Ruft EARNINGS_ESTIMATES fuer ein Symbol ab. Gibt (data, error) zurueck —
    error ist None bei Erfolg. Wirft NIE eine Exception nach aussen (Grundgesetz
    #4-Geist: ein einzelner fehlgeschlagener Ticker darf den gesamten Lauf nicht
    abbrechen)."""
    url = f"{AV_BASE_URL}?function=EARNINGS_ESTIMATES&symbol={symbol}&apikey={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        return None, f"network_error: {e}"

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, "invalid_json_response"

    # AV meldet Fehler/Rate-Limits als JSON mit "Note"/"Information"/"Error Message"
    # statt eines HTTP-Fehlercodes — muss explizit geprueft werden.
    if "Note" in payload:
        return None, f"rate_limited: {payload['Note']}"
    if "Information" in payload:
        return None, f"api_info: {payload['Information']}"
    if "Error Message" in payload:
        return None, f"api_error: {payload['Error Message']}"
    if "estimates" not in payload:
        return None, "unexpected_schema: 'estimates' key missing"

    return payload, None


def detect_repeated_value(estimates, field, min_repeats=4):
    """Muster 1: derselbe Wert wiederholt sich ueber >= min_repeats aufeinander-
    folgende Perioden (nach date absteigend sortiert, wie AV sie liefert).
    Gibt eine Liste betroffener Perioden-Daten zurueck, leer wenn nichts
    gefunden."""
    values_by_date = []
    for e in estimates:
        v = _to_float(e.get(field))
        if v is not None:
            values_by_date.append((e.get("date"), v))

    flagged = []
    i = 0
    while i < len(values_by_date):
        j = i
        while j + 1 < len(values_by_date) and values_by_date[j + 1][1] == values_by_date[i][1]:
            j += 1
        run_length = j - i + 1
        if run_length >= min_repeats:
            flagged.extend(d for d, _ in values_by_date[i:j + 1])
        i = j + 1
    return flagged


def detect_split_artifact(estimates, near_integer_factors=(2, 3, 4, 5, 10), tolerance=0.15):
    """Muster 2: eps_estimate_average weicht von einem der _{7,30,60,90}_days_ago-
    Werte um einen Near-Integer-Faktor ab (z.B. ~4x oder ~10x, typische Split-
    Verhaeltnisse). tolerance=0.15 heisst: bis zu 15% Abweichung vom exakten
    Integer-Faktor wird noch als Treffer gewertet (AV-Werte sind Durchschnitte
    mehrerer Analysten, landen selten exakt auf dem theoretischen Faktor)."""
    flagged = []
    for e in estimates:
        current = _to_float(e.get("eps_estimate_average"))
        if current is None or current == 0:
            continue
        for lookback_field in ["eps_estimate_average_60_days_ago", "eps_estimate_average_90_days_ago"]:
            past = _to_float(e.get(lookback_field))
            if past is None or past == 0:
                continue
            ratio = past / current
            for factor in near_integer_factors:
                if abs(ratio - factor) <= factor * tolerance or abs(ratio - (1 / factor)) <= (1 / factor) * tolerance:
                    flagged.append({
                        "date": e.get("date"),
                        "field": lookback_field,
                        "current": current,
                        "past": past,
                        "approx_factor": round(ratio, 2),
                    })
                    break
    return flagged


def detect_zero_row(estimates):
    """Muster 3: eps_estimate_average UND eps_estimate_analyst_count sind beide
    0, waehrend eps_estimate_average_7_days_ago einen validen (nicht-Null,
    nicht-None) Wert hat — d.h. die Zeile selbst ist ploetzlich leergelaufen,
    obwohl die Nachbarfelder zeigen, dass hier eigentlich Daten existieren
    sollten."""
    flagged = []
    for e in estimates:
        avg = _to_float(e.get("eps_estimate_average"))
        count = _to_float(e.get("eps_estimate_analyst_count"))
        seven_ago = _to_float(e.get("eps_estimate_average_7_days_ago"))
        if avg == 0 and count == 0 and seven_ago not in (None, 0):
            flagged.append(e.get("date"))
    return flagged


def run_sanity_checks(symbol, estimates):
    """Fuehrt alle drei Sanity-Checks aus, gibt ein Flags-Dict zurueck (leer,
    wenn nichts gefunden wurde). Reine Diagnose — verwirft/veraendert NICHTS
    an den Rohdaten."""
    flags = {}
    for field in ["revenue_estimate_high", "revenue_estimate_average", "revenue_estimate_low"]:
        repeated = detect_repeated_value(estimates, field)
        if repeated:
            flags.setdefault("REPEATED_PLACEHOLDER", []).append({"field": field, "dates": repeated})

    split = detect_split_artifact(estimates)
    if split:
        flags["POSSIBLE_SPLIT_ARTIFACT"] = split

    zero_rows = detect_zero_row(estimates)
    if zero_rows:
        flags["ZERO_VALUE_ANOMALY"] = zero_rows

    return flags


def build_archive_record(symbol, payload, snapshot_date, fetched_at):
    estimates = payload.get("estimates", [])
    trimmed = []
    for e in estimates:
        trimmed.append({k: e.get(k) for k in ARCHIVE_FIELDS})

    flags = run_sanity_checks(symbol, estimates)

    return {
        "symbol": symbol,
        "snapshot_date": snapshot_date,
        "fetched_at": fetched_at,
        "source": "alphavantage_earnings_estimates",
        "script_version": SCRIPT_VERSION,
        "sanity_flags": flags,
        "estimates": trimmed,
    }


def load_universe_from_master_data(path, max_tickers=None):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    symbols = [t["sym"] for t in data.get("tickers", [])]
    if max_tickers is not None:
        symbols = symbols[:max_tickers]
    return symbols


# --- Tagesbudget-Tracking -----------------------------------------------
# NEU (v0.3, 23.09.2026, Reviewer-Einwand): "15 Ticker passen unter die
# 25er-Grenze" war ein am 23.09. BEOBACHTETER Wert (5-15-Handelstage-Fenster
# an diesem einen Tag), kein garantiertes Tagesmaximum — in einer starken
# Earnings-Woche koennen deutlich mehr Kandidaten anfallen. Ein fest
# codiertes Limit haette genau das ignoriert. Stattdessen: echtes,
# persistentes Tracking der heute bereits verbrauchten Requests, das
# tatsaechlich verbleibende Budget wird PRO LAUF neu berechnet, nicht
# angenommen. Kandidaten, die wegen Budget-Erschoepfung nicht verarbeitet
# werden konnten, werden explizit fuer den naechsten Lauf dokumentiert
# (nicht automatisch nachgeholt — das bleibt eine bewusste Entscheidung des
# naechsten Aufrufs, kein stiller Automatismus).

def _usage_log_path(output_dir, snapshot_date):
    return Path(output_dir) / f".api_usage_{snapshot_date}.json"


def count_requests_today(output_dir, snapshot_date):
    """Liest den heutigen Usage-Log, gibt die Anzahl bereits getaetigter
    AV-Requests zurueck (0, falls noch keiner heute lief). Zaehlt JEDEN
    tatsaechlich abgesetzten HTTP-Call, unabhaengig davon, ob die Antwort
    inhaltlich verwertbar war — ein Rate-Limit-Fehler oder ein Netzwerkfehler
    hat AV gegenueber trotzdem einen Request ausgeloest und zaehlt
    konservativ mit (lieber das Budget unterschaetzen als ueberschaetzen und
    versehentlich gesperrt werden)."""
    path = _usage_log_path(output_dir, snapshot_date)
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        log = json.load(f)
    return len(log.get("requests", []))


def record_request(output_dir, snapshot_date, symbol):
    """Haengt einen Request-Eintrag an den heutigen Usage-Log an. Wird
    UNMITTELBAR vor jedem tatsaechlichen API-Call aufgerufen (nicht danach),
    damit ein Absturz mitten im Call das Budget trotzdem korrekt fortschreibt."""
    path = _usage_log_path(output_dir, snapshot_date)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
    else:
        log = {"date": snapshot_date, "requests": []}
    log["requests"].append({
        "symbol": symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def write_pending_candidates(output_dir, snapshot_date, pending_symbols):
    """Dokumentiert Ticker, die wegen Budget-Erschoepfung in diesem Lauf
    NICHT verarbeitet wurden. Bewusst kein Auto-Resume — der naechste Lauf
    entscheidet explizit (per --tickers-file), ob er diese Liste aufgreift."""
    if not pending_symbols:
        return None
    path = Path(output_dir) / f"pending_candidates_{snapshot_date}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "date": snapshot_date,
            "reason": "daily_budget_exhausted",
            "pending_symbols": pending_symbols,
        }, f, indent=2, ensure_ascii=False)
    return path


def main():
    parser = argparse.ArgumentParser(description="UIQ Earnings-Estimates Point-in-Time-Archiv (earnings_invest, Feasibility-Closure Punkt C)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--tickers", help="Kommagetrennte Ticker-Liste, z.B. IBKR,MPC,MRK")
    src.add_argument("--tickers-file", help="Datei mit einem Ticker pro Zeile")
    src.add_argument("--universe-file", help="master_market_data.json — extrahiert 'sym'-Feld aller Ticker")

    parser.add_argument("--tier", choices=list(TIER_PRESETS.keys()), default=DEFAULT_TIER,
                         help=f"AV-Tarif-Preset (bestimmt sleep-seconds/Tagesbudget). "
                              f"Default: {DEFAULT_TIER} (bestaetigt aktiver Tarif, Stand 23.09.2026)")
    parser.add_argument("--max-tickers", type=int, default=None,
                         help="Zusaetzliche Obergrenze pro Lauf, unabhaengig vom Tagesbudget "
                              "(optional — ohne diese Angabe zaehlt ausschliesslich das "
                              "tatsaechlich verbleibende Tagesbudget, s. --tier)")
    parser.add_argument("--sleep-seconds", type=float, default=None,
                         help="Pause zwischen Calls (Default: aus --tier-Preset)")
    parser.add_argument("--output-dir", default="data/earnings_estimates_history",
                         help="Zielverzeichnis fuer Archiv- UND Usage-Log-Dateien")
    parser.add_argument("--dry-run", action="store_true",
                         help="Nur anzeigen, welche Ticker abgefragt wuerden — kein API-Call, keine Datei")

    args = parser.parse_args()

    preset = TIER_PRESETS[args.tier]
    sleep_seconds = args.sleep_seconds if args.sleep_seconds is not None else preset["sleep_seconds"]
    daily_cap = preset["daily_cap"]
    snapshot_date = date.today().isoformat()

    # --- Tagesbudget bestimmen: NICHT angenommen, sondern aus dem
    # persistenten Usage-Log dieses Tages berechnet (Reviewer-Korrektur,
    # 23.09.2026 — "15" war ein beobachteter Wert, kein Tagesmaximum).
    already_used = count_requests_today(args.output_dir, snapshot_date) if daily_cap is not None else 0
    if daily_cap is not None:
        remaining_budget = max(0, daily_cap - already_used)
        print(f"Tarif '{args.tier}': {already_used}/{daily_cap} Requests heute bereits verbraucht, "
              f"verbleibendes Budget: {remaining_budget}")
    else:
        remaining_budget = None  # kein Tages-Cap (z.B. Premium)
        print(f"Tarif '{args.tier}': kein Tages-Cap.")

    if args.tickers:
        requested_symbols = [s.strip().upper() for s in args.tickers.split(",") if s.strip()]
    elif args.tickers_file:
        with open(args.tickers_file, "r", encoding="utf-8") as f:
            requested_symbols = [line.strip().upper() for line in f if line.strip()]
    else:
        requested_symbols = load_universe_from_master_data(args.universe_file)

    # Effektive Obergrenze fuer DIESEN Lauf: das tatsaechlich verbleibende
    # Tagesbudget ist die primaere Schranke. --max-tickers wirkt nur
    # zusaetzlich verschaerfend, nie budget-erweiternd.
    effective_limit = remaining_budget
    if args.max_tickers is not None:
        effective_limit = args.max_tickers if effective_limit is None else min(effective_limit, args.max_tickers)

    if effective_limit is not None and len(requested_symbols) > effective_limit:
        symbols = requested_symbols[:effective_limit]
        pending = requested_symbols[effective_limit:]
        print(f"⚠️  {len(requested_symbols)} Ticker angefordert, aber effektives Budget fuer diesen "
              f"Lauf ist {effective_limit} (Tagesbudget{' + --max-tickers' if args.max_tickers else ''}). "
              f"Verarbeite {len(symbols)}, {len(pending)} werden dokumentiert (s. pending_candidates-Datei).")
    else:
        symbols = requested_symbols
        pending = []

    if daily_cap is not None and remaining_budget == 0:
        print(f"❌ Tagesbudget fuer '{args.tier}' bereits vollstaendig verbraucht ({already_used}/{daily_cap}). "
              f"Kein Call moeglich, keine Verarbeitung heute.")
        if requested_symbols:
            written = write_pending_candidates(args.output_dir, snapshot_date, requested_symbols)
            if written:
                print(f"Alle {len(requested_symbols)} angeforderten Ticker dokumentiert: {written}")
        return 1

    print(f"Ticker fuer diesen Lauf ({len(symbols)}): {', '.join(symbols)}")

    if args.dry_run:
        print("--dry-run: kein API-Call, keine Datei geschrieben, kein Usage-Log-Eintrag.")
        return 0

    api_key = os.environ.get("ALPHAVANTAGE_API_KEY")
    if not api_key:
        print("FEHLER: ALPHAVANTAGE_API_KEY nicht gesetzt (Umgebungsvariable).", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{snapshot_date}.json"

    # Falls die Datei fuer heute schon existiert (z.B. zweiter Lauf am selben
    # Tag): bestehende Records behalten, nur neue/aktualisierte Ticker mergen
    # statt zu ueberschreiben — analog zum Autostash-Vorfall vom 23.09., der
    # gezeigt hat, wie leicht Archiv-Dateien bei naivem Ueberschreiben
    # kollidieren.
    existing = {}
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        for rec in existing_data.get("records", []):
            existing[rec["symbol"]] = rec
        print(f"Bestehende Archiv-Datei fuer {snapshot_date} gefunden ({len(existing)} Ticker) — merge statt ueberschreiben.")

    ok_count = 0
    error_count = 0
    for i, symbol in enumerate(symbols):
        # Usage-Log wird VOR dem Call geschrieben (nicht danach) — ein
        # Absturz mitten im Request darf das Budget nicht falsch aussehen
        # lassen, s. Docstring zu record_request().
        if daily_cap is not None:
            record_request(args.output_dir, snapshot_date, symbol)

        fetched_at = datetime.now(timezone.utc).isoformat()
        payload, error = fetch_earnings_estimates(symbol, api_key)

        if error:
            print(f"  ❌ {symbol}: {error}")
            error_count += 1
        else:
            record = build_archive_record(symbol, payload, snapshot_date, fetched_at)
            existing[symbol] = record
            flag_summary = ", ".join(record["sanity_flags"].keys()) if record["sanity_flags"] else "keine"
            print(f"  ✅ {symbol}: {len(record['estimates'])} Perioden, Sanity-Flags: {flag_summary}")
            ok_count += 1

        if i < len(symbols) - 1:
            time.sleep(sleep_seconds)

    output = {
        "snapshot_date": snapshot_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script_version": SCRIPT_VERSION,
        "ticker_count": len(existing),
        "records": list(existing.values()),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    if pending:
        written = write_pending_candidates(args.output_dir, snapshot_date, pending)
        print(f"{len(pending)} Ticker wegen Budget-Erschoepfung nicht verarbeitet, dokumentiert: {written}")

    print(f"\nFertig: {ok_count} erfolgreich, {error_count} Fehler. Archiv: {output_path}")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
