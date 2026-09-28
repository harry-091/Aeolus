"""POLARNAV // Production-Grade Real-Time Data Ingestion Framework.

Defines the core data-provider abstraction, explicit provenance classification,
anti-falsification enforcement, and spatial coverage primitives.
"""

from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel, Field


class DataCategory(str, Enum):
    """Rigorous scientific data provenance tiers.
    
    RULES:
    - Never present FORECAST or REANALYZED as live OBSERVED.
    - Never present STALE data as current.
    - If feed fails and TTL expires, mark as STALE or UNAVAILABLE.
    """
    OBSERVED = "OBSERVED"        # Direct in-situ, radar, radiometer, or satellite pass
    REANALYZED = "REANALYZED"    # Physical state reanalysis (e.g. ERA5, ETOPO relief)
    FORECAST = "FORECAST"        # Forward numerical prediction (e.g. GFS, 24h drift)
    DERIVED = "DERIVED"          # Computed composite (e.g. CPA, IMO Polar Risk Index)
    STALE = "STALE"              # Freshness TTL window has expired; cached fallback
    UNAVAILABLE = "UNAVAILABLE"  # Outside sensor swath or feed currently offline


class ProviderStatus(str, Enum):
    """Operational health status of an ingestion provider."""
    HEALTHY = "HEALTHY"          # Live feed active, timely data updates
    DEGRADED = "DEGRADED"        # Secondary fallback active or partial sensor coverage
    OFFLINE = "OFFLINE"          # Network/dataset unreachable
    INITIALIZING = "INITIALIZING"


class SpatialCoverage(BaseModel):
    """Antarctic geographic coverage boundary."""
    lat_min: float = -90.0
    lat_max: float = -50.0
    lon_min: float = -180.0
    lon_max: float = 180.0
    description: str = "Circumpolar Southern Ocean"

    def contains(self, lat: float, lon: float) -> bool:
        """Check if coordinates fall within provider coverage."""
        return (self.lat_min <= lat <= self.lat_max) and (self.lon_min <= lon <= self.lon_max)


class DataMetadata(BaseModel):
    """Unified provenance and telemetry metadata container."""
    source: str
    timestamp: datetime
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: datetime
    lat_lon_coverage: SpatialCoverage
    resolution_km: float
    data_quality: str = "NOMINAL"  # NOMINAL, HIGH, DEGRADED, ESTIMATED
    confidence: float = 1.0        # 0.0 to 1.0
    provenance: DataCategory
    provider_status: ProviderStatus = ProviderStatus.HEALTHY
    is_stale: bool = False

    def check_staleness(self) -> "DataMetadata":
        """Re-evaluate staleness against current wall-clock UTC time."""
        now = datetime.now(timezone.utc)
        if now > self.valid_until and self.provenance == DataCategory.OBSERVED:
            self.provenance = DataCategory.STALE
            self.is_stale = True
            self.data_quality = "DEGRADED"
        elif now > self.valid_until:
            self.is_stale = True
        else:
            self.is_stale = False
        return self


class ProviderHealth(BaseModel):
    """Comprehensive diagnostic health status for monitoring dashboards."""
    provider_id: str
    provider_name: str
    category: str
    status: ProviderStatus
    active_provenance: DataCategory
    last_update: Optional[datetime]
    last_successful_fetch: Optional[datetime]
    last_error: Optional[str] = None
    uptime_pct: float = 100.0
    coverage: SpatialCoverage
    resolution_km: float


class BaseDataProvider(ABC):
    """Unified abstract interface that every real-time data provider must expose."""

    @abstractmethod
    def fetch_current(self, lat: float, lon: float, **kwargs) -> Any:
        """Fetch the latest available environmental state at the given coordinate.
        
        Must return an object equipped with DataMetadata indicating exact provenance
        (OBSERVED, REANALYZED, FORECAST, DERIVED, STALE, UNAVAILABLE).
        """
        pass

    @abstractmethod
    def fetch_recent(self, lat: float, lon: float, hours: float = 24.0, **kwargs) -> List[Any]:
        """Fetch temporal sequence of observations/states over the preceding window."""
        pass

    @abstractmethod
    def get_status(self) -> ProviderHealth:
        """Return real-time diagnostic health and connection status."""
        pass

    @abstractmethod
    def get_last_update(self) -> Optional[datetime]:
        """Return UTC timestamp of the most recent data record."""
        pass

    @abstractmethod
    def get_coverage(self) -> SpatialCoverage:
        """Return the spatial bounding box of the provider."""
        pass
