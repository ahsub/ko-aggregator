# analysis/regime_compare/ — Faire Neuvalidierung regime_v1 vs. regime_v2 vs. 5-Faktor-Modell

**Session:** 23.08.2026. **Ergebnis:** s. Nachtrag in
`UIQ-Suite/docs/REGIME-BACKTEST-VALIDIERUNG.md`.

## Anlass

Drei konkurrierende Regime-Berechnungen existierten im UIQ-Ökosystem
(`market_regime_str` [Server], `determine_mse_regime()` [Server-Python-Port],
`KoMarketState.determineRegime()` [Client]) — bislang nie auf identischer
Datenbasis/Methodik verglichen. Die oft zitierte "Sharpe 1,66"-Validierung
gehört zu einem unabhängigen Backtest (DCE-Score-Ranking) und ist **keine**
Regime-Validierung — diese Korrektur ist ebenfalls im Nachtrag dokumentiert.

## Voraussetzung: Rohdaten

Alle vier Skripte lesen ausschließlich aus `../../data/raw_data/` (relativ
zu diesem Ordner, d.h. `ko-aggregator/data/raw_data/`) — keine Live-API-Calls:

- `VIX_History.csv`, `VIX3M_History.csv`, `VVIX_History.csv`,
  `SKEW_History.csv` (CBOE-CDN)
- `DIX_GEX_History.csv` (SqueezeMetrics-Bulk-Export)
- `PUT_History.csv`, `BXM_History.csv`, `CLL_History.csv` (CBOE-Strategie-Indizes,
  nur für `economic_test.py` nötig)

Alle diese Dateien waren zum Zeitpunkt dieser Session bereits im Repo
committed (s. Chatverlauf 23.08.2026).

## Ablaufreihenfolge

```
python3 build_panel.py        # Vereinheitlichtes Tagespanel (unified_panel.csv)
python3 classify.py           # Beide Modelle klassifizieren (classified_panel.csv)
python3 separation_test.py    # Forward-Vol/Max-Drawdown-Trennschärfe (separation_result.json)
python3 economic_test.py      # Sharpe-artige Kennzahl mit echten CBOE-Strategie-Indizes (economic_result.json)
python3 dsr_check.py          # Deflated Sharpe Ratio, echte n_trials=3 (dsr_result.json)
```

Jedes Skript ist auch einzeln ausführbar (importiert die vorherigen Module
bei Bedarf selbst). `dsr_check.py` braucht zusätzlich
`../deflated_sharpe_ratio.py` (bereits vorhanden in `analysis/`).

## Wichtige methodische Einschränkung

`separation_test.py` nutzt SPX-Forward-Vol/Max-Drawdown (aus der `price`-Spalte
in `DIX_GEX_History.csv`) als Risikoproxy — nicht die ökonomisch aussagekräftigeren
CBOE-Strategie-Indizes. Für die eigentliche Entscheidungsgrundlage zählt
`economic_test.py` (echte PUT/BXM/CLL-Indizes, identische Methodik wie die
ursprüngliche 10.08.2026-Validierung des 5-Faktor-Modells).

## Reproduzierbarkeits-Historie

Diese Skripte fehlten zunächst im Nachtrag von `REGIME-BACKTEST-VALIDIERUNG.md`
(dort stand fälschlich, sie lägen bereits hier — s. Korrektur-Vermerk dort,
23.08.2026). Mit diesem Commit ist die Lücke geschlossen.
