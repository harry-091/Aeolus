"""Model Evaluation Engine for Phase 4 Historical ML Models.

Computes comprehensive metrics for both classification (accuracy, precision, recall,
F1, ROC-AUC, confusion matrix) and regression (MAE, RMSE, R², domain tolerance).
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    median_absolute_error,
)


@dataclass
class ClassificationMetrics:
    """Standardized metrics for binary or multi-class navigation classifiers."""
    accuracy: float
    precision_binary: float
    recall_binary: float
    f1_binary: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    roc_auc: Optional[float]
    confusion_matrix: List[List[int]]
    confusion_matrix_breakdown: Dict[str, int]
    sample_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RegressionMetrics:
    """Standardized metrics for continuous navigation cost regressors."""
    mae: float
    rmse: float
    r2: float
    median_ae: float
    max_error: float
    tolerance_05_accuracy_pct: float  # Predictions within +/- 0.05 of actual risk
    tolerance_10_accuracy_pct: float  # Predictions within +/- 0.10 of actual risk
    sample_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MLEvaluator:
    """Evaluates ML models against historical unseen test datasets."""

    @staticmethod
    def evaluate_classifier(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_prob: Optional[np.ndarray] = None,
    ) -> ClassificationMetrics:
        """Compute all classification metrics."""
        y_true = np.asarray(y_true).astype(int)
        y_pred = np.asarray(y_pred).astype(int)
        n = len(y_true)

        acc = float(accuracy_score(y_true, y_pred))
        p_bin = float(precision_score(y_true, y_pred, zero_division=0, average="binary"))
        r_bin = float(recall_score(y_true, y_pred, zero_division=0, average="binary"))
        f1_bin = float(f1_score(y_true, y_pred, zero_division=0, average="binary"))

        p_macro = float(precision_score(y_true, y_pred, zero_division=0, average="macro"))
        r_macro = float(recall_score(y_true, y_pred, zero_division=0, average="macro"))
        f1_macro = float(f1_score(y_true, y_pred, zero_division=0, average="macro"))

        # ROC-AUC calculation if probabilities provided
        roc_auc: Optional[float] = None
        if y_prob is not None and len(np.unique(y_true)) > 1:
            try:
                # If 2D prob array, use positive class column
                prob_vec = y_prob[:, 1] if y_prob.ndim == 2 and y_prob.shape[1] > 1 else y_prob
                roc_auc = float(roc_auc_score(y_true, prob_vec))
            except Exception:
                roc_auc = None

        cm = confusion_matrix(y_true, y_pred).tolist()
        cm_breakdown: Dict[str, int] = {}
        if len(cm) == 2 and len(cm[0]) == 2:
            tn, fp = cm[0][0], cm[0][1]
            fn, tp = cm[1][0], cm[1][1]
            cm_breakdown = {"true_negative": int(tn), "false_positive": int(fp), "false_negative": int(fn), "true_positive": int(tp)}

        return ClassificationMetrics(
            accuracy=round(acc, 4),
            precision_binary=round(p_bin, 4),
            recall_binary=round(r_bin, 4),
            f1_binary=round(f1_bin, 4),
            precision_macro=round(p_macro, 4),
            recall_macro=round(r_macro, 4),
            f1_macro=round(f1_macro, 4),
            roc_auc=round(roc_auc, 4) if roc_auc is not None else None,
            confusion_matrix=cm,
            confusion_matrix_breakdown=cm_breakdown,
            sample_count=n,
        )

    @staticmethod
    def evaluate_regressor(
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> RegressionMetrics:
        """Compute all regression metrics including domain-specific bounds."""
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        n = len(y_true)

        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = float(r2_score(y_true, y_pred))
        med_ae = float(median_absolute_error(y_true, y_pred))
        max_err = float(np.max(np.abs(y_true - y_pred)))

        # Domain-specific metrics: accuracy within +/- 0.05 and +/- 0.10 risk margin
        abs_diff = np.abs(y_true - y_pred)
        tol_05_pct = float(np.mean(abs_diff <= 0.05) * 100.0)
        tol_10_pct = float(np.mean(abs_diff <= 0.10) * 100.0)

        return RegressionMetrics(
            mae=round(mae, 4),
            rmse=round(rmse, 4),
            r2=round(r2, 4),
            median_ae=round(med_ae, 4),
            max_error=round(max_err, 4),
            tolerance_05_accuracy_pct=round(tol_05_pct, 2),
            tolerance_10_accuracy_pct=round(tol_10_pct, 2),
            sample_count=n,
        )
