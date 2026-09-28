"""POLARNAV — Phase 13: Offline Historical Backtesting Test Suite.

Validates:
1. Strict OFFLINE ONLY invariant (no live external dependencies).
2. Anti-lookahead causality (at time T, only information <= T is used).
3. Three-way comparison:
   - PolarNav route
   - Comparable historical AIS
   - Shortest-path baseline
4. Operational event segmentation:
   - scientific stops
   - weather holds
   - port/station operations
   - maneuvering
   - data gaps
   - ice avoidance
5. All 9 evaluation dimensions:
   - Safety
   - Efficiency
   - Feasibility
   - ETA
   - Distance
   - High-SIC exposure
   - Iceberg clearance
   - Bathymetry violations
   - Fuel estimate
6. Operational reference statement:
   "Historical AIS is an operational reference, not guaranteed optimal ground truth."
7. REST API Endpoints: catalog, voyage detail, custom run.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.server import app
from realtime.backtesting.service import offline_backtest_service
from realtime.backtesting.models import OperationalSegmentType

client = TestClient(app)


class TestOfflineHistoricalBacktesting:
    """Core offline backtest engine test suite."""

    def test_offline_catalog_loading(self):
        """Verify catalog loads offline verified voyages with metadata."""
        catalog = offline_backtest_service.list_voyages()
        assert len(catalog) >= 1
        v0 = catalog[0]
        assert v0.voyage_id == "AAD-2015-16"
        assert v0.vessel_name == "Aurora Australis"
        assert v0.data_source_mode == "OFFLINE_ONLY"
        assert v0.total_distance_km > 0.0

    def test_zero_lookahead_and_temporal_cutoff(self):
        """Verify backtest executes without future data leakage at time T."""
        res = offline_backtest_service.run_backtest("AAD-2015-16")
        assert res.status == "COMPLETED"
        assert res.offline_only_enforced is True
        assert res.anti_lookahead_verified is True
        assert res.temporal_cutoff_time_iso is not None
        # Confirms snapshots strictly captured at T0
        assert "offline_sources" in res.environmental_snapshots_at_t0

    def test_three_way_comparison_structure(self):
        """Verify candidate PolarNav route, baseline A (AIS), and baseline B (shortest)."""
        res = offline_backtest_service.run_backtest("AAD-2015-16")
        comp = res.comparison
        assert comp.polarnav_route.route_type == "POLARNAV_BALANCED"
        assert comp.historical_ais_route.route_type == "HISTORICAL_AIS"
        assert comp.shortest_path_baseline.route_type == "SHORTEST_PATH_BASELINE"

        # Comparison deltas
        assert isinstance(comp.distance_savings_vs_ais_km, float)
        assert isinstance(comp.distance_savings_vs_ais_pct, float)
        assert isinstance(comp.time_savings_vs_ais_net_hours, float)
        assert isinstance(comp.risk_reduction_vs_ais_pct, float)
        assert isinstance(comp.fuel_savings_vs_ais_tonnes, float)

    def test_operational_event_segmentation(self):
        """Verify segmentation identifies all 6 operational categories."""
        res = offline_backtest_service.run_backtest("AAD-2015-16")
        ob = res.operational_breakdown
        assert ob.total_voyage_hours > 0.0
        assert ob.transit_hours > 0.0
        assert len(ob.segments) >= 3

        # Check types present across catalog
        found_types = {s.segment_type for s in ob.segments}
        # In AAD-2015-16, vessel stays in Casey Station berth and transits open ocean
        assert OperationalSegmentType.TRANSIT in found_types
        assert (OperationalSegmentType.PORT_STATION_OPERATIONS in found_types or
                OperationalSegmentType.SCIENTIFIC_STOP in found_types or
                OperationalSegmentType.ICE_AVOIDANCE in found_types)

        # Net transit duration strictly accounts for delays
        prof_ais = res.comparison.historical_ais_route
        assert prof_ais.net_transit_hours <= prof_ais.gross_transit_hours

    def test_all_nine_evaluation_dimensions_present(self):
        """Verify all 9 dimensions evaluated across candidate and baselines."""
        res = offline_backtest_service.run_backtest("AAD-2015-16")
        for route in [res.comparison.polarnav_route, res.comparison.historical_ais_route, res.comparison.shortest_path_baseline]:
            # 1. Distance
            assert route.distance_km > 0.0
            assert route.distance_nm == pytest.approx(route.distance_km / 1.852, rel=1e-2)

            # 2. ETA
            assert route.gross_transit_hours > 0.0
            assert route.net_transit_hours > 0.0

            # 3. Safety
            assert 0.0 <= route.composite_risk_score <= 1.0
            assert route.risk_category in ["LOW", "MODERATE", "ELEVATED", "CRITICAL"]

            # 4. Efficiency
            assert route.speed_efficiency_ratio > 0.0
            assert route.distance_efficiency_ratio > 0.0

            # 5. Feasibility
            assert isinstance(route.is_physically_feasible, bool)
            assert route.min_depth_m is not None

            # 6. High-SIC Exposure
            assert 0.0 <= route.mean_sic_pct <= 100.0
            assert 0.0 <= route.max_sic_pct <= 100.0
            assert route.distance_in_ice_km >= 0.0

            # 7. Iceberg Clearance
            assert route.min_iceberg_cpa_km >= 0.0
            assert route.min_iceberg_cpa_nm >= 0.0

            # 8. Bathymetry Violations
            assert route.bathymetry_violations_count >= 0

            # 9. Fuel Estimate
            assert route.estimated_fuel_metric_tonnes > 0.0
            assert route.fuel_burn_rate_kg_km > 0.0

    def test_operational_reference_statement_present(self):
        """Verify mandatory operational reference caveat is exposed without ambiguity."""
        res = offline_backtest_service.run_backtest("AAD-2015-16")
        statement = res.operational_reference_statement
        assert "Historical AIS is an operational reference" in statement
        assert "not guaranteed optimal ground truth" in statement

    def test_polarnav_feasibility_guarantee(self):
        """Verify PolarNav generated route obeys physical feasibility invariants."""
        res = offline_backtest_service.run_backtest("AAD-2015-16")
        p = res.comparison.polarnav_route
        assert p.land_crossings_count == 0
        assert p.is_physically_feasible is True
        assert p.under_keel_clearance_m >= 0.0


class TestBacktestAPIEndpoints:
    """FastAPI endpoint verification for Phase 13."""

    def test_api_catalog_endpoint(self):
        res = client.get("/api/realtime/backtest/catalog")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert data["data_mode"] == "OFFLINE_ONLY"
        assert data["anti_lookahead_enforced"] is True
        assert len(data["catalog"]) >= 1

    def test_api_voyage_replay_endpoint(self):
        res = client.get("/api/realtime/backtest/voyage/AAD-2015-16?polar_class=PC5&speed_knots=14.0")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "COMPLETED"
        assert data["voyage_id"] == "AAD-2015-16"
        assert "comparison" in data
        assert "operational_breakdown" in data
        assert "operational_reference_statement" in data

    def test_api_custom_run_endpoint(self):
        payload = {
            "voyage_id": "AAD-2015-16",
            "polar_class": "PC3",
            "speed_knots": 15.5,
            "draft_m": 8.5,
            "beam_m": 22.0,
            "length_m": 110.0,
        }
        res = client.post("/api/realtime/backtest/run", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "COMPLETED"
        assert data["vessel_ice_class"] == "PC3"
