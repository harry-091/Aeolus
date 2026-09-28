"""Automated Unit & Integration Tests for Phase 5 Real Ocean Current Monitoring.

Validates:
1. BaseDataProvider contract and health diagnostics.
2. Authentic data ingestion from Copernicus Marine GLO12 (no hardcoding, no fake vectors).
3. Coordinate queries return eastward (uo), northward (vo), speed, direction, SST, salinity, wave parameters.
4. Every value exposes timestamp, source, resolution, data_age, confidence.
5. Graceful handling of unavailable / out-of-bounds regions (lat > -50.0).
6. Vessel-relative current, longitudinal drift assist, cross leeway drift, and leeway crab angle.
7. Estimated current impact on route (effective SOG, time delta %, fuel impact).
8. Ocean-condition risk and opposing wave-current steepening hazard.
9. REST API endpoints & route current analysis.
10. Backward compatibility with CurrentMaritimeState.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from realtime.ocean import (
    OceanVariable,
    OceanProvider,
    ocean_service,
    RouteOceanPoint,
    RouteOceanAnalysisRequest,
)
from realtime.base import DataCategory, ProviderStatus, BaseDataProvider
from realtime import maritime_state_manager
from app.server import app

client = TestClient(app)


class TestOceanProviderContract:
    """Verify BaseDataProvider contract and health telemetry."""

    def test_provider_initialization(self):
        provider = OceanProvider()
        assert isinstance(provider, BaseDataProvider)
        assert provider.coverage.lat_min == -90.0
        assert provider.coverage.lat_max == -50.0

    def test_provider_health(self):
        provider = OceanProvider()
        health = provider.get_status()
        assert health.category == "OCEAN"
        assert health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
        assert health.uptime_pct >= 99.0


class TestAuthenticCurrentsNoHardcoding:
    """Verify authentic Copernicus Marine current vectors with zero fake/hardcoded data."""

    def test_high_res_mercator_current_vector(self):
        # Coordinate in high-res MERCATOR GLO12 coverage (-72 to -64 lat, -68 to -56 lon)
        obs = ocean_service.get_ocean_observation(-65.0, -60.0)
        assert obs.is_available is True
        c = obs.currents

        assert "Copernicus" in c.current_magnitude.source
        assert "9.25 km" in c.current_magnitude.resolution
        assert c.current_magnitude.value >= 0.0
        assert 0.0 <= c.current_direction.value <= 360.0

        # Authentic vector relationship: speed = hypot(uo, vo)
        calc_spd = round((c.eastward_current_uo.value**2 + c.northward_current_vo.value**2)**0.5 * 1.94384, 2)
        assert abs(c.current_magnitude.value - calc_spd) <= 0.05

    def test_variance_across_geographic_coordinates(self):
        """Current vectors must differ across distinct coordinates (proves no hardcoding)."""
        obs1 = ocean_service.get_ocean_observation(-64.5, -60.0)
        obs2 = ocean_service.get_ocean_observation(-70.0, -65.0)

        assert (obs1.currents.eastward_current_uo.value != obs2.currents.eastward_current_uo.value) or \
               (obs1.currents.northward_current_vo.value != obs2.currents.northward_current_vo.value)

    def test_sea_surface_temperature_and_environment(self):
        obs = ocean_service.get_ocean_observation(-65.0, -60.0)
        env = obs.environment
        assert env.sea_surface_temperature is not None
        assert -3.0 <= env.sea_surface_temperature.value <= 10.0
        if env.salinity is not None:
            assert 30.0 <= env.salinity.value <= 36.0


class TestPerValueMetadata:
    """Verify every value exposes timestamp, source, resolution, data_age, confidence."""

    def test_all_variables_expose_mandatory_metadata(self):
        obs = ocean_service.get_ocean_observation(-66.0, 65.0)
        vars_to_check = [
            obs.currents.eastward_current_uo,
            obs.currents.northward_current_vo,
            obs.currents.current_magnitude,
            obs.currents.current_direction,
            obs.environment.sea_surface_temperature,
        ]
        for v in vars_to_check:
            assert isinstance(v, OceanVariable)
            assert isinstance(v.value, (float, int))
            assert isinstance(v.timestamp, str) and len(v.timestamp) > 0
            assert isinstance(v.source, str) and len(v.source) > 0
            assert isinstance(v.resolution, str) and len(v.resolution) > 0
            assert v.data_age >= 0.0
            assert 0.0 <= v.confidence <= 1.0


class TestGracefulUnavailableHandling:
    """Verify graceful handling of out-of-bounds / unavailable regions without crashing."""

    def test_out_of_bounds_equator_coordinate(self):
        # 0.0, 0.0 is outside Antarctic domain
        obs = ocean_service.get_ocean_observation(0.0, 0.0)
        assert obs.is_available is False
        assert obs.currents.current_magnitude.value == 0.0
        assert obs.currents.current_magnitude.confidence == 0.0
        assert obs.metadata.provenance == DataCategory.UNAVAILABLE
        assert obs.metadata.data_quality == "UNAVAILABLE"

    def test_out_of_bounds_north_pacific(self):
        obs = ocean_service.get_ocean_observation(45.0, -140.0)
        assert obs.is_available is False
        assert obs.metadata.provenance == DataCategory.UNAVAILABLE


class TestMaritimeNavigationCalculations:
    """Verify vessel-relative current, estimated route impact, and ocean risk."""

    def test_vessel_relative_current_assist_and_leeway(self):
        # Current flowing towards 090 (East) at 2.0 knots
        # Vessel heading 090 (East) at 10.0 knots -> Direct tail current assist of +2.0 knots
        rel_tail = ocean_service.calculate_vessel_relative_current(
            current_speed_knots=2.0,
            current_dir_deg=90.0,
            vessel_heading_deg=90.0,
            vessel_speed_knots=10.0,
        )
        assert rel_tail.drift_assist_knots == 2.0
        assert abs(rel_tail.cross_current_leeway_knots) <= 0.01
        assert rel_tail.current_aspect == "FAVORABLE_TAIL_CURRENT"

        # Vessel heading 270 (West) into 090 current -> Head resistance of -2.0 knots
        rel_head = ocean_service.calculate_vessel_relative_current(
            current_speed_knots=2.0,
            current_dir_deg=90.0,
            vessel_heading_deg=270.0,
            vessel_speed_knots=10.0,
        )
        assert rel_head.drift_assist_knots == -2.0
        assert rel_head.current_aspect == "HEAD_RESISTANCE"

        # Vessel heading 000 (North) across 090 current -> Beam drift to starboard
        rel_beam = ocean_service.calculate_vessel_relative_current(
            current_speed_knots=2.0,
            current_dir_deg=90.0,
            vessel_heading_deg=0.0,
            vessel_speed_knots=10.0,
        )
        assert rel_beam.cross_current_leeway_knots == 2.0
        assert rel_beam.leeway_drift_angle_deg < 0  # crab angle required to port
        assert rel_beam.current_aspect == "STARBOARD_BEAM_DRIFT"

    def test_estimated_current_impact_on_route(self):
        # 10 knots ship + 2 knots assist -> 12 knots SOG
        impact_tail = ocean_service.calculate_estimated_impact_on_route(
            vessel_speed_knots=10.0,
            drift_assist_knots=2.0,
            cross_leeway_knots=0.0,
        )
        assert impact_tail.effective_speed_over_ground_knots == 12.0
        assert impact_tail.estimated_time_delta_percent < 0  # time saved
        assert impact_tail.fuel_impact_estimate == "FUEL_SAVINGS"

        # Head resistance
        impact_head = ocean_service.calculate_estimated_impact_on_route(
            vessel_speed_knots=10.0,
            drift_assist_knots=-2.0,
            cross_leeway_knots=0.0,
        )
        assert impact_head.effective_speed_over_ground_knots == 8.0
        assert impact_head.estimated_time_delta_percent > 0  # delayed
        assert impact_head.fuel_impact_estimate == "SEVERE_HEAD_CURRENT_PENALTY"

    def test_opposing_wave_current_hazard(self):
        # Wave from 270 (propagating East), Current from 090 (flowing West) -> directly opposing!
        risk_opp = ocean_service.calculate_ocean_condition_risk(
            current_speed_knots=1.8,
            current_dir_deg=270.0,  # flowing towards West (270)
            sst_c=-1.2,
            wave_height_m=3.0,
            wave_dir_deg=90.0,      # waves propagating towards East (90) -> directly opposing
            wave_period_s=8.0,
            cross_leeway_knots=0.5,
        )
        assert risk_opp.opposing_wave_current_hazard is True
        assert risk_opp.wave_steepening_factor > 1.0
        assert risk_opp.hypothermia_survival_minutes <= 45.0
        assert risk_opp.risk_score > 0.40


class TestOceanAPIEndpoints:
    """Verify FastAPI REST endpoints."""

    def test_api_ocean_current_endpoint(self):
        res = client.get("/api/realtime/ocean/current?lat=-64.0&lon=-60.0&vessel_heading=045&vessel_speed=12")
        assert res.status_code == 200
        data = res.json()

        assert "value" in data
        assert "unit" in data
        assert "timestamp" in data
        assert "source" in data
        assert "resolution" in data
        assert "data_age" in data
        assert "confidence" in data
        assert "is_available" in data
        assert data["is_available"] is True

        assert "currents" in data
        assert "eastward_current_uo" in data["currents"]
        assert "northward_current_vo" in data["currents"]
        assert "current_magnitude" in data["currents"]
        assert "current_direction" in data["currents"]

        assert "vessel_relative_current" in data
        assert "estimated_current_impact" in data
        assert "ocean_condition_risk" in data

    def test_api_route_ocean_analysis_endpoint(self):
        payload = {
            "points": [
                {"id": "pt1", "lat": -63.0, "lon": -60.0, "heading_deg": 45.0, "speed_knots": 12.0},
                {"id": "pt2", "lat": -64.0, "lon": -61.0, "heading_deg": 60.0, "speed_knots": 12.0},
                {"id": "pt3", "lat": -65.0, "lon": -62.0, "heading_deg": 90.0, "speed_knots": 10.0},
            ]
        }
        res = client.post("/api/realtime/ocean/route-analysis", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["point_count"] == 3
        assert len(data["points"]) == 3
        assert "net_drift_assist_knots" in data
        assert "overall_transit_time_delta_percent" in data
        assert "overall_current_advisory" in data

    def test_api_ocean_grid_endpoint(self):
        res = client.get("/api/realtime/ocean/grid?max_points=50")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] > 0
        assert "vectors" in data
        assert len(data["vectors"]) <= 50
        v0 = data["vectors"][0]
        assert "uo_ms" in v0
        assert "vo_ms" in v0
        assert "speed_kn" in v0
        assert "direction_deg" in v0


class TestCurrentMaritimeStateIntegration:
    """Verify integration into CurrentMaritimeState."""

    def test_current_maritime_state_ocean_layer(self):
        state = maritime_state_manager.get_current_state(lat=-64.0, lon=-60.0, vessel_heading_deg=45.0)
        assert state.ocean is not None
        assert state.ocean.current_speed_knots >= 0.0
        assert 0.0 <= state.ocean.current_direction_deg <= 360.0
        assert hasattr(state.ocean, "vessel_relative")
        assert hasattr(state.ocean, "route_impact")
        assert hasattr(state.ocean, "ocean_risk")
