"""Data models for Real-Time Risk-Aware Route Optimization (PolarNav Phase 10).

Defines:
- Route profiles (BALANCED, SAFEST, FASTEST) with distinct objective weights
- Comprehensive waypoints containing full multi-sensor telemetry & ML risk
- 9 required evaluation metrics (distance, ETA, risk, SIC, iceberg, weather, depth, confidence, explanation)
- Strict physical feasibility contracts
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from ..ml_risk.models import VesselCharacteristics, RiskCategory


class RouteProfileType(str, Enum):
    """Supported route optimization objective profiles."""
    BALANCED = "BALANCED"
    SAFEST = "SAFEST"
    FASTEST = "FASTEST"


class RouteProfileConfig(BaseModel):
    """Objective weights and operational safety limits for a route profile."""
    profile_type: RouteProfileType
    name: str
    description: str
    w_distance: float = Field(ge=0.0, description="Weight on minimizing total distance")
    w_time: float = Field(ge=0.0, description="Weight on minimizing transit ETA")
    w_risk: float = Field(ge=0.0, description="Weight on ML navigation risk")
    w_sic: float = Field(ge=0.0, description="Weight on sea ice concentration penalty")
    w_iceberg: float = Field(ge=0.0, description="Weight on iceberg collision risk")
    w_weather: float = Field(ge=0.0, description="Weight on wind/wave severity")
    w_current: float = Field(ge=0.0, description="Weight on ocean current assist/drag")
    w_fuel: float = Field(ge=0.0, description="Weight on fuel consumption")
    max_allowed_sic: float = Field(ge=0.0, le=100.0, description="Maximum navigable SIC (%)")
    min_iceberg_clearance_km: float = Field(ge=1.0, description="Safety standoff distance from icebergs (km)")
    min_under_keel_clearance_m: float = Field(ge=0.0, description="Required under-keel clearance margin (m)")
    lateral_bias: float = Field(default=0.0, description="Lateral bias parameter for corridor exploration")


class RealtimeWaypoint(BaseModel):
    """Navigational waypoint with complete multi-sensor telemetry and ML risk evaluation."""
    waypoint_index: int
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    distance_from_start_km: float = Field(ge=0.0)
    leg_distance_km: float = Field(ge=0.0)
    bearing_deg: float = Field(ge=0.0, le=360.0)
    speed_knots: float = Field(ge=0.0)
    eta_hours: float = Field(ge=0.0)
    timestamp_iso: str
    
    # Environmental & Geometry Telemetry
    depth_m: float
    under_keel_clearance_m: float
    is_land: bool
    sic_pct: float = Field(ge=0.0, le=100.0)
    nearest_iceberg_km: float = Field(ge=0.0)
    wind_speed_knots: float = Field(ge=0.0)
    wave_height_m: float = Field(ge=0.0)
    current_assist_knots: float
    
    # ML Risk Engine Outputs (NEVER AIS coordinates)
    ml_risk_score: float = Field(ge=0.0, le=1.0)
    risk_category: RiskCategory
    dominant_hazard: str
    confidence: float = Field(ge=0.0, le=1.0)


class SICExposure(BaseModel):
    """Sea ice exposure statistics along the voyage corridor."""
    avg_sic_pct: float = Field(ge=0.0, le=100.0)
    max_sic_pct: float = Field(ge=0.0, le=100.0)
    ice_covered_km: float = Field(ge=0.0)
    fast_ice_km: float = Field(ge=0.0, description="Distance in heavy ice (>80% SIC)")
    pack_ice_km: float = Field(ge=0.0, description="Distance in pack ice (15-80% SIC)")
    open_water_km: float = Field(ge=0.0, description="Distance in open water (<15% SIC)")


class IcebergClearance(BaseModel):
    """Iceberg proximity and CPA clearance metrics."""
    min_cpa_km: float = Field(ge=0.0, description="Closest Point of Approach to any tracked iceberg (km)")
    cleared_icebergs_count: int = Field(ge=0, description="Total obstacles safely cleared")
    high_threat_cpa_count: int = Field(ge=0, description="Encounters within safety clearance buffer")
    required_buffer_km: float = Field(ge=0.0)


class WeatherExposure(BaseModel):
    """Atmospheric and wave condition exposure metrics."""
    avg_wind_knots: float = Field(ge=0.0)
    max_wind_knots: float = Field(ge=0.0)
    avg_wave_height_m: float = Field(ge=0.0)
    max_wave_height_m: float = Field(ge=0.0)
    severe_weather_km: float = Field(ge=0.0, description="Distance in wind > 35kn or wave > 4m")


class DepthClearance(BaseModel):
    """Bathymetry and seafloor navigation clearance metrics."""
    min_depth_m: float = Field(description="Minimum water depth along route (m)")
    min_ukc_m: float = Field(description="Minimum under-keel clearance (m)")
    shallow_water_distance_km: float = Field(ge=0.0, description="Distance in water depth < 50m")
    is_clearance_compliant: bool = Field(description="True if UKC >= required safety margin throughout")


class RouteMetrics(BaseModel):
    """Comprehensive 9-factor evaluation metrics for an optimized route."""
    distance_km: float = Field(ge=0.0)
    distance_nm: float = Field(ge=0.0)
    eta_hours: float = Field(ge=0.0)
    departure_time: str
    estimated_arrival_time: str
    estimated_risk_score: float = Field(ge=0.0, le=1.0)
    estimated_risk_category: RiskCategory
    
    # Granular domain metrics
    sic_exposure: SICExposure
    iceberg_clearance: IcebergClearance
    weather_exposure: WeatherExposure
    depth_clearance: DepthClearance
    estimated_fuel_mt: float = Field(ge=0.0)
    
    # Uncertainty & explainability
    confidence: float = Field(ge=0.0, le=1.0, description="Non-fabricated aggregate confidence")
    confidence_explanation: str
    exposed_limitations: List[str] = Field(default_factory=list)
    explanation: str = Field(description="Transparent narrative detailing route choices and profile tradeoffs")


class RealtimeOptimizedRoute(BaseModel):
    """Complete feasible route generated for a specific optimization profile."""
    route_id: str
    profile_type: RouteProfileType
    name: str
    origin: List[float] = Field(description="[latitude, longitude]")
    destination: List[float] = Field(description="[latitude, longitude]")
    waypoints: List[RealtimeWaypoint]
    path_coords: List[List[float]] = Field(description="Dense [lat, lon] coordinates")
    multi_path: List[List[List[float]]] = Field(description="Antimeridian (+/-180) safe segmented paths")
    metrics: RouteMetrics
    is_feasible: bool = Field(description="True if route strictly has zero land crossings and UKC > 0m")
    validation_notes: List[str] = Field(default_factory=list)


class RouteOptimizationRequest(BaseModel):
    """Request payload for multi-profile real-time route optimization."""
    origin: List[float] = Field(description="[latitude, longitude] of starting point")
    destination: List[float] = Field(description="[latitude, longitude] of destination")
    vessel: VesselCharacteristics = Field(default_factory=VesselCharacteristics)
    profiles: Optional[List[RouteProfileType]] = Field(
        default=None,
        description="Profiles to generate (defaults to BALANCED, SAFEST, FASTEST)"
    )
    departure_time: Optional[str] = Field(default=None, description="ISO-8601 departure timestamp")


class RouteOptimizationResponse(BaseModel):
    """Response containing genuinely differentiated routes for each requested profile."""
    request_id: str
    routes: List[RealtimeOptimizedRoute]
    computation_time_ms: float
    evaluated_profiles: List[str]
