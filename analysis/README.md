# analysis/ — Regime-Analyse- und Backtest-Skripte

Dieser Ordner enthält Analyse-/Validierungsskripte rund um die Marktregime-
Klassifikation, getrennt vom Produktionscode in `market_aggregator.py`.
Nichts hier wird automatisch ausgeführt (kein GHA-Workflow) — alle Skripte
sind Stand-alone-Werkzeuge für Ad-hoc-Analysen.

## Dateien

- **`voranalyse_regime.py`** — Multivariate Voranalyse der Regime-Indikatoren
  (Korrelation/VIF, Random-Forest-Feature-Importance, Granger-Kausalität).
  Datenquellen: FRED (Konjunktur), yfinance (Markt-/Volatilitätsindizes),
  squeezemetrics (DIX/GEX-Vollhistorie seit 2011).

- **`regime_v2_backtest.py`** — Isolierter Test einer GEX<0-Zusatzregel zur
  Produktionsformel (VIX3M/VIX-Ratio). Importiert von `voranalyse_regime.py`
  — **muss im selben Ordner liegen**.

- **`deflated_sharpe_ratio.py`** — Eigenständige Funktion zur Berechnung der
  Deflated Sharpe Ratio (Mehrfachtest-Korrektur für Backtest-Ergebnisse,
  nach Bailey & López de Prado 2014). Unabhängig von den beiden anderen
  Dateien nutzbar.

- **`VALIDIERUNGSLAUF-2026-08-18.json`** — Tatsächliche Ausgabe von
  `regime_v2_backtest.py` aus dem lokalen Testlauf mit Axel am 18.08.2026,
  inkl. direktem Abgleich gegen die bereits dokumentierten Ergebnisse aus
  `docs/REGIME-BACKTEST-VALIDIERUNG.md`. Siehe Abschnitt "Validierungsstatus"
  unten für die Kurzfassung.

## Wichtiger Hinweis zum Entstehungskontext

`voranalyse_regime.py` und `regime_v2_backtest.py` wurden ursprünglich am
18.08.2026 in einer Chat-Session gebaut und live gegen echte Daten
verifiziert — aber **nie committed**. Die hier vorliegenden Versionen sind
eine **nachträgliche Rekonstruktion aus dem Chat-Verlauf** (18.08.2026,
Folge-Session), da das Original nicht mehr auffindbar war.

Jede Datei enthält am Ende einen Kommentarblock mit einer ehrlichen
Konfidenz-Einstufung pro Funktion/Abschnitt:

- **Hohe Konfidenz** — wörtlich aus dem Chat-Verlauf rekonstruiert (teils
  zusätzlich durch echte Fehlerlogs derselben Session bestätigt, z.B. die
  FRED-Series-IDs in `voranalyse_regime.py`)
- **Mittlere Konfidenz** — aus Verwendungsmustern/späteren Bugfix-Sessions
  abgeleitet, nicht wörtlich verifiziert
- **Lücken** — nicht rekonstruierbar (z.B. die drei Kern-Analysefunktionen
  in `voranalyse_regime.py` sowie `main()` fehlen komplett)

**Validierung:** Beide Dateien wurden am 18.08.2026 gemeinsam mit Axel lokal
mit echten Daten getestet. Details und Ergebnisse siehe Abschnitt
"Validierungsstatus" unten sowie `VALIDIERUNGSLAUF-2026-08-18.json`.

## Validierungsstatus (18.08.2026)

Lokaler Testlauf gegen echte FRED-/yfinance-/squeezemetrics-Daten
durchgeführt. Dabei wurden zwei echte Fehler gefunden und behoben:

1. **`fetch_yf_series()` in `voranalyse_regime.py`:** `yf.download()`
   lieferte für den Ticker `^VIX3M` nur 1 Zeile statt der vollen Historie.
   Fix: Umstellung auf `yf.Ticker(ticker).history()`.
2. **`analysis_b_separation()` in `regime_v2_backtest.py`:** Sortierrichtung
   für den Monotonie-Check war für Max-Drawdown-Metriken invertiert
   (negative Werte, "riskanter" = numerisch kleiner statt größer).

Nach beiden Fixes: Panel mit 3826 Handelstagen (2011-05-02 bis
2026-08-18). Die 2022-Kernzahlen (Handelstage, Reklassifizierungsrate,
Forward-Drawdowns) und 3 von 4 Trennschärfe-Monotonie-Flags stimmen
exakt bzw. nahezu exakt mit den bereits dokumentierten Ergebnissen aus
`docs/REGIME-BACKTEST-VALIDIERUNG.md` überein. Eine einzelne Flag
(`fwd_vol_21d_monotonic_as_expected`) weicht leicht ab (v1=false,
v2=true statt in beiden Versionen identisch) — ändert nichts an der
Kernschlussfolgerung. Details: `VALIDIERUNGSLAUF-2026-08-18.json`,
Abschnitt `validierung_gegen_original_dokumentation`.

**Für neue Testläufe:** Ergebnis gegen die bereits vorliegenden
Ergebnisdateien (`~/voranalyse_output/`, `~/regime_v2_output/`,
insbesondere `regime_v1_v2_panel.csv` und `summary_regime_v2.json`)
abgleichen. Bei Abweichungen gilt die lokale Ergebnisdatei als
maßgeblich — nicht der rekonstruierte Code.

## Bereits gesichertes Ergebnis (unabhängig vom Rekonstruktionsstatus)

Die inhaltliche Kernaussage aus der Original-Session ist unabhängig von
dieser Code-Rekonstruktion bereits dokumentiert in
`docs/REGIME-BACKTEST-VALIDIERUNG.md`, Nebenfund 3:

GEX<0 als starrer Zusatz-Schwellenwert wurde **nicht** in
`market_aggregator.py` übernommen. Die Monotonie-Flags (Trennschärfe nach
Forward-Volatilität/Max-Drawdown) waren für v1 und v2 identisch — GEX
veränderte die Trennschärfe nicht messbar. GEX bleibt als Feature-
Importance-Kandidat (Rang 2, hinter VVIX) dokumentiert, aber ohne
konkrete Umsetzung als starre Einzelschwelle.

## Nächster sinnvoller Schritt

Aus `docs/BACKLOG-MARKETSTATE-2026-08-18.md`: Rolling/Online-HMM als
zusätzlicher Regime-Klassifikator (Eintrag 1) — vor Umsetzung erst prüfen,
ob die aktuelle Produktionsklassifikation überhaupt ein Look-Ahead-Problem
hat, das ein rollierendes Modell lösen würde.
