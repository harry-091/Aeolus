"""Historical ML Model Trainer for Phase 4.

Orchestrates leak-free model training on historical voyages, validation-only hyperparameter
tuning, and single-pass evaluation on unseen test voyages.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from xgboost import XGBClassifier, XGBRegressor

from src.ml_dataset.feature_extractor import FEATURE_NAMES
from .evaluator import MLEvaluator, ClassificationMetrics, RegressionMetrics
from .feature_importance import extract_feature_importance
from .experiment_tracker import ExperimentTracker, ExperimentArtifacts

logger = logging.getLogger(__name__)


class HistoricalMLTrainer:
    """Trains, tunes, and evaluates XGBoost and Random Forest on partitioned historical data."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        seed: int = 42,
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.seed = seed
        self.tracker = ExperimentTracker(self.output_dir)

        # Load dataset partitions
        self.train_df = pd.read_csv(self.data_dir / "train.csv")
        self.val_df = pd.read_csv(self.data_dir / "val.csv")
        self.test_df = pd.read_csv(self.data_dir / "test.csv")

        # Load split provenance
        summary_path = self.data_dir / "dataset_summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                self.dataset_meta = json.load(f)
        else:
            self.dataset_meta = {"total_samples": len(self.train_df) + len(self.val_df) + len(self.test_df)}

        self.feature_cols = [c for c in FEATURE_NAMES if c in self.train_df.columns]

    def _get_splits(self, target_col: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Extract feature matrices and target arrays for train, val, and test splits."""
        X_train = self.train_df[self.feature_cols].values
        y_train = self.train_df[target_col].values

        X_val = self.val_df[self.feature_cols].values
        y_val = self.val_df[target_col].values

        X_test = self.test_df[self.feature_cols].values
        y_test = self.test_df[target_col].values

        return X_train, y_train, X_val, y_val, X_test, y_test

    def train_xgboost_classifier(self) -> Tuple[XGBClassifier, ExperimentArtifacts]:
        """Train and tune XGBoost Classifier for safe vs risky movement prediction."""
        target_col = "target_safe_movement"
        X_train, y_train, X_val, y_val, X_test, y_test = self._get_splits(target_col)

        # Hyperparameter tuning candidates (evaluated ONLY on validation set)
        param_grid = [
            {"n_estimators": 50, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8},
            {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.08, "subsample": 0.8},
            {"n_estimators": 150, "max_depth": 5, "learning_rate": 0.10, "subsample": 0.9},
        ]

        best_model = None
        best_val_f1 = -1.0
        best_params = param_grid[0]
        best_val_metrics = None

        for params in param_grid:
            model = XGBClassifier(
                **params,
                eval_metric="logloss",
                random_state=self.seed,
                n_jobs=-1,
            )
            model.fit(X_train, y_train)
            
            # Evaluate on validation
            val_pred = model.predict(X_val)
            val_prob = model.predict_proba(X_val)
            val_metrics = MLEvaluator.evaluate_classifier(y_val, val_pred, val_prob)

            if val_metrics.f1_binary > best_val_f1:
                best_val_f1 = val_metrics.f1_binary
                best_model = model
                best_params = params
                best_val_metrics = val_metrics

        # Final evaluation: EXACTLY ONCE on unseen test set
        test_pred = best_model.predict(X_test)
        test_prob = best_model.predict_proba(X_test)
        test_metrics = MLEvaluator.evaluate_classifier(y_test, test_pred, test_prob)

        # Feature importance
        fi = extract_feature_importance(best_model, self.feature_cols)

        artifacts = ExperimentArtifacts(
            model_name="xgboost_safety_classifier",
            target_name=target_col,
            model_type="xgboost",
            task_type="classification",
            training_timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_version="v1.0-phase3",
            feature_names=self.feature_cols,
            train_voyages=self.dataset_meta.get("train_voyages", []),
            val_voyages=self.dataset_meta.get("val_voyages", []),
            test_voyages=self.dataset_meta.get("test_voyages", []),
            hyperparameters=best_params,
            val_metrics=best_val_metrics.to_dict(),
            test_metrics=test_metrics.to_dict(),
            feature_importance=fi,
        )

        self.tracker.save_artifacts(best_model, artifacts)
        return best_model, artifacts

    def train_random_forest_classifier(self) -> Tuple[RandomForestClassifier, ExperimentArtifacts]:
        """Train and tune Random Forest Classifier for safe vs risky movement prediction."""
        target_col = "target_safe_movement"
        X_train, y_train, X_val, y_val, X_test, y_test = self._get_splits(target_col)

        param_grid = [
            {"n_estimators": 50, "max_depth": 6, "min_samples_split": 10},
            {"n_estimators": 100, "max_depth": 8, "min_samples_split": 5},
            {"n_estimators": 150, "max_depth": 10, "min_samples_split": 5},
        ]

        best_model = None
        best_val_f1 = -1.0
        best_params = param_grid[0]
        best_val_metrics = None

        for params in param_grid:
            model = RandomForestClassifier(
                **params,
                random_state=self.seed,
                n_jobs=-1,
            )
            model.fit(X_train, y_train)

            val_pred = model.predict(X_val)
            val_prob = model.predict_proba(X_val)
            val_metrics = MLEvaluator.evaluate_classifier(y_val, val_pred, val_prob)

            if val_metrics.f1_binary > best_val_f1:
                best_val_f1 = val_metrics.f1_binary
                best_model = model
                best_params = params
                best_val_metrics = val_metrics

        test_pred = best_model.predict(X_test)
        test_prob = best_model.predict_proba(X_test)
        test_metrics = MLEvaluator.evaluate_classifier(y_test, test_pred, test_prob)

        fi = extract_feature_importance(best_model, self.feature_cols)

        artifacts = ExperimentArtifacts(
            model_name="rf_safety_classifier",
            target_name=target_col,
            model_type="random_forest",
            task_type="classification",
            training_timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_version="v1.0-phase3",
            feature_names=self.feature_cols,
            train_voyages=self.dataset_meta.get("train_voyages", []),
            val_voyages=self.dataset_meta.get("val_voyages", []),
            test_voyages=self.dataset_meta.get("test_voyages", []),
            hyperparameters=best_params,
            val_metrics=best_val_metrics.to_dict(),
            test_metrics=test_metrics.to_dict(),
            feature_importance=fi,
        )

        self.tracker.save_artifacts(best_model, artifacts)
        return best_model, artifacts

    def train_xgboost_regressor(self) -> Tuple[XGBRegressor, ExperimentArtifacts]:
        """Train and tune XGBoost Regressor for continuous navigation risk cost prediction."""
        target_col = "target_risk_cost"
        X_train, y_train, X_val, y_val, X_test, y_test = self._get_splits(target_col)

        param_grid = [
            {"n_estimators": 50, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8},
            {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.08, "subsample": 0.8},
            {"n_estimators": 150, "max_depth": 5, "learning_rate": 0.10, "subsample": 0.9},
        ]

        best_model = None
        best_val_mae = float("inf")
        best_params = param_grid[0]
        best_val_metrics = None

        for params in param_grid:
            model = XGBRegressor(
                **params,
                eval_metric="rmse",
                random_state=self.seed,
                n_jobs=-1,
            )
            model.fit(X_train, y_train)

            val_pred = model.predict(X_val)
            val_metrics = MLEvaluator.evaluate_regressor(y_val, val_pred)

            if val_metrics.mae < best_val_mae:
                best_val_mae = val_metrics.mae
                best_model = model
                best_params = params
                best_val_metrics = val_metrics

        test_pred = best_model.predict(X_test)
        test_metrics = MLEvaluator.evaluate_regressor(y_test, test_pred)

        fi = extract_feature_importance(best_model, self.feature_cols)

        artifacts = ExperimentArtifacts(
            model_name="xgboost_risk_regressor",
            target_name=target_col,
            model_type="xgboost",
            task_type="regression",
            training_timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_version="v1.0-phase3",
            feature_names=self.feature_cols,
            train_voyages=self.dataset_meta.get("train_voyages", []),
            val_voyages=self.dataset_meta.get("val_voyages", []),
            test_voyages=self.dataset_meta.get("test_voyages", []),
            hyperparameters=best_params,
            val_metrics=best_val_metrics.to_dict(),
            test_metrics=test_metrics.to_dict(),
            feature_importance=fi,
        )

        self.tracker.save_artifacts(best_model, artifacts)
        return best_model, artifacts

    def train_random_forest_regressor(self) -> Tuple[RandomForestRegressor, ExperimentArtifacts]:
        """Train and tune Random Forest Regressor for continuous navigation risk cost prediction."""
        target_col = "target_risk_cost"
        X_train, y_train, X_val, y_val, X_test, y_test = self._get_splits(target_col)

        param_grid = [
            {"n_estimators": 50, "max_depth": 6, "min_samples_split": 10},
            {"n_estimators": 100, "max_depth": 8, "min_samples_split": 5},
            {"n_estimators": 150, "max_depth": 10, "min_samples_split": 5},
        ]

        best_model = None
        best_val_mae = float("inf")
        best_params = param_grid[0]
        best_val_metrics = None

        for params in param_grid:
            model = RandomForestRegressor(
                **params,
                random_state=self.seed,
                n_jobs=-1,
            )
            model.fit(X_train, y_train)

            val_pred = model.predict(X_val)
            val_metrics = MLEvaluator.evaluate_regressor(y_val, val_pred)

            if val_metrics.mae < best_val_mae:
                best_val_mae = val_metrics.mae
                best_model = model
                best_params = params
                best_val_metrics = val_metrics

        test_pred = best_model.predict(X_test)
        test_metrics = MLEvaluator.evaluate_regressor(y_test, test_pred)

        fi = extract_feature_importance(best_model, self.feature_cols)

        artifacts = ExperimentArtifacts(
            model_name="rf_risk_regressor",
            target_name=target_col,
            model_type="random_forest",
            task_type="regression",
            training_timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_version="v1.0-phase3",
            feature_names=self.feature_cols,
            train_voyages=self.dataset_meta.get("train_voyages", []),
            val_voyages=self.dataset_meta.get("val_voyages", []),
            test_voyages=self.dataset_meta.get("test_voyages", []),
            hyperparameters=best_params,
            val_metrics=best_val_metrics.to_dict(),
            test_metrics=test_metrics.to_dict(),
            feature_importance=fi,
        )

        self.tracker.save_artifacts(best_model, artifacts)
        return best_model, artifacts

    def run_all_experiments(self) -> Dict[str, ExperimentArtifacts]:
        """Train and evaluate all four baseline models, then save consolidated summaries."""
        logger.info("Training XGBoost Safety Classifier...")
        _, xgb_cls_art = self.train_xgboost_classifier()

        logger.info("Training Random Forest Safety Classifier...")
        _, rf_cls_art = self.train_random_forest_classifier()

        logger.info("Training XGBoost Risk Regressor...")
        _, xgb_reg_art = self.train_xgboost_regressor()

        logger.info("Training Random Forest Risk Regressor...")
        _, rf_reg_art = self.train_random_forest_regressor()

        results = {
            "xgboost_safety_classifier": xgb_cls_art,
            "rf_safety_classifier": rf_cls_art,
            "xgboost_risk_regressor": xgb_reg_art,
            "rf_risk_regressor": rf_reg_art,
        }

        # Consolidated summaries
        all_metrics = {k: {"val": v.val_metrics, "test": v.test_metrics} for k, v in results.items()}
        top_importances = {k: v.feature_importance.get("top_features", []) for k, v in results.items()}

        self.tracker.save_global_summary(
            all_metrics=all_metrics,
            feature_schema=self.feature_cols,
            dataset_meta=self.dataset_meta,
            top_importances=top_importances,
        )

        return results
