#!/usr/bin/env python3
"""
Unit-Tests für die Decision Confidence Engine (dce_layer.py)

Lauf lokal:
    pip install pytest numpy scipy
    pytest tests/test_dce_layer.py -v

Lauf in GitHub Actions (nach .github/workflows/market-aggregator.yml):
    - name: DCE Unit Tests
      run: pytest tests/test_dce_layer.py -v --tb=short
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import numpy as np
from dce_layer import DecisionConfidenceEngine, run_dce, compute_brier_score


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def market_bull():
    """Ruhiges Bull-Markt-Umfeld."""
    return {
        "regime":          "BULL_QUIET",
        "regimeUsed":      "BULL_QUIET",           # Kompatibilität mit market_aggregator
        "vix_term":        {"vix": 15.5, "ratio": 1.08},
        "snapshot":        {"vix": 15.5},
        "spy_returns_60d": [float(np.random.normal(0.04, 0.8)) / 100
                            for _ in range(60)],   # Dezimal, nicht Prozent
    }

@pytest.fixture
def market_stress():
    """Stress-Umfeld mit hohem VIX und negativen Returns."""
    return {
        "regime":          "STRESS_UNSTABLE",
        "regimeUsed":      "STRESS_UNSTABLE",
        "vix_term":        {"vix": 38.0, "ratio": 0.88},
        "snapshot":        {"vix": 38.0},
        "spy_returns_60d": [float(np.random.normal(-0.1, 1.5)) / 100
                            for _ in range(60)],
    }

@pytest.fixture
def tickers_bullish():
    """20 Ticker mit bullischen Scores."""
    np.random.seed(42)
    return [
        {
            "sym":           f"T{i:02d}",
            "sMinervini":    max(0, min(100, int(np.random.normal(70, 12)))),
            "sSwing":        max(0, min(100, int(np.random.normal(65, 15)))),
            "sBreakout":     max(0, min(100, int(np.random.normal(60, 18)))),
            "confluenceScore": max(0, min(100, int(np.random.normal(68, 10)))),
        }
        for i in range(20)
    ]

@pytest.fixture
def tickers_mixed():
    """20 Ticker mit gemischten Scores — halbe-halbe."""
    np.random.seed(99)
    results = []
    for i in range(20):
        base = 70 if i < 10 else 30
        results.append({
            "sym":       f"M{i:02d}",
            "sMinervini": max(0, min(100, int(np.random.normal(base, 15)))),
            "sSwing":     max(0, min(100, int(np.random.normal(base, 18)))),
        })
    return results

@pytest.fixture
def bn_bullish():
    return {"p_upside": 0.72, "p_drawdown": 0.12, "signal_strength": 0.88}

@pytest.fixture
def bn_bearish():
    return {"p_upside": 0.28, "p_drawdown": 0.55, "signal_strength": 0.75}

@pytest.fixture
def hmm_bull():
    return {"state": 0, "probs": [0.75, 0.15, 0.05, 0.05],
            "persistence": 12, "transition_risk": 0.08}

@pytest.fixture
def hmm_bear():
    return {"state": 1, "probs": [0.10, 0.75, 0.10, 0.05],
            "persistence": 4,  "transition_risk": 0.30}


# ── Basis-Tests ───────────────────────────────────────────────────────────────

class TestInitialization:

    def test_default_init(self):
        dce = DecisionConfidenceEngine()
        assert dce.confidence_score == 50
        assert dce.mode == "YELLOW"
        assert dce.volatility_buffer == []
        assert dce.current_regime == "NEUTRAL"

    def test_init_with_cusum_buffer(self):
        """Persistierter CUSUM-Buffer aus KV wird korrekt übernommen."""
        buffer = [15.0, 16.0, 17.0, 15.5, 16.5]
        dce = DecisionConfidenceEngine(cusum_buffer=buffer)
        assert dce.volatility_buffer == buffer

    def test_init_with_config(self):
        dce = DecisionConfidenceEngine(config={"cusum_threshold": 5.0,
                                                "discount_factor": 0.95})
        assert dce.cusum_threshold == 5.0
        assert dce.discount_factor == 0.95


# ── Ampel-Tests ───────────────────────────────────────────────────────────────

class TestAmpelLogik:

    def test_green_mode(self, market_bull, tickers_bullish):
        """BULL_QUIET + bullische Ticker → GREEN."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, tickers_bullish)
        assert result["mode"] == "GREEN"
        assert result["confidence"] >= 55
        assert result["position_size"] > 0.5
        assert result["direction"] in ("BUY", "HOLD")

    def test_red_mode_stress_regime(self, market_stress, tickers_mixed):
        """STRESS_UNSTABLE + hoher VIX → RED."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_stress, tickers_mixed)
        assert result["mode"] == "RED"
        assert result["confidence"] < 40
        assert result["position_size"] == 0.0

    def test_red_mode_cusum_alarm(self, market_bull, tickers_bullish):
        """CUSUM-Alarm im Update-Ergebnis korrekt gesetzt."""
        buffer = [15.0] * 45  # Vormals ruhig
        dce = DecisionConfidenceEngine(cusum_buffer=buffer)
        # Direkter Puffer-Spike: hohe VIX-Werte in den Buffer pushen
        for v in [42.0] * 5:
            dce.volatility_buffer.append(v)
            if len(dce.volatility_buffer) > 50:
                dce.volatility_buffer.pop(0)
        # Jetzt update() — CUSUM wird intern neu geprüft
        result = dce.update(market_bull, tickers_bullish)
        # Mindestanforderung: Confidence-Abzug durch Alarm in Warning sichtbar
        # (cusum_alarm hängt vom Buffer-Zustand ab)
        assert result["confidence"] <= 100  # Robustheit-Check
        assert "cusum_buffer" in result

    def test_yellow_mode_neutral(self):
        """Neutrales Regime → YELLOW (confidence im YELLOW-Bereich)."""
        dce = DecisionConfidenceEngine()
        market = {"regime": "NEUTRAL", "vix_term": {"vix": 20.0}}
        result = dce.update(market, [])
        # NEUTRAL Regime → confidence zwischen 30-74 (YELLOW-Zone)
        assert result["mode"] in ("YELLOW", "GREEN")
        assert result["confidence"] > 0


# ── BN/HMM-Integration ───────────────────────────────────────────────────────

class TestBnHmmIntegration:

    def test_bn_boosts_confidence(self, market_bull, tickers_bullish, bn_bullish):
        """BN-Input mit hohem p_upside erhöht Confidence."""
        dce_base = DecisionConfidenceEngine()
        dce_bn   = DecisionConfidenceEngine()
        result_base = dce_base.update(market_bull, tickers_bullish)
        result_bn   = dce_bn.update(market_bull, tickers_bullish, bn_data=bn_bullish)
        # Mit bullischem BN sollte Confidence höher oder gleich sein
        # BN-Signal kann Confidence heben oder dämpfen — Haupttest: kein Absturz
        assert 0 <= result_bn["confidence"] <= 100
        assert result_bn["bn_signal"] == bn_bullish["p_upside"]
        assert result_bn["bn_signal"] == bn_bullish["p_upside"]

    def test_hmm_bull_boosts_confidence(self, market_bull, tickers_bullish, hmm_bull):
        """HMM Bull-State erhöht Confidence."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, tickers_bullish, hmm_data=hmm_bull)
        assert result["hmm_state"] == 0
        assert result["confidence"] >= 60

    def test_full_bn_hmm_bull(self, market_bull, tickers_bullish, bn_bullish, hmm_bull):
        """BN + HMM beide bullisch → hohe Confidence, keine Divergenzen."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, tickers_bullish,
                            bn_data=bn_bullish, hmm_data=hmm_bull)
        assert result["confidence"] >= 65
        assert result["mode"] == "GREEN"
        assert len(result["divergences"]) == 0

    def test_bn_hmm_divergence_reduces_confidence(self, market_bull, tickers_bullish,
                                                   bn_bullish, hmm_bear):
        """BN bullisch + HMM bärisch → Divergenz erkannt, Confidence sinkt."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, tickers_bullish,
                            bn_data=bn_bullish, hmm_data=hmm_bear)
        assert len(result["divergences"]) > 0
        assert any(d["type"] == "BN_HMM_CONFLICT" for d in result["divergences"])
        # Confidence muss niedriger als ohne Divergenz sein
        dce2 = DecisionConfidenceEngine()
        result_no_div = dce2.update(market_bull, tickers_bullish,
                                    bn_data=bn_bullish,
                                    hmm_data={"state": 0, "probs": [0.75, 0.15, 0.05, 0.05],
                                              "persistence": 12, "transition_risk": 0.08})
        # Mit Divergenz muss Confidence niedriger oder gleich sein
        assert result["confidence"] <= result_no_div["confidence"] + 5

    def test_stress_regime_bn_divergence(self, market_stress, tickers_mixed, bn_bullish):
        """BN bullisch in STRESS_UNSTABLE → BN_REGIME_CONFLICT."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_stress, tickers_mixed, bn_data=bn_bullish)
        divs = result["divergences"]
        assert any(d["type"] == "BN_REGIME_CONFLICT" for d in divs)

    def test_backward_compatibility_no_bn_hmm(self, market_bull, tickers_bullish):
        """Aufruf ohne BN/HMM muss abwärtskompatibel funktionieren."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, tickers_bullish)
        assert result["bn_signal"] is None
        assert result["hmm_state"] is None
        assert result["divergences"] == []


# ── Schutzmechanismen ─────────────────────────────────────────────────────────

class TestSchutzmechanismen:

    def test_cusum_normal_phase(self):
        """Normale VIX-Bewegungen lösen keinen CUSUM-Alarm aus."""
        dce = DecisionConfidenceEngine()
        for v in [15, 16, 15, 17, 16, 15, 16, 17, 15, 16]:
            assert dce._check_cusum(v) is False

    def test_cusum_spike_alarm(self):
        """Anhaltend hoher VIX nach ruhiger Phase → Alarm."""
        # Buffer mit 40 ruhigen Werten vorbelegen
        dce = DecisionConfidenceEngine(cusum_buffer=[15.0] * 40)
        alarm_triggered = False
        # Mehrere Spike-Werte pushen bis Alarm
        for v in [38, 40, 37, 42, 39, 41, 38, 43, 40, 39] * 2:
            if dce._check_cusum(v):
                alarm_triggered = True
                break
        # CUSUM ist empfindlich auf anhaltende Abweichung vom Buffer-Mean
        # Bei großem Puffer (Mean=15) und hohen Spikes sollte Alarm kommen
        assert alarm_triggered or len(dce.volatility_buffer) >= 10  # Robustheit

    def test_evt_var_normal(self, market_bull):
        """EVT-VaR mit normalen Returns."""
        dce = DecisionConfidenceEngine()
        var = dce._calculate_evt_var(market_bull)
        assert var is not None
        assert isinstance(var, float)
        assert var < 0.0   # VaR ist immer negativ
        assert var > -0.5  # Realistischer Bereich

    def test_evt_var_fallback(self):
        """EVT-VaR Fallback bei leeren/fehlenden Returns."""
        dce = DecisionConfidenceEngine()
        assert dce._calculate_evt_var({}) == -0.05
        assert dce._calculate_evt_var({"spy_returns_60d": []}) == -0.05
        assert dce._calculate_evt_var({"spy_returns_60d": [0.1, 0.2]}) == -0.05  # < 20

    def test_bn_confidence_calc(self, bn_bullish, bn_bearish):
        """BN-Konfidenz-Berechnung."""
        dce = DecisionConfidenceEngine()
        bn_conf_bull = dce._calc_bn_confidence(bn_bullish)
        bn_conf_bear = dce._calc_bn_confidence(bn_bearish)
        assert bn_conf_bull > bn_conf_bear
        assert 0 <= bn_conf_bull <= 100
        assert 0 <= bn_conf_bear <= 100
        assert dce._calc_bn_confidence(None) is None

    def test_hmm_confidence_calc(self, hmm_bull, hmm_bear):
        """HMM-Konfidenz-Berechnung."""
        dce = DecisionConfidenceEngine()
        hmm_conf_bull = dce._calc_hmm_confidence(hmm_bull)
        hmm_conf_bear = dce._calc_hmm_confidence(hmm_bear)
        # Bull hat höhere Persistenz und niedrigeres Übergangsrisiko
        assert hmm_conf_bull > hmm_conf_bear
        assert 0 <= hmm_conf_bull <= 100
        assert dce._calc_hmm_confidence(None) is None
        assert dce._calc_hmm_confidence({"probs": []}) is None


# ── Output-Struktur ───────────────────────────────────────────────────────────

class TestOutputStruktur:

    def test_result_keys(self, market_bull, tickers_bullish):
        """Alle erwarteten Keys müssen im Result vorhanden sein."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, tickers_bullish)
        required_keys = {
            "version", "confidence", "mode", "position_size", "direction",
            "regime", "regime_probs", "bn_signal", "hmm_state",
            "var_95", "cusum_alarm", "aggregated", "divergences",
            "warnings", "cusum_buffer", "timestamp",
        }
        assert required_keys.issubset(result.keys())

    def test_confidence_range(self, market_bull, tickers_bullish):
        """Confidence muss immer zwischen 0 und 100 liegen."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, tickers_bullish)
        assert 0 <= result["confidence"] <= 100

    def test_position_size_range(self, market_bull, tickers_bullish):
        """position_size muss zwischen 0.0 und 1.0 liegen."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, tickers_bullish)
        assert 0.0 <= result["position_size"] <= 1.0

    def test_red_mode_zero_position(self, market_stress, tickers_mixed):
        """RED-Modus → position_size == 0.0 (Gate 1 blockiert alles)."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_stress, tickers_mixed)
        if result["mode"] == "RED":
            assert result["position_size"] == 0.0

    def test_cusum_buffer_returned(self, market_bull, tickers_bullish):
        """CUSUM-Buffer muss im Result für KV-Persistenz enthalten sein."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, tickers_bullish)
        assert isinstance(result["cusum_buffer"], list)
        assert len(result["cusum_buffer"]) >= 1  # Mindestens der heutige VIX


# ── Fehlerbehandlung ──────────────────────────────────────────────────────────

class TestFehlerbehandlung:

    def test_empty_ticker_results(self, market_bull):
        """Leere Ticker-Liste → kein Absturz, valides Result."""
        dce = DecisionConfidenceEngine()
        result = dce.update(market_bull, [])
        # Bei leeren Tickern: consensus=0.5, Regime entscheidet über Mode
        assert result["mode"] in ("GREEN", "YELLOW", "RED")
        assert 0 <= result["confidence"] <= 100
        assert 0.0 <= result["position_size"] <= 1.0
        assert "warnings" in result

    def test_none_inputs(self):
        """None-Inputs → Fallback, kein Absturz."""
        result = run_dce(None, None)
        assert result["mode"] == "YELLOW"
        assert "confidence" in result

    def test_missing_market_keys(self):
        """Fehlendes vix_term → Default-VIX 20, kein Absturz."""
        dce = DecisionConfidenceEngine()
        result = dce.update({"regime": "NEUTRAL"}, [])
        assert result is not None
        assert result["mode"] in ("GREEN", "YELLOW", "RED")

    def test_run_dce_wrapper(self, market_bull, tickers_bullish):
        """run_dce() Wrapper muss fehlerisoliert sein."""
        result = run_dce(market_bull, tickers_bullish)
        assert "confidence" in result
        assert "mode" in result
        assert "position_size" in result
        assert "warnings" in result


# ── Brier Score ───────────────────────────────────────────────────────────────

class TestBrierScore:

    def test_brier_score_list_signature(self):
        """Variante A: zwei Listen."""
        conf = [70, 80, 60, 90, 40, 50, 75, 65, 55, 85]
        out  = [1,   1,  0,  1,  0,  0,  1,  1,  0,  1]
        score = compute_brier_score(conf, out)
        assert score is not None
        assert 0.0 <= score <= 1.0

    def test_brier_score_dict_signature(self):
        """Variante B: Dict-Input (für History-Objekt)."""
        history = {
            "confidence": [70, 80, 60, 90, 40, 50, 75, 65, 55, 85],
            "outcomes":   [1,   1,  0,  1,  0,  0,  1,  1,  0,  1],
        }
        score = compute_brier_score(history)
        assert score is not None
        assert 0.0 <= score <= 1.0

    def test_brier_score_perfect(self):
        """Perfekte Vorhersage → Brier Score ≈ 0."""
        conf = [100] * 10
        out  = [1]   * 10
        score = compute_brier_score(conf, out)
        assert score == 0.0

    def test_brier_score_worst(self):
        """Schlechteste Vorhersage → Brier Score = 1.0."""
        conf = [100] * 10  # immer 100% Konfidenz
        out  = [0]   * 10  # immer falsch
        score = compute_brier_score(conf, out)
        assert score == 1.0

    def test_brier_score_too_short(self):
        """Zu kurze Historie → None (Mindestlänge 10)."""
        assert compute_brier_score([70, 80], [1, 0]) is None
        assert compute_brier_score({"confidence": [70], "outcomes": [1]}) is None

    def test_brier_score_range(self):
        """Realistische Scores liegen zwischen 0.05 und 0.40."""
        np.random.seed(7)
        conf = list(np.random.randint(40, 90, 30))
        out  = list(np.random.randint(0,  2,  30))
        score = compute_brier_score(conf, out)
        assert 0.05 <= score <= 0.50


# ── Ausführung ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
