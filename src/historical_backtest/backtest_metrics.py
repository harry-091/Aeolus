"""Metric Calculation Engine for Historical Voyage Backtesting.

Computes the 12 quantitative metrics comparing actual human-navigated AIS tracks
against model-generated routes (Hausdorff deviation, SIC exposure, safety violations, length/time deltas).
"""

import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from scipy.spatial import cKDTree

from .backtest_schema import RouteComparisonMetrics, ViolationAudit


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers between two geographic coordinates."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def compute_path_length_km(coords: List[List[float]]) -> float:
    """Compute cumulative great-circle path distance in km."""
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(coords)):
        total += haversine_km(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1])
    return total


def _coords_to_ecef(coords: np.ndarray, r: float = 6371.0) -> np.ndarray:
    """Convert [lat, lon] array in degrees to 3D Cartesian Earth-Centered coordinates (km)."""
    lats = np.radians(coords[:, 0])
    lons = np.radians(coords[:, 1])
    x = r * np.cos(lats) * np.cos(lons)
    y = r * np.cos(lats) * np.sin(lons)
    z = r * np.sin(lats)
    return np.column_stack((x, y, z))


def _chord_to_arc_km(chord_dist: np.ndarray, r: float = 6371.0) -> np.ndarray:
    """Convert 3D chord Euclidean distance to great-circle arc distance in km."""
    sin_half = np.clip(chord_dist / (2.0 * r), 0.0, 1.0)
    return 2.0 * r * np.arcsin(sin_half)


def compute_hausdorff_and_deviations(
    path_a: List[List[float]],
    path_b: List[List[float]],
) -> Tuple[float, float, float]:
    """Compute Hausdorff distance and mean cross-track deviations between two polylines in km.
    
    Args:
        path_a: Actual path coordinates [[lat, lon], ...]
        path_b: Model path coordinates [[lat, lon], ...]
        
    Returns:
        Tuple of (hausdorff_dist_km, mean_deviation_km, mean_nearest_error_km)
    """
    arr_a = np.array(path_a, dtype=float)
    arr_b = np.array(path_b, dtype=float)

    if len(arr_a) == 0 or len(arr_b) == 0:
        return 0.0, 0.0, 0.0

    xyz_a = _coords_to_ecef(arr_a)
    xyz_b = _coords_to_ecef(arr_b)

    tree_a = cKDTree(xyz_a)
    tree_b = cKDTree(xyz_b)

    # 1. Distances from B to nearest point on A (model to actual)
    dists_b_to_a, _ = tree_a.query(xyz_b)
    arc_b_to_a = _chord_to_arc_km(dists_b_to_a)

    # 2. Distances from A to nearest point on B (actual to model)
    dists_a_to_b, _ = tree_b.query(xyz_a)
    arc_a_to_b = _chord_to_arc_km(dists_a_to_b)

    # Hausdorff distance: max(sup_{b in B} inf_{a in A} d, sup_{a in A} inf_{b in B} d)
    directed_b_to_a = float(np.max(arc_b_to_a))
    directed_a_to_b = float(np.max(arc_a_to_b))
    hausdorff_dist = max(directed_b_to_a, directed_a_to_b)

    mean_dev = float(np.mean(arc_b_to_a))
    mean_nearest = float(np.mean(arc_a_to_b))

    return round(hausdorff_dist, 2), round(mean_dev, 2), round(mean_nearest, 2)


def audit_path_environment(
    coords: List[List[float]],
    sic_lookup_fn: Any,
    iceberg_dist_fn: Any,
    depth_lookup_fn: Any,
    is_land_fn: Any,
    speed_knots: float = 14.0,
) -> Tuple[ViolationAudit, List[float]]:
    """Audit environmental exposures and constraint violations along a trajectory.
    
    Returns:
        Tuple of (ViolationAudit, sic_profile_list)
    """
    audit = ViolationAudit()
    if not coords:
        return audit, []

    sic_profile: List[float] = []
    min_ib = 200.0
    min_dep = 3500.0
    dangerous_ice_km = 0.0
    ib_violations = 0
    bathy_violations = 0
    land_violations = 0

    speed_kmh = max(1.0, speed_knots * 1.852)

    for i in range(len(coords)):
        lat, lon = coords[i][0], coords[i][1]

        # Segment distance associated with point
        seg_dist = 0.0
        if i > 0:
            seg_dist = haversine_km(coords[i - 1][0], coords[i - 1][1], lat, lon)

        # 1. Sea ice concentration
        sic = float(sic_lookup_fn(lat, lon) or 0.0)
        sic_profile.append(sic)
        if sic > 0.40:
            dangerous_ice_km += seg_dist

        # 2. Iceberg distance
        ib_dist = float(iceberg_dist_fn(lat, lon) or 200.0)
        if ib_dist < min_ib:
            min_ib = ib_dist
        if ib_dist < 15.0:
            ib_violations += 1

        # 3. Bathymetry depth
        depth = float(depth_lookup_fn(lat, lon) or 3500.0)
        if depth < min_dep:
            min_dep = depth
        if depth < 20.0:
            bathy_violations += 1

        # 4. Land mask intersection
        if is_land_fn(lat, lon):
            land_violations += 1

    audit.dangerous_ice_distance_km = round(dangerous_ice_km, 1)
    audit.dangerous_ice_duration_hours = round(dangerous_ice_km / speed_kmh, 1)
    audit.iceberg_violations_count = ib_violations
    audit.bathymetric_violations_count = bathy_violations
    audit.coast_land_violations_count = land_violations
    audit.min_iceberg_clearance_km = round(min_ib, 1)
    audit.min_depth_m = round(min_dep, 1)

    return audit, sic_profile


def compute_route_comparison_metrics(
    actual_path: List[List[float]],
    model_path: List[List[float]],
    actual_duration_hours: float,
    model_duration_hours: float,
    audit_actual: ViolationAudit,
    audit_model: ViolationAudit,
    sic_actual: List[float],
    sic_model: List[float],
    number_of_reroutes: int,
    computational_time_ms: float,
) -> RouteComparisonMetrics:
    """Assemble all 12 standardized route comparison metrics."""
    actual_len = compute_path_length_km(actual_path)
    model_len = compute_path_length_km(model_path)

    length_diff = actual_len - model_len
    length_savings_pct = (length_diff / actual_len * 100.0) if actual_len > 0 else 0.0

    hausdorff_dist, mean_dev, mean_nearest = compute_hausdorff_and_deviations(actual_path, model_path)

    time_diff = actual_duration_hours - model_duration_hours
    time_savings_pct = (time_diff / actual_duration_hours * 100.0) if actual_duration_hours > 0 else 0.0

    avg_sic_actual = float(np.mean(sic_actual) * 100.0) if sic_actual else 0.0
    avg_sic_model = float(np.mean(sic_model) * 100.0) if sic_model else 0.0
    max_sic_actual = float(np.max(sic_actual) * 100.0) if sic_actual else 0.0
    max_sic_model = float(np.max(sic_model) * 100.0) if sic_model else 0.0
    avg_sic_reduction = avg_sic_actual - avg_sic_model

    dangerous_ice_red = audit_actual.dangerous_ice_distance_km - audit_model.dangerous_ice_distance_km

    return RouteComparisonMetrics(
        actual_length_km=round(actual_len, 1),
        model_length_km=round(model_len, 1),
        length_difference_km=round(length_diff, 1),
        length_savings_pct=round(length_savings_pct, 1),
        route_deviation_mean_km=mean_dev,
        waypoint_hausdorff_distance_km=hausdorff_dist,
        waypoint_mean_nearest_error_km=mean_nearest,
        actual_duration_hours=round(actual_duration_hours, 1),
        model_duration_hours=round(model_duration_hours, 1),
        time_difference_hours=round(time_diff, 1),
        time_savings_pct=round(time_savings_pct, 1),
        actual_avg_sic_pct=round(avg_sic_actual, 1),
        model_avg_sic_pct=round(avg_sic_model, 1),
        avg_sic_reduction_pct=round(avg_sic_reduction, 1),
        actual_max_sic_pct=round(max_sic_actual, 1),
        model_max_sic_pct=round(max_sic_model, 1),
        actual_dangerous_ice_km=audit_actual.dangerous_ice_distance_km,
        model_dangerous_ice_km=audit_model.dangerous_ice_distance_km,
        dangerous_ice_reduction_km=round(dangerous_ice_red, 1),
        actual_iceberg_violations=audit_actual.iceberg_violations_count,
        model_iceberg_violations=audit_model.iceberg_violations_count,
        actual_bathymetric_violations=audit_actual.bathymetric_violations_count,
        model_bathymetric_violations=audit_model.bathymetric_violations_count,
        actual_land_violations=audit_actual.coast_land_violations_count,
        model_land_violations=audit_model.coast_land_violations_count,
        number_of_reroutes=number_of_reroutes,
        computational_time_ms=round(computational_time_ms, 1),
    )
