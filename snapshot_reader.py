"""
snapshot_reader.py — UIQ Datenschatz-Zugriff für andere ahsub-Repos
====================================================================
Version: 1.0.0 (22.07.2026)

Nutzungsmöglichkeiten:
  A) Cloudflare KV (empfohlen, immer aktuell):
       data = load_from_kv('master_market_data')
       briefing = load_from_kv('daily_market_snapshot')

  B) GitHub Snapshot (90-Tage-Rolling-Window, gzip'd):
       data = load_latest_snapshot()
       data = load_snapshot_for_date('2026-07-21')

Beispiel:
  from snapshot_reader import load_from_kv
  market = load_from_kv('master_market_data')
  tickers = market['leaderboards']['long_minervini']
  print([t['ticker'] for t in tickers[:5]])
"""

import json
import gzip
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Konfiguration ─────────────────────────────────────────────────────────────

KV_BASE_URL  = "https://ko-sync.ahildebrand.workers.dev/public"
GITHUB_RAW   = "https://raw.githubusercontent.com/ahsub/ko-aggregator/main"
SNAPSHOT_DIR = "data/snapshots"   # Relativ zum ko-aggregator-Repo-Root

# ── Cloudflare KV (öffentlich, kein Auth) ────────────────────────────────────

def load_from_kv(key: str = "master_market_data", timeout: int = 15) -> dict:
    """
    Lädt einen KV-Key aus dem öffentlichen ko-sync Worker.

    Verfügbare Keys:
      - master_market_data        (660 Ticker, ~675 KB, 2×/Tag aktualisiert)
      - daily_market_snapshot     (Morning Briefing, Morgen-Lauf)
      - daily_market_snapshot_us  (Morning Briefing, NYSE-Lauf)
      - options_watchlist         (Options-Kandidaten, ~50 KB)
    """
    url = f"{KV_BASE_URL}/{key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "UIQ-DataReader/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:
        raise RuntimeError(f"KV-Fetch fehlgeschlagen ({key}): {e}")

# ── GitHub Snapshot-Archiv (gzip, 90-Tage-Rolling-Window) ────────────────────

def load_latest_snapshot(branch: str = "main") -> dict:
    """
    Lädt den neuesten verfügbaren Snapshot aus dem GitHub-Archiv.
    Versucht zunächst den aktuellen Morgen-Lauf, dann den gestrigen.
    """
    now = datetime.now(timezone.utc)
    # Versuche die letzten 5 Lauf-Zeitfenster
    for delta_hours in [0, 1, 10, 11, 24, 25, 34, 35]:
        candidate = now - timedelta(hours=delta_hours)
        for hour in [3, 13]:  # Morgen- und NYSE-Lauf
            name = candidate.strftime(f"%Y-%m-%d") + f"_{hour:02d}.json.gz"
            try:
                return _load_github_snapshot(name, branch)
            except Exception:
                continue
    raise RuntimeError("Kein Snapshot der letzten 2 Tage verfügbar")

def load_snapshot_for_date(date: str, lauf: str = "morning",
                           branch: str = "main") -> dict:
    """
    Lädt Snapshot für ein bestimmtes Datum.
    date: 'YYYY-MM-DD'
    lauf: 'morning' (03 UTC) oder 'nyse' (13 UTC)
    """
    hour = "03" if lauf == "morning" else "13"
    name = f"{date}_{hour}.json.gz"
    return _load_github_snapshot(name, branch)

def list_available_snapshots(branch: str = "main") -> list[str]:
    """Listet alle verfügbaren Snapshots (letzten 90 Tage) via GitHub API."""
    url = f"https://api.github.com/repos/ahsub/ko-aggregator/contents/{SNAPSHOT_DIR}"
    req = urllib.request.Request(url, headers={"User-Agent": "UIQ-DataReader/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        files = json.load(r)
    return sorted([f["name"] for f in files if f["name"].endswith(".json.gz")])

def _load_github_snapshot(filename: str, branch: str) -> dict:
    """Intern: lädt eine spezifische Snapshot-Datei von GitHub."""
    url = f"{GITHUB_RAW}/{SNAPSHOT_DIR}/{filename}"
    req = urllib.request.Request(url, headers={"User-Agent": "UIQ-DataReader/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        compressed = r.read()
    return json.loads(gzip.decompress(compressed).decode("utf-8"))

# ── Convenience-Funktionen ────────────────────────────────────────────────────

def get_leaderboard(strategy: str = "long_minervini",
                    source: str = "kv") -> list[dict]:
    """
    Direktzugriff auf ein Leaderboard.
    strategy: 'long_minervini' | 'long_swing' | 'long_breakout' | 'vcp_setups' |
              'options_csp' | 'options_cc' | 'ko_long' | 'long_mr' |
              'short_fading' | 'short_breakdown'
    source: 'kv' (aktuell) oder 'snapshot' (archiviert)
    """
    if source == "kv":
        data = load_from_kv("master_market_data")
    else:
        data = load_latest_snapshot()
    return data.get("leaderboards", {}).get(strategy, [])

def get_regime(source: str = "kv") -> str:
    """Gibt das aktuelle MSE-Regime zurück ('BULL_QUIET', 'BULL_FRAGILE', ...)."""
    if source == "kv":
        snap = load_from_kv("daily_market_snapshot")
        return snap.get("regime", "NEUTRAL")
    else:
        data = load_latest_snapshot()
        return data.get("meta", {}).get("regime", "NEUTRAL")

def get_ticker(symbol: str, source: str = "kv") -> Optional[dict]:
    """Gibt alle Aggregator-Daten für einen einzelnen Ticker zurück."""
    if source == "kv":
        data = load_from_kv("master_market_data")
    else:
        data = load_latest_snapshot()
    results = data.get("results", [])
    symbol_upper = symbol.upper()
    for r in results:
        if r.get("ticker") == symbol_upper or r.get("symbol") == symbol_upper:
            return r
    return None

# ── CLI für schnellen Test ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        snap = load_from_kv("daily_market_snapshot")
        print(f"Regime: {snap.get('regime')} | Generated: {snap.get('generated')}")
        lb = get_leaderboard("long_minervini")
        print(f"Minervini-Leaderboard: {len(lb)} Titel")
        if lb:
            print(f"  Top 3: {', '.join(t.get('ticker','?') for t in lb[:3])}")

    elif cmd == "list":
        snaps = list_available_snapshots()
        print(f"{len(snaps)} Snapshots verfügbar:")
        for s in snaps[-10:]:
            print(f"  {s}")

    elif cmd == "ticker" and len(sys.argv) > 2:
        t = get_ticker(sys.argv[2])
        if t:
            print(json.dumps(t, indent=2, ensure_ascii=False)[:1000])
        else:
            print(f"Ticker {sys.argv[2]} nicht gefunden")
