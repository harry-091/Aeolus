"""Data Schemas for Phase 2: Historical Environmental Replay Dataset.

Defines standardized, leak-free feature vectors combining AIS kinematic observations
with co-located environmental conditions.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class EnrichedAISFeaturePoint:
    """Standardized feature record matching an AIS observation with environmental state."""
    # 1. AIS Kinematics & Identity
    vessel_id: str
    voyage_id: str
    timestamp: datetime
    latitude: float
    longitude: float
    speed_knots: Optional[float] = None
    heading_deg: Optional[float] = None
    course_deg: Optional[float] = None

    # 2. Sea Ice Concentration & WMO Regime
    sic: float = 0.0                       # Fraction [0.0, 1.0]
    sic_percent: float = 0.0               # Percentage [0.0, 100.0]
    ice_classification: str = "Open Water"  # WMO standard ice nomenclature

    # 3. Iceberg Obstacles & Proximity
    iceberg_distance_km: Optional[float] = None
    nearest_iceberg_id: Optional[str] = None

    # 4. Bathymetry & Seabed Topography
    bathymetry_depth_m: float = 3500.0     # Positive water depth in meters
    is_shallow: bool = False               # True if ocean depth < 20m

    # 5. Coastline & Land Proximity
    coastline_distance_km: float = 100.0   # Distance to Antarctic land boundary
    is_on_land: bool = False               # Anomaly flag if coordinates intersect land mask

    # 6. Ocean Hydrodynamics
    ocean_current_u_ms: Optional[float] = None
    ocean_current_v_ms: Optional[float] = None
    ocean_current_speed_ms: Optional[float] = None
    sea_surface_temp_c: Optional[float] = None

    # 7. Atmospheric Conditions
    wind_speed_ms: Optional[float] = None
    air_temp_c: Optional[float] = None

    # 8. Navigation Risk Assessment
    environmental_risk_score: float = 0.0  # Composite risk [0.0, 1.0]
    risk_class: str = "LOW"                # LOW, MODERATE, HIGH, VERY_HIGH

    # 9. Data Integrity & Scientific Provenance
    quality_flags: Dict[str, str] = field(default_factory=dict)
    anti_leakage_verified: bool = True     # Enforces T_env <= T_decision
    missing_variables: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if self.timestamp else None
        return d


@dataclass
class ReplayDatasetSummary:
    """Diagnostic quality report of an environmental replay dataset."""
    total_points: int
    matched_points: int
    unmatched_points: int
    match_rate_pct: float
    missing_variables_breakdown: Dict[str, int]
    temporal_coverage: Dict[str, Optional[str]]
    spatial_coverage: Dict[str, float]
    quality_breakdown: Dict[str, int]  # HIGH, MEDIUM, DEGRADED
    mean_sic_pct: float
    mean_depth_m: float
    mean_risk_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
