"""Common spatial grid for Phase 4 risk engine.

All hazard layers must be aligned to this grid before combination.
"""
import numpy as np
import xarray as xr


def create_common_grid(
    lat_min=-80.0,
    lat_max=-50.0,
    n_lat=30,
    lon_min=-180.0,
    lon_max=180.0,
    n_lon=60,
):
    """Create a common Antarctic spatial grid.

    Returns:
        xr.Dataset with lat and lon coordinates.
    """
    lats = np.linspace(lat_min, lat_max, n_lat)
    lons = np.linspace(lon_min, lon_max, n_lon)

    ds = xr.Dataset(
        coords={
            "lat": ("lat", lats),
            "lon": ("lon", lons),
        },
        attrs={
            "description": "Common Antarctic navigation risk grid",
            "lat_range": f"{lat_min} to {lat_max}",
            "lon_range": f"{lon_min} to {lon_max}",
        },
    )
    return ds


def align_to_grid(data_array, common_lats, common_lons):
    """Regrid a data array to match the common grid using nearest-neighbor.

    Args:
        data_array: xr.DataArray with lat/lon coords.
        common_lats: target latitude array.
        common_lons: target longitude array.

    Returns:
        xr.DataArray regridded to common grid.
    """
    target = xr.Dataset(
        coords={
            "lat": ("lat", common_lats),
            "lon": ("lon", common_lons),
        }
    )
    regridded = data_array.interp(
        lat=common_lats,
        lon=common_lons,
        method="nearest",
    )
    return regridded
