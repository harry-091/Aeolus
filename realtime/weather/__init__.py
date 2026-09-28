"""POLARNAV // Real-Time Weather Monitoring Framework (Phase 4).

Atmospheric & marine weather observation, reanalysis, and forecasting with
rigorous provenance, per-variable telemetry, stale-data detection, and maritime derived navigation features.
"""

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
    RouteWeatherPoint,
    RouteWeatherAnalysisRequest,
    RoutePointWeatherAnalysis,
    RouteWeatherAnalysisResponse,
)
from .service import (
    WeatherMonitoringService,
    weather_service,
    compute_beaufort,
    compute_sea_state,
)
from .provider import WeatherProvider

__all__ = [
    "WeatherProvenance",
    "WeatherVariable",
    "AtmosphericConditions",
    "MaritimeWaveConditions",
    "VesselRelativeWind",
    "VesselRelativeWave",
    "DerivedWeatherNavigationFeatures",
    "WeatherObservation",
    "WeatherAPIResponse",
    "RouteWeatherPoint",
    "RouteWeatherAnalysisRequest",
    "RoutePointWeatherAnalysis",
    "RouteWeatherAnalysisResponse",
    "WeatherMonitoringService",
    "weather_service",
    "compute_beaufort",
    "compute_sea_state",
    "WeatherProvider",
]
