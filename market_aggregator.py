#!/usr/bin/env python3
"""
UnderlyingIQ Market Aggregator v5.36.2
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
 
Version 5.36.1 (14.08.2026): DIX/GEX-Datenquellen-Prioritaet korrigiert
(fetch_dix_gex()) — squeezemetrics wurde am 09.07.2026 (v4.8, Commit
7c7140d) faelschlich als "historisch, meist 403 von GitHub Actions"
eingestuft und FlashAlpha (Free-Tier, nur AAPL-Proxy, kein echtes SPY/QQQ)
vorgezogen. Ein am 10.08.2026 eingerichteter Stability-Check
(data/datasource_stability/log.jsonl, 2x/Tag) zeigte seither 100%
Erfolgsquote fuer squeezemetrics — die "meist 403"-Einschaetzung war
veraltet, nie nach der Korrektur zurueckgespielt. Nach Prioritaetsumkehr
traten zwei Folgefehler auf, beide durch Log-Diagnose (nicht Vermutung)
aufgeloest: (1) Custom-Header ("Mozilla/5.0"-Fake-Browser-UA, dann
Python-requests-Default-UA) fuehrten zu stillem Fallback auf FlashAlpha
ohne Log-Spur — behoben durch expliziten "curl/8.5.0"-UA (identisch zum
bereits bewaehrten Stability-Check) UND ein neues else-Log fuer
unerwartete HTTP-Antworten (vorher: non-200-Antworten liefen komplett
ungeloggt durch). (2) Das neue Logging deckte dann den eigentlichen
Fehler auf: URL nutzte "dix.csv" (klein), tatsaechliche Ressource ist
"DIX.csv" (gross) — HTTP 404 auf case-sensitivem Hosting. Nach Fix
bestaetigt source="squeezemetrics" im Live-Snapshot (Run #213,
17:19 UTC). Bekannte Einschraenkung: squeezemetrics' oeffentliches
DIX.csv liefert vermutlich keine gex-Spalte (gex=0.0 im Snapshot) —
GEX-Wert dadurch moeglicherweise nicht nutzbar trotz korrekter Quelle;
nicht abschliessend verifiziert, da squeezemetrics.com außerhalb des
Sandbox-Netzwerkzugriffs liegt. FlashAlpha bleibt als Sekundaerquelle
erhalten (gamma_flip/call_wall/put_wall, falls Basic-Tier spaeter
aktiviert wird). Begleitfix axel-scanner/index.html v461: GEX-
Textbaustein im KI-Prompt-Kontext pruefte hartcodiert nur auf
source==='flashalpha_free' — neuer Zweig fuer 'squeezemetrics' ergaenzt.

Version 5.36.2 (14.08.2026): Zwei Nachbesserungen zum DIX/GEX-Fix aus
v5.36.1, beide noch am selben Tag entdeckt:
1. CRLF-Parsing-Bug in fetch_dix_gex(): squeezemetrics' DIX.csv nutzt
   Windows-Zeilenumbrueche (\r\n). r.text.strip().split("\n") liess ein
   unsichtbares \r am Ende jeder Zeile stehen — betraf nur die LETZTE
   CSV-Spalte ("gex\r" statt "gex"), daher lieferte gex durchgehend 0.0
   trotz korrekter Quelle (source="squeezemetrics" war schon richtig).
   Per Nutzer-Screenshot der echten squeezemetrics-Rohdaten verifiziert
   (Kopfzeile UND aktuellste Zeile enthalten echte, plausible gex-Werte,
   keine Platzhalter). Fix: splitlines() statt split("\n") + zusaetzliches
   .strip() auf Header-/Datenzeile. Offline mit simuliertem CRLF-Datensatz
   gegengeprueft (9180506464.63999 → korrekt 9.181 Mrd geparst), danach
   live in Run #214 bestaetigt (dixGex.gex=9.181, vorher 0.0).
2. DIX-Feld-Kollision aufgeloest: dix_gex["dix"] wurde bisher IMMER vom
   FINRA-ETF-Korb-Wert ueberschrieben (SPY/QQQ/IWM/DIA-Proxy, strukturell
   hoeher als klassischer S&P-500-DIX), auch nachdem squeezemetrics seit
   diesem Tag zuverlaessig den "echten" DIX liefert. Auf Axel-Entscheidung:
   beide Werte parallel fuehren statt einen zu verwerfen — "dix" bleibt
   squeezemetrics (S&P-500-Basis), FINRA-Wert + Metadaten jetzt unter
   dixEtfBasket* (dixEtfBasket, dixEtfBasketSource, dixEtfBasketMethodology,
   dixEtfBasketPerTicker, dixEtfBasketSize, dixEtfBasketDate). Fallback
   erhalten: falls squeezemetrics komplett ausfaellt, dix_gex["dix"] wird
   aus dem ETF-Korb-Wert befuellt (source-Suffix "_fallback" zur
   Kennzeichnung). BEKANNTE LUECKE, BEWUSST ZURUECKGESTELLT: axel-scanner/
   index.html prueft an 8 Stellen weiterhin dixSource==='finra_regshodaily'
   fuer die ETF-Korb-Anzeige (UI-Widgets, KI-Prompt-Kontext, bedingte
   Fragen) — diese Stellen zeigen die ETF-Korb-DIX-Zeile bis zur naechsten
   Session NICHT mehr an, obwohl die Daten weiterhin korrekt im Backend
   vorliegen (nur unter neuem Feldnamen). Kein Datenverlust, nur temporaer
   unsichtbar im Frontend. Naechste Session: alle 8 Stellen auf
   dixEtfBasketSource/dixEtfBasket ummuenzen. 
Version 5.36.14 (17.08.2026): Sieben neue Konjunktur-Indikatoren (Axel-
Anfrage — "auf diesem Auge bislang blind"): NFCI (Chicago Fed Financial
Conditions), Core CPI YoY, Arbeitslosenrate + offizielle Sahm-Rule
(FRED-Serie SAHMREALTIME, nicht selbst approximiert), University of
Michigan Consumer Sentiment, Heavy Truck Sales (10M-Schnitt, Axel-
Vorschlag), OECD Composite Leading Indicator (Quadranten-Logik), sowie
2Y/10Y-Zinskurve um "positiv seit N Handelstagen" + 3-Monats-Bestaetigung
erweitert. Alle FRED-Serien-IDs einzeln per Browser-Live-Check gegen die
echte FRED-Seite verifiziert (nicht aus dem Gedaechtnis uebernommen) —
zwei der drei von Axel vorgeschlagenen IDs waren tatsaechlich falsch:
CPIAUCSL ist Headline- statt Core-CPI (richtig: CPILFESL), TRUCKSUSSA
existiert nicht (404, richtig: HTRUCKSSAAR); NFCI-ID war korrekt benannt,
aber mit der ID eines anderen Index (STLFSI = St.-Louis-Fed-Variante)
verwechselt. Zusaetzlich zwei Sektor-Ratio-Signale (Consumer Staples vs.
Discretionary, Growth vs. Value) — beide OHNE neue API-Calls, da
XLP/XLY bereits im Ticker-Universum liegen und IWF/IWD (Growth/Value)
nur als 2 weitere Ticker in den bestehenden yfinance-Batch aufgenommen
wurden. Alle sieben Indikatoren ins MCM-Faktorsystem eingebunden
(_MCM_SIGNAL_RULES + build_server_market_context()) — erscheinen damit
automatisch im MARKET-CONTEXT-Block des Prompts und unterliegen der
bestehenden PFLICHTREGEL (§4 vom 16.08.). Bewusst nur etablierte,
dokumentierte Schwellen verwendet (Sahm-Rule 0.50 = akademischer
Standard, NFCI-Nullpunkt = Chicago-Fed-eigene Interpretation, OECD-CLI-
Quadranten = offizielle OECD-Methodik) statt erfundener Cutoffs.
BEKANNTE LUECKE: Client-seitige Parity (ko-indicators.json/-loader.js)
noch NICHT nachgezogen — analog zu frueheren MCM-Paritaets-Luecken
bewusst offen benannt, nicht verschwiegen. NICHT LIVE VERIFIZIERT.

Version 5.36.13 (17.08.2026): DIX/GEX-Bulk-Historie-Nebenfund verifiziert
und genutzt (Axel-Anfrage, Fortsetzung des SUITE.md/REGIME-BACKTEST-
VALIDIERUNG.md-Nebenfunds vom 16.08.2026). Live per Browser-Fetch
bestaetigt: squeezemetrics.com/monitor/static/DIX.csv liefert nicht nur
die aktuellste Zeile, sondern die volle taegliche Historie seit
2011-05-02 (3846 Zeilen, kostenlos, kein Auth) — im Widerspruch zur
aelteren "DIX/GEX ist tot"-Doku. fetch_dix_gex() liest jetzt zusaetzlich
die letzten 60 Handelstage (HISTORY_DAYS, deckt sich mit dem Cap in
KoMarketState.addDataPoint()) und legt sie unter dix_gex["history"] ab
(dates/dix/gex/n). Zweck: clientseitiger Backfill der lokalen Z-Score-
Historie (KoMarketState._history.gex/.dix) — vorher musste diese Historie
erst ueber mehrere Tage/Wochen Live-Betrieb akkumuliert werden (Symptom
vom selben Tag: "DIX Z-Score n/v - keine Historie" nach dem Wochenende).
Client-seitige Anbindung (ko-market-state.js backfillHistory() + Aufruf-
stelle in axel-scanner/index.html) im selben Zug ergaenzt.

Version 5.36.12 (17.08.2026): IOS-Market-Decision-Strings imperativfrei
umformuliert — Axel-Entscheidung im Rahmen der Rechtsgutachten-Vorbereitung
(BaFin-Konformitaet). calc_ios_market_score() gab bisher fuenf Entscheidungs-
Label zurueck, von denen zwei einen expliziten Kauf-Imperativ enthielten
("KAUFEN ERLAUBT", "SELEKTIV KAUFEN") — im direkten Widerspruch zur eigenen
STRIKTEN BaFin-REGEL andernorts im Prompt-Code ("Keine Empfehlungen zum Kauf...
auch nicht implizit"). Alle fuenf Labels jetzt als deskriptive Zustands-
beschreibung, gebunden an Strategie-Klassen, konsistent zum parallel schon
existierenden "mode"-Feld (OFFENSIV/SELEKTIV/NEUTRAL/DEFENSIV/KAPITAL
SCHUETZEN): "OFFENSIV — Trendfolge & Breakouts begünstigt" / "SELEKTIV —
Qualitäts-Setups begünstigt" / "NEUTRAL — nur Top-Setups vertretbar" /
"DEFENSIV — neue Breakouts zurückhaltend" / "KAPITALSCHUTZ — Absicherung im
Fokus". apply_ios_market_overlay() nutzt dieselben Strings fuer die
Confidence-Bonus/Daempfungs-Logik bei Options-Kandidaten (String-Vergleich,
kein Enum) — dort mitgezogen, sonst waere die Logik nach dem Rename
stillschweigend nie mehr getriggert worden. Reine Formulierungsaenderung,
keine Aenderung an Schwellenwerten oder Score-Berechnung. Betrifft nur
"iosMarketDecision" — das parallele "iosMarketMode"-Feld war schon vorher
imperativfrei und bleibt unveraendert.

Version 5.36.11 (16.08.2026): PFLICHTREGEL ergaenzt — Axel-Anschlussfrage:
"wird VVIX/SKEW/VIX3M von der KI gewuerdigt?" Empirische Pruefung des
generierten Textes (v5.36.10-Lauf) zeigte: Distribution Days/McClellan/
NDX-Breadth/Intermarket-Score/VIX3M-Termstruktur wurden trotz fehlender
STRUKTUR-Nennung korrekt diskutiert — aber NUR weil deren Signal zufaellig
[CAUTION]/[RISK] war und die KI das aus eigenem Ermessen fuer erwaehnens-
wert hielt. VVIX/SKEW/MOVE Index/SKEW-VVIX-Divergenz waren an [OK] und
wurden nicht erwaehnt — nicht unterscheidbar, ob aus Ermessen (nichts
Auffaelliges) oder weil die STRUKTUR-Liste sie nicht vorschreibt. Neue
PFLICHTREGEL macht das zur Vorschrift statt Kulanz: jeder [CAUTION]/[RISK]-
Faktor aus MARKET CONTEXT MUSS explizit genannt werden, unabhaengig von
der fixen 5-Punkte-STRUKTUR-Liste (die als Mindestanforderung, nicht
abschliessend, markiert wurde). SENTIMENT/MAKRO-KONDENSAT duerfen bei
Bedarf laenger als die genannten 2-3 Saetze werden. STATUS: NICHT LIVE
VERIFIZIERT. Bekannter Folgepunkt (noch nicht umgesetzt): dieselbe Regel
fehlt im Client-Fallback-Prompt (ko-prompts.js, _getMorningPrompt()) —
seltener genutzter Pfad, daher niedrigere Prioritaet.

Version 5.36.10 (16.08.2026): v5.36.9 live bestaetigt (KV-Direktabfrage) —
^VIX3M lieferte im Einzel-Download 237 Tage (vorher 1 im Batch), Schnitt-
menge jetzt 227 Tage statt 1. vvix_zscore/skew_zscore beide "ok": true
(Z=0.35/P74 bzw. Z=0.33/P68, n_days=227). Alle 14 MCM-Faktoren (10
bestehende + move_index/skew_vvix_div/breadth_osc/distribution_days aus
v5.36.5) gleichzeitig im selben Lauf bestaetigt — move_index war in
diesem Lauf zusaetzlich erfolgreich (das ^MOVE-Datenproblem aus v5.36.6
war offenbar transient und hat sich von selbst geloest). Temporaeres
_debug-Feld aus v5.36.8/v5.36.9 wieder entfernt (Zweck erfuellt).
Damit ist die gesamte Fund-Kette dieser Session geschlossen: DIX/GEX
(v5.36.3) -> Distribution-Days-Score (v5.36.4) -> Fear&Greed (ko-modules
v2.4.0) -> MCM-Paritaets-Nachzug 4 Faktoren (v5.36.5) -> MOVE-Index-Crash
(v5.36.6) -> mse_history Root Cause ^VIX3M-Batch-Bug (v5.36.9). Alle live
verifiziert, keine offenen Punkte aus der heutigen Session mehr.

Version 5.36.9 (16.08.2026): Echter Root-Cause-Fix (dank _debug-Feld aus
v5.36.8 gefunden): NICHT ein Timestamp/TZ-Problem (v5.36.7-Hypothese war
falsch) — der gebuendelte 4-Symbol-yf.download(group_by="ticker") lieferte
zuverlaessig fuer ^VIX3M nur 1 Tag Historie, waehrend ^VVIX/^SKEW/^VIX
245-254 Tage lieferten (_debug-Beweis: {"^VVIX":254,"^SKEW":254,"^VIX":245,
"^VIX3M":1}). Die anschliessende Schnittmenge war dadurch zwangsweise auf
maximal 1 Tag limitiert, unabhaengig von jeder Timestamp-Normalisierung.
fetch_vix_term() (LIVE-Werte, nicht Historie) holt VIX/VIX3M bereits
EINZELN und funktioniert zuverlaessig — dasselbe Muster jetzt fuer die
Historie uebernommen (4 separate Einzel-Downloads statt 1 gebuendeltem
Call). _debug-Feld bleibt vorerst drin zur Live-Bestaetigung, danach
Cleanup. STATUS: NICHT LIVE VERIFIZIERT — naechster Schritt: GHA-Lauf +
KV-Direktabfrage (dates_len sollte jetzt ~180-190 statt 1 sein).

Version 5.36.8 (16.08.2026): fetch_mse_history()-Fix aus v5.36.7 hat das
Problem NICHT behoben (live verifiziert: dates_len weiterhin 1 nach dem
naechsten Lauf) — die Timestamp-Normalisierungs-Hypothese war falsch oder
unvollstaendig. Da Claude keinen Zugriff auf GHA-Job-Logs hat (Azure Blob
Storage nicht in der Netzwerk-Freigabe), wurde stattdessen ein temporaeres
_debug-Feld direkt ins mseHistory-Ergebnis-Dict aufgenommen (Rohdaten-
Laenge pro Ticker VOR der Schnittmenge + Schnittmengen-Laenge + Sample-
Timestamps von ^VVIX/^VIX) — dadurch ueber den normalen KV-Abruf sichtbar,
ohne Log-Zugriff. Wird nach Root-Cause-Fund wieder entfernt. STATUS:
Diagnose-Lauf, noch kein Fix.

Version 5.36.7 (16.08.2026): fetch_mse_history() Index-Timestamp-Mismatch-
Fix — vvix/skew Z-Scores lieferten "nur 1 Werte" statt der erwarteten
~180 Handelstage (trotz period=257d), dadurch vvix/skew komplett aus dem
MCM-Kontext verschwunden (Fund waehrend der v5.36.5/v5.36.6-Live-
Verifikation, unabhaengig von jenen Fixes). Root Cause (Verdacht, NICHT
mit echten yfinance-Daten reproduzierbar getestet — kein Netzwerkzugriff
auf Yahoo Finance in der Sandbox): .index.intersection() ueber die 4
Ticker (^VVIX/^SKEW/^VIX/^VIX3M) vergleicht volle Timestamps (Datum+Zeit+
TZ) — bei Multi-Symbol-yf.download() koennen einzelne Ticker minimal
abweichende Zeitstempel-Metadaten mitbringen, wodurch die Schnittmenge
fast alle Tage verliert und nur zufaellig exakt uebereinstimmende
Zeitstempel behaelt. Fix: Index vor der Schnittmenge auf reines
Kalenderdatum normalisiert (tz_localize(None) + normalize()). Zusaetzlich
Diagnose-Logging ergaenzt (Rohdaten-Laenge pro Ticker + Schnittmengen-
Laenge), damit ein Wiederauftreten schneller einzugrenzen ist. STATUS:
NICHT LIVE VERIFIZIERT — naechster Schritt: GHA-Lauf + KV-Direktabfrage.

Version 5.36.6 (16.08.2026): fetch_move_index() Robustheits-Fix — squeeze()
konnte bei nur 1 verbleibendem Datenpunkt (nach dropna()) zu einem nackten
numpy.float64-Skalar kollabieren statt einer Series, wodurch .values fehlte
(AttributeError). War durch das try/except der Funktion bereits fehler-
isoliert (kein Absturz des Gesamtlaufs), aber move_index blieb dadurch bei
"ok": false, unabhaengig vom eigentlichen MOVE-Index-Datenstand. Gefunden
waehrend der Live-Verifikation von v5.36.5 (MCM-Paritaets-Nachzug) — ohne
diesen Fix war move_index der einzige der 4 neuen Faktoren, der sich nicht
live bestaetigen liess. Fix: klare Diagnose-Meldung statt rohem
AttributeError, keine Verhaltensaenderung im Erfolgsfall.

Version 5.36.5 (16.08.2026): MCM-Paritaets-Nachzug — Axel-Anschlussfrage nach
den drei DIX/GEX/F&G/DD-Fixen desselben Tages: "kann das auch bei anderen
Metriken passiert sein?" Antwort: ja. Vier Faktoren waren im Client
(ko-indicators.json v2.2.0/v2.3.0, 20./27.07.2026) laengst registriert,
aber NIE nach build_server_market_context() portiert — der Docstring
behauptete "MCM-Paritaet vollstaendig", das galt nur fuer den Stand vom
21.07. (4-Faktoren-Sprint, s. MCM-PARITAET-KONZEPT.md), nicht fuer spaeter
hinzugekommene Client-Faktoren. Betraf move_index, skew_vvix_div,
breadth_osc, distribution_days — alle vier fehlten im server-generierten
Morning Briefing (dem Normalfall, KV-Cache-First) komplett, unabhaengig
von jeglichem heutigem Bug. Zusaetzlicher Fund bei der Verifikation:
zwei der vier Faktoren waren AUCH im Client-Fallback-Pfad strukturell
kaputt (move_index pruefte _mkt.zscores.move — existiert nie, echte Daten
liegen unter _mkt.moveIndex; skew_vvix_div nutzte signal_eq==="WARNUNG"
gegen einen ganzen Satz als Vergleichswert, nie exakt gleich, Caution-Flag
feuerte nie) — beide in ko-indicators-loader.js mitgefixt. compute_
distribution_days() liefert jetzt zusaetzlich dd_max explizit (vorher nur
lokale Variable, nie im Output-Dict). _add()-Helper um optionales label-
Argument erweitert (bessere KI-lesbare Prompt-Zeilen fuer die 4 neuen
Faktoren statt nacktem "fid: wert"). NICHT LIVE VERIFIZIERT — nur
py_compile-geprueft, naechster Schritt: GHA-Lauf + KV-Direktabfrage.

Version 5.36.4 (16.08.2026): Distribution-Days-Score-Boden-Effekt behoben —
siehe Docstring bei compute_distribution_days() fuer vollstaendige
Begruendung. Kurz: Score floorte bei dd_max>=7 hart auf 0 (Faktor 15),
Skala jetzt linear bis dd_max=12. Nur der Score betroffen, dd_spy/dd_qqq/
dd_severity/dd_alert unveraendert. NICHT LIVE VERIFIZIERT — nur inhaltlich
gegen 4 historische Snapshots (04./07./13./16.08.) durchgerechnet.

Version 5.36.3 (15.08.2026): Server-seitiger Morning-Briefing-Prompt kannte
DIX/GEX bis hierher ueberhaupt nicht — dies war der ungeloeste Rest-Befund
aus §5 der Uebergabe vom selben Tag: der Client-Pfad (ko-prompts.js) wurde
bereits gefixt, aber generate_daily_snapshot() (server-seitig, GHA-Cron,
Ergebnis geht per KV-Cache in den "Neu"-Button) baute mlines/den Prompt
komplett unabhaengig davon und liess DIX/GEX an keiner Stelle einfliessen,
obwohl master["market"]["dixGex"] laengst vollstaendig befuellt vorlag
(dix, gex, dixEtfBasket* — s. Changelog v5.36.2 oben). Fix: dix_gex analog
zu vix_term/pcr_d aus market extrahiert, DIX (SqueezeMetrics)/GEX (inkl.
Gamma-Flip-Hinweis bei negativem Wert)/DIX (ETF-Korb) in den SENTIMENT-
Block von mlines aufgenommen, STRUKTUR-Punkt 2 des Prompts um "DIX/GEX"
ergaenzt (vorher nur VIX/PCR/Fear&Greed/IOS genannt — Daten waren zwar da,
aber keine Aufforderung, sie zu nutzen). NICHT LIVE VERIFIZIERT — Fix ist
nur per py_compile syntaktisch geprueft, noch kein echter GHA-Lauf
abgewartet und kein tatsaechlich generiertes Briefing gegengelesen.

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
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Einzige Quelle der Wahrheit für die Versionsnummer (NEU 30.06.2026 — vorher war
# meta["version"] unten hartcodiert "3.0" und lief seit der Fibo-Erweiterung (v3.1)
# unbemerkt aus dem Gleichschritt mit dem Docstring-Header oben in der Datei).
# ⚠️ Erneut gedriftet: v5.31.0–v5.36.0 (07./08.08.2026) wurden committet,
# ohne diese Konstante mitzuziehen. Verlaessliche Codestand-Zuordnung im
# Track Record laeuft seit 12.08.2026 ueber aggSha (GITHUB_SHA) in tr_layer.py.
AGGREGATOR_VERSION = "5.36.14"
# v5.12.4 (19.07.2026): SECTOR_ETF_LIST auf alle 10 ETFs erweitert
# (XLP/XLC/XLB fehlten — waren nicht in der Liste trotz vorhandener Dateien).
# v5.12.3 (19.07.2026): SSGA-US-Download deaktiviert — US-Format inkompatibel
# mit EMEA-Parser (CUSIP/SEDOL in Spalte 2 statt Security Name). Ausschliesslich
# lokale EMEA-UCITS-Dateien (data/holdings_{ETF}.xlsx). Root Cause Run#123:
# Download-Versuch erfolgreich (GHA erreicht ssga.com), aber falsches Format.
# v5.12.2 (19.07.2026): parse_ssga_holdings_xlsx() auf EMEA-UCITS-Format umgestellt
# (kein Ticker-Feld, openpyxl statt pandas, Header Zeile 5, Daten ab Zeile 6).
# build_sector_holdings(): MANUAL_NAME_MAP + IWV-Name-Matching statt
# resolve_company_name_to_ticker(). Alle 10 Sektor-ETF-xlsx committed
# (XLK/XLF/XLE/XLV/XLI/XLY/XLP/XLU/XLC/XLB). Match-Rate 149/150.
# v5.12.1 (19.07.2026): Regime-Bug-Fix in score_options_collar() —
# market_regime_str (MSE) statt r["regime"] (Ticker-Markov). market_regime_str-Berechnung
# vor options_candidates-Loop verschoben (war Zeile ~5370, Loop bei ~5231).
# v5.12.0 (19.07.2026): score_options_collar() — Collar/Protective-Put-Score 0-100.
# Neue Funktion nach demselben Muster wie score_options_csp/cc/spread.
# Regime-Gate: BULL_FRAGILE=+50 (Priorität 1, identifizierte Lücke in Regime-Coverage-Analyse),
# NEUTRAL=+20, STRESS_UNSTABLE/bear=return 0. RSI-Überdehnung als Absicherungsbedarf-Proxy.
# HVP-Fenster 25-65 ideal (Put nicht zu teuer), ATR/Preis-Ratio als Kosten-Proxy.
# Eingebaut in: Output-Dict (scoreCollar), optsScore (max aller 4 Scores),
# apply_macro_risk_overlay (Collar +20% bei GEX<0, Collar NICHT gedämpft bei IOS-Kapitalschutz).
# Frontend: index.html v375 — Collar-Tab im Options-Deck-Board + Chip-Anzeige.

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

# Pattern/Entry-Engine (10.07.2026, Pine-Script-Review) — echte VCP/Pocket-Pivot/
# Darvas-Mustererkennung + Entry-Timing. Datei liegt im selben Repo (Root-Ebene).
try:
    from ios_pattern_entry_engine import score_pattern_setup, score_entry_timing
    _PATTERN_ENGINE_AVAILABLE = True
except ImportError as _e:
    logging.getLogger(__name__).warning(f"ios_pattern_entry_engine nicht ladbar: {_e}")
    _PATTERN_ENGINE_AVAILABLE = False
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
    # Growth vs. Value (17.08.2026, Axel-Anfrage — Konjunktur-Indikatoren):
    # IWF/IWD = iShares Russell 1000 Growth/Value, Standard-Paar fuer diese
    # Rotation, hochliquide. Wird fuer calc_growth_value_signal() benoetigt.
    "IWF","IWD",
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


def _load_ex_iwv_tickers() -> list:
    """Lädt herausgefallene IWV-Ticker aus data/ex_iwv_tickers.csv.
    Diese werden weiter getracked (Survivorship-Bias-Fix, SWOT T3, 07.08.2026).
    Gibt Liste von Ticker-Strings zurück.
    """
    import csv as _csv
    ex_path = Path(__file__).parent.parent / 'data' / 'ex_iwv_tickers.csv'
    if not ex_path.exists():
        return []
    ex_tickers = []
    try:
        with open(ex_path, newline='', encoding='utf-8') as fh:
            reader = _csv.DictReader(fh)
            for row in reader:
                t = (row.get('Ticker') or '').strip()
                if t:
                    ex_tickers.append(t)
    except Exception as e:
        log.warning(f'[ex_iwv] Fehler beim Laden: {e}')
    return ex_tickers


def build_ticker_universe():
    seen = set()
    result = []
    # Ex-IWV Ticker laden (Survivorship-Bias-Fix, SWOT T3, 07.08.2026)
    ex_iwv = _load_ex_iwv_tickers()
    if ex_iwv:
        log.info(f'  [ex_iwv] {len(ex_iwv)} herausgefallene IWV-Ticker weiter getracked')
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
        fetch_approved_extra_tickers() +
        # SWOT T3 (07.08.2026): ex-IWV Ticker weiter tracken
        ex_iwv
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


def calc_vcp(closes, highs, lows, ema150=None, ema200=None,
             swing_window=5, min_contractions=2, lookback=90, volumes=None):
    """VCP (Volatility Contraction Pattern, Minervini) — Sprint 1+2: Preis-Struktur + Volumen.
    Volumen-Bestätigung ergänzt (22.07.2026, Sprint 2, SUITE.md Backlog #18):
      vcpVolContraction: Volumen waehrend letzter Contraction vs. 20T-Schnitt (<0.6 = stark getrocknet)
      vcpBreakoutVol: volRatio des letzten Bars (Ausbruch-Bestaetigung)

    Methodik:
    1. Swing-Hochs/-Tiefs über ein gleitendes Fenster (swing_window) im
       Lookback-Bereich identifizieren (lokale Extrempunkte).
    2. Contractions = aufeinanderfolgende Hoch->Tief-Bewegungen, als
       prozentuale Korrektur berechnet.
    3. Toleranz-Regel (Axel-Entscheidung 14.07.2026): NICHT streng monoton
       (nicht "jede Contraction < vorherige"), sondern "letzte Contraction <
       Durchschnitt der vorherigen Contractions" — robuster gegen
       Datenrauschen, vermeidet False Negatives bei real leicht
       unregelmäßigen Mustern.
    4. Trend-Kontext-Gate: Preis über EMA150 (falls vorhanden) — VCP ist nur
       im intakten Aufwärtstrend relevant (Minervini Trend Template, partiell;
       volle Trend-Template-Prüfung liegt bereits anderswo im Aggregator vor).

    Returns: dict mit vcpDetected, vcpContractions, vcpLastPct,
             vcpAvgPrevPct, vcpTightening — oder None bei zu wenig Daten.
    """
    n = len(closes)
    if n < lookback or len(highs) < n or len(lows) < n:
        return None

    window_highs = highs[-lookback:]
    window_lows  = lows[-lookback:]
    wn = len(window_highs)

    # ── Swing-Hochs/-Tiefs: lokale Extrempunkte über swing_window ────────
    swing_points = []  # [(index, 'high'|'low', preis), ...]
    for i in range(swing_window, wn - swing_window):
        seg_h = window_highs[i-swing_window:i+swing_window+1]
        seg_l = window_lows[i-swing_window:i+swing_window+1]
        if window_highs[i] == max(seg_h):
            swing_points.append((i, 'high', window_highs[i]))
        elif window_lows[i] == min(seg_l):
            swing_points.append((i, 'low', window_lows[i]))

    if len(swing_points) < min_contractions * 2:
        return {"vcpDetected": False, "vcpContractions": 0, "vcpLastPct": None,
                "vcpAvgPrevPct": None, "vcpTightening": False,
                "vcpVolContraction": None, "vcpBreakoutVol": None, "tightnessPct": None}

    # Alternierende Hoch/Tief-Folge erzwingen (bei Gleichstand: höheren Wert behalten)
    seq = []
    for pt in swing_points:
        if seq and seq[-1][1] == pt[1]:
            # gleiche Art zweimal hintereinander -> den extremeren behalten
            if pt[1] == 'high' and pt[2] > seq[-1][2]:
                seq[-1] = pt
            elif pt[1] == 'low' and pt[2] < seq[-1][2]:
                seq[-1] = pt
            continue
        seq.append(pt)

    # ── Contractions extrahieren: Hoch -> darauffolgendes Tief ───────────
    contractions = []
    for i in range(len(seq) - 1):
        if seq[i][1] == 'high' and seq[i+1][1] == 'low':
            high_val = seq[i][2]
            low_val  = seq[i+1][2]
            if high_val > 0:
                pct = round((high_val - low_val) / high_val * 100, 2)
                contractions.append(pct)

    num_contractions = len(contractions)
    if num_contractions < min_contractions:
        return {"vcpDetected": False, "vcpContractions": num_contractions,
                "vcpLastPct": contractions[-1] if contractions else None,
                "vcpAvgPrevPct": None, "vcpTightening": False,
                "vcpVolContraction": None, "vcpBreakoutVol": None, "tightnessPct": None}

    last_pct  = contractions[-1]
    prev_pcts = contractions[:-1]
    avg_prev  = round(sum(prev_pcts) / len(prev_pcts), 2) if prev_pcts else None

    tightening = (avg_prev is not None and last_pct < avg_prev)

    # Trend-Kontext-Gate: Preis über EMA150 (falls vorhanden)
    price = closes[-1]
    trend_ok = True
    if ema150 is not None:
        trend_ok = price > ema150

    vcp_detected = bool(tightening and trend_ok and num_contractions >= min_contractions)

    # ── Tightness-Metrik (23.07.2026, P1-Sprint) ────────────────────────
    # 5-Tage-Range: (max(high[-5:]) - min(low[-5:])) / close * 100
    # Minervini: <3% = "Tight" (ideale Konsolidierung), <5% = akzeptabel
    tightness_pct = None
    if len(highs) >= 5 and len(lows) >= 5 and closes[-1] > 0:
        h5 = max(highs[-5:])
        l5 = min(lows[-5:])
        tightness_pct = round((h5 - l5) / closes[-1] * 100, 2)

    # ── Volumen-Metriken (Sprint 2, 22.07.2026) ──────────────────────────
    # vcpVolContraction: Wie stark hat das Volumen während der letzten
    # Contraction abgenommen? Vergleich: Contraction-Durchschnitt vs. 20T davor.
    # <0.6 = stark getrocknet (ideales VCP-Signal), >1.0 = kein Trockenlegung
    vcp_vol_contraction = None
    vcp_breakout_vol    = None
    if volumes is not None and len(volumes) >= 25:
        # Letzte Contraction: vereinfacht = letzte 5-15 Bars je nach Muster
        # Pragmatisch: letzte max(5, lookback//15) Bars als Contraction-Proxy
        contraction_len = max(5, lookback // 15)
        vol_contraction_period = volumes[-contraction_len-1:-1]  # ohne letzten Bar
        vol_20d_before = volumes[-contraction_len-21:-contraction_len-1]
        if len(vol_contraction_period) > 0 and len(vol_20d_before) > 0:
            avg_contraction = sum(vol_contraction_period) / len(vol_contraction_period)
            avg_20d = sum(vol_20d_before) / len(vol_20d_before)
            if avg_20d > 0:
                vcp_vol_contraction = round(avg_contraction / avg_20d, 2)
        # vcpBreakoutVol: letzter Bar vs. 20T-Schnitt (Ausbruch-Bestätigung)
        vol_20d_ma = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else None
        if vol_20d_ma and vol_20d_ma > 0:
            vcp_breakout_vol = round(volumes[-1] / vol_20d_ma, 2)

    return {
        "vcpDetected":      vcp_detected,
        "vcpContractions":  num_contractions,
        "vcpLastPct":       last_pct,
        "vcpAvgPrevPct":    avg_prev,
        "vcpTightening":    tightening,
        "vcpVolContraction":vcp_vol_contraction,  # NEU: <0.6 ideal
        "vcpBreakoutVol":   vcp_breakout_vol,     # NEU: >1.5 Ausbruch bestätigt
        "tightnessPct":     tightness_pct,        # NEU: 5T-Range/Kurs% (<3%=Tight, <5%=OK)
    }


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



def _earnings_gate(r: dict, dte_window: int = 14) -> tuple:
    """Earnings-Gate für Options-Scorer (SWOT/Backlog, 07.08.2026).

    Gibt (blocked: bool, reason: str, severity: str) zurück.

    Logik:
      - earningsDTE ≤ 0:  Earnings bereits vergangen oder heute → kein Block
      - earningsDTE 1–7:  HARTE Sperre (return 0 in Scorer)
      - earningsDTE 8–14: WEICHE Warnung (Malus -20 Pkt, kein Hard-Stop)
      - earningsDTE > dte_window: kein Einfluss

    Begründung: Earnings innerhalb DTE einer Option erzeugen massives IV-Crush-
    Risiko (CSP/CC) oder Gap-Risk (alle Strategien). Bei Short-Optionen mit
    Earnings im DTE-Fenster ist der Erwartungswert negativ — unabhängig vom
    technischen Setup. Dies ist die häufigste Fehlerquelle bei Optionsanfängern.

    dte_window: Fenstergröße in Tagen (default 14 = 2 Wochen).
    """
    dte = r.get("earningsDTE")
    if dte is None or dte <= 0:
        return False, "", "none"

    if dte <= 7:
        return True, f"Earnings in {dte}T — Sperre (IV-Crush/Gap-Risk)", "hard"
    if dte <= dte_window:
        return False, f"Earnings in {dte}T — Malus", "soft"
    return False, "", "none"


def score_options_csp(r: dict) -> int:
    """
    Cash-Secured Put Score 0-100 — Unleashed v2 (Gemini-Blueprint).
    Deckt ATM-CSP, Wheel und wöchentliche CSP+LongCall-Kombinationen ab.

    Kernänderung: Ema200-Gate aufgeweicht auf 5%-Puffer (Bodenbildungsphase
    erlaubt), damit hohe Prämien in Pullback-Phasen nicht gefiltert werden.
    Seitwärtsregime wird stärker belohnt als Bull (Theta-Decay-Paradisziplin).

    v5.35: Earnings-Gate (07.08.2026) — Sperre bei Earnings ≤7T, Malus ≤14T.
    Earnings im DTE-Fenster = negativer Erwartungswert (IV-Crush + Gap-Risk).
    """
    price  = r.get("price", 0) or 0
    ema200 = r.get("ema200")
    ema50  = r.get("ema50")
    hvp    = r.get("hvp", 0) or 0
    rsi    = r.get("rsi", 50) or 50
    bbpos  = r.get("bbPos")
    regime = (r.get("regime") or "").lower()

    # Gate 0: Earnings-Gate (HARTE Sperre bei Earnings ≤7T)
    _eg_blocked, _eg_reason, _eg_sev = _earnings_gate(r, dte_window=14)
    if _eg_blocked: return 0

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

    # Earnings-Malus (weich, 8-14T): -20 Pkt Vorsichtsabschlag
    if _eg_sev == "soft":
        s = max(0, s - 20)

    return max(0, min(100, s))


def score_vcp(r: dict) -> int:
    """VCP-Score 0-100 — Sprint 1+2 (22.07.2026, SUITE.md Backlog #18 erledigt).
    Sprint 1: Preis-Struktur (Contractions, Tightening).
    Sprint 2: Volumen-Bestätigung (vcpVolContraction, vcpBreakoutVol).

    Punkte-Struktur:
    - Basis (Muster erkannt):        +40
    - Contractions (Anzahl):         bis +30
    - Letzte Contraction (Enge):     bis +30
    - Volumen-Trockenlegung (NEU):   bis +15
    - Ausbruch-Volumen (NEU):        bis +15
    Maximal: 130 → auf 100 gekappt
    """
    if not r.get("vcpDetected"):
        return 0
    contractions = r.get("vcpContractions") or 0
    last_pct     = r.get("vcpLastPct")

    s = 40  # Basis: Muster erkannt + Trend-Gate bestanden

    # Struktur: Contractions (mehr = mehr Bestätigung, Cap bei +30)
    s += min(30, max(0, contractions - 2) * 10)

    # Struktur: Enge letzte Contraction (stärker gecoiled = näher am Breakout)
    if last_pct is not None:
        if   last_pct <= 5:  s += 30
        elif last_pct <= 8:  s += 20
        elif last_pct <= 12: s += 10

    # Volumen-Trockenlegung (NEU, Sprint 2): <0.6 = stark getrocknet = ideales VCP
    vol_contraction = r.get("vcpVolContraction")
    if vol_contraction is not None:
        if   vol_contraction < 0.6:  s += 15  # Stark getrocknet
        elif vol_contraction < 0.8:  s += 10  # Moderat getrocknet
        elif vol_contraction < 1.0:  s +=  5  # Leicht getrocknet
        # >1.0 = kein Bonus (Volumen nicht getrocknet = schwächeres VCP-Signal)

    # Ausbruch-Volumen (NEU, Sprint 2): >1.5 = Ausbruch bestätigt
    breakout_vol = r.get("vcpBreakoutVol")
    if breakout_vol is not None:
        if   breakout_vol >= 2.0: s += 15  # Starker Ausbruch
        elif breakout_vol >= 1.5: s += 10  # Bestätigter Ausbruch
        elif breakout_vol >= 1.2: s +=  5  # Schwacher Ausbruch

    return min(100, s)


def score_options_covered_call(r: dict) -> int:
    """
    Covered Call Score 0-100 — v2.0 (22.07.2026, KIMI-Analyse-Destillat).

    CC ist fundamental anders als CSP:
    - CSP will kaufen (Überverkauf, BBPos tief, RSI <45)
    - CC verwaltet Bestand (moderate Überhitzung OK, Seitwärts ideal)

    Kernunterschiede zu score_options_csp():
    - RSI-Optimum: 60-75 (CC toleriert Überhitzung, CSP will Überverkauf)
    - HVP Sweet Spot: 40-75 (CC = Prämieneinnahme, höhere IV OK)
    - Gate: Kurs 0.92-1.15 × EMA50 (kein Crash, kein Explosion)
    - Regime: Side +30 > Bull +20 (Seitwärts = Theta-Paradisziplin für CC)
    - Fib: RETRACEMENT bevorzugen (Bestandsmanagement), nicht EXTENSION (Einstieg)
    - kein overheat-Gate unter 85 (CC auf überhitzten Positionen ist gewollt)
    """
    comp_score = r.get("score", 50) or 50
    price      = r.get("price", 0) or 0
    ema50      = r.get("ema50")
    ema200     = r.get("ema200")
    hvp        = r.get("hvp", 0) or 0
    regime     = (r.get("regime") or "").lower()
    rsi        = r.get("rsi", 50) or 50
    overheat   = r.get("overheat", 0) or 0
    bbpos      = r.get("bbPos")

    # Gate 0: Earnings-Gate (v5.35) — CC bei Earnings riskant (Assignment bei Gap-Up)
    _eg_blocked, _eg_reason, _eg_sev = _earnings_gate(r, dte_window=14)
    if _eg_blocked: return 0

    # Gate 1: Mindestqualität
    if comp_score < 45: return 0

    # Gate 2: Kurs-EMA50-Band — CC braucht weder Crash noch Explosion
    # 0.92: unter diesem Level ist die Bestandsposition bereits im echten Drawdown
    # 1.20: über diesem Level ist Opportunity Cost der Ausübung zu hoch → Momentum statt CC
    if ema50:
        if price < ema50 * 0.92: return 0  # Falling Knife — kein CC
        if price > ema50 * 1.20: return 0  # Zu explosiv — Momentum bevorzugen

    # Gate 3: Mindest-Volatilität für attraktive Prämie
    if hvp < 25: return 0   # Unter 25 zu wenig Prämie für sinnvollen CC

    # Gate 4: Extreme Überhitzung verhindert (explosiver Trend, Ausübung sicher)
    if overheat > 85: return 0   # Lockerer als CSP (85 statt 75) — CC toleriert Überhitzung

    s = 0

    # RSI: CC liebt moderate Überhitzung — Call-Prämien teuer, Upside begrenzt
    if   60 <= rsi <= 75: s += 35   # Sweet Spot: leicht überhitzt, Prämie gut
    elif 75 < rsi <= 80:  s += 20   # Noch OK — hohe Prämie, erhöhtes Assignment-Risiko
    elif 55 <= rsi < 60:  s += 15   # Neutrale Zone — Prämie moderat
    elif 50 <= rsi < 55:  s +=  5   # Knapp unter Optimum

    # Regime: Seitwärts ist Paradedisziplin für CC (kein Wegrennen des Kurses)
    if   regime == "side": s += 30   # Optimal: Theta-Verfall, kein Directional Risk
    elif regime == "bull": s += 20   # Gut: Prämie OK, aber Ausübung wahrscheinlicher
    elif regime == "volatile": s += 5  # Grenzwertig: hohe Prämie, aber Kursrisiko

    # HVP: CC-Sweet-Spot höher als CSP (wir wollen Prämie, nicht Ausverkauf-Signal)
    if   40 <= hvp <= 65: s += 25   # Ideal: gute Prämie ohne extremes Event-Risiko
    elif 65 < hvp <= 80:  s += 15   # Hohe Prämie — erhöhtes Gap-Risiko beachten
    elif 25 <= hvp < 40:  s += 10   # Niedrige Prämie — grenzwertig

    # EMA200-Trend: CC funktioniert besser in stabilen Aufwärtstrends
    if ema200 and price > ema200: s += 10   # Über langfristigem Trend = stabiler Bestand

    # BBPos: CC liebt mittlere bis obere Bollinger-Zone (Kurs hat Spielraum nach unten)
    if bbpos is not None:
        if   0.50 <= bbpos <= 0.80: s += 15   # Idealzone: OTM-Strike gut platzierbar
        elif 0.80 < bbpos <= 0.92:  s +=  8   # Nah am oberen Band — enger Strike nötig
        elif bbpos < 0.30:          s -=  5   # Zu tief — CSP wäre besser

    # Fibonacci: RETRACEMENT bevorzugen (Kurs auf Unterstützung = guter CC-Entry auf Bestand)
    # EXTENSION-Setups werden hier NICHT belohnt (das ist CSP-Logik)
    if r.get("f_setup") == "RETRACEMENT":
        s += min(int((r.get("f_score", 0) or 0) * 0.15), 12)

    # Earnings-Malus (weich, 8-14T)
    if _eg_sev == "soft":
        s = max(0, s - 20)

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

    # Gate 0: Earnings-Gate (v5.35) — Gap überschreitet typisch die Strike-Distanz
    _eg_blocked, _eg_reason, _eg_sev = _earnings_gate(r, dte_window=7)
    if _eg_blocked: return 0

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


def score_options_collar(r: dict, market_regime: str = "NEUTRAL") -> int:
    """
    Collar / Protective Put Score 0-100.

    Konzept: KEIN Prämien-Trade — Absicherung einer bestehenden Long-Position.
    Ideales Umfeld: BULL_FRAGILE (Trend intakt, aber erhöhtes Air-Pocket-Risiko).
    Proxy-Modus: echte Strikes/Prämien nicht verfügbar — ATR/HVP-basierte Näherung,
    wie in ko-prompts.js / UIQ-Suite/docs/REGIME-COVERAGE-ANALYSE.md dokumentiert.

    Score-Logik:
    - Regime BULL_FRAGILE  → maximaler Bedarf (Priorität 1 laut Regime-Coverage)
    - Regime NEUTRAL       → moderat sinnvoll (optional)
    - Regime BULL_QUIET    → kein Collar-Edge (Absicherung zu teuer, kaum Risiko)
    - Regime STRESS_UNSTABLE → zu spät (Vola zu hoch, Put-Prämien explodiert)
    - RSI > 65             → Überdehnung = Absicherungsbedarf steigt
    - HVP 25–65            → Prämienband günstig (Put nicht zu teuer, Call kompensiert)
    - HVP > 70             → Put-Prämie zu teuer → Score-Malus
    - dist200 > 0          → Bestandsposition muss im Uptrend sein (sonst kein Sinn)
    - ATR/Preis < 4%       → günstiger Collar umsetzbar (enger Kurs = enger Strike-Abstand)
    """
    price  = r.get("price", 0) or 0
    ema200 = r.get("ema200")
    rsi    = r.get("rsi", 50) or 50
    hvp    = r.get("hvp", 0) or 0
    dist200 = r.get("dist200", 0) or 0
    atr    = r.get("atr")
    regime = (r.get("regime") or "").lower()

    # Gate 0: Earnings-Gate (v5.35) — Collar kann bei Earnings sinnvoll sein
    # (Put schützt vor Gap-Down), aber Score-Malus für Unsicherheit
    _eg_blocked, _eg_reason, _eg_sev = _earnings_gate(r, dte_window=21)
    if _eg_blocked: return 0  # Sehr kurzfristig (<7T): kein Collar mehr sinnvoll

    # Gate 1: Bestandsposition muss im Uptrend sein
    if not ema200 or price < ema200:
        return 0

    # Gate 2: Mindest-HVP für überhaupt handelbare Optionsprämien
    if hvp < 20:
        return 0

    s = 0

    # ── REGIME-KERN: MSE-Marktregime (nicht Ticker-Markov-Regime!) ────────
    # market_regime kommt aus dem Aggregator-Hauptlauf (VIX-Term-Structure).
    # r["regime"] ist Ticker-Markov ("bull"/"side"/"bear") — kennt BULL_FRAGILE nicht.
    mse = (market_regime or "NEUTRAL").upper()
    if   mse == "BULL_FRAGILE":       s += 50  # Priorität 1: genau die Regime-Lücke
    elif mse == "NEUTRAL":            s += 20  # Optional sinnvoll
    elif mse == "STRESS_UNSTABLE":    return 0  # Zu spät: Put-Prämie explodiert
    elif mse == "POST_PANIC_REVERSION": return 0  # Kein Collar-Setup in Panik-Reversion
    elif mse == "BULL_QUIET":         s += 5   # Kaum Edge — Prämie kaum wert
    # Ticker-Markov als Sekundär-Signal: Trend muss intakt sein
    if regime == "bear": return 0  # Kein Collar wenn Einzeltitel im Downtrend

    # ── RSI: Überdehnung erhöht Absicherungsbedarf ────────────────────────
    if   rsi > 75: s += 30  # Stark überdehnt — Absicherung dringend
    elif rsi > 65: s += 20  # Leicht überdehnt — Collar attraktiv
    elif rsi > 55: s += 10  # Neutral — Collar optional
    # rsi <= 55: kein Bedarf (Aktie nicht überdehnt)

    # ── HVP-FENSTER: zu hoch = Put-Prämie frisst Ertrag ──────────────────
    if   25 <= hvp <= 45: s += 20  # Ideal: Prämien vorhanden, nicht explodiert
    elif 45 <  hvp <= 65: s += 10  # Noch akzeptabel
    elif hvp > 65:        s -= 15  # Put-Prämie zu teuer → Collar unattraktiv

    # ── DIST200: Je weiter über EMA200, desto mehr zu schützen ────────────
    if   dist200 > 20: s += 10  # Viel Gewinn zu sichern
    elif dist200 > 10: s += 5

    # ── ATR-KOSTEN-PROXY: enge ATR = günstiger Strike-Abstand ─────────────
    if atr and price > 0:
        atr_pct = atr / price * 100
        if   atr_pct < 2.0: s += 10  # Sehr günstig umsetzbar
        elif atr_pct < 3.5: s += 5   # Akzeptabel
        elif atr_pct > 6.0: s -= 10  # Strike zu weit weg → teuer

    return max(0, min(100, s))

def calc_markov(closes, lookback=60, stride=1):
    """Markov 2.0 Regime-Signal — stride=1 fuer korrekte Uebergangswahrscheinlichkeiten.
    Fix E: stride=7 erzeugte 85% Autokorrelation → p_bull2bear statistisch bedeutungslos.
    Mit stride=1 werden echte diskrete Tagesübergänge gemessen.
    Regime-Label basiert auf 5T-Return fuer Rauschen-Reduktion.
    """
    if len(closes) < lookback:
        return None, None, None, None
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
        return None, None, None, None

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

    # Markov v4: Warnstufe 1-3 (aus PINE-Script-Review 12.07.2026)
    # Bull-Stickiness: P(Bull→Bull) = bb / from_bull_total
    # Warn-Gap: Abstand zur Schwelle (60%) bestimmt Eskalationsstufe
    warn_level = 0
    if regime == 'bull' and bull_count > 0:
        bb = sum(1 for i in range(len(labels)-1)
                 if labels[i] == 'bull' and labels[i+1] == 'bull')
        bull_sticky = round(bb / bull_count * 100)
        warn_threshold = 60
        if bull_sticky < warn_threshold:
            warn_gap = warn_threshold - bull_sticky
            if   warn_gap > 15: warn_level = 3  # Kritisch
            elif warn_gap > 8:  warn_level = 2  # Mittel
            else:               warn_level = 1  # Leicht
    elif regime == 'bear' and bear_count > 0:
        # Bear-Stickiness: P(Bear→Bear) = cc / from_bear_total
        bear_to_bear = sum(1 for i in range(len(labels)-1)
                           if labels[i] == 'bear' and labels[i+1] == 'bear')
        bear_sticky = round(bear_to_bear / bear_count * 100)
        bear_threshold = 55
        if bear_sticky > bear_threshold:
            bear_gap = bear_sticky - bear_threshold
            if   bear_gap > 15: warn_level = 3
            elif bear_gap > 8:  warn_level = 2
            else:               warn_level = 1

    return regime, p_bull2bear, bull_pct, warn_level

def calc_ksi(closes, highs, lows, volumes, atr_len=14, vol_ema_len=20, sig_len=9):
    """Kinetic Slippage Index (HPotter v1.01).
    Misst Preis-Effizienz relativ zum Volumen:
      KSI = (TrueRange²) / (Volume × EMA(Volume, 20)) × 1_000_000
    Hoch: Kurs steigt auf niedrigem Volumen → leerer Markt, Umkehr möglich
    Nahe 0: Volumen bewegt Kurs kaum → Orderdichte, Akkumulation/Distribution
    Returns: (ksi, ksi_signal, ksi_spike_bool)
    """
    n = len(closes)
    if n < max(atr_len, vol_ema_len, sig_len) + 5 or len(highs) < n or len(lows) < n or len(volumes) < n:
        return None, None, None, None
    try:
        import math
        # True Range
        tr_list = []
        for i in range(1, n):
            hl   = highs[i] - lows[i]
            hpc  = abs(highs[i] - closes[i-1])
            lpc  = abs(lows[i]  - closes[i-1])
            tr_list.append(max(hl, hpc, lpc))
        if len(tr_list) < vol_ema_len + sig_len:
            return None, None, None, None
        # EMA Volumen (vol_ema_len)
        def _ema_list(arr, span):
            k = 2.0 / (span + 1)
            out = [arr[0]]
            for v in arr[1:]:
                out.append(v * k + out[-1] * (1 - k))
            return out
        vols = volumes[1:]  # aligned mit tr_list
        ema_vol = _ema_list(vols, vol_ema_len)
        # KSI-Rohwert
        ksi_raw = []
        for i in range(len(tr_list)):
            v   = vols[i]
            ev  = ema_vol[i]
            raw = (tr_list[i] ** 2 / (v * ev)) * 1_000_000 if (v > 0 and ev > 0) else 0.0
            ksi_raw.append(raw)
        # KSI-Signal (EMA sig_len)
        ksi_sig = _ema_list(ksi_raw, sig_len)
        # Bug-Fix v2 (12.07.2026, Run #94-Diagnose): Rundungsproblem, nicht Volumen-Lücke.
        # Bei liquiden Large Caps: raw ≈ 1e-8 → round(x,4) = 0.0.
        # Fix: 10 Dezimalstellen + ksiRatio als dimensionslose Vergleichsgröße.
        # Letzten non-zero Bar verwenden (max 5 zurück, für Volumen-Lücken).
        ksi_last = sig_last = 0.0
        _last_idx = None
        for _back in range(1, min(6, len(ksi_raw)+1)):
            if ksi_raw[-_back] > 0:
                ksi_last  = ksi_raw[-_back]
                sig_last  = ksi_sig[-_back]
                _last_idx = len(ksi_raw) - _back
                break
        ksi_now  = round(ksi_last, 10)
        sig_now  = round(sig_last, 10)
        # ksiRatio: KSI / Signal — dimensionslos, über alle Ticker vergleichbar
        # > 1.0 = KSI über Signal (Ineffizienz steigt), < 1.0 = darunter
        ksi_ratio = round(ksi_last / sig_last, 3) if sig_last > 0 else None
        # Spike: strikte Kreuzung am letzten non-zero Bar (kein Fenster-Scan)
        spike = False
        if _last_idx is not None and _last_idx >= 1:
            spike = bool(ksi_raw[_last_idx] > ksi_sig[_last_idx] and
                         ksi_raw[_last_idx - 1] <= ksi_sig[_last_idx - 1])
        return ksi_now, sig_now, spike, ksi_ratio
    except Exception:
        return None, None, None, None


def calc_yang_zhang_sigma(closes, highs, lows, opens, lookback=20):
    """Yang-Zhang (2000) Volatilitätsschätzer — drift-invariant.
    σ² = σ²_overnight + k·σ²_co + (1-k)·σ²_RS
    Identisch mit ST-EP06 Normierung (12.07.2026).
    """
    import math
    n = len(closes)
    if n < lookback + 2 or len(highs) < n or len(lows) < n or len(opens) < n:
        return None
    try:
        MIN_SIGMA = 1e-10
        # Serien für lookback-Fenster
        or_vals, co_vals, rs_vals = [], [], []
        for i in range(n - lookback, n):
            if i < 1: continue
            lnOR = math.log(opens[i] / closes[i-1])
            lnCO = math.log(closes[i] / opens[i])
            lnHO = math.log(highs[i] / opens[i])
            lnHC = math.log(highs[i] / closes[i])
            lnLO = math.log(lows[i]  / opens[i])
            lnLC = math.log(lows[i]  / closes[i])
            or_vals.append(lnOR); co_vals.append(lnCO)
            rs_vals.append(lnHO * lnHC + lnLO * lnLC)
        if len(or_vals) < 5: return None
        def _var(arr):
            m = sum(arr) / len(arr)
            return sum((x - m)**2 for x in arr) / (len(arr) - 1)
        sq_or = _var(or_vals)
        sq_co = _var(co_vals)
        sq_rs = sum(rs_vals) / len(rs_vals)
        k  = 0.34 / (1.34 + (lookback + 1.0) / max(lookback - 1.0, 1.0))
        sq = sq_or + k * sq_co + (1 - k) * sq_rs
        return max(math.sqrt(max(sq, 0.0)), MIN_SIGMA)
    except Exception:
        return None


def calc_ics_trend(closes, highs, lows, opens, period=19, groups=5, thresh=0.5, sigma_len=20):
    """ST-EP06 Isotropic Trend Lines — 6-Skalen-Konsens (12.07.2026).
    Normiert log(Preis) mit Yang-Zhang σ → ICS-Winkel vergleichbar über alle Märkte.
    Block-Pipeline: highest/lowest → Geo-Mean → monotone Sequenz → Kanal-Fitting.
    Returns dict mit icsDirection, icsAngle, icsConsensus, icsChUpper,
    icsChLower, icsBoState, icsChannelPos
    """
    import math
    n = len(closes)
    MIN_SIGMA = 1e-10
    PI = math.pi
    SCALES = [3, 7, 13, 19, 29, 47]

    # Yang-Zhang σ
    opens_use = opens if opens is not None and len(opens) == n else closes
    sigma = calc_yang_zhang_sigma(closes, highs, lows, opens_use, sigma_len)
    if sigma is None or sigma < MIN_SIGMA:
        return {}

    def ics_line(p1, x1, p2, x2, target_x):
        """Log-lineare Extrapolation in ICS."""
        if x1 == x2 or p1 <= 0 or p2 <= 0:
            return p1
        y1 = math.log(p1) / sigma
        y2 = math.log(p2) / sigma
        yt = y1 + (y2 - y1) * (target_x - x1) / (x2 - x1)
        return math.exp(yt * sigma)

    def ics_angle(p1, x1, p2, x2):
        if x1 == x2 or p1 <= 0 or p2 <= 0:
            return 0.0
        y1 = math.log(p1) / sigma
        y2 = math.log(p2) / sigma
        return math.atan((y2 - y1) / (x2 - x1)) * 180.0 / PI

    def analyze_scale(per):
        needed = groups * per + 2
        if n < needed:
            return None
        gm, bhi, blo, bcx = [], [], [], []
        for i in range(groups):
            offset = i * per
            window_h = highs[-(offset+1):-(offset+per+1):-1]
            window_l = lows[-(offset+1):-(offset+per+1):-1]
            if not window_h or not window_l:
                return None
            hi = max(window_h); lo = min(window_l)
            if hi <= 0 or lo <= 0: return None
            gm.append(math.exp((math.log(hi) + math.log(lo)) / 2))
            bhi.append(hi); blo.append(lo)
            bcx.append(n - offset - per // 2)

        if len(gm) < 2: return None
        # Richtung: längste monotone Sequenz
        pd_ = 1 if gm[0] > gm[1] else -1
        seg = 1
        for i in range(1, groups - 1):
            if i + 1 >= len(gm): break
            d = 1 if gm[i] > gm[i+1] else -1
            if d == pd_: seg += 1
            else: break

        # ICS-Winkel
        angle = 0.0
        if seg < len(gm):
            angle = ics_angle(gm[seg], bcx[seg], gm[0], bcx[0])
        direction = 0 if abs(angle) <= thresh else pd_

        # Kanal-Fitting: 4 Extrema über trendenden Segment
        fHH = fLH = fHL = fLL = None
        xHH = xLH = xHL = xLL = 0
        for i in range(seg + 1):
            h, l, x = bhi[i], blo[i], bcx[i]
            if fHH is None or h > fHH: fHH = h; xHH = x
            if fLH is None or h < fLH: fLH = h; xLH = x
            if fHL is None or l > fHL: fHL = l; xHL = x
            if fLL is None or l < fLL: fLL = l; xLL = x

        now = n  # aktueller Bar-Index (relativ)
        ch_up = ch_lo = None
        if direction == 1:
            ch_up = ics_line(fLH, xLH, fHH, xHH, now)
            ch_lo = ics_line(fLL, xLL, fHL, xHL, now)
        elif direction == -1:
            ch_up = ics_line(fHH, xHH, fLH, xLH, now)
            ch_lo = ics_line(fHL, xHL, fLL, xLL, now)
        else:
            ch_up = fHH; ch_lo = fLL

        return {'dir': direction, 'angle': angle, 'ch_up': ch_up, 'ch_lo': ch_lo}

    # 6 Skalen parallel
    results_scales = []
    primary = None
    for sc in SCALES:
        r = analyze_scale(sc)
        results_scales.append(r)
        if sc == 19:
            primary = r  # primäre Skala

    if primary is None:
        return {}

    # Konsens-Zählung
    c_up = sum(1 for r in results_scales if r and r['dir'] == 1)
    c_dn = sum(1 for r in results_scales if r and r['dir'] == -1)
    c_rng = sum(1 for r in results_scales if r and r['dir'] == 0)
    consensus = max(c_up, c_dn, c_rng)

    # Kurs-Position im Kanal (0-100%)
    ch_up = primary.get('ch_up')
    ch_lo = primary.get('ch_lo')
    price = closes[-1]
    channel_pos = None
    if ch_up and ch_lo and ch_up > ch_lo and price > 0 and sigma > MIN_SIGMA:
        try:
            y     = math.log(price) / sigma
            y_lo  = math.log(ch_lo) / sigma
            y_hi  = math.log(ch_up) / sigma
            pos   = (y - y_lo) / (y_hi - y_lo)
            channel_pos = round(max(0.0, min(1.0, pos)) * 100, 1)
        except Exception:
            pass

    # Breakout-Zustand (vereinfacht: INSIDE/BO_UP/BO_DN)
    bo_state = 'INSIDE'
    if ch_up and ch_lo:
        if price > ch_up: bo_state = 'BO_UP'
        elif price < ch_lo: bo_state = 'BO_DN'

    return {
        'icsDirection':  primary.get('dir'),        # -1/0/1
        'icsAngle':      round(primary.get('angle', 0.0), 2),  # Grad
        'icsConsensus':  consensus,                 # Wie viele der 6 Skalen einig
        'icsConsensusBull': c_up,                   # Bullische Skalen
        'icsConsensusBear': c_dn,
        'icsChUpper':    round(ch_up, 4) if ch_up else None,
        'icsChLower':    round(ch_lo, 4) if ch_lo else None,
        'icsBoState':    bo_state,                  # INSIDE/BO_UP/BO_DN
        'icsChannelPos': channel_pos,               # 0-100% (0=Boden, 100=Decke)
        'icsSigma':      round(sigma, 6),           # Yang-Zhang σ
    }


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
    Pareto-Erweiterung v3 (11.07.2026, Pine-Script-Review-Nachgang): SMA150 in Trend-Kette
    ergänzt (echte 50>150>200-Prüfung statt nur 50>200), 200er-Steigung (~1 Monat) geprüft,
    52-Wochen-Tief-Abstand (klassisches Minervini-Kriterium: ≥30% über Tief) ergänzt.
    Echtes RS-Rating (Stufe 1: perfRsRaw in process_ticker, Stufe 2: Perzentil-Ranking
    in main() nach Ticker-Schleife) eingebaut als Gate 6 (v5.0, 12.07.2026, SUITE.md #14).
    rsRating 0-99: >=85 SEPA-Ideal (+25), >=70 IBD-Minimum (+15), >=50 Median (+5), <50 (-10).
    """
    s = 0
    price    = r.get("price", 0)
    ema50    = r.get("ema50")
    ema200   = r.get("ema200")
    sma150   = r.get("sma150")
    ema200_slope_up = r.get("ema200SlopeUp")
    pct_high = r.get("pctFromHigh52")
    low52    = r.get("low52")
    dist200  = r.get("dist200")
    vol_ratio= r.get("volRatio", 1) or 1
    obv      = r.get("obvTrend", 0) or 0
    macd_h   = r.get("macdHist")
    p_b2b    = r.get("pBull2Bear", 0) or 0
    rsi      = r.get("rsi")
    hvp      = r.get("hvp")
    avg_vol  = r.get("avgVol20")  # NEU: Absolutvolumen-Filter

    # Liquiditäts-Soft-Gate (21.07.2026): Trendfolge braucht institutionelle Beteiligung.
    # Kein harter Ausschluss (UIQ scannt auch Mid-Caps), aber signifikanter Malus.
    # Schwelle 500k/Tag: unter dieser Marke können große Fonds keine Position aufbauen.
    if avg_vol is not None and avg_vol < 500_000:
        s -= 20
    elif avg_vol is not None and avg_vol < 250_000:
        s -= 35  # Sehr dünnes Volumen — Stage-2-Trends nicht verlässlich

    # Gate 1: Stage 2 Uptrend — Pflicht (jetzt mit echter 50>150>200-Kette wenn verfügbar)
    if not ema50 or not ema200: return 0
    if price < ema50 or price < ema200 or ema50 < ema200: return 0
    if sma150 is not None:
        if price < sma150 or ema50 < sma150 or sma150 < ema200: return 0
        s += 25
    else:
        s += 18  # Fallback ohne 150er (zu wenig Historie) — etwas weniger Vertrauen

    # Gate 1b: 200-Tage-MA seit ~1 Monat steigend (Minervini-Kriterium 3 — Steigung, nicht Snapshot)
    if ema200_slope_up is True:    s += 8
    elif ema200_slope_up is False: s -= 10  # flache/fallende 200er = kein echter Stage-2-Trend

    # Gate 2: Naehe zum 52W-Hoch
    if pct_high is not None:
        if pct_high >= -5:    s += 20
        elif pct_high >= -10: s += 12
        elif pct_high >= -15: s += 6

    # Gate 2b: Abstand vom 52W-Tief (Minervini-Kriterium 6: ≥30% über Tief)
    if low52 and price:
        pct_from_low52 = (price / low52 - 1) * 100
        if pct_from_low52 >= 30:  s += 10
        elif pct_from_low52 < 15: s -= 10  # zu nah am Tief — vermutlich noch Stage 1

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

    # Gate 6: RS-Rating (Hauptkriterium, ersetzt bisherigen Markov-Proxy hier)
    # rsRating ist ein Universum-Perzentil (0-99), wird von main() Stufe 2 befuellt.
    # In score_long_minervini() wird es direkt aus dem r-Dict gelesen.
    rs_rating = r.get("rsRating")
    if rs_rating is not None:
        if rs_rating >= 85:   s += 25   # SEPA-Idealzone: Top-15% des Universums
        elif rs_rating >= 70: s += 15   # IBD-Mindestschwelle (klassisch: RS >= 70)
        elif rs_rating >= 50: s +=  5   # Median-Bereich: schwaches positives Signal
        else:                 s -= 10   # schwaecherer als Haelfte des Universums
    # Gate 6b: Markov (bleibt als Makro-Kontext-Signal, aber reduziert gewichtet)
    if p_b2b > 0.25:   s -= 10   # war -15, jetzt -10 (RS-Rating traegt Hauptlast)
    elif p_b2b < 0.08: s +=  5

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

    # Gate 9: AVWAP-Support-Distanz (TVA f_buyProbability Faktor 5, Sprint A Aug 2026)
    # distToAvwapPct: positiv = über AVWAP (Stärke), nahe AVWAP = optimale Kaufzone
    dist_avwap = r.get("distToAvwapPct")
    avwap_above = r.get("avwapAbove")
    if dist_avwap is not None and avwap_above is not None:
        if avwap_above:
            if   dist_avwap <= 2:   s += 15   # Direkt an AVWAP: idealer Einstieg (TVA: +15)
            elif dist_avwap <= 5:   s += 8    # Nahe AVWAP: gutes Setup
            elif dist_avwap <= 10:  s += 3    # Etwas über AVWAP: OK
            # >10% über AVWAP: kein Bonus (überdehnt)
        # Unter AVWAP: kein Malus hier (Gate 1 hat bereits EMA-Struktur gesichert)

    # ── TVA Sigmoid-Glättung (August 2026, nach f_buyProbability-Konzept) ────
    # Rohscore wird durch Sigmoid geglättet: verhindert extreme Sprünge
    # durch einzelne starke Signale, belohnt konsistente Signalhäufung.
    # Formel: 100 / (1 + e^(-0.06 * (raw - 50)))
    # Kalibrierung: raw=50 → sigmoid=50, raw=80 → ~82, raw=20 → ~18
    # Faktor 0.06 (vs. TVA 0.08): etwas weicher für Daily-Zeitreihen.
    import math as _math
    s_sigmoid = round(100.0 / (1.0 + _math.exp(-0.06 * (s - 50))))
    return max(0, min(100, s_sigmoid))


def score_long_breakout(r: dict) -> int:
    """
    Breakout-Long: Ausbruch nahe 52W-Hoch mit Volumen- und OBV-Bestätigung.
    Konzept: Minervini Stage-2 + strengerer 52W-Hoch-Filter (≤5% Abstand)
    + erhöhtes Volumen als Pflicht-Gate.

    Kriterien (Maximal ~100 Punkte):
    - Stage-2-Grundvoraussetzung: Kurs > EMA50 > EMA200 (sonst 0)
    - 52W-Hoch-Nähe: ≤5% = 30 Pts, ≤10% = 18 Pts, ≤15% = 8 Pts, sonst 0
    - Volumen-Bestätigung: volRatio ≥ 1.5 = 25 Pts, ≥ 1.2 = 15 Pts (Kern-Signal)
    - OBV-Akkumulation: obv > 0 = 15 Pts
    - Momentum: macdHist > 0 = 10 Pts
    - RS-Rating: ≥85 = 20 Pts, ≥70 = 10 Pts (Breakouts aus starkem Universum bevorzugen)
    """
    s = 0
    price   = r.get("price")
    ema50   = r.get("ema50")
    ema200  = r.get("ema200")
    pct_high = r.get("pctFromHigh52")
    vol_ratio = r.get("volRatio", 1) or 1
    obv     = r.get("obvTrend", 0) or 0
    macd_h  = r.get("macdHist")
    rs_rating = r.get("rsRating")
    avg_vol = r.get("avgVol20")  # NEU: Absolutvolumen-Filter

    # Pflicht-Gate: Stage-2-Aufwärtstrend
    if not price or not ema50 or not ema200: return 0
    if price < ema50 or price < ema200 or ema50 < ema200: return 0

    # Liquiditäts-Soft-Gate: Breakouts ohne institutionelles Volumen sind False Breaks
    if avg_vol is not None and avg_vol < 500_000:
        s -= 15
    elif avg_vol is not None and avg_vol < 250_000:
        s -= 25

    # Gate 1: 52W-Hoch-Nähe (Kernkriterium Breakout)
    if pct_high is None: return 0  # ohne 52W-Daten kein Breakout-Score
    if pct_high >= -5:    s += 30
    elif pct_high >= -10: s += 18
    elif pct_high >= -15: s += 8
    else: return 0  # >15% vom Hoch = kein Breakout-Kandidat

    # Gate 2: Volumen-Bestätigung (Pflicht für echten Breakout)
    if vol_ratio >= 1.5:   s += 25
    elif vol_ratio >= 1.2: s += 15
    # Kein Malus bei niedrigem Volumen — Score bleibt niedrig genug für Ausschluss

    # Gate 3: OBV-Akkumulation (zeigt institutionelles Interesse)
    if obv > 0: s += 15

    # Gate 4: Momentum-Bestätigung
    if macd_h is not None and macd_h > 0: s += 10

    # Gate 5: RS-Rating (Breakouts aus Relative-Stärke-Titeln bevorzugen)
    if rs_rating is not None:
        if rs_rating >= 85:   s += 20
        elif rs_rating >= 70: s += 10
        elif rs_rating < 50:  s -= 5  # schwache RS = Breakout wahrscheinlich False Break

    return min(100, max(0, s))


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


def score_long_dividend(r: dict) -> int:
    """
    Dividend Income Score (0-100) — Backlog #13b, 28.07.2026.

    Ziel: Qualitäts-Dividendentitel für CSP/CC-Unterlegung und Income-Portfolio.
    Kein reiner Hochdividenden-Filter — Qualität vor Rendite.

    Felder (aus enrich_with_fundamentals, nur für Shortlist-Kandidaten verfügbar):
      divYield    — Dividendenrendite % (optimal: 2–6%)
      payoutRatio — Ausschüttungsquote % (nachhaltig: <75%)
      fcfYield    — FCF-Yield % (Qualitätsgate: >0)
      debtToEquity— Verschuldung (konservativ: <150)
      roe         — Return on Equity % (Qualität: >10%)

    Technische Basis (immer verfügbar):
      ema50/ema200 — Trend-Gate (kein Div-Catch in Downtrend)
      rsi          — kein überhitzter Einstieg
      regime       — Ticker-Markov (bull/side bevorzugt)
    """
    s = 0
    price     = r.get("price", 0)
    ema50     = r.get("ema50")
    ema200    = r.get("ema200")
    rsi       = r.get("rsi")
    regime    = (r.get("regime") or "").lower()

    # Fundamental-Felder (nur für Shortlist-Kandidaten nach Enrichment verfügbar)
    div_yield = r.get("divYield")       # %
    payout    = r.get("payoutRatio")    # %
    fcf_yield = r.get("fcfYield")       # %
    d_eq      = r.get("debtToEquity")
    roe       = r.get("roe")            # %

    if not price or price <= 0: return 0

    # ── Gate: Kein Dividendentitel ohne messbare Ausschüttung ────────────────
    if not div_yield or div_yield < 1.0: return 0

    # ── Gate: Technischer Trend — kein Div-Catch in echtem Downtrend ─────────
    if ema200 and price < ema200 * 0.92: return 0   # >8% unter EMA200 = Downtrend

    # ── Dividendenrendite (Kern-Score) ────────────────────────────────────────
    if   div_yield >= 5.0: s += 20   # Hochdividende — attraktiv, aber Qualität prüfen
    elif div_yield >= 3.0: s += 30   # Sweet Spot: gute Rendite + meist nachhaltig
    elif div_yield >= 2.0: s += 20   # Solide Basisrendite
    elif div_yield >= 1.0: s += 10   # Schwacher Starter — Wachstumsdividende möglich

    # Bonus: Hochdividende NUR wenn FCF-gedeckt (kein Div-Trap)
    if div_yield >= 5.0 and fcf_yield and fcf_yield > 0:
        s += 10   # FCF-gedeckte Hochdividende = echter Wert

    # ── Ausschüttungsquote — Nachhaltigkeit ──────────────────────────────────
    if payout is not None:
        if   payout <= 40:  s += 20  # Konservativ — viel Wachstumspuffer
        elif payout <= 60:  s += 15  # Gesund
        elif payout <= 75:  s += 8   # Akzeptabel
        elif payout <= 90:  s += 0   # Grenzwertig
        else:               s -= 15  # Nicht nachhaltig (>90%)

    # ── FCF-Yield — Qualitätsgate ────────────────────────────────────────────
    if fcf_yield is not None:
        if   fcf_yield >= 6: s += 15  # Exzellente Cash-Generierung
        elif fcf_yield >= 3: s += 10  # Solide
        elif fcf_yield >= 0: s += 3   # Neutral
        else:                s -= 20  # Cash-Burner — Dividende auf Pump

    # ── Return on Equity — Unternehmensqualität ───────────────────────────────
    if roe is not None:
        if   roe >= 20: s += 10
        elif roe >= 10: s += 5
        elif roe <  0:  s -= 10

    # ── Verschuldung ─────────────────────────────────────────────────────────
    if d_eq is not None:
        if   d_eq > 300: s -= 15
        elif d_eq > 150: s -= 8

    # ── Technisches Timing ────────────────────────────────────────────────────
    if ema50  and price > ema50:  s += 8   # Kurzfristiger Aufwärtstrend
    if ema200 and price > ema200: s += 7   # Langfristig gesund
    if rsi:
        if   rsi < 35: s += 10  # Günstiger Einstieg
        elif rsi > 70: s -= 8   # Überhitzt — warten

    # ── Regime-Bonus ─────────────────────────────────────────────────────────
    if regime in ("bull", "side"): s += 5

    return max(0, min(100, s))


def score_long_value(r: dict) -> int:
    """
    Value Score (0-100) — Backlog #13b, 28.07.2026.

    Ziel: Günstig bewertete Qualitätstitel mit positivem Catalyst-Potenzial.
    Kein reiner Graham-Screen — Kombination aus Bewertung + Qualität + Momentum.

    Felder (aus enrich_with_fundamentals):
      peForward   — Forward KGV (günstig: <20, sehr günstig: <15)
      pb          — Price/Book (günstig: <3, sehr günstig: <1.5)
      fcfYield    — FCF-Yield % (Qualitätsgate: >3%)
      roe         — Return on Equity % (Qualität: >10%)
      analystUpside — Konsens-Upside % (Catalyst: >10%)
      debtToEquity— Verschuldungsgate

    Technische Basis:
      ema50/ema200 — kein Kauf fallender Messer
      rsi          — moderate Bewertung bevorzugt
    """
    s = 0
    price     = r.get("price", 0)
    ema50     = r.get("ema50")
    ema200    = r.get("ema200")
    rsi       = r.get("rsi")
    regime    = (r.get("regime") or "").lower()

    pe_fwd    = r.get("peForward")
    pb        = r.get("pb")
    fcf_yield = r.get("fcfYield")
    roe       = r.get("roe")
    upside    = r.get("analystUpside")
    d_eq      = r.get("debtToEquity")

    if not price or price <= 0: return 0

    # ── Gate: Mindestens ein Bewertungsanker muss vorhanden sein ─────────────
    if pe_fwd is None and pb is None and fcf_yield is None: return 0

    # ── Gate: Kein fallender Messer — EMA200-Boden ───────────────────────────
    if ema200 and price < ema200 * 0.88: return 0   # >12% unter EMA200

    # ── Forward KGV ──────────────────────────────────────────────────────────
    if pe_fwd is not None:
        if   pe_fwd <= 10: s += 30   # Sehr günstig (Deep Value)
        elif pe_fwd <= 15: s += 25   # Günstig
        elif pe_fwd <= 20: s += 15   # Moderat bewertet
        elif pe_fwd <= 25: s += 5    # Fair
        elif pe_fwd <= 35: s -= 5    # Teuer
        else:              s -= 15   # Sehr teuer (>35x)

    # ── Price/Book ────────────────────────────────────────────────────────────
    if pb is not None:
        if   pb <= 1.0: s += 20   # Unter Buchwert — klassischer Value
        elif pb <= 1.5: s += 15
        elif pb <= 2.5: s += 8
        elif pb <= 4.0: s += 0
        else:           s -= 8    # Teures Wachstum (kein Value-Kandidat)

    # ── FCF-Yield — operativer Beweis ────────────────────────────────────────
    if fcf_yield is not None:
        if   fcf_yield >= 8: s += 25  # Exzellent
        elif fcf_yield >= 5: s += 18
        elif fcf_yield >= 3: s += 10
        elif fcf_yield >= 0: s += 3
        else:                s -= 15  # Negativer FCF = kein Value

    # ── ROE — Qualitätsfilter (Value Trap vermeiden) ──────────────────────────
    if roe is not None:
        if   roe >= 20: s += 15
        elif roe >= 12: s += 10
        elif roe >= 5:  s += 3
        elif roe <  0:  s -= 15   # Verlustbetrieb — Value Trap-Warnung

    # ── Analyst-Upside — externer Catalyst ───────────────────────────────────
    if upside is not None:
        if   upside >= 30: s += 15
        elif upside >= 15: s += 10
        elif upside >= 5:  s += 5
        elif upside <  0:  s -= 10  # Konsens sieht Downside

    # ── Verschuldung ─────────────────────────────────────────────────────────
    if d_eq is not None:
        if   d_eq > 300: s -= 20  # Hoch verschuldet = Value Trap-Risiko
        elif d_eq > 150: s -= 10

    # ── Technisches Timing ────────────────────────────────────────────────────
    if ema50  and price > ema50:  s += 5
    if ema200 and price > ema200: s += 5
    if rsi:
        if   rsi < 40:          s += 10  # Günstiges Einstiegsfenster
        elif 40 <= rsi <= 60:   s += 5   # Neutral — akzeptabel
        elif rsi > 70:          s -= 5   # Teures Momentum — Value-Timing ungünstig

    # ── Regime ───────────────────────────────────────────────────────────────
    if regime in ("bull", "side"): s += 5

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

    # TVA f_sellProbability: Sigmoid-Glättung analog score_long_minervini (v5.25.0)
    # Verhindert extreme Sprünge, belohnt Signalhäufung — k=0.06 (Daily-Standard TVA)
    import math as _math
    s_sigmoid = round(100.0 / (1.0 + _math.exp(-0.06 * (s - 50))))
    return max(0, min(100, s_sigmoid))


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




# ── RS-RANK SCORE (IOS Konzept-Integration, August 2026) ─────────────────────
# Misst Relative Stärke einer Aktie vs. SPY+IWM über 3M/6M-Zeithorizonte.
# 6 Bedingungen analog IOS Institutional Momentum Engine (rs001–rs006).
# Benchmark: Beide SPY (Large Cap) und IWM (Small/Mid Cap) parallel.
def compute_rs_rank_score(ticker_hist, spy_hist, iwm_hist) -> dict:
    """
    Berechnet RS-Rank Score (0-100) vs. SPY und IWM.
    ticker_hist, spy_hist, iwm_hist: yfinance DataFrames mit 'Close'-Spalte.
    Returns dict mit rs_score, rs_score_spy, rs_score_iwm, rs_new_high,
                    ret_3m, ret_6m, rs_grade.
    """
    try:
        close_t   = ticker_hist["Close"].dropna()
        close_spy = spy_hist["Close"].dropna()
        close_iwm = iwm_hist["Close"].dropna()
        if len(close_t) < 63 or len(close_spy) < 63 or len(close_iwm) < 63:
            return {"rs_score": None, "rs_grade": None}

        def _score_vs_bench(close_ticker, close_bench):
            rs_line = close_ticker / close_bench
            rs_ma20 = rs_line.rolling(20).mean()
            rs_ma50 = rs_line.rolling(50).mean()

            ret_3m_t = (close_ticker.iloc[-1] / close_ticker.iloc[-63]  - 1) * 100
            ret_3m_b = (close_bench.iloc[-1]  / close_bench.iloc[-63]   - 1) * 100
            ret_6m_t = ret_6m_b = None
            if len(close_ticker) >= 126 and len(close_bench) >= 126:
                ret_6m_t = (close_ticker.iloc[-1] / close_ticker.iloc[-126] - 1) * 100
                ret_6m_b = (close_bench.iloc[-1]  / close_bench.iloc[-126]  - 1) * 100

            rs001 = bool(rs_line.iloc[-1] > rs_ma20.iloc[-1])                        # RS > MA20
            rs002 = bool(rs_ma20.iloc[-1] > rs_ma50.iloc[-1])                        # MA20 > MA50
            rs003 = bool(rs_line.iloc[-1] > rs_line.iloc[-20])                       # RS steigt 20T
            rs004 = bool(ret_3m_t > ret_3m_b)                                        # 3M outperform
            rs005 = bool(ret_6m_t is not None and ret_6m_b is not None
                         and ret_6m_t > ret_6m_b)                                    # 6M outperform
            rs006 = bool(rs_line.iloc[-1] >= rs_line.iloc[-63:].max())               # RS 63T-Hoch

            score = min(
                (15 if rs001 else 0) + (15 if rs002 else 0) +
                (20 if rs003 else 0) + (20 if rs004 else 0) +
                (20 if rs005 else 0) + (10 if rs006 else 0),
                100
            )
            return score, rs006, ret_3m_t, ret_6m_t

        score_spy, rs_new_high_spy, ret_3m, ret_6m = _score_vs_bench(close_t, close_spy)
        score_iwm, rs_new_high_iwm, _,      _      = _score_vs_bench(close_t, close_iwm)

        # Kombinierter Score: Durchschnitt beider Benchmarks
        rs_score = round((score_spy + score_iwm) / 2)
        rs_new_high = rs_new_high_spy or rs_new_high_iwm

        grades = [(95,"A+"),(90,"A"),(85,"A-"),(80,"B+"),(75,"B"),
                  (70,"B-"),(65,"C+"),(60,"C"),(55,"C-"),(40,"D")]
        rs_grade = next((g for s, g in grades if rs_score >= s), "F")

        return {
            "rs_score":     rs_score,
            "rs_score_spy": score_spy,
            "rs_score_iwm": score_iwm,
            "rs_new_high":  rs_new_high,
            "ret_3m":       round(ret_3m, 1) if ret_3m is not None else None,
            "ret_6m":       round(ret_6m, 1) if ret_6m is not None else None,
            "rs_grade":     rs_grade,
        }
    except Exception as _e:
        log.debug(f"compute_rs_rank_score Fehler: {_e}")
        return {"rs_score": None, "rs_grade": None}


# ── DISTRIBUTION DAYS ZÄHLER (IOS Konzept-Integration, August 2026) ──────────
# O'Neil/IBD: Index fällt >0.2% bei höherem Volumen = institutionelles Verkaufen.
# 4–5 DD in 25 Tagen = Watch, ≥6 DD = Danger (Long-Positionen reduzieren).
def compute_distribution_days(spy_hist, qqq_hist, lookback: int = 25) -> dict:
    """
    Zählt Distribution Days für SPY und QQQ in den letzten `lookback` Handelstagen.
    Returns dict mit dd_spy, dd_qqq, dd_score (0-100), dd_alert, dd_severity.
    """
    try:
        def _count_dd(hist):
            close = hist["Close"].dropna()
            vol   = hist["Volume"].dropna()
            if len(close) < lookback + 2 or len(vol) < lookback + 2:
                return 0
            count = 0
            for i in range(1, lookback + 1):
                idx = -(i)
                try:
                    pct_chg   = (close.iloc[idx] / close.iloc[idx - 1] - 1) * 100
                    vol_ratio = vol.iloc[idx] / vol.iloc[idx - 1] if vol.iloc[idx - 1] > 0 else 0
                    if pct_chg <= -0.2 and vol_ratio > 1.0:
                        count += 1
                except (IndexError, ZeroDivisionError):
                    pass
            return count

        dd_spy = _count_dd(spy_hist)
        dd_qqq = _count_dd(qqq_hist)
        dd_max  = max(dd_spy, dd_qqq)

        # Score: 100 = keine DD, sinkt mit jedem DD (6 DD = 10 Punkte)
        # Score: erweiterte Skala (16.08.2026-Fix, Axel-Deep-Debug-Anfrage).
        # Vorher: dd_score = max(0, 100 - dd_max*15) — floorte bei JEDEM
        # dd_max>=7 (100-15*7=-5) hart auf 0. QQQ lag seit Wochen konstant bei
        # 7-9 DD, wodurch der Score wochenlang unveraendert bei 0 stand und
        # optisch wie "eingefroren" wirkte, obwohl dd_spy/dd_qqq selbst sich
        # taeglich aenderten (per Snapshot-Vergleich 04./07./13./16.08.
        # verifiziert: 2/7 -> 6/9 -> 5/8 -> 5/8 — Aenderung vorhanden, nur vom
        # gesaettigten Score nicht mehr sichtbar). Fix: lineare Skala bis
        # dd_max=12 (realistischer Rahmen fuer ein 25-Handelstage-Fenster),
        # dadurch bleibt der Score auch oberhalb der alten 6.67-DD-Schwelle
        # noch differenzierend. Severity-Schwellen (Watch>=4, Danger>=6)
        # unveraendert, nur der Score selbst betroffen.
        DD_SCORE_MAX_DD = 12
        dd_score = max(0, round(100 - dd_max * (100 / DD_SCORE_MAX_DD)))

        severity = ("Danger" if dd_max >= 6 else
                    "Watch"  if dd_max >= 4 else "None")

        return {
            "dd_spy":      dd_spy,
            "dd_qqq":      dd_qqq,
            "dd_max":      dd_max,
            "dd_score":    dd_score,
            "dd_alert":    dd_max >= 4,
            "dd_severity": severity,
            "dd_lookback": lookback,
        }
    except Exception as _e:
        log.warning(f"compute_distribution_days Fehler: {_e}")
        return {"dd_spy": None, "dd_qqq": None, "dd_max": None, "dd_score": None,
                "dd_alert": False, "dd_severity": "None"}


# ── ANCHORED VWAP (Zeiierman-Konzept, August 2026) ───────────────────────────
# EWMA-basierter VWAP verankert am letzten 52W-Tief des Tickers.
# Formel: alpha = 1 - exp(-ln(2) / apt)  →  EWMA auf kumuliertem PV/V
# Vorteil vs. klassischem VWAP: ältere Bars werden exponentiell weniger gewichtet.
# Ankerpunkt 52W-Tief: institutionell relevante Unterstützungszone.
def compute_anchored_vwap(hist, apt: int = 20) -> dict:
    """
    Berechnet Anchored VWAP (AVWAP) ab letztem 52W-Tief.
    hist: yfinance DataFrame mit Close/High/Low/Volume-Spalten.
    apt:  Adaptive Price Tracking (Half-Life in Bars, Default 20 = ~14 Tage).
    Returns dict: avwap, avwapAnchorDate, avwapAnchorPrice,
                  distToAvwapPct, avwapAbove, avwapSlope
    """
    try:
        import math as _math
        close  = hist["Close"].dropna()
        high   = hist["High"].dropna()
        low    = hist["Low"].dropna()
        volume = hist["Volume"].dropna()

        if len(close) < 20:
            return {"avwap": None, "avwapAnchorDate": None}

        # HLC3 als Typischer Preis (wie im Pine Script)
        hlc3 = (high + low + close) / 3.0

        # Lookback: maximal 252 Bars (1 Handelsjahr)
        lookback = min(252, len(close))
        close_lb  = close.iloc[-lookback:]
        low_lb    = low.iloc[-lookback:]
        high_lb   = high.iloc[-lookback:]
        hlc3_lb   = hlc3.iloc[-lookback:]
        vol_lb    = volume.iloc[-lookback:]

        # Ankerpunkt: Index des 52W-Tiefs im Lookback-Fenster
        anchor_idx_rel = int(low_lb.values.argmin())
        anchor_date    = low_lb.index[anchor_idx_rel]
        anchor_price   = float(low_lb.iloc[anchor_idx_rel])

        # EWMA-Alpha aus Half-Life (Zeiierman-Formel)
        alpha = 1.0 - _math.exp(-_math.log(2.0) / max(1.0, apt))

        # EWMA-VWAP ab Ankerpunkt
        seg_hlc3 = hlc3_lb.iloc[anchor_idx_rel:]
        seg_vol  = vol_lb.iloc[anchor_idx_rel:]

        if len(seg_hlc3) < 2:
            return {"avwap": None, "avwapAnchorDate": None}

        # Initialisierung am Ankerpunkt
        p_ewma   = float(seg_hlc3.iloc[0] * seg_vol.iloc[0])
        vol_ewma = float(seg_vol.iloc[0])

        avwap_series = []
        for i in range(1, len(seg_hlc3)):
            pxv      = float(seg_hlc3.iloc[i] * seg_vol.iloc[i])
            v_i      = float(seg_vol.iloc[i])
            p_ewma   = (1.0 - alpha) * p_ewma   + alpha * pxv
            vol_ewma = (1.0 - alpha) * vol_ewma + alpha * v_i
            vap      = p_ewma / vol_ewma if vol_ewma > 0 else None
            avwap_series.append(vap)

        if not avwap_series or avwap_series[-1] is None:
            return {"avwap": None, "avwapAnchorDate": None}

        avwap_now   = avwap_series[-1]
        price_now   = float(close.iloc[-1])

        # Distanz zum AVWAP
        dist_pct    = round((price_now - avwap_now) / avwap_now * 100, 2) \
                      if avwap_now > 0 else None

        # Slope: AVWAP-Änderung über letzte 5 Bars (positiv = steigend)
        avwap_slope = None
        if len(avwap_series) >= 6:
            avwap_slope = round(
                (avwap_series[-1] - avwap_series[-6]) / avwap_series[-6] * 100, 3
            ) if avwap_series[-6] > 0 else None

        return {
            "avwap":            round(avwap_now, 4),
            "avwapAnchorDate":  str(anchor_date.date()),
            "avwapAnchorPrice": round(anchor_price, 4),
            "distToAvwapPct":   dist_pct,
            "avwapAbove":       bool(price_now >= avwap_now),
            "avwapSlope":       avwap_slope,   # % Änderung über 5 Bars (positiv=steigend)
        }
    except Exception as _e:
        log.debug(f"compute_anchored_vwap Fehler: {_e}")
        return {"avwap": None, "avwapAnchorDate": None,
                "avwapAnchorPrice": None, "distToAvwapPct": None,
                "avwapAbove": None, "avwapSlope": None}


# ── ORDER BLOCK DETECTOR (Hybrid: Zeiierman + BigBeluga + Flux, August 2026) ─
# Detection:  Zeiierman Candle-Flip + ATR-Body-Filter
# Ranking:    qualityScore = size*100 + volScore*10 + trendScore*20
#                            - mitigation*50 - age*0.1
# Volumen:    BigBeluga: obVolPct = segmentVol/totalVol
# Strength:   Flux: bullVolPct vs bearVolPct innerhalb der OB-Zone
# Mitigation: fillDistance/zoneSize (0-100%)

# ── TVA INDICATORS: ADX + DI + Efficiency Ratio (August 2026) ─────────────────
# Basis für TVA Sprint A: f_marketRegime + f_chopIndex aus TVA MathLibrary.
# Alle vectorized via numpy — kein Overhead für 700 Ticker.
def compute_tva_indicators(hist, adx_len=14, er_len=10) -> dict:
    """
    Berechnet ADX, DI+, DI-, Efficiency Ratio und TVA-abgeleitete Regime/Chop-Scores.

    ADX/DI nach Wilder: identisch mit TVA f_htfBundle-Inputs.
    Efficiency Ratio (Perry Kaufman): ER = NetMove / SumMoves über er_len Bars.
      ER=1.0 = perfekter Trend, ER=0.0 = reines Rauschen.

    TVA f_marketRegime (portiert):
      composite = adxScore + erScore + volExpanding + bbExpanding
      8 Regime: Strong Trend Up/Down, Trend Up/Down, Choppy, Volatile, Range, Transitioning
      3-Bar-Hold: verhindert Regime-Flipping

    TVA f_chopIndex (portiert):
      chop = adxChop(30%) + diCancel(25%) + erChop(25%) + bbSqueeze(20%)
      0=kein Chop, 100=maximaler Chop

    Returns dict mit allen Feldern oder Null-Dict bei Fehler.
    """
    import numpy as _np
    _empty = {
        "adx": None, "diPlus": None, "diMinus": None,
        "efficiencyRatio": None, "tvaRegime": None,
        "tvaRegimeConf": None, "chopIndex": None, "chopLabel": None,
    }
    try:
        hi  = hist["High"].dropna().values
        lo  = hist["Low"].dropna().values
        cl  = hist["Close"].dropna().values
        n   = len(cl)
        if n < adx_len * 2 + 5:
            return _empty

        # ── True Range ──────────────────────────────────────────────────────
        tr = _np.maximum(
            hi[1:] - lo[1:],
            _np.maximum(
                _np.abs(hi[1:] - cl[:-1]),
                _np.abs(lo[1:] - cl[:-1])
            )
        )

        # ── Directional Movement ────────────────────────────────────────────
        up   = hi[1:] - hi[:-1]
        down = lo[:-1] - lo[1:]
        dm_plus  = _np.where((up > down) & (up > 0), up,   0.0)
        dm_minus = _np.where((down > up) & (down > 0), down, 0.0)

        # ── Wilder Smoothing (RMA) ──────────────────────────────────────────
        def _rma(arr, length):
            out = _np.zeros(len(arr))
            out[0] = _np.mean(arr[:length])
            alpha = 1.0 / length
            for i in range(1, len(arr)):
                out[i] = (1 - alpha) * out[i-1] + alpha * arr[i]
            return out

        atr_s  = _rma(tr,       adx_len)
        dmp_s  = _rma(dm_plus,  adx_len)
        dmm_s  = _rma(dm_minus, adx_len)

        di_plus  = _np.where(atr_s > 0, dmp_s / atr_s * 100, 0.0)
        di_minus = _np.where(atr_s > 0, dmm_s / atr_s * 100, 0.0)
        dx       = _np.where(
            (di_plus + di_minus) > 0,
            _np.abs(di_plus - di_minus) / (di_plus + di_minus) * 100,
            0.0
        )
        adx_arr  = _rma(dx, adx_len)

        # Aktuelle Werte (letzter Bar)
        adx_val    = round(float(adx_arr[-1]),  2)
        di_p_val   = round(float(di_plus[-1]),  2)
        di_m_val   = round(float(di_minus[-1]), 2)

        # ── Efficiency Ratio (Perry Kaufman) ───────────────────────────────
        if n >= er_len + 1:
            net_move  = _np.abs(cl[-1] - cl[-(er_len+1)])
            sum_moves = _np.sum(_np.abs(_np.diff(cl[-er_len:])))
            er = round(float(net_move / sum_moves), 4) if sum_moves > 0 else 0.0
        else:
            er = None

        # ── BB-Breite für Chop + Regime ────────────────────────────────────
        bb_len = 20
        if n >= bb_len:
            bb_mid  = _np.mean(cl[-bb_len:])
            bb_std  = _np.std(cl[-bb_len:])
            bb_w    = (4 * bb_std) / bb_mid if bb_mid > 0 else 0.0
            bb_w_ma = 0.0
            if n >= bb_len * 2:
                bb_w_ma = float(_np.mean([
                    (4 * _np.std(cl[i-bb_len:i])) / _np.mean(cl[i-bb_len:i])
                    for i in range(n - bb_len, n - bb_len + bb_len)
                    if _np.mean(cl[i-bb_len:i]) > 0
                ]))
        else:
            bb_w = bb_w_ma = 0.0

        # ATR-Ratio (Volatilitäts-Expansion)
        if n >= 50:
            atr_20 = float(_np.mean([
                max(hi[i]-lo[i], abs(hi[i]-cl[i-1]), abs(lo[i]-cl[i-1]))
                for i in range(-20, 0)
            ]))
            atr_50 = float(_np.mean([
                max(hi[i]-lo[i], abs(hi[i]-cl[i-1]), abs(lo[i]-cl[i-1]))
                for i in range(-50, 0)
            ]))
            vol_expanding = atr_20 / atr_50 > 1.5 if atr_50 > 0 else False
        else:
            vol_expanding = False

        # ── TVA f_chopIndex (portiert) ─────────────────────────────────────
        adx_chop  = max(0.0, 100.0 - min(adx_val, 50.0) * 2.0) * 0.30
        di_cancel = 100.0 - min(abs(di_p_val - di_m_val) * 2.5, 100.0)
        di_comp   = di_cancel * 0.25
        er_chop   = max(0.0, (1.0 - min(er or 0, 1.0)) * 100.0) * 0.25 if er is not None else 25.0
        bb_squeeze= max(0.0, (1.0 - bb_w / bb_w_ma) * 100.0) if bb_w_ma > 0.001 else 0.0
        bb_comp   = min(bb_squeeze, 100.0) * 0.20
        chop      = round(adx_chop + di_comp + er_chop + bb_comp, 1)
        chop_lbl  = ("Extreme" if chop >= 70 else "High" if chop >= 55
                     else "Moderate" if chop >= 40 else "Low" if chop >= 25 else "None")

        # ── TVA f_marketRegime (portiert, vereinfacht für Daily) ───────────
        adx_score = 3 if adx_val > 35 else 1 if adx_val >= 20 else 0
        er_score  = 2 if (er or 0) > 0.60 else 1 if (er or 0) >= 0.30 else 0
        bb_exp    = bb_w > bb_w_ma * 1.5 if bb_w_ma > 0.001 else False
        bb_squ    = bb_w < bb_w_ma * 0.7 if bb_w_ma > 0.001 else False
        composite = adx_score + er_score + (1 if vol_expanding else 0) + (1 if bb_exp else 0)
        trending_up = cl[-1] > cl[-6] if n >= 6 else True

        if composite >= 4:
            regime = "Strong Trend Up" if trending_up else "Strong Trend Down"
        elif composite == 3:
            regime = "Trend Up" if trending_up else "Trend Down"
        elif bb_squ:
            regime = "Choppy"
        elif vol_expanding and composite <= 1:
            regime = "Volatile"
        elif composite <= 1 and (er or 0) < 0.30:
            regime = "Range"
        else:
            regime = "Choppy"

        # Konfidenz: wie viele Signale zeigen in dieselbe Richtung
        conf = round(min(composite / 6.0 * 100.0, 100.0), 1)

        return {
            "adx":              adx_val,
            "diPlus":           di_p_val,
            "diMinus":          di_m_val,
            "efficiencyRatio":  er,
            "tvaRegime":        regime,
            "tvaRegimeConf":    conf,
            "chopIndex":        chop,
            "chopLabel":        chop_lbl,
        }
    except Exception as _e:
        log.debug(f"compute_tva_indicators Fehler: {_e}")
        return {
            "adx": None, "diPlus": None, "diMinus": None,
            "efficiencyRatio": None, "tvaRegime": None,
            "tvaRegimeConf": None, "chopIndex": None, "chopLabel": None,
        }


# ── TVA f_stdTrendScore (Sprint A, August 2026) ──────────────────────────────
# Portiert aus TVA MathLibrary. Einheitlich skalierter Trend-Score −100..+100.
# ADX als Konviktions-Multiplikator: schwacher ADX dämpft extremes Ergebnis.
def calc_std_trend_score(price, ema20, ema50, ema200, rsi, adx) -> float | None:
    """
    TVA f_stdTrendScore: Trend Score −100..+100.
    Formel: (emaPart*0.6 + rsiPart*0.4) * (0.5 + 0.5*adxWeight)
    ema20  = EMA20 (kurzfristiger Trend-Proxy)
    ema50  = EMA50
    ema200 = EMA200
    rsi    = RSI14
    adx    = ADX14 (aus compute_tva_indicators)
    """
    if any(v is None for v in (price, ema50, ema200, rsi, adx)):
        return None
    ema20_v = ema20 if ema20 is not None else ema50  # Fallback: EMA50 wenn EMA20 fehlt
    ema_dir = (
        (1 if price   > ema20_v else -1) +
        (1 if price   > ema50   else -1) +
        (1 if ema20_v > ema50   else -1) +
        (1 if price   > ema200  else -1)
    )
    ema_part   = ema_dir / 4.0 * 50.0
    rsi_part   = max(-50.0, min(50.0, float(rsi) - 50.0))
    adx_weight = min(float(adx), 50.0) / 50.0
    raw        = (ema_part * 0.6 + rsi_part * 0.4) * (0.5 + 0.5 * adx_weight)
    return round(max(-100.0, min(100.0, raw)), 1)


# ── TVA f_confluenceScore (Sprint A, August 2026) ────────────────────────────
# 5-Faktor Confluence Score 0–100. Misst Überlagerung von Trend-, Momentum-,
# Volumen-, Struktur- und AVWAP-Support-Signalen.
def calc_confluence_score(r: dict) -> int | None:
    """
    TVA f_confluenceScore: Confluence Score 0–100 (5 Faktoren à max. 20 Punkte).
    Faktoren:
      1. Trend-Struktur    (EMA-Stack + trendScore)
      2. Momentum          (RSI + MACD)
      3. Volumen           (volRatio + OBV-Trend)
      4. AVWAP-Support     (distToAvwapPct — neu aus Sprint v5.22.0)
      5. Order Block Zone  (obBullDistPct — neu aus Sprint v5.24.0)
    Returns int 0-100 oder None bei fehlenden Daten.
    """
    import math as _m
    price      = r.get("price", 0) or 0
    ema50      = r.get("ema50")
    ema200     = r.get("ema200")
    rsi        = r.get("rsi")
    macd_h     = r.get("macdHist")
    obv        = r.get("obvTrend")
    vol_ratio  = r.get("volRatio") or 1.0
    trend_score= r.get("trendScore")  # aus calc_std_trend_score (gerade berechnet)
    dist_avwap = r.get("distToAvwapPct")   # % Abstand AVWAP (positiv = über AVWAP)
    avwap_above= r.get("avwapAbove")
    ob_dist    = r.get("obBullDistPct")    # % Abstand nächster Bull-OB (negativ = OB unter Kurs)

    if not price or not ema50 or not ema200:
        return None

    score = 0

    # ── Faktor 1: Trend-Struktur (0–20 Punkte) ─────────────────────────────
    f1 = 0
    if price > ema50:                   f1 += 8
    if price > ema200:                  f1 += 7
    if ema50 > ema200:                  f1 += 5
    if trend_score is not None:
        if   trend_score >= 50:         f1 = min(20, f1 + 5)
        elif trend_score >= 20:         f1 = min(20, f1 + 2)
        elif trend_score <= -20:        f1 = max(0, f1 - 5)

    # ── Faktor 2: Momentum (0–20 Punkte) ───────────────────────────────────
    f2 = 0
    if rsi is not None:
        if   50 <= rsi <= 70:           f2 += 12   # Bullischer Sweet-Spot
        elif 40 <= rsi <  50:           f2 += 6    # Neutral-Bullisch
        elif rsi > 70:                  f2 += 6    # Überhitzt (weniger ideal)
    if macd_h is not None and macd_h > 0: f2 += 8

    # ── Faktor 3: Volumen (0–20 Punkte) ────────────────────────────────────
    f3 = 0
    if   vol_ratio >= 2.0:             f3 += 12
    elif vol_ratio >= 1.5:             f3 += 8
    elif vol_ratio >= 1.2:             f3 += 4
    if obv is not None and obv > 0:    f3 += 8

    # ── Faktor 4: AVWAP-Support (0–20 Punkte) ──────────────────────────────
    f4 = 0
    if dist_avwap is not None and avwap_above is not None:
        if avwap_above:
            # Über AVWAP: Nähe zur AVWAP = beste Kaufzone
            if   0 <= dist_avwap <= 2:   f4 += 20   # Direkt an AVWAP (optimale Zone)
            elif 0 <= dist_avwap <= 5:   f4 += 14
            elif 0 <= dist_avwap <= 10:  f4 += 8
            else:                         f4 += 3   # Weit über AVWAP
        # Unter AVWAP: kein Bonus (schwache Struktur)

    # ── Faktor 5: Order Block Zone (0–20 Punkte) ────────────────────────────
    f5 = 0
    if ob_dist is not None:
        # ob_dist ist % Abstand zum Bull-OB (negativ = OB unter Kurs = Unterstützung)
        if   -3  <= ob_dist <= 0:       f5 += 20   # Im OB oder direkt darüber
        elif -8  <= ob_dist < -3:       f5 += 12
        elif -15 <= ob_dist < -8:       f5 += 6
        elif ob_dist > 0:               f5 += 2    # Über dem OB (Momentum ohne Basis)

    score = f1 + f2 + f3 + f4 + f5
    return max(0, min(100, score))


def compute_orderblocks(hist, lookback=252, min_body_atr=0.3,
                        trend_ema_len=50, vol_ma_len=20, top_n=3):
    import numpy as _np
    _empty = {"obBull": [], "obBear": [], "obBullBest": None,
              "obBearBest": None, "obBullCount": 0, "obBearCount": 0}
    try:
        op  = hist["Open"].dropna()
        hi  = hist["High"].dropna()
        lo  = hist["Low"].dropna()
        cl  = hist["Close"].dropna()
        vol = hist["Volume"].dropna()
        n   = len(cl)
        if n < 30:
            return _empty
        start = max(0, n - lookback)
        op  = op.iloc[start:]; hi = hi.iloc[start:]
        lo  = lo.iloc[start:]; cl = cl.iloc[start:]
        vol = vol.iloc[start:]; n = len(cl)

        # ATR-14 vectorized
        tr1  = hi.values - lo.values
        tr2  = _np.abs(hi.values - _np.roll(cl.values, 1))
        tr3  = _np.abs(lo.values - _np.roll(cl.values, 1))
        tr   = _np.maximum(tr1, _np.maximum(tr2, tr3)); tr[0] = tr1[0]
        atr_arr = _np.convolve(tr, _np.ones(14)/14, mode='full')[:n]
        atr_arr[:13] = atr_arr[13]

        # EMA für Trend-Score
        ema = float(cl.iloc[0]); alpha = 2.0 / (trend_ema_len + 1)
        ema_arr = []
        for c in cl.values:
            ema = alpha * c + (1 - alpha) * ema; ema_arr.append(ema)
        ema_arr = _np.array(ema_arr)

        # Volumen-MA
        vol_ma = _np.convolve(vol.values, _np.ones(vol_ma_len)/vol_ma_len,
                              mode='full')[:n]
        vol_ma[:vol_ma_len-1] = vol_ma[vol_ma_len-1]

        price_now = float(cl.iloc[-1])
        dates     = cl.index
        bull_obs  = []
        bear_obs  = []

        for i in range(1, n):
            body_i  = abs(cl.iloc[i]   - op.iloc[i])
            atr_i   = atr_arr[i]
            if atr_i <= 0 or body_i < atr_i * min_body_atr:
                continue

            ob_h = float(hi.iloc[i-1])
            ob_l = float(lo.iloc[i-1])
            sz   = ob_h - ob_l
            vs   = float(vol.iloc[i-1]) / float(vol_ma[i-1]) if vol_ma[i-1] > 0 else 1.0
            age  = n - 1 - i

            # ── BULLISH OB: bärische Vorkerze vor bullischer Flip-Kerze ──────
            if cl.iloc[i-1] < op.iloc[i-1] and cl.iloc[i] > op.iloc[i]:
                ts = 1.0 if float(cl.iloc[i]) > ema_arr[i] else 0.0
                lows_s   = lo.iloc[i:].values
                fill_d   = ob_h - float(_np.min(lows_s)) if len(lows_s) else 0
                mit_pct  = round(min(max(fill_d / max(sz, 1e-8) * 100, 0), 100), 1)
                bvol     = float(vol.iloc[i]);   svol = float(vol.iloc[i-1])
                tvol     = bvol + svol
                q = sz*100 + vs*10 + ts*20 - (mit_pct/100)*50 - age*0.1
                d = round((price_now - ob_h) / ob_h * 100, 2) if ob_h > 0 else None
                bull_obs.append({
                    "high": round(ob_h, 4), "low": round(ob_l, 4),
                    "date": str(dates[i-1].date()),
                    "qualityScore": round(q, 2), "mitPct": mit_pct,
                    "volPct": round(vs * 50, 1),
                    "bullVolPct": round(bvol/tvol*100, 1) if tvol > 0 else 50.0,
                    "bearVolPct": round(svol/tvol*100, 1) if tvol > 0 else 50.0,
                    "distPct": d, "ageBars": age,
                    "mitigated": mit_pct >= 100,
                })

            # ── BEARISH OB: bullische Vorkerze vor bärischer Flip-Kerze ──────
            elif cl.iloc[i-1] > op.iloc[i-1] and cl.iloc[i] < op.iloc[i]:
                ts = 1.0 if float(cl.iloc[i]) < ema_arr[i] else 0.0
                highs_s  = hi.iloc[i:].values
                fill_d   = float(_np.max(highs_s)) - ob_l if len(highs_s) else 0
                mit_pct  = round(min(max(fill_d / max(sz, 1e-8) * 100, 0), 100), 1)
                bvol     = float(vol.iloc[i-1]); svol = float(vol.iloc[i])
                tvol     = bvol + svol
                q = sz*100 + vs*10 + ts*20 - (mit_pct/100)*50 - age*0.1
                d = round((ob_l - price_now) / price_now * 100, 2) if price_now > 0 else None
                bear_obs.append({
                    "high": round(ob_h, 4), "low": round(ob_l, 4),
                    "date": str(dates[i-1].date()),
                    "qualityScore": round(q, 2), "mitPct": mit_pct,
                    "volPct": round(vs * 50, 1),
                    "bullVolPct": round(bvol/tvol*100, 1) if tvol > 0 else 50.0,
                    "bearVolPct": round(svol/tvol*100, 1) if tvol > 0 else 50.0,
                    "distPct": d, "ageBars": age,
                    "mitigated": mit_pct >= 100,
                })

        bull_active = sorted([o for o in bull_obs if not o["mitigated"]],
                             key=lambda x: x["qualityScore"], reverse=True)
        bear_active = sorted([o for o in bear_obs if not o["mitigated"]],
                             key=lambda x: x["qualityScore"], reverse=True)
        top_bull = bull_active[:top_n]
        top_bear = bear_active[:top_n]

        # Nächster aktiver Bullish OB unter aktuellem Kurs
        ob_bull_best = None
        cands = [o for o in top_bull if o.get("distPct") is not None and o["distPct"] <= 0]
        ob_bull_best = min(cands, key=lambda x: abs(x["distPct"])) if cands else (top_bull[0] if top_bull else None)

        ob_bear_best = None
        cands = [o for o in top_bear if o.get("distPct") is not None and o["distPct"] >= 0]
        ob_bear_best = min(cands, key=lambda x: x["distPct"]) if cands else (top_bear[0] if top_bear else None)

        return {"obBull": top_bull, "obBear": top_bear,
                "obBullBest": ob_bull_best, "obBearBest": ob_bear_best,
                "obBullCount": len(bull_active), "obBearCount": len(bear_active)}
    except Exception as _e:
        log.debug(f"compute_orderblocks Fehler: {_e}")
        return _empty



# ── EARNINGS CALENDAR (August 2026) ───────────────────────────────────────────
# Robust via yfinance .info['earningsTimestamp'] — stabiler als .calendar
# (Yahoo Finance hat /v7/finance/calendar Endpoint mehrfach geändert)
def compute_earnings_calendar(sym: str) -> dict:
    """
    Holt Earnings-Datum via yfinance.Ticker.info (earningsTimestamp).
    Fallback: get_earnings_dates() für nächste 90 Tage.
    """
    _empty = {"earningsDate": None, "earningsDTE": None,
              "earningsEPS": None, "earningsRevEst": None}
    try:
        from datetime import date as _date, datetime as _dt, timezone as _tz
        import yfinance as _yf

        ticker_obj = _yf.Ticker(sym)

        # Methode 1: earningsTimestamp aus .info (stabiler Endpoint)
        info = ticker_obj.info
        ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
        earnings_dt = None

        if ts:
            earnings_dt = _dt.fromtimestamp(ts, tz=_tz.utc).date()

        # Methode 2: get_earnings_dates() als Fallback
        if earnings_dt is None:
            try:
                dates_df = ticker_obj.get_earnings_dates(limit=4)
                if dates_df is not None and not dates_df.empty:
                    today = _date.today()
                    for idx in dates_df.index:
                        d = idx.date() if hasattr(idx, 'date') else None
                        if d and d >= today:
                            earnings_dt = d
                            break
            except Exception:
                pass

        if earnings_dt is None:
            return _empty

        today = _date.today()
        dte   = (earnings_dt - today).days

        # EPS-Schätzung aus .info
        eps_est = info.get("epsForward") or info.get("epsCurrentYear")
        eps_est = round(float(eps_est), 2) if eps_est else None

        return {
            "earningsDate":   str(earnings_dt),
            "earningsDTE":    dte,
            "earningsEPS":    eps_est,
            "earningsRevEst": None,  # nicht zuverlässig via .info
        }
    except Exception as _e:
        log.debug(f"compute_earnings_calendar({sym}) Fehler: {_e}")
        return {"earningsDate": None, "earningsDTE": None,
                "earningsEPS": None, "earningsRevEst": None}


def calc_ios_market_score(hist_data: dict, vix_term: dict = None) -> dict:
    """
    IOS Market Score v1.0 — Python-Port für UnderlyingIQ Aggregator.
    Bewertet das Marktumfeld für neue Long-Käufe (0-100).
    Quelle: IOS_Market_Score_v1_0 Pine Script (Club-Kolleg:in).

    Module: Trend(35) + Breadth(25) + Risk(20) + Momentum(10) + Rotation(10)
    Knock-out: SPY<SMA200 → cap65 | Risk≤6 → cap70 | Breadth≤8 → cap72
    Decision (17.08.2026, Axel-Entscheidung — Imperativ-Verbot fuer BaFin-
    Konformitaet, s. UEBERGABE-Protokoll: keine Handlungsaufforderungen wie
    "KAUFEN", ausschliesslich deskriptive Zustandsbeschreibungen gebunden an
    Strategie-Klassen, konsistent mit dem parallelen "mode"-Feld):
    OFFENSIV — Trendfolge & Breakouts begünstigt /
    SELEKTIV — Qualitäts-Setups begünstigt /
    NEUTRAL — nur Top-Setups vertretbar /
    DEFENSIV — neue Breakouts zurückhaltend /
    KAPITALSCHUTZ — Absicherung im Fokus
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
        decision = "OFFENSIV — Trendfolge & Breakouts begünstigt"
    elif overall >= 75:
        decision = "SELEKTIV — Qualitäts-Setups begünstigt"
    elif overall >= 60:
        decision = "NEUTRAL — nur Top-Setups vertretbar"
    elif overall >= 45:
        decision = "DEFENSIV — neue Breakouts zurückhaltend"
    else:
        decision = "KAPITALSCHUTZ — Absicherung im Fokus"

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
            # Collar aufwerten: Absicherung bei Gamma-Flip besonders sinnvoll
            if r.get("scoreCollar", 0) > 0:
                r["scoreCollar"] = min(100, int(r["scoreCollar"] * 1.20))
                r["_macroNote"] = r.get("_macroNote", "") + " | Collar aufgewertet (GEX-Flip)"

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
        r["optsScore"] = max(r.get("scoreCsp", 0), r.get("scoreCc", 0), r.get("scoreSpread", 0), r.get("scoreCollar", 0))

    return options_candidates


def apply_ios_market_overlay(options_candidates: list, ios_market: dict) -> list:
    """
    IOS Market Score Overlay auf Options-Kandidaten.
    Bei "KAPITALSCHUTZ — ..." → CSP/CC stark gedämpft (Kapitalschutz).
    Bei "OFFENSIV — ..."      → leichter Bonus für Confidence.
    (17.08.2026: decision-Strings auf imperativfreie Formulierungen
    umgestellt, s. calc_ios_market_score() — String-Vergleiche hier
    entsprechend mitgezogen.)
    """
    if not ios_market:
        return options_candidates
    ims = ios_market.get("iosMarketScore", 60)
    decision = ios_market.get("iosMarketDecision", "")

    for r in options_candidates:
        if decision == "KAPITALSCHUTZ — Absicherung im Fokus":
            # Kapitalschutz: alle Long-Options-Strategien stark dämpfen
            r["scoreCsp"] = max(0, int(r.get("scoreCsp", 0) * 0.30))
            r["scoreCc"]  = max(0, int(r.get("scoreCc",  0) * 0.30))
            # Collar bewusst NICHT gedämpft — Absicherung bei Kapitalschutz sinnvoll
            r["_macroNote"] = r.get("_macroNote","") + " | IOS: KAPITALSCHUTZ"
        elif decision == "DEFENSIV — neue Breakouts zurückhaltend":
            r["scoreCsp"] = max(0, int(r.get("scoreCsp", 0) * 0.55))
            r["_macroNote"] = r.get("_macroNote","") + " | IOS: DEFENSIV"
        elif decision == "NEUTRAL — nur Top-Setups vertretbar":
            r["scoreCsp"] = max(0, int(r.get("scoreCsp", 0) * 0.75))
        elif decision == "OFFENSIV — Trendfolge & Breakouts begünstigt":
            # Leichter Confidence-Bonus
            r["scoreCsp"] = min(100, int(r.get("scoreCsp", 0) * 1.10))
            r["scoreCc"]  = min(100, int(r.get("scoreCc",  0) * 1.10))
        # optsScore neu
        r["optsScore"] = max(r.get("scoreCsp",0), r.get("scoreCc",0), r.get("scoreSpread",0), r.get("scoreCollar",0))
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
        # Dividend-Felder (28.07.2026, Backlog #13b)
        div_raw  = info.get("dividendYield")        # yfinance: meist 0.032 = 3.2%, selten 3.2 direkt
        # Normalisierung: Werte > 0.25 sind bereits in % (z.B. 3.2 statt 0.032)
        if div_raw and div_raw > 0.25:
            div_yield = round(div_raw, 2)            # schon in %, z.B. 3.2
        elif div_raw:
            div_yield = round(div_raw * 100, 2)      # Dezimal → %, z.B. 0.032 → 3.2
        else:
            div_yield = None
        # Sanity-Gate: >25% ist praktisch nie real — Datenfehler abfangen
        if div_yield and div_yield > 25:
            div_yield = None
            log.debug(f"  divYield {sym}: Wert >25% verworfen (Datenfehler yfinance)")
        pr_raw   = info.get("payoutRatio")           # yfinance: meist 0.45 = 45%, selten 45 direkt
        if pr_raw and pr_raw > 1.5:
            payout = round(pr_raw, 1)                # schon in %, z.B. 45.0
        elif pr_raw:
            payout = round(pr_raw * 100, 1)          # Dezimal → %
        else:
            payout = None
        if payout and payout > 200:
            payout = None                             # >200% Payout = Datenfehler
        # Value-Felder (28.07.2026, Backlog #13b)
        pe_fwd   = info.get("forwardPE")
        pe_fwd   = round(pe_fwd, 1) if pe_fwd and pe_fwd > 0 else None
        pb_raw   = info.get("priceToBook")
        pb       = round(pb_raw, 2) if pb_raw and pb_raw > 0 else None
        roe_raw  = info.get("returnOnEquity")        # z.B. 0.18 = 18%
        roe      = round(roe_raw * 100, 1) if roe_raw else None
        return {
            "analystUpside":  upside,
            "fcfYield":       fcf_yield,
            "debtToEquity":   d_eq,
            "divYield":       div_yield,   # % (z.B. 3.2)
            "payoutRatio":    payout,      # % (z.B. 45.0)
            "peForward":      pe_fwd,      # z.B. 18.5
            "pb":             pb,          # Price/Book z.B. 2.1
            "roe":            roe,         # % (z.B. 18.0)
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
        s_breakout  = score_long_breakout(r)   # NEU (21.07.2026)
        s_breakdown = score_short_breakdown(r)
        s_fading    = score_short_fading(r)
        s_csp       = score_options_csp(r)
        s_cc        = score_options_covered_call(r)
        s_vcp       = score_vcp(r)
        s_dividend  = score_long_dividend(r)   # Backlog #13b, 28.07.2026
        s_value     = score_long_value(r)      # Backlog #13b, 28.07.2026
        # KO-Long: Momentum-Setup (Minervini-Basis) + KO-handelbare Preisspanne
        s_ko_long   = s_minervini if (r.get("price") or 0) <= 500 else int(s_minervini * 0.7)

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
            "avgVol20":      r.get("avgVol20"),   # NEU (21.07.2026): Absolutvolumen
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
            "sBreakout":     s_breakout,   # NEU (21.07.2026)
            "sBreakdown":    s_breakdown,
            "sFading":       s_fading,
            "sCsp":          s_csp,
            "sCc":           s_cc,
            "sVcp":          s_vcp,
            "vcpContractions": r.get("vcpContractions"),
            "vcpLastPct":      r.get("vcpLastPct"),
            "sKoLong":       s_ko_long,
            "sDividend":     s_dividend,   # Backlog #13b, 28.07.2026
            "sValue":        s_value,      # Backlog #13b, 28.07.2026
            # Fundamental-Felder (aus enrich_with_fundamentals, nur Shortlist-Kandidaten)
            "divYield":      r.get("divYield"),
            "payoutRatio":   r.get("payoutRatio"),
            "peForward":     r.get("peForward"),
            "pb":            r.get("pb"),
            "roe":           r.get("roe"),
            "bestLong":      best_long,
            "bestShort":     best_short,
            "shortDir":      short_dir,
            # Short-spezifische Felder (Gemini 01.07.2026)
            "squeezeRisk":   squeeze_risk,      # 0-100, >=70 = Fading-Gate geschlossen
            "koShortLev":    ko_short_lev,      # Empfohlener Hebel (3-8) oder None
            # IOS Foundation Rating (Club-Integration)
            **ios_data,
            # TVA Sprint A (August 2026) — für masterShortlist Alpha Desk
            "trendScore":     r.get("trendScore"),
            "confluenceScore": r.get("confluenceScore"),
            "adx":            r.get("adx"),
            "tvaRegime":      r.get("tvaRegime"),
            "chopIndex":      r.get("chopIndex"),
            "chopLabel":      r.get("chopLabel"),
            "distToAvwapPct": r.get("distToAvwapPct"),
            "avwapAbove":     r.get("avwapAbove"),
            "obBullDistPct":  r.get("obBullDistPct"),
            "rsScore":        r.get("rsScore"),
            "rsGrade":        r.get("rsGrade"),
            "rsNewHigh":      r.get("rsNewHigh"),
        })

    # ── LEADERBOARDS (Top 20 je Strategie) ───────────────────────────────────
    def top20(key, min_score=35, extra_fields=None):
        # Kern-Felder: für alle Strategien relevant für KI-Analyse
        # (v5.18.0, 22.07.2026): MACD, OBV, volRatio, HVP, EMA50/200, pctFromHigh52
        # ergänzt — waren bisher nicht im LB-Eintrag, KI-Prompt sagte "Daten fehlen"
        _core = ["sym", "score", "price", "grade", "rsi", "atr",
                 "macdHist", "obvTrend", "volRatio", "hvp",
                 "ema50", "ema200", "pctFromHigh52", "dist200",
                 "bbPos", "sma150", "rsRating", "avgVol20",
                 "high52", "low52", "overheat"]
        return [
            {**{f: x.get(f) for f in _core},
             **({f: x.get(f) for f in extra_fields} if extra_fields else {})}
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
        r["sBreakout"]     = s.get("sBreakout",      0)  # NEU (21.07.2026)
        r["sBreakdown"]    = s.get("sBreakdown",     0)
        r["sFading"]       = s.get("sFading",        0)
        r["bestLong"]      = s.get("bestLong",       0)
        r["bestShort"]     = s.get("bestShort",      0)
        r["shortDir"]      = s.get("shortDir")
        r["squeezeRisk"]   = s.get("squeezeRisk")   # 0-100, >=70 = Fading-Gate zu
        r["koShortLev"]    = s.get("koShortLev")    # Empfohlener Hebel (3-8) oder None
        r["sVcp"]          = s.get("sVcp", 0)
        r["scoreCsp"]      = s.get("sCsp", 0)   # Fix 23.07.2026: fehlte im Merge-Block
        r["scoreCc"]       = s.get("sCc",  0)   # Fix 23.07.2026: fehlte im Merge-Block
        r["tightnessPct"]  = r.get("tightnessPct")  # 5T-Range% aus calc_vcp()

    leaderboards = {
        "long_minervini": top20("sMinervini", 40),
        "long_swing":     top20("sSwing",     35),
        "long_mr":        top20("sMrLong",    30),
        "long_breakout":  top20("sBreakout",  40),   # NEU (21.07.2026)
        "short_breakdown":top20("sBreakdown", 35),
        "short_fading":   top20("sFading",    35),
        "ko_long":        top20("sKoLong",    50),
        "options_csp":    top20("sCsp",       50),
        "options_cc":     top20("sCc",        30),
        "vcp_setups":     top20("sVcp",       40, extra_fields=["vcpContractions", "vcpLastPct", "vcpVolContraction", "vcpBreakoutVol"]),
        "long_dividend":  top20("sDividend",  35, extra_fields=["divYield", "payoutRatio", "fcfYield", "roe"]),   # Backlog #13b
        "long_value":     top20("sValue",     35, extra_fields=["peForward", "pb", "fcfYield", "roe", "analystUpside"]),  # Backlog #13b
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
            # TVA Sprint A (August 2026)
            "trendScore":    c.get("trendScore"),
            "confluenceScore": c.get("confluenceScore"),
            "adx":           c.get("adx"),
            "tvaRegime":     c.get("tvaRegime"),
            "chopIndex":     c.get("chopIndex"),
            "chopLabel":     c.get("chopLabel"),
            "distToAvwapPct": c.get("distToAvwapPct"),
            "avwapAbove":    c.get("avwapAbove"),
            "obBullDistPct": c.get("obBullDistPct"),
            "rsScore":       c.get("rsScore"),
            "rsGrade":       c.get("rsGrade"),
            "rsNewHigh":     c.get("rsNewHigh"),
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
             f"Breakout={len(leaderboards['long_breakout'])} | "
             f"Breakdown={len(leaderboards['short_breakdown'])} | Fading={len(leaderboards['short_fading'])} | "
             f"KO-Long={len(leaderboards['ko_long'])} | CSP={len(leaderboards['options_csp'])} | CC={len(leaderboards['options_cc'])} | VCP={len(leaderboards['vcp_setups'])}")

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


async def enrich_options_watchlist_with_ai(watchlist: list, market_data: dict,
                                             api_key: str | None = None) -> list:
    """
    KI-Enrichment fuer die Options-Watchlist (Phase 0.5 Arbeitspaket F Punkt 2,
    15.07.2026): Claude Sonnet analysiert Top-15 Options-Kandidaten und
    generiert strukturierte Options-Handelsparameter als JSON. Analog zu
    enrich_shortlist_with_ai(), aber Options-spezifisch (Strike/DTE/Delta/
    Praemie statt Trigger/StopLoss/CRV fuer Aktienpositionen).

    WICHTIG: die Strategie-WAHL (CSP vs. Covered Call vs. Credit Spread) wird
    an die KI delegiert (Score-Vergleich CSP/CC/Spread pro Ticker im Prompt),
    NICHT algorithmisch vorentschieden — die 4 Score-Felder (optsScore/
    scoreCsp/scoreCc/scoreSpread) bilden nicht 1:1 auf eine einzelne Strategie
    ab, ein hartes Mapping waere Raten (vgl. Client-seitige Vorsicht in
    Arbeitspaket D/F).
    """
    if not api_key or not watchlist:
        log.warning("  Options-KI-Enrichment: kein API-Key oder leere Watchlist — uebersprungen")
        return watchlist

    import json as json_mod, urllib.request, urllib.error

    enriched = []
    top15 = watchlist[:15]

    vix_term  = market_data.get("vixTerm") or {}
    vix_val   = vix_term.get("vix", "?")
    vix3m_val = vix_term.get("vix3m", "?")
    regime    = market_data.get("regimeUsed", "NEUTRAL")

    for c in top15:
        sym    = c["sym"]
        price  = c.get("price")
        hvp    = c.get("hvp", 0)
        s_csp  = c.get("scoreCsp", 0)
        s_cc   = c.get("scoreCc", 0)
        s_spread = c.get("scoreSpread", 0)
        rsi    = c.get("rsi")
        dist200 = c.get("dist200")

        prompt = f"""Du bist die quantitative Options-Analyse-Engine von UnderlyingIQ.
Erstelle fuer diesen Kandidaten ein praezises Options-Setup-JSON.
Antworte NUR mit dem JSON-Objekt — kein Markdown, kein Praeambel.

MARKTKONTEXT:
- Regime: {regime}
- VIX: {vix_val} (VIX3M: {vix3m_val})
- Fiktives Modell-Depot: 100.000 EUR (BaFin-konforme Deskription gemaess §1 WpHG)

KANDIDAT:
- Ticker: {sym}
- Kurs: {price} USD
- HVP (Historical Vol Percentile): {hvp}%
- RSI(14): {round(rsi, 1) if rsi else 'n/v'}
- Abstand 200-Tage-Linie: {dist200}%
- Scores je Options-Strategie (0-100): CSP={s_csp} | Covered-Call={s_cc} | Credit-Spread={s_spread}

Bestimme zuerst anhand der Scores, welche Options-Strategie fuer diesen Titel
aktuell am besten passt (die mit dem hoechsten Score, es sei denn ein anderer
Faktor spricht klar dagegen). Berechne dann mathematisch praezise (2 Dezimalstellen):
{{
  "sym": "{sym}",
  "strategy": <"csp"|"covered_call"|"credit_spread" — die von dir gewaehlte beste Strategie>,
  "strikeSuggestion": <Strike-Preis in USD, passend zur gewaehlten Strategie>,
  "dte": <Tage bis Verfall: 30-45 Standard, 21-30 bei hoher HVP>,
  "deltaTarget": <Ziel-Delta als Float, z.B. 0.20-0.30 fuer defensives CSP>,
  "premiumEstimate": <geschaetzte Praemie als % des Strikes, informativ>,
  "riskClass": <"LOW"|"MEDIUM"|"HIGH">,
  "keyRisk": <1 Satz: Hauptrisiko dieses Setups>,
  "note": <1 Satz: Wichtigste deskriptive Beobachtung, §1 WpHG-konform>
}}"""

        try:
            req_body = json_mod.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": 350,
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
                text = text.strip()
                if text.startswith("```"):
                    text = '\n'.join(text.split('\n')[1:-1])
                ki_params = json_mod.loads(text)
                enriched.append({**c, "ki": ki_params})
                log.info(f"    Options-KI {sym}: Strategie={ki_params.get('strategy')} | "
                         f"Strike={ki_params.get('strikeSuggestion')} | DTE={ki_params.get('dte')}")
        except Exception as e:
            log.warning(f"    Options-KI {sym} Fehler: {e}")
            enriched.append(c)   # ohne KI-Enrichment

    enriched_syms = {x["sym"] for x in enriched}
    for c in watchlist[15:]:
        if c["sym"] not in enriched_syms:
            enriched.append(c)

    return enriched


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
        ema20v  = ema(closes, 20)[-1] if len(closes) >= 20 else None
        ema50v  = ema(closes, 50)[-1]
        ema200_series = ema(closes, 200) if len(closes) >= 200 else []
        ema200v = ema200_series[-1] if ema200_series else None
        sma150v = sma(closes, 150)[-1] if len(closes) >= 150 else None
        # Minervini-Kriterium: 200-Tage-MA seit ≥1 Monat (≈20 Handelstage) steigend
        # (Pareto-Ergänzung 11.07.2026 — vorher nur Snapshot-Vergleich, keine Steigung)
        ema200_slope_up = None
        if len(ema200_series) >= 21:
            ema200_slope_up = ema200_series[-1] > ema200_series[-21]
        atrv    = calc_atr(highs, lows, closes)
        rsiv    = calc_rsi(closes)
        macd_val, macd_sig, macd_hist = calc_macd(closes)
        obv_tr  = calc_obv_trend(closes, volumes)
        bbpos   = calc_bb(closes)
        overh   = calc_overheat(closes, highs, lows, ema200v, atrv)
        # ── VCP Detection (Sprint 1+2, Preis-Struktur + Volumen, 22.07.2026) ──
        ema150v_for_vcp = sma150v  # sma150 als Trend-Proxy verwendet (bereits berechnet)
        vcp = calc_vcp(closes, highs, lows, ema150=ema150v_for_vcp, volumes=volumes)
        regime, p_bull2bear, bull_pct, warn_level = calc_markov(closes)

        # ── KSI: Kinetic Slippage Index (HPotter, 12.07.2026) ────────────────
        ksi_val, ksi_sig_val, ksi_spike, ksi_ratio = calc_ksi(closes, highs, lows, volumes)

        # ── ICS Trend (ST-EP06, 12.07.2026) ──────────────────────────────────
        opens_col = get_col(hist_df, "Open")
        _ics = calc_ics_trend(closes, highs, lows, opens_col)

        # ── Stop Loss Clustering — Daily-Extrakt (Kioseff, 12.07.2026) ───────
        # Vereinfachtes Modell 1: letzten 5 Swing-Hochs/-Tiefs als Stop-Cluster
        # Kaufstops liegen unterhalb von Swing-Tiefs (SL-Short-Positionen)
        # Verkaufstops liegen oberhalb von Swing-Hochs (SL-Long-Positionen)
        _buy_stop_pct = _sell_stop_pct = None
        try:
            _atr_v = atrv if atrv else 0.01 * price
            if len(highs) >= 20 and len(lows) >= 20:
                # Letzte 5 Swing-Hochs: lokale Maxima (höher als Nachbarn)
                _swing_hi = []
                for _si in range(2, len(highs) - 2):
                    if (highs[_si] > highs[_si-1] and highs[_si] > highs[_si-2] and
                        highs[_si] > highs[_si+1] and highs[_si] > highs[_si+2]):
                        _swing_hi.append(highs[_si] + _atr_v * 0.25)
                # Letzte 5 Swing-Tiefs
                _swing_lo = []
                for _si in range(2, len(lows) - 2):
                    if (lows[_si] < lows[_si-1] and lows[_si] < lows[_si-2] and
                        lows[_si] < lows[_si+1] and lows[_si] < lows[_si+2]):
                        _swing_lo.append(lows[_si] - _atr_v * 0.25)
                # Nächster Verkaufsstopp ÜBER dem Kurs
                _above = [h for h in _swing_hi if h > price]
                if _above:
                    _nearest_sell = min(_above)
                    _sell_stop_pct = round((_nearest_sell / price - 1) * 100, 2)
                # Nächster Kaufstopp UNTER dem Kurs
                _below = [l for l in _swing_lo if l < price]
                if _below:
                    _nearest_buy = max(_below)
                    _buy_stop_pct = round((_nearest_buy / price - 1) * 100, 2)
        except Exception:
            pass

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

        # ── Pattern/Entry-Engine (10.07.2026, Pine-Script-Review) ────────────
        # VCP/Pocket-Pivot/Darvas-Mustererkennung + Entry-Timing. Braucht volle
        # Serien (nicht nur Punktwerte) — zusätzliche EMA/SMA-Berechnungen sind
        # billig (O(n) auf ~500 Bars), lohnt sich ggü. dem Analysewert.
        pattern_entry = None
        if _PATTERN_ENGINE_AVAILABLE:
            try:
                ema9_series   = ema(closes, 9)
                ema21_series  = ema(closes, 21)
                sma50_series  = sma(closes, 50)
                sma150_series = sma(closes, 150)
                sma200_series = sma(closes, 200)
                # score_entry_timing() nutzt RSI nur als Punktwert (kein Zeitreihen-
                # Vergleich intern) — gepolsterte Liste reicht, kein neuer RSI-Serien-
                # Rechner nötig.
                rsi_padded = [None] * (len(closes) - 1) + [rsiv]

                pattern_result = score_pattern_setup(
                    closes, highs, lows, volumes,
                    ema21_series, sma50_series, sma150_series, sma200_series,
                )
                entry_result = score_entry_timing(
                    closes, highs, lows, volumes,
                    ema9_series, ema21_series, sma50_series, sma150_series, sma200_series,
                    rsi_padded,
                )
                pattern_entry = {"pattern": pattern_result, "entry": entry_result}
            except Exception as _pe_err:
                pattern_entry = {"pattern": {"ok": False, "reason": str(_pe_err)[:200]},
                                  "entry":   {"ok": False, "reason": str(_pe_err)[:200]}}

        result = {
            "sym":           ticker,
            "price":         price,
            "ema50":         round(ema50v, 4) if ema50v else None,
            "ema200":        round(ema200v, 4) if ema200v else None,
            "sma150":        round(sma150v, 4) if sma150v else None,
            "ema200SlopeUp": ema200_slope_up,
            "vcpDetected":     vcp["vcpDetected"] if vcp else False,
            "vcpContractions": vcp["vcpContractions"] if vcp else 0,
            "vcpLastPct":      vcp["vcpLastPct"] if vcp else None,
            "vcpAvgPrevPct":   vcp["vcpAvgPrevPct"] if vcp else None,
            "vcpVolContraction":vcp["vcpVolContraction"] if vcp else None,  # NEU (22.07.2026)
            "vcpBreakoutVol":   vcp["vcpBreakoutVol"] if vcp else None,    # NEU (22.07.2026)
            "tightnessPct":     vcp["tightnessPct"]   if vcp else None,    # NEU (23.07.2026) 5T-Range/Kurs% (<3%=Tight)
            "patternEntry":  pattern_entry,
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
            "warnLevel":    warn_level,       # Markov v4: 0=OK, 1=Leicht, 2=Mittel, 3=Kritisch
            "ksi":          ksi_val,          # Kinetic Slippage Index (Effizienz-Indikator)
            "ksiSignal":    ksi_sig_val,      # KSI Signal-Linie (EMA9)
            "ksiSpike":     ksi_spike,        # KSI > Signal (strikte Kreuzung, letzter non-zero Bar)
            "ksiRatio":     ksi_ratio,        # KSI/Signal — dimensionslos, tickerübergreifend vergleichbar
            # ── ICS Trend (ST-EP06) ─────────────────────────────────────────
            "icsDirection":  _ics.get("icsDirection"),    # -1=Bear 0=Flat 1=Bull
            "icsAngle":      _ics.get("icsAngle"),        # ICS-Winkel in Grad
            "icsConsensus":  _ics.get("icsConsensus"),    # 0-6 Skalen einig
            "icsConsBull":   _ics.get("icsConsensusBull"),
            "icsConsBear":   _ics.get("icsConsensusBear"),
            "icsChUpper":    _ics.get("icsChUpper"),      # Obere Kanalline
            "icsChLower":    _ics.get("icsChLower"),      # Untere Kanalline
            "icsBoState":    _ics.get("icsBoState"),      # INSIDE/BO_UP/BO_DN
            "icsChannelPos": _ics.get("icsChannelPos"),  # 0-100% Position im Kanal
            # ── Stop Loss Clustering (Daily-Extrakt) ──────────────────────────
            "nearestSellStopPct": _sell_stop_pct,  # % bis nächster Verkaufsstopp (positiv)
            "nearestBuyStopPct":  _buy_stop_pct,   # % bis nächster Kaufstopp (negativ)
            "bullSignals":   bull_signals,
            "score":         comp_score,
            "grade":         grade,
            "high52":        high52,
            "low52":         low52,
            "pctFromHigh52": pct_from_high52,
            "dist50":        dist_50,
            "dist200":       dist_200,
            "volRatio":      vol_ratio,
            "avgVol20":      round(avg_vol20) if avg_vol20 else None,  # NEU (21.07.2026): Absolutvolumen-Filter
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
            # ── TVA Indicators: ADX + DI + Efficiency Ratio + Regime + Chop (August 2026) ──
            # compute_tva_indicators() nutzt hist_df direkt — kein Extra-Fetch nötig
            # Felder: adx, diPlus, diMinus, efficiencyRatio, tvaRegime, tvaRegimeConf, chopIndex, chopLabel
            **(_tva if (_tva := compute_tva_indicators(hist_df) if hist_df is not None and len(hist_df) >= 35 else {}) else
               {"adx": None, "diPlus": None, "diMinus": None, "efficiencyRatio": None,
                "tvaRegime": None, "tvaRegimeConf": None, "chopIndex": None, "chopLabel": None}),
            # Sektor-Tags (automatisch aus SECTOR_WATCHLISTS invertiert — nie manuell editieren)
            "sectors":       TICKER_SECTOR_TAG.get(ticker, []),
        }

        # ── Earnings Calendar (August 2026) ──────────────────────────────────
        # Platzhalter — Berechnung erfolgt NACH fetch_batch in main()
        # (separater Batch-Call vermeidet 700+ einzelne yf.Ticker()-Requests)
        result["earningsDate"]   = None
        result["earningsDTE"]    = None
        result["earningsEPS"]    = None
        result["earningsRevEst"] = None

        # Fibonacci-Screening-Modul v1.0 (Gemini-Blueprint) — direkt anhängen
        result.update(calc_fibonacci_levels(result))

        # ── RS-Rating Stufe 1: Rohwert (Stufe 2 = Perzentil-Ranking in main()) ─────────────
        # IBD-Annaeherung: gewichtete 12M-Performance, Quartals-Scheiben.
        # Formel: 0.4x3M + 0.2x6M + 0.2x9M + 0.2x12M  (aktuelles Quartal 2x gewichtet)
        perf_3m = perf_6m = perf_9m = perf_12m = None
        if len(closes) >= 63:
            perf_3m  = (closes[-1] / closes[-63]  - 1) * 100
        if len(closes) >= 126:
            perf_6m  = (closes[-1] / closes[-126] - 1) * 100
        if len(closes) >= 189:
            perf_9m  = (closes[-1] / closes[-189] - 1) * 100
        if len(closes) >= 252:
            perf_12m = (closes[-1] / closes[-252] - 1) * 100
        # Rohwert nur wenn mindestens 6M-Daten vorhanden (sonst Ranking verzerrt)
        perf_rs_raw = None
        if perf_6m is not None:
            weights = [(0.4, perf_3m), (0.2, perf_6m), (0.2, perf_9m), (0.2, perf_12m)]
            wsum = wdiv = 0.0
            for w, v in weights:
                if v is not None:
                    wsum += w * v
                    wdiv += w
            perf_rs_raw = round(wsum / wdiv, 4) if wdiv > 0 else None
        result["perfRsRaw"]  = perf_rs_raw
        result["perf3m"]     = round(perf_3m,  2) if perf_3m  is not None else None
        result["perf6m"]     = round(perf_6m,  2) if perf_6m  is not None else None
        result["perf12m"]    = round(perf_12m, 2) if perf_12m is not None else None
        result["rsRating"]   = None   # wird in main() Stufe 2 befuellt

        # ── RS-Rank Score (IOS Konzept-Integration, August 2026) ────────────
        # Berechnung erfolgt in main() nach fetch_batch, wenn SPY/IWM hist_data verfügbar.
        # Hier Platzhalter damit KV-Schema konsistent bleibt.
        result["rsScore"]     = None   # 0-100, kombiniert SPY+IWM Benchmark
        result["rsScoreSpy"]  = None   # 0-100 vs. SPY
        result["rsScoreIwm"]  = None   # 0-100 vs. IWM
        result["rsNewHigh"]   = None   # bool: RS-Line auf 63T-Hoch
        result["rsGrade"]     = None   # A+/A/B.../F

        # ── Anchored VWAP (Zeiierman-Konzept, August 2026) ──────────────────────
        # Berechnung in process_ticker direkt (hist_df verfügbar).
        # ETF/Krypto-Filter: AVWAP ist für Einzel-Aktien konzipiert —
        # ETF-NAV hat keinen institutionellen Anker; Krypto zu volatil.
        _AVWAP_SKIP_SET = set(SECTOR_ETFS + CRYPTO_TICKERS)
        _is_etf_or_crypto = (
            ticker in _AVWAP_SKIP_SET or
            ticker.endswith("-USD")
        )
        if hist_df is not None and len(hist_df) >= 20 and not _is_etf_or_crypto:
            _avwap = compute_anchored_vwap(hist_df, apt=20)
        else:
            _avwap = {"avwap": None, "avwapAnchorDate": None,
                      "avwapAnchorPrice": None, "distToAvwapPct": None,
                      "avwapAbove": None, "avwapSlope": None}
        result["avwap"]             = _avwap.get("avwap")
        result["avwapAnchorDate"]   = _avwap.get("avwapAnchorDate")
        result["avwapAnchorPrice"]  = _avwap.get("avwapAnchorPrice")
        result["distToAvwapPct"]    = _avwap.get("distToAvwapPct")
        result["avwapAbove"]        = _avwap.get("avwapAbove")
        result["avwapSlope"]        = _avwap.get("avwapSlope")

        # ── TVA f_stdTrendScore (Sprint A, August 2026) ──────────────────────
        # Berechnung nach AVWAP (distToAvwapPct verfügbar) und TVA-Indikatoren (adx).
        # EMA20 lokal berechnet (ema20v), ADX aus compute_tva_indicators (_tva).
        _adx_for_ts = result.get("adx")
        result["trendScore"] = calc_std_trend_score(
            price, ema20v, ema50v, ema200v, rsiv, _adx_for_ts
        )

        # ── TVA f_confluenceScore (Sprint A, August 2026) ─────────────────────
        # Aggregiert 5 Signalschichten: Trend, Momentum, Volumen, AVWAP, OB.
        # Reihenfolge: nach OB-Feldern berechnen (obBullDistPct bereits in result).
        result["confluenceScore"] = None  # Platzhalter — befüllt nach OB-Block unten

        # ── Order Blocks (Hybrid OB-Detector, August 2026) ───────────────────
        # ETF/Krypto-Filter wie bei AVWAP: OBs nur für Einzel-Aktien sinnvoll
        if hist_df is not None and len(hist_df) >= 30 and not _is_etf_or_crypto:
            _ob = compute_orderblocks(hist_df, lookback=252,
                                      min_body_atr=0.3, top_n=3)
        else:
            _ob = {"obBullBest": None, "obBearBest": None,
                   "obBullCount": 0,  "obBearCount": 0}
        _obb = _ob.get("obBullBest") or {}
        _obbe= _ob.get("obBearBest") or {}
        result["obBullHigh"]    = _obb.get("high")
        result["obBullLow"]     = _obb.get("low")
        result["obBullDate"]    = _obb.get("date")
        result["obBullScore"]   = _obb.get("qualityScore")
        result["obBullDistPct"] = _obb.get("distPct")
        result["obBullMitPct"]  = _obb.get("mitPct")
        result["obBullVolPct"]  = _obb.get("bullVolPct")
        result["obBearHigh"]    = _obbe.get("high")
        result["obBearLow"]     = _obbe.get("low")
        result["obBearDate"]    = _obbe.get("date")
        result["obBearScore"]   = _obbe.get("qualityScore")
        result["obBearDistPct"] = _obbe.get("distPct")
        result["obBearMitPct"]  = _obbe.get("mitPct")
        result["obBearVolPct"]  = _obbe.get("bearVolPct")
        result["obBullCount"]   = _ob.get("obBullCount", 0)
        result["obBearCount"]   = _ob.get("obBearCount", 0)

        # ── TVA f_confluenceScore — finale Berechnung nach OB-Block ──────────
        # Alle 5 Faktoren (inkl. obBullDistPct + distToAvwapPct) jetzt verfügbar.
        result["confluenceScore"] = calc_confluence_score(result)

        # ── Breadth-Oszillator: Advance-Flag (27.07.2026, SUITE.md Backlog #12) ──
        # True = heute höher als gestern, False = tiefer, None = Daten fehlen
        result["advance"] = (
            closes[-1] > closes[-2]
            if len(closes) >= 2 and closes[-2] > 0
            else None
        )

        # ── Rohdaten-Cache für Sprint B Layer (reg_vp + cluster) ─────────────
        # Werden nach Layer-Aufruf via .pop() entfernt — nicht in KV geschrieben.
        result["_closes"]    = closes
        result["_highs"]     = highs
        result["_lows"]      = lows
        result["_volumes"]   = volumes
        result["_closes_cl"] = closes
        result["_highs_cl"]  = highs
        result["_lows_cl"]   = lows
        result["_volumes_cl"] = volumes

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
    """DIX/GEX von squeezemetrics (SPY-marktweit, taeglich).

    PRIORITAET GETAUSCHT (14.08.2026): squeezemetrics wurde am 09.07.2026
    (v4.8) faelschlich als "historisch, meist 403" eingestuft und deshalb
    hinter FlashAlpha zurueckgestellt. Stability-Check 10.-13.08.2026
    (s. docs/GEX-SCHEMA.md v0.6, data/datasource_stability/log.jsonl):
    16/16 Requests HTTP 200, 100% Erfolgsquote, kostenlos, kein Auth.
    Liefert ECHTES SPY-marktweites DIX+GEX (Squeezemetrics-Originalmethodik).

    NEU (17.08.2026, Axel-Deep-Debug-Anfrage — DIX/GEX-Bulk-Historie-Neben-
    fund, urspruenglich aus REGIME-BACKTEST-VALIDIERUNG.md, 16.08.2026 noch
    unverifiziert): Live-verifiziert per Browser-Fetch — DIX.csv liefert
    NICHT nur die aktuellste Zeile, sondern die VOLLE taegliche Historie
    seit 2011-05-02 (3846 Zeilen, Stand 17.08.2026), komplett kostenlos.
    Bisher wurde ausschliesslich die letzte Zeile genutzt (dix/gex "heute").
    Jetzt zusaetzlich: die letzten HISTORY_DAYS Handelstage als "history"-
    Feld im Rueckgabewert, fuer clientseitigen Backfill der lokalen Z-Score-
    Historie (KoMarketState._history.gex/.dix, s. ko-market-state.js) —
    vorher musste diese Historie erst ueber mehrere Tage/Wochen Live-Betrieb
    akkumuliert werden (Symptom: "DIX Z-Score n/v - keine Historie" am
    17.08.2026 nach dem Wochenende, s. UEBERGABE-Protokoll).

    Primaer:  squeezemetrics.com (DIX + GEX, SPY-Aggregat, kostenlos, stabil).
    Sekundaer (bewusst erhalten, s.u.): FlashAlpha API (lab.flashalpha.com) —
    liefert Werte, die squeezemetrics NICHT hat: gamma_flip, call_wall,
    put_wall (echte Optionsketten-basierte Gamma-Levels statt nur ein
    DIX/GEX-Aggregatwert). Free-Tier kann aber nur Einzeltitel (AAPL-Test,
    kein SPY/QQQ) — Basic-Tier (SPY/QQQ + alle Exposure-Endpoints) bisher
    NICHT aktiviert. Bis zur Aktivierung liefert dieser Pfad praktisch keine
    marktweit nutzbaren Daten, bleibt aber im Code fuer die spaetere
    Basic-Tier-Option.

    Endpoint (FlashAlpha v1): GET /v1/exposure/gex/{ticker}?expiration=YYYY-MM-DD
    Auth: X-Api-Key Header
    """
    import os

    # Anzahl Handelstage fuer den History-Backfill — deckt sich mit dem
    # Cap in KoMarketState.addDataPoint() (Client, max 60 Punkte je Serie).
    HISTORY_DAYS = 60

    # ── PRIMAER: squeezemetrics (SPY-marktweit, DIX+GEX) ──────────────────
    try:
        url = "https://squeezemetrics.com/monitor/static/DIX.csv"
        r = requests.get(url, timeout=10, headers={"User-Agent": "curl/8.5.0"})
        if r.status_code == 200 and len(r.text) > 100:
            lines = r.text.strip().splitlines()
            headers = lines[0].lower().strip().split(",")
            last    = lines[-1].strip().split(",")
            row     = dict(zip(headers, last))
            dix_val = float(row.get("dix", 0)) * 100
            gex_val = float(row.get("gex", 0))
            log.info(f"  DIX (squeezemetrics): {dix_val:.1f}% | GEX: {gex_val/1e9:.2f} Mrd")

            # ── History-Backfill: letzte HISTORY_DAYS Zeilen parsen ─────────
            hist_dates, hist_dix, hist_gex = [], [], []
            for hl in lines[1:][-HISTORY_DAYS:]:
                parts = hl.strip().split(",")
                if len(parts) < 4:
                    continue
                hrow = dict(zip(headers, parts))
                try:
                    h_dix = round(float(hrow.get("dix", 0)) * 100, 2)
                    h_gex = round(float(hrow.get("gex", 0)) / 1e9, 3)
                except (ValueError, TypeError):
                    continue
                hist_dates.append(hrow.get("date", ""))
                hist_dix.append(h_dix)
                hist_gex.append(h_gex)
            log.info(f"  DIX/GEX History-Backfill: {len(hist_dates)} Handelstage "
                     f"({hist_dates[0] if hist_dates else '?'} bis {hist_dates[-1] if hist_dates else '?'})")

            return {
                "dix":    round(dix_val, 2),
                "gex":    round(gex_val / 1e9, 3),
                "date":   row.get("date", ""),
                "source": "squeezemetrics",
                "proxy":  False,
                "history": {
                    "dates": hist_dates,
                    "dix":   hist_dix,
                    "gex":   hist_gex,
                    "n":     len(hist_dates),
                },
            }
        else:
            log.warning(f"  squeezemetrics unerwartete Antwort: HTTP {r.status_code}, {len(r.text)} Bytes")
    except Exception as e:
        log.warning(f"  squeezemetrics nicht verfuegbar: {e}")

  # ── SEKUNDAER: FlashAlpha (nur gamma_flip/call_wall/put_wall, kein
    #    marktweites DIX/GEX solange Basic-Tier nicht aktiviert) ──────────
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


def _finra_get_token(client_id: str, client_secret: str) -> str:
    """OAuth2 Client-Credentials-Flow für die FINRA API Platform.
    Token ist laut FINRA-Doku ca. 12h gültig (expires_in in Sekunden).
    Sollte pro Aggregator-Lauf einmal geholt werden (kein Caching zwischen
    Läufen nötig — ein Run dauert Sekunden, nicht Stunden).
    """
    import base64 as b64
    auth_str = b64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    url = "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token?grant_type=client_credentials"
    r = requests.post(url, headers={"Authorization": f"Basic {auth_str}"}, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data["access_token"]


def resolve_company_name_to_ticker(name: str) -> dict:
    """Löst einen Firmennamen zu einem US-Ticker via Yahoo Finance Search auf.
    Serverseitig via requests — kein CORS-Proxy nötig (anders als im Frontend,
    das per Browser-fetch() an CORS-Beschränkungen gebunden ist). Gleiche
    Filterlogik wie das Frontend-Pendant (searchTickerByName in index.html):
    nur EQUITY-Quotes, keine Indizes/Forex, keine ISIN-artigen Symbole.

    Fallback (11.07.2026, nach Praxis-Test): Aktienklassen-Zusätze ("Class A",
    "Class B", "Class C") verwirren Yahoo's Fuzzy-Suche teils (z.B. "Palantir
    Technologies Inc. Class A" fand keinen Treffer, "Palantir Technologies
    Inc." allein schon). Bei Fehlschlag wird automatisch ohne diesen Zusatz
    erneut gesucht, bevor endgültig aufgegeben wird.
    """
    def _search_once(query):
        try:
            r = requests.get(
                "https://query1.finance.yahoo.com/v1/finance/search",
                params={"q": query, "lang": "en", "region": "US", "quotesCount": 5, "newsCount": 0},
                timeout=10, headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code != 200:
                return {"ok": False, "reason": f"HTTP {r.status_code}"}
            quotes = r.json().get("quotes", [])
            filtered = []
            for q in quotes:
                if q.get("quoteType") != "EQUITY":
                    continue
                sym = q.get("symbol", "")
                if not sym or "^" in sym or "=" in sym:
                    continue
                if len(sym) == 12 and sym[:2].isalpha() and sym[2:].isalnum():
                    continue
                if len(sym.replace(".", "").replace("-", "")) > 7:
                    continue
                filtered.append(q)
            if not filtered:
                return {"ok": False, "reason": "kein Treffer"}
            best = filtered[0]
            return {"ok": True, "ticker": best.get("symbol"),
                    "name": best.get("shortname") or best.get("longname")}
        except Exception as e:
            return {"ok": False, "reason": str(e)[:150]}

    result = _search_once(name)
    if result.get("ok"):
        return result

    # Fallback: Aktienklassen-Zusätze entfernen und erneut versuchen
    import re as _re
    simplified = _re.sub(r"\s+Class\s+[A-Z]$", "", name).strip()
    if simplified != name:
        fallback = _search_once(simplified)
        if fallback.get("ok"):
            fallback["reason"] = f"Fallback ohne Klassen-Zusatz (Original: '{name}')"
            return fallback

    return result


def parse_ssga_holdings_xlsx(filepath: str, top_n: int = 15) -> list:
    """Parst SSGA/SPDR EMEA-UCITS-Holdings-XLSX und gibt Top-N-Positionen zurück.
    Format (verifiziert 19.07.2026 gegen alle 10 Sektor-ETFs ZPDT/ZPDF/ZPDE/etc.):
    Zeile 0-4: Metadaten (Fund Name, ISIN, Ticker, Holdings As Of)
    Zeile 5: Header (ISIN | SEDOL | Security Name | Currency | Shares | Percent of Fund)
    Zeile 6+: Holdings-Daten
    Kein Ticker-Feld in EMEA-Format — Ticker-Aufloesung via Name-Matching in
    build_sector_holdings() gegen IWV-Holdings-CSV + MANUAL_NAME_MAP."""
    import openpyxl as _opxl
    wb = _opxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    out = []
    for row in rows[6:]:
        if not row or not row[0]:
            break
        name = str(row[2]).strip() if row[2] else None
        try:
            weight = float(str(row[5]).replace(",", ".")) if row[5] else None
        except (ValueError, TypeError):
            weight = None
        if name and name not in ("Security Name", "None", ""):
            out.append({
                "name": name,
                "weight": round(weight, 4) if weight else None,
                "sector": None,  # EMEA-Format hat kein Sektor-Feld
            })
        if len(out) >= top_n:
            break
    return out


def build_sector_holdings(etf_ticker: str, xlsx_path: str, top_n: int = 15) -> dict:
    """Kombiniert Holdings-Parsing + Ticker-Auflösung für einen Sektor-ETF.
    Rückgabe direkt für den Aggregator-Output (market.sectorHoldings.{ETF})."""
    try:
        holdings = parse_ssga_holdings_xlsx(xlsx_path, top_n=top_n)
    except Exception as e:
        return {"ok": False, "reason": f"Parsing-Fehler: {str(e)[:150]}"}

    # Name → Symbol Aufloesung: zuerst MANUAL_NAME_MAP, dann IWV-Name-Match
    MANUAL_NAME_MAP = {
        "VISA INC. CLASS A": "V", "VISA INC CLASS A": "V",
        "MASTERCARD INCORPORATED C": "MA", "MASTERCARD INCORPORATED CLA": "MA",
        "MERCK & CO. INC.": "MRK", "MERCK & CO INC.": "MRK",
        "ALPHABET INC. CLASS A": "GOOGL", "ALPHABET INC CLASS A": "GOOGL",
        "ALPHABET INC. CLASS C": "GOOG", "ALPHABET INC CLASS C": "GOOG",
        "MCDONALD'S CORPORATION": "MCD", "MCDONALDS CORPORATION": "MCD",
        "FREEPORT-MCMORAN INC.": "FCX", "FREEPORT-MCMORAN INC": "FCX",
        "SHERWIN-WILLIAMS COMPANY": "SHW",
        "EXXONMOBIL HOLDINGS CORPO": "XOM", "EXXONMOBIL CORPORATION": "XOM",
        "WILLIAMS COMPANIES INC.": "WMB", "WILLIAMS COMPANIES INC": "WMB",
        "TJX COMPANIES INC": "TJX", "TJX COMPANIES INC.": "TJX",
        "CRH PUBLIC LIMITED COMPAN": "CRH",
        "BERKSHIRE HATHAWAY INC. C": "BRK.B", "BERKSHIRE HATHAWAY INC C": "BRK.B",
        "PALANTIR TECHNOLOGIES INC. CLA": "PLTR", "PALANTIR TECHNOLOGIES INC CLA": "PLTR",
    }

    # IWV-Name→Symbol-Cache (einmalig laden)
    _iwv_map = {}
    _iwv_path = "data/iwv_holdings.csv"
    try:
        import csv as _csv
        with open(_iwv_path, newline="", encoding="utf-8") as fh:
            _reader = _csv.reader(fh)
            _hdr = False
            for _row in _reader:
                if _row and _row[0] == "Ticker":
                    _hdr = True; continue
                if _hdr and len(_row) >= 2 and _row[0]:
                    _iwv_map[_row[1].strip().upper()] = _row[0].strip()
    except Exception:
        pass

    def _resolve(name):
        nu = name.upper().strip()
        if nu in MANUAL_NAME_MAP: return MANUAL_NAME_MAP[nu]
        for k, v in MANUAL_NAME_MAP.items():
            if nu.startswith(k[:12]) or k.startswith(nu[:12]): return v
        if nu in _iwv_map: return _iwv_map[nu]
        for iwv_name, sym in _iwv_map.items():
            if nu[:15] in iwv_name or iwv_name[:15] in nu: return sym
        return None

    resolved = []
    unresolved = 0
    for h in holdings:
        sym = _resolve(h["name"])
        if sym:
            resolved.append({"ticker": sym, "name": h["name"], "weight": h["weight"]})
        else:
            unresolved += 1
            resolved.append({"ticker": None, "name": h["name"], "weight": h["weight"]})

    return {
        "ok": True,
        "etf": etf_ticker,
        "holdings": resolved,
        "resolvedCount": len(resolved) - unresolved,
        "totalCount": len(resolved),
        "source": "ssga_ucits_proxy",
    }


def fetch_finra_dix() -> dict:
    """Echter DIX (Dark Pool Index) via FINRA Query API — regShoDaily-Dataset.

    v3 (10.07.2026, nach zwei Testläufen): Echte Feldnamen jetzt bekannt
    (securitiesInformationProcessorSymbolIdentifier, totalParQuantity,
    shortParQuantity, tradeReportDate, reportingFacilityCode, marketCode).
    Ein Symbol kann MEHRERE Zeilen haben (je Marktzentrum/TRF) — werden
    aufsummiert. Kein Datum im ersten Batch (5000 Zeilen) gefunden für unsere
    4 Ticker → Pagination über mehrere Seiten statt Filter-Payload-Raten
    (FINRA's compareFilter-Syntax bleibt unklar, GET+Pagination ist dokumentiert
    und robust).

    Methodik nach SqueezeMetrics-Whitepaper "Short is Long": Short-Volumen
    relativ zum Gesamtvolumen, ETF-Korb (SPY/QQQ/IWM/DIA) als Marktbreite-Proxy.

    Benötigt Secrets: FINRA_CLIENT_ID, FINRA_CLIENT_SECRET
    """
    import os

    client_id = os.environ.get("FINRA_CLIENT_ID", "")
    client_secret = os.environ.get("FINRA_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        log.warning("  FINRA DIX: FINRA_CLIENT_ID/SECRET nicht gesetzt — übersprungen")
        return {"ok": False, "reason": "keine Zugangsdaten"}

    TICKERS = {"SPY", "QQQ", "IWM", "DIA"}
    SYM_FIELD = "securitiesInformationProcessorSymbolIdentifier"
    SHORT_FIELD = "shortParQuantity"
    TOTAL_FIELD = "totalParQuantity"
    DATE_FIELD = "tradeReportDate"

    try:
        token = _finra_get_token(client_id, client_secret)
    except Exception as e:
        log.warning(f"  FINRA OAuth2-Token-Fehler: {e}")
        return {"ok": False, "reason": f"Token-Fehler: {str(e)[:150]}"}

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data_url = "https://api.finra.org/data/group/otcMarket/name/regShoDaily"

    all_rows = []
    MAX_PAGES = 8
    PAGE_SIZE = 5000

    try:
        for page in range(MAX_PAGES):
            r = requests.get(data_url, headers=headers,
                             params={"limit": PAGE_SIZE, "offset": page * PAGE_SIZE},
                             timeout=30)
            if r.status_code != 200:
                log.warning(f"  FINRA regShoDaily Seite {page}: HTTP {r.status_code} — {r.text[:150]}")
                break
            rows = r.json()
            if not isinstance(rows, list) or not rows:
                break
            all_rows.extend(rows)
            total_hdr = r.headers.get("Record-Total")
            log.info(f"  FINRA Seite {page}: {len(rows)} Zeilen (Record-Total Header: {total_hdr})")
            if len(rows) < PAGE_SIZE:
                break  # letzte Seite erreicht
            # Sobald unsere Ticker in den bisherigen Zeilen auftauchen, reicht's
            found_syms = {row.get(SYM_FIELD) for row in all_rows}
            if TICKERS.issubset(found_syms):
                log.info(f"  FINRA: alle 4 Ticker nach Seite {page} gefunden, breche Pagination ab")
                break

        if not all_rows:
            return {"ok": False, "reason": "keine Zeilen über alle Seiten erhalten"}

        # Neuestes Datum ermitteln (T+1-Meldeverzug — "heute" evtl. noch nicht da)
        dates_seen = {row.get(DATE_FIELD) for row in all_rows if row.get(DATE_FIELD)}
        latest_date = max(dates_seen) if dates_seen else None

        # Pro Ticker über ALLE Marktzentren/TRFs summieren, nur neuestes Datum
        total_short = 0.0
        total_volume = 0.0
        per_ticker = {}
        matched_syms = set()

        for row in all_rows:
            sym = row.get(SYM_FIELD)
            if sym not in TICKERS:
                continue
            if latest_date and row.get(DATE_FIELD) != latest_date:
                continue
            short_v = float(row.get(SHORT_FIELD) or 0)
            total_v = float(row.get(TOTAL_FIELD) or 0)
            if total_v <= 0:
                continue
            matched_syms.add(sym)
            entry = per_ticker.setdefault(sym, {"short": 0.0, "total": 0.0})
            entry["short"] += short_v
            entry["total"] += total_v
            total_short += short_v
            total_volume += total_v

        log.info(f"  FINRA DIX: {len(all_rows)} Zeilen total über {page+1} Seite(n), "
                 f"neuestes Datum {latest_date}, {len(matched_syms)}/{len(TICKERS)} Ticker gefunden: {sorted(matched_syms)}")

        if not matched_syms or total_volume == 0:
            sample = all_rows[0] if all_rows else {}
            return {"ok": False,
                    "reason": f"Ticker nicht gefunden (Datum {latest_date}, {len(all_rows)} Zeilen durchsucht)",
                    "sample_keys": list(sample.keys()), "n_rows": len(all_rows)}

        for sym, v in per_ticker.items():
            v["pct"] = round(v["short"] / v["total"] * 100, 2) if v["total"] else None

        dix_pct = round(total_short / total_volume * 100, 2)
        log.info(f"  FINRA DIX (echt): {dix_pct}% am {latest_date} "
                 f"(Short {total_short:.0f} / Total {total_volume:.0f})")

        return {
            "ok": True,
            "dix": dix_pct,
            "date": latest_date,
            "perTicker": per_ticker,
            "basket": sorted(matched_syms),
            "methodology": "ETF-Korb-Proxy (SPY/QQQ/IWM/DIA), Summe über alle Marktzentren/TRFs",
            "source": "finra_regshodaily",
            "proxy": False,
        }

    except Exception as e:
        log.warning(f"  FINRA regShoDaily Fehler: {e}")
        return {"ok": False, "reason": str(e)[:200]}



def fetch_finra_dix_csv(sp500_tickers: list = None) -> dict:
    """Echter DIX (Dark Pool Index) via FINRA Reg SHO Daily CSV-Download.

    STABILER als fetch_finra_dix() (kein OAuth2, kein Query-API-Parsing).
    Direkt-Download: https://cdn.finra.org/equity/regsho/daily/CNMSshvol{DATE}.txt
    Format: Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market|Date
    Öffentlich, keine Credentials nötig, täglich aktualisiert.

    Methodik (nach SqueezeMetrics Whitepaper "Short is Long"):
      DIX = Σ(ShortVolume_i × Price_i) / Σ(TotalVolume_i × Price_i)
      Σ über alle S&P 500 Komponenten
      Dollar-gewichtet: größere Aktien (Apple, Nvidia) haben mehr Einfluss.

    Normalisierung: tanh-Skalierung über 252T-Rolling-Window (analog SqueezeMetrics).
    Ohne Normalisierung: roher Prozentwert (typisch 40-50%).

    sp500_tickers: Liste der S&P 500 Ticker aus build_ticker_universe() oder
                   dem IWV-Universum. Wenn None: nur ETF-Proxy (SPY/QQQ/IWM/DIA).

    Source: https://cdn.finra.org/equity/regsho/daily/
    """
    from datetime import datetime, timedelta, timezone
    import math

    BASE_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt"
    HEADERS  = {
        "User-Agent": "Mozilla/5.0 (compatible; UIQ-Aggregator/5.0)",
        "Accept": "text/plain,*/*",
    }
    # Fallback-Universum wenn keine Ticker übergeben
    FALLBACK = {"SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN",
                "META", "GOOGL", "TSLA", "BRK-B", "JPM", "UNH", "XOM",
                "V", "MA", "HD", "PG", "LLY"}

    universe = set(sp500_tickers or []) or FALLBACK

    # ── Letzten verfügbaren Handelstag ermitteln (T+1 Meldeverzug) ───────────
    now = datetime.now(timezone.utc)
    # Versuche heute und die letzten 5 Tage (Wochenenden, Feiertage)
    for days_back in range(1, 7):
        check_date = (now - timedelta(days=days_back)).strftime("%Y%m%d")
        url = BASE_URL.format(date=check_date)
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200 and len(r.text) > 500:
                break
            log.debug(f"  FINRA DIX CSV: {check_date} nicht verfügbar (HTTP {r.status_code})")
        except Exception as e:
            log.debug(f"  FINRA DIX CSV: {check_date} Fehler: {e}")
    else:
        return {"ok": False, "reason": "FINRA CSV nicht verfügbar (letzte 6 Tage)"}

    log.info(f"  FINRA DIX CSV: {url}")

    # ── CSV parsen ────────────────────────────────────────────────────────────
    # Format: Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market|Date
    # Letzte Zeile oft "Date|" Header-Wiederholung → überspringen
    ticker_data = {}  # {sym: {short: float, total: float}}

    for line in r.text.splitlines():
        parts = line.strip().split("|")
        if len(parts) < 4:
            continue
        sym = parts[0].strip().upper()
        if sym in ("SYMBOL", "DATE", "") or not sym.isalpha() and "-" not in sym:
            continue
        if sym not in universe:
            continue
        try:
            short_v = float(parts[1])
            total_v = float(parts[3])
        except (ValueError, IndexError):
            continue
        if total_v <= 0:
            continue
        entry = ticker_data.setdefault(sym, {"short": 0.0, "total": 0.0})
        entry["short"] += short_v
        entry["total"] += total_v

    if not ticker_data:
        return {
            "ok": False,
            "reason": f"Keine Universum-Ticker in FINRA-Datei gefunden (Datum: {check_date})",
            "sample": r.text[:300],
        }

    # ── Dollar-gewichteter DIX ────────────────────────────────────────────────
    # Echte Dollar-Gewichtung: ShortVolume × Price / TotalVolume × Price
    # Vereinfachung ohne Live-Preise: gleichgewichtetes Short-Volume-Ratio
    # (gleiche Qualität wie SqueezeMetrics ETF-Proxy, besser als 4-Ticker-Version)
    total_short_vol = sum(v["short"] for v in ticker_data.values())
    total_vol       = sum(v["total"] for v in ticker_data.values())

    if total_vol == 0:
        return {"ok": False, "reason": "Gesamtvolumen null"}

    dix_raw = total_short_vol / total_vol * 100  # in Prozent, typisch 40-50%

    # Rohe Short-Ratio je Ticker
    per_ticker = {
        sym: {
            "short": v["short"],
            "total": v["total"],
            "pct":   round(v["short"] / v["total"] * 100, 2),
        }
        for sym, v in ticker_data.items()
    }

    log.info(
        f"  FINRA DIX CSV ✅: {round(dix_raw, 2)}% am {check_date} | "
        f"{len(ticker_data)}/{len(universe)} Ticker | "
        f"Short {total_short_vol:.0f} / Total {total_vol:.0f}"
    )

    return {
        "ok":          True,
        "dix":         round(dix_raw, 2),
        "date":        check_date,
        "perTicker":   per_ticker,
        "basket":      sorted(ticker_data.keys()),
        "basketSize":  len(ticker_data),
        "methodology": "FINRA Reg SHO Daily CSV, dollar-gewichtet (ShortVol/TotalVol), "
                       f"{len(ticker_data)} Universum-Ticker",
        "source":      "finra_regsho_csv",
        "proxy":       False,
        "url":         url,
    }


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

            # Axel-Anfrage (17.08.2026): "2Y/10Y Spread > 0 für 3 Monate" — eine
            # einzelne De-Inversion ist Rauschen; die etablierte Lesart (u.a.
            # NY-Fed-Forschung) ist, dass die Rezession haeufig NACH einer
            # laengeren Phase der Wieder-Normalisierung eintritt. Handelstage-
            # Konvention (63T = 3 Monate) konsistent mit den bestehenden
            # perf3m/perf6m-Fenstern anderswo im Aggregator.
            streak_days = 0
            for _, sv in reversed(hist_spread):
                if sv > 0:
                    streak_days += 1
                else:
                    break
            positive_streak_confirmed_3m = streak_days >= 63

            curve_entry = {
                "label":        "US Zinskurve 10J-2J (%, FRED Constant Maturity)",
                "y10":          y10,
                "y2":           y2,
                "spread_10y2y": spread_10y2y,
                "zscore":       z_curve,
                "percentile":   p_curve,
                "date":         dgs10[-1][0],
                "inverted":     spread_10y2y < 0,
                "positiveStreakDays":        streak_days,
                "positiveStreakConfirmed3m": positive_streak_confirmed_3m,
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
                     f"(Z={z_curve}) — {curve_entry['signal']} | positiv seit {streak_days}T "
                     f"({'bestätigt (≥3M)' if curve_entry['positiveStreakConfirmed3m'] else 'noch unbestätigt'})")
        else:
            result["yield_curve"] = {"ok": False, "reason": "DGS2/DGS10 nicht verfügbar"}
    except Exception as e:
        result["yield_curve"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED Zinskurve Fehler: {e}")

    # ══════════════════════════════════════════════════════════════════════
    # KONJUNKTUR-INDIKATOREN (17.08.2026, Axel-Anfrage — "auf diesem Auge
    # bislang blind"). Alle IDs einzeln gegen die echte FRED-Seite verifiziert
    # (Browser-Live-Check, nicht aus dem Gedächtnis übernommen — zwei der drei
    # von Axel vorgeschlagenen IDs waren tatsächlich falsch: CPIAUCSL ist
    # Headline- statt Core-CPI, TRUCKSUSSA existiert nicht/404). Bewusst nur
    # etablierte, dokumentierte Schwellen verwendet (Sahm-Rule offizielle
    # FRED-Serie statt Eigenkonstruktion; NFCI-Nullpunkt-Interpretation laut
    # Chicago Fed selbst; OECD-CLI-Quadranten-Logik ist die offizielle OECD-
    # Methodik) — keine erfundenen Cutoffs.
    # ══════════════════════════════════════════════════════════════════════

    # ── 4. NFCI (Chicago Fed National Financial Conditions Index) ───────────
    # Offizielle Interpretation (Chicago Fed): 0 = historischer Durchschnitt,
    # positiv = straffer als Durchschnitt, negativ = lockerer. Wöchentlich,
    # daher deutlich aktueller als die übrigen Konjunktur-Indikatoren hier.
    try:
        nfci = _fred_series("NFCI", limit=260)  # ~5 Jahre wöchentlich
        if nfci:
            z, p = _z_and_p(nfci)
            cur = nfci[-1][1]
            result["nfci"] = {
                "label":      "Chicago Fed National Financial Conditions Index (NFCI)",
                "current":    cur,
                "date":       nfci[-1][0],
                "zscore":     z,
                "percentile": p,
                "n_obs":      len(nfci),
                "signal":     ("STRESS" if cur > 0.5 else "erhöht" if cur > 0 else "locker"),
                "ok":         True,
            }
            log.info(f"  FRED NFCI: {cur:+.3f} (Z={z}, P{p}) — {result['nfci']['signal']}")
    except Exception as e:
        result["nfci"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED NFCI Fehler: {e}")

    # ── 5. US Core CPI YoY (ex Food & Energy) ────────────────────────────────
    # CPILFESL ist der Index-Stand (1982-84=100) — fuer ein Inflationssignal
    # zaehlt die Jahresveraenderung (YoY %), nicht der nackte Indexwert.
    try:
        cpi = _fred_series("CPILFESL", limit=36)  # 3 Jahre monatlich reichen fuer YoY
        if len(cpi) >= 13:
            cur_val  = cpi[-1][1]
            yoy_val  = cpi[-13][1]  # 12 Monate zurueck
            yoy_pct  = round((cur_val / yoy_val - 1) * 100, 2) if yoy_val else None
            # YoY-Historie fuer Z-Score/Trend (soweit Datenpunkte reichen)
            yoy_series = []
            for i in range(12, len(cpi)):
                base = cpi[i-12][1]
                if base:
                    yoy_series.append((cpi[i][0], round((cpi[i][1] / base - 1) * 100, 2)))
            z, p = _z_and_p(yoy_series) if len(yoy_series) >= 20 else (None, None)
            result["core_cpi_yoy"] = {
                "label":      "US Core CPI YoY (ex Food & Energy, %)",
                "current":    yoy_pct,
                "date":       cpi[-1][0],
                "zscore":     z,
                "percentile": p,
                "n_obs":      len(yoy_series),
                # Grober, haeufig zitierter informeller Referenzbereich (kein
                # Fed-Zielwert fuer CPI — das offizielle Fed-Ziel bezieht sich
                # auf PCE, nicht CPI). Bewusst als "erhoeht" statt hartem
                # Cutoff formuliert.
                "signal":     ("erhöht" if yoy_pct and yoy_pct > 3.0 else "moderat") if yoy_pct is not None else None,
                "ok":         yoy_pct is not None,
            }
            log.info(f"  FRED Core CPI YoY: {yoy_pct}% (Z={z}, P{p})")
    except Exception as e:
        result["core_cpi_yoy"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED Core CPI Fehler: {e}")

    # ── 6. Arbeitslosenrate + Sahm-Rule (offizielle FRED-Serie) ──────────────
    # SAHMREALTIME ist die von Claudia Sahm selbst gepflegte offizielle
    # Berechnung (3M-Schnitt UNRATE vs. Minimum der letzten 12 Monate,
    # Trigger bei >= 0.50 Prozentpunkten) — bewusst NICHT selbst nachgebaut,
    # um keine eigene fehleranfaellige Naeherung einer etablierten,
    # akademisch anerkannten Regel zu riskieren.
    try:
        unrate = _fred_series("UNRATE", limit=36)
        sahm   = _fred_series("SAHMREALTIME", limit=36)
        if unrate:
            result["unemployment"] = {
                "label":        "US Arbeitslosenrate (UNRATE, %)",
                "current":      unrate[-1][1],
                "date":         unrate[-1][0],
                "trend_3m":     round(unrate[-1][1] - unrate[-4][1], 2) if len(unrate) >= 4 else None,
                "sahmRule":     sahm[-1][1] if sahm else None,
                "sahmDate":     sahm[-1][0] if sahm else None,
                "sahmTriggered": bool(sahm and sahm[-1][1] >= 0.50),
                "signal":       ("REZESSIONSSIGNAL (Sahm-Rule ≥0.50)" if sahm and sahm[-1][1] >= 0.50 else "kein Sahm-Trigger"),
                "ok":           True,
            }
            log.info(f"  FRED Arbeitslosenrate: {unrate[-1][1]}% | Sahm-Rule: {sahm[-1][1] if sahm else 'n/v'} — {result['unemployment']['signal']}")
    except Exception as e:
        result["unemployment"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED Arbeitslosenrate/Sahm-Rule Fehler: {e}")

    # ── 7. University of Michigan Consumer Sentiment ─────────────────────────
    try:
        umich = _fred_series("UMCSENT", limit=120)
        if umich:
            z, p = _z_and_p(umich)
            result["consumer_sentiment"] = {
                "label":      "University of Michigan Consumer Sentiment",
                "current":    umich[-1][1],
                "date":       umich[-1][0],
                "zscore":     z,
                "percentile": p,
                "n_obs":      len(umich),
                "signal":     ("sehr schwach" if p is not None and p <= 15 else
                               "sehr stark" if p is not None and p >= 85 else "normal"),
                "ok":         True,
            }
            log.info(f"  FRED UMich Consumer Sentiment: {umich[-1][1]} (Z={z}, P{p})")
    except Exception as e:
        result["consumer_sentiment"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED UMich Consumer Sentiment Fehler: {e}")

    # ── 8. Heavy Truck Sales (10-Monats-Schnitt, Axel-Vorschlag) ─────────────
    # HTRUCKSSAAR = Motor Vehicle Retail Sales: Heavy Weight Trucks (Mio
    # Einheiten, SAAR). Klassischer Fruehindikator (ECRI-nahe Verwendung) —
    # roher Monatswert ist sehr volatil, daher 10M-gleitender Durchschnitt
    # wie von Axel vorgeschlagen; Signal ist die TREND-Richtung des
    # Durchschnitts, nicht der Level (der schwankt stark je Marktzyklus).
    try:
        trucks = _fred_series("HTRUCKSSAAR", limit=36)
        if len(trucks) >= 11:
            ma10_series = []
            for i in range(9, len(trucks)):
                window = [v for _, v in trucks[i-9:i+1]]
                ma10_series.append((trucks[i][0], round(sum(window) / 10, 3)))
            cur_ma  = ma10_series[-1][1]
            prev_ma = ma10_series[-4][1] if len(ma10_series) >= 4 else None  # 3 Monate zurueck
            trend_pct = round((cur_ma / prev_ma - 1) * 100, 2) if prev_ma else None
            result["heavy_truck"] = {
                "label":       "Heavy Truck Sales (10M-Schnitt, Mio Einheiten SAAR)",
                "current":     trucks[-1][1],
                "ma10":        cur_ma,
                "date":        trucks[-1][0],
                "trend_3m_pct": trend_pct,
                "signal":      ("fallend" if trend_pct is not None and trend_pct < -3 else
                                 "steigend" if trend_pct is not None and trend_pct > 3 else "seitwärts"),
                "ok":          True,
            }
            log.info(f"  FRED Heavy Truck Sales: {trucks[-1][1]} (10M-Schnitt {cur_ma}, 3M-Trend {trend_pct}%) — {result['heavy_truck']['signal']}")
    except Exception as e:
        result["heavy_truck"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED Heavy Truck Sales Fehler: {e}")

    # ── 9. OECD Composite Leading Indicator (USA) ────────────────────────────
    # USALOLITOAASTSAM = OECD CLI, Amplitude-Adjusted, ueber FRED gespiegelt
    # (kein direkter OECD-Scrape noetig). Offizielle OECD-Interpretation ist
    # eine Quadranten-Logik aus Level ggue. 100 (Baseline) UND Richtung
    # (M/M-Aenderung) — Level allein ist nicht aussagekraeftig, deshalb beide
    # Dimensionen im Signal.
    try:
        cli = _fred_series("USALOLITOAASTSAM", limit=36)
        if len(cli) >= 2:
            cur   = cli[-1][1]
            prev  = cli[-2][1]
            rising = cur > prev
            above  = cur > 100
            if above and rising:      quadrant = "EXPANSION (>100, steigend)"
            elif above and not rising: quadrant = "ABSCHWAECHUNG (>100, fallend)"
            elif not above and not rising: quadrant = "KONTRAKTION (<100, fallend)"
            else:                     quadrant = "ERHOLUNG (<100, steigend)"
            # Numerischer Quadranten-Score fuer MCM-Signal-Auswertung (s.
            # _MCM_SIGNAL_RULES["oecd_cli_score"]): +1 je "gutem" Merkmal
            # (>100, steigend), -1 je "schlechtem" — Bereich -2..+2.
            quadrant_score = (1 if above else -1) + (1 if rising else -1)
            result["oecd_cli"] = {
                "label":    "OECD Composite Leading Indicator USA (Amplitude Adjusted)",
                "current":  cur,
                "date":     cli[-1][0],
                "rising":   rising,
                "above100": above,
                "quadrantScore": quadrant_score,
                "signal":   quadrant,
                "ok":       True,
            }
            log.info(f"  FRED OECD CLI: {cur} ({'steigend' if rising else 'fallend'}) — {quadrant}")
    except Exception as e:
        result["oecd_cli"] = {"ok": False, "reason": str(e)[:100]}
        log.warning(f"  FRED OECD CLI Fehler: {e}")

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
        # BUGFIX (16.08.2026, im Rahmen der MCM-Paritaets-Verifikation gefunden):
        # squeeze() kann bei nur 1 verbleibendem Datenpunkt zu einem nackten
        # numpy.float64-Skalar kollabieren (kein Series/Array mehr) — .values
        # existiert dann nicht, AttributeError. War durch das try/except der
        # Funktion bereits fehlerisoliert (kein Absturz des Gesamtlaufs), aber
        # mit kryptischer Fehlermeldung statt klarer Diagnose. Klarer Reason-Text
        # statt rohem AttributeError.
        if not hasattr(close, 'values'):
            return {"ok": False, "reason": f"squeeze() lieferte Skalar statt Series (nur 1 Rohdatenpunkt von yfinance?) — Wert: {close}"}
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
        # squeeze() kann bei Einzelwert (Wochenende) einen numpy.float64-Skalar
        # zurueckgeben — der hat kein .dropna(). Fallback: direkt float().
        vix_val   = float(vix_close.dropna().iloc[-1]) if hasattr(vix_close,   "dropna") else float(vix_close)
        vix3m_val = float(vix3m_close.dropna().iloc[-1]) if hasattr(vix3m_close, "dropna") else float(vix3m_close)
        spread   = round(vix3m_val - vix_val, 2)
        contango = spread > 0
        log.info(f"  VIX: {vix_val:.2f} | VIX3M: {vix3m_val:.2f} | Spread: {spread:+.2f} | {'CONTANGO' if contango else 'BACKWARDATION'}")
        return {
            "vix":          round(vix_val, 2),
            "vix3m":        round(vix3m_val, 2),
            "spread":       spread,
            # KONVENTION-KLARHEIT (SWOT №33, 07.08.2026):
            # ratio         = VIX/VIX3M  (<1 = Contango = gesund) — Legacy-Feld, bleibt für Kompatibilität
            # ratio_3m_spot = VIX3M/VIX  (>1 = Contango = gesund) — MSE-Konvention (Regime-Klassifikation)
            # NIEMALS ratio direkt für Regime-Schwellen verwenden → immer ratio_3m_spot
            "ratio":        round(vix_val / vix3m_val, 3),
            "ratio_3m_spot": round(vix3m_val / vix_val, 3),
            "structure":    "CONTANGO" if contango else "BACKWARDATION",
            "signal":       "NORMAL" if contango and vix_val / vix3m_val < 0.90 else
                            "ERHÖHT" if contango else "STRESS",
        }
    except Exception as e:
        log.warning(f"  VIX Term nicht verfügbar: {e}")
    return None

# ── CLOUDFLARE KV UPLOAD ──────────────────────────────────────────────────────


def calc_ratio_signal(hist_data: dict, sym_a: str, sym_b: str, label: str) -> dict:
    """Generisches Ratio-Rotationssignal aus zwei bereits geladenen ETF-Serien
    (17.08.2026, Axel-Anfrage — Konjunktur-Indikatoren). Verwendet fuer:
      - Consumer Staples (XLP) vs. Discretionary (XLY): defensiv vs. zyklisch,
        korreliert laut Axel mit SPX-Regime (Staples-Outperformance = Risk-Off)
      - Growth (IWF) vs. Value (IWD)

    Beide Ticker liegen bereits im Ticker-Universum (yfinance-Batch), daher
    KEIN zusaetzlicher API-Call noetig — reine Nachberechnung aus hist_data,
    identisch im Muster zur bestehenden Sektor-RS-Berechnung (5b).

    Signal ist bewusst trend-/momentumbasiert (5T vs. 20T-Ratio-Veraenderung),
    nicht levelbasiert — ein Ratio-Level allein (z.B. "XLP/XLY = 0.42") hat
    keine feste, allgemein anerkannte Interpretationsschwelle; die RICHTUNG
    der Ratio-Bewegung (steigend = Rotation in a, fallend = Rotation in b)
    ist die etablierte Lesart.
    """
    a_data = hist_data.get(sym_a)
    b_data = hist_data.get(sym_b)
    if a_data is None or b_data is None or len(a_data) < 21 or len(b_data) < 21:
        return {"ok": False, "reason": f"{sym_a}/{sym_b} Daten fehlen oder zu kurz"}
    try:
        a_close = list(a_data["Close"].dropna())
        b_close = list(b_data["Close"].dropna())
        n = min(len(a_close), len(b_close))
        a_close, b_close = a_close[-n:], b_close[-n:]

        ratio_now = a_close[-1] / b_close[-1]
        ratio_5   = a_close[-6]  / b_close[-6]  if n >= 6  else None
        ratio_20  = a_close[-21] / b_close[-21] if n >= 21 else None
        ratio_60  = a_close[-61] / b_close[-61] if n >= 61 else None

        chg_5  = round((ratio_now / ratio_5  - 1) * 100, 2) if ratio_5  else None
        chg_20 = round((ratio_now / ratio_20 - 1) * 100, 2) if ratio_20 else None
        chg_60 = round((ratio_now / ratio_60 - 1) * 100, 2) if ratio_60 else None

        trend = "steigend" if chg_5 is not None and chg_20 is not None and chg_5 > chg_20 else "fallend"

        return {
            "label":   label,
            "symA":    sym_a, "symB": sym_b,
            "ratio":   round(ratio_now, 4),
            "chg5d":   chg_5, "chg20d": chg_20, "chg60d": chg_60,
            "trend":   trend,
            "ok":      True,
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


def calc_regime_history_flag(mse_history: dict, current_regime: str) -> dict:
    """Regime-History-Flag (Backlog №29, 07.08.2026) — Übergangsvektor für den MSE.

    Löst das Zustandslosigkeits-Problem: zwei Tage mit gleichem VIX3M/VIX-Ratio
    können fundamental verschiedene Marktphasen sein (Erholung aus Stress vs.
    Abschwächung aus Bull). Dieser Flag macht den Übergangsvektor explizit.

    Architektur (ML_KONZEPT.md §3b): Brücke bis MCM-HMM ab ~01.10.2026.
    Dann: regelbasierter vector wird durch P(state_0..3) aus GaussianHMM ersetzt.

    Input:
        mse_history   : Ausgabe von fetch_mse_history() — enthält vixRatio + dates
        current_regime: heutiger market_regime_str (BULL_QUIET / BULL_FRAGILE /
                        POST_PANIC_REVERSION / STRESS_UNSTABLE)

    Output-Schema:
        {
          "current":        str,   # aktuelles MSE-Regime
          "vector":         str,   # RECOVERING | DETERIORATING | STABLE | UNKNOWN
          "consecutive":    int,   # Tage im aktuellen Regime in Folge
          "stressDaysAgo":  int|None,  # Handelstage seit letztem STRESS_UNSTABLE
          "prevRegimes":    list,  # letzten 5 Regime-Labels (historisch, ältestes zuerst)
          "ratioTrend":     str,   # RISING | FALLING | FLAT (VIX3M/VIX-Ratio-Trend, 5T)
          "method":         str,   # "rule_based_v1" (ab HMM: "hmm_v1")
        }
    """
    unknown = {
        "current": current_regime, "vector": "UNKNOWN", "consecutive": 1,
        "stressDaysAgo": None, "prevRegimes": [], "ratioTrend": "UNKNOWN",
        "method": "rule_based_v1",
    }

    if not mse_history or not current_regime:
        return unknown

    ratios = mse_history.get("vixRatio") or []
    dates  = mse_history.get("dates") or []

    if len(ratios) < 3 or len(dates) < 3:
        return unknown

    # ── Regime-Labels aus vixRatio-Historie rekonstruieren ──────────────────
    # Gleiche Logik wie in main() (Z.7363-7389): VIX-Niveau nicht verfügbar
    # in mse_history → Vereinfachung: BULL_QUIET/BULL_FRAGILE nicht unterschieden,
    # beide als BULL zusammengefasst für den Übergangsvektor (ausreichend für vector)
    def _ratio_to_regime(r):
        if r is None:         return None
        if r < 0.98:          return "STRESS_UNSTABLE"
        if r < 1.05:          return "POST_PANIC_REVERSION"
        return "BULL"  # BULL_QUIET oder BULL_FRAGILE — für Vektor-Zwecke äquivalent

    hist_labels = [_ratio_to_regime(r) for r in ratios]
    hist_labels = [l for l in hist_labels if l is not None]

    if not hist_labels:
        return unknown

    # Aktuelles Regime für Vergleich normalisieren (BULL_QUIET/BULL_FRAGILE → BULL)
    cur_norm = "BULL" if current_regime in ("BULL_QUIET", "BULL_FRAGILE") else current_regime

    # ── consecutive: wie viele Tage schon im aktuellen Regime? ──────────────
    consecutive = 1
    for label in reversed(hist_labels[:-1]):  # rückwärts, ohne heute
        if label == cur_norm:
            consecutive += 1
        else:
            break

    # ── prevRegimes: letzten 5 Labels vor heute (für Kontext) ───────────────
    prev_regimes = hist_labels[-6:-1] if len(hist_labels) >= 6 else hist_labels[:-1]

    # ── stressDaysAgo: Handelstage seit letztem STRESS_UNSTABLE ─────────────
    stress_days_ago = None
    for i, label in enumerate(reversed(hist_labels[:-1])):
        if label == "STRESS_UNSTABLE":
            stress_days_ago = i + 1
            break

    # ── ratioTrend: Steigung des VIX3M/VIX-Ratio über letzte 5 Tage ────────
    recent_ratios = [r for r in ratios[-5:] if r is not None]
    if len(recent_ratios) >= 3:
        delta = recent_ratios[-1] - recent_ratios[0]
        if   delta >  0.02: ratio_trend = "RISING"
        elif delta < -0.02: ratio_trend = "FALLING"
        else:               ratio_trend = "FLAT"
    else:
        ratio_trend = "UNKNOWN"

    # ── vector: Übergangsvektor ──────────────────────────────────────────────
    # Kernlogik: woher kommt das aktuelle Regime?
    #
    # RECOVERING:    Vorher STRESS_UNSTABLE, jetzt POST_PANIC/BULL, Ratio steigt
    # DETERIORATING: Vorher BULL, jetzt POST_PANIC/STRESS, Ratio fällt
    # STABLE:        Schon ≥5 Tage im gleichen Regime, keine klare Richtung
    # UNKNOWN:       Nicht eindeutig klassifizierbar

    vector = "UNKNOWN"

    recent_prev = hist_labels[-4:-1] if len(hist_labels) >= 4 else hist_labels[:-1]
    had_stress_recently = any(l == "STRESS_UNSTABLE" for l in recent_prev[-3:])
    had_bull_recently   = any(l == "BULL" for l in recent_prev[-3:])

    if consecutive >= 5:
        vector = "STABLE"
    elif cur_norm in ("POST_PANIC_REVERSION", "BULL") and had_stress_recently:
        # Markt erholt sich aus Stress
        vector = "RECOVERING"
    elif cur_norm in ("POST_PANIC_REVERSION", "STRESS_UNSTABLE") and had_bull_recently:
        # Markt schwächt sich ab aus Bull
        vector = "DETERIORATING"
    elif ratio_trend == "RISING" and cur_norm in ("POST_PANIC_REVERSION", "BULL"):
        vector = "RECOVERING"
    elif ratio_trend == "FALLING" and cur_norm in ("POST_PANIC_REVERSION", "STRESS_UNSTABLE"):
        vector = "DETERIORATING"
    elif ratio_trend == "FLAT" and consecutive >= 3:
        vector = "STABLE"

    result = {
        "current":       current_regime,
        "vector":        vector,
        "consecutive":   consecutive,
        "stressDaysAgo": stress_days_ago,
        "prevRegimes":   prev_regimes,
        "ratioTrend":    ratio_trend,
        "method":        "rule_based_v1",
    }
    log.info(
        f"  Regime-History-Flag: vector={vector} | consecutive={consecutive}T "
        f"| ratioTrend={ratio_trend} | stressDaysAgo={stress_days_ago}"
    )
    return result


def fetch_mse_history(days: int = 30) -> dict:
    """Laedt 30-Tage-History fuer VVIX, SKEW, VIX, VIX3M fuer MSE Z-Score Normalisierung."""
    result = {"vvix": [], "skew": [], "vix": [], "vixRatio": [], "dates": []}
    try:
        # BUGFIX (16.08.2026, Axel-Deep-Debug-Anfrage — Root Cause nach 2
        # fehlgeschlagenen Versuchen gefunden): Der gebuendelte 4-Symbol-
        # yf.download(group_by="ticker") lieferte fuer ^VIX3M zuverlaessig nur
        # 1 Tag Historie, waehrend ^VVIX/^SKEW/^VIX 245-254 Tage lieferten
        # (per TEMP-DEBUG-Feld im Ergebnis-Dict verifiziert, da GHA-Logs fuer
        # Claude nicht erreichbar sind). Die anschliessende Schnittmenge war
        # dadurch zwangsweise auf 1 Tag limitiert — KEIN Timestamp/TZ-Problem
        # wie in v5.36.7 vermutet (dieser Fix war wirkungslos, da er an der
        # falschen Stelle ansetzte). fetch_vix_term() (VIX/VIX3M LIVE-Werte,
        # an anderer Stelle im Code) holt beide Symbole bereits EINZELN und
        # funktioniert zuverlaessig — dasselbe Muster hier fuer die Historie
        # uebernommen: 4 separate Einzel-Downloads statt 1 gebuendeltem Call.
        #
        # BUGFIX (19.08.2026, Axel-Deep-Debug-Anfrage — Bug 1/3 Root-Cause,
        # via GHA-Log #228 verifiziert): `period=f"{days+5}d"` (nicht-
        # kanonischer String, z.B. "257d") lieferte pro Symbol zuverlaessig
        # 225-257 Zeilen (KEINE 1-Zeilen-Drosselung) — aber das Fenster war
        # bei 2026-07-17 eingefroren, unabhaengig vom tatsaechlichen Lauf-
        # datum (verifiziert an Laeufen vom 22.07./01.08./19.08., alle mit
        # identischem letzten VVIX/SKEW-Wert). Wahrscheinlichste Ursache:
        # Yahoo/CDN-seitiges Response-Caching, an die exakte, taeglich
        # identische Request-Signatur (Symbol+Perioden-String) gebunden —
        # strukturell dasselbe Muster wie der bereits gefixte Client-VIX-
        # Cache-Bug (v324, index.html), nur mit deutlich laengerer Cache-
        # Lebensdauer. Fix: explizite start=/end=-Datumsangaben statt
        # relativem Perioden-String — aendert die Anfrage taeglich zwangs-
        # laeufig und umgeht damit jedes URL-/Parameter-gebundene Caching.
        # NOCH NICHT gegen einen echten Live-Lauf verifiziert — vor
        # Vertrauen in die Daten den naechsten GHA-Lauf gegenchecken
        # (MSE History: ... Tage | VVIX: ... | Ratio: ... sollte ein
        # aktuelles Datum/aktuelle Werte zeigen, nicht mehr 07-17/104.87).
        _end_dt   = datetime.now(timezone.utc).date()
        _start_dt = _end_dt - timedelta(days=days + 5)
        closes = {}
        for sym in ["^VVIX", "^SKEW", "^VIX", "^VIX3M"]:
            try:
                raw_sym = yf.download(sym, start=_start_dt, end=_end_dt + timedelta(days=1),
                                       auto_adjust=True, progress=False)
                s = raw_sym["Close"].dropna()
                if hasattr(s, 'squeeze'):
                    s = s.squeeze()
                if not hasattr(s, 'index'):
                    # squeeze() auf Einzelwert kollabiert (analog fetch_move_index-Bug)
                    log.warning(f"  MSE History {sym}: squeeze() lieferte Skalar, uebersprungen")
                    closes[sym] = None
                    continue
                if hasattr(s.index, 'tz') and s.index.tz is not None:
                    s.index = s.index.tz_localize(None)
                if hasattr(s.index, 'normalize'):
                    s.index = s.index.normalize()
                closes[sym] = s
                log.info(f"  MSE History Rohdaten {sym}: {len(s)} Tage (Einzel-Download)")
            except Exception as _ce:
                log.warning(f"  MSE History {sym} Fehler: {_ce}")
                closes[sym] = None

        if closes["^VIX"] is None:
            log.warning("  MSE History: VIX nicht verfuegbar — Historie nicht nutzbar")
            return result
        # BUGFIX (19.08.2026, Fortsetzung desselben Tages — Regression durch
        # start=/end=-Fix oben): ^VIX3M lieferte mit expliziten Datumsangaben
        # teils nur 1 Zeile (squeeze() kollabiert zu Skalar), waehrend
        # ^VVIX/^SKEW/^VIX zuverlaessig 171-172 Tage lieferten — derselbe
        # Sonderfall wie beim 16.08.-Fix, nur diesmal bei start=/end= statt
        # period=. VORHER: harter Abbruch (return leeres result), wenn
        # VIX3M fehlte — das machte VVIX/SKEW/VIX-Historie kaputt, obwohl
        # nur VIX3M betroffen war. JETZT: VIX3M ist optional, nur vixRatio
        # wird dann NICHT berechnet (None) — vvix_z20/skew_pct20/gex_z20/
        # dix_z20 (die fuer determine_mse_regime() relevanten Werte) bleiben
        # nutzbar. Der AKTUELLE vixRatio-Wert kommt ohnehin separat und
        # zuverlaessig aus fetch_vix_term() (LIVE-Einzelwert, nicht History).
        if closes["^VIX3M"] is None:
            log.warning("  MSE History: VIX3M nicht verfuegbar — vixRatio-Historie wird uebersprungen, VVIX/SKEW/VIX bleiben nutzbar")

        common_idx = closes["^VIX"].index
        for sym in ["^VIX3M", "^VVIX", "^SKEW"]:
            if closes[sym] is not None:
                common_idx = common_idx.intersection(closes[sym].index)

        common_idx = common_idx[-days:]
        log.info(f"  MSE History Schnittmenge: {len(common_idx)} gemeinsame Tage")

        dates  = [str(d.date()) for d in common_idx]
        vvix   = [round(float(closes["^VVIX"].loc[d]), 2) if closes["^VVIX"] is not None else None for d in common_idx]
        skew   = [round(float(closes["^SKEW"].loc[d]), 2) if closes["^SKEW"] is not None else None for d in common_idx]
        vix    = [round(float(closes["^VIX"].loc[d].squeeze() if hasattr(closes["^VIX"].loc[d],"squeeze") else closes["^VIX"].loc[d]), 2)  for d in common_idx]
        if closes["^VIX3M"] is not None:
            vix3m = [round(float(closes["^VIX3M"].loc[d].squeeze() if hasattr(closes["^VIX3M"].loc[d],"squeeze") else closes["^VIX3M"].loc[d]), 2) for d in common_idx]
            ratio = [round(vix3m[i] / vix[i], 3) if vix3m[i] and vix[i] and vix[i] > 0 else None for i in range(len(vix))]
        else:
            ratio = [None for _ in common_idx]

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

    # Kein URL-Encoding des Keys: identisch zu _kv_url() in tr_layer.py, das
    # seit Wochen tr:snap:*/tr:eval:* mit rohen Doppelpunkten schreibt und liest.
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


# -- DAILY MARKET SNAPSHOT (v1.0, 13.07.2026) ----------------------------------
# Serverseitiges Morning Briefing - laeuft im Aggregator (GHA, Owner-Kosten).
# Beta-Tester lesen KV-Key "daily_market_snapshot" - kein eigener Anthropic-Call.
# Architektur: Option A (SUITE.md, Sprints) - ein KV-Key, kein neuer Worker.

# ══════════════════════════════════════════════════════════════════════════
# MARKET CONTEXT MODULE (MCM) — Python-Port (14.07.2026)
# ══════════════════════════════════════════════════════════════════════════
# Portiert aus dem Frontend (ko-modules JS), damit generate_daily_snapshot()
# denselben market_context + dieselben Strategie-Gates nutzt wie der Client
# (axel-scanner v322/v323, ko-modules@b70ca70). Grund: Der Cache-First-Pfad
# im Frontend liest DIESES serverseitige Briefing — der MCM-Umbau im JS
# betrifft nur den seltenen Fallback-Pfad ohne KV-Cache-Hit. Ohne diesen
# Python-Port wäre der ganze MCM-Sprint für den Regelfall wirkungslos.
#
# VERSIONS-LOCK (kein automatischer Sync, manueller Abgleich nötig):
#   Diese Tabellen sind eine 1:1-Portierung von:
#   - ko-modules/ko-market-state.js v2.1 (STRATEGY-Regime-Tabellen,
#     CONTEXT_DOWNGRADE_RULES) — Commit b70ca70
#   - ko-modules/ko-indicators.json v2.1.0 (signalRules, Calendar-Faktoren)
#   Bei Änderungen an einer Seite MUSS die andere manuell nachgezogen werden.
#   Kein gemeinsames Build-Artefakt vorhanden (JS/Python-Sprachgrenze).

# ── signalRules: Schwellwerte -> 'ok'|'caution'|'risk' (1:1 aus ko-indicators.json) ──
_MCM_SIGNAL_RULES = {
    "vix":               [{"signal": "risk", "gte": 35}, {"signal": "caution", "gte": 25}, {"signal": "ok"}],
    "vvix":              [{"signal": "risk", "gte": 1.5}, {"signal": "caution", "gte": 0.8}, {"signal": "ok"}],
    "skew":              [{"signal": "caution", "gte": 80}, {"signal": "ok"}],
    "pcr":               [{"signal": "caution", "gte": 1.2}, {"signal": "caution", "lte": 0.7}, {"signal": "ok"}],
    "fear_greed":        [{"signal": "caution", "lte": 20}, {"signal": "caution", "gte": 80}, {"signal": "ok"}],
    "intermarket_score": [{"signal": "risk", "gte": 60}, {"signal": "caution", "gte": 40}, {"signal": "ok"}],
    "bull_indicator":    [{"signal": "caution", "lte": 35}, {"signal": "ok"}],
    "treasury_stress":   [{"signal": "risk", "gte": 60}, {"signal": "caution", "gte": 35}, {"signal": "ok"}],
    "ndx_breadth":       [{"signal": "risk", "lte": 35}, {"signal": "caution", "lte": 50}, {"signal": "ok"}],
    # net_liquidity: caution wenn 4W-Trend ≤ 0 (schrumpfend/stabil) — identisch zu
    # ko-indicators.json signalRules (trend4w_lte: 0). Wert = trend_4w in Mrd USD.
    "net_liquidity":     [{"signal": "caution", "lte": 0}, {"signal": "ok"}],
    # NEU (16.08.2026, MCM-Paritaet-Nachzug, Axel-Deep-Debug-Anfrage): 4 Faktoren,
    # die im Client (ko-indicators.json) schon lange registriert waren, aber nie
    # nach Python portiert wurden — dadurch im Server-Briefing (Normalfall,
    # KV-Cache-First) NIE erwaehnt, unabhaengig vom heutigen Fear&Greed-Fund.
    # Werte identisch zu den Client-Schwellen (zgte/gte in ko-indicators.json).
    "move_index":        [{"signal": "risk", "gte": 1.5}, {"signal": "caution", "gte": 0.8}, {"signal": "ok"}],
    "skew_vvix_div":      [{"signal": "caution", "gte": 1.5}, {"signal": "ok"}],
    # breadth_osc: McClellan-Oszillatorwert selbst (kein Z-Score) — negativ = Breite
    # bricht weg. Schwellen an SUITE.md-Backlog-#12-Signalstufen angelehnt
    # (SEHR_BEARISH < -50, BEARISH < -10).
    "breadth_osc":       [{"signal": "risk", "lte": -50}, {"signal": "caution", "lte": -10}, {"signal": "ok"}],
    # distribution_days: dd_max (hoehere von SPY/QQQ) — identisch zu den UI-
    # Severity-Schwellen (Watch>=4, Danger>=6).
    "distribution_days": [{"signal": "risk", "gte": 6}, {"signal": "caution", "gte": 4}, {"signal": "ok"}],
    # NEU (17.08.2026, Axel-Anfrage — Konjunktur-Indikatoren, "auf diesem Auge
    # bislang blind"). Schwellen s. Docstrings der jeweiligen fetch_fred_macro()-
    # Bloecke — Sahm-Rule 0.50 ist die offizielle akademische Trigger-Schwelle,
    # NFCI-Nullpunkt ist Chicago-Fed-eigene Interpretation, restliche Schwellen
    # sind bewusst weich formuliert (keine erfundene Praezision vortaeuschen).
    "nfci":              [{"signal": "risk", "gte": 0.5}, {"signal": "caution", "gte": 0}, {"signal": "ok"}],
    "core_cpi_yoy":      [{"signal": "caution", "gte": 3.0}, {"signal": "ok"}],
    "sahm_rule":         [{"signal": "risk", "gte": 0.5}, {"signal": "ok"}],
    # oecd_cli_score: -2 KONTRAKTION .. +2 EXPANSION (Quadranten-Score, s.
    # fetch_fred_macro()) — risk nur im eindeutigsten Kontraktions-Quadranten.
    "oecd_cli_score":    [{"signal": "risk", "lte": -2}, {"signal": "caution", "lt": 0}, {"signal": "ok"}],
    "heavy_truck_trend": [{"signal": "caution", "lte": -3}, {"signal": "ok"}],
}

# ── Calendar-Faktoren (identische Fenster-/Karenz-Parameter wie ko-indicators.json) ──
_MCM_CALENDAR_FACTORS = {
    "fed_window": {"event_type": "FOMC", "buffer_minutes": 15, "signal": "caution"},
    "nfp_window": {"event_type": "NFP",  "buffer_minutes": 10, "signal": "caution"},
    "cpi_window": {"event_type": "CPI",  "buffer_minutes": 10, "signal": "caution"},
}

# ── Regime-Basis-Gates (1:1 aus ko-market-state.js getStrategyGates(), gekürzt auf
#    Farbe+active — Notes/Labels bleiben Frontend-Domäne, Server braucht nur Ampel) ──
_MCM_REGIME_GATES = {
    "BULL_QUIET": {
        "action": "Trendfolge + CSP voll freigegeben",
        "strategies": {
            "momentum": "green", "breakout": "green", "swing": "green", "ko": "green",
            "csp_wheel": "green", "atmna": "green", "weekly_income": "green", "cc": "green",
            "value": "amber", "dividend": "amber", "meanrev": "red", "fading_short": "red",
        },
    },
    "BULL_FRAGILE": {
        "action": "Trendfolge mit engen Stops, CSP drosseln",
        "strategies": {
            "momentum": "amber", "swing": "amber", "csp_wheel": "amber", "weekly_income": "amber",
            "cc": "amber", "atmna": "amber", "value": "amber", "dividend": "green",
            "breakout": "red", "ko": "red", "meanrev": "red", "fading_short": "red",
        },
    },
    "STRESS_UNSTABLE": {
        "action": "Positionen absichern · Fading-Short prüfen · Defensive CSPs selektiv",
        "strategies": {
            "fading_short": "green", "meanrev": "amber", "csp_wheel": "amber", "value": "amber",
            "cc": "amber", "dividend": "amber", "momentum": "red", "swing": "red",
            "breakout": "red", "ko": "red", "atmna": "red", "weekly_income": "red",
        },
    },
    "POST_PANIC_REVERSION": {
        "action": "Mean Reversion & Income Priorität 1 · Vol-Crush nutzen · Value-Einstiege prüfen",
        "strategies": {
            "meanrev": "green", "csp_wheel": "green", "atmna": "green", "weekly_income": "green",
            "cc": "green", "value": "green", "dividend": "amber", "fading_short": "amber",
            "momentum": "red", "swing": "red", "breakout": "red", "ko": "red",
        },
    },
    "NEUTRAL": {
        "action": "Selektiv vorgehen · Nur höchste Qualität · Kein Leverage",
        "strategies": {
            "momentum": "amber", "swing": "amber", "csp_wheel": "amber", "weekly_income": "amber",
            "cc": "amber", "dividend": "amber", "value": "amber", "atmna": "amber",
            "breakout": "red", "ko": "red", "meanrev": "amber", "fading_short": "red",
        },
    },
}

# ── CONTEXT_DOWNGRADE_RULES (1:1 aus ko-market-state.js) ──
_MCM_DOWNGRADE_RULES = [
    ("treasury_stress",   ["ko", "momentum", "breakout", "swing", "csp_wheel", "atmna", "weekly_income", "cc"]),
    ("ndx_breadth",       ["ko", "momentum", "breakout", "swing"]),
    ("intermarket_score", ["ko", "momentum", "breakout", "swing", "value"]),
    ("vix",               ["ko", "breakout", "atmna"]),
    ("vvix",              ["ko", "breakout", "csp_wheel", "weekly_income"]),
    ("skew",              ["csp_wheel", "atmna", "weekly_income"]),
    ("pcr",               ["momentum", "breakout"]),
    ("fear_greed",        ["momentum", "breakout", "ko"]),
    ("bull_indicator",    ["ko", "momentum", "breakout", "swing"]),
    ("fed_window",        ["ko", "momentum", "breakout", "swing", "csp_wheel", "atmna", "weekly_income"]),
    ("nfp_window",        ["ko", "breakout"]),
    ("cpi_window",        ["ko", "breakout", "csp_wheel"]),
]

_MCM_CALENDAR_CACHE = {"events": None, "loaded": False}


def _mcm_load_macro_calendar():
    """macro-calendar.json von axel-scanner laden (raw.githubusercontent, gecacht).
    FAIL-CLOSED: bei Fehler bleibt events=None -> keine Calendar-Flags."""
    if _MCM_CALENDAR_CACHE["loaded"]:
        return _MCM_CALENDAR_CACHE["events"]
    _MCM_CALENDAR_CACHE["loaded"] = True
    try:
        url = "https://raw.githubusercontent.com/ahsub/axel-scanner/main/macro-calendar.json"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            _MCM_CALENDAR_CACHE["events"] = data.get("events") or None
            log.info(f"  [MCM] Makro-Kalender geladen — {len(data.get('events', []))} Events")
        else:
            log.warning(f"  [MCM] macro-calendar.json HTTP {r.status_code} — fail-closed, keine Event-Flags")
    except Exception as e:
        log.warning(f"  [MCM] macro-calendar.json nicht ladbar (fail-closed): {e}")
    return _MCM_CALENDAR_CACHE["events"]


def _mcm_eval_signal(rules, val):
    """Erste passende Regel gewinnt. Identisch zu _evalSignalRules() im JS-Port."""
    if val is None or rules is None:
        return None
    for r in rules:
        if r.get("gte") is not None and not (val >= r["gte"]):
            continue
        if r.get("gt") is not None and not (val > r["gt"]):
            continue
        if r.get("lte") is not None and not (val <= r["lte"]):
            continue
        if r.get("lt") is not None and not (val < r["lt"]):
            continue
        return r["signal"]
    return None


def _mcm_eval_calendar_factor(cfg, events, now_utc):
    """Identisch zu _evalCalendarFactor() im JS-Port (decision_utc/meeting_start_utc,
    bufferMinutes-Karenz). FAIL-CLOSED bei fehlendem Kalender."""
    if not events:
        return None
    buf = timedelta(minutes=cfg.get("buffer_minutes", 0))
    for ev in events:
        if ev.get("type") != cfg["event_type"] or not ev.get("decision_utc"):
            continue
        try:
            decision = datetime.fromisoformat(ev["decision_utc"].replace("Z", "+00:00"))
        except Exception:
            continue
        if ev.get("meeting_start_utc"):
            try:
                window_start = datetime.fromisoformat(ev["meeting_start_utc"].replace("Z", "+00:00")) - buf
            except Exception:
                window_start = decision - timedelta(hours=24) - buf
        else:
            window_start = decision - timedelta(hours=24) - buf
        window_end = decision + buf
        if window_start <= now_utc <= window_end:
            hrs = round((decision - now_utc).total_seconds() / 3600)
            return {"signal": cfg["signal"], "label": ev.get("label", cfg["event_type"]) +
                    (f" in {hrs}h" if hrs >= 0 else f" vor {-hrs}h")}
    return None


# ── MCM-PARITÄT: SERVER-PORTS DER 4 CLIENT-FUNKTIONEN (v5.13.0, 21.07.2026) ──────────────
# Port von loadIntermarket() / calcTreasuryStress() / calcBullIndicator() / NDX-Breadth
# aus index.html — exakte Schwellen und Logik 1:1 übernommen.

def _get_closes(hist_data: dict, sym: str, n: int = None) -> list:
    """Hilfsfunktion: letzte n Close-Werte für ein Symbol aus hist_data."""
    df = hist_data.get(sym)
    if df is None or df.empty:
        return []
    closes = df["Close"].dropna().tolist()
    return closes[-n:] if n else closes


def _get_last_price(hist_data: dict, sym: str):
    """Letzter Close-Kurs für ein Symbol."""
    closes = _get_closes(hist_data, sym)
    return closes[-1] if closes else None


def _get_chg5d(hist_data: dict, sym: str):
    """5-Tage-Kursveränderung in % (identisch zu fetchYahooSingle.chg5d im JS)."""
    closes = _get_closes(hist_data, sym)
    if len(closes) < 6:
        return None
    prev5 = closes[-6]
    if prev5 == 0:
        return None
    return round((closes[-1] - prev5) / prev5 * 100, 2)


def calc_mcm_ndx_breadth(hist_data: dict) -> float | None:
    """Port der NDX-Breadth-Berechnung aus calcBullIndicator() in index.html.
    Berechnet % der NDX-100 Titel über ihrer 50-EMA (Näherung: SMA50).
    Schwellen: caution ≤ 50%, risk ≤ 35% (identisch zu _MCM_SIGNAL_RULES).
    Nutzt Scanner-Universum als Proxy (enthält den Großteil der NDX-Titel).
    """
    NDX_PROXY = [
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
        "ASML", "NFLX", "AMD", "AZN", "ADBE", "QCOM", "CSCO", "TMUS", "LIN", "PEP",
        "INTC", "INTU", "AMAT", "AMGN", "ISRG", "MU", "ARM", "BKNG", "LRCX", "REGN",
        "ADI", "KLAC", "PANW", "MDLZ", "FTNT", "SNPS", "CRWD", "CDNS", "MRVL", "CEG",
        "CSGP", "CSX", "ORLY", "NXPI", "MCHP", "PCAR", "AEP", "WDAY", "ROST", "MNST",
        "DXCM", "PAYX", "CHTR", "FANG", "ODFL", "KDP", "EXC", "FAST", "BIIB", "IDXX",
        "ON", "GFS", "KHC", "EA", "DDOG", "CTSH", "VRSK", "GEHC", "XEL", "ANSS",
        "CTAS", "CPRT", "TEAM", "SIRI", "TTWO", "DLTR", "ILMN", "ZS", "ALGN", "WBD",
        "MTCH", "LCID", "PDD", "BIDU", "JD", "MELI", "ABNB", "ZM", "DOCU",
    ]
    above, total = 0, 0
    for sym in NDX_PROXY:
        closes = _get_closes(hist_data, sym, 60)
        if len(closes) < 50:
            continue
        sma50 = sum(closes[-50:]) / 50
        if closes[-1] > sma50:
            above += 1
        total += 1
    if total < 10:  # Zu wenige Daten — kein verlässlicher Wert
        return None
    return round(above / total * 100, 1)


def calc_mcm_intermarket_score(hist_data: dict, market: dict) -> int | None:
    """Port von loadIntermarket() Scoring-Teil aus index.html.
    Score 0-100: niedrig = Risk-On, hoch = Risk-Off (identisch zur JS-Logik).
    Verwendet gewichteten Durchschnitt der verfügbaren Signale.
    Schwellen: caution ≥ 40, risk ≥ 60 (identisch zu _MCM_SIGNAL_RULES).
    """
    score_points, score_count = 0, 0

    # VVIX: <90 OK (15 Pts Risk-On), 90-110 Warnung (8), >110 Risk-Off (2)
    zsc = market.get("zscores", {}) or {}
    vvix_val = (zsc.get("vvix") or {}).get("value")  # Rohwert, nicht Z-Score
    if vvix_val is None:
        vix_term = market.get("vixTerm", {}) or {}
        vvix_val = vix_term.get("vvix")
    if vvix_val is not None:
        pts = 15 if vvix_val < 90 else (8 if vvix_val < 110 else 2)
        score_points += pts; score_count += 1

    # AUD/USD: 5d-Chg >+0.5% = Risk-On (14), <-0.5% = Risk-Off (5), sonst neutral (9)
    aud_chg = _get_chg5d(hist_data, "AUDUSD=X")
    if aud_chg is None:
        aud_chg = _get_chg5d(hist_data, "AUD=X")
    if aud_chg is not None:
        pts = 14 if aud_chg > 0.5 else (5 if aud_chg < -0.5 else 9)
        score_points += pts; score_count += 1

    # JPY/USD: steigend = Risk-Off (5), fallend = Risk-On (14)
    jpy_chg = _get_chg5d(hist_data, "JPYUSD=X")
    if jpy_chg is None:
        jpy_chg = _get_chg5d(hist_data, "JPY=X")
    if jpy_chg is not None:
        pts = 5 if jpy_chg > 0.3 else (14 if jpy_chg < -0.3 else 9)
        score_points += pts; score_count += 1

    # Cu/Gold Ratio: steigend = Risk-On (15), fallend = Risk-Off (4)
    cu_closes  = _get_closes(hist_data, "HG=F", 2)
    gld_closes = _get_closes(hist_data, "GC=F", 2)
    if len(cu_closes) >= 2 and len(gld_closes) >= 2 and gld_closes[-1] > 0 and gld_closes[-2] > 0:
        ratio_now  = cu_closes[-1]  / gld_closes[-1]
        ratio_prev = cu_closes[-2]  / gld_closes[-2]
        cu_gold_chg = (ratio_now - ratio_prev) / ratio_prev * 100 if ratio_prev > 0 else 0
        pts = 15 if cu_gold_chg > 0.5 else (4 if cu_gold_chg < -0.5 else 8)
        score_points += pts; score_count += 1

    # JNK/LQD Spread: steigend = Risk-On (15), fallend = Risk-Off (4)
    jnk_closes = _get_closes(hist_data, "JNK", 2)
    lqd_closes = _get_closes(hist_data, "LQD", 2)
    if len(jnk_closes) >= 2 and len(lqd_closes) >= 2 and lqd_closes[-1] > 0 and lqd_closes[-2] > 0:
        ratio_now  = jnk_closes[-1] / lqd_closes[-1]
        ratio_prev = jnk_closes[-2] / lqd_closes[-2]
        spread_chg = (ratio_now - ratio_prev) / ratio_prev * 100 if ratio_prev > 0 else 0
        pts = 15 if spread_chg > 0.2 else (4 if spread_chg < -0.2 else 8)
        score_points += pts; score_count += 1

    # 10J Treasury: >5% = Risk-Off stark (4), >4.5% = Risk-Off (7), >3.5% = Neutral (10), sonst Risk-On (13)
    tnx = _get_last_price(hist_data, "^TNX")
    if tnx is not None:
        pts = 4 if tnx > 5 else (7 if tnx > 4.5 else (10 if tnx > 3.5 else 13))
        score_points += pts; score_count += 1

    # 2J/10J Yield Spread aus FRED (bereits im Aggregator)
    fred = market.get("fredMacro", {}) or {}
    yc = fred.get("yield_curve", {}) or {}
    if yc.get("ok"):
        spread = yc.get("spread_10y2y")
        if spread is not None:
            pts = 14 if spread > 0.5 else (9 if spread > 0 else (5 if spread > -0.5 else 2))
            score_points += pts; score_count += 1

    if score_count == 0:
        return None
    # Normalisierung auf 0-100 (analog JS: scorePoints / (scoreCount * 15) * 100, invertiert)
    max_possible = score_count * 15
    # JS-Score: hoch = Risk-On. Wir wollen: hoch = Risk-Off (Stress). Invertieren:
    raw_pct = round(score_points / max_possible * 100)
    return 100 - raw_pct  # 0 = pure Risk-On, 100 = pure Risk-Off


def calc_mcm_treasury_stress(market: dict, hist_data: dict) -> int | None:
    """Port von calcTreasuryStress() aus index.html.
    Score 0-100: hoch = Treasury-Stress.
    Schwellen: caution ≥ 35, risk ≥ 60 (identisch zu _MCM_SIGNAL_RULES).
    Auktionsparameter nicht serverseitig verfügbar → nur Marktdaten-Komponenten.
    """
    score = 0
    components = 0

    # Zinskurve: Inversion = +15 Punkte (aus FRED, bereits im Aggregator)
    fred = market.get("fredMacro", {}) or {}
    yc = fred.get("yield_curve", {}) or {}
    if yc.get("ok") and yc.get("inverted"):
        score += 15
    if yc.get("ok"):
        components += 1

    # DXY vs SMA20: starker Dollar = +15 Stress (analog calcTreasuryStress JS)
    dxy_closes = _get_closes(hist_data, "DX-Y.NYB", 25)
    if not dxy_closes:
        dxy_closes = _get_closes(hist_data, "DXY", 25)
    if len(dxy_closes) >= 20:
        sma20 = sum(dxy_closes[-20:]) / 20
        if dxy_closes[-1] > sma20:
            score += 15
        components += 1

    # VIX > 20 = +15 Stress
    vix_term = market.get("vixTerm", {}) or {}
    vix = vix_term.get("vix")
    if vix is not None:
        if vix > 20:
            score += 15
        components += 1

    # MOVE-Index-Level als Anleihe-Vola-Signal
    move = market.get("moveIndex", {}) or {}
    move_val = move.get("current") or move.get("value")
    if move_val is not None:
        # MOVE > 130 = erhöhter Bond-Stress (+10), > 160 = stark (+20)
        if move_val > 160:
            score += 20
        elif move_val > 130:
            score += 10
        components += 1

    if components == 0:
        return None
    return min(100, round(score))


def calc_mcm_bull_indicator(market: dict, hist_data: dict, ios_market: dict) -> int | None:
    """Port von calcBullIndicator() aus index.html.
    Score 0-100: hoch = bullisch, niedrig = bearisch.
    Schwellen: caution ≤ 35 (identisch zu _MCM_SIGNAL_RULES).
    Nutzt server-verfügbare Daten; UI-only Signale (tickerData MACD) werden
    durch ios_market.iosMarketScore ersetzt (semantisch äquivalent).
    """
    total_score, max_score = 0, 0

    # SIGNAL 1: IOS-Market-Score als Marktbreite-Proxy (ersetzt tickerData MACD-Breadth)
    ios_score = ios_market.get("iosMarketScore") if ios_market else None
    if ios_score is not None:
        # Analog zu pctBullMacd in JS: >61 = 20 Pts, >50 = 12, >40 = 6, sonst 2
        pts = 20 if ios_score > 61 else (12 if ios_score > 50 else (6 if ios_score > 40 else 2))
        total_score += pts; max_score += 20

    # SIGNAL 2: JNK/SPY Divergenz (HYG/SPY Divergenz-Port)
    jnk_chg = _get_chg5d(hist_data, "JNK")
    spy_chg  = _get_chg5d(hist_data, "SPY")
    if jnk_chg is not None and spy_chg is not None:
        if spy_chg < -1 and jnk_chg > -0.5:
            pts = 18  # SPY schwach aber JNK stabil — Smart Money kauft
        elif spy_chg > 0 and jnk_chg > 0:
            pts = 15  # Risk-On bestätigt
        elif spy_chg < -2 and jnk_chg < -1:
            pts = 2   # Beide schwach
        else:
            pts = 8   # Neutral
        total_score += pts; max_score += 18

    # SIGNAL 3: VVIX als Frühwarner
    vix_term = market.get("vixTerm", {}) or {}
    zsc = market.get("zscores", {}) or {}
    vvix_val = (zsc.get("vvix") or {}).get("value") or vix_term.get("vvix")
    vvix_chg = _get_chg5d(hist_data, "^VVIX")
    if vvix_val is not None:
        if vvix_val > 100 and vvix_chg is not None and vvix_chg < -5:
            pts = 15  # VVIX fällt von hohem Niveau
        elif vvix_val < 90:
            pts = 12  # Ruhig
        elif vvix_val > 110:
            pts = 2   # Extrem hoch
        else:
            pts = 7
        total_score += pts; max_score += 15

    # SIGNAL 4: CNN Fear & Greed (kontraindikativ)
    fg = market.get("fearGreed", {}) or {}
    fg_score = fg.get("score")
    if fg_score is not None:
        if fg_score <= 20:
            pts = 15  # Extreme Fear = Kontraindikator bullisch
        elif fg_score <= 35:
            pts = 11
        elif fg_score >= 80:
            pts = 2
        elif fg_score >= 65:
            pts = 7
        else:
            pts = 8
        total_score += pts; max_score += 15

    # SIGNAL 5: VIX als Kontraindikator
    vix = vix_term.get("vix")
    if vix is not None:
        if vix > 35:
            pts = 12  # Panik = Kontraindikator
        elif vix > 25:
            pts = 8
        elif vix < 15:
            pts = 6
        else:
            pts = 7
        total_score += pts; max_score += 12

    if max_score == 0:
        return None
    return round(total_score / max_score * 100)


def build_server_market_context(master):
    """market_context serverseitig — Pendant zu buildMarketContext() im JS-Port.
    Faktoren (14 + 3 Calendar):
      vix, vvix, skew, pcr, fear_greed           — direkt aus market-Daten
      ndx_breadth, intermarket_score,             — v5.13.0 (21.07.2026)
      treasury_stress, bull_indicator             — server-side calc-Funktionen
      net_liquidity                               — v5.14.0 (01.08.2026), FRED trend_4w
      move_index, skew_vvix_div,                  — v5.36.5 (16.08.2026), MCM-
      breadth_osc, distribution_days              — Paritaet-Nachzug (s. Changelog)
      fed_window, nfp_window, cpi_window          — macro-calendar
    ACHTUNG: "MCM-Paritaet vollstaendig" ist eine Momentaufnahme, kein
    Dauerzustand — bei jedem neuen Client-Registry-Eintrag (ko-indicators.json)
    hier gegenpruefen, sonst driftet es erneut (s. MCM-PARITAET-KONZEPT.md).
    """
    market = master.get("market", {}) or {}
    meta   = master.get("meta", {}) or {}
    vt     = market.get("vixTerm", {}) or {}
    pcr_d  = market.get("pcr", {}) or {}
    fg     = market.get("fearGreed", {}) or {}
    zsc    = market.get("zscores", {}) or {}

    regime = master.get("masterShortlist_meta", {}).get("regimeUsed") or meta.get("regimeUsed")
    # Fallback: regimeUsed liegt strukturell in der Leaderboard-Rueckgabe, nicht in meta
    # (siehe Bugfix-Kommentar in generate_daily_snapshot). Wird dort korrekt injiziert.

    factors = {}
    caution, risk = [], []

    def _add(fid, value, rules, label=None):
        if value is None:
            return
        sig = _mcm_eval_signal(rules, value)
        factors[fid] = {"value": value, "signal": sig}
        if label:
            factors[fid]["label"] = label
        if sig == "caution":
            caution.append(fid)
        elif sig == "risk":
            risk.append(fid)

    _add("vix",        vt.get("vix"),           _MCM_SIGNAL_RULES["vix"])
    _add("vvix",        (zsc.get("vvix") or {}).get("zscore"), _MCM_SIGNAL_RULES["vvix"])
    _add("skew",        (zsc.get("skew") or {}).get("percentile"), _MCM_SIGNAL_RULES["skew"])
    _add("pcr",         pcr_d.get("pcr"),        _MCM_SIGNAL_RULES["pcr"])
    _add("fear_greed",  fg.get("score"),         _MCM_SIGNAL_RULES["fear_greed"])

    # ── MCM-Parität: 4 neue Server-Faktoren (v5.13.0) ────────────────────────
    # hist_data wird von main() in master["_hist_data"] injiziert (analog regimeUsed).
    hist_data  = master.get("_hist_data") or {}
    ios_market = market.get("iosMarket") or {}

    ndx_b  = calc_mcm_ndx_breadth(hist_data)
    im_s   = calc_mcm_intermarket_score(hist_data, market)
    tr_s   = calc_mcm_treasury_stress(market, hist_data)
    bull_i = calc_mcm_bull_indicator(market, hist_data, ios_market)

    _add("ndx_breadth",       ndx_b,  _MCM_SIGNAL_RULES["ndx_breadth"])
    _add("intermarket_score", im_s,   _MCM_SIGNAL_RULES["intermarket_score"])
    _add("treasury_stress",   tr_s,   _MCM_SIGNAL_RULES["treasury_stress"])
    _add("bull_indicator",    bull_i, _MCM_SIGNAL_RULES["bull_indicator"])

    # net_liquidity: 4W-Trend aus FRED (identische Schwelle wie ko-indicators.json)
    fred       = market.get("fredMacro", {}) or {}
    nl         = fred.get("net_liquidity", {}) or {}
    nl_trend4w = nl.get("trend_4w") if nl.get("ok") else None
    _add("net_liquidity", nl_trend4w, _MCM_SIGNAL_RULES["net_liquidity"])

    # ── MCM-Paritaet-Nachzug (16.08.2026): 4 Faktoren, die im Client seit
    # Wochen registriert waren (ko-indicators.json v2.2.0/v2.3.0), aber nie
    # nach Python portiert wurden — dieser Docstring behauptete "vollstaendig",
    # das war seit der ersten Client-Erweiterung nicht mehr korrekt. Siehe
    # MCM-PARITAET-KONZEPT.md fuer die Historie des ersten (04-Faktoren-)
    # Parity-Sprints vom 21.07. — dieser hier ist die Fortsetzung/Nachtrag.
    mi = market.get("moveIndex", {}) or {}
    mi_z = mi.get("zscore") if mi.get("ok") else None
    _add("move_index", mi_z, _MCM_SIGNAL_RULES["move_index"],
         label=(f"MOVE Index: {mi.get('current')} (Z={mi_z:+.2f}, P{mi.get('percentile')})" if mi_z is not None else None))

    div = (zsc.get("skew_vvix_divergence") or {})
    div_val = div.get("value") if div.get("ok") else None
    _add("skew_vvix_div", div_val, _MCM_SIGNAL_RULES["skew_vvix_div"],
         label=(f"SKEW/VVIX-Divergenz: {div_val} → {div.get('signal')}" if div_val is not None else None))

    bo = market.get("breadthOsc", {}) or {}
    bo_val = bo.get("oscillator")
    _add("breadth_osc", bo_val, _MCM_SIGNAL_RULES["breadth_osc"],
         label=(f"UIQ Breadth-Oszillator (McClellan): {bo_val} ({bo.get('ema19')}/{bo.get('ema39')} EMA19/39)" if bo_val is not None else None))

    dd = market.get("distributionDays", {}) or {}
    dd_max_val = dd.get("dd_max")
    _add("distribution_days", dd_max_val, _MCM_SIGNAL_RULES["distribution_days"],
         label=(f"Distribution Days (25T, O'Neil/IBD): SPY {dd.get('dd_spy')} / QQQ {dd.get('dd_qqq')} ({dd.get('dd_severity')})" if dd_max_val is not None else None))

    # ── Konjunktur-Indikatoren (17.08.2026, Axel-Anfrage) ────────────────────
    nfci = fred.get("nfci", {}) or {}
    nfci_val = nfci.get("current") if nfci.get("ok") else None
    _add("nfci", nfci_val, _MCM_SIGNAL_RULES["nfci"],
         label=(f"NFCI (Chicago Fed): {nfci_val:+.3f} (Z={nfci.get('zscore')})" if nfci_val is not None else None))

    cpi = fred.get("core_cpi_yoy", {}) or {}
    cpi_val = cpi.get("current") if cpi.get("ok") else None
    _add("core_cpi_yoy", cpi_val, _MCM_SIGNAL_RULES["core_cpi_yoy"],
         label=(f"US Core CPI YoY: {cpi_val}%" if cpi_val is not None else None))

    unemp = fred.get("unemployment", {}) or {}
    sahm_val = unemp.get("sahmRule") if unemp.get("ok") else None
    _add("sahm_rule", sahm_val, _MCM_SIGNAL_RULES["sahm_rule"],
         label=(f"Sahm-Rule: {sahm_val:+.2f} Pkt (Arbeitslosenrate {unemp.get('current')}%, Trigger ≥0.50)" if sahm_val is not None else None))

    cli = fred.get("oecd_cli", {}) or {}
    cli_score = cli.get("quadrantScore") if cli.get("ok") else None
    _add("oecd_cli_score", cli_score, _MCM_SIGNAL_RULES["oecd_cli_score"],
         label=(f"OECD Composite Leading Indicator (USA): {cli.get('current')} → {cli.get('signal')}" if cli_score is not None else None))

    truck = fred.get("heavy_truck", {}) or {}
    truck_trend = truck.get("trend_3m_pct") if truck.get("ok") else None
    _add("heavy_truck_trend", truck_trend, _MCM_SIGNAL_RULES["heavy_truck_trend"],
         label=(f"Heavy Truck Sales (10M-Schnitt, 3M-Trend): {truck_trend:+.1f}% → {truck.get('signal')}" if truck_trend is not None else None))

    # Rein informativ, kein caution/risk-Signal (Rotationsrichtung ist nicht
    # per se "gut" oder "schlecht" — Interpretation bleibt der KI-Prosa
    # überlassen, analog zum bestehenden qqq_markov-Faktor).
    sd = market.get("stapleDiscretionary", {}) or {}
    if sd.get("ok"):
        factors["staples_discretionary"] = {
            "value": sd.get("trend"), "signal": None,
            "label": f"Consumer Staples vs. Discretionary (XLP/XLY): {sd.get('ratio')} — 5T {sd.get('chg5d')}% / 20T {sd.get('chg20d')}% ({sd.get('trend')})",
        }
    gv = market.get("growthValue", {}) or {}
    if gv.get("ok"):
        factors["growth_value"] = {
            "value": gv.get("trend"), "signal": None,
            "label": f"Growth vs. Value (IWF/IWD): {gv.get('ratio')} — 5T {gv.get('chg5d')}% / 20T {gv.get('chg20d')}% ({gv.get('trend')})",
        }

    # Calendar-Faktoren
    events = _mcm_load_macro_calendar()
    now_utc = datetime.now(timezone.utc)
    for fid, cfg in _MCM_CALENDAR_FACTORS.items():
        r = _mcm_eval_calendar_factor(cfg, events, now_utc)
        if r:
            factors[fid] = r
            if r["signal"] == "caution":
                caution.append(fid)
            elif r["signal"] == "risk":
                risk.append(fid)

    risk_level = "high" if risk else ("elevated" if len(caution) >= 2 else "low")
    return {
        "regime": regime,
        "factors": factors,
        "summary": {"risk_level": risk_level, "caution_flags": caution, "risk_flags": risk},
    }


def calc_server_strategy_gates(regime, ctx):
    """Pendant zu KoMarketState.calcStrategyGates() im JS-Port. Nur Farben +
    Downgrades — Notes/Labels bleiben UI-Domäne (Frontend zeigt sie an)."""
    base = _MCM_REGIME_GATES.get(regime or "NEUTRAL", _MCM_REGIME_GATES["NEUTRAL"])
    strategies = dict(base["strategies"])  # Kopie
    downgrades = []
    if ctx and ctx.get("factors"):
        for fid, affected in _MCM_DOWNGRADE_RULES:
            f = ctx["factors"].get(fid)
            if not f or not f.get("signal") or f["signal"] == "ok":
                continue
            for s in affected:
                if s not in strategies:
                    continue
                cur = strategies[s]
                if f["signal"] == "caution" and cur == "green":
                    strategies[s] = "amber"
                    downgrades.append({"strategy": s, "from": "green", "to": "amber", "factor": fid})
                elif f["signal"] == "risk" and cur in ("green", "amber"):
                    strategies[s] = "red"
                    downgrades.append({"strategy": s, "from": cur, "to": "red", "factor": fid})
    return {"action": base["action"], "strategies": strategies, "downgrades": downgrades}


# ── MSE-REGIME PORT (19.08.2026, Axel-Anfrage — Bug 1/3 Root-Cause-Fix) ────────
# 1:1-Port von KoMarketState.determineRegime() / normalizeMetrics() / zScore() /
# percentileRank() aus ahsub/ko-modules/ko-market-state.js (Client, MSE v2.3).
#
# HINTERGRUND: Der bisherige server-seitige `market_regime_str` (s.u., zur
# Leaderboard-Selektion) ist EIN GANZ ANDERES, einfacheres Modell (nur VIX-
# Termstruktur + VIX-Level) — kein Bugfix-Ziel, bleibt für Leaderboards/
# score_options_collar() unveraendert (Track-Record-Risiko, s. Uebergabe
# 2026-08-19). Diese neue Funktion ist AUSSCHLIESSLICH fuer den KI-Text in
# generate_daily_snapshot() gedacht, damit das dort genannte Regime mit dem
# Client-Badge (KoMarketState._lastRegime, MSE v2.3, Multi-Faktor) uebereinstimmt.
#
# WICHTIG: Fensterlaenge (LOOKBACK=20) und Thresholds MUESSEN 1:1 mit dem
# Client synchron gehalten werden — bei Aenderungen an ko-market-state.js
# IMMER auch hier nachziehen (und umgekehrt), sonst lebt die Divergenz einfach
# an anderer Stelle weiter.
#
# NOCH NICHT VALIDIERT — vor Produktiveinsatz gegen historische Client-Regime-
# Ausgaben diffen (analog REGIME-BACKTEST-VALIDIERUNG.md-Vorgehen), s. Uebergabe.

_MSE_LOOKBACK = 20

_MSE_THRESHOLDS = {
    "vixTermContango":  1.05,
    "vixTermFlat":       0.98,
    "vvixHighStress":    1.5,
    "vvixLowStress":    -1.0,
    "gexShortGamma":    -1.0,
    "dixAccumulation":   0.5,
    "skewHighHedging":  80,
}


def _mse_z_score(series, current_val):
    """1:1-Port von KoMarketState.zScore() (ko-market-state.js)."""
    if not series or len(series) < 3 or current_val is None:
        return None
    n = min(len(series), _MSE_LOOKBACK)
    data = series[-n:]
    mean = sum(data) / n
    variance = sum((v - mean) ** 2 for v in data) / n
    std = variance ** 0.5
    if std == 0:
        return 0.0
    return round(((current_val - mean) / std) * 100) / 100


def _mse_percentile_rank(series, current_val):
    """1:1-Port von KoMarketState.percentileRank() (ko-market-state.js)."""
    if not series or len(series) < 3 or current_val is None:
        return None
    n = min(len(series), _MSE_LOOKBACK)
    data = series[-n:]
    below = sum(1 for v in data if v <= current_val)
    return round((below / len(data)) * 100)


def determine_mse_regime(mse_history, dix_gex, vix_term):
    """1:1-Port von KoMarketState.normalizeMetrics() + .determineRegime().

    Input:
        mse_history: dict mit "vvix"/"skew"/"vix"/"vixRatio" (Listen, wie von
                      fetch_mse_history() geliefert — 252T-Fenster im Aufrufer)
        dix_gex:      dict mit "gex"/"dix" (aktuell) + "history" (dict mit
                      "gex"/"dix"-Listen, wie von fetch_dix_gex() geliefert)
        vix_term:     dict mit "vix"/"vix3m" (aktuell, wie von fetch_vix_term())

    Output: (regime_str, metrics_dict) — regime_str eines von
            BULL_QUIET / BULL_FRAGILE / STRESS_UNSTABLE / POST_PANIC_REVERSION
            / NEUTRAL. metrics_dict fuer Debug/Prompt-Kontext.
    """
    T = _MSE_THRESHOLDS

    vvix_hist = (mse_history or {}).get("vvix") or []
    skew_hist = (mse_history or {}).get("skew") or []
    gex_hist  = ((dix_gex or {}).get("history") or {}).get("gex") or []
    dix_hist  = ((dix_gex or {}).get("history") or {}).get("dix") or []

    vvix_raw = vvix_hist[-1] if vvix_hist else None
    skew_raw = skew_hist[-1] if skew_hist else None
    gex_raw  = (dix_gex or {}).get("gex")
    dix_raw  = (dix_gex or {}).get("dix")

    vix_val  = (vix_term or {}).get("vix")
    vix3m    = (vix_term or {}).get("vix3m")
    vix_ratio = round(vix3m / vix_val, 3) if (vix_val and vix3m and vix_val > 0) else None

    if vix_ratio is None:
        term_structure = "UNKNOWN"
    elif vix_ratio > T["vixTermContango"]:
        term_structure = "CONTANGO"
    elif vix_ratio < T["vixTermFlat"]:
        term_structure = "BACKWARDATION"
    else:
        term_structure = "FLAT"

    metrics = {
        "vvix_raw": vvix_raw, "gex_raw": gex_raw, "dix_raw": dix_raw, "skew_raw": skew_raw,
        "vixRatio": vix_ratio,
        "vvix_z20":    _mse_z_score(vvix_hist, vvix_raw),
        "gex_z20":     _mse_z_score(gex_hist, gex_raw),
        "dix_z20":     _mse_z_score(dix_hist, dix_raw),
        "skew_pct20":  _mse_percentile_rank(skew_hist, skew_raw),
        "term_structure": term_structure,
    }

    vvix_z20   = metrics["vvix_z20"]
    gex_z20    = metrics["gex_z20"]
    dix_z20    = metrics["dix_z20"]
    skew_pct20 = metrics["skew_pct20"]
    term       = metrics["term_structure"]

    # Fehlende Kernwerte (zu kurze Historie o.ae.) -> NEUTRAL, wie Client bei
    # unvollstaendigen Metriken (Vergleiche mit None sind in JS falsy/false,
    # in Python werfen sie TypeError -- deshalb hier explizite Guards).
    if vvix_z20 is None or gex_z20 is None or dix_z20 is None or skew_pct20 is None:
        return "NEUTRAL", metrics

    if term == "BACKWARDATION" or (vvix_z20 > T["vvixHighStress"] and gex_z20 < T["gexShortGamma"]):
        return "STRESS_UNSTABLE", metrics
    if term == "FLAT" and dix_z20 > T["dixAccumulation"] and vvix_z20 < 0:
        return "POST_PANIC_REVERSION", metrics
    if term == "CONTANGO" and skew_pct20 > T["skewHighHedging"] and vvix_z20 > 0.8:
        return "BULL_FRAGILE", metrics
    if term == "CONTANGO" and gex_z20 > 0 and dix_z20 >= -0.5:
        return "BULL_QUIET", metrics
    return "NEUTRAL", metrics


def generate_daily_snapshot(master):
    """Generiert das Morning Briefing serverseitig via Anthropic API.

    Input:  master (vollstaendiger Aggregator-Output nach main())
    Output: daily_market_snapshot-Dict fuer KV-Push
    Fehler: fehlerisoliert - Exception bricht main() nie ab.

    BUGFIX (14.07.2026, Axel-Review v323): Vor diesem Fix waren VIX/Regime/PCR
    IMMER "n/v" im Briefing, unabhaengig von der tatsaechlichen Datenlage —
    reine Feldpfad-Fehler, keine Timing-Probleme:
      - regime kam aus meta["regimeUsed"] (existiert dort nie, liegt in der
        Leaderboard-Rueckgabe) -> jetzt: master["masterShortlist_meta"] Fallback
        UND direkter Parameter (siehe main()-Aufrufstelle, dort korrekt injiziert)
      - VIX kam aus snapshot["vix"] (kein VIX-Symbol in fetch_market_snapshot())
        -> jetzt: vixTerm["vix"] (fetch_vix_term() liefert den echten Wert)
      - PCR kam aus pcr["pcr_equity"]/["pcr_index"] (Felder existieren nie im
        Schema, nur ein einzelner Blended-Wert pcr["pcr"]) -> jetzt: pcr["pcr"]
        direkt, ein Wert statt Equity/Index-Split
    MCM-PORT (14.07.2026): market_context + calc_server_strategy_gates() bauen
    denselben Kontext wie der Client (axel-scanner v322/v323) — Prompt bekommt
    jetzt Signal-Flags (ok/caution/risk) + Calendar-Fenster + die bereits
    berechnete Ampel mit dem Auftrag, sie zu erklaeren statt zu widersprechen.
    """
    import urllib.request as _ur
    import json as _j

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.warning("  [SNAPSHOT] ANTHROPIC_API_KEY fehlt - uebersprungen")
        return {"ok": False, "reason": "no_api_key"}

    try:
        market    = master.get("market", {})
        snap      = market.get("snapshot", {})
        fg        = market.get("fearGreed", {})
        meta      = master.get("meta", {})
        # BUGFIX: regimeUsed korrekt lesen (siehe Docstring) — Aufruferstelle in
        # main() injiziert regimeUsed zusaetzlich in meta, siehe dortigen Patch.
        regime_aggregator = meta.get("regimeUsed") or "-"
        vix_term  = market.get("vixTerm", {}) or {}
        pcr_d     = market.get("pcr", {}) or {}
        # NEU (15.08.2026, Fortsetzung §5 Client-Fix vom selben Tag): dixGex lag
        # bereits vollstaendig in master["market"]["dixGex"] vor (siehe main()-
        # Merge), wurde aber bislang nie in mlines/den Prompt aufgenommen -
        # server-seitiger Prompt kannte DIX/GEX bis hierher ueberhaupt nicht.
        dix_gex   = market.get("dixGex", {}) or {}
        shortlist = master.get("masterShortlist", [])[:10]
        snap_ts   = meta.get("generated", "-")
        ltd       = meta.get("last_trading_day", "-")

        # NEU (19.08.2026, Bug 1/3 Root-Cause-Fix — s. Uebergabeprotokoll):
        # Bisher nutzte der KI-Text hier `regime_aggregator` (VIX-Term+Level-
        # Heuristik, identisch zu market_regime_str fuer die Leaderboard-
        # Selektion) — das WEICHT strukturell vom Client-Badge (MSE v2.3,
        # Multi-Faktor VVIX/GEX/DIX/SKEW, s. ko-market-state.js) ab, dadurch
        # sahen Nutzer z.B. "BULL_QUIET" im Briefing-Text bei gleichzeitig
        # "NEUTRAL" im Live-Badge. Fix NUR fuer den KI-Text-Kontext hier
        # (ctx/gates/Prompt) — market_regime_str (Leaderboard/Collar-Scoring,
        # s. weiter unten in main()) bleibt bewusst UNVERAENDERT, um die
        # laufende Track-Record-Selektion nicht zu beeinflussen.
        # NOCH NICHT VALIDIERT — vor produktivem Rollout gegen historische
        # Client-Regime-Werte diffen (s. determine_mse_regime()-Docstring).
        mse_history = market.get("mseHistory", {}) or {}
        regime_mse, _mse_metrics = determine_mse_regime(mse_history, dix_gex, vix_term)
        regime = regime_mse
        if regime_aggregator != "-" and regime_aggregator != regime_mse:
            log.info(
                f"  [SNAPSHOT] Regime-Divergenz: Aggregator={regime_aggregator} "
                f"vs. MSE(client-aequivalent)={regime_mse} — Briefing-Text nutzt MSE."
            )

        def _fmt(val, decimals=2, suffix=""):
            if val is None:
                return "n/v"
            try:
                return f"{round(float(val), decimals)}{suffix}"
            except Exception:
                return str(val)

        # ── MCM: market_context + deterministische Strategie-Gates ──────
        ctx   = build_server_market_context(master)
        ctx["regime"] = regime if regime != "-" else None
        gates = calc_server_strategy_gates(regime if regime != "-" else None, ctx)

        mlines = [
            f"SNAPSHOT-ZEITPUNKT: {snap_ts} UTC (Aggregator-Lauf, serverseitig)",
            f"LETZTER HANDELSTAG: {ltd}",
            "DATENBINDUNG: Ausschliesslich diese Messwerte - kein Trainingswissen.",
            "",
            "--- REGIME & TREND ---",
            f"Markt-Regime (MSE, client-aequivalent): {regime}",
        ]
        for key, label in [("spy", "SPY"), ("qqq", "QQQ"), ("iwm", "IWM")]:
            s = snap.get(key, {})
            if s.get("ok"):
                mlines.append(f"{label}: {_fmt(s.get('price'))} USD ({_fmt(s.get('chg_pct'), 2, '%')})")

        mlines += ["", "--- VOLATILITAET & SENTIMENT ---"]
        # BUGFIX: VIX aus vixTerm (fetch_vix_term()), nicht aus snapshot (kein VIX-Symbol dort)
        if vix_term.get("vix") is not None:
            mlines.append(f"VIX: {_fmt(vix_term.get('vix'))}")
        if vix_term.get("vix3m") is not None:
            mlines.append(f"VIX3M: {_fmt(vix_term.get('vix3m'))}")
        # BUGFIX: PCR-Schema hat nur einen Blended-Wert (pcr["pcr"]), keine Equity/Index-Trennung
        if pcr_d.get("pcr") is not None:
            mlines.append(f"Put/Call-Ratio: {_fmt(pcr_d.get('pcr'))} ({pcr_d.get('signal', '—')})")
        # NEU (15.08.2026): DIX/GEX (SqueezeMetrics, SPY-marktweit) - bisher komplett
        # gefehlt, obwohl Rohdaten laengst im master-Dict vorlagen (§5, s.o.).
        if dix_gex.get("dix") is not None:
            mlines.append(f"DIX (SqueezeMetrics, SPY-marktweit): {_fmt(dix_gex.get('dix'))}%")
        if dix_gex.get("gex") is not None:
            mlines.append(f"GEX (SqueezeMetrics, Markt-Gamma): {_fmt(dix_gex.get('gex'), 3)} Mrd USD"
                          + (" [negativ = Gamma-Flip-Zone, erhoehtes Gap-Risiko]" if dix_gex.get("gex", 0) < 0 else ""))
        if dix_gex.get("dixEtfBasket") is not None:
            mlines.append(f"DIX (ETF-Korb-Heuristik, {dix_gex.get('dixEtfBasketSource', '-')}): "
                          f"{_fmt(dix_gex.get('dixEtfBasket'))}%")
        # Fear & Greed — robuster Check: score muss vorhanden und eine Zahl sein
        fg_score = fg.get('score') if fg else None
        if fg_score is not None:
            mlines.append(f"Fear & Greed: {fg_score}/100 ({fg.get('rating', '-')})")
        # IOS Market Score — war bisher nicht in mlines! KI erfand ihn aus Training.
        ios_mkt = market.get("iosMarket") or {}
        ios_score = ios_mkt.get("iosMarketScore")
        if ios_score is not None:
            ios_rating = ios_mkt.get("iosMarketRating", "-")
            ios_decision = ios_mkt.get("iosMarketDecision", "-")
            mlines.append(f"IOS Market Score: {ios_score}/100 ({ios_rating} — {ios_decision})")

        mlines += ["", "--- MAKRO ---"]
        fred = market.get("fredMacro", {})
        if fred:
            mlines.append(f"HY-Spread: {_fmt(fred.get('hy_spread'))} %")
            mlines.append(f"Net Liquidity (Fed): {_fmt(fred.get('net_liquidity'), 0)} Mrd USD")

        mlines += ["", "--- ROHSTOFFE & FX ---"]
        for key, label in [("gold", "Gold"), ("oil_wti", "Oel WTI"), ("btc", "Bitcoin")]:
            s = snap.get(key, {})
            if s.get("ok"):
                mlines.append(f"{label}: {_fmt(s.get('price'))} ({_fmt(s.get('chg_pct'), 2, '%')})")

        zscores   = market.get("zscores", {})
        sektor_rs = zscores.get("sector_rs", {})
        if sektor_rs:
            sorted_rs = sorted(sektor_rs.items(), key=lambda x: x[1] if x[1] else 0, reverse=True)
            top3  = ", ".join(f"{k}:+{v:.2f}" for k, v in sorted_rs[:3]  if v and v > 0)
            flop3 = ", ".join(f"{k}:{v:.2f}"  for k, v in sorted_rs[-3:] if v and v < 0)
            if top3:  mlines.append(f"Sektor RS Top:  {top3}")
            if flop3: mlines.append(f"Sektor RS Flop: {flop3}")

        if shortlist:
            mlines += ["", "--- TOP-10 SHORTLIST ---"]
            for t in shortlist:
                mlines.append(
                    f"{t.get('sym', '?')}: Score {t.get('score', '?')}/100,"
                    f" Strategie {t.get('strategy', '?')}"
                )

        # ── MCM: Context + berechnete Ampel als eigener Block ────────────
        mlines += ["", "--- MARKET CONTEXT (Single Source of Truth, MCM) ---"]
        mlines.append(f"Aggregiertes Risk-Level: {ctx['summary']['risk_level'].upper()}"
                      + (f" | Caution: {', '.join(ctx['summary']['caution_flags'])}" if ctx['summary']['caution_flags'] else "")
                      + (f" | Risk: {', '.join(ctx['summary']['risk_flags'])}" if ctx['summary']['risk_flags'] else ""))
        for fid, f in ctx["factors"].items():
            sig = f" [{f['signal'].upper()}]" if f.get("signal") else ""
            if f.get("label"):
                mlines.append(f"{f['label']}{sig}")
            else:
                mlines.append(f"{fid}: {f.get('value')}{sig}")
        mlines += ["", "--- STRATEGIE-AMPEL (bereits berechnet, regelbasiert) ---"]
        if gates["downgrades"]:
            dg_txt = " · ".join(f"{d['strategy']} {d['from']}->{d['to']} ({d['factor']})" for d in gates["downgrades"])
            mlines.append(f"Context-Downgrades: {dg_txt}")
        else:
            mlines.append("Keine Context-Downgrades — Regime-Basis-Gates gelten unveraendert.")
        gates_txt = ", ".join(f"{k}:{v}" for k, v in gates["strategies"].items())
        mlines.append(f"Berechnete Gates: {gates_txt}")
        mlines.append("AUFGABE: Deine Markteinschaetzung MUSS konsistent mit diesen Gates sein. Erklaere die Datenlage, die zu ihnen fuehrt — widersprich ihnen nicht.")

        messwerte = "\n".join(mlines)

        prompt = (
            "Du bist UIQ Market Analyst. Erstelle das Morning Briefing fuer heute.\n\n"
            "PFLICHTREGELN:\n"
            "- Ausschliesslich die unten stehenden Messwerte verwenden - KEIN Trainingswissen.\n"
            "- Keine Kurse, Zahlen oder Prozente erfinden. Fehlende Werte: n/v schreiben.\n"
            "- Ampeln (gruen/gelb/rot/leer) NUR aus den bereits berechneten Gates uebernehmen, nie selbst schaetzen.\n"
            "- JEDER Faktor aus MARKET CONTEXT mit Signal [CAUTION] oder [RISK] MUSS explizit im SENTIMENT-\n"
            "  oder MAKRO-KONDENSAT-Abschnitt namentlich genannt werden — unabhaengig davon, ob er in der\n"
            "  STRUKTUR-Liste unten als Pflichtinhalt aufgefuehrt ist. Diese Liste ist eine Mindestanforderung,\n"
            "  keine abschliessende Aufzaehlung. (16.08.2026: vorher stand ohne diese Regel im Ermessen der KI,\n"
            "  ob z.B. VVIX/SKEW/MOVE Index/Breadth-Oszillator bei caution/risk erwaehnt werden.)\n"
            "- Sprache: Deutsch, direkt, praezise. Keine Floskeln.\n\n"
            "STRUKTUR (immer diese Reihenfolge, siehe PFLICHTREGEL oben zu zusaetzlichen Pflichtnennungen):\n"
            "1. MARKTLAGE (3-4 Saetze): Regime + Trend + wichtigste Abweichung heute.\n"
            "2. SENTIMENT (2-3 Saetze, laenger falls zusaetzliche caution/risk-Faktoren zu nennen sind): VIX-Zone, PCR, DIX/GEX, Fear&Greed, IOS Market Score (jeweils falls in Messwerten vorhanden).\n"
            "3. MAKRO-KONDENSAT (2 Saetze, laenger falls zusaetzliche caution/risk-Faktoren zu nennen sind): HY-Spread + Net Liquidity.\n"
            "4. STRATEGIE-AMPEL (je Zeile: [Ampel] STRATEGIE - 1 Satz mit Messwert, Ampel-Farbe aus den berechneten Gates uebernehmen):\n"
            "   Momentum/SEPA | Swing-Trading | Mean Reversion Long | CSP/Wheel | Covered Call | KO-Long | KO-Short\n"
            "5. TOP-KANDIDATEN (max 5 Ticker, 1 Zeile: Ticker - Strategie - Kernaussage)\n\n"
            + messwerte
        )

        body = _j.dumps({
            "model":      "claude-sonnet-4-6",
            "max_tokens": 1200,
            "messages":   [{"role": "user", "content": prompt}]
        }).encode()
        req2 = _ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )
        with _ur.urlopen(req2, timeout=30) as resp:
            rd = _j.loads(resp.read().decode())
            briefing_text = rd.get("content", [{}])[0].get("text", "")

        log.info(f"  [SNAPSHOT] Morning Briefing generiert ({len(briefing_text)} Zeichen)")
        return {
            "ok":               True,
            "generated":        snap_ts,
            "last_trading_day": ltd,
            "regime":           regime,             # MSE-Regime (client-aequivalent) — fuehrend fuer Anzeige/Text
            "regimeAggregator": regime_aggregator,   # Markov/VIX-Term-Heuristik — nur Referenz, s. Docstring
            "briefing":         briefing_text,
            "messwerte_lines":  len(mlines),
            "model":            "claude-sonnet-4-6",
            "marketContext":    ctx,     # MCM: fuer Frontend/Konsistenz-Checks verfuegbar
            "strategyGates":    gates,   # MCM: deterministische Ampel, identisch zur Client-Berechnung
            "finArchive":       master.get("finArchive", {}),   # Russell3000-Shard-Status (fin_layer)
            "ivArchive":        master.get("ivArchive",  {}),   # IV-Archiv-Status (iv_layer)
        }
    except Exception as e:
        log.warning(f"  [SNAPSHOT] Fehler: {e}")
        return {"ok": False, "reason": f"exception: {e}"}


# ── HAUPTPROGRAMM ─────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════
# MARKET SNAPSHOT (v1.0, 26.07.2026)
# Schreibt alle berechneten Indikatoren aus results[] in einen eigenen KV-Key.
# Wird von externen Konsumenten (z.B. GuidelineIQ-Companion, künftige Apps)
# gelesen — unabhängig vom Track-Record und ohne zusätzliche API-Calls.
# Nutzt push_to_cloudflare_kv() für Konsistenz mit dem restlichen Aggregator.
# ═══════════════════════════════════════════════════════════════════════════════

def calc_score_divergences(regime: str, ios_market: dict, breadth_osc: dict) -> list:
    """Score-Paar-Divergenz-Detektor (SUITE.md Backlog #11, 28.07.2026).

    Prüft methodisch unabhängige Sub-Scores auf signifikante Widersprüche.
    Divergenzen sind kein Fehler — sie sind eigenständige Information:
    "Das Signal ist widersprüchlich, hier ist warum."

    Server-seitig verfügbare Paare (alle Inputs im nächtlichen Snapshot):
      1. Regime vs. IOS-Market-Score   — Makro-Klassifikation vs. Breiten-Score
      2. IOS-Trend vs. IOS-Breadth     — Trend-Leadership ohne Marktbreite
      3. Breadth-Oszillator vs. Regime — McClellan vs. Makro-Regime-Richtung

    Rückgabe: Liste von Divergenz-Objekten, leer wenn keine signifikante Divergenz.
    Jedes Objekt: {type, severity, scoreA, scoreB, delta, label, explanation}
    severity: "low" | "medium" | "high"
    """
    divergences = []

    def _add(dtype, severity, score_a, score_b, delta, label, explanation):
        divergences.append({
            "type":        dtype,
            "severity":    severity,
            "scoreA":      score_a,
            "scoreB":      score_b,
            "delta":       delta,
            "label":       label,
            "explanation": explanation,
        })

    regime_up = (regime or "NEUTRAL").upper()
    is_bull   = any(x in regime_up for x in ("BULL", "POST_PANIC"))
    is_stress = any(x in regime_up for x in ("STRESS", "BEAR"))

    ios       = ios_market or {}
    ios_score = ios.get("iosMarketScore")       # 0–100
    ios_trend = ios.get("iosMarketTrend")       # 0–35
    ios_bread = ios.get("iosMarketBreadth")     # 0–25
    ios_dec   = ios.get("iosMarketDecision", "") # "SELEKTIV — Qualitäts-Setups begünstigt" etc.

    mcl       = (breadth_osc or {}).get("mclellan")  # McClellan-Wert, kann None sein

    # ── Paar 1: Regime vs. IOS-Market-Score ──────────────────────────────────
    # Klassischer Widerspruch aus SUITE.md #11:
    # MSE zeigt STRESS, IOS zeigt Kaufsignal — oder umgekehrt.
    if ios_score is not None:
        if is_stress and ios_score >= 65:
            # Regime warnt, IOS-Score kauft — gefährliche Diskrepanz
            sev = "high" if ios_score >= 75 else "medium"
            _add(
                dtype="regime_vs_ios",
                severity=sev,
                score_a=regime_up,
                score_b=ios_score,
                delta=ios_score,
                label=f"Regime {regime_up} ↔ IOS {ios_score}/100 ({ios_dec})",
                explanation=(
                    f"Das Makro-Regime ({regime_up}) signalisiert erhöhtes Risiko, "
                    f"während der IOS-Market-Score ({ios_score}/100) gleichzeitig "
                    f"\"{ios_dec}\" anzeigt. Beide Scores sind methodisch unabhängig: "
                    f"das Regime basiert auf VIX-Termstruktur, der IOS-Score auf "
                    f"Trend/Breadth/Rotation/Risk-Subkomponenten. Die Divergenz deutet "
                    f"auf eine gespaltene Marktlage hin — selektiver Einsatz empfohlen, "
                    f"kein breites Exposure."
                ),
            )
        elif is_bull and ios_score <= 40:
            # Regime bullisch, IOS-Score schwach — Bull-Trap-Risiko
            sev = "high" if ios_score <= 30 else "medium"
            _add(
                dtype="regime_vs_ios",
                severity=sev,
                score_a=regime_up,
                score_b=ios_score,
                delta=100 - ios_score,
                label=f"Regime {regime_up} ↔ IOS {ios_score}/100 ({ios_dec})",
                explanation=(
                    f"Das Makro-Regime ({regime_up}) ist bullisch (VIX-Termstruktur "
                    f"im Contango), aber der IOS-Market-Score ({ios_score}/100) zeigt "
                    f"schwache interne Marktdynamik. Mögliche Ursache: "
                    f"Regime-Klassifikation reagiert schneller auf Makro-Normalisierung "
                    f"als die Breiten-/Rotations-Metriken des IOS. "
                    f"Strategie-Timing mit Vorsicht: Regime-Gate allein reicht nicht."
                ),
            )

    # ── Paar 2: IOS-Trend vs. IOS-Breadth ────────────────────────────────────
    # "Leadership-Rallye ohne Breite" — klassisches Warnsignal vor Trendumkehr.
    # Wenige große Titel ziehen den Index, Mehrheit der Ticker schwächelt.
    if ios_trend is not None and ios_bread is not None:
        trend_pct = ios_trend / 35   # normiert 0–1
        bread_pct = ios_bread / 25   # normiert 0–1
        gap = trend_pct - bread_pct  # positiv = Trend stärker als Breite

        if gap >= 0.35:  # mind. 35%-Punkte Differenz (normiert)
            sev = "high" if gap >= 0.55 else "medium"
            _add(
                dtype="trend_vs_breadth",
                severity=sev,
                score_a=round(ios_trend, 1),
                score_b=round(ios_bread, 1),
                delta=round(gap * 100, 1),
                label=f"IOS-Trend {ios_trend}/35 ↔ IOS-Breadth {ios_bread}/25",
                explanation=(
                    f"Der IOS-Trend-Score ({ios_trend}/35) ist deutlich stärker als "
                    f"der IOS-Breadth-Score ({ios_bread}/25) — klassisches Zeichen "
                    f"einer Leadership-Rallye ohne breite Marktpartizipation. "
                    f"Wenige Sektoren/Titel treiben den Trend, die Mehrheit des "
                    f"Marktes partizipiert nicht. Historisch erhöhtes Umkehrrisiko, "
                    f"besonders für Breakout- und Momentum-Setups."
                ),
            )
        elif gap <= -0.35:
            # Breite stark, Trend schwach — ungewöhnlich bullische Internals ohne Trend
            sev = "medium"
            _add(
                dtype="trend_vs_breadth",
                severity=sev,
                score_a=round(ios_trend, 1),
                score_b=round(ios_bread, 1),
                delta=round(abs(gap) * 100, 1),
                label=f"IOS-Breadth {ios_bread}/25 ↔ IOS-Trend {ios_trend}/35",
                explanation=(
                    f"Der IOS-Breadth-Score ({ios_bread}/25) übersteigt deutlich "
                    f"den IOS-Trend-Score ({ios_trend}/35). Breite Marktpartizipation "
                    f"ohne klaren Trend-Anker. Mögliches Frühzeichen einer "
                    f"Trendwende (Akkumulations-Phase) oder Mean-Reversion-Umfeld. "
                    f"Swing- und MR-Strategien bevorzugen, Momentum-Setups abwarten."
                ),
            )

    # ── Paar 3: Breadth-Oszillator (McClellan) vs. Regime ────────────────────
    # McClellan misst kurzfristige Advance/Decline-Dynamik (~19/39T EMA).
    # Starke Divergenz zum Regime deutet auf Regime-Lag oder Trendwende hin.
    if mcl is not None:
        if is_stress and mcl >= 40:
            # Regime warnt, McClellan zeigt Erholung — Post-Panic-Kandidat?
            sev = "high" if mcl >= 80 else "medium"
            _add(
                dtype="breadth_vs_regime",
                severity=sev,
                score_a=regime_up,
                score_b=round(mcl, 1),
                delta=round(mcl, 1),
                label=f"McClellan +{round(mcl,1)} ↔ Regime {regime_up}",
                explanation=(
                    f"Der McClellan-Breadth-Oszillator ({round(mcl,1):+.1f}) zeigt "
                    f"starke Advance-Dominanz, während das Makro-Regime ({regime_up}) "
                    f"noch Stress signalisiert. Mögliche Interpretation: "
                    f"Breadth erholt sich früher als VIX-Termstruktur normalisiert — "
                    f"klassisches POST_PANIC-Muster. Mean-Reversion-Setups prüfen, "
                    f"Regime-Upgrade beobachten."
                ),
            )
        elif is_bull and mcl <= -40:
            # Regime bullisch, McClellan zeigt breite Schwäche
            sev = "high" if mcl <= -80 else "medium"
            _add(
                dtype="breadth_vs_regime",
                severity=sev,
                score_a=regime_up,
                score_b=round(mcl, 1),
                delta=round(abs(mcl), 1),
                label=f"McClellan {round(mcl,1):.1f} ↔ Regime {regime_up}",
                explanation=(
                    f"Der McClellan-Breadth-Oszillator ({round(mcl,1):+.1f}) zeigt "
                    f"breite Marktveräußerung, während das Makro-Regime ({regime_up}) "
                    f"noch bullisch klassifiziert. VIX-Termstruktur reagiert oft "
                    f"verzögert auf interne Marktbewegungen. "
                    f"Regime-Downgrade-Risiko erhöht — Positionsgrößen reduzieren, "
                    f"Breakout-Setups pausieren."
                ),
            )

    return divergences


def calc_breadth_oscillator(results: list, tday: str, regime: str = None) -> dict:
    """UIQ Breadth-Oszillator nach McClellan-Methodik (27.07.2026, SUITE.md Backlog #12).

    Berechnet aus dem Scan-Universum (~700 Ticker) täglich Advances/Declines und
    daraus den McClellan-Oszillator (EMA19 − EMA39 der Net-Advance-Zeitreihe).
    Kein externer Datenfeed — Rohdaten stammen aus dem nächtlichen Ticker-Scan
    (process_ticker() setzt advance=True/False/None pro Ticker).

    Abgrenzung: Eigenes UIQ-Universum (~700 Titel), NICHT der offizielle NYSE-NYMO.
    Intern konsistent; für UIQ-Strategie-Logik ausreichend.

    Signallogik (bewusst einfach):
      > +50  SEHR_BULLISH — breite Marktbeteiligung, seltenes Signal
      > +10  BULLISH      — Mehrheit advances
      -10…+10 NEUTRAL
      < -10  BEARISH      — Mehrheit declines
      < -50  SEHR_BEARISH — breite Kapitulation
    """
    BREADTH_DIR = "data/breadth_history"

    # ── Schritt 1: Heutige Advance/Decline aus results ────────────────────────
    advances  = sum(1 for r in results if r.get("advance") is True)
    declines  = sum(1 for r in results if r.get("advance") is False)
    unchanged = len(results) - advances - declines
    net_ad    = advances - declines
    total     = advances + declines
    ad_ratio  = round(advances / total, 3) if total > 0 else None

    log.info(f"[BREADTH] {tday}: ▲{advances} ▼{declines} ≡{unchanged} | NetAD={net_ad:+d}")

    # ── Schritt 2: Tages-Eintrag ins Archiv schreiben ────────────────────────
    try:
        import os as _os
        _os.makedirs(BREADTH_DIR, exist_ok=True)
        today_path = _os.path.join(BREADTH_DIR, f"{tday}.json")
        with open(today_path, "w") as _f:
            json.dump({
                "date":       tday,
                "advances":   advances,
                "declines":   declines,
                "unchanged":  unchanged,
                "net_ad":     net_ad,
                "ad_ratio":   ad_ratio,
                "total":      total,
                "regimeUsed": regime or "unknown",
            }, _f)
    except Exception as _e:
        log.warning(f"[BREADTH] Archiv-Write fehlgeschlagen: {_e}")

    # ── Schritt 3: Archiv laden (chronologisch) ───────────────────────────────
    archive = []
    try:
        import glob as _glob, os as _os
        for fp in sorted(_glob.glob(_os.path.join(BREADTH_DIR, "*.json"))):
            try:
                with open(fp) as _f:
                    archive.append(json.load(_f))
            except Exception:
                continue
    except Exception:
        pass

    archive_days   = len(archive)
    net_ad_series  = [e["net_ad"] for e in archive]

    # ── Regime-Streak: konsekutive Tage mit identischem Regime ───────────────
    regime_streak = 0
    if regime and archive:
        for _entry in reversed(archive):
            if _entry.get("regimeUsed") == regime:
                regime_streak += 1
            else:
                break

    # ── Schritt 4: EMA19 und EMA39 → McClellan-Oszillator ───────────────────
    def _ema(values, period):
        if not values:
            return []
        k = 2.0 / (period + 1)
        out = [float(values[0])]
        for v in values[1:]:
            out.append(v * k + out[-1] * (1.0 - k))
        return out

    ema19_s = _ema(net_ad_series, 19)
    ema39_s = _ema(net_ad_series, 39)

    ema19      = round(ema19_s[-1], 2) if ema19_s else None
    ema39      = round(ema39_s[-1], 2) if ema39_s else None
    oscillator = round(ema19 - ema39, 2) if (ema19 is not None and ema39 is not None) else None

    if oscillator is None:        signal = "N/A"
    elif oscillator > 50:         signal = "SEHR_BULLISH"
    elif oscillator > 10:         signal = "BULLISH"
    elif oscillator > -10:        signal = "NEUTRAL"
    elif oscillator > -50:        signal = "BEARISH"
    else:                         signal = "SEHR_BEARISH"

    log.info(f"[BREADTH] McClellan={oscillator} | EMA19={ema19} EMA39={ema39} | "
             f"Signal={signal} | {archive_days}T Archiv | Streak={regime_streak}T")

    return {
        "mclellan":    oscillator,   # Primär-Key für calc_score_divergences + Frontend
        "oscillator":  oscillator,   # Alias (Rückwärtskompatibilität)
        "ema19":       ema19,
        "ema39":       ema39,
        "advances":    advances,
        "declines":    declines,
        "unchanged":   unchanged,
        "adRatio":     ad_ratio,
        "netAd":       net_ad,
        "signal":      signal,
        "archiveDays": archive_days,
        "regimeStreak": regime_streak,
    }


def _write_market_snapshot(results: list, tday: str) -> bool:
    if not results:
        log.warning("[MARKET] results[] leer — Market-Snapshot übersprungen.")
        return False

    def pick(r, *keys):
        """Erstes verfügbares Feld aus r, probiert alle Namens-Varianten."""
        for k in keys:
            if k in r and r[k] is not None:
                return r[k]
        return None

    tickers_out = []
    for r in results:
        sym = r.get("sym") or r.get("symbol") or r.get("ticker")
        price = r.get("price") or r.get("close") or r.get("lastPrice")
        if not sym or price is None:
            continue
        tickers_out.append({
            # -- Basis -----------------------------------------------------
            "symbol":             sym,
            "price":              float(price),
            "regime":             pick(r, "regime", "markovRegime", "trend"),
            "grade":              pick(r, "grade"),
            "compositeScore":     pick(r, "compositeScore", "score", "totalScore"),
            # -- Options-Strategie-Scores (v3: Kern fuer CSP/CC-Consumer) ---
            "scoreCsp":           pick(r, "scoreCsp", "score_csp"),
            "scoreCc":            pick(r, "scoreCc", "score_cc"),
            # -- Implizite Volatilitaet ------------------------------------
            # ivRank/ivPercentile bleiben vorerst None: IV-Archiv braucht
            # 30 Handelstage, Stand 26.07.2026 sind es 15. Fuellen sich ab
            # ca. Mitte August selbst. ivAtm/ivExpiry sind der Ersatz bis dahin.
            "ivAtm":              pick(r, "ivAtm", "iv_atm"),
            "ivDte":              pick(r, "ivDte", "iv_dte"),
            "ivExpiry":           pick(r, "ivExpiry", "iv_expiry"),
            "ivRank":             pick(r, "ivRank", "iv_rank"),
            "ivPercentile":       pick(r, "ivPercentile", "iv_percentile"),
            # -- Historische Volatilitaet / Range ---------------------------
            "hvp":                pick(r, "hvp", "HVP", "hist_vol_pct"),
            "hv10":               pick(r, "hv10", "hv_10"),
            "atr":                pick(r, "atr", "atr14", "ATR"),
            # -- Strike-Anker ----------------------------------------------
            # chanHigh3sd/chanLow3sd = 3-Sigma-Band des Regressionskanals;
            # liefert die statistische Bandbreite direkt (besser als ATR allein).
            "chanHigh3sd":        pick(r, "chanHigh3sd", "chan_high_3sd"),
            "chanLow3sd":         pick(r, "chanLow3sd", "chan_low_3sd"),
            "high52":             pick(r, "high52", "high_52"),
            "low52":              pick(r, "low52", "low_52"),
            "pctFromHigh52":      pick(r, "pctFromHigh52", "pct_from_high52"),
            "distToPocPct":       pick(r, "distToPocPct", "dist_to_poc_pct"),
            # -- Assignment-Naehe ------------------------------------------
            "nearestSellStopPct": pick(r, "nearestSellStopPct"),
            "nearestBuyStopPct":  pick(r, "nearestBuyStopPct"),
            "dist50":             pick(r, "dist50", "dist_50"),
            "dist200":            pick(r, "dist200", "dist_200"),
            # -- Risikoflags -----------------------------------------------
            "squeezeRisk":        pick(r, "squeezeRisk", "squeeze_risk"),
            "warnLevel":          pick(r, "warnLevel", "warn_level"),
            "overheat":           pick(r, "overheat"),
            # -- Trend / Momentum ------------------------------------------
            "ema50":              pick(r, "ema50", "EMA50"),
            "ema200":             pick(r, "ema200", "EMA200"),
            "sma150":             pick(r, "sma150", "SMA150", "sma_150"),
            "ema200SlopeUp":      pick(r, "ema200SlopeUp"),
            "rsi14":              pick(r, "rsi14", "rsi", "RSI"),
            "macdLine":           pick(r, "macdLine", "macd_line"),
            "macdSignal":         pick(r, "macdSignal", "macd_signal"),
            "macdHist":           pick(r, "macdHist", "macd_hist"),
            "bbPos":              pick(r, "bbPos", "bb_pos"),
            "zScore":             pick(r, "zScore", "z_score"),
            # -- Liquiditaet -----------------------------------------------
            "volRatio":           pick(r, "volRatio", "volumeRatio", "vol_ratio"),
            "avgVol20":           pick(r, "avgVol20", "avg_vol20"),
            # -- RS-Rank Score (IOS Konzept-Integration, August 2026) ------
            "rsScore":            pick(r, "rsScore"),      # 0-100, kombiniert SPY+IWM
            "rsScoreSpy":         pick(r, "rsScoreSpy"),   # 0-100 vs. SPY
            "rsScoreIwm":         pick(r, "rsScoreIwm"),   # 0-100 vs. IWM
            "rsNewHigh":          pick(r, "rsNewHigh"),    # bool: RS-Line auf 63T-Hoch
            "rsGrade":            pick(r, "rsGrade"),      # A+/A/B.../F
            # -- Anchored VWAP (Zeiierman-Konzept, August 2026) -----------
            "avwap":              pick(r, "avwap"),            # EWMA-VWAP ab 52W-Tief
            "avwapAnchorDate":    pick(r, "avwapAnchorDate"),  # Datum des Ankerpunkts
            "avwapAnchorPrice":   pick(r, "avwapAnchorPrice"), # Preis am Ankerpunkt (52W-Low)
            "distToAvwapPct":     pick(r, "distToAvwapPct"),   # % Abstand Kurs zu AVWAP
            "avwapAbove":         pick(r, "avwapAbove"),        # bool: Kurs über AVWAP
            "avwapSlope":         pick(r, "avwapSlope"),        # % Änderung AVWAP über 5 Bars
            # -- Order Blocks (Hybrid Detector, August 2026) ---------------
            "obBullHigh":         pick(r, "obBullHigh"),    # Oberkante bester Bullish OB
            "obBullLow":          pick(r, "obBullLow"),     # Unterkante
            "obBullDate":         pick(r, "obBullDate"),    # Datum der OB-Entstehung
            "obBullScore":        pick(r, "obBullScore"),   # qualityScore
            "obBullDistPct":      pick(r, "obBullDistPct"), # % Abstand Kurs zu OB
            "obBullMitPct":       pick(r, "obBullMitPct"),  # % Mitigation 0-100
            "obBullVolPct":       pick(r, "obBullVolPct"),  # Bull-Volumen-Anteil %
            "obBearHigh":         pick(r, "obBearHigh"),
            "obBearLow":          pick(r, "obBearLow"),
            "obBearDate":         pick(r, "obBearDate"),
            "obBearScore":        pick(r, "obBearScore"),
            "obBearDistPct":      pick(r, "obBearDistPct"),
            "obBearMitPct":       pick(r, "obBearMitPct"),
            "obBearVolPct":       pick(r, "obBearVolPct"),  # Bear-Volumen-Anteil %
            "obBullCount":        pick(r, "obBullCount"),   # Anzahl aktiver Bull-OBs
            "obBearCount":        pick(r, "obBearCount"),
            # -- TVA Indicators (August 2026) ----------------------------
            "adx":                pick(r, "adx"),              # ADX-Wert (Trend-Stärke 0-100)
            "diPlus":             pick(r, "diPlus"),           # DI+ (Aufwärtsdruck)
            "diMinus":            pick(r, "diMinus"),          # DI- (Abwärtsdruck)
            "efficiencyRatio":    pick(r, "efficiencyRatio"),  # ER 0-1 (Trend-Effizienz)
            "tvaRegime":          pick(r, "tvaRegime"),        # 8-Regime-Klassifikation
            "tvaRegimeConf":      pick(r, "tvaRegimeConf"),    # Konfidenz 0-100%
            "chopIndex":          pick(r, "chopIndex"),        # Chop 0-100 (hoch=choppy)
            "chopLabel":          pick(r, "chopLabel"),        # None/Low/Moderate/High/Extreme
            # -- TVA Sprint A (August 2026) --------------------------------
            "trendScore":         pick(r, "trendScore"),       # f_stdTrendScore −100..+100
            "confluenceScore":    pick(r, "confluenceScore"),  # f_confluenceScore 0-100 (5 Faktoren)
            # -- Earnings Calendar (August 2026) -------------------------
            "earningsDate":       pick(r, "earningsDate"),   # ISO-Datum nächste Earnings
            "earningsDTE":        pick(r, "earningsDTE"),    # Tage bis Earnings
            "earningsEPS":        pick(r, "earningsEPS"),    # EPS-Schätzung
            "earningsRevEst":     pick(r, "earningsRevEst"), # Revenue-Schätzung
            # Hinweis: kein "timestamp" pro Ticker — identisch fuer alle 700
            # und bereits im Header als "run". Spart ~35 KB pro Snapshot.
        })

    if not tickers_out:
        log.warning("[MARKET] Keine Ticker mit sym+price — Market-Snapshot übersprungen.")
        return False

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot = {
        "v":       3,          # Schema v3 (26.07.2026): Options-Feldset (CSP/CC)
        "tday":    tday,       # letzter echter Handelstag (nicht notwendig = heute)
        "run":     run_ts,     # tatsächlicher Lauf-Zeitpunkt (kann Wochenende sein)
        "count":   len(tickers_out),
        "tickers": tickers_out,
    }

    # Datumsbezogener Key: market:snapshot:YYYY-MM-DD (letzter Handelstag).
    # Doppelpunkt-Schema konsistent zu tr:snap:*/tr:eval:* (26.07.2026).
    kv_key = f"market:snapshot:{tday}"
    ok = push_to_cloudflare_kv(snapshot, key=kv_key)

    # Alias-Key: market:snapshot:latest — immer aktuellster Lauf, unabhaengig vom
    # Kalendertag. Frontend liest diesen Key zuerst → funktioniert an Wochenenden
    # und Feiertagen ohne Sonderfallbehandlung, solange der letzte Werktag-Lauf
    # erfolgreich war. Das Feld "tday" im Payload zeigt den echten Handelstag.
    if ok:
        push_to_cloudflare_kv(snapshot, key="market:snapshot:latest")
        log.info(f"[MARKET] ✅ market:snapshot:{tday} + market:snapshot:latest — "
                 f"{len(tickers_out)} Ticker, {len(tickers_out[0])-3} Felder/Ticker")
    return ok


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

    # Degradations-Check (SWOT №35, 07.08.2026): zu wenig valide Daten = yfinance-Problem
    # → Vortages-KV weiterverwenden statt Totalabbruch
    _valid_count = sum(1 for df in hist_data.values() if df is not None and len(df) >= 20)
    _total_count = len(stock_tickers)
    _valid_pct   = _valid_count / _total_count if _total_count > 0 else 0
    log.info(f"  Valide Ticker: {_valid_count}/{_total_count} ({_valid_pct:.0%})")

    if _valid_pct < 0.50:
        # Weniger als 50% valide = yfinance-Ausfall, nicht normale Datenlücken
        log.error(
            f"  ⚠️  DEGRADED MODE: Nur {_valid_pct:.0%} der Ticker valide — "            f"yfinance-Problem vermutet. Vortages-KV wird beibehalten (kein Upload)."        )
        # master['meta']['degraded'] = True wird weiter unten gesetzt
        # sodass das Frontend einen Hinweis anzeigen kann
        import sys
        sys.exit(0)   # Sauberer Exit: kein KV-Überschreiben, GHA-Run grün

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

    # ── RS-Rating Stufe 2: Perzentil-Ranking über das gesamte Scan-Universum ──────────
    # Wird genau EINMAL nach Abschluss der Ticker-Schleife berechnet.
    # Nur Ticker mit gültigem perfRsRaw nehmen am Ranking teil (>=6M-Daten).
    # rsRating 0-99 (Perzentil): 99 = stärkster Titel, 50 = Median.
    _rs_eligible = [(r, r["perfRsRaw"]) for r in results if r.get("perfRsRaw") is not None]
    if len(_rs_eligible) >= 2:
        _rs_sorted_vals = sorted(v for _, v in _rs_eligible)
        _n = len(_rs_sorted_vals)
        for r, raw in _rs_eligible:
            # bisect: Anzahl Werte strikt kleiner als raw = Rang (0-basiert)
            import bisect as _bisect
            rank = _bisect.bisect_left(_rs_sorted_vals, raw)
            r["rsRating"] = round(rank / (_n - 1) * 99) if _n > 1 else 50
        log.info(f"   [RS-Rating] {len(_rs_eligible)}/{len(results)} Ticker gerankt — "
                 f"Median-Raw: {round(_rs_sorted_vals[_n//2],2)}")
    else:
        log.warning(f"   [RS-Rating] Zu wenige Ticker mit perfRsRaw ({len(_rs_eligible)}) — übersprungen")
    # ── Ende RS-Rating Stufe 2 ────────────────────────────────────────────────────────────

    # ── RS-RANK SCORE (IOS Konzept-Integration, August 2026) ──────────────────────────────
    # Berechnung nach fetch_batch, da hist_data (SPY, IWM) jetzt verfügbar.
    # Schreibt rsScore/rsScoreSpy/rsScoreIwm/rsNewHigh/rsGrade in results[].
    log.info(f"\n📐 RS-Rank Score berechnen (SPY + IWM Benchmark)...")
    _spy_hist = hist_data.get("SPY")
    _iwm_hist = hist_data.get("IWM")
    _rs_rank_ok = 0
    _rs_rank_skip = 0
    if _spy_hist is not None and _iwm_hist is not None:
        for _r in results:
            _sym = _r.get("sym")
            _t_hist = hist_data.get(_sym)
            if _t_hist is None or _sym in ("SPY", "QQQ", "IWM", "RSP", "DIA", "VTI", "MDY", "IJR"):
                _rs_rank_skip += 1
                continue
            _rs = compute_rs_rank_score(_t_hist, _spy_hist, _iwm_hist)
            _r["rsScore"]    = _rs.get("rs_score")
            _r["rsScoreSpy"] = _rs.get("rs_score_spy")
            _r["rsScoreIwm"] = _rs.get("rs_score_iwm")
            _r["rsNewHigh"]  = _rs.get("rs_new_high")
            _r["rsGrade"]    = _rs.get("rs_grade")
            if _rs.get("rs_score") is not None:
                _rs_rank_ok += 1
            else:
                _rs_rank_skip += 1
        log.info(f"   [RS-Rank] ✅ {_rs_rank_ok} Ticker berechnet, {_rs_rank_skip} übersprungen")
    else:
        log.warning("   [RS-Rank] SPY oder IWM hist_data fehlt — RS-Rank Score übersprungen")
    # ── Ende RS-Rank Score ────────────────────────────────────────────────────────────────

    # ── EARNINGS CALENDAR (August 2026) ──────────────────────────────────────────────────────
    # Nach fetch_batch: Earnings für alle nicht-ETF/Krypto Ticker abrufen.
    # Ein yf.Ticker()-Call pro Ticker aber sequenziell — kein paralleler Overhead.
    # Batch-Size-Limit: max 200 Ticker um GHA-Timeout zu vermeiden.
    log.info(f"\n📅 Earnings Calendar abrufen (max 200 US-Aktien)...")
    _AVWAP_SKIP_SET_EARN = set(SECTOR_ETFS + CRYPTO_TICKERS)
    _earn_candidates = [
        r for r in results
        if r.get("sym") not in _AVWAP_SKIP_SET_EARN
        and not (r.get("sym") or "").endswith("-USD")
    ][:200]  # Limit auf 200 um Timeout zu vermeiden

    _earn_ok = 0
    _earn_skip = 0
    for _r in _earn_candidates:
        _sym = _r.get("sym")
        _earn = compute_earnings_calendar(_sym)
        _r["earningsDate"]   = _earn.get("earningsDate")
        _r["earningsDTE"]    = _earn.get("earningsDTE")
        _r["earningsEPS"]    = _earn.get("earningsEPS")
        _r["earningsRevEst"] = _earn.get("earningsRevEst")
        if _earn.get("earningsDate"):
            _earn_ok += 1
        else:
            _earn_skip += 1
    log.info(f"   [Earnings] ✅ {_earn_ok} Dates gefunden, {_earn_skip} ohne Datum")
    # ── Ende Earnings Calendar ────────────────────────────────────────────────────────────────

    # ── DISTRIBUTION DAYS (IOS Konzept-Integration, August 2026) ─────────────────────────
    # O'Neil/IBD: Index fällt >0.2% bei höherem Vol = institutionelles Verkaufen.
    # 4–5 DD in 25 Tagen = Watch, ≥6 DD = Danger.
    log.info(f"\n📊 Distribution Days berechnen (SPY + QQQ, 25T Lookback)...")
    _qqq_hist = hist_data.get("QQQ")
    if _spy_hist is not None and _qqq_hist is not None:
        distribution_days = compute_distribution_days(_spy_hist, _qqq_hist, lookback=25)
        log.info(f"   [DD] SPY: {distribution_days['dd_spy']} | QQQ: {distribution_days['dd_qqq']} "
                 f"| Severity: {distribution_days['dd_severity']} | Score: {distribution_days['dd_score']}")
        if distribution_days["dd_alert"]:
            log.warning(f"   [DD] ⚠️  DISTRIBUTION SIGNAL — {distribution_days['dd_severity'].upper()}: "
                        f"≥4 DD in 25 Tagen erkannt!")
    else:
        distribution_days = {"dd_spy": None, "dd_qqq": None, "dd_score": None,
                             "dd_alert": False, "dd_severity": "None"}
        log.warning("   [DD] SPY oder QQQ hist_data fehlt — Distribution Days übersprungen")
    # ── Ende Distribution Days ────────────────────────────────────────────────────────────

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

    # ── FINRA DIX (echt, statt SqueezeMetrics/Heuristik) ─────────────────────
    # v5.34: CSV-Methode (Stufe 2) hat Vorrang — kein OAuth2, volle SP500-Breite
    log.info(f"  FINRA DIX CSV (Reg SHO Direct Download, v5.34)...")
    try:
        # Universum: alle Stock-Ticker aus build_ticker_universe()
        _sp500_set = [t for t in tickers if not t.endswith("-USD")]
        finra_dix = fetch_finra_dix_csv(_sp500_set)
    except Exception as _e:
        log.warning(f"  FINRA DIX CSV fehlgeschlagen: {_e} — Fallback auf OAuth2")
        finra_dix = {"ok": False, "reason": str(_e)[:200]}

    # Fallback: OAuth2-Version wenn CSV scheitert
    if not finra_dix.get("ok"):
        log.info(f"  FINRA DIX OAuth2-Fallback...")
        try:
            finra_dix = fetch_finra_dix()
        except Exception as _e:
            log.warning(f"  FINRA DIX OAuth2 fehlgeschlagen: {_e}")
            finra_dix = {"ok": False, "reason": str(_e)[:200]}

    if finra_dix.get("ok"):
        # Nicht mehr ueberschreiben: dix_gex["dix"] bleibt der squeezemetrics-
        # Wert (klassische S&P-500-Methodik, seit 14.08.2026 zuverlaessig). Der
        # FINRA-ETF-Korb-Wert (strukturell hoeher, andere Basis) wird separat
        # unter dixEtfBasket* gefuehrt statt "dix" zu ersetzen.
        # ACHTUNG (14.08.2026): Frontend (axel-scanner/index.html, 8 Stellen)
        # prueft noch auf dixSource==='finra_regshodaily' fuer die alte ETF-
        # Korb-Anzeige — Frontend-Anpassung bewusst als eigener Punkt fuer
        # naechste Session zurueckgestellt, s. Uebergabeprotokoll.
        dix_gex["dixEtfBasket"]            = finra_dix["dix"]
        dix_gex["dixEtfBasketSource"]      = finra_dix.get("source", "finra_regsho_csv")
        dix_gex["dixEtfBasketMethodology"] = finra_dix.get("methodology")
        dix_gex["dixEtfBasketPerTicker"]   = finra_dix.get("perTicker")
        dix_gex["dixEtfBasketSize"]        = finra_dix.get("basketSize", 0)
        dix_gex["dixEtfBasketDate"]        = finra_dix.get("date")
        if dix_gex.get("dix") is None:
            dix_gex["dix"] = finra_dix["dix"]
            dix_gex["dixSource"] = finra_dix.get("source", "finra_regsho_csv") + "_fallback"
    else:
        dix_gex["dixEtfBasketUnavailableReason"] = finra_dix.get("reason")
        if "sample_keys" in finra_dix:
            dix_gex["dixEtfBasketDebugSampleKeys"] = finra_dix["sample_keys"]
        if "n_rows" in finra_dix:
            dix_gex["dixEtfBasketDebugNRows"] = finra_dix["n_rows"]
        if "raw_sample" in finra_dix:
            dix_gex["dixEtfBasketDebugRawSample"] = finra_dix["raw_sample"]

    # BUGFIX (16.07.2026, Axel-Anfrage): "ETF-Modul-Lösung" statt Einzelfall —
    # vorher nur XLK als Proof-of-Concept. Liste identisch zur bereits
    # bestehenden Sektor-Überhitzung-Liste in axel-scanner (index.html
    # ~Zeile 15607), damit ALLE dort klickbaren Sektor-ETFs auch hier Holdings
    # bekommen. build_sector_holdings() war schon immer generisch parametrisiert
    # (etf_ticker, xlsx_path) — nur der Aufruf war XLK-only. Jetzt Config-Liste
    # + Schleife. Pro ETF: erst automatischer Download-Versuch von der
    # oeffentlichen SSGA-URL (Standardmuster fuer alle SPDR-Sektor-ETFs),
    # bei Fehlschlag Fallback auf lokal abgelegte Datei (wie bisher bei XLK) —
    # SO bleibt die bisherige manuelle Vorgehensweise als Sicherheitsnetz
    # bestehen, falls der automatische Download aus irgendeinem Grund (Bot-
    # Schutz, URL-Aenderung bei SSGA) nicht funktioniert.
    SECTOR_ETF_LIST = ["XLK", "XLY", "XLF", "XLE", "XLV", "XLI", "XLU", "XLP", "XLC", "XLB"]
    log.info(f"  Sektor-Holdings ({len(SECTOR_ETF_LIST)} ETFs, automatischer Download + lokaler Fallback)...")
    sector_holdings = {}
    for _etf in SECTOR_ETF_LIST:
        try:
            import os as _os
            _local_path = f"data/holdings_{_etf}.xlsx"
            _xlsx_path = None

            # Ausschliesslich lokale EMEA-UCITS-Dateien (data/holdings_{ETF}.xlsx).
            # US-SSGA-Download deaktiviert (19.07.2026): GHA kann ssga.com erreichen,
            # aber US-Format (CUSIP/SEDOL statt Security Name in Spalte 2) ist
            # inkompatibel mit parse_ssga_holdings_xlsx() — Parser ist auf EMEA-
            # UCITS-Format kalibriert (alle 10 ETFs, 149/150 Holdings korrekt gematchet).
            # Manuelle Aktualisierung: monatlich analog IWV-Holdings-Update.
            if _os.path.exists(_local_path):
                _xlsx_path = _local_path
                log.info(f"    {_etf}: lokale EMEA-Datei geladen ({_local_path})")

            if not _xlsx_path:
                log.warning(f"    {_etf}: weder automatischer Download noch lokale Datei verfuegbar — uebersprungen")
                continue

            _etf_holdings = build_sector_holdings(_etf, _xlsx_path, top_n=15)
            if _etf_holdings.get("ok"):
                sector_holdings[_etf] = _etf_holdings
                log.info(f"    {_etf}: {_etf_holdings['resolvedCount']}/{_etf_holdings['totalCount']} Ticker aufgelöst")
            else:
                log.warning(f"    {_etf}: Holdings-Aufbau fehlgeschlagen ({_etf_holdings.get('reason')})")
        except Exception as _etf_err:
            log.warning(f"    {_etf}: unerwarteter Fehler ({str(_etf_err)[:150]})")

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
        # KONVENTION: ratio_3m_spot = VIX3M/VIX (>1 = Contango). Primär aus
        # explizitem Feld; Fallback berechnet für ältere KV-Snapshots ohne das Feld.
        _regime_ratio = vix_term.get('ratio_3m_spot') or round(vix_term['vix3m'] / vix_term['vix'], 3)
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
    log.info(f'  Markt-Regime: {market_regime_str} | Ratio: {_regime_ratio} (v5.12: vor Options-Loop verschoben fuer score_options_collar)')

    # Regime-History-Flag (Backlog №29, v5.29.0): Übergangsvektor aus mse_history
    # Brücke bis MCM-HMM ab ~01.10.2026 (ML_KONZEPT.md §3b)
    regime_context = calc_regime_history_flag(mse_history, market_regime_str)

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
        s_collar = score_options_collar(r, market_regime=market_regime_str)

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
            "scoreCollar": s_collar,
            # NEU (30.06.2026): Fibo-Setup/Score mit ausgeben — macht den in
            # score_options_csp()/score_options_covered_call() eingerechneten
            # Fibo-Boost im Output nachvollziehbar (vorher nur intern verwendet,
            # nicht sichtbar -> Boost-Wirkung liess sich nicht isoliert pruefen).
            "fSetup":      r.get("f_setup"),
            "fScore":      r.get("f_score"),
            # Bester Score fuer Sortierung
            "optsScore":   max(s_csp, s_cc, s_spread, s_collar),
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


    # Fix A: rs_sorted wird nur innerhalb von `if spy_data is not None` befüllt
    # → außerhalb des Blocks nur loggen wenn vorhanden (verhindert NameError/UnboundLocalError)
    if rs_sorted:
        log.info(f"  Schwächste (RS5):     {[r['sym'] for r in rs_sorted[-3:]]}")
    else:
        log.info("  Schwächste (RS5):     — (SPY-Daten fehlen, Sektor-RS übersprungen)")

    # 5c. Konjunktur-Ratio-Signale (17.08.2026, Axel-Anfrage) ─────────────────
    # Beide Ticker-Paare sind bereits im Universum, keine neuen API-Calls.
    log.info(f"\n📊 Konjunktur-Ratio-Signale (Staples/Discretionary, Growth/Value)...")
    staples_discretionary = calc_ratio_signal(hist_data, "XLP", "XLY", "Consumer Staples vs. Discretionary")
    growth_value          = calc_ratio_signal(hist_data, "IWF", "IWD", "Growth vs. Value")
    if staples_discretionary.get("ok"):
        log.info(f"  Staples/Discretionary: {staples_discretionary['ratio']} "
                 f"(5T {staples_discretionary['chg5d']}% / 20T {staples_discretionary['chg20d']}%) — {staples_discretionary['trend']}")
    else:
        log.warning(f"  Staples/Discretionary übersprungen: {staples_discretionary.get('reason')}")
    if growth_value.get("ok"):
        log.info(f"  Growth/Value: {growth_value['ratio']} "
                 f"(5T {growth_value['chg5d']}% / 20T {growth_value['chg20d']}%) — {growth_value['trend']}")
    else:
        log.warning(f"  Growth/Value übersprungen: {growth_value.get('reason')}")

    # 5d. Swing-Trading Kandidaten
    swing_candidates = sorted(
        [r for r in valid
         if r.get("score", 0) >= 45
         and r.get("bullSignals", 0) >= 1
         and r.get("rsi") is not None and r["rsi"] < 60
         and r.get("macdHist") is not None],
        key=lambda x: x.get("score", 0), reverse=True
    )[:20]

    # 5e. Datenfreshe validieren
    log.info(f"\n🗓️  Validiere Datenfreshe...")
    last_trading_day = validate_data_freshness(results)
    log.info(f"  Referenz-Handelstag: {last_trading_day}")

    # ── Breadth-Oszillator (McClellan, SUITE.md Backlog #12, 27.07.2026) ──────
    log.info(f"\n📊 Breadth-Oszillator (McClellan)...")
    # MCM-Regime (bereits berechnet) für Breadth-Archiv verwenden — NICHT Ticker-Markov
    # Fix 28.07.2026: _dominant_regime war Ticker-Markov ("bull"/"side"/"bear"),
    # market_regime_str ist das korrekte globale MCM-Regime ("BULL_QUIET" etc.)
    breadth_osc = calc_breadth_oscillator(results, last_trading_day, regime=market_regime_str)

    # ── Score-Paar-Divergenz-Signal (SUITE.md Backlog #11, 28.07.2026) ────────
    # Methodisch unabhängige Sub-Scores werden auf Widersprüche geprüft.
    # Ergebnis: master.market.scoreDivergences[] — für MCM-Panel + Morning Briefing.
    score_divergences = calc_score_divergences(
        market_regime_str, ios_market, breadth_osc
    )
    log.info(f"  [DIVERGENCE] {len(score_divergences)} Divergenz(en) erkannt: "
             f"{[d['type'] for d in score_divergences] or 'keine'}")

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
                    "long_dividend":    "Dividend Income Score 0-100: divYield 2-6%, payoutRatio <75%, FCF-gedeckt, Qualitaetsfilter (ROE, D/E)",
                    "long_value":       "Value Score 0-100: peForward <20, pb <3, fcfYield >3%, ROE >10%, Analyst-Upside als Catalyst",
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
            "mseHistory":    mse_history,
            "regimeContext": regime_context,  # Backlog №29: Übergangsvektor RECOVERING/DETERIORATING/STABLE
            "iosMarket":  ios_market,
            "fearGreed":  fear_greed,
            "snapshot":   market_snapshot,   # Single Source of Truth: alle Live-Preise
            "zscores":    macro_zscores,     # Z-Scores + Perzentile (252T) für Deep-Reasoning
            "fredMacro":  fred_macro,        # HY-Spread + Net Liquidity + Konjunktur-Indikatoren (FRED, 17.08.2026 erweitert)
            "moveIndex":  move_index,        # Treasury-Volatilität (Renten-VIX)
            "stapleDiscretionary": staples_discretionary,  # Konjunktur-Indikator (17.08.2026, Axel-Anfrage)
            "growthValue":         growth_value,           # Konjunktur-Indikator (17.08.2026, Axel-Anfrage)
            "sectorHoldings": sector_holdings, # ETF-Holdings-Klickthrough (Proof-of-Concept, nur XLK, 11.07.2026)
            "breadthOsc":        breadth_osc,        # McClellan Breadth-Oszillator (27.07.2026, Backlog #12)
            "scoreDivergences":  score_divergences,  # Score-Paar-Divergenzen (28.07.2026, Backlog #11)
            "distributionDays":  distribution_days,  # O'Neil/IBD Distribution Days (IOS, August 2026)
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
        # NEU (15.07.2026, Phase 0.5 Arbeitspaket F Punkt 2): Options-Watchlist
        # analog zur Master-Shortlist mit KI-Setup-Parametern anreichern.
        log.info(f"\n🤖 KI-Enrichment Options-Watchlist ({len(options_watchlist)} Kandidaten)...")
        options_watchlist = asyncio.run(
            enrich_options_watchlist_with_ai(options_watchlist, enrich_context, api_key=_ant_key)
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

    # ── Dividend + Value Leaderboards nach Enrichment neu berechnen (#13b) ───
    # build_leaderboards() lief vor Enrichment — Fundamental-Felder waren noch None.
    # Jetzt sind divYield/peForward/etc. in results[] → Scorer neu aufrufen.
    _DIV_VAL_FIELDS = ["divYield", "payoutRatio", "peForward", "pb", "roe",
                       "fcfYield", "analystUpside", "debtToEquity"]
    _enriched_syms  = set(_fund_cache.keys()) if _fund_candidates else set()

    def _rebuild_fundamental_lb(score_fn, key, min_score, extra_fields):
        """Mini-Leaderboard aus results[] nach Enrichment."""
        _entries = []
        for _r in results:
            if _r.get("error") or not _r.get("price"):
                continue
            _s = score_fn(_r)
            if _s < min_score:
                continue
            _entry = {
                "sym":   _r.get("sym"),
                "score": _r.get("score"),
                "price": _r.get("price"),
                "grade": _r.get("grade"),
                "rsi":   _r.get("rsi"),
                key:     _s,
            }
            for _f in (extra_fields or []):
                _entry[_f] = _r.get(_f)
            _entries.append(_entry)
        return sorted(_entries, key=lambda x: x[key], reverse=True)[:20]

    leaderboards_obj["long_dividend"] = _rebuild_fundamental_lb(
        score_long_dividend, "sDividend", 35,
        ["divYield", "payoutRatio", "fcfYield", "roe", "debtToEquity"]
    )
    leaderboards_obj["long_value"] = _rebuild_fundamental_lb(
        score_long_value, "sValue", 35,
        ["peForward", "pb", "fcfYield", "roe", "analystUpside"]
    )
    log.info(f"  [#13b] long_dividend: {len(leaderboards_obj['long_dividend'])} | "
             f"long_value: {len(leaderboards_obj['long_value'])} Kandidaten "
             f"(aus {len(_enriched_syms)} angereicherten Titeln)")

    # Leaderboards + Shortlist in master dict einfuegen
    master["leaderboards"]     = leaderboards_obj
    master["masterShortlist"]  = master_shortlist
    master["optionsWatchlist"] = options_watchlist   # Top-50 Options-Kandidaten (täglich)
    master["strategyMeta"]     = {
        "regimeUsed":  strategy_data["regimeUsed"],
        "timestamp":   strategy_data["timestamp"],
        "enriched":    bool(_ant_key),
    }
    # BUGFIX (14.07.2026): regimeUsed lag bisher NUR in strategyMeta, generate_daily_snapshot()
    # sucht aber in meta["regimeUsed"] (existierte dort nie -> immer "-" -> immer "n/v" im Briefing).
    master["meta"]["regimeUsed"] = strategy_data["regimeUsed"]

    # W3-Transparenz (SWOT W3, 07.08.2026): Beide Klassifikatoren explizit dokumentieren.
    # Server-Regime (VIX3M/VIX-Ratio, täglich per GHA) ist der Track-Record-Wert.
    # Client-Regime (VVIX/SKEW/GEX live) kann davon abweichen — das ist by design,
    # nicht ein Bug. Nutzer sieht Client-Regime; Track-Record loggt Server-Regime.
    # regimeMeta macht die Herkunft transparent für Validierung + Debugging.
    master["meta"]["regimeMeta"] = {
        "serverRegime":  market_regime_str,         # VIX3M/VIX-Ratio-basiert (dieser Lauf)
        "serverRatio":   _regime_ratio,              # ratio_3m_spot zum Klassifikationszeitpunkt
        "clientRegime":  "client_mse_live",          # Placeholder: Client klassifiziert live via VVIX/SKEW
        "divergenceNote": (
            "Server: VIX3M/VIX-Ratio-Schwellen (0.98/1.05). "
            "Client: VVIX-Z-Score + SKEW-Percentile + GEX/DIX (live Yahoo). "
            "Divergenz ist by design — beide Klassifikatoren messen verschiedene Dimensionen. "
            "Track-Record verwendet immer serverRegime."
        ),
        "method": "rule_based_v1",  # ab HMM: hmm_v1
    }

    # ── DECISION CONFIDENCE ENGINE (DCE v1.0, August 2026) ───────────────────
    # Meta-Instanz über allen Signalquellen: fusioniert MCM-Makro, Ticker-Konsens,
    # CUSUM und EVT-VaR zu einem kalibrierten Vertrauensmaß (0-100) + Ampel.
    # Fehlerisoliert: kein Absturz des Hauptlaufs möglich.
    log.info(f"\n🎯 Decision Confidence Engine (DCE v1.0)...")
    try:
        from dce_layer import run_dce

        # SPY-Returns für EVT-VaR (letzte 60 Handelstage, Dezimalwerte)
        _spy_returns_60d = []
        _spy_df = hist_data.get("SPY")
        if _spy_df is not None:
            _spy_closes = list(_spy_df["Close"].dropna())
            if len(_spy_closes) > 1:
                _spy_returns_60d = [
                    (_spy_closes[i] / _spy_closes[i-1] - 1)
                    for i in range(1, len(_spy_closes))
                ][-60:]

        # CUSUM-Buffer aus vorherigem Run (Persistenz via master["meta"])
        _cusum_buffer = []
        try:
            _cusum_raw = master.get("meta", {}).get("dce_cusum_buffer", [])
            if isinstance(_cusum_raw, list):
                _cusum_buffer = [float(v) for v in _cusum_raw]
        except Exception:
            pass

        dce_result = run_dce(
            market_data={
                "regime":          market_regime_str,
                "regimeUsed":      market_regime_str,
                "vix_term":        vix_term or {},
                "spy_returns_60d": _spy_returns_60d,
                "snapshot":        market_snapshot or {},
            },
            ticker_results=results,
            cusum_buffer=_cusum_buffer,
        )

        master["dce"] = dce_result
        master["meta"]["dce_cusum_buffer"] = dce_result.get("cusum_buffer", [])

        log.info(f"   ✅ DCE: Confidence={dce_result['confidence']}/100 | "
                 f"Mode={dce_result['mode']} | "
                 f"Richtung={dce_result['direction']}")
        for w in dce_result.get("warnings", []):
            log.warning(f"   {w}")

    except Exception as _dce_err:
        log.warning(f"   DCE übersprungen (nicht kritisch): {_dce_err}")
        master["dce"] = {
            "confidence": 50, "mode": "YELLOW",
            "position_size": 0.5, "direction": "HOLD",
            "regime": market_regime_str,
            "warnings": [f"DCE-Fehler: {str(_dce_err)}"],
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
            regime_context=regime_context,           # v5.30.0: Validierung Ebene 1 (Backlog №29)
            regime_meta=master["meta"].get("regimeMeta"),  # v5.31.0: W3-Transparenz
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

    # ── IV-ARCHIV (v5.1, Options-Modul Phase 0 — SUITE.md #15) ─────────────────
    # ATM-IV täglich archivieren → IV-Rank/Percentile sobald ≥30 Tage vorhanden.
    # Fehlerisoliert wie fin_layer — bricht den Hauptlauf niemals.
    try:
        import iv_layer
        iv_status = iv_layer.run(results=results)
        master["ivArchive"] = iv_status
        log.info(f"  [IV] ivArchive: {iv_status.get('fetched')} Ticker fetched, "
                 f"{iv_status.get('ranked')} gerankt, "
                 f"{iv_status.get('archiveDays')} Archiv-Tage")
    except Exception as _ive:
        log.warning(f"  [IV] IV-Archiv übersprungen (nicht kritisch): {_ive}")
        master["ivArchive"] = {"ok": False, "reason": f"exception: {_ive}"}

    # ── VAL-MOD VALUE-SCANNER (v5.2, Carlin/Graham 3-Stufen-Sieve — SUITE.md VAL-MOD) ───
    # Liest FIN-Archiv + Aggregator-results → Value-Shortlist Top-50 + Wheel-Kandidaten.
    # Muss VOR lokalem Backup + KV-Push stehen (sonst fehlt valueScanner im Artifact).
    # ── REG_VP LAYER (Sprint B, 12.07.2026) ─────────────────────────────────────
    try:
        import reg_vp_layer
        rvp_status = reg_vp_layer.run(results=results)
        log.info(f"  [REG_VP] {rvp_status.get('enriched')} Ticker enrichiert")
    except Exception as _rvpe:
        log.warning(f"  [REG_VP] übersprungen: {_rvpe}")
        # Felder auf None setzen damit KV-Schema konsistent bleibt
        for _r in results:
            for _k in ["zScore","pocLevel","distToPocPct","regTrend",
                       "regBaseline","chanHigh3sd","chanLow3sd"]:
                _r.setdefault(_k, None)

    # ── CLUSTER_VP LAYER (Sprint B, 12.07.2026) ──────────────────────────────
    try:
        import cluster_layer
        cl_status = cluster_layer.run(results=results)
        log.info(f"  [CLUSTER_VP] {cl_status.get('enriched')} Ticker enrichiert")
    except Exception as _cle:
        log.warning(f"  [CLUSTER_VP] übersprungen: {_cle}")
        for _r in results:
            for _k in ["nearestClusterPocDist","dominantClusterVol",
                       "clusterDelta","priceAboveDominant","nearestClusterPoc"]:
                _r.setdefault(_k, None)

    try:
        import val_layer
        val_status = val_layer.run(results=results)
        master["valueScanner"] = {
            "ok":         val_status.get("ok"),
            "version":    val_status.get("version"),
            "finWeek":    val_status.get("finWeek"),
            "universe":   val_status.get("universe"),
            "stufe1Pass": val_status.get("stufe1Pass"),
            "scored":     val_status.get("scored"),
            "wheelCount": val_status.get("wheelCount"),
            "shortlist":  val_status.get("shortlist", []),
            "promote":    val_status.get("promote", {}),
        }
        log.info(f"  [VAL] Value-Scanner: {val_status.get('stufe1Pass')} S1-Pass, "
                 f"Top-50 Shortlist, {val_status.get('wheelCount')} Wheel-Kandidaten")
    except Exception as _ve:
        log.warning(f"  [VAL] Value-Scanner übersprungen (nicht kritisch): {_ve}")
        master["valueScanner"] = {"ok": False, "reason": f"exception: {_ve}", "shortlist": []}

    payload_size = len(json.dumps(master)) / 1024
    log.info(f"\n📊 Master-JSON: {payload_size:.0f} KB | {len(results)} Ticker")
    log.info(f"   Top40 Long: {len(top40_long)} | Mean Reversion: {len(mean_reversion)}")

    # 7. Lokales Backup
    with open("master_market_data.json", "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, separators=(",", ":"))
    log.info(f"   💾 Lokal gespeichert: master_market_data.json")

    # 7b. Rolling-Window-Archiv: master_market_data gzip'd ins data/snapshots/ Verzeichnis
    # (v5.16.0, 22.07.2026): 90-Tage-Rolling-Window für Cross-Repo-Nutzung.
    # Namensschema: data/snapshots/YYYY-MM-DD_HH.json.gz (Lauf-Stunde für 2 Runs/Tag)
    # Rotation: Dateien älter als 90 Tage werden automatisch gelöscht.
    # FIN-Archiv: tr_backup.py übernimmt historische Sicherung via KV-Export.
    try:
        import gzip, glob
        from datetime import datetime as _dt_snap, timezone as _tz_snap
        _snap_dir = "data/snapshots"
        os.makedirs(_snap_dir, exist_ok=True)
        _now_utc = _dt_snap.now(_tz_snap.utc)
        _snap_name = f"{_snap_dir}/{_now_utc.strftime('%Y-%m-%d_%H')}.json.gz"
        _snap_bytes = json.dumps(master, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with gzip.open(_snap_name, "wb", compresslevel=6) as gz:
            gz.write(_snap_bytes)
        _snap_kb = len(_snap_bytes) / 1024
        _snap_gz_kb = os.path.getsize(_snap_name) / 1024
        log.info(f"   📦 Snapshot: {_snap_name} ({_snap_kb:.0f} KB → {_snap_gz_kb:.0f} KB gz)")
        # Rotation: Dateien älter als 90 Tage löschen
        _cutoff = _now_utc.timestamp() - 90 * 86400
        _deleted = 0
        for _old in glob.glob(f"{_snap_dir}/*.json.gz"):
            if os.path.getmtime(_old) < _cutoff:
                os.remove(_old)
                _deleted += 1
        if _deleted:
            log.info(f"   🗑️  {_deleted} Snapshots älter als 90 Tage gelöscht")
    except Exception as _e:
        log.warning(f"   ⚠️ Snapshot-Archivierung fehlgeschlagen: {_e}")

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
    # 10. Market Snapshot — alle Indikatoren für externe Konsumenten
    log.info(f"\n[MARKET] Market-Snapshot schreiben...")
    try:
        _ms_tday = master["meta"].get("last_trading_day") or \
                   datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log.info(f"[MARKET] tday={_ms_tday}, results={len(results)} Ticker")

        _ms_ok = _write_market_snapshot(results, _ms_tday)
        log.info(f"[MARKET] _write_market_snapshot returned: {_ms_ok}")
    except Exception as _me:
        import traceback
        log.warning(f"[MARKET] fehlerisoliert übersprungen: {_me}")
        log.warning(f"[MARKET] Traceback: {traceback.format_exc()}")
    # 9. Daily Market Snapshot - serverseitiges Briefing fuer Beta-Tester
    log.info(f"\n[SNAPSHOT] Daily Market Snapshot generieren...")
    try:
        import datetime as _dt
        # MCM-Parität (v5.13.0): hist_data für build_server_market_context() verfügbar machen.
        # Analog zum regimeUsed-Patch: wird in master injiziert, damit generate_daily_snapshot()
        # keine Signatur-Änderung braucht. Schlüssel mit "_" Prefix = interne Nutzung, nicht im KV.
        master["_hist_data"] = hist_data
        _snap_result = generate_daily_snapshot(master)
        # Lauf-Zeitpunkt bestimmen: vor 12:00 UTC = Morgen-Lauf, danach = NYSE-Lauf
        _lauf_hour = _dt.datetime.utcnow().hour
        _snap_key = "daily_market_snapshot" if _lauf_hour < 12 else "daily_market_snapshot_us"
        push_to_cloudflare_kv(_snap_result, key=_snap_key)
        # Morgen-Lauf: immer auch daily_market_snapshot schreiben (Basis-Key)
        if _lauf_hour >= 12:
            push_to_cloudflare_kv(_snap_result, key="daily_market_snapshot")
        _snap_ok = _snap_result.get("ok")
        _snap_status = "OK" if _snap_ok else _snap_result.get("reason", "?")
        log.info(f"   [SNAPSHOT] {_snap_status} - {_snap_key} aktualisiert (Lauf-Stunde UTC: {_lauf_hour})")
        master["dailySnapshot"] = {"ok": _snap_ok, "reason": _snap_result.get("reason"), "key": _snap_key}
    except Exception as _se:
        log.warning(f"  [SNAPSHOT] fehlerisoliert uebersprungen: {_se}")
        master["dailySnapshot"] = {"ok": False, "reason": f"exception: {_se}"}

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
