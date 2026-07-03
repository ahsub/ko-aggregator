# Investment-Suite — Dachdokument

**Version:** 1.0
**Stand:** 03.07.2026
**Ablage:** `ahsub/ko-aggregator/docs/SUITE.md`
**Geltung:** Verbindlich für alle Suite-Module. Bei Widerspruch zwischen diesem Dokument und einer Modul-STRATEGIE gilt: Grundgesetze und Konsistenz-Standards aus SUITE.md schlagen Modul-Regeln; fachliche Modul-Spezifika bleiben Sache der Module.
**Fortschreibung:** Claude, versioniert, analog den Modul-Strategiedokumenten.

---

## 1. Zielbild: Der geschlossene Anlegerzyklus (3 + 2)

Die Suite bildet den vollständigen Lebenszyklus eines selbstentscheidenden Privatanlegers ab — jedes Modul besetzt genau eine Phase, kein Modul überlappt:

| Phase | Modul | Repo | Status |
|---|---|---|---|
| **Entscheiden** | UnderlyingIQ — Regime → Strategie → Underlying → Instrument | `ko-aggregator` (App: `axel-scanner`) | Produktiv (underlyingiq.com) |
| **Bewirtschaften** | Premium Options — steuerbewusster Options-Doktor | `premium-options` | Sanierung (P1) vor Publikation |
| **Abrechnen** | Refundex — Anlage KAP + Quellensteuer-Rückholung | `refundex` | Öffentliche Beta |
| **Bilanzieren** | DepotIQ *(Arbeitstitel)* — Strategie-Bilanz netto EUR nach Steuer, Risiko-Cockpit; die Rückkopplung, die den Zyklus schließt | — | Zukunftsprojekt, hohe Prio |
| **Vorsorgen** | Ruhestandsmodul — Entnahmeplanung | — | Zukunftsprojekt, hohe Prio; StBerG-sensibelstes Modul der Suite, eigenes Gate zwingend |

**Der Kreislauf-Gedanke:** Bilanzieren füttert Entscheiden — die ehrliche Netto-EUR-Bilanz je Strategie ist der Input für die nächste Strategie-Router-Entscheidung. Erst mit DepotIQ wird aus der Werkzeugkiste ein lernendes System.

---

## 2. Suite-Grundgesetze (konsolidiert, für alle Module verbindlich)

1. **Streng-modularer Aufbau.** Kein Modul kennt Interna eines anderen; Austausch nur über definierte Kontrakte (JSON-Schemata, ko-* Suite-Module). Fachlogik, die zwei Module brauchen, lebt in genau **einem** Suite-Modul.
2. **ES6-Zielarchitektur.** Neuer Code ausschließlich ES6-konform (const/let, Arrow Functions, zentrale String-Objekte, keine Inline-Handler, JSDoc). Monolithen werden schrittweise migriert, nie big-bang.
3. **80/20-Vorbehalt.** Jedes Feature nur, wenn ≤ 20 % Aufwand ≥ 80 % Nutzerwert liefern. Randfälle werden dokumentierte Grenzen, keine Features.
4. **No-Hallucination auf allen Ebenen.** Zahlen entstehen deterministisch aus Daten + belegten Konstanten (GZ, Norm, Preisliste mit Standdatum). KI erklärt und formuliert — sie rechnet, schätzt und zitiert nie ohne Quelle. Näherungen sind sichtbar markiert (~). Gilt auch fürs Marketing („verifiziert" nur nach echtem Lauf).
5. **Compliance by Design im Public-Bereich.** Je Modul die einschlägige Schranke: WpHG/BaFin (UIQ, PO — Public/EIC-Split, „Statistische Kontext-Analyse"), StBerG (Refundex, PO, künftig Ruhestand — Rechenwerk mit Szenarien nebeneinander, nie Ratschlag). Empfehlungssprache existiert ausschließlich hinter dem EIC-PIN.
6. **Datensouveränität.** Browser-first; Depot- und Steuerdaten verlassen den Rechner des Nutzers nicht. Kein Suite-Server hält Nutzerdaten.
7. **Belegkette.** Jeder ausgewiesene Wert ist rückführbar auf Datenzeile, Modul und Rechts-/Datenquelle.
8. **Governance-Muster.** Jedes Modul führt `docs/STRATEGIE.md` + `docs/ROADMAP.md` (versioniert, Fortschreibung Claude), Entscheidungen laufen durch den Vier-Fragen-Filter (Belegkette / 80-20 / ES6-Modularität / Compliance). Deploy nach Zwei-Vorgänge-Prinzip: GitHub = Quellcode, Cloudflare-Pages-Zip = Publikation.

---

## 3. Konsistenz-Standards — „wie aus einem Guss"

Konsistenz ist Governance, nicht Geschmack: Divergenz entsteht, wo es keine verbindliche Quelle gibt. Deshalb gilt für vier Ebenen das **Single-Source-Prinzip** — je Ebene existiert genau eine Quelle, alle Apps konsumieren sie.

### 3.1 Terminologie-Standard (eine Sprache)

Ein zentrales, versioniertes **Suite-Glossar** definiert jeden fachlichen Begriff genau einmal — Bezeichnung, Definition, ggf. verbotene Alt-Bezeichnung:

| Begriff (verbindlich) | Definition | Verboten/Altlast |
|---|---|---|
| atmna-Systematik | Stillhalter-Regelwerk (Checkliste, 3-Stufen-Roll) | „Ludwig" (Namensrecht; UIQ bereinigt, PO offen → P1.1) |
| Statistische Kontext-Analyse | Public-Output aller Analyse-Features | „Handlungsempfehlung", „Empfehlung" (nur EIC) |
| EIC-Modus | PIN-gated Expertenbereich, suiteweit ein Konzept | app-eigene Bezeichnungen |
| Regime-Namen | BULL_QUIET, BULL_FRAGILE, STRESS_UNSTABLE, POST_CRACK_REVERSION | freie Übersetzungen im UI ohne Glossar-Eintrag |
| Ampel-Status | OK / WATCH / ROLLEN / DRINGEND (PO-Doktor); Break-even-Ampel grün/rot (Refundex QSt) | abweichende Stufenzahl je App |
| Verlusttöpfe | Allgemein / Aktien / Termingeschäfte (+ 20k-Cap) | umgangssprachliche Mischbegriffe |
| Belegkette, Recherche-Gate, Suite-Modul | wie in den Strategiedokumenten definiert | — |

**Regel:** Neue Begriffe werden erst ins Glossar eingetragen, dann im Code/UI verwendet. Das Glossar startet als Abschnitt dieses Dokuments und wandert bei Wachstum nach `suite-core/glossar.md`.

### 3.2 Regelwerk-Einheit (eine Wahrheit je Fachfrage)

Jede fachliche Beurteilungsregel existiert genau **einmal**, implementiert in einem ko-Suite-Modul, konsumiert von allen Apps:

| Fachfrage | Single Source | Konsumenten |
|---|---|---|
| IV-Rank-Schwellen (z. B. Skip < 25 %) | ko-Modul (Ziel: ko-scoring o. ä.) | UIQ, PO |
| FIFO / EUR-Umrechnung / Töpfe / 20k-Cap | ko-fifo, ko-fx, (Topf-Logik als Suite-Modul, ROADMAP Refundex 2.1 / PO 2.3) | Refundex, PO, künftig DepotIQ |
| DBA-Sätze, Voucher-Kosten, Fristen | ko-dba + versionierte Referenztabellen mit Standdatum | Refundex, künftig DepotIQ |
| Regime-Erkennung, Scoring | ko-market-state, ko-scoring, ko-strategies | UIQ, perspektivisch PO (Markt-Tab) |
| Ampel-Schwellwerte (ITM-%, DTE) | zentrale Konstanten-Objekte im jeweiligen ko-Modul, nie hart im UI | PO |

**Regel:** Findet sich dieselbe Schwelle/Formel in zwei Apps, ist das ein Bug — Konsolidierungs-Item in die nächste Roadmap-Fortschreibung.

### 3.3 Prompt-Bibliothek (ein Prompt je Frage-Typ)

KI-Prompts sind Regelwerk und werden wie Code behandelt: zentral, versioniert, mit Public-/EIC-Variante je Frage-Typ — nie app-individuell formuliert.

- **Struktur:** `suite-core/prompts/` (bzw. bis dahin ko-modules) mit z. B. `position-analyse.public.md`, `position-analyse.eic.md`, `strategie-erklaerung.public.md`, `briefing.eic.md` — inkl. Versionskopf und Änderungshistorie.
- **Bau-Regeln für jeden Suite-Prompt:** (1) Rollendefinition ohne geschützte Namen; (2) Public-Prompts enthalten strukturell keinen Empfehlungsauftrag — nicht nur eine Bitte um Zurückhaltung; (3) Strict-Source: „Verwende ausschließlich die mitgelieferten Zahlen; erfinde keine Werte, Quellen oder Paragraphen; kennzeichne fehlende Daten als fehlend"; (4) Ausgabeformat und Maximallänge definiert; (5) deutsche Fachbegriffe gemäß Glossar 3.1.
- **Regel:** Ein neuer KI-Einsatzzweck beginnt mit einem Bibliothekseintrag, nicht mit einem Inline-String im App-Code.

### 3.4 Design-System (ein Erscheinungsbild)

Ziel: Ein Nutzer, der von UIQ zu Refundex wechselt, muss nichts neu lernen — gleiche Farben, gleiche Interaktionsmuster, gleiche Anordnungslogik.

- **Design-Tokens:** Ein zentrales `:root`-Token-Set (Farben, Radius, Mono-Font, Ampelfarben) als `suite-core/tokens.css`; Referenz-Kandidat ist das Refundex-Set (bg/bg2/bg3, border, text/muted, accent, green/amber/red). ⚠️ **Vor Festschreibung: Bestandsaufnahme der UIQ- und PO-Tokens** (Konsolidierungs-Item, kein Blindtausch).
- **UI-Muster-Katalog (verbindliche Bausteine):** Beta-/Status-Banner mit aufklappbarem Haftungsblock (Muster: Refundex v139); EIC-PIN-Dialog (Muster: UIQ); Scanner-/Positions-Karten mit einheitlicher Anatomie (Titel · Status-Badge · Kennzahlen · Aktionen rechts unten); Ampel-Badges; Hilfe-Zugang einheitlich (❓ oben rechts, modales Fenster, Markdown-Module); Disclaimer-Vier-Punkte-Struktur.
- **Usability-Konventionen:** Primäraktion je Ansicht genau ein farbiger Button (accent), destruktive Aktionen nie primär gefärbt und nie ohne Bestätigung; Dropdowns für Auswahl, Buttons für Aktionen — nie gemischt; identische Reihenfolge wiederkehrender Elemente über Apps hinweg (z. B. Feedback/Bug/Schließen im Banner); Zahlen rechtsbündig in Mono; ~ kennzeichnet suiteweit Näherungswerte.
- **Regel:** Neues UI wird gegen den Muster-Katalog gebaut; ein neues Muster wird erst hier eingetragen, dann verwendet.

### 3.5 Umsetzungspfad der Konsistenz (realistisch, 80/20)

Konsistenz wird **nicht** als Big-Bang-Redesign erzwungen, sondern in drei Wellen: **(K1)** Dieses Dokument + Glossar-Kern gilt ab sofort für alles Neue. **(K2)** Bestandsaufnahme-Session: Token-, Begriffs- und Prompt-Inventur über die drei Apps, Abweichungsliste mit Prioritäten (Konsolidierungs-Backlog). **(K3)** Konsolidierung huckepack: Abweichungen werden im Zuge ohnehin anstehender Arbeiten bereinigt (z. B. PO-P1-Rename erledigt Glossar-Konformität gleich mit), nie als Selbstzweck-Deploy.

---

## 4. Suite-Portal (Zielbild, P-Item)

Eine gemeinsame Einstiegsseite als Klammer nach außen: die vier/fünf Module mit Ein-Satz-Beschreibung, gemeinsames Design-Token-Set, ein EIC-Login-Konzept, und die Suite-Prinzipien (Belegkette, No-Hallucination, Datensouveränität) als öffentliches Qualitätsversprechen — sie sind das Verkaufsargument an die Zielgruppe, nicht nur Interna. Voraussetzung: K2-Bestandsaufnahme und Namens-/Domainfragen (siehe Refundex-Backlog) geklärt.

---

## 5. Offene Suite-Entscheidungen (Backlog)

1. **Heimat von `suite-core`** (tokens.css, prompts/, glossar.md): eigenes Repo vs. ko-modules-Erweiterung — Entscheidung bei K2.
2. **Suite-Name nach außen** (das Portal braucht einen Titel) — zusammen mit der Refundex-Namensrecherche (DENIC/DPMA) behandeln.
3. **DepotIQ-Gate** definieren, bevor Konzeptarbeit beginnt (u. a. Methodik-Recherche TWR vs. MWR mit Quellen).
4. **Ruhestandsmodul-Gate:** StBerG-Abgrenzung ist hier Existenzfrage — vor jeder Zeile Konzept.
5. Verlinkung dieses Dokuments aus den drei Modul-STRATEGIEs — bei deren jeweils nächster Fortschreibung (kein Extra-Push).

---

## Fortschreibungshistorie

| Version | Datum | Änderung |
|---|---|---|
| 1.0 | 03.07.2026 | Erstfassung: Zielbild 3+2 (inkl. DepotIQ und Ruhestandsmodul als Zukunftsprojekte hoher Prio), konsolidierte Grundgesetze, Konsistenz-Standards (Glossar, Regelwerk-Einheit, Prompt-Bibliothek, Design-System, K1–K3-Umsetzungspfad), Suite-Portal-Zielbild, offene Entscheidungen |
