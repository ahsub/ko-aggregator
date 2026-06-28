#!/usr/bin/env python3
"""
UnderlyingIQ Market Aggregator v3.0
=====================================
Single-Source-of-Truth Aggregator für Alpha Desk + Scanner Tab.
Läuft als GitHub Actions Cron-Job (täglich 04:00 UTC nach US-Schluss).
Version 3.0: EU-ADR-Universum (US-gelistete ADRs statt Heimatbörsen .DE/.PA/.L),
Multi-Strategy Scoring Engine (Gemini v3), Macro Risk Overlay (GEX/PCR),
KV-basierte Scanner-Architektur (Single Source of Truth).

Ablauf:
  1. Lädt OHLCV-Daten für ~600 Ticker via yfinance (parallel)
  2. Berechnet technische Indikatoren (EMA, RSI, MACD, OBV, ATR, BB, HVP, hv10)
  3. Berechnet Markov 2.0 Regime-Signale
  4. Berechnet Composite Score + 5 Strategie-Scores (Gemini v3)
  5. Lädt DIX/GEX von squeezemetrics (wenn verfügbar)
  6. Lädt PCR von CBOE
  7. Wendet Macro Risk Overlay (GEX/PCR) auf Options-Kandidaten an
  8. Pusht master_market_data.json → Cloudflare KV

Umgebungsvariablen (GitHub Secrets):
  CF_ACCOUNT_ID   — Cloudflare Account ID
  CF_API_TOKEN    — Cloudflare API Token (KV Write)
  CF_KV_NS_ID     — Cloudflare KV Namespace ID
  ANTHROPIC_API_KEY — Claude API für KI-Enrichment
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

def get_last_trading_day():
    """
    Bestimmt den letzten echten US-Handelstag.
    Berücksichtigt Wochenenden und US-Feiertage via yfinance SPY-Daten.
    """
    try:
        spy = yf.download("SPY", period="10d", interval="1d",
                          auto_adjust=True, progress=False, threads=False)
        if spy is not None and len(spy) > 0:
            last_date = spy.index[-1].date()
            log.info(f"  Letzter Handelstag (via SPY): {last_date}")
            return last_date
    except Exception as e:
        log.warning(f"  get_last_trading_day Fehler: {e}")
    from datetime import date
    return date.today()

def validate_data_freshness(results):
    """
    Prüft ob die geladenen Daten vom letzten Handelstag stammen.
    Warnt wenn Daten veraltet sind (z.B. nach Feiertag).
    """
    last_trading_day = get_last_trading_day()
    stale_count = 0
    fresh_count = 0

    for r in results:
        if 'updated' in r:
            try:
                data_date = r['updated'][:10]  # YYYY-MM-DD
                if data_date == str(last_trading_day):
                    fresh_count += 1
                else:
                    stale_count += 1
            except:
                pass

    log.info(f"  Datenfreshe: {fresh_count} aktuell · {stale_count} veraltet")
    log.info(f"  Letzter Handelstag: {last_trading_day}")

    # Warnung wenn mehr als 20% der Daten nicht vom letzten Handelstag
    if stale_count > 0 and (stale_count / max(fresh_count + stale_count, 1)) > 0.2:
        log.warning(f"  ⚠ Viele veraltete Daten — möglicher Feiertag oder Datenproblem!")

    return str(last_trading_day)

# ── TICKER UNIVERSUM ──────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════════════
# TICKER UNIVERSUM v3.0  (~600 Titel)
# Struktur: US-Aktien | DE/EU Aktien | FTSE Non-US | Sektor-ETFs US+ExUS | Crypto
# Datenquelle: Yahoo Finance (Xetra .DE fuer DE/EU — beste Datenqualitaet)
# ══════════════════════════════════════════════════════════════════════════════

# ── US LARGE/MID CAP (S&P500 Kern + Nasdaq Wachstum) ─────────────────────────
SP500_TICKERS = [
    # Mega-Cap Tech
    "AAPL","MSFT","NVDA","AMZN","GOOGL","GOOG","META","TSLA","AVGO","ORCL",
    # Financials
    "JPM","BAC","WFC","GS","MS","BLK","SCHW","AXP","CB","MMC","AON","CME","SPGI","MCO",
    # Healthcare
    "UNH","LLY","JNJ","ABT","MRK","ABBV","TMO","DHR","SYK","BSX","MDT","ELV","CI","HUM",
    "ISRG","REGN","VRTX","GILD","AMGN","BMY","PFE","CVS","ZTS","IDXX","A","IQV",
    # Consumer
    "COST","WMT","HD","MCD","SBUX","TGT","LOW","TJX","BKNG","MAR","HLT","YUM",
    "NKE","PG","KO","PEP","PM","MO","CL","EL","CHD",
    # Industrials
    "CAT","HON","UPS","DE","GE","GEV","BA","LMT","RTX","NOC","GD","HII","TDG","KTOS","AXON",
    "UNP","CSX","NSC","TT","CARR","OTIS","JCI","EMR","ROK","AME","ITW","ETN","PH","IR",
    # Energy
    "XOM","CVX","COP","EOG","SLB","MPC","PSX","VLO","OXY","DVN","HAL","BKR","FANG",
    # Utilities & REITs
    "NEE","DUK","SO","AEP","D","SRE","EXC","PLD","AMT","EQIX","CCI","PSA","O","VICI",
    # Tech & Software
    "V","MA","INTU","ADBE","CRM","NOW","SNPS","CDNS","ANSS","ADSK","WDAY","TEAM",
    "PANW","CRWD","FTNT","ZS","OKTA","S","DDOG","MDB","SNOW","NET","CFLT","ESTC",
    "QCOM","TXN","ADI","MCHP","NXPI","KLAC","LRCX","AMAT","MU","WDC","STX",
    "IBM","CSCO","ACN","HPQ","HPE","DELL","NTAP",
    # Semiconductors / AI
    "ARM","SMCI","MRVL","MSTR","PLTR","COIN",
    # E-Commerce / Consumer Tech
    "NFLX","UBER","ABNB","LYFT","RBLX","SNAP","PINS","MTCH","ZM","DOCU",
    "SHOP","MELI","SE","GRAB","SQ","HOOD","SOFI","AFRM","UPST","PYPL",
    # China ADRs (US-listed)
    "BABA","JD","PDD","BIDU","NTES","TCOM","FUTU","NIO","XPEV","LI",
    # Auto
    "GM","F","RIVN","LCID","STLA","TM","HMC",
    # Materials
    "LIN","APD","ECL","SHW","FCX","NEM","GOLD","ALB","MP",
    # Biotech / Pharma Growth
    "MRNA","BNTX","BIIB","ILMN","SGEN","RARE","EXAS","INCY","NBIX","ALLO",
    "VKTX","RYTM","ACAD","MRUS","PRCT",
    # Clean Energy
    "ENPH","FSLR","SEDG","RUN","ARRY","NOVA","BE","PLUG","BLDP","NEE",
    # Fintech
    "HOOD","AFRM","UPST","SOFI",
    # Misc Growth
    "GLW","LDOS","SAIC","CACI","BAH","HUBS","ZI","GTLB","BILL","PCTY",
]

NASDAQ100_EXTRA = [
    "ADSK","FAST","IDXX","KDP","KHC","LULU","MNST","ODFL","PAYX","PCAR",
    "ROST","SIRI","TMUS","VRSK","VRSN","XEL","CPRT","CTAS","DLTR","EBAY","EXC",
]

# ── DEUTSCHE MAERKTE (Xetra .DE — beste yfinance Verfuegbarkeit) ──────────────
# DAX40/MDAX/TecDAX: NUR Referenz + KO-Produkt-Screener (keine Options-Kandidaten)
# Werden in build_ticker_universe() NICHT mehr direkt eingebunden.
DAX40_TICKERS = [
    "ADS.DE","AIR.DE","ALV.DE","BAS.DE","BAYN.DE","BMW.DE","BNR.DE",
    "CBK.DE","CON.DE","1COV.DE","DBK.DE","DB1.DE","DHL.DE","DTE.DE",
    "EOAN.DE","FRE.DE","HEI.DE","HEN3.DE","IFX.DE","INL.DE","LIN.DE",
    "MBG.DE","MRK.DE","MTX.DE","MUV2.DE","P911.DE","PAH3.DE","QIA.DE",
    "RHM.DE","RWE.DE","SAP.DE","SHL.DE","SIE.DE","SY1.DE",
    "VNA.DE","VOW3.DE","ZAL.DE","ENR.DE","DHER.DE","PUMA.DE",
]

MDAX_TICKERS = [
    "AFX.DE","AG1.DE","AIXA.DE","BC8.DE","BOSS.DE","DEQ.DE","DWS.DE",
    "EVD.DE","EVK.DE","FNTN.DE","HAG.DE","HHFA.DE","HNR1.DE","HOT.DE",
    "JEN.DE","KGX.DE","LEG.DE","NDA.DE","NOEJ.DE","O2D.DE","PBB.DE",
    "PSM.DE","SFQ.DE","SGL.DE","TAG.DE","TLX.DE","TUI1.DE","UTDI.DE",
    "WAF.DE","WCH.DE","KSB.DE","SMT.DE","GFK.DE","ARND.DE",
]

TECDAX_TICKERS = [
    "AIXA.DE","BB1.DE","EVNT.DE","FNTN.DE","IFX.DE","INH.DE",
    "NDX1.DE","PFV.DE","PSM.DE","S92.DE","SAP.DE","SFQ.DE","SHL.DE",
    "SIE.DE","SOW.DE","SRT3.DE","UTDI.DE","WAF.DE","ZAL.DE",
]

# ── EUROSTOXX / EU-Heimatboersen (NUR fuer Referenz + KV-Filterung) ──────────
# Diese Liste wird NICHT mehr direkt in build_ticker_universe() eingebunden.
# Stattdessen: EU_ADR_TICKERS (US-gelistete Pendants) werden verwendet.
# Heimatboersen bleiben als Referenz fuer KO-Produkt-Screener und Watchlisten.
EUROSTOXX_TICKERS_LEGACY = [
    # Frankreich (.PA) — nur Referenz
    "OR.PA","MC.PA","SU.PA","BNP.PA","AIR.PA","TTE.PA","STM.PA","RNO.PA",
    # Niederlande (.AS)
    "ASML.AS","PHIA.AS","ING.AS","ADYEN.AS","HEIA.AS",
    # Italien (.MI)
    "ENI.MI","ENEL.MI","RACE.MI","STM.MI",
    # Schweiz (.SW)
    "NOVN.SW","ROG.SW","NESN.SW","ABBN.SW",
    # UK (.L)
    "AZN.L","SHEL.L","BP.L","GSK.L","ULVR.L","RIO.L",
    # Skandinavien / Sonstige
    "NOVO-B.CO","ERICB.ST",
]
# Alias fuer abwaertskompatible KV-Keys
EUROSTOXX_TICKERS = EUROSTOXX_TICKERS_LEGACY

# ── EU BLUE CHIPS — US-gelistete ADRs (Options-faehig, liquid) ───────────────
# Ersetzt DAX40, MDAX, TecDAX, EuroStoxx, FTSE100, STOXX_EU_EXTRA im Universum.
# Nur US-gelistete Ticker: NYSE/NASDAQ-ADRs oder primär US-notierte Titel.
# Quelle: OTC Markets / NYSE ADR-Datenbank — geprüft auf Optionsliquidität.
EU_ADR_TICKERS = [
    # ── Deutschland (DAX + MDAX) ──────────────────────────────────────────────
    "SAP",      # SAP SE (NYSE, primär US-listing)
    "DB",       # Deutsche Bank (NYSE ADR)
    "SIEGY",    # Siemens (OTC ADR, liquid)
    "BAYRY",    # Bayer (OTC ADR)
    "BMWYY",    # BMW (OTC ADR)
    "ADDYY",    # Adidas (OTC ADR)
    "DHLGY",    # DHL Group (OTC ADR)
    "DTEGY",    # Deutsche Telekom (OTC ADR)
    "AZSEY",    # Allianz (OTC ADR)
    "MURGY",    # Munich Re (OTC ADR)
    "RWEOY",    # RWE (OTC ADR)
    "IFNNY",    # Infineon (OTC ADR)
    "LIN",      # Linde (NYSE, primär US-listing seit Fusion)
    "BASFY",    # BASF (OTC ADR)
    "MKKGY",    # Merck KGaA (OTC ADR — nicht Merck US!)
    "FSNUY",    # Fresenius (OTC ADR)
    "RNMBY",    # Rheinmetall (OTC ADR, Defense)
    "VWAGY",    # Volkswagen (OTC ADR)
    "MBGAF",    # Mercedes-Benz (OTC ADR)
    "HBMRY",    # Heidelberg Materials (OTC ADR)
    "HENKY",    # Henkel (OTC ADR)
    "EADSY",    # Airbus (OTC ADR)
    "SBGSY",    # Schneider Electric (OTC ADR)
    # ── Frankreich ────────────────────────────────────────────────────────────
    "TTE",      # TotalEnergies (NYSE, liquid Options)
    "LRLCY",    # L'Oreal (OTC ADR)
    "LVMUY",    # LVMH (OTC ADR)
    "PPRUY",    # Kering (OTC ADR)
    "HESAY",    # Hermès (OTC ADR)
    "BNPQY",    # BNP Paribas (OTC ADR)
    "CFRUY",    # Richemont (OTC ADR)
    "PDRDY",    # Pernod Ricard (OTC ADR)
    "VCISY",    # Vinci (OTC ADR)
    "STM",      # STMicroelectronics (NYSE, US-listing)
    "AIVAF",    # Air Liquide (OTC ADR)
    # ── Niederlande ───────────────────────────────────────────────────────────
    "ASML",     # ASML (NASDAQ, primär US-listing)
    "PHG",      # Philips (NYSE ADR)
    "ING",      # ING Groep (NYSE ADR, liquid Options)
    "HEINY",    # Heineken (OTC ADR)
    # ── Schweiz ───────────────────────────────────────────────────────────────
    "NVS",      # Novartis (NYSE ADR, liquid Options)
    "RHHBY",    # Roche (OTC ADR)
    "NSRGY",    # Nestle (OTC ADR)
    "ABB",      # ABB (NYSE, US-listing)
    # CFR/ZURN entfernt — schlechte OTC-Liquidität (CFRUY bereits in Liste)
    # ── UK ────────────────────────────────────────────────────────────────────
    "AZN",      # AstraZeneca (NASDAQ, primär US-listing, liquid Options!)
    "SHEL",     # Shell (NYSE ADR, liquid Options)
    "BP",       # BP (NYSE ADR, liquid Options)
    "GSK",      # GSK (NYSE ADR, liquid Options)
    "RIO",      # Rio Tinto (NYSE ADR, liquid Options)
    "HSBC",     # HSBC (NYSE ADR, liquid Options)
    "VOD",      # Vodafone (NASDAQ ADR)
    "UL",       # Unilever (NYSE ADR)
    "DEO",      # Diageo (NYSE ADR)
    "BTI",      # British American Tobacco (NYSE ADR)
    "NGG",      # National Grid (NYSE ADR)
    # ── Skandinavien ──────────────────────────────────────────────────────────
    "NVO",      # Novo Nordisk (NYSE ADR, SEHR liquid Options!)
    "ERIC",     # Ericsson (NASDAQ ADR)
    "NOK",      # Nokia (NYSE ADR)
    "VOLVY",    # Volvo (OTC ADR)
    "ATLKY",    # Atlas Copco (OTC ADR)
    # ── Sonstige Europa ───────────────────────────────────────────────────────
    "E",        # Eni (NYSE ADR)
    "RACE",     # Ferrari (NYSE, primär US-listing, liquid Options!)
    "SNY",      # Sanofi (NASDAQ ADR)
    # ── Defensive Ergänzungen (Gemini-Empfehlung: Sektorparität) ─────────────
    "NUE",      # Nucor (Industrials/Materials — S&P500)
    "FCX",      # Freeport-McMoRan (Materials — liquid Options)
    "URI",      # United Rentals (Industrials — liquid Options)
    "WM",       # Waste Management (Defensive — liquid Options)
    "RSG",      # Republic Services (Defensive)
    "VMC",      # Vulcan Materials (Materials)
    "MLM",      # Martin Marietta (Materials)
]

# ── FTSE ALL-WORLD NON-US TOP 150 ─────────────────────────────────────────────
# ADRs (US-listed) bevorzugt — bessere yfinance-Datenqualitaet
# Heimatboersen als Fallback fuer Titel ohne liquides ADR
INTL_TIER1 = [
    # Europa — Technologie (ADR/US-listed)
    "ASML","STM","ERIC","NOK","SAP","INFN","KEYS",
    # Europa — Healthcare (ADR)
    "NVO","AZN","NVS","RHHBY","SNY","GSK","BAYRY","NVCR",
    # Europa — Energie & Rohstoffe (ADR)
    "SHEL","BP","TTE","ENLAY","E","ENGIY","SQM","RIO","BHP","VALE","SCCO",
    # Europa — Finanzen (ADR)
    "UBS","ING","BCS","HSBC","DB",  # INGA entfernt (Duplikat von ING); CS delisted
    # Europa — Konsum & Luxus (ADR)
    "LVMUY","CFRUY","PPRUY","HESAY","BURBY","ADDYY",
    # Europa — Industrie (ADR)
    "SIEGY","ATLKY","VOLVY","ABB","DSDVY",
    # Japan (ADRs only — Heimatboersen .T entfernt)
    "TM","HMC","SONY","NTT","MUFG","SMFG","MFG","NTDOY","KYOCY","FANUY",
    "CCOEY","ITOCY","MARUY",
    # Suedkorea (nur SSNLF OTC als ADR — .KS Heimatboersen entfernt)
    "SSNLF",   # Samsung ADR (OTC, begrenzte Liquidität — nur Monitoring)
    "MX",      # Magnachip (US-listed KR-Chip)
    # Taiwan (nur TSM US-listed — .TW Heimatboersen entfernt)
    "TSM",
    # China/Hongkong (nur US-gelistete ADRs — .HK entfernt)
    "BABA","JD","PDD","BIDU",
    "TCEHY","BYDDY","NIO","XPEV","LI",
    # Indien (ADR)
    "INFY","WIT","HDB","IBN","VEDL","RDY","TTM",
    # Kanada (US-listed)
    "SHOP","CNQ","SU","CNI","CP","TD","RY","BNS","ENB","TRP","NTR","CCO",
    # Australien (ADR)
    "BHP","RIO","WDS","ORG",
    # Brasilien (ADR)
    "VALE","PBR","ITUB","BBD","ABEV","BRKM",
    # Mexiko/Latam
    "AMX","FMXB",  # GMEXICOB.MX entfernt (Heimatboerse)
    # Suedafrika / EM Sonstiges
    "PROSSY","NPSNY",  # NPN.JO entfernt (Heimatboerse JSE)
    # Israel Tech
    "CHKP","NICE","CYBR","WIX","MNDY","GLBE","GTLB",
]

# ── SEKTOR-ETFs USA (2-5 pro Sektor) ─────────────────────────────────────────
# Breite Markt-Benchmarks
SECTOR_ETFS_BROAD = [
    "SPY","QQQ","IWM","DIA","VTI","MDY","IJR",          # US Broad
    "VEA","VWO","EFA","EEM","IEFA","IEMG",               # Ex-US Broad
    "ACWI","VT","URTH",                                  # World
]

# US Sektoren (SPDR XL-Familie + Alternativen)
SECTOR_ETFS_US = [
    # Technologie
    "XLK","VGT","FTEC","IYW","QTEC",
    # Semiconductors
    "SMH","SOXX","SOXQ","USD",
    # Software / Cyber
    "IGV","BUG","CIBR","HACK","WCLD",
    # Financials
    "XLF","VFH","IYF","KRE","KBE",
    # Healthcare
    "XLV","VHT","IYH",
    # Biotech / Pharma
    "XBI","IBB","ARKG","PJP","BBP",
    # Energie
    "XLE","VDE","IYE","OIH","XOP",
    # Industrials
    "XLI","VIS","IYJ",
    # Defense & Aerospace
    "ITA","XAR","DFEN","PPA",
    # Consumer Discretionary
    "XLY","VCR","IYC",
    # Consumer Staples
    "XLP","VDC","IYK",
    # Utilities
    "XLU","VPU","IDU",
    # Real Estate
    "XLRE","VNQ","IYR","REET",
    # Materials
    "XLB","VAW","IYM",
    # Communication
    "XLC","VOX","IYZ",
    # Clean Energy / ESG
    "ICLN","QCLN","CNRG","ACES","ESGU",
    # AI & Robotics
    "BOTZ","ROBO","IRBO","AIQ","THNQ",
    # Crypto-related
    "BITO","GBTC","ETHA",
    # Commodities
    "GLD","IAU","GLDM","SLV","PPLT","PDBC","DJP","USO","UNG","CORN",
    # Bonds
    "TLT","IEF","SHY","HYG","LQD","EMB","BND","VCIT","VCSH","TIPS",
]

# Ex-US Sektoren (iShares / Vanguard international)
SECTOR_ETFS_EXUS = [
    # Europa
    "EZU","VGK","IEUR","FEZ","EWG","EWU","EWF","EWI","EWQ","EWP","EWN","EWD","EWL",
    # Asien Developed
    "EWJ","EWA","EWH","EWS","EWY",
    # Asien Emerging
    "FXI","KWEB","MCHI","EWT","INDA","VNM",
    # Latam
    "EWZ","EWW","ILF",
    # Sector Ex-US
    "IXUS","VXUS",
    # Ex-US Technologie
    "IFRA","IQLT",
    # Ex-US Energie
    "IXC",
    # Ex-US Healthcare
    "IXJ",
    # Ex-US Financials
    "IXG",
    # Schwellenlaender Sektoren
    "EMXC","EEMS","EMSG",
]

# Zusammengefasst (fuer Aggregator)
SECTOR_ETFS = list(dict.fromkeys(
    SECTOR_ETFS_BROAD + SECTOR_ETFS_US + SECTOR_ETFS_EXUS
))

# ── KRYPTO ────────────────────────────────────────────────────────────────────
CRYPTO_TICKERS = [
    "BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD",
    "ADA-USD","AVAX-USD","DOGE-USD","DOT-USD","POL-USD",
    "LINK-USD","UNI-USD","ATOM-USD","LTC-USD","BCH-USD",
]

# ── SEKTOR-WATCHLISTEN (fuer Deep-Dive & EIC-Vorschlaege) ────────────────────
SECTOR_WATCHLISTS = {
    "AI_TECH":      ["NVDA","AMD","MSFT","GOOGL","META","PLTR","ARM","SMCI","MSTR","NET","CRDO","ALAB"],
    "SEMIS":        ["NVDA","AMD","AVGO","QCOM","TXN","AMAT","LRCX","KLAC","MU","ASML","MRVL","NXPI","ADI"],
    "DEFENSE":      ["LMT","RTX","NOC","GD","BA","KTOS","AXON","HII","TDG","HWM","RNMBY","EADSY","HEICO"],
    "BIOTECH":      ["MRNA","BNTX","REGN","VRTX","GILD","BIIB","ILMN","ARKG","ABBV","LLY","NVO","AZN"],
    "CLEAN_ENERGY": ["ENPH","FSLR","SEDG","RUN","BE","PLUG","NEE","ARRY","NOVA","BLDP","ICLN","QCLN"],
    "FINTECH":      ["SQ","HOOD","AFRM","SOFI","UPST","COIN","PYPL","V","MA","SCHW","NU","STNE"],
    "GLPONE":       ["LLY","NVO","VKTX","RYTM","AMGN","REGN","AZN","SNY","GILD","PFE","RHHBY"],
    "PICKS_SHOVELS":["NVDA","AMD","AVGO","AMAT","LRCX","TSM","ARM","KLAC","SNPS","CDNS","ONTO","ACLS"],
    "WHEEL_STOCKS": ["DDOG","AMSC","IREN","CIFR","PBR","CLSK","NVO","HOOD","ENVX","MRVL","COIN","HOOD"],
    "LUXURY_EU":    ["LVMUY","LRLCY","HESAY","CFRUY","PPRUY","ADDYY","BURBY","RACE","CPRI","RL"],
    "JAPAN_TECH":   ["TM","SONY","NTDOY","KYOCY","FANUY","CCOEY","SONY","HMC"],
    "EM_GROWTH":    ["TSM","BABA","PDD","INFY","VALE","ITUB","NU","STNE","SE","GRAB"],
}

# ── RS-REFERENZ ETFs fuer Sektor Relative-Staerke ─────────────────────────────
RS_SECTOR_ETFS = [
    "XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLRE","XLB","XLC",
    "SMH","SOXX","IBB","XBI","ARKK","BOTZ","ITA","ICLN","VNQ",
    # Ex-US RS
    "EZU","EWJ","EWG","FXI","INDA","EWZ","EWY","EWT",
]


# ── FTSE 100 TOP 40 (London Stock Exchange) ───────────────────────────────────
# FTSE100/STOXX_EU_EXTRA: NUR Referenz (Heimatboersen — keine US-Optionen)
FTSE100_TICKERS = ['AZN.L', 'SHEL.L', 'HSBA.L', 'ULVR.L', 'RIO.L', 'BP.L', 'GSK.L', 'REL.L', 'BATS.L', 'DGE.L', 'NG.L', 'VOD.L', 'BA.L', 'EXPN.L', 'LSEG.L', 'PRU.L', 'AAL.L', 'GLEN.L', 'NWG.L', 'LLOY.L', 'BT-A.L', 'MNG.L', 'AV.L', 'TSCO.L', 'ABF.L', 'IMB.L', 'STAN.L', 'WPP.L', 'CRH.L', 'IHG.L', 'RKT.L', 'SSE.L', 'BME.L', 'EZJ.L', 'IAG.L', 'RR.L', 'SBRY.L', 'MKS.L', 'JD.L', 'SPX.L']

# ── STOXX EUROPE EXTRA (Schweiz, Skandinavien, Benelux) ──────────────────────
STOXX_EU_EXTRA = ['NOVO-B.CO', 'DSV.CO', 'CARL-B.CO', 'ORSTED.CO', 'MAERSK-B.CO', 'GIVN.SW', 'SIKA.SW', 'LONN.SW', 'ROG.SW', 'NOVN.SW', 'ABBN.SW', 'ZURN.SW', 'ALC.SW', 'PGHN.SW', 'HOLN.SW', 'ERICB.ST', 'VOLVA.ST', 'ATCO-A.ST', 'SAND.ST', 'SEB-A.ST', 'UCB.BR', 'KER.PA', 'KNEBV.HE']

# ── BEAR-KANDIDATEN US (Momentum/Hype-Titel mit hohem Rückschlagpotenzial) ───
BEAR_US_TICKERS = ['SMCI', 'MSTR', 'MRVL', 'ALAB', 'CRWD', 'SNOW', 'NET', 'DDOG', 'MDB', 'SHOP', 'SQ', 'HOOD', 'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'ENPH', 'FSLR', 'PLUG', 'BE', 'MRNA', 'BNTX', 'ILMN', 'BIIB', 'ZM', 'DOCU', 'UBER', 'LYFT', 'ABNB', 'DASH', 'RBLX', 'SNAP', 'PINS', 'MTCH', 'UPST', 'AFRM', 'SOFI', 'GME', 'PLTR', 'COIN', 'TSLA', 'BABA', 'PDD', 'BIDU', 'AMD', 'NVDA', 'ARM']

# ── BEAR-KANDIDATEN DE/EU (Zykliker, Immobilien, Hochverschuldete) ───────────
BEAR_DE_EU_TICKERS = ['BAYN.DE', 'VOW3.DE', 'BMW.DE', 'MBG.DE', 'CON.DE', 'DHER.DE', 'ZAL.DE', 'VNA.DE', 'LEG.DE', 'TAG.DE', '1COV.DE', 'EVT.DE', 'SRT.DE', 'NDX1.DE', 'AIXA.DE', 'WAF.DE', 'IFX.DE', 'STLAM.MI', 'RNO.PA', 'VOD.L', 'BT-A.L', 'TEF.MC', 'UCB.BR', 'GLPG.BR', 'ARND.DE', 'WDP.BR', 'RWE.DE', 'ENEL.MI', 'EZJ.L', 'IAG.L', 'DTE.DE', 'GLEN.L', 'AAL.L']

def build_ticker_universe():
    seen = set()
    result = []
    # Alle Quellen zusammenführen
    all_sources = (
        SP500_TICKERS + NASDAQ100_EXTRA +
        # EU_ADR_TICKERS: US-gelistete ADRs/Primärlistings (ersetzt .DE/.PA/.AS/.L etc.)
        EU_ADR_TICKERS +
        # BEAR_DE_EU: nur fuer Bear-Scanner Referenz (keine Options-Kandidaten)
        BEAR_US_TICKERS + BEAR_DE_EU_TICKERS +
        INTL_TIER1 + SECTOR_ETFS + CRYPTO_TICKERS +
        [t for wl in SECTOR_WATCHLISTS.values() for t in wl]
    )
    # Filter: keine leeren Strings, keine bekannt ungueltige Symbole
    # Fix Gemini: Doppelte BAD_SYMS zusammengeführt (zweite Zeile überschrieb erste)
    BAD_SYMS = {"CS","SAMSUNG","SoftBank","CSCO.DE","SDAX.DE","MDNT.DE",
                "STRN.DE","SKB.DE","SLT.DE","ARND.DE","SSNLF","2330.TW",
                "9988.HK","0700.HK","3690.HK","1810.HK",
                "STLAM.MI","WDP.BR","ARND.DE","GLPG.BR",  # schlechte Verfuegbarkeit
                "SPX.L","BME.L","MNG.L","SDAX",  # nicht eindeutig
                }  # Schlechte Yahoo-Daten
    for t in all_sources:
        if t and t not in seen and t not in BAD_SYMS:
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
        if series[i] is not None:
            # Fix A: Wenn vorheriger EMA None (Datenlücke), hole letzten verfügbaren Wert
            prev_ema = next((result[j] for j in range(i-1, -1, -1) if result[j] is not None), None)
            if prev_ema is not None:
                result[i] = series[i] * k + prev_ema * (1 - k)
        else:
            # Datenlücke: letzten bekannten EMA weiterführen (kein None-Kaskaden-Bug)
            result[i] = result[i-1]
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
    # Gemini Bug C: Normalisierung auf Avg-Vol-20 → vergleichbar zwischen Titeln
    lookback_vol = min(20, len(volumes))
    avg_vol = sum(volumes[-lookback_vol:]) / lookback_vol if lookback_vol > 0 else 0
    if avg_vol and avg_vol > 0:
        return round(trend / avg_vol, 3)
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


def calc_hv_percentile(closes, window=30, lookback=252):
    """
    Berechnet Historical Volatility Percentile (HVP).
    HVP = wie hoch ist die aktuelle 30T-HV im Vergleich zu den letzten 252 Handelstagen?
    Returns: int 0-100 oder None
    """
    import math
    # Adaptiver lookback: passt sich an verfügbare Bars an
    # Behebt: period="1y" liefert nur ~251 Bars, fixer Guard 302 blockiert alle
    available = len(closes) - window - 5  # 5 Bars Sicherheitsabstand
    if available < 30:  # Mindestens 30 historische HV-Punkte für stabilen Percentil
        return None
    lookback = min(lookback, available)  # Adaptiv: nie mehr als vorhanden
    try:
        def hv30(cls):
            cls = [c for c in cls if c and c > 0]
            if len(cls) < 2:
                return None
            log_rets = [math.log(cls[i] / cls[i-1]) for i in range(1, len(cls))]
            if not log_rets:
                return None
            mean_lr = sum(log_rets) / len(log_rets)
            variance = sum(x**2 for x in log_rets) / len(log_rets) - mean_lr**2
            return math.sqrt(252) * math.sqrt(max(0.0, variance))

        # Aktuelle HV
        current_hv = hv30(closes[-window:])
        if current_hv is None:
            return None

        # Historische HV-Serie — per-Window Exception-Handling
        # (ein schlechtes Fenster killt nicht die gesamte Percentil-Berechnung)
        hv_series = []
        for i in range(lookback):
            try:
                end = len(closes) - i
                start = end - window
                if start < 0:
                    break
                hv = hv30(closes[start:end])
                if hv is not None:
                    hv_series.append(hv)
            except Exception:
                continue


        if not hv_series:
            return None

        # Percentile: wie viele historische HVs sind kleiner als die aktuelle?
        pct = sum(1 for h in hv_series if h < current_hv) / len(hv_series) * 100
        return round(pct)
    except Exception:
        return None


def score_options_csp(r: dict) -> int:
    """
    Cash-Secured Put Score 0-100 — Unleashed v2 (Gemini-Blueprint).
    Deckt ATM-CSP, Wheel und wöchentliche CSP+LongCall-Kombinationen ab.

    Kernänderung: Ema200-Gate aufgeweicht auf 5%-Puffer (Bodenbildungsphase
    erlaubt), damit hohe Prämien in Pullback-Phasen nicht gefiltert werden.
    Seitwärtsregime wird stärker belohnt als Bull (Theta-Decay-Paradisziplin).
    """
    price  = r.get("price", 0) or 0
    ema200 = r.get("ema200")
    ema50  = r.get("ema50")
    hvp    = r.get("hvp", 0) or 0
    rsi    = r.get("rsi", 50) or 50
    bbpos  = r.get("bbPos")
    regime = (r.get("regime") or "").lower()

    # Gate 1: Preis nicht mehr als 5% unter EMA200 (strukturelle Bärenmärkte raus,
    #         Bodenbildung/Pullback erlaubt — genau hier sind Prämien am höchsten)
    if not ema200: return 0
    if price < ema200 * 0.95: return 0

    # Gate 2: Mindest-Volatilität für attraktive Prämie
    if hvp < 20: return 0

    s = 0

    # Bollinger-Position: ATM/Wheel liebt Ausverkauf am unteren Band
    if bbpos is not None:
        if   bbpos <= 0.20: s += 30   # Krasser Ausverkauf = maximale Prämie am Support
        elif bbpos <= 0.40: s += 15

    # Regime: Seitwärtsphasen sind Paradedisziplin für CSPs (Theta-Verfall maximal)
    if   regime == "side":     s += 30
    elif regime == "bull":     s += 20
    elif regime == "volatile": s += 10

    # RSI: Überverkaufte Situationen bieten den höchsten statistischen Edge
    if   rsi < 30:       s += 35   # Extremer Ausverkauf — beste ATM-Prämien
    elif rsi <= 45:      s += 25   # Gesunder Pullback
    elif rsi <= 60:      s += 10   # Neutrale Zone noch akzeptabel

    # HVP-Bonus: je höher die historische Vola, desto attraktiver die Prämie
    s += min(hvp // 5, 15)         # Max 15 Pkt (HVP 75+ → voll)

    # 10-Tage-HV Short-Term Boost (für Weeklies): wenn vorhanden und erhöht
    hv10 = r.get("hv10")
    if hv10 is not None and hv10 > 25:
        s += 5                     # Kurzfristiger Vola-Spike begünstigt Weeklies

    return max(0, min(100, s))


def score_options_covered_call(r: dict) -> int:
    """
    Covered Call Score 0-100 — Gemini v3.
    CCs brauchen strukturell stabile Underlyings: EMA50-Gate schützt vor
    fallenden Messern. Leicht überkaufte Phasen (RSI 55-70) sind ideal,
    da Call-Prämien teuer sind. Überhitzte Titel (overheat>75) ausschließen
    — Gefahr verpasster Mega-Rallies beim Cap.
    """
    comp_score = r.get("score", 50) or 50
    price      = r.get("price", 0) or 0
    ema50      = r.get("ema50")
    hvp        = r.get("hvp", 0) or 0
    regime     = (r.get("regime") or "").lower()
    rsi        = r.get("rsi", 50) or 50
    overheat   = r.get("overheat", 0) or 0

    # Gates: Schutz vor strukturellen Abwärtstrends
    if comp_score < 45:            return 0  # Mindestkvalität
    if ema50 and price < ema50:    return 0  # Aktie MUSS über EMA50 (kein fallender Messerfang)
    if overheat > 75:              return 0  # Keine CCs bei extrem überhitzten Titeln

    s = 0
    # CCs lieben leicht überkaufte Phasen — Call-Prämien teuer, Kurs begrenzt
    if   55 <= rsi <= 70: s += 35
    elif 45 <= rsi < 55:  s += 15

    # Regime: Bull = Prämie gut aber Kurs kann wegrennen; Side = reiner Theta-Gewinn
    if   regime == "bull": s += 30
    elif regime == "side": s += 25

    # HVP: Gesunde Bandbreite — nicht zu tief (wenig Prämie), nicht zu hoch (Event-Risiko)
    if 30 <= hvp <= 65: s += 20
    elif hvp > 65:      s += 10   # Noch akzeptabel, aber erhöhtes Gap-Risiko

    return max(0, min(100, s))


def score_options_credit_spread(r: dict) -> int:
    """
    Credit Spread Score 0-100 — Gemini v3.
    Bull Put Spread: direktionaler Edge an Bollinger-Unterband im Bull/Side-Regime.
    Bear Call Spread: Überdehnung an Bollinger-Oberband in Volatile/Bear-Regime.
    HVP-Gate 25 (gesenkt): Spreads sind risikobegrenzt, kein extremes HVP nötig.
    Präzises Bollinger-Pricing statt HVP als primäres Signal.
    """
    price  = r.get("price", 0) or 0
    ema50  = r.get("ema50")
    bbpos  = r.get("bbPos")
    hvp    = r.get("hvp", 0) or 0
    regime = (r.get("regime") or "").lower()

    # Minimale Vola für überhaupt eine handelbare Prämie
    if hvp < 25:   return 0
    if not ema50:  return 0

    s = 0

    # ── BULL PUT SPREAD: Dip im Aufwärtstrend ──────────────────────────────
    if regime in ("bull", "side") and price > ema50:
        s += 25
        if bbpos is not None:
            if bbpos <= 0.20:   s += 40  # Perfekter Ausverkauf: Short-Put-Strike weit weg
            elif bbpos <= 0.35: s += 25  # Dip: gutes Chancen/Risiko-Verhältnis
        s += min(hvp // 4, 20)           # HVP-Bonus (moderat gewichtet)

    # ── BEAR CALL SPREAD: Überdehnung im schwachen Markt ───────────────────
    elif regime in ("volatile", "bear"):
        if bbpos is not None and bbpos >= 0.80:
            s += 30                      # Aktie stößt an Oberkante — ideal für Bear Call
            s += min(hvp // 3, 25)       # Höhere HVP = teurere Calls zu verkaufen

    return max(0, min(100, s))

def calc_markov(closes, lookback=60, stride=1):
    """Markov 2.0 Regime-Signal — stride=1 fuer korrekte Uebergangswahrscheinlichkeiten.
    Fix E: stride=7 erzeugte 85% Autokorrelation → p_bull2bear statistisch bedeutungslos.
    Mit stride=1 werden echte diskrete Tagesübergänge gemessen.
    Regime-Label basiert auf 5T-Return fuer Rauschen-Reduktion.
    """
    if len(closes) < lookback:
        return None, None, None
    recent = closes[-lookback:]
    # Regime-Labels: 5T-Return fuer Stabilität, aber 1T-Uebergaenge messen
    labels = []
    smooth_window = 5
    for i in range(smooth_window, len(recent)):
        ret = (recent[i] / recent[i-smooth_window]) - 1
        if   ret >  0.03: labels.append('bull')
        elif ret < -0.03: labels.append('bear')
        else:             labels.append('side')

    if len(labels) < 10:
        return None, None, None

    # Transitions in 1T-Schritten (keine Autokorrelation)
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


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGIE-SCORING ENGINE v1.0 — Multi-Strategy Leaderboards
# Implementiert nach Gemini-Blueprint (Strategie-Matrix)
# Jede Funktion gibt normalisierten Score 0-100 zurueck
# ══════════════════════════════════════════════════════════════════════════════

def score_long_minervini(r: dict) -> int:
    """
    Minervini SEPA: Stage 2 Uptrend + VCP (Volatility Contraction) + Volumen-Ausbruch.
    Gemini-Refactoring v2: HVP-Integration (niedrige Vola = VCP-Ideal), strikterer Dist200.
    """
    s = 0
    price    = r.get("price", 0)
    ema50    = r.get("ema50")
    ema200   = r.get("ema200")
    pct_high = r.get("pctFromHigh52")
    dist200  = r.get("dist200")
    vol_ratio= r.get("volRatio", 1) or 1
    obv      = r.get("obvTrend", 0) or 0
    macd_h   = r.get("macdHist")
    p_b2b    = r.get("pBull2Bear", 0) or 0
    rsi      = r.get("rsi")
    hvp      = r.get("hvp")

    # Gate 1: Stage 2 Uptrend — Pflicht
    if not ema50 or not ema200: return 0
    if price < ema50 or price < ema200 or ema50 < ema200: return 0
    s += 25

    # Gate 2: Naehe zum 52W-Hoch
    if pct_high is not None:
        if pct_high >= -5:    s += 20
        elif pct_high >= -10: s += 12
        elif pct_high >= -15: s += 6

    # Gate 3: Abstand EMA200 — Gemini: Obergrenze von 50 auf 40 gesenkt
    if dist200 is not None:
        if 10 <= dist200 <= 40:   s += 15
        elif 5 <= dist200 < 10:   s += 8
        elif dist200 > 50:         s -= 15  # Gemini: von -10 auf -15 verschaerft

    # Gate 4: Volumen-Akkumulation
    if vol_ratio > 1.5:   s += 15
    elif vol_ratio > 1.2: s += 8
    if obv > 0:           s += 10

    # Gate 5: Momentum
    if macd_h is not None and macd_h > 0: s += 10

    # Gate 6: Markov
    if p_b2b > 0.25:   s -= 15
    elif p_b2b < 0.08: s += 5

    # Gate 7: HVP + VCP (Gemini-Fix: Gate 25→40 — verhindert Verpassen von Ausbruchstagen)
    if hvp is not None:
        if hvp <= 40:   s += 10  # Kontraktion UND frühe Ausbrüche erfasst (war ≤25 — zu eng)
        elif hvp >= 75: s -= 15  # Zu erratisch fuer SEPA

    # bbPos VCP-Erkennung: Stage-2 Coiling nahe Hochs = klassisches SEPA-Setup
    bbpos = r.get('bbPos')
    if bbpos is not None:
        if 0.70 <= bbpos <= 0.92:  s += 10  # VCP: Kompression nahe Hochs
        elif bbpos > 0.95:         s -= 5   # Überschießen — zu spät für Einstieg

    # Gate 8: RSI — Gemini: Schwelle von 85 auf 80 gesenkt
    if rsi and rsi > 80: s -= 15

    return max(0, min(100, s))


def score_long_swing(r: dict) -> int:
    """
    Swing-Pullback: EMA50-Bounce im Aufwaertstrend.
    Gemini-Fix v2: Richtungskorrektur EMA50-Abstand (nur UEBER EMA50 belohnen),
    Basis auf 20 erhoehen, HVP-Integration (moderate Vola bevorzugt).
    """
    s = 0
    price   = r.get("price", 0)
    ema50   = r.get("ema50")
    ema200  = r.get("ema200")
    rsi     = r.get("rsi")
    macd_h  = r.get("macdHist")
    bbpos   = r.get("bbPos")
    obv     = r.get("obvTrend", 0) or 0
    p_b2b   = r.get("pBull2Bear", 0) or 0
    hvp     = r.get("hvp")

    # Gate 1: Uebergeordneter Uptrend
    if not ema200 or price < ema200: return 0
    s += 20  # Gemini: Basis von 15 auf 20 erhoehen

    # Gate 2: Pullback-Zone
    if rsi is not None:
        if 30 <= rsi <= 48:   s += 25   # Gemini: engere Pullback-Zone
        elif 25 <= rsi < 30:  s += 15
        elif 48 < rsi <= 58:  s += 10
        elif rsi > 70:         s -= 15  # Gemini: haertere Abstrafung

    # Gate 3: Gemini-Fix — nur belohnen wenn Kurs UEBER oder exakt AM EMA50
    if ema50:
        if price >= ema50:
            dist50 = ((price / ema50) - 1) * 100
            if dist50 <= 2.5:   s += 20   # Praziser Bounce-Bereich
            elif dist50 <= 5.0: s += 12
        else:
            s -= 10  # Gemini: Abzug wenn EMA50 unterschritten

    # Gate 4: Bollinger Band
    if bbpos is not None:
        if bbpos <= 0.25:   s += 15
        elif bbpos <= 0.40: s += 8

    # Gate 5: OBV
    if obv >= 0: s += 10

    # Gate 6: MACD
    if macd_h is not None and macd_h > 0: s += 10

    # Gate 7: Markov
    if p_b2b > 0.25: s -= 20

    # Gate 8: HVP — moderate Vola bevorzugt (Gemini-Integration)
    if hvp is not None:
        if 20 <= hvp <= 60: s += 5
        elif hvp > 80:      s -= 15

    return max(0, min(100, s))


def score_long_mean_reversion(r: dict) -> int:
    """
    Mean Reversion Long: Extreme Kapitulation, weit unter EMA200.
    Gemini-Fix v2: HVP-Integration (hohe Vola = echter Bounce-Kandidat,
    niedrige Vola = Value Trap), RSI-Extremwert verschaerft.
    """
    s = 0
    price   = r.get("price", 0)
    ema200  = r.get("ema200")
    atr     = r.get("atr")
    rsi     = r.get("rsi")
    bbpos   = r.get("bbPos")
    overheat= r.get("overheat", 0) or 0
    vol_ratio = r.get("volRatio", 1) or 1
    hvp     = r.get("hvp")

    if not ema200 or not atr or atr == 0: return 0
    dist_atr = (price - ema200) / atr

    if dist_atr >= 0: return 0

    dist_abs = abs(dist_atr)
    if   dist_abs >= 4.0: s += 40
    elif dist_abs >= 3.0: s += 28
    elif dist_abs >= 2.0: s += 15
    else: return 0

    # Gemini: RSI-Extremwert von 20 auf 18 verschaerft
    if rsi is not None:
        if   rsi <= 18: s += 30
        elif rsi <= 25: s += 20
        elif rsi <= 30: s += 12
        elif rsi <= 35: s += 5

    # Gemini: BBPos-Schwelle verschaerft (nur 2 Stufen)
    if bbpos is not None:
        if   bbpos <= 0.05: s += 20
        elif bbpos <= 0.15: s += 12

    if vol_ratio >= 2.0: s += 10
    if overheat > 30:    s -= 10

    # HVP-Integration (Gemini): Gummiband-Effekt nur bei hoher hist. Vola
    if hvp is not None:
        if hvp >= 80:  s += 10  # Echter Bounce-Kandidat mit hist. Vola-Hintergrund
        elif hvp < 40: s -= 20  # Value Trap — keine lahmenden Enten einsammeln

    return max(0, min(100, s))


def score_short_breakdown(r: dict) -> int:
    """
    Short Breakdown: Death-Cross-Bereich, fallender OBV, Distribution.
    Gemini-Fix v2: RSI-Gate entschaerft (dynamische Breakdowns erhalten),
    Score-Werte entzerrt (Max war 140 → jetzt ~100), HVP-Integration.
    """
    s = 0
    price    = r.get("price", 0)
    ema50    = r.get("ema50")
    ema200   = r.get("ema200")
    atr      = r.get("atr")
    rsi      = r.get("rsi")
    macd_h   = r.get("macdHist")
    obv      = r.get("obvTrend", 0) or 0
    vol_ratio= r.get("volRatio", 1) or 1
    regime   = (r.get("regime") or "").lower()
    bbpos    = r.get("bbPos")
    hvp      = r.get("hvp")

    if not ema200 or price <= 0: return 0
    if ema50 and price > ema50 * 1.02: return 0
    if price > ema200 * 0.995: return 0
    if atr and atr > 0:
        if (price - ema200) / atr < -6.0: return 0  # Kapitulation → MR, kein Short
    s += 15  # Gemini: von 20 auf 15 gesenkt (Score-Entzerrung)

    if ema50 and ema50 < ema200: s += 10  # Gemini: von 15 auf 10
    if ema50 and price < ema50:  s += 10

    # Gemini-Fix: RSI-Gate entschaerft — dynamische Breakdowns nicht abschneiden
    if rsi is not None:
        if rsi < 20 or rsi > 65: return 0   # <20 = zu spaet, >65 = Bullen-Struktur
        if 30 <= rsi <= 45:   s += 15        # Gemini: von 20 auf 15
        elif 20 <= rsi < 30:  s += 8         # Dynamische Breakdowns erlaubt

    if obv is not None and obv < 0:  s += 10  # Gemini: von 15 auf 10
    if macd_h is not None and macd_h < 0: s += 10  # Gemini: von 15 auf 10

    if bbpos is not None and bbpos <= 0.25: s += 10  # Gemini: vereinfacht

    if "bear" in regime: s += 10
    if vol_ratio > 1.3:  s += 10  # Gemini: von 1.2 auf 1.3 (strenger)

    # HVP-Integration (Gemini): steigende Vola = Short-Dynamik
    if hvp is not None and hvp >= 65: s += 10

    return max(0, min(100, s))


def score_short_fading(r: dict) -> int:
    """
    Short Fading (FOMO-Climax): Extreme Ueberdehnung + Kauf-Erschoepfung.
    Gemini-Fix v2: BBPos-Schwelle 0.92->0.85, HVP Squeeze-Schutz.
    """
    s = 0
    price    = r.get("price", 0)
    ema200   = r.get("ema200")
    atr      = r.get("atr")
    rsi      = r.get("rsi")
    bbpos    = r.get("bbPos")
    overheat = r.get("overheat", 0) or 0
    vol_ratio= r.get("volRatio", 1) or 1
    p_b2b    = r.get("pBull2Bear", 0) or 0
    obv      = r.get("obvTrend", 0) or 0
    hvp      = r.get("hvp")

    if not ema200 or not atr or atr == 0: return 0
    dist_atr = (price - ema200) / atr

    if dist_atr < 2.5: return 0
    if   dist_atr >= 4.0: s += 30
    elif dist_atr >= 3.0: s += 20
    else:                  s += 15

    if rsi is None or rsi <= 68: return 0
    if   rsi >= 80: s += 25
    elif rsi >= 75: s += 18
    else:           s += 10

    # Gemini: BBPos-Schwelle von 0.92 auf 0.85 gesenkt
    if bbpos is not None and bbpos >= 0.85: s += 15

    if   overheat >= 75: s += 15
    elif overheat >= 55: s += 8

    # Gemini: Kauf-Erschoepfung
    if vol_ratio and vol_ratio < 0.80: s += 10
    if obv < 0:                         s += 7

    if p_b2b > 0.20: s += 10

    # HVP-Integration (Gemini): Squeeze-Schutz — KRITISCH
    if hvp is not None:
        if hvp >= 85:   s -= 20  # Short-Squeeze / Meme-Stock Gefahr
        elif hvp <= 40: s += 8   # Ruhiger Erschoepfungs-Peak

    return max(0, min(100, s))


def calc_last_swing_high(highs: list, lookback: int = 20) -> float | None:
    """Berechnet das letzte signifikante Swing-Hoch (fuer Short Stop-Loss)."""
    if len(highs) < lookback + 2:
        return None
    window = highs[-(lookback+2):-1]   # ohne letzten Bar
    # Swing-Hoch = lokales Maximum (hoeher als n-1 und n+1)
    swing_highs = []
    for i in range(1, len(window)-1):
        if window[i] > window[i-1] and window[i] > window[i+1]:
            swing_highs.append(window[i])
    return round(max(swing_highs), 4) if swing_highs else round(max(window), 4)


def calc_last_swing_low(lows: list, lookback: int = 20) -> float | None:
    """Berechnet das letzte signifikante Swing-Tief (fuer Long Stop-Loss)."""
    if len(lows) < lookback + 2:
        return None
    window = lows[-(lookback+2):-1]
    swing_lows = []
    for i in range(1, len(window)-1):
        if window[i] < window[i-1] and window[i] < window[i+1]:
            swing_lows.append(window[i])
    return round(min(swing_lows), 4) if swing_lows else round(min(window), 4)


def apply_macro_risk_overlay(options_candidates: list, dix_gex: dict, pcr_data: dict) -> list:
    """
    Macro Risk Overlay — Gemini-Blueprint.
    Skaliert Options-Scores dynamisch anhand von GEX (institutionelles Gamma)
    und PCR (Put/Call-Ratio). Wenn Gamma-Flip oder Panik erkannt → aggressive
    nackte Strategien (ATM-CSP) abwerten, risikobegrenzte Spreads aufwerten.
    """
    gex = (dix_gex or {}).get("gex", 0)   # in Mrd USD (kann negativ sein)
    pcr = (pcr_data or {}).get("pcr", 0.9)

    for r in options_candidates:
        # ── GEX negativ: Gamma-Flip-Zone → Gap-Risiko für nackte Puts ────────────
        if gex < 0:
            # ATM-CSPs abwerten (Slippage-Risiko bei unkontrollierten Gaps)
            if r.get("scoreCsp", 0) > 0:
                r["scoreCsp"] = max(0, int(r["scoreCsp"] * 0.55))
                r["_macroNote"] = "GEX negativ — CSP abgewertet (Gap-Risiko)"
            # Risikobegrenzte Spreads bevorzugen
            if r.get("scoreSpread", 0) > 0:
                r["scoreSpread"] = min(100, int(r["scoreSpread"] * 1.20))

        # ── PCR < 0.75: Extremes Bull-Sentiment → CCs gefährdet (Rallye-Kapper) ──
        if pcr < 0.75:
            if r.get("scoreCc", 0) > 0:
                r["scoreCc"] = max(0, int(r["scoreCc"] * 0.60))
                r["_macroNote"] = r.get("_macroNote", "") + " | PCR<0.75 — CC abgewertet"

        # ── PCR > 1.10: Panik-Modus → CSPs riskant, Spreads attraktiv ────────────
        if pcr > 1.10:
            if r.get("scoreCsp", 0) > 0:
                r["scoreCsp"] = max(0, int(r["scoreCsp"] * 0.70))
            if r.get("scoreSpread", 0) > 0:
                r["scoreSpread"] = min(100, int(r["scoreSpread"] * 1.15))
                r["_macroNote"] = r.get("_macroNote", "") + " | PCR>1.10 — Spread bevorzugt"

        # Gesamtscore nach Overlay neu berechnen
        r["optsScore"] = max(r.get("scoreCsp", 0), r.get("scoreCc", 0), r.get("scoreSpread", 0))

    return options_candidates


def build_leaderboards(results: list, market_regime: str = "NEUTRAL") -> dict:
    """
    Berechnet alle 5 Strategie-Scores und erstellt sortierte Leaderboards.
    Gibt auch Master-Shortlist (Top 15 regime-adaptiv) zurueck.
    """
    log.info("  Berechne Multi-Strategie Leaderboards...")
    scored = []

    for r in results:
        if r.get("error") or not r.get("price"):
            continue

        sym = r["sym"]
        s_minervini = score_long_minervini(r)
        s_swing     = score_long_swing(r)
        s_mr_long   = score_long_mean_reversion(r)
        s_breakdown = score_short_breakdown(r)
        s_fading    = score_short_fading(r)

        # Best Long / Short Score
        best_long  = max(s_minervini, s_swing, s_mr_long)
        best_short = max(s_breakdown, s_fading)

        # Short-Richtung
        short_dir = None
        if best_short >= 30:
            short_dir = "BREAKDOWN" if s_breakdown >= s_fading else "FADING"

        # Kompaktes Scoring-Objekt (inkl. Chart-Felder fuer Alpha Desk Parität)
        scored.append({
            "sym":           sym,
            "price":         r.get("price"),
            "score":         r.get("score"),        # Composite (bestehend)
            "grade":         r.get("grade"),
            "rsi":           r.get("rsi"),
            "atr":           r.get("atr"),
            "regime":        r.get("regime"),
            "overheat":      r.get("overheat"),
            "pBull2Bear":    r.get("pBull2Bear"),
            # Chart-Metriken fuer Alpha Desk / Scanner-Parität
            "ema50":         r.get("ema50"),
            "ema200":        r.get("ema200"),
            "macdHist":      r.get("macdHist"),
            "obvTrend":      r.get("obvTrend"),
            "bbPos":         r.get("bbPos"),
            "volRatio":      r.get("volRatio"),
            "hvp":           r.get("hvp"),
            "hv10":          r.get("hv10"),
            "pctFromHigh52": r.get("pctFromHigh52"),
            "dist200":       r.get("dist200"),
            "dist50":        r.get("dist50"),
            "high52":        r.get("high52"),
            "low52":         r.get("low52"),
            "bullSignals":   r.get("bullSignals"),
            # Strategie-Scores
            "sMinervini":    s_minervini,
            "sSwing":        s_swing,
            "sMrLong":       s_mr_long,
            "sBreakdown":    s_breakdown,
            "sFading":       s_fading,
            "bestLong":      best_long,
            "bestShort":     best_short,
            "shortDir":      short_dir,
        })

    # ── LEADERBOARDS (Top 20 je Strategie) ───────────────────────────────────
    def top20(key, min_score=35):
        return [
            {"sym": x["sym"], "score": x[key], "price": x["price"],
             "grade": x["grade"], "rsi": x["rsi"], "atr": x["atr"]}
            for x in sorted(scored, key=lambda x: x[key], reverse=True)
            if x[key] >= min_score
        ][:20]

    leaderboards = {
        "long_minervini": top20("sMinervini", 40),
        "long_swing":     top20("sSwing",     35),
        "long_mr":        top20("sMrLong",    30),
        "short_breakdown":top20("sBreakdown", 35),
        "short_fading":   top20("sFading",    35),
    }

    # ── REGIME-ADAPTIVER MASTER-SHORTLIST ALGORITHMUS v2 (Gemini-Review Fix C+F) ──
    regime_upper = market_regime.upper() if market_regime else "NEUTRAL"
    is_bear = any(x in regime_upper for x in ["STRESS", "BEAR", "PANIC"])
    is_bull = any(x in regime_upper for x in ["BULL", "POST_PANIC"])

    shortlist_dict = {}   # Fix F: Dict verhindert Duplikate, Dict-Key = Ticker-Symbol

    if is_bear:
        # Bärenmarkt: MR Long zuerst (Kapitulation = Priorität 1), dann Breakdown-Shorts
        for x in scored:
            if x["sMrLong"] >= 45:
                shortlist_dict[x["sym"]] = {**x,
                    "masterScore": min(100, x["sMrLong"] * 1.2),
                    "masterStrategy": "long_mr"}
        for x in scored:
            if x["bestShort"] >= 55 and x["sym"] not in shortlist_dict:
                shortlist_dict[x["sym"]] = {**x,
                    "masterScore": min(100, x["bestShort"]),
                    "masterStrategy": "short_" + (x["shortDir"] or "breakdown").lower()}

    elif is_bull:
        # Bullenmarkt: Minervini + Swing primär, Fading-Shorts selektiv
        for x in scored:
            if x["sMinervini"] >= 75:
                shortlist_dict[x["sym"]] = {**x,
                    "masterScore": x["sMinervini"],
                    "masterStrategy": "long_minervini"}
            elif x["sSwing"] >= 70 and x["sym"] not in shortlist_dict:
                shortlist_dict[x["sym"]] = {**x,
                    "masterScore": x["sSwing"],
                    "masterStrategy": "long_swing"}
            elif x["sFading"] >= 70 and x["sym"] not in shortlist_dict:
                shortlist_dict[x["sym"]] = {**x,
                    "masterScore": x["sFading"],
                    "masterStrategy": "short_fading"}

    else:
        # Fix C: NEUTRAL Fallback — Top 5 aus JEDER Strategie, kein leeres Ergebnis mehr
        strat_map = [
            ("sMinervini",  "long_minervini",  50),
            ("sSwing",      "long_swing",      50),
            ("sMrLong",     "long_mr",         45),
            ("sBreakdown",  "short_breakdown", 50),
            ("sFading",     "short_fading",    50),
        ]
        for key, label, min_score in strat_map:
            top5 = sorted(scored, key=lambda x: x.get(key, 0), reverse=True)[:5]
            for x in top5:
                if x.get(key, 0) >= min_score and x["sym"] not in shortlist_dict:
                    shortlist_dict[x["sym"]] = {**x,
                        "masterScore": x[key],
                        "masterStrategy": label}

    # Fix F: Sortierung nach masterScore — knallhart, keine Alphabetik-Artefakte
    master_shortlist_raw = sorted(shortlist_dict.values(),
                                   key=lambda x: x["masterScore"], reverse=True)

    master_shortlist_raw = master_shortlist_raw[:20]

    # Kompaktes Format fuer JSON (erweitertes Payload fuer Alpha Desk Scanner-Paritaet)
    master_shortlist = [
        {
            "sym":           c["sym"],
            "price":         c["price"],
            "strategy":      c["masterStrategy"],
            "score":         round(c["masterScore"]),
            "grade":         c["grade"],
            "rsi":           c["rsi"],
            "atr":           c["atr"],
            "shortDir":      c.get("shortDir"),
            "overheat":      c.get("overheat"),
            "ema50":         c.get("ema50"),
            "ema200":        c.get("ema200"),
            "macdHist":      c.get("macdHist"),
            "obvTrend":      c.get("obvTrend"),
            "bbPos":         c.get("bbPos"),
            "volRatio":      c.get("volRatio"),
            "hvp":           c.get("hvp"),
            "hv10":          c.get("hv10"),
            "pctFromHigh52": c.get("pctFromHigh52"),
            "dist200":       c.get("dist200"),
            "dist50":        c.get("dist50"),
            "high52":        c.get("high52"),
            "low52":         c.get("low52"),
            "bullSignals":   c.get("bullSignals"),
            "sMinervini":    c.get("sMinervini"),
            "sSwing":        c.get("sSwing"),
            "sMrLong":       c.get("sMrLong"),
            "sBreakdown":    c.get("sBreakdown"),
            "sFading":       c.get("sFading"),
        }
        for c in master_shortlist_raw
    ]
Block 2 — hv30() (ersetze die alte def hv30(cls): Funktion):
python
        for c in master_shortlist_raw
    ]

    log.info(f"  Leaderboards: Minervini={len(leaderboards['long_minervini'])} | "
             f"Swing={len(leaderboards['long_swing'])} | MR={len(leaderboards['long_mr'])} | "
             f"Breakdown={len(leaderboards['short_breakdown'])} | Fading={len(leaderboards['short_fading'])}")

    # Strategie-Scores in die originalen results schreiben (fuer Ticker-Export)
    scored_map = {x["sym"]: x for x in scored}
    for r in results:
        s = scored_map.get(r.get("sym"), {})
        if s:
            r["sMinervini"] = s.get("sMinervini", 0)
            r["sSwing"]     = s.get("sSwing", 0)
            r["sMrLong"]    = s.get("sMrLong", 0)
            r["sBreakdown"] = s.get("sBreakdown", 0)
            r["sFading"]    = s.get("sFading", 0)
            r["bestLong"]   = s.get("bestLong", 0)
            r["bestShort"]  = s.get("bestShort", 0)
            r["shortDir"]   = s.get("shortDir")
    log.info(f"  Master Shortlist: {len(master_shortlist)} Kandidaten | Regime: {regime_upper}")

    return {
        "leaderboards":   leaderboards,
        "masterShortlist": master_shortlist,
        "regimeUsed":     regime_upper,
        "timestamp":      datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


async def enrich_shortlist_with_ai(shortlist: list, market_data: dict,
                                    api_key: str | None = None) -> list:
    """
    KI-Enrichment: Claude Sonnet analysiert Top-15 Shortlist-Kandidaten
    und generiert strukturierte Trading-Parameter als JSON.
    """
    if not api_key or not shortlist:
        log.warning("  KI-Enrichment: kein API-Key oder leere Shortlist — uebersprungen")
        return shortlist

    import json as json_mod, urllib.request, urllib.error

    enriched = []
    top15 = shortlist[:15]

    # Fix Gemini Review 1: dual-regime — VIX-Struktur vs. Leaderboard-Regime
    vix_term     = market_data.get("vixTerm") or {}
    vix_signal   = market_data.get("vixRegime", vix_term.get("signal", "?"))
    vix_val      = market_data.get("vixActual", vix_term.get("vix", "?"))
    vix3m_val    = market_data.get("vix3mActual", vix_term.get("vix3m", "?"))
    ratio_val    = market_data.get("ratioActual", vix_term.get("ratio", "?"))
    lb_regime    = market_data.get("regimeUsed", "NEUTRAL")   # Leaderboard-Regime (Strategie-Filter)
    # Für KI-Prompt: echtes VIX-Termstruktur-Regime verwenden
    regime = f"{lb_regime} | VIX-Struktur: {vix_signal} (VIX:{vix_val} / VIX3M:{vix3m_val} = {ratio_val})" 

    for c in top15:
        sym      = c["sym"]
        strategy = c["strategy"]
        price    = c["price"]
        atr      = c["atr"] or 0
        rsi      = c["rsi"]
        overheat = c["overheat"]
        is_short = strategy.startswith("short")

        strat_labels = {
            "long_minervini":  "Minervini SEPA (Stage 2 Ausbruch)",
            "long_swing":      "Swing-Pullback (EMA-Bounce)",
            "long_mr":         "Mean Reversion Long (Kapitulations-Bounce)",
            "short_breakdown": "Short Breakdown (Trendfolge abwaerts)",
            "short_fading":    "Short Fading (FOMO-Top Mean Reversion)",
        }
        strat_label = strat_labels.get(strategy, strategy)

        prompt = f"""Du bist die quantitative Analyse-Engine von UnderlyingIQ.
Erstelle fuer diesen Kandidaten ein praezises Setup-JSON.
Antworte NUR mit dem JSON-Objekt — kein Markdown, kein Praeambel.

MARKTKONTEXT:
- Regime: {regime}
- VIX: {vix_val}
- Fiktives Modell-Depot: 100.000 EUR (BaFin-konforme Deskription gemaess §1 WpHG)

KANDIDAT:
- Ticker: {sym}
- Kurs: {price} USD
- Strategie: {strat_label}
- Score: {c['score']}/100
- ATR(14): {round(atr, 2) if atr else 'n/v'}
- RSI(14): {round(rsi, 1) if rsi else 'n/v'}
- Ueberhitzung: {overheat}/100
- Richtung: {"SHORT" if is_short else "LONG"}

Berechne mathematisch praezise (alle Werte auf 2 Dezimalstellen):
{{
  "sym": "{sym}",
  "strategy": "{strategy}",
  "direction": "<SHORT oder LONG>",
  "trigger": <Einstiegsniveau: {"Short-Trigger unter" if is_short else "Buy Stop ueber"} dem {"Swing-Hoch" if is_short else "Tageshoch"} in USD>,
  "stopLoss": <Stop-Loss in USD: {"Swing-Hoch + 0.5×ATR" if is_short else "letztes Swing-Tief - 0.3×ATR"}>,
  "target": <Take-Profit in USD: CRV min. 2:1 zum Stop-Abstand>,
  "crv": <Chance-Risiko-Verhaeltnis als Float>,
  "holdingDays": <Haltedauer in Tagen: Short-Swing 3-7, Position-Trade 10-30>,
  "positionPct": <Depotanteil in %: max 2% bei Long, max 1% bei Short>,
  "leverageRec": <"Konservativ: Aktie/ETF" oder "Moderat: KO-Zertifikat Hebel 2-3" oder "Aggressiv: KO Hebel 4-6">,
  "riskClass": <"LOW"|"MEDIUM"|"HIGH">,
  "keyRisk": <1 Satz: Hauptrisiko dieses Setups>,
  "note": <1 Satz: Wichtigste deskriptive Beobachtung, §1 WpHG-konform>
}}"""

        try:
            req_body = json_mod.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}]
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=req_body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json_mod.loads(resp.read().decode())
                text = resp_data.get("content", [{}])[0].get("text", "")
                # JSON aus Antwort extrahieren
                text = text.strip()
                if text.startswith("```"):
                    text = '\n'.join(text.split('\n')[1:-1])
                ki_params = json_mod.loads(text)
                enriched.append({**c, "ki": ki_params})
                log.info(f"    KI {sym}: Trigger={ki_params.get('trigger')} | SL={ki_params.get('stopLoss')} | CRV={ki_params.get('crv')}")
        except Exception as e:
            log.warning(f"    KI {sym} Fehler: {e}")
            enriched.append(c)   # ohne KI-Enrichment

    # Nicht-enriched hinzufuegen
    enriched_syms = {x["sym"] for x in enriched}
    for c in shortlist[15:]:
        if c["sym"] not in enriched_syms:
            enriched.append(c)

    return enriched

# ── EINZELTITEL VERARBEITUNG ──────────────────────────────────────────────────

def process_ticker(ticker, hist_df):
    """Berechnet alle Indikatoren für einen Ticker."""
    try:
        if hist_df is None or len(hist_df) < 30:
            return {"sym": ticker, "error": "insufficient_data", "bars": len(hist_df) if hist_df is not None else 0}

        # Spalten robust extrahieren (auch bei MultiIndex)
        def get_col(df, col):
            # Fix: MultiIndex-Columns (yfinance gibt manchmal ('Close','AAPL') zurück)
            if col in df.columns:
                vals = list(df[col].dropna())
                return vals
            # MultiIndex: suche Spalte die mit col beginnt
            for c in df.columns:
                cname = c[0] if isinstance(c, tuple) else str(c)
                if cname == col:
                    return list(df[c].dropna())
            # Fallback: jede Spalte die den Namen enthält
            for c in df.columns:
                if col in str(c):
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
            "obvTrend":      round(obv_tr, 3) if obv_tr is not None else None,
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
            "hvp":           calc_hv_percentile(closes),          # 30-Tage HV-Percentile 0-100
            "hv10":          calc_hv_percentile(closes, window=10, lookback=90),  # 10-Tage HV für Weeklies
            "updated":       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            # Strategie-Scores werden im build_leaderboards-Pass hinzugefuegt
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
        # yfinance kann MultiIndex zurueckgeben — flatten
        vix_close  = vix["Close"]
        vix3m_close = vix3m["Close"]
        if hasattr(vix_close, "squeeze"):  vix_close  = vix_close.squeeze()
        if hasattr(vix3m_close,"squeeze"): vix3m_close = vix3m_close.squeeze()
        vix_val   = float(vix_close.dropna().iloc[-1])
        vix3m_val = float(vix3m_close.dropna().iloc[-1])
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


def fetch_mse_history(days: int = 30) -> dict:
    """Laedt 30-Tage-History fuer VVIX, SKEW, VIX, VIX3M fuer MSE Z-Score Normalisierung."""
    period = f"{days + 5}d"
    result = {"vvix": [], "skew": [], "vix": [], "vixRatio": [], "dates": []}
    try:
        raw = yf.download(
            ["^VVIX", "^SKEW", "^VIX", "^VIX3M"],
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
        closes = {}
        for sym in ["^VVIX", "^SKEW", "^VIX", "^VIX3M"]:
            try:
                closes[sym] = raw[sym]["Close"].dropna()
            except Exception:
                closes[sym] = None

        if closes["^VIX"] is None or closes["^VIX3M"] is None:
            log.warning("  MSE History: VIX/VIX3M nicht verfuegbar")
            return result

        common_idx = closes["^VIX"].index
        for sym in ["^VIX3M", "^VVIX", "^SKEW"]:
            if closes[sym] is not None:
                common_idx = common_idx.intersection(closes[sym].index)

        common_idx = common_idx[-days:]

        dates  = [str(d.date()) for d in common_idx]
        vvix   = [round(float(closes["^VVIX"].loc[d]), 2) if closes["^VVIX"] is not None else None for d in common_idx]
        skew   = [round(float(closes["^SKEW"].loc[d]), 2) if closes["^SKEW"] is not None else None for d in common_idx]
        vix    = [round(float(closes["^VIX"].loc[d].squeeze() if hasattr(closes["^VIX"].loc[d],"squeeze") else closes["^VIX"].loc[d]), 2)  for d in common_idx]
        vix3m  = [round(float(closes["^VIX3M"].loc[d].squeeze() if hasattr(closes["^VIX3M"].loc[d],"squeeze") else closes["^VIX3M"].loc[d]), 2) for d in common_idx]
        ratio  = [round(vix3m[i] / vix[i], 3) if vix[i] and vix[i] > 0 else None for i in range(len(vix))]

        result = {"vvix": vvix, "skew": skew, "vix": vix, "vixRatio": ratio, "dates": dates}
        log.info(f"  MSE History: {len(dates)} Tage | VVIX: {vvix[-1]} | SKEW: {skew[-1] if skew[-1] else chr(8212)} | Ratio: {ratio[-1]}")
    except Exception as e:
        log.warning(f"  MSE History nicht verfuegbar: {e}")
    return result


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
    log.info("UnderlyingIQ Market Aggregator v3.0")
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
    hist_data = fetch_batch(stock_tickers, period="2y", max_workers=25)

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
    dix_gex  = fetch_dix_gex() or {}   # Fallback auf leeres Dict wenn API nicht verfügbar
    pcr      = fetch_pcr_cboe() or {}   # Fallback auf leeres Dict
    vix_term    = fetch_vix_term()
    log.info(f"  Lade MSE History (VVIX/SKEW/VIX 30T)...")
    mse_history = fetch_mse_history(days=30)

    # 5. Top-Signale ermitteln
    valid = [r for r in results if r.get("score") is not None]
    top40_long = sorted(
        [r for r in valid if r.get("score", 0) >= 50 and r.get("bullSignals", 0) >= 2],
        key=lambda x: x["score"], reverse=True
    )[:40]

    mean_reversion = sorted(
        [r for r in valid
         # Fix Gemini Review 3: overheat>=60 war falsch — MR braucht TIEFES overheat
         # Echte Kapitulation: RSI<35, weit unter EMA200, BB unten
         if r.get("rsi") is not None and r["rsi"] < 35
         and r.get("dist200") is not None and r["dist200"] < -8   # min 8% unter EMA200
         and r.get("bbPos") is not None and r["bbPos"] < 0.20
         and r.get("score", 0) >= 15],   # mind. leichtes Signal
        key=lambda x: x.get("rsi", 99)   # nach RSI sortieren (niedrigster zuerst)
    )[:20]

    # 5a. Options-Watchlist (Top-50, Gemini-Architektur) ────────────────────────
    log.info(f"\n🎯 Options-Watchlist berechnen (3 Strategien)...")

    # Preisfilter entfernt (war $10-$800 → schloss BRK.A, NVO etc. aus)
    # Optionsliquidität wird durch Ticker-Universum (US_ADR) sichergestellt

    options_candidates = []
    for r in valid:
        sym   = r.get("sym", "")
        price = r.get("price") or 0

        # Gemini Fix 1: Nur US-Ticker (kein .DE, .L, .PA etc. oder Krypto mit -)
        if "." in sym or "-" in sym:
            continue

        # Preis-Filter
        # Kein Preisfilter — wird durch US-ADR Universum sichergestellt
        # Sanity: Preise über $50k = Datenfehler (BRK.A-Klasse)
        if (r.get("price") or 0) > 50000: continue

        # HVP muss vorhanden sein
        if r.get("hvp") is None:
            continue

        # Berechne alle 3 Strategy-Scores (Gemini-Modelle)
        s_csp    = score_options_csp(r)
        s_cc     = score_options_covered_call(r)
        s_spread = score_options_credit_spread(r)

        # Mindestens eine Strategie muss > 0 sein
        if max(s_csp, s_cc, s_spread) == 0:
            continue

        options_candidates.append({
            "sym":         sym,
            "price":       price,
            "hvp":         r.get("hvp"),
            "hv10":        r.get("hv10"),
            "rsi":         r.get("rsi"),
            "atr":         r.get("atr"),
            "dist200":     round(r.get("dist200") or 0, 1),
            "score":       r.get("score"),
            "grade":       r.get("grade"),
            "regime":      r.get("regime"),
            "scoreCsp":    s_csp,
            "scoreCc":     s_cc,
            "scoreSpread": s_spread,
            # Bester Score fuer Sortierung
            "optsScore":   max(s_csp, s_cc, s_spread),
        })

    # Sortierung: bester Strategie-Score zuerst, Top-50
    # Macro Risk Overlay anwenden (GEX/PCR-Skalierung) — Gemini-Blueprint
    options_candidates = apply_macro_risk_overlay(options_candidates, dix_gex, pcr)

    options_watchlist = sorted(
        options_candidates,
        key=lambda x: x["optsScore"],
        reverse=True
    )[:50]

    log.info(f"   ✅ Options-WL: {len(options_watchlist)} US-Kandidaten "
             f"(aus {len(valid)} validen Tickern)")
    if options_watchlist:
        top3 = [f"{r['sym']}(CSP:{r['scoreCsp']}/CC:{r['scoreCc']}/Spr:{r['scoreSpread']})"
                for r in options_watchlist[:3]]
        log.info(f"   Top-3: {', '.join(top3)}")

    # 5b. Sektor Relative Stärke vs. SPY berechnen
    log.info(f"\n📐 Berechne Sektor Relative Stärke...")
    sector_rs = {}
    rs_sorted = []   # Fix A: initialisieren — wird nur befüllt wenn SPY-Daten vorhanden
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

    # Markt-Regime aus VIX-Term-Structure ableiten (fuer Leaderboard-Filter)
    market_regime_str = 'NEUTRAL'
    # Primärquelle: VIX Term Structure (VIX/VIX3M Ratio)
    _regime_ratio = None
    if vix_term and vix_term.get('ratio'):
        _regime_ratio = vix_term['ratio']
    elif mse_history and mse_history.get('vixRatio') and mse_history['vixRatio']:
        _regime_ratio = mse_history['vixRatio'][-1]

    if _regime_ratio:
        if _regime_ratio < 0.98:
            market_regime_str = 'STRESS_UNSTABLE'
        elif _regime_ratio < 1.05:
            market_regime_str = 'POST_PANIC_REVERSION'
        else:
            # Contango = BULL — unterscheide QUIET vs FRAGILE per VIX-Niveau
            _vix_val = vix_term.get('vix') if vix_term else None
            if _vix_val and _vix_val > 25:
                market_regime_str = 'BULL_FRAGILE'
            else:
                market_regime_str = 'BULL_QUIET'
    log.info(f'  Markt-Regime (Leaderboards): {market_regime_str} | Ratio: {_regime_ratio}')

    # Fix A: rs_sorted wird nur innerhalb von `if spy_data is not None` befüllt
    # → außerhalb des Blocks nur loggen wenn vorhanden (verhindert NameError/UnboundLocalError)
    if rs_sorted:
        log.info(f"  Schwächste (RS5):     {[r['sym'] for r in rs_sorted[-3:]]}")
    else:
        log.info("  Schwächste (RS5):     — (SPY-Daten fehlen, Sektor-RS übersprungen)")

    # 5c. Swing-Trading Kandidaten
    swing_candidates = sorted(
        [r for r in valid
         if r.get("score", 0) >= 45
         and r.get("bullSignals", 0) >= 1
         and r.get("rsi") is not None and r["rsi"] < 60
         and r.get("macdHist") is not None],
        key=lambda x: x.get("score", 0), reverse=True
    )[:20]

    # 5d. Datenfreshe validieren
    log.info(f"\n🗓️  Validiere Datenfreshe...")
    last_trading_day = validate_data_freshness(results)
    log.info(f"  Referenz-Handelstag: {last_trading_day}")

    # 6. Master-JSON zusammenbauen
    elapsed = round(time.time() - start_time, 1)
    master  = {
        "schema": {
            "version":       "3.0",
            "description":   "UnderlyingIQ Master Market Data — Multi-Strategy Leaderboard Engine",
            "generated_by":  "ko-aggregator / market_aggregator.py",
            "documentation": {
                "meta":       "Run-Metadaten: Zeitstempel, Ticker-Anzahl, Fehler, Laufzeit",
                "market":     "Makro-Indikatoren: dixGex (Dark Pool), pcr (Put/Call), vixTerm (VIX-Termstruktur), mseHistory (30T VVIX/SKEW/VIX)",
                "leaderboards": {
                    "long_minervini":   "Minervini SEPA Score 0-100: Stage2-Uptrend, 52W-Hoch-Naehe, Volumen-Akkumulation",
                    "long_swing":       "Swing-Pullback Score 0-100: EMA50-Bounce, RSI 30-50, Bollinger-Kompression",
                    "long_mr":          "Mean Reversion Long Score 0-100: Extreme Kapitulation >2 ATR unter EMA200, RSI<30",
                    "short_breakdown":  "Short Breakdown Score 0-100: Downtrend unter EMA200, OBV faellt, Markov baerig, RSI 28-60",
                    "short_fading":     "Short Fading Score 0-100: FOMO-Top >2.5 ATR ueber EMA200, RSI>68, Kauf-Erschoepfung",
                },
                "masterShortlist": "Top 15-20 regime-adaptive Kandidaten. KI-Felder (trigger/stopLoss/target/crv/holdingDays/positionPct/leverageRec) nur bei ANTHROPIC_API_KEY vorhanden",
                "strategyMeta":    "Regime-Klassifikation und KI-Enrichment Status",
                "tickers":         "Alle 716 Ticker mit vollstaendigen Indikatoren",
                "ticker_fields": {
                    "sym":          "Yahoo Finance Symbol",
                    "price":        "Letzter Schlusskurs (USD/EUR)",
                    "ema50":        "EMA 50 Tage",
                    "ema200":       "EMA 200 Tage",
                    "atr":          "Average True Range 14T",
                    "rsi":          "RSI 14T",
                    "macdHist":     "MACD Histogramm (12/26/9)",
                    "obvTrend":     "OBV-Trend 5T (positiv=bullisch)",
                    "bbPos":        "Bollinger Band Position 0-1 (0=unten, 1=oben)",
                    "overheat":     "Ueberhitzungs-Score 0-100",
                    "regime":       "Markov Regime: bull/side/bear",
                    "pBull2Bear":   "Markov Transition-Wahrscheinlichkeit Bull->Bear (0-1)",
                    "score":        "Composite Long-Score 0-100 (Basis-Metrik)",
                    "grade":        "A+/A/B/C/D/F",
                    "high52":       "52-Wochen Hoch",
                    "low52":        "52-Wochen Tief",
                    "pctFromHigh52":"Abstand vom 52W-Hoch in %",
                    "dist50":       "Abstand EMA50 in %",
                    "dist200":      "Abstand EMA200 in %",
                    "volRatio":     "Volumen-Verhaeltnis vs. 20T-Durchschnitt",
                    "sMinervini":   "Strategie-Score Minervini 0-100",
                    "sSwing":       "Strategie-Score Swing 0-100",
                    "sMrLong":      "Strategie-Score Mean Reversion Long 0-100",
                    "sBreakdown":   "Strategie-Score Short Breakdown 0-100",
                    "sFading":      "Strategie-Score Short Fading 0-100",
                    "shortDir":     "Short-Richtung: BREAKDOWN oder FADING",
                },
                "regime_values": {
                    "BULL_QUIET":           "Contango + VIX<25: Trendfolge freigegeben",
                    "BULL_FRAGILE":         "Contango + VIX>25: Trendfolge mit engeren Stops",
                    "POST_PANIC_REVERSION": "Uebergang von Backwardation zu Contango: MR + CSP optimal",
                    "STRESS_UNSTABLE":      "Backwardation (VIX>VIX3M): Short + MR Long prioritaet",
                    "NEUTRAL":              "Kein klares Signal",
                },
            },
        },
        "meta": {
            "version":      "3.0",
            "generated":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "elapsed_s":    elapsed,
            "total":        len(results),
            "errors":       len(errors),
            "tickers_ok":   len(results),
            "last_trading_day": str(get_last_trading_day()),
        },
        "market": {
            "dixGex":     dix_gex,
            "pcr":        pcr,
            "vixTerm":    vix_term,
            "mseHistory": mse_history,   # 30T VVIX/SKEW/VIX fuer Z-Score
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
            "intl_eu":  [r for r in results if r["sym"] in EUROSTOXX_TICKERS],
            "ftse100":  [r for r in results if r["sym"] in FTSE100_TICKERS],
            "stoxx_eu": [r for r in results if r["sym"] in STOXX_EU_EXTRA],
            "bear_us":  [r for r in results if r["sym"] in BEAR_US_TICKERS],
            "bear_eu":  [r for r in results if r["sym"] in BEAR_DE_EU_TICKERS],
            "etfs_exus":[r for r in results if r["sym"] in SECTOR_ETFS_EXUS],
            "etfs":     [r for r in results if r["sym"] in SECTOR_ETFS],
            "crypto":   [r for r in results if r["sym"] in CRYPTO_TICKERS],
        },
        "sectorRS":       sector_rs,   # Sektor Relative Stärke vs. SPY
        "swingCandidates": [{"sym": r["sym"], "score": r["score"], "price": r["price"],
                             "rsi": r["rsi"], "macdHist": r.get("macdHist"), "regime": r["regime"]}
                            for r in swing_candidates],
        "tickers":        results,  # Alle Ergebnisse
    }

    # ── STRATEGIE LEADERBOARDS & MASTER SHORTLIST ───────────────────────────
    import os as _os
    _ant_key = _os.environ.get("ANTHROPIC_API_KEY") or _os.environ.get("ANT_KEY")
    strategy_data = build_leaderboards(results, market_regime=market_regime_str)
    leaderboards_obj  = strategy_data["leaderboards"]
    master_shortlist  = strategy_data["masterShortlist"]
    log.info(f"\n🤖 KI-Enrichment Master Shortlist ({len(master_shortlist)} Kandidaten)...")
    if _ant_key:
        import asyncio
        # Fix Gemini Review 1: echtes vixTerm + dual-regime an KI übergeben
        # Fix B: vix_term kann None sein wenn fetch_vix_term() fehlschlägt
        _vt = vix_term or {}
        enrich_context = {
            **strategy_data,
            "vixTerm":      vix_term,                   # echte VIX-Termstruktur
            "vixRegime":    _vt.get("signal", "?"),     # CONTANGO/BACKWARDATION/NORMAL
            "vixActual":    _vt.get("vix", "?"),
            "vix3mActual":  _vt.get("vix3m", "?"),
            "ratioActual":  _vt.get("ratio", "?"),
        }
        master_shortlist = asyncio.run(
            enrich_shortlist_with_ai(master_shortlist, enrich_context, api_key=_ant_key)
        )
    else:
        log.warning("  ANTHROPIC_API_KEY fehlt — KI-Enrichment uebersprungen")

    # Leaderboards + Shortlist in master dict einfuegen
    master["leaderboards"]     = leaderboards_obj
    master["masterShortlist"]  = master_shortlist
    master["optionsWatchlist"] = options_watchlist   # Top-50 Options-Kandidaten (täglich)
    master["strategyMeta"]     = {
        "regimeUsed":  strategy_data["regimeUsed"],
        "timestamp":   strategy_data["timestamp"],
        "enriched":    bool(_ant_key),
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

    # Separater KV-Key für schnellen Options-Desk Zugriff
    options_kv = {
        "generated":        master["meta"]["generated"],
        "last_trading_day": master["meta"].get("last_trading_day"),
        "tickers":          options_watchlist,
        "count":            len(options_watchlist),
        "criteria": {
            "note":       "Kein Preisfilter — US-ADR Universum sichert Liquidität",
            "min_hvp":    20,   # CSP Gate (Unleashed v2)
            "min_score":  30,
            "macro":      "GEX/PCR Overlay aktiv",
        }
    }
    push_to_cloudflare_kv(options_kv, key="options_watchlist")
    log.info(f"   ✅ options_watchlist KV-Key aktualisiert ({len(options_watchlist)} Ticker)")

    log.info(f"\n{'='*60}")
    log.info(f"✅ Fertig in {elapsed}s")
    log.info(f"{'='*60}")

if __name__ == "__main__":
    main()
    
