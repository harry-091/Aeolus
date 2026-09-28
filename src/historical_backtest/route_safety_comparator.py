"""Three-Way Route Safety & Efficiency Comparison Engine for Phase 6.

Evaluates and benchmarks:
A. Actual Historical AIS Route
B. ML + Routing Predicted Route (Balanced Corridor)
C. Safety-Optimized Route (Safest Corridor)

Computes decoupled Route Similarity, Environmental Safety, and Navigational Efficiency metrics.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from src.optimization.fuel_model import fuel_engine
from .safety_metrics_schema import (
    RouteProfileMetrics,
    PairwiseSimilarityMetrics,
    ThreeWayRouteComparison,
)
from .backtest_metrics import (
    haversine_km,
    compute_path_length_km,
    compute_hausdorff_and_deviations,
)


class RouteSafetyComparator:
    """Computes transparent, decoupled safety and efficiency profiles across route alternatives."""

    def __init__(
        self,
        sic_lookup_fn: Any,
        iceberg_dist_fn: Any,
        depth_lookup_fn: Any,
        is_land_fn: Any,
    ):
        self.sic_lookup_fn = sic_lookup_fn
        self.iceberg_dist_fn = iceberg_dist_fn
        self.depth_lookup_fn = depth_lookup_fn
        self.is_land_fn = is_land_fn

    def compute_route_profile(
        self,
        route_name: str,
        route_id: str,
        coords: List[List[float]],
        speed_knots: float = 14.0,
        polar_class: str = "PC3",
        reroute_count: int = 0,
        duration_hours_override: Optional[float] = None,
    ) -> RouteProfileMetrics:
        """Compute the independent Safety and Efficiency profile for a single route."""
        total_dist_km = compute_path_length_km(coords)
        speed_kmh = max(1.0, speed_knots * 1.852)

        if duration_hours_override is not None and duration_hours_override > 0:
            est_duration = duration_hours_override
        else:
            est_duration = total_dist_km / speed_kmh

        # Fuel consumption estimate (metric tonnes)
        try:
            fuel_res = fuel_engine.estimate_fuel(
                distance_km=total_dist_km,
                speed_knots=speed_knots,
                polar_class=polar_class,
            )
            fuel_tonnes = float(fuel_res.get("fuel_consumed_tonnes", fuel_res.get("total_fuel_tonnes", total_dist_km * 0.022)))
        except Exception:
            # Standard polar research vessel diesel consumption ~22 kg/km
            fuel_tonnes = total_dist_km * 0.022

        if not coords:
            return RouteProfileMetrics(
                route_name=route_name,
                route_id=route_id,
                total_distance_km=0.0,
                estimated_duration_hours=0.0,
                fuel_consumption_tonnes=0.0,
                reroute_checkpoints_count=0,
                mean_sic_pct=0.0,
                max_sic_pct=0.0,
                high_sic_distance_km=0.0,
                extreme_sic_distance_km=0.0,
                min_iceberg_clearance_km=200.0,
                iceberg_encounters_15km=0,
                iceberg_encounters_25km=0,
                min_bathymetry_depth_m=3500.0,
                bathymetry_violations_20m=0,
                bathymetry_cautions_50m=0,
                coastline_land_violations=0,
                composite_safety_index=1.0,
            )

        # Environmental Profiling
        sic_list: List[float] = []
        high_sic_km = 0.0
        extreme_sic_km = 0.0
        min_ib_clearance = 200.0
        ib_15km = 0
        ib_25km = 0
        min_depth = 3500.0
        bathy_20m = 0
        bathy_50m = 0
        land_viol = 0

        for i in range(len(coords)):
            lat, lon = float(coords[i][0]), float(coords[i][1])

            seg_d = 0.0
            if i > 0:
                seg_d = haversine_km(coords[i - 1][0], coords[i - 1][1], lat, lon)

            # 1. Sea ice
            sic = float(self.sic_lookup_fn(lat, lon) or 0.0)
            sic = max(0.0, min(1.0, sic))
            sic_list.append(sic)
            if sic > 0.40:
                high_sic_km += seg_d
            if sic > 0.70:
                extreme_sic_km += seg_d

            # 2. Icebergs
            ib_dist = float(self.iceberg_dist_fn(lat, lon) or 200.0)
            if ib_dist < min_ib_clearance:
                min_ib_clearance = ib_dist
            if ib_dist < 15.0:
                ib_15km += 1
            if ib_dist < 25.0:
                ib_25km += 1

            # 3. Bathymetry
            depth = float(self.depth_lookup_fn(lat, lon) or 3500.0)
            if depth < min_depth:
                min_depth = depth
            if depth < 20.0:
                bathy_20m += 1
            if depth < 50.0:
                bathy_50m += 1

            # 4. Land mask
            if self.is_land_fn(lat, lon):
                land_viol += 1

        mean_sic = float(np.mean(sic_list)) if sic_list else 0.0
        max_sic = float(np.max(sic_list)) if sic_list else 0.0

        # Composite Safety Index (CSI) [0.0 - 1.0]
        # Formula: 0.40*(1 - mean_SIC) + 0.30*min(1, ib_dist/50) + 0.15*min(1, depth/100) + 0.15*(1 - is_land)
        ib_factor = min(1.0, max(0.0, min_ib_clearance / 50.0))
        depth_factor = min(1.0, max(0.0, min_depth / 100.0))
        land_factor = 0.0 if land_viol > 0 else 1.0

        csi = (
            0.40 * (1.0 - mean_sic) +
            0.30 * ib_factor +
            0.15 * depth_factor +
            0.15 * land_factor
        )
        csi = max(0.0, min(1.0, csi))

        return RouteProfileMetrics(
            route_name=route_name,
            route_id=route_id,
            total_distance_km=round(total_dist_km, 1),
            estimated_duration_hours=round(est_duration, 1),
            fuel_consumption_tonnes=round(fuel_tonnes, 1),
            reroute_checkpoints_count=reroute_count,
            mean_sic_pct=round(mean_sic * 100.0, 1),
            max_sic_pct=round(max_sic * 100.0, 1),
            high_sic_distance_km=round(high_sic_km, 1),
            extreme_sic_distance_km=round(extreme_sic_km, 1),
            min_iceberg_clearance_km=round(min_ib_clearance, 1),
            iceberg_encounters_15km=ib_15km,
            iceberg_encounters_25km=ib_25km,
            min_bathymetry_depth_m=round(min_depth, 1),
            bathymetry_violations_20m=bathy_20m,
            bathymetry_cautions_50m=bathy_50m,
            coastline_land_violations=land_viol,
            composite_safety_index=round(csi, 4),
        )

    def compute_pairwise_similarity(
        self,
        pair_name: str,
        path_ref: List[List[float]],
        path_candidate: List[List[float]],
    ) -> PairwiseSimilarityMetrics:
        """Compute spatial and length similarity between two route trajectories."""
        len_ref = compute_path_length_km(path_ref)
        len_cand = compute_path_length_km(path_candidate)

        len_diff = len_ref - len_cand
        len_diff_pct = (len_diff / len_ref * 100.0) if len_ref > 0 else 0.0

        h_dist, mean_dev, nearest_err = compute_hausdorff_and_deviations(path_ref, path_candidate)

        return PairwiseSimilarityMetrics(
            comparison_pair=pair_name,
            hausdorff_distance_km=h_dist,
            mean_cross_track_deviation_km=mean_dev,
            mean_nearest_waypoint_error_km=nearest_err,
            length_difference_km=round(len_diff, 1),
            length_difference_pct=round(len_diff_pct, 1),
        )

    def compare_three_routes(
        self,
        voyage_id: str,
        vessel_name: str,
        departure_time: str,
        actual_path: List[List[float]],
        predicted_path: List[List[float]],
        safest_path: List[List[float]],
        speed_knots: float = 14.0,
        polar_class: str = "PC3",
        actual_duration_hours: Optional[float] = None,
    ) -> ThreeWayRouteComparison:
        """Execute full three-way comparison across Route A, Route B, and Route C."""
        # 1. Independent profiles
        prof_actual = self.compute_route_profile(
            route_name=f"Actual Track ({vessel_name})",
            route_id="route_actual",
            coords=actual_path,
            speed_knots=speed_knots,
            polar_class=polar_class,
            duration_hours_override=actual_duration_hours,
        )

        prof_pred = self.compute_route_profile(
            route_name="ML + Routing Predicted Route (Balanced)",
            route_id="route_predicted",
            coords=predicted_path,
            speed_knots=speed_knots,
            polar_class=polar_class,
        )

        prof_safest = self.compute_route_profile(
            route_name="Safety-Optimized Route (Safest)",
            route_id="route_safety_optimized",
            coords=safest_path,
            speed_knots=speed_knots,
            polar_class=polar_class,
        )

        # 2. Pairwise similarities
        sim_act_pred = self.compute_pairwise_similarity("Actual vs Predicted", actual_path, predicted_path)
        sim_act_safe = self.compute_pairwise_similarity("Actual vs Safety-Optimized", actual_path, safest_path)
        sim_pred_safe = self.compute_pairwise_similarity("Predicted vs Safety-Optimized", predicted_path, safest_path)

        dep_coords = actual_path[0] if actual_path else [0.0, 0.0]
        dest_coords = actual_path[-1] if actual_path else [0.0, 0.0]

        return ThreeWayRouteComparison(
            voyage_id=voyage_id,
            vessel_name=vessel_name,
            departure_time=departure_time,
            departure_coords=dep_coords,
            destination_coords=dest_coords,
            route_actual=prof_actual,
            route_predicted=prof_pred,
            route_safety_optimized=prof_safest,
            similarity_actual_vs_predicted=sim_act_pred,
            similarity_actual_vs_safest=sim_act_safe,
            similarity_predicted_vs_safest=sim_pred_safe,
            actual_path_coords=actual_path,
            predicted_path_coords=predicted_path,
            safety_optimized_path_coords=safest_path,
        )
