#!/usr/bin/env python3
"""
audit_ticker_sources.py — v0.1 (23.09.2026)

CHANGELOG:
v0.2 (23.09.2026, Claude): Fund beim Testen (CEG zeigte faelschlich
     "universes: []", obwohl real gescannt) — SECTOR_WATCHLISTS selbst ist
     im echten Code (market_aggregator.py Zeile 2182,
     "[t for wl in SECTOR_WATCHLISTS.values() for t in wl]") eine der
     summierten Universe-Quellen, nicht nur eine Sektor-Tag-Quelle. Jetzt
     als eigene Universe-Quelle mitgefuehrt, sonst haette die Migration
     faelschlich angenommen, rein thematisch getaggte Ticker wie CEG
     wuerden nicht gescannt.
v0.1 (23.09.2026, Claude + Axel + Reviewer): Erstfassung. Phase A der
     TICKER_MASTER-Migration (Reviewer-Vorschlag, 23.09.2026) — beantwortet
     die Frage "Kann die bestehende ~12.000-Zeilen market_aggregator.py ohne
     Informationsverlust auf einen Master-Datensatz abgebildet werden?"
     BEVOR irgendein Code umgebaut wird.

ZWECK
-----
Read-only Audit — liest ALLE bekannten Ticker-Quell-Listen aus
market_aggregator.py per AST-Parsing aus (KEIN Import des Moduls, keine
Netzwerk-/Seiteneffekte, keine Ausfuehrung von Business-Logik) und baut pro
Ticker einen Datensatz {universes, sectors, category, bear}, exakt nach dem
im Chat abgestimmten TICKER_MASTER-Schema. Klassifiziert danach jeden
Ticker in drei Klassen:

  A. EINDEUTIG        — genau eine plausible Zuordnung pro Dimension
  B. MEHRFACH_OK       — mehrere Zuordnungen, aber nicht widersprüchlich
                          (z.B. Mitgliedschaft in mehreren Universe-Quellen
                          UND/ODER mehreren thematischen Sektoren — beides
                          ist im bestehenden System ausdruecklich gewollt)
  C. KONFLIKT          — echte Widersprueche, die eine automatische
                          Migration NICHT selbststaendig entscheiden darf
                          (z.B. gleichzeitig als ETF UND als Einzelaktie
                          gefuehrt, gleichzeitig als Krypto UND als Aktie)

WICHTIG: Dieses Skript AENDERT NICHTS. Es ist reine Diagnose fuer die
Migrationsentscheidung — Phase B (TICKER_MASTER parallel erzeugen + OLD==NEW
Vergleichstest) und Phase C (alte Listen entfernen) sind bewusst NICHT Teil
dieser Version.

VERWENDUNG
----------
    python audit_ticker_sources.py market_aggregator.py
    python audit_ticker_sources.py market_aggregator.py --json out.json
"""

import argparse
import ast
import json
import sys
from collections import defaultdict

# Bekannte Ticker-Quell-Listen aus market_aggregator.py, per Live-Grep am
# 23.09.2026 identifiziert (s. Chat-Verlauf). EQUITY_UNIVERSE_LISTS sind
# reine Aktien-/ADR-Universen, KEIN ETF/Krypto — Mitgliedschaft dort UND in
# einer ETF-/Krypto-Liste ist ein Klasse-C-Konflikt.
EQUITY_UNIVERSE_LISTS = [
    "SP500_TICKERS", "NASDAQ100_EXTRA", "MDAX_TICKERS", "TECDAX_TICKERS",
    "EUROSTOXX_TICKERS_LEGACY", "EU_ADR_TICKERS", "INTL_TIER1",
    "STOXX_EU_EXTRA",
]
ETF_LISTS = ["SECTOR_ETFS_BROAD", "SECTOR_ETFS_US", "SECTOR_ETFS_EXUS"]
CRYPTO_LIST = "CRYPTO_TICKERS"
BEAR_LISTS = {"BEAR_US_TICKERS": "us", "BEAR_DE_EU_TICKERS": "eu"}
SECTOR_WATCHLISTS_NAME = "SECTOR_WATCHLISTS"

ALL_LIST_NAMES = set(EQUITY_UNIVERSE_LISTS) | set(ETF_LISTS) | {CRYPTO_LIST} | set(BEAR_LISTS.keys()) | {SECTOR_WATCHLISTS_NAME}


def extract_literal_assignments(source_path):
    """Parst die Datei per AST, extrahiert NUR die Werte der bekannten
    Listen-/Dict-Namen via ast.literal_eval auf den jeweiligen Assign-Value-
    Knoten. Keine Ausfuehrung von Code, kein Import — sicher fuer eine
    12.000-Zeilen-Produktionsdatei mit Netzwerk-Calls/Seiteneffekten an
    anderer Stelle."""
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=source_path)

    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name not in ALL_LIST_NAMES:
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            # z.B. SECTOR_ETFS = list(dict.fromkeys(A+B+C)) ist KEIN reines
            # Literal (Funktionsaufruf) — bewusst uebersprungen, betrifft
            # keine der hier gelisteten Namen, nur zur Sicherheit geloggt.
            print(f"  ⚠️  {name}: kein reines Literal (Ausdruck statt Wert) — übersprungen", file=sys.stderr)
            continue
        # Bei mehrfacher Zuweisung desselben Namens (sollte nicht vorkommen,
        # aber defensiv): letzte gewinnt, wie in Python selbst auch.
        found[name] = value
    return found


def build_ticker_master_from_audit(literals):
    """Baut pro Ticker {universes, sectors, category, bear} aus den
    extrahierten Rohlisten — exakt das im Chat abgestimmte Schema."""
    records = defaultdict(lambda: {"universes": [], "sectors": [], "category": None, "bear": None})

    for list_name in EQUITY_UNIVERSE_LISTS:
        for t in literals.get(list_name, []):
            records[t]["universes"].append(list_name)

    for list_name in ETF_LISTS:
        for t in literals.get(list_name, []):
            records[t]["universes"].append(list_name)
            if records[t]["category"] not in (None, "etf"):
                records[t]["_category_conflict"] = True
            records[t]["category"] = "etf"

    for t in literals.get(CRYPTO_LIST, []):
        records[t]["universes"].append(CRYPTO_LIST)
        if records[t]["category"] not in (None, "crypto"):
            records[t]["_category_conflict"] = True
        records[t]["category"] = "crypto"

    for list_name, region in BEAR_LISTS.items():
        for t in literals.get(list_name, []):
            records[t]["universes"].append(list_name)
            if records[t]["bear"] not in (None, region):
                records[t]["_bear_conflict"] = True
            records[t]["bear"] = region

    sector_watchlists = literals.get(SECTOR_WATCHLISTS_NAME, {})
    for sector, tickers in sector_watchlists.items():
        for t in tickers:
            records[t]["sectors"].append(sector)
            # FIX (v0.2, 23.09.2026, Live-Fund beim Testen): build_ticker_
            # universe() zaehlt "[t for wl in SECTOR_WATCHLISTS.values() for
            # t in wl]" selbst als eine der summierten Universe-Quellen (s.
            # market_aggregator.py Zeile 2182) — ein Ticker, der NUR in
            # SECTOR_WATCHLISTS steht (Beispiel: CEG), ist trotzdem im
            # Scan-Universum, nicht nur "thematisch getaggt ohne Scan".
            # Ohne diesen Zusatz haette der Audit CEG faelschlich als
            # "universes: []" ausgewiesen.
            if SECTOR_WATCHLISTS_NAME not in records[t]["universes"]:
                records[t]["universes"].append(SECTOR_WATCHLISTS_NAME)

    return dict(records)


def classify(records):
    """Klasse A/B/C je Ticker. C = echter Widerspruch (category-Konflikt
    ETF-vs-Crypto, oder Mitgliedschaft in einer Equity-Universe-Liste UND
    gleichzeitig als ETF/Krypto gefuehrt, oder bear-Regionskonflikt)."""
    classA, classB, classC = {}, {}, {}

    for sym, rec in records.items():
        universes = rec["universes"]
        sectors = rec["sectors"]
        category = rec["category"]
        has_category_conflict = rec.get("_category_conflict", False)
        has_bear_conflict = rec.get("_bear_conflict", False)

        is_in_equity_list = any(u in EQUITY_UNIVERSE_LISTS for u in universes)
        is_in_etf_or_crypto = category in ("etf", "crypto")

        reasons = []
        if has_category_conflict:
            reasons.append("category-Konflikt (ETF UND Krypto gleichzeitig)")
        if has_bear_conflict:
            reasons.append("bear-Regionskonflikt (US UND EU gleichzeitig)")
        if is_in_equity_list and is_in_etf_or_crypto:
            reasons.append(f"in Equity-Universe-Liste UND als {category} gefuehrt")

        clean_rec = {k: v for k, v in rec.items() if not k.startswith("_")}

        if reasons:
            classC[sym] = {**clean_rec, "konflikt_gruende": reasons}
        elif len(universes) > 1 or len(sectors) > 1:
            classB[sym] = clean_rec
        else:
            classA[sym] = clean_rec

    return classA, classB, classC


def main():
    parser = argparse.ArgumentParser(description="Read-only Audit der Ticker-Quell-Listen in market_aggregator.py (Phase A, TICKER_MASTER-Migration)")
    parser.add_argument("source_file", help="Pfad zu market_aggregator.py")
    parser.add_argument("--json", help="Optional: vollstaendigen Audit als JSON-Datei schreiben")
    args = parser.parse_args()

    print(f"Lese {args.source_file} per AST (kein Import, keine Ausfuehrung)...")
    literals = extract_literal_assignments(args.source_file)

    print(f"\nGefundene Listen: {len(literals)} von {len(ALL_LIST_NAMES)} erwarteten")
    missing = ALL_LIST_NAMES - set(literals.keys())
    if missing:
        print(f"  ⚠️  NICHT gefunden (evtl. kein reines Literal, s.o.): {sorted(missing)}")
    for name in sorted(literals.keys()):
        val = literals[name]
        count = len(val) if isinstance(val, (list, dict)) else "?"
        print(f"  {name}: {count} Einträge")

    records = build_ticker_master_from_audit(literals)
    classA, classB, classC = classify(records)

    total = len(records)
    print(f"\n=== Klassifikation: {total} eindeutige Ticker insgesamt ===")
    print(f"  A. EINDEUTIG:    {len(classA)} ({100*len(classA)/total:.1f}%)")
    print(f"  B. MEHRFACH_OK:  {len(classB)} ({100*len(classB)/total:.1f}%)")
    print(f"  C. KONFLIKT:     {len(classC)} ({100*len(classC)/total:.1f}%)")

    if classC:
        print(f"\n=== Klasse C — KONFLIKTE, NICHT automatisch entscheidbar ({len(classC)}) ===")
        for sym, rec in sorted(classC.items()):
            print(f"  {sym}: {rec['konflikt_gruende']}")
            print(f"    universes={rec['universes']}, sectors={rec['sectors']}, category={rec['category']}, bear={rec['bear']}")

    if args.json:
        out = {
            "meta": {
                "source_file": args.source_file,
                "total_tickers": total,
                "class_a_count": len(classA),
                "class_b_count": len(classB),
                "class_c_count": len(classC),
            },
            "class_a_eindeutig": classA,
            "class_b_mehrfach_ok": classB,
            "class_c_konflikt": classC,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nVollständiger Audit geschrieben: {args.json}")

    return 0 if not classC else 1


if __name__ == "__main__":
    sys.exit(main())
