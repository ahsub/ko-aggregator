"""
ticker_master.py — TICKER_MASTER: einzige Quelle der Wahrheit (SSOT) fuer das
statische Ticker-Universum, die Sektor-Watchlists und die Referenzlisten von
market_aggregator.py.
====================================================================
Version: 1.0 (24.09.2026, Claude + Axel + Reviewer, TICKER_MASTER-Migration
Phase C, Schritte 1-6). Erzeugt automatisch aus market_aggregator.py (Stand vor
Phase C, v5.43.1) durch migrate_ticker_master_phase_c.py — NICHT von Hand
abgeschrieben. Paritaet gegen v5.43.1: test_phase_c.py (alle Pruefungen gruen).

WAS HIER STEHT (statische Konfiguration):
  TICKER_MASTER[ticker] = {
      "lists":   {Listenname: Position, ...},   # Mitgliedschaft + Reihenfolge
      "sectors": {Sektorname: Position, ...},   # Sektor-Watchlist + Reihenfolge
  }
  Die Position bestimmt die Reihenfolge innerhalb der jeweiligen Liste bzw.
  Sektor-Watchlist (Reihenfolge ist outputrelevant, z.B. "sectorWatchlists"
  im master_market_data-JSON). Positionen muessen innerhalb einer Liste nicht
  lueckenlos sein, aber eindeutig.

WAS HIER BEWUSST NICHT STEHT (Laufzeit, bleibt in market_aggregator.py):
  - admin-freigegebene Extra-Ticker aus Cloudflare KV
    (fetch_approved_extra_tickers())
  - ex-IWV-Ticker (_load_ex_iwv_tickers())
  - BAD_SYMS-Filter in build_ticker_universe()
  Master = statische Konfiguration, Runtime Sources = dynamische
  Erweiterungen/Filter.

GOVERNANCE — NEUEN TICKER AUFNEHMEN (bis add_ticker.py existiert):
  1. Pruefen, ob der Ticker schon als Schluessel existiert (Suche in dieser
     Datei). Wenn ja: nur den fehlenden Listen-/Sektor-Eintrag ergaenzen.
  2. Sonst neuen Eintrag anlegen. Position = hoechste bisherige Position der
     Liste/des Sektors + 1 (haengt ans Ende an).
  3. Bei jeder inhaltlichen Aenderung an Sektor-Zuordnungen
     SECTOR_WATCHLISTS_VERSION hochzaehlen.
  4. _validate() laeuft beim Import: fehlerhafte Eintraege brechen den
     Aggregator-Lauf sofort und laut ab (gewollt, s. Entscheidung E1).

ENTFERNT IN PHASE C (separat dokumentiert, nicht Teil der Paritaet):
  DAX40_TICKERS, MDAX_TICKERS, TECDAX_TICKERS, EUROSTOXX_TICKERS_LEGACY
  (+ Alias EUROSTOXX_TICKERS), FTSE100_TICKERS, STOXX_EU_EXTRA — nachweislich
  ungenutzte Legacy-Listen (nur im master["markets"]-Block verwendet, fuer den
  in 84 Code-Dateien aus 6 Repos kein Leser existiert). S. Changelog
  market_aggregator.py.
"""

TICKER_MASTER_VERSION = "1.0"

# Versionsnummer der Sektor-Zuordnung (pro Ticker als "sectorTagVersion" im
# Output mitgefuehrt). Bei jeder inhaltlichen Aenderung an "sectors"-
# Eintraegen hochzaehlen. Wert unveraendert aus market_aggregator.py
# uebernommen (dort weiterhin unter demselben Namen verfuegbar).
SECTOR_WATCHLISTS_VERSION = "4.7"

# Statische Universums-Quellen, in der Reihenfolge, in der
# build_ticker_universe() sie zusammensetzt. SECTOR_ETFS_* werden dort wie
# bisher zu SECTOR_ETFS zusammengefasst.
UNIVERSE_SOURCE_LISTS = (
    "SP500_TICKERS",
    "NASDAQ100_EXTRA",
    "EU_ADR_TICKERS",
    "BEAR_US_TICKERS",
    "BEAR_DE_EU_TICKERS",
    "INTL_TIER1",
    "SECTOR_ETFS_BROAD",
    "SECTOR_ETFS_US",
    "SECTOR_ETFS_EXUS",
    "CRYPTO_TICKERS",
)

# Referenzlisten ohne eigene Universums-Wirkung (Mitglieder sind ueber andere
# Listen im Universum).
REFERENCE_LISTS = (
    "RS_SECTOR_ETFS",
)

# Reihenfolge der Sektor-Watchlists (= Schluesselreihenfolge von
# SECTOR_WATCHLISTS und Reihenfolge der Sektoren im "sectors"-Feld je Ticker).
SECTOR_ORDER = (
    "AI_TECH",
    "SEMIS",
    # [SECTOR_WATCHLISTS] Defence: US-Titel + europäische Heimatbörsen-Symbole (ADRs wie RHTRY haben keinen stabilen API-Feed)
    "DEFENSE",
    # [SECTOR_WATCHLISTS] Robotics/AI-Hardware (01.07.2026): IRBO neu, bestehende konsolidiert
    "ROBOTICS",
    "BIOTECH",
    "CLEAN_ENERGY",
    "FINTECH",
    "GLPONE",
    # [SECTOR_WATCHLISTS] v4.7: Picks&Shovels vom Frontend-Index-Slot zum getaggten Sektor befördert
    # [SECTOR_WATCHLISTS] (Axel: "hat nichts zu suchen in der Kategorie S&P500/Nasdaq")
    "PICKS_SHOVELS",
    "WHEEL_STOCKS",
    "LUXURY_EU",
    "JAPAN_TECH",
    "EM_GROWTH",
    # [SECTOR_WATCHLISTS] ── v4.2 (02.07.2026): 5 neue Sektoren (Gemini-Liste, Kausalitätsprüfung bestanden) ──
    # [SECTOR_WATCHLISTS] Governance: CEG NUR hier unter NUCLEAR_ENERGY (Kernkraft-Versorger, kein
    # [SECTOR_WATCHLISTS] Rohstoffwert). IBM/HON bewusst NICHT in CYBERSECURITY (Mischkonzerne mit
    # [SECTOR_WATCHLISTS] Cyber-Anteil <10% Umsatz — würden den Sektor-Filter im Scanner verwässern).
    "MATERIALS",
    "CYBERSECURITY",
    "NUCLEAR_ENERGY",
    "SPACE",
    "BIOTECH_LONGEVITY",
    # [SECTOR_WATCHLISTS] v4.7 (05.07.2026): Supercycle-Sektoren (Gemini-Vorschlag, Claude-verifiziert —
    # [SECTOR_WATCHLISTS] 10 Fehlticker/Fehlklassifikationen aussortiert: VERT→VRT, PRE→PLPC, GOLD→B,
    # [SECTOR_WATCHLISTS] SILV/PEAK/UHR/CNHI veraltet, FI/TTE Fehlkategorie, RKDA Nano-Cap).
    # [SECTOR_WATCHLISTS] Demografie-Qualitätstitel bewusst NICHT als Scan-Sektor (Value-Thema →
    # [SECTOR_WATCHLISTS] docs/VALUE_MOD_KONZEPT.md Themenregister; FIN-Archiv sammelt sie via R3000).
    "GRID_ELECTRIFICATION",
    "PRECIOUS_METALS",
    "AGRICULTURE",
    "WATER",
)

# 684 Ticker
TICKER_MASTER = {
    # [SP500_TICKERS] Mega-Cap Tech
    "AAPL": {"lists": {"SP500_TICKERS": 0}, "sectors": {}},
    "MSFT": {"lists": {"SP500_TICKERS": 1}, "sectors": {"AI_TECH": 2, "PICKS_SHOVELS": 10}},
    "NVDA": {"lists": {"SP500_TICKERS": 2, "BEAR_US_TICKERS": 46}, "sectors": {"AI_TECH": 0, "SEMIS": 0, "ROBOTICS": 0, "PICKS_SHOVELS": 0}},
    "AMZN": {"lists": {"SP500_TICKERS": 3}, "sectors": {"PICKS_SHOVELS": 11}},
    "GOOGL": {"lists": {"SP500_TICKERS": 4}, "sectors": {"AI_TECH": 3, "PICKS_SHOVELS": 12}},
    "GOOG": {"lists": {"SP500_TICKERS": 5}, "sectors": {}},
    "META": {"lists": {"SP500_TICKERS": 6}, "sectors": {"AI_TECH": 4, "PICKS_SHOVELS": 13}},
    "TSLA": {"lists": {"SP500_TICKERS": 7, "BEAR_US_TICKERS": 41}, "sectors": {}},
    "AVGO": {"lists": {"SP500_TICKERS": 8}, "sectors": {"SEMIS": 2, "PICKS_SHOVELS": 2}},
    "ORCL": {"lists": {"SP500_TICKERS": 9}, "sectors": {"PICKS_SHOVELS": 14}},
    # [SP500_TICKERS] Financials
    "JPM": {"lists": {"SP500_TICKERS": 10}, "sectors": {}},
    "BAC": {"lists": {"SP500_TICKERS": 11}, "sectors": {}},
    "WFC": {"lists": {"SP500_TICKERS": 12}, "sectors": {}},
    "GS": {"lists": {"SP500_TICKERS": 13}, "sectors": {}},
    "MS": {"lists": {"SP500_TICKERS": 14}, "sectors": {}},
    "BLK": {"lists": {"SP500_TICKERS": 15}, "sectors": {}},
    "SCHW": {"lists": {"SP500_TICKERS": 16}, "sectors": {"FINTECH": 9}},
    "AXP": {"lists": {"SP500_TICKERS": 17}, "sectors": {}},
    "CB": {"lists": {"SP500_TICKERS": 18}, "sectors": {}},
    "MMC": {"lists": {"SP500_TICKERS": 19}, "sectors": {}},
    "AON": {"lists": {"SP500_TICKERS": 20}, "sectors": {}},
    "CME": {"lists": {"SP500_TICKERS": 21}, "sectors": {}},
    "SPGI": {"lists": {"SP500_TICKERS": 22}, "sectors": {}},
    "MCO": {"lists": {"SP500_TICKERS": 23}, "sectors": {}},
    # [SP500_TICKERS] Healthcare
    "UNH": {"lists": {"SP500_TICKERS": 24}, "sectors": {}},
    "LLY": {"lists": {"SP500_TICKERS": 25}, "sectors": {"BIOTECH": 9, "GLPONE": 0}},
    "JNJ": {"lists": {"SP500_TICKERS": 26}, "sectors": {}},
    "ABT": {"lists": {"SP500_TICKERS": 27}, "sectors": {}},
    "MRK": {"lists": {"SP500_TICKERS": 28}, "sectors": {}},
    "ABBV": {"lists": {"SP500_TICKERS": 29}, "sectors": {"BIOTECH": 8}},
    "TMO": {"lists": {"SP500_TICKERS": 30}, "sectors": {}},
    "DHR": {"lists": {"SP500_TICKERS": 31}, "sectors": {}},
    "SYK": {"lists": {"SP500_TICKERS": 32}, "sectors": {}},
    "BSX": {"lists": {"SP500_TICKERS": 33}, "sectors": {}},
    "MDT": {"lists": {"SP500_TICKERS": 34}, "sectors": {}},
    "ELV": {"lists": {"SP500_TICKERS": 35}, "sectors": {}},
    "CI": {"lists": {"SP500_TICKERS": 36}, "sectors": {}},
    "HUM": {"lists": {"SP500_TICKERS": 37}, "sectors": {}},
    "ISRG": {"lists": {"SP500_TICKERS": 38}, "sectors": {"ROBOTICS": 6}},
    "REGN": {"lists": {"SP500_TICKERS": 39}, "sectors": {"BIOTECH": 2, "GLPONE": 5}},
    "VRTX": {"lists": {"SP500_TICKERS": 40}, "sectors": {"BIOTECH": 3}},
    "GILD": {"lists": {"SP500_TICKERS": 41}, "sectors": {"BIOTECH": 4, "GLPONE": 8}},
    "AMGN": {"lists": {"SP500_TICKERS": 42}, "sectors": {"GLPONE": 4}},
    "BMY": {"lists": {"SP500_TICKERS": 43}, "sectors": {}},
    "PFE": {"lists": {"SP500_TICKERS": 44}, "sectors": {"GLPONE": 9}},
    "CVS": {"lists": {"SP500_TICKERS": 45}, "sectors": {}},
    "ZTS": {"lists": {"SP500_TICKERS": 46}, "sectors": {}},
    "IDXX": {"lists": {"SP500_TICKERS": 47, "NASDAQ100_EXTRA": 2}, "sectors": {}},
    "A": {"lists": {"SP500_TICKERS": 48}, "sectors": {}},
    "IQV": {"lists": {"SP500_TICKERS": 49}, "sectors": {}},
    # [SP500_TICKERS] Consumer
    "COST": {"lists": {"SP500_TICKERS": 50}, "sectors": {}},
    "WMT": {"lists": {"SP500_TICKERS": 51}, "sectors": {}},
    "HD": {"lists": {"SP500_TICKERS": 52}, "sectors": {}},
    "MCD": {"lists": {"SP500_TICKERS": 53}, "sectors": {}},
    "SBUX": {"lists": {"SP500_TICKERS": 54}, "sectors": {}},
    "TGT": {"lists": {"SP500_TICKERS": 55}, "sectors": {}},
    "LOW": {"lists": {"SP500_TICKERS": 56}, "sectors": {}},
    "TJX": {"lists": {"SP500_TICKERS": 57}, "sectors": {}},
    "BKNG": {"lists": {"SP500_TICKERS": 58}, "sectors": {}},
    "MAR": {"lists": {"SP500_TICKERS": 59}, "sectors": {}},
    "HLT": {"lists": {"SP500_TICKERS": 60}, "sectors": {}},
    "YUM": {"lists": {"SP500_TICKERS": 61}, "sectors": {}},
    "NKE": {"lists": {"SP500_TICKERS": 62}, "sectors": {}},
    "PG": {"lists": {"SP500_TICKERS": 63}, "sectors": {}},
    "KO": {"lists": {"SP500_TICKERS": 64}, "sectors": {}},
    "PEP": {"lists": {"SP500_TICKERS": 65}, "sectors": {}},
    "PM": {"lists": {"SP500_TICKERS": 66}, "sectors": {}},
    "MO": {"lists": {"SP500_TICKERS": 67}, "sectors": {}},
    "CL": {"lists": {"SP500_TICKERS": 68}, "sectors": {}},
    "EL": {"lists": {"SP500_TICKERS": 69}, "sectors": {}},
    "CHD": {"lists": {"SP500_TICKERS": 70}, "sectors": {}},
    # [SP500_TICKERS] Industrials
    "CAT": {"lists": {"SP500_TICKERS": 71}, "sectors": {}},
    "HON": {"lists": {"SP500_TICKERS": 72}, "sectors": {}},
    "UPS": {"lists": {"SP500_TICKERS": 73}, "sectors": {}},
    "DE": {"lists": {"SP500_TICKERS": 74}, "sectors": {"AGRICULTURE": 0}},
    "GE": {"lists": {"SP500_TICKERS": 75}, "sectors": {}},
    "GEV": {"lists": {"SP500_TICKERS": 76}, "sectors": {"GRID_ELECTRIFICATION": 0}},
    "BA": {"lists": {"SP500_TICKERS": 77}, "sectors": {"DEFENSE": 4}},
    "LMT": {"lists": {"SP500_TICKERS": 78}, "sectors": {"DEFENSE": 0}},
    "RTX": {"lists": {"SP500_TICKERS": 79}, "sectors": {"DEFENSE": 1}},
    "NOC": {"lists": {"SP500_TICKERS": 80}, "sectors": {"DEFENSE": 2}},
    "GD": {"lists": {"SP500_TICKERS": 81}, "sectors": {"DEFENSE": 3}},
    "HII": {"lists": {"SP500_TICKERS": 82}, "sectors": {"DEFENSE": 7}},
    "TDG": {"lists": {"SP500_TICKERS": 83}, "sectors": {"DEFENSE": 8, "SPACE": 3}},
    "KTOS": {"lists": {"SP500_TICKERS": 84}, "sectors": {"DEFENSE": 5}},
    "AXON": {"lists": {"SP500_TICKERS": 85}, "sectors": {"DEFENSE": 6}},
    "UNP": {"lists": {"SP500_TICKERS": 86}, "sectors": {}},
    "CSX": {"lists": {"SP500_TICKERS": 87}, "sectors": {}},
    "NSC": {"lists": {"SP500_TICKERS": 88}, "sectors": {}},
    "TT": {"lists": {"SP500_TICKERS": 89}, "sectors": {}},
    "CARR": {"lists": {"SP500_TICKERS": 90}, "sectors": {}},
    "OTIS": {"lists": {"SP500_TICKERS": 91}, "sectors": {}},
    "JCI": {"lists": {"SP500_TICKERS": 92}, "sectors": {}},
    "EMR": {"lists": {"SP500_TICKERS": 93}, "sectors": {"GRID_ELECTRIFICATION": 1}},
    "ROK": {"lists": {"SP500_TICKERS": 94}, "sectors": {"ROBOTICS": 13}},
    "AME": {"lists": {"SP500_TICKERS": 95}, "sectors": {"GRID_ELECTRIFICATION": 3}},
    "ITW": {"lists": {"SP500_TICKERS": 96}, "sectors": {}},
    "ETN": {"lists": {"SP500_TICKERS": 97}, "sectors": {"PICKS_SHOVELS": 16, "NUCLEAR_ENERGY": 6}},
    "PH": {"lists": {"SP500_TICKERS": 98}, "sectors": {}},
    "IR": {"lists": {"SP500_TICKERS": 99}, "sectors": {"ROBOTICS": 19}},
    # [SP500_TICKERS] Energy
    "XOM": {"lists": {"SP500_TICKERS": 100}, "sectors": {}},
    "CVX": {"lists": {"SP500_TICKERS": 101}, "sectors": {}},
    "COP": {"lists": {"SP500_TICKERS": 102}, "sectors": {}},
    "EOG": {"lists": {"SP500_TICKERS": 103}, "sectors": {}},
    "SLB": {"lists": {"SP500_TICKERS": 104}, "sectors": {}},
    "MPC": {"lists": {"SP500_TICKERS": 105}, "sectors": {}},
    "PSX": {"lists": {"SP500_TICKERS": 106}, "sectors": {}},
    "VLO": {"lists": {"SP500_TICKERS": 107}, "sectors": {}},
    "OXY": {"lists": {"SP500_TICKERS": 108}, "sectors": {}},
    "DVN": {"lists": {"SP500_TICKERS": 109}, "sectors": {}},
    "HAL": {"lists": {"SP500_TICKERS": 110}, "sectors": {}},
    "BKR": {"lists": {"SP500_TICKERS": 111}, "sectors": {}},
    "FANG": {"lists": {"SP500_TICKERS": 112}, "sectors": {}},
    # [SP500_TICKERS] Utilities & REITs
    "NEE": {"lists": {"SP500_TICKERS": 113}, "sectors": {"CLEAN_ENERGY": 6}},
    "DUK": {"lists": {"SP500_TICKERS": 114}, "sectors": {}},
    "SO": {"lists": {"SP500_TICKERS": 115}, "sectors": {}},
    "AEP": {"lists": {"SP500_TICKERS": 116}, "sectors": {}},
    "D": {"lists": {"SP500_TICKERS": 117}, "sectors": {}},
    "SRE": {"lists": {"SP500_TICKERS": 118}, "sectors": {}},
    "EXC": {"lists": {"SP500_TICKERS": 119, "NASDAQ100_EXTRA": 20}, "sectors": {}},
    "PLD": {"lists": {"SP500_TICKERS": 120}, "sectors": {}},
    "AMT": {"lists": {"SP500_TICKERS": 121}, "sectors": {}},
    "EQIX": {"lists": {"SP500_TICKERS": 122}, "sectors": {}},
    "CCI": {"lists": {"SP500_TICKERS": 123}, "sectors": {}},
    "PSA": {"lists": {"SP500_TICKERS": 124}, "sectors": {}},
    "O": {"lists": {"SP500_TICKERS": 125}, "sectors": {}},
    "VICI": {"lists": {"SP500_TICKERS": 126}, "sectors": {}},
    # [SP500_TICKERS] Tech & Software
    "V": {"lists": {"SP500_TICKERS": 127}, "sectors": {"FINTECH": 7}},  # [SP500_TICKERS] v4.3: ANSS delistet (Synopsys-Übernahme 2025)
    "MA": {"lists": {"SP500_TICKERS": 128}, "sectors": {"FINTECH": 8}},
    "INTU": {"lists": {"SP500_TICKERS": 129}, "sectors": {}},
    "ADBE": {"lists": {"SP500_TICKERS": 130}, "sectors": {}},
    "CRM": {"lists": {"SP500_TICKERS": 131}, "sectors": {}},
    "NOW": {"lists": {"SP500_TICKERS": 132}, "sectors": {}},
    "SNPS": {"lists": {"SP500_TICKERS": 133}, "sectors": {}},
    "CDNS": {"lists": {"SP500_TICKERS": 134}, "sectors": {}},
    "ADSK": {"lists": {"SP500_TICKERS": 135, "NASDAQ100_EXTRA": 0}, "sectors": {}},
    "WDAY": {"lists": {"SP500_TICKERS": 136}, "sectors": {}},
    "TEAM": {"lists": {"SP500_TICKERS": 137}, "sectors": {}},
    "PANW": {"lists": {"SP500_TICKERS": 138}, "sectors": {"CYBERSECURITY": 0}},
    "CRWD": {"lists": {"SP500_TICKERS": 139, "BEAR_US_TICKERS": 4}, "sectors": {"CYBERSECURITY": 1}},
    "FTNT": {"lists": {"SP500_TICKERS": 140}, "sectors": {"CYBERSECURITY": 2}},
    "ZS": {"lists": {"SP500_TICKERS": 141}, "sectors": {"CYBERSECURITY": 4}},
    "OKTA": {"lists": {"SP500_TICKERS": 142}, "sectors": {"CYBERSECURITY": 5}},
    "S": {"lists": {"SP500_TICKERS": 143}, "sectors": {}},
    "DDOG": {"lists": {"SP500_TICKERS": 144, "BEAR_US_TICKERS": 7}, "sectors": {"WHEEL_STOCKS": 0}},
    "MDB": {"lists": {"SP500_TICKERS": 145, "BEAR_US_TICKERS": 8}, "sectors": {}},
    "SNOW": {"lists": {"SP500_TICKERS": 146, "BEAR_US_TICKERS": 5}, "sectors": {}},
    "NET": {"lists": {"SP500_TICKERS": 147, "BEAR_US_TICKERS": 6}, "sectors": {"AI_TECH": 9, "CYBERSECURITY": 3}},
    "CFLT": {"lists": {"SP500_TICKERS": 148}, "sectors": {}},
    "ESTC": {"lists": {"SP500_TICKERS": 149}, "sectors": {}},
    "QCOM": {"lists": {"SP500_TICKERS": 150}, "sectors": {"SEMIS": 3}},
    "TXN": {"lists": {"SP500_TICKERS": 151}, "sectors": {"SEMIS": 4}},
    "ADI": {"lists": {"SP500_TICKERS": 152}, "sectors": {"SEMIS": 12, "ROBOTICS": 20}},
    "MCHP": {"lists": {"SP500_TICKERS": 153}, "sectors": {"ROBOTICS": 22}},
    "NXPI": {"lists": {"SP500_TICKERS": 154}, "sectors": {"SEMIS": 11, "ROBOTICS": 21}},
    "KLAC": {"lists": {"SP500_TICKERS": 155}, "sectors": {"SEMIS": 7, "PICKS_SHOVELS": 5}},
    "LRCX": {"lists": {"SP500_TICKERS": 156}, "sectors": {"SEMIS": 6, "PICKS_SHOVELS": 4}},
    "AMAT": {"lists": {"SP500_TICKERS": 157}, "sectors": {"SEMIS": 5, "PICKS_SHOVELS": 3}},
    "MU": {"lists": {"SP500_TICKERS": 158}, "sectors": {"SEMIS": 8}},
    "WDC": {"lists": {"SP500_TICKERS": 159}, "sectors": {}},
    "STX": {"lists": {"SP500_TICKERS": 160}, "sectors": {}},
    "IBM": {"lists": {"SP500_TICKERS": 161}, "sectors": {}},
    "CSCO": {"lists": {"SP500_TICKERS": 162}, "sectors": {}},
    "ACN": {"lists": {"SP500_TICKERS": 163}, "sectors": {}},
    "HPQ": {"lists": {"SP500_TICKERS": 164}, "sectors": {}},
    "HPE": {"lists": {"SP500_TICKERS": 165}, "sectors": {}},
    "DELL": {"lists": {"SP500_TICKERS": 166}, "sectors": {}},
    "NTAP": {"lists": {"SP500_TICKERS": 167}, "sectors": {}},
    # [SP500_TICKERS] Semiconductors / AI
    "ARM": {"lists": {"SP500_TICKERS": 168, "BEAR_US_TICKERS": 47}, "sectors": {"AI_TECH": 6, "PICKS_SHOVELS": 7}},
    "SMCI": {"lists": {"SP500_TICKERS": 169, "BEAR_US_TICKERS": 0}, "sectors": {"AI_TECH": 7, "PICKS_SHOVELS": 9}},
    "MRVL": {"lists": {"SP500_TICKERS": 170, "BEAR_US_TICKERS": 2}, "sectors": {"SEMIS": 10, "PICKS_SHOVELS": 6, "WHEEL_STOCKS": 9}},
    "MSTR": {"lists": {"SP500_TICKERS": 171, "BEAR_US_TICKERS": 1}, "sectors": {"AI_TECH": 8}},
    "PLTR": {"lists": {"SP500_TICKERS": 172, "BEAR_US_TICKERS": 39}, "sectors": {"AI_TECH": 5, "DEFENSE": 21}},
    "COIN": {"lists": {"SP500_TICKERS": 173, "BEAR_US_TICKERS": 40}, "sectors": {"FINTECH": 5, "WHEEL_STOCKS": 10}},
    # [SP500_TICKERS] E-Commerce / Consumer Tech
    "NFLX": {"lists": {"SP500_TICKERS": 174}, "sectors": {}},
    "UBER": {"lists": {"SP500_TICKERS": 175, "BEAR_US_TICKERS": 27}, "sectors": {}},
    "ABNB": {"lists": {"SP500_TICKERS": 176, "BEAR_US_TICKERS": 29}, "sectors": {}},
    "LYFT": {"lists": {"SP500_TICKERS": 177, "BEAR_US_TICKERS": 28}, "sectors": {}},
    "RBLX": {"lists": {"SP500_TICKERS": 178, "BEAR_US_TICKERS": 31}, "sectors": {}},
    "SNAP": {"lists": {"SP500_TICKERS": 179, "BEAR_US_TICKERS": 32}, "sectors": {}},
    "PINS": {"lists": {"SP500_TICKERS": 180, "BEAR_US_TICKERS": 33}, "sectors": {}},
    "MTCH": {"lists": {"SP500_TICKERS": 181, "BEAR_US_TICKERS": 34}, "sectors": {}},
    "ZM": {"lists": {"SP500_TICKERS": 182, "BEAR_US_TICKERS": 25}, "sectors": {}},
    "DOCU": {"lists": {"SP500_TICKERS": 183, "BEAR_US_TICKERS": 26}, "sectors": {}},
    # [INTL_TIER1] Kanada (US-listed)
    # [INTL_TIER1] v4.2-Fix: CCO war Clear Channel Outdoor (falsche Firma!) — Cameco = CCJ
    "SHOP": {"lists": {"SP500_TICKERS": 184, "BEAR_US_TICKERS": 9, "INTL_TIER1": 76}, "sectors": {}},  # [SP500_TICKERS] v4.3: SQ→XYZ (Block-Umbenennung 01/2025)
    "MELI": {"lists": {"SP500_TICKERS": 185}, "sectors": {}},
    "SE": {"lists": {"SP500_TICKERS": 186}, "sectors": {"EM_GROWTH": 8}},
    "GRAB": {"lists": {"SP500_TICKERS": 187}, "sectors": {"EM_GROWTH": 9}},
    "XYZ": {"lists": {"SP500_TICKERS": 188, "BEAR_US_TICKERS": 10}, "sectors": {"FINTECH": 0}},
    # [SP500_TICKERS] Fintech
    "HOOD": {"lists": {"SP500_TICKERS": 189, "BEAR_US_TICKERS": 11}, "sectors": {"FINTECH": 1, "WHEEL_STOCKS": 7}},
    "SOFI": {"lists": {"SP500_TICKERS": 190, "BEAR_US_TICKERS": 37}, "sectors": {"FINTECH": 3}},
    "AFRM": {"lists": {"SP500_TICKERS": 191, "BEAR_US_TICKERS": 36}, "sectors": {"FINTECH": 2}},
    "UPST": {"lists": {"SP500_TICKERS": 192, "BEAR_US_TICKERS": 35}, "sectors": {"FINTECH": 4}},
    "PYPL": {"lists": {"SP500_TICKERS": 193}, "sectors": {"FINTECH": 6}},
    # [SP500_TICKERS] China ADRs (US-listed)
    # [INTL_TIER1] China/Hongkong (US-gelistete ADRs)
    "BABA": {"lists": {"SP500_TICKERS": 194, "BEAR_US_TICKERS": 42, "INTL_TIER1": 62}, "sectors": {"EM_GROWTH": 1}},
    "JD": {"lists": {"SP500_TICKERS": 195, "INTL_TIER1": 63}, "sectors": {}},
    "PDD": {"lists": {"SP500_TICKERS": 196, "BEAR_US_TICKERS": 43, "INTL_TIER1": 64}, "sectors": {"EM_GROWTH": 2}},
    "BIDU": {"lists": {"SP500_TICKERS": 197, "BEAR_US_TICKERS": 44, "INTL_TIER1": 65}, "sectors": {}},
    "NTES": {"lists": {"SP500_TICKERS": 198}, "sectors": {}},
    "TCOM": {"lists": {"SP500_TICKERS": 199}, "sectors": {}},
    "FUTU": {"lists": {"SP500_TICKERS": 200}, "sectors": {}},
    "NIO": {"lists": {"SP500_TICKERS": 201, "BEAR_US_TICKERS": 14, "INTL_TIER1": 68}, "sectors": {}},
    "XPEV": {"lists": {"SP500_TICKERS": 202, "BEAR_US_TICKERS": 15, "INTL_TIER1": 69}, "sectors": {}},
    "LI": {"lists": {"SP500_TICKERS": 203, "BEAR_US_TICKERS": 16, "INTL_TIER1": 70}, "sectors": {}},
    # [SP500_TICKERS] Auto
    "GM": {"lists": {"SP500_TICKERS": 204}, "sectors": {}},
    "F": {"lists": {"SP500_TICKERS": 205}, "sectors": {}},
    "RIVN": {"lists": {"SP500_TICKERS": 206, "BEAR_US_TICKERS": 12}, "sectors": {}},
    "LCID": {"lists": {"SP500_TICKERS": 207, "BEAR_US_TICKERS": 13}, "sectors": {}},
    "STLA": {"lists": {"SP500_TICKERS": 208}, "sectors": {}},
    # [INTL_TIER1] Japan (ADRs only)
    "TM": {"lists": {"SP500_TICKERS": 209, "INTL_TIER1": 46}, "sectors": {"JAPAN_TECH": 0}},
    "HMC": {"lists": {"SP500_TICKERS": 210, "INTL_TIER1": 47}, "sectors": {"JAPAN_TECH": 6}},
    # [SP500_TICKERS] Materials
    "LIN": {"lists": {"SP500_TICKERS": 211, "EU_ADR_TICKERS": 12}, "sectors": {}},  # [EU_ADR_TICKERS] Linde (NYSE, primär US-listing seit Fusion)
    "APD": {"lists": {"SP500_TICKERS": 212}, "sectors": {}},
    "ECL": {"lists": {"SP500_TICKERS": 213}, "sectors": {"WATER": 4}},
    "SHW": {"lists": {"SP500_TICKERS": 214}, "sectors": {}},
    "FCX": {"lists": {"SP500_TICKERS": 215, "EU_ADR_TICKERS": 62}, "sectors": {"MATERIALS": 0}},  # [EU_ADR_TICKERS] Freeport-McMoRan (Materials — liquid Options)
    "NEM": {"lists": {"SP500_TICKERS": 216}, "sectors": {"PRECIOUS_METALS": 0}},
    "GOLD": {"lists": {"SP500_TICKERS": 217}, "sectors": {}},
    "ALB": {"lists": {"SP500_TICKERS": 218}, "sectors": {"MATERIALS": 1}},
    "MP": {"lists": {"SP500_TICKERS": 219}, "sectors": {"MATERIALS": 2}},
    # [SP500_TICKERS] Biotech / Pharma Growth
    "MRNA": {"lists": {"SP500_TICKERS": 220, "BEAR_US_TICKERS": 21}, "sectors": {"BIOTECH": 0}},  # [SP500_TICKERS] v4.3: SGEN delistet (Pfizer-Übernahme 2023)
    "BNTX": {"lists": {"SP500_TICKERS": 221, "BEAR_US_TICKERS": 22}, "sectors": {"BIOTECH": 1}},
    "BIIB": {"lists": {"SP500_TICKERS": 222, "BEAR_US_TICKERS": 24}, "sectors": {"BIOTECH": 5}},
    "ILMN": {"lists": {"SP500_TICKERS": 223, "BEAR_US_TICKERS": 23}, "sectors": {"BIOTECH": 6, "BIOTECH_LONGEVITY": 4}},
    "RARE": {"lists": {"SP500_TICKERS": 224}, "sectors": {}},
    "EXAS": {"lists": {"SP500_TICKERS": 225}, "sectors": {"BIOTECH_LONGEVITY": 3}},
    "INCY": {"lists": {"SP500_TICKERS": 226}, "sectors": {}},
    "NBIX": {"lists": {"SP500_TICKERS": 227}, "sectors": {}},
    "ALLO": {"lists": {"SP500_TICKERS": 228}, "sectors": {}},
    "VKTX": {"lists": {"SP500_TICKERS": 229}, "sectors": {"GLPONE": 2}},
    "RYTM": {"lists": {"SP500_TICKERS": 230}, "sectors": {"GLPONE": 3}},
    "ACAD": {"lists": {"SP500_TICKERS": 231}, "sectors": {}},
    "MRUS": {"lists": {"SP500_TICKERS": 232}, "sectors": {}},
    "PRCT": {"lists": {"SP500_TICKERS": 233}, "sectors": {}},
    # [SP500_TICKERS] Clean Energy
    "ENPH": {"lists": {"SP500_TICKERS": 234, "BEAR_US_TICKERS": 17}, "sectors": {"CLEAN_ENERGY": 0}},  # [SP500_TICKERS] v4.3: NOVA (Sunnova) delistet nach Insolvenz 2025
    "FSLR": {"lists": {"SP500_TICKERS": 235, "BEAR_US_TICKERS": 18}, "sectors": {"CLEAN_ENERGY": 1}},
    "SEDG": {"lists": {"SP500_TICKERS": 236}, "sectors": {"CLEAN_ENERGY": 2}},
    "RUN": {"lists": {"SP500_TICKERS": 237}, "sectors": {"CLEAN_ENERGY": 3}},
    "ARRY": {"lists": {"SP500_TICKERS": 238}, "sectors": {"CLEAN_ENERGY": 7}},
    "BE": {"lists": {"SP500_TICKERS": 239, "BEAR_US_TICKERS": 20}, "sectors": {"CLEAN_ENERGY": 4}},
    "PLUG": {"lists": {"SP500_TICKERS": 240, "BEAR_US_TICKERS": 19}, "sectors": {"CLEAN_ENERGY": 5}},
    "BLDP": {"lists": {"SP500_TICKERS": 241}, "sectors": {"CLEAN_ENERGY": 8}},
    # [SP500_TICKERS] Misc Growth
    "GLW": {"lists": {"SP500_TICKERS": 247}, "sectors": {}},  # [SP500_TICKERS] v4.3: ZI→GTM (ZoomInfo-Umbenennung 2025)
    "LDOS": {"lists": {"SP500_TICKERS": 248}, "sectors": {"DEFENSE": 11}},  # [SECTOR_WATCHLISTS] v4.3: Yahoo-Symbol für Moog ist MOG-A
    "SAIC": {"lists": {"SP500_TICKERS": 249}, "sectors": {"DEFENSE": 12}},
    "CACI": {"lists": {"SP500_TICKERS": 250}, "sectors": {"DEFENSE": 13}},
    "BAH": {"lists": {"SP500_TICKERS": 251}, "sectors": {}},
    "HUBS": {"lists": {"SP500_TICKERS": 252}, "sectors": {}},
    "GTM": {"lists": {"SP500_TICKERS": 253}, "sectors": {}},
    "GTLB": {"lists": {"SP500_TICKERS": 254, "INTL_TIER1": 108}, "sectors": {}},
    "BILL": {"lists": {"SP500_TICKERS": 255}, "sectors": {}},
    "PCTY": {"lists": {"SP500_TICKERS": 256}, "sectors": {}},
    "FAST": {"lists": {"NASDAQ100_EXTRA": 1}, "sectors": {}},
    "KDP": {"lists": {"NASDAQ100_EXTRA": 3}, "sectors": {}},
    "KHC": {"lists": {"NASDAQ100_EXTRA": 4}, "sectors": {}},
    "LULU": {"lists": {"NASDAQ100_EXTRA": 5}, "sectors": {}},
    "MNST": {"lists": {"NASDAQ100_EXTRA": 6}, "sectors": {}},
    "ODFL": {"lists": {"NASDAQ100_EXTRA": 7}, "sectors": {}},
    "PAYX": {"lists": {"NASDAQ100_EXTRA": 8}, "sectors": {}},
    "PCAR": {"lists": {"NASDAQ100_EXTRA": 9}, "sectors": {}},
    "ROST": {"lists": {"NASDAQ100_EXTRA": 10}, "sectors": {}},
    "SIRI": {"lists": {"NASDAQ100_EXTRA": 11}, "sectors": {}},
    "TMUS": {"lists": {"NASDAQ100_EXTRA": 12}, "sectors": {}},
    "VRSK": {"lists": {"NASDAQ100_EXTRA": 13}, "sectors": {}},
    "VRSN": {"lists": {"NASDAQ100_EXTRA": 14}, "sectors": {}},
    "XEL": {"lists": {"NASDAQ100_EXTRA": 15}, "sectors": {}},
    "CPRT": {"lists": {"NASDAQ100_EXTRA": 16}, "sectors": {}},
    "CTAS": {"lists": {"NASDAQ100_EXTRA": 17}, "sectors": {}},
    "DLTR": {"lists": {"NASDAQ100_EXTRA": 18}, "sectors": {}},
    "EBAY": {"lists": {"NASDAQ100_EXTRA": 19}, "sectors": {}},
    # [EU_ADR_TICKERS] ── Deutschland (DAX + MDAX) ──────────────────────────────────────────────
    "SAP": {"lists": {"EU_ADR_TICKERS": 0, "INTL_TIER1": 4}, "sectors": {}},  # [EU_ADR_TICKERS] SAP SE (NYSE, primär US-listing)
    "DB": {"lists": {"EU_ADR_TICKERS": 1, "INTL_TIER1": 29}, "sectors": {}},  # [EU_ADR_TICKERS] Deutsche Bank (NYSE ADR)
    # [INTL_TIER1] Europa — Industrie (ADR)
    "SIEGY": {"lists": {"EU_ADR_TICKERS": 2, "INTL_TIER1": 36}, "sectors": {}},  # [EU_ADR_TICKERS] Siemens (OTC ADR, liquid)
    "BAYRY": {"lists": {"EU_ADR_TICKERS": 3, "INTL_TIER1": 12}, "sectors": {}},  # [EU_ADR_TICKERS] Bayer (OTC ADR)
    "BMWYY": {"lists": {"EU_ADR_TICKERS": 4}, "sectors": {}},  # [EU_ADR_TICKERS] BMW (OTC ADR)
    "ADDYY": {"lists": {"EU_ADR_TICKERS": 5, "INTL_TIER1": 35}, "sectors": {"LUXURY_EU": 5}},  # [EU_ADR_TICKERS] Adidas (OTC ADR)
    "DHLGY": {"lists": {"EU_ADR_TICKERS": 6}, "sectors": {}},  # [EU_ADR_TICKERS] DHL Group (OTC ADR)
    "DTEGY": {"lists": {"EU_ADR_TICKERS": 7}, "sectors": {}},  # [EU_ADR_TICKERS] Deutsche Telekom (OTC ADR)
    "AZSEY": {"lists": {"EU_ADR_TICKERS": 8}, "sectors": {}},  # [EU_ADR_TICKERS] Allianz (OTC ADR)
    "MURGY": {"lists": {"EU_ADR_TICKERS": 9}, "sectors": {}},  # [EU_ADR_TICKERS] Munich Re (OTC ADR)
    "RWEOY": {"lists": {"EU_ADR_TICKERS": 10}, "sectors": {}},  # [EU_ADR_TICKERS] RWE (OTC ADR)
    "IFNNY": {"lists": {"EU_ADR_TICKERS": 11}, "sectors": {}},  # [EU_ADR_TICKERS] Infineon (OTC ADR)
    "BASFY": {"lists": {"EU_ADR_TICKERS": 13}, "sectors": {}},  # [EU_ADR_TICKERS] BASF (OTC ADR)
    "MKKGY": {"lists": {"EU_ADR_TICKERS": 14}, "sectors": {}},  # [EU_ADR_TICKERS] Merck KGaA (OTC ADR — nicht Merck US!)
    "FSNUY": {"lists": {"EU_ADR_TICKERS": 15}, "sectors": {}},  # [EU_ADR_TICKERS] Fresenius (OTC ADR)
    "RNMBY": {"lists": {"EU_ADR_TICKERS": 16}, "sectors": {}},  # [EU_ADR_TICKERS] Rheinmetall (OTC ADR, Defense)
    "VWAGY": {"lists": {"EU_ADR_TICKERS": 17}, "sectors": {}},  # [EU_ADR_TICKERS] Volkswagen (OTC ADR)
    "MBGAF": {"lists": {"EU_ADR_TICKERS": 18}, "sectors": {}},  # [EU_ADR_TICKERS] Mercedes-Benz (OTC ADR)
    "HBMRY": {"lists": {"EU_ADR_TICKERS": 19}, "sectors": {}},  # [EU_ADR_TICKERS] Heidelberg Materials (OTC ADR)
    "HENKY": {"lists": {"EU_ADR_TICKERS": 20}, "sectors": {}},  # [EU_ADR_TICKERS] Henkel (OTC ADR)
    "EADSY": {"lists": {"EU_ADR_TICKERS": 21}, "sectors": {}},  # [EU_ADR_TICKERS] Airbus (OTC ADR)
    "SBGSY": {"lists": {"EU_ADR_TICKERS": 22}, "sectors": {}},  # [EU_ADR_TICKERS] Schneider Electric (OTC ADR)
    # [EU_ADR_TICKERS] ── Frankreich ────────────────────────────────────────────────────────────
    "TTE": {"lists": {"EU_ADR_TICKERS": 23, "INTL_TIER1": 16}, "sectors": {}},  # [EU_ADR_TICKERS] TotalEnergies (NYSE, liquid Options)
    "LRLCY": {"lists": {"EU_ADR_TICKERS": 24}, "sectors": {"LUXURY_EU": 1}},  # [EU_ADR_TICKERS] L'Oreal (OTC ADR)
    # [INTL_TIER1] Europa — Konsum & Luxus (ADR)
    "LVMUY": {"lists": {"EU_ADR_TICKERS": 25, "INTL_TIER1": 30}, "sectors": {"LUXURY_EU": 0}},  # [EU_ADR_TICKERS] LVMH (OTC ADR)
    "PPRUY": {"lists": {"EU_ADR_TICKERS": 26, "INTL_TIER1": 32}, "sectors": {"LUXURY_EU": 4}},  # [EU_ADR_TICKERS] Kering (OTC ADR)
    "HESAY": {"lists": {"EU_ADR_TICKERS": 27, "INTL_TIER1": 33}, "sectors": {"LUXURY_EU": 2}},  # [EU_ADR_TICKERS] Hermès (OTC ADR)
    "BNPQY": {"lists": {"EU_ADR_TICKERS": 28}, "sectors": {}},  # [EU_ADR_TICKERS] BNP Paribas (OTC ADR)
    "CFRUY": {"lists": {"EU_ADR_TICKERS": 29, "INTL_TIER1": 31}, "sectors": {"LUXURY_EU": 3}},  # [EU_ADR_TICKERS] Richemont (OTC ADR)
    "PDRDY": {"lists": {"EU_ADR_TICKERS": 30}, "sectors": {}},  # [EU_ADR_TICKERS] Pernod Ricard (OTC ADR)
    "VCISY": {"lists": {"EU_ADR_TICKERS": 31}, "sectors": {}},  # [EU_ADR_TICKERS] Vinci (OTC ADR)
    "STM": {"lists": {"EU_ADR_TICKERS": 32, "INTL_TIER1": 1}, "sectors": {}},  # [EU_ADR_TICKERS] STMicroelectronics (NYSE, US-listing)
    "AIVAF": {"lists": {"EU_ADR_TICKERS": 33}, "sectors": {}},  # [EU_ADR_TICKERS] Air Liquide (OTC ADR)
    # [EU_ADR_TICKERS] ── Niederlande ───────────────────────────────────────────────────────────
    # [INTL_TIER1] Europa — Technologie (ADR/US-listed)
    "ASML": {"lists": {"EU_ADR_TICKERS": 34, "INTL_TIER1": 0}, "sectors": {"SEMIS": 9}},  # [EU_ADR_TICKERS] ASML (NASDAQ, primär US-listing) | [INTL_TIER1] v4.3: INFN delistet (Nokia-Übernahme 2025)
    "PHG": {"lists": {"EU_ADR_TICKERS": 35}, "sectors": {}},  # [EU_ADR_TICKERS] Philips (NYSE ADR)
    "ING": {"lists": {"EU_ADR_TICKERS": 36, "INTL_TIER1": 26}, "sectors": {}},  # [EU_ADR_TICKERS] ING Groep (NYSE ADR, liquid Options)
    "HEINY": {"lists": {"EU_ADR_TICKERS": 37}, "sectors": {}},  # [EU_ADR_TICKERS] Heineken (OTC ADR)
    # [EU_ADR_TICKERS] ── Schweiz ───────────────────────────────────────────────────────────────
    "NVS": {"lists": {"EU_ADR_TICKERS": 38, "INTL_TIER1": 8}, "sectors": {}},  # [EU_ADR_TICKERS] Novartis (NYSE ADR, liquid Options)
    "RHHBY": {"lists": {"EU_ADR_TICKERS": 39, "INTL_TIER1": 9}, "sectors": {"GLPONE": 10}},  # [EU_ADR_TICKERS] Roche (OTC ADR)
    "NSRGY": {"lists": {"EU_ADR_TICKERS": 40}, "sectors": {}},  # [EU_ADR_TICKERS] Nestle (OTC ADR)
    "ABB": {"lists": {"EU_ADR_TICKERS": 41, "INTL_TIER1": 39}, "sectors": {"ROBOTICS": 1}},  # [EU_ADR_TICKERS] ABB (NYSE, US-listing)
    # [EU_ADR_TICKERS] CFR/ZURN entfernt — schlechte OTC-Liquidität (CFRUY bereits in Liste)
    # [EU_ADR_TICKERS] ── UK ────────────────────────────────────────────────────────────────────
    "AZN": {"lists": {"EU_ADR_TICKERS": 42, "INTL_TIER1": 7}, "sectors": {"BIOTECH": 11, "GLPONE": 6}},  # [EU_ADR_TICKERS] AstraZeneca (NASDAQ, primär US-listing, liquid Options!)
    # [INTL_TIER1] Europa — Energie & Rohstoffe (ADR)
    "SHEL": {"lists": {"EU_ADR_TICKERS": 43, "INTL_TIER1": 14}, "sectors": {}},  # [EU_ADR_TICKERS] Shell (NYSE ADR, liquid Options)
    "BP": {"lists": {"EU_ADR_TICKERS": 44, "INTL_TIER1": 15}, "sectors": {}},  # [EU_ADR_TICKERS] BP (NYSE ADR, liquid Options)
    "GSK": {"lists": {"EU_ADR_TICKERS": 45, "INTL_TIER1": 11}, "sectors": {}},  # [EU_ADR_TICKERS] GSK (NYSE ADR, liquid Options)
    "RIO": {"lists": {"EU_ADR_TICKERS": 46, "INTL_TIER1": 21}, "sectors": {"MATERIALS": 9}},  # [EU_ADR_TICKERS] Rio Tinto (NYSE ADR, liquid Options)
    "HSBC": {"lists": {"EU_ADR_TICKERS": 47, "INTL_TIER1": 28}, "sectors": {}},  # [EU_ADR_TICKERS] HSBC (NYSE ADR, liquid Options)
    "VOD": {"lists": {"EU_ADR_TICKERS": 48}, "sectors": {}},  # [EU_ADR_TICKERS] Vodafone (NASDAQ ADR)
    "UL": {"lists": {"EU_ADR_TICKERS": 49}, "sectors": {}},  # [EU_ADR_TICKERS] Unilever (NYSE ADR)
    "DEO": {"lists": {"EU_ADR_TICKERS": 50}, "sectors": {}},  # [EU_ADR_TICKERS] Diageo (NYSE ADR)
    "BTI": {"lists": {"EU_ADR_TICKERS": 51}, "sectors": {}},  # [EU_ADR_TICKERS] British American Tobacco (NYSE ADR)
    "NGG": {"lists": {"EU_ADR_TICKERS": 52}, "sectors": {}},  # [EU_ADR_TICKERS] National Grid (NYSE ADR)
    # [EU_ADR_TICKERS] ── Skandinavien ──────────────────────────────────────────────────────────
    # [INTL_TIER1] Europa — Healthcare (ADR)
    "NVO": {"lists": {"EU_ADR_TICKERS": 53, "INTL_TIER1": 6}, "sectors": {"BIOTECH": 10, "GLPONE": 1, "WHEEL_STOCKS": 6}},  # [EU_ADR_TICKERS] Novo Nordisk (NYSE ADR, SEHR liquid Options!)
    "ERIC": {"lists": {"EU_ADR_TICKERS": 54, "INTL_TIER1": 2}, "sectors": {}},  # [EU_ADR_TICKERS] Ericsson (NASDAQ ADR)
    "NOK": {"lists": {"EU_ADR_TICKERS": 55, "INTL_TIER1": 3}, "sectors": {}},  # [EU_ADR_TICKERS] Nokia (NYSE ADR)
    "VOLVY": {"lists": {"EU_ADR_TICKERS": 56, "INTL_TIER1": 38}, "sectors": {}},  # [EU_ADR_TICKERS] Volvo (OTC ADR)
    "ATLKY": {"lists": {"EU_ADR_TICKERS": 57, "INTL_TIER1": 37}, "sectors": {}},  # [EU_ADR_TICKERS] Atlas Copco (OTC ADR)
    # [EU_ADR_TICKERS] ── Sonstige Europa ───────────────────────────────────────────────────────
    "E": {"lists": {"EU_ADR_TICKERS": 58, "INTL_TIER1": 18}, "sectors": {}},  # [EU_ADR_TICKERS] Eni (NYSE ADR)
    "RACE": {"lists": {"EU_ADR_TICKERS": 59}, "sectors": {"LUXURY_EU": 7}},  # [EU_ADR_TICKERS] Ferrari (NYSE, primär US-listing, liquid Options!)
    "SNY": {"lists": {"EU_ADR_TICKERS": 60, "INTL_TIER1": 10}, "sectors": {"GLPONE": 7}},  # [EU_ADR_TICKERS] Sanofi (NASDAQ ADR)
    # [EU_ADR_TICKERS] ── Defensive Ergänzungen (Gemini-Empfehlung: Sektorparität) ─────────────
    "NUE": {"lists": {"EU_ADR_TICKERS": 61}, "sectors": {}},  # [EU_ADR_TICKERS] Nucor (Industrials/Materials — S&P500)
    "URI": {"lists": {"EU_ADR_TICKERS": 63}, "sectors": {}},  # [EU_ADR_TICKERS] United Rentals (Industrials — liquid Options)
    "WM": {"lists": {"EU_ADR_TICKERS": 64}, "sectors": {}},  # [EU_ADR_TICKERS] Waste Management (Defensive — liquid Options)
    "RSG": {"lists": {"EU_ADR_TICKERS": 65}, "sectors": {}},  # [EU_ADR_TICKERS] Republic Services (Defensive)
    "VMC": {"lists": {"EU_ADR_TICKERS": 66}, "sectors": {}},  # [EU_ADR_TICKERS] Vulcan Materials (Materials)
    "MLM": {"lists": {"EU_ADR_TICKERS": 67}, "sectors": {}},  # [EU_ADR_TICKERS] Martin Marietta (Materials)
    "ALAB": {"lists": {"BEAR_US_TICKERS": 3}, "sectors": {"AI_TECH": 11}},
    "DASH": {"lists": {"BEAR_US_TICKERS": 30}, "sectors": {}},
    "GME": {"lists": {"BEAR_US_TICKERS": 38}, "sectors": {}},
    "AMD": {"lists": {"BEAR_US_TICKERS": 45}, "sectors": {"AI_TECH": 1, "SEMIS": 1, "PICKS_SHOVELS": 1}},
    "BAYN.DE": {"lists": {"BEAR_DE_EU_TICKERS": 0}, "sectors": {}},
    "VOW3.DE": {"lists": {"BEAR_DE_EU_TICKERS": 1}, "sectors": {}},
    "BMW.DE": {"lists": {"BEAR_DE_EU_TICKERS": 2}, "sectors": {}},
    "MBG.DE": {"lists": {"BEAR_DE_EU_TICKERS": 3}, "sectors": {}},
    "CON.DE": {"lists": {"BEAR_DE_EU_TICKERS": 4}, "sectors": {}},
    "DHER.DE": {"lists": {"BEAR_DE_EU_TICKERS": 5}, "sectors": {}},
    "ZAL.DE": {"lists": {"BEAR_DE_EU_TICKERS": 6}, "sectors": {}},
    "VNA.DE": {"lists": {"BEAR_DE_EU_TICKERS": 7}, "sectors": {}},
    "LEG.DE": {"lists": {"BEAR_DE_EU_TICKERS": 8}, "sectors": {}},
    "TAG.DE": {"lists": {"BEAR_DE_EU_TICKERS": 9}, "sectors": {}},
    "1COV.DE": {"lists": {"BEAR_DE_EU_TICKERS": 10}, "sectors": {}},
    "EVT.DE": {"lists": {"BEAR_DE_EU_TICKERS": 11}, "sectors": {}},
    "SRT.DE": {"lists": {"BEAR_DE_EU_TICKERS": 12}, "sectors": {}},
    "NDX1.DE": {"lists": {"BEAR_DE_EU_TICKERS": 13}, "sectors": {}},
    "AIXA.DE": {"lists": {"BEAR_DE_EU_TICKERS": 14}, "sectors": {}},
    "WAF.DE": {"lists": {"BEAR_DE_EU_TICKERS": 15}, "sectors": {}},
    "IFX.DE": {"lists": {"BEAR_DE_EU_TICKERS": 16}, "sectors": {}},
    "STLAM.MI": {"lists": {"BEAR_DE_EU_TICKERS": 17}, "sectors": {}},
    "RNO.PA": {"lists": {"BEAR_DE_EU_TICKERS": 18}, "sectors": {}},
    "VOD.L": {"lists": {"BEAR_DE_EU_TICKERS": 19}, "sectors": {}},
    "BT-A.L": {"lists": {"BEAR_DE_EU_TICKERS": 20}, "sectors": {}},
    "TEF.MC": {"lists": {"BEAR_DE_EU_TICKERS": 21}, "sectors": {}},
    "UCB.BR": {"lists": {"BEAR_DE_EU_TICKERS": 22}, "sectors": {}},
    "GLPG.BR": {"lists": {"BEAR_DE_EU_TICKERS": 23}, "sectors": {}},
    "ARND.DE": {"lists": {"BEAR_DE_EU_TICKERS": 24}, "sectors": {}},
    "WDP.BR": {"lists": {"BEAR_DE_EU_TICKERS": 25}, "sectors": {}},
    "RWE.DE": {"lists": {"BEAR_DE_EU_TICKERS": 26}, "sectors": {}},
    "ENEL.MI": {"lists": {"BEAR_DE_EU_TICKERS": 27}, "sectors": {}},
    "EZJ.L": {"lists": {"BEAR_DE_EU_TICKERS": 28}, "sectors": {}},
    "IAG.L": {"lists": {"BEAR_DE_EU_TICKERS": 29}, "sectors": {}},
    "DTE.DE": {"lists": {"BEAR_DE_EU_TICKERS": 30}, "sectors": {}},
    "GLEN.L": {"lists": {"BEAR_DE_EU_TICKERS": 31}, "sectors": {}},
    "AAL.L": {"lists": {"BEAR_DE_EU_TICKERS": 32}, "sectors": {}},
    "KEYS": {"lists": {"INTL_TIER1": 5}, "sectors": {"ROBOTICS": 7}},
    "NVCR": {"lists": {"INTL_TIER1": 13}, "sectors": {}},
    "ENLAY": {"lists": {"INTL_TIER1": 17}, "sectors": {}},
    "ENGIY": {"lists": {"INTL_TIER1": 19}, "sectors": {}},
    "SQM": {"lists": {"INTL_TIER1": 20}, "sectors": {"MATERIALS": 7}},
    # [INTL_TIER1] Australien (ADR)
    "BHP": {"lists": {"INTL_TIER1": 22}, "sectors": {"MATERIALS": 8}},  # [INTL_TIER1] v4.3: ORG hat kein US-Listing → Heimatbörse ASX
    # [INTL_TIER1] Brasilien (ADR)
    "VALE": {"lists": {"INTL_TIER1": 23}, "sectors": {"EM_GROWTH": 4, "MATERIALS": 6}},
    "SCCO": {"lists": {"INTL_TIER1": 24}, "sectors": {"MATERIALS": 5}},
    # [INTL_TIER1] Europa — Finanzen (ADR)
    "UBS": {"lists": {"INTL_TIER1": 25}, "sectors": {}},
    "BCS": {"lists": {"INTL_TIER1": 27}, "sectors": {}},
    "BURBY": {"lists": {"INTL_TIER1": 34}, "sectors": {"LUXURY_EU": 6}},
    "DSDVY": {"lists": {"INTL_TIER1": 40}, "sectors": {}},
    # [INTL_TIER1] Europa — Defence (DIREKT .DE/.PA — OTC-ADRs wie RHTRY haben schlechten API-Feed)
    # [INTL_TIER1] NEU (01.07.2026): Rheinmetall, BAE Systems, Saab, Thales, Leonardo über
    # [INTL_TIER1] Heimatboersen-Suffix statt OTC-ADR — stabiler yfinance-Feed via Yahoo .DE/.PA/.ST
    "RHM.DE": {"lists": {"INTL_TIER1": 41}, "sectors": {"DEFENSE": 22}},  # [INTL_TIER1] Rheinmetall AG (XETRA) — kein stabiler OTC-ADR verfügbar
    "BA.L": {"lists": {"INTL_TIER1": 42}, "sectors": {"DEFENSE": 23}},  # [INTL_TIER1] BAE Systems (London) — BAESY OTC zu dünn
    "SAAB-B.ST": {"lists": {"INTL_TIER1": 43}, "sectors": {"DEFENSE": 24}},  # [INTL_TIER1] Saab AB (Stockholm) — SAABY OTC zu dünn
    "HO.PA": {"lists": {"INTL_TIER1": 44}, "sectors": {"DEFENSE": 25}},  # [INTL_TIER1] Thales SA (Euronext Paris) — THLLY OTC zu dünn
    "LDO.MI": {"lists": {"INTL_TIER1": 45}, "sectors": {"DEFENSE": 26}},  # [INTL_TIER1] Leonardo SpA (Milano)
    "SONY": {"lists": {"INTL_TIER1": 48}, "sectors": {"JAPAN_TECH": 1}},
    "NTT": {"lists": {"INTL_TIER1": 49}, "sectors": {}},
    "MUFG": {"lists": {"INTL_TIER1": 50}, "sectors": {}},
    "SMFG": {"lists": {"INTL_TIER1": 51}, "sectors": {}},
    "MFG": {"lists": {"INTL_TIER1": 52}, "sectors": {}},
    "NTDOY": {"lists": {"INTL_TIER1": 53}, "sectors": {"JAPAN_TECH": 2}},
    "KYOCY": {"lists": {"INTL_TIER1": 54}, "sectors": {"JAPAN_TECH": 3}},
    "FANUY": {"lists": {"INTL_TIER1": 55}, "sectors": {"ROBOTICS": 2, "JAPAN_TECH": 4}},
    "CCOEY": {"lists": {"INTL_TIER1": 56}, "sectors": {"JAPAN_TECH": 5}},
    "ITOCY": {"lists": {"INTL_TIER1": 57}, "sectors": {}},
    "MARUY": {"lists": {"INTL_TIER1": 58}, "sectors": {}},
    # [INTL_TIER1] Suedkorea
    "SSNLF": {"lists": {"INTL_TIER1": 59}, "sectors": {}},
    "MX": {"lists": {"INTL_TIER1": 60}, "sectors": {}},
    # [INTL_TIER1] Taiwan
    "TSM": {"lists": {"INTL_TIER1": 61}, "sectors": {"PICKS_SHOVELS": 8, "EM_GROWTH": 0}},
    "TCEHY": {"lists": {"INTL_TIER1": 66}, "sectors": {}},
    "BYDDY": {"lists": {"INTL_TIER1": 67}, "sectors": {}},
    # [INTL_TIER1] Indien (ADR)
    "INFY": {"lists": {"INTL_TIER1": 71}, "sectors": {"EM_GROWTH": 3}},  # [INTL_TIER1] v4.3: VEDL + TTM (ADRs delistet)
    "WIT": {"lists": {"INTL_TIER1": 72}, "sectors": {}},
    "HDB": {"lists": {"INTL_TIER1": 73}, "sectors": {}},
    "IBN": {"lists": {"INTL_TIER1": 74}, "sectors": {}},
    "RDY": {"lists": {"INTL_TIER1": 75}, "sectors": {}},
    "CNQ": {"lists": {"INTL_TIER1": 77}, "sectors": {}},
    "SU": {"lists": {"INTL_TIER1": 78}, "sectors": {}},
    "CNI": {"lists": {"INTL_TIER1": 79}, "sectors": {}},
    "CP": {"lists": {"INTL_TIER1": 80}, "sectors": {}},
    "TD": {"lists": {"INTL_TIER1": 81}, "sectors": {}},
    "RY": {"lists": {"INTL_TIER1": 82}, "sectors": {}},
    "BNS": {"lists": {"INTL_TIER1": 83}, "sectors": {}},
    "ENB": {"lists": {"INTL_TIER1": 84}, "sectors": {}},
    "TRP": {"lists": {"INTL_TIER1": 85}, "sectors": {}},
    "NTR": {"lists": {"INTL_TIER1": 86}, "sectors": {"AGRICULTURE": 3}},
    "CCJ": {"lists": {"INTL_TIER1": 87}, "sectors": {"MATERIALS": 4}},
    "WDS": {"lists": {"INTL_TIER1": 90}, "sectors": {}},
    "ORG.AX": {"lists": {"INTL_TIER1": 91}, "sectors": {}},
    "PBR": {"lists": {"INTL_TIER1": 93}, "sectors": {"WHEEL_STOCKS": 4}},
    "ITUB": {"lists": {"INTL_TIER1": 94}, "sectors": {"EM_GROWTH": 5}},
    "BBD": {"lists": {"INTL_TIER1": 95}, "sectors": {}},
    "ABEV": {"lists": {"INTL_TIER1": 96}, "sectors": {}},
    "BRKM": {"lists": {"INTL_TIER1": 97}, "sectors": {}},
    # [INTL_TIER1] Mexiko/Latam
    "AMX": {"lists": {"INTL_TIER1": 98}, "sectors": {}},  # [INTL_TIER1] v4.3: Femsa-NYSE-Symbol ist FMX (FMXB ungültig)
    "FMX": {"lists": {"INTL_TIER1": 99}, "sectors": {}},
    # [INTL_TIER1] Suedafrika / EM Sonstiges
    "PROSY": {"lists": {"INTL_TIER1": 100}, "sectors": {}},  # [INTL_TIER1] v4.3: Prosus-OTC-Symbol ist PROSY (PROSSY ungültig)
    "NPSNY": {"lists": {"INTL_TIER1": 101}, "sectors": {}},
    # [INTL_TIER1] Israel Tech
    "CHKP": {"lists": {"INTL_TIER1": 102}, "sectors": {}},
    "NICE": {"lists": {"INTL_TIER1": 103}, "sectors": {}},
    "CYBR": {"lists": {"INTL_TIER1": 104}, "sectors": {}},
    "WIX": {"lists": {"INTL_TIER1": 105}, "sectors": {}},
    "MNDY": {"lists": {"INTL_TIER1": 106}, "sectors": {}},
    "GLBE": {"lists": {"INTL_TIER1": 107}, "sectors": {}},
    "SPY": {"lists": {"SECTOR_ETFS_BROAD": 0}, "sectors": {}},  # [SECTOR_ETFS_BROAD] US Broad (RSP = Equal-Weight S&P für Breadth)
    "QQQ": {"lists": {"SECTOR_ETFS_BROAD": 1}, "sectors": {}},
    "IWM": {"lists": {"SECTOR_ETFS_BROAD": 2}, "sectors": {}},
    "RSP": {"lists": {"SECTOR_ETFS_BROAD": 3}, "sectors": {}},
    "DIA": {"lists": {"SECTOR_ETFS_BROAD": 4}, "sectors": {}},
    "VTI": {"lists": {"SECTOR_ETFS_BROAD": 5}, "sectors": {}},
    "MDY": {"lists": {"SECTOR_ETFS_BROAD": 6}, "sectors": {}},
    "IJR": {"lists": {"SECTOR_ETFS_BROAD": 7}, "sectors": {}},
    "VEA": {"lists": {"SECTOR_ETFS_BROAD": 8}, "sectors": {}},  # [SECTOR_ETFS_BROAD] Ex-US Broad
    "VWO": {"lists": {"SECTOR_ETFS_BROAD": 9}, "sectors": {}},
    "EFA": {"lists": {"SECTOR_ETFS_BROAD": 10}, "sectors": {}},
    "EEM": {"lists": {"SECTOR_ETFS_BROAD": 11}, "sectors": {}},
    "IEFA": {"lists": {"SECTOR_ETFS_BROAD": 12}, "sectors": {}},
    "IEMG": {"lists": {"SECTOR_ETFS_BROAD": 13}, "sectors": {}},
    "ACWI": {"lists": {"SECTOR_ETFS_BROAD": 14}, "sectors": {}},  # [SECTOR_ETFS_BROAD] World
    "VT": {"lists": {"SECTOR_ETFS_BROAD": 15}, "sectors": {}},
    "URTH": {"lists": {"SECTOR_ETFS_BROAD": 16}, "sectors": {}},
    # [SECTOR_ETFS_US] Technologie
    "XLK": {"lists": {"SECTOR_ETFS_US": 0, "RS_SECTOR_ETFS": 0}, "sectors": {}},
    "VGT": {"lists": {"SECTOR_ETFS_US": 1}, "sectors": {}},
    "FTEC": {"lists": {"SECTOR_ETFS_US": 2}, "sectors": {}},
    "IYW": {"lists": {"SECTOR_ETFS_US": 3}, "sectors": {}},
    "QTEC": {"lists": {"SECTOR_ETFS_US": 4}, "sectors": {}},
    # [SECTOR_ETFS_US] Semiconductors
    "SMH": {"lists": {"SECTOR_ETFS_US": 5, "RS_SECTOR_ETFS": 11}, "sectors": {}},
    "SOXX": {"lists": {"SECTOR_ETFS_US": 6, "RS_SECTOR_ETFS": 12}, "sectors": {}},
    "SOXQ": {"lists": {"SECTOR_ETFS_US": 7}, "sectors": {}},
    "USD": {"lists": {"SECTOR_ETFS_US": 8}, "sectors": {}},
    # [SECTOR_ETFS_US] Software / Cyber
    "IGV": {"lists": {"SECTOR_ETFS_US": 9}, "sectors": {}},
    "BUG": {"lists": {"SECTOR_ETFS_US": 10}, "sectors": {}},
    "CIBR": {"lists": {"SECTOR_ETFS_US": 11, "RS_SECTOR_ETFS": 25}, "sectors": {}},
    # [RS_SECTOR_ETFS] v4.2 (02.07.2026): RS-Referenzen der neuen Watchlists —
    # [RS_SECTOR_ETFS] XLB (Materials) und ITA/XBI bereits oben vorhanden
    "HACK": {"lists": {"SECTOR_ETFS_US": 12, "RS_SECTOR_ETFS": 24}, "sectors": {}},  # [RS_SECTOR_ETFS] Cybersecurity
    "WCLD": {"lists": {"SECTOR_ETFS_US": 13}, "sectors": {}},
    # [SECTOR_ETFS_US] Financials
    "XLF": {"lists": {"SECTOR_ETFS_US": 14, "RS_SECTOR_ETFS": 1}, "sectors": {}},
    "VFH": {"lists": {"SECTOR_ETFS_US": 15}, "sectors": {}},
    "IYF": {"lists": {"SECTOR_ETFS_US": 16}, "sectors": {}},
    "KRE": {"lists": {"SECTOR_ETFS_US": 17}, "sectors": {}},
    "KBE": {"lists": {"SECTOR_ETFS_US": 18}, "sectors": {}},
    # [SECTOR_ETFS_US] Healthcare
    "XLV": {"lists": {"SECTOR_ETFS_US": 19, "RS_SECTOR_ETFS": 3}, "sectors": {}},
    "VHT": {"lists": {"SECTOR_ETFS_US": 20}, "sectors": {}},
    "IYH": {"lists": {"SECTOR_ETFS_US": 21}, "sectors": {}},
    # [SECTOR_ETFS_US] Biotech / Pharma
    "XBI": {"lists": {"SECTOR_ETFS_US": 22, "RS_SECTOR_ETFS": 14}, "sectors": {}},
    "IBB": {"lists": {"SECTOR_ETFS_US": 23, "RS_SECTOR_ETFS": 13}, "sectors": {}},
    "ARKG": {"lists": {"SECTOR_ETFS_US": 24, "RS_SECTOR_ETFS": 29}, "sectors": {"BIOTECH": 7}},  # [RS_SECTOR_ETFS] Biotech/Genomics (BIOTECH_LONGEVITY)
    "PJP": {"lists": {"SECTOR_ETFS_US": 25}, "sectors": {}},
    "BBP": {"lists": {"SECTOR_ETFS_US": 26}, "sectors": {}},
    # [SECTOR_ETFS_US] Energie
    "XLE": {"lists": {"SECTOR_ETFS_US": 27, "RS_SECTOR_ETFS": 2}, "sectors": {}},
    "VDE": {"lists": {"SECTOR_ETFS_US": 28}, "sectors": {}},
    "IYE": {"lists": {"SECTOR_ETFS_US": 29}, "sectors": {}},
    "OIH": {"lists": {"SECTOR_ETFS_US": 30}, "sectors": {}},
    "XOP": {"lists": {"SECTOR_ETFS_US": 31}, "sectors": {}},
    # [SECTOR_ETFS_US] Industrials
    "XLI": {"lists": {"SECTOR_ETFS_US": 32, "RS_SECTOR_ETFS": 4}, "sectors": {}},
    "VIS": {"lists": {"SECTOR_ETFS_US": 33}, "sectors": {}},
    "IYJ": {"lists": {"SECTOR_ETFS_US": 34}, "sectors": {}},
    # [SECTOR_ETFS_US] Defense & Aerospace (DFEN bewusst NICHT aufgenommen -- 24.08.2026,
    # [SECTOR_ETFS_US] Axel-Entscheidung: 3x taeglich gehebelter Fonds verzerrt Leaderboards/
    # [SECTOR_ETFS_US] technische Scores, widerspricht UIQ-Leitprinzip Fehler-Reduzierer)
    "ITA": {"lists": {"SECTOR_ETFS_US": 35, "RS_SECTOR_ETFS": 17}, "sectors": {}},
    # [RS_SECTOR_ETFS] Defence & Aerospace (01.07.2026 ergänzt; DFEN am 24.08.2026 wieder
    # [RS_SECTOR_ETFS] entfernt -- 3x taeglich gehebelt, verzerrt den RS-Vergleich, s. Kommentar
    # [RS_SECTOR_ETFS] bei SECTOR_ETFS_US)
    "XAR": {"lists": {"SECTOR_ETFS_US": 36, "RS_SECTOR_ETFS": 20}, "sectors": {}},
    "PPA": {"lists": {"SECTOR_ETFS_US": 37, "RS_SECTOR_ETFS": 21}, "sectors": {}},
    # [SECTOR_ETFS_US] Nuclear / Uranium / Space (v4.2, 02.07.2026 — RS-Referenz neue Watchlists)
    "NLR": {"lists": {"SECTOR_ETFS_US": 38, "RS_SECTOR_ETFS": 26}, "sectors": {}},  # [RS_SECTOR_ETFS] Nuclear Energy / Uran
    "URA": {"lists": {"SECTOR_ETFS_US": 39, "RS_SECTOR_ETFS": 27}, "sectors": {}},
    "ARKX": {"lists": {"SECTOR_ETFS_US": 40, "RS_SECTOR_ETFS": 28}, "sectors": {}},  # [RS_SECTOR_ETFS] Space
    # [SECTOR_ETFS_US] Consumer Discretionary
    "XLY": {"lists": {"SECTOR_ETFS_US": 41, "RS_SECTOR_ETFS": 5}, "sectors": {}},
    "VCR": {"lists": {"SECTOR_ETFS_US": 42}, "sectors": {}},
    "IYC": {"lists": {"SECTOR_ETFS_US": 43}, "sectors": {}},
    # [SECTOR_ETFS_US] Consumer Staples
    "XLP": {"lists": {"SECTOR_ETFS_US": 44, "RS_SECTOR_ETFS": 6}, "sectors": {}},
    "VDC": {"lists": {"SECTOR_ETFS_US": 45}, "sectors": {}},
    "IYK": {"lists": {"SECTOR_ETFS_US": 46}, "sectors": {}},
    # [SECTOR_ETFS_US] Growth vs. Value (17.08.2026, Axel-Anfrage — Konjunktur-Indikatoren):
    # [SECTOR_ETFS_US] IWF/IWD = iShares Russell 1000 Growth/Value, Standard-Paar fuer diese
    # [SECTOR_ETFS_US] Rotation, hochliquide. Wird fuer calc_growth_value_signal() benoetigt.
    "IWF": {"lists": {"SECTOR_ETFS_US": 47}, "sectors": {}},
    "IWD": {"lists": {"SECTOR_ETFS_US": 48}, "sectors": {}},
    # [SECTOR_ETFS_US] Utilities
    "XLU": {"lists": {"SECTOR_ETFS_US": 49, "RS_SECTOR_ETFS": 7}, "sectors": {}},
    "VPU": {"lists": {"SECTOR_ETFS_US": 50}, "sectors": {}},
    "IDU": {"lists": {"SECTOR_ETFS_US": 51}, "sectors": {}},
    # [SECTOR_ETFS_US] Real Estate
    "XLRE": {"lists": {"SECTOR_ETFS_US": 52, "RS_SECTOR_ETFS": 8}, "sectors": {}},
    "VNQ": {"lists": {"SECTOR_ETFS_US": 53, "RS_SECTOR_ETFS": 19}, "sectors": {}},
    "IYR": {"lists": {"SECTOR_ETFS_US": 54}, "sectors": {}},
    "REET": {"lists": {"SECTOR_ETFS_US": 55}, "sectors": {}},
    # [SECTOR_ETFS_US] Materials
    "XLB": {"lists": {"SECTOR_ETFS_US": 56, "RS_SECTOR_ETFS": 9}, "sectors": {}},
    "VAW": {"lists": {"SECTOR_ETFS_US": 57}, "sectors": {}},
    "IYM": {"lists": {"SECTOR_ETFS_US": 58}, "sectors": {}},
    # [SECTOR_ETFS_US] Communication
    "XLC": {"lists": {"SECTOR_ETFS_US": 59, "RS_SECTOR_ETFS": 10}, "sectors": {}},
    "VOX": {"lists": {"SECTOR_ETFS_US": 60}, "sectors": {}},
    "IYZ": {"lists": {"SECTOR_ETFS_US": 61}, "sectors": {}},
    # [SECTOR_ETFS_US] Clean Energy / ESG
    "ICLN": {"lists": {"SECTOR_ETFS_US": 62, "RS_SECTOR_ETFS": 18}, "sectors": {"CLEAN_ENERGY": 9}},
    "QCLN": {"lists": {"SECTOR_ETFS_US": 63}, "sectors": {"CLEAN_ENERGY": 10}},
    "CNRG": {"lists": {"SECTOR_ETFS_US": 64}, "sectors": {}},
    "ACES": {"lists": {"SECTOR_ETFS_US": 65}, "sectors": {}},
    "ESGU": {"lists": {"SECTOR_ETFS_US": 66}, "sectors": {}},
    # [SECTOR_ETFS_US] AI & Robotics / Innovation
    # [SECTOR_ETFS_US] v4.2-Fix: ARKK stand seit v4.0 in RS_SECTOR_ETFS, fehlte aber im
    # [SECTOR_ETFS_US] Download-Universum → RS-Berechnung wurde nachts still übersprungen
    "BOTZ": {"lists": {"SECTOR_ETFS_US": 67, "RS_SECTOR_ETFS": 16}, "sectors": {"ROBOTICS": 4}},
    "ROBO": {"lists": {"SECTOR_ETFS_US": 68, "RS_SECTOR_ETFS": 23}, "sectors": {"ROBOTICS": 5}},
    # [RS_SECTOR_ETFS] Robotics & AI-Hardware (01.07.2026 ergänzt)
    "IRBO": {"lists": {"SECTOR_ETFS_US": 69, "RS_SECTOR_ETFS": 22}, "sectors": {"ROBOTICS": 3}},
    "AIQ": {"lists": {"SECTOR_ETFS_US": 70}, "sectors": {}},
    "THNQ": {"lists": {"SECTOR_ETFS_US": 71}, "sectors": {}},
    "ARKK": {"lists": {"SECTOR_ETFS_US": 72, "RS_SECTOR_ETFS": 15}, "sectors": {}},
    # [SECTOR_ETFS_US] Crypto-related
    "BITO": {"lists": {"SECTOR_ETFS_US": 73}, "sectors": {}},
    "GBTC": {"lists": {"SECTOR_ETFS_US": 74}, "sectors": {}},
    "ETHA": {"lists": {"SECTOR_ETFS_US": 75}, "sectors": {}},
    # [SECTOR_ETFS_US] Commodities
    "GLD": {"lists": {"SECTOR_ETFS_US": 76}, "sectors": {}},
    "IAU": {"lists": {"SECTOR_ETFS_US": 77}, "sectors": {}},
    "GLDM": {"lists": {"SECTOR_ETFS_US": 78}, "sectors": {}},
    "SLV": {"lists": {"SECTOR_ETFS_US": 79}, "sectors": {}},
    "PPLT": {"lists": {"SECTOR_ETFS_US": 80}, "sectors": {}},
    "PDBC": {"lists": {"SECTOR_ETFS_US": 81}, "sectors": {}},
    "DJP": {"lists": {"SECTOR_ETFS_US": 82}, "sectors": {}},
    "USO": {"lists": {"SECTOR_ETFS_US": 83}, "sectors": {}},
    "UNG": {"lists": {"SECTOR_ETFS_US": 84}, "sectors": {}},
    "CORN": {"lists": {"SECTOR_ETFS_US": 85}, "sectors": {}},
    # [SECTOR_ETFS_US] Bonds
    "TLT": {"lists": {"SECTOR_ETFS_US": 86}, "sectors": {}},
    "IEF": {"lists": {"SECTOR_ETFS_US": 87}, "sectors": {}},
    "SHY": {"lists": {"SECTOR_ETFS_US": 88}, "sectors": {}},
    "HYG": {"lists": {"SECTOR_ETFS_US": 89}, "sectors": {}},
    "LQD": {"lists": {"SECTOR_ETFS_US": 90}, "sectors": {}},
    "EMB": {"lists": {"SECTOR_ETFS_US": 91}, "sectors": {}},
    "BND": {"lists": {"SECTOR_ETFS_US": 92}, "sectors": {}},
    "VCIT": {"lists": {"SECTOR_ETFS_US": 93}, "sectors": {}},
    "VCSH": {"lists": {"SECTOR_ETFS_US": 94}, "sectors": {}},
    "TIPS": {"lists": {"SECTOR_ETFS_US": 95}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Europa
    # [RS_SECTOR_ETFS] Ex-US RS
    "EZU": {"lists": {"SECTOR_ETFS_EXUS": 0, "RS_SECTOR_ETFS": 30}, "sectors": {}},  # [SECTOR_ETFS_EXUS] v4.3: EWF existiert nicht (Frankreich = EWQ)
    "VGK": {"lists": {"SECTOR_ETFS_EXUS": 1}, "sectors": {}},
    "IEUR": {"lists": {"SECTOR_ETFS_EXUS": 2}, "sectors": {}},
    "FEZ": {"lists": {"SECTOR_ETFS_EXUS": 3}, "sectors": {}},
    "EWG": {"lists": {"SECTOR_ETFS_EXUS": 4, "RS_SECTOR_ETFS": 32}, "sectors": {}},
    "EWU": {"lists": {"SECTOR_ETFS_EXUS": 5}, "sectors": {}},
    "EWI": {"lists": {"SECTOR_ETFS_EXUS": 6}, "sectors": {}},
    "EWQ": {"lists": {"SECTOR_ETFS_EXUS": 7}, "sectors": {}},
    "EWP": {"lists": {"SECTOR_ETFS_EXUS": 8}, "sectors": {}},
    "EWN": {"lists": {"SECTOR_ETFS_EXUS": 9}, "sectors": {}},
    "EWD": {"lists": {"SECTOR_ETFS_EXUS": 10}, "sectors": {}},
    "EWL": {"lists": {"SECTOR_ETFS_EXUS": 11}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Asien Developed
    "EWJ": {"lists": {"SECTOR_ETFS_EXUS": 12, "RS_SECTOR_ETFS": 31}, "sectors": {}},
    "EWA": {"lists": {"SECTOR_ETFS_EXUS": 13}, "sectors": {}},
    "EWH": {"lists": {"SECTOR_ETFS_EXUS": 14}, "sectors": {}},
    "EWS": {"lists": {"SECTOR_ETFS_EXUS": 15}, "sectors": {}},
    "EWY": {"lists": {"SECTOR_ETFS_EXUS": 16, "RS_SECTOR_ETFS": 36}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Asien Emerging
    "FXI": {"lists": {"SECTOR_ETFS_EXUS": 17, "RS_SECTOR_ETFS": 33}, "sectors": {}},
    "KWEB": {"lists": {"SECTOR_ETFS_EXUS": 18}, "sectors": {}},
    "MCHI": {"lists": {"SECTOR_ETFS_EXUS": 19}, "sectors": {}},
    "EWT": {"lists": {"SECTOR_ETFS_EXUS": 20, "RS_SECTOR_ETFS": 37}, "sectors": {}},
    "INDA": {"lists": {"SECTOR_ETFS_EXUS": 21, "RS_SECTOR_ETFS": 34}, "sectors": {}},
    "VNM": {"lists": {"SECTOR_ETFS_EXUS": 22}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Latam
    "EWZ": {"lists": {"SECTOR_ETFS_EXUS": 23, "RS_SECTOR_ETFS": 35}, "sectors": {}},
    "EWW": {"lists": {"SECTOR_ETFS_EXUS": 24}, "sectors": {}},
    "ILF": {"lists": {"SECTOR_ETFS_EXUS": 25}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Sector Ex-US
    "IXUS": {"lists": {"SECTOR_ETFS_EXUS": 26}, "sectors": {}},
    "VXUS": {"lists": {"SECTOR_ETFS_EXUS": 27}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Ex-US Technologie
    "IFRA": {"lists": {"SECTOR_ETFS_EXUS": 28}, "sectors": {}},
    "IQLT": {"lists": {"SECTOR_ETFS_EXUS": 29}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Ex-US Energie
    "IXC": {"lists": {"SECTOR_ETFS_EXUS": 30}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Ex-US Healthcare
    "IXJ": {"lists": {"SECTOR_ETFS_EXUS": 31}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Ex-US Financials
    "IXG": {"lists": {"SECTOR_ETFS_EXUS": 32}, "sectors": {}},
    # [SECTOR_ETFS_EXUS] Schwellenlaender Sektoren
    "EMXC": {"lists": {"SECTOR_ETFS_EXUS": 33}, "sectors": {}},
    "EEMS": {"lists": {"SECTOR_ETFS_EXUS": 34}, "sectors": {}},
    "EMSG": {"lists": {"SECTOR_ETFS_EXUS": 35}, "sectors": {}},
    "BTC-USD": {"lists": {"CRYPTO_TICKERS": 0}, "sectors": {}},
    "ETH-USD": {"lists": {"CRYPTO_TICKERS": 1}, "sectors": {}},
    "SOL-USD": {"lists": {"CRYPTO_TICKERS": 2}, "sectors": {}},
    "BNB-USD": {"lists": {"CRYPTO_TICKERS": 3}, "sectors": {}},
    "XRP-USD": {"lists": {"CRYPTO_TICKERS": 4}, "sectors": {}},
    "ADA-USD": {"lists": {"CRYPTO_TICKERS": 5}, "sectors": {}},
    "AVAX-USD": {"lists": {"CRYPTO_TICKERS": 6}, "sectors": {}},
    "DOGE-USD": {"lists": {"CRYPTO_TICKERS": 7}, "sectors": {}},
    "DOT-USD": {"lists": {"CRYPTO_TICKERS": 8}, "sectors": {}},
    "POL-USD": {"lists": {"CRYPTO_TICKERS": 9}, "sectors": {}},
    "LINK-USD": {"lists": {"CRYPTO_TICKERS": 10}, "sectors": {}},
    "UNI-USD": {"lists": {"CRYPTO_TICKERS": 11}, "sectors": {}},
    "ATOM-USD": {"lists": {"CRYPTO_TICKERS": 12}, "sectors": {}},
    "LTC-USD": {"lists": {"CRYPTO_TICKERS": 13}, "sectors": {}},
    "BCH-USD": {"lists": {"CRYPTO_TICKERS": 14}, "sectors": {}},
    "CRDO": {"lists": {}, "sectors": {"AI_TECH": 10}},
    "HWM": {"lists": {}, "sectors": {"DEFENSE": 9, "SPACE": 2}},
    "HEI": {"lists": {}, "sectors": {"DEFENSE": 10}},
    "MOG-A": {"lists": {}, "sectors": {"DEFENSE": 14}},
    "TXT": {"lists": {}, "sectors": {"DEFENSE": 15}},
    "CW": {"lists": {}, "sectors": {"DEFENSE": 16}},
    "DRS": {"lists": {}, "sectors": {"DEFENSE": 17}},
    # [SECTOR_WATCHLISTS] v4.2 (02.07.2026): Gemini-Liste — Drohnen/Nuklear/Defense-Tech
    "AVAV": {"lists": {}, "sectors": {"DEFENSE": 18}},
    "LHX": {"lists": {}, "sectors": {"DEFENSE": 19}},
    "BWXT": {"lists": {}, "sectors": {"DEFENSE": 20}},
    "TER": {"lists": {}, "sectors": {"ROBOTICS": 8}},
    "AZTA": {"lists": {}, "sectors": {"ROBOTICS": 9}},
    "ONTO": {"lists": {}, "sectors": {"ROBOTICS": 10}},
    "NDSN": {"lists": {}, "sectors": {"ROBOTICS": 11}},
    # [SECTOR_WATCHLISTS] v4.2 (02.07.2026): Gemini-Liste — Automation/Vision/Chips (COGN→CGNX korrigiert)
    "SYM": {"lists": {}, "sectors": {"ROBOTICS": 12}},
    "MBLY": {"lists": {}, "sectors": {"ROBOTICS": 14}},
    "TDY": {"lists": {}, "sectors": {"ROBOTICS": 15}},
    "CGNX": {"lists": {}, "sectors": {"ROBOTICS": 16}},
    "PATH": {"lists": {}, "sectors": {"ROBOTICS": 17}},
    "ZBRA": {"lists": {}, "sectors": {"ROBOTICS": 18}},
    "NU": {"lists": {}, "sectors": {"FINTECH": 10, "EM_GROWTH": 6}},
    "STNE": {"lists": {}, "sectors": {"FINTECH": 11, "EM_GROWTH": 7}},
    "VRT": {"lists": {}, "sectors": {"PICKS_SHOVELS": 15}},
    "PWR": {"lists": {}, "sectors": {"PICKS_SHOVELS": 17, "NUCLEAR_ENERGY": 7}},
    "HUBB": {"lists": {}, "sectors": {"PICKS_SHOVELS": 18, "NUCLEAR_ENERGY": 8}},
    "CEG": {"lists": {}, "sectors": {"PICKS_SHOVELS": 19, "NUCLEAR_ENERGY": 0}},
    "AMSC": {"lists": {}, "sectors": {"WHEEL_STOCKS": 1}},
    "IREN": {"lists": {}, "sectors": {"WHEEL_STOCKS": 2}},
    "CIFR": {"lists": {}, "sectors": {"WHEEL_STOCKS": 3}},
    "CLSK": {"lists": {}, "sectors": {"WHEEL_STOCKS": 5}},
    "ENVX": {"lists": {}, "sectors": {"WHEEL_STOCKS": 8}},
    "CPRI": {"lists": {}, "sectors": {"LUXURY_EU": 8}},
    "RL": {"lists": {}, "sectors": {"LUXURY_EU": 9}},
    "TECK": {"lists": {}, "sectors": {"MATERIALS": 3}},
    "HBM": {"lists": {}, "sectors": {"MATERIALS": 10}},  # [SECTOR_WATCHLISTS] v4.7: Kupfer-Mid-Caps + Lithium (Gemini, verifiziert)
    "ERO": {"lists": {}, "sectors": {"MATERIALS": 11}},
    "LAC": {"lists": {}, "sectors": {"MATERIALS": 12}},
    "VST": {"lists": {}, "sectors": {"NUCLEAR_ENERGY": 1}},
    "NRG": {"lists": {}, "sectors": {"NUCLEAR_ENERGY": 2}},
    "TLN": {"lists": {}, "sectors": {"NUCLEAR_ENERGY": 3}},
    "SMR": {"lists": {}, "sectors": {"NUCLEAR_ENERGY": 4}},
    "OKLO": {"lists": {}, "sectors": {"NUCLEAR_ENERGY": 5}},
    "LEU": {"lists": {}, "sectors": {"NUCLEAR_ENERGY": 9}},  # [SECTOR_WATCHLISTS] v4.7: Uran-Fuel-Cycle (Gemini, verifiziert)
    "UEC": {"lists": {}, "sectors": {"NUCLEAR_ENERGY": 10}},
    "UUUU": {"lists": {}, "sectors": {"NUCLEAR_ENERGY": 11}},
    "NXE": {"lists": {}, "sectors": {"NUCLEAR_ENERGY": 12}},
    "RKLB": {"lists": {}, "sectors": {"SPACE": 0}},
    "ASTS": {"lists": {}, "sectors": {"SPACE": 1}},
    "CRSP": {"lists": {}, "sectors": {"BIOTECH_LONGEVITY": 0}},
    "BEAM": {"lists": {}, "sectors": {"BIOTECH_LONGEVITY": 1}},
    "NTLA": {"lists": {}, "sectors": {"BIOTECH_LONGEVITY": 2}},
    "RXRX": {"lists": {}, "sectors": {"BIOTECH_LONGEVITY": 5}},
    "DXCM": {"lists": {}, "sectors": {"BIOTECH_LONGEVITY": 6}},
    "ALGN": {"lists": {}, "sectors": {"BIOTECH_LONGEVITY": 7}},
    "VMI": {"lists": {}, "sectors": {"GRID_ELECTRIFICATION": 2}},
    "POWL": {"lists": {}, "sectors": {"GRID_ELECTRIFICATION": 4}},
    "AEIS": {"lists": {}, "sectors": {"GRID_ELECTRIFICATION": 5}},
    "PLPC": {"lists": {}, "sectors": {"GRID_ELECTRIFICATION": 6}},
    "B": {"lists": {}, "sectors": {"PRECIOUS_METALS": 1}},
    "WPM": {"lists": {}, "sectors": {"PRECIOUS_METALS": 2}},
    "FNV": {"lists": {}, "sectors": {"PRECIOUS_METALS": 3}},
    "RGLD": {"lists": {}, "sectors": {"PRECIOUS_METALS": 4}},
    "PAAS": {"lists": {}, "sectors": {"PRECIOUS_METALS": 5}},
    "HL": {"lists": {}, "sectors": {"PRECIOUS_METALS": 6}},
    "AG": {"lists": {}, "sectors": {"PRECIOUS_METALS": 7}},
    "EXK": {"lists": {}, "sectors": {"PRECIOUS_METALS": 8}},
    "FSM": {"lists": {}, "sectors": {"PRECIOUS_METALS": 9}},
    "MAG": {"lists": {}, "sectors": {"PRECIOUS_METALS": 10}},
    "AGCO": {"lists": {}, "sectors": {"AGRICULTURE": 1}},
    "CTVA": {"lists": {}, "sectors": {"AGRICULTURE": 2}},
    "MOS": {"lists": {}, "sectors": {"AGRICULTURE": 4}},
    "CF": {"lists": {}, "sectors": {"AGRICULTURE": 5}},
    "FMC": {"lists": {}, "sectors": {"AGRICULTURE": 6}},
    "DAR": {"lists": {}, "sectors": {"AGRICULTURE": 7}},
    "CNH": {"lists": {}, "sectors": {"AGRICULTURE": 8}},
    "AVD": {"lists": {}, "sectors": {"AGRICULTURE": 9}},
    "XYL": {"lists": {}, "sectors": {"WATER": 0}},
    "AWK": {"lists": {}, "sectors": {"WATER": 1}},
    "WTS": {"lists": {}, "sectors": {"WATER": 2}},
    "AOS": {"lists": {}, "sectors": {"WATER": 3}},
    "BMI": {"lists": {}, "sectors": {"WATER": 5}},
}


def _validate():
    known_lists = set(UNIVERSE_SOURCE_LISTS) | set(REFERENCE_LISTS)
    known_sectors = set(SECTOR_ORDER)
    seen_pos = {}
    problems = []
    for t, e in TICKER_MASTER.items():
        if not isinstance(t, str) or not t or t != t.strip():
            problems.append(f"ungueltiger Ticker-Schluessel: {t!r}")
            continue
        if set(e) != {"lists", "sectors"}:
            problems.append(f"{t}: Felder muessen genau 'lists' und 'sectors' sein, sind {sorted(e)}")
            continue
        if not e["lists"] and not e["sectors"]:
            problems.append(f"{t}: weder Liste noch Sektor — Eintrag ohne Wirkung")
        for kind, known, d in (("Liste", known_lists, e["lists"]), ("Sektor", known_sectors, e["sectors"])):
            for name, pos in d.items():
                if name not in known:
                    problems.append(f"{t}: unbekannte(r) {kind} {name!r}")
                if not isinstance(pos, int) or isinstance(pos, bool) or pos < 0:
                    problems.append(f"{t}: Position fuer {name} muss int >= 0 sein, ist {pos!r}")
                key = (kind, name, pos)
                if key in seen_pos:
                    problems.append(f"{t}: Position {pos} in {kind} {name} bereits von {seen_pos[key]} belegt")
                seen_pos[key] = t
    if problems:
        raise ValueError("TICKER_MASTER ungueltig:\n  " + "\n  ".join(problems))


def derive_list(name):
    """Rekonstruiert eine Quell-/Referenzliste in ihrer konfigurierten Reihenfolge."""
    if name not in UNIVERSE_SOURCE_LISTS and name not in REFERENCE_LISTS:
        raise KeyError(f"unbekannte Liste: {name}")
    members = [(e["lists"][name], t) for t, e in TICKER_MASTER.items() if name in e["lists"]]
    return [t for _, t in sorted(members)]


def derive_sector_watchlists():
    """Rekonstruiert SECTOR_WATCHLISTS (Sektorreihenfolge + Reihenfolge je Sektor)."""
    out = {}
    for s in SECTOR_ORDER:
        members = [(e["sectors"][s], t) for t, e in TICKER_MASTER.items() if s in e["sectors"]]
        out[s] = [t for _, t in sorted(members)]
    return out


def static_universe_candidates():
    """Statischer Teil der Universums-Kandidaten in exakt der bisherigen
    Zusammensetzungsreihenfolge von build_ticker_universe() — noch OHNE
    Laufzeitquellen, Deduplizierung und BAD_SYMS-Filter (die bleiben im
    Aggregator)."""
    sector_etfs = list(dict.fromkeys(
        derive_list("SECTOR_ETFS_BROAD") + derive_list("SECTOR_ETFS_US") + derive_list("SECTOR_ETFS_EXUS")
    ))
    sw = derive_sector_watchlists()
    return (
        derive_list("SP500_TICKERS") + derive_list("NASDAQ100_EXTRA") +
        derive_list("EU_ADR_TICKERS") +
        derive_list("BEAR_US_TICKERS") + derive_list("BEAR_DE_EU_TICKERS") +
        derive_list("INTL_TIER1") + sector_etfs + derive_list("CRYPTO_TICKERS") +
        [t for s in SECTOR_ORDER for t in sw[s]]
    )


_validate()
