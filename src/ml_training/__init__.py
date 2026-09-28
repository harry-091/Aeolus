"""Phase 4: Historical Machine Learning Training and Evaluation Pipeline.

Provides dedicated, leak-free model training, validation-based hyperparameter tuning,
unseen-test evaluation, and provenance tracking for polar maritime navigation.
"""

from .evaluator import MLEvaluator, ClassificationMetrics, RegressionMetrics
from .feature_importance import extract_feature_importance
from .experiment_tracker import ExperimentTracker, ExperimentArtifacts
from .trainer import HistoricalMLTrainer

__all__ = [
    "MLEvaluator",
    "ClassificationMetrics",
    "RegressionMetrics",
    "extract_feature_importance",
    "ExperimentTracker",
    "ExperimentArtifacts",
    "HistoricalMLTrainer",
]
