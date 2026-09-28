"""Weather risk layer for Phase 4.

Optional layer. If weather data is available, converts wind speed
and other meteorological variables into navigation risk.

If weather data is unavailable, returns zeros with a flag.
"""
import numpy as np
import xarray as xr


def compute_weather_risk_layer(grid_lats, grid_lons, wind_speed=None):
    """Compute weather risk layer.

    Args:
        grid_lats: 1D grid latitudes.
        grid_lons: 1D grid longitudes.
        wind_speed: optional 2D array of wind speed (m/s).
            If None, returns zero risk (unavailable).

    Returns:
        xr.DataArray of weather risk (0-1).
        attrs contains 'available' flag.
    """
    if wind_speed is None:
        return xr.DataArray(
            np.zeros((len(grid_lats), len(grid_lons))),
            dims=["lat", "lon"],
            coords={"lat": grid_lats, "lon": grid_lons},
            attrs={
                "name": "weather_risk",
                "available": False,
                "description": "Weather risk - NO DATA AVAILABLE",
                "note": "Weather data not integrated in MVP. Risk set to zero.",
            },
        )

    ws = np.asarray(wind_speed, dtype=float)
    # Simple Beaufort-inspired risk: 0 m/s => 0, >=30 m/s => 1.0
    risk = np.clip(ws / 30.0, 0.0, 1.0)

    return xr.DataArray(
        risk,
        dims=["lat", "lon"],
        coords={"lat": grid_lats, "lon": grid_lons},
        attrs={
            "name": "weather_risk",
            "available": True,
            "description": "Navigation risk from wind speed",
            "units": "normalized 0-1",
        },
    )
