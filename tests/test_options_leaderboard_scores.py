#!/usr/bin/env python3
"""
test_options_leaderboard_scores.py — Ranking-Score in den Options-Leaderboards (SUITE №72, G1)
=============================================================================================
Schuetzt die Datenkette Berechnung -> Leaderboard -> strategy_score (UIQ-Suite/scripts/
generate_public_recommendations.js). Bis v5.44.0 fehlte das Sortierfeld (sCsp/sAtmna/sCc) in den
Leaderboard-Zeilen; der Generator fiel dadurch still auf den Composite-Score zurueck.

Prueft je Options-Leaderboard (options_csp/atmna/weekly/collar/cc) auf synthetischen Tickern:
  1. Jede Zeile traegt das Sortierfeld.
  2. Der Feldwert entspricht der direkten Score-Funktion (score_options_*).
  3. Die Zeilen sind nach dem Feld absteigend sortiert.
  4. Ohne Feld-Aenderung an den uebrigen Leaderboards: equity-Zeilen tragen die Options-Felder NICHT
     (gezielte Aufnahme per extra_fields, _core unveraendert).

Lauf:  pytest tests/test_options_leaderboard_scores.py -v     (oder: python3 tests/test_options_leaderboard_scores.py)
"""
import sys, os, random, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

import market_aggregator as ma

# Leaderboard -> (Sortierfeld, Score-Funktion)
OPTIONS_LB = {
    "options_csp":    ("sCsp",   ma.score_options_csp),
    "options_atmna":  ("sAtmna", ma.score_options_atmna),
    "options_weekly": ("sCsp",   ma.score_options_csp),
    "options_collar": ("sCsp",   ma.score_options_csp),
    "options_cc":     ("sCc",    ma.score_options_covered_call),
}
MIN_SCORE = {"options_cc": 30}   # alle anderen 50, s. build_leaderboards()


def _synthetic_results(n=400, seed=29):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        price = round(rnd.uniform(15, 400), 2)
        ema200 = round(price * rnd.uniform(0.85, 1.15), 2)
        out.append({
            "sym": f"T{i:03d}", "price": price, "ema200": ema200, "ema50": round(price * rnd.uniform(0.9, 1.1), 2),
            "hvp": rnd.randint(15, 95), "hv10": round(rnd.uniform(10, 60), 1), "rsi": round(rnd.uniform(20, 80), 1),
            "bbPos": round(rnd.uniform(0, 1), 3), "tightnessPct": round(rnd.uniform(1, 9), 2),
            "regime": rnd.choice(["side", "bull", "bear", "volatile"]), "score": rnd.randint(30, 95),
            "grade": rnd.choice(["A", "B", "C"]), "atr": round(price * rnd.uniform(0.01, 0.05), 2),
            "dist200": round((price / ema200 - 1) * 100, 2), "overheat": rnd.randint(0, 80),
            "earningsDTE": rnd.choice([None, None, -30, 5, 10, 20, 40]),
            "macdHist": rnd.uniform(-1, 1), "obvTrend": rnd.uniform(-1, 1), "volRatio": rnd.uniform(0.5, 2),
            "pctFromHigh52": rnd.uniform(-30, 0), "avgVol20": rnd.randint(200_000, 9_000_000),
        })
    return out


def _leaderboards():
    results = _synthetic_results()
    out = ma.build_leaderboards(results, "BULL_QUIET")
    return results, out["leaderboards"]


def test_options_rows_carry_ranking_field():
    _, lbs = _leaderboards()
    for lb, (field, _fn) in OPTIONS_LB.items():
        rows = lbs[lb]
        assert rows, f"{lb}: leer — Testdaten decken das Leaderboard nicht ab"
        missing = [r["sym"] for r in rows if field not in r]
        assert not missing, f"{lb}: Feld {field} fehlt in {len(missing)}/{len(rows)} Zeilen"


def test_options_field_matches_score_function():
    results, lbs = _leaderboards()
    by_sym = {r["sym"]: r for r in results}
    for lb, (field, fn) in OPTIONS_LB.items():
        for row in lbs[lb]:
            assert field in row, f"{lb} {row['sym']}: Feld {field} fehlt"
            assert row[field] == fn(by_sym[row["sym"]]), f"{lb} {row['sym']}: {field}={row[field]} != {fn.__name__}"
            assert row[field] >= MIN_SCORE.get(lb, 50), f"{lb} {row['sym']}: unter min_score"


def test_options_rows_sorted_by_ranking_field():
    _, lbs = _leaderboards()
    for lb, (field, _fn) in OPTIONS_LB.items():
        assert all(field in r for r in lbs[lb]), f"{lb}: Feld {field} fehlt"
        vals = [r[field] for r in lbs[lb]]
        assert vals == sorted(vals, reverse=True), f"{lb}: nicht absteigend nach {field}"


def test_equity_rows_unchanged():
    _, lbs = _leaderboards()
    for lb in ("long_minervini", "long_swing", "long_mr", "long_breakout", "ko_long"):
        for row in lbs[lb]:
            assert not ({"sCsp", "sAtmna", "sCc"} & set(row)), f"{lb}: Options-Feld in Equity-Zeile (extra_fields-Regel verletzt)"


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)):
        try:
            fn(); print("PASS", name)
        except (AssertionError, KeyError) as e:
            failed += 1; print("FAIL", name, "-", e)
    sys.exit(1 if failed else 0)
