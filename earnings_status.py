#!/usr/bin/env python3
"""
earnings_status.py — Zustand der Earnings-Information je Ticker (SUITE №72, P1 #3, Schritt 1, v5.47.0)
=====================================================================================================
Macht sichtbar, WARUM `earningsDTE` leer ist oder nichts aussagt. Rein additiv: `earningsDTE`, Scores, Gates,
Leaderboards und Kandidatenauswahl bleiben unveraendert (D16: `None` bedeutet "nicht abgefragt", nicht "keine Earnings").

Zustaende (intern, Feld `earningsStatus` je Ticker):
  KNOWN_FUTURE  Abfrage ok, Datum liegt in der Zukunft (DTE >= 1)
  STALE_PAST    Abfrage ok, Datum heute oder vergangen (DTE <= 0): der naechste Termin ist unbekannt
  NOT_QUERIED   Ticker wurde nicht abgefragt (200er-Grenze, Sektor-ETF/Krypto, Platzhalter)
  NO_DATE       Abfrage lief, die Quelle lieferte kein Datum
  LOOKUP_ERROR  Abfrage fehlgeschlagen (Ausnahme) oder Ergebnis nicht auswertbar

Oeffentlich (Generator) werden daraus KNOWN_FUTURE -> BLOCKED / IN_WINDOW_SOFT / NONE_IN_WINDOW und alle uebrigen
Zustaende -> UNKNOWN (kein belastbarer Termin). NONE_IN_WINDOW und UNKNOWN fallen nie zusammen.
"""
from typing import Any, Optional

KNOWN_FUTURE = "KNOWN_FUTURE"
STALE_PAST = "STALE_PAST"
NOT_QUERIED = "NOT_QUERIED"
NO_DATE = "NO_DATE"
LOOKUP_ERROR = "LOOKUP_ERROR"
ALL_STATES = (KNOWN_FUTURE, STALE_PAST, NOT_QUERIED, NO_DATE, LOOKUP_ERROR)

LOOKUP_OK = "OK"
LOOKUP_NO_DATE = "NO_DATE"
LOOKUP_ERR = "ERROR"


def classify_earnings(queried: bool, lookup: Optional[str], dte: Any) -> str:
    """queried: wurde der Ticker abgefragt? lookup: 'OK'|'NO_DATE'|'ERROR'|None (Ergebnis von compute_earnings_calendar).
    dte: earningsDTE (int oder None)."""
    if not queried:
        return NOT_QUERIED
    if lookup == LOOKUP_ERR:
        return LOOKUP_ERROR
    if lookup == LOOKUP_NO_DATE:
        return NO_DATE
    if lookup == LOOKUP_OK or lookup is None:
        if isinstance(dte, bool) or not isinstance(dte, int):
            # abgefragt, aber kein auswertbares Datum
            return NO_DATE if (dte is None and lookup is None) else LOOKUP_ERROR
        return KNOWN_FUTURE if dte >= 1 else STALE_PAST
    return LOOKUP_ERROR
