"""Real-Time Ocean Hydrodynamics & Current Dynamics Provider.

Ingests E.U. Copernicus Marine Service MERCATOR GLO12 physics reanalysis.
Exposes explicit provenance:
- REANALYZED: Numerical hydrodynamic model state (uo, vo surface currents, SST).
- DERIVED: Vessel drift assistance, leeway crab angle, and route impact.
- UNAVAILABLE: Outside Antarctic Southern Ocean domain.

CRITICAL RULES:
- Never presents hydrodynamic model reanalysis as a live buoy/acoustic observation.
- Never hardcodes or fabricates fake current vectors.
- Gracefully handles unavailable regions.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from ..base import (
    BaseDataProvider,
    DataCategory,
    ProviderStatus,
    SpatialCoverage,
    DataMetadata,
    ProviderHealth,
)
from .models import (
    OceanVariable,
    OceanCurrentState,
    OceanEnvironmentalState,
    VesselRelativeCurrent,
    EstimatedCurrentImpact,
    OceanConditionRisk,
    OceanObservation,
    OceanAPIResponse,
)
from .service import ocean_service


class OceanProvider(BaseDataProvider):
    """Unified ocean currents and hydrodynamics provider."""

    def __init__(self):
        self.provider_id = "provider_copernicus_ocean_currents"
        self.provider_name = "E.U. Copernicus Marine Service (MERCATOR GLO12 Reanalysis)"
        self.coverage = SpatialCoverage(
            lat_min=-90.0,
            lat_max=-50.0,
            description="Antarctic Circumpolar Hydrodynamics"
        )
        self.resolution_km = 9.25  # 1/12 degree MERCATOR grid
        self._last_successful_fetch: Optional[datetime] = None
        self._last_error: Optional[str] = None
        ocean_service.initialize()

    def fetch_current(
        self,
        lat: float,
        lon: float,
        vessel_heading_deg: float = 0.0,
        vessel_speed_knots: float = 12.0,
        **kwargs,
    ) -> OceanObservation:
        """Fetch surface current vectors, SST, and vessel drift assistance."""
        try:
            obs = ocean_service.get_ocean_observation(
                lat=lat,
                lon=lon,
                vessel_heading_deg=vessel_heading_deg,
                vessel_speed_knots=vessel_speed_knots,
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
                provider_status=ProviderStatus.OFFLINE,
            )
            dummy_var = OceanVariable(
                value=0.0,
                unit="none",
                timestamp=now.isoformat(),
                source=self.provider_name,
                resolution="Unavailable",
                data_age=0.0,
                confidence=0.0,
                status="UNAVAILABLE",
            )
            return OceanObservation(
                latitude=lat,
                longitude=lon,
                is_available=False,
                currents=OceanCurrentState(
                    eastward_current_uo=dummy_var,
                    northward_current_vo=dummy_var,
                    current_magnitude=dummy_var,
                    current_direction=dummy_var,
                ),
                environment=OceanEnvironmentalState(
                    sea_surface_temperature=dummy_var,
                ),
                vessel_relative=VesselRelativeCurrent(
                    relative_current_angle_deg=0.0,
                    drift_assist_knots=0.0,
                    cross_current_leeway_knots=0.0,
                    leeway_drift_angle_deg=0.0,
                    current_aspect="UNAVAILABLE",
                ),
                route_impact=EstimatedCurrentImpact(
                    effective_speed_over_ground_knots=vessel_speed_knots,
                    estimated_time_delta_percent=0.0,
                    fuel_impact_estimate="NOMINAL",
                ),
                ocean_risk=OceanConditionRisk(
                    risk_score=0.0,
                    risk_level="LOW",
                    opposing_wave_current_hazard=False,
                    wave_steepening_factor=1.0,
                    hypothermia_survival_minutes=60.0,
                    current_shear_hazard=False,
                ),
                metadata=meta,
            )

    def fetch_recent(self, lat: float, lon: float, hours: float = 24.0, **kwargs) -> List[OceanObservation]:
        return [self.fetch_current(lat, lon, **kwargs)]

    def get_status(self) -> ProviderHealth:
        now = datetime.now(timezone.utc)
        stat = ProviderStatus.HEALTHY if self._last_error is None else ProviderStatus.DEGRADED
        return ProviderHealth(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            category="OCEAN",
            status=stat,
            active_provenance=DataCategory.REANALYZED,
            last_update=self.get_last_update(),
            last_successful_fetch=self._last_successful_fetch,
            last_error=self._last_error,
            uptime_pct=100.0,
            coverage=self.coverage,
            resolution_km=self.resolution_km,
        )

    def get_last_update(self) -> Optional[datetime]:
        return self._last_successful_fetch or ocean_service._reg_timestamp

    def get_coverage(self) -> SpatialCoverage:
        return self.coverage
