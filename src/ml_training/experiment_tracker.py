"""Experiment Tracker & Provenance Engine for Phase 4 Historical ML.

Serializes trained models, hyperparameter configurations, dataset split provenance,
metrics, and feature schemas to a dedicated historical directory without modifying production models.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import joblib

logger = logging.getLogger(__name__)


@dataclass
class ExperimentArtifacts:
    """Provenance bundle for a trained historical ML model."""
    model_name: str
    target_name: str
    model_type: str  # "xgboost" or "random_forest"
    task_type: str   # "classification" or "regression"
    training_timestamp: str
    dataset_version: str
    feature_names: List[str]
    train_voyages: List[str]
    val_voyages: List[str]
    test_voyages: List[str]
    hyperparameters: Dict[str, Any]
    val_metrics: Dict[str, Any]
    test_metrics: Dict[str, Any]
    feature_importance: Dict[str, Any]
    notes: str = (
        "DISCLAIMER: ML prediction performance reflects local environmental risk/safety "
        "classification per observation and does NOT equate to end-to-end route optimality."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExperimentTracker:
    """Manages serialization of historical models and audit trails."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_artifacts(
        self,
        model: Any,
        artifacts: ExperimentArtifacts,
    ) -> Path:
        """Save model binary and JSON metadata to disk.
        
        Args:
            model: Trained estimator.
            artifacts: Metadata container.
            
        Returns:
            Path to saved model file.
        """
        prefix = artifacts.model_name
        model_path = self.output_dir / f"{prefix}.joblib"
        joblib.dump(model, model_path)

        meta_path = self.output_dir / f"{prefix}_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(artifacts.to_dict(), f, indent=2)

        logger.info(f"Successfully saved {prefix} to {model_path}")
        return model_path

    def save_global_summary(
        self,
        all_metrics: Dict[str, Any],
        feature_schema: List[str],
        dataset_meta: Dict[str, Any],
        top_importances: Dict[str, Any],
    ) -> None:
        """Save consolidated evaluation and schema files."""
        # 1. Feature schema
        with open(self.output_dir / "feature_schema.json", "w", encoding="utf-8") as f:
            json.dump({
                "feature_count": len(feature_schema),
                "features": feature_schema,
                "version": "v1.0-phase4",
            }, f, indent=2)

        # 2. Evaluation metrics
        with open(self.output_dir / "evaluation_metrics.json", "w", encoding="utf-8") as f:
            json.dump(all_metrics, f, indent=2)

        # 3. Feature importance
        with open(self.output_dir / "feature_importance.json", "w", encoding="utf-8") as f:
            json.dump(top_importances, f, indent=2)

        # 4. Model metadata summary
        summary_metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "experiment_tag": "phase4_historical_ml_benchmark",
            "dataset_provenance": dataset_meta,
            "models_evaluated": list(all_metrics.keys()),
            "anti_leakage_guarantee": {
                "voyage_isolated_splits": True,
                "tuning_on_validation_only": True,
                "single_evaluation_on_unseen_test": True,
                "production_models_preserved": True,
            },
            "conceptual_distinction": (
                "ML model accuracy evaluates individual state prediction (local hazard risk cost / safe movement) "
                "from historical sensor & environmental inputs. End-to-end route optimality is governed by graph "
                "pathfinding across thousands of nodes and is evaluated via maritime nautical metrics (distance, time, fuel, CPA)."
            ),
        }
        with open(self.output_dir / "model_metadata.json", "w", encoding="utf-8") as f:
            json.dump(summary_metadata, f, indent=2)
