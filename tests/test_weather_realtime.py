"""Automated Unit & Integration Tests for Phase 4 Real-Time Weather Monitoring.

Validates:
1. BaseDataProvider contract & health diagnostics.
2. Rigorous provenance separation: OBSERVATION vs FORECAST vs REANALYSIS vs STALE.
3. Stale-data detection when observation age exceeds freshness TTL.
4. Atmospheric parameters: temperature, wind speed, wind direction, pressure, precipitation, humidity, visibility.
5. Maritime wave parameters: significant wave height, wave direction, wave period, sea state.
6. Per-variable telemetry: value, unit, timestamp, source, data_age, confidence.
7. Derived maritime navigation features: wind severity, wave severity, vessel-relative wind,
   vessel-relative wave, polar spray icing risk, composite weather risk.
8. REST API endpoints & route weather analysis.
9. Backward compatibility and integration with CurrentMaritimeState.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from realtime.weather import (
    WeatherProvenance,
    WeatherVariable,
    WeatherProvider,
    weather_service,
    compute_beaufort,
    compute_sea_state,
)
from realtime.base import DataCategory, ProviderStatus, BaseDataProvider
from realtime import maritime_state_manager
from app.server import app

client = TestClient(app)


class TestWeatherProviderContract:
    """Verify BaseDataProvider contract and health telemetry."""

    def test_provider_initialization(self):
        provider = WeatherProvider()
        assert isinstance(provider, BaseDataProvider)
        assert provider.coverage.lat_min == -90.0
        assert provider.coverage.lat_max == -50.0

    def test_provider_health(self):
        provider = WeatherProvider()
        health = provider.get_status()
        assert health.category == "WEATHER"
        assert health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
        assert health.uptime_pct >= 99.0


class TestWeatherProvenanceTiers:
    """Verify strict provenance classification and anti-falsification enforcement."""

    def test_reanalysis_never_labeled_as_observation(self):
        obs = weather_service.get_reanalysis_weather(-68.0, -60.0)
        assert obs.provenance == WeatherProvenance.REANALYSIS
        assert obs.metadata.provenance == DataCategory.REANALYZED
        assert "ECMWF ERA5" in obs.metadata.source or "Reanalysis" in obs.metadata.source
        assert obs.provenance != WeatherProvenance.OBSERVATION

    def test_forecast_provenance(self):
        obs = weather_service.get_forecast_weather(-66.0, 65.0, hours_ahead=24.0)
        assert obs.provenance == WeatherProvenance.FORECAST
        assert obs.metadata.provenance == DataCategory.FORECAST
        assert "Forecast" in obs.metadata.source or "NWP" in obs.metadata.source

    def test_stale_data_detection(self):
        """When observation age exceeds TTL, system must flag is_stale and assign STALE provenance."""
        service = weather_service
        past_time = datetime.now(timezone.utc) - timedelta(hours=10.0)  # > 6h TTL
        var = service._package_variable(
            value=25.0,
            unit="knots",
            timestamp=past_time,
            source="Test Station Pass",
            provenance=WeatherProvenance.OBSERVATION,
        )
        assert var.is_stale is True
        assert var.provenance == WeatherProvenance.STALE
        assert var.confidence < 0.90  # degraded confidence due to staleness


class TestAtmosphereAndMaritimeParameters:
    """Verify comprehensive atmospheric and wave telemetry."""

    def test_all_atmospheric_parameters_present(self):
        obs = weather_service.get_current_weather(-65.0, 64.0)
        atmos = obs.atmosphere

        # Required atmospheric parameters
        assert atmos.air_temperature is not None
        assert atmos.air_temperature.unit == "degC"
        assert -80.0 <= atmos.air_temperature.value <= 40.0

        assert atmos.wind_speed is not None
        assert atmos.wind_speed.unit == "knots"
        assert atmos.wind_speed.value >= 0.0

        assert atmos.wind_direction is not None
        assert atmos.wind_direction.unit == "deg"
        assert 0.0 <= atmos.wind_direction.value <= 360.0

        assert atmos.pressure is not None
        assert atmos.pressure.unit == "hPa"
        assert 900.0 <= atmos.pressure.value <= 1050.0

        assert atmos.precipitation is not None
        assert atmos.precipitation.unit == "mm/h"
        assert atmos.precipitation.value >= 0.0

        if atmos.humidity is not None:
            assert atmos.humidity.unit == "%"
            assert 0.0 <= atmos.humidity.value <= 100.0

        if atmos.visibility is not None:
            assert atmos.visibility.unit == "km"
            assert atmos.visibility.value >= 0.0

        assert 0 <= atmos.beaufort_scale <= 12
        assert len(atmos.beaufort_description) > 0

    def test_all_maritime_wave_parameters_present(self):
        obs = weather_service.get_current_weather(-65.0, 64.0)
        mar = obs.maritime

        assert mar.significant_wave_height is not None
        assert mar.significant_wave_height.unit == "m"
        assert mar.significant_wave_height.value >= 0.0

        assert mar.wave_direction is not None
        assert mar.wave_direction.unit == "deg"
        assert 0.0 <= mar.wave_direction.value <= 360.0

        assert mar.wave_period is not None
        assert mar.wave_period.unit == "s"
        assert mar.wave_period.value > 0.0

        assert 0 <= mar.sea_state_code <= 9
        assert len(mar.sea_state_description) > 0

    def test_per_variable_telemetry_fields(self):
        """Every single variable must expose value, unit, timestamp, source, data_age, confidence."""
        obs = weather_service.get_current_weather(-65.0, 64.0)
        vars_to_check = [
            obs.atmosphere.air_temperature,
            obs.atmosphere.wind_speed,
            obs.atmosphere.wind_direction,
            obs.atmosphere.pressure,
            obs.atmosphere.precipitation,
            obs.maritime.significant_wave_height,
            obs.maritime.wave_direction,
            obs.maritime.wave_period,
        ]
        for v in vars_to_check:
            assert isinstance(v, WeatherVariable)
            assert isinstance(v.value, (float, int))
            assert isinstance(v.unit, str) and len(v.unit) > 0
            assert isinstance(v.timestamp, str) and len(v.timestamp) > 0
            assert isinstance(v.source, str) and len(v.source) > 0
            assert v.data_age >= 0.0
            assert 0.0 <= v.confidence <= 1.0


class TestDerivedMaritimeNavigationFeatures:
    """Verify wind severity, wave severity, relative wind/waves, and weather risk."""

    def test_vessel_relative_wind_resolution(self):
        # Heading 000 (North), True Wind 090 (from East at 20 knots), Vessel speed 10 knots
        rel = weather_service.calculate_vessel_relative_wind(
            true_wind_speed_knots=20.0,
            true_wind_dir_deg=90.0,
            vessel_heading_deg=0.0,
            vessel_speed_knots=10.0,
        )
        assert rel.relative_wind_angle_deg == 90.0
        assert rel.wind_aspect in ("STARBOARD_BOW", "BEAM")
        assert rel.apparent_wind_speed_knots > 0.0

    def test_vessel_relative_wave_hazards(self):
        # Beam sea scenario: wave from 090, heading 000, wave height 3.0m
        rel = weather_service.calculate_vessel_relative_wave(
            wave_height_m=3.0,
            wave_dir_deg=90.0,
            wave_period_s=8.0,
            vessel_heading_deg=0.0,
            vessel_speed_knots=10.0,
        )
        assert rel.wave_aspect == "BEAM_SEAS"
        assert rel.beam_sea_roll_risk is True

        # Following sea scenario: wave from 180, heading 000, wave height 3.5m, high speed
        rel_foll = weather_service.calculate_vessel_relative_wave(
            wave_height_m=3.5,
            wave_dir_deg=180.0,
            wave_period_s=9.0,
            vessel_heading_deg=0.0,
            vessel_speed_knots=12.0,
        )
        assert rel_foll.wave_aspect == "FOLLOWING_SEAS"
        assert rel_foll.following_sea_broaching_risk is True

    def test_spray_icing_hazard_detection(self):
        # Extreme sub-zero cold and gale wind -> severe icing
        df = weather_service.calculate_derived_features(
            air_temp_c=-15.0,
            wind_speed_knots=35.0,
            wind_dir_deg=240.0,
            wave_height_m=3.0,
            wave_dir_deg=240.0,
            wave_period_s=7.0,
            visibility_km=5.0,
        )
        assert df.superstructure_icing_risk is True
        assert df.icing_severity in ("MODERATE", "SEVERE")
        assert df.weather_risk > 0.40

    def test_severity_indices_normalized(self):
        df = weather_service.calculate_derived_features(
            air_temp_c=-5.0,
            wind_speed_knots=25.0,
            wind_dir_deg=180.0,
            wave_height_m=2.0,
            wave_dir_deg=180.0,
            wave_period_s=8.0,
            visibility_km=15.0,
        )
        assert 0.0 <= df.wind_severity <= 1.0
        assert 0.0 <= df.wave_severity <= 1.0
        assert 0.0 <= df.weather_risk <= 1.0


class TestWeatherAPIEndpoints:
    """Verify FastAPI REST endpoints."""

    def test_api_weather_current_endpoint(self):
        res = client.get("/api/realtime/weather/current?lat=-66.0&lon=65.0&vessel_heading=045&vessel_speed=12")
        assert res.status_code == 200
        data = res.json()

        assert "value" in data
        assert "unit" in data
        assert "timestamp" in data
        assert "source" in data
        assert "data_age" in data
        assert "confidence" in data
        assert "provenance" in data
        assert "atmosphere" in data
        assert "maritime" in data
        assert "derived_navigation_features" in data

        # Validate atmosphere fields
        atmos = data["atmosphere"]
        assert "air_temperature" in atmos
        assert "wind_speed" in atmos
        assert "pressure" in atmos
        assert "precipitation" in atmos

        # Validate maritime fields
        mar = data["maritime"]
        assert "significant_wave_height" in mar
        assert "wave_direction" in mar
        assert "wave_period" in mar
        assert "sea_state_code" in mar

    def test_api_weather_forecast_endpoint(self):
        res = client.get("/api/realtime/weather/forecast?lat=-66.0&lon=65.0&hours_ahead=12")
        assert res.status_code == 200
        data = res.json()
        assert data["provenance"] == "FORECAST"

    def test_api_weather_reanalysis_endpoint(self):
        res = client.get("/api/realtime/weather/reanalysis?lat=-66.0&lon=65.0")
        assert res.status_code == 200
        data = res.json()
        assert data["provenance"] == "REANALYSIS"

    def test_api_route_weather_analysis_endpoint(self):
        payload = {
            "points": [
                {"id": "pt1", "lat": -60.0, "lon": 60.0, "heading_deg": 45.0, "speed_knots": 12.0},
                {"id": "pt2", "lat": -63.0, "lon": 62.0, "heading_deg": 60.0, "speed_knots": 12.0},
                {"id": "pt3", "lat": -66.0, "lon": 65.0, "heading_deg": 90.0, "speed_knots": 10.0},
            ]
        }
        res = client.post("/api/realtime/weather/route-analysis", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["point_count"] == 3
        assert len(data["points"]) == 3
        assert 0.0 <= data["max_weather_risk"] <= 1.0
        assert "overall_weather_advisory" in data


class TestCurrentMaritimeStateIntegration:
    """Verify integration into CurrentMaritimeState."""

    def test_current_maritime_state_weather_layer(self):
        state = maritime_state_manager.get_current_state(lat=-66.0, lon=65.0)
        assert state.weather is not None
        assert hasattr(state.weather, "atmosphere")
        assert hasattr(state.weather, "maritime")
        assert hasattr(state.weather, "derived_features")
        assert state.weather.wind_speed_knots >= 0.0
        assert state.weather.wave_height_meters >= 0.0
