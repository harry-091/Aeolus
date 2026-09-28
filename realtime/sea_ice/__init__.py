"""POLARNAV // Sea Ice Monitoring Framework (Phase 3).

Real-time & historical Antarctic Sea Ice Concentration, edge detection,
extent, spatial gradients, coupled drift, and derived maritime safety analytics.
"""

from .models import (
    IceMonitoringMode,
    IceStage,
    IceEdgeInfo,
    SpatialGradient,
    IceDriftInfo,
    IceExtentSummary,
    DerivedNavigationFeatures,
    SeaIceObservation,
    SeaIceAPIResponse,
    RouteWaypoint,
    RouteAnalysisRequest,
    RoutePointAnalysis,
    RouteAnalysisResponse,
)
from .service import (
    SeaIceMonitoringService,
    sea_ice_service,
    classify_ice_stage,
    classify_polar_code,
)
from .provider import SeaIceProvider

__all__ = [
    "IceMonitoringMode",
    "IceStage",
    "IceEdgeInfo",
    "SpatialGradient",
    "IceDriftInfo",
    "IceExtentSummary",
    "DerivedNavigationFeatures",
    "SeaIceObservation",
    "SeaIceAPIResponse",
    "RouteWaypoint",
    "RouteAnalysisRequest",
    "RoutePointAnalysis",
    "RouteAnalysisResponse",
    "SeaIceMonitoringService",
    "sea_ice_service",
    "classify_ice_stage",
    "classify_polar_code",
    "SeaIceProvider",
]
