#!/usr/bin/env python3
"""
UIQ CoT Data Collector (Commitment of Traders, TFF-Report)
============================================================
Version 1.1 (18.09.2026, Claude + Axel — Live-Recherche-Fund)

Spec: docs/UIQ-COT-MODULE-DATA-ACQUISITION-SPEC-v1.0-2026-09-17.md
(UIQ-Suite, war nie committet — diese Datei implementiert sie, mit einer
wichtigen Korrektur gegenueber der urspruenglichen v1.0-Fassung, s.u.).

Bewusst NUR passiver Data-Collector — KEIN Feature-Engineering (Net
Position/Percentile/Velocity/Divergence/Crowding), KEIN Score, KEINE
Integration in MCM/BN/HMM/Strategy-Gates/Public-Digest/AI-Prompts (Spec
Abschnitt 9). Sammelt wöchentliche CFTC-TFF-Positionierungsdaten für ein
festes 6-Instrumente-Universum, roh + normalisiert, sonst nichts.

KORREKTUR GEGENUEBER v1.0 (18.09.2026, Live-Recherche via CFTC-Socrata-API
UND cftc.gov/MarketReports/.../HistoricalCompressed): die urspruengliche
Spec-Annahme "TFF-Historie reicht bis 2006 zurueck" war im KERN richtig,
aber nicht ueber die AKTUELLEN market_and_exchange_names-Bezeichnungen
abrufbar — die CFTC hat am 08.02.2022 die Bezeichnungen mehrerer Maerkte
umbenannt (z.B. "E-MINI S&P 500 STOCK INDEX" -> "E-MINI S&P 500"), nahtlos
(alte Bezeichnung endet 2022-02-01, neue beginnt 2022-02-08, keine Luecke).
Verifiziert fuer SP500/NASDAQ100/UST10Y/UST2Y (alle vier: alte Bezeichnung
ab 2006-06-13) und VIX (Bezeichnung unveraendert, Daten ab 2006-08-29).
RUSSELL2000 ist komplexer: ICE FUTURES U.S. (2008-07-22 bis 2018-06-05) ->
CME unter einem ZWISCHEN-Namen (2017-08-15 bis 2022-02-01, UEBERLAPPT mit
ICE) -> aktueller CME-Name (ab 2022-02-08). Diese Historie ist ueber
DIESELBE Live-API abrufbar, kein Bulk-Download noetig — s.
INSTRUMENT_SOURCE_NAMES unten. Diese Namen wurden 18.09.2026 per Ad-hoc-
Recherche (LIKE-Suche gegen echte Daten) gefunden, NICHT aus einer
offiziellen CFTC-Variablennamen-Dokumentation — bei Bedarf periodisch
gegenpruefen, falls sich CFTC-Bezeichnungen erneut aendern.

Zwei-Schichten-Speicherung (Spec Abschnitt 4), je Instrument eine JSONL-
Datei (append-only, ein Datensatz pro Zeile — analog zur Git-History-als-
Backup-Philosophie von tr_backup.py):
    data/cot/raw/{instrument_id}.jsonl        — unveraenderte API-Antwort
    data/cot/normalized/{instrument_id}.jsonl — geparste Kernfelder

Die CFTC-Quellbezeichnung (market_and_exchange_names) wird NIEMALS
ueberschrieben oder konsolidiert — sie bleibt roh erhalten (Raw Layer)
UND als eigenes Feld im Normalized Layer sichtbar. Mehrere Bezeichnungen
koennen unter derselben uiq_instrument_id nebeneinander stehen (normale
Umbenennung UND, bei RUSSELL2000, echte Venue-Ueberlappung) — der
Collector konsolidiert das NICHT fachlich (keine "welche Quelle ist
richtiger"-Entscheidung), das bleibt einer spaeteren, separaten
Datenvalidierung vorbehalten (Reviewer-Vorgabe 18.09.2026).

Idempotenz (Spec Abschnitt 5, ERWEITERT 18.09.2026): Schluessel ist
uiq_instrument_id + market_and_exchange_names + report_date_as_yyyy_mm_dd
— NICHT mehr instrument_id + report_date allein. Grund: bei RUSSELL2000
existieren fuer 2017-08-15 bis 2018-06-05 ECHTE zwei Beobachtungen pro
Report-Date (ICE UND CME, unterschiedliche Open-Interest-Pools) — der
alte, groebere Schluessel haette das als Duplikat behandelt und eine der
beiden Quellen stillschweigend verworfen. Mit dem erweiterten Schluessel
bleiben beide erhalten (s. _load_existing_keys()). Rows in einem bekannten
Ueberlappungsfenster tragen zusaetzlich historical_source_overlap=true
(s. KNOWN_SOURCE_OVERLAPS) — reine Kennzeichnung, keine Wertung.

Look-Ahead-Bias-Schutz (Spec Abschnitt 6): uiq_effective_date_type
unterscheidet "observed" (laufender woechentlicher Betrieb — Datum des
tatsaechlichen UIQ-Abrufs) von "backfill_estimate" (initialer historischer
Vollimport — report_date + 3 Kalendertage als AUSDRUECKLICH markierte
Naeherung, keine beobachtete Tatsache). Jede spaetere Research-Nutzung
MUSS uiq_effective_date verwenden, NIEMALS report_date_as_yyyy_mm_dd, um
zu bestimmen, ab wann ein Datenpunkt "bekannt" gewesen waere.

Zwei Modi (COT_MODE env var, Default "weekly"):
    weekly   — laufender Betrieb (Spec Abschnitt 7): pro Instrument NUR
               die aktuell gueltige Bezeichnung (CURRENT_NAMES, letzter
               Eintrag in INSTRUMENT_SOURCE_NAMES), letzte 5 verfuegbare
               Wochen (Puffer fuer verpasste Laeufe). Historische
               Bezeichnungen werden hier NICHT erneut abgefragt (waeren
               laengst vollstaendig, kein neuer Datenpunkt zu erwarten).
               uiq_effective_date_type = "observed".
    backfill — einmaliger Vollimport ALLER bekannten Bezeichnungen pro
               Instrument (INSTRUMENT_SOURCE_NAMES), je Bezeichnung eigene
               Socrata-Pagination via $limit/$offset. uiq_effective_date_
               type = "backfill_estimate". Kann pro Instrument Minuten
               dauern — eigener, expliziter Lauf, nicht Teil des
               woechentlichen Betriebs.
    COT_INSTRUMENT env var (optional): auf eine einzelne uiq_instrument_id
    beschraenken (z.B. fuer einen gezielten Backfill-Test), Default: alle.

Fehlerphilosophie (Spec Abschnitt 8, analog tr_backup.py): pro Instrument
UND pro Quellbezeichnung einzeln try/except — ein Fehlschlag blockiert die
uebrigen nicht. Das Script selbst bricht den Workflow nie (Exit 0 auch bei
Fehlern) — CoT-Daten sind nicht zeitkritisch (Spec Abschnitt 8), ein
verpasster Wochenpunkt wird beim naechsten Lauf nachgeholt.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta

import requests

CFTC_DATASET_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"

# ── Instrumenten-Universum v1.1 (Spec Abschnitt 3+5, exakte Namen verifiziert
# gegen echte Live-Daten, 18.09.2026) ───────────────────────────────────────
# Pro UIQ-Instrument ALLE bekannten historischen CFTC-Bezeichnungen, in
# chronologischer Reihenfolge — der LETZTE Eintrag ist die aktuell gueltige
# Bezeichnung (wird von run_weekly() verwendet), ALLE Eintraege zusammen
# werden von run_backfill() abgefragt. Bewusst NICHT als einzelner String
# pro Instrument (wie in v1.0) — das haette die vor-2022-Historie fuer
# fuenf von sechs Instrumenten stillschweigend verloren.
#
# DXY/DOLLAR INDEX bewusst NICHT enthalten — exakter Name noch nicht
# verifiziert (Spec Abschnitt 3: "pending", blockiert v1.0 nicht). Als 7.
# Instrument nachziehen, sobald der Name bestaetigt ist.
INSTRUMENT_SOURCE_NAMES = {
    "SP500": [
        "E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE",  # bis 2022-02-01
        "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",              # ab 2022-02-08
    ],
    "NASDAQ100": [
        "NASDAQ-100 STOCK INDEX (MINI) - CHICAGO MERCANTILE EXCHANGE",  # bis 2022-02-01
        "NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE",                    # ab 2022-02-08
    ],
    # RUSSELL2000: DREI historische Bezeichnungen, mit einer ECHTEN
    # Ueberlappung (ICE + CME parallel 2017-08-15 bis 2018-06-05) — s.
    # KNOWN_SOURCE_OVERLAPS unten. Bewusst KEINE Konsolidierung/Praeferenz
    # zwischen ICE und CME in diesem Fenster (Reviewer-Vorgabe 18.09.2026:
    # das ist eine spaetere Datenvalidierungsfrage, keine Collector-
    # Entscheidung).
    "RUSSELL2000": [
        "RUSSELL 2000 MINI INDEX FUTURE - ICE FUTURES U.S.",          # 2008-07-22 bis 2018-06-05
        "E-MINI RUSSELL 2000 INDEX - CHICAGO MERCANTILE EXCHANGE",    # 2017-08-15 bis 2022-02-01 (ueberlappt mit ICE)
        "RUSSELL E-MINI - CHICAGO MERCANTILE EXCHANGE",               # ab 2022-02-08
    ],
    "VIX": [
        "VIX FUTURES - CBOE FUTURES EXCHANGE",  # unveraendert seit 2006-08-29
    ],
    "UST10Y": [
        "10-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE",  # bis 2022-02-01
        "UST 10Y NOTE - CHICAGO BOARD OF TRADE",                 # ab 2022-02-08
    ],
    "UST2Y": [
        "2-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE",  # bis 2022-02-01
        "UST 2Y NOTE - CHICAGO BOARD OF TRADE",                 # ab 2022-02-08
    ],
}

# Fuer run_weekly(): nur die jeweils aktuelle (letzte) Bezeichnung.
CURRENT_NAMES = {k: v[-1] for k, v in INSTRUMENT_SOURCE_NAMES.items()}

# Bekannte Venue-Ueberlappungsfenster (Spec-Korrektur 18.09.2026) — Zeilen
# in diesem Datumsfenster bekommen historical_source_overlap=true (s.
# _normalize_row()), damit spaetere Research-Nutzung diese Faelle explizit
# behandeln kann, statt sie unbemerkt als normale Einzelbeobachtung zu
# lesen. Reine Kennzeichnung, keine Wertung/Konsolidierung.
KNOWN_SOURCE_OVERLAPS = {
    "RUSSELL2000": [("2017-08-15", "2018-06-05")],
}

RAW_DIR        = os.path.join("data", "cot", "raw")
NORMALIZED_DIR = os.path.join("data", "cot", "normalized")

# Explizit benannte Kernfelder (Spec Abschnitt 4, Normalized Layer).
EXPLICIT_FIELDS = [
    "report_date_as_yyyy_mm_dd",
    "market_and_exchange_names",
    "open_interest_all",
    "dealer_positions_long_all", "dealer_positions_short_all", "dealer_positions_spread_all",
    "asset_mgr_positions_long", "asset_mgr_positions_short", "asset_mgr_positions_spread",
    "lev_money_positions_long", "lev_money_positions_short", "lev_money_positions_spread",
    "other_rept_positions_long", "other_rept_positions_short", "other_rept_positions_spread",
    "nonrept_positions_long_all", "nonrept_positions_short_all",
    "contract_units", "futonly_or_combined",
]

# Feld-PRAEFIXE statt einer starren Vollliste (Spec Abschnitt 4: "alle
# change_in_*-Felder" / "alle pct_of_oi_*" / "alle traders_*" / "alle
# conc_*-Felder") — jedes Feld aus der rohen CFTC-Antwort, das mit einem
# dieser Praefixe beginnt, wandert automatisch in den Normalized Layer.
# Bewusst so statt hartcodierter Einzelfeldnamen: robust gegen CFTC-
# Schema-Erweiterungen (neues change_in_*-Feld erscheint automatisch),
# ohne diese Datei aendern zu muessen — der Raw Layer bleibt ohnehin die
# vollstaendige Quelle der Wahrheit, falls hier doch etwas fehlt.
PREFIX_FIELDS = ("change_in_", "pct_of_oi_", "pct_of_open_interest_", "traders_", "conc_")


def _log(msg: str) -> None:
    print(f"[COT] {msg}")


def _jsonl_path(base_dir: str, instrument_id: str) -> str:
    return os.path.join(base_dir, f"{instrument_id}.jsonl")


def _append_jsonl(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _load_existing_keys(instrument_id: str) -> set:
    """
    Idempotenz-Grundlage (Spec Abschnitt 5, ERWEITERT 18.09.2026): liest die
    bereits vorhandenen (market_and_exchange_names, report_date)-Paare aus
    der normalisierten Datei — NICHT mehr report_date allein, s. Modul-
    Kommentar oben (RUSSELL2000-Ueberlappung). Datei fehlt beim allerersten
    Lauf noch — dann leere Menge, kein Fehler.
    """
    path = _jsonl_path(NORMALIZED_DIR, instrument_id)
    keys = set()
    if not os.path.exists(path):
        return keys
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                d = row.get("report_date_as_yyyy_mm_dd")
                name = row.get("market_and_exchange_names")
                if d and name:
                    keys.add((name, _date_only(d)))
            except (json.JSONDecodeError, AttributeError):
                # Eine beschaedigte Zeile darf die Idempotenz-Pruefung
                # nicht zum Absturz bringen — s. Fehlerphilosophie oben.
                continue
    return keys


def _date_only(value: str) -> str:
    """
    Socrata liefert report_date_as_yyyy_mm_dd als ISO-Timestamp
    ("2020-01-07T00:00:00.000") — auf den reinen Datumsanteil kuerzen,
    damit Idempotenz-Vergleiche nicht an Zeitanteilen scheitern.
    """
    return value[:10] if value else value


def _is_known_overlap(instrument_id: str, report_date: str) -> bool:
    """
    Prueft, ob report_date (YYYY-MM-DD) in einem bekannten Venue-
    Ueberlappungsfenster liegt (KNOWN_SOURCE_OVERLAPS) — reine
    Kennzeichnung fuer historical_source_overlap, s. Modul-Kommentar oben.
    Keine Konsolidierung, keine Wertung.
    """
    for start, end in KNOWN_SOURCE_OVERLAPS.get(instrument_id, []):
        if start <= report_date <= end:
            return True
    return False


def _fetch_page(market_name: str, order: str, limit: int, offset: int = 0) -> list:
    params = {
        "$where": f"market_and_exchange_names='{market_name}'",
        "$order": f"report_date_as_yyyy_mm_dd {order}",
        "$limit": limit,
        "$offset": offset,
    }
    resp = requests.get(CFTC_DATASET_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _normalize_row(raw_row: dict, instrument_id: str, fetched_at_iso: str,
                    effective_date: str, effective_date_type: str) -> dict:
    normalized = {k: raw_row.get(k) for k in EXPLICIT_FIELDS}
    for k, v in raw_row.items():
        if k not in normalized and any(k.startswith(p) for p in PREFIX_FIELDS):
            normalized[k] = v
    normalized["uiq_instrument_id"] = instrument_id
    normalized["uiq_fetched_at"] = fetched_at_iso
    normalized["uiq_effective_date"] = effective_date
    normalized["uiq_effective_date_type"] = effective_date_type
    # ERGAENZT (18.09.2026, Reviewer-Vorgabe): reine Kennzeichnung bekannter
    # Venue-Ueberlappungen (aktuell nur RUSSELL2000, 2017-08-15 bis
    # 2018-06-05) — KEINE Konsolidierung, spaetere Research-Phase entscheidet.
    report_date = _date_only(raw_row.get("report_date_as_yyyy_mm_dd"))
    normalized["historical_source_overlap"] = _is_known_overlap(instrument_id, report_date) if report_date else False
    return normalized


def _store_row(raw_row: dict, instrument_id: str, fetched_at_iso: str,
                effective_date: str, effective_date_type: str) -> None:
    _append_jsonl(_jsonl_path(RAW_DIR, instrument_id), {
        "raw_cftc_json": raw_row,
        "uiq_instrument_id": instrument_id,
        "uiq_fetched_at": fetched_at_iso,
    })
    _append_jsonl(
        _jsonl_path(NORMALIZED_DIR, instrument_id),
        _normalize_row(raw_row, instrument_id, fetched_at_iso, effective_date, effective_date_type),
    )


def run_weekly(instrument_id: str) -> int:
    """
    Laufender Betrieb (Spec Abschnitt 7). Fragt NUR die aktuell gueltige
    Bezeichnung ab (CURRENT_NAMES) — historische Bezeichnungen sind fuer
    den laufenden Betrieb irrelevant (laengst abgeschlossen, kein neuer
    Datenpunkt zu erwarten). Holt die letzten 5 verfuegbaren Wochen
    (Puffer gegen verpasste Laeufe) und haengt nur tatsaechlich neue
    (Bezeichnung, report_date)-Paare an.
    """
    market_name = CURRENT_NAMES[instrument_id]
    fetched_at = datetime.now(timezone.utc).isoformat()
    existing = _load_existing_keys(instrument_id)

    rows = _fetch_page(market_name, order="DESC", limit=5)
    new_count = 0
    for row in rows:
        report_date = _date_only(row.get("report_date_as_yyyy_mm_dd"))
        key = (market_name, report_date)
        if not report_date or key in existing:
            continue
        _store_row(
            row, instrument_id, fetched_at,
            effective_date=fetched_at, effective_date_type="observed",
        )
        existing.add(key)
        new_count += 1
    return new_count


def run_backfill(instrument_id: str) -> int:
    """
    Einmaliger Vollimport (Spec Abschnitt 7, ERWEITERT 18.09.2026): fragt
    ALLE bekannten historischen Bezeichnungen aus INSTRUMENT_SOURCE_NAMES
    ab (nicht nur die aktuelle) — s. Modul-Kommentar zur 08.02.2022-
    Umbenennung. Je Bezeichnung eigene aufsteigende Pagination.
    uiq_effective_date = report_date + 3 Kalendertage, AUSDRUECKLICH als
    "backfill_estimate" markiert (Spec Abschnitt 6). Ein Fehlschlag bei
    EINER Bezeichnung (z.B. Netzwerkfehler mitten in der ICE-Historie)
    blockiert die uebrigen Bezeichnungen desselben Instruments nicht.
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    existing = _load_existing_keys(instrument_id)
    new_count = 0

    for market_name in INSTRUMENT_SOURCE_NAMES[instrument_id]:
        try:
            page_size = 1000
            offset = 0
            name_new_count = 0
            while True:
                rows = _fetch_page(market_name, order="ASC", limit=page_size, offset=offset)
                if not rows:
                    break
                for row in rows:
                    report_date = _date_only(row.get("report_date_as_yyyy_mm_dd"))
                    key = (market_name, report_date)
                    if not report_date or key in existing:
                        continue
                    try:
                        report_dt = datetime.strptime(report_date, "%Y-%m-%d")
                    except ValueError:
                        _log(f"  ⚠ {instrument_id} ({market_name}): unlesbares "
                             f"report_date '{report_date}' — Zeile übersprungen")
                        continue
                    effective_date = (report_dt + timedelta(days=3)).strftime("%Y-%m-%d")
                    _store_row(
                        row, instrument_id, fetched_at,
                        effective_date=effective_date, effective_date_type="backfill_estimate",
                    )
                    existing.add(key)
                    new_count += 1
                    name_new_count += 1
                if len(rows) < page_size:
                    break
                offset += page_size
                time.sleep(0.2)  # kleine Pause, kein CFTC-Rate-Limit bekannt, aber kein Grund zu drängen
            _log(f"  · {instrument_id} ({market_name}): {name_new_count} neue Zeile(n)")
        except Exception as e:
            # Eine Bezeichnung darf die uebrigen Bezeichnungen desselben
            # Instruments nicht blockieren — dieselbe Fehlerisolation wie
            # zwischen verschiedenen Instrumenten (Spec Abschnitt 8).
            _log(f"  ⚠ {instrument_id} ({market_name}): fehlgeschlagen ({e}) — "
                 f"übrige Bezeichnungen dieses Instruments laufen trotzdem weiter")

    # ── VOLLSTAENDIGKEITS-DIAGNOSE (18.09.2026, Reviewer-Feedback) ─────────
    # "Backfill lief ohne Fehler" beweist NICHT, dass die komplette
    # verfuegbare Historie geladen wurde (z.B. stiller Abbruch bei einer
    # unerwarteten API-Antwort auf halbem Weg). Bewusst KEINE harte
    # Pruefung gegen ein festes Datum (z.B. "muss bis 2006 reichen") — die
    # tatsaechliche CFTC-Historienlaenge unterscheidet sich pro Instrument
    # (RUSSELL2000 z.B. erst ab 2008, s. INSTRUMENT_SOURCE_NAMES) und ein
    # starrer Schwellenwert wuerde dafuer falsche Alarme werfen. Stattdessen
    # ein reines Diagnose-Log ueber ALLE nun gespeicherten Daten dieses
    # Instruments (existing enthaelt nach der Schleife alt+neu, ueber ALLE
    # Bezeichnungen hinweg) — Axel beurteilt die Plausibilitaet selbst.
    if existing:
        dates_only = [d for (_name, d) in existing]
        overlap_count = sum(1 for (_name, d) in existing if _is_known_overlap(instrument_id, d))
        _log(f"  ℹ {instrument_id}: älteste gespeicherte Beobachtung = {min(dates_only)}, "
             f"jüngste = {max(dates_only)} ({len(existing)} Datensätze insgesamt über "
             f"{len(INSTRUMENT_SOURCE_NAMES[instrument_id])} Bezeichnung(en)"
             + (f", davon {overlap_count} in bekanntem Überlappungsfenster" if overlap_count else "")
             + ") — Plausibilität selbst prüfen, Historienlänge unterscheidet sich pro Instrument")
    else:
        _log(f"  ⚠ {instrument_id}: nach Backfill keine Datensätze vorhanden — "
             f"CFTC-Antwort leer oder market_and_exchange_names-Werte prüfen")

    return new_count


def main() -> int:
    mode = os.environ.get("COT_MODE", "weekly").strip().lower()
    if mode not in ("weekly", "backfill"):
        _log(f"⚠ Unbekannter COT_MODE='{mode}' — falle zurück auf 'weekly'.")
        mode = "weekly"

    only_instrument = os.environ.get("COT_INSTRUMENT", "").strip().upper() or None
    instrument_ids = (
        [only_instrument]
        if only_instrument and only_instrument in INSTRUMENT_SOURCE_NAMES
        else list(INSTRUMENT_SOURCE_NAMES.keys())
    )
    if only_instrument and only_instrument not in INSTRUMENT_SOURCE_NAMES:
        _log(f"⚠ COT_INSTRUMENT='{only_instrument}' unbekannt — "
             f"laufe über alle {len(INSTRUMENT_SOURCE_NAMES)} Instrumente.")

    _log(f"Modus: {mode} — {len(instrument_ids)} Instrument(e): {', '.join(instrument_ids)}")

    total_new = 0
    failed = []
    for instrument_id in instrument_ids:
        try:
            runner = run_backfill if mode == "backfill" else run_weekly
            new_count = runner(instrument_id)
            total_new += new_count
            _log(f"  ✅ {instrument_id}: {new_count} neue Zeile(n) gespeichert")
        except Exception as e:
            # Ein Instrument darf die übrigen nicht blockieren — Spec
            # Abschnitt 8. Kein Retry über einen erneuten Lauf hinaus
            # nötig (CoT ist nicht zeitkritisch).
            _log(f"  ⚠ {instrument_id}: fehlgeschlagen ({e}) — übersprungen, nicht kritisch")
            failed.append(instrument_id)

    _log(f"Fertig — {total_new} neue Datensätze insgesamt"
         + (f" | ⚠ fehlgeschlagen: {failed}" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
