"""Navigation grid from Phase 4 risk output.

Converts the risk grid into a traversable graph for A* pathfinding.
"""
import numpy as np
import xarray as xr


def create_nav_grid(risk_dataset, max_risk=0.95):
    """Convert Phase 4 risk grid into a navigation grid.

    Args:
        risk_dataset: xr.Dataset from Phase 4 with total_risk.
        max_risk: risk threshold above which cells are blocked.

    Returns:
        xr.Dataset with nav_grid (0=blocked, 1=traversable),
        risk values, lat, lon.
    """
    lats = risk_dataset.lat.values
    lons = risk_dataset.lon.values
    total_risk = risk_dataset["total_risk"].values

    # Traversable = risk below threshold
    nav_grid = (total_risk < max_risk).astype(int)

    return xr.Dataset(
        {
            "nav_grid": (["lat", "lon"], nav_grid),
            "risk": (["lat", "lon"], total_risk),
        },
        coords={"lat": lats, "lon": lons},
        attrs={"max_risk_threshold": max_risk},
    )


def get_neighbors(i, j, n_lat, n_lon):
    """Get valid neighbor indices (4-connected grid).

    Args:
        i, j: current cell indices.
        n_lat, n_lon: grid dimensions.

    Returns:
        List of (ni, nj) neighbor tuples.
    """
    neighbors = []
    for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        ni, nj = i + di, j + dj
        if 0 <= ni < n_lat and 0 <= nj < n_lon:
            neighbors.append((ni, nj))
    return neighbors


def haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km."""
    from math import radians, sin, cos, asin, sqrt
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


def cell_distance(lat1, lon1, lat2, lon2):
    """Distance between two grid cells in km."""
    return haversine_km(lat1, lon1, lat2, lon2)
