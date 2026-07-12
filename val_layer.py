#!/usr/bin/env python3
"""
UIQ VAL-MOD — Value-Scanner Layer (3-Stufen-Sieve nach Carlin/Graham)
======================================================================
Version 1.0 (12.07.2026) | Konzept: docs/VALUE_MOD_KONZEPT.md v5

ARCHITEKTUR: 3-Stufen-Sieve
  Stufe 1 — Ausschluss-Gate:  harte Mindestanforderungen (täglich aus FIN-Archiv)
  Stufe 2 — Value-Score:      Carlin-inspiriertes Scoring 0-100 (6 Dimensionen)
  Stufe 3 — Momentum-Brücke:  RS-Rating + Trend-Bestätigung aus Aggregator-results

DATENQUELLEN:
  - FIN-Archiv (data/fundamentals/YYYY-WW.json.gz) für Fundamentaldaten
  - market_aggregator.py results[] für Kurs/Momentum-Daten (RS-Rating, EMA200)

FEHLERPHILOSOPHIE: identisch zu fin_layer/iv_layer — bricht Hauptlauf niemals.

CARLIN-KRITERIEN (Modern Value Investing, 2018):
  Tool #7  ROIC > Kapitalkosten (Proxy: ROE / (1 + D/E))
  Tool #8  Wachstum als Value-Komponente (Revenue Growth > 0)
  Tool #10 Net Cash / FCF Yield als Margin of Safety
  Tool #12 Gross Margin > 40% als Moat-Indikator
  Tool #16 Preis entscheidet: P/E und P/B relativ zum Universum
  Tool #24 Asset Quality: kein negativer FCF, kein extremer D/E

SCORING-PHILOSOPHIE:
  Kein absoluter Score=100 durch Summe — stattdessen Perzentil-Normalisierung
  nach Stufe-1-Pass: jeder Ticker bekommt seinen Rang im eigenen Universum.
  Zielgröße Top-Shortlist: 50 Titel (analog Options-Watchlist).
"""

import os
import json
import gzip
import glob
import logging
from datetime import datetime, timezone

log = logging.getLogger("aggregator")

VAL_VERSION      = "1.0"
FUNDAMENTALS_DIR = "data/fundamentals"
VAL_TOP_N        = 50      # Shortlist-Größe
VAL_MIN_MCAP     = 300_000_000   # $300M Market Cap Mindestgröße


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def _f(d, key, default=None):
    """Sicheres float-Cast aus dict."""
    v = d.get(key)
    if v is None: return default
    try:    return float(v)
    except: return default


def _load_latest_fin_archive() -> dict:
    """Lädt die neueste Wochen-Fundamentaldatei aus data/fundamentals/."""
    pattern = os.path.join(FUNDAMENTALS_DIR, "*.json.gz")
    files   = sorted(glob.glob(pattern))
    if not files:
        return {}
    latest = files[-1]
    try:
        with gzip.open(latest, 'rt') as f:
            data = json.load(f)
        log.info(f"  [VAL] FIN-Archiv geladen: {os.path.basename(latest)} "
                 f"({len(data.get('data', {}))} Ticker)")
        return data.get('data', {})
    except Exception as e:
        log.warning(f"  [VAL] FIN-Archiv Ladefehler ({latest}): {e}")
        return {}


# ── Stufe 1: Ausschluss-Gate ───────────────────────────────────────────────────

def _stufe1_pass(sym: str, t: dict) -> tuple[bool, str]:
    """
    Harte Mindestanforderungen — Ausschluss bei Verstoß.
    Gibt (True, '') oder (False, Grund) zurück.
    """
    mc  = _f(t, 'marketCap')
    gm  = _f(t, 'grossMargins')
    de  = _f(t, 'debtToEquity')
    fcf = _f(t, 'freeCashflow')

    # Mindest-Marktkapitalisierung
    if mc is None or mc < VAL_MIN_MCAP:
        return False, 'mcap_too_small'

    # Positive Bruttomarge (kein strukturelles Verlustgeschäft)
    if gm is None or gm <= 0:
        return False, 'negative_gross_margin'

    # Verschuldung nicht exzessiv (D/E < 200% als Grenze; Finanzsektor ausgenommen)
    sector = t.get('sector', '')
    if sector not in ('Financial Services', 'Real Estate'):
        if de is not None and de > 200:
            return False, 'excessive_debt'

    # Kein negativer FCF (wenn vorhanden — Datenlücken werden toleriert)
    if fcf is not None and fcf < 0:
        return False, 'negative_fcf'

    return True, ''


# ── Stufe 2: Value-Score (Carlin-inspiriert) ───────────────────────────────────

def _raw_value_score(t: dict) -> dict:
    """
    Berechnet 6 Dimensionen des Value-Scores als Rohdaten.
    Rückgabe: dict mit Einzelwerten für Normalisierung + Logging.
    """
    sector = t.get('sector', '')
    is_financial = sector in ('Financial Services', 'Real Estate')

    # D1: Bewertung — P/E (Carlin #16)
    pe = _f(t, 'trailingPE') or _f(t, 'forwardPE')
    if pe and pe < 0: pe = None  # neg. PE = Verlustjahr, kein Bewertungssignal

    # D2: Substanz — P/B (Graham-Erbe)
    pb = _f(t, 'priceToBook')
    if pb and pb < 0: pb = None

    # D3: Kapitalrendite — ROIC-Proxy (Carlin #7)
    roe = _f(t, 'returnOnEquity')
    de  = _f(t, 'debtToEquity') or 0
    roic_proxy = None
    if roe is not None:
        # ROIC-Proxy: ROE / (1 + D/E als Dezimal) — konservativ nach Carlin
        denominator = 1 + (de / 100) if de > 0 else 1
        roic_proxy = roe / denominator
        # Cap bei 50%: Extreme ROE durch Leverage/Einmaleffekte nicht übergewichten
        if roic_proxy is not None:
            roic_proxy = min(roic_proxy, 0.50)

    # D4: Wachstum — Revenue Growth (Carlin #8: Wachstum ist Teil von Value)
    rev_growth = _f(t, 'revenueGrowth')

    # D5: Cashflow-Qualität — FCF Yield (Carlin #10)
    fcf = _f(t, 'freeCashflow')
    mc  = _f(t, 'marketCap')
    fcf_yield = (fcf / mc) if (fcf and mc and mc > 0) else None

    # D6: Moat — Gross Margin (Carlin #12: Preismacht als Burggraben)
    gross_margin = _f(t, 'grossMargins')

    return {
        'pe':          pe,
        'pb':          pb,
        'roic_proxy':  roic_proxy,
        'rev_growth':  rev_growth,
        'fcf_yield':   fcf_yield,
        'gross_margin': gross_margin,
        'is_financial': is_financial,
    }


def _score_from_raw(raw: dict) -> float:
    """
    Wandelt Rohdaten in Punkte (vor Normalisierung).
    Additive Logik mit Malus — Zielbereich ca. -40 bis +130.
    """
    s = 0.0
    pe  = raw['pe']
    pb  = raw['pb']
    rp  = raw['roic_proxy']
    rg  = raw['rev_growth']
    fy  = raw['fcf_yield']
    gm  = raw['gross_margin']

    # D1 — Bewertung (P/E): günstig = mehr Punkte
    if pe is not None:
        if   pe < 10:  s += 30
        elif pe < 15:  s += 25
        elif pe < 20:  s += 18
        elif pe < 30:  s += 10
        elif pe < 40:  s +=  4
        else:          s -=  8   # teuer

    # D2 — Substanz (P/B)
    if pb is not None:
        if   pb < 1:   s += 25
        elif pb < 2:   s += 18
        elif pb < 3:   s += 12
        elif pb < 5:   s +=  6
        elif pb > 10:  s -=  8

    # D3 — ROIC-Proxy: Kapitaleffizienz (gedeckelt bei 50% durch _raw_value_score)
    if rp is not None:
        if   rp > 0.25:  s += 28   # 25-50%: exzellent (Cap greift)
        elif rp > 0.18:  s += 22
        elif rp > 0.12:  s += 16
        elif rp > 0.06:  s +=  9
        elif rp > 0:     s +=  3
        else:            s -= 15   # kapitalvernichtend

    # D4 — Wachstum (Revenue Growth)
    if rg is not None:
        if   rg > 0.25:  s += 22
        elif rg > 0.15:  s += 18
        elif rg > 0.05:  s += 12
        elif rg > 0:     s +=  6
        elif rg > -0.05: s +=  0
        else:            s -= 10   # schrumpfend

    # D5 — FCF Yield: Cashflow-Qualität
    if fy is not None:
        if   fy > 0.10:  s += 25
        elif fy > 0.05:  s += 18
        elif fy > 0.02:  s += 10
        elif fy > 0:     s +=  4

    # D6 — Gross Margin: Moat-Indikator
    if gm is not None:
        if   gm > 0.70:  s += 22
        elif gm > 0.50:  s += 18
        elif gm > 0.35:  s += 12
        elif gm > 0.20:  s +=  6
        else:            s -=  5

    return s


def _percentile_rank(value: float, sorted_vals: list) -> int:
    """Perzentil-Rang 0-99 (bisect, wie RS-Rating)."""
    import bisect
    if len(sorted_vals) < 2: return 50
    rank = bisect.bisect_left(sorted_vals, value)
    return round(rank / (len(sorted_vals) - 1) * 99)


# ── Stufe 3: Momentum-Brücke ───────────────────────────────────────────────────

def _momentum_score(sym: str, agg_map: dict) -> dict:
    """
    RS-Rating + Trendbestätigung aus dem Aggregator-Ergebnis.
    agg_map: {sym: result_dict} aus market_aggregator.results[]
    """
    r = agg_map.get(sym, {})
    rs    = r.get('rsRating')     # 0-99, Universum-Perzentil
    price = r.get('price')
    ema200= r.get('ema200')
    regime= r.get('regime', '')

    # Momentum-Bonus (0-30 Punkte)
    m = 0
    above_ema200 = (price and ema200 and price > ema200)

    if rs is not None:
        if   rs >= 70: m += 20
        elif rs >= 50: m += 12
        elif rs >= 30: m +=  4
        else:          m -=  8   # Kurs schwächer als 70% des Universums

    if above_ema200:
        m += 10   # Kurs über EMA200 = Trend dreht / intakt

    if 'BULL' in regime.upper():
        m += 5
    elif 'BEAR' in regime.upper():
        m -= 5

    return {
        'momentumBonus': m,
        'rsRating':      rs,
        'aboveEma200':   above_ema200,
        'regime':        regime,
    }


# ── Haupt-Einstiegspunkt ───────────────────────────────────────────────────────

def run(results: list) -> dict:
    """
    Haupt-Einstiegspunkt — wird von market_aggregator.main() aufgerufen.

    Args:
        results: Liste der Ticker-Dicts aus process_ticker() (mit rsRating, price, ema200).

    Returns:
        Status-Dict + Top-N-Shortlist für master["valueScanner"].
    """
    log.info(f"  [VAL] VAL-MOD v{VAL_VERSION} — Start")

    # FIN-Archiv laden
    fin = _load_latest_fin_archive()
    if not fin:
        return {'ok': False, 'reason': 'no_fin_archive', 'shortlist': []}

    # Aggregator-Ergebnisse als Lookup
    agg_map = {r['sym']: r for r in results if 'sym' in r}

    # ── Stufe 1: Ausschluss-Gate ──────────────────────────────────────────
    s1_candidates = []
    s1_rejected   = {}
    for sym, t in fin.items():
        passed, reason = _stufe1_pass(sym, t)
        if passed:
            s1_candidates.append((sym, t))
        else:
            s1_rejected[reason] = s1_rejected.get(reason, 0) + 1

    log.info(f"  [VAL] Stufe 1: {len(s1_candidates)}/{len(fin)} bestanden | "
             f"Ausschlüsse: {dict(sorted(s1_rejected.items(), key=lambda x: -x[1]))}")

    # ── Stufe 2: Value-Score ──────────────────────────────────────────────
    raw_scores = []
    for sym, t in s1_candidates:
        raw  = _raw_value_score(t)
        pts  = _score_from_raw(raw)
        raw_scores.append((sym, t, raw, pts))

    # Perzentil-Normalisierung über Stufe-1-Pass
    all_pts     = sorted(pts for _, _, _, pts in raw_scores)
    scored      = []
    for sym, t, raw, pts in raw_scores:
        val_rank = _percentile_rank(pts, all_pts)   # 0-99
        scored.append((sym, t, raw, pts, val_rank))

    # ── Stufe 3: Momentum-Brücke + Finale Sortierung ─────────────────────
    final = []
    for sym, t, raw, pts, val_rank in scored:
        mom   = _momentum_score(sym, agg_map)
        # Finaler Score: Value-Rang (Hauptgewicht) + Momentum-Bonus normiert
        # Momentum kann max ±15 Punkte auf 0-99-Skala verschieben
        mom_norm  = round(mom['momentumBonus'] / 30 * 15)   # -15 bis +15
        final_score = max(0, min(99, val_rank + mom_norm))

        # Wheel-Synergie: IV-Rank aus Aggregator wenn vorhanden
        agg_r = agg_map.get(sym, {})

        final.append({
            'sym':          sym,
            'finalScore':   final_score,
            'valRank':      val_rank,
            'valPts':       round(pts, 1),
            # Stufe-2-Dimensionen
            'pe':           round(raw['pe'], 1)          if raw['pe']          is not None else None,
            'pb':           round(raw['pb'], 2)          if raw['pb']          is not None else None,
            'roicProxy':    round(raw['roic_proxy']*100, 1) if raw['roic_proxy'] is not None else None,
            'revGrowth':    round(raw['rev_growth']*100, 1) if raw['rev_growth'] is not None else None,
            'fcfYield':     round(raw['fcf_yield']*100, 2)  if raw['fcf_yield']  is not None else None,
            'grossMargin':  round(raw['gross_margin']*100, 1) if raw['gross_margin'] is not None else None,
            # Stufe-3-Momentum
            'rsRating':     mom['rsRating'],
            'aboveEma200':  mom['aboveEma200'],
            'regime':       mom['regime'],
            'momentumBonus': mom['momentumBonus'],
            # Kontext
            'sector':       t.get('sector', ''),
            'marketCap':    t.get('marketCap'),
            'price':        agg_r.get('price'),
            # Wheel-Synergie-Vorbereitung (Carlin: Value-Kandidat → CSP prüfen)
            'ivRank':       agg_r.get('ivRank'),
            'hvp':          agg_r.get('hvp'),
            'wheelCandidate': (
                mom['rsRating'] is not None and mom['rsRating'] >= 50
                and mom['aboveEma200']
                and (agg_r.get('ivRank') or agg_r.get('hvp') or 0) >= 30
            ),
        })

    final.sort(key=lambda x: -x['finalScore'])
    shortlist = final[:VAL_TOP_N]

    # Wheel-Kandidaten zählen
    wheel_count = sum(1 for t in shortlist if t.get('wheelCandidate'))

    log.info(f"  [VAL] Stufe 2+3: {len(final)} gescort | "
             f"Top-{VAL_TOP_N} Shortlist | "
             f"{wheel_count} Wheel-Kandidaten")

    if shortlist:
        top3 = [f"{t['sym']}({t['finalScore']})" for t in shortlist[:3]]
        log.info(f"  [VAL] Top-3: {', '.join(top3)}")

    return {
        'ok':           True,
        'version':      VAL_VERSION,
        'finWeek':      _latest_fin_week(),
        'universe':     len(fin),
        'stufe1Pass':   len(s1_candidates),
        'scored':       len(final),
        'shortlist':    shortlist,
        'wheelCount':   wheel_count,
    }


def _latest_fin_week() -> str:
    """Gibt den Dateinamen der neuesten FIN-Archiv-Datei zurück."""
    pattern = os.path.join(FUNDAMENTALS_DIR, "*.json.gz")
    files   = sorted(glob.glob(pattern))
    return os.path.basename(files[-1]).replace('.json.gz', '') if files else 'unknown'
