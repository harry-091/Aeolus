"""
Iceberg Trajectory Model Training.

Trains:
1. Baseline: constant-velocity persistence
2. Random Forest: predicts displacement
3. XGBoost (optional)
"""
import json
import time
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib

try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


FEATURE_COLS = [
    "latitude", "longitude", "speed_kmh", "bearing_deg",
    "dt_hours", "major_axis_km", "minor_axis_km",
]


def prepare_features(df):
    """Create ML features from track data."""
    features = df[FEATURE_COLS].copy()
    features["month"] = pd.to_datetime(df["timestamp"]).dt.month
    features["day_of_year"] = pd.to_datetime(df["timestamp"]).dt.dayofyear
    return features


def prepare_targets(df):
    """Create target displacement vectors."""
    return df[["delta_lat", "delta_lon"]].copy()


def chronological_split(df, train_frac=0.7, val_frac=0.15):
    """Time-aware split using row order."""
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df.iloc[:train_end].copy(), df.iloc[train_end:val_end].copy(), df.iloc[val_end:].copy()


def train_baseline(train, val, test):
    """Baseline: predict zero displacement (stay in place)."""
    metrics = {}
    for name, split in [("train", train), ("val", val), ("test", test)]:
        y_true_lat = split["delta_lat"].values
        y_true_lon = split["delta_lon"].values
        # Baseline: predict mean displacement from training
        mean_dlat = train["delta_lat"].mean()
        mean_dlon = train["delta_lon"].mean()
        pred_dlat = np.full_like(y_true_lat, mean_dlat)
        pred_dlon = np.full_like(y_true_lon, mean_dlon)

        mae_lat = mean_absolute_error(y_true_lat, pred_dlat)
        mae_lon = mean_absolute_error(y_true_lon, pred_dlon)
        metrics[name] = {"mae_lat": float(mae_lat), "mae_lon": float(mae_lon),
                         "mae_avg": float((mae_lat + mae_lon) / 2)}
    return metrics


def train_random_forest(train_df, val_df, n_estimators=100, max_depth=15):
    """Train RF on displacement prediction."""
    X_train = prepare_features(train_df).values
    y_train = prepare_targets(train_df).values
    X_val = prepare_features(val_df).values
    y_val = prepare_targets(val_df).values

    model = RandomForestRegressor(
        n_estimators=n_estimators, max_depth=max_depth,
        random_state=42, n_jobs=-1,
    )

    t0 = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - t0

    y_pred_val = model.predict(X_val)
    mae_lat = mean_absolute_error(y_val[:, 0], y_pred_val[:, 0])
    mae_lon = mean_absolute_error(y_val[:, 1], y_pred_val[:, 1])

    metrics = {
        "train_time": train_time,
        "val": {"mae_lat": float(mae_lat), "mae_lon": float(mae_lon),
                "mae_avg": float((mae_lat + mae_lon) / 2)},
    }
    return model, metrics


def train_xgboost(train_df, val_df):
    """Train XGBoost on displacement prediction."""
    if not HAS_XGBOOST:
        return None, None

    X_train = prepare_features(train_df).values
    y_train = prepare_targets(train_df).values
    X_val = prepare_features(val_df).values
    y_val = prepare_targets(val_df).values

    model = XGBRegressor(
        n_estimators=100, max_depth=6, learning_rate=0.1,
        random_state=42, n_jobs=-1, verbosity=0,
    )

    t0 = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - t0

    y_pred_val = model.predict(X_val)
    mae_lat = mean_absolute_error(y_val[:, 0], y_pred_val[:, 0])
    mae_lon = mean_absolute_error(y_val[:, 1], y_pred_val[:, 1])

    metrics = {
        "train_time": train_time,
        "val": {"mae_lat": float(mae_lat), "mae_lon": float(mae_lon),
                "mae_avg": float((mae_lat + mae_lon) / 2)},
    }
    return model, metrics


def evaluate_on_test(model, test_df):
    """Evaluate on test set."""
    X_test = prepare_features(test_df).values
    y_test = prepare_targets(test_df).values
    y_pred = model.predict(X_test)

    # Convert displacement to approximate km error
    from .tracks import haversine_km
    km_errors = []
    for i in range(len(y_test)):
        pred_lat = test_df["latitude"].iloc[i] + y_pred[i, 0]
        pred_lon = test_df["longitude"].iloc[i] + y_pred[i, 1]
        actual_lat = test_df["latitude"].iloc[i] + y_test[i, 0]
        actual_lon = test_df["longitude"].iloc[i] + y_test[i, 1]
        km_errors.append(haversine_km(pred_lat, pred_lon, actual_lat, actual_lon))

    km_errors = np.array(km_errors)
    metrics = {
        "mae_lat": float(mean_absolute_error(y_test[:, 0], y_pred[:, 0])),
        "mae_lon": float(mean_absolute_error(y_test[:, 1], y_pred[:, 1])),
        "mean_position_error_km": float(np.mean(km_errors)),
        "median_position_error_km": float(np.median(km_errors)),
    }
    return metrics, y_test, y_pred, km_errors


def save_model(model, model_name="iceberg_trajectory_model.joblib", config=None):
    """Save model and config."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / model_name
    joblib.dump(model, model_path)
    print(f"  Model saved: {model_path} ({model_path.stat().st_size / 1024:.0f} KB)")

    if config is None:
        config = {
            "feature_columns": FEATURE_COLS + ["month", "day_of_year"],
            "target": "displacement (delta_lat, delta_lon)",
            "model_type": type(model).__name__,
        }

    config_path = MODELS_DIR / "iceberg_feature_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Config saved: {config_path}")
    return model_path, config_path


def run_iceberg_training():
    """Train and validate iceberg trajectory model across real BYU/NIC observations."""
    print("=== Training Real BYU/NIC Iceberg Trajectory Model ===")
    from .load import load_all_icebergs
    from .tracks import build_tracks

    raw_df = load_all_icebergs()
    tracks_df = build_tracks(raw_df)
    # Filter valid displacement rows
    tracks_df = tracks_df.dropna(subset=["delta_lat", "delta_lon", "dt_hours"]).copy()
    tracks_df = tracks_df[(tracks_df["dt_hours"] > 0) & (tracks_df["dt_hours"] <= 72.0)]
    print(f"  Total valid trajectory steps: {len(tracks_df)}")

    train_df, val_df, test_df = chronological_split(tracks_df, train_frac=0.70, val_frac=0.15)
    print(f"  Data split: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")

    # 1. Baseline
    b_metrics = train_baseline(train_df, val_df, test_df)
    print(f"  Baseline Test MAE: {b_metrics['test']['mae_avg']:.4f}")

    # 2. Random Forest Regressor
    rf_model, rf_metrics = train_random_forest(train_df, val_df, n_estimators=60, max_depth=12)
    test_metrics, y_test, y_pred, km_errors = evaluate_on_test(rf_model, test_df)
    print(f"  Random Forest Test MAE Lat: {test_metrics['mae_lat']:.4f}, Lon: {test_metrics['mae_lon']:.4f}")
    print(f"  Mean Position Error: {test_metrics['mean_position_error_km']:.2f} km, Median Error: {test_metrics['median_position_error_km']:.2f} km")

    # 3. Save model and metrics
    save_model(rf_model, "iceberg_trajectory_model.joblib")
    metrics_path = MODELS_DIR / "iceberg_metrics.json"
    full_metrics = {
        "dataset": "BYU/NIC Antarctic Iceberg Database (180+ Tracked Targets)",
        "model_type": "RandomForestRegressor",
        "total_trajectory_steps": len(tracks_df),
        "train_samples": len(train_df),
        "test_samples": len(test_df),
        "baseline_mae_avg": round(b_metrics["test"]["mae_avg"], 4),
        "test_mae_lat": round(test_metrics["mae_lat"], 4),
        "test_mae_lon": round(test_metrics["mae_lon"], 4),
        "mean_position_error_km": round(test_metrics["mean_position_error_km"], 2),
        "median_position_error_km": round(test_metrics["median_position_error_km"], 2),
        "training_time_seconds": round(rf_metrics["train_time"], 2)
    }
    with open(metrics_path, "w") as f:
        json.dump(full_metrics, f, indent=2)
    print(f"  Metrics saved: {metrics_path}")
    return rf_model, full_metrics


if __name__ == "__main__":
    run_iceberg_training()

