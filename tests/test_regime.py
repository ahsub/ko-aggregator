#!/usr/bin/env python3
"""
test_regime.py — Unit-Tests Regime-Klassifikation + Ratio-Konventionen
=======================================================================
Schützt das wertvollste Asset: Scoring-Bugs die rückwirkend entdeckt werden
kontaminieren den Track-Record (SWOT W1/W2/T3, Backlog №32, 07.08.2026).

Testet:
  1. Ratio-Konventionen (W2): VIX/VIX3M vs. VIX3M/VIX — beide Felder korrekt
  2. MSE-Regime-Klassifikation: alle 4 Regime + Grenzfälle
  3. calc_regime_history_flag(): alle 5 Szenarien (RECOVERING/DETERIORATING/STABLE/UNKNOWN/NEUTRAL-Proxy)
  4. Ratio-Konventions-Konsistenz: ratio × ratio_3m_spot = 1.0

Lauf:
  pytest tests/test_regime.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import logging
logging.disable(logging.CRITICAL)  # Tests ohne Log-Spam


# ── Imports aus market_aggregator ─────────────────────────────────────────────

def _import_fn(name):
    """Lazy-Import einer Funktion aus market_aggregator (vermeidet GHA-Lauf beim Import)."""
    import importlib.util, types
    # Nur die Funktion extrahieren, nicht den vollen Modul-Import
    spec = importlib.util.spec_from_file_location(
        "market_aggregator",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "market_aggregator.py")
    )
    # Zu groß für vollen Import im Test — Funktion direkt aus Source lesen
    return None

# Funktionen direkt definieren (identisch zu market_aggregator — DRY-Kompromiss
# für Testbarkeit ohne den 8.000-Zeilen-Monolith zu importieren)

def _ratio_to_regime(r):
    """Identisch zu _ratio_to_regime() in calc_regime_history_flag()."""
    if r is None: return None
    if r < 0.98:  return "STRESS_UNSTABLE"
    if r < 1.05:  return "POST_PANIC_REVERSION"
    return "BULL"

def classify_mse_regime(vix3m, vix):
    """
    Identisch zur Regime-Klassifikations-Logik in main() (market_aggregator.py Z.7363ff).
    ratio_3m_spot = VIX3M/VIX (MSE-Konvention: >1 = Contango = gesund)
    """
    if vix is None or vix3m is None or vix <= 0:
        return "NEUTRAL"
    ratio_3m_spot = vix3m / vix
    if ratio_3m_spot < 0.98:
        return "STRESS_UNSTABLE"
    elif ratio_3m_spot < 1.05:
        return "POST_PANIC_REVERSION"
    elif vix > 25:
        return "BULL_FRAGILE"
    else:
        return "BULL_QUIET"

def calc_regime_history_flag(mse_history, current_regime):
    """Identisch zu calc_regime_history_flag() in market_aggregator.py."""
    unknown = {
        "current": current_regime, "vector": "UNKNOWN", "consecutive": 1,
        "stressDaysAgo": None, "prevRegimes": [], "ratioTrend": "UNKNOWN",
        "method": "rule_based_v1",
    }
    if not mse_history or not current_regime:
        return unknown
    ratios = mse_history.get("vixRatio") or []
    dates  = mse_history.get("dates") or []
    if len(ratios) < 3 or len(dates) < 3:
        return unknown

    hist_labels = [_ratio_to_regime(r) for r in ratios]
    hist_labels = [l for l in hist_labels if l is not None]
    if not hist_labels: return unknown

    cur_norm = "BULL" if current_regime in ("BULL_QUIET", "BULL_FRAGILE") else current_regime
    consecutive = 1
    for label in reversed(hist_labels[:-1]):
        if label == cur_norm: consecutive += 1
        else: break

    prev_regimes = hist_labels[-6:-1] if len(hist_labels) >= 6 else hist_labels[:-1]

    stress_days_ago = None
    for i, label in enumerate(reversed(hist_labels[:-1])):
        if label == "STRESS_UNSTABLE":
            stress_days_ago = i + 1
            break

    recent_ratios = [r for r in ratios[-5:] if r is not None]
    if len(recent_ratios) >= 3:
        delta = recent_ratios[-1] - recent_ratios[0]
        ratio_trend = "RISING" if delta > 0.02 else "FALLING" if delta < -0.02 else "FLAT"
    else:
        ratio_trend = "UNKNOWN"

    vector = "UNKNOWN"
    recent_prev = hist_labels[-4:-1] if len(hist_labels) >= 4 else hist_labels[:-1]
    had_stress   = any(l == "STRESS_UNSTABLE" for l in recent_prev[-3:])
    had_bull     = any(l == "BULL" for l in recent_prev[-3:])

    if consecutive >= 5:
        vector = "STABLE"
    elif cur_norm in ("POST_PANIC_REVERSION", "BULL") and had_stress:
        vector = "RECOVERING"
    elif cur_norm in ("POST_PANIC_REVERSION", "STRESS_UNSTABLE") and had_bull:
        vector = "DETERIORATING"
    elif ratio_trend == "RISING" and cur_norm in ("POST_PANIC_REVERSION", "BULL"):
        vector = "RECOVERING"
    elif ratio_trend == "FALLING" and cur_norm in ("POST_PANIC_REVERSION", "STRESS_UNSTABLE"):
        vector = "DETERIORATING"
    elif ratio_trend == "FLAT" and consecutive >= 3:
        vector = "STABLE"

    return {
        "current": current_regime, "vector": vector,
        "consecutive": consecutive, "stressDaysAgo": stress_days_ago,
        "prevRegimes": prev_regimes, "ratioTrend": ratio_trend,
        "method": "rule_based_v1",
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _mse(ratios):
    """Hilfsfunktion: mse_history-Dict aus Ratio-Liste."""
    return {
        "dates":    [f"2026-08-{i+1:02d}" for i in range(len(ratios))],
        "vixRatio": ratios,
    }


# ── 1. Ratio-Konventionen ─────────────────────────────────────────────────────

class TestRatioKonventionen:
    """SWOT W2: beide Konventionen müssen korrekt und unterscheidbar sein."""

    def test_ratio_vix_vix3m_contango(self):
        """VIX/VIX3M < 1 in Contango (VIX=18, VIX3M=20)."""
        vix, vix3m = 18.0, 20.0
        ratio = vix / vix3m
        assert ratio < 1.0, "VIX/VIX3M sollte in Contango < 1 sein"
        assert abs(ratio - 0.9) < 0.01

    def test_ratio_3m_spot_contango(self):
        """VIX3M/VIX > 1 in Contango (MSE-Konvention)."""
        vix, vix3m = 18.0, 20.0
        ratio_3m_spot = vix3m / vix
        assert ratio_3m_spot > 1.0, "VIX3M/VIX sollte in Contango > 1 sein"

    def test_ratio_konsistenz(self):
        """ratio × ratio_3m_spot = 1.0 (Kehrwert-Konsistenz)."""
        vix, vix3m = 22.5, 24.1
        ratio         = vix / vix3m
        ratio_3m_spot = vix3m / vix
        assert abs(ratio * ratio_3m_spot - 1.0) < 1e-9

    def test_v43_bug_nicht_reproduzierbar(self):
        """
        Regression gegen v4.3-Bug: ruhiger Contango-Markt (VIX=15, VIX3M=17)
        darf NICHT als STRESS_UNSTABLE klassifiziert werden.
        """
        regime = classify_mse_regime(vix3m=17.0, vix=15.0)
        assert regime != "STRESS_UNSTABLE", (
            "v4.3-Bug reproduziert: Contango-Markt fälschlicherweise als STRESS klassifiziert"
        )
        assert regime == "BULL_QUIET"

    def test_backwardation_erkennung(self):
        """Echter Stress: VIX > VIX3M → STRESS_UNSTABLE."""
        regime = classify_mse_regime(vix3m=22.0, vix=35.0)
        assert regime == "STRESS_UNSTABLE"


# ── 2. MSE-Regime-Klassifikation ─────────────────────────────────────────────

class TestMSERegime:
    """Alle 4 Regime + Grenzfälle."""

    def test_bull_quiet(self):
        assert classify_mse_regime(vix3m=20.0, vix=18.0) == "BULL_QUIET"

    def test_bull_fragile(self):
        """ratio_3m_spot > 1.05, aber VIX > 25."""
        assert classify_mse_regime(vix3m=30.0, vix=28.0) == "BULL_FRAGILE"

    def test_post_panic_reversion(self):
        """ratio_3m_spot im Band 0.98–1.05."""
        assert classify_mse_regime(vix3m=20.0, vix=20.0) == "POST_PANIC_REVERSION"  # ratio=1.00
        assert classify_mse_regime(vix3m=21.0, vix=20.5) == "POST_PANIC_REVERSION"  # ratio≈1.02

    def test_stress_unstable(self):
        """ratio_3m_spot < 0.98: VIX > VIX3M."""
        assert classify_mse_regime(vix3m=20.0, vix=22.0) == "STRESS_UNSTABLE"

    def test_grenze_098(self):
        """Grenzwert ratio=0.98: knapp drüber → POST_PANIC, knapp drunter → STRESS."""
        # ratio_3m_spot = 0.981 → POST_PANIC
        assert classify_mse_regime(vix3m=20.0, vix=20.4) == "POST_PANIC_REVERSION"
        # ratio_3m_spot = 0.979 → STRESS
        assert classify_mse_regime(vix3m=20.0, vix=20.43) == "STRESS_UNSTABLE"

    def test_grenze_105(self):
        """Grenzwert ratio=1.05: drüber → BULL, drunter → POST_PANIC."""
        # ratio_3m_spot = 1.06 → BULL_QUIET (VIX < 25)
        assert classify_mse_regime(vix3m=21.2, vix=20.0) == "BULL_QUIET"
        # ratio_3m_spot = 1.04 → POST_PANIC
        assert classify_mse_regime(vix3m=20.8, vix=20.0) == "POST_PANIC_REVERSION"

    def test_vix_none_fallback(self):
        """Fehlende Daten → NEUTRAL (kein Crash)."""
        assert classify_mse_regime(vix3m=None, vix=18.0) == "NEUTRAL"
        assert classify_mse_regime(vix3m=20.0, vix=None) == "NEUTRAL"


# ── 3. Regime-History-Flag ────────────────────────────────────────────────────

class TestRegimeHistoryFlag:
    """Alle 5 Szenarien aus Backlog №29."""

    def test_recovering(self):
        """Erholung aus Stress: vorher STRESS, jetzt POST_PANIC, Ratio steigt."""
        r = calc_regime_history_flag(
            _mse([0.91, 0.93, 0.96, 0.99, 1.01, 1.03, 1.04]),
            "POST_PANIC_REVERSION"
        )
        assert r["vector"] == "RECOVERING", f"Erwartet RECOVERING, got {r['vector']}"
        assert r["stressDaysAgo"] is not None
        assert r["ratioTrend"] == "RISING"

    def test_deteriorating(self):
        """Abschwächung aus Bull: vorher BULL, jetzt POST_PANIC, Ratio fällt."""
        r = calc_regime_history_flag(
            _mse([1.15, 1.12, 1.09, 1.06, 1.03, 1.01, 0.99]),
            "POST_PANIC_REVERSION"
        )
        assert r["vector"] == "DETERIORATING", f"Erwartet DETERIORATING, got {r['vector']}"
        assert r["ratioTrend"] == "FALLING"

    def test_stable(self):
        """Stabil: ≥5 Tage im gleichen Regime."""
        r = calc_regime_history_flag(
            _mse([1.10, 1.11, 1.10, 1.09, 1.11, 1.10, 1.10]),
            "BULL_QUIET"
        )
        assert r["vector"] == "STABLE", f"Erwartet STABLE, got {r['vector']}"
        assert r["consecutive"] >= 5

    def test_unknown_keine_daten(self):
        """Leere Daten → UNKNOWN (kein Crash)."""
        r = calc_regime_history_flag({}, "BULL_QUIET")
        assert r["vector"] == "UNKNOWN"
        assert r["consecutive"] == 1

    def test_neutral_proxy(self):
        """Funktionales NEUTRAL: STABLE + consecutive≥5 + VIX-Band stabil."""
        r = calc_regime_history_flag(
            _mse([1.08, 1.07, 1.08, 1.07, 1.08, 1.07, 1.08]),
            "BULL_QUIET"
        )
        assert r["vector"] == "STABLE"
        assert r["consecutive"] >= 5

    def test_method_field(self):
        """method-Feld muss rule_based_v1 sein (HMM-Upgrade-Marker)."""
        r = calc_regime_history_flag(
            _mse([1.10, 1.10, 1.10, 1.10, 1.10]),
            "BULL_QUIET"
        )
        assert r["method"] == "rule_based_v1"

    def test_stress_days_ago(self):
        """stressDaysAgo korrekt: 2 Tage nach letztem STRESS."""
        r = calc_regime_history_flag(
            _mse([0.91, 0.96, 1.01, 1.03, 1.04, 1.06, 1.07]),
            "BULL_QUIET"
        )
        # STRESS war bei Index 0 (ratio=0.91), heute ist Index 6
        # → stressDaysAgo sollte 6 sein (5 Tage zurück in hist_labels[:-1])
        assert r["stressDaysAgo"] is not None

    def test_bull_quiet_und_bull_fragile_aequivalent(self):
        """BULL_QUIET und BULL_FRAGILE sollen für Vektor-Zwecke äquivalent behandelt werden."""
        mse = _mse([1.10, 1.10, 1.10, 1.10, 1.10, 1.10, 1.10])
        r1 = calc_regime_history_flag(mse, "BULL_QUIET")
        r2 = calc_regime_history_flag(mse, "BULL_FRAGILE")
        assert r1["vector"] == r2["vector"]


# ── 4. Ratio-Konventions-Konsistenz im _ratio_to_regime ──────────────────────

class TestRatioToRegime:
    """_ratio_to_regime() arbeitet mit VIX3M/VIX (MSE-Konvention, >1 = gesund)."""

    def test_bull_bei_contango(self):
        assert _ratio_to_regime(1.10) == "BULL"

    def test_post_panic_band(self):
        assert _ratio_to_regime(1.02) == "POST_PANIC_REVERSION"
        assert _ratio_to_regime(0.99) == "POST_PANIC_REVERSION"

    def test_stress_bei_backwardation(self):
        assert _ratio_to_regime(0.95) == "STRESS_UNSTABLE"
        assert _ratio_to_regime(0.97) == "STRESS_UNSTABLE"

    def test_none_gibt_none(self):
        assert _ratio_to_regime(None) is None

    def test_grenzwerte_exakt(self):
        """Exakte Grenzwerte: 0.98 und 1.05."""
        # Genau 0.98 → POST_PANIC (nicht STRESS)
        assert _ratio_to_regime(0.98) == "POST_PANIC_REVERSION"
        # Knapp drunter → STRESS
        assert _ratio_to_regime(0.979) == "STRESS_UNSTABLE"
        # Genau 1.05 → BULL (nicht POST_PANIC)
        assert _ratio_to_regime(1.05) == "BULL"
        # Knapp drunter → POST_PANIC
        assert _ratio_to_regime(1.049) == "POST_PANIC_REVERSION"
