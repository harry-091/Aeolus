"""Real-Time Antarctic Seabed Bathymetry & Keel Clearance Provider (Phase 7).

Ingests NOAA NGDC ETOPO 2022 Global Relief Model and circumpolar bathymetry grids.
Exposes explicit provenance:
- REANALYZED: Static authoritative seabed topography and relief model.
- DERIVED: Under-keel clearance, land masking, and draft grounding evaluations.
- UNAVAILABLE: Coordinate outside polar bounds.
"""
from datetime import datetime, timezone, timedelta
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
    SeabedZone,
    BathymetryObservation,
    NavigationGeometryPoint,
    RouteGeometryValidationResult,
)
from .service import navigation_geometry_service, NavigationGeometryService


def classify_seabed_zone(depth_m: float, is_land: bool = False) -> str:
    """Classify seabed depth zone."""
    if is_land:
        return "LAND"
    elif depth_m < 20.0:
        return "SHOAL_GROUNDING_HAZARD"
    elif depth_m < 200.0:
        return "SHALLOW_CONTINENTAL_SHELF"
    elif depth_m < 1000.0:
        return "CONTINENTAL_SLOPE"
    else:
        return "ABYSSAL_PLAIN"


class BathymetryProvider(BaseDataProvider):
    """Unified bathymetric depth and static navigation geometry provider."""

    def __init__(self, service: Optional[NavigationGeometryService] = None):
        self.provider_id = "provider_noaa_etopo_bathymetry"
        self.provider_name = "NOAA NCEI ETOPO 2022 Global Relief Model"
        self.coverage = SpatialCoverage(lat_min=-90.0, lat_max=-50.0, description="Antarctic Coastal & Abyssal Seabed")
        self.resolution_km = 1.85  # 1 arc-minute resolution
        self._last_successful_fetch: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self.service = service or navigation_geometry_service
        self.service.initialize()

    def get_depth(self, lat: float, lon: float) -> float:
        """Query water depth in meters (0.0 on land)."""
        return self.service.get_depth(lat, lon)

    def is_land(self, lat: float, lon: float) -> bool:
        """Check if coordinate is on land or ice sheet."""
        return self.service.is_land(lat, lon)

    def get_depth_clearance(self, lat: float, lon: float, vessel_draft: float = 8.0) -> float:
        """Calculate under-keel clearance in meters (depth - draft)."""
        return self.service.get_depth_clearance(lat, lon, vessel_draft)

    def validate_route(self, waypoints: List[List[float]], vessel_draft: float = 8.0) -> RouteGeometryValidationResult:
        """Audit route waypoints against land, shallow water, and clearance."""
        return self.service.validate_route_geometry(waypoints, vessel_draft)

    def fetch_current(self, lat: float, lon: float, vessel_draft_m: float = 8.0, **kwargs) -> BathymetryObservation:
        """Fetch depth, land check, and under-keel clearance at coordinates."""
        now = datetime.now(timezone.utc)

        # Coordinate bounds check
        if not self.coverage.contains(lat, lon):
            meta = DataMetadata(
                source=self.provider_name,
                timestamp=now,
                valid_until=now + timedelta(days=365),
                lat_lon_coverage=self.coverage,
                resolution_km=self.resolution_km,
                data_quality="UNAVAILABLE",
                confidence=0.0,
                provenance=DataCategory.UNAVAILABLE,
                provider_status=ProviderStatus.DEGRADED,
            )
            return BathymetryObservation(
                latitude=lat,
                longitude=lon,
                depth_meters=3500.0,
                is_shallow_warning=False,
                is_grounding_hazard=False,
                under_keel_clearance_m=round(3500.0 - vessel_draft_m, 1),
                seabed_zone="OUT_OF_BOUNDS",
                metadata=meta,
            )

        try:
            depth_val = self.service.get_depth(lat, lon)
            on_land = self.service.is_land(lat, lon)
            under_keel = self.service.get_depth_clearance(lat, lon, vessel_draft_m)

            is_shallow = not on_land and depth_val < 50.0
            is_grounding = on_land or depth_val < 20.0 or under_keel <= 0.0

            meta = DataMetadata(
                source=self.provider_name,
                timestamp=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                received_at=now,
                valid_until=now + timedelta(days=365),  # Bathymetry is persistent static relief
                lat_lon_coverage=self.coverage,
                resolution_km=self.resolution_km,
                data_quality="HIGH",
                confidence=0.98,
                provenance=DataCategory.REANALYZED,     # Authoritative global relief model
                provider_status=ProviderStatus.HEALTHY,
                is_stale=False,
            )

            self._last_successful_fetch = now
            return BathymetryObservation(
                latitude=lat,
                longitude=lon,
                depth_meters=round(depth_val, 1),
                is_shallow_warning=is_shallow,
                is_grounding_hazard=is_grounding,
                under_keel_clearance_m=round(under_keel, 1),
                seabed_zone=classify_seabed_zone(depth_val, on_land),
                metadata=meta,
            )
        except Exception as e:
            self._last_error = str(e)
            meta = DataMetadata(
                source=self.provider_name,
                timestamp=now,
                valid_until=now,
                lat_lon_coverage=self.coverage,
                resolution_km=self.resolution_km,
                data_quality="ERROR",
                confidence=0.0,
                provenance=DataCategory.UNAVAILABLE,
                provider_status=ProviderStatus.OFFLINE,
            )
            return BathymetryObservation(
                latitude=lat,
                longitude=lon,
                depth_meters=3500.0,
                is_shallow_warning=False,
                is_grounding_hazard=False,
                under_keel_clearance_m=round(3500.0 - vessel_draft_m, 1),
                seabed_zone="UNKNOWN",
                metadata=meta,
            )

    def fetch_recent(self, lat: float, lon: float, hours: float = 24.0, **kwargs) -> List[BathymetryObservation]:
        return [self.fetch_current(lat, lon, **kwargs)]

    def get_status(self) -> ProviderHealth:
        stat = ProviderStatus.HEALTHY if self._last_error is None else ProviderStatus.DEGRADED
        return ProviderHealth(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            category="BATHYMETRY",
            status=stat,
            active_provenance=DataCategory.REANALYZED,
            last_update=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
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
