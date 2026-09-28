"""Dataset Generator for Phase 3 ML Training Dataset.

Orchestrates leak-free feature extraction, target derivation, voyage-level partitioning,
training-only feature normalization, and statistical dataset reporting.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from src.environmental_replay.replay_schema import EnrichedAISFeaturePoint
from src.environmental_replay.replay_pipeline import EnvironmentalReplayPipeline
from .feature_extractor import FeatureExtractor, FEATURE_NAMES, MLFeatureVector
from .target_generator import TargetGenerator, TARGET_NAMES, MLTargetVector
from .voyage_splitter import VoyageSplitter, DatasetSplits

logger = logging.getLogger(__name__)


@dataclass
class DatasetSummary:
    """Comprehensive statistical summary of generated ML datasets."""
    total_samples: int
    num_voyages: int
    num_vessels: int
    feature_count: int
    feature_names: List[str]
    target_names: List[str]
    
    # Split distributions
    train_samples: int
    val_samples: int
    test_samples: int
    train_pct: float
    val_pct: float
    test_pct: float
    train_voyages: List[str]
    val_voyages: List[str]
    test_voyages: List[str]
    
    # Target distributions
    target_stats: Dict[str, Dict[str, float]]
    risk_class_distribution: Dict[str, int]
    safe_movement_counts: Dict[str, int]
    
    # Anti-leakage verification audit
    leakage_audit: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MLDatasetGenerator:
    """Pipeline generating supervised machine learning datasets from historical navigation data."""

    def __init__(
        self,
        feature_extractor: Optional[FeatureExtractor] = None,
        target_generator: Optional[TargetGenerator] = None,
        splitter: Optional[VoyageSplitter] = None,
        scale_features: bool = True,
        seed: int = 42,
    ):
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.target_generator = target_generator or TargetGenerator()
        self.splitter = splitter or VoyageSplitter(seed=seed)
        self.scale_features = scale_features
        self.seed = seed
        self.scaler: Optional[StandardScaler] = None

    def _points_to_dataframe(
        self,
        points: List[EnrichedAISFeaturePoint],
    ) -> pd.DataFrame:
        """Convert points into a tabular DataFrame with features, targets, and metadata."""
        if not points:
            return pd.DataFrame()

        rows: List[Dict[str, Any]] = []
        for p in points:
            f_vec = self.feature_extractor.extract(p)
            t_vec = self.target_generator.generate(p)
            
            row: Dict[str, Any] = {
                "vessel_id": p.vessel_id,
                "voyage_id": p.voyage_id,
                "timestamp": p.timestamp.isoformat() if p.timestamp else None,
            }
            # Append features
            row.update(f_vec.features)
            # Append targets
            row.update(t_vec.targets)
            rows.append(row)

        df = pd.DataFrame(rows)
        return df

    def generate_from_points(
        self,
        points: List[EnrichedAISFeaturePoint],
        output_dir: Optional[Path] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, DatasetSummary]:
        """Generate train, val, test datasets from in-memory enriched points.
        
        Args:
            points: List of EnrichedAISFeaturePoint observations.
            output_dir: Optional directory path to export CSVs and metadata.
            
        Returns:
            Tuple of (train_df, val_df, test_df, DatasetSummary)
        """
        if not points:
            raise ValueError("Cannot generate ML dataset from empty list of points")

        # 1. Voyage-level split (ZERO point-level leakage across splits)
        splits: DatasetSplits = self.splitter.split(points)
        splits.verify_zero_leakage()

        # 2. Build DataFrames for each split
        train_df = self._points_to_dataframe(splits.train_points)
        val_df = self._points_to_dataframe(splits.val_points)
        test_df = self._points_to_dataframe(splits.test_points)

        # 3. Fit Scaler STRICTLY on Train split only (Zero Distributional Leakage)
        scaler_params: Dict[str, Any] = {}
        if self.scale_features and not train_df.empty:
            self.scaler = StandardScaler()
            self.scaler.fit(train_df[FEATURE_NAMES].values)

            # Record fitted params
            scaler_params = {
                "mean": {feat: float(m) for feat, m in zip(FEATURE_NAMES, self.scaler.mean_)},
                "scale": {feat: float(s) for feat, s in zip(FEATURE_NAMES, self.scaler.scale_)},
                "fitted_on_split": "TRAIN_ONLY",
                "fitted_sample_count": len(train_df),
            }

            # Transform features
            scaled_train_vals = self.scaler.transform(train_df[FEATURE_NAMES].values)
            scaled_col_names = [f"scaled_{c}" for c in FEATURE_NAMES]
            
            for idx, col in enumerate(scaled_col_names):
                train_df[col] = scaled_train_vals[:, idx]

            if not val_df.empty:
                scaled_val_vals = self.scaler.transform(val_df[FEATURE_NAMES].values)
                for idx, col in enumerate(scaled_col_names):
                    val_df[col] = scaled_val_vals[:, idx]

            if not test_df.empty:
                scaled_test_vals = self.scaler.transform(test_df[FEATURE_NAMES].values)
                for idx, col in enumerate(scaled_col_names):
                    test_df[col] = scaled_test_vals[:, idx]

        # 4. Generate Comprehensive Statistics
        total_samples = len(points)
        all_voyages = {p.voyage_id for p in points if p.voyage_id}
        all_vessels = {p.vessel_id for p in points if p.vessel_id}

        # Target statistics across entire population
        combined_targets_df = pd.concat([train_df[TARGET_NAMES], val_df[TARGET_NAMES], test_df[TARGET_NAMES]]) if not train_df.empty else pd.DataFrame()
        
        target_stats: Dict[str, Dict[str, float]] = {}
        for t_col in TARGET_NAMES:
            if not combined_targets_df.empty and t_col in combined_targets_df.columns:
                target_stats[t_col] = {
                    "mean": float(combined_targets_df[t_col].mean()),
                    "std": float(combined_targets_df[t_col].std() or 0.0),
                    "min": float(combined_targets_df[t_col].min()),
                    "max": float(combined_targets_df[t_col].max()),
                    "median": float(combined_targets_df[t_col].median()),
                }

        # Category breakdowns
        risk_class_counts: Dict[str, int] = {
            "0_LOW": int((combined_targets_df["target_risk_class"] == 0).sum()) if not combined_targets_df.empty else 0,
            "1_MODERATE": int((combined_targets_df["target_risk_class"] == 1).sum()) if not combined_targets_df.empty else 0,
            "2_HIGH": int((combined_targets_df["target_risk_class"] == 2).sum()) if not combined_targets_df.empty else 0,
            "3_VERY_HIGH": int((combined_targets_df["target_risk_class"] == 3).sum()) if not combined_targets_df.empty else 0,
        }

        safe_mvmt_counts: Dict[str, int] = {
            "safe_1": int((combined_targets_df["target_safe_movement"] == 1.0).sum()) if not combined_targets_df.empty else 0,
            "risky_0": int((combined_targets_df["target_safe_movement"] == 0.0).sum()) if not combined_targets_df.empty else 0,
        }

        leakage_audit = {
            "train_val_voyage_overlap": list(splits.train_voyages.intersection(splits.val_voyages)),
            "train_test_voyage_overlap": list(splits.train_voyages.intersection(splits.test_voyages)),
            "val_test_voyage_overlap": list(splits.val_voyages.intersection(splits.test_voyages)),
            "zero_leakage_verified": (
                len(splits.train_voyages.intersection(splits.val_voyages)) == 0 and
                len(splits.train_voyages.intersection(splits.test_voyages)) == 0 and
                len(splits.val_voyages.intersection(splits.test_voyages)) == 0
            ),
            "scaler_training_split_only": True if self.scale_features else None,
            "split_strategy": splits.metadata.get("strategy", "voyage_split"),
        }

        summary = DatasetSummary(
            total_samples=total_samples,
            num_voyages=len(all_voyages),
            num_vessels=len(all_vessels),
            feature_count=len(FEATURE_NAMES),
            feature_names=FEATURE_NAMES,
            target_names=TARGET_NAMES,
            train_samples=len(train_df),
            val_samples=len(val_df),
            test_samples=len(test_df),
            train_pct=round(len(train_df) / total_samples * 100.0, 2) if total_samples > 0 else 0.0,
            val_pct=round(len(val_df) / total_samples * 100.0, 2) if total_samples > 0 else 0.0,
            test_pct=round(len(test_df) / total_samples * 100.0, 2) if total_samples > 0 else 0.0,
            train_voyages=sorted(list(splits.train_voyages)),
            val_voyages=sorted(list(splits.val_voyages)),
            test_voyages=sorted(list(splits.test_voyages)),
            target_stats=target_stats,
            risk_class_distribution=risk_class_counts,
            safe_movement_counts=safe_mvmt_counts,
            leakage_audit=leakage_audit,
        )

        # 5. Export to disk if output_dir specified
        if output_dir:
            out_p = Path(output_dir)
            out_p.mkdir(parents=True, exist_ok=True)

            train_df.to_csv(out_p / "train.csv", index=False)
            val_df.to_csv(out_p / "val.csv", index=False)
            test_df.to_csv(out_p / "test.csv", index=False)

            with open(out_p / "dataset_summary.json", "w", encoding="utf-8") as f:
                json.dump(summary.to_dict(), f, indent=2)

            if scaler_params:
                with open(out_p / "scaler_params.json", "w", encoding="utf-8") as f:
                    json.dump(scaler_params, f, indent=2)

            logger.info(f"Exported ML datasets and summary to {out_p}")

        return train_df, val_df, test_df, summary

    def generate_from_ais(
        self,
        ais_path: str,
        output_dir: Optional[Path] = None,
        replay_pipeline: Optional[EnvironmentalReplayPipeline] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, DatasetSummary]:
        """Generate ML datasets directly from raw/historical AIS files using replay pipeline."""
        pipeline = replay_pipeline or EnvironmentalReplayPipeline()
        points, _ = pipeline.process_file_or_dir(ais_path)
        return self.generate_from_points(points, output_dir=output_dir)
