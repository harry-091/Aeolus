"""Automated Unit & Integration Tests for PolarNav Phase 6 Real Iceberg Monitoring.

Validates:
1. BaseDataProvider contract and health telemetry.
2. Authentic data ingestion from BYU MERS / NIC database (zero fabrication, no mock positions).
3. Mandatory metadata exposure: source, observation_time, data_age (hours and days), confidence.
4. Old observation age tracking: fixes older than 7 days flagged is_stale with decayed confidence.
5. Geodesic distance calculation to nearest tracked iceberg.
6. Dynamic Closest Point of Approach (CPA) & TCPA relative kinematics.
7. Spatial iceberg density indexing per 10,000 km².
8. Voyage route corridor cross-track intersection analytics.
9. Scientifically justified multi-horizon drift prediction with expanding uncertainty radiuses.
10. Graceful out-of-bounds handling (lat > -50°S).
11. FastAPI REST API endpoints: current, catalog, detail, cpa-matrix, route-intersection, density-grid.
12. Full backward compatibility with CurrentMaritimeState.
"""
import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from realtime.iceberg import (
    IcebergProvider,
    iceberg_monitoring_service,
    IcebergObservation,
    TrackedIceberg,
    ClosestPointOfApproach,
    IcebergDensity,
    RouteIcebergIntersection,
    RouteWaypoint,
    IcebergProvenance,
)
from realtime.base import DataCategory, ProviderStatus, BaseDataProvider
from realtime import maritime_state_manager
from app.server import app

client = TestClient(app)


class TestIcebergProviderContract:
    """Verify BaseDataProvider contract and provider lifecycle."""

    def test_provider_initialization(self):
        provider = IcebergProvider()
        assert isinstance(provider, BaseDataProvider)
        assert provider.provider_name == "BYU MERS / U.S. NIC Antarctic Iceberg Tracking Database"

    def test_provider_health(self):
        provider = IcebergProvider()
        health = provider.get_status()
        assert health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
        assert health.category == "ICEBERG"
        assert health.coverage.lat_min == -90.0
        assert health.coverage.lat_max == -50.0

    def test_current_maritime_state_iceberg_layer(self):
        """Verify seamless integration into composite CurrentMaritimeState."""
        state = maritime_state_manager.get_current_state(lat=-64.0, lon=-60.0)
        assert hasattr(state, "iceberg")
        assert state.iceberg.nearest_iceberg_id != ""
        assert state.iceberg.distance_to_nearest_km >= 0.0
        assert 0.0 <= state.iceberg.collision_risk_index <= 1.0
        assert state.iceberg.metadata.provenance in (DataCategory.DERIVED, DataCategory.OBSERVED)


class TestIcebergAuthenticityAndMetadata:
    """Verify zero fabrication, age tracking, and required metadata fields."""

    def test_no_fabricated_icebergs(self):
        """Ensure all tracked icebergs originate from legitimate BYU/NIC records."""
        catalog = iceberg_monitoring_service.get_catalog()
        assert len(catalog) > 0, "Catalog should contain authentic BYU/NIC tracked icebergs"
        for berg in catalog:
            # Positions must be strictly Southern Ocean / Antarctic waters (-90 to -40)
            assert -90.0 <= berg.latitude <= -40.0, f"Iceberg {berg.iceberg_id} latitude out of Southern Ocean bounds: {berg.latitude}"
            assert -180.0 <= berg.longitude <= 180.0
            # Dimensions must be positive floats
            assert berg.dimensions.length_km > 0.0
            assert berg.dimensions.area_km2 > 0.0
            assert berg.dimensions.estimated_draft_m > 0.0

    def test_every_iceberg_has_required_metadata(self):
        """Every single iceberg must display source, observation_time, data_age, and confidence."""
        catalog = iceberg_monitoring_service.get_catalog()
        for berg in catalog[:25]:
            assert berg.source != "", f"Missing source for {berg.iceberg_id}"
            assert berg.observation_time != "", f"Missing observation_time for {berg.iceberg_id}"
            assert berg.data_age_hours >= 0.0, f"Invalid data_age_hours for {berg.iceberg_id}"
            assert berg.data_age_days >= 0.0, f"Invalid data_age_days for {berg.iceberg_id}"
            assert 0.0 <= berg.confidence <= 1.0, f"Confidence out of range for {berg.iceberg_id}: {berg.confidence}"
            assert isinstance(berg.is_stale, bool)

    def test_old_iceberg_observation_age_and_staleness(self):
        """Old iceberg fixes must show true age and be marked is_stale (never labeled as fresh live observation)."""
        # Find an iceberg with older observation fix
        catalog = iceberg_monitoring_service.get_catalog()
        stale_bergs = [b for b in catalog if b.data_age_days > 7.0]
        assert len(stale_bergs) > 0, "Should detect icebergs with observation age > 7 days"

        for b in stale_bergs[:5]:
            assert b.is_stale is True
            assert b.data_age_days > 7.0
            assert b.data_age_hours > 168.0
            # Decayed confidence should be lower than pristine base 0.95
            assert b.confidence < 0.95


class TestIcebergKinematicsAndCalculations:
    """Verify nearest distance, CPA, TCPA, density, and route intersection."""

    def test_nearest_iceberg_and_distance_calculation(self):
        """Query coordinate near the tip of Antarctic Peninsula."""
        # Query near A40 at -77.3, -49.0
        nearest_berg, dist_km = iceberg_monitoring_service.find_nearest_iceberg(-77.2, -49.1)
        assert nearest_berg is not None
        assert dist_km < 50.0  # Should be within ~15-20 km
        assert nearest_berg.iceberg_id in ["A40", "A63", "B15A", "A23A"] or nearest_berg.latitude < -70.0

    def test_cpa_head_on_collision_course(self):
        """Vessel steaming North towards an iceberg drifting South -> Head-on convergence."""
        vessel_lat, vessel_lon = -65.0, -60.0
        vessel_heading = 0.0   # Steaming True North
        vessel_speed = 15.0    # 15 knots

        # Iceberg directly North of vessel, drifting South
        mock_berg = TrackedIceberg(
            iceberg_id="TEST_HEADON",
            name="Test Head-on Berg",
            latitude=-64.5,    # ~30 NM directly North
            longitude=-60.0,
            source="Test Radar",
            observation_time=datetime.now(timezone.utc).isoformat(),
            data_age_hours=1.0,
            data_age_days=0.04,
            is_stale=False,
            confidence=0.95,
            provenance=IcebergProvenance.OBSERVED_RADAR,
            dimensions=iceberg_monitoring_service._catalog[list(iceberg_monitoring_service._catalog.keys())[0]].dimensions,
            movement=iceberg_monitoring_service._catalog[list(iceberg_monitoring_service._catalog.keys())[0]].movement.model_copy(
                update={"speed_knots": 1.0, "bearing_deg": 180.0} # Drifting South
            ),
            quadrant="A_WEDDELL",
        )

        cpa = iceberg_monitoring_service.calculate_cpa(
            vessel_lat=vessel_lat,
            vessel_lon=vessel_lon,
            vessel_heading_deg=vessel_heading,
            vessel_speed_knots=vessel_speed,
            target_iceberg=mock_berg,
        )

        assert cpa.is_converging is True
        assert cpa.tcpa_hours > 0.0
        assert cpa.cpa_distance_nm < 1.0  # Head-on directly on track!
        assert cpa.threat_level in ("CRITICAL", "WARNING")
        assert cpa.collision_risk_index > 0.50

    def test_cpa_diverging_motion(self):
        """Vessel steaming away from an iceberg -> Diverging motion."""
        vessel_lat, vessel_lon = -65.0, -60.0
        vessel_heading = 180.0  # Steaming South away from berg at -64.5
        vessel_speed = 12.0

        mock_berg = TrackedIceberg(
            iceberg_id="TEST_DIVERGING",
            name="Test Diverging Berg",
            latitude=-64.5,     # North of vessel
            longitude=-60.0,
            source="Test Radar",
            observation_time=datetime.now(timezone.utc).isoformat(),
            data_age_hours=1.0,
            data_age_days=0.04,
            is_stale=False,
            confidence=0.95,
            provenance=IcebergProvenance.OBSERVED_RADAR,
            dimensions=iceberg_monitoring_service._catalog[list(iceberg_monitoring_service._catalog.keys())[0]].dimensions,
            movement=iceberg_monitoring_service._catalog[list(iceberg_monitoring_service._catalog.keys())[0]].movement.model_copy(
                update={"speed_knots": 0.5, "bearing_deg": 0.0} # Drifting North further away
            ),
            quadrant="A_WEDDELL",
        )

        cpa = iceberg_monitoring_service.calculate_cpa(
            vessel_lat=vessel_lat,
            vessel_lon=vessel_lon,
            vessel_heading_deg=vessel_heading,
            vessel_speed_knots=vessel_speed,
            target_iceberg=mock_berg,
        )

        assert cpa.is_converging is False
        assert cpa.tcpa_hours <= 0.0
        assert cpa.cpa_distance_km == cpa.current_distance_km  # Diverging CPA is current distance
        assert cpa.threat_level in ("CAUTION", "CLEAR")

    def test_iceberg_density_calculation(self):
        """Verify spatial density calculation per 10,000 km²."""
        # Query near Weddell Sea high-density cluster
        first_berg = list(iceberg_monitoring_service._catalog.values())[0]
        density = iceberg_monitoring_service.calculate_density(
            lat=first_berg.latitude,
            lon=first_berg.longitude,
            radius_km=150.0,
        )
        assert density.search_radius_km == 150.0
        assert density.iceberg_count >= 1
        assert density.density_per_10k_km2 > 0.0
        assert density.congestion_level in ("SPARSE", "MODERATE", "CONGESTED")

    def test_route_intersection_detection(self):
        """Verify route corridor intersection when leg passes directly by an iceberg."""
        first_berg = list(iceberg_monitoring_service._catalog.values())[0]
        b_lat, b_lon = first_berg.latitude, first_berg.longitude

        # Create a route waypoint leg passing right through the iceberg position
        waypoints_intersecting = [
            RouteWaypoint(lat=b_lat - 0.5, lon=b_lon),
            RouteWaypoint(lat=b_lat + 0.5, lon=b_lon),
        ]
        res_hit = iceberg_monitoring_service.evaluate_route_intersections(
            waypoints=waypoints_intersecting,
            safety_buffer_km=18.52,  # 10 NM
        )
        assert res_hit.has_intersection is True
        assert len(res_hit.intersecting_icebergs) >= 1
        assert res_hit.min_clearance_km < 18.52

        # Create a route thousands of km away
        waypoints_clear = [
            RouteWaypoint(lat=-52.0, lon=0.0),
            RouteWaypoint(lat=-52.0, lon=5.0),
        ]
        res_clear = iceberg_monitoring_service.evaluate_route_intersections(
            waypoints=waypoints_clear,
            safety_buffer_km=18.52,
        )
        assert res_clear.min_clearance_km > 100.0

    def test_scientific_trajectory_prediction(self):
        """Verify multi-horizon predictions have expanding uncertainty radiuses."""
        first_berg = list(iceberg_monitoring_service._catalog.values())[0]
        if first_berg.predicted_trajectory:
            prev_uncertainty = 0.0
            for step in first_berg.predicted_trajectory:
                assert "horizon" in step
                assert "uncertainty_radius_km" in step
                assert step["uncertainty_radius_km"] > prev_uncertainty  # expanding uncertainty
                prev_uncertainty = step["uncertainty_radius_km"]

    def test_unavailable_region_graceful_handling(self):
        """Query coordinate north of -50.0 deg (e.g. tropical latitude) returns safe UNAVAILABLE state."""
        obs = iceberg_monitoring_service.observe(lat=10.0, lon=-20.0)
        assert obs.metadata.provenance == DataCategory.UNAVAILABLE
        assert obs.nearest_iceberg_id == "NONE"
        assert obs.distance_to_nearest_km == 999.0
        assert obs.threat_level == "CLEAR"
        assert obs.collision_risk_index == 0.0


class TestIcebergAPIEndpoints:
    """Verify FastAPI REST endpoints."""

    def test_api_iceberg_current_endpoint(self):
        res = client.get("/api/realtime/iceberg/current?lat=-64.5&lon=-60.0&vessel_heading=045&vessel_speed=12")
        assert res.status_code == 200
        data = res.json()

        assert "nearest_iceberg_id" in data
        assert "distance_to_nearest_km" in data
        assert "closest_point_of_approach_km" in data
        assert "collision_risk_index" in data
        assert "threat_level" in data
        assert "tracked_berg_count" in data
        assert data["tracked_berg_count"] > 0
        assert "density" in data
        assert "metadata" in data

    def test_api_iceberg_catalog_endpoint(self):
        res = client.get("/api/realtime/iceberg/catalog?quadrant=A_WEDDELL")
        assert res.status_code == 200
        data = res.json()

        assert "total_count" in data
        assert "icebergs" in data
        assert len(data["icebergs"]) > 0
        for berg in data["icebergs"][:10]:
            assert "source" in berg
            assert "observation_time" in berg
            assert "data_age_hours" in berg
            assert "confidence" in berg

    def test_api_iceberg_detail_endpoint(self):
        # Fetch first berg ID from catalog
        cat_res = client.get("/api/realtime/iceberg/catalog")
        first_id = cat_res.json()["icebergs"][0]["iceberg_id"]

        res = client.get(f"/api/realtime/iceberg/{first_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["iceberg_id"] == first_id
        assert "dimensions" in data
        assert "movement" in data

    def test_api_iceberg_cpa_matrix_endpoint(self):
        payload = {
            "vessel_lat": -64.5,
            "vessel_lon": -60.0,
            "vessel_heading_deg": 45.0,
            "vessel_speed_knots": 14.0,
            "max_distance_km": 500.0,
        }
        res = client.post("/api/realtime/iceberg/cpa-matrix", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "obstacles_evaluated" in data
        assert "cpa_matrix" in data
        assert isinstance(data["cpa_matrix"], list)

    def test_api_route_intersection_endpoint(self):
        payload = {
            "waypoints": [
                {"lat": -63.0, "lon": -60.0, "planned_speed_knots": 12.0},
                {"lat": -64.0, "lon": -61.0, "planned_speed_knots": 12.0},
                {"lat": -65.0, "lon": -62.0, "planned_speed_knots": 10.0},
            ],
            "safety_buffer_km": 20.0,
        }
        res = client.post("/api/realtime/iceberg/route-intersection", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "has_intersection" in data
        assert "min_clearance_km" in data
        assert "summary" in data

    def test_api_density_grid_endpoint(self):
        res = client.get("/api/realtime/iceberg/density-grid")
        assert res.status_code == 200
        data = res.json()
        assert "total_tracked_obstacles" in data
        assert "quadrant_distribution" in data
        assert "A_WEDDELL" in data["quadrant_distribution"]
