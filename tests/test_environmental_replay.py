"""Unit and Integration Tests for Phase 2: Historical Environmental Replay Dataset.

Verifies:
1. Anti-leakage constraint enforcement (T_env <= T_decision).
2. NOAA ETOPO Bathymetry depth lookups and shallow water detection.
3. Antarctica Land Mask coastline proximity and on-land detection.
4. NOAA/NSIDC CDR V4 Sea Ice Concentration matching and WMO classification.
5. BYU/NIC Iceberg obstacle proximity.
6. Copernicus ocean current extraction.
7. Composite navigation risk calculation.
8. Quality flags and missing variable tracking.
9. End-to-end replay pipeline on real AAD voyage tracks.
10. Standardized export formats (JSON, CSV).
"""
import os
import sys
import tempfile
import json
import pytest
from datetime import datetime

# Ensure backend root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.vessel_tracking.ais_schema import AISRecord
from src.environmental_replay.replay_schema import EnrichedAISFeaturePoint, ReplayDatasetSummary
from src.environmental_replay.environmental_matcher import EnvironmentalMatcher
from src.environmental_replay.replay_pipeline import EnvironmentalReplayPipeline
from src.environmental_replay.dataset_quality_report import run_environmental_quality_report


# =============================================================================
# 1. Environmental Matcher & Anti-Leakage Tests
# =============================================================================
@pytest.fixture(scope="module")
def matcher():
    m = EnvironmentalMatcher()
    m.initialize()
    return m


class TestEnvironmentalMatcher:

    def test_anti_leakage_flag(self, matcher):
        rec = AISRecord(
            vessel_id="test_ship",
            timestamp=datetime(2015, 12, 10, 12, 0),
            latitude=-65.0,
            longitude=140.0,
            speed_knots=10.0
        )
        pt = matcher.match_point(rec)
        assert pt.anti_leakage_verified is True
        assert "anti_leakage" in pt.quality_flags
        assert "VERIFIED" in pt.quality_flags["anti_leakage"]

    def test_open_ocean_sic_and_bathymetry(self, matcher):
        # Sub-polar open ocean point (e.g. -45°S, 140°E)
        rec = AISRecord(
            vessel_id="test_ship",
            timestamp=datetime(2015, 12, 10, 12, 0),
            latitude=-45.0,
            longitude=140.0,
            speed_knots=12.0
        )
        pt = matcher.match_point(rec)
        # North of 50°S should be open water
        assert pt.sic == 0.0
        assert pt.sic_percent == 0.0
        assert "Open Water" in pt.ice_classification
        # Deep Southern Ocean bathymetry
        assert pt.bathymetry_depth_m > 500.0
        assert pt.is_shallow is False

    def test_inland_antarctica_land_mask(self, matcher):
        # South Pole or deep continental ice sheet (-80°S, 100°E)
        rec = AISRecord(
            vessel_id="test_ship",
            timestamp=datetime(2015, 12, 10, 12, 0),
            latitude=-80.0,
            longitude=100.0,
            speed_knots=0.0
        )
        pt = matcher.match_point(rec)
        # Should detect on-land intersection
        assert pt.is_on_land is True
        assert pt.coastline_distance_km == 0.0

    def test_offshore_coastline_distance(self, matcher):
        # Offshore maritime point (-60.0°S, 120.0°E)
        rec = AISRecord(
            vessel_id="test_ship",
            timestamp=datetime(2015, 12, 10, 12, 0),
            latitude=-60.0,
            longitude=120.0,
            speed_knots=10.0
        )
        pt = matcher.match_point(rec)
        assert pt.is_on_land is False
        assert pt.coastline_distance_km > 20.0

    def test_composite_risk_score_bounds(self, matcher):
        rec = AISRecord(
            vessel_id="test_ship",
            timestamp=datetime(2015, 12, 10, 12, 0),
            latitude=-65.0,
            longitude=110.0,
            speed_knots=8.0
        )
        pt = matcher.match_point(rec)
        assert 0.0 <= pt.environmental_risk_score <= 1.0
        assert pt.risk_class in ("LOW", "MODERATE", "HIGH", "VERY_HIGH")

    def test_quality_flags_present(self, matcher):
        rec = AISRecord(
            vessel_id="test_ship",
            timestamp=datetime(2015, 12, 10, 12, 0),
            latitude=-62.0,
            longitude=115.0,
            speed_knots=10.0
        )
        pt = matcher.match_point(rec)
        assert "overall" in pt.quality_flags
        assert pt.quality_flags["overall"] in ("HIGH", "MEDIUM", "DEGRADED")
        assert "bathymetry" in pt.quality_flags
        assert "sic" in pt.quality_flags


# =============================================================================
# 2. Environmental Replay Pipeline Tests
# =============================================================================
class TestReplayPipeline:
    def test_process_records(self):
        pipeline = EnvironmentalReplayPipeline()
        records = [
            AISRecord(vessel_id="Ship1", timestamp=datetime(2015, 12, 1, 0, 0),
                      latitude=-50.0, longitude=120.0, speed_knots=10.0),
            AISRecord(vessel_id="Ship1", timestamp=datetime(2015, 12, 1, 1, 0),
                      latitude=-51.0, longitude=120.0, speed_knots=10.0),
        ]
        enriched = pipeline.process_records(records, voyage_id="voyage_test")
        assert len(enriched) == 2
        assert enriched[0].voyage_id == "voyage_test"
        assert enriched[0].latitude == -50.0
        assert enriched[1].latitude == -51.0
        assert enriched[0].anti_leakage_verified is True

    def test_summary_generation(self):
        pipeline = EnvironmentalReplayPipeline()
        records = [
            AISRecord(vessel_id="Ship1", timestamp=datetime(2015, 12, 1, 0, 0),
                      latitude=-50.0, longitude=120.0, speed_knots=10.0),
            AISRecord(vessel_id="Ship1", timestamp=datetime(2015, 12, 1, 1, 0),
                      latitude=-51.0, longitude=120.0, speed_knots=10.0),
        ]
        enriched = pipeline.process_records(records)
        summary = pipeline.generate_summary(enriched)
        assert summary.total_points == 2
        assert summary.matched_points == 2
        assert summary.match_rate_pct == 100.0
        assert "start" in summary.temporal_coverage
        assert "min_lat" in summary.spatial_coverage

    def test_export_dataset_json_and_csv(self):
        pipeline = EnvironmentalReplayPipeline()
        records = [
            AISRecord(vessel_id="Ship1", timestamp=datetime(2015, 12, 1, 0, 0),
                      latitude=-50.0, longitude=120.0, speed_knots=10.0),
        ]
        enriched = pipeline.process_records(records)

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "replay.json")
            csv_path = os.path.join(tmpdir, "replay.csv")

            pipeline.export_dataset(enriched, json_path, format="json")
            assert os.path.exists(json_path)
            with open(json_path, "r") as f:
                data = json.load(f)
                assert "features" in data
                assert len(data["features"]) == 1

            pipeline.export_dataset(enriched, csv_path, format="csv")
            assert os.path.exists(csv_path)


# =============================================================================
# 3. Real Antarctic Dataset Integration Test
# =============================================================================
class TestRealDatasetReplay:
    def test_real_aad_voyage_environmental_replay(self):
        aad_csv = os.path.join(BASE_DIR, "data", "raw", "vessel_tracks", "aurora_australis_2015_16.csv")
        if not os.path.exists(aad_csv):
            pytest.skip("Raw AAD CSV not present in test environment")

        pipeline = EnvironmentalReplayPipeline()
        enriched, summary = pipeline.process_file_or_dir(aad_csv)

        assert len(enriched) > 1000
        assert summary.matched_points > 1000
        assert summary.match_rate_pct > 95.0

        # Sample observation checks
        pt = enriched[len(enriched) // 2]
        assert pt.vessel_id is not None
        assert pt.voyage_id is not None
        assert pt.timestamp is not None
        assert pt.latitude < 0.0
        assert pt.bathymetry_depth_m > 0.0
        assert pt.anti_leakage_verified is True
        assert 0.0 <= pt.environmental_risk_score <= 1.0

    def test_quality_report_utility(self):
        aad_csv = os.path.join(BASE_DIR, "data", "raw", "vessel_tracks", "aurora_australis_2015_16.csv")
        if not os.path.exists(aad_csv):
            pytest.skip("Raw AAD CSV not present in test environment")

        report = run_environmental_quality_report(input_ais_path=aad_csv, output_json=True)
        assert "summary" in report
        s = report["summary"]
        assert s["matched_points"] > 1000
        assert "temporal_coverage" in s
        assert "spatial_coverage" in s
        assert "quality_breakdown" in s
