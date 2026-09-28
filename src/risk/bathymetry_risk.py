"""Bathymetry/depth risk layer for Phase 4.

Uses GEBCO or similar bathymetric data if available.
Shallow areas => high risk (hard constraint if below min vessel draft).
"""
import json
import numpy as np
import xarray as xr


def load_config(path="configs/risk_config.json"):
    """Load risk configuration."""
    with open(path) as f:
        return json.load(f)


def compute_bathymetry_risk_layer(grid_lats, grid_lons, depth=None, config=None):
    """Compute bathymetry risk layer.

    Args:
        grid_lats: 1D grid latitudes.
        grid_lons: 1D grid longitudes.
        depth: optional 2D depth array in meters (negative = below surface).
            If None, returns zero risk (unavailable).
        config: optional risk config.

    Returns:
        xr.DataArray of bathymetry risk (0-1).
    """
    if config is None:
        config = load_config()

    min_depth = config["bathymetry"]["min_safe_depth_m"]

    if depth is None:
        return xr.DataArray(
            np.zeros((len(grid_lats), len(grid_lons))),
            dims=["lat", "lon"],
            coords={"lat": grid_lats, "lon": grid_lons},
            attrs={
                "name": "bathymetry_risk",
                "available": False,
                "description": "Bathymetry risk - NO DATA AVAILABLE",
                "note": "Bathymetry data not integrated in MVP. Risk set to zero.",
            },
        )

    depth_arr = np.asarray(depth, dtype=float)
    # depth is negative below surface; convert to positive depth
    positive_depth = np.abs(depth_arr)

    # Risk: shallow => high, deep => low
    risk = np.where(
        positive_depth < min_depth,
        1.0,  # hard constraint: too shallow
        np.clip((min_depth * 2 - positive_depth) / (min_depth * 2), 0.0, 1.0),
    )

    return xr.DataArray(
        risk,
        dims=["lat", "lon"],
        coords={"lat": grid_lats, "lon": grid_lons},
        attrs={
            "name": "bathymetry_risk",
            "available": True,
            "description": "Navigation risk from water depth",
            "units": "normalized 0-1",
            "min_safe_depth_m": min_depth,
        },
    )
