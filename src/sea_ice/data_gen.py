"""
Realistic Spatial Sea-Ice Concentration Data Generator

Generates synthetic but scientifically-grounded Antarctic SIC data
based on documented seasonal patterns from NSIDC observations.

IMPORTANT: This is synthetic data for MVP prototyping.
The ML pipeline works identically with real spatial SIC data.

Reference patterns from NSIDC:
- Maximum extent: ~18-19 M km2 in September
- Minimum extent: ~2-3 M km2 in February
- SIC decreases from coast outward
- Strong seasonal cycle

Output: NetCDF with lat, lon, time, sic variables.
"""
import numpy as np
import xarray as xr
from pathlib import Path


def generate_spatial_sic(
    n_months=24,
    lat_min=-80.0,
    lat_max=-50.0,
    lon_min=-180.0,
    lon_max=180.0,
    n_lat=30,
    n_lon=60,
    output_path=None,
    seed=42,
):
    """
    Generate realistic spatial Antarctic SIC data.

    Parameters
    ----------
    n_months : int
        Number of monthly time steps.
    lat_min, lat_max : float
        Latitude bounds (degrees).
    lon_min, lon_max : float
        Longitude bounds (degrees).
    n_lat, n_lon : int
        Grid dimensions.
    output_path : str or Path, optional
        Where to save NetCDF.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    xarray.Dataset
        Dataset with variables: sic, lat, lon, time.
    """
    np.random.seed(seed)

    # Create coordinate arrays
    lats = np.linspace(lat_min, lat_max, n_lat)
    lons = np.linspace(lon_min, lon_max, n_lon)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    # Create time coordinates (monthly)
    import pandas as pd
    start_date = "2020-01-01"
    dates = pd.date_range(start=start_date, periods=n_months, freq="MS")

    # Antarctic seasonal SIC pattern (fraction 0-1)
    # Peak: September (~0.85), Minimum: February (~0.15)
    month_sic_base = {
        1: 0.25, 2: 0.15, 3: 0.18, 4: 0.30,
        5: 0.45, 6: 0.60, 7: 0.72, 8: 0.82,
        9: 0.88, 10: 0.78, 11: 0.55, 12: 0.35,
    }

    sic_data = np.zeros((n_months, n_lat, n_lon))

    for t, date in enumerate(dates):
        month = date.month
        base_sic = month_sic_base[month]

        # Latitude gradient: higher SIC near coast (more negative lat)
        lat_factor = (lat_grid - lat_min) / (lat_max - lat_min)
        lat_effect = 1.0 - 0.6 * lat_factor

        # Longitude variation (Weddell Sea / Ross Sea sectors have more ice)
        lon_effect = 1.0 + 0.15 * np.cos(np.radians(lon_grid - 30))

        # Combine
        sic = base_sic * lat_effect * lon_effect

        # Add realistic noise
        noise = np.random.normal(0, 0.03, (n_lat, n_lon))
        sic = sic + noise

        # Clip to valid range
        sic = np.clip(sic, 0.0, 1.0)

        # Apply land mask (set very low values near grid edges to 0)
        sic[0, :] = 0.0  # southernmost row
        sic[-1, :] = 0.0  # northernmost row

        sic_data[t] = sic

    # Create xarray Dataset
    ds = xr.Dataset(
        {
            "sic": (["time", "lat", "lon"], sic_data),
        },
        coords={
            "time": dates,
            "lat": lats,
            "lon": lons,
        },
        attrs={
            "title": "Antarctic Sea-Ice Concentration (Synthetic MVP)",
            "source": "Generated from NSIDC seasonal patterns",
            "reference": "NSIDC Sea Ice Index G02135 seasonal patterns",
            "units": "fraction (0-1)",
            "note": "Synthetic data for SIH Phase 2 MVP. Replace with real CDR/G02202 data.",
            "spatial_resolution": f"{(lat_max-lat_min)/n_lat:.1f} x {(lon_max-lon_min)/n_lon:.1f} degrees",
            "temporal_resolution": "monthly",
        },
    )

    # Save
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(output_path)
        print(f"  Saved: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")

    return ds


if __name__ == "__main__":
    ds = generate_spatial_sic(
        n_months=24,
        output_path="data/raw/sea_ice/spatial_sic_monthly.nc",
    )
    print(f"\nDataset: {ds}")
    print(f"SIC range: {float(ds.sic.min()):.3f} to {float(ds.sic.max()):.3f}")
