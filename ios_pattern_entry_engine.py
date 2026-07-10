"""
IOS Pattern & Entry Engine — Python-Portierung der Pine-Scripts #4/#5
========================================================================
Quelle: 8 Pine-Script-Indikatoren eines Freundes von Axel (10.07.2026),
Framework: Market → Trend → Momentum → Pattern → Entry → Risk → Position → Decision.

Diese Datei portiert NUR Pattern Score (#4) + Entry Score (#5), weil:
- Market/Trend/Momentum überschneiden sich stark mit UIQ's bestehendem
  score_long_minervini() / IOS Market Score / Sektor-RS — kein Neubau nötig,
  ggf. spätere Verfeinerung (explizites 7-Kriterien-Template, Weinstein-Stages).
- Pattern (VCP/Pocket-Pivot/Darvas) und Entry (präzises Timing+Preis) sind
  UIQ-Neuland — UIQ hat aktuell nur eine grobe bbPos/HVP-VCP-Näherung.
- Position Risk/Position/Decision brauchen Account-/Portfolio-Kontext
  (Depotgröße, aktuelle Exposure) — das ist User-spezifisch, kein
  Scan-Kriterium für "interessante Underlyings". Eigener Baustein später.

WICHTIG: Noch NICHT in market_aggregator.py verdrahtet (bewusst, Stand
10.07.2026 — Präsentation am selben Tag, kein Risiko für Produktivumgebung).
Nutzt dieselben Rohdaten-Listen (closes/highs/lows/volumes) wie
process_ticker() — keine neue Datenquelle nötig, nur neue Berechnung.

Status: Prototyp, gegen echte Ticker-Historie verifiziert, aber noch nicht
in den Scan-Loop integriert. Nächster Schritt (nach Präsentation): Aufruf
in process_ticker() einbauen, Ergebnis in results.json aufnehmen.
"""

import math


# ─────────────────────────────────────────────────────────────────────────
# HILFSFUNKTIONEN (fehlen noch im Aggregator, hier nachgebaut)
# ─────────────────────────────────────────────────────────────────────────

def rolling_max(series, window):
    """Höchster Wert der letzten `window` Perioden, pro Index. NaN-sicher."""
    out = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        chunk = series[start:i + 1]
        out.append(max(chunk) if chunk else None)
    return out


def rolling_min(series, window):
    out = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        chunk = series[start:i + 1]
        out.append(min(chunk) if chunk else None)
    return out


def calc_atr_series(highs, lows, closes, period=14):
    """ATR als volle Serie (nicht nur letzter Wert wie calc_atr() im Aggregator).
    Wilder's Smoothing, identisch zu Pine's ta.atr()."""
    if len(closes) < period + 1:
        return [None] * len(closes)
    trs = [None]
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    atr = [None] * len(closes)
    valid_trs = [t for t in trs[1:period + 1] if t is not None]
    if len(valid_trs) < period:
        return atr
    atr[period] = sum(valid_trs) / period
    for i in range(period + 1, len(closes)):
        atr[i] = (atr[i - 1] * (period - 1) + trs[i]) / period
    return atr


def low_i(lows, i):
    """Kleine Hilfsfunktion für Lesbarkeit (low[i])."""
    return lows[i]


# ─────────────────────────────────────────────────────────────────────────
# PATTERN SCORE (Pine #4) — VCP / Pocket Pivot / Darvas / Pullback
# ─────────────────────────────────────────────────────────────────────────

def score_pattern_setup(closes, highs, lows, volumes,
                         ema21_series, sma50_series, sma150_series, sma200_series,
                         vol_ma_len=20, pivot_len=20, darvas_len=20,
                         max_ema_ext_pct=6.0, max_pivot_ext_pct=5.0):
    """
    Portierung von "IOS Core Pattern Engine v1.0" (Pine #4).

    Erwartet volle Serien (Listen), nicht nur Punktwerte — Pattern-Erkennung
    braucht Ranges über mehrere Perioden (VCP-Kontraktion, Darvas-Box).

    Rückgabe: dict mit patternScore (0-100), bestPattern (Label),
    patternEntry (vorgeschlagener Einstiegspreis), Einzelscores je Pattern-Typ.
    """
    n = len(closes)
    if n < max(darvas_len, pivot_len, 200) + 5:
        return {"ok": False, "reason": f"zu wenig Historie ({n} Bars, brauche >{max(darvas_len,pivot_len,200)+5})"}

    i = n - 1  # letzter (aktuellster) Bar
    close = closes[i]
    open_ = closes[i - 1] if i > 0 else close  # Fallback falls kein Open verfügbar
    high, low = highs[i], lows[i]

    ema21 = ema21_series[i]
    sma50 = sma50_series[i]
    sma150 = sma150_series[i]
    sma200 = sma200_series[i]

    if None in (ema21, sma50, sma150, sma200):
        return {"ok": False, "reason": "SMA/EMA-Serien unvollständig (zu wenig Historie)"}

    vol_ma = sum(volumes[max(0, i - vol_ma_len + 1):i + 1]) / min(vol_ma_len, i + 1)
    rel_vol = volumes[i] / vol_ma if vol_ma else None

    trend_ok = close > sma50 and close > sma150 and close > sma200 and sma50 > sma150 and sma150 > sma200

    bull_candle = close > open_
    strong_close = (close >= low + (high - low) * 0.65) if high != low else False

    pivot_high = max(highs[max(0, i - pivot_len):i]) if i > 0 else high
    dist_pivot_pct = (close / pivot_high - 1) * 100 if pivot_high else None
    dist_ema_pct = (close / ema21 - 1) * 100 if ema21 else None

    not_extended_ema = dist_ema_pct is not None and dist_ema_pct <= max_ema_ext_pct
    not_extended_pivot = dist_pivot_pct is not None and dist_pivot_pct <= max_pivot_ext_pct

    # EMA21 Pullback
    ema_touch = low <= ema21 and close > ema21
    ema_near = dist_ema_pct is not None and abs(dist_ema_pct) <= 3
    ema_pb_score = min(
        (25 if trend_ok else 0)
        + (30 if ema_touch else (20 if ema_near else 0))
        + (15 if bull_candle else 0)
        + (15 if strong_close else 0)
        + (10 if rel_vol and rel_vol >= 1.0 else 0)
        + (5 if not_extended_ema else 0),
        100)

    # SMA50 Pullback
    sma50_touch = low <= sma50 and close > sma50
    sma50_near = abs((close / sma50 - 1) * 100) <= 4 if sma50 else False
    sma50_pb_score = min(
        (30 if trend_ok else 0)
        + (30 if sma50_touch else (20 if sma50_near else 0))
        + (15 if bull_candle else 0)
        + (15 if strong_close else 0)
        + (10 if rel_vol and rel_vol >= 1.0 else 0),
        100)

    # Pocket Pivot
    down_vols = [volumes[j] for j in range(max(0, i - 10), i) if closes[j] < closes[j - 1]] if i >= 11 else []
    down_vol_max10 = max(down_vols) if down_vols else 0
    pocket_pivot_score = min(
        (25 if trend_ok else 0)
        + (30 if volumes[i] > down_vol_max10 else 0)
        + (20 if strong_close else 0)
        + (15 if close > ema21 else 0)
        + (10 if rel_vol and rel_vol >= 1.2 else 0),
        100)

    # Breakout
    breakout_raw = close > pivot_high if pivot_high else False
    breakout_score = min(
        (20 if trend_ok else 0)
        + (25 if breakout_raw else 0)
        + (25 if rel_vol and rel_vol >= 1.5 else (15 if rel_vol and rel_vol >= 1.2 else 0))
        + (15 if strong_close else 0)
        + (15 if not_extended_pivot else 0),
        100)

    # Darvas Box
    darvas_top = max(highs[max(0, i - darvas_len):i]) if i > 0 else high
    darvas_bottom = min(lows[max(0, i - darvas_len):i]) if i > 0 else low
    darvas_range_pct = (darvas_top - darvas_bottom) / close * 100 if close else None
    darvas_tight = darvas_range_pct is not None and darvas_range_pct <= 15
    darvas_breakout_raw = close > darvas_top if darvas_top else False
    darvas_score = min(
        (20 if trend_ok else 0)
        + (20 if darvas_tight else 0)
        + (30 if darvas_breakout_raw else 0)
        + (15 if rel_vol and rel_vol >= 1.2 else 0)
        + (15 if strong_close else 0),
        100)

    # VCP (Volatility Contraction Pattern)
    def _range_pct(window):
        h = max(highs[max(0, i - window + 1):i + 1])
        l = min(lows[max(0, i - window + 1):i + 1])
        return (h - l) / close * 100 if close else None

    range30_pct = _range_pct(30)
    range15_pct = _range_pct(15)
    range7_pct = _range_pct(7)

    atr_series = calc_atr_series(highs, lows, closes, period=7)
    atr_series_slow = calc_atr_series(highs, lows, closes, period=21)
    atr_now = atr_series[i] if i < len(atr_series) else None
    atr_old = atr_series_slow[i] if i < len(atr_series_slow) else None

    vcp_contraction = (range7_pct is not None and range15_pct is not None and range30_pct is not None
                       and range7_pct < range15_pct < range30_pct)
    vcp_atr_contract = atr_now is not None and atr_old is not None and atr_now < atr_old
    vcp_volume_dry = volumes[i] < vol_ma if vol_ma else False
    vcp_near_pivot = dist_pivot_pct is not None and abs(dist_pivot_pct) <= 5
    vcp_tight = range7_pct is not None and range7_pct <= 6

    vcp_score = min(
        (15 if trend_ok else 0)
        + (25 if vcp_contraction else 0)
        + (20 if vcp_atr_contract else 0)
        + (15 if vcp_volume_dry else 0)
        + (15 if vcp_near_pivot else 0)
        + (10 if vcp_tight else 0),
        100)

    # Tight / Inside Day
    inside_day = i >= 1 and high < highs[i - 1] and low > lows[i - 1]
    tight_close = i >= 1 and abs(close - closes[i - 1]) / close <= 0.015
    tight_range = (high - low) / close <= 0.025 if close else False
    tight_score = min(
        (25 if trend_ok else 0)
        + (20 if inside_day else 0)
        + (20 if tight_close else 0)
        + (20 if tight_range else 0),
        100)

    # Bestes Pattern + finaler Score
    scores = {
        "Breakout": breakout_score, "Pocket Pivot": pocket_pivot_score,
        "EMA21 Pullback": ema_pb_score, "SMA50 Pullback": sma50_pb_score,
        "Darvas": darvas_score, "VCP": vcp_score, "Tight / Inside": tight_score,
    }
    best_pattern = max(scores, key=scores.get)
    best_score = scores[best_pattern]
    if best_score < 60:
        best_pattern = "Kein Pattern"

    pattern_decision = (
        "HIGH QUALITY" if best_score >= 85 and trend_ok else
        "VALID PATTERN" if best_score >= 70 and trend_ok else
        "WATCH" if best_score >= 55 and trend_ok else
        "NO PATTERN"
    )

    # Entry-Preis-Vorschlag
    buy_stop = max(pivot_high or 0, darvas_top or 0) * 1.002
    limit_pullback = ema21 * 1.01
    normal_entry = (ema21 + pivot_high) / 2 if pivot_high else ema21
    deep_pullback = (ema21 + sma50) / 2
    max_buy = min((pivot_high or close) * 1.03, ema21 * (1 + max_ema_ext_pct / 100))

    if breakout_raw and breakout_score >= 70:
        pattern_entry = close
    elif pocket_pivot_score >= 70 and volumes[i] > down_vol_max10:
        pattern_entry = close
    elif ema_pb_score >= 70:
        pattern_entry = limit_pullback
    elif sma50_pb_score >= 70:
        pattern_entry = sma50 * 1.01
    elif vcp_score >= 75:
        pattern_entry = buy_stop
    elif darvas_score >= 70 and darvas_breakout_raw:
        pattern_entry = buy_stop
    else:
        pattern_entry = normal_entry

    return {
        "ok": True,
        "patternScore": round(best_score),
        "bestPattern": best_pattern,
        "patternDecision": pattern_decision,
        "trendOk": trend_ok,
        "scores": {k: round(v) for k, v in scores.items()},
        "entry": {
            "suggested": round(pattern_entry, 4),
            "buyStop": round(buy_stop, 4),
            "limitPullback": round(limit_pullback, 4),
            "normalEntry": round(normal_entry, 4),
            "deepPullback": round(deep_pullback, 4),
            "maxBuy": round(max_buy, 4),
        },
        "diagnostics": {
            "relVol": round(rel_vol, 2) if rel_vol else None,
            "distPivotPct": round(dist_pivot_pct, 2) if dist_pivot_pct is not None else None,
            "distEmaPct": round(dist_ema_pct, 2) if dist_ema_pct is not None else None,
            "darvasRangePct": round(darvas_range_pct, 2) if darvas_range_pct is not None else None,
            "vcpContraction": vcp_contraction,
            "vcpAtrContract": vcp_atr_contract,
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# ENTRY SCORE (Pine #5) — Timing-Bewertung, eigenständig nutzbar
# ─────────────────────────────────────────────────────────────────────────

def score_entry_timing(closes, highs, lows, volumes,
                        ema9_series, ema21_series, sma50_series, sma150_series, sma200_series,
                        rsi_series, vol_ma_len=20, pivot_len=20):
    """
    Portierung von "IOS Entry Score v1.0" (Pine #5).
    Eigenständig von score_pattern_setup() nutzbar — bewertet NUR Timing,
    nicht welches Pattern vorliegt (das macht score_pattern_setup()).

    FIX ggü. Pine-Original: Division-by-Zero-Schutz bei vol_ma==0 ergänzt
    (Original hatte hier keinen Schutz — Bug im Original-Script gefunden,
    Review 10.07.2026).
    """
    n = len(closes)
    if n < 200 + 5:
        return {"ok": False, "reason": f"zu wenig Historie ({n} Bars, brauche >205)"}

    i = n - 1
    close = closes[i]

    ema9 = ema9_series[i]
    ema21 = ema21_series[i]
    sma50 = sma50_series[i]
    sma150 = sma150_series[i]
    sma200 = sma200_series[i]
    rsi = rsi_series[i] if i < len(rsi_series) else None

    if None in (ema9, ema21, sma50, sma150, sma200, rsi):
        return {"ok": False, "reason": "Indikator-Serien unvollständig"}

    vol_ma = sum(volumes[max(0, i - vol_ma_len + 1):i + 1]) / min(vol_ma_len, i + 1)
    rel_vol = volumes[i] / vol_ma if vol_ma else 0

    prior_high = max(highs[max(0, i - pivot_len):i]) if i > 0 else highs[i]
    breakout = close > prior_high and rel_vol >= 1.2

    trend_ok = close > sma50 and close > sma150 and close > sma200 and sma50 > sma150 and sma150 > sma200
    ema_ok = ema9 > ema21

    pullback_to_ema = low_i(lows, i) <= ema21 and close > ema21 and trend_ok
    pullback_to_sma50 = low_i(lows, i) <= sma50 and close > sma50 and trend_ok

    extended_pct = (close - ema21) / close * 100 if close else 0
    extended = extended_pct > 8

    near_ema = abs(close - ema21) / close * 100 <= 3 if close else False
    near_sma50 = abs(close - sma50) / close * 100 <= 4 if close else False

    candle_bull = close > closes[i - 1] if i > 0 else True
    strong_close = close >= lows[i] + (highs[i] - lows[i]) * 0.65 if highs[i] != lows[i] else False

    trend_score = min((45 if trend_ok else 0) + (20 if ema_ok else 0)
                       + (15 if close > sma50 else 0)
                       + (20 if i >= 10 and sma50 > sma50_series[i - 10] else 0), 100)

    timing_score = (40 if breakout else 0) + (30 if pullback_to_ema else 0) + (25 if pullback_to_sma50 else 0) \
        + (15 if near_ema else 0) + (10 if near_sma50 else 0) - (30 if extended else 0)
    timing_score = max(0, min(timing_score, 100))

    volume_score = min((25 if rel_vol > 1 else 0) + (25 if rel_vol > 1.2 else 0)
                        + (25 if rel_vol > 1.5 else 0) + (25 if candle_bull and rel_vol > 1 else 0), 100)

    momentum_score = min((25 if rsi > 50 else 0) + (20 if rsi > 55 else 0) + (20 if rsi < 75 else 0)
                          + (20 if strong_close else 0) + (15 if candle_bull else 0), 100)

    entry_score = round(trend_score * 0.35 + timing_score * 0.30 + volume_score * 0.20 + momentum_score * 0.15)

    grade = ("A+ Entry" if entry_score >= 90 else "A Entry" if entry_score >= 80 else
             "B Entry" if entry_score >= 70 else "Watch" if entry_score >= 55 else "No Entry")
    action = ("BUY / ADD" if entry_score >= 85 else "BUY SMALL" if entry_score >= 70 else
              "WATCH" if entry_score >= 55 else "WAIT")
    setup = "Breakout" if breakout else ("Pullback" if (pullback_to_ema or pullback_to_sma50) else
             ("Extended" if extended else "Neutral"))

    return {
        "ok": True,
        "entryScore": entry_score,
        "grade": grade,
        "action": action,
        "setup": setup,
        "components": {
            "trend": round(trend_score), "timing": round(timing_score),
            "volume": round(volume_score), "momentum": round(momentum_score),
        },
        "diagnostics": {
            "relVol": round(rel_vol, 2), "extendedPct": round(extended_pct, 2),
            "rsi": round(rsi, 1),
        },
    }
