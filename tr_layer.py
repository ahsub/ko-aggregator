#!/usr/bin/env python3
"""
UIQ Track-Record-Layer — Snapshot-Writer (Phase A) + Evaluator (Phase B)
=========================================================================
Version 1.1 (03.07.2026) | Spezifikation: docs/TRACK_RECORD_SPEC.md v1.2

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


# ═══════════════════════════════════════════════════════════════════════════
# PHASE B: EVALUATOR + AGGREGATION (v1.1, 03.07.2026 — Spez §3.3/§3.4/§4/§5)
# ═══════════════════════════════════════════════════════════════════════════

HORIZONS = (7, 30, 90)
_DUE_BUFFER = 3   # Extra-SPY-Bars vor Fälligkeit: EU-Ticker (eigener Feiertags-
                  # kalender) haben zum Bewertungszeitpunkt sicher genug Bars.


def _series(df):
    """(dates, closes, highs, lows) aus einem yfinance-DataFrame.
    None bei unbrauchbaren Daten. Fehlende High/Low-Spalten → Close-Fallback."""
    try:
        if df is None or len(df) < 2:
            return None

        def col(name):
            if name in df.columns:
                return df[name]
            for c in df.columns:
                n = c[0] if isinstance(c, tuple) else str(c)
                if n == name:
                    return df[c]
            return None

        cl = col("Close")
        if cl is None:
            return None
        cl = cl.dropna()
        if len(cl) < 2:
            return None
        hi, lo = col("High"), col("Low")
        dates  = [d.date() for d in cl.index]
        closes = [float(x) for x in cl.tolist()]
        highs  = [float(x) for x in (hi.reindex(cl.index).fillna(cl) if hi is not None else cl).tolist()]
        lows   = [float(x) for x in (lo.reindex(cl.index).fillna(cl) if lo is not None else cl).tolist()]
        return dates, closes, highs, lows
    except Exception:
        return None


def _idx_on_or_before(dates, dstr):
    """Index des letzten Bars mit Datum <= dstr (aufsteigend sortierte Liste)."""
    from datetime import date as _date
    try:
        y, m, d = map(int, str(dstr).split("-"))
        target = _date(y, m, d)
    except Exception:
        return None
    idx = None
    for i, dt in enumerate(dates):
        if dt <= target:
            idx = i
        else:
            break
    return idx


def _eval_horizon(rec, ser, tday, H):
    """Richtungsgerechte Rendite + MFE/MAE nach H Handelstagen (Bars des
    Tickers selbst). None, wenn nicht genug Bars (→ noData für diesen Horizont).
    Renditen aus konsistent adjustierter Historie (nicht aus gespeichertem p0 —
    Dividenden-Readjustierung würde sonst verzerren; p0 bleibt Dokumentation)."""
    dates, closes, highs, lows = ser
    i0 = _idx_on_or_before(dates, tday)
    if i0 is None or i0 + H >= len(closes):
        return None
    c0 = closes[i0]
    if not c0:
        return None
    d   = rec.get("dir", 1)
    raw = closes[i0 + H] / c0 - 1
    hw  = highs[i0 + 1:i0 + H + 1]
    lw  = lows[i0 + 1:i0 + H + 1]
    if d == 1:
        mfe, mae = max(hw) / c0 - 1, min(lw) / c0 - 1
    else:
        mfe, mae = -(min(lw) / c0 - 1), -(max(hw) / c0 - 1)
    return {"r": round(d * raw * 100, 2), "mfe": round(mfe * 100, 2),
            "mae": round(mae * 100, 2), "raw": raw}


def _sim_trade(rec, ser, tday, max_bars):
    """KI-Trade-Simulation (Spez §3.3): Stop-Order-Einstieg am Trigger,
    danach Stop/Target; Same-Bar-Ambiguität konservativ als STOP.
    st ∈ NOT_TRIGGERED | OPEN | TARGET | STOP; r = realisiertes R-Multiple."""
    ki = rec.get("ki")
    if not ki:
        return None
    dates, closes, highs, lows = ser
    i0 = _idx_on_or_before(dates, tday)
    if i0 is None:
        return None
    d = rec.get("dir", 1)
    trig, sl, tgt = ki.get("trig"), ki.get("sl"), ki.get("tgt")
    if trig is None or sl is None or tgt is None:
        return None
    risk = (trig - sl) if d == 1 else (sl - trig)
    if not risk or risk <= 0:
        return None   # implausible KI-Parameter → keine Simulation
    end = min(i0 + max_bars, len(closes) - 1)
    trig_i, st, exit_p, exit_i = None, "NOT_TRIGGERED", None, None
    for i in range(i0 + 1, end + 1):
        if trig_i is None:
            hit = (highs[i] >= trig) if d == 1 else (lows[i] <= trig)
            if not hit:
                continue
            trig_i = i
        if d == 1:
            if lows[i] <= sl:
                st, exit_p, exit_i = "STOP", sl, i; break
            if highs[i] >= tgt:
                st, exit_p, exit_i = "TARGET", tgt, i; break
        else:
            if highs[i] >= sl:
                st, exit_p, exit_i = "STOP", sl, i; break
            if lows[i] <= tgt:
                st, exit_p, exit_i = "TARGET", tgt, i; break
    if trig_i is not None and st == "NOT_TRIGGERED":
        st = "OPEN"
    out = {"st": st}
    if exit_p is not None:
        r = (exit_p - trig) / risk if d == 1 else (trig - exit_p) / risk
        out["r"], out["bars"] = round(r, 2), exit_i - i0
    return out


def _median(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _aggregate_stats(days):
    """Voll-Recompute von tr:stats aus allen tr:eval:* (Spez §3.4).
    TODO (Optimierung ab ~150 Tagen): inkrementelle Aggregation statt
    nächtlicher GETs aller Eval-Dokumente."""
    from datetime import datetime as _dt, timezone as _tz
    cells, trade_acc, total = {}, {}, 0
    since = days[0].get("d") if days else None
    for drec in days:
        if not any(drec.get(f"h{H}") for H in HORIZONS):
            continue
        ev = kv_get(f"tr:eval:{drec.get('d')}")
        if not ev:
            continue
        regime = ev.get("regime") or "UNKNOWN"
        for er in ev.get("recs", {}).values():
            total += 1
            strat = er.get("strat")
            for H in HORIZONS:
                rk = f"r{H}"
                if rk not in er:
                    continue          # Horizont für diesen Tag noch nicht fällig
                ck = f"{strat}|{regime}|h{H}"
                c = cells.setdefault(ck, {"n": 0, "nFresh": 0, "noData": 0,
                                          "_r": [], "_rf": [], "_a": [], "_mae": []})
                r = er.get(rk)
                if r is None:
                    c["noData"] += 1
                    continue
                c["n"] += 1
                c["_r"].append(r)
                if er.get("fresh"):
                    c["nFresh"] += 1
                    c["_rf"].append(r)
                a = er.get(f"a{H}")
                if a is not None:
                    c["_a"].append(a)
                m = er.get(f"mae{H}")
                if m is not None:
                    c["_mae"].append(m)
            tr = er.get("trade")
            if tr and tr.get("st") in ("TARGET", "STOP"):
                tk = f"{strat}|{regime}"
                t = trade_acc.setdefault(tk, {"n": 0, "win": 0, "_r": []})
                t["n"] += 1
                t["win"] += 1 if tr["st"] == "TARGET" else 0
                if "r" in tr:
                    t["_r"].append(tr["r"])

    out_cells = {}
    for ck, c in cells.items():
        if c["n"] == 0 and c["noData"] == 0:
            continue
        oc = {"n": c["n"], "nFresh": c["nFresh"], "noData": c["noData"]}
        if c["_r"]:
            oc["hit"] = round(sum(1 for x in c["_r"] if x > 0) / len(c["_r"]), 2)
            oc["avg"] = round(sum(c["_r"]) / len(c["_r"]), 2)
            oc["med"] = round(_median(c["_r"]), 2)
        if c["_rf"]:
            oc["hitFresh"] = round(sum(1 for x in c["_rf"] if x > 0) / len(c["_rf"]), 2)
        if c["_a"]:
            oc["alpha"] = round(sum(c["_a"]) / len(c["_a"]), 2)
        if c["_mae"]:
            oc["mae"] = round(sum(c["_mae"]) / len(c["_mae"]), 2)
        out_cells[ck] = oc

    # Trade-Simulation in die h30-Zelle einbetten (Leithorizont, Spez §3.4)
    for tk, t in trade_acc.items():
        oc = out_cells.setdefault(f"{tk}|h30", {"n": 0, "nFresh": 0, "noData": 0})
        td = {"n": t["n"], "win": round(t["win"] / t["n"], 2)}
        if t["_r"]:
            td["avgR"] = round(sum(t["_r"]) / len(t["_r"]), 2)
        oc["trade"] = td

    # Rollups über h30 (n-gewichtet)
    def _roll(pick):
        acc = {}
        for ck, oc in out_cells.items():
            strat, regime, h = ck.split("|")
            if h != "h30" or oc.get("n", 0) == 0 or "avg" not in oc:
                continue
            k = pick(strat, regime)
            a = acc.setdefault(k, {"n": 0, "hs": 0.0, "as": 0.0})
            a["n"] += oc["n"]
            a["hs"] += oc.get("hit", 0) * oc["n"]
            a["as"] += oc["avg"] * oc["n"]
        return {k: {"n": a["n"], "hit": round(a["hs"] / a["n"], 2),
                    "avg": round(a["as"] / a["n"], 2)}
                for k, a in acc.items() if a["n"]}

    return {"v": TR_SCHEMA_VERSION,
            "updated": _dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "since": since, "totalRecs": total, "cells": out_cells,
            "byStrategy": _roll(lambda s, r: s),
            "byRegime":   _roll(lambda s, r: r)}


def run_evaluation(hist_data):
    """Bewertet alle fälligen Snapshot-Tage (Spez §4 Schritt 2+3) und
    aktualisiert tr:eval:<d>, tr:index und tr:stats.
    Nutzt ausschließlich das bereits geladene hist_data des Nachtlaufs
    (Null-Extra-Downloads); SPY dient als Handelstags-Kalender.
    Ticker ohne ausreichende Bars → rH=None (noData in der Statistik)."""
    if not _kv_creds():
        return {"evaluated": 0, "reason": "no_kv_creds"}
    index = kv_get("tr:index")
    days = (index or {}).get("days") or []
    if not days:
        return {"evaluated": 0, "reason": "no_index"}
    spy_ser = _series((hist_data or {}).get("SPY"))
    if not spy_ser:
        return {"evaluated": 0, "reason": "no_spy"}
    spy_dates, spy_closes = spy_ser[0], spy_ser[1]

    changed = []
    for drec in days:
        d = drec.get("d")
        i0s = _idx_on_or_before(spy_dates, d)
        if i0s is None:
            continue
        elapsed = len(spy_dates) - 1 - i0s
        due = [H for H in HORIZONS
               if not drec.get(f"h{H}") and elapsed >= H + _DUE_BUFFER]
        if not due:
            continue
        snap = kv_get(f"tr:snap:{d}")
        if not snap:
            for H in due:
                drec[f"h{H}"] = True   # kein Snapshot → abhaken statt ewig retryen
            changed.append(d)
            continue
        ev = kv_get(f"tr:eval:{d}") or {"v": TR_SCHEMA_VERSION, "tday": d,
                                        "regime": snap.get("regime"), "recs": {}}
        max_bars = min(90, elapsed)
        for rec in snap.get("recs", []):
            key = f"{rec.get('sym')}|{rec.get('strat')}"
            er = ev["recs"].setdefault(key, {
                "sym": rec.get("sym"), "strat": rec.get("strat"),
                "src": rec.get("src"), "dir": rec.get("dir", 1),
                "fresh": bool(rec.get("fresh"))})
            ser = _series((hist_data or {}).get(rec.get("sym")))
            for H in due:
                res = _eval_horizon(rec, ser, d, H) if ser else None
                if res is None:
                    er[f"r{H}"] = None
                    continue
                er[f"r{H}"]   = res["r"]
                er[f"mfe{H}"] = res["mfe"]
                er[f"mae{H}"] = res["mae"]
                if i0s + H < len(spy_closes):
                    dsign = rec.get("dir", 1)
                    spy_raw = spy_closes[i0s + H] / spy_closes[i0s] - 1
                    er[f"a{H}"] = round((dsign * res["raw"] - dsign * spy_raw) * 100, 2)
            if rec.get("ki") and ser:
                tr = _sim_trade(rec, ser, d, max_bars)
                if tr:
                    er["trade"] = tr   # bei jedem Pass aktualisiert; final ab h90
        for H in due:
            drec[f"h{H}"] = True
        if kv_put(f"tr:eval:{d}", ev):
            changed.append(d)
            log.info(f"  [TR] Bewertet {d}: Horizonte {due} | {len(ev['recs'])} Empfehlungen")

    if not changed:
        return {"evaluated": 0}
    kv_put("tr:index", index)
    stats = _aggregate_stats(days)
    stats_ok = kv_put("tr:stats", stats) if stats else False
    log.info(f"  [TR] ✅ Evaluation: {len(changed)} Tag(e) | tr:stats: "
             f"{len((stats or {}).get('cells', {}))} Zellen "
             f"{'aktualisiert' if stats_ok else '⚠ Upload fehlgeschlagen'}")
    return {"evaluated": len(changed), "days": changed,
            "statsUpdated": stats_ok,
            "cells": len((stats or {}).get("cells", {}))}
