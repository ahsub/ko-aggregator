#!/usr/bin/env python3
"""
dce_public.py — Öffentliche DCE-Marktdiagnostik (ADR-1, Stufe 1) und Trennung vom internen Objekt
==================================================================================================
SUITE №72 / Runmap 2 (Batch 1b, Nacht A). Version 1.0 (30.09.2026).

Aufgabe (nur Feldfluss, KEINE Änderung der Messlogik):
  * build_dce_public(dce, as_of)  — enges Whitelist-Schema, serverseitig erzeugt.
  * split_public_master(master)   — Kopie von master OHNE internes `dce` und OHNE
                                    meta.dce_cusum_buffer; mit `dce_public`.

Entscheidungen (Axel + Review, 30.09.2026):
  E1  Stufe 1 = nur Signalbreite. CUSUM und VaR öffentlich `n/v` mit Ursache; keine Korrektur, keine
      Umdefinition (eigenes Paket mit Präregistrierung, SUITE №75).
  E2  Internes Objekt geht nach KV-Key `dce_internal` (Worker-Route GET /owner/dce, nur Owner-Token).
  E4  Fallback-Dict wird intern mit `fallback: true` gekennzeichnet und NIE als Signal veröffentlicht.

Nicht öffentlich (nie in dce_public): confidence, mode/Ampel, direction, position_size, warnings, regime_probs,
divergences, var_95, cusum_alarm, cusum_buffer.
"""
from typing import Any, Dict, Optional

SCHEMA = "dce_public/1"
SIGNAL_THRESHOLD = 55  # entspricht `s > 0.55` in dce_layer._aggregate_ticker_signals (Werte /100)

# Whitelist der Top-Level-Schlüssel von dce_public (Test prüft exakt diese Menge)
PUBLIC_KEYS = {"schema", "as_of", "generated", "signal_breadth", "cusum", "var"}

REASON_CUSUM = "Implementierung derzeit nicht funktionsfähig"
REASON_VAR = "bestehender EVT-Zweig nicht aktiv"

# Schlüssel, die im öffentlichen Master nirgends aus dem internen DCE-Objekt stammen dürfen
INTERNAL_MASTER_KEY = "dce"
INTERNAL_META_KEY = "dce_cusum_buffer"


def _nv(reason: str) -> Dict[str, Any]:
    return {"status": "n/v", "reason": reason}


def _signal_breadth(dce: Optional[Dict]) -> Dict[str, Any]:
    if not isinstance(dce, dict) or not dce:
        return _nv("DCE-Berechnung nicht verfügbar")
    if dce.get("fallback") is True:
        return _nv("DCE-Berechnung fehlgeschlagen (Fallback aktiv)")
    agg = dce.get("aggregated")
    if not isinstance(agg, dict) or not agg:
        return _nv("Ticker-Aggregation nicht verfügbar")
    n = agg.get("n")
    bull = agg.get("bullish_pct")
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0 or bull is None:
        return _nv("keine auswertbaren Titel")
    try:
        bull = float(bull)
    except (TypeError, ValueError):
        return _nv("ungültiger Wert")
    if not 0.0 <= bull <= 1.0:
        return _nv("ungültiger Wert")
    return {
        "status": "ok",
        "share_pct": round(bull * 100, 1),
        "n": n,
        "threshold": SIGNAL_THRESHOLD,
        "definition": (
            f"Anteil der ausgewerteten Titel, deren Mittelwert der jeweils verfügbaren Scores "
            f"(sMinervini, sSwing, sBreakout, confluenceScore) über {SIGNAL_THRESHOLD} liegt. "
            f"Beschreibt die Breite der Signale, keine Kauf- oder Erfolgswahrscheinlichkeit."
        ),
    }


def build_dce_public(dce: Optional[Dict], as_of: Optional[str] = None,
                     generated: Optional[str] = None) -> Dict[str, Any]:
    """Enges Ausgabeschema. Liest aus dem internen Objekt ausschließlich aggregated.n / aggregated.bullish_pct."""
    return {
        "schema": SCHEMA,
        "as_of": as_of,
        "generated": generated,
        "signal_breadth": _signal_breadth(dce),
        "cusum": _nv(REASON_CUSUM),
        "var": _nv(REASON_VAR),
    }


def split_public_master(master: Dict[str, Any]) -> Dict[str, Any]:
    """Flache Kopie von master für Datei/KV/Digest: ohne internes `dce`, ohne meta.dce_cusum_buffer, mit `dce_public`.
    master selbst wird nicht verändert (das private Archiv behält das volle Objekt)."""
    meta = master.get("meta") if isinstance(master.get("meta"), dict) else {}
    pub = {k: v for k, v in master.items() if k != INTERNAL_MASTER_KEY}
    if "meta" in pub and isinstance(pub["meta"], dict):
        pub["meta"] = {k: v for k, v in pub["meta"].items() if k != INTERNAL_META_KEY}
    pub["dce_public"] = build_dce_public(
        master.get(INTERNAL_MASTER_KEY),
        as_of=meta.get("last_trading_day"),
        generated=meta.get("generated"),
    )
    return pub
