"""POLARNAV // Phase 9: Real-Time Vessel-Aware ML Risk Models.

Defines schemas for:
1. Vessel characteristics (type, dimensions, speed, heading, ice class, constraints).
2. Risk prediction outputs (continuous score, categorical classification, factorized breakdown).
3. Non-fabricated confidence and limitation reporting.
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class VesselType(str, Enum):
    """Vessel structural classification."""
    ICEBREAKER = "ICEBREAKER"
    RESEARCH_VESSEL = "RESEARCH_VESSEL"
    CARGO = "CARGO"
    PASSENGER_EXPEDITION = "PASSENGER_EXPEDITION"
    TANKER = "TANKER"
    FISHING = "FISHING"
    SUPPORT_TUG = "SUPPORT_TUG"


class PolarIceClass(str, Enum):
    """IMO Polar Class and standard Baltic ice-strengthening tiers."""
    PC1 = "PC1"              # Year-round in all polar waters
    PC2 = "PC2"              # Year-round in moderate multi-year ice
    PC3 = "PC3"              # Year-round in second-year ice
    PC4 = "PC4"              # Year-round in thick first-year ice
    PC5 = "PC5"              # Year-round in medium first-year ice
    PC6 = "PC6"              # Summer/autumn in medium first-year ice
    PC7 = "PC7"              # Summer/autumn in thin first-year ice
    CLASS_1A_SUPER = "1A_SUPER"
    CLASS_1A = "1A"
    CLASS_1B = "1B"
    CLASS_1C = "1C"
    NON_ICE = "NON_ICE"      # Unstrengthened open-water hull


class OperationalConstraints(BaseModel):
    """Vessel-specific operational safety envelopes."""
    max_allowed_sic_pct: float = Field(default=80.0, ge=0.0, le=100.0, description="Maximum navigable SIC (%)")
    min_under_keel_clearance_m: float = Field(default=2.0, ge=0.0, le=1000.0, description="Minimum safe UKC (m)")
    max_wind_speed_knots: float = Field(default=45.0, ge=0.0, le=200.0, description="Maximum safe wind speed (kn)")
    max_wave_height_m: float = Field(default=5.0, ge=0.0, le=50.0, description="Maximum allowable wave height (m)")
    prohibit_night_in_ice: bool = Field(default=False, description="Whether night passage in pack ice is barred")


class VesselCharacteristics(BaseModel):
    """Comprehensive vessel profile parameterizing physical interaction with the polar environment."""
    vessel_id: str = Field(default="VESSEL-01", description="Unique vessel identifier")
    name: str = Field(default="Polar Explorer", description="Vessel display name")
    vessel_type: VesselType = Field(default=VesselType.RESEARCH_VESSEL)
    length_m: float = Field(default=105.0, ge=10.0, le=450.0, description="Length overall (m)")
    beam_m: float = Field(default=20.0, ge=3.0, le=80.0, description="Molded beam width (m)")
    draft_m: float = Field(default=8.0, ge=1.0, le=30.0, description="Operational vessel draft (m)")
    speed_knots: float = Field(default=12.0, ge=0.0, le=40.0, description="Speed over ground (kn)")
    heading_deg: float = Field(default=180.0, ge=0.0, le=360.0, description="True heading [0, 360)")
    ice_class: PolarIceClass = Field(default=PolarIceClass.PC5, description="Structural ice-strengthening capability")
    operational_constraints: OperationalConstraints = Field(default_factory=OperationalConstraints)


class RiskCategory(str, Enum):
    """Discrete operational risk tier aligned with IMO Polar Code POLARIS and SIH metrics."""
    LOW = "LOW"                      # Nominal open water / very light ice; standard watch
    MODERATE = "MODERATE"            # Manageable conditions within vessel ice capability
    HIGH = "HIGH"                    # Significant hazard; requires reduced speed and active ice searchlight
    CRITICAL = "CRITICAL"            # Severe besetting or hull damage hazard; escort or avoidance mandatory
    PROHIBITED = "PROHIBITED"        # Grounding hazard or ice conditions exceed structural capability


class RiskBreakdown(BaseModel):
    """Granular multi-factor risk decomposition."""
    sea_ice_risk: float = Field(ge=0.0, le=1.0, description="Sea ice concentration, thickness, and besetting hazard")
    iceberg_risk: float = Field(ge=0.0, le=1.0, description="Iceberg proximity, density, and CPA collision hazard")
    wind_risk: float = Field(ge=0.0, le=1.0, description="Atmospheric wind drag and superstructure icing risk")
    wave_risk: float = Field(ge=0.0, le=1.0, description="Swell height, slamming probability, and ship motion risk")
    current_leeway_risk: float = Field(ge=0.0, le=1.0, description="Hydrodynamic advection and leeway crab drift hazard")
    bathymetry_grounding_risk: float = Field(ge=0.0, le=1.0, description="Under-keel clearance and shoal grounding hazard")
    vessel_ice_capability_penalty: float = Field(ge=0.0, le=1.0, description="Penalty based on vessel polar class vs ice severity")
    speed_hazard_penalty: float = Field(ge=0.0, le=1.0, description="Risk escalation from excessive speed in heavy sea/ice")
    dominant_hazard: str = Field(description="Primary driver of current risk level")
    constraint_violations: List[str] = Field(default_factory=list, description="List of operational constraints breached")


class MLRiskPrediction(BaseModel):
    """Output of the Vessel-Aware ML Risk Engine.
    
    IMPORTANT:
    The model predicts environmental/navigation risk and operational cost.
    It does NOT predict AIS coordinates.
    """
    risk_score: float = Field(ge=0.0, le=1.0, description="Normalized composite risk score [0.0, 1.0]")
    risk_score_100: float = Field(ge=0.0, le=100.0, description="Risk scaled to [0, 100]")
    risk_category: RiskCategory = Field(description="Categorical risk classification")
    risk_breakdown: RiskBreakdown = Field(description="Sub-factor decomposition")
    
    # Confidence and Uncertainty Reporting (Anti-Fabrication)
    confidence: float = Field(ge=0.0, le=1.0, description="Calibrated non-fabricated confidence score [0.0, 1.0]")
    confidence_explanation: str = Field(description="Transparent explanation of confidence level")
    exposed_limitations: List[str] = Field(default_factory=list, description="Exposed data quality limitations & staleness cautions")
    is_degraded_confidence: bool = Field(description="True if live input confidence or freshness degraded output confidence")
    safe_to_proceed: bool = Field(description="True if risk is within acceptable operational boundaries")
    
    # ML Provenance Metadata
    model_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="ML architecture details, training version, and validation metrics"
    )
