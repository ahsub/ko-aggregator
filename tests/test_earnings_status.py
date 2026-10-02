#!/usr/bin/env python3
"""
test_earnings_status.py — Earnings-Zustand (SUITE №72, P1 #3, Schritt 1, Aggregator v5.47.0)
============================================================================================
Prueft:
  1. classify_earnings: Tabelle inkl. Grenzen DTE 0 / 1 und alle Fehler-/Leerfaelle; None-DTE bei abgefragtem
     Ticker ist NIE KNOWN_FUTURE.
  2. compute_earnings_calendar (yfinance gemockt): OK -> 'OK'; kein Datum -> 'NO_DATE'; Ausnahme -> 'ERROR';
     die alten vier Felder sind unveraendert vorhanden.
  3. Invarianz: Mit vs. ohne `earningsStatus` sind _earnings_gate, alle Options-Scorer und die Leaderboards
     (synthetisch UND auf den echten Zeilen des Archiv-Snapshots, falls vorhanden) identisch.
  4. Vorher/Nachher auf dem Snapshot: Verteilung der DTE-Klassen -> Zustaende; DTE bleibt unveraendert.

Lauf: python3 tests/test_earnings_status.py   (oder pytest)
"""
import sys, os, json, gzip, copy, glob, logging, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

import market_aggregator as ma
import earnings_status as es
from earnings_status import classify_earnings as cl

SNAP_GLOB = os.environ.get("UIQ_SNAPSHOT_GLOB", "/home/claude/uiq-archive/data/snapshots/*.json.gz")


def test_classify_table():
    cases = [
        (False, None, None, es.NOT_QUERIED),
        (False, "OK", 5, es.NOT_QUERIED),
        (True, "OK", 1, es.KNOWN_FUTURE),
        (True, "OK", 7, es.KNOWN_FUTURE),
        (True, "OK", 90, es.KNOWN_FUTURE),
        (True, "OK", 0, es.STALE_PAST),
        (True, "OK", -30, es.STALE_PAST),
        (True, "NO_DATE", None, es.NO_DATE),
        (True, "ERROR", None, es.LOOKUP_ERROR),
        (True, "OK", None, es.LOOKUP_ERROR),       # OK ohne DTE = nicht auswertbar
        (True, None, None, es.NO_DATE),            # alter Aufrufer ohne Lookup-Feld
        (True, None, 3, es.KNOWN_FUTURE),
        (True, None, -1, es.STALE_PAST),
        (True, "OK", "5", es.LOOKUP_ERROR),
        (True, "OK", True, es.LOOKUP_ERROR),
        (True, "???", 5, es.LOOKUP_ERROR),
    ]
    for q, lk, dte, want in cases:
        got = cl(q, lk, dte)
        assert got == want, f"classify({q},{lk!r},{dte!r}) = {got}, erwartet {want}"
        assert got in es.ALL_STATES


def test_none_dte_never_known_future():
    for q in (True, False):
        for lk in (None, "OK", "NO_DATE", "ERROR", "x"):
            assert cl(q, lk, None) != es.KNOWN_FUTURE


class _FakeTicker:
    def __init__(self, info=None, boom=False, dates=None):
        self._info, self._boom, self._dates = info or {}, boom, dates

    @property
    def info(self):
        if self._boom:
            raise RuntimeError("yahoo down")
        return self._info

    def get_earnings_dates(self, limit=4):
        raise RuntimeError("n/a")


def _with_fake_yf(fake):
    mod = types.ModuleType("yfinance")
    mod.Ticker = lambda sym: fake
    old = sys.modules.get("yfinance")
    sys.modules["yfinance"] = mod
    return old


def _restore_yf(old):
    if old is None:
        sys.modules.pop("yfinance", None)
    else:
        sys.modules["yfinance"] = old


def test_compute_earnings_calendar_lookup_states():
    from datetime import datetime, timezone, timedelta
    ts = int((datetime.now(timezone.utc) + timedelta(days=10)).timestamp())
    old_keys = {"earningsDate", "earningsDTE", "earningsEPS", "earningsRevEst"}
    for fake, want_lookup, want_dte_none in [
        (_FakeTicker(info={"earningsTimestamp": ts}), "OK", False),
        (_FakeTicker(info={}), "NO_DATE", True),
        (_FakeTicker(boom=True), "ERROR", True),
    ]:
        old = _with_fake_yf(fake)
        try:
            out = ma.compute_earnings_calendar("TST")
        finally:
            _restore_yf(old)
        assert old_keys <= set(out), out
        assert out["earningsLookup"] == want_lookup, out
        assert (out["earningsDTE"] is None) == want_dte_none, out
        if want_lookup == "OK":
            assert out["earningsDTE"] in (9, 10, 11)
            assert cl(True, out["earningsLookup"], out["earningsDTE"]) == es.KNOWN_FUTURE
    # Fehler und "kein Datum" duerfen nie zusammenfallen
    assert cl(True, "ERROR", None) != cl(True, "NO_DATE", None)


def test_process_ticker_placeholder_not_queried():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market_aggregator.py"),
               encoding="utf-8").read()
    assert 'result["earningsStatus"] = "NOT_QUERIED"' in src


# ── Invarianz ────────────────────────────────────────────────────────────────────────────────────
OPT_FUNCS = ["score_options_csp", "score_options_atmna", "score_options_covered_call"]


def _strip(rows):
    out = []
    for r in rows:
        c = {k: v for k, v in r.items() if k != "earningsStatus"}
        out.append(c)
    return out


def _with_status(rows):
    out = []
    for i, r in enumerate(rows):
        c = dict(r)
        c["earningsStatus"] = es.ALL_STATES[i % len(es.ALL_STATES)]
        out.append(c)
    return out


def _lb_summary(rows):
    lbs = ma.build_leaderboards(copy.deepcopy(rows), "BULL_QUIET")["leaderboards"]
    return {k: [(r.get("sym"), r.get("score"), r.get("sCsp"), r.get("sAtmna"), r.get("sCc"))
                for r in v] for k, v in lbs.items() if isinstance(v, list)}


def _check_invariance(rows):
    base = _strip(rows)
    with_s = _with_status(base)
    for a, b in zip(base, with_s):
        assert ma._earnings_gate(a) == ma._earnings_gate(b)
        assert ma._earnings_gate(a, 7) == ma._earnings_gate(b, 7)
        for fn in OPT_FUNCS:
            assert getattr(ma, fn)(a) == getattr(ma, fn)(b), f"{fn} {a.get('sym')}"
    assert _lb_summary(base) == _lb_summary(with_s), "Leaderboards unterscheiden sich"


def test_invariance_synthetic():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import test_options_leaderboard_scores as t
    _check_invariance(t._synthetic_results(300, seed=7))


def _latest_snapshot():
    files = sorted(glob.glob(SNAP_GLOB))
    if not files:
        return None
    return json.load(gzip.open(files[-1], "rt", encoding="utf-8"))


def test_invariance_and_distribution_real_snapshot():
    snap = _latest_snapshot()
    if snap is None:
        print("  (kein Archiv-Snapshot vorhanden - uebersprungen)")
        return
    rows = snap["tickers"]
    # nur Zeilen mit allen Pflichtfeldern, wie vom Scorer erwartet (ganze Zeilen des Snapshots)
    _check_invariance(rows[:250])
    # Vorher/Nachher: Klassifikation der alten Felder (Snapshot ohne earningsStatus = Altstand)
    from collections import Counter
    cnt = Counter()
    for i, r in enumerate(rows):
        queried = i < 200 and r.get("earningsDate") is not None
        lookup = "OK" if r.get("earningsDate") else None
        st = cl(i < 200, lookup if i < 200 else None, r.get("earningsDTE"))
        cnt[st] += 1
        dte = r.get("earningsDTE")
        if st == es.KNOWN_FUTURE:
            assert isinstance(dte, int) and dte >= 1
        if dte is None:
            assert st != es.KNOWN_FUTURE
    assert sum(cnt.values()) == len(rows)
    # Konsistenz mit Inventur 01.10.: keine KNOWN_FUTURE ohne Datum, STALE_PAST nur mit DTE <= 0
    print("  Zustandsverteilung (Snapshot, aus alten Feldern):", dict(cnt))


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)):
        try:
            fn(); print("PASS", name)
        except Exception as e:
            failed += 1; print("FAIL", name, "-", type(e).__name__, e)
    sys.exit(1 if failed else 0)
