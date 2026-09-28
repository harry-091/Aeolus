"""Schema Definitions for Phase 6: Historical Route Safety Comparison.

Defines decoupled data structures for Route Similarity, Safety, and Efficiency across:
A. Actual Historical AIS Route
B. ML + Routing Predicted Route (Balanced Corridor)
C. Safety-Optimized Route (Safest Corridor)
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional


@dataclass
class RouteProfileMetrics:
    """Independent Safety & Efficiency profile for a single route corridor."""
    route_name: str                            # "Actual AIS Route", "Predicted Route (Balanced)", "Safety-Optimized Route"
    route_id: str                              # "route_actual", "route_predicted", "route_safest"

    # Efficiency Metrics
    total_distance_km: float                   # Total corridor length in km
    estimated_duration_hours: float            # Transit duration in hours
    fuel_consumption_tonnes: float             # Fuel consumed in metric tons
    reroute_checkpoints_count: int             # Dynamic replanning interventions

    # Safety Metrics - Sea Ice
    mean_sic_pct: float                        # Average sea ice concentration along track (%)
    max_sic_pct: float                         # Peak sea ice concentration encountered (%)
    high_sic_distance_km: float                # Distance through SIC > 40% (pack ice boundary)
    extreme_sic_distance_km: float             # Distance through SIC > 70% (heavy consolidated ice)

    # Safety Metrics - Obstacles & Topography
    min_iceberg_clearance_km: float            # Minimum distance to any tracked iceberg
    iceberg_encounters_15km: int               # Waypoints within tactical collision zone (< 15 km)
    iceberg_encounters_25km: int               # Waypoints within caution zone (< 25 km)
    min_bathymetry_depth_m: float              # Shallowest water depth encountered
    bathymetry_violations_20m: int             # Points in critical shallow waters (< 20 m)
    bathymetry_cautions_50m: int               # Points in shallow waters (< 50 m)
    coastline_land_violations: int             # Points intersecting land mask

    # Transparent Composite Safety Index (CSI) [0.0 - 1.0]
    # Formula: 0.40*(1 - SIC) + 0.30*min(1, ib_dist/50) + 0.15*min(1, depth/100) + 0.15*(1 - is_land)
    composite_safety_index: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PairwiseSimilarityMetrics:
    """Geographic similarity metrics between two distinct route corridors."""
    comparison_pair: str                       # e.g. "Actual vs Predicted", "Actual vs Safety-Optimized"
    hausdorff_distance_km: float               # Maximum divergence between polylines in km
    mean_cross_track_deviation_km: float       # Average orthogonal distance between trajectories
    mean_nearest_waypoint_error_km: float      # Mean distance from candidate points to reference
    length_difference_km: float                # Difference in corridor length (ref - candidate)
    length_difference_pct: float               # Percentage difference in distance

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThreeWayRouteComparison:
    """Standardized composite comparative evaluation across all three routes."""
    voyage_id: str
    vessel_name: str
    departure_time: str
    departure_coords: List[float]              # [lat, lon]
    destination_coords: List[float]            # [lat, lon]

    # Individual Route Profiles
    route_actual: RouteProfileMetrics
    route_predicted: RouteProfileMetrics
    route_safety_optimized: RouteProfileMetrics

    # Pairwise Similarity Metrics
    similarity_actual_vs_predicted: PairwiseSimilarityMetrics
    similarity_actual_vs_safest: PairwiseSimilarityMetrics
    similarity_predicted_vs_safest: PairwiseSimilarityMetrics

    # Scoring Methodology & Disclosures
    csi_formula_weights: Dict[str, float] = field(default_factory=lambda: {
        "sea_ice_avoidance_weight": 0.40,
        "iceberg_clearance_weight": 0.30,
        "bathymetric_depth_weight": 0.15,
        "land_mask_avoidance_weight": 0.15,
    })

    methodological_notes: Dict[str, str] = field(default_factory=lambda: {
        "ground_truth_disclaimer": (
            "The actual historical AIS route is NOT assumed to be ground-truth safe. Human navigators "
            "frequently accept local ice risks, encounter unpredictable weather, or execute unrecorded scientific missions."
        ),
        "no_fake_accuracy_disclaimer": (
            "No manufactured 'route accuracy percentage' is claimed. Spatial differences reflect alternative "
            "navigational strategies between human decision-making and multi-objective Pareto optimization."
        ),
        "operational_limitations": (
            "Actual AIS tracks include unrecorded oceanographic CTD stations and ice reconnaissance detours. "
            "Satellite SIC has a 25km grid resolution limit in narrow coastal sounds."
        ),
    })

    # Polylines for ECDIS / Map display
    actual_path_coords: List[List[float]] = field(default_factory=list)
    predicted_path_coords: List[List[float]] = field(default_factory=list)
    safety_optimized_path_coords: List[List[float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voyage_id": self.voyage_id,
            "vessel_name": self.vessel_name,
            "departure_time": self.departure_time,
            "departure_coords": self.departure_coords,
            "destination_coords": self.destination_coords,
            "route_actual": self.route_actual.to_dict(),
            "route_predicted": self.route_predicted.to_dict(),
            "route_safety_optimized": self.route_safety_optimized.to_dict(),
            "pairwise_similarities": {
                "actual_vs_predicted": self.similarity_actual_vs_predicted.to_dict(),
                "actual_vs_safest": self.similarity_actual_vs_safest.to_dict(),
                "predicted_vs_safest": self.similarity_predicted_vs_safest.to_dict(),
            },
            "csi_formula_weights": self.csi_formula_weights,
            "methodological_notes": self.methodological_notes,
            "geojson_features": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": f"Actual Track ({self.vessel_name})", "route_type": "actual"},
                        "geometry": {"type": "LineString", "coordinates": [[c[1], c[0]] for c in self.actual_path_coords]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Predicted Route (Balanced)", "route_type": "predicted"},
                        "geometry": {"type": "LineString", "coordinates": [[c[1], c[0]] for c in self.predicted_path_coords]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Safety-Optimized Route (Safest)", "route_type": "safest"},
                        "geometry": {"type": "LineString", "coordinates": [[c[1], c[0]] for c in self.safety_optimized_path_coords]},
                    },
                ],
            },
        }
