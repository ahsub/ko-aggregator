#!/usr/bin/env python3
"""
test_dce_public.py — DCE-Trennung (SUITE №72 / Runmap 2, Nacht A, v5.46.0)
=========================================================================
Prueft:
  1. dce_public hat exakt die Whitelist-Schluessel; keine internen Felder (confidence, mode, direction,
     position_size, warnings, var_95, cusum_alarm, regime_probs, divergences, cusum_buffer) irgendwo darin.
  2. CUSUM und VaR sind immer n/v mit Ursache — auch bei "gesundem" DCE-Objekt (keine Korrektur, E1).
  3. Signalbreite: ok nur bei echtem DCE mit n>0; n/v bei None, {}, fallback:true, leerer/fehlender
     Aggregation, n=0, ungueltigen Werten.
  4. E4: Ein Fallback-Objekt (dce_layer._fallback UND das Aggregator-Fallback-Dict) landet nie als Signal.
  5. split_public_master: Kopie ohne `dce`, ohne meta.dce_cusum_buffer, mit dce_public; Original unveraendert;
     uebrige Schluessel identisch (additiv/subtraktiv nur diese Felder); Ergebnis JSON-serialisierbar und
     enthaelt als Text weder "position_size" noch "\"direction\":\"SELL\"" aus dem DCE-Objekt.
  6. Fallback-Kennzeichnung aus dce_layer (_fallback) vorhanden.

Lauf: python3 tests/test_dce_public.py   (oder pytest)
"""
import sys, os, json, copy, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

import dce_public as dp
from dce_layer import DecisionConfidenceEngine

INTERNAL_FIELDS = ["confidence", "mode", "direction", "position_size", "warnings", "var_95",
                   "cusum_alarm", "regime_probs", "divergences", "cusum_buffer", "bn_signal", "hmm_state"]


def _real_dce():
    return {
        "version": "1.0", "confidence": 71, "mode": "GREEN", "position_size": 1.0, "direction": "SELL",
        "regime": "BULL_QUIET", "regime_probs": {}, "bn_signal": None, "hmm_state": None,
        "var_95": -0.0136, "cusum_alarm": False,
        "aggregated": {"consensus": 0.25, "bullish_pct": 0.183, "std_dev": 0.2, "n": 738},
        "divergences": [], "warnings": ["Testwarnung mit Handlungsbezug"], "cusum_buffer": [17.5],
        "timestamp": "2026-09-30T22:00:00+00:00",
    }


def _aggregator_fallback():  # exakt wie im except-Zweig von market_aggregator.py
    return {"confidence": 50, "mode": "YELLOW", "position_size": 0.5, "direction": "HOLD",
            "regime": "BULL_QUIET", "fallback": True, "warnings": ["DCE-Fehler: x"]}


def _master():
    return {"meta": {"generated": "2026-09-30T22:00:00Z", "last_trading_day": "2026-09-30",
                     "dce_cusum_buffer": [17.5], "version": "5.46.0"},
            "dce": _real_dce(), "tickers": [{"t": "AAPL"}], "leaderboards": {"a": [1]}}


def _all_keys(o, acc=None):
    acc = set() if acc is None else acc
    if isinstance(o, dict):
        for k, v in o.items():
            acc.add(k); _all_keys(v, acc)
    elif isinstance(o, list):
        for v in o: _all_keys(v, acc)
    return acc


def test_whitelist_und_keine_internen_felder():
    pub = dp.build_dce_public(_real_dce(), "2026-09-30", "2026-09-30T22:00:00Z")
    assert set(pub) == dp.PUBLIC_KEYS
    leaked = _all_keys(pub) & set(INTERNAL_FIELDS)
    assert not leaked, leaked


def test_cusum_var_immer_nv():
    for d in (_real_dce(), None, {}, _aggregator_fallback()):
        pub = dp.build_dce_public(d)
        assert pub["cusum"] == {"status": "n/v", "reason": dp.REASON_CUSUM}
        assert pub["var"] == {"status": "n/v", "reason": dp.REASON_VAR}


def test_signalbreite_ok_und_werte():
    sb = dp.build_dce_public(_real_dce())["signal_breadth"]
    assert sb["status"] == "ok" and sb["n"] == 738 and sb["share_pct"] == 18.3 and sb["threshold"] == 55
    assert "kauf" in sb["definition"].lower() and "wahrscheinlichkeit" in sb["definition"].lower()


def test_signalbreite_nv_faelle():
    base = _real_dce()
    cases = {"None": None, "leer": {}, "fallback": {**base, "fallback": True},
             "agg fehlt": {k: v for k, v in base.items() if k != "aggregated"},
             "agg leer": {**base, "aggregated": {}}, "n=0": {**base, "aggregated": {"n": 0, "bullish_pct": 0.5}},
             "n bool": {**base, "aggregated": {"n": True, "bullish_pct": 0.5}},
             "bull None": {**base, "aggregated": {"n": 10, "bullish_pct": None}},
             "bull >1": {**base, "aggregated": {"n": 10, "bullish_pct": 1.5}},
             "bull str": {**base, "aggregated": {"n": 10, "bullish_pct": "x"}}}
    for name, d in cases.items():
        sb = dp.build_dce_public(d)["signal_breadth"]
        assert sb["status"] == "n/v" and sb.get("reason"), name
        assert "share_pct" not in sb, name


def test_fallback_nie_als_signal():
    eng = DecisionConfidenceEngine(config={}, cusum_buffer=[])
    fb = eng._fallback("boom")
    assert fb.get("fallback") is True
    for d in (fb, _aggregator_fallback()):
        assert dp.build_dce_public(d)["signal_breadth"]["status"] == "n/v"
        pub = dp.split_public_master({"meta": {}, "dce": d})
        assert pub["dce_public"]["signal_breadth"]["status"] == "n/v"
        assert "dce" not in pub


def test_split_public_master():
    m = _master(); before = copy.deepcopy(m)
    pub = dp.split_public_master(m)
    assert m == before, "Original darf nicht veraendert werden"
    assert "dce" not in pub and "dce_cusum_buffer" not in pub["meta"]
    assert pub["dce_public"]["as_of"] == "2026-09-30" and pub["dce_public"]["generated"] == "2026-09-30T22:00:00Z"
    assert {k: v for k, v in pub.items() if k != "dce_public"} == \
        {k: (v if k != "meta" else {a: b for a, b in v.items() if a != "dce_cusum_buffer"})
         for k, v in m.items() if k != "dce"}
    txt = json.dumps(pub)
    assert "position_size" not in txt and "Testwarnung" not in txt and '"SELL"' not in txt


def test_split_ohne_dce_und_ohne_meta():
    pub = dp.split_public_master({"tickers": []})
    assert "dce" not in pub and pub["dce_public"]["signal_breadth"]["status"] == "n/v"
    assert pub["dce_public"]["as_of"] is None


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("OK  ", name)
            except Exception as e:
                fails += 1; print("FAIL", name, repr(e))
    sys.exit(1 if fails else 0)
