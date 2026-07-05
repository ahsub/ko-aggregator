#!/usr/bin/env python3
"""
UIQ FIN-Archiv — Point-in-Time-Fundamentaldaten-Sammler (Value-Modul Phase 0)
==============================================================================
Version 1.0 (05.07.2026) | Konzept: docs/VALUE_MOD_KONZEPT.md, STRATEGIE.md §9

ZWECK: Fundamentaldaten sind — anders als Kurshistorie — NICHT rückwirkend
beschaffbar (Point-in-Time-Datenbanken kosten vierstellig/Jahr). Dieses Modul
archiviert deshalb ab sofort wöchentlich den Fundamental-Zustand eines breiten
Value-Universums, damit künftige VAL-MOD-Bewertungsmodelle (v4, v5, …) gegen
echte, survivorship-freie Historie geprüft werden können. Es loggt ROHDATEN,
keine Scores — modellagnostisch.

UNIVERSUM (Entscheidung 05.07.2026): Russell 3000 (via iShares-IWV-Holdings,
frei verfügbar) ∪ Smart-Picks (data/value_smart_picks.txt, händisch gepflegt)
∪ UIQ-Trading-Universum (EU-ADRs + Kontinuität). Die Konstituentenliste wird
MIT archiviert → Universum selbst ist Point-in-Time dokumentiert (künftige
Delistings/Absteiger bleiben sichtbar — Survivorship-Ehrlichkeit ab Tag 1).

ABLAUF (implementiert die Wochentags-Fraktionierung aus VAL-MOD Layer 1):
  Mo–Fr (nightly): deterministischer 1/5-Shard (crc32) → yfinance .info,
                   fester Feldsatz → KV fin:shard:<1-5>
  Sa (merge):      Shards zusammenführen + IWV-Liste + Smart-Picks →
                   data/fundamentals/<YYYY-WW>.json.gz (Workflow committet;
                   Git-History = Archiv, wie beim tr-Backup)

FEHLERPHILOSOPHIE: identisch zu tr_layer — dieses Modul bricht den Hauptlauf
niemals; Status landet in master["finArchive"].
"""

import os
import io
import csv
import json
import gzip
import logging
import requests
from zlib import crc32
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger("aggregator")

FIN_SCHEMA_VERSION = 1
SHARDS = 5
SMART_PICKS_PATH = "data/value_smart_picks.txt"
ARCHIVE_DIR = "data/fundamentals"
IWV_CSV_URL = ("https://www.ishares.com/us/products/239714/"
               "ishares-russell-3000-etf/1467271812596.ajax"
               "?fileType=csv&fileName=IWV_holdings&dataType=fund")
_KV_TIMEOUT = 15
_FETCH_WORKERS = 6

# Fester, modellagnostischer Feldsatz (VAL-MOD FinancialData v4 — yf .info).
# ROIC + 3J-Wachstumsreihen brauchen Financial Statements → Layer 2 (später).
INFO_FIELDS = (
    "marketCap", "grossMargins", "operatingMargins", "profitMargins",
    "returnOnEquity", "returnOnAssets", "debtToEquity", "currentRatio",
    "trailingPE", "forwardPE", "priceToBook", "trailingEps", "bookValue",
    "revenueGrowth", "earningsGrowth", "freeCashflow", "totalRevenue",
    "sharesOutstanding", "shortPercentOfFloat", "regularMarketPrice",
    "fiftyTwoWeekLow", "fiftyTwoWeekHigh", "sector", "industry",
)


# ── KV-I/O (bewusst eigenständig — kein Import-Coupling zu tr_layer) ─────────

def _kv_creds():
    a = os.environ.get("CF_ACCOUNT_ID")
    t = os.environ.get("CF_API_TOKEN")
    n = os.environ.get("CF_KV_NS_ID")
    return (a, t, n) if all([a, t, n]) else None


def _kv_url(key):
    a, _, n = _kv_creds()
    return (f"https://api.cloudflare.com/client/v4/accounts/{a}"
            f"/storage/kv/namespaces/{n}/values/{key}")


def kv_get(key):
    creds = _kv_creds()
    if not creds:
        return None
    try:
        r = requests.get(_kv_url(key),
                         headers={"Authorization": f"Bearer {creds[1]}"},
                         timeout=_KV_TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.warning(f"  [FIN] kv_get({key}): {e}")
    return None


def kv_put(key, data):
    creds = _kv_creds()
    if not creds:
        return False
    try:
        r = requests.put(_kv_url(key),
                         headers={"Authorization": f"Bearer {creds[1]}",
                                  "Content-Type": "application/json"},
                         data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
                         timeout=60)
        return r.status_code in (200, 201)
    except Exception as e:
        log.warning(f"  [FIN] kv_put({key}): {e}")
        return False


# ── Universum ─────────────────────────────────────────────────────────────────

def _clean_iwv_symbol(sym):
    """iShares-Ticker → Yahoo-Symbolik (Share-Klassen: BRK.B → BRK-B)."""
    s = (sym or "").strip().upper()
    if not s or s in ("--", "USD") or " " in s or len(s) > 6:
        return None
    return s.replace(".", "-")


def fetch_iwv_tickers():
    """Russell-3000-Proxy via iShares-IWV-Holdings-CSV (frei verfügbar).
    None bei Fehlschlag (Aufrufer nutzt dann den KV-Cache der Vorwoche)."""
    try:
        r = requests.get(IWV_CSV_URL, timeout=60,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or len(r.text) < 10000:
            log.warning(f"  [FIN] IWV-Fetch: Status {r.status_code}")
            return None
        lines = r.text.splitlines()
        # Header-Zeile finden (iShares stellt ~9 Metazeilen voran)
        start = next((i for i, l in enumerate(lines)
                      if l.split(",")[0].strip().strip('"') == "Ticker"), None)
        if start is None:
            log.warning("  [FIN] IWV-CSV: Header nicht gefunden")
            return None
        reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
        out = []
        for row in reader:
            if (row.get("Asset Class") or "").strip() not in ("Equity", ""):
                continue
            s = _clean_iwv_symbol(row.get("Ticker"))
            if s:
                out.append(s)
        out = sorted(set(out))
        return out if len(out) > 1000 else None   # Plausibilitäts-Gate
    except Exception as e:
        log.warning(f"  [FIN] IWV-Fetch fehlgeschlagen: {e}")
        return None


def load_smart_picks(path=SMART_PICKS_PATH):
    """Händisch gepflegte Kandidaten (eine Zeile = ein Ticker, # = Kommentar).
    Datei wird im GitHub-Web-Editor gepflegt; Repo-Checkout macht sie hier
    verfügbar. Fehlend/leer → []."""
    try:
        with open(path, encoding="utf-8") as f:
            return sorted({l.strip().upper() for l in f
                           if l.strip() and not l.strip().startswith("#")})
    except FileNotFoundError:
        return []
    except Exception as e:
        log.warning(f"  [FIN] Smart-Picks unlesbar: {e}")
        return []


def build_fin_universe(uiq_universe):
    """IWV ∪ Smart-Picks ∪ UIQ. Liefert (universum, meta).
    IWV-Fallback: KV-Cache fin:universe der Vorwoche."""
    iwv = fetch_iwv_tickers()
    iwv_source = "live"
    if iwv is None:
        cached = kv_get("fin:universe") or {}
        iwv = cached.get("iwv") or []
        iwv_source = f"cache:{cached.get('week', '?')}" if iwv else "unavailable"
    else:
        kv_put("fin:universe", {"v": FIN_SCHEMA_VERSION, "week": _iso_week(),
                                "iwv": iwv})
    picks = load_smart_picks()
    uiq = [t for t in (uiq_universe or []) if not t.endswith("-USD")]
    uni = sorted(set(iwv) | set(picks) | set(uiq))
    meta = {"iwv": len(iwv), "iwvSource": iwv_source,
            "smartPicks": picks, "uiq": len(uiq), "total": len(uni)}
    return uni, meta


# ── Sammeln ───────────────────────────────────────────────────────────────────

def shard_of(sym):
    """Deterministischer Mo–Fr-Shard (1–5) — stabil über Wochen."""
    return (crc32(sym.encode()) % SHARDS) + 1


def _fetch_info(sym):
    """yfinance-.info auf den festen Feldsatz reduziert. None = kein Zugriff."""
    try:
        import yfinance as yf
        info = yf.Ticker(sym).info or {}
        rec = {}
        for f in INFO_FIELDS:
            v = info.get(f)
            if v is not None:
                if isinstance(v, float):
                    v = round(v, 6)
                rec[f] = v
        return rec if rec else None
    except Exception:
        return None


def collect_shard(universe, weekday):
    """Sammelt den Tages-Shard parallel. Gibt (data, fehlgeschlagen) zurück."""
    todo = [t for t in universe if shard_of(t) == weekday]
    data, failed = {}, 0
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as ex:
        futs = {ex.submit(_fetch_info, t): t for t in todo}
        for fut in as_completed(futs):
            sym = futs[fut]
            rec = fut.result()
            if rec:
                data[sym] = rec
            else:
                failed += 1
    return todo, data, failed


def _iso_week(dt=None):
    dt = dt or datetime.now(timezone.utc)
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


# ── Orchestrierung ────────────────────────────────────────────────────────────

def run(uiq_universe, weekday_override=None):
    """Einhängepunkt im Nachtlauf. Mo–Fr: Shard sammeln → KV.
    Sa: Wochen-Merge → data/fundamentals/<YYYY-WW>.json.gz (Commit macht
    der Workflow). So: no-op. Gibt Status-Dict für master["finArchive"]."""
    if not _kv_creds():
        return {"ok": False, "reason": "no_kv_creds"}
    now = datetime.now(timezone.utc)
    weekday = weekday_override or now.isoweekday()
    week = _iso_week(now)

    if weekday == 7:
        return {"ok": True, "mode": "off", "reason": "sunday"}

    if 1 <= weekday <= 5:
        universe, umeta = build_fin_universe(uiq_universe)
        todo, data, failed = collect_shard(universe, weekday)
        payload = {"v": FIN_SCHEMA_VERSION, "week": week, "weekday": weekday,
                   "collected": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "universeMeta": umeta, "data": data, "failed": failed}
        ok = kv_put(f"fin:shard:{weekday}", payload)
        log.info(f"  [FIN] Shard {weekday}/{SHARDS}: {len(data)}/{len(todo)} "
                 f"Ticker erfasst ({failed} ohne Daten) | Universum "
                 f"{umeta['total']} (IWV {umeta['iwv']}/{umeta['iwvSource']}) "
                 f"| KV: {'✅' if ok else '❌'}")
        return {"ok": ok, "mode": "shard", "weekday": weekday, "week": week,
                "shardSize": len(todo), "collected": len(data),
                "failed": failed, "universe": umeta}

    # ── Samstag: Wochen-Merge ────────────────────────────────────────────────
    merged, shard_weeks, missing_shards = {}, {}, []
    for wd in range(1, SHARDS + 1):
        sh = kv_get(f"fin:shard:{wd}")
        if not sh:
            missing_shards.append(wd)   # Lauf fand nie statt (≠ leerer Shard)
            continue
        shard_weeks[str(wd)] = sh.get("week")
        for sym, rec in (sh.get("data") or {}).items():
            merged[sym] = rec
    if not merged:
        log.warning("  [FIN] Merge: keine Shards vorhanden — nichts geschrieben.")
        return {"ok": False, "mode": "merge", "reason": "no_shards"}

    universe, umeta = build_fin_universe(uiq_universe)
    field_fill = {f: sum(1 for r in merged.values() if f in r)
                  for f in INFO_FIELDS}
    archive = {"v": FIN_SCHEMA_VERSION, "week": week,
               "created": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "universeMeta": umeta,
               "iwvConstituents": (kv_get("fin:universe") or {}).get("iwv", []),
               "shardWeeks": shard_weeks, "missingShards": missing_shards,
               "fieldFill": field_fill, "count": len(merged),
               "data": merged}
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    path = f"{ARCHIVE_DIR}/{week}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False)
    size_kb = os.path.getsize(path) / 1024
    stale = [w for w in shard_weeks.values() if w != week]
    log.info(f"  [FIN] ✅ Wochen-Archiv {path}: {len(merged)} Ticker, "
             f"{size_kb:.0f} KB | fehlende Shards: {missing_shards or 'keine'}"
             + (f" | ⚠ Shards aus Vorwoche: {stale}" if stale else ""))
    return {"ok": True, "mode": "merge", "week": week, "count": len(merged),
            "file": path, "sizeKb": round(size_kb),
            "missingShards": missing_shards, "staleShardWeeks": stale}
