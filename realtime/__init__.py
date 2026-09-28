"""POLARNAV // Real-Time Environmental Ingestion Framework & Multi-Sensor Fusion.

Exposes unified provider abstractions, explicit provenance tracking (OBSERVED,
REANALYZED, FORECAST, DERIVED, STALE, UNAVAILABLE), and composite CurrentMaritimeState.
"""

from .base import (
    DataCategory,
    ProviderStatus,
    SpatialCoverage,
    DataMetadata,
    ProviderHealth,
    BaseDataProvider,
)
from .state import (
    CurrentMaritimeState,
    SpatialCellMaritimeState,
    VesselState,
    LayerFreshness,
    LayerTemporalAudit,
    CellWindState,
    CellWaveState,
    CellCurrentState,
    CoastlineObservation,
    MaritimeStateManager,
    maritime_state_manager,
)
from .sea_ice import SeaIceProvider, SeaIceObservation
from .iceberg import IcebergProvider, IcebergObservation
from .bathymetry import BathymetryProvider, BathymetryObservation, navigation_geometry_service
from .weather import WeatherProvider, WeatherObservation
from .ocean import OceanProvider, OceanObservation
from .satellite import SatelliteProvider, SatelliteObservation

__all__ = [
    "DataCategory",
    "ProviderStatus",
    "SpatialCoverage",
    "DataMetadata",
    "ProviderHealth",
    "BaseDataProvider",
    "CurrentMaritimeState",
    "SpatialCellMaritimeState",
    "VesselState",
    "LayerFreshness",
    "LayerTemporalAudit",
    "CellWindState",
    "CellWaveState",
    "CellCurrentState",
    "CoastlineObservation",
    "MaritimeStateManager",
    "maritime_state_manager",
    "SeaIceProvider",
    "SeaIceObservation",
    "IcebergProvider",
    "IcebergObservation",
    "BathymetryProvider",
    "BathymetryObservation",
    "navigation_geometry_service",
    "WeatherProvider",
    "WeatherObservation",
    "OceanProvider",
    "OceanObservation",
    "SatelliteProvider",
    "SatelliteObservation",
]
