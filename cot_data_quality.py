#!/usr/bin/env python3
"""
UIQ CoT Data Quality Report
============================================================
Version 1.0 (19.09.2026, Claude + Axel + Reviewer) — "Data Quality v1.0 –
Research Entry Gate", eingefroren als Baseline nach dem VIX Historical
Availability Audit (cross-validiert gegen 3 unabhaengige CFTC-Quellen,
s. KNOWN_CROSS_VALIDATED_GAPS). Aenderungen an dieser Datei nach diesem
Einfrieren sollten den Grund benennen (neuer Instrument-Fund, neue Cross-
Validierung, etc.), nicht stillschweigend die Baseline verschieben.

Liest die vom Collector (cot_layer.py) erzeugten Normalized-Layer-Dateien
(data/cot/normalized/{instrument_id}.jsonl) und erzeugt einen
maschinenlesbaren Data-Quality-Report (cot_data_quality_report.json).

Ausdruecklich NICHT Bestandteil dieses Skripts:
  - Feature-Berechnung (Net Position, Percentile, Delta4W/Delta12W)
  - Score/Gewichtung/HMM-Variable
  - Konsolidierung der Russell-ICE/CME-Ueberlappung ("welche Quelle ist
    richtiger" ist KEINE Frage, die dieses Skript beantwortet)
  - MCM/BN/Strategy-Gate-Integration
Reine Diagnose der Rohdatenqualitaet. Der Report darf Zahlen ausgeben
("ICE_CME_POSITION_CORRELATION = 0.xx"), aber keine Interpretation
("CME ist praeziser") - das waere bereits Research.

Reihenfolge (Axel-Vorgabe 19.09.2026, bewusst NICHT alphabetisch A-E):
  E - Temporal Integrity      harte Voraussetzung fuer jeden Research-Schritt
  D - Schema Stability        Voraussetzung fuer C: sind Werte ueberhaupt
                               semantisch vergleichbar?
  A - Coverage                zeitliche Vollstaendigkeit der Zeitreihen
  B - Source Mapping          dokumentiert Bezeichnungswechsel
  C - Russell ICE/CME Overlap auf einer bereits geprueften, stabilen Basis

Aufruf:
    python3 cot_data_quality.py
      -> schreibt data/cot/cot_data_quality_report.json

    COT_QUALITY_INSTRUMENT=SP500 python3 cot_data_quality.py
      -> beschraenkt auf ein Instrument (Debug/Entwicklung)
"""

import os
import sys
import json
import glob
from datetime import datetime, timedelta, timezone
from collections import defaultdict

REPORT_VERSION = "1.0"
CFTC_DATASET = "gpe5-46if"

NORMALIZED_DIR = os.path.join("data", "cot", "normalized")
REPORT_PATH = os.path.join("data", "cot", "cot_data_quality_report.json")

# Muss synchron zu cot_layer.py KNOWN_SOURCE_OVERLAPS bleiben. Bewusst hier
# dupliziert statt importiert, damit dieses Skript unabhaengig von
# cot_layer.py lauffaehig bleibt (kein Import-Pfad-Risiko in CI) - bei
# Aenderung dort MUSS hier nachgezogen werden (s. Test
# test_known_overlaps_matches_collector in tests/test_cot_data_quality.py,
# der beide Konstanten gegeneinander prueft).
KNOWN_SOURCE_OVERLAPS = {
    "RUSSELL2000": [("2017-08-15", "2018-06-05")],
}

# Cross-validierte historische Datenlücken (19.09.2026, Axel + Reviewer +
# Claude): Befunde, die gegen MEHRERE unabhaengige CFTC-Publikationsformate
# geprueft wurden, NICHT nur gegen unsere eigene Socrata-Kopie. Der Eintrag
# haelt Befund (Lage/Dauer der Luecke, welche Quellen sie zeigen) und
# Ursache (Hypothese) STRIKT getrennt - "cross_validated" bezieht sich nur
# auf die Existenz/Lage der Luecke, NIE auf die Ursache.
#
# VIX-Fall (19.09.2026): identische Luecke bestaetigt in drei unabhaengigen
# Quellen - (1) unser Collector ueber Socrata gpe5-46if (TFF), (2) CFTC-
# Direktdownload F_TFF_2006_2016.xls (TFF, andere Bezugsquelle als unsere
# API), (3) CFTC Legacy Futures Only Report (Datensatz 6dca-aqww, KOMPLETT
# andere Kategorisierung: Noncommercial/Commercial statt Dealer/Asset Mgr/
# Lev Money) - VIX existiert dort unter demselben Code 1170E1 als eigener
# Markt, fehlt aber im selben Fenster. Die Evidenz spricht damit deutlich
# gegen ein ausschliesslich TFF-spezifisches Datenproblem (nicht: schliesst
# jede denkbare TFF-spezifische Ursache logisch aus - drei uebereinstimmende
# Publikationsformate sind ein starkes Indiz, kein Beweis). NICHT belegt ist
# die Ursache - "Meldepflicht
# ausgesetzt" waere eine staerkere Aussage als die Daten hergeben. Sicher
# beobachtet ist nur: der VIX-Futures-Markt erscheint in diesem Zeitraum in
# KEINEM der geprueften CFTC-COT-Publikationsformate. Die Schwellenwert-
# Erklaerung bleibt HYPOTHESIS mit MEDIUM confidence.
KNOWN_CROSS_VALIDATED_GAPS = {
    "VIX": [
        {
            "gap_start": "2008-12-16",
            "gap_end": "2009-06-02",
            "cross_validated_sources": [
                "TFF_Socrata_gpe5-46if",
                "TFF_CFTC_F_TFF_2006_2016_xls",
                "Legacy_Futures_Only_6dca-aqww",
            ],
            "cause": {
                "status": "HYPOTHESIS",
                "hypothesis": (
                    "Der VIX-Futures-Markt erscheint in diesem Zeitraum in "
                    "keinem der geprueften CFTC-COT-Publikationsformate "
                    "(TFF und Legacy). Moegliche, NICHT belegte Erklaerung: "
                    "Open Interest/Trader-Zahl unterschritt waehrend der "
                    "Finanzkrise die CFTC-Aufnahmeschwelle fuer die COT-"
                    "Veroeffentlichung. Keine Aussage ueber eine rechtliche "
                    "Meldepflicht - dafuer geben die Daten allein nichts her."
                ),
                "confidence": "MEDIUM",
            },
            "research_implication": {
                "stable_series_start": "2009-06-02",
                "usage_before_stable_start": "RESEARCH_ONLY",
            },
            "verified_at": "2026-09-19",
        },
    ],
}

# Erwartete Kernfelder (Spec Abschnitt 4). Fehlt eines davon KOMPLETT über
# die gesamte Historie eines Instruments, ist das ein Schema-Fund, kein
# Programmfehler - wird gemeldet, nicht angenommen.
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

# Trader-Kategorien fuer Block C (Russell-Overlap-Vergleich). Bewusst ALLE
# vier statt einer einzelnen "Net Position"-Definition - Phase 2 hat noch
# nicht festgelegt, welche Kategorie fuer Features massgeblich ist, dieses
# Skript soll dieser Entscheidung nicht vorgreifen.
NET_POSITION_CATEGORIES = {
    "dealer": ("dealer_positions_long_all", "dealer_positions_short_all"),
    "asset_mgr": ("asset_mgr_positions_long", "asset_mgr_positions_short"),
    "lev_money": ("lev_money_positions_long", "lev_money_positions_short"),
    "other_rept": ("other_rept_positions_long", "other_rept_positions_short"),
}


def _log(msg: str) -> None:
    print(f"[COT-QUALITY] {msg}")


def _date_only(value):
    return value[:10] if value else value


def _parse_date(value):
    try:
        return datetime.strptime(_date_only(value), "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _to_float(value):
    """CFTC-Zahlenfelder kommen als Strings. None/leer/unparsebar -> None,
    NIE eine stille 0 - eine echte 0-Position und ein fehlender Wert sind
    fachlich verschieden."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _pearson(xs, ys):
    """Reine Stdlib-Implementierung (kein numpy-Dependency in der GHA-CI).
    Erwartet gleich lange, bereits auf None gefilterte Listen. None bei
    < 2 Punkten oder Nullvarianz."""
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x * var_y) ** 0.5


def load_instrument_rows(instrument_id: str, base_dir: str = NORMALIZED_DIR) -> list:
    path = os.path.join(base_dir, f"{instrument_id}.jsonl")
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                _log(f"  ⚠ {instrument_id}: Zeile {line_no} nicht lesbar (JSONDecodeError) - uebersprungen")
    return rows


def discover_instruments(base_dir: str = NORMALIZED_DIR) -> list:
    only = os.environ.get("COT_QUALITY_INSTRUMENT", "").strip().upper()
    if only:
        return [only]
    paths = sorted(glob.glob(os.path.join(base_dir, "*.jsonl")))
    return [os.path.splitext(os.path.basename(p))[0] for p in paths]


# ── E - Temporal Integrity ──────────────────────────────────────────────

def check_temporal_integrity(rows: list) -> dict:
    """
    E1 - Datenintegritaet: uiq_effective_date >= report_date, sinnvolle
    Datumsbeziehungen, effective_date_type aus bekannter Menge.

    E2 - Research availability ist KEINE Eigenschaft der gespeicherten
    Zeilen, sondern eine Regel fuer kuenftigen Research-Code (s.
    lookahead_filter() unten, die diese Regel implementiert und in
    tests/test_cot_data_quality.py gegen Beispieldaten geprueft wird).
    Hier wird nur bestaetigt, dass die dafuer noetigen Felder
    (uiq_effective_date, uiq_effective_date_type) vollstaendig und
    plausibel vorhanden sind - ohne das waere E2 gar nicht durchsetzbar.
    """
    known_types = {"observed", "backfill_estimate"}
    violations = []
    type_counts = defaultdict(int)

    for i, row in enumerate(rows):
        report_date = _parse_date(row.get("report_date_as_yyyy_mm_dd"))
        effective_date = _parse_date(row.get("uiq_effective_date"))
        effective_type = row.get("uiq_effective_date_type")
        type_counts[effective_type] += 1

        if report_date is None:
            violations.append({"row": i, "issue": "report_date fehlt/unlesbar"})
            continue
        if effective_date is None:
            violations.append({"row": i, "report_date": _date_only(row.get("report_date_as_yyyy_mm_dd")),
                                "issue": "uiq_effective_date fehlt/unlesbar"})
            continue
        if effective_type not in known_types:
            violations.append({"row": i, "report_date": _date_only(row.get("report_date_as_yyyy_mm_dd")),
                                "issue": f"unbekannter uiq_effective_date_type={effective_type!r}"})
        if effective_date < report_date:
            violations.append({
                "row": i,
                "report_date": _date_only(row.get("report_date_as_yyyy_mm_dd")),
                "uiq_effective_date": _date_only(row.get("uiq_effective_date")),
                "issue": "uiq_effective_date < report_date (Look-ahead-Risiko)",
            })

    status = "FAIL" if violations else "PASS"
    return {
        "status": status,
        "record_count": len(rows),
        "effective_date_type_counts": dict(type_counts),
        "violation_count": len(violations),
        "violations_sample": violations[:20],
    }


def check_cross_validated_gaps(rows: list, instrument_id: str) -> dict:
    """
    Reicht die dokumentierten Cross-Validation-Funde aus
    KNOWN_CROSS_VALIDATED_GAPS durch, PRUEFT sie aber live gegen die
    aktuellen Daten nach, statt dem statischen Eintrag blind zu vertrauen:
    (a) gap_start und gap_end muessen tatsaechlich als Beobachtungen
    vorhanden sein, (b) dazwischen darf keine einzige Beobachtung liegen.
    Weicht die Live-Pruefung vom dokumentierten Befund ab (z.B. weil ein
    spaeterer CFTC-Revisionslauf die Luecke nachtraeglich gefuellt hat),
    wird das explizit als "STALE" markiert statt die alte Aussage
    unveraendert weiterzureichen - der Registry-Eintrag beschreibt einen
    Pruefzeitpunkt (verified_at), keine ewige Wahrheit.

    Befund (cross_validated_sources, Lage/Dauer der Luecke) und Ursache
    (cause.hypothesis) bleiben strikt getrennte Felder - status bezieht
    sich NUR auf die Lueckenexistenz, nie auf die Ursachenhypothese.
    """
    entries = KNOWN_CROSS_VALIDATED_GAPS.get(instrument_id)
    if not entries:
        return {"applicable": False}

    dates = sorted(set(_date_only(r.get("report_date_as_yyyy_mm_dd")) for r in rows if r.get("report_date_as_yyyy_mm_dd")))
    date_set = set(dates)

    results = []
    for entry in entries:
        start, end = entry["gap_start"], entry["gap_end"]
        start_present = start in date_set
        end_present = end in date_set
        between = [d for d in dates if start < d < end]
        still_confirmed = start_present and end_present and not between

        results.append({
            "gap_start": start,
            "gap_end": end,
            "duration_days": (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days,
            "live_reverification": "CONFIRMED" if still_confirmed else "STALE_NEEDS_REVIEW",
            "cross_validated": True,
            "cross_validated_sources": entry["cross_validated_sources"],
            "cause": entry["cause"],
            "research_implication": entry["research_implication"],
            "verified_at": entry["verified_at"],
        })

    return {"applicable": True, "findings": results}


def lookahead_filter(rows: list, observation_date) -> list:
    """
    E2 als wiederverwendbare Funktion, NICHT nur Dokumentation: gibt genau
    die Zeilen zurueck, deren uiq_effective_date <= observation_date liegt.
    Jeder kuenftige Research-Code MUSS diese Funktion (oder eine aequivalente
    Pruefung) verwenden, statt report_date_as_yyyy_mm_dd direkt gegen
    observation_date zu vergleichen - genau das waere der Look-ahead-Fehler,
    den Block E verhindern soll. Siehe tests/test_cot_data_quality.py fuer
    den Beweis, dass dies tatsaechlich Zeilen ausschliesst, die sonst
    faelschlich als "verfuegbar" gegolten haetten.
    """
    if isinstance(observation_date, str):
        observation_date = _parse_date(observation_date)
    result = []
    for row in rows:
        eff = _parse_date(row.get("uiq_effective_date"))
        if eff is not None and eff <= observation_date:
            result.append(row)
    return result


# ── D - Schema Stability ────────────────────────────────────────────────

def _classify_anomaly(field: str) -> tuple:
    """
    Trennt Befund und Hypothese (Axel-Vorgabe): ein Feld-Gap wird NICHT
    automatisch als CFTC-Unterdrueckung erklaert, sondern als
    REVIEW_REQUIRED markiert, wenn es zum bekannten Muster passt (traders_*-
    Felder: plausible Ursache ist ein Schwellenwert/Vertraulichkeitsregel
    bei zu wenigen Marktteilnehmern in dieser Kategorie) - aber diese
    Erklaerung bleibt eine unverifizierte Hypothese, keine Feststellung.
    Alles ausserhalb dieses Musters bleibt ein unklassifizierter Gap ohne
    Erklaerungsversuch (z.B. der 2010-07-20-Fund bei change_in_* - eine
    isolierte fehlende Woche mitten in einer sonst durchgehenden Reihe ist
    KEIN erwartetes Threshold-Muster und braucht eine eigene Pruefung).
    """
    if field.startswith("traders_"):
        return "REVIEW_REQUIRED", (
            "threshold/confidentiality-related suppression (Hypothese: CFTC "
            "unterdrueckt den Trader-Count in dieser Kategorie evtl., wenn zu "
            "wenige Marktteilnehmer melden - noch NICHT gegen offizielle "
            "CFTC-Dokumentation verifiziert)"
        )
    return "UNCLASSIFIED_GAP", None


def check_schema_stability(rows: list) -> dict:
    """
    Prueft nicht nur "existiert das Feld jemals", sondern wann es zum
    ersten/letzten Mal auftritt bzw. verschwindet - und ob eine Luecke
    (fehlt, obwohl vorher UND nachher vorhanden) eine echte Anomalie ist
    statt einer plausiblen "erste Beobachtung hat noch kein change_in_*"-
    Situation.

    Status-Stufen (bewusst getrennt, Axel-Vorgabe 19.09.2026): PASS (keine
    Funde) < REVIEW_REQUIRED (nur Funde mit bekanntem, aber unverifiziertem
    Erklaerungsmuster, z.B. traders_*) < WARN (mindestens ein Fund OHNE
    Erklaerungsmuster, oder ein explizit erwartetes Kernfeld fehlt komplett).
    REVIEW_REQUIRED ist ausdruecklich NICHT "geklaert" - nur von "unerklaert"
    unterschieden.
    """
    if not rows:
        return {"status": "FAIL", "reason": "keine Zeilen vorhanden"}

    rows_sorted = sorted(rows, key=lambda r: _date_only(r.get("report_date_as_yyyy_mm_dd")) or "")
    fields_seen_at = defaultdict(list)  # field -> [report_date, ...] wo vorhanden
    all_dates = []

    for row in rows_sorted:
        d = _date_only(row.get("report_date_as_yyyy_mm_dd"))
        all_dates.append(d)
        for k, v in row.items():
            if v is not None:
                fields_seen_at[k].append(d)

    missing_explicit = [f for f in EXPLICIT_FIELDS if f not in fields_seen_at]

    field_reports = {}
    anomalies = []
    for field, dates_present in fields_seen_at.items():
        present_set = set(dates_present)
        first_present = min(dates_present)
        last_present = max(dates_present)
        # Zeilen im Bereich [first_present, last_present], wo das Feld
        # eigentlich vorhanden sein sollte, aber fehlt:
        in_range = [d for d in all_dates if first_present <= d <= last_present]
        missing_in_range = [d for d in in_range if d not in present_set]
        field_reports[field] = {
            "first_present": first_present,
            "last_present": last_present,
            "coverage_in_range_pct": round(100 * (len(in_range) - len(missing_in_range)) / len(in_range), 2) if in_range else None,
            "missing_in_range_count": len(missing_in_range),
        }
        if missing_in_range and field not in ("historical_source_overlap",):
            # Ausnahme: fehlt NUR am allerersten Datenpunkt insgesamt (kein
            # Vorlaufwert fuer change_in_* moeglich) - das ist plausibel,
            # keine Anomalie.
            unexplained = [d for d in missing_in_range if d != all_dates[0]]
            if unexplained:
                classification, hypothesis = _classify_anomaly(field)
                anomalies.append({
                    "field": field,
                    "classification": classification,
                    "hypothesis": hypothesis,
                    "missing_dates": unexplained[:10],
                    "missing_count_total": len(unexplained),
                })

    review_required = [a for a in anomalies if a["classification"] == "REVIEW_REQUIRED"]
    unclassified = [a for a in anomalies if a["classification"] == "UNCLASSIFIED_GAP"]

    if unclassified or missing_explicit:
        status = "WARN"
    elif review_required:
        status = "REVIEW_REQUIRED"
    else:
        status = "PASS"

    return {
        "status": status,
        "missing_explicit_fields": missing_explicit,
        "anomaly_count": len(anomalies),
        "review_required_count": len(review_required),
        "unclassified_gap_count": len(unclassified),
        "anomalies_sample": anomalies[:30],
        "field_first_last_seen": {
            f: {"first_present": r["first_present"], "last_present": r["last_present"]}
            for f, r in field_reports.items()
        },
    }


# ── A - Coverage ────────────────────────────────────────────────────────

def check_coverage(rows: list) -> dict:
    """
    Wochenabstaende pro (market_and_exchange_names)-Serie getrennt
    berechnen - bei Russell wuerden ICE- und CME-Zeilen sonst faelschlich
    gegeneinander als "Luecke" gewertet, obwohl es zwei parallele Serien
    sind. Feiertage/Verschiebungen werden NICHT automatisch als Fehler
    gezaehlt (Toleranzband), sondern nur echte Ausreisser.
    """
    by_name = defaultdict(list)
    seen_keys = defaultdict(int)
    for row in rows:
        name = row.get("market_and_exchange_names")
        d = _date_only(row.get("report_date_as_yyyy_mm_dd"))
        if not name or not d:
            continue
        by_name[name].append(d)
        seen_keys[(name, d)] += 1

    duplicates = [{"market_and_exchange_names": k[0], "report_date": k[1], "count": c}
                  for k, c in seen_keys.items() if c > 1]

    per_series = {}
    material_gap_found = False
    for name, dates in by_name.items():
        dates_sorted = sorted(dates)
        gaps = []
        for a, b in zip(dates_sorted, dates_sorted[1:]):
            delta = (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days
            if delta > 7:
                gaps.append({"from": a, "to": b, "days": delta})
        minor_gaps = [g for g in gaps if 7 < g["days"] <= 14]
        material_gaps = [g for g in gaps if g["days"] > 14]
        if material_gaps:
            material_gap_found = True
        per_series[name] = {
            "record_count": len(dates_sorted),
            "earliest": dates_sorted[0],
            "latest": dates_sorted[-1],
            "minor_gaps": minor_gaps,
            "material_gaps": material_gaps,
        }

    if duplicates or material_gap_found:
        overall = "MATERIAL_GAPS" if material_gap_found else "MINOR_GAPS"
    elif any(s["minor_gaps"] for s in per_series.values()):
        overall = "MINOR_GAPS"
    else:
        overall = "COMPLETE"

    return {
        "coverage_status": overall,
        "duplicate_keys": duplicates,
        "per_source_name": per_series,
    }


# ── B - Source Mapping ──────────────────────────────────────────────────

def check_source_mapping(rows: list) -> dict:
    """Dokumentiert nur, macht keine Konsolidierungs-Entscheidung."""
    by_name = defaultdict(list)
    for row in rows:
        name = row.get("market_and_exchange_names")
        d = _date_only(row.get("report_date_as_yyyy_mm_dd"))
        if name and d:
            by_name[name].append(d)

    transitions = []
    for name, dates in by_name.items():
        dates_sorted = sorted(dates)
        transitions.append({
            "market_and_exchange_names": name,
            "first_report_date": dates_sorted[0],
            "last_report_date": dates_sorted[-1],
            "record_count": len(dates_sorted),
        })
    transitions.sort(key=lambda t: t["first_report_date"])
    return {
        "distinct_source_names": len(transitions),
        "transitions": transitions,
    }


# ── C - Russell ICE/CME Overlap ─────────────────────────────────────────

def check_russell_overlap(rows: list, instrument_id: str) -> dict:
    windows = KNOWN_SOURCE_OVERLAPS.get(instrument_id)
    if not windows:
        return {"applicable": False}

    by_date_name = defaultdict(dict)
    for row in rows:
        d = _date_only(row.get("report_date_as_yyyy_mm_dd"))
        name = row.get("market_and_exchange_names")
        if row.get("historical_source_overlap") and d and name:
            by_date_name[d][name] = row

    dates_with_pair = sorted(d for d, names in by_date_name.items() if len(names) == 2)
    dates_with_single = sorted(d for d, names in by_date_name.items() if len(names) == 1)

    source_names = sorted({n for names in by_date_name.values() for n in names})
    if len(source_names) != 2:
        return {
            "applicable": True,
            "status": "WARN",
            "reason": f"erwartet genau 2 Quellbezeichnungen im Overlap-Fenster, gefunden: {source_names}",
            "windows": windows,
        }
    name_a, name_b = source_names

    oi_a, oi_b = [], []
    net_series = {cat: {"a": [], "b": []} for cat in NET_POSITION_CATEGORIES}
    per_date_rows = []

    for d in dates_with_pair:
        row_a = by_date_name[d][name_a]
        row_b = by_date_name[d][name_b]
        ov_a = _to_float(row_a.get("open_interest_all"))
        ov_b = _to_float(row_b.get("open_interest_all"))
        entry = {"report_date": d, f"open_interest_{name_a}": ov_a, f"open_interest_{name_b}": ov_b}
        if ov_a is not None and ov_b is not None:
            oi_a.append(ov_a)
            oi_b.append(ov_b)
        for cat, (long_f, short_f) in NET_POSITION_CATEGORIES.items():
            la, sa = _to_float(row_a.get(long_f)), _to_float(row_a.get(short_f))
            lb, sb = _to_float(row_b.get(long_f)), _to_float(row_b.get(short_f))
            net_a = (la - sa) if (la is not None and sa is not None) else None
            net_b = (lb - sb) if (lb is not None and sb is not None) else None
            entry[f"net_{cat}_{name_a}"] = net_a
            entry[f"net_{cat}_{name_b}"] = net_b
            if net_a is not None and net_b is not None:
                net_series[cat]["a"].append(net_a)
                net_series[cat]["b"].append(net_b)
        per_date_rows.append(entry)

    oi_diff_abs = [abs(a - b) for a, b in zip(oi_a, oi_b)]
    oi_diff_rel_to_oi = [abs(a - b) / a for a, b in zip(oi_a, oi_b) if a] if oi_a else []

    category_stats = {}
    for cat, series in net_series.items():
        a, b = series["a"], series["b"]
        if not a:
            category_stats[cat] = {"pearson_correlation": None, "n": 0}
            continue
        diffs = [x - y for x, y in zip(a, b)]
        same_sign = sum(1 for x, y in zip(a, b) if (x >= 0) == (y >= 0))
        category_stats[cat] = {
            "n": len(a),
            "pearson_correlation": round(_pearson(a, b), 4) if _pearson(a, b) is not None else None,
            "mean_abs_diff": round(sum(abs(x) for x in diffs) / len(diffs), 2),
            "directional_agreement_pct": round(100 * same_sign / len(a), 2),
        }

    return {
        "applicable": True,
        "status": "PASS",
        "windows": windows,
        "source_names": {"a": name_a, "b": name_b},
        "dates_with_both_sources": len(dates_with_pair),
        "dates_with_single_source_in_window": dates_with_single,
        "open_interest_correlation": round(_pearson(oi_a, oi_b), 4) if oi_a and _pearson(oi_a, oi_b) is not None else None,
        "open_interest_mean_abs_diff": round(sum(oi_diff_abs) / len(oi_diff_abs), 2) if oi_diff_abs else None,
        "open_interest_mean_abs_diff_relative_to_oi_a": round(sum(oi_diff_rel_to_oi) / len(oi_diff_rel_to_oi), 4) if oi_diff_rel_to_oi else None,
        "net_position_by_category": category_stats,
        # bewusst KEINE Zeile wie "CME repraesentativer" o.ae. - reine Zahlen.
    }


# ── Zusammenfuehrung ─────────────────────────────────────────────────────

def _worst_status(statuses: list) -> str:
    order = {"PASS": 0, "COMPLETE": 0,
             "REVIEW_REQUIRED": 1, "MINOR_GAPS": 1,
             "WARN": 2, "MATERIAL_GAPS": 2,
             "FAIL": 3}
    worst = "PASS"
    for s in statuses:
        if s and order.get(s, 3) > order.get(worst, 0):
            worst = s
    return worst


def build_report(base_dir: str = NORMALIZED_DIR) -> dict:
    instrument_ids = discover_instruments(base_dir)
    _log(f"Instrumente: {', '.join(instrument_ids) if instrument_ids else '(keine Dateien gefunden)'}")

    checks = {
        "temporal_integrity": {},
        "schema_stability": {},
        "coverage": {},
        "source_mapping": {},
        "russell_overlap": {},
        "cross_validated_gaps": {},
    }
    total_records = 0
    statuses = []

    for instrument_id in instrument_ids:
        rows = load_instrument_rows(instrument_id, base_dir)
        total_records += len(rows)
        if not rows:
            _log(f"  ⚠ {instrument_id}: keine Datensaetze - uebersprungen")
            continue

        e = check_temporal_integrity(rows)
        d = check_schema_stability(rows)
        a = check_coverage(rows)
        b = check_source_mapping(rows)

        checks["temporal_integrity"][instrument_id] = e
        checks["schema_stability"][instrument_id] = d
        checks["coverage"][instrument_id] = a
        checks["source_mapping"][instrument_id] = b
        statuses.extend([e["status"], d["status"], a["coverage_status"]])

        c = check_russell_overlap(rows, instrument_id)
        if c.get("applicable"):
            checks["russell_overlap"][instrument_id] = c
            if c.get("status"):
                statuses.append(c["status"])

        g = check_cross_validated_gaps(rows, instrument_id)
        if g.get("applicable"):
            checks["cross_validated_gaps"][instrument_id] = g
            # STALE_NEEDS_REVIEW ist ein eigenstaendiger Warnzustand -
            # fliesst in overall_status ein wie jeder andere WARN-Fund.
            if any(f["live_reverification"] == "STALE_NEEDS_REVIEW" for f in g["findings"]):
                statuses.append("WARN")

        _log(f"  ✓ {instrument_id}: {len(rows)} Zeilen geprueft "
             f"(E={e['status']}, D={d['status']}, A={a['coverage_status']})")

    overall_status = _worst_status(statuses) if statuses else "FAIL"

    # research_readiness: DREI Zustaende statt Boolean (Axel-Korrektur
    # 19.09.2026) - "Data Quality PASS" heisst NICHT automatisch "fachlich
    # freigegeben". READY / CONDITIONAL / BLOCKED, rein regelbasiert aus
    # den obigen Befunden, KEINE fachliche Zusatzbewertung.
    #
    # WICHTIGE EINSCHRAENKUNG (Reviewer, 19.09.2026): a_material ist GLOBAL
    # (any() ueber ALLE Instrumente) - ein einzelnes Instrument mit
    # MATERIAL_GAPS (aktuell: VIX) zieht regime_backtest fuer das GESAMTE
    # Universum auf CONDITIONAL, auch wenn ein konkretes Vorhaben das
    # betroffene Instrument gar nicht braucht. Das ist als Data-Quality-
    # Sicherheitsgurt fuer v1.0 gewollt und vertretbar, aber grob: es ist
    # KEINE Aussage, dass jedes einzelne Feature-/Regime-Research-Vorhaben
    # von derselben Luecke betroffen ist. Sobald der CoT Feature Layer
    # gebaut wird, sollte die Freigabe FEATURE-/INSTRUMENTBEZOGEN werden
    # (s. instrument_notes unten fuer den ersten Schritt in diese Richtung -
    # z.B. ein reines SP500-Feature ist ab 2006-06-13 stable_from, unabhaengig
    # von der VIX-Luecke; ein VIX-Feature erst ab 2009-06-02). Diese
    # Verfeinerung ist bewusst NICHT Teil von v1.0.
    e_fail = any(v["status"] == "FAIL" for v in checks["temporal_integrity"].values())
    d_warn = any(v["status"] == "WARN" for v in checks["schema_stability"].values())
    d_review_required = any(v["status"] == "REVIEW_REQUIRED" for v in checks["schema_stability"].values())
    a_material = any(v["coverage_status"] == "MATERIAL_GAPS" for v in checks["coverage"].values())
    russell_pending = "RUSSELL2000" in checks["russell_overlap"] and checks["russell_overlap"]["RUSSELL2000"].get("applicable")

    if e_fail:
        feature_research = "BLOCKED"
    elif d_warn:
        feature_research = "CONDITIONAL"
    elif d_review_required:
        feature_research = "CONDITIONAL"
    else:
        feature_research = "READY"

    if feature_research == "BLOCKED":
        regime_backtest = "BLOCKED"
    elif feature_research == "CONDITIONAL" or a_material:
        regime_backtest = "CONDITIONAL"
    else:
        regime_backtest = "READY"

    full_universe_research = (
        feature_research == "READY"
        and regime_backtest == "READY"
        and not russell_pending
    )

    # instrument_notes: granulare Auflage je Instrument, ZUSAETZLICH zu den
    # drei globalen Ampel-Feldern oben - z.B. VIX ist insgesamt CONDITIONAL,
    # aber innerhalb von VIX gilt eine klare zeitliche Grenze (stabile Reihe
    # erst ab stable_series_start). Nur fuer Instrumente mit einem Eintrag
    # in KNOWN_CROSS_VALIDATED_GAPS - sagt NICHTS ueber Instrumente ohne
    # Eintrag aus (die folgen weiterhin nur den drei globalen Feldern).
    instrument_notes = {}
    for instrument_id, gap_check in checks["cross_validated_gaps"].items():
        for finding in gap_check["findings"]:
            note = instrument_notes.setdefault(instrument_id, {})
            note["stable_series_start"] = finding["research_implication"]["stable_series_start"]
            note["usage_before_stable_start"] = finding["research_implication"]["usage_before_stable_start"]
            note["cause_status"] = finding["cause"]["status"]

    reasons = []
    if e_fail:
        reasons.append("Temporal Integrity (E) FAIL - Look-ahead-Risiko, muss vor jedem Research-Schritt behoben werden")
    if d_warn:
        reasons.append("Schema Stability (D): mindestens ein unklassifizierter Gap (UNCLASSIFIED_GAP) oder fehlendes Kernfeld - noch nicht erklaert")
    if d_review_required:
        reasons.append("Schema Stability (D): REVIEW_REQUIRED-Funde (z.B. traders_*) - Hypothese vorhanden, aber nicht gegen CFTC-Dokumentation verifiziert")
    if a_material:
        reasons.append("Coverage (A) zeigt MATERIAL_GAPS bei mindestens einem Instrument")
    if russell_pending:
        reasons.append("Russell ICE/CME Overlap: Research Decision Pending (keine Konsolidierung getroffen, Zahlen liegen vor - full_universe_research bleibt false, bis das entschieden ist)")
    if instrument_notes:
        for inst, note in instrument_notes.items():
            reasons.append(f"{inst}: cross-validierte Luecke, stabile Reihe erst ab {note['stable_series_start']} (Ursache: {note['cause_status']}) - s. instrument_notes")
    if not reasons:
        reasons.append("keine blockierenden Befunde - volle Freigabe fuer Phase 2 (Feature Research) ueber das gesamte Instrumenten-Universum moeglich")

    report = {
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "dataset": CFTC_DATASET,
            "instrument_count": len(instrument_ids),
            "record_count": total_records,
        },
        "overall_status": overall_status,
        "checks": checks,
        "research_readiness": {
            "feature_research": feature_research,
            "regime_backtest": regime_backtest,
            "full_universe_research": full_universe_research,
            "instrument_notes": instrument_notes,
            "reason": "; ".join(reasons),
        },
    }
    return report


def main() -> int:
    report = build_report()
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    _log(f"Report geschrieben: {REPORT_PATH} (overall_status={report['overall_status']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
