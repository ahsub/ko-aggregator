# CBOE Volatilitäts-Datenquellen — VVIX/SKEW-Blocker-Fix

**Status:** Blocker aus "Top of mind" (VVIX/SKEW eingefroren seit 2026-07-17 via yfinance-internem Endpoint) behoben durch direkten CBOE-Download.
**Stand der Daten:** bis 2026-08-19 (lückenlos).
**Abgelegt:** Rohdaten in `ahsub/ko-aggregator/data/raw_data/`, aufbereitetes Master-Panel in `ahsub/ko-aggregator/data/cboe_vol_panel_daily.csv`.

## Quellen

| Datei | CBOE-Quelle | Abdeckung | Anmerkung |
|---|---|---|---|
| `VIX_History__1_.csv` | `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv` | 1990-01-02 – 2026-08-19 | OHLC. Bestätigt: direkt aus dem Seitenquelltext von cboe.com/tradable-products/vix/vix-historical-data ausgelesen. |
| `VVIX_History__1_.csv` | `https://cdn.cboe.com/api/global/us_indices/daily_prices/VVIX_History.csv` | 2006-03-06 – 2026-08-19 | Nur Close; VVIX existiert erst ab 03/2006. Bestätigt: dieselbe Seite wie VIX. |
| `SKEW_History.csv` | `https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv` | 1990-01-02 – 2026-08-19 | Nur Close. **Nicht explizit im Seitenquelltext verifiziert** — folgt dem bestätigten CDN-Muster von VIX/VVIX, mit hoher Wahrscheinlichkeit korrekt. Dashboard-Seite (ohne direkten CSV-Link gefunden): `https://www.cboe.com/us/indices/dashboard/skew/` |
| `skewtermstructure.csv` | `https://cdn.cboe.com/resources/indices/documents/skewtermstructure.csv` | 1990-01-02 – 2026-08-19 | SKEW je Expiration, mehrere Laufzeiten/Tag. **Bestätigt von Axel** (20.08.2026) — liegt unter einem anderen CDN-Pfad (`/resources/indices/documents/`) als die übrigen drei Reihen (`/api/global/us_indices/daily_prices/`) und war über die normale Website-Navigation/Suche nicht auffindbar. |

**Rechercheweg (zur Nachvollziehbarkeit):** VIX/VVIX-URLs wurden am 20.08.2026 per Claude-in-Chrome-Browsersteuerung direkt aus dem Seitenquelltext der offiziellen CBOE-Historical-Data-Seite ausgelesen (nicht geraten). Die SKEW-Term-Structure-URL war über Website-Navigation, CBOE-interne Suche und Google-Suche (`site:cboe.com skewtermstructure.csv`) nicht auffindbar — sie liegt offenbar nicht unter dem regulären Produkt-/Dashboard-Menü, sondern unter einem separaten Dokumenten-CDN-Pfad, und wurde von Axel direkt beigesteuert.

## Bekannte Datenqualitäts-Punkte

- **VIX 1990 (frühe Historie):** OPEN=HIGH=LOW=CLOSE identisch an vielen frühen Handelstagen — damals nur ein Tageswert veröffentlicht, kein echtes Intraday-OHLC. Bei ATR/Range-Features auf Vor-2000-Daten berücksichtigen.
- **VVIX:** Reihe beginnt erst 2006-03-06 — kein Fehler, VVIX wurde erst ab dort berechnet.
- **skewtermstructure.csv:** 89 Zeilen mit fehlerhaftem Wert `"."` statt Zahl (bekanntes CBOE-Rohdatenproblem) — in der bereinigten Version als NaN behandelt und entfernt.
- **`skew_cm30` (konstante 30-Tage-Restlaufzeit):** an einzelnen Tagen NaN, wenn keine Expiration sowohl unter als auch über 30 Tagen DTE vorlag (Interpolation dann nicht möglich).

## Aufbereitung

Aus den vier Rohdateien wurde zusätzlich `skew_cm30_clean.csv` erzeugt: eine SKEW-Reihe mit konstanter 30-Tage-Restlaufzeit, linear zwischen den beiden nächstgelegenen Expirations interpoliert (analog zur Standard-VIX-Konstruktionsmethode) — methodisch sauberer als der rohe `SKEW_History`-Wert, der auf einer festen CBOE-internen Berechnung basiert, deren Laufzeit-Konvention nicht dieselbe sein muss wie eure sonstigen 30D-Vola-Features.

`cboe_vol_panel_daily.csv` = Outer-Join von VIX (OHLC), VVIX (Close), SKEW (Close), SKEW-CM30 auf gemeinsamer Tagesachse, ISO-Datumsformat.

## Refresh-Anleitung (nächstes Update)

Alle vier Reihen lassen sich direkt per Download-Link aktualisieren (kein Login nötig):

1. VIX: `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`
2. VVIX: `https://cdn.cboe.com/api/global/us_indices/daily_prices/VVIX_History.csv`
3. SKEW: `https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv` (Muster-basiert, siehe Anmerkung oben)
4. SKEW Term Structure: `https://cdn.cboe.com/resources/indices/documents/skewtermstructure.csv`
5. VIX3M: `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv`
6. DIX/GEX: `https://squeezemetrics.com/monitor/static/DIX.csv`
7. PUT-Index (CSP/Wheel-Proxy):	`https://cdn.cboe.com/api/global/us_indices/daily_prices/PUT_History.csv`	
8. BXM-Index (Covered Call-Proxy):	`https://cdn.cboe.com/api/global/us_indices/daily_prices/BXM_History.csv`
9. CLL-Index (Collar-Proxy):	`https://cdn.cboe.com/api/global/us_indices/daily_prices/CLL_History.csv`

Vorgehen: Link im Browser öffnen (lädt automatisch als CSV) → Datei ersetzt die alte in `data/raw_data/` unter demselben Namen → `python cboe_vol_loader.py` laufen lassen, um `cboe_vol_panel_daily.csv` neu zu bauen → `diagnose_coverage()`-Ausgabe auf Lückenfreiheit und aktuelles Enddatum prüfen, bevor die Daten produktiv genutzt werden.
