# GEX-SCHEMA.md — UIQ GEX/Options-Struktur Datenschema

**Version:** v0.3
**Status:** Brainstorming-Ergebnis + Context-Inventur verifiziert, NOCH NICHT implementiert
**Datum:** 2026-07-10
**Ablageort:** `ahsub/ko-aggregator/docs/GEX-SCHEMA.md`

---

## 1. Zweck

Zentrales JSON-Schema für GEX-/Options-Strukturdaten als Ersatz für die tote
DIX/GEX-Quelle (SqueezeMetrics, HTTP 403). Dient gleichwertig:

1. **MB-Prompt-Input** — data-bound gemäß Palantir-Ansatz (keine Halluzination,
   Verdict wird konsumiert, nie vom LLM erzeugt)
2. **UIQ-Frontend-Visualisierung** — direkt renderbar ohne KI-Call
   (kompatibel mit `daily_market_snapshot`-Cache: Betatester lesen nur aus KV)

## 2. Herkunft / Inspirationsquellen

Destillat aus 7 analysierten Open-Source Pine-Scripts (Brainstorming-Session
2026-07-10):

| Schema-Element | Quelle |
|---|---|
| `meta.basisShift` | GEX Levels + BOS + AVWAP (ES/SPX/SPY-Konvertierung) |
| `levels[].volResilience` | Tiki Gamma (4-Tuple-Format) |
| `levels[].relStrength` | Tiki Gamma (peer-relative Stärke 0–100) |
| `profile[]` | GEX Levels + BOS (P:-Segment, vollständige Strike-Kurve) |
| `expiry{}` | Hardcoded GEX Levels (Expiry-Zeitscheiben) |
| `regime.score` | Prism Intelligence SPX (Confluence-Scoring 0–12) |
| `regime.signal` | Prism (State-Automat: sniper/caution/exit) |
| `verdict.pinForce` | SYNC & TRADE (ordinale Kategorie statt Scheinpräzision) |
| `verdict.text` regelbasiert | SYNC & TRADE + Prism kombiniert |
| Volume-Proxy-Fallback | Gamma Exposure (GEX) Levels (jmercado5671) |

## 3. Schema v0.2

```json
{
  "meta": {
    "symbol": "SPX",
    "asOf": "2026-07-10T14:00:00Z",
    "source": "quiver_quant | manual | proxy",
    "basisShift": 48.87
  },

  "regime": {
    "label": "CONSTRUCTIVE",
    "netGex": 1.391,
    "aboveFlip": true,
    "signal": "sniper_long | caution | exit | neutral",
    "score": { "total": 9, "max": 12 }
  },

  "levels": [
    {
      "price": 7599,
      "type": "CW",
      "relStrength": 92,
      "rawGex": 1365,
      "volResilience": 18
    }
  ],

  "profile": [
    { "strike": 7564, "gex": 3.3, "sign": 1 }
  ],

  "expiry": {
    "0dte": {
      "callGex1": { "price": 6772, "value": 8765 },
      "putGex1":  { "price": 6757, "value": -264837 }
    },
    "eow": {
      "callGex1": { "price": 6873, "value": 23254 },
      "putGex1":  { "price": 6757, "value": -279070 }
    },
    "full": {
      "callGex1": { "price": 7023, "value": 509436 },
      "putGex1":  { "price": 6020, "value": -356499 }
    }
  },

  "context": {
    "vix": 18.4,
    "pcr": 0.85,
    "move": 98.2,
    "termStructure": "contango"
  },

  "verdict": {
    "text": "Preis über HVL, Score 9/12 — Mean-Reversion-Regime aktiv.",
    "pinLevel": 7524,
    "pinForce": "med",
    "breakoutLevel": 7679,
    "supportLevel": 7474
  }
}
```

## 3b. Context-Erweiterung v0.3 (verifiziert gegen Aggregator v4.9)

Am 10.07. wurde parallel in einer zweiten Session Aggregator v4.9 um einen
kompletten Deep-Reasoning-Makro-Layer erweitert (Single-Source-of-Truth-
Snapshot, Z-Scores/Perzentile über 252 Handelstage, FRED-Makrodaten). Die
`context{}`-Sektion aus v0.2 sollte diese Felder mit aufnehmen statt eine
verkürzte Parallelstruktur zu pflegen:

```json
"context": {
  "vix":            18.4,
  "vixZScore":       -0.60,
  "vixPercentile":    28,
  "pcr":              0.85,
  "pcrSource":        "vix_proxy",
  "move":            98.2,
  "moveZScore":       -0.21,
  "termStructure":   "contango",
  "skewVvixDivergence": {
    "value":  1.79,
    "signal": "WARNUNG: institutionelles Tail-Hedging bei ruhiger Oberfläche"
  },
  "hySpread":         2.7,
  "netLiquidity":     5955.8,
  "netLiquidityTrend": "EXPANDIEREND",
  "yieldCurve10y2y":  0.35,
  "yieldCurveInverted": false
}
```

**Wichtig:** `pcrSource` ist zwingend, nicht optional — der PCR-Wert im
Aggregator ist aktuell ein VIX/VVIX-Proxy (`source: "vix_proxy"`), kein
echter CBOE-Put/Call-Ratio (CBOE liefert HTTP 403 von GitHub Actions aus).
Ohne `pcrSource`-Flag würde das GEX-Schema denselben Fehler wiederholen,
den die Woche an anderer Stelle bereits aufgedeckt hat: eine Proxy-Zahl,
die wie eine echte Kennzahl aussieht.

## 4. Feldbeschreibungen

### meta
- **symbol** — Underlying (SPX, SPY, QQQ, …)
- **asOf** — ISO-8601-Zeitstempel UTC; Staleness-Erkennung >24h analog Tiki Gamma
- **source** — Datenherkunft, bestimmt Vertrauensstufe:
  `quiver_quant` (echte Daten) > `manual` (Paste) > `proxy` (approximiert)
- **basisShift** — Spot→Futures-Offset (ES/SPX), 0 = kein Shift

### regime
- **label** — `CONSTRUCTIVE | CONTESTED | TRANSITIONAL | BEARISH`
- **netGex** — Netto-Dealer-Gamma in Mrd. USD (Vorzeichen = Regime-Charakter)
- **aboveFlip** — Preis über Zero-Gamma/HVL (deterministisch berechnet)
- **signal** — regelbasierter State-Automat (siehe §5), NIE vom LLM erzeugt
- **score** — Confluence-Score; Komponenten-Aufschlüsselung ab v0.3 optional

### levels[]
- **type** — `CW | PW | ZG | MP | EH | EL` (Registry-Enum, erweiterbar)
- **relStrength** — 0–100, peer-relativ innerhalb der Kategorie (100 = stärkstes)
- **rawGex** — absolute GEX-Magnitude in Mio. USD (produktspezifisch, nur
  innerhalb desselben Symbols vergleichbar)
- **volResilience** — -100…+100; positiv = Level verstärkt sich bei IV-Expansion

### profile[]
- Vollständige Strike-Kurve (nicht nur Top-Levels); `sign` redundant zu
  Vorzeichen von `gex`, aber explizit für einfaches Frontend-Filtering

### expiry
- Minimalset: `0dte / eow / full` — bewusste Reduktion von 7 auf 3 Scheiben
  (Kosten: API-Calls, KV-Speicher, Prompt-Tokens). Erweiterung um
  `1dte / eom / nw / nm` nur bei konkretem Use Case.

### context (v0.3)
- **vix, vixZScore, vixPercentile** — Rohwert + 252T-Kontext, direkt aus
  `market.vixTerm` + `market.zscores.vix` übernehmbar (Aggregator v4.9)
- **pcr, pcrSource** — `pcrSource` zwingend (`vix_proxy | cboe`), siehe §3b
- **move, moveZScore** — aus `market.moveIndex` (Aggregator v4.9)
- **termStructure** — aus `market.vixTerm.structure`
- **skewVvixDivergence** — aus `market.zscores.skew_vvix_divergence`, sofern
  vorhanden (nicht immer signifikant genug für ein Signal)
- **hySpread, netLiquidity, netLiquidityTrend** — aus `market.fredMacro`
- **yieldCurve10y2y, yieldCurveInverted** — aus `market.fredMacro.yield_curve`
- Gestrichen ggü. v0.2-Annahme: NYMO, VRP, IVRank — weiterhin keine
  Datenquelle dafür im Aggregator, kein Marginalie-Ausbau ohne Bedarf

### verdict
- **text** — deterministisch vom Python-Aggregator generiert (Regelwerk),
  MB-Prompt konsumiert als Faktum. Testbar via pytest.
- **pinForce** — ordinale Kategorie `low | med | high` statt Scheinpräzision
- **breakoutLevel** — Level mit dynamischer Semantik: darunter = Bedingung,
  darüber = ausgelöst (Springboard-Konzept)

## 5. Verdict-Regelwerk (Skizze, v0.3-Aufgabe — weiterhin offen)

```
signal-Ableitung (deterministisch):
  score ≥ 9  AND aboveFlip AND uptrend  → sniper_long
  score 6–8  AND aboveFlip              → caution
  flipVerlust OR score < 6              → exit
  sonst                                 → neutral
```

Genaues Regelwerk inkl. `uptrend`-Definition und `text`-Templates:
eigene Design-Session vor Implementierung. Unverändert seit v0.2.

## 6. Datenquellen-Strategie (Fallback-Kaskade)

```
Prio 1: Quiver Quant API (~$20/mo, post-Monetisierung)  → source: quiver_quant
Prio 2: PCR als DIX-Proxy + OI-approximiertes GEX       → source: proxy
Prio 3: Volume-Ratio-Proxy (upVol-downVol)/totalVol     → source: proxy
        (aggregator-seitig in Python, NICHT im Frontend)
```

`source`-Feld macht die Vertrauensstufe für MB-Prompt und Frontend transparent.

**Ergänzung v0.3:** Diese Kaskade betrifft ausschließlich das eigentliche
GEX/Options-Struktur-Schema (§3). Der PCR-Proxy in `context.pcr` (§3b) ist
bereits produktiv in Aggregator v4.9 (`calc_pcr_proxy()`, VIX/VVIX-basiert)
— unabhängig von dieser Kaskade, schon heute nutzbar, nicht Teil der
"noch zu bauen"-Liste.

## 7. Offene Punkte vor Implementierung

1. ~~**Context-Inventur:** Welche Felder liefert Aggregator v4.9 wirklich?~~
   **✅ ERLEDIGT 10.07.2026** — verifiziert gegen Produktivcode:
   VIX ✓ (`vixTerm`), PCR ✓ (`pcr`, aber Proxy — siehe §3b), MOVE ✓
   (`moveIndex`). Zusätzlich vorhanden und in §3b/§4 aufgenommen: Z-Scores/
   Perzentile (252T), SKEW/VVIX-Divergenz, HY-Spread, Net Liquidity
   (+Trend), echte 10J-2J-Zinskurve (FRED).
2. **Expiry-Beschaffbarkeit:** Liefert Quiver Quant expiry-granulare GEX-Daten
   oder nur Aggregat? Bestimmt, ob `expiry{}` in v1 realisierbar ist.
   *(weiterhin offen — externe API-Doku-Prüfung nötig)*
3. **Ablage:** Eigenes `ko-gex.json`-Modul in ko-modules vs. Integration in
   `ko-indicators.json`-Registry — Entscheidung ausstehend.
   *(Hinweis: `ko-indicators.json` wurde am 10.07. bereits um zwei tote
   Einträge bereinigt (`pcr_z`, `gex_proxy` — Registry v1.0.1). Bei
   Integrations-Entscheidung für dieses Schema relevant, da genau diese
   beiden Einträge konzeptuell durch ein sauberes GEX-Schema ersetzt würden.)*
4. **Verdict-Regelwerk:** Detaillierung §5 in eigener Session. *(weiterhin offen)*
5. **ko-darkpool.js-Migration:** Bestehender Placeholder-Status →
   Schema-Anbindung. *(Hinweis: ko-darkpool.js wurde am 10.07. bereits in
   einer separaten Entscheidung angepasst — DIX/GEX-Volumen-Heuristik dort
   ehrlich umbenannt, runtergewichtet [50%→15%] und aus KI-Prompts
   ausgeschlossen, Option B/Axel-Entscheidung. Dieses Schema hier wäre der
   langfristige Ersatzpfad für genau diese Heuristik, sobald Prio 1 oder 2
   der Datenquellen-Kaskade steht.)*

## 8. Versionierung

| Version | Datum | Änderung |
|---|---|---|
| v0.1 | 2026-07-10 | Erster Entwurf (7 Expiry-Scheiben, 7 Context-Felder) |
| v0.2 | 2026-07-10 | Eindampfung: 3 Expiry-Scheiben, 4 Context-Felder, pinForce nur in verdict, Verdict-Generierung deterministisch festgelegt |
| v0.3 | 2026-07-10 | Context-Inventur (§7.1) gegen Aggregator v4.9 verifiziert und abgeschlossen; `context{}` um 9 Felder erweitert (Z-Scores, SKEW/VVIX-Divergenz, FRED-Makro, echte Zinskurve) statt Parallelstruktur; `pcrSource`-Feld als Pflichtfeld ergänzt (Proxy-Transparenz); Querverweise zu parallel abgeschlossener ko-indicators.json-Bereinigung und ko-darkpool.js-Heuristik-Entscheidung ergänzt |
