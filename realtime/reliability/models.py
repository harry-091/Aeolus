"""POLARNAV — Phase 15: Production Reliability and Failure Handling Models.

Defines data schemas for auditing system health, tracking provider availability,
detecting stale or unavailable environmental feeds, enforcing anti-fabrication
rules, and managing resilience fallbacks.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ProviderId(str, Enum):
    """Core real-time environmental and navigation providers."""
    SATELLITE = "satellite"
    SEA_ICE = "sea_ice"
    WEATHER = "weather"
    OCEAN = "ocean"
    ICEBERG = "iceberg"
    BATHYMETRY = "bathymetry"


class HealthStatus(str, Enum):
    """Discrete operational health status of an ingestion provider."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class DataAvailabilityState(str, Enum):
    """Standardized user-facing data availability classification."""
    LIVE = "LIVE"
    DATA_STALE = "DATA STALE"
    DATA_UNAVAILABLE = "DATA UNAVAILABLE"
    FALLBACK_ACTIVE = "FALLBACK ACTIVE"


class FaultType(str, Enum):
    """Simulated failure modes for chaos engineering and reliability testing."""
    API_FAILURE = "API_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    TIMEOUT = "TIMEOUT"
    STALE_DATA = "STALE_DATA"
    MALFORMED_DATA = "MALFORMED_DATA"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    CONFLICTING_TIMESTAMPS = "CONFLICTING_TIMESTAMPS"


class FaultInjectionConfig(BaseModel):
    """Configuration for injecting simulated environmental faults."""
    provider: ProviderId
    fault_type: FaultType
    delay_ms: float = 0.0
    error_message: str = "Simulated provider failure"
    force_stale_hours: float = 72.0
    active: bool = True


class ProviderReliabilityRecord(BaseModel):
    """Real-time reliability, staleness, and fallback telemetry for an individual provider."""
    provider_id: ProviderId
    name: str
    health_status: HealthStatus
    availability_state: DataAvailabilityState
    
    # Provenance & Fallback Tracking
    source_name: str
    observation_timestamp: Optional[str] = None
    data_age_hours: float = 0.0
    freshness_threshold_hours: float = 24.0
    is_stale: bool = False
    is_fallback_active: bool = False
    fallback_label: Optional[str] = Field(
        default=None,
        description="Must be explicitly labelled (e.g., 'FALLBACK_CACHE', 'HISTORICAL_CLIMATOLOGY')."
    )
    
    # Telemetry & Diagnostics
    latency_ms: float = 0.0
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    uptime_pct: float = 100.0
    confidence_multiplier: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence attenuation multiplier due to staleness or fallback"
    )
    limitation_notes: List[str] = Field(default_factory=list)


class SystemReliabilityAudit(BaseModel):
    """Comprehensive system-wide audit of all real-time providers and routing resilience."""
    audit_id: str
    timestamp: str
    overall_status: HealthStatus = HealthStatus.HEALTHY
    
    # Aggregated counts
    total_providers: int = 6
    healthy_providers_count: int = 6
    degraded_providers_count: int = 0
    unavailable_providers_count: int = 0
    stale_providers_count: int = 0
    
    # Critical Safety Invariants
    critical_data_stale: bool = False
    critical_data_unavailable: bool = False
    degraded_routing_operation: bool = False
    route_confidence_penalty_pct: float = 0.0
    max_allowable_route_confidence: float = 1.0
    
    # Provider Details
    providers: Dict[str, ProviderReliabilityRecord]
    
    # Anti-Fabrication & Diagnostics
    zero_fabrication_guaranteed: bool = True
    active_fallbacks_count: int = 0
    active_fault_injections: List[str] = Field(default_factory=list)
    system_limitations_disclosed: List[str] = Field(default_factory=list)
    recommendation: str = "Nominal operation; live navigation data within safety tolerances."
