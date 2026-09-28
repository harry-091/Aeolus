"""Automated Unit & Integration Tests for PolarNav Phase 7 Navigation Geometry Layer.

Validates:
1. Static in-memory persistence (zero repeat downloads).
2. Canonical functions:
   - get_depth(lat, lon)
   - is_land(lat, lon)
   - get_depth_clearance(lat, lon, vessel_draft)
3. Bathymetry depth soundings (deep ocean, continental margin, zero on land).
4. Land and continental ice sheet detection via prepared geometry.
5. Configurable vessel draft under-keel clearance calculation.
6. Prohibited shallow water and shoal grounding hazard detection.
7. Route optimizer invariants:
   - NEVER generates a route through land.
   - NEVER generates a route through prohibited shallow water.
   - NEVER generates a route with impossible vessel clearance.
8. Route geometry validation engine.
9. FastAPI REST endpoints.
10. Full backward compatibility with CurrentMaritimeState.
"""
import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from realtime.bathymetry import (
    BathymetryProvider,
    navigation_geometry_service,
    NavigationGeometryPoint,
    RouteGeometryValidationResult,
    SeabedZone,
)
from realtime.base import DataCategory, ProviderStatus, BaseDataProvider
from realtime import maritime_state_manager
from src.optimization.polar_routing_engine import routing_engine
from app.server import app

client = TestClient(app)


class TestGeometryProviderContract:
    """Verify BaseDataProvider contract and static persistence."""

    def test_provider_initialization(self):
        provider = BathymetryProvider()
        assert isinstance(provider, BaseDataProvider)
        assert provider.provider_name == "NOAA NCEI ETOPO 2022 Global Relief Model"

    def test_provider_health(self):
        provider = BathymetryProvider()
        health = provider.get_status()
        assert health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
        assert health.category == "BATHYMETRY"
        assert health.active_provenance == DataCategory.REANALYZED

    def test_static_persistence_no_repeat_downloads(self):
        """Ensure service initializes statically from local files without downloading."""
        assert navigation_geometry_service._initialized is True
        # Calling initialize again must be a fast no-op returning True
        assert navigation_geometry_service.initialize() is True

    def test_current_maritime_state_bathymetry_layer(self):
        """Verify seamless integration into CurrentMaritimeState."""
        state = maritime_state_manager.get_current_state(lat=-63.0, lon=-58.0, vessel_draft_m=8.0)
        assert hasattr(state, "bathymetry")
        assert state.bathymetry.depth_meters > 0.0
        assert state.bathymetry.under_keel_clearance_m > 0.0
        assert state.bathymetry.metadata.provenance == DataCategory.REANALYZED


class TestCanonicalGeometryFunctions:
    """Validate get_depth, is_land, and get_depth_clearance."""

    def test_get_depth_open_ocean(self):
        """Deep Drake Passage / Southern Ocean must return abyssal depths (> 1000m)."""
        depth = navigation_geometry_service.get_depth(lat=-58.0, lon=-60.0)
        assert depth >= 1000.0, f"Expected deep ocean sounding, got {depth}m"

    def test_get_depth_continental_shelf(self):
        """Continental margin waters around Antarctic Peninsula (100m - 1000m)."""
        depth = navigation_geometry_service.get_depth(lat=-63.0, lon=-58.0)
        assert 100.0 <= depth <= 1000.0, f"Expected continental shelf depth, got {depth}m"

    def test_get_depth_on_land(self):
        """Coordinates on land or continental ice sheet must return depth = 0.0m."""
        depth_pole = navigation_geometry_service.get_depth(lat=-89.0, lon=0.0)
        assert depth_pole == 0.0, f"Expected 0.0m on South Pole, got {depth_pole}m"

        depth_interior = navigation_geometry_service.get_depth(lat=-75.0, lon=-65.0)
        assert depth_interior == 0.0, f"Expected 0.0m on Antarctic interior land, got {depth_interior}m"

    def test_is_land_detection(self):
        """Verify land mask discrimination."""
        # On land
        assert navigation_geometry_service.is_land(lat=-89.0, lon=0.0) is True     # South Pole
        assert navigation_geometry_service.is_land(lat=-82.0, lon=-40.0) is True    # Ronne Ice Shelf
        assert navigation_geometry_service.is_land(lat=-64.0, lon=-60.0) is True    # Antarctic Peninsula
        assert navigation_geometry_service.is_land(lat=-75.0, lon=-65.0) is True    # Peninsula mountain spine

        # Open water
        assert navigation_geometry_service.is_land(lat=-58.0, lon=-60.0) is False   # Drake Passage
        assert navigation_geometry_service.is_land(lat=-62.0, lon=-56.0) is False   # Bransfield Strait water
        assert navigation_geometry_service.is_land(lat=-72.0, lon=-170.0) is False  # Ross Sea open water

    def test_get_depth_clearance(self):
        """Verify under-keel clearance calculation (depth - draft)."""
        # Deep water: 3500m depth with 8.0m draft -> clearance = 3492.0m
        clearance_deep = navigation_geometry_service.get_depth_clearance(lat=-58.0, lon=-60.0, vessel_draft=8.0)
        assert clearance_deep > 1000.0

        # On land: depth is 0.0m with 10.0m draft -> clearance = -10.0m (severe grounding)
        clearance_land = navigation_geometry_service.get_depth_clearance(lat=-89.0, lon=0.0, vessel_draft=10.0)
        assert clearance_land == -10.0

        # Custom configurable draft: 15.0m draft vs 8.0m draft
        c_8 = navigation_geometry_service.get_depth_clearance(lat=-64.0, lon=-60.0, vessel_draft=8.0)
        c_15 = navigation_geometry_service.get_depth_clearance(lat=-64.0, lon=-60.0, vessel_draft=15.0)
        assert c_8 - c_15 == pytest.approx(7.0, abs=0.01)

    def test_prohibited_shallow_water_detection(self):
        """Verify shallow water flag and grounding hazard classification."""
        pt_ocean = navigation_geometry_service.evaluate_point(lat=-58.0, lon=-60.0, vessel_draft=8.0)
        assert pt_ocean.is_land is False
        assert pt_ocean.is_shallow is False
        assert pt_ocean.is_navigable is True
        assert pt_ocean.seabed_zone in (SeabedZone.ABYSSAL_PLAIN, SeabedZone.CONTINENTAL_SLOPE)

        pt_land = navigation_geometry_service.evaluate_point(lat=-89.0, lon=0.0, vessel_draft=8.0)
        assert pt_land.is_land is True
        assert pt_land.depth_meters == 0.0
        assert pt_land.under_keel_clearance_m < 0.0
        assert pt_land.is_navigable is False
        assert pt_land.seabed_zone == SeabedZone.LAND


class TestRouteOptimizerGeometryInvariants:
    """Verify route optimizer NEVER generates a route through land, shallow water, or impossible clearance."""

    @classmethod
    def setup_class(cls):
        routing_engine.initialize()

    def test_route_optimizer_never_crosses_land(self):
        """Generate route across Antarctic Peninsula and verify zero land collisions."""
        # Route from King George Island (-62.2, -58.9) to Marguerite Bay (-67.8, -67.5)
        res = routing_engine.solve_route(
            s_lon=-58.9,
            s_lat=-62.2,
            d_lon=-67.5,
            d_lat=-67.8,
            departure_dt="2026-03-01T00:00:00Z",
            vessel_speed_kn=12.0,
            mode="BALANCED",
            vessel_draft_m=8.5,
        )
        assert "path_coordinates" in res
        path = res["path_coordinates"]
        assert len(path) >= 5, "Route should generate a valid trajectory"

        # Check EVERY waypoint in generated route
        for pt in path:
            lat, lon = pt[0], pt[1]
            assert navigation_geometry_service.is_land(lat, lon) is False, f"Route crossed land at ({lat}, {lon})!"

    def test_route_optimizer_never_crosses_prohibited_shallow_water(self):
        """Generate route with deep draft (12.0m) and verify all waypoints have safe clearance."""
        vessel_draft = 12.0
        res = routing_engine.solve_route(
            s_lon=-58.9,
            s_lat=-62.2,
            d_lon=-67.5,
            d_lat=-67.8,
            departure_dt="2026-03-01T00:00:00Z",
            vessel_speed_kn=12.0,
            mode="BALANCED",
            vessel_draft_m=vessel_draft,
        )
        path = res["path_coordinates"]

        for pt in path:
            lat, lon = pt[0], pt[1]
            depth = navigation_geometry_service.get_depth(lat, lon)
            clearance = navigation_geometry_service.get_depth_clearance(lat, lon, vessel_draft)
            assert depth >= 12.0, f"Prohibited shallow water at ({lat}, {lon}) with depth {depth}m!"
            assert clearance >= 0.0, f"Impossible vessel clearance at ({lat}, {lon}): {clearance}m under draft {vessel_draft}m!"

    def test_validate_route_geometry_audit(self):
        """Verify audit engine catches land intrusion on invalid route and passes valid route."""
        # 1. Valid offshore route
        valid_route = [
            [-60.0, -60.0],
            [-61.0, -60.5],
            [-62.0, -61.0],
        ]
        audit_valid = navigation_geometry_service.validate_route_geometry(valid_route, vessel_draft=8.0)
        assert audit_valid.is_valid is True
        assert audit_valid.land_violations_count == 0
        assert audit_valid.min_clearance_m > 50.0

        # 2. Invalid route cutting directly across Antarctic continent
        invalid_route = [
            [-65.0, -60.0],  # Peninsula coast
            [-75.0, -60.0],  # Land mass interior
            [-80.0, -60.0],  # Continental ice sheet
        ]
        audit_invalid = navigation_geometry_service.validate_route_geometry(invalid_route, vessel_draft=8.0)
        assert audit_invalid.is_valid is False
        assert audit_invalid.land_violations_count > 0


class TestGeometryAPIEndpoints:
    """Verify FastAPI REST endpoints."""

    def test_api_geometry_depth_endpoint(self):
        res = client.get("/api/realtime/geometry/depth?lat=-63.0&lon=-58.0")
        assert res.status_code == 200
        data = res.json()
        assert "depth_meters" in data
        assert "is_land" in data
        assert data["depth_meters"] > 0.0

    def test_api_geometry_is_land_endpoint(self):
        res_land = client.get("/api/realtime/geometry/is-land?lat=-89.0&lon=0.0")
        assert res_land.status_code == 200
        assert res_land.json()["is_land"] is True

        res_water = client.get("/api/realtime/geometry/is-land?lat=-58.0&lon=-60.0")
        assert res_water.status_code == 200
        assert res_water.json()["is_land"] is False

    def test_api_geometry_clearance_endpoint(self):
        res = client.get("/api/realtime/geometry/clearance?lat=-63.0&lon=-58.0&vessel_draft=9.5")
        assert res.status_code == 200
        data = res.json()
        assert "under_keel_clearance_m" in data
        assert "is_navigable" in data
        assert "seabed_zone" in data

    def test_api_geometry_validate_route_endpoint(self):
        payload = {
            "waypoints": [
                [-60.0, -60.0],
                [-61.0, -60.5],
                [-62.0, -61.0],
            ],
            "vessel_draft": 8.0,
            "min_clearance_m": 2.0,
        }
        res = client.post("/api/realtime/geometry/validate-route", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "is_valid" in data
        assert data["is_valid"] is True
        assert "land_violations_count" in data
        assert data["land_violations_count"] == 0
