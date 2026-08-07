#!/usr/bin/env python3
"""
update_iwv.py — IWV Holdings Update mit Survivorship-Tracking
=============================================================
Backlog T3 (SWOT T3, 07.08.2026) — Survivorship-Bias-Fix

PROBLEM:
  IWV Holdings CSV wird monatlich manuell ersetzt. Herausgefallene
  Ticker verschwinden stillschweigend. Bei Track-Record-Auswertungen
  sehen die Ergebnisse besser aus als sie sind (Survivorship-Bias):
  schlechte Performer fallen aus dem Index und aus dem Tracking.

LÖSUNG:
  1. Alte Liste laden (data/iwv_holdings.csv)
  2. Neue Liste laden (Download-Argument oder interaktiv)
  3. Diff berechnen: ADDED + REMOVED
  4. REMOVED → data/ex_iwv_tickers.csv (mit Datum, kumulativ)
  5. Alte CSV archivieren: data/holdings_archive/iwv_holdings_YYYY-MM-DD.csv
  6. Neue CSV einsetzen: data/iwv_holdings.csv

EX-IWV TRACKING:
  data/ex_iwv_tickers.csv — alle jemals herausgefallenen Ticker:
    Ticker, Name, Sector, RemovedDate, AddedDate (wenn bekannt)
  Diese Ticker werden weiter im Aggregator-Universum behalten
  (tagged als ex_iwv=True) und im Track-Record korrekt attributiert.

AUSFÜHRUNG:
  # Mit neuer CSV-Datei:
  python engine/update_iwv.py --new data/iwv_holdings_new.csv

  # Dry-Run (zeigt Diff ohne Änderungen):
  python engine/update_iwv.py --new data/iwv_holdings_new.csv --dry-run

  # Interaktiv (fragt nach Pfad):
  python engine/update_iwv.py

ABLAGE: engine/update_iwv.py
"""

import sys
import csv
import shutil
import argparse
from datetime import date
from pathlib import Path

# ── Konfiguration ─────────────────────────────────────────────

REPO_ROOT      = Path(__file__).parent.parent
IWV_CURRENT    = REPO_ROOT / 'data' / 'iwv_holdings.csv'
EX_IWV_FILE    = REPO_ROOT / 'data' / 'ex_iwv_tickers.csv'
ARCHIVE_DIR    = REPO_ROOT / 'data' / 'holdings_archive'
IWV_SKIP_ROWS  = 9   # Metadaten-Zeilen am Anfang (iShares-Format)


# ── CSV-Parser ────────────────────────────────────────────────

def load_iwv_csv(path: Path) -> dict:
    """
    Lädt IWV holdings CSV (iShares-Format) und gibt
    {ticker: {name, sector, weight}} zurück.
    Ignoriert Nicht-Equity-Zeilen (Cash, CASH, etc.)
    """
    holdings = {}
    try:
        with open(path, newline='', encoding='utf-8-sig') as fh:
            # Überspringe Metadaten-Zeilen
            for _ in range(IWV_SKIP_ROWS):
                next(fh)
            reader = csv.DictReader(fh)
            for row in reader:
                ticker = (row.get('Ticker') or '').strip().strip('"')
                asset  = (row.get('Asset Class') or '').strip().strip('"')
                name   = (row.get('Name') or '').strip().strip('"')
                sector = (row.get('Sector') or '').strip().strip('"')
                weight = (row.get('Weight (%)') or '0').strip().strip('"')

                # Nur Aktien (kein Cash, kein Bond)
                if not ticker or ticker in ('-', '') or asset != 'Equity':
                    continue

                holdings[ticker] = {
                    'name':   name,
                    'sector': sector,
                    'weight': weight,
                }
    except StopIteration:
        pass
    return holdings


# ── Ex-IWV Tracking ───────────────────────────────────────────

def load_ex_iwv() -> dict:
    """Lädt bestehende ex-IWV Liste. {ticker: {name, sector, removed_date, ...}}"""
    ex = {}
    if not EX_IWV_FILE.exists():
        return ex
    with open(EX_IWV_FILE, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ex[row['Ticker']] = row
    return ex


def save_ex_iwv(ex: dict):
    """Speichert ex-IWV Liste."""
    EX_IWV_FILE.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ['Ticker', 'Name', 'Sector', 'RemovedDate', 'LastWeight', 'Notes']
    with open(EX_IWV_FILE, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for ticker, data in sorted(ex.items()):
            writer.writerow({
                'Ticker':      ticker,
                'Name':        data.get('Name') or data.get('name', ''),
                'Sector':      data.get('Sector') or data.get('sector', ''),
                'RemovedDate': data.get('RemovedDate', ''),
                'LastWeight':  data.get('LastWeight') or data.get('weight', ''),
                'Notes':       data.get('Notes', ''),
            })


# ── Archivierung ──────────────────────────────────────────────

def archive_current(today: date):
    """Archiviert die aktuelle IWV-Holdings-CSV mit Datum."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_DIR / f'iwv_holdings_{today}.csv'
    shutil.copy2(IWV_CURRENT, archive_path)
    return archive_path


# ── Hauptprogramm ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='IWV Holdings Update mit Survivorship-Tracking'
    )
    parser.add_argument(
        '--new', '-n',
        type=Path,
        help='Pfad zur neuen IWV-Holdings-CSV (Download von ishares.com)',
    )
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Nur Diff anzeigen, keine Dateien ändern',
    )
    args = parser.parse_args()

    today = date.today()

    print("UIQ — IWV Holdings Update mit Survivorship-Tracking")
    print("=" * 52)
    print(f"Datum: {today}")
    print()

    # ── 1. Neue CSV-Datei bestimmen ──────────────────────────────
    new_path = args.new
    if not new_path:
        print("Wo liegt die neue IWV-Holdings-CSV?")
        print("(Download: ishares.com → IWV → Holdings → CSV)")
        inp = input("Pfad: ").strip()
        new_path = Path(inp)

    if not new_path.exists():
        print(f"❌ Datei nicht gefunden: {new_path}")
        sys.exit(1)

    # ── 2. Alte + neue Liste laden ───────────────────────────────
    if not IWV_CURRENT.exists():
        print(f"❌ Aktuelle IWV-Holdings nicht gefunden: {IWV_CURRENT}")
        sys.exit(1)

    print(f"📂 Lade aktuelle Liste: {IWV_CURRENT}")
    old_holdings = load_iwv_csv(IWV_CURRENT)
    print(f"   → {len(old_holdings)} Ticker")

    print(f"📂 Lade neue Liste: {new_path}")
    new_holdings = load_iwv_csv(new_path)
    print(f"   → {len(new_holdings)} Ticker")

    if not new_holdings:
        print("❌ Neue Liste ist leer — CSV-Format prüfen")
        sys.exit(1)

    # ── 3. Diff berechnen ────────────────────────────────────────
    old_set = set(old_holdings.keys())
    new_set = set(new_holdings.keys())

    added   = new_set - old_set
    removed = old_set - new_set
    stayed  = old_set & new_set

    print()
    print(f"📊 Diff:")
    print(f"   Unverändert: {len(stayed):4d} Ticker")
    print(f"   Neu hinzu:   {len(added):4d} Ticker")
    print(f"   Herausgef.:  {len(removed):4d} Ticker")

    if removed:
        print()
        print(f"⚠️  Herausgefallene Ticker ({len(removed)}) — werden in ex_iwv_tickers.csv gespeichert:")
        for t in sorted(removed):
            info = old_holdings[t]
            print(f"   {t:<8} {info['name'][:35]:<35} [{info['sector']}] Gew.: {info['weight']}%")

    if added:
        print()
        print(f"✅ Neu hinzugekommen ({len(added)}):")
        for t in sorted(added):
            info = new_holdings[t]
            print(f"   {t:<8} {info['name'][:35]:<35} [{info['sector']}]")

    if not removed and not added:
        print()
        print("✅ Keine Änderungen — Listen identisch.")
        if not args.dry_run:
            # Trotzdem archivieren
            arc = archive_current(today)
            print(f"📁 Archiviert: {arc}")
        return

    if args.dry_run:
        print()
        print("🔍 DRY-RUN — keine Dateien geändert.")
        return

    # ── 4. Bestätigung ───────────────────────────────────────────
    print()
    confirm = input(f"Update durchführen? [{len(removed)} entfernt, {len(added)} hinzu] (j/N): ").strip().lower()
    if confirm not in ('j', 'ja', 'y', 'yes'):
        print("Abgebrochen.")
        sys.exit(0)

    # ── 5. Alte CSV archivieren ──────────────────────────────────
    arc = archive_current(today)
    print(f"📁 Archiviert: {arc}")

    # ── 6. Ex-IWV Tracking aktualisieren ────────────────────────
    ex = load_ex_iwv()
    new_ex_count = 0
    for ticker in removed:
        if ticker not in ex:
            ex[ticker] = {
                'Name':        old_holdings[ticker]['name'],
                'Sector':      old_holdings[ticker]['sector'],
                'RemovedDate': str(today),
                'LastWeight':  old_holdings[ticker]['weight'],
                'Notes':       f'Aus IWV-Holdings entfernt am {today}',
            }
            new_ex_count += 1
        else:
            # Bereits bekannt — nur Datum aktualisieren falls leer
            if not ex[ticker].get('RemovedDate'):
                ex[ticker]['RemovedDate'] = str(today)

    save_ex_iwv(ex)
    print(f"📋 ex_iwv_tickers.csv: {new_ex_count} neue Einträge ({len(ex)} gesamt)")

    # ── 7. Neue CSV einsetzen ────────────────────────────────────
    shutil.copy2(new_path, IWV_CURRENT)
    print(f"✅ {IWV_CURRENT} aktualisiert ({len(new_holdings)} Ticker)")

    # ── 8. Zusammenfassung ───────────────────────────────────────
    print()
    print("=" * 52)
    print(f"✅ IWV Update abgeschlossen ({today})")
    print(f"   Archiv:    data/holdings_archive/iwv_holdings_{today}.csv")
    print(f"   Ex-IWV:    data/ex_iwv_tickers.csv ({len(ex)} Ticker gesamt)")
    print(f"   Universum: {len(new_holdings)} aktive + {len(ex)} ex-IWV Ticker")
    print()
    print("Nächste Schritte:")
    print("  1. git add data/iwv_holdings.csv data/ex_iwv_tickers.csv data/holdings_archive/")
    print("  2. git commit -m 'data: IWV Holdings Update {today}'")
    print("  3. GHA-Lauf abwarten — ex-IWV Ticker bleiben im Universum (tagged)")


if __name__ == '__main__':
    main()
