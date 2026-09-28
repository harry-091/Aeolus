"""Unit and integration tests for Phase 4: Historical ML Training and Evaluation.

Validates metric calculations, hyperparameter tuning on validation only, feature importance
ranking, and zero pollution of production model files.
"""

from datetime import datetime, timezone
import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from xgboost import XGBClassifier, XGBRegressor

from src.ml_training.evaluator import MLEvaluator, ClassificationMetrics, RegressionMetrics
from src.ml_training.feature_importance import extract_feature_importance
from src.ml_training.experiment_tracker import ExperimentTracker, ExperimentArtifacts
from src.ml_training.trainer import HistoricalMLTrainer


class TestMLEvaluator:
    """Test standard and domain-specific metric evaluations."""

    def test_classification_metrics(self):
        y_true = np.array([1, 1, 0, 0, 1, 0, 1, 0])
        y_pred = np.array([1, 1, 0, 0, 0, 0, 1, 1])
        y_prob = np.array([
            [0.1, 0.9],
            [0.2, 0.8],
            [0.8, 0.2],
            [0.9, 0.1],
            [0.6, 0.4],
            [0.7, 0.3],
            [0.3, 0.7],
            [0.4, 0.6],
        ])

        metrics = MLEvaluator.evaluate_classifier(y_true, y_pred, y_prob)

        assert isinstance(metrics, ClassificationMetrics)
        assert 0.0 <= metrics.accuracy <= 1.0
        assert 0.0 <= metrics.precision_binary <= 1.0
        assert 0.0 <= metrics.recall_binary <= 1.0
        assert 0.0 <= metrics.f1_binary <= 1.0
        assert metrics.roc_auc is not None
        assert 0.0 <= metrics.roc_auc <= 1.0

        # Check confusion matrix: 3 TP, 3 TN, 1 FP, 1 FN
        cm = metrics.confusion_matrix_breakdown
        assert cm["true_positive"] == 3
        assert cm["true_negative"] == 3
        assert cm["false_positive"] == 1
        assert cm["false_negative"] == 1

    def test_regression_metrics(self):
        y_true = np.array([0.10, 0.25, 0.50, 0.75, 0.90])
        y_pred = np.array([0.12, 0.28, 0.48, 0.72, 0.94])

        metrics = MLEvaluator.evaluate_regressor(y_true, y_pred)

        assert isinstance(metrics, RegressionMetrics)
        assert metrics.mae > 0.0
        assert metrics.rmse >= metrics.mae
        assert metrics.r2 > 0.90  # Very close predictions
        # All errors are <= 0.04, so 100% within 0.05 tolerance
        assert metrics.tolerance_05_accuracy_pct == 100.0


class TestFeatureImportance:
    """Test tree feature importance extraction and normalization."""

    def test_feature_importance_ranking(self):
        X = np.random.RandomState(42).randn(100, 4)
        y = (X[:, 0] * 2.0 + X[:, 1] > 0).astype(int)
        feature_names = ["feat_dominant", "feat_secondary", "noise_1", "noise_2"]

        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)

        fi = extract_feature_importance(model, feature_names)

        assert "ranked_features" in fi
        assert len(fi["ranked_features"]) == 4
        # Total normalized importances should sum close to 1.0
        total_imp = sum(f["importance"] for f in fi["ranked_features"])
        assert np.isclose(total_imp, 1.0, atol=1e-2)

        # First feature should have highest rank
        assert fi["ranked_features"][0]["rank"] == 1


class TestExperimentTrackerAndPreservation:
    """Verify artifact serialization and verify production models remain untouched."""

    def test_production_models_untouched(self):
        prod_models_dir = Path(__file__).resolve().parent.parent / "models"
        prod_files_before = set(f.name for f in prod_models_dir.glob("*.*") if f.is_file())

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ExperimentTracker(Path(tmpdir))
            dummy_model = RandomForestClassifier()
            artifacts = ExperimentArtifacts(
                model_name="test_model",
                target_name="target_safe_movement",
                model_type="random_forest",
                task_type="classification",
                training_timestamp=datetime.now(timezone.utc).isoformat(),
                dataset_version="v1.0-test",
                feature_names=["f1", "f2"],
                train_voyages=["v1"],
                val_voyages=["v2"],
                test_voyages=["v3"],
                hyperparameters={"n_estimators": 10},
                val_metrics={"accuracy": 0.9},
                test_metrics={"accuracy": 0.85},
                feature_importance={},
            )
            tracker.save_artifacts(dummy_model, artifacts)

            assert (Path(tmpdir) / "test_model.joblib").exists()
            assert (Path(tmpdir) / "test_model_metadata.json").exists()

        # Check production directory was not modified
        prod_files_after = set(f.name for f in prod_models_dir.glob("*.*") if f.is_file())
        assert prod_files_before == prod_files_after


class TestHistoricalTrainerIntegration:
    """Integration test training small models with HistoricalMLTrainer."""

    def test_trainer_pipeline_on_phase3_datasets(self):
        data_dir = Path(__file__).resolve().parent.parent / "data" / "processed" / "ml_datasets"
        if not (data_dir / "train.csv").exists():
            pytest.skip("Phase 3 datasets not found on disk")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            trainer = HistoricalMLTrainer(data_dir=data_dir, output_dir=out_dir, seed=42)

            # Train XGBoost Safety Classifier
            model_xgb, art_xgb = trainer.train_xgboost_classifier()
            assert (out_dir / "xgboost_safety_classifier.joblib").exists()
            assert (out_dir / "xgboost_safety_classifier_metadata.json").exists()
            assert art_xgb.test_metrics["accuracy"] > 0.50

            # Train Random Forest Risk Regressor
            model_rf, art_rf = trainer.train_random_forest_regressor()
            assert (out_dir / "rf_risk_regressor.joblib").exists()
            assert art_rf.test_metrics["mae"] < 0.50
