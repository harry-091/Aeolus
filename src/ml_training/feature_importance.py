"""Feature Importance Utility for Phase 4 Historical ML Models.

Extracts, normalizes, and ranks feature contributions for tree-based ensemble models
(XGBoost and Random Forest).
"""

from typing import List, Dict, Any, Union
import numpy as np


def extract_feature_importance(
    model: Any,
    feature_names: List[str],
    top_n: int = 15,
) -> Dict[str, Any]:
    """Extract and rank feature importances from a fitted tree model.
    
    Args:
        model: Fitted scikit-learn or XGBoost model.
        feature_names: List of feature names corresponding to model input columns.
        top_n: Number of top features to highlight.
        
    Returns:
        Dictionary with full rankings and top_n summary.
    """
    importances: np.ndarray

    if hasattr(model, "feature_importances_"):
        importances = np.array(model.feature_importances_, dtype=float)
    else:
        # Fallback if attribute missing
        importances = np.zeros(len(feature_names), dtype=float)

    # Normalize to sum to 1.0 (or percentage)
    total = np.sum(importances)
    if total > 0:
        norm_importances = importances / total
    else:
        norm_importances = importances

    ranking = []
    importance_map = {}
    for name, imp, raw_imp in zip(feature_names, norm_importances, importances):
        importance_map[name] = round(float(imp), 5)
        ranking.append({
            "feature": name,
            "importance": round(float(imp), 5),
            "raw_importance": round(float(raw_imp), 5),
        })

    # Sort descending by importance
    ranking.sort(key=lambda x: x["importance"], reverse=True)
    for idx, item in enumerate(ranking, 1):
        item["rank"] = idx

    return {
        "ranked_features": ranking,
        "top_features": ranking[:top_n],
        "feature_importance_map": importance_map,
    }
