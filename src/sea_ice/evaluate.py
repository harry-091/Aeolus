"""
Model Evaluation Module.

Provides evaluation metrics and visualization utilities.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def compute_metrics(y_true, y_pred):
    """Compute standard regression metrics."""
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }


def plot_actual_vs_predicted(y_true, y_pred, title="Actual vs Predicted SIC",
                              save_path=None):
    """Scatter plot of actual vs predicted values."""
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(y_true, y_pred, alpha=0.1, s=5, color="steelblue")
    ax.plot([0, 1], [0, 1], "r--", linewidth=2, label="Perfect prediction")
    ax.set_xlabel("Actual SIC", fontsize=12)
    ax.set_ylabel("Predicted SIC", fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig


def plot_residuals(y_true, y_pred, title="Residual Distribution",
                    save_path=None):
    """Histogram of prediction residuals."""
    residuals = y_true - y_pred
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(residuals, bins=50, color="steelblue", edgecolor="white", alpha=0.8)
    ax.axvline(0, color="red", linestyle="--", linewidth=2)
    ax.set_xlabel("Residual (Actual - Predicted)", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.grid(True, alpha=0.3)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig


def plot_model_comparison(metrics_dict, title="Model Comparison",
                           save_path=None):
    """Bar chart comparing model metrics."""
    models = list(metrics_dict.keys())
    maes = [metrics_dict[m]["mae"] for m in models]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(models, maes, color=["gray", "steelblue", "coral"][:len(models)])
    ax.set_ylabel("MAE", fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.grid(True, alpha=0.3, axis="y")

    for bar, mae in zip(bars, maes):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                f"{mae:.4f}", ha="center", fontsize=10)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig
