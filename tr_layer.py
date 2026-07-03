#!/usr/bin/env python3
"""
UIQ Track-Record-Layer — Phase A: Snapshot-Writer
==================================================
Version 1.0 (03.07.2026) | Spezifikation: docs/TRACK_RECORD_SPEC.md v1.1

Protokolliert die nächtlichen Empfehlungen des Strategie-Routers nach
Cloudflare KV (append-only), als Grundlage für die spätere Bewertung
(Phase B: Evaluator) und das kommerzielle Track Record (STRATEGIE.md,
Roadmap Phase 0, Punkt 1).

KV-Keys:
  tr:snap:<YYYY-MM-DD>  — Snapshot pro HANDELSTAG (nicht Laufdatum!)
  tr:index              — Fahrplan für den Evaluator (Fälligkeits-Flags)

Design-Regeln (Spez §4/§6):
  - Fehlerisolation: Aufrufer kapselt run_snapshot() in try/except;
    dieses Modul wirft im I/O-Pfad keine Exceptions nach außen, sondern
    liefert einen Status-Dict (für master["trackRecord"] im Output).
  - Dedupe über den Handelstag: manuelle Doppel-Runs (z.B. #49/#50 am
    02.07.2026) erzeugen keinen zweiten Snapshot.
  - fresh-Flag: (sym, strat) stand NICHT im Snapshot des vorherigen
    Handelstags → Primärstatistik gegen Serienkorrelation (Spez §6.1).
  - Architektur: reine Build-Funktion (build_snapshot) von I/O getrennt —
    Blaupause für v2.0-Modularisierung, testbar ohne KV.
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone

log = logging.getLogger("aggregator")

TR_SCHEMA_VERSION = 1
LB_TOP_N = 10          # Top-N je Leaderboard, die geloggt werden (Spez §2)
_KV_TIMEOUT = 15


# ── KV-I/O (gleiche Credential-Konvention wie market_aggregator.py) ──────────

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
    """JSON-Wert aus KV lesen. None bei 404/Fehler/fehlenden Credentials."""
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
        log.warning(f"  [TR] kv_get({key}) fehlgeschlagen: {e}")
    return None


def kv_put(key, data):
    """JSON-Wert nach KV schreiben. True/False, wirft nicht."""
    creds = _kv_creds()
    if not creds:
        return False
    try:
        payload = json.dumps(data, ensure_ascii=False)
        r = requests.put(_kv_url(key),
                         headers={"Authorization": f"Bearer {creds[1]}",
                                  "Content-Type": "application/json"},
                         data=payload.encode("utf-8"),
                         timeout=30)
        return r.status_code in (200, 201)
    except Exception as e:
        log.warning(f"  [TR] kv_put({key}) fehlgeschlagen: {e}")
        return False


# ── Snapshot-Bau (reine Funktionen, KV-frei, testbar) ────────────────────────

def _ctx(ticker_rec, shortlist_rec=None):
    """Kleine, feste Kalibrierfeld-Auswahl (Spez §3.1) — kein Voll-Dump."""
    src = ticker_rec or {}
    ctx = {}
    for f in ("rsi", "hvp", "bbPos", "dist200"):
        v = src.get(f)
        if v is not None:
            ctx[f] = v
    q = (shortlist_rec or {}).get("iosQuality")
    if q is not None:
        ctx["iosQ"] = q
    return ctx


def _ki_params(c):
    """KI-Trade-Parameter (trigger/stopLoss/target) numerisch extrahieren.
    None, wenn unvollständig oder nicht numerisch — Trade-Simulation (Phase B)
    läuft nur auf vollständigen Tripeln."""
    k = c.get("ki") or {}
    try:
        trig = float(k.get("trigger"))
        sl   = float(k.get("stopLoss"))
        tgt  = float(k.get("target"))
        return {"trig": round(trig, 4), "sl": round(sl, 4), "tgt": round(tgt, 4)}
    except (TypeError, ValueError):
        return None


def build_snapshot(shortlist, leaderboards, tickers, regime, tday,
                   agg_version, prev_pairs, run_iso):
    """Baut den Tages-Snapshot (Spez §3.1) aus Shortlist + Leaderboard-Top-N.

    prev_pairs: set[(sym, strat)] des vorherigen Handelstags-Snapshots
                (leer bei Tag 0) — bestimmt das fresh-Flag.
    Dedupe innerhalb des Tages: (sym, strat) einmal; Shortlist ("sl") gewinnt,
    da sie die KI-Felder trägt (Spez §2)."""
    tickers_by_sym = {t.get("sym"): t for t in (tickers or []) if t.get("sym")}
    recs, seen = [], set()

    # 1) Master-Shortlist — produktnahes Track Record
    for c in (shortlist or []):
        sym, strat = c.get("sym"), c.get("strategy")
        price = c.get("price")
        if not sym or not strat or not price:
            continue
        key = (sym, strat)
        if key in seen:
            continue
        seen.add(key)
        recs.append({
            "sym":   sym,
            "src":   "sl",
            "strat": strat,
            "dir":   -1 if strat.startswith("short") else 1,
            "score": c.get("score"),
            "p0":    round(float(price), 4),
            "atr":   c.get("atr"),
            "fresh": key not in prev_pairs,
            "ki":    _ki_params(c),
            "ctx":   _ctx(tickers_by_sym.get(sym), c),
        })

    # 2) Leaderboards Top-N — Kalibrierungs-Sample
    for lb_name, entries in (leaderboards or {}).items():
        for e in (entries or [])[:LB_TOP_N]:
            sym, price = e.get("sym"), e.get("price")
            if not sym or not price:
                continue
            key = (sym, lb_name)
            if key in seen:
                continue
            seen.add(key)
            recs.append({
                "sym":   sym,
                "src":   "lb",
                "strat": lb_name,
                "dir":   -1 if lb_name.startswith("short") else 1,
                "score": e.get("score"),
                "p0":    round(float(price), 4),
                "atr":   e.get("atr"),
                "fresh": key not in prev_pairs,
                "ki":    None,
                "ctx":   _ctx(tickers_by_sym.get(sym)),
            })

    return {
        "v":          TR_SCHEMA_VERSION,
        "tday":       tday,
        "run":        run_iso,
        "regime":     regime,
        "aggVersion": agg_version,
        "recs":       recs,
    }


# ── Orchestrierung (Nachtlauf-Einhängepunkt, Spez §4 Schritt 1) ──────────────

def run_snapshot(shortlist, leaderboards, tickers, regime, tday, agg_version):
    """Schreibt den Tages-Snapshot + Index. Gibt Status-Dict zurück
    (landet als master["trackRecord"] im Output — Verifikationspfad).
    Wirft keine Exceptions im Normalpfad; Aufrufer kapselt zusätzlich."""
    if not tday:
        return {"written": False, "reason": "no_trading_day"}
    if not _kv_creds():
        log.warning("  [TR] CF-Credentials fehlen — Snapshot übersprungen.")
        return {"written": False, "reason": "no_kv_creds"}

    snap_key = f"tr:snap:{tday}"

    # Dedupe über den Handelstag (schützt vor manuellen Doppel-Runs)
    if kv_get(snap_key) is not None:
        log.info(f"  [TR] Snapshot {snap_key} existiert bereits — übersprungen (Dedupe).")
        return {"written": False, "reason": "exists", "tday": tday}

    # Index + Vortags-Snapshot für fresh-Flags
    index = kv_get("tr:index") or {"v": TR_SCHEMA_VERSION, "days": []}
    days = index.get("days") or []
    prev_pairs = set()
    if days:
        prev_day = days[-1].get("d")
        prev = kv_get(f"tr:snap:{prev_day}") or {}
        prev_pairs = {(r.get("sym"), r.get("strat"))
                      for r in prev.get("recs", [])}

    run_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snap = build_snapshot(shortlist, leaderboards, tickers, regime, tday,
                          agg_version, prev_pairs, run_iso)
    if not snap["recs"]:
        log.warning("  [TR] Leerer Snapshot — nichts geschrieben.")
        return {"written": False, "reason": "empty", "tday": tday}

    if not kv_put(snap_key, snap):
        return {"written": False, "reason": "kv_put_failed", "tday": tday}

    days.append({"d": tday, "n": len(snap["recs"]),
                 "h7": False, "h30": False, "h90": False})
    index["v"] = TR_SCHEMA_VERSION
    index["days"] = days
    index_ok = kv_put("tr:index", index)

    n_fresh = sum(1 for r in snap["recs"] if r["fresh"])
    n_ki    = sum(1 for r in snap["recs"] if r["ki"])
    log.info(f"  [TR] ✅ Snapshot {snap_key}: {len(snap['recs'])} Empfehlungen "
             f"({n_fresh} fresh, {n_ki} mit KI-Parametern) | Index: "
             f"{'aktualisiert' if index_ok else '⚠ FEHLGESCHLAGEN'}")

    return {"written": True, "tday": tday, "n": len(snap["recs"]),
            "fresh": n_fresh, "withKi": n_ki, "indexUpdated": index_ok}
