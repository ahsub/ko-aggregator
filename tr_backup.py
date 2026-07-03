#!/usr/bin/env python3
"""
UIQ Track-Record-Backup (RUNBOOK §7.3)
=======================================
Version 1.0 (03.07.2026)

Exportiert alle tr:*-Keys aus Cloudflare KV nach backups/tr_backup_latest.json.
Die tr:*-Keys sind die EINZIGEN nicht regenerierbaren Daten des Systems
(Track Record = kommerzielles Kernasset) — dieses Script ist die Versicherung.

Läuft im Nachtlauf-Workflow, aktiv nur samstags (UTC) oder mit
TR_BACKUP_FORCE=1. Der Workflow committet die Datei anschließend ins Repo:
Die Git-History IST das Backup-Archiv (jede Woche ein Stand, für immer).

Fehlerphilosophie: Dieses Script bricht den Workflow nie (Exit 0 auch bei
Fehlern) — ein misslungenes Backup ist ein Log-Warnhinweis, kein Lauf-Killer.
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone


def main():
    now = datetime.now(timezone.utc)
    if now.isoweekday() != 6 and os.environ.get("TR_BACKUP_FORCE") != "1":
        print(f"[TR-BACKUP] {now.strftime('%A')} — Backup läuft nur samstags, übersprungen.")
        return 0

    acc = os.environ.get("CF_ACCOUNT_ID")
    tok = os.environ.get("CF_API_TOKEN")
    ns  = os.environ.get("CF_KV_NS_ID")
    if not all([acc, tok, ns]):
        print("[TR-BACKUP] ⚠ CF-Credentials fehlen — übersprungen.")
        return 0

    base = f"https://api.cloudflare.com/client/v4/accounts/{acc}/storage/kv/namespaces/{ns}"
    hdr  = {"Authorization": f"Bearer {tok}"}

    try:
        # 1) Alle tr:*-Keys auflisten (Cursor-Pagination)
        keys, cursor = [], None
        while True:
            url = f"{base}/keys?prefix=tr:&limit=1000"
            if cursor:
                url += f"&cursor={cursor}"
            r = requests.get(url, headers=hdr, timeout=30).json()
            keys += [k["name"] for k in r.get("result", [])]
            cursor = (r.get("result_info") or {}).get("cursor")
            if not cursor:
                break

        if not keys:
            print("[TR-BACKUP] Keine tr:*-Keys vorhanden — nichts zu sichern.")
            return 0

        # 2) Werte holen
        data, failed = {}, []
        for k in keys:
            rr = requests.get(f"{base}/values/{k}", headers=hdr, timeout=30)
            if rr.status_code == 200:
                try:
                    data[k] = rr.json()
                except ValueError:
                    data[k] = rr.text
            else:
                failed.append(k)

        # 3) Schreiben
        os.makedirs("backups", exist_ok=True)
        out = {"exported": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "keyCount": len(data), "failedKeys": failed, "keys": data}
        with open("backups/tr_backup_latest.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        size_kb = os.path.getsize("backups/tr_backup_latest.json") / 1024
        print(f"[TR-BACKUP] ✅ {len(data)} Keys exportiert ({size_kb:.0f} KB)"
              + (f" | ⚠ {len(failed)} fehlgeschlagen: {failed[:5]}" if failed else ""))
    except Exception as e:
        print(f"[TR-BACKUP] ⚠ Fehler (nicht kritisch): {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
