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

UIQ-UNIVERSUM-ERWEITERUNG (automatisch, samstags):
  Neue Value-Kandidaten aus dem Russell3000-Scan, die noch nicht im UIQ-Universum
  sind, werden automatisch in den KV-Key 'approved_extra_tickers' geschrieben.
  Bedingungen: finalScore >= VAL_UIQ_PROMOTE_THRESHOLD, nicht bereits im UIQ-Scan,
  ValRank >= 85 (Top-15% der Fundamental-Qualität).
  Beim nächsten Mo-Nachtlauf werden sie von fetch_approved_extra_tickers() gelesen
  und sind dann vollständig im Scan-Universum mit RS-Rating, IV, Technischen Daten.
"""

import os
import json
import gzip
import glob
import logging
import requests
from datetime import datetime, timezone

log = logging.getLogger("aggregator")

VAL_VERSION             = "1.3"
FUNDAMENTALS_DIR        = "data/fundamentals"
VAL_TOP_N               = 50      # Shortlist-Größe
VAL_MIN_MCAP            = 300_000_000   # $300M Market Cap Mindestgröße
VAL_UIQ_PROMOTE_THRESH  = 85     # finalScore-Schwelle für UIQ-Universum-Aufnahme
VAL_UIQ_PROMOTE_VAL_MIN = 85     # valRank-Mindest (Top-15% Fundamentalqualität)
VAL_UIQ_PROMOTE_MAX     = 20     # max. neue Ticker pro Samstags-Lauf


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
    pb  = _f(t, 'priceToBook')

    # Nur US-Ticker: kein Punkt im Symbol (VOD.L, BHP.AX etc.)
    if '.' in sym:
        return False, 'non_us_ticker'

    # Mindest-Marktkapitalisierung
    if mc is None or mc < VAL_MIN_MCAP:
        return False, 'mcap_too_small'

    # P/B-Plausibilitäts-Cap: > 50 = Datenfehler (ADR-Buchwert-Umrechnung etc.)
    if pb is not None and pb > 50:
        return False, 'pb_data_error'

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
        elif rg > -0.15: s -= 10   # leicht schrumpfend
        else:            s -= 18   # strukturell schrumpfend (Carlin: Value Trap Risiko)

    # D5 — FCF Yield: Cashflow-Qualität (Cap bei 50%: Einmal-Spikes nicht übergewichten)
    if fy is not None:
        fy_capped = min(fy, 0.50)
        if   fy_capped > 0.10:  s += 25
        elif fy_capped > 0.05:  s += 18
        elif fy_capped > 0.02:  s += 10
        elif fy_capped > 0:     s +=  4

    # D6 — Gross Margin: Moat-Indikator
    if gm is not None:
        if   gm > 0.70:  s += 22
        elif gm > 0.50:  s += 18
        elif gm > 0.35:  s += 12
        elif gm > 0.20:  s +=  6
        else:            s -=  5

    return s


def _enrich_rs_yfinance(syms: list) -> dict:
    """
    Lädt Kursdaten für Russell3000-only Titel (nicht im UIQ-Scan) via yfinance
    und berechnet RS-Rating analog zum Aggregator-Verfahren:
    - Gewichtete 12M-Performance (IBD-Annäherung: 0.4×3M + 0.2×6M + 0.2×9M + 0.2×12M)
    - Rang im eigenen Mini-Universum (die enrichten Titel untereinander)
    - EMA200-Lage als Trendindikator

    Beschränkt auf max. 100 Ticker um Laufzeit zu begrenzen (~30s extra).
    Gibt {sym: {rsRating, perf3m, perf6m, perf12m, price, aboveEma200}} zurück.
    """
    import bisect as _bisect
    try:
        import yfinance as yf
    except ImportError:
        log.warning("  [VAL-Enrich] yfinance nicht verfügbar")
        return {}

    syms = syms[:100]   # Hard-Cap: max 100 Ticker pro Lauf
    log.info(f"  [VAL-Enrich] Lade {len(syms)} Ticker via yfinance batch...")

    try:
        # Batch-Download: 1 Jahr Tagesdaten
        raw = yf.download(
            syms, period="1y", interval="1d",
            auto_adjust=True, progress=False, threads=True
        )
        close_df = raw["Close"] if "Close" in raw else raw
    except Exception as e:
        log.warning(f"  [VAL-Enrich] yfinance batch fehlgeschlagen: {e}")
        return {}

    # RS-Rohwerte berechnen
    raw_scores = {}
    results_data = {}

    for sym in syms:
        try:
            if sym not in close_df.columns:
                continue
            closes = list(close_df[sym].dropna())
            if len(closes) < 63:   # mind. 3 Monate
                continue

            price = closes[-1]

            # Periodische Performance
            p3m  = (closes[-1] / closes[-63]  - 1) * 100 if len(closes) >= 63  else None
            p6m  = (closes[-1] / closes[-126] - 1) * 100 if len(closes) >= 126 else None
            p9m  = (closes[-1] / closes[-189] - 1) * 100 if len(closes) >= 189 else None
            p12m = (closes[-1] / closes[-252] - 1) * 100 if len(closes) >= 252 else None

            # Gewichteter Rohwert (wie Aggregator)
            if p6m is None:
                continue
            weights = [(0.4, p3m), (0.2, p6m), (0.2, p9m), (0.2, p12m)]
            wsum = wdiv = 0.0
            for w, v in weights:
                if v is not None:
                    wsum += w * v
                    wdiv += w
            rs_raw = wsum / wdiv if wdiv > 0 else None

            # EMA200
            if len(closes) >= 200:
                k = 2 / 201
                ema200 = sum(closes[:200]) / 200
                for c in closes[200:]:
                    ema200 = c * k + ema200 * (1 - k)
                above_ema200 = price > ema200
            else:
                above_ema200 = None

            raw_scores[sym]  = rs_raw
            results_data[sym] = {
                'price':       round(price, 2),
                'perf3m':      round(p3m,  2) if p3m  is not None else None,
                'perf6m':      round(p6m,  2) if p6m  is not None else None,
                'perf12m':     round(p12m, 2) if p12m is not None else None,
                'aboveEma200': above_ema200,
                'rsRaw':       round(rs_raw, 4) if rs_raw is not None else None,
            }
        except Exception as _e:
            log.debug(f"  [VAL-Enrich] {sym}: {_e}")
            continue

    # Perzentil-Ranking im Mini-Universum der enrichten Titel
    if len(raw_scores) >= 2:
        sorted_vals = sorted(raw_scores.values())
        n = len(sorted_vals)
        for sym, raw_val in raw_scores.items():
            rank = _bisect.bisect_left(sorted_vals, raw_val)
            rs_rating = round(rank / (n - 1) * 99) if n > 1 else 50
            results_data[sym]['rsRating'] = rs_rating
    elif raw_scores:
        sym = next(iter(raw_scores))
        results_data[sym]['rsRating'] = 50

    log.info(f"  [VAL-Enrich] {len(results_data)}/{len(syms)} Ticker enriched")
    return results_data


def _percentile_rank(value: float, sorted_vals: list) -> int:
    """Perzentil-Rang 0-99 (bisect, wie RS-Rating)."""
    import bisect
    if len(sorted_vals) < 2: return 50
    rank = bisect.bisect_left(sorted_vals, value)
    return round(rank / (len(sorted_vals) - 1) * 99)


# ── Stufe 3: Momentum-Brücke ───────────────────────────────────────────────────

def _momentum_score(sym: str, agg_map: dict) -> dict:
    """
    RS-Rating + Trendbestätigung + vollständige UIQ-Felder aus dem Aggregator.
    agg_map: {sym: result_dict} aus market_aggregator.results[]
    Für Russell3000-only Ticker (nicht im UIQ-Universum): rs=None, Fallback-Bonus=0.
    """
    r = agg_map.get(sym, {})
    rs    = r.get('rsRating')
    price = r.get('price')
    ema200= r.get('ema200')
    regime= r.get('regime', '')

    # Momentum-Bonus (0-30 Punkte)
    m = 0
    above_ema200 = bool(price and ema200 and price > ema200)

    if rs is not None:
        if   rs >= 70: m += 20
        elif rs >= 50: m += 12
        elif rs >= 30: m +=  4
        else:          m -=  8

    if above_ema200:
        m += 10

    if 'BULL' in regime.upper():   m += 5
    elif 'BEAR' in regime.upper(): m -= 5

    return {
        'momentumBonus':  m,
        'rsRating':       rs,
        'aboveEma200':    above_ema200,
        'regime':         regime,
        # ── Vollständige UIQ-Felder (nur wenn Ticker im Scan-Universum) ──
        'rsi':            r.get('rsi'),
        'hvp':            r.get('hvp'),
        'ivAtm':          r.get('ivAtm'),
        'ivRank':         r.get('ivRank'),
        'ivPercentile':   r.get('ivPercentile'),
        'ivArchiveDays':  r.get('ivArchiveDays'),
        'atr':            r.get('atr'),
        'dist200':        r.get('dist200'),
        'pctFromHigh52':  r.get('pctFromHigh52'),
        'ema200SlopeUp':  r.get('ema200SlopeUp'),
        'overheat':       r.get('overheat'),
        'squeezeRisk':    r.get('squeezeRisk'),
        'sMinervini':     r.get('sMinervini'),
        'scoreCsp':       r.get('scoreCsp'),        # aus Options-WL wenn vorhanden
        'scoreCc':        r.get('scoreCc'),
        'grade':          r.get('grade'),
        'perf3m':         r.get('perf3m'),
        'perf6m':         r.get('perf6m'),
        'perf12m':        r.get('perf12m'),
        'macdHist':       r.get('macdHist'),
        'bbPos':          r.get('bbPos'),
        'inUiqUniverse':  bool(r),                  # True wenn im UIQ-Scan
    }


# ── UIQ-Universum-Erweiterung ─────────────────────────────────────────────────

def _kv_creds():
    """KV-Credentials aus Umgebungsvariablen (analog fin_layer)."""
    a = os.environ.get("CF_ACCOUNT_ID")
    t = os.environ.get("CF_API_TOKEN")
    n = os.environ.get("CF_KV_NS_ID")
    return (a, t, n) if all([a, t, n]) else None


def _promote_to_uiq_universe(shortlist: list, uiq_syms: set) -> dict:
    """
    Identifiziert Value-Top-Kandidaten die noch nicht im UIQ-Scan-Universum sind
    und schreibt sie in den KV-Key 'approved_extra_tickers'.

    Auswahlkriterien (konservativ — Qualität vor Quantität):
      - inUiqUniverse == False  (noch nicht im Scan)
      - finalScore >= VAL_UIQ_PROMOTE_THRESH  (starke Gesamt-Bewertung)
      - valRank >= VAL_UIQ_PROMOTE_VAL_MIN    (Top-15% Fundamental-Qualität)
      - rsRating != None                       (RS-Enrichment hat funktioniert)
      - Max. VAL_UIQ_PROMOTE_MAX Ticker pro Lauf (verhindert Universum-Inflation)

    Bestehende approved_extra_tickers werden gelesen, neue Ticker werden
    hinzugefügt (keine Duplikate, kein Überschreiben bestehender Einträge).

    Rückgabe: {'promoted': [...], 'total_in_kv': N, 'skipped': N}
    """
    creds = _kv_creds()
    if not creds:
        return {'ok': False, 'reason': 'no_kv_credentials', 'promoted': []}

    account_id, api_token, ns_id = creds
    kv_url    = (f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
                 f"/storage/kv/namespaces/{ns_id}/values/approved_extra_tickers")
    headers   = {"Authorization": f"Bearer {api_token}",
                 "Content-Type": "application/json"}

    # Kandidaten filtern
    candidates = [
        t for t in shortlist
        if not t.get('inUiqUniverse', True)
        and t.get('finalScore', 0)  >= VAL_UIQ_PROMOTE_THRESH
        and t.get('valRank', 0)     >= VAL_UIQ_PROMOTE_VAL_MIN
        and t.get('rsRating') is not None   # RS-Enrichment muss geklappt haben
    ][:VAL_UIQ_PROMOTE_MAX]

    if not candidates:
        log.info("  [VAL-Promote] Keine neuen Kandidaten für UIQ-Universum-Erweiterung")
        return {'ok': True, 'promoted': [], 'total_in_kv': 0, 'skipped': 0}

    # Bestehende KV-Einträge lesen (Merge, kein Überschreiben)
    existing = []
    existing_syms = set()
    try:
        r = requests.get(kv_url, headers={"Authorization": f"Bearer {api_token}"},
                         timeout=15)
        if r.status_code == 200:
            existing = r.json() if isinstance(r.json(), list) else []
            existing_syms = {e.get('sym') for e in existing if isinstance(e, dict)}
    except Exception as _e:
        log.warning(f"  [VAL-Promote] KV-Lesen fehlgeschlagen: {_e} — fahre fort")

    # Neue Einträge aufbauen
    promoted = []
    skipped  = 0
    for t in candidates:
        sym = t['sym']
        if sym in existing_syms:
            skipped += 1
            continue
        entry = {
            'sym':        sym,
            'source':     'val_mod_auto',          # Herkunft klar kennzeichnen
            'addedDate':  datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'valRank':    t.get('valRank'),
            'finalScore': t.get('finalScore'),
            'rsRating':   t.get('rsRating'),
            'sector':     t.get('sector', ''),
            'pe':         t.get('pe'),
            'grossMargin': t.get('grossMargin'),
            'reason':     (f"VAL-MOD Top-Kandidat: Score={t.get('finalScore')} "
                           f"ValRank={t.get('valRank')} RS={t.get('rsRating')} "
                           f"PE={t.get('pe')} GM={t.get('grossMargin')}%"),
        }
        existing.append(entry)
        promoted.append(sym)

    if not promoted:
        log.info(f"  [VAL-Promote] Alle {len(candidates)} Kandidaten bereits in KV")
        return {'ok': True, 'promoted': [], 'total_in_kv': len(existing), 'skipped': skipped}

    # In KV schreiben
    try:
        r = requests.put(kv_url, headers=headers,
                         data=json.dumps(existing), timeout=15)
        if r.status_code in (200, 201):
            log.info(f"  [VAL-Promote] ✅ {len(promoted)} neue Ticker ins UIQ-Universum: "
                     f"{', '.join(promoted)}")
            return {
                'ok':         True,
                'promoted':   promoted,
                'total_in_kv': len(existing),
                'skipped':    skipped,
            }
        else:
            log.warning(f"  [VAL-Promote] KV-Schreiben fehlgeschlagen: HTTP {r.status_code}")
            return {'ok': False, 'reason': f'kv_write_{r.status_code}', 'promoted': []}
    except Exception as _e:
        log.warning(f"  [VAL-Promote] KV-Schreiben Exception: {_e}")
        return {'ok': False, 'reason': str(_e), 'promoted': []}


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

        # Wheel-Synergie: IV-Rank oder HVP als Proxy
        iv_signal = mom.get('ivRank') or mom.get('hvp') or 0
        wheel = (
            mom['rsRating'] is not None and mom['rsRating'] >= 50
            and mom['aboveEma200']
            and iv_signal >= 30
        )

        final.append({
            'sym':          sym,
            'finalScore':   final_score,
            'valRank':      val_rank,
            'valPts':       round(pts, 1),
            # Stufe-2-Dimensionen (Fundamental)
            'pe':           round(raw['pe'], 1)               if raw['pe']           is not None else None,
            'pb':           round(raw['pb'], 2)               if raw['pb']           is not None else None,
            'roicProxy':    round(raw['roic_proxy']*100, 1)   if raw['roic_proxy']   is not None else None,
            'revGrowth':    round(raw['rev_growth']*100, 1)   if raw['rev_growth']   is not None else None,
            'fcfYield':     round(raw['fcf_yield']*100, 2)    if raw['fcf_yield']    is not None else None,
            'grossMargin':  round(raw['gross_margin']*100, 1) if raw['gross_margin'] is not None else None,
            # Stufe-3-Momentum (aus UIQ-Scan wenn verfügbar)
            'rsRating':     mom['rsRating'],
            'aboveEma200':  mom['aboveEma200'],
            'regime':       mom['regime'],
            'momentumBonus': mom['momentumBonus'],
            'inUiqUniverse': mom['inUiqUniverse'],
            # UIQ-Technische Felder (nur wenn im Scan-Universum, sonst None)
            'rsi':          mom.get('rsi'),
            'hvp':          mom.get('hvp'),
            'ivAtm':        mom.get('ivAtm'),
            'ivRank':       mom.get('ivRank'),
            'ivPercentile': mom.get('ivPercentile'),
            'ivArchiveDays': mom.get('ivArchiveDays'),
            'atr':          mom.get('atr'),
            'dist200':      mom.get('dist200'),
            'pctFromHigh52': mom.get('pctFromHigh52'),
            'ema200SlopeUp': mom.get('ema200SlopeUp'),
            'overheat':     mom.get('overheat'),
            'squeezeRisk':  mom.get('squeezeRisk'),
            'sMinervini':   mom.get('sMinervini'),
            'grade':        mom.get('grade'),
            'perf3m':       mom.get('perf3m'),
            'perf6m':       mom.get('perf6m'),
            'perf12m':      mom.get('perf12m'),
            'macdHist':     mom.get('macdHist'),
            'bbPos':        mom.get('bbPos'),
            # Kontext
            'sector':       t.get('sector', ''),
            'industry':     t.get('industry', ''),
            'marketCap':    t.get('marketCap'),
            'price':        agg_r.get('price') or t.get('regularMarketPrice'),
            # Wheel-Synergie (Carlin: Value-Kandidat → CSP prüfen)
            'ivSignal':     iv_signal,
            'wheelCandidate': wheel,
        })

    # ── RS-Enrichment für Russell3000-only Titel (nicht im UIQ-Universum) ──────
    # Für die Top-N*2 Kandidaten ohne rsRating: Kursdaten via yfinance nachladen
    # und RS-Rating berechnen (Vergleich mit SPY, 3M-Performance).
    # Beschränkt auf Top-Kandidaten (Rohscore-Ranking) um API-Calls zu minimieren.
    final.sort(key=lambda x: -x['valPts'])   # vorläufige Sortierung nach Val-Rohpunkten
    no_rs_syms = [e['sym'] for e in final[:VAL_TOP_N*2] if e.get('rsRating') is None]

    if no_rs_syms:
        log.info(f"  [VAL] RS-Enrichment: {len(no_rs_syms)} Russell3000-only Ticker nachladen...")
        enriched_rs = _enrich_rs_yfinance(no_rs_syms)
        # Ergebnisse in final[] einschreiben
        enrich_map = {sym: rd for sym, rd in enriched_rs.items()}
        for e in final:
            if e['sym'] in enrich_map:
                rd = enrich_map[e['sym']]
                e['rsRating']    = rd.get('rsRating')
                e['perf3m']      = rd.get('perf3m')
                e['perf6m']      = rd.get('perf6m')
                e['perf12m']     = rd.get('perf12m')
                e['price']       = e['price'] or rd.get('price')
                e['aboveEma200'] = rd.get('aboveEma200', False)
                e['inUiqUniverse'] = False   # bleibt False — nur RS-Enrichment
                # Momentum-Bonus neu berechnen mit frischem RS-Rating
                rs = rd.get('rsRating')
                m  = e.get('momentumBonus', 0)
                if rs is not None:
                    if   rs >= 70: m = max(m, 12)
                    elif rs >= 50: m = max(m, 6)
                    elif rs <  30: m = min(m, -4)
                if rd.get('aboveEma200'): m += 5
                e['momentumBonus'] = m
                # finalScore aktualisieren
                mom_norm = round(m / 30 * 15)
                e['finalScore'] = max(0, min(99, e['valRank'] + mom_norm))
                # Wheel-Kandidat neu prüfen
                iv_signal = e.get('ivSignal', 0)
                e['wheelCandidate'] = (rs is not None and rs >= 50
                                       and e['aboveEma200'] and iv_signal >= 30)
        log.info(f"  [VAL] RS-Enrichment: {len(enriched_rs)} erfolgreich")

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

    # ── UIQ-Universum-Erweiterung (samstags, nach FIN-Archiv-Merge) ──────────
    # Samstag = Wochentag 5. Nur dann promoten um Universum-Inflation zu vermeiden.
    # Täglich würden immer dieselben Kandidaten erneut geprüft (KV-Read schützt
    # vor Duplikaten, aber der Log wäre noisig). Samstag ist nach dem Merge, wenn
    # die Fundamentaldaten frisch sind.
    promote_status = {'ok': False, 'reason': 'not_saturday', 'promoted': []}
    from datetime import datetime, timezone
    if datetime.now(timezone.utc).weekday() == 5:   # 5 = Samstag
        uiq_syms = {r['sym'] for r in results}
        promote_status = _promote_to_uiq_universe(shortlist, uiq_syms)
        log.info(f"  [VAL-Promote] Status: {promote_status}")
    else:
        log.info(f"  [VAL-Promote] Nicht Samstag — Universum-Erweiterung übersprungen")

    return {
        'ok':           True,
        'version':      VAL_VERSION,
        'finWeek':      _latest_fin_week(),
        'universe':     len(fin),
        'stufe1Pass':   len(s1_candidates),
        'scored':       len(final),
        'shortlist':    shortlist,
        'wheelCount':   wheel_count,
        'promote':      promote_status,
    }


def _latest_fin_week() -> str:
    """Gibt den Dateinamen der neuesten FIN-Archiv-Datei zurück."""
    pattern = os.path.join(FUNDAMENTALS_DIR, "*.json.gz")
    files   = sorted(glob.glob(pattern))
    return os.path.basename(files[-1]).replace('.json.gz', '') if files else 'unknown'
