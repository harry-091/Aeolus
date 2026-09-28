"""POLARNAV — Phase 13: Offline Historical Backtesting Models.

Schemas for:
1. Operational segment classification:
   - scientific stops
   - weather holds
   - port/station operations
   - maneuvering
   - data gaps
   - ice avoidance
2. Three-way route comparisons:
   - PolarNav route
   - Comparable historical AIS
   - Shortest-path baseline
3. Multi-dimensional evaluation:
   - Safety
   - Efficiency
   - Feasibility
   - ETA
   - Distance
   - High-SIC exposure
   - Iceberg clearance
   - Bathymetry violations
   - Fuel estimate
"""

from enum import Enum
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class OperationalSegmentType(str, Enum):
    """Categorization of operational activities within historical AIS voyages."""
    TRANSIT = "TRANSIT"
    SCIENTIFIC_STOP = "SCIENTIFIC_STOP"
    WEATHER_HOLD = "WEATHER_HOLD"
    PORT_STATION_OPERATIONS = "PORT_STATION_OPERATIONS"
    MANEUVERING = "MANEUVERING"
    DATA_GAP = "DATA_GAP"
    ICE_AVOIDANCE = "ICE_AVOIDANCE"


class OperationalSegment(BaseModel):
    """An identified contiguous phase within a voyage."""
    segment_id: str
    segment_type: OperationalSegmentType
    start_index: int
    end_index: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_hours: float
    distance_km: float
    mean_speed_knots: float
    mean_sic_pct: float
    description: str
    is_non_transit_delay: bool = False


class HistoricalVoyageMetadata(BaseModel):
    """Summary of a historical Antarctic voyage available for offline backtesting."""
    voyage_id: str
    vessel_name: str
    operator: str
    country: str
    source: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_distance_km: float
    observation_count: int
    data_source_mode: str = "OFFLINE_ONLY"


class RouteEvaluationMetrics(BaseModel):
    """Comprehensive 9-dimensional route metrics for safety and performance evaluation."""
    route_id: str
    route_name: str
    route_type: str  # "POLARNAV_BALANCED", "HISTORICAL_AIS", "SHORTEST_PATH_BASELINE"
    
    # 1. Distance
    distance_km: float
    distance_nm: float
    
    # 2. ETA & Duration
    gross_transit_hours: float
    net_transit_hours: float  # Excludes scientific stops & port operations
    nominal_speed_knots: float
    
    # 3. Safety
    composite_risk_score: float  # [0.0 - 1.0]
    risk_category: str  # LOW, MODERATE, ELEVATED, CRITICAL
    hazard_encounters_count: int
    imo_polaris_compliant: bool
    
    # 4. Efficiency
    speed_efficiency_ratio: float
    distance_efficiency_ratio: float
    
    # 5. Feasibility
    is_physically_feasible: bool
    land_crossings_count: int
    min_depth_m: float
    under_keel_clearance_m: float
    bathymetry_violations_count: int
    
    # 6. High-SIC Exposure
    mean_sic_pct: float
    max_sic_pct: float
    distance_in_ice_km: float  # SIC >= 15%
    distance_in_heavy_ice_km: float  # SIC >= 60%
    high_sic_exposure_pct: float
    
    # 7. Iceberg Clearance
    min_iceberg_cpa_km: float
    min_iceberg_cpa_nm: float
    iceberg_encounters_count: int
    
    # 8. Fuel Estimate
    estimated_fuel_metric_tonnes: float
    fuel_burn_rate_kg_km: float


class OperationalEventBreakdown(BaseModel):
    """Accounting of time spent in operational categories."""
    total_voyage_hours: float
    transit_hours: float
    scientific_stops_hours: float
    weather_holds_hours: float
    port_station_hours: float
    maneuvering_hours: float
    data_gaps_hours: float
    ice_avoidance_hours: float
    segments: List[OperationalSegment]


class ThreeWayRouteComparison(BaseModel):
    """Three-way benchmark comparing PolarNav against Historical AIS and Shortest Baseline."""
    polarnav_route: RouteEvaluationMetrics
    historical_ais_route: RouteEvaluationMetrics
    shortest_path_baseline: RouteEvaluationMetrics
    
    # Decoupled deltas
    distance_savings_vs_ais_km: float
    distance_savings_vs_ais_pct: float
    time_savings_vs_ais_net_hours: float
    risk_reduction_vs_ais_pct: float
    fuel_savings_vs_ais_tonnes: float


class HistoricalBacktestResult(BaseModel):
    """Complete offline backtest evaluation response."""
    status: str = "COMPLETED"
    voyage_id: str
    vessel_name: str
    vessel_ice_class: str
    departure_time_iso: str
    offline_only_enforced: bool = True
    anti_lookahead_verified: bool = True
    temporal_cutoff_time_iso: str
    
    # Critical Invariant
    operational_reference_statement: str = (
        "Historical AIS is an operational reference, not guaranteed optimal ground truth. "
        "Captains make tactical adaptations for marine science, resupply, and unmapped ice."
    )
    
    # Results
    comparison: ThreeWayRouteComparison
    operational_breakdown: OperationalEventBreakdown
    polarnav_waypoints: List[List[float]]
    historical_ais_waypoints: List[List[float]]
    shortest_path_waypoints: List[List[float]]
    environmental_snapshots_at_t0: Dict[str, Any]
