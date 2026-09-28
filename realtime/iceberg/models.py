"""Domain models for PolarNav Real Iceberg / Maritime Obstacle Monitoring.

Adheres strictly to zero-fabrication standards:
- All obstacles derive from authentic BYU/NIC tracking records and Sentinel-1 SAR detections.
- Explicit observation age, staleness flags, and confidence calibration.
- CPA, TCPA, spatial density, route intersection, and hydrodynamic drift schemas.
"""
from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from ..base import DataMetadata, DataCategory


class IcebergProvenance(str, Enum):
    """Provenance tiers for iceberg / maritime obstacle observations."""
    OBSERVED_RADAR = "OBSERVED_RADAR"                   # Sentinel-1 SAR high-resolution radar fix
    OBSERVED_SCATTEROMETER = "OBSERVED_SCATTEROMETER"   # BYU MERS / QuikSCAT / ASCAT sensor fix
    OBSERVED_NIC_CHART = "OBSERVED_NIC_CHART"           # U.S. National Ice Center manual / optical fix
    DERIVED_KINEMATICS = "DERIVED_KINEMATICS"           # CPA, TCPA, and velocity calculations
    PREDICTED_DRIFT = "PREDICTED_DRIFT"                 # Ocean-current and Coriolis coupled projection
    STALE = "STALE"                                     # Observation older than freshness threshold (>7 days)
    UNAVAILABLE = "UNAVAILABLE"                         # Region without obstacle coverage or data void


class IcebergDimensions(BaseModel):
    """Physical dimensions and hydrodynamic draft of an iceberg."""
    length_km: float = Field(..., description="Major axis length in kilometers")
    width_km: float = Field(..., description="Minor axis length in kilometers")
    area_km2: float = Field(..., description="Estimated horizontal surface area in km²")
    estimated_draft_m: float = Field(..., description="Estimated keel depth below waterline in meters")
    freeboard_m: float = Field(default=35.0, description="Estimated height above waterline in meters")


class IcebergMovement(BaseModel):
    """Kinematic drift motion parameters of an iceberg."""
    speed_knots: float = Field(..., description="Drift velocity over ground in knots")
    bearing_deg: float = Field(..., description="Drift heading in degrees True (0-360)")
    velocity_u_ms: float = Field(..., description="Eastward drift velocity in m/s")
    velocity_v_ms: float = Field(..., description="Northward drift velocity in m/s")
    drift_forcing: str = Field(default="Copernicus GLO12 Current + Coriolis", description="Primary hydrodynamic forcing")


class TrackedIceberg(BaseModel):
    """Detailed record of a tracked Antarctic iceberg or verified radar contact."""
    iceberg_id: str = Field(..., description="Unique alphanumeric identifier (e.g. A23A, B15W)")
    name: str = Field(..., description="Human-readable catalog name")
    latitude: float = Field(..., description="Observed latitude (-90.0 to -50.0)")
    longitude: float = Field(..., description="Observed longitude (-180.0 to 180.0)")
    source: str = Field(..., description="Legitimate data origin")
    observation_time: str = Field(..., description="UTC ISO-8601 observation timestamp of the fix")
    data_age_hours: float = Field(..., description="Elapsed time in hours since observation")
    data_age_days: float = Field(..., description="Elapsed time in days since observation")
    is_stale: bool = Field(..., description="Flag indicating if observation is older than 7 days")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence factoring sensor and age decay")
    provenance: IcebergProvenance = Field(..., description="Data provenance tier")
    dimensions: IcebergDimensions = Field(..., description="Physical size metrics")
    movement: IcebergMovement = Field(..., description="Current drift motion vector")
    quadrant: str = Field(..., description="Antarctic quadrant (A_WEDDELL, B_BELLINGSHAUSEN, C_ROSS, D_DAVIS)")
    historical_positions: Optional[List[List[float]]] = Field(default=None, description="Recent historical GPS fixes [[lat, lon], ...]")
    predicted_trajectory: Optional[List[Dict[str, Any]]] = Field(default=None, description="Multi-horizon scientific forecast points")


class ClosestPointOfApproach(BaseModel):
    """Dynamic Closest Point of Approach (CPA) and Time to CPA (TCPA)."""
    target_iceberg_id: str = Field(..., description="Identifier of the iceberg obstacle")
    current_distance_km: float = Field(..., description="Current distance to obstacle in kilometers")
    current_distance_nm: float = Field(..., description="Current distance in nautical miles")
    cpa_distance_km: float = Field(..., description="Distance at closest point of approach in kilometers")
    cpa_distance_nm: float = Field(..., description="Distance at closest point of approach in nautical miles")
    tcpa_hours: float = Field(..., description="Time to closest point of approach in hours (negative if diverging)")
    tcpa_minutes: float = Field(..., description="Time to closest point of approach in minutes")
    is_converging: bool = Field(..., description="True if distance between vessel and obstacle is decreasing")
    threat_level: str = Field(..., description="CRITICAL, WARNING, CAUTION, or CLEAR")
    collision_risk_index: float = Field(..., ge=0.0, le=1.0, description="Normalized collision hazard index [0.0 - 1.0]")


class IcebergDensity(BaseModel):
    """Spatial density of tracked icebergs within a tactical radius."""
    search_radius_km: float = Field(..., description="Search radius in kilometers")
    iceberg_count: int = Field(..., description="Number of tracked obstacles within search radius")
    density_per_10k_km2: float = Field(..., description="Normalized spatial density (icebergs / 10,000 km²)")
    congestion_level: str = Field(..., description="CLEAR, SPARSE, MODERATE, or CONGESTED")


class RouteIcebergIntersection(BaseModel):
    """Evaluation of voyage route corridor against iceberg positions and drift."""
    has_intersection: bool = Field(..., description="True if any iceberg enters route safety buffer")
    min_clearance_km: float = Field(..., description="Minimum clearance to any iceberg along entire route")
    min_clearance_nm: float = Field(..., description="Minimum clearance in nautical miles")
    intersecting_icebergs: List[Dict[str, Any]] = Field(default=[], description="List of obstacles violating safety buffer")
    hazard_waypoints: List[int] = Field(default=[], description="Indices of route legs requiring diversion")
    summary: str = Field(..., description="Navigational assessment summary")


class IcebergObservation(BaseModel):
    """Top-level observation conforming to BaseDataProvider and CurrentMaritimeState."""
    latitude: float = Field(..., description="Query latitude")
    longitude: float = Field(..., description="Query longitude")
    nearest_iceberg_id: str = Field(..., description="ID of nearest tracked iceberg")
    distance_to_nearest_km: float = Field(..., description="Geodesic distance to nearest iceberg in km")
    closest_point_of_approach_km: float = Field(..., description="CPA distance in km")
    collision_risk_index: float = Field(..., ge=0.0, le=1.0, description="Collision risk [0.0 - 1.0]")
    threat_level: str = Field(..., description="CLEAR, MONITOR, CAUTION, IMMEDIATE_ACTION")
    tracked_berg_count: int = Field(..., description="Total tracked icebergs in database")
    metadata: DataMetadata = Field(..., description="Provenance and metadata envelope")

    # Enriched Phase 6 Attributes
    nearest_iceberg: Optional[TrackedIceberg] = Field(default=None, description="Full details of nearest iceberg")
    cpa_details: Optional[ClosestPointOfApproach] = Field(default=None, description="Dynamic CPA kinematics")
    density: Optional[IcebergDensity] = Field(default=None, description="Local spatial obstacle density")
    surrounding_icebergs: List[TrackedIceberg] = Field(default=[], description="Obstacles within tactical proximity")


class CPAMatrixRequest(BaseModel):
    """Request payload for multi-obstacle CPA calculation."""
    vessel_lat: float = Field(..., ge=-90.0, le=90.0)
    vessel_lon: float = Field(..., ge=-180.0, le=180.0)
    vessel_heading_deg: float = Field(..., ge=0.0, le=360.0)
    vessel_speed_knots: float = Field(..., ge=0.0, le=50.0)
    max_distance_km: float = Field(default=150.0, ge=10.0, le=1000.0)


class RouteWaypoint(BaseModel):
    """Waypoint along a vessel voyage."""
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    planned_speed_knots: float = Field(default=12.0, ge=0.0)


class RouteIntersectionRequest(BaseModel):
    """Request payload for route corridor intersection analysis."""
    waypoints: List[RouteWaypoint] = Field(..., min_length=2)
    safety_buffer_km: float = Field(default=18.52, ge=1.0, le=100.0, description="Safety corridor buffer (default 10 NM = 18.52 km)")
