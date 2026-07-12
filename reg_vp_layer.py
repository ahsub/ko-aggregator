"""
reg_vp_layer.py — Polynomial/Linear Regression Volume Profile (BigBeluga, 12.07.2026)
UIQ-Port: mathematischer Kern ohne TV-Visualisierung.

Berechnet pro Ticker:
  - Polynomiale OLS-Regression (Grad 2) auf hl2 × 200 Bars
  - Standardabweichung als Kanal-Breite
  - Volume Profile relativ zur Regressionskurve → POC (Point of Control)
  - Z-Score: Abstand Kurs zur Regressionskurve in σ-Einheiten
  - distToPocPct: Abstand Kurs zum POC in %
  - regTrend: Richtung der Regressionskurve (Bullish/Bearish/Flat)

Lizenz: CC BY-NC-SA 4.0 (analog BigBeluga-Original)
"""

import numpy as np
import logging

log = logging.getLogger("aggregator")

# ── Konfiguration ────────────────────────────────────────────────────────────
LENGTH   = 200   # Lookback-Fenster in Bars
DEGREE   = 2     # Grad der Regression (2 = quadratisch, wie BigBeluga-Default)
NUM_BINS = 20    # Volume-Profile-Bins (±NUM_BINS um Regressionskurve)


def _polyfit_ols(source: np.ndarray, degree: int) -> np.ndarray:
    """OLS-Regression: gibt Preis-Prognosen für alle Bars zurück."""
    n = len(source)
    x = np.arange(n, dtype=float)
    coeffs = np.polyfit(x, source, degree)
    return np.polyval(coeffs, x)


def calc_reg_vp(closes: list, highs: list, lows: list, volumes: list,
                length: int = LENGTH, degree: int = DEGREE,
                num_bins: int = NUM_BINS) -> dict:
    """
    Berechnet Regression Volume Profile für einen Ticker.
    Returns: dict mit zScore, pocLevel, distToPocPct, regTrend, regBaseline,
             chanHigh3sd, chanLow3sd oder {} bei Fehler/zu wenig Daten.
    """
    n = len(closes)
    if n < length or len(highs) < length or len(lows) < length or len(volumes) < length:
        return {}
    try:
        # Letzten `length` Bars
        c  = np.array(closes[-length:],  dtype=float)
        h  = np.array(highs[-length:],   dtype=float)
        l  = np.array(lows[-length:],    dtype=float)
        v  = np.array(volumes[-length:], dtype=float)
        hl2 = (h + l) / 2.0

        # OLS-Regression auf hl2
        preds = _polyfit_ols(hl2, degree)

        # Stichproben-Standardabweichung von hl2
        stdev = float(np.std(hl2, ddof=1))
        if stdev < 1e-10:
            return {}

        # Bin-Größe: 3σ-Raum aufgeteilt in num_bins
        dev = (stdev * 3.0) / num_bins

        # Volume Profile Bins aufbauen
        bin_volumes = np.zeros(num_bins * 2, dtype=float)
        for i in range(length):
            diff = hl2[i] - preds[i]
            bin_idx = int(np.floor(diff / dev)) + num_bins
            if 0 <= bin_idx < num_bins * 2:
                bin_volumes[bin_idx] += v[i]

        max_vol = float(bin_volumes.max())
        if max_vol <= 0:
            return {}

        poc_bin   = int(np.argmax(bin_volumes))
        poc_offset = (poc_bin - num_bins) * dev
        last_pred  = float(preds[-1])
        poc_level  = last_pred + poc_offset

        # Aktuelle Kennzahlen
        current_close = float(c[-1])
        z_score = (current_close - last_pred) / stdev

        # Kanal-Grenzen ±3σ
        chan_high = last_pred + stdev * 3.0
        chan_low  = last_pred - stdev * 3.0

        # Trend: erste vs. letzte Vorhersage
        first_pred = float(preds[0])
        slope_pct  = (last_pred - first_pred) / first_pred * 100 if first_pred > 0 else 0
        if   slope_pct >  0.5: reg_trend = "Bullish"
        elif slope_pct < -0.5: reg_trend = "Bearish"
        else:                   reg_trend = "Flat"

        # Abstand Kurs → POC in %
        dist_to_poc = ((current_close - poc_level) / poc_level * 100
                       if poc_level > 0 else None)

        return {
            "zScore":       round(z_score, 3),
            "pocLevel":     round(poc_level, 4),
            "distToPocPct": round(dist_to_poc, 2) if dist_to_poc is not None else None,
            "regTrend":     reg_trend,
            "regBaseline":  round(last_pred, 4),
            "chanHigh3sd":  round(chan_high, 4),
            "chanLow3sd":   round(chan_low, 4),
        }
    except Exception as e:
        log.debug(f"[REG_VP] Fehler: {e}")
        return {}


def run(results: list) -> dict:
    """
    Wird aus market_aggregator.main() aufgerufen.
    Iteriert über alle Ticker-Ergebnisse und enrichiert sie mit reg_vp Feldern.
    Erwartet: results[i] enthält 'closes', 'highs', 'lows', 'volumes' ODER
              der Aggregator übergibt hist_df-Daten separat.
    Da hist_df nicht persistiert wird, berechnen wir die Felder aus den
    bereits im result enthaltenen Preisreihen — diese wurden als Rohwerte
    via get_col() extrahiert. Wir rufen calc_reg_vp() pro Ticker auf.

    Returns: status dict
    """
    enriched = 0
    errors   = 0

    for r in results:
        sym = r.get("sym", "?")
        # Rohdaten aus _hist_cache (wird vom Aggregator bereitgestellt)
        closes  = r.pop("_closes",  None)
        highs   = r.pop("_highs",   None)
        lows    = r.pop("_lows",    None)
        volumes = r.pop("_volumes", None)

        if closes and highs and lows and volumes:
            rv = calc_reg_vp(closes, highs, lows, volumes)
            if rv:
                r.update(rv)
                enriched += 1
            else:
                errors += 1
        else:
            # Kein Cache → Felder auf None setzen (kein Fehler, nur kein Wert)
            for k in ["zScore","pocLevel","distToPocPct","regTrend",
                      "regBaseline","chanHigh3sd","chanLow3sd"]:
                r.setdefault(k, None)

    log.info(f"  [REG_VP] {enriched} Ticker enrichiert, {errors} Fehler")
    return {"ok": True, "enriched": enriched, "errors": errors}
