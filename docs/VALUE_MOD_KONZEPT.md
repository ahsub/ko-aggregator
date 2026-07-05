# UIQ Value-Modul (VAL-MOD) — Konzeptspezifikation v4
**Status: GEPARKT bis Roadmap-Freigabe (STRATEGIE.md: nach UIQ Phase 1 + Options-Erweiterung) | Archiviert: 05.07.2026 | Autor: Dr. Axel Hildebrand (Konzept) + Claude (Review)**

> **Vorgeschaltete Umsetzung (05.07.2026): FIN-Archiv.** Da Fundamentaldaten — anders als Kurse — nicht rückwirkend beschaffbar sind, sammelt `fin_layer.py` ab sofort wöchentlich Point-in-Time-Rohdaten über Russell 3000 (IWV) ∪ Smart-Picks (`data/value_smart_picks.txt`) ∪ UIQ-Universum nach `data/fundamentals/` (Git-History = Archiv, inkl. Konstituentenliste → survivorship-frei ab Tag 1). Jedes künftige VAL-MOD-Bewertungsmodell wird gegen dieses Archiv geprüft.

## Claude-Review (05.07.2026) — verbindliche Anpassungen für die Umsetzung

1. **§4 C++-Spezifikation ist als Datenmodell zu lesen, nicht als Implementierung.** UIQ-Stack ist Python (Aggregator) + ES6 (Frontend) + CF Workers; `FinancialData v4` wird JSON-Schema im KV/Archiv + Python-Dataclass. Der Feldsatz ist im FIN-Archiv bereits umgesetzt (`INFO_FIELDS`).
2. **Layer 2 (ROIC, 3J-Wachstum, 5J-ROE-Konstanz)** braucht yfinance Financial Statements statt `.info` — API-lastigster Teil, korrekt im Wochenend-Lauf verortet. ROIC in FIN-Archiv v1 noch nicht enthalten (Statements-Erweiterung bei VAL-MOD-Bau).
3. **Track-Record-Anbindung ab Tag 1:** VAL-MOD-Empfehlungen loggen als eigene Strategiefamilien (`value_buy` / `value_csp`) in den bestehenden tr_layer — der ist generisch genug; Wheel-Synergie-Router-Entscheide werden damit messbar.
4. **Design-Entscheidung dokumentiert:** Der Layer-1-Filter „>15 % über 52W-Tief" biegt das Modul bewusst Richtung Momentum-Value (Anti-fallendes-Messer) und schließt Graham-Bodenfischerei aus. Gewollt, aber bei Modellprüfung als Hypothese behandeln (FIN-Archiv erlaubt den A/B-Vergleich).
5. **Ablösung:** Dieses Konzept ersetzt das ältere ValueMatrix-Screener-Konzept vollständig.
6. **Stärkste Idee = Phase 4 (Wheel-Synergie-Router):** Value-Kandidat + IV-Prüfung → Direktkauf vs. CSP. Verlängert die UIQ-Router-Kette um ein Instrumenten-Glied und verschmilzt Value mit der Kernkompetenz statt ein Silo zu bauen.
7. **Sharding (Layer 1 / Wochentags-Fraktionierung)** ist durch das FIN-Archiv bereits produktiv implementiert und getestet — VAL-MOD erbt die Infrastruktur fertig.

---

**Konzeptspezifikation: UIQ Value-Scanner Modul (VAL-MOD) - V4**

*Pareto-Optimierte 3-Layer-Sieve-Architektur mit integriertem
Wheel-Synergie-Protokoll*

**1. Executive Summary & Zielsetzung**

Das Modul VAL-MOD erweitert die Trading-Suite UnderlyingIQ (UIQ) um eine
fundamentale, langfristig orientierte Screening-Komponente. Die Version
4 implementiert eine rigorose Pareto-Optimierung (80/20-Regel). Das Ziel
besteht darin, mit minimalem Entwicklungsaufwand und ohne zusätzliche
API-Kosten für volatile Drittanbieter-Metriken (wie SEC 13F-Filings oder
Social Media Sentiment Tracker) maximale Alpha-Generierung und
Systemstabilität zu erreichen. Durch die Entkopplung in ein dreistufiges
Sieb-Verfahren (Sieve Architecture) und die logische Verschmelzung mit
dem bestehenden Optionen-Modul (Wheel-Strategie) entsteht ein
hocheffizientes, resilienteres Gesamtsystem.

**2. Begründung der Strategieanpassung (80/20 Pareto-Review)**

Im Zuge eines pragmatischen Software-Reviews wurden die theoretischen
Ansätze aus Version 3 gezielt auf ihre architektonische
Wirtschaftlichkeit hin korrigiert. Drei wesentliche Design-Flaws wurden
eliminiert:

-   **Eliminierung des KGV-Grobfilters in Layer 1:** Ein strikter
    KGV-Filter (\<40) unter der Woche hätte die profitabelsten
    Peter-Lynch-Unternehmen (\'Fast Growers\' in ihrer hyperdynamischen
    Phase wie Nvidia, Tesla, Celsius Holdings) sowie klassische
    Graham-Turnarounds mit temporär negativen Gewinnen fälschlicherweise
    eliminiert. Ersetzt durch die ökonomisch stärkere Bruttomarge.

-   **Ersetzung nacheilender & volatiler API-Daten in Layer 3:** Das
    Parsen von US-SEC-13F-Filings ist datentechnisch komplex und hinkt
    dem Markt bis zu 45-135 Tage hinterher. Social-Media-Meme-Buzz
    verpufft zudem in Tagen und ist für einen monatlichen Batch-Lauf
    ungeeignet. Große Marktteilnehmer und Kleinanleger hinterlassen ihre
    Spuren ohnehin direkt im Chart. Daher nutzt das System nun das
    Relative Volumen (RVOL) und die Relative Stärke (RS nach Levy) --
    Daten, die ohnehin kostenlos im Standard-Kurs-Feed enthalten sind.

-   **Verschmelzung mit der Kern-Engine (Wheel-Synergie):** Anstatt ein
    isoliertes Value-Depot aufzubauen, prüft das System nun bei
    qualifizierten Aktien die implizite Volatilität, um den Einstieg
    systematisch über hochrentable Cash-Secured Puts (CSPs) abzuwickeln.
    Damit schlagen wir die Brücke zur derivaten Kernkompetenz von UIQ.

**3. Das optimierte 3-Layer-Sieve-Verfahren**

**3.1 Sieve Layer 1: Wochentags-Fraktionierung (Kostengünstiges
Sicherheitsnetz)**

Das Universum wird in 5 Shards partitioniert. Der tägliche Grob-Filter
verzichtet auf Bewertungskennzahlen und filtert rein auf fundamentale
Basis-Resilienz und Dynamik:

-   **Bruttomarge (Gross Margin) \> 30%:** Schützt sofort vor
    strukturell sterbenden Industrien und beweist inhärente Preismacht
    (Lynch-Burggraben).

-   **Abstand vom 52-Wochen-Tief \> 15%:** Stellt sicher, dass das
    Unternehmen erste Lebenszeichen sendet und kein fallendes Messer
    (\'klinisch tot\') ist.

-   **Market-Cap-Floor:** Ausschluss von illiquiden Micro-Caps (\< 50
    Mio. USD).

**3.2 Sieve Layer 2: Wochenend-Deep-Dive (Harte Fundamental-Scores)**

Am Wochenende läuft die komplexe Fundamental-Engine über die Shortlist
der Woche. Hier werden die echten mathematischen Zielwerte berechnet:
Lynch-PEG-Ratio (Wachstum-KGV-Verhältnis), Graham-Zahl (Wurzel aus 22.5
\* EPS \* Buchwert) sowie die Buffett-Kriterien (5 Jahre konstante
ROIC/ROE \> 15% und Verschuldung \< 0.4).

**3.3 Sieve Layer 3: Monatlicher Trend- & Footprint-Monitor (Real-Time
Momentum)**

Läuft monatlich über die qualifizierten Value-Kandidaten, um
charttechnische und volumetrische Anomalien zu erfassen:

-   **STRENGTHS (Markt-Outperformance):** Relative Stärke nach Levy (3
    Monate) \> 1.0. Die Aktie muss sich im Aufwärtstrend befinden und
    den Gesamtmarkt schlagen.

-   **WEAKNESSES (Volumen-Auffälligkeit):** Volumenpeaks an starken
    Abwärtstagen signalisieren institutionelle Distribution.

-   **OPPORTUNITIES (Der institutionelle Fußabdruck):** Relatives
    Volumen (RVOL) \> 1.5 im Monatsdurchschnitt. Ein massiver Anstieg
    des Volumens beweist das unbemerkte Akkumulieren durch Großanleger
    oder anspringendes Retail-Interesse, lange bevor Filings oder News
    greifen.

-   **THREATS (Marktrisiko):** Explosionsartiger Anstieg der Short
    Interest (\> 15%) signalisiert akute Short-Seller-Attacken.

**4. C++ Architektur-Spezifikation (FinancialData v4)**

> #pragma once\
> \
> #include \<string\>\
> #include \<optional\>\
> #include \<chrono\>\
> \
> enum class SieveStatus : uint8_t {\
> Unprocessed,\
> PassedLayer1,\
> RejectedLayer1,\
> ProcessedDeepDive,\
> QualifiedValueStock\
> };\
> \
> struct MarketBehaviorMetrics {\
> double relativeStrengthLevy3M{0.0}; // RS nach Levy
> (Momentum-Indikator)\
> double relativeVolume30D{1.0}; // RVOL (Volumen-Fußabdruck von
> Institutionen/Masse)\
> double shortInterestPercent{0.0}; // Bedrohungs-Proxy (Short-Seller
> Aktivität)\
> };\
> \
> struct TickerSwotResult {\
> bool hasTrendStrength{false}; // Strength (RS \> 1.0)\
> bool hasVolumeWeakness{false}; // Weakness (Distribution)\
> bool institutionalFootprint{false}; // Opportunity (RVOL \> 1.5)\
> bool shortSellerThreat{false}; // Threat (High Short Interest)\
> std::chrono::system_clock::time_point lastSwotEvaluation;\
> };\
> \
> struct FinancialData {\
> // Identifikation & Shard-Routing\
> std::string ticker;\
> std::string companyName;\
> uint8_t shardWeekday{0};\
> SieveStatus status{SieveStatus::Unprocessed};\
> std::chrono::system_clock::time_point lastUpdated;\
> \
> // 1. Pareto-optimierte Vorfilter-Kennzahlen (Layer 1 - Extrem
> \'günstig\')\
> double grossMargin{0.0}; // Bruttomarge (\> 30% statt KGV-Filter)\
> double distFrom52WLowPct{0.0}; // Abstand vom Jahrestief (\> 15%)\
> double marketCap{0.0};\
> \
> // 2. Komplexe Wachstums- & Substanzmetriken (Layer 2 -
> Wochenend-Deep-Dive)\
> double peRatio{0.0};\
> std::optional\<double\> pbRatio;\
> double revenueGrowth3Y{0.0};\
> double epsGrowth3Y{0.0};\
> double expectedEpsGrowth{0.0};\
> \
> // 3. Rentabilität & Solvenz (Buffett/Graham)\
> double roe{0.0};\
> double roic{0.0};\
> double debtToEquity{0.0};\
> \
> // 4. Dynamisches Marktverhalten & SWOT-Zustand (Layer 3)\
> MarketBehaviorMetrics behavior;\
> TickerSwotResult monthlySwot;\
> };

**5. Aktualisierte SWOT-Analyse des Gesamtsystems (v4)**

  -----------------------------------------------------------------------
  **Dimension**           **Positive Aspekte      **Risiken /
                          (80/20 Optimiert)**     Herausforderungen**
  ----------------------- ----------------------- -----------------------
  **Interne Faktoren**    Stärken (Strengths):\   Schwächen
                          • Drastische Reduktion  (Weaknesses):\
                          des                     • Höhere Komplexität in
                          Entwicklungsaufwands    der
                          durch Verzicht auf      systemübergreifenden
                          SEC-Parser.\            Kommunikation zwischen
                          • 0 € Zusatz-API-Kosten Value-Engine und
                          durch Nutzung von       Optionen-Modul.
                          reinen                  
                          Preis-/Volumendaten für 
                          das Sentiment.\         
                          • Keine False-Negatives 
                          bei explosiven          
                          Wachstumsaktien         
                          (KGV-Filter gelöscht).\ 
                          • Direkte Generierung   
                          von Cashflow über die   
                          integrierte             
                          Optionen-Kopplung.      

  **Externe Faktoren**    Chancen                 Risiken (Threats):\
                          (Opportunities):\       • Schnelle Trendwenden
                          • Synergieeffekt:       (V-Formationen) könnten
                          Perfekte                dazu führen, dass die
                          Monetarisierung hoher   Aktie die 15%-Hürde vom
                          impliziter Volatilität  Jahrestief zu schnell
                          durch das Schreiben von überspringt und erst
                          Cash-Secured Puts auf   verspätet erfasst wird.
                          absolute fundamentale   
                          Qualitätswerte.         
  -----------------------------------------------------------------------

**6. Pareto-optimierte Implementierungs-Roadmap (Runmap)**

> **Phase 1: Sharding & Basis-Datenlayer (Monat 1)**
>
> Realisierung der FinancialData-Struktur v4 im UIQ-Core. Aufsetzen des
> wöchentlichen Partitionierungsschemas (Mo-Fr Shards). Einbindung der
> standardmäßigen, kostengünstigen EOD-Datenfeeds (Umsatz, Bruttomarge,
> Kursdaten).
>
> **Phase 2: Sieve Engine Layer 1 & 2 (Monat 2)**
>
> Programmierung des täglichen Sicherheitsnetzes (Gross Margin \> 30%,
> Abstand vom Tief \> 15%). Aufbau der lokalen relationalen
> Shortlist-Tabellen. Implementierung der harten mathematischen
> Core-Kriterien für das Wochenende (Peter Lynch &
> Graham-Buffett-Zahlen).
>
> **Phase 3: Footprint-Engine & Layer 3 SWOT (Monat 3) - \[HIGH EFFORT
> REDUCED\]**
>
> Implementierung der rein mathematischen Indikatoren für Relative
> Stärke nach Levy und RVOL (Relatives Volumen) direkt aus dem
> bestehenden Kursdatenfeed. Verzicht auf Drittanbieter-Scraper.
> Automatisierte Generierung der monatlichen Ticker-SWOT-Einträge.
>
> **Phase 4: UI-Dashboard & Wheel-Synergie-Router (Monat 4)**
>
> Visualisierung der Ticker-SWOTs im Dashboard. Kernmeilenstein:
> Entwicklung des Cross-Modul-Routers. Sobald ein Top-Kandidat vorliegt,
> prüft das System automatisch die IV der Optionskette, um den optimalen
> Einstiegstrigger (direkter Kauf vs. Cash-Secured Put) an die
> Trader-Suite zu übergeben.


---

## Anhang A: Value-Themenregister (Kandidaten für VAL-MOD-Modelle, KEINE Scan-Sektoren)

Diese Titel compounden über Jahre statt in Wochenfenstern zu "laufen" — als Trading-Scan-Sektor
wären sie tote Dropdown-Einträge (80/20). Das FIN-Archiv sammelt ihre Fundamentaldaten bereits
wöchentlich (alle im Russell 3000); bei VAL-MOD-Aktivierung dienen sie als erste Modell-Testfälle.

**Demografie / Silver Society (05.07.2026, Gemini-Vorschlag, verifiziert):**
ENSG (Ensign Group), CHE (Chemed), STE (Steris), SEM (Select Medical), AMN (AMN Healthcare),
MMS (Maximus), HCA (HCA Healthcare), SYK (Stryker), MDT (Medtronic); Health-REITs: WELL, VTR,
DOC (ex PEAK), UHT (nicht "UHR" — Gemini-Fehlticker korrigiert).
