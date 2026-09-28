"""
Sea-Ice Concentration Model Training.

Trains and compares:
1. Persistence baseline (predicted = last observed)
2. Random Forest
3. XGBoost (if available)

Saves best model to models/ directory.
"""
import json
import time
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

from .features import get_feature_columns, get_target_column


MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


def chronological_split(df, train_frac=0.7, val_frac=0.15):
    """
    Time-aware train/val/test split.

    Uses row order (assumed chronological).
    No shuffling to prevent future data leakage.
    """
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))

    train = df.iloc[:train_end].copy()
    val = df.iloc[train_end:val_end].copy()
    test = df.iloc[val_end:].copy()

    return train, val, test


def train_baseline(train_df, val_df, test_df):
    """
    Persistence baseline: predict SIC(t+1) = SIC(t).

    Uses sic_lag_1 as prediction.
    """
    feature_cols = get_feature_columns()
    target_col = get_target_column()

    # Baseline predicts sic_lag_1 as the target
    for split_name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        df["pred_baseline"] = df["sic_lag_1"]

    metrics = {}
    for split_name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        mae = mean_absolute_error(df[target_col], df["pred_baseline"])
        rmse = np.sqrt(mean_squared_error(df[target_col], df["pred_baseline"]))
        r2 = r2_score(df[target_col], df["pred_baseline"])
        metrics[split_name] = {"mae": mae, "rmse": rmse, "r2": r2}

    return metrics


def train_random_forest(train_df, val_df, n_estimators=100, max_depth=15):
    """Train Random Forest regressor."""
    feature_cols = get_feature_columns()
    target_col = get_target_column()

    X_train = train_df[feature_cols].values
    y_train = train_df[target_col].values
    X_val = val_df[feature_cols].values
    y_val = val_df[target_col].values

    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42,
        n_jobs=-1,
    )

    t0 = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - t0

    # Predictions
    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)

    # Clip to valid range
    y_train_pred = np.clip(y_train_pred, 0, 1)
    y_val_pred = np.clip(y_val_pred, 0, 1)

    metrics = {
        "train": {
            "mae": float(mean_absolute_error(y_train, y_train_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_train, y_train_pred))),
            "r2": float(r2_score(y_train, y_train_pred)),
        },
        "val": {
            "mae": float(mean_absolute_error(y_val, y_val_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_val, y_val_pred))),
            "r2": float(r2_score(y_val, y_val_pred)),
        },
        "train_time": train_time,
    }

    return model, metrics


def train_xgboost(train_df, val_df, n_estimators=100, max_depth=6, learning_rate=0.1):
    """Train XGBoost regressor."""
    if not HAS_XGBOOST:
        return None, None

    feature_cols = get_feature_columns()
    target_col = get_target_column()

    X_train = train_df[feature_cols].values
    y_train = train_df[target_col].values
    X_val = val_df[feature_cols].values
    y_val = val_df[target_col].values

    model = XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    t0 = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - t0

    y_train_pred = np.clip(model.predict(X_train), 0, 1)
    y_val_pred = np.clip(model.predict(X_val), 0, 1)

    metrics = {
        "train": {
            "mae": float(mean_absolute_error(y_train, y_train_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_train, y_train_pred))),
            "r2": float(r2_score(y_train, y_train_pred)),
        },
        "val": {
            "mae": float(mean_absolute_error(y_val, y_val_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_val, y_val_pred))),
            "r2": float(r2_score(y_val, y_val_pred)),
        },
        "train_time": train_time,
    }

    return model, metrics


def evaluate_on_test(model, test_df):
    """Evaluate model on test set."""
    feature_cols = get_feature_columns()
    target_col = get_target_column()

    X_test = test_df[feature_cols].values
    y_test = test_df[target_col].values

    y_pred = np.clip(model.predict(X_test), 0, 1)

    metrics = {
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2": float(r2_score(y_test, y_pred)),
    }

    return metrics, y_test, y_pred


def save_model(model, model_name="sea_ice_model.joblib", feature_config=None):
    """Save trained model and feature config."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / model_name
    joblib.dump(model, model_path)
    print(f"  Model saved: {model_path} ({model_path.stat().st_size / 1024:.0f} KB)")

    if feature_config is None:
        feature_config = {
            "feature_columns": get_feature_columns(),
            "target_column": get_target_column(),
            "model_type": type(model).__name__,
        }

    config_path = MODELS_DIR / "sea_ice_feature_config.json"
    with open(config_path, "w") as f:
        json.dump(feature_config, f, indent=2)
    print(f"  Config saved: {config_path}")

    return model_path, config_path


def load_saved_model(model_name="sea_ice_model.joblib"):
    """Load a saved model."""
    model_path = MODELS_DIR / model_name
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    return joblib.load(model_path)


def run_sea_ice_training():
    """Execute end-to-end training and validation on real NOAA CDR satellite data."""
    print("=== Training Real NOAA/NSIDC CDR Sea-Ice Forecasting Model ===")
    from .features import create_features_from_cdr
    df = create_features_from_cdr(sample_step=3)
    train_df, val_df, test_df = chronological_split(df, train_frac=0.70, val_frac=0.15)
    print(f"  Data split: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")

    # 1. Baseline
    b_metrics = train_baseline(train_df, val_df, test_df)
    print(f"  Baseline Test MAE: {b_metrics['test']['mae']:.4f}, RMSE: {b_metrics['test']['rmse']:.4f}")

    # 2. Random Forest Regressor
    rf_model, rf_metrics = train_random_forest(train_df, val_df, n_estimators=60, max_depth=12)
    test_metrics, y_test, y_pred = evaluate_on_test(rf_model, test_df)
    print(f"  Random Forest Test MAE: {test_metrics['mae']:.4f}, RMSE: {test_metrics['rmse']:.4f}, R2: {test_metrics['r2']:.4f}")

    # 3. Save model and metrics
    save_model(rf_model, "sea_ice_model.joblib")
    metrics_path = MODELS_DIR / "sea_ice_metrics.json"
    full_metrics = {
        "dataset": "NOAA/NSIDC CDR V4 (G02202)",
        "model_type": "RandomForestRegressor",
        "samples_total": len(df),
        "train_samples": len(train_df),
        "test_samples": len(test_df),
        "baseline_mae": round(b_metrics["test"]["mae"], 4),
        "test_mae": round(test_metrics["mae"], 4),
        "test_rmse": round(test_metrics["rmse"], 4),
        "test_r2": round(test_metrics["r2"], 4),
        "training_time_seconds": round(rf_metrics["train_time"], 2)
    }
    with open(metrics_path, "w") as f:
        json.dump(full_metrics, f, indent=2)
    print(f"  Metrics saved: {metrics_path}")
    return rf_model, full_metrics


if __name__ == "__main__":
    run_sea_ice_training()
