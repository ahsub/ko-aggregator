#!/usr/bin/env python3
"""
UnderlyingIQ Market Aggregator v4.7
=====================================
Single-Source-of-Truth Aggregator für Alpha Desk + Scanner Tab.
Läuft als GitHub Actions Cron-Job (täglich 04:00 UTC nach US-Schluss).
Version 3.0: EU-ADR-Universum (US-gelistete ADRs statt Heimatbörsen .DE/.PA/.L),
Multi-Strategy Scoring Engine (Gemini v3), Macro Risk Overlay (GEX/PCR),
KV-basierte Scanner-Architektur (Single Source of Truth).
Version 3.1 (30.06.2026): Fibonacci-Screening-Modul (Gemini-Blueprint) —
calc_fibonacci_levels() pro Ticker: Retracement/Extension-Level aus 52W-Range,
Confluence-Score (0-100), Setup-Klassifikation (CSP_ZONE/BREAKOUT/EXTENSION).
Version 3.2 (30.06.2026): Extra-Ticker-Erweiterung — fetch_approved_extra_tickers()
liest admin-freigegebene Ticker-Vorschläge (Fibo-Tab → Pending-Review → KV) und
mergt sie zusätzlich zu den fest codierten Listen in die Ticker-Universe.
Version 3.3 (30.06.2026): pusht zusätzlich known_universe_tickers nach KV (volle
Ticker-Liste nach jedem Lauf), damit der ko-ai Worker Extra-Ticker-Vorschläge
gegen bereits vorhandene Ticker abgleichen kann (Dedupe vor Admin-Review).
Bugfix: meta["version"] im Output war seit der Fibo-Erweiterung (v3.1) hartcodiert
"3.0" und lief vom Docstring-Header auseinander — jetzt zentrale AGGREGATOR_VERSION-
Konstante als einzige Quelle der Wahrheit für beide Stellen.
Version 3.4 (30.06.2026): Fibo-Score → Options-Scoring-Boost (offener Punkt aus
Übergabeprotokoll) — score_options_csp() erhält bis zu +15 Pkt bei CSP_ZONE-Setup,
score_options_covered_call() bis zu +15 Pkt bei EXTENSION-Setup, jeweils skaliert
mit dem Fibo-Confluence-Score. Hand-verifiziert gegen Live-Daten (SCHW, 30.06.2026).
Version 3.5 (30.06.2026): f_setup/f_score (als fSetup/fScore) zusätzlich in
optionsWatchlist-Output aufgenommen — vorher nur intern für die Score-Berechnung
genutzt, im Output unsichtbar, daher Boost-Wirkung nicht nachvollziehbar/prüfbar.
Version 3.6 (30.06.2026): IOS v1.2 Leader-Boost in Minervini-Scoring integriert
(Batch-2-Punkt aus Übergabeprotokoll) — score_long_minervini() erhält +10 Pkt
wenn iosIsLeader=true UND Stage-2-Gate bereits bestanden (s_minervini>0). Vorher
liefen IOS-Score und Minervini-Score komplett unabhängig nebeneinander her.
Version 3.7 (01.07.2026): Short-Strategien Phase 1 (Gemini-Blueprint):
calc_squeeze_risk() — Proxy-Score (0-100) für Short-Squeeze-Risiko aus HVP/RSI/
BB-Position/Volumen (kein SI-API nötig), hartes Gate für score_short_fading().
calc_ko_short_leverage() — dynamische Hebelempfehlung (3-8x) aus ATR/Preis.
score_short_fading() erweitert: Squeeze-Risk-Gate, Penny-Stock-Gate (<$15),
ATH-Gate (kein Short nahe 52W-Hoch), Sektor-RS-Boost (_sector_rs5 Feld).
squeezeRisk + koShortLev im Scored-Output sichtbar für Frontend-Darstellung.
Version 3.8 (01.07.2026): Bugfix — squeezeRisk/koShortLev und alle Strategie-
Scores wurden zwar im Leaderboard-Pass (scored[]) berechnet, aber nie in den
tickers-Output (results[]) zurückgeschrieben → tickers["squeezeRisk"] war immer
None. Fix: scored_by_sym-Merge schreibt alle Short-Felder nach dem Leaderboard-
Pass zurück in results[], sodass sie im tickers-JSON-Output sichtbar werden.
Version 3.9 (01.07.2026): 3 Erweiterungen:
1. _calc_squeeze_risk_df(): Gemini-Blueprint v2 — direktionaler Volumen-Check
   (Spike an grünem Tag) in process_ticker() mit hist_df-Zugriff statt altem
   nicht-direktionalem Proxy. Berechnung jetzt vor dem Leaderboard-Pass.
2. Fundamental-Enrichment auf 3 Kernfelder reduziert (80/20-Review):
   analystUpside, fcfYield, debtToEquity (Versorger/REITs ausgenommen).
3. macdLine + macdSignal (waren berechnet aber nicht im result-Dict).
Version 4.0 (01.07.2026): Sektor-Tag-Architektur (Zwischenstufe):
TICKER_SECTOR_TAG automatisch aus SECTOR_WATCHLISTS invertiert — jeder Ticker
bekommt ein sectors-Feld [...] im Output. Governance: neue Ticker NUR in
SECTOR_WATCHLISTS eintragen, TICKER_SECTOR_TAG wird automatisch abgeleitet.
Defence erweitert (RHTRY/BAESY/SAABY/THLLY + US-Titel). ROBOTICS als eigene
Watchlist. RS_SECTOR_ETFS: XAR, PPA, DFEN, IRBO, ROBO neu aufgenommen.
Mittelfristig: Migration zu TICKER_SECTOR_MAP als echter Single Source of Truth.
Version 4.2 (02.07.2026): Ticker-Erweiterung (Gemini-Liste, Governance-konform):
DEFENSE +4 (AVAV/LHX/BWXT/PLTR), ROBOTICS +11 (SYM/ROK/MBLY/TDY/CGNX/PATH/
ZBRA/IR/ADI/NXPI/MCHP), 5 neue Watchlists: MATERIALS, CYBERSECURITY,
NUCLEAR_ENERGY, SPACE, BIOTECH_LONGEVITY. Governance-Entscheidungen: CEG nur
in NUCLEAR_ENERGY (Kernkraft-Versorger, kein Rohstoffwert); IBM/HON nicht in
CYBERSECURITY (Mischkonzerne verwässern Sektor-Filter); COGN aus Gemini-Liste
→ CGNX korrigiert (Cognex). RS_SECTOR_ETFS + SECTOR_ETFS_US erweitert:
HACK/CIBR (Cyber), NLR/URA (Nuclear), ARKX (Space), ARKG (Biotech).
Ticker-Korrekturen Bestand: HEICO→HEI, BRKS→AZTA (Umbenennung 2022),
CCO→CCJ (CCO = Clear Channel Outdoor, nicht Cameco — falsche Firma!).
Bugfix (latent, kritisch): calc_fg_proxy()-Fallback referenzierte sector_rs
VOR dessen Definition (Schritt 5b) → NameError-Crash bei CNN-API-Ausfall.
Fallback-Block hinter die Sektor-RS-Berechnung verschoben.
Kosmetik: Startup-Log nutzt AGGREGATOR_VERSION statt hartcodiert "v3.0";
Fundamental-Log printet die 3 realen Felder statt der in v3.9 entfernten.
Version 4.3 (02.07.2026): KRITISCHER FIX — Regime-Routing war invertiert:
vix_term['ratio'] (VIX/VIX3M, <1=gesund) wurde gegen Schwellen der inversen
Konvention VIX3M/VIX geprüft → ruhiger Contango-Markt als STRESS_UNSTABLE
geroutet (Lauf v4.2: 13× MR-Long + 7 Shorts bei VIX 16/CONTANGO). Fix:
_regime_ratio jetzt einheitlich VIX3M/VIX aus Rohwerten. Ticker-Fixes:
SQ→XYZ (Block-Umbenennung 01/2025), NOVA entfernt (Sunnova delistet nach
Insolvenz), MOOG→MOG-A (Yahoo-Symbolik). Zusätzlich 10 strukturell tote
Ticker aus dem Fehler-Log des v4.2-Laufs bereinigt: SGEN (Pfizer 2023),
ANSS (Synopsys 2025), INFN (Nokia 2025), TTM/VEDL (ADRs delistet),
EWF (ungültig, Frankreich=EWQ), FMXB→FMX, PROSSY→PROSY, ZI→GTM
(ZoomInfo-Umbenennung 2025), ORG→ORG.AX. Verbleibende Fehlticker (MMC,
ABB, EXAS, NTT, 1COV.DE, CYBR u.a.) bewusst NICHT angefasst — Regel:
erst nach 2. Fehllauf in Folge als strukturell behandeln (transiente
yfinance-Aussetzer vs. echte Delistings). Entdeckt durch Output-Review
des ersten v4.2-Laufs. Shiller CAPE komplett entfernt (80/20: alle drei
Quellen defekt, kein Einfluss auf 2-30-Tage-Setups) — Frontend behandelt
fehlendes market.shillerCape bereits sauber als n/v.
Version 4.4 (03.07.2026): Track-Record-Layer Phase A (tr_layer.py, Spez:
docs/TRACK_RECORD_SPEC.md v1.1) — nächtlicher Snapshot aller Empfehlungen
(masterShortlist + Top-10 je Leaderboard, tages-dedupliziert, fresh-Flag
gegen Vortag) nach tr:snap:<Handelstag> + tr:index. Fehlerisoliert: Layer-
Fehler brechen den Hauptlauf nie; Schreibstatus in master["trackRecord"].
Cron-Härtung im Workflow: 03:37 UTC statt 04:00 (GitHub-Queue-Verzögerungen
zur vollen Stunde, am 02.07. waren es 3h23min).
Version 4.5 (03.07.2026): Track-Record-Layer Phase B — Evaluator + Aggregation
(tr_layer.py v1.1, Spez v1.2): bewertet fällige Snapshot-Tage nach 7/30/90
Handelstagen (Bar-Zählung, +3-Bar-Puffer für EU-Kalender) gegen die im Lauf
ohnehin geladene Historie; richtungsgerechte Rendite, Alpha vs. SPY, MFE/MAE,
KI-Trade-Simulation (Same-Bar konservativ = STOP). Schreibt tr:eval:<Tag> und
aggregiert tr:stats (Zellen Strategie×Regime×Horizont, fresh-getrennt,
noData-Ausweis, h30-Rollups). Zusätzlich tr_backup.py: samstäglicher Export
aller tr:*-Keys nach backups/ (Workflow-Commit — Git-History als Archiv,
RUNBOOK §7.3). Erste Bewertungen fällig ab ~13.07.2026 (Tag 0 + 7 Bars + Puffer).
Version 4.6 (05.07.2026): FIN-Archiv (fin_layer.py, Value-Modul Phase 0):
Point-in-Time-Fundamentaldaten-Archiv — Fundamentaldaten sind nicht
rückwirkend beschaffbar, daher wöchentliche Rohdaten-Sammlung (24 Felder,
modellagnostisch) über Russell 3000 (iShares-IWV-Holdings, Konstituenten
mit-archiviert → survivorship-frei) ∪ Smart-Picks (data/value_smart_picks
.txt) ∪ UIQ-Universum. Wochentags-Sharding Mo–Fr (crc32, ~600/Nacht) → KV
fin:shard:<1-5>; Samstag Merge → data/fundamentals/<YYYY-WW>.json.gz per
Workflow-Commit (Git-History = Archiv). Implementiert nebenbei die VAL-MOD-
Layer-1-Sharding-Infrastruktur. Status in master["finArchive"].

Version 4.7 (05.07.2026): Supercycle-Sektoren (Gemini-Brainstorm, Claude-
Audit: ~15% der Vorschläge waren tote/falsche Ticker — aussortiert): 5 neue
Watchlists GRID_ELECTRIFICATION, PRECIOUS_METALS, AGRICULTURE, WATER sowie
PICKS_SHOVELS (vom Frontend-Index-Slot zum getaggten Sektor befördert);
NUCLEAR_ENERGY +Fuel-Cycle (LEU/UEC/UUUU/NXE), MATERIALS +HBM/ERO/LAC.
Demografie-Titel als Value-Thema ins VAL-MOD-Register (kein Scan-Sektor).

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

# Einzige Quelle der Wahrheit für die Versionsnummer (NEU 30.06.2026 — vorher war
# meta["version"] unten hartcodiert "3.0" und lief seit der Fibo-Erweiterung (v3.1)
# unbemerkt aus dem Gleichschritt mit dem Docstring-Header oben in der Datei).
AGGREGATOR_VERSION = "4.7"

# yfinance für Marktdaten
try:
    import yfinance as yf
except ImportError:
    os.system("pip install yfinance --quiet")
    import yfinance as yf

# Thread-Safety für yfinance
try:
    yf.set_tz_cache_path(None)
except AttributeError:
    pass  # Ältere yfinance-Version ohne diese Methode
except Exception:
    pass

import socket
socket.setdefaulttimeout(30)  # 30s: genug für 2y-Downloads, aber keine ewigen Hänger

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
        spy = yf.download("SPY", period="5d", interval="1d",
                          auto_adjust=True, progress=False, threads=False)  # Fix: 10d→5d, socket timeout greift
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
    "V","MA","INTU","ADBE","CRM","NOW","SNPS","CDNS","ADSK","WDAY","TEAM",  # v4.3: ANSS delistet (Synopsys-Übernahme 2025)
    "PANW","CRWD","FTNT","ZS","OKTA","S","DDOG","MDB","SNOW","NET","CFLT","ESTC",
    "QCOM","TXN","ADI","MCHP","NXPI","KLAC","LRCX","AMAT","MU","WDC","STX",
    "IBM","CSCO","ACN","HPQ","HPE","DELL","NTAP",
    # Semiconductors / AI
    "ARM","SMCI","MRVL","MSTR","PLTR","COIN",
    # E-Commerce / Consumer Tech
    "NFLX","UBER","ABNB","LYFT","RBLX","SNAP","PINS","MTCH","ZM","DOCU",
    "SHOP","MELI","SE","GRAB","XYZ","HOOD","SOFI","AFRM","UPST","PYPL",  # v4.3: SQ→XYZ (Block-Umbenennung 01/2025)
    # China ADRs (US-listed)
    "BABA","JD","PDD","BIDU","NTES","TCOM","FUTU","NIO","XPEV","LI",
    # Auto
    "GM","F","RIVN","LCID","STLA","TM","HMC",
    # Materials
    "LIN","APD","ECL","SHW","FCX","NEM","GOLD","ALB","MP",
    # Biotech / Pharma Growth
    "MRNA","BNTX","BIIB","ILMN","RARE","EXAS","INCY","NBIX","ALLO",  # v4.3: SGEN delistet (Pfizer-Übernahme 2023)
    "VKTX","RYTM","ACAD","MRUS","PRCT",
    # Clean Energy
    "ENPH","FSLR","SEDG","RUN","ARRY","BE","PLUG","BLDP","NEE",  # v4.3: NOVA (Sunnova) delistet nach Insolvenz 2025
    # Fintech
    "HOOD","AFRM","UPST","SOFI",
    # Misc Growth
    "GLW","LDOS","SAIC","CACI","BAH","HUBS","GTM","GTLB","BILL","PCTY",  # v4.3: ZI→GTM (ZoomInfo-Umbenennung 2025)
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
    "ASML","STM","ERIC","NOK","SAP","KEYS",  # v4.3: INFN delistet (Nokia-Übernahme 2025)
    # Europa — Healthcare (ADR)
    "NVO","AZN","NVS","RHHBY","SNY","GSK","BAYRY","NVCR",
    # Europa — Energie & Rohstoffe (ADR)
    "SHEL","BP","TTE","ENLAY","E","ENGIY","SQM","RIO","BHP","VALE","SCCO",
    # Europa — Finanzen (ADR)
    "UBS","ING","BCS","HSBC","DB",
    # Europa — Konsum & Luxus (ADR)
    "LVMUY","CFRUY","PPRUY","HESAY","BURBY","ADDYY",
    # Europa — Industrie (ADR)
    "SIEGY","ATLKY","VOLVY","ABB","DSDVY",
    # Europa — Defence (DIREKT .DE/.PA — OTC-ADRs wie RHTRY haben schlechten API-Feed)
    # NEU (01.07.2026): Rheinmetall, BAE Systems, Saab, Thales, Leonardo über
    # Heimatboersen-Suffix statt OTC-ADR — stabiler yfinance-Feed via Yahoo .DE/.PA/.ST
    "RHM.DE",   # Rheinmetall AG (XETRA) — kein stabiler OTC-ADR verfügbar
    "BA.L",     # BAE Systems (London) — BAESY OTC zu dünn
    "SAAB-B.ST",# Saab AB (Stockholm) — SAABY OTC zu dünn
    "HO.PA",    # Thales SA (Euronext Paris) — THLLY OTC zu dünn
    "LDO.MI",   # Leonardo SpA (Milano)
    # Japan (ADRs only)
    "TM","HMC","SONY","NTT","MUFG","SMFG","MFG","NTDOY","KYOCY","FANUY",
    "CCOEY","ITOCY","MARUY",
    # Suedkorea
    "SSNLF","MX",
    # Taiwan
    "TSM",
    # China/Hongkong (US-gelistete ADRs)
    "BABA","JD","PDD","BIDU",
    "TCEHY","BYDDY","NIO","XPEV","LI",
    # Indien (ADR)
    "INFY","WIT","HDB","IBN","RDY",  # v4.3: VEDL + TTM (ADRs delistet)
    # Kanada (US-listed)
    # v4.2-Fix: CCO war Clear Channel Outdoor (falsche Firma!) — Cameco = CCJ
    "SHOP","CNQ","SU","CNI","CP","TD","RY","BNS","ENB","TRP","NTR","CCJ",
    # Australien (ADR)
    "BHP","RIO","WDS","ORG.AX",  # v4.3: ORG hat kein US-Listing → Heimatbörse ASX
    # Brasilien (ADR)
    "VALE","PBR","ITUB","BBD","ABEV","BRKM",
    # Mexiko/Latam
    "AMX","FMX",  # v4.3: Femsa-NYSE-Symbol ist FMX (FMXB ungültig)
    # Suedafrika / EM Sonstiges
    "PROSY","NPSNY",  # v4.3: Prosus-OTC-Symbol ist PROSY (PROSSY ungültig)
    # Israel Tech
    "CHKP","NICE","CYBR","WIX","MNDY","GLBE","GTLB",
]

# ── SEKTOR-ETFs USA (2-5 pro Sektor) ─────────────────────────────────────────
# Breite Markt-Benchmarks
SECTOR_ETFS_BROAD = [
    "SPY","QQQ","IWM","RSP","DIA","VTI","MDY","IJR",    # US Broad (RSP = Equal-Weight S&P für Breadth)
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
    # Nuclear / Uranium / Space (v4.2, 02.07.2026 — RS-Referenz neue Watchlists)
    "NLR","URA","ARKX",
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
    # AI & Robotics / Innovation
    # v4.2-Fix: ARKK stand seit v4.0 in RS_SECTOR_ETFS, fehlte aber im
    # Download-Universum → RS-Berechnung wurde nachts still übersprungen
    "BOTZ","ROBO","IRBO","AIQ","THNQ","ARKK",
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
    "EZU","VGK","IEUR","FEZ","EWG","EWU","EWI","EWQ","EWP","EWN","EWD","EWL",  # v4.3: EWF existiert nicht (Frankreich = EWQ)
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
    # Defence: US-Titel + europäische Heimatbörsen-Symbole (ADRs wie RHTRY haben keinen stabilen API-Feed)
    "DEFENSE":      ["LMT","RTX","NOC","GD","BA","KTOS","AXON","HII","TDG","HWM","HEI",
                     "LDOS","SAIC","CACI","MOG-A","TXT","CW","DRS",  # v4.3: Yahoo-Symbol für Moog ist MOG-A
                     # v4.2 (02.07.2026): Gemini-Liste — Drohnen/Nuklear/Defense-Tech
                     "AVAV","LHX","BWXT","PLTR",
                     "RHM.DE","BA.L","SAAB-B.ST","HO.PA","LDO.MI"],
    # Robotics/AI-Hardware (01.07.2026): IRBO neu, bestehende konsolidiert
    "ROBOTICS":     ["NVDA","ABB","FANUY","IRBO","BOTZ","ROBO","ISRG","KEYS","TER","AZTA","ONTO","NDSN",
                     # v4.2 (02.07.2026): Gemini-Liste — Automation/Vision/Chips (COGN→CGNX korrigiert)
                     "SYM","ROK","MBLY","TDY","CGNX","PATH","ZBRA","IR","ADI","NXPI","MCHP"],
    "BIOTECH":      ["MRNA","BNTX","REGN","VRTX","GILD","BIIB","ILMN","ARKG","ABBV","LLY","NVO","AZN"],
    "CLEAN_ENERGY": ["ENPH","FSLR","SEDG","RUN","BE","PLUG","NEE","ARRY","BLDP","ICLN","QCLN"],
    "FINTECH":      ["XYZ","HOOD","AFRM","SOFI","UPST","COIN","PYPL","V","MA","SCHW","NU","STNE"],
    "GLPONE":       ["LLY","NVO","VKTX","RYTM","AMGN","REGN","AZN","SNY","GILD","PFE","RHHBY"],
    "PICKS_SHOVELS":["NVDA","AMD","AVGO","AMAT","LRCX","TSM","ARM","KLAC","SNPS","CDNS","ONTO","ACLS"],
    "WHEEL_STOCKS": ["DDOG","AMSC","IREN","CIFR","PBR","CLSK","NVO","HOOD","ENVX","MRVL","COIN"],
    "LUXURY_EU":    ["LVMUY","LRLCY","HESAY","CFRUY","PPRUY","ADDYY","BURBY","RACE","CPRI","RL"],
    "JAPAN_TECH":   ["TM","SONY","NTDOY","KYOCY","FANUY","CCOEY","HMC"],
    "EM_GROWTH":    ["TSM","BABA","PDD","INFY","VALE","ITUB","NU","STNE","SE","GRAB"],
    # ── v4.2 (02.07.2026): 5 neue Sektoren (Gemini-Liste, Kausalitätsprüfung bestanden) ──
    # Governance: CEG NUR hier unter NUCLEAR_ENERGY (Kernkraft-Versorger, kein
    # Rohstoffwert). IBM/HON bewusst NICHT in CYBERSECURITY (Mischkonzerne mit
    # Cyber-Anteil <10% Umsatz — würden den Sektor-Filter im Scanner verwässern).
    "MATERIALS":    ["FCX","ALB","MP","TECK","CCJ","SCCO","VALE","SQM","BHP","RIO",
                     "HBM","ERO","LAC"],  # v4.7: Kupfer-Mid-Caps + Lithium (Gemini, verifiziert)
    "CYBERSECURITY":["PANW","CRWD","FTNT","NET","ZS","OKTA"],
    "NUCLEAR_ENERGY":["CEG","VST","NRG","TLN","SMR","OKLO","ETN","PWR","HUBB",
                     "LEU","UEC","UUUU","NXE"],  # v4.7: Uran-Fuel-Cycle (Gemini, verifiziert)
    "SPACE":        ["RKLB","ASTS","HWM","TDG"],
    "BIOTECH_LONGEVITY":["CRSP","BEAM","NTLA","EXAS","ILMN","RXRX","DXCM","ALGN"],
    # v4.7 (05.07.2026): Supercycle-Sektoren (Gemini-Vorschlag, Claude-verifiziert —
    # 10 Fehlticker/Fehlklassifikationen aussortiert: VERT→VRT, PRE→PLPC, GOLD→B,
    # SILV/PEAK/UHR/CNHI veraltet, FI/TTE Fehlkategorie, RKDA Nano-Cap).
    # Demografie-Qualitätstitel bewusst NICHT als Scan-Sektor (Value-Thema →
    # docs/VALUE_MOD_KONZEPT.md Themenregister; FIN-Archiv sammelt sie via R3000).
    "GRID_ELECTRIFICATION": ["GEV","EMR","VMI","AME","POWL","AEIS","PLPC"],
    "PRECIOUS_METALS":      ["NEM","B","WPM","FNV","RGLD","PAAS","HL","AG","EXK","FSM","MAG"],
    "AGRICULTURE":          ["DE","AGCO","CTVA","NTR","MOS","CF","FMC","DAR","CNH","AVD"],
    "WATER":                ["XYL","AWK","WTS","AOS","ECL","BMI"],
    # v4.7: Picks&Shovels vom Frontend-Index-Slot zum getaggten Sektor befördert
    # (Axel: "hat nichts zu suchen in der Kategorie S&P500/Nasdaq")
    "PICKS_SHOVELS":        ["NVDA","AMD","AVGO","AMAT","LRCX","KLAC","MRVL","ARM","TSM","SMCI",
                             "MSFT","AMZN","GOOGL","META","ORCL","VRT","ETN","PWR","HUBB","CEG"],
}

# ── SEKTOR-TAG-INDEX (automatisch abgeleitet, NICHT manuell pflegen!) ─────────
# Invertierung von SECTOR_WATCHLISTS: {ticker → [sektoren]}.
# Zwischenstufe auf dem Weg zu TICKER_SECTOR_MAP als einziger Wahrheitsquelle.
#
# GOVERNANCE — NEUE TICKER AUFNEHMEN:
#   1. Ticker zur passenden Liste in SECTOR_WATCHLISTS oben eintragen
#   2. TICKER_SECTOR_TAG wird automatisch neu berechnet
#   3. KEIN manueller Eintrag hier nötig — diese Variable nie direkt editieren!
#
# MITTELFRISTIG (eigene Session):
#   Migration zu TICKER_SECTOR_MAP = {"NVDA": ["AI_TECH","SEMIS",...], ...}
#   als echter Single Source of Truth — dann entfällt auch die Duplikation
#   zwischen SECTOR_WATCHLISTS und SP500_TICKERS/NASDAQ100_EXTRA.
TICKER_SECTOR_TAG = {}
for _sector, _tickers in SECTOR_WATCHLISTS.items():
    for _t in _tickers:
        TICKER_SECTOR_TAG.setdefault(_t, []).append(_sector)

# ── RS-REFERENZ ETFs fuer Sektor Relative-Staerke ─────────────────────────────
RS_SECTOR_ETFS = [
    "XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLRE","XLB","XLC",
    "SMH","SOXX","IBB","XBI","ARKK","BOTZ","ITA","ICLN","VNQ",
    # Defence & Aerospace (01.07.2026 ergänzt)
    "XAR","PPA","DFEN",
    # Robotics & AI-Hardware (01.07.2026 ergänzt)
    "IRBO","ROBO",
    # v4.2 (02.07.2026): RS-Referenzen der neuen Watchlists —
    # XLB (Materials) und ITA/XBI bereits oben vorhanden
    "HACK","CIBR",   # Cybersecurity
    "NLR","URA",     # Nuclear Energy / Uran
    "ARKX",          # Space
    "ARKG",          # Biotech/Genomics (BIOTECH_LONGEVITY)
    # Ex-US RS
    "EZU","EWJ","EWG","FXI","INDA","EWZ","EWY","EWT",
]


# ── FTSE 100 TOP 40 (London Stock Exchange) ───────────────────────────────────
# FTSE100/STOXX_EU_EXTRA: NUR Referenz (Heimatboersen — keine US-Optionen)
FTSE100_TICKERS = ['AZN.L', 'SHEL.L', 'HSBA.L', 'ULVR.L', 'RIO.L', 'BP.L', 'GSK.L', 'REL.L', 'BATS.L', 'DGE.L', 'NG.L', 'VOD.L', 'BA.L', 'EXPN.L', 'LSEG.L', 'PRU.L', 'AAL.L', 'GLEN.L', 'NWG.L', 'LLOY.L', 'BT-A.L', 'MNG.L', 'AV.L', 'TSCO.L', 'ABF.L', 'IMB.L', 'STAN.L', 'WPP.L', 'CRH.L', 'IHG.L', 'RKT.L', 'SSE.L', 'BME.L', 'EZJ.L', 'IAG.L', 'RR.L', 'SBRY.L', 'MKS.L', 'JD.L', 'SPX.L']

# ── STOXX EUROPE EXTRA (Schweiz, Skandinavien, Benelux) ──────────────────────
STOXX_EU_EXTRA = ['NOVO-B.CO', 'DSV.CO', 'CARL-B.CO', 'ORSTED.CO', 'MAERSK-B.CO', 'GIVN.SW', 'SIKA.SW', 'LONN.SW', 'ROG.SW', 'NOVN.SW', 'ABBN.SW', 'ZURN.SW', 'ALC.SW', 'PGHN.SW', 'HOLN.SW', 'ERICB.ST', 'VOLVA.ST', 'ATCO-A.ST', 'SAND.ST', 'SEB-A.ST', 'UCB.BR', 'KER.PA', 'KNEBV.HE']

# ── BEAR-KANDIDATEN US (Momentum/Hype-Titel mit hohem Rückschlagpotenzial) ───
BEAR_US_TICKERS = ['SMCI', 'MSTR', 'MRVL', 'ALAB', 'CRWD', 'SNOW', 'NET', 'DDOG', 'MDB', 'SHOP', 'XYZ', 'HOOD', 'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'ENPH', 'FSLR', 'PLUG', 'BE', 'MRNA', 'BNTX', 'ILMN', 'BIIB', 'ZM', 'DOCU', 'UBER', 'LYFT', 'ABNB', 'DASH', 'RBLX', 'SNAP', 'PINS', 'MTCH', 'UPST', 'AFRM', 'SOFI', 'GME', 'PLTR', 'COIN', 'TSLA', 'BABA', 'PDD', 'BIDU', 'AMD', 'NVDA', 'ARM']

# ── BEAR-KANDIDATEN DE/EU (Zykliker, Immobilien, Hochverschuldete) ───────────
BEAR_DE_EU_TICKERS = ['BAYN.DE', 'VOW3.DE', 'BMW.DE', 'MBG.DE', 'CON.DE', 'DHER.DE', 'ZAL.DE', 'VNA.DE', 'LEG.DE', 'TAG.DE', '1COV.DE', 'EVT.DE', 'SRT.DE', 'NDX1.DE', 'AIXA.DE', 'WAF.DE', 'IFX.DE', 'STLAM.MI', 'RNO.PA', 'VOD.L', 'BT-A.L', 'TEF.MC', 'UCB.BR', 'GLPG.BR', 'ARND.DE', 'WDP.BR', 'RWE.DE', 'ENEL.MI', 'EZJ.L', 'IAG.L', 'DTE.DE', 'GLEN.L', 'AAL.L']

def fetch_approved_extra_tickers():
    """Liest vom Frontend vorgeschlagene + per Admin-Review freigegebene Ticker
    aus Cloudflare KV (Key: approved_extra_tickers, geschrieben vom ko-ai Worker
    nach /extra-tickers/approve). Erweitert die feste Ticker-Universe NEU
    (30.06.2026) — siehe ko-ai-worker.js für den Review-Workflow.
    Fehlerfall (KV nicht erreichbar, keine Credentials, leere Liste): gibt
    einfach [] zurück, bricht den Lauf NICHT ab — fest codierte Listen bleiben
    die verlässliche Grundlage."""
    account_id = os.environ.get("CF_ACCOUNT_ID")
    api_token  = os.environ.get("CF_API_TOKEN")
    ns_id      = os.environ.get("CF_KV_NS_ID")
    if not all([account_id, api_token, ns_id]):
        return []

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{ns_id}/values/approved_extra_tickers"
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            log.info(f"  Keine approved_extra_tickers in KV (Status {r.status_code}) — übersprungen.")
            return []
        entries = r.json()
        if not isinstance(entries, list):
            return []
        syms = [e.get("sym") for e in entries if isinstance(e, dict) and e.get("sym")]
        if syms:
            log.info(f"  ✅ {len(syms)} Extra-Ticker aus Admin-Review-KV übernommen: {', '.join(syms[:20])}{' ...' if len(syms) > 20 else ''}")
        return syms
    except Exception as e:
        log.warning(f"  Extra-Ticker-Abruf fehlgeschlagen (nicht kritisch): {e}")
        return []


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
        [t for wl in SECTOR_WATCHLISTS.values() for t in wl] +
        # NEU (30.06.2026): per Fibo-Tab vorgeschlagene + admin-freigegebene Ticker
        fetch_approved_extra_tickers()
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
    # Diagnose (temporär)
    import logging as _lg; _lg.getLogger("aggregator").debug(f"[HVP] available={available} lookback={lookback} closes={len(closes)}")
    try:
        def hv30(cls):
            # Fix: Filter Nullen/negative Preise (yfinance Datenfehler)
            cls = [c for c in cls if c and c > 0]
            if len(cls) < 2:
                return None
            log_rets = [math.log(cls[i] / cls[i-1]) for i in range(1, len(cls))]
            if not log_rets:
                return None
            mean_lr = sum(log_rets) / len(log_rets)
            variance = sum(x**2 for x in log_rets) / len(log_rets) - mean_lr**2
            # Fix: max(0,...) verhindert sqrt negativer Zahl (Float-Precision)
            return math.sqrt(252) * math.sqrt(max(0.0, variance))

        # Aktuelle HV
        current_hv = hv30(closes[-window:])
        if current_hv is None:
            return None

        # Historische HV-Serie — per-Window Exception-Handling
        # Gemini Fix 1: i=1 statt i=0 → current_hv nicht in historischer Verteilung
        # (sonst wird current_hv doppelt gezählt → Perzentil-Verzerrung)
        hv_series = []
        for i in range(1, lookback + 1):
            try:
                end = len(closes) - i
                start = end - window
                if start < 0:
                    break
                hv = hv30(closes[start:end])
                # Gemini Fix 2: hv=0.0 = flache Kurshistorie → unbrauchbar für Perzentil
                if hv is not None and hv > 0.0:
                    hv_series.append(hv)
            except Exception:
                continue  # Schlechtes Fenster überspringen

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

    # Gate 1 (Gemini Fix: aufgeweicht auf 15% für Bear/MR-Setups)
    if not ema200: return 0
    if price < ema200 * 0.85: return 0   # Gemini: war 0.95 → 0.85

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

    # Fibonacci-Boost (NEU 30.06.2026, Gemini-Blueprint-Zuordnung) — CSP_ZONE
    # bestaetigt unabhaengig von BB/RSI/Regime, dass der Kurs nahe einem
    # Retracement-Level (61.8%/78.6%) liegt = klassische CSP-Einstiegszone.
    # Skaliert mit Confluence-Score (0-100), max +15 Pkt bei Score>=75.
    if r.get("f_setup") == "CSP_ZONE":
        s += min(int((r.get("f_score", 0) or 0) * 0.20), 15)

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
    if ema50 and price < ema50 * 0.90: return 0  # Gemini Fix: 10% Puffer erlaubt
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

    # Fibonacci-Boost (NEU 30.06.2026, Gemini-Blueprint-Zuordnung) — EXTENSION
    # bestaetigt: Kurs nahe 127.2%/161.8%-Extension + ueberkauft (RSI>70) =
    # klassische Covered-Call-Zone (Strike am Extension-Level). Skaliert mit
    # Confluence-Score (0-100), max +15 Pkt bei Score>=75.
    if r.get("f_setup") == "EXTENSION":
        s += min(int((r.get("f_score", 0) or 0) * 0.20), 15)

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
        s += 20  # Gemini Fix: Basis-Punkte für korrektes Regime
        if bbpos is not None:
            if bbpos >= 0.80:   s += 30  # Überdehnt = Bear-Call ideal
            elif bbpos <= 0.20: s += 15  # Gemini Fix: Überverkauft = Bounce-Prämie                      # Aktie stößt an Oberkante — ideal für Bear Call
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


def calc_squeeze_risk(r: dict) -> int:
    """
    Short-Squeeze-Risiko-Proxy (Gemini-Blueprint, 01.07.2026).
    Kein Short-Interest-API verfügbar — Proxy aus Volumen-/Vola-Struktur.
    Gibt Score 0-100 zurück: >=70 = hartes Gate für alle Short-Strategien.

    Kernlogik: Aktie im Keller (BB-Bottom) + plötzlicher Volumen-Spike an
    grünem Tag + historisch tiefes Volatilität-Percentil → elastische Feder,
    Squeeze-Wahrscheinlichkeit sehr hoch.
    """
    hvp      = r.get("hvp")
    rsi      = r.get("rsi")
    bbpos    = r.get("bbPos")
    vol_ratio= r.get("volRatio", 1) or 1
    price    = r.get("price", 0)
    open_    = r.get("open_last")   # Intraday-Open nicht immer verfügbar

    score = 0

    # Primärsignal: HVP extrem niedrig + RSI überverkauft → aufgebaute Spannung
    if hvp is not None and hvp < 15:
        score += 30
    elif hvp is not None and hvp < 25:
        score += 15

    if rsi is not None and rsi < 25:
        score += 25
    elif rsi is not None and rsi < 35:
        score += 12

    # BB-Position im Keller (aufgestaute Energie)
    if bbpos is not None and bbpos < 0.10:
        score += 20
    elif bbpos is not None and bbpos < 0.20:
        score += 10

    # Volumen-Spike (Proxy für institutionelles Eindecken)
    if vol_ratio >= 2.0:
        score += 20
    elif vol_ratio >= 1.5:
        score += 10

    return max(0, min(100, score))


def calc_ko_short_leverage(r: dict) -> int:
    """
    Dynamische KO-Short-Hebelempfehlung (Gemini-Blueprint, 01.07.2026).
    Formel: Hebel = clamp(1.5 / (ATR / Preis), 3, 8).
    Hohe ATR = niedriger Hebel (weiter KO-Strike-Abstand nötig) und umgekehrt.
    Gibt empfohlenen Hebel als Integer zurück (3-8).
    """
    price = r.get("price", 0)
    atr   = r.get("atr")
    if not price or not atr or atr <= 0:
        return 3   # konservativer Fallback
    atr_pct = atr / price
    if atr_pct <= 0:
        return 3
    leverage = 1.5 / atr_pct
    return max(3, min(8, round(leverage)))


def score_short_fading(r: dict) -> int:
    """
    Short Fading (FOMO-Climax): Extreme Ueberdehnung + Kauf-Erschoepfung.
    Gemini-Fix v2: BBPos-Schwelle 0.92->0.85, HVP Squeeze-Schutz.
    Gemini-Review 01.07.2026: Squeeze-Risk-Gate + Sektor-RS-Boost.
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
    high52   = r.get("high52")

    if not ema200 or not atr or atr == 0: return 0

    # Hartes Gate (Gemini): Penny-Stock-Schutz
    if price < 15.0: return 0

    # Hartes Gate (Gemini): Niemals gegen säkulare Allzeithochs shorten
    if high52 and price >= high52 * 0.99: return 0

    # Hartes Gate (Gemini 01.07.2026): Squeeze-Risk aus process_ticker() lesen
    # (dort mit Zugriff auf hist_df/direktionalem Volumen-Check berechnet).
    squeeze_risk = r.get("squeezeRisk") or 0
    if squeeze_risk >= 70: return 0   # Zu gefährlich — kein Fading-Short

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

    # Sektor-RS-Boost (Gemini 01.07.2026): Schwacher Sektor verstärkt Fading-Signal.
    # Nutzt sektor_rs (relatives Momentum des Sektor-ETFs) falls in r vorhanden.
    # Wird in build_leaderboards() gesetzt wenn Sektor-Daten geladen wurden.
    sector_rs = r.get("_sector_rs5")
    if sector_rs is not None and sector_rs < -1.0:
        # Sektor underperformt SPY um >1% (5-Tage) → Tailwind für Short
        s += 15 if sector_rs < -2.0 else 8

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




def calc_ios_market_score(hist_data: dict, vix_term: dict = None) -> dict:
    """
    IOS Market Score v1.0 — Python-Port für UnderlyingIQ Aggregator.
    Bewertet das Marktumfeld für neue Long-Käufe (0-100).
    Quelle: IOS_Market_Score_v1_0 Pine Script (Club-Kolleg:in).

    Module: Trend(35) + Breadth(25) + Risk(20) + Momentum(10) + Rotation(10)
    Knock-out: SPY<SMA200 → cap65 | Risk≤6 → cap70 | Breadth≤8 → cap72
    Decision: KAUFEN ERLAUBT / SELEKTIV KAUFEN / NUR TOP-SETUPS /
              KEINE NEUEN BREAKOUTS / KEINE NEUEN KAEUFE
    """
    def get_closes(sym):
        df = hist_data.get(sym)
        if df is None or len(df) < 10: return []
        try:
            col = 'Close' if 'Close' in df.columns else df.columns[0]
            return [float(x) for x in df[col].dropna().tolist()]
        except Exception:
            return []

    def sma(closes, n):
        if len(closes) < n: return None
        return sum(closes[-n:]) / n

    def sma_n_ago(closes, n, ago=20):
        if len(closes) < n + ago: return None
        return sum(closes[-(n+ago):-ago]) / n

    def ratio_ma(a_closes, b_closes, ma_len=50):
        """Verhältnis zweier Serien — synchronisiert via min-Länge (Gemini Fix 2)."""
        # Gemini Fix: Längen synchronisieren verhindert Indexverschiebung bei Datalücken
        min_len = min(len(a_closes), len(b_closes))
        if min_len < ma_len + 5: return None, None  # +5 Sicherheitspuffer
        # Beide auf gleiche Länge kürzen (neueste Daten behalten)
        a = a_closes[-min_len:]
        b = b_closes[-min_len:]
        ratios = [a[i] / b[i] for i in range(min_len) if b[i] != 0]
        if len(ratios) < ma_len: return None, None
        current = ratios[-1]
        ma      = sum(ratios[-ma_len:]) / ma_len
        return current, ma

    def rsi(closes, period=14):
        if len(closes) < period + 1: return None
        gains = [max(closes[i]-closes[i-1], 0) for i in range(1, len(closes))]
        losses= [max(closes[i-1]-closes[i], 0) for i in range(1, len(closes))]
        ag = sum(gains[-period:]) / period
        al = sum(losses[-period:]) / period
        if al == 0: return 100.0
        return round(100 - 100 / (1 + ag/al), 1)

    def macd_bull(closes):
        if len(closes) < 35: return False
        def ema_last(s, p):
            k = 2/(p+1); v = s[0]
            for x in s[1:]: v = x*k + v*(1-k)
            return v
        fast = ema_last(closes[-34:], 12)
        slow = ema_last(closes[-34:], 26)
        return fast > slow

    # Daten laden
    spy = get_closes('SPY');  qqq = get_closes('QQQ')
    iwm = get_closes('IWM');  rsp = get_closes('RSP')
    smh = get_closes('SMH');  hyg = get_closes('HYG')
    tlt = get_closes('TLT')

    vix_val = (vix_term or {}).get('vix', 20)

    # SMAs
    spy50  = sma(spy, 50);  spy200  = sma(spy, 200)
    spy200_ago20 = sma_n_ago(spy, 200, 20)
    qqq200 = sma(qqq, 200); qqq200_ago20 = sma_n_ago(qqq, 200, 20)
    smh200 = sma(smh, 200)
    rsp50  = sma(rsp, 50);  rsp200  = sma(rsp, 200)
    iwm50  = sma(iwm, 50);  iwm200  = sma(iwm, 200)
    hyg50  = sma(hyg, 50)

    spy_last = spy[-1] if spy else None
    qqq_last = qqq[-1] if qqq else None
    smh_last = smh[-1] if smh else None
    rsp_last = rsp[-1] if rsp else None
    iwm_last = iwm[-1] if iwm else None

    # Ratios
    rspSpy, rspSpyMa = ratio_ma(rsp, spy, 50)
    iwmSpy, iwmSpyMa = ratio_ma(iwm, spy, 50)
    qqqSpy, qqqSpyMa = ratio_ma(qqq, spy, 50)
    smhSpy, smhSpyMa = ratio_ma(smh, spy, 50)
    hygTlt, hygTltMa = ratio_ma(hyg, tlt, 50)
    hygSpy, hygSpyMa = ratio_ma(hyg, spy, 50)

    # RSP/SPY Trend (10 Bars)
    min_rsp_spy = min(len(rsp), len(spy))
    rspSpy_10ago = (rsp[-11]/spy[-11]) if min_rsp_spy >= 11 else None

    # ── MODULE 1: MARKET TREND /35 ────────────────────────────────────────────
    trend1 = bool(spy_last and spy200 and spy_last > spy200)
    trend2 = bool(spy200 and spy200_ago20 and spy200 > spy200_ago20)
    trend3 = bool(spy_last and spy50 and spy_last > spy50)
    trend4 = bool(qqq_last and qqq200 and qqq_last > qqq200)
    trend5 = bool(qqq200 and qqq200_ago20 and qqq200 > qqq200_ago20)
    trend6 = bool(smh_last and smh200 and smh_last > smh200)
    trend7 = bool(rsp_last and rsp200 and rsp_last > rsp200)
    trend_score = sum([trend1,trend2,trend3,trend4,trend5,trend6,trend7]) * 5

    # ── MODULE 2: BREADTH PROXY /25 ───────────────────────────────────────────
    breadth1 = bool(rsp_last and rsp50  and rsp_last > rsp50)
    breadth2 = bool(rsp_last and rsp200 and rsp_last > rsp200)
    breadth3 = bool(rspSpy and rspSpyMa and rspSpy > rspSpyMa)
    breadth4 = bool(rspSpy and rspSpy_10ago and rspSpy > rspSpy_10ago)
    breadth5 = bool(iwmSpy and iwmSpyMa and iwmSpy > iwmSpyMa)
    breadth_score = sum([breadth1,breadth2,breadth3,breadth4,breadth5]) * 5

    # ── MODULE 3: RISK /20 ────────────────────────────────────────────────────
    vix_ma20 = None  # Proxy: wir nutzen vix_term Daten
    vix_calm   = 20.0
    vix_stress = 25.0
    risk1 = bool(vix_val and vix_val < vix_calm)
    risk2 = bool(vix_val and vix_val < vix_stress)  # vereinfacht (kein vixMa20)
    risk3 = bool(vix_val and vix_val < 22)           # VIX MA-Proxy
    risk4 = bool(hygTlt and hygTltMa and hygTlt > hygTltMa)
    risk5 = bool(hyg and hyg[-1] and hyg50 and hyg[-1] > hyg50)
    risk_score = ((5 if risk1 else 0) + (4 if risk2 else 0) +
                  (4 if risk3 else 0) + (4 if risk4 else 0) + (3 if risk5 else 0))

    # ── MODULE 4: MARKET MOMENTUM /10 ─────────────────────────────────────────
    spy_rsi = rsi(spy, 14)
    mom1 = bool(spy_rsi and 50 <= spy_rsi <= 75)
    mom2 = macd_bull(spy)
    mom3 = bool(spy_rsi and spy_rsi > 50)  # ADX-Proxy: Trend stark wenn RSI>50
    mom_score = (4 if mom1 else 0) + (3 if mom2 else 0) + (3 if mom3 else 0)

    # ── MODULE 5: ROTATION /10 ────────────────────────────────────────────────
    rot1 = bool(qqqSpy and qqqSpyMa and qqqSpy > qqqSpyMa)
    rot2 = bool(smhSpy and smhSpyMa and smhSpy > smhSpyMa)
    rot3 = bool(hygSpy and hygSpyMa and hygSpy > hygSpyMa)
    rotation_score = (4 if rot1 else 0) + (3 if rot2 else 0) + (3 if rot3 else 0)

    # ── KNOCK-OUT CAPS ────────────────────────────────────────────────────────
    raw = trend_score + breadth_score + risk_score + mom_score + rotation_score
    capped = raw
    if not trend1:      capped = min(capped, 65)   # SPY unter SMA200
    if risk_score <= 6: capped = min(capped, 70)   # Risikoumfeld kritisch
    if breadth_score <= 8: capped = min(capped, 72) # Marktbreite schwach
    overall = max(0, min(100, capped))

    # ── RATING & DECISION ─────────────────────────────────────────────────────
    def rating(s):
        if s >= 95: return "AAA"
        if s >= 90: return "AA+"
        if s >= 85: return "AA"
        if s >= 80: return "A"
        if s >= 75: return "BBB+"
        if s >= 70: return "BBB"
        if s >= 65: return "BB"
        if s >= 50: return "B"
        return "NO"

    if overall >= 85 and trend_score >= 28 and breadth_score >= 18 and risk_score >= 14:
        decision = "KAUFEN ERLAUBT"
    elif overall >= 75:
        decision = "SELEKTIV KAUFEN"
    elif overall >= 60:
        decision = "NUR TOP-SETUPS"
    elif overall >= 45:
        decision = "KEINE NEUEN BREAKOUTS"
    else:
        decision = "KEINE NEUEN KAEUFE"

    if overall >= 85 and risk_score >= 14:
        mode = "OFFENSIV"
    elif overall >= 75:
        mode = "SELEKTIV"
    elif overall >= 60:
        mode = "NEUTRAL"
    elif overall >= 45:
        mode = "DEFENSIV"
    else:
        mode = "KAPITAL SCHUETZEN"

    # Diagnose
    diag_trend    = "Markttrend stark" if trend_score >= 30 else "Trend intakt" if trend_score >= 22 else "Trend fragil" if trend_score >= 15 else "Trend schwach"
    diag_breadth  = "Breite Teilnahme" if breadth_score >= 20 else "Breadth okay" if breadth_score >= 15 else "Breadth schmal" if breadth_score >= 10 else "Interne Schwaeche"
    diag_risk     = "Risiko ruhig"     if risk_score >= 16 else "Risiko normal" if risk_score >= 11 else "Risiko erhoeht" if risk_score >= 7 else "Risiko kritisch"
    diag_rotation = "Risk-on Rotation" if rotation_score >= 8 else "Rotation neutral" if rotation_score >= 5 else "Defensive Rotation"

    log.info(f"  [IOS-Market] Score={overall} ({rating(overall)}) | {decision}")
    log.info(f"  [IOS-Market] Trend={trend_score}/35 Breadth={breadth_score}/25 Risk={risk_score}/20 Mom={mom_score}/10 Rot={rotation_score}/10")

    return {
        "iosMarketScore":    overall,
        "iosMarketRating":   rating(overall),
        "iosMarketDecision": decision,
        "iosMarketMode":     mode,
        "iosMarketTrend":    trend_score,
        "iosMarketBreadth":  breadth_score,
        "iosMarketRisk":     risk_score,
        "iosMarketMom":      mom_score,
        "iosMarketRotation": rotation_score,
        "iosMarketDiags": {
            "trend":    diag_trend,
            "breadth":  diag_breadth,
            "risk":     diag_risk,
            "rotation": diag_rotation,
        },
        "details": {
            "spy_above_sma200":  trend1,
            "spy_sma200_rising": trend2,
            "qqq_above_sma200":  trend4,
            "smh_above_sma200":  trend6,
            "rsp_above_sma200":  trend7,
            "breadth_rsp_spy":   breadth3,
            "risk_vix_calm":     risk1,
            "risk_hyg_tlt":      risk4,
            "rotation_qqq_spy":  rot1,
            "rotation_smh_spy":  rot2,
        }
    }

def calc_ios_score(r: dict) -> dict:
    """
    IOS Foundation v1.2 — Python-Port für UnderlyingIQ (Club-Integration).
    Neu in v1.2: Quality/Entry-Trennung, Leader-Wait-Pullback-Logik.

    overallScore = qualityPct×0.70 + entryPct×0.30
    → Leader im Pullback bekommt jetzt "LEADER WAIT PULLBACK" statt "NO BUY"
    → Entry-Score bleibt separat sichtbar

    Rating-Skala: AAA(95+) AA+(90) AA(85) A(80) BBB+(75) BBB(70) BB(65) B(50) NO
    Decision: BUY FIRST TRANCHE / LEADER WAIT PULLBACK / SELECTIVE ENTRY / WATCHLIST / NO BUY
    """
    price    = r.get("price", 0) or 0
    ema50    = r.get("ema50")
    ema200   = r.get("ema200")
    rsi      = r.get("rsi", 50) or 50
    macd_h   = r.get("macdHist")
    vol_r    = r.get("volRatio", 1) or 1
    atr      = r.get("atr")
    dist50   = r.get("dist50", 0) or 0
    dist200  = r.get("dist200", 0) or 0
    overheat = r.get("overheat", 0) or 0
    pct_high = r.get("pctFromHigh52", 0) or 0
    bbpos    = r.get("bbPos")
    regime   = (r.get("regime") or "").lower()
    score_c  = r.get("score", 50) or 50
    s_min    = r.get("sMinervini", 0) or 0

    # ── TREND SCORE /35 ───────────────────────────────────────────────────────
    trend_score = 0
    if ema200 and price > ema200:   trend_score += 5
    if dist200 > 0:                 trend_score += 5
    if ema50 and price > ema50:     trend_score += 5
    if dist50 > 0:                  trend_score += 5
    if ema50 and ema200 and ema50 > ema200: trend_score += 5
    if regime in ("bull", "side"):  trend_score += 5
    if bbpos is not None and bbpos > 0.5:   trend_score += 5

    # ── RS SCORE /20 ──────────────────────────────────────────────────────────
    rs_score = 0
    if s_min >= 50:   rs_score += 5
    if s_min >= 65:   rs_score += 5
    if score_c >= 60: rs_score += 5
    if dist200 > 5 and dist200 < 40: rs_score += 5

    # ── MOMENTUM SCORE /10 ────────────────────────────────────────────────────
    mom_score = 0
    if rsi >= 55 and rsi <= 75:         mom_score += 4
    if macd_h is not None and macd_h > 0: mom_score += 3
    if regime == "bull":                mom_score += 3

    # ── VOLUME SCORE /15 ──────────────────────────────────────────────────────
    vol_score = 0
    if vol_r >= 1.0: vol_score += 5
    if vol_r >= 1.2: vol_score += 5
    if vol_r >= 1.2 and macd_h and macd_h > 0: vol_score += 5

    # ── QUALITY (Trend + RS + Mom + Vol, max 80) ──────────────────────────────
    quality_raw = trend_score + rs_score + mom_score + vol_score  # max 80
    quality_pct = round(quality_raw / 80 * 100)

    # ── ENTRY SCORE /20 ───────────────────────────────────────────────────────
    atr_pct = (atr / price * 100) if atr and price > 0 else 0
    entry1 = -2 <= dist50 <= 8
    entry2 = -3 <= dist50 <= 15
    entry3 = atr_pct <= 7
    entry4 = pct_high >= -15 and dist50 <= 15

    entry_base = sum([entry1, entry2, entry3, entry4]) * 5

    # v1.2 FIX #3: rvol aus Penalty entfernt (Doppelzählung mit vol_score)
    # Nur noch 3 reine Geometrie-Penalties
    penalty = ((3 if rsi > 80 else 0) +
               (3 if dist50 > 8 + 5  else 0) +   # distEma21 Proxy
               (4 if dist50 > 15 + 5 else 0))     # distSma50 Proxy

    entry_score = max(0, min(20, entry_base - penalty))
    entry_pct   = round(entry_score / 20 * 100)

    # ── OVERALL = Quality×0.70 + Entry×0.30 (v1.2 Kernformel) ───────────────
    overall = max(0, min(100, round(quality_pct * 0.70 + entry_pct * 0.30)))

    def rating(s):
        if s >= 95: return "AAA"
        if s >= 90: return "AA+"
        if s >= 85: return "AA"
        if s >= 80: return "A"
        if s >= 75: return "BBB+"
        if s >= 70: return "BBB"
        if s >= 65: return "BB"
        if s >= 50: return "B"
        return "NO"

    # ── v1.2 DECISION LOGIC ───────────────────────────────────────────────────
    is_leader   = quality_pct >= 85
    is_tradable = quality_pct >= 70
    entry_good  = entry_pct   >= 75
    strong_ovx  = dist50 > 20 or rsi > 80  # strongOverextension Proxy

    if is_leader and entry_good:
        decision = "BUY FIRST TRANCHE"
    elif is_leader and not entry_good:
        decision = "LEADER WAIT PULLBACK"   # NEU in v1.2
    elif is_tradable and entry_good:
        decision = "SELECTIVE ENTRY"        # NEU in v1.2
    elif is_tradable:
        decision = "WATCHLIST"
    else:
        decision = "NO BUY"

    # ── DIAGNOSE ──────────────────────────────────────────────────────────────
    diag_trend  = ("Trend sehr stark" if trend_score >= 30 else
                   "Trend intakt"     if trend_score >= 20 else "Trend schwach")
    diag_rs     = "Leader vs Benchmark" if rs_score >= 15 else "RS nicht führend"
    diag_entry  = ("Einstieg attraktiv"  if entry_pct >= 75 else
                   "Entry nur selektiv"  if entry_pct >= 55 else "Pullback abwarten")
    diag_risk   = "Überdehnung" if strong_ovx else "Keine Überdehnung"
    summary     = ("Top-Aktie mit kaufbarem Setup"  if is_leader and entry_good     else
                   "Top-Aktie, kein idealer Einstieg" if is_leader                  else
                   "Watchlist, nur selektiv"         if is_tradable                 else
                   "Keine Kaufqualität")

    return {
        "iosScore":      overall,
        "iosRating":     rating(overall),
        "iosDecision":   decision,
        # v1.2 neu: Quality/Entry getrennt
        "iosQuality":    quality_pct,
        "iosQualityRating": rating(quality_pct),
        "iosEntry":      entry_pct,
        "iosEntryRating": rating(entry_pct),
        "iosIsLeader":   is_leader,
        "iosTrend":      trend_score,
        "iosRS":         rs_score,
        "iosMom":        mom_score,
        "iosVol":        vol_score,
        "iosPenalty":    penalty,
        "iosSummary":    summary,
        "iosDiagTrend":  diag_trend,
        "iosDiagRS":     diag_rs,
        "iosDiagEntry":  diag_entry,
        "iosDiagWarn":   diag_risk,
    }


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


def apply_ios_market_overlay(options_candidates: list, ios_market: dict) -> list:
    """
    IOS Market Score Overlay auf Options-Kandidaten.
    Bei "KEINE NEUEN KAEUFE" → CSP/CC stark gedämpft (Kapitalschutz).
    Bei "KAUFEN ERLAUBT"  → leichter Bonus für Confidence.
    """
    if not ios_market:
        return options_candidates
    ims = ios_market.get("iosMarketScore", 60)
    decision = ios_market.get("iosMarketDecision", "")

    for r in options_candidates:
        if decision == "KEINE NEUEN KAEUFE":
            # Kapitalschutz: alle Long-Options-Strategien stark dämpfen
            r["scoreCsp"] = max(0, int(r.get("scoreCsp", 0) * 0.30))
            r["scoreCc"]  = max(0, int(r.get("scoreCc",  0) * 0.30))
            r["_macroNote"] = r.get("_macroNote","") + " | IOS: KAPITAL SCHUETZEN"
        elif decision == "KEINE NEUEN BREAKOUTS":
            r["scoreCsp"] = max(0, int(r.get("scoreCsp", 0) * 0.55))
            r["_macroNote"] = r.get("_macroNote","") + " | IOS: DEFENSIV"
        elif decision == "NUR TOP-SETUPS":
            r["scoreCsp"] = max(0, int(r.get("scoreCsp", 0) * 0.75))
        elif decision == "KAUFEN ERLAUBT":
            # Leichter Confidence-Bonus
            r["scoreCsp"] = min(100, int(r.get("scoreCsp", 0) * 1.10))
            r["scoreCc"]  = min(100, int(r.get("scoreCc",  0) * 1.10))
        # optsScore neu
        r["optsScore"] = max(r.get("scoreCsp",0), r.get("scoreCc",0), r.get("scoreSpread",0))
    return options_candidates


def enrich_with_fundamentals(sym: str, price: float, sector: str = None) -> dict:
    """
    Fundamentaldaten — bewusst auf 3 Kernfelder reduziert (01.07.2026).
    Jedes Feld hat direkten kausalen Einfluss auf Handelsentscheidungen:

    - analystUpside: Sentiment-Filter — tradest du mit oder gegen den Konsens?
    - fcfYield:      CSP/Wheel-Schutz — kein Put auf Cash-Burner schreiben.
    - debtToEquity:  Short-Gate — hohes D/E stützt Breakdown, ABER:
                     Versorger/REITs ausgenommen (strukturell hohes D/E = normal).

    Alle anderen Felder (P/E, PEG, ROE, EV/EBITDA etc.) haben keinen
    ausreichenden kausalen Einfluss auf 2-30-Tage-Setups und wurden
    bewusst entfernt (80/20-Entscheidung, Gemini + Claude Review 01.07.2026).
    Bei Bedarf: on-demand im DeepDive-Button laden, nicht im Nachtlauf.
    """
    _STRUCTURAL_HIGH_DEBT_SECTORS = {"utilities", "real estate", "reits"}
    try:
        info     = yf.Ticker(sym).info
        target   = info.get("targetMeanPrice")
        upside   = round((target - price) / price * 100, 1) if target and price else None
        fcf      = info.get("freeCashflow")
        mcap     = info.get("marketCap")
        fcf_yield= round(fcf / mcap * 100, 2) if fcf and mcap and mcap > 0 else None
        # D/E nur für Nicht-Versorger/REIT aussagekräftig
        det_sector = (sector or info.get("sector") or "").lower()
        is_structural_debt = any(s in det_sector for s in _STRUCTURAL_HIGH_DEBT_SECTORS)
        de_raw   = info.get("debtToEquity")
        d_eq     = round(de_raw, 1) if de_raw and not is_structural_debt else None
        return {
            "analystUpside":  upside,
            "fcfYield":       fcf_yield,
            "debtToEquity":   d_eq,
        }
    except Exception as e:
        log.warning(f"  Fundamental-Fetch {sym}: {e}")
        return {}


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

        # IOS Foundation v1.2 — NEU (30.06.2026, Batch-2-Punkt aus Übergabeprotokoll):
        # vorher liefen IOS-Score und Minervini-Score komplett unabhängig
        # nebeneinander her, obwohl iosIsLeader (Quality >= 85%) inhaltlich ein
        # starkes Bestätigungssignal für SEPA-Stage-2-Setups ist. Boost nur wenn
        # Gate 1 (Stage-2-Uptrend) in score_long_minervini() bereits bestanden
        # wurde (s_minervini > 0) — Leader-Status soll kein totes Setup retten.
        ios_data = calc_ios_score(r)
        if ios_data.get("iosIsLeader") and s_minervini > 0:
            s_minervini = min(100, s_minervini + 10)

        # Squeeze-Risiko bereits in process_ticker() mit hist_df berechnet (Gemini v2)
        squeeze_risk = r.get("squeezeRisk") or 0
        # KO-Short-Hebelempfehlung (dynamisch aus ATR/Preis)
        ko_short_lev = calc_ko_short_leverage(r) if s_fading >= 35 else None

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
            # Short-spezifische Felder (Gemini 01.07.2026)
            "squeezeRisk":   squeeze_risk,      # 0-100, >=70 = Fading-Gate geschlossen
            "koShortLev":    ko_short_lev,      # Empfohlener Hebel (3-8) oder None
            # IOS Foundation Rating (Club-Integration)
            **ios_data,
        })

    # ── LEADERBOARDS (Top 20 je Strategie) ───────────────────────────────────
    def top20(key, min_score=35):
        return [
            {"sym": x["sym"], "score": x[key], "price": x["price"],
             "grade": x["grade"], "rsi": x["rsi"], "atr": x["atr"]}
            for x in sorted(scored, key=lambda x: x[key], reverse=True)
            if x[key] >= min_score
        ][:20]

    # NEU (01.07.2026): Strategie-Scores + Short-Felder (squeezeRisk, koShortLev)
    # aus dem scored-Pass zurück in results mergen, damit sie auch im
    # "tickers"-Output sichtbar sind (tickers=results, nicht tickers=scored).
    # Vorher: squeezeRisk/koShortLev == None in tickers weil Felder nur in
    # scored[] standen, das ausschliesslich für Leaderboards/masterShortlist
    # genutzt wurde.
    scored_by_sym = {x["sym"]: x for x in scored}
    for r in results:
        s = scored_by_sym.get(r.get("sym"))
        if not s:
            continue
        r["sMinervini"]    = s.get("sMinervini",    0)
        r["sSwing"]        = s.get("sSwing",         0)
        r["sMrLong"]       = s.get("sMrLong",        0)
        r["sBreakdown"]    = s.get("sBreakdown",     0)
        r["sFading"]       = s.get("sFading",        0)
        r["bestLong"]      = s.get("bestLong",       0)
        r["bestShort"]     = s.get("bestShort",      0)
        r["shortDir"]      = s.get("shortDir")
        r["squeezeRisk"]   = s.get("squeezeRisk")   # 0-100, >=70 = Fading-Gate zu
        r["koShortLev"]    = s.get("koShortLev")    # Empfohlener Hebel (3-8) oder None

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
            # Chart-Metriken fuer Alpha Desk (MACD, OBV, 52W, EMA, Bollinger)
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
            # Alle Strategie-Scores fuer Frontend-Kontext
            "sMinervini":    c.get("sMinervini"),
            "sSwing":        c.get("sSwing"),
            "sMrLong":       c.get("sMrLong"),
            "sBreakdown":    c.get("sBreakdown"),
            "sFading":       c.get("sFading"),
            # IOS Foundation
            "iosScore":      c.get("iosScore"),
            "iosRating":     c.get("iosRating"),
            "iosDecision":   c.get("iosDecision"),
            "iosDiagTrend":  c.get("iosDiagTrend"),
            "iosDiagEntry":  c.get("iosDiagEntry"),
            "iosDiagWarn":   c.get("iosDiagWarn"),
            "iosQuality":    c.get("iosQuality"),
            "iosEntry":      c.get("iosEntry"),
            "iosIsLeader":   c.get("iosIsLeader"),
            "iosSummary":    c.get("iosSummary"),
            # Fibonacci-Screening-Modul v1.0
            "f_setup":       c.get("f_setup"),
            "f_score":       c.get("f_score"),
            "f_next_name":   c.get("f_next_name"),
            "f_next_p":      c.get("f_next_p"),
            "f_dist_atr":    c.get("f_dist_atr"),
            "f_strike":      c.get("f_strike"),
            "f_lvls":        c.get("f_lvls"),
        }
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

def calc_fibonacci_levels(r: dict) -> dict:
    """
    Fibonacci-Screening-Modul v1.0 (Gemini-Blueprint, 30.06.2026).
    Berechnet Retracement/Extension-Level aus der 52-Wochen-Range (high52/low52),
    einen Confluence-Score (0-100) und klassifiziert handelbare Setups.

    Kompakte Keys (f_*) zur Schonung der KV-Storage-Größe.
    Performance: <0.2ms pro Ticker, nutzt ausschließlich bereits vorhandene Felder.

    Setup-Typen:
      CSP_ZONE   — Preis nahe 61.8%/78.6% Retracement + nicht im Bärenmarkt
                   → Cash-Secured-Put-Kandidat, Strike leicht unterhalb des Levels
      BREAKOUT   — Preis durchbricht 23.6%/38.2% mit erhöhtem Volumen
      EXTENSION  — Preis nahe 127.2%/161.8% Extension + überkauft (RSI>70)
                   → Covered-Call-Kandidat, Strike am Extension-Level
      NO_SETUP   — keine Confluence / zu weit entfernt
    """
    high  = r.get("high52", 0) or 0
    low   = r.get("low52", 0) or 0
    price = r.get("price", 0) or 0
    atr   = r.get("atr", 1.0) or 1.0
    ema50  = r.get("ema50")
    ema200 = r.get("ema200")
    rsi    = r.get("rsi", 50) or 50
    regime = (r.get("regime") or "").lower()
    vol_ratio = r.get("volRatio", 1.0) or 1.0

    if high == low or price == 0:
        return {"f_setup": "NO_SETUP", "f_score": 0}

    rng = high - low

    # ── 1. Levels berechnen (Retracements + Extensions) ──────────────────────
    fibo = {
        "r236":  high - rng * 0.236,
        "r382":  high - rng * 0.382,
        "r500":  high - rng * 0.500,
        "r618":  high - rng * 0.618,
        "r786":  high - rng * 0.786,
        "e1272": high + rng * 0.272,
        "e1618": high + rng * 0.618,
    }

    all_levels = [
        ("23.6%",  fibo["r236"]),  ("38.2%",  fibo["r382"]), ("50.0%", fibo["r500"]),
        ("61.8%",  fibo["r618"]),  ("78.6%",  fibo["r786"]),
        ("127.2%", fibo["e1272"]), ("161.8%", fibo["e1618"]),
    ]

    # ── 2. Nächstes Level identifizieren ──────────────────────────────────────
    next_lvl_name, next_lvl_p = min(all_levels, key=lambda x: abs(price - x[1]))
    dist_atr = abs(price - next_lvl_p) / atr if atr else 99

    # ── 3. Confluence-Score (0-100) ───────────────────────────────────────────
    # A) Distanz-Dämpfung (max 50 Pkt) — 0 ATR Abstand = 50 Pkt, ab 1.5 ATR = 0
    s_dist = max(0, 50 * (1 - (dist_atr / 1.5)))

    # B) MA-Confluence (max 25 Pkt) — Fibo-Level deckt sich mit EMA200/EMA50
    s_ma = 0
    if ema200 and abs(next_lvl_p - ema200) <= 1.0 * atr:
        s_ma = 25
    elif ema50 and abs(next_lvl_p - ema50) <= 1.0 * atr:
        s_ma = 15

    # C) Technischer Match-Bonus (max 25 Pkt)
    s_tech = 0
    is_retracement = next_lvl_name in ("23.6%", "38.2%", "50.0%", "61.8%", "78.6%")
    if is_retracement:
        if regime in ("bull", "side"): s_tech += 10
        if rsi < 35:                   s_tech += 15
    else:  # Extension (Widerstand)
        if regime == "bear":  s_tech += 10
        if rsi > 65:           s_tech += 15

    conf_score = int(min(100, s_dist + s_ma + s_tech))

    # ── 4. Setup-Klassifikation (nur wenn Abstand <= 0.75 ATR) ────────────────
    setup  = "NO_SETUP"
    strike = None

    if dist_atr <= 0.75:
        if next_lvl_name in ("61.8%", "78.6%") and price >= next_lvl_p and regime != "bear":
            setup  = "CSP_ZONE"
            strike = round(next_lvl_p - (0.2 * atr), 2)
        elif next_lvl_name in ("23.6%", "38.2%") and price > next_lvl_p and vol_ratio > 1.2:
            setup = "BREAKOUT"
        elif next_lvl_name in ("127.2%", "161.8%") and rsi > 70:
            setup  = "EXTENSION"
            strike = round(next_lvl_p, 2)

    return {
        "f_lvls":      {k: round(v, 2) for k, v in fibo.items()},
        "f_next_name": next_lvl_name,
        "f_next_p":    round(next_lvl_p, 2),
        "f_dist_atr":  round(dist_atr, 2),
        "f_score":     conf_score,
        "f_setup":     setup,
        "f_strike":    strike,
    }


def _calc_squeeze_risk_df(closes: list, volumes: list, hvp: int, rsi: float) -> int:
    """
    Squeeze-Risiko-Score (0-100) — Gemini-Blueprint v2 (01.07.2026).
    Verbesserte Version ggü. calc_squeeze_risk(r): nutzt direktionalen
    Volumen-Check (Spike an grünem Tag = potenzielle Short-Eindeckung),
    was das entscheidende Squeeze-Frühwarnsignal ist.

    Gate für score_short_fading(): Score >=70 sperrt Fading-Shorts.

    Kombinations-Logik:
    - Niedrige HVP + überverkaufter RSI + Volumen-Spike an grünem Tag
      = maximales Squeeze-Signal (85 Punkte, sofortiger Gate-Trigger)
    - Breiterer Score für Zwischenwerte (kein Alles-oder-Nichts)
    """
    if not closes or not volumes or len(closes) < 21:
        return 0

    score = 0

    # A) Niedrige implizite Volatilität — aufgestaute Spannung
    if hvp is not None:
        if hvp < 15:   score += 30
        elif hvp < 25: score += 15

    # B) RSI überverkauft — potenzielle Eindeckungs-Kandidaten warten
    if rsi is not None:
        if rsi < 25:   score += 25
        elif rsi < 35: score += 12

    # C) Direktionaler Volumen-Check (Gemini-Blueprint):
    # Volumen-Spike speziell an einem grünen Tag = Eindeckung beginnt
    try:
        last_close  = closes[-1]
        last_open   = closes[-2]        # Proxy: vorheriger Close als Open
        last_vol    = volumes[-1] if volumes[-1] else 0
        vol_mean_20 = sum(v for v in volumes[-21:-1] if v) / 20 if len(volumes) >= 21 else 0
        vol_spike   = vol_mean_20 > 0 and last_vol > vol_mean_20 * 1.5
        price_up    = last_close > last_open

        # Maximales Signal (Gemini): alle drei Bedingungen erfüllt
        if hvp is not None and hvp < 20 and rsi is not None and rsi < 30 and vol_spike and price_up:
            return 85   # Kritisches Squeeze-Risiko → Gate schließt sofort

        if vol_spike and price_up:
            score += 20
        elif vol_spike:
            score += 10
    except Exception:
        pass

    return max(0, min(100, score))


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

        result = {
            "sym":           ticker,
            "price":         price,
            "ema50":         round(ema50v, 4) if ema50v else None,
            "ema200":        round(ema200v, 4) if ema200v else None,
            "atr":           atrv,
            "rsi":           rsiv,
            "macdHist":      macd_hist,
            "macdLine":      round(macd_val, 4) if macd_val is not None else None,   # NEU: MACD-Linie
            "macdSignal":    round(macd_sig, 4) if macd_sig is not None else None,   # NEU: Signal-Linie
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
            "_bars_raw":     len(hist_df) if hist_df is not None else 0,
            "hvp":           calc_hv_percentile(closes),
            "hv10":          calc_hv_percentile(closes, window=10, lookback=90),
            "updated":       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            # NEU (01.07.2026): Squeeze-Risiko direkt in process_ticker berechnet,
            # wo hist_df verfügbar ist — Gemini-Blueprint: direktionaler Volumen-
            # Check (Spike an grünem Tag) ist präziser als nicht-direktionales
            # volRatio-Proxy aus dem früheren calc_squeeze_risk(r)-Ansatz.
            "squeezeRisk":   _calc_squeeze_risk_df(closes, volumes, hvp=calc_hv_percentile(closes), rsi=rsiv),
            # Sektor-Tags (automatisch aus SECTOR_WATCHLISTS invertiert — nie manuell editieren)
            "sectors":       TICKER_SECTOR_TAG.get(ticker, []),
        }

        # Fibonacci-Screening-Modul v1.0 (Gemini-Blueprint) — direkt anhängen
        result.update(calc_fibonacci_levels(result))

        return result
    except Exception as e:
        return {"sym": ticker, "error": str(e)}

# ── MARKT-DATEN LADEN ─────────────────────────────────────────────────────────

def fetch_batch(tickers, period="1y", max_workers=12):
    """Lädt OHLCV-Daten für alle Ticker parallel via yfinance."""
    log.info(f"Lade {len(tickers)} Ticker (parallel, {max_workers} Threads)...")
    results = {}

    # DEADLOCK-FIX: datetime Import AUSSERHALB fetch_one berechnen
    # from datetime inside nested function × 716 Threads = Python Import-Lock Deadlock!
    from datetime import datetime as _dt, timedelta as _td
    _end_s   = _dt.now().strftime("%Y-%m-%d")
    _start_s = (_dt.now() - _td(days=730)).strftime("%Y-%m-%d")

    def fetch_one(ticker):
        # start/end aus äusserem Scope (kein Import-Lock-Problem)
        start_s, end_s = _start_s, _end_s

        for attempt, kwargs in [
            ("2y_explicit", {"start": start_s, "end": end_s}),
            ("1y_fallback", {"period": "1y"}),
            ("6mo_fallback", {"period": "6mo"}),
        ]:
            try:
                df = yf.download(ticker, interval="1d",
                                 auto_adjust=True, progress=False, threads=False,
                                 **kwargs)
                if df is not None and len(df) >= 20:
                    if hasattr(df.columns, 'levels'):
                        df.columns = df.columns.get_level_values(0)
                    return ticker, df
            except Exception as e:
                log.warning(f"  {ticker} ({attempt}): {e}")
        return ticker, None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, t): t for t in tickers}
        done = 0
        for future in as_completed(futures):
            ticker, df = future.result()
            results[ticker] = df
            done += 1
            if done % 25 == 0:
                print(f"[PROGRESS] {done}/{len(tickers)} Ticker geladen...", flush=True)
                log.info(f"  {done}/{len(tickers)} geladen...")

    return results

# ── EXTERNE DATENQUELLEN ──────────────────────────────────────────────────────

def fetch_dix_gex() -> dict:
    """GEX via FlashAlpha API (lab.flashalpha.com).

    Free Tier:  5 Req/Tag, nur Individual Stocks (kein SPY/QQQ).
                → AAPL als Connectivity-Test + GEX-Signal.
    Basic Tier: SPY/QQQ + alle Exposure-Endpoints (nach Beta aktivieren).
    Fallback:   squeezemetrics (historisch, meist 403 von GitHub Actions).

    Endpoint (v1): GET /v1/exposure/gex/{ticker}?expiration=YYYY-MM-DD
    Auth:          X-Api-Key Header
    """
    import os
    from datetime import date, timedelta

    fa_key = os.environ.get("FLASHALPHA_API_KEY", "")
    if fa_key:
        try:
            today = date.today()
            days_to_friday = (4 - today.weekday()) % 7
            if days_to_friday == 0:
                days_to_friday = 7
            next_friday = today + timedelta(days=days_to_friday)
            expiry = next_friday.strftime("%Y-%m-%d")

            test_ticker = "AAPL"
            url = f"https://lab.flashalpha.com/v1/exposure/gex/{test_ticker}"
            r = requests.get(url, headers={"X-Api-Key": fa_key},
                             params={"expiration": expiry}, timeout=15)

            remaining = r.headers.get("X-RateLimit-Remaining", "?")
            limit     = r.headers.get("X-RateLimit-Limit", "?")
            log.info(f"  FlashAlpha API: HTTP {r.status_code} | "
                     f"Quota: {remaining}/{limit} | Expiry: {expiry}")

            if r.status_code == 200:
                data = r.json()
                net_gex    = data.get("net_gex") or data.get("total_gex") or data.get("gex")
                gamma_flip = data.get("gamma_flip")
                call_wall  = data.get("call_wall")
                put_wall   = data.get("put_wall")
                regime_raw = data.get("regime", "")
                gex_regime = "POSITIVE" if (net_gex or 0) >= 0 else "NEGATIVE"
                log.info(f"  FlashAlpha GEX {test_ticker}: net_gex={net_gex}, "
                         f"flip={gamma_flip}, call_wall={call_wall}, put_wall={put_wall}")
                return {
                    "gex":             round(float(net_gex) / 1e9, 4) if net_gex else None,
                    "gamma_flip":      gamma_flip,
                    "call_wall":       call_wall,
                    "put_wall":        put_wall,
                    "gex_regime":      gex_regime,
                    "regime_raw":      regime_raw,
                    "ticker":          test_ticker,
                    "expiry":          expiry,
                    "quota_remaining": remaining,
                    "dix":             None,
                    "date":            today.isoformat(),
                    "source":          "flashalpha_free",
                    "proxy":           False,
                }
            elif r.status_code == 402:
                log.warning(f"  FlashAlpha: 402 — {test_ticker} erfordert höheres Tier")
            elif r.status_code == 429:
                retry_after = r.headers.get('Retry-After', '?')
                log.warning(f"  FlashAlpha: 429 Rate Limit — Retry-After: {retry_after}s")
            else:
                log.warning(f"  FlashAlpha: HTTP {r.status_code} — {r.text[:120]}")
        except Exception as e:
            log.warning(f"  FlashAlpha GEX nicht verfügbar: {e}")


    # Fallback: squeezemetrics (oft 403 von GitHub Actions)
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
            log.info(f"  DIX (squeezemetrics): {dix_val:.1f}% | GEX: {gex_val/1e9:.2f} Mrd")
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
    """Echter Put/Call Ratio von CBOE (tägliche CSV).
    Fallback: interner VIX-basierter PCR-Proxy (kein externer Call nötig).
    CBOE blockiert GitHub Actions IPs (HTTP 403) — Proxy greift automatisch.
    """
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
        log.warning(f"  CBOE PCR HTTP {r.status_code} — nutze VIX-Proxy")
    except Exception as e:
        log.warning(f"  CBOE PCR nicht verfügbar: {e} — nutze VIX-Proxy")
    return None


def calc_pcr_proxy(vix_term: dict, mse_history: dict = None) -> dict:
    """Interner PCR-Proxy aus VIX-Termstruktur + VVIX (kein externer API-Call).

    Methodologie (bewährt, keine Halluzination):
    - VIX absolut:      >30 → Panik (PCR hoch), <15 → Gier (PCR niedrig)
    - VIX/VIX3M Ratio:  <0.85 = starkes Contango = wenig Put-Nachfrage (bullish)
                        >1.00 = Backwardation = hohe Put-Nachfrage (bearish)
    - VVIX (Vol of Vol): >100 = Put-Käufe nehmen zu → PCR-Aufschlag

    Ausgabe: dict mit pcr (0.5–1.4), signal, source='vix_proxy', proxy=True
    """
    vt     = vix_term or {}
    vix    = vt.get("vix",   20.0)
    vix3m  = vt.get("vix3m", 22.0)
    struct = vt.get("structure", "CONTANGO")

    # VVIX aus mse_history (letzter Wert)
    vvix = 90.0  # neutraler Default
    if mse_history:
        vvix_hist = mse_history.get("vvix") or []
        if vvix_hist:
            vvix = float(vvix_hist[-1]) if vvix_hist[-1] is not None else 90.0

    # ── Basis: VIX-Level (0.50 – 1.40) ────────────────────────────────────────
    if   vix >= 35:  pcr_base = 1.35
    elif vix >= 28:  pcr_base = 1.15
    elif vix >= 22:  pcr_base = 1.00
    elif vix >= 18:  pcr_base = 0.88
    elif vix >= 14:  pcr_base = 0.78
    else:            pcr_base = 0.68

    # ── Korrektur: VIX-Termstruktur ────────────────────────────────────────────
    ratio = vix / vix3m if vix3m > 0 else 1.0   # <1 = Contango (bullish)
    if   ratio < 0.82:  pcr_base -= 0.10   # starkes Contango → wenig Puts
    elif ratio < 0.90:  pcr_base -= 0.05   # normales Contango
    elif ratio > 1.00:  pcr_base += 0.12   # Backwardation → Put-Nachfrage hoch
    elif ratio > 0.95:  pcr_base += 0.05   # Übergang Contango→Backwardation

    # ── Korrektur: VVIX (Volatilität der Volatilität) ──────────────────────────
    if   vvix >= 120:  pcr_base += 0.12
    elif vvix >= 105:  pcr_base += 0.06
    elif vvix >= 95:   pcr_base += 0.02
    elif vvix <= 80:   pcr_base -= 0.05

    pcr = round(max(0.50, min(1.40, pcr_base)), 3)
    signal = "ÜBERKAUFT" if pcr < 0.7 else "ÜBERVERKAUFT" if pcr > 1.0 else "NEUTRAL"

    log.info(f"  PCR-Proxy (VIX={vix:.1f}, VIX3M={vix3m:.1f}, VVIX={vvix:.0f}, "
             f"Ratio={ratio:.3f}): PCR={pcr:.3f} → {signal}")
    return {
        "pcr":    pcr,
        "date":   "proxy",
        "signal": signal,
        "source": "vix_proxy",
        "proxy":  True,
        "components": {"vix": vix, "vix3m": vix3m, "vvix": round(vvix, 1),
                       "ratio": round(ratio, 3), "struct": struct},
    }


def fetch_fear_greed() -> dict:
    """
    CNN Fear & Greed Index (0-100).
    Fallback: eigener Proxy aus VIX + PCR + Momentum.
    """
    import urllib.request, json as _json
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer":    "https://www.cnn.com/markets/fear-and-greed",
            "Accept":     "application/json, text/plain, */*",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            data = _json.loads(r.read())
        fg = data.get("fear_and_greed", {})
        score = fg.get("score")
        if score is not None:
            score = round(float(score))
            rating = fg.get("rating", "")
            prev   = round(float(fg.get("previous_close", score)))
            log.info(f"  Fear & Greed: {score} ({rating}) | prev: {prev}")
            return {
                "score":    score,
                "rating":   rating,
                "previous": prev,
                "source":   "CNN",
                "proxy":    False,
            }
    except Exception as e:
        log.warning(f"  CNN Fear & Greed nicht verfügbar: {e}")
    return None


def calc_fg_proxy(vix_term: dict, pcr_data: dict, sector_rs: dict) -> dict:
    """
    Eigener Fear & Greed Proxy wenn CNN API nicht verfügbar.
    Berechnet aus: VIX, PCR, Marktbreite (sector_rs).
    Skala: 0-100 (0=extreme Fear, 100=extreme Greed).
    """
    score = 50  # Neutral

    # VIX-Komponente (30 Punkte)
    vix = (vix_term or {}).get("vix", 20)
    if   vix < 13: score += 20   # Extreme Greed
    elif vix < 16: score += 12   # Greed
    elif vix < 20: score += 5    # leicht bullisch
    elif vix > 30: score -= 20   # Fear
    elif vix > 25: score -= 12   # Erhöhte Angst
    elif vix > 20: score -= 5    # leicht bärisch

    # VIX Termstruktur (10 Punkte)
    struct = (vix_term or {}).get("structure", "")
    if struct == "CONTANGO":    score += 5   # Normal = Greed
    elif struct == "BACKWARDATION": score -= 10  # Stress = Fear

    # PCR (20 Punkte)
    pcr = (pcr_data or {}).get("pcr", 0.9)
    if   pcr < 0.7:  score += 15   # Wenig Puts = Greed
    elif pcr < 0.85: score += 7
    elif pcr > 1.1:  score -= 15   # Viele Puts = Fear
    elif pcr > 0.95: score -= 7

    # Marktbreite via Sektor-RS (10 Punkte)
    if sector_rs:
        positive = sum(1 for v in sector_rs.values() if v.get("rs5", 0) > 0)
        total    = max(1, len(sector_rs))
        breadth_pct = positive / total * 100
        if   breadth_pct > 65: score += 8
        elif breadth_pct > 50: score += 3
        elif breadth_pct < 35: score -= 8
        elif breadth_pct < 50: score -= 3

    score = max(0, min(100, score))

    if   score >= 80: rating = "Extreme Greed"
    elif score >= 60: rating = "Greed"
    elif score >= 45: rating = "Neutral"
    elif score >= 25: rating = "Fear"
    else:             rating = "Extreme Fear"

    return {"score": score, "rating": rating, "source": "UIQ Proxy", "proxy": True}

def fetch_market_snapshot() -> dict:
    """Einheitlicher Markt-Preisschnappschuss für Single Source of Truth.

    Holt via yf.download() (funktioniert von GitHub Actions):
    - US-Indizes:     SPY, QQQ, IWM
    - Rohstoffe:      GC=F (Gold), SI=F (Silber), CL=F (Öl WTI), BZ=F (Brent), PA=F (Palladium)
    - Krypto:         BTC-USD, ETH-USD
    - EU-Indizes:     ^GDAXI (DAX), ^STOXX50E (EuroStoxx50), ^FTSE (FTSE100)
    - Anleihen/USD:   ^TNX (10J Treasury Yield), DX-Y.NYB (USD Index)

    Output landet in master["market"]["snapshot"] — wird im MB-Prompt als
    einzige Kursquelle verwendet. Frontend liest aus KV, kein Live-Fetch nötig.
    """
    SYMBOLS = {
        # US Indizes
        "spy":      ("SPY",        "S&P 500 ETF",         "index_us"),
        "qqq":      ("QQQ",        "Nasdaq 100 ETF",       "index_us"),
        "iwm":      ("IWM",        "Russell 2000 ETF",     "index_us"),
        # EU Indizes
        "dax":      ("^GDAXI",     "DAX 40",               "index_eu"),
        "stoxx50":  ("^STOXX50E",  "EuroStoxx 50",         "index_eu"),
        "ftse":     ("^FTSE",      "FTSE 100",             "index_eu"),
        # Rohstoffe
        "gold":     ("GC=F",       "Gold ($/oz)",          "commodity"),
        "silver":   ("SI=F",       "Silber ($/oz)",        "commodity"),
        "oil_wti":  ("CL=F",       "Öl WTI ($/bbl)",       "commodity"),
        "oil_brent":("BZ=F",       "Öl Brent ($/bbl)",     "commodity"),
        "copper":   ("HG=F",       "Kupfer ($/lb)",        "commodity"),
        "palladium":("PA=F",       "Palladium ($/oz)",     "commodity"),
        # Krypto
        "btc":      ("BTC-USD",    "Bitcoin (USD)",        "crypto"),
        "eth":      ("ETH-USD",    "Ethereum (USD)",       "crypto"),
        # Anleihen & Währungen
        "tnx":      ("^TNX",       "US 10J Treasury (%)",  "bond"),
        "usd_idx":  ("DX-Y.NYB",   "USD Index (DXY)",      "fx"),
        "eur_usd":  ("EURUSD=X",   "EUR/USD",              "fx"),
    }

    syms_yf = [v[0] for v in SYMBOLS.values()]
    snapshot = {}
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        log.info(f"  Lade Market Snapshot ({len(syms_yf)} Symbole)…")
        df = yf.download(syms_yf, period="5d", interval="1d",
                         auto_adjust=True, progress=False, threads=True)

        close = df["Close"] if "Close" in df.columns else df.xs("Close", axis=1, level=0)

        def _last_valid(series):
            """Letzten NICHT-NaN Wert einer Spalte finden (rückwärts).
            Nötig weil Yahoo für Aktien/ETFs/Indizes vor US-Marktöffnung oft
            eine leere 'heute'-Zeile anhängt (NaN), während 24/7-Märkte
            (Rohstoffe/Krypto/FX) immer frische Werte haben. Ohne diesen Fix
            fallen alle Equity-Symbole aus, wenn der Aggregator früh läuft
            (z.B. planmäßiger Cron 03:37 UTC, 8h vor NYSE-Open)."""
            for i in range(len(series) - 1, -1, -1):
                v = series.iloc[i]
                if v == v:  # NaN-Check (NaN != NaN)
                    return float(v), i
            return None, None

        ok_count = 0
        for key, (yf_sym, label, category) in SYMBOLS.items():
            try:
                if yf_sym not in close.columns:
                    raise KeyError(yf_sym)
                col = close[yf_sym]
                price, idx = _last_valid(col)
                if price is None or idx == 0:
                    raise ValueError("kein gültiger Wert oder keine Vorperiode")
                price_prev, _ = _last_valid(col.iloc[:idx])
                chg_pct = round((price / price_prev - 1) * 100, 2) if price_prev else None
                snapshot[key] = {
                    "sym":      yf_sym,
                    "label":    label,
                    "category": category,
                    "price":    round(price, 4),
                    "chg_pct":  chg_pct,
                    "ok":       True,
                }
                ok_count += 1
            except Exception:
                snapshot[key] = {"sym": yf_sym, "label": label,
                                  "category": category, "ok": False}

        log.info(f"  Market Snapshot: {ok_count}/{len(SYMBOLS)} Symbole geladen")

    except Exception as e:
        log.warning(f"  Market Snapshot Fehler: {e}")

    return {
        "data":         snapshot,
        "generated_at": generated_at,
        "ok_count":     sum(1 for v in snapshot.values() if v.get("ok")),
        "total":        len(SYMBOLS),
        "source":       "yfinance",
    }


def calc_macro_zscores(mse_history: dict, pcr: dict = None, vix_term: dict = None) -> dict:
    """Z-Scores + Perzentile für Makro-Parameter aus der MSE-History.

    Abstraktions-Schicht für Deep-Reasoning (Gemini-Empfehlung 09.07.2026):
    KI bekommt nicht "SKEW: 150" sondern "SKEW: 150 (Z=+1.6, 91. Perzentil, 252T)".
    Erst der historische Kontext macht aus einer Zahl eine Aussage.

    Berechnung: Z-Score = (aktuell - Mittelwert) / Stdabw über volle History.
    Perzentil: Midpoint-Methode ((below + equal/2) / n).
    """
    import statistics

    def _zscore(series):
        vals = [v for v in series if v is not None]
        if len(vals) < 20:
            return None
        cur = vals[-1]
        mean = statistics.mean(vals)
        stdev = statistics.stdev(vals)
        return round((cur - mean) / stdev, 2) if stdev > 0 else 0.0

    def _percentile(series):
        raw = [v for v in series if v is not None]
        if len(raw) < 20:
            return None
        cur = raw[-1]
        vals = sorted(raw)
        below = sum(1 for v in vals if v < cur)
        equal = sum(1 for v in vals if v == cur)
        return round((below + equal / 2) / len(vals) * 100)

    def _entry(series, label):
        vals = [v for v in series if v is not None]
        if len(vals) < 20:
            return {"label": label, "ok": False, "reason": f"nur {len(vals)} Werte"}
        return {
            "label":      label,
            "current":    vals[-1],
            "zscore":     _zscore(series),
            "percentile": _percentile(series),
            "min":        round(min(vals), 2),
            "max":        round(max(vals), 2),
            "mean":       round(statistics.mean(vals), 2),
            "n_days":     len(vals),
            "ok":         True,
        }

    result = {}
    hist = mse_history or {}

    result["vvix"]     = _entry(hist.get("vvix", []),     "VVIX (Vol of Vol)")
    result["skew"]     = _entry(hist.get("skew", []),     "CBOE SKEW (Tail-Risk)")
    result["vix"]      = _entry(hist.get("vix", []),      "VIX Spot")
    result["vixRatio"] = _entry(hist.get("vixRatio", []), "VIX3M/VIX Ratio (Contango)")

    # Divergenz-Detektor: SKEW hoch + VVIX niedrig = verstecktes Tail-Risk
    skew_z = result["skew"].get("zscore")
    vvix_z = result["vvix"].get("zscore")
    if skew_z is not None and vvix_z is not None:
        divergence = skew_z - vvix_z
        result["skew_vvix_divergence"] = {
            "label":  "SKEW/VVIX Divergenz (Tail-Hedging bei ruhiger Oberfläche)",
            "value":  round(divergence, 2),
            "signal": ("WARNUNG: Institutionelle kaufen Tail-Absicherung bei ruhiger Oberfläche"
                       if divergence > 1.5 else
                       "erhöht" if divergence > 0.8 else "normal"),
            "ok":     True,
        }

    n_days = result.get("vix", {}).get("n_days", 0)
    log.info(f"  Makro Z-Scores ({n_days}T): "
             f"VIX Z={result['vix'].get('zscore')} P{result['vix'].get('percentile')} | "
             f"SKEW Z={result['skew'].get('zscore')} P{result['skew'].get('percentile')} | "
             f"VVIX Z={result['vvix'].get('zscore')} P{result['vvix'].get('percentile')}")

    return result


def fetch_fred_macro() -> dict:
    """Makro-Parameter via FRED-API (kostenlos, Regierungsquelle, kein IP-Blocking).

    Serien (Gemini-Empfehlung 09.07.2026, verifiziert):
    - BAMLH0A0HYM2:  ICE BofA US High Yield Spread (%) — Kreditrisiko-Frühwarner
    - WALCL:         Fed Balance Sheet (Mio USD, wöchentlich)
    - WTREGEN:       Treasury General Account (Mio USD, wöchentlich)
    - RRPONTSYD:     Overnight Reverse Repo (Mrd USD, täglich)
    → Net Liquidity = WALCL/1000 - (WTREGEN + RRPONTSYD)  [Mrd USD]

    MOVE Index: nicht auf FRED → via yfinance ^MOVE (separater Versuch).

    Z-Scores werden über die letzten 252 Beobachtungen berechnet.
    """
    import os, statistics

    fred_key = os.environ.get("FRED_API_KEY", "")
    result = {"ok": False, "source": "fred"}

    def _fred_series(series_id, limit=300):
        """Letzte `limit` Beobachtungen einer FRED-Serie, älteste zuerst."""
        url = (f"https://api.stlouisfed.org/fred/series/observations"
               f"?series_id={series_id}&api_key={fred_key}&file_type=json"
               f"&sort_order=desc&limit={limit}")
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"FRED {series_id}: HTTP {r.status_code}")
        obs = r.json().get("observations", [])
        vals = []
        for o in reversed(obs):   # älteste zuerst
            try:
                v = float(o["value"])
                vals.append((o["date"], v))
            except (ValueError, KeyError):
                continue          # "." = fehlender Wert bei FRED
        return vals

    def _z_and_p(vals):
        """Z-Score + Perzentil des letzten Werts über die Serie."""
        if len(vals) < 20:
            return None, None
        nums = [v for _, v in vals]
        cur = nums[-1]
        mean = statistics.mean(nums)
        stdev = statistics.stdev(nums)
        z = round((cur - mean) / stdev, 2) if stdev > 0 else 0.0
        s = sorted(nums)
        below = sum(1 for v in s if v < cur)
        equal = sum(1 for v in s if v == cur)
        p = round((below + equal / 2) / len(s) * 100)
        return z, p

    if not fred_key:
        result["reason"] = "FRED_API_KEY nicht gesetzt"
        log.warning("  FRED: kein API-Key — Makro-Parameter übersprungen")
        return result

    # ── 1. High Yield Credit Spread ──────────────────────────────────────────
    try:
        hy = _fred_series("BAMLH0A0HYM2", limit=300)
        if hy:
            z, p = _z_and_p(hy)
            result["hy_spread"] = {
                "label":      "ICE BofA US High Yield Spread (%)",
                "current":    hy[-1][1],
                "date":       hy[-1][0],
                "zscore":     z,
                "percentile": p,
                "n_obs":      len(hy),
                "signal":     ("STRESS" if hy[-1][1] > 5.0 else
                               "erhöht" if hy[-1][1] > 4.0 else "normal"),
                "ok":         True,
            }
            log.info(f"  FRED HY-Spread: {hy[-1][1]:.2f}% (Z={z}, P{p}) — {result['hy_spread']['signal']}")
    except Exception as e:
        result["hy_spread"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED HY-Spread Fehler: {e}")

    # ── 2. Net Liquidity = Fed Balance - (TGA + RRP) ─────────────────────────
    try:
        walcl = _fred_series("WALCL", limit=120)      # Mio USD, wöchentlich
        tga   = _fred_series("WTREGEN", limit=120)    # Mio USD, wöchentlich
        rrp   = _fred_series("RRPONTSYD", limit=300)  # Mrd USD, täglich

        if walcl and tga and rrp:
            fed_bs   = walcl[-1][1] / 1000.0   # Mio → Mrd
            tga_v    = tga[-1][1] / 1000.0     # Mio → Mrd
            rrp_v    = rrp[-1][1]
            net_liq  = round(fed_bs - tga_v - rrp_v, 1)

            # Historische Netto-Liquidität für Trend (wöchentliche Punkte)
            hist_nl = []
            rrp_by_date = dict(rrp)
            tga_by_date = dict(tga)
            for date_w, walcl_v in walcl:
                t = tga_by_date.get(date_w)
                # RRP: nächstliegender Tageswert
                r_v = rrp_by_date.get(date_w)
                if t is not None and r_v is not None:
                    hist_nl.append((date_w, round(walcl_v / 1000.0 - t / 1000.0 - r_v, 1)))

            nl_trend = None
            if len(hist_nl) >= 5:
                nl_4w_ago = hist_nl[-5][1]
                nl_trend = round(net_liq - nl_4w_ago, 1)

            result["net_liquidity"] = {
                "label":       "US Net Liquidity (Fed BS - TGA - RRP, Mrd USD)",
                "current":     net_liq,
                "fed_bs":      round(fed_bs, 1),
                "tga":         tga_v,
                "rrp":         rrp_v,
                "trend_4w":    nl_trend,
                "date":        walcl[-1][0],
                "signal":      ("EXPANDIEREND" if nl_trend and nl_trend > 50 else
                                "SCHRUMPFEND" if nl_trend and nl_trend < -50 else "STABIL"),
                "ok":          True,
            }
            log.info(f"  FRED Net Liquidity: {net_liq:.0f} Mrd (4W-Trend: {nl_trend}) — {result['net_liquidity']['signal']}")
    except Exception as e:
        result["net_liquidity"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED Net Liquidity Fehler: {e}")

    # ── 3. Echte Zinskurve: 10J-2J + 10J-3M (Rezessions-Frühwarner) ──────────
    # Ersetzt fragile Client-Proxy-Kette (^IRX/^FVX via Yahoo, falsch als "2Y"
    # gelabelt — ^FVX ist tatsächlich 5J, ^IRX ist 3M). FRED liefert echte
    # Konstant-Laufzeit-Renditen (Constant Maturity), keine Proxy nötig.
    try:
        dgs2   = _fred_series("DGS2",   limit=300)   # 2J Treasury Constant Maturity (%)
        dgs10  = _fred_series("DGS10",  limit=300)   # 10J Treasury Constant Maturity (%)
        dgs3mo = _fred_series("DGS3MO", limit=300)   # 3M Treasury Constant Maturity (%)

        if dgs2 and dgs10:
            y10 = dgs10[-1][1]
            y2  = dgs2[-1][1]
            spread_10y2y = round(y10 - y2, 3)

            # Historische Spread-Serie für Z-Score (Datum-Match zwischen beiden Serien)
            dgs2_by_date = dict(dgs2)
            hist_spread = [(d, round(v10 - dgs2_by_date[d], 3))
                           for d, v10 in dgs10 if d in dgs2_by_date]

            z_curve, p_curve = _z_and_p(hist_spread) if len(hist_spread) >= 20 else (None, None)

            curve_entry = {
                "label":        "US Zinskurve 10J-2J (%, FRED Constant Maturity)",
                "y10":          y10,
                "y2":           y2,
                "spread_10y2y": spread_10y2y,
                "zscore":       z_curve,
                "percentile":   p_curve,
                "date":         dgs10[-1][0],
                "inverted":     spread_10y2y < 0,
                "signal":       ("INVERTIERT — Rezessionswarnung" if spread_10y2y < 0 else
                                 "flach (<0.25%)" if spread_10y2y < 0.25 else "normal"),
                "source":       "fred",
                "ok":           True,
            }

            # Zusätzlich: 10J-3M (NY-Fed-Variante, eigenständig legitim, oft robuster)
            if dgs3mo:
                y3mo = dgs3mo[-1][1]
                spread_10y3m = round(y10 - y3mo, 3)
                curve_entry["y3mo"] = y3mo
                curve_entry["spread_10y3m"] = spread_10y3m
                curve_entry["inverted_10y3m"] = spread_10y3m < 0

            result["yield_curve"] = curve_entry
            log.info(f"  FRED Zinskurve: 10J={y10:.2f}% 2J={y2:.2f}% → Spread {spread_10y2y:+.2f}% "
                     f"(Z={z_curve}) — {curve_entry['signal']}")
        else:
            result["yield_curve"] = {"ok": False, "reason": "DGS2/DGS10 nicht verfügbar"}
    except Exception as e:
        result["yield_curve"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED Zinskurve Fehler: {e}")

    result["ok"] = any(v.get("ok") for k, v in result.items() if isinstance(v, dict))
    return result


def fetch_move_index() -> dict:
    """MOVE Index (Treasury-Volatilität, Renten-VIX) via yfinance ^MOVE.
    Z-Score über 252 Handelstage."""
    import statistics
    try:
        raw = yf.download("^MOVE", period="15mo", interval="1d",
                          auto_adjust=True, progress=False)
        close = raw["Close"].dropna()
        if hasattr(close, 'squeeze'):
            close = close.squeeze()
        vals = [float(v) for v in close.values[-252:]]
        if len(vals) < 20:
            return {"ok": False, "reason": f"nur {len(vals)} Werte"}
        cur = vals[-1]
        mean = statistics.mean(vals)
        stdev = statistics.stdev(vals)
        z = round((cur - mean) / stdev, 2) if stdev > 0 else 0.0
        s = sorted(vals)
        below = sum(1 for v in s if v < cur)
        equal = sum(1 for v in s if v == cur)
        p = round((below + equal / 2) / len(s) * 100)
        signal = ("STRESS" if cur > 130 else "erhöht" if cur > 110 else "ruhig")
        log.info(f"  MOVE Index: {cur:.1f} (Z={z}, P{p}) — {signal}")
        return {
            "label":      "MOVE Index (Treasury-Volatilität)",
            "current":    round(cur, 1),
            "zscore":     z,
            "percentile": p,
            "n_days":     len(vals),
            "signal":     signal,
            "ok":         True,
        }
    except Exception as e:
        log.warning(f"  MOVE Index nicht verfügbar: {e}")
        return {"ok": False, "reason": str(e)[:100]}


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


def push_to_cloudflare_kv(data, key="master_market_data", retries=1):
    """Pusht JSON-Daten in Cloudflare KV. Mit einem Retry bei transienten Fehlern
    (Fix 30.06.2026: der separate "options_watchlist"-Key schlug gelegentlich
    schweigend fehl, obwohl der Hauptlauf erfolgreich war — Frontend liest seitdem
    primär aus dem eingebetteten master_market_data.optionsWatchlist, dieser Retry
    erhöht zusätzlich die Robustheit des separaten Legacy-Keys)."""
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
    log.info(f"  Upload zu Cloudflare KV ({len(payload)/1024:.1f} KB)... key={key}")

    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            r = requests.put(url, headers=headers, data=payload.encode("utf-8"), timeout=30)
            if r.status_code in (200, 201):
                log.info(f"  ✅ KV-Upload erfolgreich! (key={key}, Versuch {attempt})")
                return True
            else:
                log.error(f"  ❌ KV-Upload fehlgeschlagen (key={key}, Versuch {attempt}): {r.status_code} — {r.text[:200]}")
        except Exception as e:
            log.error(f"  ❌ KV-Upload Exception (key={key}, Versuch {attempt}): {e}")
        if attempt <= retries:
            time.sleep(2)
    return False

# ── HAUPTPROGRAMM ─────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    import time as _time
    _t0 = _time.time()
    def _t(label):
        elapsed = round(_time.time() - _t0, 1)
        print(f"[T+{elapsed}s] {label}", flush=True)
    _t(f"START — UnderlyingIQ Market Aggregator v{AGGREGATOR_VERSION}")
    log.info("=" * 60)
    log.info(f"UnderlyingIQ Market Aggregator v{AGGREGATOR_VERSION}")
    log.info(f"Start: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 60)

    # ── CODE-VERIFIKATION (Gemini-Empfehlung) ────────────────────────────────
    _src = open(__file__).read()
    _zl = _src.count(chr(10))
    _2y = '["2y", period' in _src
    _ema = 'c.get("ema50")' in _src
    _guard = 'available = len(closes)' in _src
    log.info(f"[VERIFY] Zeilen={_zl} | 2y_first={_2y} | ema50_in_shortlist={_ema} | adaptive_guard={_guard}")
    # ── ENDE VERIFIKATION ─────────────────────────────────────────────────────

    # 1. Ticker-Universum aufbauen
    tickers = build_ticker_universe()
    _t(f"Ticker-Universum: {len(tickers)} Titel")
    log.info(f"\n📋 Ticker-Universum: {len(tickers)} Titel")

    # NEU (30.06.2026): bekannte Universe-Liste separat in KV pushen — der ko-ai
    # Worker gleicht Extra-Ticker-Vorschläge (Fibo-Tab) dagegen ab, um Doppel-
    # Einreichungen für bereits vorhandene Ticker gar nicht erst in die Pending-
    # Review-Liste zu lassen (sonst unnötiger Admin-Aufwand für längst vorhandene
    # Ticker wie z.B. AAPL).
    push_to_cloudflare_kv(tickers, key="known_universe_tickers")

    # Krypto separat
    stock_tickers  = [t for t in tickers if not t.endswith("-USD")]
    crypto_tickers = [t for t in tickers if t.endswith("-USD")]
    log.info(f"   Aktien/ETFs: {len(stock_tickers)} | Krypto: {len(crypto_tickers)}")

    # 2. Marktdaten laden
    _t("VOR fetch_batch — Downloads starten jetzt")
    log.info(f"\n📥 Lade Marktdaten...")
    hist_data = fetch_batch(stock_tickers, period="1y", max_workers=12)  # OOM-Fix

    # Krypto mit 6 Monaten
    if crypto_tickers:
        log.info(f"   Lade Krypto-Daten ({len(crypto_tickers)} Ticker)...")
        crypto_data = fetch_batch(crypto_tickers, period="6mo", max_workers=5)  # OOM-Fix
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

    _t(f"NACH fetch_batch — {len(results)} OK / {len(errors)} Fehler")
    log.info(f"   ✅ Erfolgreich: {len(results)} | ❌ Fehler: {len(errors)}")
    # Bars-Statistik (Gemini-Diagnose)
    _bars_all = [r.get("bars", 0) for r in results if r.get("bars")]
    if _bars_all:
        import numpy as _np
        log.info(f"   [DIAGNOSE] Ø-Bars: {_np.mean(_bars_all):.0f} | max: {max(_bars_all)} | >300: {sum(1 for b in _bars_all if b>300)}/{len(_bars_all)}")

    # 4. Externe Datenquellen
    log.info(f"\n🌐 Externe Datenquellen...")
    _t("Externe APIs: DIX/GEX, PCR, VIX, Fear&Greed, CAPE")
    dix_gex  = fetch_dix_gex() or {}   # Fallback auf leeres Dict wenn API nicht verfügbar
    pcr      = fetch_pcr_cboe() or {}   # CBOE-Versuch; Proxy-Fallback nach mse_history (s.u.)
    vix_term    = fetch_vix_term()
    # ── Market Snapshot: Single Source of Truth für alle Live-Preise ──────────
    log.info(f"  Market Snapshot (SPY/QQQ/Gold/Öl/Krypto/EU-Indizes)…")
    market_snapshot = fetch_market_snapshot()
    # Fear & Greed
    log.info(f"  Fear & Greed Index...")
    fear_greed  = fetch_fear_greed()
    # v4.3: Shiller CAPE gestrichen (80/20-Entscheidung 02.07.2026) — alle drei
    # Quellen defekt (FRED-Serie "CAPE" existiert nicht, multpl-Scrape fragil,
    # SPY-P/E-Fallback leer) UND kein kausaler Einfluss auf 2-30-Tage-Setups.
    # F&G Proxy-Fallback: v4.2 nach Schritt 5b verschoben — sector_rs existiert
    # hier noch nicht (latenter NameError-Crash bei CNN-API-Ausfall behoben).
    # IOS Market Score (Club-Integration)
    log.info(f"\n🏛️  IOS Market Score berechnen (Breadth/Rotation/Risk)...")
    ios_market = calc_ios_market_score(hist_data, vix_term)
    log.info(f"  Lade MSE History (VVIX/SKEW/VIX 252T für Z-Score-Kontext)...")
    mse_history = fetch_mse_history(days=252)

    # PCR-Proxy-Fallback: CBOE lieferte nichts (403) → intern aus VIX + VVIX ableiten
    if not pcr:
        log.info(f"  PCR-Proxy: berechne aus VIX-Termstruktur + VVIX (kein externer Call)...")
        pcr = calc_pcr_proxy(vix_term, mse_history) or {}

    # ── Makro Z-Scores: Abstraktions-Schicht für Deep-Reasoning ──────────────
    log.info(f"  Berechne Makro Z-Scores + Perzentile (252T-Kontext)...")
    macro_zscores = calc_macro_zscores(mse_history, pcr, vix_term)

    # ── FRED Makro (HY-Spread, Net Liquidity) + MOVE Index ───────────────────
    log.info(f"  FRED Makro-Parameter (HY-Spread, Net Liquidity)...")
    fred_macro = fetch_fred_macro()
    log.info(f"  MOVE Index (Treasury-Vol)...")
    move_index = fetch_move_index()

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

        # ── DIAGNOSE-LOG (erste 5 Ticker) ────────────────────────────────
        if len(options_candidates) < 3 or sym in ("DDOG","BAH","AAPL","MSFT","NVO"):
            log.info(f"  [OPT-DIAG] {sym}: price={price:.1f} "
                     f"ema200={r.get('ema200')} hvp={r.get('hvp')} "
                     f"rsi={r.get('rsi')} bbPos={r.get('bbPos')} "
                     f"regime={r.get('regime')} "
                     f"→ CSP={s_csp} CC={s_cc} Spr={s_spread}")
        # ── ENDE DIAGNOSE ─────────────────────────────────────────────────

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
            # NEU (30.06.2026): Fibo-Setup/Score mit ausgeben — macht den in
            # score_options_csp()/score_options_covered_call() eingerechneten
            # Fibo-Boost im Output nachvollziehbar (vorher nur intern verwendet,
            # nicht sichtbar -> Boost-Wirkung liess sich nicht isoliert pruefen).
            "fSetup":      r.get("f_setup"),
            "fScore":      r.get("f_score"),
            # Bester Score fuer Sortierung
            "optsScore":   max(s_csp, s_cc, s_spread),
        })

    # Sortierung: bester Strategie-Score zuerst, Top-50
    # Macro Risk Overlay anwenden (GEX/PCR-Skalierung) — Gemini-Blueprint
    options_candidates = apply_macro_risk_overlay(options_candidates, dix_gex, pcr)
    # IOS Market Score Overlay (Club-Integration)
    options_candidates = apply_ios_market_overlay(options_candidates, ios_market)

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

    # F&G Proxy wenn CNN nicht verfügbar (v4.2: hierher verschoben — am alten
    # Aufrufort in Schritt 4 war sector_rs noch nicht definiert → NameError
    # bei CNN-API-Ausfall. Jetzt fließt die Marktbreite korrekt in den Proxy ein.)
    if not fear_greed:
        fear_greed = calc_fg_proxy(vix_term, pcr, sector_rs)
        log.info(f"  Fear & Greed Proxy: {fear_greed.get('score')} ({fear_greed.get('rating')})")

    # Markt-Regime aus VIX-Term-Structure ableiten (fuer Leaderboard-Filter)
    market_regime_str = 'NEUTRAL'
    # Primärquelle: VIX Term Structure — KONVENTION: VIX3M/VIX (>1 = Contango/gesund)
    # v4.3 KRITISCHER FIX (02.07.2026): vix_term['ratio'] ist VIX/VIX3M (<1 = gesund),
    # die Schwellen unten (<0.98 STRESS, <1.05 POST_PANIC, sonst BULL) wurden aber
    # für die INVERSE Konvention VIX3M/VIX geschrieben (wie mseHistory.vixRatio).
    # Folge: ruhiger Contango-Markt wurde als STRESS_UNSTABLE geroutet und umgekehrt
    # — Master-Shortlist lief im Bärenmodus bei gesunder Marktlage (Lauf v4.2:
    # VIX 16.15 / VIX3M 19.04 / CONTANGO → fälschlich STRESS_UNSTABLE, 13× MR-Long
    # + 7 Shorts). Fix: Ratio aus vix/vix3m-Rohwerten in VIX3M/VIX-Konvention bilden.
    _regime_ratio = None
    if vix_term and vix_term.get('vix') and vix_term.get('vix3m'):
        _regime_ratio = round(vix_term['vix3m'] / vix_term['vix'], 3)
    elif mse_history and mse_history.get('vixRatio') and mse_history['vixRatio']:
        _regime_ratio = mse_history['vixRatio'][-1]   # bereits VIX3M/VIX

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
            "version":      AGGREGATOR_VERSION,
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
            "mseHistory": mse_history,
            "iosMarket":  ios_market,
            "fearGreed":  fear_greed,
            "snapshot":   market_snapshot,   # Single Source of Truth: alle Live-Preise
            "zscores":    macro_zscores,     # Z-Scores + Perzentile (252T) für Deep-Reasoning
            "fredMacro":  fred_macro,        # HY-Spread + Net Liquidity (FRED)
            "moveIndex":  move_index,        # Treasury-Volatilität (Renten-VIX)
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

    # ── DIAGNOSE-LOG (temporär) ──────────────────────────────────────────────
    _ms_raw = strategy_data.get("masterShortlist", [])
    if _ms_raw:
        _s0 = _ms_raw[0]
        log.info(f"  [DIAG] masterShortlist[0] Felder: {len(_s0.keys())} — {list(_s0.keys())[:8]}")
        log.info(f"  [DIAG] ema50={_s0.get('ema50')} hvp={_s0.get('hvp')} sMinervini={_s0.get('sMinervini')}")
    _sample_hvp = [(r.get('sym'), r.get('hvp'), r.get('bars')) for r in results[:5]]
    log.info(f"  [DIAG] results[0:5] hvp+bars: {_sample_hvp}")
    _sample_ema = [(r.get('sym'), r.get('ema50')) for r in results[:3]]
    log.info(f"  [DIAG] results[0:3] ema50: {_sample_ema}")
    # ── ENDE DIAGNOSE ────────────────────────────────────────────────────────
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

    # ── FUNDAMENTAL ENRICHMENT (Option A, 01.07.2026) ────────────────────────
    # Bewertungskennzahlen für Top-Kandidaten via yfinance .info.
    # Nur für masterShortlist + optionsWatchlist (max ~50 Titel, ~1s/Ticker).
    # Felder: peTrailing, peForward, peg, pb, roe, revenueGrowth, earningsGrowth,
    #         analystTarget, analystUpside (Fair-Value-Proxy), fcfYield, evEbitda.
    # ETFs und Krypto werden übersprungen (keine sinnvollen KGV-Werte).
    _ETF_CRYPTOSUFFIXES = ("-USD", "SPY", "QQQ", "GLD", "SLV", "USO", "UNG",
                           "XL", "XBI", "IBB", "IAU", "VIX", "TLT", "HYG",
                           "SH", "SQQQ", "EWH", "EWG", "EWJ")
    _fund_candidates = list({c["sym"] for c in master_shortlist + options_watchlist
                             if not any(c["sym"].startswith(pfx) or c["sym"].endswith(pfx)
                                        for pfx in _ETF_CRYPTOSUFFIXES)})[:50]
    if _fund_candidates:
        log.info(f"\n📊 Fundamental-Enrichment: {len(_fund_candidates)} Kandidaten...")
        _fund_cache = {}
        for _fsym in _fund_candidates:
            _fprice = next((r.get("price") for r in results if r.get("sym") == _fsym), None)
            _fdata  = enrich_with_fundamentals(_fsym, _fprice)
            if _fdata:
                _fund_cache[_fsym] = _fdata
                log.info(f"  {_fsym}: Upside={_fdata.get('analystUpside')}% "
                         f"FCF-Yield={_fdata.get('fcfYield')}% "
                         f"D/E={_fdata.get('debtToEquity')}")
        # Felder in masterShortlist einhängen
        for c in master_shortlist:
            if c.get("sym") in _fund_cache:
                c.update(_fund_cache[c["sym"]])
        # Felder in optionsWatchlist einhängen
        for c in options_watchlist:
            if c.get("sym") in _fund_cache:
                c.update(_fund_cache[c["sym"]])
        # Felder auch in results[] für tickers-Output
        _fund_by_sym = {c["sym"]: _fund_cache[c["sym"]] for c in master_shortlist if c.get("sym") in _fund_cache}
        for r in results:
            if r.get("sym") in _fund_by_sym:
                r.update(_fund_by_sym[r["sym"]])
        log.info(f"  ✅ Fundamental-Enrichment: {len(_fund_cache)}/{len(_fund_candidates)} erfolgreich")
    else:
        log.info("  Fundamental-Enrichment: keine Kandidaten (alle ETF/Krypto)")

    # Leaderboards + Shortlist in master dict einfuegen
    master["leaderboards"]     = leaderboards_obj
    master["masterShortlist"]  = master_shortlist
    master["optionsWatchlist"] = options_watchlist   # Top-50 Options-Kandidaten (täglich)
    master["strategyMeta"]     = {
        "regimeUsed":  strategy_data["regimeUsed"],
        "timestamp":   strategy_data["timestamp"],
        "enriched":    bool(_ant_key),
    }

    # ── TRACK-RECORD-LAYER Phase A (v4.4, Spez: docs/TRACK_RECORD_SPEC.md) ──
    # Snapshot der heutigen Empfehlungen nach tr:snap:<Handelstag> + tr:index.
    # Fehlerisoliert: Ein Fehler hier darf den Hauptlauf NIEMALS brechen (§4).
    # Schreibstatus landet in master["trackRecord"] — Verifikation im Output.
    try:
        import tr_layer
        master["trackRecord"] = tr_layer.run_snapshot(
            shortlist=master_shortlist,
            leaderboards=leaderboards_obj,
            tickers=results,
            regime=market_regime_str,
            tday=master["meta"].get("last_trading_day"),
            agg_version=AGGREGATOR_VERSION,
        )
        # Phase B (v4.5): fällige Horizonte bewerten + tr:stats aggregieren.
        # Nutzt das bereits geladene hist_data — keine zusätzlichen Downloads.
        try:
            master["trackRecord"]["evaluation"] = tr_layer.run_evaluation(hist_data=hist_data)
        except Exception as _tre2:
            log.warning(f"  [TR] Evaluator übersprungen (nicht kritisch): {_tre2}")
            master["trackRecord"]["evaluation"] = {"evaluated": 0, "reason": f"exception: {_tre2}"}
    except Exception as _tre:
        log.warning(f"  [TR] Track-Record-Layer übersprungen (nicht kritisch): {_tre}")
        master["trackRecord"] = {"written": False, "reason": f"exception: {_tre}"}

    # ── FIN-ARCHIV (v4.6, Value-Modul Phase 0 — Konzept: docs/VALUE_MOD_KONZEPT.md) ──
    # Point-in-Time-Fundamentaldaten: Mo–Fr Tages-Shard (Russell3000∪SmartPicks∪UIQ)
    # → KV; Sa Wochen-Merge → data/fundamentals/<YYYY-WW>.json.gz (Workflow-Commit).
    # Fehlerisoliert wie tr_layer — bricht den Hauptlauf niemals.
    try:
        import fin_layer
        master["finArchive"] = fin_layer.run(uiq_universe=tickers)
    except Exception as _fe:
        log.warning(f"  [FIN] FIN-Archiv übersprungen (nicht kritisch): {_fe}")
        master["finArchive"] = {"ok": False, "reason": f"exception: {_fe}"}

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
    try:
        main()
    except KeyboardInterrupt:
        print("[ABORT] KeyboardInterrupt", flush=True)
    except MemoryError:
        print("[ABORT] MemoryError — OOM Kill", flush=True)
        raise
    except Exception as _e:
        print(f"[ABORT] Unbehandelte Exception: {type(_e).__name__}: {_e}", flush=True)
        import traceback; traceback.print_exc()
        raise
