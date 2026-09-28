"""Domain models for Continuous Live Monitoring (PolarNav Phase 11).

Defines:
- RerouteTriggerType: high SIC, iceberg proximity, severe weather, unsafe depth, current shift, confidence drop
- MonitoringThresholds: configurable trigger criteria with noise filtering deadbands
- RouteAuditResult: validity evaluation of active route against fresh telemetry
- Lineage models: current_route, previous_route, reroute_reason, timestamp
- "Why did POLARNAV change my route?" transparent explainability contracts
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from ..route_optimizer.models import RealtimeOptimizedRoute, RouteProfileType
from ..ml_risk.models import VesselCharacteristics


class RerouteTriggerType(str, Enum):
    """Categorical catalysts that force an automatic route recalculation."""
    NO_CHANGE = "NO_CHANGE"
    HIGH_SIC_INCREASE = "HIGH_SIC_INCREASE"
    ICEBERG_PROXIMITY_BREACH = "ICEBERG_PROXIMITY_BREACH"
    SEVERE_WEATHER_ALERT = "SEVERE_WEATHER_ALERT"
    UNSAFE_DEPTH_OR_GROUNDING = "UNSAFE_DEPTH_OR_GROUNDING"
    ROUTE_OBSTRUCTION = "ROUTE_OBSTRUCTION"
    SIGNIFICANT_CURRENT_CHANGE = "SIGNIFICANT_CURRENT_CHANGE"
    DATA_CONFIDENCE_DEGRADATION = "DATA_CONFIDENCE_DEGRADATION"
    MANUAL = "MANUAL"


class MonitoringThresholds(BaseModel):
    """Configurable trigger boundaries with noise rejection deadbands.
    
    Insignificant numerical noise below the floor thresholds is filtered out
    to prevent erratic route flapping.
    """
    # Sea Ice Concentration (%)
    min_sic_delta_pct: float = Field(default=15.0, description="Minimum delta SIC to trigger reroute (%)")
    sic_noise_floor_pct: float = Field(default=5.0, description="Noise threshold below which SIC variation is ignored (%)")
    
    # Iceberg Obstacles (km)
    min_iceberg_cpa_km: float = Field(default=12.0, description="Proximity threshold where iceberg drift forces reroute (km)")
    
    # Weather (Atmosphere & Waves)
    max_wind_delta_knots: float = Field(default=15.0, description="Wind speed increase triggering reroute (knots)")
    wind_noise_floor_knots: float = Field(default=3.0, description="Wind noise deadband (knots)")
    max_wave_delta_m: float = Field(default=1.5, description="Significant wave height increase triggering reroute (m)")
    wave_noise_floor_m: float = Field(default=0.3, description="Wave noise deadband (m)")
    
    # Bathymetry & Under-Keel Clearance (m)
    min_ukc_clearance_m: float = Field(default=2.0, description="Minimum allowable under-keel clearance before grounding alert (m)")
    
    # Hydrodynamic Currents
    max_adverse_current_delta_knots: float = Field(default=2.0, description="Adverse opposing current increase (knots)")
    current_noise_floor_knots: float = Field(default=0.3, description="Current noise deadband (knots)")
    
    # Sensor Data Confidence Floor
    min_confidence_floor: float = Field(default=0.40, description="Confidence floor below which degraded data alert triggers")


class EnvironmentalChange(BaseModel):
    """Detailed parameter-level delta detection at a specific waypoint."""
    parameter: str
    waypoint_index: int
    latitude: float
    longitude: float
    previous_value: float
    current_value: float
    delta: float
    unit: str
    is_meaningful: bool
    description: str


class RouteAuditResult(BaseModel):
    """Result of auditing an active voyage against live updated maritime telemetry."""
    is_valid: bool = Field(description="True if route remains safe and navigable")
    requires_reroute: bool = Field(description="True if a safety threshold was crossed requiring diversion")
    trigger: RerouteTriggerType = Field(default=RerouteTriggerType.NO_CHANGE)
    alert_severity: str = Field(default="INFO", description="INFO, WARNING, or CRITICAL")
    meaningful_changes: List[EnvironmentalChange] = Field(default_factory=list)
    compromised_waypoint_indices: List[int] = Field(default_factory=list)
    why_rerouted: str = Field(description="Clear answer to 'Why did POLARNAV change my route?'")
    alert_banner: Optional[str] = None


class RerouteHistoryRecord(BaseModel):
    """Archival record documenting a route replacement event."""
    record_id: str
    timestamp_iso: str
    trigger: RerouteTriggerType
    primary_catalyst: str
    why_changed: str
    previous_route_id: str
    new_route_id: str
    previous_distance_km: float
    new_distance_km: float
    delta_distance_km: float
    previous_eta_hours: float
    new_eta_hours: float
    delta_eta_hours: float
    previous_risk_score: float
    new_risk_score: float


class MonitoringStatusResponse(BaseModel):
    """Full operational response for the continuous live monitoring loop."""
    monitoring_active: bool
    active_route_id: Optional[str] = None
    active_profile: Optional[RouteProfileType] = None
    last_checked_iso: str
    check_interval_seconds: float
    reroute_count: int
    current_route: Optional[RealtimeOptimizedRoute] = None
    previous_route: Optional[RealtimeOptimizedRoute] = None
    last_reroute_reason: Optional[str] = None
    why_did_polarnav_change_my_route: Optional[str] = None
    active_alerts: List[str] = Field(default_factory=list)
    recent_history: List[RerouteHistoryRecord] = Field(default_factory=list)


class SimulateEventRequest(BaseModel):
    """Payload to simulate live dynamic environmental hazards and test reroute triggers."""
    event_type: str = Field(
        default="HIGH_SIC_INCREASE",
        description="Event type: HIGH_SIC_INCREASE, ICEBERG_PROXIMITY_BREACH, SEVERE_WEATHER_ALERT, UNSAFE_DEPTH_OR_GROUNDING, NOISE"
    )
    waypoint_index: int = Field(default=1, ge=0)
    delta_value: float = Field(default=25.0)
