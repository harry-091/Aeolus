"""Standardized Schemas for Phase 5: Historical Voyage Replay & Backtesting Engine.

Defines standardized data models for simulation steps, constraint audits, and comprehensive
12-metric comparative evaluations between actual AIS tracks and model-recommended corridors.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional


@dataclass
class SimulatedStep:
    """Telemetry recorded at a single discrete simulation time horizon."""
    step_index: int
    timestamp: str
    latitude: float
    longitude: float
    step_distance_km: float
    cumulative_distance_km: float
    speed_knots: float
    ml_risk_cost: float
    sic: float
    nearest_iceberg_dist_km: float
    depth_m: float
    is_reroute: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ViolationAudit:
    """Environmental and navigational hazard constraint violation audit."""
    dangerous_ice_distance_km: float = 0.0     # Distance traveled through SIC > 40%
    dangerous_ice_duration_hours: float = 0.0  # Time spent in dangerous pack ice
    iceberg_violations_count: int = 0          # Occurrences within tactical zone (< 15 km)
    bathymetric_violations_count: int = 0      # Occurrences in shallow waters (< 20 m)
    coast_land_violations_count: int = 0       # Occurrences intersecting land mask
    min_iceberg_clearance_km: float = 200.0    # Closest encounter to any tracked iceberg
    min_depth_m: float = 3500.0                # Minimum water depth encountered

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteComparisonMetrics:
    """The 12 Core Comparative Backtesting Metrics (Actual AIS vs. Recommended Corridor)."""
    # 1. Route length difference
    actual_length_km: float
    model_length_km: float
    length_difference_km: float                # actual - model (positive means model saved km)
    length_savings_pct: float                  # (actual - model) / actual * 100

    # 2. Route deviation
    route_deviation_mean_km: float             # Mean cross-track deviation

    # 3. Waypoint/geographic error
    waypoint_hausdorff_distance_km: float      # Maximum deviation between the two polylines
    waypoint_mean_nearest_error_km: float      # Average distance from model points to actual track

    # 4. ETA/transit time difference
    actual_duration_hours: float
    model_duration_hours: float
    time_difference_hours: float               # actual - model (positive means model saved hours)
    time_savings_pct: float

    # 5. Average SIC exposure
    actual_avg_sic_pct: float
    model_avg_sic_pct: float
    avg_sic_reduction_pct: float               # actual - model

    # 6. Maximum SIC exposure
    actual_max_sic_pct: float
    model_max_sic_pct: float

    # 7. Dangerous ice conditions (SIC > 40%)
    actual_dangerous_ice_km: float
    model_dangerous_ice_km: float
    dangerous_ice_reduction_km: float

    # 8. Iceberg/obstacle constraint violations (< 15 km)
    actual_iceberg_violations: int
    model_iceberg_violations: int

    # 9. Bathymetric/depth violations (< 20 m)
    actual_bathymetric_violations: int
    model_bathymetric_violations: int

    # 10. Coast/land constraint violations
    actual_land_violations: int
    model_land_violations: int

    # 11. Number of reroutes / simulated replans
    number_of_reroutes: int

    # 12. Computational runtime
    computational_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BacktestResult:
    """Standardized top-level backtest result object."""
    voyage_id: str
    vessel_name: str
    vessel_characteristics: Dict[str, Any]
    departure_location: List[float]            # [lat, lon]
    destination_location: List[float]          # [lat, lon]
    departure_time: str
    arrival_time_actual: Optional[str]
    arrival_time_model: str
    actual_track_points_count: int
    model_route_points_count: int
    metrics: RouteComparisonMetrics
    audit_actual: ViolationAudit
    audit_model: ViolationAudit
    simulated_steps: List[SimulatedStep]
    actual_path_coords: List[List[float]]      # [[lat, lon], ...]
    model_path_coords: List[List[float]]       # [[lat, lon], ...]
    notes: str = (
        "Anti-leakage verified: Simulation executed using only temporally antecedent "
        "environmental information without look-ahead to future actual AIS positions."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voyage_id": self.voyage_id,
            "vessel_name": self.vessel_name,
            "vessel_characteristics": self.vessel_characteristics,
            "departure_location": self.departure_location,
            "destination_location": self.destination_location,
            "departure_time": self.departure_time,
            "arrival_time_actual": self.arrival_time_actual,
            "arrival_time_model": self.arrival_time_model,
            "actual_track_points_count": self.actual_track_points_count,
            "model_route_points_count": self.model_route_points_count,
            "metrics": self.metrics.to_dict(),
            "audit_actual": self.audit_actual.to_dict(),
            "audit_model": self.audit_model.to_dict(),
            "simulated_steps": [s.to_dict() for s in self.simulated_steps],
            "actual_path_coords": self.actual_path_coords,
            "model_path_coords": self.model_path_coords,
            "geojson_features": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": f"Actual Track ({self.vessel_name})", "type": "actual_ais"},
                        "geometry": {"type": "LineString", "coordinates": [[c[1], c[0]] for c in self.actual_path_coords]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": f"PolarNav Model Route", "type": "model_route"},
                        "geometry": {"type": "LineString", "coordinates": [[c[1], c[0]] for c in self.model_path_coords]},
                    },
                ],
            },
            "notes": self.notes,
        }
