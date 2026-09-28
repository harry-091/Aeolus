"""Multi-objective navigation cost function for Phase 6.

Computes route quality using configurable weighted objectives:
  distance, risk, sea-ice exposure, iceberg exposure.

All weights are documented and configurable.
"""
import numpy as np
import xarray as xr
from math import radians, sin, cos, asin, sqrt


# Default optimization weights (sum to 1.0)
DEFAULT_WEIGHTS = {
    "distance": 0.30,
    "risk": 0.35,
    "sic": 0.20,
    "iceberg": 0.15,
}


def validate_weights(weights):
    """Validate and normalize optimization weights.

    Args:
        weights: dict of weight_name -> float.

    Returns:
        Normalized weights summing to 1.0.

    Raises:
        ValueError: if total weight <= 0.
    """
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Weights must sum to > 0")
    return {k: v / total for k, v in weights.items()}


def haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km between two points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


def compute_distance_cost(route_coords):
    """Compute total route distance in km."""
    total = 0.0
    for i in range(len(route_coords) - 1):
        total += haversine_km(
            route_coords[i][0], route_coords[i][1],
            route_coords[i + 1][0], route_coords[i + 1][1],
        )
    return total


def _sample_grid_values(route_coords, grid_lats, grid_lons, grid_values):
    """Sample grid values at nearest cell for each route coordinate."""
    vals = []
    for lat, lon in route_coords:
        i = int(np.argmin(np.abs(grid_lats - lat)))
        j = int(np.argmin(np.abs(grid_lons - lon)))
        i = min(max(i, 0), len(grid_lats) - 1)
        j = min(max(j, 0), len(grid_lons) - 1)
        vals.append(float(grid_values[i, j]))
    return np.array(vals)


def compute_risk_exposure(route_coords, risk_dataset):
    """Compute risk exposure metrics along a route.

    Args:
        route_coords: list of (lat, lon) tuples.
        risk_dataset: xr.Dataset with total_risk.

    Returns:
        dict with average_risk, maximum_risk, high_risk_fraction.
    """
    if not route_coords or len(route_coords) < 2:
        return {"average_risk": 0.0, "maximum_risk": 0.0, "high_risk_fraction": 0.0}

    risk_vals = _sample_grid_values(
        route_coords,
        risk_dataset.lat.values,
        risk_dataset.lon.values,
        risk_dataset["total_risk"].values,
    )
    return {
        "average_risk": round(float(np.mean(risk_vals)), 4),
        "maximum_risk": round(float(np.max(risk_vals)), 4),
        "high_risk_fraction": round(float(np.mean(risk_vals > 0.50)), 4),
    }


def compute_sic_exposure(route_coords, sic_dataset):
    """Compute sea-ice exposure metrics along a route.

    Args:
        route_coords: list of (lat, lon) tuples.
        sic_dataset: xr.Dataset with sic_current (0-1 concentration).

    Returns:
        dict with average_sic, max_sic, high_ice_fraction.
    """
    if not route_coords or sic_dataset is None:
        return {"average_sic": 0.0, "max_sic": 0.0, "high_ice_fraction": 0.0}

    sic_var = "sic_current" if "sic_current" in sic_dataset else list(sic_dataset.data_vars)[0]
    sic_vals = _sample_grid_values(
        route_coords,
        sic_dataset.lat.values,
        sic_dataset.lon.values,
        sic_dataset[sic_var].values,
    )
    return {
        "average_sic": round(float(np.mean(sic_vals)), 4),
        "max_sic": round(float(np.max(sic_vals)), 4),
        "high_ice_fraction": round(float(np.mean(sic_vals > 0.50)), 4),
    }


def compute_iceberg_exposure(route_coords, icebergs, predicted_icebergs=None):
    """Compute iceberg exposure metrics along a route.

    Args:
        route_coords: list of (lat, lon) tuples.
        icebergs: list of dicts with lat, lon, risk.
        predicted_icebergs: optional list of predicted future positions.

    Returns:
        dict with min_distance_km, avg_distance_km, high_risk_encounters.
    """
    if not route_coords or not icebergs:
        return {"min_distance_km": 9999.0, "avg_distance_km": 9999.0, "high_risk_encounters": 0}

    min_dist = float("inf")
    dists = []
    encounters = 0

    for ib in icebergs:
        ib_lat = ib.get("latitude", ib.get("lat", 0))
        ib_lon = ib.get("longitude", ib.get("lon", 0))
        ib_risk = ib.get("risk", "LOW")

        for lat, lon in route_coords:
            d = haversine_km(lat, lon, ib_lat, ib_lon)
            dists.append(d)
            if d < min_dist:
                min_dist = d
            if ib_risk in ("HIGH", "CRITICAL") and d < 50:
                encounters += 1

    # Check predicted positions too
    if predicted_icebergs:
        for pred in predicted_icebergs:
            if isinstance(pred, (list, tuple)) and len(pred) == 2:
                for lat, lon in route_coords:
                    d = haversine_km(lat, lon, pred[0], pred[1])
                    if d < min_dist:
                        min_dist = d

    return {
        "min_distance_km": round(min_dist, 1) if min_dist != float("inf") else 9999.0,
        "avg_distance_km": round(float(np.mean(dists)), 1) if dists else 9999.0,
        "high_risk_encounters": encounters,
    }


def compute_total_cost(distance_km, risk_metrics, sic_metrics, iceberg_metrics, weights=None):
    """Compute total route cost from component metrics.

    Args:
        distance_km: total distance.
        risk_metrics: dict from compute_risk_exposure.
        sic_metrics: dict from compute_sic_exposure.
        iceberg_metrics: dict from compute_iceberg_exposure.
        weights: optional custom weights dict.

    Returns:
        dict with total_cost, component_costs, weights_used.
    """
    w = validate_weights(weights or DEFAULT_WEIGHTS)

    # Normalize each component to [0, 1] range for fair weighting
    dist_cost = min(distance_km / 2000.0, 1.0)  # 2000km = max normalized
    risk_cost = risk_metrics.get("average_risk", 0.0)
    sic_cost = sic_metrics.get("average_sic", 0.0)
    ib_cost = min(iceberg_metrics.get("min_distance_km", 100) / 100.0, 1.0)
    ib_cost = 1.0 - ib_cost  # Closer = higher cost

    components = {
        "distance": round(dist_cost, 4),
        "risk": round(risk_cost, 4),
        "sic": round(sic_cost, 4),
        "iceberg": round(ib_cost, 4),
    }

    total = sum(w[k] * components[k] for k in w)

    return {
        "total_cost": round(total, 4),
        "component_costs": components,
        "weights_used": w,
    }


def compute_route_quality(distance_km, risk_metrics, sic_metrics, iceberg_metrics, weights=None):
    """Compute normalized route quality score (0=worst, 100=best).

    The score inverts the total cost: quality = (1 - total_cost) * 100.
    """
    cost = compute_total_cost(distance_km, risk_metrics, sic_metrics, iceberg_metrics, weights)
    quality = max(0.0, (1.0 - cost["total_cost"])) * 100.0
    return {
        "quality_score": round(quality, 1),
        "total_cost": cost["total_cost"],
        "component_costs": cost["component_costs"],
        "weights_used": cost["weights_used"],
    }
