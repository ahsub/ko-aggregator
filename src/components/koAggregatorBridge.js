const MASTER_ENDPOINT = 'https://ko-sync.ahildebrand.workers.dev/public/master_market_data';
const GITHUB_FALLBACK = 'https://raw.githubusercontent.com/ahsub/ko-aggregator/main/backups/tr_backup_latest.json';
const FINNHUB_KEY = import.meta.env.VITE_FINNHUB_KEY || '';

const CACHE_TTL = 5 * 60 * 1000;
let cache = null;
let cacheTime = 0;
let metaCache = null;

// ═══════════════════════════════════════════════════════════════════════════
// PRIMARY: master_market_data (ko-sync Worker)
// ═══════════════════════════════════════════════════════════════════════════

export async function fetchKoAggregatorData() {
  const now = Date.now();
  if (cache && now - cacheTime < CACHE_TTL) return cache;

  // 1. Primär: master_market_data vom ko-sync Worker
  try {
    const res = await fetch(MASTER_ENDPOINT);
    if (res.ok) {
      const data = await res.json();
      const normalized = normalizeMasterData(data);
      if (normalized.length > 0) {
        cache = normalized;
        cacheTime = now;
        console.log(`[KO-Bridge] ✅ ${normalized.length} Ticker aus master_market_data (Schema ${metaCache?.schema || '?'})`);
        return cache;
      }
    }
  } catch (err) {
    console.warn('[KO-Bridge] master_market_data fehlgeschlagen:', err.message);
  }

  // 2. Sekundär: GitHub Backup (market-snapshot oder legacy)
  try {
    const res = await fetch(GITHUB_FALLBACK);
    const backup = await res.json();
    const marketKey = Object.keys(backup.keys || {}).find(k =>
      k.startsWith('market-snapshot-')
    );
    if (marketKey && backup.keys[marketKey]?.tickers) {
      cache = normalizeKoData(backup.keys[marketKey].tickers);
      cacheTime = now;
      console.log(`[KO-Bridge] ⚠️ Fallback: ${cache.length} Ticker aus Backup ${marketKey}`);
      return cache;
    }
    const legacy = normalizeKoData(backup);
    if (legacy.length > 0) {
      cache = legacy;
      cacheTime = now;
      return cache;
    }
  } catch (err2) {
    console.warn('[KO-Bridge] GitHub-Fallback fehlgeschlagen:', err2.message);
  }

  // 3. Tertiär: Finnhub Live (nur wenn alles andere leer ist)
  console.warn('[KO-Bridge] 🔄 Keine Aggregator-Daten — wechsle zu Finnhub...');
  return await fetchFinnhubMarketData();
}

// ═══════════════════════════════════════════════════════════════════════════
// OPTIONS WATCHLIST (KI-Strikes direkt aus dem Aggregator)
// ═══════════════════════════════════════════════════════════════════════════

export async function fetchOptionsWatchlist() {
  try {
    const res = await fetch(MASTER_ENDPOINT);
    if (!res.ok) return [];
    const data = await res.json();
    const master = data.data || data;
    const list = master.optionsWatchlist || [];
    return list.map(o => ({
      symbol: o.sym || o.symbol,
      strategy: o.strategy || o.strat,
      price: parseFloat(o.price || 0),
      score: parseFloat(o.score || 0),
      ki: o.ki || null,
      atr: parseFloat(o.atr || 0),
      dte: o.dte || null,
      source: 'Aggregator'
    })).filter(o => o.symbol);
  } catch (e) {
    console.warn('[KO-Bridge] OptionsWatchlist fehlgeschlagen:', e);
    return [];
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// META-INFO (Handelstag, Schema, Errors)
// ═══════════════════════════════════════════════════════════════════════════

export function getMarketMeta() {
  return metaCache || {
    lastTradingDay: null,
    errors: null,
    schema: null,
    generated: null
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// NORMALIZER: master_market_data → Frontend-Schema
// ═══════════════════════════════════════════════════════════════════════════

function normalizeMasterData(raw) {
  const master = raw.data || raw;
  const tickers = master.tickers || master.data?.tickers || [];
  const meta = master.meta || {};

  metaCache = {
    lastTradingDay: meta.last_trading_day || meta.lastTradingDay || null,
    errors: meta.errors || null,
    schema: master.schema || null,
    generated: meta.generated || null
  };

  return tickers.map(t => {
    const price = parseFloat(t.price || t.close || 0);
    return {
      // Identität
      symbol: t.sym || t.symbol || t.ticker,
      price,

      // Scores (CSP = Cash-Secured Put, CC = Covered Call)
      compositeScore: parseFloat(t.scoreCsp || t.scoreCc || t.score || t.compositeScore || 0),
      scoreCsp: parseFloat(t.scoreCsp || 0),
      scoreCc: parseFloat(t.scoreCc || 0),

      // Trend (EMA / SMA)
      ema20: parseFloat(t.ema20 || t.EMA20 || 0),
      ema50: parseFloat(t.ema50 || t.EMA50 || 0),
      ema200: parseFloat(t.ema200 || t.EMA200 || 0),
      sma50: parseFloat(t.sma50 || t.SMA50 || 0),
      sma150: parseFloat(t.sma150 || t.SMA150 || 0),
      sma200: parseFloat(t.sma200 || t.SMA200 || 0),

      // Momentum
      rsi14: parseFloat(t.rsi14 || t.rsi || t.RSI || 50),
      macdLine: parseFloat(t.macdLine || t.macd || 0),
      macdSignal: parseFloat(t.macdSignal || 0),

      // Volatilität
      hvp: parseFloat(t.hvp || t.HVP || t.histVolPct || 30),
      atr14: parseFloat(t.atr14 || t.atr || t.ATR || 0),
      ivAtm: parseFloat(t.ivAtm || t.iv_atm || 0),
      ivExpiry: t.ivExpiry || t.iv_expiry || null,
      ivRank: parseFloat(t.ivRank || t.iv_rank || 0),
      ivPercentile: parseFloat(t.ivPercentile || t.iv_percentile || 0),

      // Regime & Marktstruktur
      regime: t.regime || t.markovRegime || t.trend || 'UNKNOWN',
      zScore: parseFloat(t.zScore || t.z_score || 0),
      pocLevel: parseFloat(t.pocLevel || t.poc_level || 0),
      distToPocPct: parseFloat(t.distToPocPct || t.dist_to_poc_pct || 0),
      regTrend: t.regTrend || t.reg_trend || '',
      regBaseline: parseFloat(t.regBaseline || t.reg_baseline || 0),
      chanHigh3sd: parseFloat(t.chanHigh3sd || t.chan_high_3sd || 0),
      chanLow3sd: parseFloat(t.chanLow3sd || t.chan_low_3sd || 0),

      // VCP / Technische Qualität
      vcpVolContraction: parseFloat(t.vcpVolContraction || t.vcp_vol_contraction || 0),
      vcpBreakoutVol: parseFloat(t.vcpBreakoutVol || t.vcp_breakout_vol || 0),
      tightnessPct: parseFloat(t.tightnessPct || t.tightness_pct || 0),
      dist200: parseFloat(t.dist200 || t.dist_200 || 0),
      bbPos: parseFloat(t.bbPos || t.bb_pos || 0),

      // Risiko-Indikatoren
      nearestSellStopPct: parseFloat(t.nearestSellStopPct || t.nearest_sell_stop_pct || 0),
      squeezeRisk: parseFloat(t.squeezeRisk || t.squeeze_risk || 0),
      overheat: parseFloat(t.overheat || 0),

      // Fundamentale Daten
      sectors: t.sectors || t.sector || t.industry || '',
      marketCap: parseFloat(t.marketCap || t.market_cap || 0),

      // Meta
      timestamp: metaCache.lastTradingDay || new Date().toISOString(),
      source: 'Aggregator'
    };
  }).filter(t => t.symbol && t.price > 0);
}

// ═══════════════════════════════════════════════════════════════════════════
// LEGACY NORMALIZER (für Backup/Snapshot/Finnhub)
// ═══════════════════════════════════════════════════════════════════════════

function normalizeKoData(raw) {
  const arr = Array.isArray(raw) ? raw : raw?.data || raw?.tickers || [];
  return arr.map(t => ({
    symbol: t.symbol || t.sym || t.ticker || t.name,
    price: parseFloat(t.price || t.close || 0),
    compositeScore: parseFloat(t.compositeScore || t.score || t.scoreCsp || t.scoreCc || t.trendScore || 0),
    scoreCsp: parseFloat(t.scoreCsp || 0),
    scoreCc: parseFloat(t.scoreCc || 0),
    ema20: parseFloat(t.ema20 || t.EMA20 || 0),
    ema50: parseFloat(t.ema50 || t.EMA50 || 0),
    ema200: parseFloat(t.ema200 || t.EMA200 || 0),
    rsi14: parseFloat(t.rsi14 || t.rsi || t.RSI || 50),
    hvp: parseFloat(t.hvp || t.HVP || t.volatility || 30),
    regime: t.regime || t.markovRegime || t.trend || 'UNKNOWN',
    sma50: parseFloat(t.sma50 || t.SMA50 || 0),
    sma200: parseFloat(t.sma200 || t.SMA200 || 0),
    atr14: parseFloat(t.atr14 || t.ATR14 || t.atr || 0),
    ivAtm: parseFloat(t.ivAtm || 0),
    ivRank: parseFloat(t.ivRank || 0),
    timestamp: t.timestamp || new Date().toISOString(),
    source: 'Backup'
  })).filter(t => t.symbol && t.price > 0);
}

// ═══════════════════════════════════════════════════════════════════════════
// FINNHUB FALLBACK (nur wenn Aggregator komplett offline)
// ═══════════════════════════════════════════════════════════════════════════

async function fetchFinnhubMarketData() {
  if (!FINNHUB_KEY) {
    console.error('[KO-Bridge] Kein Finnhub-Key');
    return [];
  }

  const UNIVERSE = [
    'AAPL','MSFT','AMZN','GOOGL','META','TSLA','NVDA','AMD','NFLX','CRM',
    'UBER','PYPL','SQ','SHOP','ROKU','ZM','DOCU','CRWD','SNOW','PLTR',
    'INTC','IBM','CSCO','ORCL','ADBE','INTU','NOW','TWLO','DDOG','NET',
    'MRNA','PFE','JNJ','UNH','ABBV','LLY','TMO','DHR','ABT','BMY',
    'XOM','CVX','COP','OXY','SLB','EOG','MPC','VLO','PSX','KMI',
    'JPM','BAC','GS','MS','WFC','C','USB','PNC','TFC','COF',
    'HD','LOW','COST','TGT','WMT','NKE','LULU','TJX','ROST','BBY',
    'DIS','SBUX','MCD','CMG','YUM','DPZ','DRI','TXRH','PLAY',
    'BA','LMT','RTX','NOC','GD','TXT','HII','TDG','HEI','CW'
  ];

  const results = await Promise.allSettled(
    UNIVERSE.map(sym => fetchSingleTicker(sym))
  );

  const valid = results
    .filter(r => r.status === 'fulfilled' && r.value)
    .map(r => r.value);

  cache = valid;
  cacheTime = Date.now();
  console.log(`[KO-Bridge] Finnhub: ${valid.length}/${UNIVERSE.length} Ticker`);
  return valid;
}

async function fetchSingleTicker(symbol) {
  try {
    const quoteRes = await fetch(
      `https://finnhub.io/api/v1/quote?symbol=${symbol}&token=${FINNHUB_KEY}`
    );
    if (!quoteRes.ok) return null;
    const quote = await quoteRes.json();
    if (!quote.c || quote.c === 0) return null;

    const now = Math.floor(Date.now() / 1000);
    const from = now - 300 * 86400;
    const candleRes = await fetch(
      `https://finnhub.io/api/v1/stock/candle?symbol=${symbol}&resolution=D&from=${from}&to=${now}&token=${FINNHUB_KEY}`
    );

    let candles = null;
    if (candleRes.ok) {
      const c = await candleRes.json();
      if (c.s === 'ok' && c.c && c.c.length > 50) {
        candles = { close: c.c, high: c.h, low: c.l, open: c.o, volume: c.v, timestamp: c.t };
      }
    }

    const indicators = candles ? computeIndicators(candles) : computeMinimalIndicators(quote);

    return {
      symbol,
      price: quote.c,
      compositeScore: indicators.compositeScore,
      scoreCsp: indicators.compositeScore,
      scoreCc: indicators.compositeScore,
      ema20: indicators.ema20,
      ema50: indicators.ema50,
      ema200: indicators.ema200,
      rsi14: indicators.rsi14,
      hvp: indicators.hvp,
      atr14: indicators.atr14,
      regime: indicators.regime,
      sma50: indicators.sma50,
      sma200: indicators.sma200,
      ivAtm: 0,
      ivRank: 0,
      timestamp: new Date().toISOString(),
      source: 'Finnhub'
    };
  } catch (e) {
    return null;
  }
}

function computeIndicators(c) {
  const n = c.close.length;
  const close = c.close, high = c.high, low = c.low;

  const ema20 = calcEMA(close, 20);
  const ema50 = calcEMA(close, 50);
  const ema200 = calcEMA(close, 200);
  const sma50 = calcSMA(close, 50);
  const sma200 = calcSMA(close, 200);
  const rsi14 = calcRSI(close, 14);
  const atr14 = calcATR(high, low, close, 14);

  const vol20 = calcVolatility(close, 20);
  const volSeries = [];
  for (let i = 20; i < n; i++) volSeries.push(calcVolatility(close.slice(0, i + 1), 20));
  const currentVol = vol20;
  const lookback = volSeries.slice(-100);
  const hvp = lookback.length > 0 ? (lookback.filter(v => v < currentVol).length / lookback.length) * 100 : 50;

  const lastPrice = close[n - 1];
  let regime = 'UNKNOWN';
  if (sma50 > sma200 && lastPrice > sma200) regime = 'BULL';
  else if (sma50 < sma200 && lastPrice < sma200) regime = 'BEAR';
  else regime = 'TRANSITION';

  let trendScore = 0;
  if (lastPrice > ema200) trendScore += 20;
  if (sma50 > sma200) trendScore += 20;
  if (lastPrice > ema50) trendScore += 15;
  if (lastPrice > ema20) trendScore += 10;

  let rsiScore = 0;
  if (rsi14 >= 45 && rsi14 <= 65) rsiScore = 15;
  else if (rsi14 > 65) rsiScore = Math.max(0, 15 - (rsi14 - 65) * 0.5);
  else rsiScore = Math.max(0, 15 - (45 - rsi14) * 0.5);

  let volScore = 0;
  if (currentVol < 20) volScore = 10;
  else if (currentVol < 40) volScore = 20;
  else if (currentVol < 60) volScore = 10;

  const compositeScore = Math.min(100, Math.round(trendScore + rsiScore + volScore));

  return { ema20, ema50, ema200, sma50, sma200, rsi14, atr14, hvp: Math.round(hvp), regime, compositeScore };
}

function computeMinimalIndicators(quote) {
  const price = quote.c;
  const changePct = ((quote.c - quote.pc) / quote.pc) * 100;
  let regime = 'UNKNOWN';
  if (changePct > 2) regime = 'BULL';
  else if (changePct < -2) regime = 'BEAR';
  else regime = 'TRANSITION';
  return {
    ema20: price * 0.98, ema50: price * 0.95, ema200: price * 0.90,
    sma50: price * 0.95, sma200: price * 0.90,
    rsi14: 50, atr14: price * 0.02, hvp: 50, regime, compositeScore: 50
  };
}

// ─── Math Helpers ───
function calcEMA(data, period) {
  const k = 2 / (period + 1);
  let ema = data[0];
  for (let i = 1; i < data.length; i++) ema = data[i] * k + ema * (1 - k);
  return ema;
}
function calcSMA(data, period) {
  if (data.length < period) return data.reduce((a, b) => a + b, 0) / data.length;
  const slice = data.slice(-period);
  return slice.reduce((a, b) => a + b, 0) / period;
}
function calcRSI(data, period) {
  if (data.length < period + 1) return 50;
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = data[data.length - period - 1 + i] - data[data.length - period - 2 + i];
    if (diff > 0) gains += diff; else losses -= diff;
  }
  const avgGain = gains / period, avgLoss = losses / period;
  if (avgLoss === 0) return 100;
  return 100 - (100 / (1 + avgGain / avgLoss));
}
function calcATR(high, low, close, period) {
  if (close.length < 2) return 0;
  const tr = [];
  for (let i = 1; i < close.length; i++) {
    tr.push(Math.max(high[i] - low[i], Math.abs(high[i] - close[i - 1]), Math.abs(low[i] - close[i - 1])));
  }
  if (tr.length < period) return tr.reduce((a, b) => a + b, 0) / tr.length;
  return tr.slice(-period).reduce((a, b) => a + b, 0) / period;
}
function calcVolatility(data, period) {
  if (data.length < period + 1) return 30;
  const returns = [];
  for (let i = data.length - period; i < data.length; i++) returns.push((data[i] - data[i - 1]) / data[i - 1]);
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((a, b) => a + (b - mean) ** 2, 0) / returns.length;
  return Math.sqrt(variance) * Math.sqrt(252) * 100;
}

// ═══════════════════════════════════════════════════════════════════════════
// FILTER (angepasst an Aggregator-Felder)
// ═══════════════════════════════════════════════════════════════════════════

export function filterLeapCandidates(tickers) {
  return tickers.filter(t => {
    const trendOk = t.price > t.ema200 && (t.sma50 > t.sma200 || t.regTrend === 'Bullish');
    const scoreOk = (t.compositeScore >= 70) || (t.scoreCsp >= 70);
    const rsiOk = t.rsi14 >= 45 && t.rsi14 <= 62;
    const hvpOk = t.hvp < 40;
    const regimeOk = t.regime?.toLowerCase().includes('bull') || t.regime === 'BULL_QUIET' || t.regime === 'BULL';
    return trendOk && scoreOk && rsiOk && hvpOk && regimeOk;
  });
}

export function filterPmccCandidates(tickers) {
  return tickers.filter(t => {
    const trendOk = t.price > t.ema200 && (t.sma50 > t.sma200 || t.regTrend === 'Bullish');
    const scoreOk = (t.compositeScore >= 65) || (t.scoreCc >= 65);
    const rsiOk = t.rsi14 >= 40 && t.rsi14 <= 65;
    const hvpOk = t.hvp < 45;
    return trendOk && scoreOk && rsiOk && hvpOk;
  });
}

export function filterZebraCandidates(tickers) {
  return tickers.filter(t => {
    const trendOk = t.price > t.ema200 && (t.sma50 > t.sma200 || t.regTrend === 'Bullish');
    const scoreOk = (t.compositeScore >= 60) || (t.scoreCsp >= 60);
    const rsiOk = t.rsi14 >= 50 && t.rsi14 <= 70;
    const hvpOk = t.hvp >= 20 && t.hvp < 50;
    return trendOk && scoreOk && rsiOk && hvpOk;
  });
}

export function filterPutDiagonalCandidates(tickers) {
  return tickers.filter(t => {
    const trendNeutral = t.rsi14 >= 35 && t.rsi14 <= 55;
    const supportOk = t.price > t.ema50;
    const hvpOk = t.hvp >= 25 && t.hvp < 55;
    const scoreOk = (t.compositeScore >= 55) || (t.scoreCc >= 55);
    return trendNeutral && supportOk && hvpOk && scoreOk;
  });
}

export function filterCollaredLeapCandidates(tickers) {
  return tickers.filter(t => {
    const trendOk = t.price > t.ema200;
    const scoreOk = (t.compositeScore >= 65) || (t.scoreCsp >= 65);
    const rsiOk = t.rsi14 >= 45 && t.rsi14 <= 65;
    const hvpOk = t.hvp >= 15 && t.hvp < 45;
    return trendOk && scoreOk && rsiOk && hvpOk;
  });
}

export function filterIronCondorCandidates(tickers) {
  return tickers.filter(t => {
    const rangeOk = t.rsi14 >= 40 && t.rsi14 <= 60;
    const hvpOk = t.hvp >= 30 && t.hvp < 60;
    const atrOk = t.atr14 / t.price < 0.03;
    const scoreOk = t.compositeScore >= 50;
    return rangeOk && hvpOk && atrOk && scoreOk;
  });
}
