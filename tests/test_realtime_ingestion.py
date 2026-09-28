"""Automated Unit & Integration Tests for Phase 1 Real-Time Ingestion Architecture.

Validates:
1. BaseDataProvider abstraction and contract compliance across all 6 providers.
2. Explicit provenance enforcement (OBSERVED, REANALYZED, FORECAST, DERIVED, STALE, UNAVAILABLE).
3. Out-of-bounds geographic rejection (lat > -50.0°S marked UNAVAILABLE).
4. Dynamic staleness evaluation against freshness TTL windows.
5. Composite CurrentMaritimeState generation and IMO Polar Code advisory calculation.
6. Diagnostic health monitoring across all providers.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from realtime.base import (
    DataCategory,
    ProviderStatus,
    SpatialCoverage,
    DataMetadata,
    ProviderHealth,
    BaseDataProvider,
)
from realtime.state import (
    CurrentMaritimeState,
    MaritimeStateManager,
    maritime_state_manager,
)
from realtime.sea_ice import SeaIceProvider
from realtime.iceberg import IcebergProvider
from realtime.bathymetry import BathymetryProvider
from realtime.weather import WeatherProvider
from realtime.ocean import OceanProvider
from realtime.satellite import SatelliteProvider
from app.server import app

client = TestClient(app)


class TestDataProviderContract:
    """Ensure every provider satisfies the mandatory BaseDataProvider contract."""

    @pytest.mark.parametrize("provider_cls", [
        SeaIceProvider,
        IcebergProvider,
        BathymetryProvider,
        WeatherProvider,
        OceanProvider,
        SatelliteProvider,
    ])
    def test_provider_contract_methods(self, provider_cls):
        provider = provider_cls()
        assert isinstance(provider, BaseDataProvider)

        # 1. get_coverage()
        cov = provider.get_coverage()
        assert isinstance(cov, SpatialCoverage)
        assert cov.lat_max <= 0.0

        # 2. get_status()
        health = provider.get_status()
        assert isinstance(health, ProviderHealth)
        assert health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
        assert health.resolution_km > 0

        # 3. get_last_update()
        last_up = provider.get_last_update()
        assert last_up is not None

        # 4. fetch_current() in Antarctic zone
        obs = provider.fetch_current(-65.0, 64.0)
        assert hasattr(obs, "metadata")
        assert isinstance(obs.metadata, DataMetadata)
        assert obs.metadata.provenance in DataCategory

        # 5. fetch_recent()
        recent = provider.fetch_recent(-65.0, 64.0, hours=12.0)
        assert isinstance(recent, list)
        assert len(recent) >= 1


class TestProvenanceAndAntiLeakage:
    """Ensure strict provenance rules: never present forecast/reanalysis as observation."""

    def test_bathymetry_never_labeled_observed(self):
        bathy = BathymetryProvider()
        obs = bathy.fetch_current(-65.0, 64.0)
        assert obs.metadata.provenance == DataCategory.REANALYZED
        assert obs.metadata.provenance != DataCategory.OBSERVED

    def test_ocean_currents_never_labeled_observed(self):
        ocean = OceanProvider()
        obs = ocean.fetch_current(-65.0, 64.0)
        assert obs.metadata.provenance == DataCategory.REANALYZED
        assert obs.metadata.provenance != DataCategory.OBSERVED

    def test_out_of_bounds_marked_unavailable(self):
        providers = [
            SeaIceProvider(),
            IcebergProvider(),
            BathymetryProvider(),
            WeatherProvider(),
            OceanProvider(),
            SatelliteProvider(),
        ]
        # Equator (0.0, 0.0) is out of Antarctic bounds
        for p in providers:
            obs = p.fetch_current(0.0, 0.0)
            assert obs.metadata.provenance == DataCategory.UNAVAILABLE

    def test_staleness_recalculation(self):
        meta = DataMetadata(
            source="Test Radar",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=30),
            received_at=datetime.now(timezone.utc) - timedelta(hours=29),
            valid_until=datetime.now(timezone.utc) - timedelta(hours=6),
            lat_lon_coverage=SpatialCoverage(),
            resolution_km=10.0,
            data_quality="HIGH",
            confidence=0.9,
            provenance=DataCategory.OBSERVED,
        )
        assert meta.provenance == DataCategory.OBSERVED
        meta.check_staleness()
        assert meta.is_stale is True
        assert meta.provenance == DataCategory.STALE


class TestCurrentMaritimeState:
    """Validate composite state aggregation and risk evaluation."""

    def test_get_current_state(self):
        mgr = MaritimeStateManager()
        state = mgr.get_current_state(-65.20, 64.30, vessel_heading_deg=180.0, vessel_draft_m=8.5)
        
        assert isinstance(state, CurrentMaritimeState)
        assert state.latitude == -65.20
        assert state.longitude == 64.30
        assert 0.0 <= state.composite_navigation_risk <= 1.0
        assert 0.0 <= state.composite_safety_index <= 1.0
        assert state.imo_polar_advisory in ("CLEAR_NAVIGATION", "HEIGHTENED_WATCH", "ICE_WATCH_ESCORT_REQUIRED", "PROHIBITED_TRANSIT")
        
        # Verify provenance breakdown covers all 6 layers
        for layer in ["sea_ice", "iceberg", "bathymetry", "weather", "ocean", "satellite_sar"]:
            assert layer in state.provenance_breakdown
            assert state.provenance_breakdown[layer] in [c.value for c in DataCategory]

    def test_health_monitoring_aggregation(self):
        mgr = MaritimeStateManager()
        status = mgr.get_system_status()
        assert status["overall_status"] in ("ONLINE", "DEGRADED")
        assert status["provider_count"] == 6
        assert status["healthy_count"] + status["degraded_count"] + status["offline_count"] == 6
        assert len(status["providers"]) == 6


class TestRealTimeAPIEndpoints:
    """Validate live REST API endpoints."""

    def test_api_realtime_health(self):
        response = client.get("/api/realtime/health")
        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert data["provider_count"] == 6
        assert "providers" in data

    def test_api_realtime_state(self):
        response = client.get("/api/realtime/state?lat=-66.27&lon=110.54&vessel_heading=90&vessel_draft=8.0")
        assert response.status_code == 200
        data = response.json()
        assert data["latitude"] == -66.27
        assert data["longitude"] == 110.54
        assert "sea_ice" in data
        assert "iceberg" in data
        assert "bathymetry" in data
        assert "weather" in data
        assert "ocean" in data
        assert "satellite" in data
        assert "composite_navigation_risk" in data
        assert "provenance_breakdown" in data
