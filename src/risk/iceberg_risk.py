"""Iceberg risk layer for Phase 4.

Computes navigation risk based on distance to predicted iceberg
positions AND predicted future trajectory corridor.

Uses haversine distance (not raw degree differences).
"""
import json
import numpy as np
import xarray as xr
from math import radians, sin, cos, asin, sqrt


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate haversine distance in km between two points.

    Args:
        lat1, lon1: first point in degrees.
        lat2, lon2: second point in degrees.

    Returns:
        Distance in kilometers.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371.0 * c


def haversine_grid(grid_lats, grid_lons, point_lat, point_lon):
    """Calculate haversine distance from every grid cell to a point.

    Args:
        grid_lats: 1D array of grid latitudes.
        grid_lons: 1D array of grid longitudes.
        point_lat: target latitude.
        point_lon: target longitude.

    Returns:
        2D array of distances in km (n_lat x n_lon).
    """
    lat_rad = np.radians(grid_lats)
    lon_rad = np.radians(grid_lons)
    pt_lat_rad = radians(point_lat)
    pt_lon_rad = radians(point_lon)

    dlat = lat_rad - pt_lat_rad
    dlon = lon_rad - pt_lon_rad

    # Broadcast: (n_lat, 1) and (1, n_lon)
    a = np.sin(dlat[:, None] / 2) ** 2 + \
        np.cos(lat_rad[:, None]) * np.cos(pt_lat_rad) * \
        np.sin(dlon[None, :] / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    return 6371.0 * c


def load_config(path="configs/risk_config.json"):
    """Load risk configuration."""
    with open(path) as f:
        return json.load(f)


def iceberg_positions_to_risk(grid_lats, grid_lons, iceberg_lats, iceberg_lons, config=None):
    """Compute iceberg risk from current + predicted future positions.

    Uses nearest iceberg distance with configurable risk thresholds.

    Args:
        grid_lats: 1D array of grid latitudes.
        grid_lons: 1D array of grid longitudes.
        iceberg_lats: array of iceberg latitudes (current + predicted).
        iceberg_lons: array of iceberg longitudes (current + predicted).
        config: optional risk config.

    Returns:
        2D risk array (n_lat x n_lon), values 0-1.
    """
    if config is None:
        config = load_config()

    dist_cfg = config["iceberg_distance_km"]
    very_high_max = dist_cfg["very_high_max"]
    high_max = dist_cfg["high_max"]
    moderate_max = dist_cfg["moderate_max"]

    n_lat = len(grid_lats)
    n_lon = len(grid_lons)
    min_dist = np.full((n_lat, n_lon), np.inf)

    for lat_i, lon_i in zip(iceberg_lats, iceberg_lons):
        dist = haversine_grid(grid_lats, grid_lons, lat_i, lon_i)
        min_dist = np.minimum(min_dist, dist)

    risk = np.zeros_like(min_dist)
    mask_vh = min_dist <= very_high_max
    mask_h = (min_dist > very_high_max) & (min_dist <= high_max)
    mask_m = (min_dist > high_max) & (min_dist <= moderate_max)

    risk[mask_vh] = 0.75 + 0.25 * (1.0 - min_dist[mask_vh] / very_high_max)
    risk[mask_h] = 0.50 + 0.25 * (1.0 - (min_dist[mask_h] - very_high_max) / (high_max - very_high_max))
    risk[mask_m] = 0.25 + 0.25 * (1.0 - (min_dist[mask_m] - high_max) / (moderate_max - high_max))

    return risk


def compute_iceberg_risk_layer(grid_lats, grid_lons, current_positions, predicted_trajectory):
    """Compute iceberg risk layer including trajectory corridor.

    Args:
        grid_lats: 1D grid latitudes.
        grid_lons: 1D grid longitudes.
        current_positions: list of (lat, lon) current iceberg positions.
        predicted_trajectory: list of (lat, lon) predicted future positions.

    Returns:
        xr.DataArray of iceberg risk (0-1).
    """
    all_lats = [p[0] for p in current_positions]
    all_lons = [p[1] for p in current_positions]

    # Include trajectory corridor positions
    if predicted_trajectory:
        all_lats.extend([p[0] for p in predicted_trajectory])
        all_lons.extend([p[1] for p in predicted_trajectory])

    risk_data = iceberg_positions_to_risk(grid_lats, grid_lons, all_lats, all_lons)

    return xr.DataArray(
        risk_data,
        dims=["lat", "lon"],
        coords={"lat": grid_lats, "lon": grid_lons},
        attrs={
            "name": "iceberg_risk",
            "description": "Navigation risk from predicted iceberg positions and trajectory",
            "units": "normalized 0-1",
            "note": "Includes trajectory corridor for future predicted positions",
        },
    )
