"""
Tests fuer cot_data_quality.py (19.09.2026).

Schwerpunkt: E2 (lookahead_filter) ist der Test mit dem hoechsten Wert -
das ist die technische Durchsetzung des Look-ahead-Bias-Schutzes, den
Block E architektonisch garantieren soll. Ein Fehler hier waere der
teuerste denkbare Fehler in der ganzen Pipeline (unbemerkter Bias in
jedem spaeteren Backtest).

Ausfuehren: pytest tests/test_cot_data_quality.py -v
(kein externes Test-Framework-Setup noetig ausser pytest selbst)
"""

import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cot_data_quality as cdq


# ── Fixtures / Hilfsfunktionen ───────────────────────────────────────────

def _row(report_date, effective_date, effective_type="observed", name="TEST MARKET", **extra):
    base = {
        "report_date_as_yyyy_mm_dd": f"{report_date}T00:00:00.000",
        "market_and_exchange_names": name,
        "uiq_effective_date": effective_date,
        "uiq_effective_date_type": effective_type,
        "open_interest_all": "1000",
        "dealer_positions_long_all": "100", "dealer_positions_short_all": "50", "dealer_positions_spread_all": "10",
        "asset_mgr_positions_long": "200", "asset_mgr_positions_short": "150", "asset_mgr_positions_spread": "20",
        "lev_money_positions_long": "300", "lev_money_positions_short": "250", "lev_money_positions_spread": "30",
        "other_rept_positions_long": "50", "other_rept_positions_short": "40", "other_rept_positions_spread": "5",
        "nonrept_positions_long_all": "10", "nonrept_positions_short_all": "5",
        "contract_units": "TEST", "futonly_or_combined": "FutOnly",
    }
    base.update(extra)
    return base


def _write_jsonl(tmpdir, instrument_id, rows):
    path = os.path.join(tmpdir, f"{instrument_id}.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


# ── E1 - Temporal Integrity ──────────────────────────────────────────────

def test_temporal_integrity_pass_on_clean_data():
    rows = [
        _row("2020-01-07", "2020-01-10"),
        _row("2020-01-14", "2020-01-17"),
    ]
    result = cdq.check_temporal_integrity(rows)
    assert result["status"] == "PASS"
    assert result["violation_count"] == 0


def test_temporal_integrity_flags_effective_before_report():
    """Der eigentliche Look-ahead-Fall: uiq_effective_date < report_date
    darf niemals PASS ergeben."""
    rows = [_row("2020-01-07", "2020-01-05")]  # effective VOR report - Fehler
    result = cdq.check_temporal_integrity(rows)
    assert result["status"] == "FAIL"
    assert result["violation_count"] == 1
    assert "Look-ahead" in result["violations_sample"][0]["issue"]


def test_temporal_integrity_flags_unknown_effective_type():
    rows = [_row("2020-01-07", "2020-01-10", effective_type="guessed")]
    result = cdq.check_temporal_integrity(rows)
    assert result["status"] == "FAIL"
    assert any("unbekannter" in v["issue"] for v in result["violations_sample"])


# ── E2 - lookahead_filter (der wichtigste Test in dieser Datei) ─────────

def test_lookahead_filter_excludes_rows_not_yet_effective():
    """
    Kernszenario: eine Beobachtung mit report_date=Dienstag,
    uiq_effective_date=Freitag darf an einem Research-Zeitpunkt VOR
    Freitag NICHT zurueckgegeben werden - selbst wenn report_date bereits
    in der Vergangenheit liegt. Genau das ist der Fehler, den ein naiver
    "report_date <= observation_date"-Vergleich machen wuerde.
    """
    rows = [
        _row("2020-01-07", "2020-01-10"),  # Dienstag -> Freitag
    ]
    # Beobachtungszeitpunkt Mittwoch (nach report_date, aber VOR effective_date)
    result = cdq.lookahead_filter(rows, "2020-01-08")
    assert result == [], "Zeile war am Mittwoch noch nicht bekannt - haette ausgeschlossen werden muessen"

    # Beobachtungszeitpunkt Freitag selbst (Veroeffentlichungstag) -> jetzt verfuegbar
    result_on_effective = cdq.lookahead_filter(rows, "2020-01-10")
    assert len(result_on_effective) == 1


def test_lookahead_filter_includes_rows_effective_before_observation():
    rows = [_row("2020-01-07", "2020-01-10")]
    result = cdq.lookahead_filter(rows, "2020-06-01")
    assert len(result) == 1


def test_lookahead_filter_handles_multiple_rows_mixed_availability():
    rows = [
        _row("2020-01-07", "2020-01-10"),
        _row("2020-01-14", "2020-01-17"),
        _row("2020-01-21", "2020-01-24"),
    ]
    # Beobachtungszeitpunkt zwischen der zweiten und dritten Veroeffentlichung
    result = cdq.lookahead_filter(rows, "2020-01-20")
    assert len(result) == 2
    assert all(cdq._parse_date(r["uiq_effective_date"]) <= cdq._parse_date("2020-01-20") for r in result)


# ── D - Schema Stability ─────────────────────────────────────────────────

def test_schema_stability_pass_when_all_fields_present_throughout():
    rows = [_row(f"2020-01-{d:02d}", f"2020-01-{d+3:02d}") for d in (7, 14, 21)]
    result = cdq.check_schema_stability(rows)
    assert result["status"] == "PASS"
    assert not result["missing_explicit_fields"]


def test_schema_stability_tolerates_field_missing_only_at_first_observation():
    """Analog zum echten SP500-Befund: change_in_* fehlt plausibel nur in
    der allerersten Zeile (kein Vorwochenwert moeglich) - das ist KEINE
    Anomalie."""
    rows = [
        _row("2020-01-07", "2020-01-10"),  # kein change_in_open_interest_all
        _row("2020-01-14", "2020-01-17", change_in_open_interest_all="5"),
        _row("2020-01-21", "2020-01-24", change_in_open_interest_all="-3"),
    ]
    result = cdq.check_schema_stability(rows)
    assert result["status"] == "PASS"
    assert result["anomaly_count"] == 0


def test_schema_stability_flags_gap_after_field_established():
    """Der echte 2010-07-20-Fund: Feld fehlt NICHT am Anfang, sondern
    mitten in einer Reihe, wo es vorher und nachher vorhanden ist -
    das MUSS als Anomalie erscheinen, und zwar als UNCLASSIFIED_GAP
    (change_in_* passt nicht ins traders_*-Erklaerungsmuster), Status WARN."""
    rows = [
        _row("2020-01-07", "2020-01-10", change_in_open_interest_all="1"),
        _row("2020-01-14", "2020-01-17"),  # fehlt mittendrin - Anomalie
        _row("2020-01-21", "2020-01-24", change_in_open_interest_all="-3"),
    ]
    result = cdq.check_schema_stability(rows)
    assert result["status"] == "WARN"
    assert result["anomaly_count"] == 1
    assert result["anomalies_sample"][0]["field"] == "change_in_open_interest_all"
    assert result["anomalies_sample"][0]["classification"] == "UNCLASSIFIED_GAP"
    assert result["anomalies_sample"][0]["cause"] is None


def test_schema_stability_classifies_traders_field_gap_as_review_required():
    """traders_*-Felder bekommen eine CFTC-dokumentierte Ursache (Vier-
    Trader-Vertraulichkeitsregel, TFF-spezifisch verifiziert 20.09.2026),
    aber Status bleibt REVIEW_REQUIRED - Existenz des Mechanismus und
    Ursache eines konkreten Einzelfunds bleiben getrennt (Axel-Vorgabe)."""
    rows = [
        _row("2020-01-07", "2020-01-10", traders_other_rept_spread="5"),
        _row("2020-01-14", "2020-01-17"),  # traders_-Feld fehlt mittendrin
        _row("2020-01-21", "2020-01-24", traders_other_rept_spread="4"),
    ]
    result = cdq.check_schema_stability(rows)
    assert result["status"] == "REVIEW_REQUIRED"
    anomaly = next(a for a in result["anomalies_sample"] if a["field"] == "traders_other_rept_spread")
    assert anomaly["classification"] == "REVIEW_REQUIRED"
    assert anomaly["cause"]["confidence"] == "HIGH"
    assert "suppression" in anomaly["cause"]["mechanism"] or "unterdrueckt" in anomaly["cause"]["mechanism"]
    assert "tfmexplanatorynotes" in anomaly["cause"]["source_url"]


def test_schema_stability_flags_missing_explicit_field_entirely():
    rows = [{k: v for k, v in _row("2020-01-07", "2020-01-10").items() if k != "contract_units"}]
    result = cdq.check_schema_stability(rows)
    assert "contract_units" in result["missing_explicit_fields"]


# ── A - Coverage ──────────────────────────────────────────────────────────

def test_coverage_complete_on_regular_weekly_series():
    rows = [_row(f"2020-01-{d:02d}", f"2020-01-{d+3:02d}") for d in (7, 14, 21, 28)]
    result = cdq.check_coverage(rows)
    assert result["coverage_status"] == "COMPLETE"


def test_coverage_detects_material_gap():
    rows = [
        _row("2020-01-07", "2020-01-10"),
        _row("2020-03-01", "2020-03-04"),  # >14 Tage Luecke
    ]
    result = cdq.check_coverage(rows)
    assert result["coverage_status"] == "MATERIAL_GAPS"


def test_coverage_treats_minor_gap_as_non_material():
    rows = [
        _row("2020-01-07", "2020-01-10"),
        _row("2020-01-21", "2020-01-24"),  # 14 Tage - genau an der Grenze, MINOR
    ]
    result = cdq.check_coverage(rows)
    assert result["coverage_status"] == "MINOR_GAPS"


def test_coverage_flags_duplicates():
    rows = [
        _row("2020-01-07", "2020-01-10"),
        _row("2020-01-07", "2020-01-10"),  # echtes Duplikat, gleicher Key
    ]
    result = cdq.check_coverage(rows)
    assert len(result["duplicate_keys"]) == 1


def test_coverage_does_not_confuse_two_parallel_sources_with_a_gap():
    """Russell-Overlap-Fall: zwei verschiedene market_and_exchange_names
    am selben report_date duerfen NICHT als Luecke der jeweils anderen
    Serie gewertet werden."""
    rows = [
        _row("2020-01-07", "2020-01-10", name="ICE MARKET"),
        _row("2020-01-14", "2020-01-17", name="ICE MARKET"),
        _row("2020-01-07", "2020-01-10", name="CME MARKET"),
        _row("2020-01-14", "2020-01-17", name="CME MARKET"),
    ]
    result = cdq.check_coverage(rows)
    assert result["coverage_status"] == "COMPLETE"
    assert not result["duplicate_keys"]


# ── B - Source Mapping ─────────────────────────────────────────────────

def test_source_mapping_lists_transitions_in_chronological_order():
    rows = [
        _row("2022-02-08", "2022-02-11", name="NEW NAME"),
        _row("2006-06-13", "2006-06-16", name="OLD NAME"),
    ]
    result = cdq.check_source_mapping(rows)
    assert result["distinct_source_names"] == 2
    assert result["transitions"][0]["market_and_exchange_names"] == "OLD NAME"
    assert result["transitions"][1]["market_and_exchange_names"] == "NEW NAME"


# ── C - Russell ICE/CME Overlap ──────────────────────────────────────────

def test_russell_overlap_not_applicable_for_other_instruments():
    result = cdq.check_russell_overlap([_row("2020-01-07", "2020-01-10")], "SP500")
    assert result["applicable"] is False


def test_russell_overlap_computes_stats_without_interpretation():
    rows = [
        _row("2017-08-15", "2017-08-18", name="RUSSELL 2000 MINI INDEX FUTURE - ICE FUTURES U.S.",
             historical_source_overlap=True,
             lev_money_positions_long="100", lev_money_positions_short="40"),
        _row("2017-08-15", "2017-08-18", name="E-MINI RUSSELL 2000 INDEX - CHICAGO MERCANTILE EXCHANGE",
             historical_source_overlap=True,
             lev_money_positions_long="90", lev_money_positions_short="35"),
        _row("2017-08-22", "2017-08-25", name="RUSSELL 2000 MINI INDEX FUTURE - ICE FUTURES U.S.",
             historical_source_overlap=True,
             lev_money_positions_long="130", lev_money_positions_short="50"),
        _row("2017-08-22", "2017-08-25", name="E-MINI RUSSELL 2000 INDEX - CHICAGO MERCANTILE EXCHANGE",
             historical_source_overlap=True,
             lev_money_positions_long="95", lev_money_positions_short="45"),
    ]
    result = cdq.check_russell_overlap(rows, "RUSSELL2000")
    assert result["applicable"] is True
    assert result["dates_with_both_sources"] == 2
    stats = result["net_position_by_category"]["lev_money"]
    assert stats["n"] == 2
    assert stats["pearson_correlation"] is not None
    # Keine Interpretations-Keys wie "better_source" o.ae. duerfen existieren:
    assert "better_source" not in result
    assert "recommended_source" not in result


def test_known_overlaps_matches_collector_constant():
    """Verhindert, dass cot_data_quality.py und cot_layer.py bei den
    Ueberlappungsfenstern unbemerkt auseinanderlaufen (s. Kommentar in
    cot_data_quality.py zu KNOWN_SOURCE_OVERLAPS). Import ist optional -
    wenn cot_layer.py in der CI nicht importierbar ist (z.B. fehlendes
    'requests'-Paket), wird dieser Test uebersprungen statt fehlzuschlagen,
    da er kein Kernbestandteil der Quality-Logik selbst ist."""
    try:
        import cot_layer
    except ImportError:
        import pytest
        pytest.skip("cot_layer.py nicht importierbar (z.B. fehlendes 'requests') - Vergleich uebersprungen")
        return
    assert cdq.KNOWN_SOURCE_OVERLAPS == cot_layer.KNOWN_SOURCE_OVERLAPS


# ── Cross-validated Gaps (VIX-Audit 19.09.2026) ──────────────────────────

def test_cross_validated_gap_not_applicable_for_other_instruments():
    result = cdq.check_cross_validated_gaps([_row("2020-01-07", "2020-01-10")], "SP500")
    assert result["applicable"] is False


def test_cross_validated_gap_confirms_when_data_matches_registry():
    """Die 2008-12-16 -> 2009-06-02-Luecke exakt nachgebaut: Registry-
    Eintrag muss als CONFIRMED zurueckkommen, Befund und Ursache bleiben
    getrennte Felder."""
    rows = [
        _row("2008-12-09", "2008-12-12", name="VIX FUTURES - CBOE FUTURES EXCHANGE"),
        _row("2008-12-16", "2008-12-19", name="VIX FUTURES - CBOE FUTURES EXCHANGE"),
        # Luecke
        _row("2009-06-02", "2009-06-05", name="VIX FUTURES - CBOE FUTURES EXCHANGE"),
        _row("2009-06-09", "2009-06-12", name="VIX FUTURES - CBOE FUTURES EXCHANGE"),
    ]
    result = cdq.check_cross_validated_gaps(rows, "VIX")
    assert result["applicable"] is True
    finding = result["findings"][0]
    assert finding["live_reverification"] == "CONFIRMED"
    assert finding["cross_validated"] is True
    assert len(finding["cross_validated_sources"]) == 3
    assert finding["cause"]["status"] == "HYPOTHESIS"
    assert finding["research_implication"]["stable_series_start"] == "2009-06-02"
    # Ursachentext darf keine staerkere Aussage treffen als belegt -
    # "Meldepflicht" darf nur in der ausdruecklichen Verneinung vorkommen:
    assert "Meldepflicht" not in finding["cause"]["hypothesis"].split("Keine Aussage")[0]


def test_cross_validated_gap_flags_stale_if_gap_no_longer_present():
    """Wenn eine spaetere CFTC-Revision die Luecke fuellt, MUSS das als
    STALE_NEEDS_REVIEW auffallen statt den alten Befund unveraendert
    durchzureichen."""
    rows = [
        _row("2008-12-16", "2008-12-19", name="VIX FUTURES - CBOE FUTURES EXCHANGE"),
        _row("2009-02-10", "2009-02-13", name="VIX FUTURES - CBOE FUTURES EXCHANGE"),  # fuellt die Luecke
        _row("2009-06-02", "2009-06-05", name="VIX FUTURES - CBOE FUTURES EXCHANGE"),
    ]
    result = cdq.check_cross_validated_gaps(rows, "VIX")
    assert result["findings"][0]["live_reverification"] == "STALE_NEEDS_REVIEW"


def test_build_report_includes_instrument_notes_for_vix():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_jsonl(tmpdir, "VIX", [
            _row("2008-12-16", "2008-12-19", name="VIX FUTURES - CBOE FUTURES EXCHANGE"),
            _row("2009-06-02", "2009-06-05", name="VIX FUTURES - CBOE FUTURES EXCHANGE"),
        ])
        report = cdq.build_report(base_dir=tmpdir)
        notes = report["research_readiness"]["instrument_notes"]
        assert "VIX" in notes
        assert notes["VIX"]["stable_series_start"] == "2009-06-02"
        assert notes["VIX"]["cause_status"] == "HYPOTHESIS"


# ── Integration: build_report() gegen echte Dateistruktur ───────────────

def test_build_report_end_to_end_with_temp_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_jsonl(tmpdir, "SP500", [
            _row("2020-01-07", "2020-01-10", name="OLD NAME"),
            _row("2020-01-14", "2020-01-17", name="OLD NAME"),
        ])
        report = cdq.build_report(base_dir=tmpdir)

        assert report["report_version"] == cdq.REPORT_VERSION
        assert report["source"]["instrument_count"] == 1
        assert report["source"]["record_count"] == 2
        assert "SP500" in report["checks"]["temporal_integrity"]
        assert report["overall_status"] in ("PASS", "REVIEW_REQUIRED", "MINOR_GAPS", "MATERIAL_GAPS", "FAIL", "WARN")
        assert report["research_readiness"]["feature_research"] in ("READY", "CONDITIONAL", "BLOCKED")
        assert report["research_readiness"]["regime_backtest"] in ("READY", "CONDITIONAL", "BLOCKED")
        assert isinstance(report["research_readiness"]["full_universe_research"], bool)


def test_build_report_gates_regime_backtest_on_material_gaps():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_jsonl(tmpdir, "SP500", [
            _row("2020-01-07", "2020-01-10"),
            _row("2020-06-01", "2020-06-04"),  # grosse Luecke
        ])
        report = cdq.build_report(base_dir=tmpdir)
        assert report["research_readiness"]["regime_backtest"] == "CONDITIONAL"
        assert "MATERIAL_GAPS" in report["research_readiness"]["reason"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
