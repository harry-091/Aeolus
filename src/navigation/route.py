"""Multi-vessel route generation, validation, and comparison."""
import numpy as np
from src.navigation.grid import create_nav_grid
from src.navigation.pathfinding import a_star


def find_route(vessel, risk_dataset, risk_weight=2.0, max_risk=0.95):
    """Find a route for a single vessel using A*.

    Args:
        vessel: dict with start, destination, risk_tolerance.
        risk_dataset: xr.Dataset from Phase 4.
        risk_weight: weight of risk in path cost.
        max_risk: risk threshold for blocking cells.

    Returns:
        dict with route details.
    """
    nav = create_nav_grid(risk_dataset, max_risk=max_risk)
    lats = nav.lat.values
    lons = nav.lon.values

    # Find nearest grid cells for start and destination
    si = int(np.argmin(np.abs(lats - vessel["start"]["lat"])))
    sj = int(np.argmin(np.abs(lons - vessel["start"]["lon"])))
    gi = int(np.argmin(np.abs(lats - vessel["destination"]["lat"])))
    gj = int(np.argmin(np.abs(lons - vessel["destination"]["lon"])))

    # Use vessel risk_tolerance if available
    tol = vessel.get("risk_tolerance", 0.7)
    effective_weight = risk_weight * (2.0 - tol)

    result = a_star(nav, (si, sj), (gi, gj), risk_weight=effective_weight)

    # Calculate ETA if speed available
    eta_hours = None
    speed = vessel.get("cruising_speed_kn")
    if speed and result.get("found"):
        dist_nm = result["total_distance_km"] * 0.539957
        eta_hours = round(dist_nm / speed, 1)

    return {
        "vessel_id": vessel["id"],
        "vessel_name": vessel["name"],
        "vessel_type": vessel["type"],
        "start": vessel["start"],
        "destination": vessel["destination"],
        "found": result.get("found", False),
        "reason": result.get("reason", ""),
        "route_coords": result.get("route_coords", []),
        "distance_km": result.get("total_distance_km", 0),
        "risk_cost": result.get("total_risk_cost", 0),
        "waypoints": result.get("waypoints", 0),
        "eta_hours": eta_hours,
    }


def find_routes(vessels, risk_dataset, risk_weight=2.0, max_risk=0.95):
    """Find routes for all vessels.

    Args:
        vessels: list of vessel dicts.
        risk_dataset: xr.Dataset from Phase 4.
        risk_weight: base risk weight.
        max_risk: risk threshold.

    Returns:
        list of route result dicts.
    """
    return [find_route(v, risk_dataset, risk_weight, max_risk) for v in vessels]


def validate_route(route_result):
    """Validate a single route result."""
    checks = {}
    checks["route_found"] = route_result.get("found", False)
    if not checks["route_found"]:
        return {"valid": False, "checks": checks, "message": route_result.get("reason", "No route")}

    coords = route_result.get("route_coords", [])
    checks["has_coords"] = len(coords) > 0
    checks["min_waypoints"] = route_result.get("waypoints", 0) >= 2
    checks["distance_positive"] = route_result.get("distance_km", 0) > 0
    checks["risk_finite"] = np.isfinite(route_result.get("risk_cost", 0))

    if coords:
        lats = [c[0] for c in coords]
        lons = [c[1] for c in coords]
        checks["valid_lats"] = all(-90 <= lat <= 90 for lat in lats)
        checks["valid_lons"] = all(-180 <= lon <= 180 for lon in lons)
        checks["start_end_different"] = coords[0] != coords[-1]

    all_pass = all(checks.values())
    return {"valid": all_pass, "checks": checks, "message": "Route valid" if all_pass else "Route invalid"}


def route_comparison(routes):
    """Generate a comparison table for multiple routes."""
    rows = []
    for r in routes:
        rows.append({
            "vessel": r["vessel_name"],
            "type": r["vessel_type"],
            "distance_km": r["distance_km"],
            "risk_cost": r["risk_cost"],
            "waypoints": r["waypoints"],
            "status": "FOUND" if r["found"] else "NO ROUTE",
            "eta_hours": r.get("eta_hours"),
        })
    return rows


def route_summary(route_result):
    """Generate a human-readable route summary."""
    if not route_result.get("found"):
        return f"No route: {route_result.get('reason', 'unknown')}"

    lines = [
        f"VESSEL: {route_result['vessel_name']} ({route_result['vessel_type']})",
        f"  Start:      {route_result['start']['lat']}, {route_result['start']['lon']}",
        f"  Dest:       {route_result['destination']['lat']}, {route_result['destination']['lon']}",
        f"  Distance:   {route_result['distance_km']:.1f} km",
        f"  Risk Cost:  {route_result['risk_cost']:.4f}",
        f"  Waypoints:  {route_result['waypoints']}",
    ]
    if route_result.get("eta_hours"):
        lines.append(f"  ETA:        {route_result['eta_hours']:.1f} hours")
    else:
        lines.append("  ETA:        NOT AVAILABLE")
    return "\n".join(lines)
