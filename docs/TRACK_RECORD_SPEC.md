# UIQ Track-Record-Layer — Umsetzungsspezifikation v1.2
**Stand: 03.07.2026 | Status: Phase A + B DEPLOYED (Aggregator v4.5) | Referenz: STRATEGIE.md Phase 0, Punkt 1**

## 1. Zweck & Einordnung

Der Track-Record-Layer protokolliert jede nächtliche Empfehlung des Strategie-Routers und bewertet sie nach festen Horizonten gegen die tatsächliche Kursentwicklung. Ergebnis sind Trefferquoten, Renditen und Alpha **pro Strategie × Marktregime × Horizont** — die Nachweisgrundlage für die Kommerzialisierung (STRATEGIE.md, Roadmap Phase 0) und zugleich Kalibrierungsdaten für Score-Schwellen sowie langfristig die Datenbasis der ML-Vision.

**Zeitkritik:** Nur das Protokollieren (Phase A) ist unwiederbringlich — jeder Tag ohne Snapshot fehlt für immer. Die Bewertung (Phase B) ist beliebig nachholbar, da Kurshistorie rückwirkend verfügbar ist. Tag 0 ist frühestens der 03.07.2026: Alle früheren Läufe arbeiteten mit invertiertem Regime-Routing (Fix v4.3, 02.07.2026) und wären als Datenbasis wertlos.

**Kein historisches Backfill:** Vergangene Empfehlungen existieren nicht rekonstruierbar (Scores hängen an Tagesdaten und Codestand). Frischer Start = saubere Provenienz.

## 2. Was gilt als Empfehlung (Log-Quellen)

| Quelle | Umfang/Tag | Zweck | Phase |
|---|---|---|---|
| `masterShortlist` | ~20 | Produktnahes Track Record; inkl. KI-Felder (trigger/stopLoss/target) für Trade-Simulation | A |
| Leaderboards, Top 10 je Strategie (5×10) | ~50 | Kalibrierungs-Sample; beschleunigt statistische Signifikanz je Strategie×Regime-Zelle | A |
| `optionsWatchlist` Top 10 | ~10 | Eigene Metrik (Strike-basiert, nicht direktional) | C (Ausbaustufe) |

Erwartung: ~70 Einträge/Tag (Phase A/B). Dedupe innerhalb eines Tages: derselbe (sym, strat) aus Shortlist UND Leaderboard wird einmal geloggt, Quelle `src:"sl"` gewinnt (trägt KI-Felder).

## 3. Datenmodell (Cloudflare KV)

Namespace: bestehendes UIQ-KV. Alle Keys mit Präfix `tr:`. Append-only; jede Struktur trägt Schema-Version `"v":1`.

### 3.1 Snapshot — `tr:snap:<YYYY-MM-DD>` (Key-Datum = **Handelstag** der Daten, nicht Laufdatum)
```json
{ "v":1, "tday":"2026-07-02", "run":"2026-07-02T21:20:05Z",
  "regime":"BULL_QUIET", "aggVersion":"4.3",
  "recs":[
    { "sym":"MSFT", "src":"sl", "strat":"long_minervini", "dir":1,
      "score":87, "p0":512.34, "atr":5.6, "fresh":true,
      "ki":{"trig":515.2,"sl":505.1,"tgt":535.0},
      "ctx":{"rsi":61.2,"hvp":34,"bbPos":0.81,"iosQ":88,"dist200":18.4} }
  ]}
```
- `p0` = Schlusskurs des Handelstags (Referenzpreis). `dir`: +1 Long, −1 Short.
- `fresh`: false, wenn (sym, strat) bereits im Snapshot des Vortags-Handelstags stand (Serienkorrelation-Markierung, §6).
- `ctx`: bewusst kleine, feste Feldauswahl für spätere Kalibrierung — kein Voll-Dump.
- Größe: ~70 × ~350 B ≈ 25 KB/Tag ≈ 6 MB/Jahr über ~250 Keys. KV-Limits (25 MB/Value) irrelevant fern.

### 3.2 Index — `tr:index`
```json
{ "v":1, "days":[ {"d":"2026-07-02","n":68,"h7":false,"h30":false,"h90":false} ] }
```
Kompakter Fahrplan für den Evaluator: welcher Handelstag ist für welchen Horizont fällig/erledigt. Ein Key, klein, wird nightly fortgeschrieben.

### 3.3 Bewertung — `tr:eval:<YYYY-MM-DD>`
Pro Empfehlung nach Fälligkeit ergänzt:
```json
{ "sym":"MSFT","strat":"long_minervini","dir":1,"fresh":true,"regime":"BULL_QUIET",
  "r7":2.1,"r30":5.8,"r90":null,
  "a30":1.9,             
  "mfe30":8.2,"mae30":-2.4,
  "trade":{"st":"TARGET","r":2.0,"bars":11},
  "status":"OK" }
```
- `rX`: richtungsgerechte Rendite in % nach X **Handelstagen** (Bar-Zählung ab p0-Bar; Short: Vorzeichen gedreht).
- `a30`: r30 minus richtungsgerechte SPY-Rendite gleicher Spanne (v1: SPY als Universalbenchmark; Limitation für .DE-Titel dokumentiert).
- `mfe/mae`: max. günstige/ungünstige Auslenkung im Fenster (aus OHLC der Historie zum Bewertungszeitpunkt — kein tägliches Tracking nötig).
- `trade` (nur wo `ki` vorhanden): Simulation Trigger→(Stop|Target); Same-Bar-Ambiguität konservativ als STOP gewertet. `st` ∈ NOT_TRIGGERED | TARGET | STOP | OPEN; `r` = realisiertes R-Multiple.
- `status` ∈ OK | DELISTED | NO_DATA. DELISTED/NO_DATA fließen NICHT in Mittelwerte, werden aber gezählt und ausgewiesen (Survivorship-Transparenz, §6).

### 3.4 Aggregat — `tr:stats` (das einzige, was das Frontend liest)
```json
{ "v":1, "updated":"…", "since":"2026-07-03", "totalRecs":4210,
  "cells":{ "long_minervini|BULL_QUIET|h30":
     {"n":142,"nFresh":61,"hit":0.63,"hitFresh":0.61,
      "avg":3.4,"med":2.6,"alpha":1.9,"mae":-4.1,
      "delisted":1,"trade":{"n":38,"win":0.58,"avgR":0.7}} },
  "byStrategy":{…}, "byRegime":{…} }
```
Vollständige Neuberechnung nightly aus allen `tr:eval:*` (v1: Dateien sind klein genug; Optimierung erst bei Bedarf).

## 4. Ablauf im Nachtlauf (market_aggregator.py)

Einhängepunkt: nach KI-Enrichment, vor KV-Upload des Master-JSON. Gesamter Layer in try/except gekapselt — **ein Fehler im TR-Layer darf den Hauptlauf niemals brechen** (Warnung loggen, weiter).

1. **Snapshot schreiben:** Handelstag = `last_trading_day`. Existiert `tr:snap:<tday>` bereits → überspringen (Dedupe; schützt vor manuellen Doppel-Runs wie #49/#50 am 02.07.). `fresh`-Flag gegen Vortags-Snapshot bestimmen. Index fortschreiben.
2. **Evaluator:** Index laden; jeden Tag mit fälligem Horizont (≥7/30/90 Bars seit tday, Bar-Zählung über SPY-Historie als Kalender) bewerten. Kursdaten primär aus dem **bereits geladenen `hist_data`** (Null-Kosten); Ticker, die nicht mehr im Universum sind, per Einzel-Fetch, bei Fehlschlag `status:NO_DATA`, bei bestätigtem Delisting `DELISTED`.
3. **`tr:stats` neu aggregieren** und pushen.

Laufzeitbudget: < 3 s. Kein zusätzlicher API-Verbrauch im Normalfall.

## 5. Metrik-Definitionen (verbindlich)

- **Treffer (hit)**, Primärdefinition: richtungsgerechte Rendite nach 30 Handelstagen > 0. Sekundär ausgewiesen: hit7, hit90, hitFresh, Alpha>0-Quote.
- **Trade-Metrik** (KI-Simulation) als separate Spalte — nicht mit hit vermengt.
- **Mean-Reversion-Long:** identische Horizonte, aber h7 als Leithorizont ausgewiesen (Strategie-Natur).
- Rundung: Renditen 1 Dezimale, Quoten 2 Dezimalen. Keine Annualisierung in v1.

## 6. Statistische Ehrlichkeit (nicht verhandelbar)

1. **Serienkorrelation:** `fresh`-Trennung; Primärkommunikation nutzt `hitFresh`/`nFresh`, Gesamtwerte daneben.
2. **Survivorship:** DELISTED/NO_DATA werden gezählt und je Zelle ausgewiesen, nie stillschweigend entfernt.
3. **Mindest-n:** Anzeige einer Zelle erst ab n≥20 (Fresh-Werte ab nFresh≥20); darunter „sammelt noch (n=…)".
4. **Append-only:** Keine rückwirkende Korrektur von Snapshots. Metrik-Änderungen nur via Schema-Version + Neuauswertung, dokumentiert im Changelog dieses Dokuments.
5. **Selbstreferenz-Hinweis:** Sobald Track-Record-Werte Score-Schwellen kalibrieren, gilt ab diesem Datum ein Regime-Bruch-Marker in `tr:stats` (in-sample/out-of-sample-Trennung).

## 7. BaFin / Kommunikation

`tr:stats` ist deskriptive Statistik historischer Signale. Public-Darstellung (falls/wenn) mit festem Disclaimer: „Statistische Auswertung historischer Signale des Systems. Vergangenheitswerte sind kein Indikator für künftige Ergebnisse. Keine Anlageberatung." Bis Datenreife: Anzeige nur im Expert/EIC-Modus (→ §9, Frage 3).

## 8. Phasenplan

| Phase | Inhalt | Aufwand | Bemerkung |
|---|---|---|---|
| **A** | Snapshot-Writer + Index + Dedupe (Python, `tr_layer.py` als eigenes Modul, Import in Aggregator) | ~1 Session | **Zeitkritisch — startet die Uhr.** Deployment-würdig allein. |
| **B** | Evaluator + `tr:stats`-Aggregation | ~1 Session | Bewertet Phase-A-Daten rückwirkend automatisch, sobald Horizonte reifen (frühestens tday+7 Bars). |
| **C** | Frontend `ko-trackrecord.js` (ko-modules, ES6, i18n-konform): Matrix Strategie×Regime, Expert/EIC | ~1 Session | Erst sinnvoll mit ersten h7-Daten (~2 Wochen nach A). |
| **B+** | Backtest-Modus des Evaluators: heutige v4.3+-Regeln auf 2023–2026 anwenden (simulierte Snapshots, identische Bewertungslogik) | ~1 Session nach B | **Rolle: ausschließlich Kalibrierung/Plausibilisierung — niemals Marketing.** Bekannte, nicht behebbare Verzerrungen: Survivorship (Delistings fehlen physisch), rückschauend kuratierte Universumslisten, In-Sample-Tuning der Schwellen (2025/26 kalibriert). Auflagen: eingefrorene, dokumentierte Backtest-Universumsliste; Ergebnisse strikt getrennt in `tr:backtest`, nie mit `tr:stats` vermischt. |
| **D** | Options-Track-Record (Strike-Metrik), Trade-Sim-Verfeinerung, DE-Benchmark | offen | Nach 80/20-Review mit echten Daten. |

Architektur-Vorgabe: `tr_layer.py` als in sich geschlossenes Modul (reine Funktionen, Abhängigkeiten als Parameter) — Blaupause für die v2.0-Modularisierung auch auf Python-Seite.

## 9. Entscheidungen (fixiert 03.07.2026)

1. **Log-Umfang v1:** Shortlist + Top 10 je Leaderboard (~70/Tag). ✅
2. **Leitmetrik:** hit30 (richtungsgerecht, fresh-primär) als Headline; KI-Trade-Simulation als separate Zweitspalte. ✅
3. **Sichtbarkeit:** ausschließlich Expert/EIC; Public erst nach expliziter Freigabe (n≥20-Zellen + Disclaimer). ✅

### Implementierungsnotizen Phase B (v1.2)
- Fälligkeit = Horizont **+ 3 SPY-Bars Puffer** (EU-Ticker mit eigenem Feiertagskalender haben dann sicher genug eigene Bars).
- v1 zählt fehlende Bewertbarkeit als `noData` je Zelle; explizite Delisting-Erkennung (Einzel-Fetch) folgt in B.1.
- `tr:stats` wird nightly voll neu aggregiert (alle `tr:eval:*` per GET); inkrementelle Aggregation als Optimierung ab ~150 Tagen vorgemerkt.
- Renditen aus der konsistent adjustierten Historie desselben Downloads (nicht aus gespeichertem p0 — Dividenden-Readjustierung würde sonst verzerren; p0 bleibt Dokumentation).
- **tr-Backup (§7.3 RUNBOOK):** samstäglicher Export aller `tr:*`-Keys nach `backups/tr_backup_latest.json`, per Workflow committet — die Git-History ist das Archiv.

## 10. Changelog
- v1.2 (03.07.2026): Phase B deployed (Evaluator, tr:stats, tr-Backup); Implementierungsnotizen ergänzt.
- v1.1 (03.07.2026): §9-Entscheidungen fixiert; Phase B+ (Backtest-Modus) mit Ehrlichkeits-Auflagen ergänzt. Phase A deployed mit Aggregator v4.4 — Tag 0 = Handelstag 02.07.2026.
- v1.0 (03.07.2026): Erstfassung nach Konzept-Session.
