"""Unit and integration tests for Phase 6: Historical Route Safety Comparison.

Validates 3-way route evaluation (Actual vs Predicted vs Safety-Optimized),
decoupled Route Similarity, Environmental Safety, and Efficiency metric suites,
and transparent Composite Safety Index calculation.
"""

from datetime import datetime, timezone
import json
import pytest
import numpy as np

from src.historical_backtest.safety_metrics_schema import (
    RouteProfileMetrics,
    PairwiseSimilarityMetrics,
    ThreeWayRouteComparison,
)
from src.historical_backtest.route_safety_comparator import RouteSafetyComparator
from src.historical_backtest.replay_engine import HistoricalVoyageReplayEngine


class TestRouteSafetyComparator:
    """Test safety profiling, efficiency calculation, and CSI mathematical properties."""

    def test_composite_safety_index_calculation(self):
        # Path with 0 SIC, 200km iceberg distance, 3500m depth, no land
        coords = [
            [-50.0, 100.0],
            [-55.0, 105.0],
            [-60.0, 110.0],
        ]
        comparator = RouteSafetyComparator(
            sic_lookup_fn=lambda lat, lon: 0.0,
            iceberg_dist_fn=lambda lat, lon: 200.0,
            depth_lookup_fn=lambda lat, lon: 3500.0,
            is_land_fn=lambda lat, lon: False,
        )

        profile = comparator.compute_route_profile(
            route_name="Clean Ocean Test",
            route_id="test_clean",
            coords=coords,
            speed_knots=14.0,
            polar_class="PC3",
        )

        # Perfect conditions:
        # CSI = 0.40*(1 - 0) + 0.30*min(1, 200/50) + 0.15*min(1, 3500/100) + 0.15*(1 - 0)
        #     = 0.40 + 0.30 + 0.15 + 0.15 = 1.0000
        assert np.isclose(profile.composite_safety_index, 1.0, atol=1e-3)
        assert profile.mean_sic_pct == 0.0
        assert profile.high_sic_distance_km == 0.0
        assert profile.iceberg_encounters_15km == 0
        assert profile.bathymetry_violations_20m == 0

    def test_degraded_conditions_lower_csi(self):
        coords = [
            [-65.0, 100.0],
            [-66.0, 100.0],
        ]
        # Severe pack ice (80%), near iceberg (10 km), shallow water (15 m), on land
        comparator = RouteSafetyComparator(
            sic_lookup_fn=lambda lat, lon: 0.80,
            iceberg_dist_fn=lambda lat, lon: 10.0,
            depth_lookup_fn=lambda lat, lon: 15.0,
            is_land_fn=lambda lat, lon: True,
        )

        profile = comparator.compute_route_profile(
            route_name="Hazardous Test",
            route_id="test_hazard",
            coords=coords,
            speed_knots=14.0,
            polar_class="PC3",
        )

        # Degraded CSI:
        # 0.40*(1 - 0.80) = 0.08
        # 0.30*(10 / 50)  = 0.06
        # 0.15*(15 / 100) = 0.0225
        # 0.15*(1 - 1)    = 0.00
        # Total = 0.1625
        assert profile.composite_safety_index < 0.20
        assert profile.extreme_sic_distance_km > 0.0
        assert profile.iceberg_encounters_15km == 2
        assert profile.bathymetry_violations_20m == 2
        assert profile.coastline_land_violations == 2

    def test_pairwise_similarity_metrics(self):
        comparator = RouteSafetyComparator(
            sic_lookup_fn=lambda lat, lon: 0.0,
            iceberg_dist_fn=lambda lat, lon: 200.0,
            depth_lookup_fn=lambda lat, lon: 3500.0,
            is_land_fn=lambda lat, lon: False,
        )
        path_a = [[-50.0, 100.0], [-50.0, 110.0]]
        path_b = [[-50.5, 100.0], [-50.5, 110.0]]

        sim = comparator.compute_pairwise_similarity("A vs B", path_a, path_b)
        assert isinstance(sim, PairwiseSimilarityMetrics)
        assert sim.comparison_pair == "A vs B"
        assert sim.hausdorff_distance_km > 0.0
        assert sim.mean_cross_track_deviation_km > 0.0


class TestThreeWayRouteComparisonIntegration:
    """Test full 3-way comparison using HistoricalVoyageReplayEngine."""

    @pytest.fixture(scope="module")
    def replay_engine(self):
        return HistoricalVoyageReplayEngine()

    def test_compare_voyage_safety_three_routes(self, replay_engine):
        fixture_track = [
            [-43.0, 147.3],
            [-50.0, 140.0],
            [-58.0, 130.0],
            [-66.2, 110.5],
        ]
        dep_time = datetime(2015, 12, 9, 0, 0, 0, tzinfo=timezone.utc)

        comparison = replay_engine.compare_voyage_safety(
            voyage_id="TEST-3WAY-001",
            actual_track=fixture_track,
            departure_time=dep_time,
            vessel_name="Aurora Australis",
            polar_class="PC3",
            speed_knots=14.0,
            actual_duration_hours=200.0,
        )

        assert isinstance(comparison, ThreeWayRouteComparison)
        assert comparison.voyage_id == "TEST-3WAY-001"

        # Verify all three route profiles exist
        assert comparison.route_actual.total_distance_km > 0.0
        assert comparison.route_predicted.total_distance_km > 0.0
        assert comparison.route_safety_optimized.total_distance_km > 0.0

        # Verify pairwise comparisons exist for all 3 pairs
        assert comparison.similarity_actual_vs_predicted.hausdorff_distance_km >= 0.0
        assert comparison.similarity_actual_vs_safest.hausdorff_distance_km >= 0.0
        assert comparison.similarity_predicted_vs_safest.hausdorff_distance_km >= 0.0

        # Verify methodological disclosures exist
        assert "ground_truth_disclaimer" in comparison.methodological_notes
        assert "no_fake_accuracy_disclaimer" in comparison.methodological_notes

        # Verify GeoJSON export contains 3 lines
        data = comparison.to_dict()
        assert len(data["geojson_features"]["features"]) == 3
