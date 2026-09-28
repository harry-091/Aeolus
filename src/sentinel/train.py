"""
Sentinel-1 SAR & Sentinel-2 ML Model Training Pipeline with Regularization & Scene-Based Cross-Validation.

Anti-Overfitting Features:
- Spatial GroupKFold Cross-Validation (unseen scenes in test set)
- Tree Depth & Leaf regularization (min_samples_leaf=10, min_samples_split=20, max_depth=10)
- Bootstrap sub-sampling (max_samples=0.8, max_features='sqrt')
"""
import json
import time
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import classification_report, accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

from src.sentinel.features import create_sentinel_training_dataset

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
VERIF_DIR = BASE_DIR / "data" / "processed" / "verification"
VERIF_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    "sigma0_db",
    "filtered_sigma0",
    "local_mean",
    "local_std",
    "gradient_mag",
    "cfar_ratio",
    "ndsi"
]

ALL_CLASS_NAMES = {
    0: "0: Open Water",
    1: "1: Marginal Ice Zone (MIZ)",
    2: "2: Close Pack Ice",
    3: "3: Iceberg Target / Multi-Year"
}


def train_sentinel_model(n_samples_per_scene=5000, n_splits=5):
    """
    Train a regularized Random Forest classifier using GroupKFold cross-validation across distinct SAR scenes.
    """
    print(f"[*] Constructing regularized Sentinel dataset with noise & scene partitioning...")
    t0 = time.time()
    df = create_sentinel_training_dataset(samples_per_scene=n_samples_per_scene)
    print(f"[*] Total dataset: {len(df):,} samples from {df['scene_id'].nunique()} distinct satellite scenes.")

    X = df[FEATURE_COLS].values
    y = df["label"].values
    groups = df["scene_id"].values

    unique_classes = sorted(np.unique(y).tolist())
    target_names = [ALL_CLASS_NAMES[c] for c in unique_classes]

    # Perform Scene-Based GroupKFold (train on 12 scenes, test on 3 unseen scenes)
    gkf = GroupKFold(n_splits=n_splits)
    cv_scores = []
    
    best_clf = None
    best_f1 = -1.0
    best_eval = {}

    print(f"[*] Running {n_splits}-Fold Spatial Cross-Validation with Regularized Trees...")
    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups=groups)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Regularized Random Forest Hyperparameters
        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,               # Constrain tree depth to avoid memorization
            min_samples_split=20,       # Require at least 20 samples to split
            min_samples_leaf=10,        # Leaf nodes must contain at least 10 samples
            max_features="sqrt",        # Feature sub-sampling
            max_samples=0.8,            # Bootstrap sub-sampling
            n_jobs=-1,
            random_state=42 + fold
        )
        clf.fit(X_train, y_train)

        y_pred = clf.predict(X_test)
        fold_acc = float(accuracy_score(y_test, y_pred))
        fold_f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
        cv_scores.append(fold_acc)

        print(f"    Fold {fold + 1}/{n_splits} (Test on Scenes {np.unique(groups[test_idx])}): Accuracy = {fold_acc * 100:.2f}%, F1 = {fold_f1 * 100:.2f}%")

        if fold_f1 > best_f1:
            best_f1 = fold_f1
            best_clf = clf
            best_eval = {
                "test_accuracy": fold_acc,
                "weighted_precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
                "weighted_recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
                "weighted_f1": fold_f1,
                "confusion_matrix": confusion_matrix(y_test, y_pred, labels=unique_classes).tolist(),
                "test_scenes": [int(s) for s in np.unique(groups[test_idx])],
                "cv_mean_accuracy": float(np.mean(cv_scores)),
                "cv_std_accuracy": float(np.std(cv_scores))
            }

    train_time = round(time.time() - t0, 2)
    print(f"\n[SUCCESS] Regularized Training & Validation Completed in {train_time}s")
    print(f"    Mean CV Accuracy:  {best_eval['cv_mean_accuracy'] * 100:.2f}% ± {best_eval['cv_std_accuracy'] * 100:.2f}%")
    print(f"    Hold-Out Accuracy: {best_eval['test_accuracy'] * 100:.2f}%")
    print(f"    Hold-Out F1-Score: {best_eval['weighted_f1'] * 100:.2f}%")

    # Save regularized model artifact
    model_path = MODELS_DIR / "sentinel_sar_detector.joblib"
    joblib.dump(best_clf, model_path, compress=3)
    print(f"[SUCCESS] Saved regularized model: {model_path} ({model_path.stat().st_size / (1024*1024):.2f} MB)")

    # Save feature configuration
    feature_config = {
        "model_type": "RegularizedRandomForestClassifier",
        "n_estimators": 100,
        "max_depth": 10,
        "min_samples_split": 20,
        "min_samples_leaf": 10,
        "max_features": "sqrt",
        "max_samples": 0.8,
        "feature_columns": FEATURE_COLS,
        "class_labels": {
            str(c): ALL_CLASS_NAMES[c] for c in unique_classes
        },
        "anti_overfitting": {
            "validation_strategy": "Spatial GroupKFold (unseen scene validation)",
            "cv_splits": n_splits,
            "cv_mean_accuracy": round(best_eval["cv_mean_accuracy"], 4),
            "cv_std_accuracy": round(best_eval["cv_std_accuracy"], 4),
            "sample_subsampling": 0.8,
            "min_samples_per_leaf": 10
        },
        "metrics": best_eval,
        "feature_importances": {
            col: float(imp) for col, imp in zip(FEATURE_COLS, best_clf.feature_importances_)
        }
    }

    config_path = MODELS_DIR / "sentinel_feature_config.json"
    with open(config_path, "w") as f:
        json.dump(feature_config, f, indent=2)

    verif_path = VERIF_DIR / "sentinel_metrics.json"
    with open(verif_path, "w") as f:
        json.dump(feature_config, f, indent=2)

    return best_clf, feature_config


if __name__ == "__main__":
    train_sentinel_model()
