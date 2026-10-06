#!/usr/bin/env python3
"""
test_data_integrity.py — D26 Variante A-1 (diagnostisch, Aggregator v5.48.0)
============================================================================
Beobachtungsfelder fuer D26 (letzte yfinance-Tageszeile mit Datum/Volumen, aber OHLC = NaN):
  Ticker: `_lastRowIncomplete`, `_lastCloseDate`      (process_ticker)
  Lauf:   meta.data_integrity via calc_data_integrity(results, last_trading_day)

Geprueft (Pflicht-Header Punkt 7: Inhalt, positive UND negative Faelle):
  T1  NaN-Letztzeile: Flag True, _lastCloseDate = vorletzte Zeile, bars = N-1, _bars_raw = N;
      price bleibt der letzte gueltige Close (heutiges Verhalten, bewusst UNVERAENDERT).
  T2  Saubere Daten: Flag False, _lastCloseDate = _dataAsOf.
  T3  INVARIANZ: Ausgabe von process_ticker() == Golden-Fixture der Version 5.47.0 (561a6f0)
      MINUS die zwei neuen Felder, Schluessel fuer Schluessel (price, volRatio, Scores, _dataAsOf ...).
  T4  Laufebene gegen alle 182 Archiv-Laeufe (Zaehlwerte aus uiq-archive): LAST_ROW_INCOMPLETE genau in den 26
      D26-Laeufen. (Fixture: tests/fixtures_data_integrity_runs.json)
  T5  Laufklassen auf Ticker-Ebene (D26, sauber, EU-only, D27): richtige Flags.
  T6  Reinheit: calc_data_integrity veraendert results nicht; leere/fehlende Eingaben -> kein Fehler.

Kein Backtest, keine Kursauswertung: reine Datenintegritaets-Zaehlung.
Lauf: python3 tests/test_data_integrity.py   (oder pytest)
"""
import sys, os, json, copy, logging, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

import numpy as np
import pandas as pd
import market_aggregator as ma

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "fixtures_data_integrity_golden.json")
RUNS = os.path.join(HERE, "fixtures_data_integrity_runs.json")
NEW_FIELDS = ("_lastRowIncomplete", "_lastCloseDate")
VOLATILE = ("updated",)          # Verarbeitungszeitpunkt, bewusst nicht deterministisch


# ── synthetische Daten (deterministisch, ohne Netz) ──────────────────────────────────────
def _frame(n, seed, end="2026-10-02"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=n)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, n)))
    high = close * (1 + rng.uniform(0.001, 0.02, n))
    low = close * (1 - rng.uniform(0.001, 0.02, n))
    open_ = close * (1 + rng.normal(0, 0.004, n))
    vol = rng.integers(800_000, 3_000_000, n).astype(float)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def make_cases():
    """name -> (ticker, DataFrame|None)"""
    c = {}
    c["clean_300"] = ("TESTA", _frame(300, 1))
    d26 = _frame(300, 2)
    d26.loc[d26.index[-1], ["Open", "High", "Low", "Close"]] = np.nan      # Volume der Letztzeile bleibt
    c["d26_last_nan"] = ("TESTB", d26)
    d26l = _frame(300, 3)
    d26l.loc[d26l.index[-1], ["Open", "High", "Low", "Close"]] = np.nan
    d26l.loc[d26l.index[-1], "Volume"] = 0.0                               # wie .L-Titel: Volumen 0
    c["d26_last_nan_vol0"] = ("TEST.DE", d26l)
    mid = _frame(300, 4)
    mid.loc[mid.index[-50], ["Open", "High", "Low", "Close"]] = np.nan     # NaN-Zeile MITTEN in der Historie
    c["mid_nan_last_valid"] = ("TESTC", mid)
    c["short_35"] = ("TESTD", _frame(35, 5))
    c["too_short_29"] = ("TESTE", _frame(29, 6))
    few = _frame(31, 7)
    few.iloc[-6:-1, :4] = np.nan                                            # 31 Zeilen, aber nur 26 gueltige Closes
    c["closes_lt_30"] = ("TESTF", few)
    c["none_frame"] = ("TESTG", None)
    crypto = _frame(300, 8)
    c["crypto_clean"] = ("TEST-USD", crypto)
    return c


def _jsonable(x):
    """Rekursiv JSON-faehig machen (NaN/inf -> None, numpy-Skalare -> Python), danach round-trip."""
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        try:
            x = x.item()
        except Exception:
            return str(x)
    if isinstance(x, float) and (x != x or x in (float("inf"), float("-inf"))):
        return None
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    return str(x)


def _run(name):
    ticker, df = make_cases()[name]
    return ma.process_ticker(ticker, df)


def _strip(d, drop):
    return {k: v for k, v in d.items() if k not in drop}


# ── T1 / T2 ─────────────────────────────────────────────────────────────────────────────
def test_T1_incomplete_last_row():
    ticker, df = make_cases()["d26_last_nan"]
    r = ma.process_ticker(ticker, df)
    assert r["_lastRowIncomplete"] is True
    assert r["bars"] == len(df) - 1 and r["_bars_raw"] == len(df)
    assert r["_lastCloseDate"] == df.index[-2].strftime("%Y-%m-%d")
    assert r["_dataAsOf"] == df.index[-1].strftime("%Y-%m-%d")
    # heutiges Verhalten bleibt: Preis = letzter gueltiger Close (Vortag), NICHT korrigiert
    assert abs(r["price"] - round(float(df["Close"].dropna().iloc[-1]), 4)) < 1e-9


def test_T1b_zero_volume_and_mid_nan():
    r = _run("d26_last_nan_vol0")
    assert r["_lastRowIncomplete"] is True
    # NaN mitten in der Historie, letzte Zeile gueltig -> KEIN Flag (genau der Unterschied zu `_bars_raw - bars`)
    m = _run("mid_nan_last_valid")
    assert m["_bars_raw"] - m["bars"] == 1
    assert m["_lastRowIncomplete"] is False
    ticker, df = make_cases()["mid_nan_last_valid"]
    assert m["_lastCloseDate"] == df.index[-1].strftime("%Y-%m-%d")


def test_T2_clean():
    for name in ("clean_300", "short_35", "crypto_clean"):
        ticker, df = make_cases()[name]
        r = ma.process_ticker(ticker, df)
        assert r["_lastRowIncomplete"] is False, name
        assert r["_lastCloseDate"] == r["_dataAsOf"] == df.index[-1].strftime("%Y-%m-%d"), name


def test_T2b_error_paths_unchanged():
    for name in ("too_short_29", "closes_lt_30", "none_frame"):
        r = _run(name)
        assert r.get("error") == "insufficient_data", name
        assert not any(k in r for k in NEW_FIELDS), name     # Fehlerpfad bleibt wie bisher


# ── T3 Invarianz ────────────────────────────────────────────────────────────────────────
def _same(a, b, rel=1e-9):
    """Gleichheit mit Gleitkomma-Toleranz (1e-9 relativ). Die Golden-Fixture stammt aus einer
    bestimmten numpy/pandas-Version; andere Versionen (Mac, GitHub Actions mit ungepinnten Paketen)
    weichen in der letzten Stelle ab (ULP). Echte Aenderungen (Score, Datum, Struktur) liegen
    um Groessenordnungen darueber und werden weiter erkannt. Nicht-Floats: exakt."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, float) or isinstance(b, float):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            return False
        if a != a and b != b:
            return True
        return math.isclose(a, b, rel_tol=rel, abs_tol=1e-12)
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_same(a[k], b[k], rel) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y, rel) for x, y in zip(a, b))
    return a == b


def test_T3_invariance_against_golden_5_47_0():
    with open(GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)
    assert set(golden["cases"]) == set(make_cases()), "Golden-Fixture und Testfaelle weichen ab"
    for name, ref in golden["cases"].items():
        new = _jsonable(_strip(_run(name), NEW_FIELDS + VOLATILE))
        ref = _strip(ref, VOLATILE)
        assert set(new) == set(ref), (name, sorted(set(new) ^ set(ref)))
        for k in ref:
            assert _same(new[k], ref[k]), (name, k, new[k], ref[k])


# ── T4 Laufebene gegen Archiv ───────────────────────────────────────────────────────────
def _run_summary_to_results(rec):
    """Baut aus den Archiv-Zaehlwerten eines Laufs minimale Ticker-Dicts (nur die Felder, die
    calc_data_integrity liest). US: us_of Ticker (davon us_flag mit Flag, us_ahead mit _dataAsOf != Label);
    Nicht-US: nonus_of (davon nonus_flag)."""
    ltd = rec["ltd"]
    prev = "2000-01-01"
    res = []
    for i in range(rec["us_of"]):
        res.append({"sym": f"U{i}", "homeMarket": "US",
                    "_lastRowIncomplete": i < rec["us_flag"],
                    "_dataAsOf": prev if i < rec["us_ahead"] else ltd})
    for i in range(rec["nonus_of"]):
        res.append({"sym": f"N{i}.DE", "homeMarket": "DE",
                    "_lastRowIncomplete": i < rec["nonus_flag"], "_dataAsOf": ltd})
    for r in res:
        r["_lastCloseDate"] = r["_dataAsOf"]
    if rec.get("spy") is not None:
        res.append({"sym": "SPY", "homeMarket": "US", "_lastRowIncomplete": bool(rec["spy"]), "_dataAsOf": ltd,
                    "_lastCloseDate": ltd})
    return res, ltd


def test_T4_all_archive_runs():
    with open(RUNS, encoding="utf-8") as f:
        runs = json.load(f)["runs"]
    assert len(runs) == 182
    pos = [r for r in runs if r["expect_last_row"]]
    assert len(pos) == 26 and len(runs) - len(pos) == 156
    for rec in runs:
        res, ltd = _run_summary_to_results(rec)
        di = ma.calc_data_integrity(res, ltd)
        has = "LAST_ROW_INCOMPLETE" in di["flags"]
        assert has == rec["expect_last_row"], (rec["n"], di)
        if rec.get("expect_label_ahead") is not None:
            assert ("LABEL_AHEAD_OF_TICKER_DATA" in di["flags"]) == rec["expect_label_ahead"], (rec["n"], di)
        # Zweiter Durchgang OHNE SPY-Flag: der US-Anteil allein muss die Laeufe trennen (prueft die Schwelle,
        # nicht nur die Deckungsgleichheit mit SPY)
        rec2 = dict(rec, spy=None)
        res2, ltd2 = _run_summary_to_results(rec2)
        di2 = ma.calc_data_integrity(res2, ltd2)
        assert ("LAST_ROW_INCOMPLETE" in di2["flags"]) == rec["expect_last_row"], (rec["n"], "ohne SPY", di2)


# ── T5 Laufklassen mit Ticker-Ebene ─────────────────────────────────────────────────────
def _mk(n_us, n_non, us_flag, non_flag, spy, ahead=0, ltd="2026-10-02"):
    res = []
    for i in range(n_us):
        res.append({"sym": f"U{i}", "homeMarket": "US", "_lastRowIncomplete": i < us_flag,
                    "_dataAsOf": "2026-10-01" if i < ahead else ltd, "_lastCloseDate": ltd})
    for i in range(n_non):
        res.append({"sym": f"N{i}.DE", "homeMarket": "DE", "_lastRowIncomplete": i < non_flag,
                    "_dataAsOf": ltd, "_lastCloseDate": ltd})
    res.append({"sym": "SPY", "homeMarket": "US", "_lastRowIncomplete": spy, "_dataAsOf": ltd, "_lastCloseDate": ltd})
    return res, ltd


def test_T5_run_classes():
    # D26 (wie 2026-10-03_01): ~92 % US, 30/31 Nicht-US, SPY
    res, ltd = _mk(707, 31, 651, 30, True)
    di = ma.calc_data_integrity(res, ltd)
    assert di["flags"] == ["LAST_ROW_INCOMPLETE"], di
    # sauber (wie 2026-10-04_13)
    res, ltd = _mk(711, 31, 0, 0, False)
    assert ma.calc_data_integrity(res, ltd)["flags"] == []
    # EU-only (wie 2026-09-29_01 / 2026-10-06_02): US sauber, 30 von 31 Nicht-US geflaggt -> KEIN Lauf-Flag
    res, ltd = _mk(707, 31, 2, 30, False)
    di = ma.calc_data_integrity(res, ltd)
    assert di["flags"] == [], di
    assert di["lastRowIncomplete"]["nonUs"]["n"] == 30 and di["lastRowIncomplete"]["nonUs"]["of"] == 31
    # D27-Beobachtung (wie 2026-09-22_13): keine Extra-Zeile, Label VOR den Ticker-Daten
    res, ltd = _mk(711, 31, 0, 0, False, ahead=711, ltd="2026-09-22")
    di = ma.calc_data_integrity(res, ltd)
    assert di["flags"] == ["LABEL_AHEAD_OF_TICKER_DATA"], di


# ── T6 Reinheit/Robustheit ──────────────────────────────────────────────────────────────
def test_T6_pure_and_robust():
    res, ltd = _mk(100, 10, 95, 10, True)
    before = copy.deepcopy(res)
    ma.calc_data_integrity(res, ltd)
    assert res == before
    for bad in ([], [{"sym": "X"}], [{"sym": "Y", "homeMarket": "US", "_lastRowIncomplete": None}]):
        di = ma.calc_data_integrity(bad, "2026-10-02")
        assert di["flags"] == [] and di["schema"] == "data_integrity/1"
    assert ma.calc_data_integrity(None, None)["flags"] == []


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        try:
            fn(); print("PASS", name)
        except Exception as e:
            fails += 1; print("FAIL", name, repr(e)[:300])
    sys.exit(1 if fails else 0)
