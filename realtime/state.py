"""POLARNAV // Phase 8: Real-Time Maritime Data Fusion Engine.

Combines the latest available telemetry from:
- Satellite (SAR & Optical)
- Sea Ice (Concentration, Edge, Extent, Drift)
- Weather (Atmospheric Pressure, Temperature, Winds)
- Ocean Currents (Copernicus GLO12 Physics, Leeway)
- Waves (Significant Wave Height, Direction, Period)
- Icebergs (BYU/NIC Tracking, Kinematic CPA, Spatial Density)
- Bathymetry (NOAA ETOPO 2022 Relief, Soundings)
- Coastline (Distance to Coast, Continental Boundaries)
- Vessel State (Speed, Heading, Draft, Polar Class)

into a unified, coherent CurrentMaritimeState.

ANTI-FALSIFICATION TEMPORAL INVARIANTS:
1. Different sources have different timestamps — NEVER pretend they were measured simultaneously.
2. Every layer tracks authentic source timestamps, elapsed data age, calibrated confidence, and freshness.
3. Derives a unified multi-sensor environmental confidence score.
4. If critical data (sea ice, weather, iceberg) becomes stale:
   - FLAG IT explicitly (critical_data_stale = True, degraded_operation = True).
   - Emit unignorable actionable warnings.
   - Do NOT silently continue as if it were live.
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
import math
from typing import Dict, List, Any, Optional, Tuple, Union
from pydantic import BaseModel, Field

from .base import (
    DataCategory,
    ProviderStatus,
    ProviderHealth,
    DataMetadata,
    SpatialCoverage,
)
from .sea_ice import SeaIceProvider, SeaIceObservation
from .iceberg import IcebergProvider, IcebergObservation
from .bathymetry import BathymetryProvider, BathymetryObservation, navigation_geometry_service
from .weather import WeatherProvider, WeatherObservation
from .ocean import OceanProvider, OceanObservation
from .satellite import SatelliteProvider, SatelliteObservation


# =============================================================================
# 1. TEMPORAL & FRESHNESS DEFINITIONS
# =============================================================================

class LayerFreshness(str, Enum):
    """Categorical freshness status for an environmental layer."""
    FRESH = "FRESH"              # Within primary tactical freshness threshold
    ACCEPTABLE = "ACCEPTABLE"    # Within secondary operational threshold
    STALE = "STALE"              # Exceeds operational threshold; cached fallback
    EXPIRED = "EXPIRED"          # Severely aged; unsuited for safe tactical navigation
    UNAVAILABLE = "UNAVAILABLE"  # Sensor offline or out of spatial swath


class VesselState(BaseModel):
    """Operational state of the navigated vessel."""
    speed_knots: float = Field(default=12.0, ge=0.0, le=40.0, description="Vessel speed over ground in knots")
    heading_deg: float = Field(default=0.0, ge=0.0, le=360.0, description="True heading in degrees [0, 360)")
    draft_m: float = Field(default=8.0, ge=1.0, le=30.0, description="Vessel design/current draft in meters")
    polar_class: str = Field(default="PC5", description="IMO Polar Class (e.g. PC1-PC7, Non-Ice)")
    beam_m: Optional[float] = Field(default=20.0, description="Vessel beam width in meters")
    length_m: Optional[float] = Field(default=100.0, description="Vessel length overall in meters")
    displacement_mt: Optional[float] = Field(default=5000.0, description="Displacement in metric tons")


class LayerTemporalAudit(BaseModel):
    """Rigorous per-layer temporal and confidence metadata."""
    layer_name: str
    source: str
    category: DataCategory
    timestamp: datetime
    timestamp_iso: str
    data_age_hours: float
    data_age_seconds: float
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: LayerFreshness
    is_stale: bool
    threshold_hours: float
    is_critical: bool = False
    warning: Optional[str] = None


# =============================================================================
# 2. DISCRETE CELL ENVIRONMENTAL PRIMITIVES
# =============================================================================

class CellWindState(BaseModel):
    """Atmospheric wind conditions at cell / route node."""
    speed_knots: float
    direction_deg: float
    gust_knots: Optional[float] = None
    severity: str = "LOW"
    timestamp: Optional[datetime] = None


class CellWaveState(BaseModel):
    """Maritime sea state and swell conditions at cell / route node."""
    height_m: float
    direction_deg: float
    period_s: float
    severity: str = "LOW"
    timestamp: Optional[datetime] = None


class CellCurrentState(BaseModel):
    """Ocean hydrodynamic currents at cell / route node."""
    speed_knots: float
    direction_deg: float
    u_ms: float
    v_ms: float
    leeway_drift_deg: Optional[float] = 0.0
    apparent_speed_knots: Optional[float] = 0.0
    timestamp: Optional[datetime] = None


class CoastlineObservation(BaseModel):
    """Static and dynamic coastline proximity diagnostics."""
    is_land: bool
    distance_to_coast_km: float
    coastal_zone: str  # "INLAND", "COASTAL_MARGIN", "NEARSHORE", "OFFSHORE", "OPEN_OCEAN"
    seabed_margin: str
    metadata: DataMetadata


class SpatialCellMaritimeState(BaseModel):
    """Normalized multi-sensor fusion state for a discrete geographic cell or route node.
    
    Contains all 13 canonical parameters explicitly required by Phase 8:
    1. timestamp
    2. sic (Sea Ice Concentration)
    3. ice_risk
    4. iceberg_risk
    5. wind
    6. wave
    7. current
    8. sst (Sea Surface Temperature)
    9. air_temperature
    10. pressure
    11. depth
    12. land_status
    13. data_confidence
    """
    latitude: float
    longitude: float
    timestamp: datetime  # Exact fusion time

    # 13 Canonical Navigation Parameters
    sic: float = Field(ge=0.0, le=100.0, description="Sea ice concentration (0-100%)")
    ice_risk: float = Field(ge=0.0, le=1.0, description="Normalized sea ice collision/besetting risk [0, 1]")
    iceberg_risk: float = Field(ge=0.0, le=1.0, description="Normalized iceberg proximity collision hazard [0, 1]")
    wind: CellWindState
    wave: CellWaveState
    current: CellCurrentState
    sst: float = Field(description="Sea surface temperature in degrees Celsius")
    air_temperature: float = Field(description="Surface air temperature in degrees Celsius")
    pressure: float = Field(description="Mean sea-level atmospheric pressure in hPa")
    depth: float = Field(ge=0.0, description="Water depth in meters (0.0 on land)")
    land_status: str = Field(description="'LAND', 'WATER', 'ICE_SHELF', or 'SHALLOW_WATER'")
    is_land: bool = Field(description="True if cell lies on continental land or ice sheet")
    data_confidence: float = Field(ge=0.0, le=1.0, description="Unified multi-source environmental confidence [0, 1]")

    # Geometry & Proximity Diagnostics
    coastline_distance_km: float
    under_keel_clearance_m: float

    # Non-simultaneous Layer Temporal Tracking
    source_timestamps: Dict[str, str] = Field(
        default_factory=dict,
        description="Individual observation timestamps per sensor layer (proving non-simultaneous acquisition)"
    )
    layer_audits: Dict[str, LayerTemporalAudit] = Field(default_factory=dict)

    # Staleness & Anti-Falsification Flags
    has_stale_data: bool = False
    critical_data_stale: bool = False
    stale_layers: List[str] = Field(default_factory=list)
    staleness_warnings: List[str] = Field(default_factory=list)


# =============================================================================
# 3. TOP-LEVEL CURRENT MARITIME STATE SNAPSHOT
# =============================================================================

class CurrentMaritimeState(BaseModel):
    """Unified composite environmental state snapshot at a geographic coordinate.
    
    Combines Satellite, Sea Ice, Weather, Ocean Currents, Waves, Icebergs,
    Bathymetry, Coastline, and Vessel State.
    """
    latitude: float
    longitude: float
    queried_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Vessel State
    vessel_state: VesselState = Field(default_factory=VesselState)

    # 7 Autonomous Provider Layers
    satellite: SatelliteObservation
    sea_ice: SeaIceObservation
    weather: WeatherObservation
    ocean: OceanObservation
    iceberg: IcebergObservation
    bathymetry: BathymetryObservation
    coastline: CoastlineObservation

    # Normalized Spatial Cell Representation (13 Canonical Parameters)
    cell_state: SpatialCellMaritimeState

    # Multi-Source Temporal & Confidence Tracking
    layer_audits: Dict[str, LayerTemporalAudit] = Field(default_factory=dict)
    unified_environmental_confidence: float = Field(ge=0.0, le=1.0)
    data_freshness_index: float = Field(ge=0.0, le=1.0)

    # Critical Staleness & Operational Safety Alerts
    has_stale_data: bool = False
    critical_data_stale: bool = False
    stale_layers: List[str] = Field(default_factory=list)
    staleness_warnings: List[str] = Field(default_factory=list)
    degraded_operation: bool = False
    operational_advisory: str = "NORMAL_NAVIGATION"

    # Backwards-Compatible Derived Composite Decision Metrics
    composite_navigation_risk: float = Field(ge=0.0, le=1.0)
    composite_safety_index: float = Field(ge=0.0, le=1.0)
    imo_polar_advisory: str = "CLEAR_NAVIGATION"
    provenance_breakdown: Dict[str, str] = Field(default_factory=dict)
    all_providers_healthy: bool = True


# =============================================================================
# 4. MARITIME STATE MANAGER & DATA FUSION ENGINE
# =============================================================================

class MaritimeStateManager:
    """Orchestrates all real-time polar environmental ingestion providers,
    performs multi-sensor temporal alignment, evaluates unified confidence,
    and enforces strict critical staleness flagging.
    """

    # Primary tactical freshness limits (in hours)
    FRESHNESS_THRESHOLDS: Dict[str, float] = {
        "sea_ice": 24.0,       # Daily NOAA CDR / AMSR2 pass (Critical)
        "weather": 6.0,        # Numerical atmospheric prediction cycle (Critical)
        "iceberg": 168.0,      # BYU/NIC weekly consolidation (Critical)
        "ocean": 48.0,         # Copernicus MERCATOR daily physics
        "satellite": 24.0,     # Sentinel-1 SAR orbital repeat cycle
        "bathymetry": 87600.0, # Static NOAA ETOPO relief model (10 years)
        "coastline": 87600.0,  # Static continental boundary polygon (10 years)
    }

    # Relative multi-sensor weightings for unified environmental confidence
    CONFIDENCE_WEIGHTS: Dict[str, float] = {
        "sea_ice": 0.25,       # Primary polar obstacle & resistance hazard
        "iceberg": 0.20,       # Major catastrophic collision hazard
        "bathymetry": 0.15,    # Grounding & draft clearance hazard
        "weather": 0.15,       # Sea state, storm winds & structural icing
        "ocean": 0.10,         # Hydrodynamic drift & leeway advection
        "satellite": 0.10,     # High-resolution SAR ground-truth validation
        "coastline": 0.05,     # Continental boundary separation
    }

    CRITICAL_LAYERS = {"sea_ice", "weather", "iceberg"}

    def __init__(self):
        self.sea_ice_provider = SeaIceProvider()
        self.iceberg_provider = IcebergProvider()
        self.bathymetry_provider = BathymetryProvider()
        self.weather_provider = WeatherProvider()
        self.ocean_provider = OceanProvider()
        self.satellite_provider = SatelliteProvider()

    def _evaluate_layer_temporal_audit(
        self,
        layer_name: str,
        metadata: DataMetadata,
        now: datetime,
    ) -> LayerTemporalAudit:
        """Compute exact non-simultaneous temporal telemetry, age, and freshness."""
        dt = metadata.timestamp
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        age_sec = max(0.0, (now - dt).total_seconds())
        age_hours = round(age_sec / 3600.0, 2)
        threshold = self.FRESHNESS_THRESHOLDS.get(layer_name, 24.0)
        is_crit = layer_name in self.CRITICAL_LAYERS

        # Freshness classification
        if metadata.provenance in (DataCategory.UNAVAILABLE, DataCategory.STALE) or metadata.is_stale:
            freshness = LayerFreshness.STALE
            is_stale = True
        elif age_hours <= 0.5 * threshold:
            freshness = LayerFreshness.FRESH
            is_stale = False
        elif age_hours <= 1.0 * threshold:
            freshness = LayerFreshness.ACCEPTABLE
            is_stale = False
        elif age_hours <= 2.0 * threshold:
            freshness = LayerFreshness.STALE
            is_stale = True
        else:
            freshness = LayerFreshness.EXPIRED
            is_stale = True

        warning = None
        if is_stale:
            if is_crit:
                warning = (
                    f"CRITICAL: {layer_name.upper()} observation timestamp {dt.isoformat()} "
                    f"is {age_hours:.1f}h old (exceeds {threshold:.1f}h threshold). "
                    f"Live navigation safety cannot be guaranteed without manual confirmation."
                )
            else:
                warning = (
                    f"WARNING: {layer_name.capitalize()} data is {age_hours:.1f}h old "
                    f"(exceeds {threshold:.1f}h threshold)."
                )

        return LayerTemporalAudit(
            layer_name=layer_name,
            source=metadata.source,
            category=metadata.provenance,
            timestamp=dt,
            timestamp_iso=dt.isoformat(),
            data_age_hours=age_hours,
            data_age_seconds=round(age_sec, 1),
            confidence=round(float(metadata.confidence), 4),
            freshness=freshness,
            is_stale=is_stale,
            threshold_hours=threshold,
            is_critical=is_crit,
            warning=warning,
        )

    def _compute_unified_confidence(
        self,
        layer_audits: Dict[str, LayerTemporalAudit]
    ) -> Tuple[float, float]:
        """Derive unified multi-sensor confidence score and data freshness index.
        
        Returns:
            (unified_environmental_confidence, data_freshness_index)
        """
        freshness_multipliers = {
            LayerFreshness.FRESH: 1.00,
            LayerFreshness.ACCEPTABLE: 0.90,
            LayerFreshness.STALE: 0.40,
            LayerFreshness.EXPIRED: 0.15,
            LayerFreshness.UNAVAILABLE: 0.00,
        }

        weighted_confidence_sum = 0.0
        weighted_freshness_sum = 0.0
        total_weight = 0.0

        for layer_name, audit in layer_audits.items():
            w = self.CONFIDENCE_WEIGHTS.get(layer_name, 0.1)
            f_factor = freshness_multipliers.get(audit.freshness, 0.5)
            weighted_confidence_sum += w * audit.confidence * f_factor
            weighted_freshness_sum += w * f_factor
            total_weight += w

        base_confidence = weighted_confidence_sum / max(1e-6, total_weight)
        freshness_index = weighted_freshness_sum / max(1e-6, total_weight)

        # Severe penalty if any critical layer is stale
        any_crit_stale = any(a.is_critical and a.is_stale for a in layer_audits.values())
        if any_crit_stale:
            unified_confidence = round(base_confidence * 0.70, 4)
        else:
            unified_confidence = round(base_confidence, 4)

        return unified_confidence, round(freshness_index, 4)

    def get_current_state(
        self,
        lat: float,
        lon: float,
        vessel_heading_deg: float = 0.0,
        vessel_draft_m: float = 8.0,
        vessel_state: Optional[VesselState] = None,
    ) -> CurrentMaritimeState:
        """Query all 7 providers and fuse into a coherent CurrentMaritimeState.
        
        Evaluates distinct timestamps, age, freshness, unified confidence,
        and enforces critical staleness alerting.
        """
        now = datetime.now(timezone.utc)

        # Resolve vessel state parameters
        if vessel_state is not None:
            v_state = vessel_state
            v_heading = vessel_state.heading_deg
            v_draft = vessel_state.draft_m
        else:
            v_state = VesselState(speed_knots=12.0, heading_deg=vessel_heading_deg, draft_m=vessel_draft_m)
            v_heading = vessel_heading_deg
            v_draft = vessel_draft_m

        # 1. Ingest each autonomous environmental layer
        obs_sic = self.sea_ice_provider.fetch_current(lat, lon)
        obs_ib = self.iceberg_provider.fetch_current(lat, lon, vessel_heading=v_heading, vessel_speed=v_state.speed_knots)
        obs_bathy = self.bathymetry_provider.fetch_current(lat, lon, vessel_draft_m=v_draft)
        obs_wx = self.weather_provider.fetch_current(lat, lon)
        obs_oc = self.ocean_provider.fetch_current(lat, lon, vessel_heading_deg=v_heading)
        obs_sat = self.satellite_provider.fetch_current(lat, lon)

        # 2. Build Coastline Observation from static navigation geometry layer
        navigation_geometry_service.initialize()
        is_land_val = navigation_geometry_service.is_land(lat, lon)
        dist_coast = navigation_geometry_service.get_coastline_distance_km(lat, lon)
        if is_land_val:
            c_zone = "INLAND"
        elif dist_coast <= 10.0:
            c_zone = "COASTAL_MARGIN"
        elif dist_coast <= 50.0:
            c_zone = "NEARSHORE"
        elif dist_coast <= 200.0:
            c_zone = "OFFSHORE"
        else:
            c_zone = "OPEN_OCEAN"

        coastline_meta = DataMetadata(
            source="Antarctica High-Resolution Coastline Polygon Model",
            timestamp=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            valid_until=datetime(2032, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            lat_lon_coverage=SpatialCoverage(),
            resolution_km=1.0,
            confidence=1.0,
            provenance=DataCategory.REANALYZED,
            provider_status=ProviderStatus.HEALTHY,
            is_stale=False,
        )
        obs_coast = CoastlineObservation(
            is_land=is_land_val,
            distance_to_coast_km=round(dist_coast, 2),
            coastal_zone=c_zone,
            seabed_margin="CONTINENTAL_MARGIN" if dist_coast <= 50.0 else "ABYSSAL_PLAIN",
            metadata=coastline_meta,
        )

        # 3. Dynamic Staleness Evaluation
        obs_sic.metadata.check_staleness()
        obs_wx.metadata.check_staleness()
        obs_sat.metadata.check_staleness()

        # 4. Build Non-Simultaneous Layer Temporal Audits
        layer_audits: Dict[str, LayerTemporalAudit] = {
            "sea_ice": self._evaluate_layer_temporal_audit("sea_ice", obs_sic.metadata, now),
            "iceberg": self._evaluate_layer_temporal_audit("iceberg", obs_ib.metadata, now),
            "bathymetry": self._evaluate_layer_temporal_audit("bathymetry", obs_bathy.metadata, now),
            "weather": self._evaluate_layer_temporal_audit("weather", obs_wx.metadata, now),
            "ocean": self._evaluate_layer_temporal_audit("ocean", obs_oc.metadata, now),
            "satellite": self._evaluate_layer_temporal_audit("satellite", obs_sat.metadata, now),
            "coastline": self._evaluate_layer_temporal_audit("coastline", obs_coast.metadata, now),
        }

        # 5. Evaluate Multi-Sensor Confidence & Staleness Flags
        unified_conf, freshness_idx = self._compute_unified_confidence(layer_audits)

        stale_layers = [name for name, a in layer_audits.items() if a.is_stale]
        has_stale = len(stale_layers) > 0
        critical_stale = any(a.is_critical and a.is_stale for a in layer_audits.values())
        staleness_warnings = [a.warning for a in layer_audits.values() if a.warning]

        # 6. Provenance Mapping
        prov_map = {
            "sea_ice": obs_sic.metadata.provenance.value,
            "iceberg": obs_ib.metadata.provenance.value,
            "bathymetry": obs_bathy.metadata.provenance.value,
            "weather": obs_wx.metadata.provenance.value,
            "ocean": obs_oc.metadata.provenance.value,
            "satellite_sar": obs_sat.metadata.provenance.value,
            "coastline": obs_coast.metadata.provenance.value,
        }

        # 7. Health Status
        healths = self.get_all_provider_health()
        all_healthy = all(h.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED) for h in healths)

        # 8. Composite Risk Calculations (IMO Polar Code aligned)
        sic_risk = max(0.0, min(1.0, obs_sic.concentration_pct / 100.0 if hasattr(obs_sic, "concentration_pct") else obs_sic.sic_fraction))
        ib_risk = max(0.0, min(1.0, 1.0 - (obs_ib.distance_to_nearest_km / 100.0)))
        depth_risk = 1.0 if obs_bathy.is_grounding_hazard else (0.4 if obs_bathy.is_shallow_warning else 0.0)
        wx_risk = min(1.0, (obs_wx.wind_speed_knots / 60.0) * 0.6 + (obs_wx.wave_height_meters / 6.0) * 0.4)

        composite_risk = (
            0.45 * sic_risk +
            0.25 * ib_risk +
            0.15 * depth_risk +
            0.15 * wx_risk
        )
        composite_risk = round(float(max(0.0, min(1.0, composite_risk))), 4)
        csi = round(1.0 - composite_risk, 4)

        # Advisory determinations
        degraded_op = critical_stale or (not all_healthy)

        # 1. Pure IMO Polar Code risk-based classification
        if obs_bathy.is_grounding_hazard or composite_risk >= 0.75:
            imo_advisory = "PROHIBITED_TRANSIT"
        elif composite_risk >= 0.50:
            imo_advisory = "ICE_WATCH_ESCORT_REQUIRED"
        elif composite_risk >= 0.25:
            imo_advisory = "HEIGHTENED_WATCH"
        else:
            imo_advisory = "CLEAR_NAVIGATION"

        # 2. Operational advisory incorporating sensor staleness mode
        if obs_bathy.is_grounding_hazard or composite_risk >= 0.75:
            operational_adv = "PROHIBITED_TRANSIT"
        elif critical_stale:
            operational_adv = "DEGRADED_OPERATION_CRITICAL_DATA_STALE"
        elif composite_risk >= 0.50:
            operational_adv = "ICE_WATCH_ESCORT_REQUIRED"
        elif composite_risk >= 0.25:
            operational_adv = "HEIGHTENED_WATCH"
        else:
            operational_adv = "CLEAR_NAVIGATION"

        # 9. Populate the 13 Canonical Parameters for SpatialCellMaritimeState
        source_timestamps = {name: a.timestamp_iso for name, a in layer_audits.items()}

        # Extract atmospheric and maritime variables safely
        wind_spd = float(getattr(obs_wx, "wind_speed_knots", 0.0))
        wind_dir = float(getattr(obs_wx, "wind_direction_deg", 0.0))
        wind_gust = (
            float(obs_wx.atmosphere.wind_speed.value * 1.25)
            if hasattr(obs_wx, "atmosphere") and hasattr(obs_wx.atmosphere, "wind_speed")
            else None
        )
        wind_sev = (
            getattr(obs_wx.derived_features, "wind_severity_category", "MODERATE")
            if hasattr(obs_wx, "derived_features")
            else "MODERATE"
        )
        wind_state = CellWindState(
            speed_knots=wind_spd,
            direction_deg=wind_dir,
            gust_knots=wind_gust,
            severity=str(wind_sev),
            timestamp=obs_wx.metadata.timestamp,
        )

        wave_h = float(getattr(obs_wx, "wave_height_meters", 0.0))
        if hasattr(obs_wx, "maritime") and hasattr(obs_wx.maritime, "wave_direction"):
            wave_d = float(obs_wx.maritime.wave_direction.value)
            wave_p = float(obs_wx.maritime.wave_period.value)
            wave_s = getattr(obs_wx.maritime, "sea_state_description", "MODERATE")
        else:
            wave_d = float(getattr(obs_wx, "wave_direction_deg", 0.0))
            wave_p = float(getattr(obs_wx, "wave_period_seconds", 8.0))
            wave_s = "MODERATE"

        wave_state = CellWaveState(
            height_m=wave_h,
            direction_deg=wave_d,
            period_s=wave_p,
            severity=str(wave_s),
            timestamp=obs_wx.metadata.timestamp,
        )

        current_state = CellCurrentState(
            speed_knots=float(getattr(obs_oc, "current_speed_knots", 0.0)),
            direction_deg=float(getattr(obs_oc, "current_direction_deg", 0.0)),
            u_ms=float(getattr(obs_oc, "zonal_uo_ms", getattr(obs_oc, "u_current_ms", 0.0))),
            v_ms=float(getattr(obs_oc, "meridional_vo_ms", getattr(obs_oc, "v_current_ms", 0.0))),
            leeway_drift_deg=float(getattr(obs_oc, "leeway_crab_angle_deg", 0.0)),
            apparent_speed_knots=float(getattr(obs_oc, "apparent_speed_knots", getattr(obs_oc, "current_speed_knots", 0.0))),
            timestamp=obs_oc.metadata.timestamp,
        )

        land_status_str = (
            "LAND" if is_land_val else (
                "SHALLOW_WATER" if obs_bathy.is_grounding_hazard or obs_bathy.is_shallow_warning else "WATER"
            )
        )

        air_temp = float(getattr(obs_wx, "temperature_celsius", getattr(obs_wx, "air_temperature_c", 0.0)))
        surf_press = float(getattr(obs_wx, "surface_pressure_hpa", 1013.25))
        sst_val = float(getattr(obs_oc, "sea_surface_temp_c", getattr(obs_oc, "sea_surface_temperature_c", 0.0)))

        cell_state = SpatialCellMaritimeState(
            latitude=lat,
            longitude=lon,
            timestamp=now,
            sic=round(float(obs_sic.concentration_pct if hasattr(obs_sic, "concentration_pct") else obs_sic.sic_fraction * 100.0), 2),
            ice_risk=round(sic_risk, 4),
            iceberg_risk=round(ib_risk, 4),
            wind=wind_state,
            wave=wave_state,
            current=current_state,
            sst=round(sst_val, 2),
            air_temperature=round(air_temp, 2),
            pressure=round(surf_press, 2),
            depth=round(float(obs_bathy.depth_meters), 2),
            land_status=land_status_str,
            is_land=is_land_val,
            data_confidence=unified_conf,
            coastline_distance_km=round(dist_coast, 2),
            under_keel_clearance_m=round(float(obs_bathy.under_keel_clearance_m), 2),
            source_timestamps=source_timestamps,
            layer_audits=layer_audits,
            has_stale_data=has_stale,
            critical_data_stale=critical_stale,
            stale_layers=stale_layers,
            staleness_warnings=staleness_warnings,
        )

        return CurrentMaritimeState(
            latitude=lat,
            longitude=lon,
            queried_at=now,
            vessel_state=v_state,
            satellite=obs_sat,
            sea_ice=obs_sic,
            weather=obs_wx,
            ocean=obs_oc,
            iceberg=obs_ib,
            bathymetry=obs_bathy,
            coastline=obs_coast,
            cell_state=cell_state,
            layer_audits=layer_audits,
            unified_environmental_confidence=unified_conf,
            data_freshness_index=freshness_idx,
            has_stale_data=has_stale,
            critical_data_stale=critical_stale,
            stale_layers=stale_layers,
            staleness_warnings=staleness_warnings,
            degraded_operation=degraded_op,
            operational_advisory=operational_adv,
            composite_navigation_risk=composite_risk,
            composite_safety_index=csi,
            imo_polar_advisory=imo_advisory,
            provenance_breakdown=prov_map,
            all_providers_healthy=all_healthy,
        )

    def get_spatial_cell_state(
        self,
        lat: float,
        lon: float,
        vessel_state: Optional[VesselState] = None,
    ) -> SpatialCellMaritimeState:
        """Convenience method returning the 13-parameter SpatialCellMaritimeState."""
        full_state = self.get_current_state(lat=lat, lon=lon, vessel_state=vessel_state)
        return full_state.cell_state

    def fuse_route_nodes(
        self,
        waypoints: List[Tuple[float, float]],
        vessel_state: Optional[VesselState] = None,
    ) -> List[SpatialCellMaritimeState]:
        """Evaluate and fuse the complete environmental state along route nodes.
        
        Args:
            waypoints: List of (lat, lon) pairs along the planned voyage corridor.
            vessel_state: Optional vessel dimensions and speed.
            
        Returns:
            List of SpatialCellMaritimeState instances with all 13 canonical parameters.
        """
        fused_nodes = []
        for lat, lon in waypoints:
            cell = self.get_spatial_cell_state(lat=lat, lon=lon, vessel_state=vessel_state)
            fused_nodes.append(cell)
        return fused_nodes

    def get_all_provider_health(self) -> List[ProviderHealth]:
        """Collect diagnostic health across all 6 primary ingestion providers."""
        return [
            self.sea_ice_provider.get_status(),
            self.iceberg_provider.get_status(),
            self.bathymetry_provider.get_status(),
            self.weather_provider.get_status(),
            self.ocean_provider.get_status(),
            self.satellite_provider.get_status(),
        ]

    def get_system_status(self) -> Dict[str, Any]:
        """Summary dashboard telemetry for real-time ingestion status."""
        healths = self.get_all_provider_health()
        now = datetime.now(timezone.utc)
        return {
            "timestamp": now.isoformat(),
            "overall_status": "ONLINE" if all(h.status != ProviderStatus.OFFLINE for h in healths) else "DEGRADED",
            "provider_count": len(healths),
            "healthy_count": sum(1 for h in healths if h.status == ProviderStatus.HEALTHY),
            "degraded_count": sum(1 for h in healths if h.status == ProviderStatus.DEGRADED),
            "offline_count": sum(1 for h in healths if h.status == ProviderStatus.OFFLINE),
            "providers": [h.model_dump() if hasattr(h, "model_dump") else h.dict() for h in healths],
        }


# Global singleton manager instance
maritime_state_manager = MaritimeStateManager()
