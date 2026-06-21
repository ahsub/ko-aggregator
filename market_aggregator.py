#!/usr/bin/env python3
"""
KO-Scanner Market Aggregator v2.0
==================================
Zentraler Daten-Aggregator für die KO-Scanner Investment Suite.
Läuft als GitHub Actions Cron-Job (täglich 22:15 UTC nach US-Schluss).
Version 2.0: DE-Märkte (DAX40, MDAX, TecDAX, EuroStoxx), Sektor-Watchlisten,
robustes Datenladen mit Fallback-Perioden.

Ablauf:
  1. Lädt OHLCV-Daten für alle ~600 Ticker via yfinance (parallel)
  2. Berechnet technische Indikatoren (EMA, RSI, MACD, OBV, ATR, BB)
  3. Berechnet Markov 2.0 Regime-Signale
  4. Berechnet Composite Score (A+ bis F)
  5. Lädt echte DIX/GEX von squeezemetrics (wenn verfügbar)
  6. Lädt echten PCR von CBOE
  7. Pusht master_market_data.json → Cloudflare KV

Umgebungsvariablen (GitHub Secrets):
  CF_ACCOUNT_ID   — Cloudflare Account ID
  CF_API_TOKEN    — Cloudflare API Token (KV Write)
  CF_KV_NS_ID     — Cloudflare KV Namespace ID (ko-sync)
"""

import os
import json
import time
import math
import logging
import requests
import numpy as np
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# yfinance für Marktdaten
try:
    import yfinance as yf
except ImportError:
    os.system("pip install yfinance --quiet")
    import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("aggregator")

# ── TICKER UNIVERSUM ──────────────────────────────────────────────────────────

SP500_TICKERS = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","JPM","LLY",
    "UNH","XOM","V","MA","COST","PG","HD","JNJ","ORCL","MRK","ABBV","BAC",
    "NFLX","WMT","AMD","KO","CRM","PEP","TMO","CVX","MCD","CSCO","ADBE",
    "ABT","ACN","DHR","LIN","INTC","WFC","TXN","NEE","PM","HON","AMGN",
    "IBM","CAT","UPS","RTX","GS","INTU","SPGI","BLK","SYK","GILD","MDT",
    "LOW","AXP","REGN","ISRG","VRTX","PLD","ELV","MO","C","CVS","ADP",
    "TJX","SCHW","NOW","ZTS","BKNG","DE","DUK","SO","TGT","BSX","CI",
    "AON","MMC","SHW","CME","CB","ITW","HUM","MCO","COP","EOG","SLB",
    "BDX","KLAC","LRCX","SNPS","CDNS","MCHP","ADI","AMAT","MU","QCOM",
    "PANW","CRWD","FTNT","DDOG","SNOW","PLTR","UBER","ABNB","LYFT","SQ",
    "SHOP","MELI","SE","GRAB","COIN","RBLX","HOOD","SOFI","AFRM","UPST",
    "GLW","TXN","MRVL","MSTR","SMCI","ARM","ASML","TSM","SAMSUNG","BABA",
    "JD","PDD","NIO","XPEV","LI","BIDU","NTES","TCOM","TIGR","FUTU",
    "RIVN","LCID","F","GM","STLA","TM","HMC","VOW3.DE","BMW.DE","MBG.DE",
    "GE","GEV","BA","LMT","RTX","NOC","GD","HII","TDG","HWM","SPR",
    "AMSC","ENPH","FSLR","SEDG","RUN","ARRY","NOVA","BE","PLUG","BLDP",
    "UNP","CSX","NSC","CP","CNI","WAB","TT","CARR","OTIS","JCI","EMR",
    "ROK","AME","LDOS","SAIC","CACI","BAH","KTOS","AXON","TNET","HUBS",
    "TEAM","ZM","DOCU","BOX","DBX","TWLO","DDOG","MDB","ESTC","CFLT",
    "NET","ZS","OKTA","S","SAIL","CYBER","HACK","BUG","CIBR",
    "ALV.DE","SAP.DE","SIE.DE","RHM.DE","DTE.DE","BAYN.DE","ADS.DE",
    "DBK.DE","MUV2.DE","BAS.DE","HEN3.DE","MRK.DE","HAG.DE","EOAN.DE",
    "IFX.DE","MTX.DE","CBK.DE","HNR1.DE","VOW3.DE","BMW.DE",
]

NASDAQ100_EXTRA = [
    "ADSK","ANSS","BIIB","CHTR","CPRT","CTAS","DLTR","EBAY","EXC","FAST",
    "FANG","IDXX","ILMN","KDP","KHC","LULU","MAR","MELI","MNST","MRNA",
    "MTCH","NXPI","ODFL","PAYX","PCAR","PDD","ROST","SBUX","SIRI","TMUS",
    "VRSK","VRSN","WDAY","XEL","ZS",
]

# ── DEUTSCHE MÄRKTE ───────────────────────────────────────────────────────────
DAX40_TICKERS = [
    "ADS.DE","AIR.DE","ALV.DE","BAS.DE","BAYN.DE","BMW.DE","BNR.DE",
    "CBK.DE","CON.DE","1COV.DE","DBK.DE","DB1.DE","DHL.DE","DTE.DE",
    "EOAN.DE","FRE.DE","HEI.DE","HEN3.DE","IFX.DE","INL.DE","LIN.DE",
    "MBG.DE","MRK.DE","MTX.DE","MUV2.DE","P911.DE","PAH3.DE","PUMA.DE",
    "QIA.DE","RHM.DE","RWE.DE","SAP.DE","SHL.DE","SIE.DE","SY1.DE",
    "VNA.DE","VOW3.DE","ZAL.DE","ENR.DE","DHER.DE",
]

MDAX_TICKERS = [
    "AFX.DE","AG1.DE","AIXA.DE","ARND.DE","BC8.DE","BOSS.DE","COP.DE",
    "CSCO.DE","DEQ.DE","DWS.DE","EVD.DE","EVK.DE","FNTN.DE","GFK.DE",
    "HAG.DE","HHFA.DE","HNR1.DE","HOT.DE","JEN.DE","KGX.DE","KSB.DE",
    "LEG.DE","MDNT.DE","NDA.DE","NOEJ.DE","O2D.DE","PBB.DE","PSM.DE",
    "SDAX.DE","SFQ.DE","SGL.DE","SKB.DE","SLT.DE","SMT.DE","STRN.DE",
    "SY1.DE","TAG.DE","TLX.DE","TUI1.DE","UTDI.DE","WAF.DE","WCH.DE",
]

TECDAX_TICKERS = [
    "AIXA.DE","ARND.DE","BB1.DE","CSCO.DE","EVNT.DE","FNTN.DE","IFX.DE",
    "INH.DE","KNEBV.HE","NDX1.DE","NFON.DE","NTT.DE","PFV.DE","PSM.DE",
    "QIAGEN.DE","RIB.DE","S92.DE","SAP.DE","SFQ.DE","SHL.DE","SIE.DE",
    "SOW.DE","SRT3.DE","TPVG.DE","UTDI.DE","WAF.DE","WIB.DE","ZAL.DE",
]

EUROSTOXX_TICKERS = [
    "ASML.AS","SAN.MC","OR.PA","MC.PA","SU.PA","BNP.PA","AIR.PA",
    "DG.PA","RI.PA","CS.PA","SAP.DE","SIE.DE","ALV.DE","MBG.DE",
    "PHIA.AS","ING.AS","RDSA.AS","ABN.AS","NN.AS","ADYEN.AS",
    "ENI.MI","ENEL.MI","ISP.MI","UCG.MI","TIT.MI","STM.MI",
    "NOVN.SW","ROG.SW","NESN.SW","AZN.L","SHEL.L","HSBA.L",
]

# ── SEKTOR-WATCHLISTEN ────────────────────────────────────────────────────────
SECTOR_WATCHLISTS = {
    "AI_TECH":      ["NVDA","AMD","MSFT","GOOGL","META","PLTR","ARM","SMCI","MSTR","NET"],
    "SEMIS":        ["NVDA","AMD","AVGO","QCOM","TXN","AMAT","LRCX","KLAC","MU","ASML"],
    "DEFENSE":      ["LMT","RTX","NOC","GD","BA","KTOS","AXON","HII","TDG","RHM.DE"],
    "BIOTECH":      ["MRNA","BNTX","REGN","VRTX","GILD","BIIB","ILMN","ARKG","ABBV","LLY"],
    "CLEAN_ENERGY": ["ENPH","FSLR","SEDG","RUN","BE","PLUG","NEE","ARRY","NOVA","BLDP"],
    "FINTECH":      ["SQ","HOOD","AFRM","SOFI","UPST","COIN","PYPL","V","MA","SCHW"],
    "GLPONE":       ["LLY","NVO","VKTX","RYTM","AMGN","REGN","AZN","SNY","GILD","PFE"],
    "PICKS_SHOVELS":["NVDA","AMD","AVGO","AMAT","LRCX","TSM","ARM","KLAC","SNPS","CDNS"],
    "WHEEL_STOCKS": ["DDOG","AMSC","IREN","CIFR","PBR","CLSK","NVO","HOOD","ENVX","MRVL"],
}

SECTOR_ETFS = [
    "SPY","QQQ","IWM","DIA","VTI","VEA","VWO","EFA",
    "XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLRE","XLB","XLC",
    "SMH","SOXX","IGV","HACK","CIBR","ARKK","ARKG","ARKW","ARKF",
    "GLD","SLV","USO","UNG","PDBC",
    "TLT","IEF","SHY","HYG","LQD","EMB","BND",
    "VNQ","REET","IYR",
    "EWJ","EWG","EWU","EWC","EWA","EWZ","FXI","KWEB","MCHI",
    "IAU","GLDM","BAR",
    "XBI","IBB","ARKG",
    "BOTZ","ROBO","IRBO","AIQ",
]

CRYPTO_TICKERS = [
    "BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD",
    "ADA-USD","AVAX-USD","DOGE-USD","DOT-USD","MATIC-USD",
]

# ── FTSE ALL-WORLD TIER-1 (NYSE/Nasdaq ADRs) ─────────────────────────────────
# Größte Nicht-US Titel mit echten US-Listings — gute Datenqualität
INTL_TIER1 = [
    # Europa — Technologie & Halbleiter
    "ASML","STM","ERIC","NOK","SAP",
    # Europa — Healthcare & Pharma
    "NVO","AZN","NOVN","ROG","SNY","GSK","BAYRY",
    # Europa — Energie & Industrie
    "SHEL","BP","TTE","ENEL","ENI",
    # Europa — Finanzen
    "UBS","CS","ING","INGA","BCS","HSBC",
    # Europa — Konsum & Luxus
    "LVMUY","CFRUY","ALIZF","PPRUY",
    # Asien — Technologie
    "TSM","2330.TW","Samsung","005930.KS",
    # Asien — Konsum & E-Commerce
    "BABA","JD","PDD","BIDU","9988.HK",
    # Japan
    "TM","HMC","SONY","NTT","MUFG","SoftBank",
    # Kanada & Australien
    "SHOP","CNQ","SU","BHP","RIO",
    # Schwellenländer Blue Chips
    "VALE","PBR","ITUB","BBD",
]

# Sektor-ETFs für Relative-Stärke Berechnung (vs. SPY)
RS_SECTOR_ETFS = [
    "XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLRE","XLB","XLC",
    "SMH","SOXX","IBB","XBI","ARKK",
]

def build_ticker_universe():
    seen = set()
    result = []
    # Alle Quellen zusammenführen
    all_sources = (
        SP500_TICKERS + NASDAQ100_EXTRA +
        DAX40_TICKERS + MDAX_TICKERS + TECDAX_TICKERS + EUROSTOXX_TICKERS +
        INTL_TIER1 + SECTOR_ETFS + CRYPTO_TICKERS +
        [t for wl in SECTOR_WATCHLISTS.values() for t in wl]
    )
    for t in all_sources:
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result

# ── TECHNISCHE INDIKATOREN ────────────────────────────────────────────────────

def ema(series, period):
    """Exponentiell gewichteter Durchschnitt."""
    k = 2.0 / (period + 1)
    result = [None] * len(series)
    # Initialisierung mit einfachem Durchschnitt
    valid_start = None
    for i, v in enumerate(series):
        if v is not None:
            valid_start = i
            break
    if valid_start is None:
        return result
    # Erster EMA = SMA der ersten `period` Werte
    if len([v for v in series[valid_start:valid_start+period] if v is not None]) < period:
        return result
    sma_vals = [v for v in series[valid_start:valid_start+period] if v is not None]
    result[valid_start + period - 1] = sum(sma_vals) / len(sma_vals)
    for i in range(valid_start + period, len(series)):
        if series[i] is not None and result[i-1] is not None:
            result[i] = series[i] * k + result[i-1] * (1 - k)
    return result

def sma(series, period):
    result = [None] * len(series)
    for i in range(period - 1, len(series)):
        window = [v for v in series[i-period+1:i+1] if v is not None]
        if len(window) == period:
            result[i] = sum(window) / period
    return result

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i-1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    if len(gains) < period:
        return None
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        trs.append(tr)
    if len(trs) < period:
        return None
    return round(sum(trs[-period:]) / period, 4)

def calc_macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = []
    for f, s in zip(ema_fast, ema_slow):
        macd_line.append(f - s if f is not None and s is not None else None)
    valid_macd = [v for v in macd_line if v is not None]
    if len(valid_macd) < signal:
        return None, None, None
    signal_line = ema(valid_macd, signal)
    if not signal_line or signal_line[-1] is None:
        return None, None, None
    macd_val    = valid_macd[-1]
    signal_val  = signal_line[-1]
    hist_val    = macd_val - signal_val
    return round(macd_val, 4), round(signal_val, 4), round(hist_val, 4)

def calc_obv_trend(closes, volumes, days=5):
    """OBV-Trend über `days` Bars. Positiv = bullisch."""
    if len(closes) < days + 1 or len(volumes) < days + 1:
        return None
    obv = 0
    obvs = [0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            obv += volumes[i]
        elif closes[i] < closes[i-1]:
            obv -= volumes[i]
        obvs.append(obv)
    if len(obvs) < days + 1:
        return None
    trend = obvs[-1] - obvs[-(days+1)]
    return trend

def calc_bb(closes, period=20, std_dev=2):
    """Bollinger Band Position (0-1)."""
    if len(closes) < period:
        return None
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((v - mid) ** 2 for v in window) / period
    std = math.sqrt(variance)
    if std == 0:
        return 0.5
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    price = closes[-1]
    bb_pos = (price - lower) / (upper - lower) if (upper - lower) != 0 else 0.5
    return round(max(0, min(1, bb_pos)), 3)

def calc_overheat(closes, highs, lows, ema200_val, atr_val):
    """Überhitzungs-Score (0-100)."""
    if ema200_val is None or atr_val is None or atr_val == 0:
        return 0
    price = closes[-1]
    dist_atr = (price - ema200_val) / atr_val
    score = 0
    if   dist_atr > 5: score += 40
    elif dist_atr > 4: score += 30
    elif dist_atr > 3: score += 20
    elif dist_atr > 2: score += 10

    rsi = calc_rsi(closes)
    if rsi:
        if   rsi > 80: score += 30
        elif rsi > 75: score += 20
        elif rsi > 70: score += 10
        elif rsi > 65: score += 5

    bb = calc_bb(closes)
    if bb:
        if   bb > 0.95: score += 30
        elif bb > 0.85: score += 15
        elif bb > 0.75: score += 5

    return min(100, score)

def calc_markov(closes, lookback=60, stride=7):
    """Vereinfachtes Markov 2.0 Regime-Signal."""
    if len(closes) < lookback:
        return None, None, None
    recent = closes[-lookback:]
    labels = []
    for i in range(stride, len(recent)):
        ret = (recent[i] / recent[i-stride]) - 1
        if   ret >  0.02: labels.append('bull')
        elif ret < -0.02: labels.append('bear')
        else:             labels.append('side')

    if len(labels) < 10:
        return None, None, None

    bull_to_bear = 0
    bull_count   = 0
    bear_count   = 0
    for i in range(len(labels) - 1):
        if labels[i] == 'bull':
            bull_count += 1
            if labels[i+1] == 'bear':
                bull_to_bear += 1
        elif labels[i] == 'bear':
            bear_count += 1

    p_bull2bear = round(bull_to_bear / bull_count, 3) if bull_count > 0 else 0
    regime      = labels[-1]
    bull_pct    = round(labels.count('bull') / len(labels) * 100)

    return regime, p_bull2bear, bull_pct

def calc_composite_score(close, ema50, ema200, macd_hist, obv_trend, overheat, p_bull2bear, rsi):
    """Composite Score 0-100 → Note A+ bis F."""
    score = 50  # Neutral-Basis

    # MA-Signal (20%)
    if ema50 and close > ema50:   score += 10
    if ema200 and close > ema200: score += 10

    # MACD (20%)
    if macd_hist is not None:
        if   macd_hist > 0:  score += 20
        elif macd_hist < 0:  score -= 10

    # OBV (15%)
    if obv_trend is not None:
        if obv_trend > 0: score += 15
        else:             score -= 5

    # Überhitzung (Abzug, 15%)
    score -= round(overheat * 0.15)

    # Markov (10%)
    if p_bull2bear is not None:
        if   p_bull2bear > 0.25: score -= 15
        elif p_bull2bear > 0.15: score -= 8
        elif p_bull2bear < 0.05: score += 10

    # RSI (10%)
    if rsi is not None:
        if   rsi < 30: score += 10  # Überverkauft = Mean Reversion Potential
        elif rsi > 75: score -= 10  # Überkauft

    score = max(0, min(100, score))

    if   score >= 85: grade = "A+"
    elif score >= 70: grade = "A"
    elif score >= 55: grade = "B"
    elif score >= 40: grade = "C"
    elif score >= 25: grade = "D"
    else:             grade = "F"

    return score, grade

# ── EINZELTITEL VERARBEITUNG ──────────────────────────────────────────────────

def process_ticker(ticker, hist_df):
    """Berechnet alle Indikatoren für einen Ticker."""
    try:
        if hist_df is None or len(hist_df) < 30:
            return {"sym": ticker, "error": "insufficient_data", "bars": len(hist_df) if hist_df is not None else 0}

        # Spalten robust extrahieren (auch bei MultiIndex)
        def get_col(df, col):
            if col in df.columns:
                return list(df[col].dropna())
            # MultiIndex fallback
            for c in df.columns:
                if str(c).startswith(col):
                    return list(df[c].dropna())
            return []

        closes  = get_col(hist_df, "Close")
        highs   = get_col(hist_df, "High")
        lows    = get_col(hist_df, "Low")
        vol_col = "Volume"
        volumes = list(hist_df[vol_col].fillna(0)) if vol_col in hist_df.columns else [0]*len(closes)

        if len(closes) < 30:
            return {"sym": ticker, "error": "insufficient_data", "bars": len(closes)}

        price   = round(closes[-1], 4)
        ema50v  = ema(closes, 50)[-1]
        ema200v = ema(closes, 200)[-1] if len(closes) >= 200 else None
        atrv    = calc_atr(highs, lows, closes)
        rsiv    = calc_rsi(closes)
        macd_val, macd_sig, macd_hist = calc_macd(closes)
        obv_tr  = calc_obv_trend(closes, volumes)
        bbpos   = calc_bb(closes)
        overh   = calc_overheat(closes, highs, lows, ema200v, atrv)
        regime, p_bull2bear, bull_pct = calc_markov(closes)

        # 52-Wochen High/Low
        w52_closes = closes[-252:] if len(closes) >= 252 else closes
        high52 = round(max(w52_closes), 4)
        low52  = round(min(w52_closes), 4)
        pct_from_high52 = round((price / high52 - 1) * 100, 2) if high52 else None

        # Buy Point Nähe
        dist_50  = round((price / ema50v - 1) * 100, 2) if ema50v else None
        dist_200 = round((price / ema200v - 1) * 100, 2) if ema200v else None

        # Volumen
        avg_vol20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else None
        vol_ratio = round(volumes[-1] / avg_vol20, 2) if avg_vol20 and avg_vol20 > 0 else None

        # Bull-Signale (0-3)
        bull_signals = 0
        if ema50v and price > ema50v:      bull_signals += 1
        if macd_hist is not None and macd_hist > 0: bull_signals += 1
        if obv_tr is not None and obv_tr > 0:       bull_signals += 1

        comp_score, grade = calc_composite_score(
            price, ema50v, ema200v, macd_hist,
            obv_tr, overh, p_bull2bear, rsiv
        )

        return {
            "sym":           ticker,
            "price":         price,
            "ema50":         round(ema50v, 4) if ema50v else None,
            "ema200":        round(ema200v, 4) if ema200v else None,
            "atr":           atrv,
            "rsi":           rsiv,
            "macdHist":      macd_hist,
            "obvTrend":      round(obv_tr) if obv_tr else None,
            "bbPos":         bbpos,
            "overheat":      overh,
            "regime":        regime,
            "pBull2Bear":    p_bull2bear,
            "bullPct":       bull_pct,
            "bullSignals":   bull_signals,
            "score":         comp_score,
            "grade":         grade,
            "high52":        high52,
            "low52":         low52,
            "pctFromHigh52": pct_from_high52,
            "dist50":        dist_50,
            "dist200":       dist_200,
            "volRatio":      vol_ratio,
            "bars":          len(closes),
            "updated":       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except Exception as e:
        return {"sym": ticker, "error": str(e)}

# ── MARKT-DATEN LADEN ─────────────────────────────────────────────────────────

def fetch_batch(tickers, period="1y", max_workers=20):
    """Lädt OHLCV-Daten für alle Ticker parallel via yfinance."""
    log.info(f"Lade {len(tickers)} Ticker (parallel, {max_workers} Threads)...")
    results = {}

    def fetch_one(ticker):
        # Versuche mehrere Perioden falls primär leer
        for p in [period, "2y", "6mo"]:
            try:
                df = yf.download(ticker, period=p, interval="1d",
                                 auto_adjust=True, progress=False, threads=False)
                if df is not None and len(df) >= 20:
                    # Sicherstellen dass Spalten korrekt sind (MultiIndex flatten)
                    if hasattr(df.columns, 'levels'):
                        df.columns = df.columns.get_level_values(0)
                    return ticker, df
            except Exception as e:
                log.warning(f"  {ticker} ({p}): {e}")
        return ticker, None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, t): t for t in tickers}
        done = 0
        for future in as_completed(futures):
            ticker, df = future.result()
            results[ticker] = df
            done += 1
            if done % 50 == 0:
                log.info(f"  {done}/{len(tickers)} geladen...")

    return results

# ── EXTERNE DATENQUELLEN ──────────────────────────────────────────────────────

def fetch_dix_gex():
    """Echter DIX/GEX von squeezemetrics (tägliche CSV)."""
    try:
        url = "https://squeezemetrics.com/monitor/static/dix.csv"
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://squeezemetrics.com/monitor/"
        })
        if r.status_code == 200 and len(r.text) > 100:
            lines = r.text.strip().split("\n")
            headers = lines[0].lower().split(",")
            last    = lines[-1].split(",")
            row     = dict(zip(headers, last))
            dix_val = float(row.get("dix", 0)) * 100
            gex_val = float(row.get("gex", 0))
            log.info(f"  DIX: {dix_val:.1f}% | GEX: {gex_val/1e9:.2f} Mrd")
            return {
                "dix":    round(dix_val, 2),
                "gex":    round(gex_val / 1e9, 3),
                "date":   row.get("date", ""),
                "source": "squeezemetrics",
                "proxy":  False,
            }
    except Exception as e:
        log.warning(f"  squeezemetrics nicht verfügbar: {e}")
    return None

def fetch_pcr_cboe():
    """Echter Put/Call Ratio von CBOE (tägliche CSV)."""
    try:
        url = "https://www.cboe.com/publish/scheduledtask/mktdata/datahouse/totalpc.csv"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            lines = [l for l in r.text.strip().split("\n")
                     if l and not l.startswith('"DATE') and not l.startswith("DATE")]
            if lines:
                parts = lines[-1].split(",")
                pcr   = float(parts[4].strip().replace('"', ''))
                date  = parts[0].strip().replace('"', '')
                log.info(f"  PCR (CBOE): {pcr:.2f} | Datum: {date}")
                return {
                    "pcr":    round(pcr, 3),
                    "date":   date,
                    "signal": "ÜBERKAUFT" if pcr < 0.7 else "ÜBERVERKAUFT" if pcr > 1.0 else "NEUTRAL",
                    "source": "cboe",
                    "proxy":  False,
                }
    except Exception as e:
        log.warning(f"  CBOE PCR nicht verfügbar: {e}")
    return None

def fetch_vix_term():
    """VIX Term Structure via Yahoo Finance."""
    try:
        vix   = yf.download("^VIX",  period="5d", auto_adjust=True, progress=False)
        vix3m = yf.download("^VIX3M", period="5d", auto_adjust=True, progress=False)
        vix_val  = float(vix["Close"].iloc[-1])
        vix3m_val = float(vix3m["Close"].iloc[-1])
        spread   = round(vix3m_val - vix_val, 2)
        contango = spread > 0
        log.info(f"  VIX: {vix_val:.2f} | VIX3M: {vix3m_val:.2f} | Spread: {spread:+.2f} | {'CONTANGO' if contango else 'BACKWARDATION'}")
        return {
            "vix":       round(vix_val, 2),
            "vix3m":     round(vix3m_val, 2),
            "spread":    spread,
            "ratio":     round(vix_val / vix3m_val, 3),
            "structure": "CONTANGO" if contango else "BACKWARDATION",
            "signal":    "NORMAL" if contango and vix_val / vix3m_val < 0.90 else
                         "ERHÖHT" if contango else "STRESS",
        }
    except Exception as e:
        log.warning(f"  VIX Term nicht verfügbar: {e}")
    return None

# ── CLOUDFLARE KV UPLOAD ──────────────────────────────────────────────────────

def push_to_cloudflare_kv(data, key="master_market_data"):
    """Pusht JSON-Daten in Cloudflare KV."""
    account_id = os.environ.get("CF_ACCOUNT_ID")
    api_token  = os.environ.get("CF_API_TOKEN")
    ns_id      = os.environ.get("CF_KV_NS_ID")

    if not all([account_id, api_token, ns_id]):
        log.warning("CF-Credentials fehlen — KV-Upload übersprungen.")
        log.info("  Setze: CF_ACCOUNT_ID, CF_API_TOKEN, CF_KV_NS_ID als Umgebungsvariablen.")
        return False

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{ns_id}/values/{key}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type":  "application/json",
    }
    payload = json.dumps(data, ensure_ascii=False)
    log.info(f"  Upload zu Cloudflare KV ({len(payload)/1024:.1f} KB)...")

    try:
        r = requests.put(url, headers=headers, data=payload.encode("utf-8"), timeout=30)
        if r.status_code in (200, 201):
            log.info("  ✅ KV-Upload erfolgreich!")
            return True
        else:
            log.error(f"  ❌ KV-Upload fehlgeschlagen: {r.status_code} — {r.text[:200]}")
            return False
    except Exception as e:
        log.error(f"  ❌ KV-Upload Exception: {e}")
        return False

# ── HAUPTPROGRAMM ─────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    log.info("=" * 60)
    log.info("KO-Scanner Market Aggregator v2.1")
    log.info(f"Start: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 60)

    # 1. Ticker-Universum aufbauen
    tickers = build_ticker_universe()
    log.info(f"\n📋 Ticker-Universum: {len(tickers)} Titel")

    # Krypto separat
    stock_tickers  = [t for t in tickers if not t.endswith("-USD")]
    crypto_tickers = [t for t in tickers if t.endswith("-USD")]
    log.info(f"   Aktien/ETFs: {len(stock_tickers)} | Krypto: {len(crypto_tickers)}")

    # 2. Marktdaten laden
    log.info(f"\n📥 Lade Marktdaten...")
    hist_data = fetch_batch(stock_tickers, period="1y", max_workers=25)

    # Krypto mit 6 Monaten
    if crypto_tickers:
        log.info(f"   Lade Krypto-Daten ({len(crypto_tickers)} Ticker)...")
        crypto_data = fetch_batch(crypto_tickers, period="6mo", max_workers=10)
        hist_data.update(crypto_data)

    # 3. Indikatoren berechnen
    log.info(f"\n⚙️  Berechne Indikatoren...")
    results = []
    errors  = []

    for ticker, df in hist_data.items():
        result = process_ticker(ticker, df)
        if "error" in result:
            errors.append(result)
        else:
            results.append(result)

    log.info(f"   ✅ Erfolgreich: {len(results)} | ❌ Fehler: {len(errors)}")

    # 4. Externe Datenquellen
    log.info(f"\n🌐 Externe Datenquellen...")
    dix_gex  = fetch_dix_gex()
    pcr      = fetch_pcr_cboe()
    vix_term = fetch_vix_term()

    # 5. Top-Signale ermitteln
    valid = [r for r in results if r.get("score") is not None]
    top40_long = sorted(
        [r for r in valid if r.get("score", 0) >= 50 and r.get("bullSignals", 0) >= 2],
        key=lambda x: x["score"], reverse=True
    )[:40]

    mean_reversion = sorted(
        [r for r in valid
         if r.get("overheat", 0) >= 60
         and r.get("rsi") is not None and r["rsi"] < 35
         and r.get("bbPos") is not None and r["bbPos"] < 0.15],
        key=lambda x: x.get("overheat", 0), reverse=True
    )[:20]

    # 5b. Sektor Relative Stärke vs. SPY berechnen
    log.info(f"\n📐 Berechne Sektor Relative Stärke...")
    sector_rs = {}
    spy_data  = hist_data.get("SPY")
    if spy_data is not None and len(spy_data) >= 6:
        spy_closes = list(spy_data["Close"].dropna())
        spy_ret5  = (spy_closes[-1] / spy_closes[-6] - 1) * 100 if len(spy_closes) >= 6 else 0
        spy_ret20 = (spy_closes[-1] / spy_closes[-21] - 1) * 100 if len(spy_closes) >= 21 else 0
        spy_ret60 = (spy_closes[-1] / spy_closes[-61] - 1) * 100 if len(spy_closes) >= 61 else 0

        for etf in RS_SECTOR_ETFS:
            etf_data = hist_data.get(etf)
            if etf_data is None or len(etf_data) < 6:
                continue
            etf_closes = list(etf_data["Close"].dropna())
            try:
                ret5  = (etf_closes[-1] / etf_closes[-6] - 1) * 100  if len(etf_closes) >= 6  else None
                ret20 = (etf_closes[-1] / etf_closes[-21] - 1) * 100 if len(etf_closes) >= 21 else None
                ret60 = (etf_closes[-1] / etf_closes[-61] - 1) * 100 if len(etf_closes) >= 61 else None

                rs5  = round(ret5  - spy_ret5,  2) if ret5  is not None else None
                rs20 = round(ret20 - spy_ret20, 2) if ret20 is not None else None
                rs60 = round(ret60 - spy_ret60, 2) if ret60 is not None else None

                # Trend: steigend wenn RS5 > RS20
                trend = "steigend" if rs5 and rs20 and rs5 > rs20 else "fallend"

                sector_rs[etf] = {
                    "sym":   etf,
                    "price": round(etf_closes[-1], 2),
                    "rs5":   rs5,   # 5T RS vs SPY
                    "rs20":  rs20,  # 20T RS vs SPY
                    "rs60":  rs60,  # 60T RS vs SPY
                    "ret5":  round(ret5, 2)  if ret5  else None,
                    "ret20": round(ret20, 2) if ret20 else None,
                    "trend": trend,
                    # Rotation Signal: positiv RS + steigend = Geld fließt rein
                    "inflow": rs5 is not None and rs5 > 0 and trend == "steigend",
                }
            except Exception as e:
                log.warning(f"  RS Fehler {etf}: {e}")

        # Top Sektoren nach RS5 sortiert
        rs_sorted = sorted(
            [v for v in sector_rs.values() if v.get("rs5") is not None],
            key=lambda x: x["rs5"], reverse=True
        )
        log.info(f"  Top-3 Sektoren (RS5): {[r['sym'] for r in rs_sorted[:3]]}")
        log.info(f"  Schwächste (RS5):     {[r['sym'] for r in rs_sorted[-3:]]}")

    # 5c. Swing-Trading Kandidaten
    swing_candidates = sorted(
        [r for r in valid
         if r.get("score", 0) >= 45
         and r.get("bullSignals", 0) >= 1
         and r.get("rsi") is not None and r["rsi"] < 60
         and r.get("macdHist") is not None],
        key=lambda x: x.get("score", 0), reverse=True
    )[:20]

    # 6. Master-JSON zusammenbauen
    elapsed = round(time.time() - start_time, 1)
    master  = {
        "meta": {
            "version":    "1.0",
            "generated":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "elapsed_s":  elapsed,
            "total":      len(results),
            "errors":     len(errors),
            "tickers_ok": len(results),
        },
        "market": {
            "dixGex":   dix_gex,
            "pcr":      pcr,
            "vixTerm":  vix_term,
        },
        "top40":          [{"sym": r["sym"], "score": r["score"], "grade": r["grade"],
                            "price": r["price"], "bullSignals": r["bullSignals"],
                            "regime": r["regime"], "overheat": r["overheat"]}
                           for r in top40_long],
        "meanReversion":  [{"sym": r["sym"], "overheat": r["overheat"], "rsi": r["rsi"],
                            "bbPos": r["bbPos"], "price": r["price"]}
                           for r in mean_reversion],
        "sectorWatchlists": {
            name: [next((r for r in results if r["sym"] == t), {"sym": t, "error": "no_data"})
                   for t in tickers]
            for name, tickers in SECTOR_WATCHLISTS.items()
        },
        "markets": {
            "dax40":    [r for r in results if r["sym"] in DAX40_TICKERS],
            "mdax":     [r for r in results if r["sym"] in MDAX_TICKERS],
            "tecdax":   [r for r in results if r["sym"] in TECDAX_TICKERS],
            "eurostoxx":[r for r in results if r["sym"] in EUROSTOXX_TICKERS],
            "sp500":    [r for r in results if r["sym"] in SP500_TICKERS],
            "nasdaq100":[r for r in results if r["sym"] in NASDAQ100_EXTRA],
            "intl":     [r for r in results if r["sym"] in INTL_TIER1],
            "etfs":     [r for r in results if r["sym"] in SECTOR_ETFS],
            "crypto":   [r for r in results if r["sym"] in CRYPTO_TICKERS],
        },
        "sectorRS":       sector_rs,   # Sektor Relative Stärke vs. SPY
        "swingCandidates": [{"sym": r["sym"], "score": r["score"], "price": r["price"],
                             "rsi": r["rsi"], "macdHist": r.get("macdHist"), "regime": r["regime"]}
                            for r in swing_candidates],
        "tickers":        results,  # Alle Ergebnisse
    }

    payload_size = len(json.dumps(master)) / 1024
    log.info(f"\n📊 Master-JSON: {payload_size:.0f} KB | {len(results)} Ticker")
    log.info(f"   Top40 Long: {len(top40_long)} | Mean Reversion: {len(mean_reversion)}")

    # 7. Lokales Backup
    with open("master_market_data.json", "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, separators=(",", ":"))
    log.info(f"   💾 Lokal gespeichert: master_market_data.json")

    # 8. Cloudflare KV Upload
    log.info(f"\n☁️  Cloudflare KV Upload...")
    push_to_cloudflare_kv(master, key="master_market_data")

    log.info(f"\n{'='*60}")
    log.info(f"✅ Fertig in {elapsed}s")
    log.info(f"{'='*60}")

if __name__ == "__main__":
    main()
