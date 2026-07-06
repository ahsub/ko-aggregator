
# UnderlyingIQ — Strategiedokument v1.9
**Stand: 08.07.2026 | Status: Arbeitsgrundlage | Autor: Dr. Axel Hildebrand mit Claude**

Dieses Dokument ist der Referenzrahmen für alle künftigen Produkt- und Priorisierungsentscheidungen. Jede neue Feature-Idee wird gegen Abschnitt 2 (Leitbild) und Abschnitt 6 (Entscheidungsfilter) geprüft, bevor Code entsteht.

---

## 1. Ausgangslage

UIQ (underlyingiq.com) ist eine browserbasierte Market-Analysis-PWA, entstanden 2025/26 als Solo-Projekt. Aktueller Stand: 590 Ticker im nächtlichen Aggregator-Lauf, 4-Regime Market State Engine, Strategiemodul v2.1.0 (Momentum, Trendfolge, Knock-out, Mean Reversion, einkommensorientierte Optionsstrategien), Sektor-Tag-Architektur, KI-gestützte Deep-Dive-Analysen, Morning Briefing. Infrastruktur: Cloudflare Pages/Workers/KV, GitHub Actions, jsDelivr-CDN-Module.

Das Projekt wird als kommerziell aussichtsreich eingeschätzt. Dieses Dokument definiert, was UIQ ist, was es nicht ist, und in welcher Reihenfolge der Weg zur Marktreife sinnvoll ist.

---

## 2. Leitbild

> **UIQ erkennt die aktuelle Marktverfassung und führt den Nutzer zur dafür geeigneten Handelsstrategie und den besten Underlyings — vom kurzfristigen Hebel-Trade bis zum einkommensorientierten Portfolio.**

UIQ ist ein **Strategie-Router**, kein Screener und keine Einzelstrategie-App. Die Wertschöpfungskette lautet:

**Regime-Erkennung → Strategie-Routing → Underlying-Auswahl → Instrumenten-Vorschlag**

Diese Kette ist die Differenzierung gegenüber dem gesamten Wettbewerb, der jeweils nur einzelne Glieder abbildet. Jedes Feature muss mindestens ein Glied dieser Kette messbar stärken.

### Zieldefinition Strategiefamilien

| Familie | Status | Horizont |
|---|---|---|
| Momentum / Trendfolge | ✅ produktiv | — |
| Knock-out (KO) | ✅ produktiv | — |
| Mean Reversion | ✅ produktiv | — |
| Options-Einkommen (Wheel, CSP, CC) | ✅ produktiv | — |
| Options-Erweiterung (LEAP, Spreads, Ketten) | geplant | mittelfristig |
| Value / Portfoliodesign (Sektorebene) | geplant (ValueMatrix als Vorleistung) | mittelfristig |
| Devisen | geplant | langfristig (eigene Analytik-Welt: Carry, Zinsdifferenzen, Makro) |
| Selbstlernende Optimierung | Vision | langfristig, setzt Track-Record-Layer voraus |

### Zielgruppe

Selbstentscheidende deutschsprachige Privatanleger mit Broker-Zugang (IBKR/CapTrader-Typ), die Optionsstrategien und/oder KO-Zertifikate aktiv handeln. Kein Massenmarkt, aber nachweislich zahlungsbereit (Vergleichspreise: TrendSpider, Option Samurai: 30–80 €/Monat). Synergie: identische Zielgruppe wie Refundex → Bundling-Potenzial.

---

## 3. SWOT-Analyse

### Stärken
- **Einzigartige Kette** Regime → Strategie → Underlying → Instrument; in dieser Form ohne bekannten direkten Wettbewerber.
- **Deutsche Perspektive als Feature:** Heimatbörsen-Symbole, KO-Zertifikate (genuin deutsches Produkt), BaFin-bewusstes Design von Beginn an.
- **Saubere, kostengünstige Architektur:** Cloudflare-Stack nahezu kostenfrei skalierbar, modulare Strategie-Engine (v2.1.0) nimmt neue Familien ohne Umbau auf.
- **Etablierte Entwicklungsdisziplin:** 80/20-Regel, Kausalitätsprüfung, Governance-Regeln, Batch-Deployment.
- **Gründer versteht beide Seiten:** aktiver Trader (Wheel, KO) und Entwickler — Produktentscheidungen aus eigener Handelspraxis.
- **Refundex als Schwesterprodukt** mit identischer Zielgruppe.

### Schwächen
- **Kein belegter Track-Record.** Empfehlungen werden nicht protokolliert und nicht gegen die Marktrealität ausgewertet. Ohne Trefferquoten-Nachweis fehlt das zentrale Verkaufsargument. *(→ Roadmap Phase 0, höchste Priorität)*
- **Single Point of Failure (SPOF):** Eine Person kennt System, Schlüssel, Betrieb. Keine Dokumentation für Dritte. *(→ Bus-Factor-Dokument, Phase 0)*
- **Datenbasis yfinance:** inoffiziell, ohne SLA, jederzeit drossel-/abschaltbar. Für Privatnutzung akzeptabel, für zahlende Kunden Ausfallrisiko. *(→ Phase 2: lizenzierte Datenquelle, 50–500 €/Monat einpreisen)*
- **Technische Altlast Frontend:** monolithische index.html (u.a. 1266 hardcodierte font-size-Angaben); v2.0-Migration (ES6-Module) nötig, bevor externe Entwickler mitarbeiten könnten.
- **Begrenzte Entwicklungskapazität:** Nebenprojekt neben Vollzeit-Praxis.

### Chancen
- **Echte Marktlücke** im deutschsprachigen Raum (siehe Stärken 1–2).
- **Community-Zugang:** Optionshandel-Szene (Wheel/CSP-Umfeld), Investmentclub als Beta-Kanal.
- **Bundling UIQ + Refundex:** "Handeln + Steuern" aus einer Hand — hohe Kundenbindung.
- **KI-Differenzierung:** Deep-Dive-Analysen und Morning Briefing als KI-Features, die klassische Screener nicht bieten.
- **Track-Record als Burggraben:** Sobald 12–18 Monate belegter Performance-Daten existieren, ist der Vorsprung für Nachahmer kaum aufholbar.

### Risiken
- **Regulatorik:** Grenze Finanzanalyse ↔ Anlageberatung (WpIG/WpHG). Mitigation: Compliance by Design (s. Abschnitt 5), Rechtsgutachten vor Kommerzialisierung (~800 €).
- **Datenquellen-Abschaltung** (yfinance) vor Umstieg auf lizenzierte Daten.
- **Schlüsselperson-Ausfall** vor Fertigstellung der Betriebsdokumentation.
- **Nischen-Größe:** Zielgruppe zahlungskräftig, aber klein; Wachstum jenseits einiger hundert Abonnenten ungewiss.
- **Plattformrisiko Cloudflare/GitHub:** gering, aber vorhanden (Vendor-Lock-in KV-Datenmodell).

---

## 4. Kommerzielle Roadmap

### Phase 0 — Fundament (ab sofort, ~2–3 Monate)
*Ziel: Nachweisbarkeit und Betriebssicherheit herstellen. Kein Kundenkontakt.*

1. **Track-Record-Layer** *(höchste Priorität — die Uhr läuft erst ab Go-live des Loggings)*
   - Jede Empfehlung wird in KV protokolliert: Strategie, Ticker, Regime, Score, Zeitstempel, implizite Erwartung.
   - Nachtlauf bewertet nach 7/30/90 Tagen gegen tatsächliche Kursentwicklung.
   - Auswertung: Trefferquote und CRV **pro Strategie × Regime**.
   - Nebeneffekt: Kalibrierungsdaten für Score-Schwellen; später Datenbasis für ML-Vision.
   - Umsetzung als erstes echtes ES6-Modul (v2.0-Blaupause).
   - **→ Verabschiedete Umsetzungsspezifikation: `docs/TRACK_RECORD_SPEC.md` v1.1 (03.07.2026).** Kernentscheidungen: Log-Umfang Shortlist + Top-10 je Leaderboard (~70/Tag); Leitmetrik hit30 auf frischen Signalen (KI-Trade-Simulation als Zweitspalte); Sichtbarkeit zunächst nur Expert/EIC. **Phase A (Snapshot-Logging) deployed mit Aggregator v4.4 — Tag 0 = Handelstag 02.07.2026.**
   - Backtest 2023–2026 als Phase B+ definiert: Rolle ausschließlich Kalibrierung/Plausibilisierung, niemals Marketing (Survivorship-, Kuratierungs- und In-Sample-Verzerrungen sind strukturell nicht behebbar); Ergebnisse strikt getrennt in `tr:backtest`.
2. **Bus-Factor-Dokument** im Repo: Systemüberblick, Schlüsselverzeichnis, Nachtlauf-Ablauf, Störungs-Runbook, Wiederanlauf-Anleitung.
3. Laufende Feature-Arbeit nach Session-Backlog-Modus (Batch-Deployments), gefiltert durch Abschnitt 6.

### Phase 0.5 — UX-Reifung vor Beta (zwischen Phase 0 und Phase 1)
*Ziel: Die App fremdnutzertauglich machen, bevor Beta-Tester eingeladen werden.*

Auslöser: Externes UX-Review vom 07.07.2026 durch tech-affinen Ex-Praxispartner (QM-Erfahrung Medizin-KI, Canfield-Kontext, ohne Trading-Vorwissen). Zentraler Befund: **Konzept beeindruckend, Bedienbarkeit abschreckend.** Nerd-Faktor hoch, Buttons irreführend, Workflow inkonsistent, versehentliche Trigger häufig. Ohne Behebung dieser Punkte kein sinnvoller Beta-Test möglich (Beta-Tester springen ab, bevor sie den Kern-Wert erleben).

**Verortung:** Zwischen h7-Reife (~14.07., Phase-0-Abschluss) und Phase-1-Beta-Start. Zeitfenster ~zweite Julihälfte / Anfang August 2026.

**Reifekriterium:** Ein fremder Nutzer (kein Autor, kein Trader) kann ohne mündliche Erklärung den Kern-Workflow (Morning Briefing → Marktlage → Alpha Desk → Ticker-Analyse) durchlaufen und versteht, was er sieht und was das nächste sinnvolle Handeln wäre.

**Phase-0-Blocker (muss zuerst, unabhängig von 0.5):**
- **KI-Halluzinations-Datum im Scanner-KI-Aufruf** (07.07.: „19. Januar 2025" bzw. „6. Januar 2025" wechselnd zwischen zwei Aufrufen). Direkte Widerlegung der Präsentations-Kernaussage (Slides 2/6/7). Ursache-Prüfung: Grounding-Kontrakt (aktuelles Datum im Prompt?) + Post-Filter auf halluzinierte Zeitangaben. Höchste Priorität.

**Arbeitspakete Phase 0.5 (gruppiert):**

A. **Homescreen / Landing** — Klick auf „UnderlyingIQ" in Sidebar oben links öffnet Home-Panel: heutiges Datum, Status Morning Briefing (erledigt/ausstehend, mit Uhrzeit), letztes gecachtes Briefing + Makro-Einschätzung + KI-Beurteilung lesbar, Changelog seit letztem Build mit Workflow-/Bedienungs-Auswirkungen, regulatorische Kurz-Hinweise. Rückkehr zum Home von überall per Klick auf Sidebar-Titel.

B. **Trigger-/Cache-Disziplin (Token-Ökonomie)** — Morning Briefing und Makro-Analyse werden nach Erstberechnung lokal gecacht bis zur explizit angeforderten Neuberechnung. Kein Trigger bei Mouse-over, kein Trigger bei versehentlichem Klick, kein Trigger als Nebeneffekt anderer Tab-Aktionen. Neuberechnung nur mit User-Rückfrage. Betrifft insbesondere: Morning-Briefing-Button-Duplikate in Alpha Desk und Scanner (beide entfernen), „Briefing abgeschlossen"-Bereich verliert Button-Charakter (reiner Status mit Datum/Uhrzeit).

C. **Sprache / Beschriftung** — Durchgängige Umbenennung „KI-Analyse" → „KI-basierte Markt-Einschätzung". Keine Modell-Herkunftsnennung (Claude/Anthropic/etc.) im UI, sondern nur an dedizierter Programm-Beschreibungsstelle. „Einfache Sprache" → „Kurz und bündig" (als Standard-Ansicht), Zahlen-Variante als Deep-Dive-Option. „m" → „min" in Zeitfenster-Buttons. Handelsplatz-Bezeichnungen aktualisieren (NYSE/NASDAQ/TR/L&S-Wording prüfen).

D. **Visuelle Konsistenz Button vs. Info** — Elemente, die wie Buttons aussehen, aber keine Funktion haben (Trading-Strategie-Kacheln im Morning Briefing und Scanner), verlieren Button-Optik oder bekommen echte Funktion. Empfehlungen wie „Selektiv vorgehen · Nur höchste Qualität handeln" müssen kontextualisiert werden (gilt allgemein oder für die darüber stehenden Strategien?).

E. **Alpha Desk konsolidieren** — Erste Zeile: kurze textliche Erklärung Zweck des Tabs. Beim Öffnen zunächst nur Master-Shortlist zeigen. Enrichment nur auf explizite User-Aufforderung mit Rückfrage. „KI-basierte Markt-Einschätzung"-Button liefert vielversprechendste Ticker × vielversprechendste Strategie. Strategie-Nerds: separater Weg für favorisierte Strategie mit eigener Listen-Darstellung. Marktzustands-Bezeichnung („Bull-Quiet") muss aus Briefing/Makro herleitbar oder erklärt sein. Refresh-Button rechts entweder erklären oder entfernen.

F. **Options Desk als vollwertiger Modus** — Klick öffnet eigenständigen Ansichts-Modus, der Master-Shortlist verdrängt (statt versteckt darunter). KI-enriched Top-Options-Ticker prominent, KI-Einschätzung-Button liefert Underlying × Options-Strategie. Analog zu Alpha Desk: separater Weg für favorisierte Options-Strategien (Wheel, CSP/CC, Weekly Options) mit eigener Listen-Darstellung.

G. **Scanner-Tab Neuordnung** — Marktstimmungs-Anzeige konsistent zur Alpha-Desk-Anzeige (heute widersprüchlich). Strategie-Button-Leiste entweder funktional oder als Info-Chips markiert. „Aufklappen/Zuklappen"-Buttons über die Tickerkarten. „Scan" vs. „Live" per Mouse-over erklärt. Handelsplatz-Auswahl mit Auto-Sinnvoll-Watchlists (DE → DAX/TecDAX/MDAX, US → S&P500/NASDAQ100), bei fehlender Watchlist als Popup-Empfehlung + Caching. Erklärungs-Tooltips für „KI-Analyse Watchlist Top-Performer" mit EIC-Modus-Verhalten.

H. **„Wolf-im-Schafspelz"-Modus (Investor-friendly)** — Non-Nerd-Ansicht im Admin/User-Bereich umschaltbar, reduziert Feature-Vielfalt auf das für den Anlage-Alltag Notwendige. Ziel: Einschüchterung durch Feature-Dichte abmildern, ohne den Expert-Modus zu verlieren. Erste Konzept-Skizze in Phase 0.5, Umsetzung im Detail möglicherweise erst in Phase-1-Iteration.

I. **Fehler-Kommunikation KI-Aufrufe (akut, aus Beobachtung 08.07.2026)** — Beim wiederholten Rate-Limit-Fehler („⚠️ Fetch-Fehler: Rate-Limit erreicht — bitte kurz warten") passiert im UI danach *nichts weiter*: keine automatische Wiederholung, keine Wartezeit-Angabe, kein Retry-Button, kein Cache-Fallback auf vorherige Antwort, keine Zustands-Klarheit. Der Nutzer weiß auch nicht, ob es sich um ein temporäres RPM/TPM-Limit (60 s warten) oder ein aufgebrauchtes Tageskontingent handelt (bis morgen warten) oder eine leere Credit-Balance (aufladen). Arbeitspaket: (1) Unterscheidbare Meldungen je 429-Grund, (2) sichtbarer Retry-Button mit Countdown bei transienten Limits, (3) Cache-Fallback auf zuletzt gespeicherte KI-Einschätzung für denselben Ticker mit Alters-Anzeige, (4) klarer Zustands-Wechsel im UI (nicht nur Toast). Kleiner Aufwand, hoher UX-Effekt. Verweist strukturell auf Phase 1 (Skalierungs-Konzept, siehe dort).

**Was Phase 0.5 nicht ist:** Kein Design-System-Rollout (bleibt an v2.0/D2 gekoppelt, SUITE §3.7). Kein Corporate-Redesign. Kein Umbau der Aggregator-Logik. Kein IP-Schutz-Refactor. Reine UX-Reifung auf bestehender Architektur, minimale invasive Änderungen mit maximaler Bedienungs-Wirkung.

### Phase 1 — Geschlossene Beta (nach Phase 0, ~3–6 Monate)
*Ziel: Fremdnutzer-Feedback ohne kommerzielles Risiko.*

- Beta-Kreis aus Investmentclub (5–15 Nutzer), kostenfrei, mit klarem "Analyse-Tool, keine Beratung"-Rahmen.
- Erkenntnisziele: Verständlichkeit ohne Erklärung durch den Autor, Feature-Nutzung real vs. vermutet, Zahlungsbereitschaft (Befragung).
- Parallel: Track-Record reift.
- **KI-Kontingent-Skalierung (Phase-1-Blocker, aus Beobachtung 08.07.2026):** Bei 5+ Beta-Testern mit paralleler Nutzung ist ein persönlicher Anthropic-API-Key kontingent- und limitseitig nicht mehr tragfähig. Bausteine (Konzept, Umsetzung nach Bedarf): (a) **Server-seitige Request-Queue** — Requests werden gepuffert, Rate-Limit-Handling zentral im Cloudflare Worker, Nutzer sehen "wird verarbeitet" mit Warteschlangen-Position statt Fehler; passt zur Server-Function-Architektur des v2.0-IP-Schutz-Konzepts (Phase 3). (b) **Aggressives Ergebnis-Caching** — jede KI-Einschätzung pro Ticker wird gecacht mit Standard-TTL 6–24 h (je nach Datenaktualitätsanspruch), Nutzer sieht Cache-Alter transparent, "Neu berechnen" nur bewusst und mit Kosten-Hinweis; passt zur Trigger-/Cache-Disziplin Phase 0.5 AP B. (c) **Pro-Nutzer-Budget** — Restkontingent pro Beta-Tester sichtbar, verhindert Verbrauch durch Einzelnen. (d) Grundsätzlich: **Kostenposition wird in Phase 2 Preismodell-Hypothese hart** — freie KI-Anfragen sind bei API-Kosten nicht dauerhaft skalierbar.

### Phase 2 — Kommerzialisierungs-Voraussetzungen (parallel zu Phase 1 vorbereiten)
*Ziel: Alle Blocker beseitigen, bevor der erste Euro fließt.*

- **Rechtsgutachten** (Fachanwalt Kapitalmarktrecht): Bestätigung Finanzanalyse-Status, Disclaimer-Prüfung, AGB-Grundlage.
- **Datenquellen-Upgrade:** Evaluierung EODHD / Polygon / Twelve Data; Migration des Aggregators.
- **Gesellschaftsform:** GmbH-Entscheidung inkl. Rollenklärung (s. Abschnitt 7 — offene Entscheidung Mitgründung).
- **Preismodell-Hypothese:** Freemium (Public-Modus) + Abo (Expert-Features), Zielkorridor 20–50 €/Monat; Bundle-Option mit Refundex.

### Phase 3 — Launch & Ausbau
- Öffentlicher Launch mit belegtem Track-Record als zentralem Marketing-Asset.
- **Vite/React-Migration (v2.0)** ist der natürliche Träger für den Suite-Design-System-Rollout (siehe SUITE.md §3.6/§3.7, Phase D2). UIQ-Corporate-Design, öffentliche Web-Präsenz und Rechtsseiten (Impressum, Datenschutz, Kontakt, FAQ) gehen mit v2.0 live — kein Vorziehen in den v1.x-Monolithen, weil doppelt gebaut.
- **v2.0-Architektur-Anforderung (Single Source of Truth):** Konfigurations-Listen (Ticker/Sektoren, Strategien, Regime, Ampelfarben, Preset-Maps) werden in eigenen Config-Modulen zentralisiert; alle UI-Komponenten und der Aggregator konsumieren diese als einzige Quelle. Adressiert die im v1.x akkumulierte DRY-Verletzung (Log 06.07.2026). Kein Retrofit in v1.x.
- **IP-Schutz-Konzept (Server-Function-Split, siehe Log 07.07.2026):** Sensible Rechen­pfade (Scoring-Formeln, Regime-Klassifikator-Schwellen, Fibonacci-Konfluenz-Logik, Setup-Klassifikation) und LLM-Prompt-Kontrakte wandern in Cloudflare Workers als Server-Functions. Frontend erhält nur Ergebnisse, nicht die Algorithmen. Auth-gated Expert-Features über echten Session-Layer statt PIN-in-Client. Adressiert den IP-Preisgabe-Vorbehalt (JS-im-Browser lesbar) ohne kompletten Backend-Umbau. Client bleibt Rendering-Schicht; Split entlang der Vertraulichkeitsgrenze. Aggregator-Repo `ahsub/ko-aggregator` kann parallel von öffentlich auf privat gestellt werden — reversible Einzelentscheidung, unabhängig vom v2.0-Split.
- Ausbau Strategiefamilien in dieser Reihenfolge: Options-Erweiterung (LEAP/Spreads) → Value/Portfoliodesign (ValueMatrix-Integration) → Devisen.
- ML-Optimierung erst, wenn Track-Record-Datenbasis ≥ 12 Monate.

**Internationalisierungs-Stufenplan** (Reihenfolge verbindlich):
1. **DACH** (deutsch) mit belegtem Track-Record — Kernmarkt, konkurrenzlos, KO-Familie voll gültig.
2. **Englischsprachiges Europa** (Nordics, Benelux, UK): KO-/Turbo-/Mini-Future-Kultur existiert dort ebenso (DEGIRO, Nordnet); volle Feature-Parität, nur Sprachwechsel. Heimatbörsen-Governance ist bereits die passende Datenbasis.
3. **USA** nur als optionale Fernstufe: KO-Familie entfällt, Router + Options-Familie träfe auf gesättigten Wettbewerb (OptionStrat, Market Chameleon, Unusual Whales). Grenznutzen deutlich geringer — keine aktive Planung.

*Hinweis Bundling: Refundex bleibt strukturell deutsch (Anlage KAP); Bundle-Argument gilt daher nur im DACH-Kernmarkt.*

---

## 5. Regulatorischer Rahmen (Compliance by Design)

**Grundsatz:** UIQ ist im Public-/User-Modus ein **Informations- und Analysewerkzeug**, keine Anlageberatung.

- **Keine personalisierten Instrumenten-Empfehlungen im Public-Modus.** Portfoliodesign ausschließlich auf Sektor-/Allokationsebene und generisch formuliert ("In Regime X waren defensive Sektoren historisch relativ stark").
- **Architektonische Absicherung:** Keine Kopplung von Personendaten an Empfehlungslogik im Public-Modus. Was das System nicht kann, kann rechtlich nicht vorgeworfen werden.
- **Disclaimer-Layer:** rendert statisch bei allen Portfolio- und Strategie-Ausgaben mit.
- **EIC-Expert-Modus (PIN):** bleibt Konstrukt für den Eigengebrauch; ist **keine** tragfähige Lösung für zahlende Dritte mit individuellen Empfehlungen.
- **Redlichkeitspflichten** (§ 85 WpHG) bei Finanzanalysen beachten: sachgerechte Darstellung, Offenlegung von Interessenkonflikten (Eigenpositionen!).
- **Pflichttermin:** einmalige anwaltliche Prüfung vor Phase 3 (eingeplant in Phase 2).

---

## 6. Entscheidungsfilter für neue Features

Jede Idee durchläuft vor Aufnahme ins Session-Backlog drei Fragen:

1. **Router-Frage:** Stärkt das Feature messbar ein Glied der Kette Regime → Strategie → Underlying → Instrument? *(Wenn nein: verwerfen oder Parkliste.)*
2. **80/20-Frage:** Würde dieser Wert eine konkrete Handelsentscheidung in den nächsten 30 Tagen verändern? *(Wenn nicht eindeutig ja: nicht in den Nachtlauf.)*
3. **v2.0-Frage:** Ist die Umsetzung ES6-konform und portierungsarm angelegt? *(Wenn nein: Umsetzungsentwurf überarbeiten.)*
4. **i18n-Frage:** Bezieht neuer Code alle nutzersichtbaren Texte aus einem zentralen String-Objekt statt Inline-Verdrahtung? *(Kostet beim Schreiben nichts, macht v2.0 übersetzungsfähig by design. Bestandscode wird nicht präventiv umgebaut.)*

**Deployment-Disziplin:** Sammeln im Session-Backlog; Deployment nur bei lohnendem Batch oder kritischem Bug. Claude weist aktiv auf erreichte Deployment-Schwelle hin.

### Bestehende Todo-Liste nach Filterlauf (02.07.2026)

| Punkt | Router-Beitrag | Priorität neu |
|---|---|---|
| **Track-Record-Layer** *(neu)* | Fundament für alles | **1 — strategisch** |
| **Bus-Factor-Dokument** *(neu)* | Betriebssicherheit | **2 — strategisch** |
| Ticker-Erweiterung (Gemini-Liste) | Underlying-Auswahl | 3 — nächster Aggregator-Batch |
| TTM Squeeze (sqzOn/sqzOff) | Timing Options-Familie × Regime | 4 — hoch |
| TICKER_SECTOR_MAP Migration | Datenbasis aller Familien, v2.0-Baustein | 5 — hoch |
| KO-Leaderboard | Instrumenten-Vorschlag KO-Familie | 6 — mittel |
| Short-Strategie Phase 2 (Bear-Put-Spread) | neue Strategieoption | 7 — mittel |
| Liquidity Sweep Score | Indikator, kein Router-Glied | 8 — Mittelfeld |
| Fair Value Gaps | Indikator, kein Router-Glied | 9 — Mittelfeld |
| BSL/SSL für DeepDive-Prompts | KI-Anreicherung | 10 — niedrig |
| Sektor-Treiber als persistente WL | Komfort | 11 — niedrig |

---

## 7. Risikoregister & offene Entscheidungen

| Risiko | Schwere | Mitigation | Status |
|---|---|---|---|
| SPOF (Wissen nur bei Gründer) | hoch | Bus-Factor-Dokument; mittelfristig zweite Person | offen — Phase 0 |
| yfinance-Ausfall | hoch | lizenzierte Datenquelle vor Launch | geplant — Phase 2 |
| Regulatorik-Fehleinschätzung | mittel | Compliance by Design + Rechtsgutachten | teilmitigiert |
| Frontend-Monolith blockiert Mitarbeit Dritter | mittel | v2.0/ES6-Migration; neuer Code ab sofort ES6-konform | laufend |
| Nischengröße begrenzt Umsatz | mittel | Bundling mit Refundex; Beta validiert Zahlungsbereitschaft | offen — Phase 1 |
| yfinance-Ausfall VOR Phase-2-Migration (Interim) | hoch | **Plan B light (03.07.2026):** (a) Graceful Degradation — letzter erfolgreicher Nachtlauf bleibt mit sichtbarem Stale-Banner nutzbar, App stirbt nie; (b) eigener Twelve-Data-Key als Notbetrieb für Kern-Indikatorensatz (800 Calls/Tag ≈ Minimalversorgung 590 Ticker, ehrlich dokumentiert); (c) Phase-2-Datenquellen-Evaluierung wird bei Ausfall zeitlich vorgezogen. **Verworfen:** serverseitige Nutzung der Nutzer-Twelve-Data-Keys (Gemini-Vorschlag) — architektonisch unmöglich (Keys per Design nur im localStorage der Nutzer-Browser) und lizenzwidrig (personengebundene Free-Keys) | definiert |
| KI-Kosten-Skalierung (Deep Dive/Briefing je Nutzer) | mittel→hoch bei Beta | **Rate-Limiting im ko-ai Worker** (KV-Tageszähler je Token-Hash; Startlimits: 5 Deep Dives, 2 Briefings/Tag, konfigurierbar) macht Beta-Kosten fix statt nur beobachtbar; KI-Kosten/Nutzer/Monat als Pflicht-Metrik Phase 1 vor Preisfestlegung | beschlossen — Umsetzung Leitprojekt |
| ko-ai-Worker-Quellcode nicht versioniert | mittel | Befund 03.07.2026: Worker v4 existiert nur im CF-Dashboard, nicht in Git — SPOF-Verschärfung. Quellcode ins workers-Repo exportieren (RUNBOOK-Ergänzung); Rate-Limit-Patch liegt bereits dort als Startpunkt | offen — Phase 0 |

**Offene strategische Entscheidungen** (bewusst nicht terminiert):
1. **Mitgründung Tochter:** Rollenfrage klären (Entwicklung vs. Geschäftsführung/Organisation — unterschiedliche Anforderungsprofile). Vorgeschlagener Weg: Testballon ohne Festlegung — dieses Dokument + Bus-Factor-Dokument zum Lesen geben, offenes Gespräch über Interesse.
2. **Preismodell final** (nach Beta-Befragung).
3. **Claude-Team-Lizenz** für 2–4 Mitarbeiter (gekoppelt an Entscheidung 1).

---

## 8. Fortschreibung

Dieses Dokument wird bei jeder strategischen Weichenstellung versioniert fortgeschrieben (v1.1, v1.2 …) und liegt im Repo neben dem Bus-Factor-Dokument. Es ist Bestandteil jedes Session-Übergabeprotokolls (Verweis genügt).

---

## 9. Entscheidungs-Log

| Datum | Entscheidung |
|---|---|
| 02.07.2026 | Leitbild „Strategie-Router" verabschiedet; SWOT + Roadmap Phase 0–3; i18n-Stufenplan (DACH → EN-Europa → USA optional); vierstufiger Entscheidungsfilter. |
| 02.07.2026 | Aggregator v4.2 deployed: Ticker-Erweiterung 7 Watchlists (+61), RS-ETFs, CEG nur NUCLEAR_ENERGY, IBM/HON nicht in CYBERSECURITY. |
| 02.07.2026 | **Aggregator v4.3 deployed: kritischer Regime-Routing-Fix** — VIX-Ratio-Konvention war invertiert, ruhige Contango-Märkte wurden als STRESS_UNSTABLE geroutet (entdeckt durch Output-Review des ersten v4.2-Laufs). Zusätzlich 13 tote Ticker bereinigt; Shiller CAPE per 80/20 gestrichen (alle Quellen defekt, kein 30-Tage-Entscheidungseinfluss). |
| 03.07.2026 | Track-Record-Spec v1.1 verabschiedet (docs/TRACK_RECORD_SPEC.md) inkl. der drei §9-Entscheidungen; Backtest-Rolle definiert (Phase B+, nur Kalibrierung). |
| 03.07.2026 | Cron-Härtung: Nachtlauf auf 03:37 UTC verlegt (GitHub-Actions-Queues verzögern zur vollen Stunde regelmäßig um Stunden; 02.07: 3h23min). Langfristig: CF-Worker-Dispatch für minutengenaue Auslösung (RUNBOOK/Phase 0). |
| 03.07.2026 | Suite-Governance etabliert: SUITE.md (Meta-Repo UIQ-Suite) mit Prioritäten-Wirbelsäule — UIQ Phase 0 ist Leitprojekt mit absoluter Build-Priorität; Refundex Wartungsmodus, PO geparkt, DepotIQ/Ruhestand eingefroren. Recherche-Gates aller Module laufen weiter (Denk- vs. Build-Kapazität). |
| 03.07.2026 | Meta-SWOT (Claude + Gemini-Cross-Check) in SUITE.md §5; Risikoregister ergänzt: yfinance-Plan-B-light (Gemini-Vorschlag Nutzer-Keys serverseitig verworfen: localStorage-Architektur + Lizenzbindung), KI-Rate-Limiting beschlossen (5 DD / 2 Briefings pro Token/Tag), Befund ko-ai-Quellcode unversioniert. |
| 05.07.2026 | **VAL-MOD-Konzept v4 archiviert** (docs/VALUE_MOD_KONZEPT.md, Status GEPARKT): 3-Layer-Sieve + Wheel-Synergie-Router (Value-Kandidat → IV-Prüfung → Direktkauf vs. CSP). Claude-Review: Datenmodell statt C++-Implementierung, Track-Record-Anbindung ab Tag 1, Momentum-Value-Bias als dokumentierte Hypothese. Löst ValueMatrix-Konzept ab. |
| 05.07.2026 | **FIN-Archiv GO (Aggregator v4.6):** Point-in-Time-Fundamentaldaten sind nicht rückwirkend beschaffbar → wöchentliche Rohdaten-Archivierung startet sofort (Value-Modul Phase 0, VAL-MOD bleibt geparkt). Universum: Russell 3000 (IWV-Holdings, Konstituenten mit-archiviert = survivorship-frei) ∪ Smart-Picks (data/value_smart_picks.txt) ∪ UIQ — Begründung: 10-Bagger/Value-Perlen entstehen jenseits des Trading-Universums. Sharding Mo–Fr, Samstag-Merge nach data/fundamentals/ (Git-History = Archiv). Erste Vollwoche: 2026-W28 (Archiv am 11.07.). |
| 05.07.2026 | **Supercycle-Sektoren (Aggregator v4.7):** 5 neue Watchlists (GRID_ELECTRIFICATION, PRECIOUS_METALS, AGRICULTURE, WATER, PICKS_SHOVELS als getaggter Sektor statt Index-Slot) + Fuel-Cycle/Kupfer-Erweiterungen; Universum 644→678. Arbeitsmuster etabliert: Gemini als Ideen-Generator, Claude-Verifikations-Filter vor jeder Integration (hier ~15% Fehlticker aussortiert). Demografie-Titel als Value-Thema ins VAL-MOD-Register statt Scan-Sektor. |
| 05.07.2026 | **UI-Leitprinzip beschlossen: Form follows Function** — oberstes Prinzip jeder UI-Änderung; Tab-Folge orientiert sich am Tages-Workflow (Tagesstart → Markt-Kontext → Arbeit → Verwaltung). Frontend-Reorg v243: DarkPool in Makro integriert (kein eigener Tab), Journal-Tab entfernt (8 Monate unbenutzt, 80/20; Git-History = Archiv), Tab-Container-Strukturschuld behoben. |
| 06.07.2026 | **Corporate Design & Web-Präsenz-Rollout an v2.0 gekoppelt (SUITE.md §3.7 Phase D2, Q4 2026):** Suite-übergreifender Timeframe verabschiedet (D0 Sammelbecken ab sofort → D1 Konzept ~Ende Juli/August → D2 Rollout mit Vite/React-Migration Q4 2026 → D3 Suite-weit 2027). Bewusste Effizienz-Kopplung: Design-System nicht in v1.x-Monolithen zurückbauen (Doppelarbeit); Warnpflicht bleibt auf UIQ Phase 0 aktiv, Design bleibt bis D2 reine Denk-Kapazität. |
| 06.07.2026 | Scanner-UX v244 deployed: Long/Bear-Segmentschalter statt zweier separater Buttons neben Scan-Button (FFF-konform, ein Bear-Button pro Tab-Kontext war Streuner); KI-Analyse-Dropdown erst nach Scan sichtbar und mit sprechendem Label „KI-Analyse der Treffer" statt reinem Icon; help.html BaFin-Sprachhygiene: „Frühausstieg-Regel" → „Frühausstieg-Empfehlung". |
| 06.07.2026 | **Architektur-Befund vor Präsentation (just-for-the-record):** DRY-Verletzung bei Konfigurations-Listen — dieselben Ticker-/Sektor-/Strategie-Definitionen werden an mehreren Stellen im v1.x-Monolithen redundant gepflegt (FIXED_LISTS, Preset-Maps, Auto-Scan-Zeitplan, Bear-Scanner, Alpha-Desk-Presets, ko-prompts.js, Aggregator-Watchlists). Symptom: Einstellungen-Tab zeigt Auto-Scan-Liste ohne die 4 Supercycle-Sektoren aus v4.7 (GRID_ELECTRIFICATION/PRECIOUS_METALS/AGRICULTURE/WATER). **Entscheidung: Kein Retrofit in v1.x** (Doppelarbeit, hohes Regressionsrisiko, würde UIQ Phase 0 stören) — Single-Source-of-Truth-Refactor wandert als **verbindliche v2.0-Architektur-Anforderung** in Phase 3. Symptom-Ticker im Backlog. |
| 06.07.2026 | help.html Dark/Light-Theme-Sync bleibt v244b-geparkt (CSS-Variablen-Umbau, kein Präsentations-Blocker); Auto-Scan-Konfig-Liste im Einstellungen-Tab fehlen 4 Supercycle-Sektoren (Symptom der DRY-Verletzung oben, kein separater Fix bis v2.0). |
| 07.07.2026 | **Externes UX-Review durch tech-affinen Ex-Praxispartner (4 Std., auf Basis der Engineering-Präsentation + Live-Nutzung).** Befund: „Konzept beeindruckend, Bedienbarkeit abschreckend." Detail-Punkte gruppiert in Arbeitspaketen A–H (§4 Phase 0.5). **Phase-0-Blocker identifiziert:** KI-Halluzinations-Datum im Scanner-KI-Aufruf (wechselnde erfundene Daten „19.01.2025" / „06.01.2025" zwischen zwei Aufrufen desselben Tickers) — direkte Widerlegung der Präsentations-Kernaussage zu Halluzinations-Kontrolle. Ursachen-Prüfung offen (Grounding-Kontrakt? Post-Filter?), Priorität höchste, unabhängig von Phase 0.5. |
| 07.07.2026 | **IP-Schutz-Vorbehalt aus UX-Review-Nachgespräch:** Ex-Praxispartner (Canfield-Hintergrund, Medizin-KI mit serverseitigem Modell-Schutz) hält JS-im-Browser-Architektur für IP-riskant, schlägt „komplettes Redesign mit serverseitigem geschütztem Backend" vor. **Entscheidung: Kein komplettes Redesign** (18–24 Monate Vollzeit, Track-Record-Uhr würde sterben, dieselbe Funktionalität am Ende, Design-Rollout-Kopplung an v2.0 wäre Kollateralschaden). Stattdessen: **Server-Function-Split in v2.0-Migration** als 80/20-Antwort (Phase 3, siehe §4). Aggregator-Repo-Sichtbarkeits-Entscheidung (öffentlich vs. privat) reversibel und unabhängig. Kern-IP liegt ohnehin in wachsendem Track Record + FIN-Archiv + dokumentierten Architektur-Entscheidungen (STRATEGIE/SUITE), nicht im rekonstruierbaren Code. |
| 08.07.2026 | **Phase 0.5 „UX-Reifung vor Beta" als eigene Phase eingeführt** (§4, zwischen Phase 0 und Phase 1, Zeitfenster ~zweite Julihälfte / Anfang August). Reifekriterium: Fremdnutzer ohne mündliche Erklärung durchläuft Kern-Workflow. Arbeitspakete A–H aus UX-Review destilliert. Warnpflicht-Verortung: bewusst NICHT parallel zu Phase 0 gebaut (Track-Record-Reife hat weiter absolute Priorität), sondern als aufgesetzter Reifeschritt vor Beta-Start. |
| 08.07.2026 | **Rate-Limit-Beobachtung (Anthropic-API):** Wiederholt „⚠️ Fetch-Fehler: Rate-Limit erreicht" bei KI-Ticker-Analysen im EIC-Modus, teils Tageskontingent aufgebraucht. UI reagiert danach nicht weiter (keine Retry-Logik, keine Zustandsklärung, kein Cache-Fallback). **Zwei separate Konsequenzen dokumentiert:** (1) Akute UX-Reparatur in Phase 0.5 AP I (unterscheidbare 429-Meldungen, Retry-Button, Cache-Fallback). (2) Struktureller Skalierungs-Blocker in Phase 1 (Server-Queue, Ergebnis-Caching, Pro-Nutzer-Budget; Kostenposition wird Preismodell-Hypothese Phase 2 hart machen). Bau steht in beiden Phasen an — hier nur Verankerung. |
