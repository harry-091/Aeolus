"""CLI utility for Phase 3: ML Training Dataset Generation.

Executes leak-free supervised dataset extraction, produces CSV partitions (train/val/test),
and displays comprehensive statistics and anti-leakage audit results.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path if not present
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.ml_dataset.dataset_generator import MLDatasetGenerator
from src.ml_dataset.voyage_splitter import VoyageSplitter
from src.environmental_replay.replay_pipeline import EnvironmentalReplayPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MLDatasetCLI")


def main():
    parser = argparse.ArgumentParser(description="Generate ML Training Datasets from Historical AIS & Environmental Replay.")
    parser.add_argument(
        "--data-path",
        type=str,
        default="data/raw/vessel_tracks",
        help="Path to AIS directory or CSV/JSON file (default: data/raw/vessel_tracks)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed/ml_datasets",
        help="Directory to save train.csv, val.csv, test.csv and summary metadata",
    )
    parser.add_argument("--train-ratio", type=float, default=0.70, help="Train split ratio (default: 0.70)")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Val split ratio (default: 0.15)")
    parser.add_argument("--test-ratio", type=float, default=0.15, help="Test split ratio (default: 0.15)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()

    data_path = Path(args.data_path)
    output_dir = Path(args.output_dir)

    print("=" * 72)
    print("PHASE 3: ML TRAINING DATASET GENERATION")
    print("Zero-Leakage Historical AIS & Environmental Replay Ingestion")
    print("=" * 72)
    print(f"Source Data Path:    {data_path.resolve()}")
    print(f"Output Directory:    {output_dir.resolve()}")
    print(f"Split Configuration: Train: {args.train_ratio*100:.0f}%, Val: {args.val_ratio*100:.0f}%, Test: {args.test_ratio*100:.0f}%")
    print(f"Reproducibility Seed: {args.seed}")
    print("-" * 72)

    splitter = VoyageSplitter(
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
    generator = MLDatasetGenerator(splitter=splitter, seed=args.seed)

    print("Replaying environmental conditions and matching AIS tracks...")
    pipeline = EnvironmentalReplayPipeline()
    train_df, val_df, test_df, summary = generator.generate_from_ais(
        ais_path=str(data_path),
        output_dir=output_dir,
        replay_pipeline=pipeline,
    )

    print("\n" + "=" * 72)
    print("DATASET SUMMARY & POPULATION STATISTICS")
    print("=" * 72)
    print(f"Total Supervised Samples: {summary.total_samples:,}")
    print(f"Total Unique Voyages:     {summary.num_voyages}")
    print(f"Total Unique Vessels:     {summary.num_vessels}")
    print(f"Feature Vector Dimension: {summary.feature_count} features")
    print(f"Target Count:             {len(summary.target_names)} targets")

    print("\n" + "-" * 72)
    print("SPLIT DISTRIBUTION (VOYAGE-LEVEL PARTITIONING)")
    print("-" * 72)
    print(f"TRAIN Set:      {summary.train_samples:>6,} samples ({summary.train_pct:>5.1f}%) | Voyages: {len(summary.train_voyages)} {summary.train_voyages[:3]}")
    print(f"VAL Set:        {summary.val_samples:>6,} samples ({summary.val_pct:>5.1f}%) | Voyages: {len(summary.val_voyages)} {summary.val_voyages[:3]}")
    print(f"TEST Set:       {summary.test_samples:>6,} samples ({summary.test_pct:>5.1f}%) | Voyages: {len(summary.test_voyages)} {summary.test_voyages[:3]}")

    print("\n" + "-" * 72)
    print("TARGET DISTRIBUTION (GROUND TRUTH)")
    print("-" * 72)
    for target_name, stats in summary.target_stats.items():
        print(f"[{target_name}]")
        print(f"  Mean: {stats['mean']:.4f} | Std: {stats['std']:.4f} | Min: {stats['min']:.4f} | Max: {stats['max']:.4f} | Median: {stats['median']:.4f}")

    print("\n[target_risk_class Breakdown]")
    for k, v in summary.risk_class_distribution.items():
        pct = (v / summary.total_samples * 100.0) if summary.total_samples > 0 else 0.0
        print(f"  Class {k:<12}: {v:>6,} samples ({pct:>5.1f}%)")

    print("\n[target_safe_movement Breakdown]")
    for k, v in summary.safe_movement_counts.items():
        pct = (v / summary.total_samples * 100.0) if summary.total_samples > 0 else 0.0
        print(f"  {k:<18}: {v:>6,} samples ({pct:>5.1f}%)")

    print("\n" + "=" * 72)
    print("ANTI-LEAKAGE VERIFICATION AUDIT")
    print("=" * 72)
    audit = summary.leakage_audit
    print(f"Zero Voyage Overlap Verified:    {audit['zero_leakage_verified']} (NO points from same voyage in Train & Test)")
    print(f"Train/Val Overlapping Voyages:   {len(audit['train_val_voyage_overlap'])}")
    print(f"Train/Test Overlapping Voyages:  {len(audit['train_test_voyage_overlap'])}")
    print(f"Val/Test Overlapping Voyages:    {len(audit['val_test_voyage_overlap'])}")
    print(f"StandardScaler Parameter Fit:   {audit['scaler_training_split_only']} (Fitted on TRAIN ONLY)")
    print(f"Partitioning Strategy:           {audit['split_strategy']}")
    print("=" * 72)
    print(f"Datasets successfully written to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
