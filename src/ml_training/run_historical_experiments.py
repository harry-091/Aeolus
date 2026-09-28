"""Executable CLI for Phase 4: Historical ML Training and Evaluation.

Trains XGBoost & Random Forest models on historical voyages, tunes hyperparameters on
validation data, performs a single-pass evaluation on unseen test voyages, saves all
artifacts to models/historical/, and displays a structured Judge Q&A briefing.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.ml_training.trainer import HistoricalMLTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HistoricalMLExperiments")


def main():
    parser = argparse.ArgumentParser(description="Train and Evaluate Historical Polar ML Models (Phase 4).")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/processed/ml_datasets",
        help="Path to processed ML datasets containing train.csv, val.csv, test.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/historical",
        help="Directory to save trained models, schemas, and metrics (default: models/historical)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    print("=" * 76)
    print("PHASE 4: HISTORICAL ML TRAINING & EVALUATION BENCHMARK")
    print("Zero-Leakage Voyage-Partitioned Supervised Learning")
    print("=" * 76)
    print(f"Dataset Path:       {data_dir.resolve()}")
    print(f"Output Directory:   {output_dir.resolve()}")
    print(f"Random Seed:        {args.seed}")
    print("-" * 76)

    trainer = HistoricalMLTrainer(data_dir=data_dir, output_dir=output_dir, seed=args.seed)
    results = trainer.run_all_experiments()

    print("\n" + "=" * 76)
    print("MODEL EVALUATION RESULTS (EVALUATED ON UNSEEN TEST VOYAGES)")
    print("=" * 76)

    # 1. Classification Models
    xgb_cls = results["xgboost_safety_classifier"]
    rf_cls = results["rf_safety_classifier"]

    print("\n[TASK 1: SAFE MOVEMENT CLASSIFICATION (target_safe_movement)]")
    print("-" * 76)
    print(f"{'Metric':<25} | {'XGBoost (Unseen Test)':<22} | {'Random Forest (Unseen Test)':<22}")
    print("-" * 76)
    print(f"{'Accuracy':<25} | {xgb_cls.test_metrics['accuracy']:>20.4f} | {rf_cls.test_metrics['accuracy']:>20.4f}")
    print(f"{'Precision (Binary)':<25} | {xgb_cls.test_metrics['precision_binary']:>20.4f} | {rf_cls.test_metrics['precision_binary']:>20.4f}")
    print(f"{'Recall (Binary)':<25} | {xgb_cls.test_metrics['recall_binary']:>20.4f} | {rf_cls.test_metrics['recall_binary']:>20.4f}")
    print(f"{'F1 Score (Binary)':<25} | {xgb_cls.test_metrics['f1_binary']:>20.4f} | {rf_cls.test_metrics['f1_binary']:>20.4f}")
    print(f"{'F1 Score (Macro)':<25} | {xgb_cls.test_metrics['f1_macro']:>20.4f} | {rf_cls.test_metrics['f1_macro']:>20.4f}")
    roc_xgb = f"{xgb_cls.test_metrics['roc_auc']:.4f}" if xgb_cls.test_metrics['roc_auc'] is not None else "N/A"
    roc_rf = f"{rf_cls.test_metrics['roc_auc']:.4f}" if rf_cls.test_metrics['roc_auc'] is not None else "N/A"
    print(f"{'ROC-AUC':<25} | {roc_xgb:>20} | {roc_rf:>20}")
    print(f"{'Evaluation Samples':<25} | {xgb_cls.test_metrics['sample_count']:>20,} | {rf_cls.test_metrics['sample_count']:>20,}")

    print("\nConfusion Matrix Breakdown (XGBoost Test Set):")
    cm_b = xgb_cls.test_metrics.get("confusion_matrix_breakdown", {})
    print(f"  True Negatives (Risky correctly identified): {cm_b.get('true_negative', 0):>6,}")
    print(f"  False Positives (Risky flagged as Safe):     {cm_b.get('false_positive', 0):>6,}")
    print(f"  False Negatives (Safe flagged as Risky):     {cm_b.get('false_negative', 0):>6,}")
    print(f"  True Positives (Safe correctly identified):  {cm_b.get('true_positive', 0):>6,}")

    # 2. Regression Models
    xgb_reg = results["xgboost_risk_regressor"]
    rf_reg = results["rf_risk_regressor"]

    print("\n\n[TASK 2: NAVIGATION RISK COST REGRESSION (target_risk_cost)]")
    print("-" * 76)
    print(f"{'Metric':<25} | {'XGBoost (Unseen Test)':<22} | {'Random Forest (Unseen Test)':<22}")
    print("-" * 76)
    print(f"{'Mean Absolute Error (MAE)':<25} | {xgb_reg.test_metrics['mae']:>20.4f} | {rf_reg.test_metrics['mae']:>20.4f}")
    print(f"{'Root Mean Sq Error (RMSE)':<25} | {xgb_reg.test_metrics['rmse']:>20.4f} | {rf_reg.test_metrics['rmse']:>20.4f}")
    print(f"{'R-squared (R²)':<25} | {xgb_reg.test_metrics['r2']:>20.4f} | {rf_reg.test_metrics['r2']:>20.4f}")
    print(f"{'Median Abs Error':<25} | {xgb_reg.test_metrics['median_ae']:>20.4f} | {rf_reg.test_metrics['median_ae']:>20.4f}")
    print(f"{'Accuracy within +/- 0.05':<25} | {xgb_reg.test_metrics['tolerance_05_accuracy_pct']:>19.1f}% | {rf_reg.test_metrics['tolerance_05_accuracy_pct']:>19.1f}%")
    print(f"{'Accuracy within +/- 0.10':<25} | {xgb_reg.test_metrics['tolerance_10_accuracy_pct']:>19.1f}% | {rf_reg.test_metrics['tolerance_10_accuracy_pct']:>19.1f}%")

    # 3. Feature Importance Highlights
    print("\n\n" + "=" * 76)
    print("TOP PREDICTIVE FEATURES (XGBoost Feature Importance)")
    print("=" * 76)
    top_feats = xgb_cls.feature_importance.get("top_features", [])[:8]
    for feat_info in top_feats:
        bar = "#" * int(feat_info["importance"] * 40)
        print(f"  {feat_info['rank']:>2}. {feat_info['feature']:<25} : {feat_info['importance']:>6.4f}  {bar}")

    # 4. Critical Route vs ML Performance Disclaimer
    print("\n" + "=" * 76)
    print("CRITICAL ARCHITECTURAL DISTINCTION: ML ACCURACY vs ROUTE QUALITY")
    print("=" * 76)
    print("  * Local ML Prediction Performance evaluates how reliably the trained model")
    print("    predicts point-level hazard risk or safety classification given a single sensor")
    print("    and environmental observation.")
    print("  * Global Route Generation Performance evaluates the multi-objective graph-search")
    print("    corridor (A* / Dijkstra) over thousands of nautical miles, optimizing total distance,")
    print("    transit hours, fuel consumption, and closest-point-of-approach (CPA) iceberg margins.")
    print("  * HIGH CLASSIFICATION ACCURACY DOES NOT EQUAL ROUTE ACCURACY.")

    # 5. Judge Q&A Briefing
    print("\n" + "=" * 76)
    print("SIH 2026 JUDGE DEFENSE Q&A BRIEFING")
    print("=" * 76)
    print("Q1: 'What historical data did you train on?'")
    print("A1: 10,462 verified Antarctic AIS observations matched with co-located environmental")
    print("    data (NOAA/NSIDC CDR sea-ice concentration, NOAA ETOPO bathymetry, and 22,391 BYU/NIC")
    print("    iceberg tracks) spanning 2008 to 2019 from Australian Antarctic Division research vessels.")
    print()
    print("Q2: 'How did you split train and test?'")
    print("A2: Strictly by VOYAGE, using chronological ordering:")
    print("    - Train (6,262 samples): Voyages from 2008, 2010, 2015")
    print("    - Validation (2,100 samples): Voyage from 2017-18 season (used solely for hyperparameter tuning)")
    print("    - Test (2,100 samples): Unseen voyage from 2018-19 season (evaluated strictly once)")
    print()
    print("Q3: 'How did you prevent data leakage?'")
    print("A3: Four strict firewalls:")
    print("    1. Voyage-level split: 0 points from any training voyage exist in validation or test.")
    print("    2. StandardScaler fitted ONLY on training split; parameters frozen before transforming val/test.")
    print("    3. Environmental anti-leakage: T_env <= T_decision (no future satellite observations).")
    print("    4. Production isolation: Production models in models/ are completely preserved.")
    print()
    print("Q4: 'What exactly does XGBoost predict?'")
    print("A4: We evaluate two project-aligned targets:")
    print("    1. 'target_safe_movement': Binary classification indicating whether a point is navigable")
    print("       (risk < 0.35, depth >= 20m, iceberg clearance >= 15km, off-land).")
    print("    2. 'target_risk_cost': Continuous multi-objective cost in [0.0, 1.0] derived from project's")
    print("       navigation cost function (SIC: 0.50, iceberg: 0.25, bathymetry: 0.15, coastline: 0.10).")
    print()
    print("Q5: 'How well does it perform on unseen voyages?'")
    print(f"A5: On the completely unseen 2018-19 voyage ({xgb_cls.test_metrics['sample_count']:,} samples):")
    print(f"    - Classification Accuracy: {xgb_cls.test_metrics['accuracy']*100:.1f}% | F1 Score: {xgb_cls.test_metrics['f1_binary']:.4f} | ROC-AUC: {roc_xgb}")
    print(f"    - Regression MAE: {xgb_reg.test_metrics['mae']:.4f} | Within +/-0.05 risk tolerance: {xgb_reg.test_metrics['tolerance_05_accuracy_pct']:.1f}%")
    print("=" * 76)
    print(f"All model weights, metadata, and metric files written to: {output_dir.resolve()}\n")


if __name__ == "__main__":
    main()
