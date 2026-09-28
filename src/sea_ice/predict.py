"""
Sea-Ice Concentration Prediction Module.

Loads saved model and generates spatial forecasts.
Must NOT depend on notebook variables.
"""
import json
import numpy as np
import pandas as pd
import xarray as xr
import joblib
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


def load_model(model_name="sea_ice_model.joblib"):
    """Load saved model and feature config."""
    model_path = MODELS_DIR / model_name
    config_path = MODELS_DIR / "sea_ice_feature_config.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    model = joblib.load(model_path)
    with open(config_path) as f:
        config = json.load(f)

    return model, config


def predict_single(model, features_dict):
    """Predict SIC for a single grid cell."""
    feature_cols = ["lat", "lon", "month", "day_of_year",
                    "sic_lag_1", "sic_lag_2", "sic_lag_3", "sic_mean_3month"]
    X = np.array([[features_dict[col] for col in feature_cols]])
    pred = float(model.predict(X)[0])
    return np.clip(pred, 0.0, 1.0)


def predict_grid(model, ds, time_idx=-1):
    """
    Generate forecast SIC grid using vectorized prediction.

    Much faster than cell-by-cell loop.
    """
    sic = ds["sic"]
    lats = sic.lat.values
    lons = sic.lon.values
    times = pd.to_datetime(sic.time.values)

    current_time = times[time_idx]
    current_sic = sic.values[time_idx]

    lag1 = sic.values[time_idx - 1] if time_idx >= 1 else current_sic
    lag2 = sic.values[time_idx - 2] if time_idx >= 2 else current_sic
    lag3 = sic.values[time_idx - 3] if time_idx >= 3 else current_sic

    n_lat, n_lon = len(lats), len(lons)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    # Build feature matrix (vectorized)
    features = np.column_stack([
        lat_grid.ravel(),
        lon_grid.ravel(),
        np.full(n_lat * n_lon, current_time.month),
        np.full(n_lat * n_lon, current_time.timetuple().tm_yday),
        lag1.ravel(),
        lag2.ravel(),
        lag3.ravel(),
        np.mean([lag1, lag2, lag3], axis=0).ravel(),
    ])

    # Predict all cells at once
    preds = model.predict(features)
    forecast_sic = np.clip(preds, 0, 1).reshape(n_lat, n_lon)

    forecast_time = current_time + pd.DateOffset(months=1)

    ds_out = xr.Dataset(
        {
            "sic_current": (["lat", "lon"], current_sic),
            "sic_forecast": (["lat", "lon"], forecast_sic),
        },
        coords={"lat": lats, "lon": lons},
        attrs={
            "current_date": str(current_time.date()),
            "forecast_date": str(forecast_time.date()),
            "forecast_horizon": "1 month",
            "model_type": type(model).__name__,
        },
    )

    return ds_out


def compute_risk_layer(sic_forecast):
    """
    Convert forecast SIC to navigation risk categories.

    Thresholds (documented operational prototype):
    - LOW: SIC < 0.15 (open water)
    - MODERATE: 0.15 <= SIC < 0.50 (some ice, navigable with caution)
    - HIGH: 0.50 <= SIC < 0.80 (significant ice, difficult navigation)
    - VERY HIGH: SIC >= 0.80 (heavy ice, navigation dangerous)

    Reference:
    - 15% threshold is standard for sea-ice extent definition (NSIDC)
    - Higher thresholds are operational estimates for MVP
    """
    sic = sic_forecast["sic_forecast"]

    risk = np.zeros_like(sic.values, dtype=int)
    risk[sic.values >= 0.15] = 1  # MODERATE
    risk[sic.values >= 0.50] = 2  # HIGH
    risk[sic.values >= 0.80] = 3  # VERY HIGH

    ds = xr.Dataset(
        {"risk": (["lat", "lon"], risk)},
        coords={"lat": sic.lat, "lon": sic.lon},
        attrs={
            "risk_categories": "0=LOW, 1=MODERATE, 2=HIGH, 3=VERY_HIGH",
            "thresholds": "LOW<0.15, MODERATE<0.50, HIGH<0.80, VERY_HIGH>=0.80",
            "note": "Operational prototype thresholds for SIH MVP",
        },
    )

    return ds
