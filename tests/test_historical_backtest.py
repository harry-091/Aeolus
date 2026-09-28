"""Unit and integration tests for Phase 5: Historical Voyage Replay / Backtesting Engine.

Validates metric calculations (Hausdorff, cross-track deviations, length deltas),
simulated time-advancing routing decisions, constraint violation audits, and anti-leakage compliance.
"""

from datetime import datetime, timedelta, timezone
import json
import pytest
import numpy as np
from pathlib import Path

from src.historical_backtest.backtest_schema import (
    SimulatedStep,
    ViolationAudit,
    RouteComparisonMetrics,
    BacktestResult,
)
from src.historical_backtest.backtest_metrics import (
    haversine_km,
    compute_path_length_km,
    compute_hausdorff_and_deviations,
    audit_path_environment,
    compute_route_comparison_metrics,
)
from src.historical_backtest.replay_engine import HistoricalVoyageReplayEngine


class TestBacktestMetricsMath:
    """Test geometric and spherical distance computations."""

    def test_haversine_known_distance(self):
        # 1 degree of latitude at equator is approx 111.19 km
        d = haversine_km(0.0, 0.0, 1.0, 0.0)
        assert np.isclose(d, 111.19, atol=0.5)

        # Same point distance is 0.0
        assert haversine_km(-65.0, 140.0, -65.0, 140.0) == 0.0

    def test_path_length(self):
        path = [
            [-43.0, 147.0],
            [-44.0, 147.0],
            [-45.0, 147.0],
        ]
        total_d = compute_path_length_km(path)
        assert np.isclose(total_d, 222.38, atol=1.0)

    def test_hausdorff_and_deviation_identical_paths(self):
        path = [
            [-43.0, 147.0],
            [-50.0, 140.0],
            [-66.0, 110.0],
        ]
        h_dist, mean_dev, nearest_err = compute_hausdorff_and_deviations(path, path)
        assert h_dist == 0.0
        assert mean_dev == 0.0
        assert nearest_err == 0.0

    def test_hausdorff_parallel_offset_paths(self):
        # Two parallel lines offset by 1 degree of latitude (~111 km)
        path_a = [[-50.0, 100.0], [-50.0, 110.0], [-50.0, 120.0]]
        path_b = [[-51.0, 100.0], [-51.0, 110.0], [-51.0, 120.0]]

        h_dist, mean_dev, _ = compute_hausdorff_and_deviations(path_a, path_b)
        assert np.isclose(h_dist, 111.19, atol=2.0)
        assert np.isclose(mean_dev, 111.19, atol=2.0)


class TestEnvironmentalAuditing:
    """Test constraint violation detections along paths."""

    def test_violation_audit_triggers(self):
        coords = [
            [-65.0, 140.0],
            [-66.0, 140.0],
            [-67.0, 140.0],
        ]
        # Mock lookup functions
        def mock_sic(lat, lon):
            return 0.50 if lat == -66.0 else 0.10  # Point 2 has dangerous pack ice

        def mock_iceberg(lat, lon):
            return 8.0 if lat == -67.0 else 50.0   # Point 3 within 15 km of iceberg

        def mock_depth(lat, lon):
            return 15.0 if lat == -65.0 else 2000.0 # Point 1 in shallow water

        def mock_land(lat, lon):
            return False

        audit, sic_prof = audit_path_environment(
            coords=coords,
            sic_lookup_fn=mock_sic,
            iceberg_dist_fn=mock_iceberg,
            depth_lookup_fn=mock_depth,
            is_land_fn=mock_land,
            speed_knots=14.0,
        )

        assert audit.dangerous_ice_distance_km > 0.0
        assert audit.iceberg_violations_count == 1
        assert audit.bathymetric_violations_count == 1
        assert audit.coast_land_violations_count == 0
        assert audit.min_iceberg_clearance_km == 8.0
        assert audit.min_depth_m == 15.0
        assert len(sic_prof) == 3


class TestReplayEngineIntegration:
    """Test end-to-end replay simulation on a small historical fixture."""

    @pytest.fixture(scope="module")
    def replay_engine(self):
        return HistoricalVoyageReplayEngine()

    def test_historical_voyage_replay_fixture(self, replay_engine):
        # Small historical voyage fixture (Hobart to Casey sector)
        actual_fixture = [
            [-43.0, 147.3],
            [-48.5, 142.0],
            [-55.0, 135.0],
            [-60.2, 125.0],
            [-66.2, 110.5],
        ]
        dep_time = datetime(2015, 12, 9, 0, 0, 0, tzinfo=timezone.utc)

        result = replay_engine.replay_voyage(
            voyage_id="FIXTURE-VOYAGE-001",
            actual_track=actual_fixture,
            departure_time=dep_time,
            vessel_name="Aurora Australis Fixture",
            polar_class="PC3",
            speed_knots=14.0,
            actual_duration_hours=180.0,
        )

        assert isinstance(result, BacktestResult)
        assert result.voyage_id == "FIXTURE-VOYAGE-001"
        assert result.actual_track_points_count == len(actual_fixture)
        assert result.model_route_points_count > 0

        # Verify all 12 metrics are populated
        m = result.metrics
        assert isinstance(m, RouteComparisonMetrics)
        assert m.actual_length_km > 0.0
        assert m.model_length_km > 0.0
        assert m.route_deviation_mean_km >= 0.0
        assert m.waypoint_hausdorff_distance_km >= 0.0
        assert m.actual_duration_hours > 0.0
        assert m.model_duration_hours > 0.0
        assert 0.0 <= m.model_avg_sic_pct <= 100.0
        assert 0.0 <= m.model_max_sic_pct <= 100.0
        assert m.model_iceberg_violations >= 0
        assert m.model_bathymetric_violations >= 0
        assert m.model_land_violations == 0  # Recommended route must avoid land
        assert m.computational_time_ms > 0.0

        # Verify simulated steps advance chronologically
        assert len(result.simulated_steps) > 0
        steps = result.simulated_steps
        for idx in range(1, len(steps)):
            assert steps[idx].cumulative_distance_km >= steps[idx - 1].cumulative_distance_km

        # Verify serialization
        res_dict = result.to_dict()
        assert "geojson_features" in res_dict
        assert len(res_dict["geojson_features"]["features"]) == 2

        # Verify anti-leakage: model path is not an identical copy of actual fixture
        assert result.model_path_coords != actual_fixture
