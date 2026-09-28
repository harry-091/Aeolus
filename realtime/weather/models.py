"""Domain models and Pydantic schemas for Antarctic Weather Monitoring.

Supports:
- Provenance separation: OBSERVATION vs FORECAST vs REANALYSIS vs STALE
- Atmosphere: air temperature, wind speed, wind direction, pressure, precipitation, humidity, visibility
- Maritime: significant wave height, wave direction, wave period, sea state
- Per-variable telemetry: value, unit, timestamp, source, data_age, confidence
- Stale data detection
- Derived navigation features: wind severity, wave severity, vessel-relative wind, vessel-relative wave, weather risk
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field

from ..base import DataCategory, DataMetadata, ProviderStatus, SpatialCoverage


class WeatherProvenance(str, Enum):
    """Rigorous weather data provenance classification.
    
    CRITICAL RULE:
    Never label REANALYSIS or FORECAST as live OBSERVATION.
    """
    OBSERVATION = "OBSERVATION"      # Live in-situ / calibrated satellite pass / AWS reading
    FORECAST = "FORECAST"            # Forward numerical weather prediction (NWP)
    REANALYSIS = "REANALYSIS"        # Climate reanalysis (e.g. ERA5, GLO12)
    STALE = "STALE"                  # Telemetry whose freshness TTL has expired
    UNAVAILABLE = "UNAVAILABLE"      # Sensor offline or coordinate out of bounds


class WeatherVariable(BaseModel):
    """Standardized telemetry container for an individual weather measurement.
    
    Exposes: value, unit, timestamp, source, data_age, confidence.
    """
    value: float
    unit: str                        # "degC", "knots", "m/s", "deg", "hPa", "mm/h", "%", "km", "m", "s"
    timestamp: str                   # ISO-8601 UTC observation timestamp
    source: str                      # Legitimate product identifier
    data_age: float                  # Age in seconds from queried / reference moment
    confidence: float                # 0.0 to 1.0 confidence score
    provenance: WeatherProvenance = WeatherProvenance.OBSERVATION
    is_stale: bool = False


class AtmosphericConditions(BaseModel):
    """Atmospheric meteorological state at a geographic coordinate."""
    air_temperature: WeatherVariable
    wind_speed: WeatherVariable
    wind_direction: WeatherVariable
    pressure: WeatherVariable
    precipitation: WeatherVariable
    humidity: Optional[WeatherVariable] = None
    visibility: Optional[WeatherVariable] = None
    beaufort_scale: int
    beaufort_description: str


class MaritimeWaveConditions(BaseModel):
    """Ocean wave dynamics and sea-state conditions."""
    significant_wave_height: WeatherVariable
    wave_direction: WeatherVariable
    wave_period: WeatherVariable
    sea_state_code: int             # WMO Sea State 0 to 9
    sea_state_description: str      # e.g., "Moderate", "Rough", "Very Rough", "High"


class VesselRelativeWind(BaseModel):
    """Apparent and relative wind vector encounter dynamics."""
    relative_wind_angle_deg: float   # -180.0 to +180.0 relative to bow (0 = dead ahead)
    apparent_wind_speed_knots: float # Vector sum of true wind and vessel velocity
    apparent_wind_speed_ms: float
    wind_aspect: str                 # "HEAD_WIND", "PORT_BOW", "STARBOARD_BOW", "BEAM", "QUARTERING", "FOLLOWING"
    gust_factor: float = 1.25


class VesselRelativeWave(BaseModel):
    """Relative sea encounter dynamics and stability risk."""
    relative_wave_angle_deg: float   # Encounter angle relative to heading
    wave_aspect: str                 # "HEAD_SEAS", "BOW_QUARTERING", "BEAM_SEAS", "STERN_QUARTERING", "FOLLOWING_SEAS"
    encounter_period_seconds: float  # Doppler-shifted wave encounter period
    beam_sea_roll_risk: bool         # High roll resonance hazard in beam seas
    following_sea_broaching_risk: bool # Broaching hazard when vessel speed ~ wave celerity


class DerivedWeatherNavigationFeatures(BaseModel):
    """Derived maritime safety and stability indicators."""
    wind_severity: float             # Normalized index 0.0 (calm) to 1.0 (extreme gale)
    wind_severity_category: str      # "LIGHT", "MODERATE", "STRONG", "GALE", "STORM", "VIOLENT_STORM"
    wave_severity: float             # Normalized index 0.0 (calm) to 1.0 (phenomenal)
    wave_severity_category: str      # "CALM", "SLIGHT", "MODERATE", "ROUGH", "VERY_ROUGH", "HIGH"
    vessel_relative_wind: VesselRelativeWind
    vessel_relative_wave: VesselRelativeWave
    superstructure_icing_risk: bool  # Polar spray icing hazard (sub-zero + high wind)
    icing_severity: str              # "NONE", "LIGHT", "MODERATE", "SEVERE"
    weather_risk: float              # Composite multi-factor weather risk score 0.0 to 1.0


class WeatherObservation(BaseModel):
    """Comprehensive weather observation compatible with Phase 1 BaseDataProvider."""
    latitude: float
    longitude: float
    provenance: WeatherProvenance = WeatherProvenance.OBSERVATION
    atmosphere: AtmosphericConditions
    maritime: MaritimeWaveConditions
    derived_features: DerivedWeatherNavigationFeatures
    metadata: DataMetadata

    # Backwards-compatibility properties for Phase 1 CurrentMaritimeState
    @property
    def wind_speed_knots(self) -> float:
        return self.atmosphere.wind_speed.value

    @property
    def wind_speed_ms(self) -> float:
        return round(self.atmosphere.wind_speed.value * 0.514444, 2)

    @property
    def wind_direction_deg(self) -> float:
        return self.atmosphere.wind_direction.value

    @property
    def temperature_celsius(self) -> float:
        return self.atmosphere.air_temperature.value

    @property
    def surface_pressure_hpa(self) -> float:
        return self.atmosphere.pressure.value

    @property
    def wave_height_meters(self) -> float:
        return self.maritime.significant_wave_height.value

    @property
    def beaufort_scale(self) -> int:
        return self.atmosphere.beaufort_scale

    @property
    def beaufort_description(self) -> str:
        return self.atmosphere.beaufort_description


class WeatherAPIResponse(BaseModel):
    """Standardized API response meeting explicit Phase 4 requirements:
    value, unit, timestamp, source, data_age, confidence, provenance.
    """
    value: Dict[str, Any]
    unit: str = "composite_weather_report"
    timestamp: str
    source: str
    data_age: float
    confidence: float
    provenance: WeatherProvenance
    is_stale: bool
    latitude: float
    longitude: float
    atmosphere: AtmosphericConditions
    maritime: MaritimeWaveConditions
    derived_navigation_features: DerivedWeatherNavigationFeatures


class RouteWeatherPoint(BaseModel):
    """Route point for weather risk evaluation."""
    id: Optional[str] = None
    lat: float
    lon: float
    heading_deg: float = 0.0
    speed_knots: float = 12.0
    timestamp: Optional[datetime] = None


class RouteWeatherAnalysisRequest(BaseModel):
    """Request payload for route weather and wave severity evaluation."""
    points: List[RouteWeatherPoint]
    include_forecast: bool = False


class RoutePointWeatherAnalysis(BaseModel):
    """Evaluated weather parameters and risk along a single route waypoint."""
    point_id: Optional[str] = None
    lat: float
    lon: float
    air_temp_c: float
    wind_speed_knots: float
    wind_direction_deg: float
    wave_height_m: float
    wave_direction_deg: float
    sea_state_code: int
    wind_severity: float
    wave_severity: float
    weather_risk: float
    icing_risk: bool
    beam_sea_roll_risk: bool
    relative_wind_aspect: str
    relative_wave_aspect: str
    provenance: str
    is_stale: bool


class RouteWeatherAnalysisResponse(BaseModel):
    """Aggregated route weather risk analysis."""
    evaluated_at: str
    point_count: int
    max_wind_knots: float
    mean_wind_knots: float
    max_wave_height_m: float
    mean_wave_height_m: float
    max_weather_risk: float
    mean_weather_risk: float
    high_wind_points_count: int
    severe_wave_points_count: int
    icing_hazard_points_count: int
    overall_weather_advisory: str
    source: str
    confidence: float
    points: List[RoutePointWeatherAnalysis]
