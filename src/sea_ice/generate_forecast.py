"""Generate forecast SIC and save as NetCDF for visualization.

Uses the trained model to predict next-timestep SIC from the last known state.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import xarray as xr
import joblib
import json


def generate_forecast():
    """Generate 1-step forecast SIC and save to NetCDF."""
    # Load model and config
    model = joblib.load("models/sea_ice_model.joblib")
    with open("models/sea_ice_feature_config.json") as f:
        config = json.load(f)

    # Load SIC data
    sic_ds = xr.open_dataset("data/raw/sea_ice/spatial_sic_monthly.nc")
    lats = sic_ds.lat.values
    lons = sic_ds.lon.values
    n_lat = len(lats)
    n_lon = len(lons)

    # Use last 3 timesteps for lag features
    sic_values = sic_ds["sic"].values  # (time, lat, lon)
    sic_ds.close()

    # Current: last timestep
    current_sic = sic_values[-1]
    # Lags
    lag1 = sic_values[-2]
    lag2 = sic_values[-3]
    lag3 = sic_values[-4] if len(sic_values) > 3 else sic_values[-3]
    sic_mean_3 = (lag1 + lag2 + lag3) / 3.0

    # Build features for each grid cell
    features = []
    coords = []
    for i in range(n_lat):
        for j in range(n_lon):
            features.append([
                lats[i], lons[j],
                1,  # month (Jan=forecast)
                15,  # day_of_year
                lag1[i, j],
                lag2[i, j],
                lag3[i, j],
                sic_mean_3[i, j],
            ])
            coords.append((i, j))

    X = np.array(features)
    predictions = model.predict(X)

    # Reshape to grid
    forecast_sic = np.zeros((n_lat, n_lon))
    for idx, (i, j) in enumerate(coords):
        forecast_sic[i, j] = np.clip(predictions[idx], 0.0, 1.0)

    # Save as NetCDF
    forecast_ds = xr.Dataset(
        {
            "sic": (["lat", "lon"], forecast_sic),
            "sic_current": (["lat", "lon"], current_sic),
        },
        coords={
            "lat": lats,
            "lon": lons,
        },
        attrs={
            "description": "Phase 2 SIC forecast (1-step ahead)",
            "current_time": "2021-12",
            "forecast_time": "2022-01",
            "model": "RandomForestRegressor",
            "note": "Prototype forecast for SIH demonstration",
        },
    )

    outpath = "data/processed/sic_forecast.nc"
    forecast_ds.to_netcdf(outpath)
    print(f"Forecast saved: {outpath}")
    print(f"Forecast SIC range: {forecast_sic.min():.3f} - {forecast_sic.max():.3f}")
    print(f"Current SIC range: {current_sic.min():.3f} - {current_sic.max():.3f}")

    return forecast_ds


if __name__ == "__main__":
    generate_forecast()
