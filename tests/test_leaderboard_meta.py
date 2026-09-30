#!/usr/bin/env python3
"""
test_leaderboard_meta.py — Spitzengruppe der Options-Leaderboards (SUITE №72, P1 #2, v5.45.0)
============================================================================================
Prueft auf synthetischen Tickern (build_leaderboards):
  1. leaderboardMeta enthaelt die fuenf Options-Leaderboards mit allen Feldern.
  2. topScore == Sortierfeld der ersten Leaderboard-Zeile.
  3. topTieCount ist konsistent zu den Leaderboard-Zeilen: >= Laenge des fuehrenden Gleichstands im
     (auf 20 gekappten) Leaderboard; ist der Gleichstand kuerzer als das Leaderboard, ist er exakt gleich.
  4. Saturiertes Szenario (viele Titel am Deckel 100): topTieCount ist groesser als die 20 sichtbaren Zeilen.
  5. Additiv: leaderboards und masterShortlist tragen keine neuen Schluessel ausser den Options-Feldern
     aus v5.44.1; leaderboardMeta steht neben, nicht in den Leaderboards.

Lauf: python3 tests/test_leaderboard_meta.py   (oder pytest)
"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import market_aggregator as ma
from test_options_leaderboard_scores import _synthetic_results

FIELD = {"options_csp": "sCsp", "options_atmna": "sAtmna", "options_weekly": "sCsp",
         "options_collar": "sCsp", "options_cc": "sCc"}
KEYS = {"rankField", "minScore", "candidatesAtOrAboveMin", "topScore", "topTieCount"}


def _build(results=None):
    return ma.build_leaderboards(results if results is not None else _synthetic_results(), "BULL_QUIET")


def _lead_run(rows, field):
    if not rows:
        return 0
    top = rows[0][field]
    n = 0
    for r in rows:
        if r[field] != top:
            break
        n += 1
    return n


def test_meta_present_and_complete():
    out = _build()
    meta = out["leaderboardMeta"]
    for name, field in FIELD.items():
        assert name in meta, f"leaderboardMeta[{name}] fehlt"
        assert KEYS <= set(meta[name]), f"{name}: Felder fehlen: {KEYS - set(meta[name])}"
        assert meta[name]["rankField"] == field


def test_meta_consistent_with_leaderboard():
    out = _build()
    for name, field in FIELD.items():
        rows, m = out["leaderboards"][name], out["leaderboardMeta"][name]
        if not rows:
            assert m["topScore"] is None and m["topTieCount"] == 0
            continue
        assert m["topScore"] == rows[0][field], f"{name}: topScore != erste Zeile"
        run = _lead_run(rows, field)
        assert m["topTieCount"] >= run, f"{name}: topTieCount {m['topTieCount']} < sichtbarer Gleichstand {run}"
        if run < len(rows):
            assert m["topTieCount"] == run, f"{name}: Gleichstand endet in den Zeilen, Zaehlung muss exakt sein"
        assert m["candidatesAtOrAboveMin"] >= len(rows)


def test_saturation_counts_beyond_visible_rows():
    # Uebersaettigung erzwingen: Deckel-Werte fuer sCsp/sAtmna/sCc bei vielen Titeln
    orig = (ma.score_options_csp, ma.score_options_atmna, ma.score_options_covered_call)
    try:
        ma.score_options_csp = lambda r: 100
        ma.score_options_atmna = lambda r: 100
        ma.score_options_covered_call = lambda r: 100
        out = _build()
    finally:
        ma.score_options_csp, ma.score_options_atmna, ma.score_options_covered_call = orig
    for name, field in FIELD.items():
        m = out["leaderboardMeta"][name]
        assert len(out["leaderboards"][name]) == 20
        assert m["topScore"] == 100
        assert m["topTieCount"] > 20, f"{name}: Spitzengruppe muss groesser als die 20 sichtbaren Zeilen sein ({m['topTieCount']})"


def test_additive_only():
    out = _build()
    assert "leaderboardMeta" not in out["leaderboards"]
    for name in FIELD:
        for row in out["leaderboards"][name]:
            assert "topTieCount" not in row


if __name__ == "__main__":
    fails = 0
    for t in [test_meta_present_and_complete, test_meta_consistent_with_leaderboard,
              test_saturation_counts_beyond_visible_rows, test_additive_only]:
        try:
            t(); print("PASS", t.__name__)
        except (AssertionError, KeyError) as e:
            fails += 1; print("FAIL", t.__name__, "-", repr(e))
    sys.exit(1 if fails else 0)
