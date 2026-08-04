#!/usr/bin/env python3
"""
dce_layer.py — Decision Confidence Engine (DCE) für UIQ Suite
Version: 1.0
Datum: August 2026

Aufgabe: Fusioniert alle heterogenen Signale (MCM-Makro, Ticker-Konsens,
CUSUM, EVT-VaR) zu einem kalibrierten Vertrauensmaß (confidence_score 0-100)
und einer operativen Ampel (GREEN/YELLOW/RED).

Architektur (aus ML_KONZEPT.md §4b):
  Research Layer  → Validated Model → Production Layer (diese Datei)
  Kein Notebook-Output geht direkt in Produktionsparameter.

Phase-Integration (Platzhalter bis Phasen implementiert):
  Phase 1 (BN,  Sept. 2026): _get_bn_signal()  → P(Kursteigerung)
  Phase 2 (HMM, Okt.  2026): _get_hmm_state() → P(Regime_0..3)
  Phase 3 (NN,  Q1    2027): _get_nn_signal()  → Transition-Timing

Fehlerisolierung: Ein Fehler in der DCE bricht den Hauptlauf NICHT ab.
Fallback: confidence=50, mode=YELLOW (konservative neutrale Haltung).

CUSUM-Persistenz: Der volatility_buffer wird als JSON in KV gespeichert
(Schlüssel: 'dce:cusum_buffer') damit er GHA-Run-übergreifend erhalten bleibt.
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

log = logging.getLogger("aggregator.dce")


# ── Konstanten ────────────────────────────────────────────────────────────────

DCE_VERSION = "1.0"

# Regime-Mapping: UIQ-Regime-Labels → DCE-Konfidenz-Prior
REGIME_CONFIDENCE = {
    "BULL_QUIET":           80,
    "BULL_FRAGILE":         60,
    "NEUTRAL":              50,
    "POST_PANIC_REVERSION": 35,
    "STRESS_UNSTABLE":      20,
}

# Regime-Dämpfungsfaktoren
REGIME_DAMPENING = {
    "STRESS_UNSTABLE":      0.60,
    "POST_PANIC_REVERSION": 0.75,
}


# ── Haupt-Klasse ──────────────────────────────────────────────────────────────

class DecisionConfidenceEngine:
    """
    Die zentrale Schaltzentrale der UIQ-Suite.
    Implementiert die Meta-Intelligenz über allen Signalquellen.

    Verwendung:
        dce = DecisionConfidenceEngine(config={}, cusum_buffer=[])
        result = dce.update(market_data, ticker_results)
        # result["confidence"], result["mode"], result["warnings"] etc.
    """

    def __init__(self, config: Optional[Dict] = None,
                 cusum_buffer: Optional[List[float]] = None):
        self.config = config or {}
        self.confidence_score = 50      # 0-100, Start neutral
        self.mode = "YELLOW"            # GREEN / YELLOW / RED
        self.current_regime = "NEUTRAL"
        self.regime_probabilities: Dict = {}
        self.cusum_alarm = False

        # Sekerke-Discounting: ältere Daten werden abgewertet
        self.discount_factor  = self.config.get("discount_factor",  0.98)
        self.cusum_threshold  = self.config.get("cusum_threshold",  3.0)

        # CUSUM-Buffer persistiert über GHA-Runs (via KV)
        self.volatility_buffer: List[float] = cusum_buffer or []
        self.var_95 = 0.0

        # Phasen-Modelle (Platzhalter bis Phasen implementiert)
        self.bn_model  = None   # Phase 1: PyMC BN (Sept. 2026)
        self.hmm_model = None   # Phase 2: hmmlearn HMM (Okt. 2026)
        self.nn_model  = None   # Phase 3: LSTM (Q1 2027, Go/No-Go)

    def update(self, market_data: Dict, ticker_results: List[Dict],
               bn_data: Optional[Dict] = None,
               hmm_data: Optional[Dict] = None) -> Dict:
        """
        Täglicher Update-Cycle der DCE mit optionaler BN/HMM-Integration.

        Args:
            market_data:    Makro-Kontext aus main() — vix_term, pcr, regime etc.
            ticker_results: results[] aus dem Aggregator (nach process_ticker)
            bn_data (optional, Phase 1 Sept. 2026): {
                "p_upside":       0.65,  # P(Kursteigerung) aus BN Posterior
                "p_drawdown":     0.20,  # P(Verlust >5% in 10 Tagen)
                "signal_strength": 0.8   # Konsistenz der BN-Kausalstruktur
            }
            hmm_data (optional, Phase 2 Okt. 2026): {
                "state":           0,              # 0=EXPANSION 1=RISK_OFF 2=CRASH 3=TRANSITION
                "probs":           [0.7,0.2,0.05,0.05],
                "persistence":     8,              # Tage im aktuellen Zustand
                "transition_risk": 0.2             # P(Regimewechsel in 3 Tagen)
            }

        Returns:
            Dict mit confidence, mode, position_size, direction, warnings,
            cusum_buffer (für KV-Persistenz), divergences, timestamp
        """
        try:
            # 1. Makro-Regime aus market_data
            self.current_regime = (
                market_data.get("regime") or
                market_data.get("regimeUsed") or
                "NEUTRAL"
            ).upper()

            # 2. BN/HMM-Konfidenz berechnen (wenn Daten vorhanden)
            bn_confidence  = self._calc_bn_confidence(bn_data)
            hmm_confidence = self._calc_hmm_confidence(hmm_data)
            if hmm_data and hmm_data.get("probs"):
                self.regime_probabilities = {
                    i: p for i, p in enumerate(hmm_data["probs"])
                }

            # 3. Divergenz-Detektor: BN vs. HMM vs. Makro
            divergences = self._detect_divergences(bn_data, hmm_data, market_data)

            # 4. Ticker-Konsens aus bestehenden UIQ-Scores
            aggregated = self._aggregate_ticker_signals(ticker_results)

            # 5. Schutzmechanismen
            vix = self._extract_vix(market_data)
            self.cusum_alarm = self._check_cusum(vix)
            self.var_95      = self._calculate_evt_var(market_data)

            # 6. Confidence fusionieren (Meta-Intelligenz)
            self.confidence_score = self._calculate_confidence(
                aggregated, self.cusum_alarm, self.var_95, market_data,
                bn_confidence=bn_confidence,
                hmm_confidence=hmm_confidence,
                divergences=divergences,
            )

            # 7. Operative Entscheidung
            action = self._derive_action(
                aggregated["consensus"],
                self.confidence_score,
                self.var_95
            )

            return {
                "version":       DCE_VERSION,
                "confidence":    self.confidence_score,
                "mode":          self.mode,
                "position_size": action["position_size"],
                "direction":     action["direction"],
                "regime":        self.current_regime,
                "regime_probs":  self.regime_probabilities,
                "bn_signal":     bn_data.get("p_upside") if bn_data else None,
                "hmm_state":     hmm_data.get("state")   if hmm_data else None,
                "var_95":        self.var_95,
                "cusum_alarm":   self.cusum_alarm,
                "aggregated":    aggregated,
                "divergences":   divergences,
                "warnings":      self._collect_warnings(),
                "cusum_buffer":  self.volatility_buffer[-50:],
                "timestamp":     datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            log.error(f"[DCE] update() fehlgeschlagen: {e}", exc_info=True)
            return self._fallback(str(e))

    # ── Phasen-Schnittstellen (Platzhalter) ───────────────────────────────────

    def _get_bn_signal(self, data: Dict) -> float:
        """
        Phase 1 (Sept. 2026): Bayesian Network → P(Kursteigerung).
        Trainiert auf: rsScore, confluenceScore, trendScore, adx, chopIndex,
                       distToAvwapPct (Cross-Section 711 Ticker × ~30 Felder).
        Bis Phase 1 aktiv: neutraler Prior 0.5.
        """
        if self.bn_model is None:
            return 0.5
        # → PyMC posterior predictive hier
        return 0.5  # Platzhalter

    def _get_hmm_state(self, data: Dict) -> tuple:
        """
        Phase 2 (Okt. 2026): GaussianHMM(n_components=4) auf MCM-Zeitreihen.
        Features: VIX, HY-Spread, Net Liquidity, Move Index, SKEW.
        States: 0=EXPANSION, 1=RISK_OFF, 2=CRASH, 3=TRANSITION.
        Bis Phase 2 aktiv: neutral gleichverteilt.
        """
        if self.hmm_model is None:
            return 0, {0: 0.25, 1: 0.25, 2: 0.25, 3: 0.25}
        # → hmmlearn predict_proba hier
        return 0, {}  # Platzhalter

    def _get_nn_signal(self, data: Dict) -> float:
        """
        Phase 3 (Q1 2027): LSTM(32) für Regime-Transition-Timing.
        Go/No-Go: Erst aktivieren wenn Phase 2 ≥ 60 Tage Betrieb hat
        UND messbarer Timing-Lag (≥ 2 Tage) im HMM nachgewiesen ist.
        In RED-Phasen: immer deaktiviert.
        """
        if self.nn_model is None or self.mode == "RED":
            return 0.5
        return 0.5  # Platzhalter

    # ── BN/HMM-Konfidenz (Phase 1/2 Integration) ─────────────────────────────

    def _calc_bn_confidence(self, bn_data: Optional[Dict]) -> Optional[float]:
        """
        Phase 1 (Sept. 2026): BN-Konfidenz aus Posterior-Wahrscheinlichkeiten.
        Je höher p_upside und signal_strength, je niedriger p_drawdown — desto höher.
        """
        if not bn_data:
            return None
        p_up     = float(bn_data.get("p_upside",       0.5))
        p_dd     = float(bn_data.get("p_drawdown",     0.2))
        strength = float(bn_data.get("signal_strength", 0.5))
        raw    = (p_up * 100.0) - (p_dd * 50.0)
        scaled = max(0.0, min(100.0, raw * strength))
        return round(scaled, 2)

    def _calc_hmm_confidence(self, hmm_data: Optional[Dict]) -> Optional[float]:
        """
        Phase 2 (Okt. 2026): HMM-Konfidenz aus Zustandswahrscheinlichkeiten.
        Hohe Max-Prob + lange Persistenz + niedriges Übergangsrisiko = hohe Konfidenz.
        """
        if not hmm_data:
            return None
        probs = hmm_data.get("probs", [])
        if not probs:
            return None
        max_prob    = float(max(probs))
        persistence = float(hmm_data.get("persistence",     1))
        trans_risk  = float(hmm_data.get("transition_risk", 0.0))
        persist_bonus = min(20.0, persistence * 2.0)   # max +20 nach 10 Tagen
        risk_penalty  = trans_risk * 30.0               # max -30
        raw = (max_prob * 100.0) + persist_bonus - risk_penalty
        return round(max(0.0, min(100.0, raw)), 2)

    def _detect_divergences(self, bn_data: Optional[Dict],
                             hmm_data: Optional[Dict],
                             market_data: Dict) -> List[Dict]:
        """
        Erkennt signifikante Widersprüche zwischen Modell-Outputs.
        Sekerke: Divergenzen zwischen Signalquellen sind ein explizites Warnsignal
        für erhöhte Modell-Unsicherheit.
        """
        divs: List[Dict] = []
        regime = (
            market_data.get("regime") or
            market_data.get("regimeUsed") or
            "NEUTRAL"
        ).upper()

        # 1. BN bullisch vs. HMM bärisch (oder umgekehrt)
        if bn_data and hmm_data:
            bn_up     = float(bn_data.get("p_upside", 0.5))
            hmm_state = int(hmm_data.get("state", 0))  # 0=EXPANSION, 1=RISK_OFF, 2=CRASH
            if bn_up > 0.65 and hmm_state in (1, 2):
                divs.append({
                    "type":     "BN_HMM_CONFLICT",
                    "severity": "high",
                    "message":  f"BN bullish ({bn_up:.0%}) vs. HMM bearish (state={hmm_state})",
                    "impact":   -25,
                })
            elif bn_up < 0.40 and hmm_state == 0:
                divs.append({
                    "type":     "BN_HMM_CONFLICT",
                    "severity": "medium",
                    "message":  f"BN bearish ({bn_up:.0%}) vs. HMM bullish (state=0)",
                    "impact":   -15,
                })

        # 2. BN bullisch im Stress-Regime
        if bn_data:
            bn_up = float(bn_data.get("p_upside", 0.5))
            if bn_up > 0.70 and "STRESS" in regime:
                divs.append({
                    "type":     "BN_REGIME_CONFLICT",
                    "severity": "medium",
                    "message":  f"BN bullish ({bn_up:.0%}) im Stress-Regime ({regime})",
                    "impact":   -15,
                })

        return divs

    # ── Ticker-Aggregation ────────────────────────────────────────────────────

    def _aggregate_ticker_signals(self, results: List[Dict]) -> Dict:
        """
        Aggregiert UIQ-Scores aller Ticker zu einem Markt-Konsens.
        Nutzt bestehende sMinervini, sSwing, sBreakout, confluenceScore.
        """
        empty = {"consensus": 0.5, "bullish_pct": 0.5, "std_dev": 0.0, "n": 0}
        if not results:
            return empty

        scores = []
        for r in results:
            # Primär: UIQ-Strategie-Scores (normalisiert 0-1)
            s_vals = [v for k in ("sMinervini", "sSwing", "sBreakout")
                      if (v := r.get(k)) is not None]
            # Ergänzend: confluenceScore (TVA Sprint A)
            if (cs := r.get("confluenceScore")) is not None:
                s_vals.append(cs)
            if s_vals:
                scores.append(np.mean(s_vals) / 100.0)

        if not scores:
            return empty

        mean = float(np.mean(scores))
        std  = float(np.std(scores))
        bull = sum(1 for s in scores if s > 0.55) / len(scores)

        return {
            "consensus":   round(mean, 3),
            "bullish_pct": round(bull, 3),
            "std_dev":     round(std,  3),
            "n":           len(scores),
        }

    # ── Schutzmechanismen ─────────────────────────────────────────────────────

    def _extract_vix(self, market_data: Dict) -> float:
        """VIX aus verschiedenen Quellstrukturen extrahieren."""
        # vix_term Dict (Hauptquelle aus market_aggregator.py)
        vt = market_data.get("vix_term", {}) or {}
        if (v := vt.get("vix")) is not None:
            return float(v)
        # Snapshot-Fallback
        snap = market_data.get("snapshot", {}) or {}
        if (v := snap.get("vix")) is not None:
            return float(v)
        return 20.0  # neutraler Default

    def _check_cusum(self, new_vix: float) -> bool:
        """
        CUSUM-Alarm: struktureller Bruch in der VIX-Zeitreihe.
        Buffer wird via KV persistiert (über GHA-Runs hinweg).
        """
        self.volatility_buffer.append(float(new_vix))
        if len(self.volatility_buffer) > 50:
            self.volatility_buffer.pop(0)
        if len(self.volatility_buffer) < 10:
            return False

        mean   = float(np.mean(self.volatility_buffer))
        cumsum = float(np.sum([x - mean for x in self.volatility_buffer]))
        std    = float(np.std(self.volatility_buffer)) or 1.0
        return cumsum > self.cusum_threshold * std

    def _calculate_evt_var(self, market_data: Dict) -> float:
        """
        EVT-basierter VaR (Generalized Pareto Distribution auf linken Tail).
        Input: SPY-Returns aus main() (letzte 60 Tage).
        """
        returns = market_data.get("spy_returns_60d", [])
        if not returns or len(returns) < 20:
            return -0.05  # konservativer Default

        try:
            from scipy.stats import genpareto
            arr       = np.array(returns, dtype=float)
            threshold = float(np.percentile(arr, 5))
            excess    = arr[arr < threshold] - threshold
            if len(excess) > 3:
                shape, loc, scale = genpareto.fit(-excess)
                var = threshold - genpareto.ppf(0.95, shape, loc=loc, scale=scale)
                return round(float(var), 4)
            return round(float(np.percentile(arr, 1)), 4)
        except Exception as e:
            log.debug(f"[DCE] EVT-VaR Fehler: {e}")
            return -0.05

    # ── Kern-Logik DCE ────────────────────────────────────────────────────────

    def _calculate_confidence(self, agg: Dict, alarm: bool,
                               var: float, market_data: Dict,
                               bn_confidence: Optional[float] = None,
                               hmm_confidence: Optional[float] = None,
                               divergences: Optional[List[Dict]] = None) -> int:
        """
        Sekerke-inspirierte Fusion mit optionaler BN/HMM-Integration.

        Ohne BN/HMM:  70% Ticker-Konsistenz + 30% Regime-Konfidenz
        Mit BN/HMM:   60% Basis + 40% Modell-Score (BN 60% / HMM 40%)
        Abzüge: Divergenzen, CUSUM, VaR, VIX
        Dämpfer: STRESS_UNSTABLE × 0.6 / POST_PANIC × 0.75
        """
        # 1. Ticker-Konsistenz
        std = agg.get("std_dev", 0.5)
        consistency = max(0.0, 100.0 - std * 150.0)

        # 2. Regime-Konfidenz
        regime_conf = float(REGIME_CONFIDENCE.get(self.current_regime, 50))

        # 3. Basis-Score
        base = consistency * 0.70 + regime_conf * 0.30

        # 4. BN/HMM-Fusion (wenn verfügbar — Phase 1/2)
        model_score  = 0.0
        model_weight = 0.0
        if bn_confidence is not None:
            model_score  += bn_confidence * 0.60
            model_weight += 0.60
        if hmm_confidence is not None:
            model_score  += hmm_confidence * 0.40
            model_weight += 0.40
        if model_weight > 0:
            model_avg = model_score / model_weight
            base = base * 0.60 + model_avg * 0.40

        # 5. Divergenz-Strafen
        penalty = 0.0
        for d in (divergences or []):
            penalty += abs(float(d.get("impact", 0)))

        # 6. Sicherheitsabzüge
        if alarm:       penalty += 30.0
        if var < -0.03: penalty += 20.0
        if var < -0.05: penalty += 15.0

        vix = self._extract_vix(market_data)
        if   vix > 30: penalty += 15.0
        elif vix > 25: penalty +=  8.0

        # 7. Regime-Dämpfer (Sekerke: Modelle in Krisen weniger verlässlich)
        dampener = REGIME_DAMPENING.get(self.current_regime, 1.0)
        base *= dampener

        return max(0, min(100, round(base - penalty)))

    def _derive_action(self, consensus: float, confidence: int,
                        var: float) -> Dict:
        """
        Operative Entscheidung: Ampel → Positionsgröße → Richtung.
        Implementiert §0-Logik: Gate 1 (Ob) → Gate 2 (Wie) → Gate 3 (Was).
        """
        # Gate 1: Ob gehandelt werden soll (Ampel)
        if   confidence < 30 or var < -0.05: self.mode = "RED"
        elif confidence < 55 or var < -0.025: self.mode = "YELLOW"
        else:                                  self.mode = "GREEN"

        # Gate 2: Wie (Positionsgröße)
        size_factor   = {"GREEN": 1.0, "YELLOW": 0.5, "RED": 0.0}[self.mode]
        position_size = round((confidence / 100.0) * size_factor, 2)

        # Gate 3: Was (Richtung — nur wenn Gates 1+2 offen)
        if   self.mode == "RED":    direction = "HOLD"
        elif consensus > 0.55:      direction = "BUY"
        elif consensus < 0.45:      direction = "SELL"
        else:                       direction = "HOLD"

        return {"position_size": position_size, "direction": direction}

    def _collect_warnings(self) -> List[str]:
        """Warnungen für Morning Briefing und Log."""
        w = []
        if   self.mode == "RED":    w.append("🔴 ROTE AMPEL: Keine neuen Positionen — Kapitalschutz")
        elif self.mode == "YELLOW": w.append("🟡 GELBE AMPEL: Reduzierte Positionsgrößen, selektiv vorgehen")
        if self.cusum_alarm:
            w.append("⚠️  CUSUM-ALARM: Struktureller Bruch in VIX-Zeitreihe erkannt")
        if self.var_95 < -0.05:
            w.append(f"⚠️  EXTREM-RISIKO: EVT-VaR(95) bei {self.var_95:.2%} — defensive Positionierung")
        if self.current_regime == "STRESS_UNSTABLE":
            w.append("⚠️  REGIME STRESS_UNSTABLE: Alle Modelle gedämpft (Sekerke-Faktor 0.6)")
        return w

    def _fallback(self, error_msg: str = "") -> Dict:
        """Konservativer Fallback bei DCE-Fehler — niemals Absturz des Hauptlaufs."""
        return {
            "version":       DCE_VERSION,
            "confidence":    50,
            "mode":          "YELLOW",
            "position_size": 0.5,
            "direction":     "HOLD",
            "regime":        self.current_regime,
            "regime_probs":  {},
            "var_95":        -0.05,
            "cusum_alarm":   False,
            "aggregated":    {},
            "warnings":      [f"DCE-Fehler (Fallback aktiv): {error_msg}"],
            "cusum_buffer":  self.volatility_buffer[-50:],
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        }


# ── Brier Score ───────────────────────────────────────────────────────────────

def compute_brier_score(
    confidence_history,   # List[float] ODER Dict{"confidence":[], "outcomes":[]}
    outcome_history: Optional[List[int]] = None,
) -> Optional[float]:
    """
    Brier Score: Kalibrierungsmaß der DCE-Confidence.
    Gut: < 0.25 | Akzeptabel: < 0.33 | Schlecht: > 0.33

    Zwei Aufruf-Varianten:
        # Variante A (zwei Listen):
        compute_brier_score([70, 80, 60], [1, 1, 0])

        # Variante B (Dict — für History-Objekt):
        compute_brier_score({"confidence": [70, 80], "outcomes": [1, 1]})

    Args:
        confidence_history: Liste (0-100) ODER Dict mit "confidence"+"outcomes"
        outcome_history:    1 wenn Markt-Erwartung eingetreten, 0 wenn nicht
    """
    # Variante B: Dict-Input
    if isinstance(confidence_history, dict):
        conf_list = confidence_history.get("confidence", [])
        out_list  = confidence_history.get("outcomes",   [])
    else:
        conf_list = confidence_history or []
        out_list  = outcome_history    or []

    if len(conf_list) < 10 or len(out_list) < 10:
        return None
    n = min(len(conf_list), len(out_list))
    c = [v / 100.0 for v in conf_list[-n:]]
    o = out_list[-n:]
    return round(float(np.mean([(ci - oi) ** 2 for ci, oi in zip(c, o)])), 4)


# ── Aggregator-Einstiegspunkt ─────────────────────────────────────────────────

def run_dce(market_data: Dict,
            ticker_results: List[Dict],
            config: Optional[Dict] = None,
            cusum_buffer: Optional[List[float]] = None) -> Dict:
    """
    Haupt-Einstiegspunkt für market_aggregator.py.

    Aufruf in main() nach build_leaderboards(), vor finalem Master-JSON:

        from dce_layer import run_dce
        dce_result = run_dce(
            market_data={
                "regime":         market_regime_str,
                "vix_term":       vix_term,
                "spy_returns_60d": spy_returns_60d,   # Liste von float (% Returns)
                "snapshot":       market_snapshot,
            },
            ticker_results=results,
            cusum_buffer=kv_cusum_buffer,  # aus KV geladen, für Persistenz
        )
        master["dce"] = dce_result
        # cusum_buffer für nächsten Run: dce_result["cusum_buffer"]

    Fehlerisoliert: Liefert immer ein gültiges Dict zurück.
    """
    try:
        dce = DecisionConfidenceEngine(config=config or {}, cusum_buffer=cusum_buffer)
        return dce.update(market_data, ticker_results)
    except Exception as e:
        log.error(f"[DCE] run_dce Fehler: {e}", exc_info=True)
        return DecisionConfidenceEngine()._fallback(str(e))


# ── Smoke-Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Simulierte Inputs (analog market_aggregator.py main())
    import random
    random.seed(42)

    mock_market = {
        "regime":          "BULL_FRAGILE",
        "vix_term":        {"vix": 18.5, "ratio": 1.05},
        "spy_returns_60d": [random.gauss(0.0004, 0.012) for _ in range(60)],  # Dezimal, nicht %
        "snapshot":        {"vix": 18.5},
    }
    mock_tickers = [
        {"sym": "AAPL", "sMinervini": 72, "sSwing": 58, "sBreakout": 65, "confluenceScore": 68},
        {"sym": "NVDA", "sMinervini": 85, "sSwing": 80, "sBreakout": 78, "confluenceScore": 82},
        {"sym": "TSLA", "sMinervini": 22, "sSwing": 18, "sBreakout": 20, "confluenceScore": 16},
        {"sym": "MSFT", "sMinervini": 61, "sSwing": 55, "sBreakout": 59, "confluenceScore": 52},
    ]

    print("═" * 60)
    print("  DCE Smoke-Test v" + DCE_VERSION)
    print("═" * 60)

    result = run_dce(mock_market, mock_tickers)

    print(f"  Confidence:    {result['confidence']}/100")
    print(f"  Mode:          {result['mode']}")
    print(f"  Position Size: {result['position_size']:.0%}")
    print(f"  Direction:     {result['direction']}")
    print(f"  Regime:        {result['regime']}")
    print(f"  CUSUM-Alarm:   {result['cusum_alarm']}")
    print(f"  VaR(95):       {result['var_95']:.2%}")
    print(f"  Ticker-Konsens: {result['aggregated']}")
    print(f"  Warnungen:     {result['warnings']}")

    # Brier Score Test
    bs = compute_brier_score([75, 80, 45, 60, 70, 55, 85, 40, 65, 72],
                              [1,   1,  0,  1,  1,  0,  1,  0,  1,  1])
    print(f"\n  Brier Score (Demo): {bs} ({'gut' if bs < 0.25 else 'akzeptabel' if bs < 0.33 else 'schlecht'})")
    print("═" * 60)
    sys.exit(0)
