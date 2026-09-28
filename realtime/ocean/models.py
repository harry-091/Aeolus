"""Domain models and Pydantic schemas for Antarctic Ocean Current Monitoring.

Supports:
- Ocean currents: eastward (uo), northward (vo), magnitude, direction
- Marine environment: sea surface temperature, sea surface height, salinity, wave parameters
- Derived maritime navigation features:
  - current speed and direction
  - vessel-relative current and leeway drift
  - estimated current impact on route (effective SOG, time delta %, fuel impact)
  - ocean-condition risk (wave-current opposing hazard, hypothermia survival)
- Per-value telemetry metadata: timestamp, source, resolution, data_age, confidence
- Graceful handling of unavailable / out-of-bounds regions
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field

from ..base import DataCategory, DataMetadata, ProviderStatus, SpatialCoverage


class OceanVariable(BaseModel):
    """Standardized telemetry container for an individual oceanographic measurement.
    
    Exposes: value, unit, timestamp, source, resolution, data_age, confidence.
    """
    value: float
    unit: str                        # "m/s", "knots", "deg", "degC", "m", "PSU", "s"
    timestamp: str                   # ISO-8601 UTC observation timestamp
    source: str                      # Legitimate product identifier
    resolution: str                  # Spatial resolution (e.g., "9.25 km (1/12 deg)")
    data_age: float                  # Age in seconds from queried/reference time
    confidence: float                # 0.0 to 1.0 confidence score
    status: str = "REAL"             # "REAL", "REANALYZED", "UNAVAILABLE"


class OceanCurrentState(BaseModel):
    """Current vector dynamics at a geographic coordinate."""
    eastward_current_uo: OceanVariable
    northward_current_vo: OceanVariable
    current_magnitude: OceanVariable
    current_direction: OceanVariable


class OceanEnvironmentalState(BaseModel):
    """Physical marine water column and surface state."""
    sea_surface_temperature: OceanVariable
    sea_surface_height: Optional[OceanVariable] = None
    salinity: Optional[OceanVariable] = None
    significant_wave_height: Optional[OceanVariable] = None
    wave_direction: Optional[OceanVariable] = None
    wave_period: Optional[OceanVariable] = None


class VesselRelativeCurrent(BaseModel):
    """Vessel-relative current encounter dynamics and leeway drift."""
    relative_current_angle_deg: float   # Angle relative to vessel heading [-180, 180]
    drift_assist_knots: float          # Longitudinal component (+ assist, - resistance)
    cross_current_leeway_knots: float  # Transverse component pushing vessel off course
    leeway_drift_angle_deg: float      # Crab angle required to counteract leeway
    current_aspect: str                # "FAVORABLE_TAIL_CURRENT", "HEAD_RESISTANCE", "PORT_BEAM_DRIFT", "STARBOARD_BEAM_DRIFT", "QUARTERING_ASSIST", "QUARTERING_RETARDING"


class EstimatedCurrentImpact(BaseModel):
    """Impact of ocean currents on voyage transit and fuel economy."""
    effective_speed_over_ground_knots: float
    estimated_time_delta_percent: float  # Negative = time savings, Positive = delayed
    fuel_impact_estimate: str            # "FUEL_SAVINGS", "NOMINAL", "INCREASED_CONSUMPTION", "SEVERE_HEAD_CURRENT_PENALTY"


class OceanConditionRisk(BaseModel):
    """Risk indicators derived from ocean currents, thermal state, and wave interactions."""
    risk_score: float                   # Composite risk 0.0 (safe) to 1.0 (extreme)
    risk_level: str                     # "LOW", "MODERATE", "ELEVATED", "HIGH", "HAZARDOUS"
    opposing_wave_current_hazard: bool  # Wave steepening hazard when waves oppose strong current
    wave_steepening_factor: float       # Wave amplification factor
    hypothermia_survival_minutes: float # Estimated immersion survival time based on SST
    current_shear_hazard: bool          # Rapid velocity gradient / eddy shear boundary


class OceanObservation(BaseModel):
    """Comprehensive oceanographic observation meeting BaseDataProvider contract."""
    latitude: float
    longitude: float
    is_available: bool = True
    currents: OceanCurrentState
    environment: OceanEnvironmentalState
    vessel_relative: VesselRelativeCurrent
    route_impact: EstimatedCurrentImpact
    ocean_risk: OceanConditionRisk
    metadata: DataMetadata

    # Backwards-compatibility properties for Phase 1 CurrentMaritimeState
    @property
    def current_speed_knots(self) -> float:
        return self.currents.current_magnitude.value

    @property
    def current_speed_ms(self) -> float:
        return round(self.currents.current_magnitude.value * 0.514444, 2)

    @property
    def current_direction_deg(self) -> float:
        return self.currents.current_direction.value

    @property
    def zonal_uo_ms(self) -> float:
        return self.currents.eastward_current_uo.value

    @property
    def meridional_vo_ms(self) -> float:
        return self.currents.northward_current_vo.value

    @property
    def sea_surface_temp_c(self) -> float:
        return self.environment.sea_surface_temperature.value

    @property
    def sea_surface_temperature_c(self) -> float:
        return self.environment.sea_surface_temperature.value

    @property
    def drift_assist_knots(self) -> float:
        return self.vessel_relative.drift_assist_knots


class OceanAPIResponse(BaseModel):
    """Standardized API response meeting explicit Phase 5 requirements."""
    value: Dict[str, Any]
    unit: str = "composite_ocean_report"
    timestamp: str
    source: str
    resolution: str
    data_age: float
    confidence: float
    is_available: bool
    latitude: float
    longitude: float
    currents: OceanCurrentState
    environment: OceanEnvironmentalState
    vessel_relative_current: VesselRelativeCurrent
    estimated_current_impact: EstimatedCurrentImpact
    ocean_condition_risk: OceanConditionRisk


class RouteOceanPoint(BaseModel):
    """Route point for ocean current evaluation."""
    id: Optional[str] = None
    lat: float
    lon: float
    heading_deg: float = 0.0
    speed_knots: float = 12.0
    timestamp: Optional[datetime] = None


class RouteOceanAnalysisRequest(BaseModel):
    """Request payload for route ocean current and route impact analysis."""
    points: List[RouteOceanPoint]


class RoutePointOceanAnalysis(BaseModel):
    """Evaluated ocean conditions along a single waypoint."""
    point_id: Optional[str] = None
    lat: float
    lon: float
    current_speed_knots: float
    current_direction_deg: float
    eastward_uo_ms: float
    northward_vo_ms: float
    sea_surface_temp_c: float
    drift_assist_knots: float
    cross_leeway_knots: float
    effective_sog_knots: float
    time_delta_percent: float
    ocean_risk_score: float
    opposing_wave_hazard: bool
    is_available: bool


class RouteOceanAnalysisResponse(BaseModel):
    """Aggregated route ocean analysis."""
    evaluated_at: str
    point_count: int
    max_current_speed_knots: float
    mean_current_speed_knots: float
    net_drift_assist_knots: float
    overall_transit_time_delta_percent: float
    opposing_wave_hazard_count: int
    mean_ocean_risk: float
    max_ocean_risk: float
    overall_current_advisory: str
    source: str
    resolution: str
    confidence: float
    points: List[RoutePointOceanAnalysis]
