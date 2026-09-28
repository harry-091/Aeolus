"""Domain models and Pydantic schemas for Antarctic Sea Ice Monitoring.

Supports:
- Dual execution modes: CURRENT ICE STATE vs HISTORICAL ICE STATE
- Physical attributes: SIC, ice edge (15%), ice extent, spatial gradients, drift dynamics
- Derived navigation features: SIC at point, SIC gradient, high-ice region, ice-edge proximity, ice-risk score, data confidence
- Strict API response contract: value, timestamp, source, age, confidence
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field

from ..base import DataCategory, DataMetadata, ProviderStatus, SpatialCoverage


class IceMonitoringMode(str, Enum):
    """Execution mode separating live operations from historical backtesting.
    
    CRITICAL RULE:
    Never mix CURRENT and HISTORICAL states.
    - CURRENT: uses the newest available legitimate satellite observation; age computed against wall-clock UTC.
    - HISTORICAL: strictly uses observations corresponding to the simulated time; age computed against simulated time; zero lookahead.
    """
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"


class IceStage(str, Enum):
    """WMO Sea Ice nomenclature stages of development."""
    OPEN_WATER = "OPEN_WATER"                    # < 0.10 (or < 0.15)
    VERY_OPEN_PACK = "VERY_OPEN_PACK"            # 0.10 - 0.39
    OPEN_PACK = "OPEN_PACK"                      # 0.40 - 0.69
    CLOSE_PACK = "CLOSE_PACK"                    # 0.70 - 0.89
    CONSOLIDATED_PACK = "CONSOLIDATED_PACK"      # >= 0.90
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"              # Outside Southern Ocean domain
    UNKNOWN = "UNKNOWN"


class IceEdgeInfo(BaseModel):
    """Details regarding the 15% sea-ice boundary contour."""
    edge_threshold_sic: float = 0.15
    is_ice_covered: bool
    distance_to_edge_km: float
    nearest_edge_lat: Optional[float] = None
    nearest_edge_lon: Optional[float] = None
    bearing_to_edge_deg: Optional[float] = None
    edge_status: str  # e.g., "WITHIN_PACK", "OPEN_WATER_OUTSIDE_EDGE", "AT_EDGE"


class SpatialGradient(BaseModel):
    """Directional spatial derivative of Sea Ice Concentration ∇SIC."""
    magnitude_per_100km: float  # Change in SIC fraction per 100 km
    magnitude_fraction_km: float  # Change in SIC fraction per km
    gradient_easting: float  # dSIC / dx (eastward)
    gradient_northing: float  # dSIC / dy (northward)
    direction_deg: float  # Direction of steepest concentration increase (0-360)
    steepness_category: str  # "FLAT", "MODERATE", "STEEP", "DISCONTINUOUS_FRONT"


class IceDriftInfo(BaseModel):
    """Kinematic sea ice drift vector where reliable hydrodynamics/wind exist."""
    available: bool = False
    drift_speed_knots: float = 0.0
    drift_speed_ms: float = 0.0
    drift_direction_deg: float = 0.0  # Flow direction heading towards
    u_drift_ms: float = 0.0  # Eastward drift velocity
    v_drift_ms: float = 0.0  # Northward drift velocity
    reliability: str = "ESTIMATED"  # "HIGH", "RELIABLE", "ESTIMATED", "UNAVAILABLE"
    source: str = "Copernicus Marine MERCATOR GLO12 & Kinematic Advection"


class IceExtentSummary(BaseModel):
    """Antarctic circumpolar and regional ice extent metric."""
    total_extent_million_sqkm: float
    observation_period: str
    source: str
    anomaly_from_mean_sqkm: Optional[float] = None


class DerivedNavigationFeatures(BaseModel):
    """Derived maritime safety and routing features along waypoints or coordinates."""
    sic_at_point: float                  # 0.0 to 1.0 fraction
    sic_gradient: float                  # Magnitude per 100km
    high_ice_region: bool                # True if SIC >= 0.70 (hazardous pack ice)
    ice_edge_proximity_km: float        # Distance to 15% edge (km)
    ice_risk_score: float                # 0.0 (safe) to 1.0 (extreme risk)
    data_confidence: float               # 0.0 to 1.0 based on sensor age & swath


class SeaIceObservation(BaseModel):
    """Comprehensive sea ice observation satisfying Phase 1 BaseDataProvider contract."""
    latitude: float
    longitude: float
    mode: IceMonitoringMode = IceMonitoringMode.CURRENT
    sic_fraction: float          # 0.0 to 1.0
    sic_percent: float           # 0.0 to 100.0%
    ice_stage: str               # WMO nomenclature
    polar_code_category: str     # IMO Polar Code category
    ice_edge: IceEdgeInfo
    spatial_gradient: SpatialGradient
    ice_drift: IceDriftInfo
    derived_features: DerivedNavigationFeatures
    metadata: DataMetadata


class SeaIceAPIResponse(BaseModel):
    """Standardized API response meeting explicit requirements:
    value, timestamp, source, age, confidence, mode, details.
    """
    value: Union[float, Dict[str, Any]]
    timestamp: str               # ISO-8601 UTC observation timestamp
    source: str                  # Legitimate product identifier
    age: float                   # Freshness age in seconds relative to current or simulated time
    confidence: float            # Confidence score between 0.0 and 1.0
    mode: IceMonitoringMode      # CURRENT or HISTORICAL
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    derived_navigation_features: Optional[DerivedNavigationFeatures] = None
    full_observation: Optional[Dict[str, Any]] = None


class RouteWaypoint(BaseModel):
    """Input waypoint for route navigation analysis."""
    id: Optional[str] = None
    lat: float
    lon: float
    timestamp: Optional[datetime] = None


class RouteAnalysisRequest(BaseModel):
    """Request payload for route sea-ice risk and navigation analysis."""
    waypoints: List[RouteWaypoint]
    mode: IceMonitoringMode = IceMonitoringMode.CURRENT
    simulated_time: Optional[datetime] = None


class RoutePointAnalysis(BaseModel):
    """Evaluated derived features for a single waypoint along a voyage."""
    waypoint_id: Optional[str] = None
    lat: float
    lon: float
    sic_at_point: float
    sic_percent: float
    ice_stage: str
    sic_gradient_per_100km: float
    high_ice_region: bool
    ice_edge_proximity_km: float
    ice_risk_score: float
    data_confidence: float
    drift_speed_knots: float
    drift_direction_deg: float


class RouteAnalysisResponse(BaseModel):
    """Aggregated route analysis containing overall risk and point-by-point details."""
    mode: IceMonitoringMode
    evaluation_time: str
    waypoint_count: int
    max_sic: float
    mean_sic: float
    high_ice_segments_count: int
    mean_ice_risk_score: float
    max_ice_risk_score: float
    overall_route_advisory: str
    source: str
    confidence: float
    points: List[RoutePointAnalysis]
