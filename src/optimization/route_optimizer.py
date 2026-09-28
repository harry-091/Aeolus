"""Route optimizer for Phase 6 (DEPRECATED / PROTOTYPE).

NOTE: This module is retained for backwards-compatibility testing only.
The AUTHORITATIVE production routing pipeline is src.optimization.polar_routing_engine.PolarRoutingEngine,
which uses Antarctic Polar Stereographic EPSG:3031 projection, real Shapely coastlines, real satellite SIC,
0-48h BYU iceberg trajectories, 7 cost surfaces, and IMO POLARIS compliance.
"""
import time
import logging
import numpy as np
from src.navigation.grid import create_nav_grid
from src.navigation.pathfinding import a_star
from src.optimization.cost_function import (
    compute_distance_cost, compute_risk_exposure, compute_sic_exposure,
    compute_iceberg_exposure, compute_total_cost, compute_route_quality,
)

logger = logging.getLogger("polarnav.optimization")

# Alternative route profiles: different risk tolerances produce different routes
ROUTE_PROFILES = {
    "safest": {
        "risk_weight": 5.0,
        "max_risk": 0.60,
        "description": "Minimizes risk exposure at the cost of longer distance.",
    },
    "balanced": {
        "risk_weight": 2.0,
        "max_risk": 0.85,
        "description": "Balances safety and distance.",
    },
    "fastest": {
        "risk_weight": 0.5,
        "max_risk": 0.95,
        "description": "Minimizes distance while avoiding blocked cells.",
    },
}


def generate_candidate_routes(vessel, risk_dataset, sic_dataset=None,
                               icebergs=None, weights=None, profiles=None):
    """Generate candidate routes using different risk profiles.

    Args:
        vessel: dict with start, destination, risk_tolerance.
        risk_dataset: xr.Dataset from Phase 4.
        sic_dataset: optional xr.Dataset with SIC.
        icebergs: optional list of iceberg dicts.
        weights: optional optimization weights.
        profiles: optional dict of profile_name -> config overrides.

    Returns:
        dict with candidates (list), recommended, comparison.
    """
    t0 = time.time()
    profiles = profiles or ROUTE_PROFILES
    icebergs = icebergs or []

    candidates = []
    for name, profile in profiles.items():
        nav = create_nav_grid(risk_dataset, max_risk=profile["max_risk"])
        lats = nav.lat.values
        lons = nav.lon.values

        si = int(np.argmin(np.abs(lats - vessel["start"]["lat"])))
        sj = int(np.argmin(np.abs(lons - vessel["start"]["lon"])))
        gi = int(np.argmin(np.abs(lats - vessel["destination"]["lat"])))
        gj = int(np.argmin(np.abs(lons - vessel["destination"]["lon"])))

        result = a_star(nav, (si, sj), (gi, gj), risk_weight=profile["risk_weight"])

        if not result.get("found"):
            logger.warning(f"Profile '{name}': no route found - {result.get('reason')}")
            continue

        coords = result["route_coords"]
        distance = result["total_distance_km"]

        # Compute all exposure metrics
        risk_m = compute_risk_exposure(coords, risk_dataset)
        sic_m = compute_sic_exposure(coords, sic_dataset) if sic_dataset else {"average_sic": 0, "max_sic": 0, "high_ice_fraction": 0}

        # Collect predicted iceberg positions for exposure calc
        pred_positions = []
        for ib in icebergs:
            for pt in ib.get("predictedTrajectory", []):
                if isinstance(pt, (list, tuple)) and len(pt) == 2:
                    pred_positions.append(pt)
        ib_m = compute_iceberg_exposure(coords, icebergs, pred_positions)

        quality = compute_route_quality(distance, risk_m, sic_m, ib_m, weights)

        # Travel time (if speed available)
        speed_kn = vessel.get("cruising_speed_kn", 12)
        dist_nm = distance * 0.539957
        travel_time_hours = round(dist_nm / speed_kn, 1) if speed_kn else None

        # Relative fuel cost: proportional to distance * (1 + avg_risk * 0.3)
        relative_fuel = round(distance * (1.0 + risk_m["average_risk"] * 0.3), 1)

        candidate = {
            "route_id": name,
            "profile": profile["description"],
            "coordinates": coords,
            "distance_km": round(distance, 1),
            "travel_time_hours": travel_time_hours,
            "risk_weight": profile["risk_weight"],
            "max_risk_threshold": profile["max_risk"],
            "average_risk": risk_m["average_risk"],
            "maximum_risk": risk_m["maximum_risk"],
            "high_risk_fraction": risk_m["high_risk_fraction"],
            "sea_ice_exposure": sic_m,
            "iceberg_exposure": ib_m,
            "relative_fuel_cost": relative_fuel,
            "total_cost": quality["total_cost"],
            "quality_score": quality["quality_score"],
            "component_costs": quality["component_costs"],
            "waypoints": len(coords),
        }
        candidates.append(candidate)

    # Select recommended route (highest quality score)
    recommended = None
    if candidates:
        recommended = max(candidates, key=lambda c: c["quality_score"])

    elapsed = round(time.time() - t0, 3)
    logger.info(f"Generated {len(candidates)} candidates in {elapsed}s")

    return {
        "candidates": candidates,
        "recommended": recommended,
        "profiles_used": list(profiles.keys()),
        "computation_time_ms": round(elapsed * 1000, 1),
    }


def generate_baseline_route(vessel, risk_dataset):
    """Generate a baseline route (shortest feasible path).

    This serves as the comparison baseline for optimization.
    Uses low risk weight to produce a near-direct path.
    """
    nav = create_nav_grid(risk_dataset, max_risk=0.99)
    lats = nav.lat.values
    lons = nav.lon.values

    si = int(np.argmin(np.abs(lats - vessel["start"]["lat"])))
    sj = int(np.argmin(np.abs(lons - vessel["start"]["lon"])))
    gi = int(np.argmin(np.abs(lats - vessel["destination"]["lat"])))
    gj = int(np.argmin(np.abs(lons - vessel["destination"]["lon"])))

    result = a_star(nav, (si, sj), (gi, gj), risk_weight=0.1)

    if not result.get("found"):
        return {"found": False, "reason": result.get("reason", "No baseline route")}

    coords = result["route_coords"]
    distance = result["total_distance_km"]

    speed_kn = vessel.get("cruising_speed_kn", 12)
    dist_nm = distance * 0.539957
    travel_time_hours = round(dist_nm / speed_kn, 1) if speed_kn else None

    return {
        "found": True,
        "route_id": "baseline",
        "coordinates": coords,
        "distance_km": round(distance, 1),
        "travel_time_hours": travel_time_hours,
        "total_risk_cost": result.get("total_risk_cost", 0),
        "waypoints": len(coords),
    }


def compare_routes(optimized, baseline):
    """Compare optimized route vs baseline.

    Returns dict with improvement metrics.
    """
    if not optimized.get("found") and not baseline.get("found"):
        return {"comparison_available": False, "reason": "Neither route found"}

    opt_dist = optimized.get("distance_km", 0)
    base_dist = baseline.get("distance_km", 0)

    opt_risk = optimized.get("average_risk", 0)
    base_risk = baseline.get("total_risk_cost", 0)

    dist_diff = opt_dist - base_dist
    dist_pct = (dist_diff / base_dist * 100) if base_dist > 0 else 0

    return {
        "comparison_available": True,
        "optimized_distance_km": opt_dist,
        "baseline_distance_km": base_dist,
        "distance_difference_km": round(dist_diff, 1),
        "distance_change_percent": round(dist_pct, 1),
        "optimized_risk": opt_risk,
        "baseline_risk": round(base_risk, 4),
        "explanation": (
            f"Optimized route is {abs(round(dist_pct, 1))}% "
            f"{'longer' if dist_pct > 0 else 'shorter'} than baseline "
            f"with {'reduced' if opt_risk < base_risk else 'increased'} risk exposure."
        ),
    }
