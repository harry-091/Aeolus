"""Domain models for PolarNav Real Navigation Geometry Layer (Phase 7).

Integrates static bathymetry, coastline, land mask, shallow-water regions,
and configurable vessel draft clearance.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from ..base import DataMetadata, DataCategory


class SeabedZone(str, Enum):
    """Bathymetric and seabed depth classification zones."""
    SHOAL_GROUNDING_HAZARD = "SHOAL_GROUNDING_HAZARD"       # Depth < 20m
    SHALLOW_CONTINENTAL_SHELF = "SHALLOW_CONTINENTAL_SHELF" # 20m <= Depth < 200m
    CONTINENTAL_SLOPE = "CONTINENTAL_SLOPE"                 # 200m <= Depth < 1000m
    ABYSSAL_PLAIN = "ABYSSAL_PLAIN"                         # Depth >= 1000m
    LAND = "LAND"                                           # Elevation >= 0m
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"                         # Coordinate outside regional grid


class BathymetryObservation(BaseModel):
    """Structured bathymetric sounding at a geographic coordinate (backward-compatible)."""
    latitude: float = Field(..., description="Query latitude")
    longitude: float = Field(..., description="Query longitude")
    depth_meters: float = Field(..., description="Positive downward depth in meters below sea level (0.0 on land)")
    is_shallow_warning: bool = Field(..., description="True if depth < 50m")
    is_grounding_hazard: bool = Field(..., description="True if depth < 20m or clearance <= 0")
    under_keel_clearance_m: float = Field(..., description="Water depth minus vessel draft in meters")
    seabed_zone: str = Field(..., description="Seabed zone classification")
    metadata: DataMetadata = Field(..., description="Provenance metadata envelope")


class NavigationGeometryPoint(BaseModel):
    """High-precision static navigation geometry evaluation at a coordinate."""
    latitude: float = Field(..., description="Geographic latitude")
    longitude: float = Field(..., description="Geographic longitude")
    depth_meters: float = Field(..., description="Water depth in meters (0.0 on land)")
    altitude_meters: float = Field(..., description="Raw topographic elevation / seabed relief in meters")
    is_land: bool = Field(..., description="True if point is on land or ice sheet")
    is_shallow: bool = Field(..., description="True if depth < 20m")
    under_keel_clearance_m: float = Field(..., description="Depth minus vessel draft")
    coastline_distance_km: float = Field(..., description="Distance to nearest Antarctic coastline in km")
    is_navigable: bool = Field(..., description="True if not land and clearance >= safe margin")
    seabed_zone: SeabedZone = Field(..., description="Seabed classification zone")


class RouteGeometryValidationResult(BaseModel):
    """Audit report of route waypoints against land and bathymetry constraints."""
    is_valid: bool = Field(..., description="True if route has zero land, shallow, or clearance violations")
    total_points_evaluated: int = Field(..., description="Number of waypoint and intermediate checks")
    land_violations_count: int = Field(..., description="Number of points intersecting land mask")
    shallow_violations_count: int = Field(..., description="Number of points in prohibited shallow water")
    min_clearance_m: float = Field(..., description="Minimum under-keel clearance recorded along route")
    hazard_segments: List[Dict[str, Any]] = Field(default=[], description="Details of violated segments")
    summary: str = Field(..., description="Navigational assessment summary")


class ValidateRouteGeometryRequest(BaseModel):
    """Request payload for route geometry audit."""
    waypoints: List[List[float]] = Field(..., min_length=2, description="List of [lat, lon] waypoints")
    vessel_draft: float = Field(default=8.0, ge=0.5, le=30.0, description="Vessel draft in meters")
    min_clearance_m: float = Field(default=2.0, ge=0.0, le=10.0, description="Minimum safe under-keel clearance")
