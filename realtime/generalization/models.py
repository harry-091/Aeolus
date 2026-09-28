"""POLARNAV — Phase 14: Generalization Test Models.

Defines data schemas for evaluating the live route engine across unseen vessels,
novel origin/destination corridors, and extreme/unseen environmental conditions
without relying on historical AIS tracks.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from realtime.ml_risk.models import VesselCharacteristics, PolarIceClass
from realtime.route_optimizer.models import RouteProfileType


class EnvironmentalStressType(str, Enum):
    """Environmental condition profiles for generalization stress-testing."""
    STANDARD_SUMMER_MIZ = "STANDARD_SUMMER_MIZ"
    WINTER_PACK_ICE_BARRIER = "WINTER_PACK_ICE_BARRIER"
    SEVERE_KATABATIC_GALE = "SEVERE_KATABATIC_GALE"
    ICEBERG_SWARM_BARRIER = "ICEBERG_SWARM_BARRIER"
    DOMAIN_BOUNDARY_EDGE = "DOMAIN_BOUNDARY_EDGE"
    OUT_OF_COVERAGE_CONTINENTAL = "OUT_OF_COVERAGE_CONTINENTAL"


class UnseenVesselConfig(BaseModel):
    """Configuration for an unseen vessel never present in training AIS logs."""
    vessel_id: str
    name: str
    vessel_type: str = Field(description="Commercial Container, Polar Yacht, Heavy Icebreaker, etc.")
    ice_class: PolarIceClass
    length_m: float
    beam_m: float
    draft_m: float
    speed_knots: float = 12.0
    operational_constraints: List[str] = Field(default_factory=list)
    max_tolerable_sic: float = Field(default=80.0, description="Maximum SIC % before traversal is prohibited")
    min_under_keel_clearance_m: float = Field(default=2.0, description="Minimum UKC in meters")


class NovelCorridorConfig(BaseModel):
    """Novel origin-destination geographic corridor without historical AIS logs."""
    corridor_id: str
    name: str
    origin: List[float] = Field(description="[lat, lon] of origin")
    destination: List[float] = Field(description="[lat, lon] of destination")
    description: str = ""
    expected_geographic_region: str = "Antarctic Maritime"


class GeneralizationTestRequest(BaseModel):
    """Request payload to test generalization on custom inputs."""
    vessel: UnseenVesselConfig
    corridor: NovelCorridorConfig
    stress_condition: EnvironmentalStressType = EnvironmentalStressType.STANDARD_SUMMER_MIZ
    profile: RouteProfileType = RouteProfileType.BALANCED


class GeneralizationTestResult(BaseModel):
    """Comprehensive outcome of a generalization test case."""
    scenario_id: str
    scenario_name: str
    vessel_id: str
    vessel_name: str
    vessel_type: str
    vessel_ice_class: str
    vessel_draft_m: float
    corridor_id: str
    corridor_name: str
    stress_condition: str
    
    # Core Generalization Invariant
    historical_ais_used: bool = Field(
        default=False,
        description="Must be strictly False. Demonstrates zero reliance on historical AIS."
    )
    
    # Feasibility & Routing
    is_feasible: bool = Field(description="True if route strictly has zero land crossings and positive UKC")
    route_found: bool = Field(description="Whether a valid route was synthesized")
    route_waypoints_count: int = 0
    distance_km: float = 0.0
    distance_nm: float = 0.0
    gross_transit_hours: float = 0.0
    
    # Environmental & Risk Dimensions
    composite_risk_score: float = 0.0
    risk_category: str = "UNKNOWN"
    max_sic_encountered: float = 0.0
    high_sic_distance_km: float = 0.0
    min_depth_m: float = 0.0
    min_under_keel_clearance_m: float = 0.0
    min_iceberg_cpa_nm: float = 999.0
    
    # Performance & Limitations
    computation_time_ms: float = 0.0
    limitation_notes: List[str] = Field(default_factory=list)
    path_coords: List[List[float]] = Field(default_factory=list)
    confidence_score: float = 1.0


class GeneralizationBenchmarkReport(BaseModel):
    """Aggregate benchmark report across the full generalization test suite."""
    report_id: str
    timestamp: str
    total_tests: int
    passed_tests: int
    feasibility_rate_pct: float
    zero_historical_ais_guarantee: bool = True
    unseen_vessels_tested: List[str]
    novel_corridors_tested: List[str]
    environmental_conditions_tested: List[str]
    results: List[GeneralizationTestResult]
    disclosed_limitations: List[str]
    summary_verdict: str
