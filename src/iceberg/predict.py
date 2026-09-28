"""
Iceberg Trajectory Prediction Module.

Loads saved model and generates future position predictions.
Must NOT depend on notebook variables.
"""
import json
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


def load_model(model_name="iceberg_trajectory_model.joblib"):
    """Load saved model and config."""
    model_path = MODELS_DIR / model_name
    config_path = MODELS_DIR / "iceberg_feature_config.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    model = joblib.load(model_path)
    with open(config_path) as f:
        config = json.load(f)
    return model, config


def predict_next_position(model, current_state):
    """
    Predict next iceberg position from current state.

    Parameters
    ----------
    model : trained model
    current_state : dict with keys: latitude, longitude, speed_kmh,
                    bearing_deg, dt_hours, major_axis_km, minor_axis_km,
                    month, day_of_year

    Returns
    -------
    dict with keys: pred_lat, pred_lon
    """
    feature_cols = [
        "latitude", "longitude", "speed_kmh", "bearing_deg",
        "dt_hours", "major_axis_km", "minor_axis_km",
        "month", "day_of_year",
    ]
    X = np.array([[current_state[col] for col in feature_cols]])
    displacement = model.predict(X)[0]  # [delta_lat, delta_lon]

    return {
        "pred_lat": current_state["latitude"] + displacement[0],
        "pred_lon": current_state["longitude"] + displacement[1],
    }


def predict_trajectory(model, track_df, n_steps=5, dt_hours=24):
    """
    Generate multi-step future trajectory.

    Parameters
    ----------
    model : trained model
    track_df : pd.DataFrame with at least one row of current state
    n_steps : int
        Number of future time steps to predict.
    dt_hours : float
        Time step in hours.

    Returns
    -------
    pd.DataFrame
        Predicted positions: timestamp, latitude, longitude, step
    """
    last = track_df.iloc[-1].copy()
    predictions = []

    for step in range(1, n_steps + 1):
        # Build features from current state
        current = {
            "latitude": last["latitude"],
            "longitude": last["longitude"],
            "speed_kmh": last.get("speed_kmh", 0),
            "bearing_deg": last.get("bearing_deg", 0),
            "dt_hours": dt_hours,
            "major_axis_km": last.get("major_axis_km", 10),
            "minor_axis_km": last.get("minor_axis_km", 5),
            "month": pd.to_datetime(last["timestamp"]).month,
            "day_of_year": pd.to_datetime(last["timestamp"]).dayofyear,
        }

        pred = predict_next_position(model, current)
        future_time = pd.to_datetime(last["timestamp"]) + pd.Timedelta(hours=dt_hours)

        predictions.append({
            "timestamp": future_time,
            "latitude": pred["pred_lat"],
            "longitude": pred["pred_lon"],
            "step": step,
        })

        # Update last for next iteration
        last = {
            "timestamp": future_time,
            "latitude": pred["pred_lat"],
            "longitude": pred["pred_lon"],
            "speed_kmh": current["speed_kmh"],
            "bearing_deg": current["bearing_deg"],
            "major_axis_km": current["major_axis_km"],
            "minor_axis_km": current["minor_axis_km"],
        }

    return pd.DataFrame(predictions)
