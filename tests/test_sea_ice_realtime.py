"""Automated Unit & Integration Tests for Phase 3 Sea Ice Monitoring.

Validates:
1. Dual-mode support: CURRENT ICE STATE vs HISTORICAL ICE STATE.
2. Mode separation: Live uses newest legitimate observation; historical matches simulated time (zero leakage).
3. Physical attributes: SIC, 15% ice edge proximity, extent, spatial gradients, coupled drift vectors.
4. Derived navigation features: sic_at_point, sic_gradient, high_ice_region, ice_edge_proximity, ice_risk_score, data_confidence.
5. Strict API response schema: value, timestamp, source, age, confidence.
6. Route analysis batch navigation evaluations.
7. BaseDataProvider contract & CurrentMaritimeState integration.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from realtime.sea_ice import (
    IceMonitoringMode,
    IceStage,
    SeaIceProvider,
    sea_ice_service,
    RouteWaypoint,
    RouteAnalysisRequest,
)
from realtime.base import DataCategory, ProviderStatus, BaseDataProvider
from realtime import maritime_state_manager
from app.server import app

client = TestClient(app)


class TestSeaIceProviderContract:
    """Verify BaseDataProvider contract and basic telemetry."""

    def test_provider_initialization(self):
        provider = SeaIceProvider()
        assert isinstance(provider, BaseDataProvider)
        assert provider.coverage.lat_min == -90.0
        assert provider.coverage.lat_max == -50.0

    def test_provider_health_status(self):
        provider = SeaIceProvider()
        health = provider.get_status()
        assert health.category == "SEA_ICE"
        assert health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
        assert health.coverage.contains(-70.0, 0.0)


class TestDualModeOperation:
    """Verify strict separation between CURRENT and HISTORICAL ice states."""

    def test_current_mode_uses_newest_product(self):
        provider = SeaIceProvider()
        # McMurdo Station coordinate: high ice pack in winter
        obs = provider.fetch_current(-77.85, 166.67)
        assert obs.mode == IceMonitoringMode.CURRENT
        assert obs.sic_fraction >= 0.70
        assert obs.metadata.provenance in (DataCategory.OBSERVED, DataCategory.STALE)
        assert "NOAA/NSIDC CDR" in obs.metadata.source

    def test_historical_mode_matches_simulated_time(self):
        provider = SeaIceProvider()
        # Winter observation: September 2023
        t_winter = datetime(2023, 9, 15, 0, 0, tzinfo=timezone.utc)
        obs_winter = provider.fetch_historical(-66.0, 90.0, t_winter)
        assert obs_winter.mode == IceMonitoringMode.HISTORICAL
        assert obs_winter.metadata.timestamp.month == 9
        assert obs_winter.metadata.timestamp.year == 2023

        # Summer observation: February 2024
        t_summer = datetime(2024, 2, 15, 0, 0, tzinfo=timezone.utc)
        obs_summer = provider.fetch_historical(-66.0, 90.0, t_summer)
        assert obs_summer.mode == IceMonitoringMode.HISTORICAL
        assert obs_summer.metadata.timestamp.month == 2
        assert obs_summer.metadata.timestamp.year == 2024

        # Antiphase seasonal validation: winter ice concentration should exceed summer
        assert obs_winter.sic_fraction >= obs_summer.sic_fraction

    def test_no_temporal_mixing(self):
        """Historical mode must never use current live time; current mode must never return historical mode."""
        provider = SeaIceProvider()
        obs_current = provider.fetch_current(-68.0, -60.0)
        assert obs_current.mode == IceMonitoringMode.CURRENT

        t_hist = datetime(2023, 5, 1, 0, 0, tzinfo=timezone.utc)
        obs_hist = provider.fetch_historical(-68.0, -60.0, t_hist)
        assert obs_hist.mode == IceMonitoringMode.HISTORICAL
        assert obs_hist.metadata.timestamp != obs_current.metadata.timestamp or obs_hist.metadata.timestamp.year == 2023


class TestPhysicalIceAnalytics:
    """Verify physical properties: SIC, ice edge (15%), spatial gradient, extent, and drift."""

    def test_sea_ice_concentration_and_classification(self):
        # Open water coordinate north of polar front
        obs_open = sea_ice_service.get_current_observation(-45.0, 0.0)
        assert obs_open.sic_fraction == 0.0
        assert obs_open.ice_stage == IceStage.OUT_OF_BOUNDS.value or obs_open.ice_stage == IceStage.OPEN_WATER.value

        # Pack ice inside Ross Sea
        obs_pack = sea_ice_service.get_current_observation(-76.0, -170.0)
        assert 0.0 <= obs_pack.sic_fraction <= 1.0
        assert obs_pack.sic_percent == round(obs_pack.sic_fraction * 100.0, 2)
        assert obs_pack.ice_stage in [
            IceStage.OPEN_WATER.value,
            IceStage.VERY_OPEN_PACK.value,
            IceStage.OPEN_PACK.value,
            IceStage.CLOSE_PACK.value,
            IceStage.CONSOLIDATED_PACK.value,
        ]

    def test_ice_edge_15_percent_threshold(self):
        obs = sea_ice_service.get_current_observation(-64.0, -60.0)
        assert obs.ice_edge.edge_threshold_sic == 0.15
        assert obs.ice_edge.distance_to_edge_km >= 0.0
        if obs.ice_edge.nearest_edge_lat is not None:
            assert -90.0 <= obs.ice_edge.nearest_edge_lat <= -50.0

    def test_spatial_gradient_calculation(self):
        obs = sea_ice_service.get_current_observation(-66.0, -65.0)
        grad = obs.spatial_gradient
        assert grad.magnitude_per_100km >= 0.0
        assert 0.0 <= grad.direction_deg <= 360.0
        assert grad.steepness_category in ("FLAT", "MODERATE", "STEEP", "DISCONTINUOUS_FRONT")

    def test_ice_drift_kinematics(self):
        # In heavy ice, drift should be evaluated
        obs = sea_ice_service.get_current_observation(-68.0, -60.0)
        if obs.sic_fraction >= 0.15:
            assert obs.ice_drift.available is True
            assert obs.ice_drift.drift_speed_knots >= 0.0
            assert 0.0 <= obs.ice_drift.drift_direction_deg <= 360.0
            assert obs.ice_drift.reliability in ("HIGH", "ESTIMATED")
        else:
            assert obs.ice_drift.available is False

    def test_ice_extent_summary(self):
        records = sea_ice_service.get_ice_extent_summary()
        assert len(records) > 0
        # Check standard NSIDC monthly extent structure
        first = records[0]
        assert "year" in first
        assert "month" in first
        assert "extent_million_sqkm" in first
        assert first["extent_million_sqkm"] > 1.0


class TestDerivedNavigationFeatures:
    """Verify calculated derived navigation features."""

    def test_navigation_features_structure(self):
        obs = sea_ice_service.get_current_observation(-68.0, 60.0)
        df = obs.derived_features
        assert 0.0 <= df.sic_at_point <= 1.0
        assert df.sic_gradient >= 0.0
        assert isinstance(df.high_ice_region, bool)
        assert df.high_ice_region == (df.sic_at_point >= 0.70)
        assert df.ice_edge_proximity_km >= 0.0
        assert 0.0 <= df.ice_risk_score <= 1.0
        assert 0.0 <= df.data_confidence <= 1.0


class TestSeaIceAPIEndpoints:
    """Verify REST API endpoints and mandatory schema contract: value, timestamp, source, age, confidence."""

    def test_api_current_endpoint(self):
        res = client.get("/api/realtime/sea_ice/current?lat=-66.0&lon=65.0")
        assert res.status_code == 200
        data = res.json()

        # Mandatory fields
        assert "value" in data
        assert "timestamp" in data
        assert "source" in data
        assert "age" in data
        assert "confidence" in data

        assert isinstance(data["value"], (float, int))
        assert 0.0 <= data["value"] <= 1.0
        assert data["mode"] == "CURRENT"
        assert "derived_navigation_features" in data
        df = data["derived_navigation_features"]
        assert "sic_at_point" in df
        assert "sic_gradient" in df
        assert "high_ice_region" in df
        assert "ice_edge_proximity_km" in df
        assert "ice_risk_score" in df
        assert "data_confidence" in df

    def test_api_historical_endpoint(self):
        sim_time = "2023-10-01T00:00:00Z"
        res = client.get(f"/api/realtime/sea_ice/historical?lat=-66.0&lon=65.0&simulated_time={sim_time}")
        assert res.status_code == 200
        data = res.json()

        assert "value" in data
        assert "timestamp" in data
        assert "source" in data
        assert "age" in data
        assert "confidence" in data

        assert data["mode"] == "HISTORICAL"
        # Matched timestamp should be in October 2023
        assert "2023-10" in data["timestamp"]

    def test_api_route_analysis_endpoint(self):
        payload = {
            "mode": "CURRENT",
            "waypoints": [
                {"id": "wp1", "lat": -60.0, "lon": 60.0},
                {"id": "wp2", "lat": -63.0, "lon": 62.0},
                {"id": "wp3", "lat": -66.0, "lon": 65.0},
                {"id": "wp4", "lat": -69.0, "lon": 70.0},
            ]
        }
        res = client.post("/api/realtime/sea_ice/route-analysis", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["waypoint_count"] == 4
        assert 0.0 <= data["mean_sic"] <= 1.0
        assert 0.0 <= data["max_sic"] <= 1.0
        assert 0.0 <= data["max_ice_risk_score"] <= 1.0
        assert "overall_route_advisory" in data
        assert len(data["points"]) == 4

        # Validate point derived features
        p = data["points"][0]
        assert "sic_at_point" in p
        assert "sic_gradient_per_100km" in p
        assert "high_ice_region" in p
        assert "ice_edge_proximity_km" in p
        assert "ice_risk_score" in p
        assert "data_confidence" in p

    def test_api_extent_and_edge_endpoints(self):
        res_ext = client.get("/api/realtime/sea_ice/extent")
        assert res_ext.status_code == 200
        assert res_ext.json()["count"] > 0

        res_edge = client.get("/api/realtime/sea_ice/edge?step=10")
        assert res_edge.status_code == 200
        assert res_edge.json()["count"] > 0
        assert res_edge.json()["edge_threshold_sic"] == 0.15


class TestMaritimeStateIntegration:
    """Verify integration into CurrentMaritimeState."""

    def test_current_maritime_state_sea_ice_layer(self):
        state = maritime_state_manager.get_current_state(lat=-66.0, lon=65.0)
        assert state.sea_ice is not None
        assert hasattr(state.sea_ice, "derived_features")
        assert hasattr(state.sea_ice, "ice_edge")
        assert hasattr(state.sea_ice, "spatial_gradient")
        assert state.sea_ice.metadata.confidence > 0.0
