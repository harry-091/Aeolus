"""Ocean current risk layer for Phase 4.

Optional layer. Strong currents treated as increased navigation cost
ONLY as a prototype assumption. Documented as such.
"""
import numpy as np
import xarray as xr


def compute_ocean_risk_layer(grid_lats, grid_lons, current_u=None, current_v=None):
    """Compute ocean current risk layer.

    Args:
        grid_lats: 1D grid latitudes.
        grid_lons: 1D grid longitudes.
        current_u: optional 2D zonal current (m/s).
        current_v: optional 2D meridional current (m/s).

    Returns:
        xr.DataArray of ocean risk (0-1).
    """
    if current_u is None or current_v is None:
        return xr.DataArray(
            np.zeros((len(grid_lats), len(grid_lons))),
            dims=["lat", "lon"],
            coords={"lat": grid_lats, "lon": grid_lons},
            attrs={
                "name": "ocean_risk",
                "available": False,
                "description": "Ocean current risk - NO DATA AVAILABLE",
                "note": "Ocean current data not integrated in MVP. Risk set to zero.",
            },
        )

    speed = np.sqrt(np.asarray(current_u) ** 2 + np.asarray(current_v) ** 2)
    # Prototype: >2 m/s strong current => high risk
    risk = np.clip(speed / 2.0, 0.0, 1.0)

    return xr.DataArray(
        risk,
        dims=["lat", "lon"],
        coords={"lat": grid_lats, "lon": grid_lons},
        attrs={
            "name": "ocean_risk",
            "available": True,
            "description": "Navigation risk from ocean current speed",
            "units": "normalized 0-1",
        },
    )
