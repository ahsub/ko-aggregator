"""
test_earnings_estimates_archive.py — v0.2 (23.09.2026)

CHANGELOG:
v0.2 (23.09.2026, Claude): sys.path-Fix — fruehere Fassung fuegte nur das
     eigene Verzeichnis (tests/) zum Pfad hinzu, das reichte fuer die
     Fixtures, aber nicht fuer den Import von earnings_estimates_archive.py
     selbst (liegt im Repo-Root, eine Ebene hoeher). In der urspruenglichen
     flachen Testumgebung (Skript+Test im selben Ordner) unbemerkt, erst
     beim Nachbau der echten ko-aggregator-Repo-Struktur als
     ModuleNotFoundError aufgefallen. Ausserdem: Flag-Namen in den
     Assertions bereits seit der vorherigen Fassung auf
     REPEATED_PLACEHOLDER/POSSIBLE_SPLIT_ARTIFACT/ZERO_VALUE_ANOMALY
     aktualisiert (Docstring-Version war dabei nicht mitgezogen worden).
v0.1 (23.09.2026, Claude): Erstfassung.

Testet die drei Sanity-Check-Detektoren gegen ECHTE Live-Daten aus der
Phase-0-Feasibility-Recherche (IBKR/MPC/NVDA, s. EARNINGS-INVEST-PHASE0-
FEASIBILITY.md Abschnitt 4). Keine synthetischen Fixtures — die Werte sind
Ausschnitte der tatsaechlichen Alpha-Vantage-Antworten vom 23.09.2026.

Bekannter, dokumentierter Befund beim Ausfuehren dieser Tests (KEIN Bug,
absichtlich nicht per Assert geprueft): der Split-Artefakt-Detektor markiert
bei MPC zusaetzlich zwei Stellen (2026-03-31), die vermutlich kein Split
sind, sondern echte Rohstoff-Volatilitaet (Crack-Spread-Schwankungen, s.
Feasibility-Report §14-Referenz). Der Detektor arbeitet rein statistisch
(Near-Integer-Verhaeltnis) und kann das aktuell nicht von einem echten Split
unterscheiden -- Refinement-Kandidat fuer Phase 2/3 (Abgleich gegen eine
echte Split-Kalenderquelle statt reiner Heuristik).

Ausfuehren (von ueberall, dank sys.path-Fix): python tests/test_earnings_estimates_archive.py
        oder: python -m pytest tests/test_earnings_estimates_archive.py -v
"""

import json
import os
import sys

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
# NEU (v0.2, Fund beim Verifizieren des echten Repo-Layouts, 23.09.2026):
# earnings_estimates_archive.py liegt im Repo-Root (neben market_aggregator.py,
# iv_layer.py), diese Testdatei + die Fixtures liegen in tests/. Das fruehere
# sys.path.insert() fuegte NUR tests/ hinzu — das reichte fuers Finden der
# Fixtures, aber NICHT fuer den Modul-Import selbst ("from
# earnings_estimates_archive import ..."), da das Skript eine Ebene hoeher
# liegt. Unbemerkt in der urspruenglichen flachen Testumgebung (Skript+Test
# im selben Ordner), erst beim Nachbau der echten Repo-Struktur aufgefallen
# (ModuleNotFoundError). Jetzt wird zusaetzlich das Repo-Root ergaenzt.
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _TESTS_DIR)
from earnings_estimates_archive import (
    detect_repeated_value, detect_split_artifact, detect_zero_row, run_sanity_checks,
)

FIXTURES_DIR = _TESTS_DIR


def _load(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def test_mpc_repeated_value_detected():
    """MPC: revenue_estimate_high wiederholt sich 7x exakt bei 40 Mrd."""
    mpc = _load("fixtures_mpc_excerpt.json")
    flags = run_sanity_checks("MPC", mpc)
    assert "REPEATED_PLACEHOLDER" in flags
    assert len(flags["REPEATED_PLACEHOLDER"][0]["dates"]) >= 4


def test_nvda_split_artifact_detected():
    """NVDA: 10:1-Split Juni 2024 und 4:1-Split Juli 2021 als Near-Integer-
    Sprung in den *_days_ago-Feldern erkennbar."""
    nvda = _load("fixtures_nvda_excerpt.json")
    flags = run_sanity_checks("NVDA", nvda)
    assert "POSSIBLE_SPLIT_ARTIFACT" in flags
    dates_found = {f["date"] for f in flags["POSSIBLE_SPLIT_ARTIFACT"]}
    assert "2024-07-31" in dates_found
    assert "2021-10-31" in dates_found


def test_nvda_zero_row_detected():
    """NVDA: Quartal 2022-07-31 mit eps_estimate_average=0 UND
    eps_estimate_analyst_count=0 bei befuelltem _7_days_ago-Nachbarfeld."""
    nvda = _load("fixtures_nvda_excerpt.json")
    flags = run_sanity_checks("NVDA", nvda)
    assert "ZERO_VALUE_ANOMALY" in flags
    assert "2022-07-31" in flags["ZERO_VALUE_ANOMALY"]


def test_ibkr_no_false_positives():
    """IBKR: sauberer Ticker, keine der drei Anomalien vorhanden — Detektoren
    duerfen hier nichts markieren."""
    ibkr = _load("fixtures_ibkr_clean.json")
    flags = run_sanity_checks("IBKR", ibkr)
    assert flags == {}


if __name__ == "__main__":
    tests = [
        test_mpc_repeated_value_detected,
        test_nvda_split_artifact_detected,
        test_nvda_zero_row_detected,
        test_ibkr_no_false_positives,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1
    sys.exit(1 if failed else 0)
