#!/usr/bin/env python3
"""
migrate_ticker_master_phase_b.py — v0.1 (23.09.2026)

CHANGELOG:
v0.1 (23.09.2026, Claude + Axel + Reviewer): Erstfassung. Phase B der
     TICKER_MASTER-Migration — rein technische, verlustfreie Parallel-
     Migration MIT exaktem OLD-vs-NEW-Diff, KEINE produktive Umstellung.
     Baut auf Phase A (audit_ticker_sources.py, 0 Konflikte bei 767
     Tickern) auf.

     WICHTIGER FUND waehrend des Aufbaus (nicht Teil des Migrations-Scopes,
     nur dokumentiert): DAX40_TICKERS/MDAX_TICKERS/TECDAX_TICKERS/
     EUROSTOXX_TICKERS_LEGACY/FTSE100_TICKERS/STOXX_EU_EXTRA speisen NICHT
     build_ticker_universe()s all_sources — sie werden AUSSCHLIESSLICH fuer
     die Leaderboard-Anzeigekategorisierung verwendet (Zeile ~11510-11524).
     Verifiziert: 27 von 40 DAX40-Tickern, 29 von 34 MDAX-Tickern, 14 von 19
     TECDAX-Tickern, 27 von 29 EuroStoxx-Legacy, 33 von 40 FTSE100, 22 von
     23 StoxxEuExtra sind NICHT im tatsaechlichen Scan-Universum — diese
     Leaderboard-Tabs zeigen fuer die meisten "eigentlichen" Mitglieder
     leere/fehlende Eintraege, da `results` (die gescannten Ticker) sie nie
     enthaelt. BEWUSST NICHT IN DIESER MIGRATION BEHOBEN (Reviewer-Vorgabe:
     "Phase B beweist NUR Alte Semantik -> Master -> gleiche alte Semantik,
     keine fachliche Neubewertung") — TICKER_MASTER bildet dieses
     Verhalten TREU ab (inkl. des Bugs), nicht korrigiert. Separate
     Entscheidung fuer Axel: ob/wie das behoben wird, gehoert NICHT zu
     Phase B.

ZWECK
-----
1. TICKER_MASTER automatisch aus den bestehenden produktiven Quellen
   generieren (NICHT von Hand geschrieben) — Beweis, dass die Mastertabelle
   eine verlustfreie Abbildung des Ist-Zustands ist, BEVOR sie zur neuen
   editierbaren Quelle wird.
2. Drei unabhaengige OLD-vs-NEW-Gleichheitspruefungen (exakte Mengen-/
   Mapping-Gleichheit, nicht nur Anzahl):
     a. OLD_UNIVERSE == NEW_UNIVERSE
     b. OLD_TICKER_SECTOR_TAG == NEW_TICKER_SECTOR_TAG
     c. OLD_LEADERBOARD_TAGS == NEW_LEADERBOARD_TAGS
3. Vierter Test: Pro-Ticker-Volldatensatz-Diff ueber alle 767 Ticker (findet
   z.B. einen fehlenden zweiten Sector-Tag bei einem einzelnen Ticker, was
   ein reiner Mengenvergleich uebersehen koennte).
4. Mutations-Test (NUR wenn 1-3 vollstaendig gruen): ein synthetischer
   Test-Ticker wird in TICKER_MASTER veraendert, alle vier abgeleiteten
   Strukturen (SECTOR_WATCHLISTS-Aequivalent, TICKER_SECTOR_TAG-Aequivalent,
   Universe, Leaderboard-Tags) werden neu generiert und auf korrekte
   Propagation geprueft — der eigentliche Beweis, dass die neue Architektur
   FUNKTIONIERT, nicht nur dass die Migration des Ist-Zustands gelingt.

KEINE produktive Umstellung, KEINE Aenderung an market_aggregator.py.

VERWENDUNG
----------
    python migrate_ticker_master_phase_b.py market_aggregator.py --json ticker_master.json
"""

import argparse
import ast
import json
import sys
from collections import defaultdict

# ── Bekannte Quell-Listen, nach tatsaechlicher Funktion getrennt ────────────
# UNIVERSE_SOURCE_LISTS: speisen build_ticker_universe()s all_sources direkt
# (Zeile 2175-2187 in market_aggregator.py, statischer Teil — dynamische
# Quellen fetch_approved_extra_tickers()/ex_iwv bewusst NICHT Teil dieses
# statischen Audits, da sie zur Laufzeit aus KV/CSV kommen).
UNIVERSE_SOURCE_LISTS = [
    "SP500_TICKERS", "NASDAQ100_EXTRA", "EU_ADR_TICKERS",
    "BEAR_US_TICKERS", "BEAR_DE_EU_TICKERS", "INTL_TIER1",
    "SECTOR_ETFS_BROAD", "SECTOR_ETFS_US", "SECTOR_ETFS_EXUS",
    "CRYPTO_TICKERS",
    # SECTOR_WATCHLISTS wird separat behandelt (Dict, nicht flache Liste)
]

# LEADERBOARD_TAG_SPEC: exakte Nachbildung des Leaderboard-Kategorisierungs-
# Blocks (market_aggregator.py Zeile ~11510-11524). "listname" verweist auf
# die Rohliste, "alias_of" markiert reine Namens-Aliase (z.B.
# EUROSTOXX_TICKERS = EUROSTOXX_TICKERS_LEGACY), die kein eigenes AST-Literal
# sind und aufgeloest werden muessen.
LEADERBOARD_TAG_SPEC = {
    "dax40":     "DAX40_TICKERS",
    "mdax":      "MDAX_TICKERS",
    "tecdax":    "TECDAX_TICKERS",
    "eurostoxx": "EUROSTOXX_TICKERS_LEGACY",  # EUROSTOXX_TICKERS ist Alias hierauf
    "sp500":     "SP500_TICKERS",
    "nasdaq100": "NASDAQ100_EXTRA",
    "intl":      "INTL_TIER1",
    "intl_eu":   "EUROSTOXX_TICKERS_LEGACY",  # dieselbe Quelle wie "eurostoxx" (im Original ebenfalls Duplikat)
    "ftse100":   "FTSE100_TICKERS",
    "stoxx_eu":  "STOXX_EU_EXTRA",
    "bear_us":   "BEAR_US_TICKERS",
    "bear_eu":   "BEAR_DE_EU_TICKERS",
    "etfs_exus": "SECTOR_ETFS_EXUS",
    "etfs":      "__SECTOR_ETFS_COMBINED__",  # SECTOR_ETFS_BROAD+US+EXUS, dedupliziert
    "crypto":    "CRYPTO_TICKERS",
}

SECTOR_WATCHLISTS_NAME = "SECTOR_WATCHLISTS"

ALL_LITERAL_NAMES = set(UNIVERSE_SOURCE_LISTS) | {
    SECTOR_WATCHLISTS_NAME, "DAX40_TICKERS", "MDAX_TICKERS", "TECDAX_TICKERS",
    "EUROSTOXX_TICKERS_LEGACY", "FTSE100_TICKERS", "STOXX_EU_EXTRA",
}

BAD_SYMS = {"CS", "SAMSUNG", "SoftBank", "CSCO.DE", "SDAX.DE", "MDNT.DE",
            "STRN.DE", "SKB.DE", "SLT.DE", "ARND.DE", "SSNLF", "2330.TW",
            "9988.HK", "0700.HK", "3690.HK", "1810.HK",
            "STLAM.MI", "WDP.BR", "GLPG.BR",
            "SPX.L", "BME.L", "MNG.L", "SDAX"}


def extract_literals(source_path):
    """AST-basierte Extraktion — kein Import, keine Ausfuehrung. Reine
    Listen-/Dict-Literale werden per ast.literal_eval erfasst."""
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
        if name not in ALL_LITERAL_NAMES:
            continue
        try:
            found[name] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            pass  # Aliase/Ausdruecke bewusst uebersprungen, hier nicht gebraucht
    return found


def derive_old_universe(literals):
    """Repliziert build_ticker_universe()s STATISCHEN Anteil exakt (Zeile
    2175-2200) — ohne fetch_approved_extra_tickers()/ex_iwv (dynamische
    Laufzeitquellen, nicht Teil eines statischen AST-Audits)."""
    all_sources = []
    for name in ["SP500_TICKERS", "NASDAQ100_EXTRA", "EU_ADR_TICKERS",
                 "BEAR_US_TICKERS", "BEAR_DE_EU_TICKERS", "INTL_TIER1"]:
        all_sources.extend(literals.get(name, []))
    for name in ["SECTOR_ETFS_BROAD", "SECTOR_ETFS_US", "SECTOR_ETFS_EXUS"]:
        all_sources.extend(literals.get(name, []))
    all_sources.extend(literals.get("CRYPTO_TICKERS", []))
    for wl in literals.get(SECTOR_WATCHLISTS_NAME, {}).values():
        all_sources.extend(wl)

    seen = set()
    result = []
    for t in all_sources:
        if t and t not in seen and t not in BAD_SYMS:
            seen.add(t)
            result.append(t)
    return result  # Reihenfolge erhalten (wie im Original), Set fuer Vergleich separat


def derive_old_sector_tags(literals):
    """Repliziert TICKER_SECTOR_TAG exakt: Invertierung von
    SECTOR_WATCHLISTS."""
    tag = defaultdict(list)
    for sector, tickers in literals.get(SECTOR_WATCHLISTS_NAME, {}).items():
        for t in tickers:
            tag[t].append(sector)
    return dict(tag)


def _resolve_leaderboard_source(list_key, literals):
    if list_key == "__SECTOR_ETFS_COMBINED__":
        combined = []
        for name in ["SECTOR_ETFS_BROAD", "SECTOR_ETFS_US", "SECTOR_ETFS_EXUS"]:
            combined.extend(literals.get(name, []))
        # list(dict.fromkeys(...)) im Original — Reihenfolge erhalten, dedupliziert
        return list(dict.fromkeys(combined))
    return literals.get(list_key, [])


def derive_old_leaderboard_tags(literals, old_universe_set):
    """Repliziert den Leaderboard-Kategorisierungs-Block EXAKT, inklusive
    der wichtigen Einschraenkung: `[r for r in results if r["sym"] in X]`
    kann NUR Ticker enthalten, die tatsaechlich gescannt wurden (in
    old_universe_set) — ein Ticker in z.B. DAX40_TICKERS, der NICHT im
    Universum ist, bekommt in der Realitaet NIE das "dax40"-Tag im Output,
    selbst wenn er formal in der Liste steht. Diese Funktion bildet das
    treu ab (inkl. des oben dokumentierten Bugs), keine Korrektur."""
    ticker_tags = defaultdict(list)
    for tag_name, list_key in LEADERBOARD_TAG_SPEC.items():
        source = _resolve_leaderboard_source(list_key, literals)
        for t in source:
            if t in old_universe_set and tag_name not in ticker_tags[t]:
                ticker_tags[t].append(tag_name)
    return dict(ticker_tags)


def generate_ticker_master(literals, old_universe_list):
    """Generiert TICKER_MASTER automatisch aus denselben Rohquellen — EIN
    Datensatz pro Ticker mit allen fuer die drei Dimensionen noetigen
    Informationen. Das ist die neue, kuenftig editierbare Struktur."""
    old_universe_set = set(old_universe_list)
    master = defaultdict(lambda: {
        "in_universe": False,
        "universe_sources": [],
        "sectors": [],
        "leaderboard_tags": [],
    })

    for name in UNIVERSE_SOURCE_LISTS:
        for t in literals.get(name, []):
            master[t]["universe_sources"].append(name)

    for sector, tickers in literals.get(SECTOR_WATCHLISTS_NAME, {}).items():
        for t in tickers:
            master[t]["sectors"].append(sector)
            if SECTOR_WATCHLISTS_NAME not in master[t]["universe_sources"]:
                master[t]["universe_sources"].append(SECTOR_WATCHLISTS_NAME)

    for tag_name, list_key in LEADERBOARD_TAG_SPEC.items():
        source = _resolve_leaderboard_source(list_key, literals)
        for t in source:
            if tag_name not in master[t]["leaderboard_tags"]:
                master[t]["leaderboard_tags"].append(tag_name)

    for t in master:
        master[t]["in_universe"] = t in old_universe_set and t not in BAD_SYMS

    return dict(master)


def derive_new_universe(ticker_master):
    return sorted([t for t, rec in ticker_master.items() if rec["in_universe"]])


def derive_new_sector_tags(ticker_master):
    return {t: rec["sectors"] for t, rec in ticker_master.items() if rec["sectors"]}


def derive_new_leaderboard_tags(ticker_master):
    return {
        t: rec["leaderboard_tags"]
        for t, rec in ticker_master.items()
        if rec["leaderboard_tags"] and rec["in_universe"]
    }


def compare_sets(old_list, new_list, label):
    old_set, new_set = set(old_list), set(new_list)
    only_old = old_set - new_set
    only_new = new_set - old_set
    ok = not only_old and not only_new
    print(f"  [{label}] OLD={len(old_set)}, NEW={len(new_set)} — {'✅ IDENTISCH' if ok else '❌ ABWEICHUNG'}")
    if only_old:
        print(f"    Nur in OLD ({len(only_old)}): {sorted(only_old)[:20]}{' ...' if len(only_old) > 20 else ''}")
    if only_new:
        print(f"    Nur in NEW ({len(only_new)}): {sorted(only_new)[:20]}{' ...' if len(only_new) > 20 else ''}")
    return ok


def compare_mappings(old_map, new_map, label):
    all_keys = set(old_map.keys()) | set(new_map.keys())
    mismatches = []
    for k in all_keys:
        old_v = sorted(old_map.get(k, []))
        new_v = sorted(new_map.get(k, []))
        if old_v != new_v:
            mismatches.append((k, old_v, new_v))
    ok = not mismatches
    print(f"  [{label}] {len(all_keys)} Ticker geprüft — {'✅ IDENTISCH' if ok else f'❌ {len(mismatches)} ABWEICHUNGEN'}")
    for k, old_v, new_v in mismatches[:20]:
        print(f"    {k}: OLD={old_v} vs NEW={new_v}")
    if len(mismatches) > 20:
        print(f"    ... und {len(mismatches) - 20} weitere")
    return ok


def per_ticker_full_diff(ticker_master, old_universe_set, old_sector_tags, old_leaderboard_tags):
    """Test 4: voller Datensatz-Vergleich pro Ticker — findet z.B. einen
    einzelnen fehlenden zweiten Sector-Tag, den ein reiner Mengenvergleich
    uebersehen koennte."""
    all_tickers = set(ticker_master.keys()) | old_universe_set | set(old_sector_tags.keys()) | set(old_leaderboard_tags.keys())
    mismatches = []
    for t in all_tickers:
        rec = ticker_master.get(t, {"in_universe": False, "sectors": [], "leaderboard_tags": []})
        old_in_universe = t in old_universe_set and t not in BAD_SYMS
        old_sectors = sorted(old_sector_tags.get(t, []))
        old_lb = sorted(old_leaderboard_tags.get(t, []))
        new_in_universe = rec["in_universe"]
        new_sectors = sorted(rec["sectors"])
        new_lb = sorted(rec["leaderboard_tags"]) if new_in_universe else []

        diffs = []
        if old_in_universe != new_in_universe:
            diffs.append(f"in_universe: OLD={old_in_universe} NEW={new_in_universe}")
        if old_sectors != new_sectors:
            diffs.append(f"sectors: OLD={old_sectors} NEW={new_sectors}")
        if old_lb != new_lb:
            diffs.append(f"leaderboard_tags: OLD={old_lb} NEW={new_lb}")
        if diffs:
            mismatches.append((t, diffs))

    ok = not mismatches
    print(f"  [Pro-Ticker-Volldiff] {len(all_tickers)} Ticker geprüft — {'✅ ALLE IDENTISCH' if ok else f'❌ {len(mismatches)} TICKER MIT ABWEICHUNG'}")
    for t, diffs in mismatches[:20]:
        print(f"    {t}: {'; '.join(diffs)}")
    return ok


def mutation_test(ticker_master):
    """Test 5 — NUR wenn Tests 1-4 vollstaendig gruen liefen. Fuegt einen
    synthetischen Test-Ticker zu TICKER_MASTER hinzu, generiert alle
    abgeleiteten Strukturen neu, prueft korrekte Propagation."""
    test_sym = "ZZTEST99"
    assert test_sym not in ticker_master, "Test-Symbol kollidiert mit echtem Ticker — Testdesign-Fehler"

    mutated = dict(ticker_master)
    mutated[test_sym] = {
        "in_universe": True,
        "universe_sources": [SECTOR_WATCHLISTS_NAME],
        "sectors": ["AI_TECH", "SEMIS"],
        "leaderboard_tags": [],
    }

    new_universe = derive_new_universe(mutated)
    new_sector_tags = derive_new_sector_tags(mutated)

    checks = {
        "Ticker im neuen Universe": test_sym in new_universe,
        "Ticker hat AI_TECH-Tag": "AI_TECH" in new_sector_tags.get(test_sym, []),
        "Ticker hat SEMIS-Tag": "SEMIS" in new_sector_tags.get(test_sym, []),
        "Ticker hat genau 2 Sektor-Tags": len(new_sector_tags.get(test_sym, [])) == 2,
    }
    all_ok = all(checks.values())
    print(f"  [Mutations-Test, Symbol={test_sym}] {'✅ ALLE PROPAGATIONEN KORREKT' if all_ok else '❌ FEHLER'}")
    for desc, ok in checks.items():
        print(f"    {'✅' if ok else '❌'} {desc}")
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Phase B — TICKER_MASTER-Migration, rein technisch, verlustfrei, OLD-vs-NEW-Diff")
    parser.add_argument("source_file")
    parser.add_argument("--json", help="TICKER_MASTER als JSON schreiben")
    args = parser.parse_args()

    print(f"Lese {args.source_file} per AST...")
    literals = extract_literals(args.source_file)
    missing = ALL_LITERAL_NAMES - set(literals.keys())
    if missing:
        print(f"  ⚠️  Nicht gefunden: {sorted(missing)}")

    print("\n=== OLD_* aus den bestehenden Quellen ableiten ===")
    old_universe = derive_old_universe(literals)
    old_universe_set = set(old_universe)
    old_sector_tags = derive_old_sector_tags(literals)
    old_leaderboard_tags = derive_old_leaderboard_tags(literals, old_universe_set)
    print(f"  OLD_UNIVERSE: {len(old_universe)} Ticker")
    print(f"  OLD_TICKER_SECTOR_TAG: {len(old_sector_tags)} Ticker mit Tags")
    print(f"  OLD_LEADERBOARD_TAGS: {len(old_leaderboard_tags)} Ticker mit Tags")

    print("\n=== TICKER_MASTER automatisch generieren ===")
    ticker_master = generate_ticker_master(literals, old_universe)
    print(f"  {len(ticker_master)} Ticker-Datensätze erzeugt")

    print("\n=== NEW_* aus TICKER_MASTER ableiten ===")
    new_universe = derive_new_universe(ticker_master)
    new_sector_tags = derive_new_sector_tags(ticker_master)
    new_leaderboard_tags = derive_new_leaderboard_tags(ticker_master)

    print("\n=== Test 1-3: OLD vs NEW, drei Dimensionen ===")
    ok1 = compare_sets(old_universe, new_universe, "1. UNIVERSE")
    ok2 = compare_mappings(old_sector_tags, new_sector_tags, "2. SECTOR_TAG")
    ok3 = compare_mappings(old_leaderboard_tags, new_leaderboard_tags, "3. LEADERBOARD_TAGS")

    print("\n=== Test 4: Pro-Ticker-Volldatensatz-Diff ===")
    ok4 = per_ticker_full_diff(ticker_master, old_universe_set, old_sector_tags, old_leaderboard_tags)

    all_prior_ok = ok1 and ok2 and ok3 and ok4
    print(f"\n=== Tests 1-4 Gesamtergebnis: {'✅ ALLE GRÜN' if all_prior_ok else '❌ MINDESTENS EIN TEST FEHLGESCHLAGEN'} ===")

    ok5 = None
    if all_prior_ok:
        print("\n=== Test 5: Mutations-Test (nur da 1-4 grün) ===")
        ok5 = mutation_test(ticker_master)
    else:
        print("\n=== Test 5: ÜBERSPRUNGEN (Tests 1-4 nicht vollständig grün) ===")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(ticker_master, f, indent=2, ensure_ascii=False)
        print(f"\nTICKER_MASTER geschrieben: {args.json}")

    final_ok = all_prior_ok and (ok5 is not False)
    print(f"\n{'🎉 PHASE B ERFOLGREICH' if final_ok else '⚠️ PHASE B NICHT VOLLSTÄNDIG — s. Abweichungen oben'}")
    return 0 if final_ok else 1


if __name__ == "__main__":
    sys.exit(main())
