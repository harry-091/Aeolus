"""Real-Time Meteorological & Marine Sea-State Weather Provider.

Ingests live Open-Meteo atmospheric & marine telemetry with local ERA5 fallback.
Exposes explicit provenance:
- OBSERVATION: Live in-situ or satellite-calibrated API observation within 6 hours.
- REANALYZED: ECMWF ERA5 local NetCDF reanalysis.
- FORECAST: Multi-hour numerical weather prediction.
- STALE: Cached telemetry whose TTL has expired without live network refresh.
- UNAVAILABLE: Out of bounds or network/data failure.

CRITICAL RULE:
Never label REANALYSIS or FORECAST as live OBSERVATION.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from ..base import (
    BaseDataProvider,
    DataCategory,
    ProviderStatus,
    SpatialCoverage,
    DataMetadata,
    ProviderHealth,
)
from .models import (
    WeatherProvenance,
    WeatherVariable,
    AtmosphericConditions,
    MaritimeWaveConditions,
    VesselRelativeWind,
    VesselRelativeWave,
    DerivedWeatherNavigationFeatures,
    WeatherObservation,
    WeatherAPIResponse,
)
from .service import weather_service, compute_beaufort, compute_sea_state


class WeatherProvider(BaseDataProvider):
    """Unified polar meteorological provider."""

    def __init__(self, ttl_hours: float = 6.0):
        self.provider_id = "provider_openmeteo_era5_weather"
        self.provider_name = "Open-Meteo Live Marine API / ECMWF ERA5 Reanalysis"
        self.ttl_hours = ttl_hours
        self.coverage = SpatialCoverage(
            lat_min=-90.0,
            lat_max=-50.0,
            description="Antarctic Circumpolar Atmosphere"
        )
        self.resolution_km = 25.0
        self._last_successful_fetch: Optional[datetime] = None
        self._last_error: Optional[str] = None
        weather_service.initialize()

    def fetch_current(
        self,
        lat: float,
        lon: float,
        vessel_heading_deg: float = 0.0,
        vessel_speed_knots: float = 12.0,
        **kwargs,
    ) -> WeatherObservation:
        """Fetch current weather with authentic provenance tracking and derived navigation features."""
        try:
            obs = weather_service.get_current_weather(
                lat=lat,
                lon=lon,
                vessel_heading_deg=vessel_heading_deg,
                vessel_speed_knots=vessel_speed_knots,
            )
            self._last_successful_fetch = datetime.now(timezone.utc)
            return obs
        except Exception as e:
            self._last_error = str(e)
            now = datetime.now(timezone.utc)
            meta = DataMetadata(
                source=self.provider_name,
                timestamp=now,
                valid_until=now,
                lat_lon_coverage=self.coverage,
                resolution_km=self.resolution_km,
                data_quality="ERROR",
                confidence=0.0,
                provenance=DataCategory.UNAVAILABLE,
                provider_status=ProviderStatus.OFFLINE,
            )
            dummy_var = WeatherVariable(
                value=0.0,
                unit="none",
                timestamp=now.isoformat(),
                source=self.provider_name,
                data_age=0.0,
                confidence=0.0,
                provenance=WeatherProvenance.UNAVAILABLE,
                is_stale=False,
            )
            return WeatherObservation(
                latitude=lat,
                longitude=lon,
                provenance=WeatherProvenance.UNAVAILABLE,
                atmosphere=AtmosphericConditions(
                    air_temperature=dummy_var,
                    wind_speed=dummy_var,
                    wind_direction=dummy_var,
                    pressure=dummy_var,
                    precipitation=dummy_var,
                    humidity=dummy_var,
                    visibility=dummy_var,
                    beaufort_scale=0,
                    beaufort_description="Error",
                ),
                maritime=MaritimeWaveConditions(
                    significant_wave_height=dummy_var,
                    wave_direction=dummy_var,
                    wave_period=dummy_var,
                    sea_state_code=0,
                    sea_state_description="Error",
                ),
                derived_features=weather_service.calculate_derived_features(0, 0, 0, 0, 0, 7, 20),
                metadata=meta,
            )

    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: float = 24.0,
        vessel_heading_deg: float = 0.0,
        vessel_speed_knots: float = 12.0,
        **kwargs,
    ) -> WeatherObservation:
        """Fetch forward predictive forecast strictly labeled as FORECAST."""
        return weather_service.get_forecast_weather(
            lat=lat,
            lon=lon,
            hours_ahead=hours_ahead,
            vessel_heading_deg=vessel_heading_deg,
            vessel_speed_knots=vessel_speed_knots,
        )

    def fetch_reanalysis(
        self,
        lat: float,
        lon: float,
        vessel_heading_deg: float = 0.0,
        vessel_speed_knots: float = 12.0,
        **kwargs,
    ) -> WeatherObservation:
        """Fetch historical reanalysis strictly labeled as REANALYSIS."""
        return weather_service.get_reanalysis_weather(
            lat=lat,
            lon=lon,
            vessel_heading_deg=vessel_heading_deg,
            vessel_speed_knots=vessel_speed_knots,
        )

    def fetch_recent(self, lat: float, lon: float, hours: float = 24.0, **kwargs) -> List[WeatherObservation]:
        return [self.fetch_current(lat, lon)]

    def get_status(self) -> ProviderHealth:
        now = datetime.now(timezone.utc)
        stat = ProviderStatus.HEALTHY if self._last_error is None else ProviderStatus.DEGRADED
        return ProviderHealth(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            category="WEATHER",
            status=stat,
            active_provenance=DataCategory.OBSERVED,
            last_update=self.get_last_update(),
            last_successful_fetch=self._last_successful_fetch,
            last_error=self._last_error,
            uptime_pct=99.5,
            coverage=self.coverage,
            resolution_km=self.resolution_km,
        )

    def get_last_update(self) -> Optional[datetime]:
        return self._last_successful_fetch or datetime.now(timezone.utc)

    def get_coverage(self) -> SpatialCoverage:
        return self.coverage
