"""Real-Time Antarctic Iceberg Obstacle & Drift Provider.

Ingests BYU MERS / U.S. National Ice Center (NIC) consolidated tracking data
and Sentinel-1 SAR radar obstacle detections.

Exposes explicit provenance:
- OBSERVED: Verified radar scatterometer or SAR fix.
- DERIVED: Closest Point of Approach (CPA) and spatial density calculations.
- STALE: Track fix older than 7 days.
- UNAVAILABLE: Outside Antarctic quadrants.
"""
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from ..base import (
    BaseDataProvider,
    DataCategory,
    ProviderStatus,
    SpatialCoverage,
    DataMetadata,
    ProviderHealth,
)
from .models import (
    IcebergObservation,
    TrackedIceberg,
    ClosestPointOfApproach,
    IcebergDensity,
    RouteIcebergIntersection,
    RouteWaypoint,
)
from .service import iceberg_monitoring_service, IcebergMonitoringService


class IcebergProvider(BaseDataProvider):
    """Unified Antarctic iceberg obstacle tracking and CPA collision hazard provider."""

    def __init__(self, service: Optional[IcebergMonitoringService] = None, ttl_days: float = 7.0):
        self.provider_id = "provider_byu_nic_icebergs"
        self.provider_name = "BYU MERS / U.S. NIC Antarctic Iceberg Tracking Database"
        self.ttl_days = ttl_days
        self.coverage = SpatialCoverage(lat_min=-90.0, lat_max=-50.0, description="Antarctic Iceberg Quadrants A, B, C, D")
        self.resolution_km = 1.0
        self._last_successful_fetch: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self.service = service or iceberg_monitoring_service

    def fetch_current(self, lat: float, lon: float, **kwargs) -> IcebergObservation:
        """Fetch real-time nearest iceberg, geodesic clearance, CPA, and collision hazard."""
        vessel_heading = float(kwargs.get("vessel_heading", kwargs.get("vessel_heading_deg", 0.0)))
        vessel_speed = float(kwargs.get("vessel_speed", kwargs.get("vessel_speed_knots", 12.0)))

        try:
            obs = self.service.observe(
                lat=lat,
                lon=lon,
                vessel_heading_deg=vessel_heading,
                vessel_speed_knots=vessel_speed,
            )
            self._last_successful_fetch = datetime.now(timezone.utc)
            return obs
        except Exception as e:
            self._last_error = str(e)
            now = datetime.now(timezone.utc)
            meta = DataMetadata(
                source=self.provider_name,
                timestamp=now,
                valid_until=now,
                lat_lon_coverage=self.coverage,
                resolution_km=self.resolution_km,
                data_quality="ERROR",
                confidence=0.0,
                provenance=DataCategory.UNAVAILABLE,
                provider_status=ProviderStatus.ERROR,
            )
            return IcebergObservation(
                latitude=lat,
                longitude=lon,
                nearest_iceberg_id="NONE",
                distance_to_nearest_km=999.0,
                closest_point_of_approach_km=999.0,
                collision_risk_index=0.0,
                threat_level="CLEAR",
                tracked_berg_count=0,
                metadata=meta,
            )

    def fetch_recent(self, lat: float, lon: float, hours: float = 24.0, **kwargs) -> List[IcebergObservation]:
        """Fetch recent observations at coordinate."""
        return [self.fetch_current(lat, lon, **kwargs)]

    def get_catalog(
        self,
        quadrant: Optional[str] = None,
        max_age_days: Optional[float] = None,
        min_confidence: Optional[float] = None,
    ) -> List[TrackedIceberg]:
        """Retrieve catalog of tracked obstacles."""
        return self.service.get_catalog(quadrant, max_age_days, min_confidence)

    def get_iceberg(self, iceberg_id: str) -> Optional[TrackedIceberg]:
        """Fetch individual iceberg details."""
        return self.service.get_iceberg_by_id(iceberg_id)

    def evaluate_route(
        self,
        waypoints: List[RouteWaypoint],
        safety_buffer_km: float = 18.52,
    ) -> RouteIcebergIntersection:
        """Evaluate route corridor cross-track clearances against all catalog icebergs."""
        return self.service.evaluate_route_intersections(waypoints, safety_buffer_km)

    def get_status(self) -> ProviderHealth:
        stat = ProviderStatus.HEALTHY if self._last_error is None else ProviderStatus.DEGRADED
        return ProviderHealth(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            category="ICEBERG",
            status=stat,
            active_provenance=DataCategory.OBSERVED,
            last_update=self.get_last_update(),
            last_successful_fetch=self._last_successful_fetch,
            last_error=self._last_error,
            uptime_pct=100.0,
            coverage=self.coverage,
            resolution_km=self.resolution_km,
        )

    def get_last_update(self) -> Optional[datetime]:
        return self._last_successful_fetch or datetime.now(timezone.utc)

    def get_coverage(self) -> SpatialCoverage:
        return self.coverage
