"""Unit and integration tests for Phase 3: ML Training Dataset Generation.

Validates zero voyage data leakage, proper feature extraction and cyclical transformations,
aligned target derivation, and training-only feature scaler fitting.
"""

from datetime import datetime, timedelta
import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile

from src.environmental_replay.replay_schema import EnrichedAISFeaturePoint
from src.ml_dataset.feature_extractor import FeatureExtractor, FEATURE_NAMES, MLFeatureVector
from src.ml_dataset.target_generator import TargetGenerator, TARGET_NAMES, MLTargetVector
from src.ml_dataset.voyage_splitter import VoyageSplitter, DatasetSplits
from src.ml_dataset.dataset_generator import MLDatasetGenerator, DatasetSummary


def _create_synthetic_point(
    vessel_id: str,
    voyage_id: str,
    timestamp: datetime,
    lat: float = -65.0,
    lon: float = 140.0,
    speed: float = 12.0,
    sic: float = 0.20,
    depth: float = 1500.0,
    ib_dist: float = 40.0,
    risk_score: float = 0.25,
) -> EnrichedAISFeaturePoint:
    return EnrichedAISFeaturePoint(
        vessel_id=vessel_id,
        voyage_id=voyage_id,
        timestamp=timestamp,
        latitude=lat,
        longitude=lon,
        speed_knots=speed,
        heading_deg=180.0,
        course_deg=180.0,
        sic=sic,
        sic_percent=sic * 100.0,
        ice_classification="Open Drift Ice" if sic > 0.15 else "Open Water",
        iceberg_distance_km=ib_dist,
        bathymetry_depth_m=depth,
        is_shallow=(depth < 20.0),
        coastline_distance_km=50.0,
        is_on_land=False,
        ocean_current_speed_ms=0.3,
        sea_surface_temp_c=-1.2,
        wind_speed_ms=8.5,
        air_temp_c=-5.0,
        environmental_risk_score=risk_score,
        risk_class="LOW" if risk_score < 0.35 else "MODERATE",
    )


class TestFeatureExtractor:
    """Test feature engineering and cyclical encoding."""

    def test_feature_extraction_fields(self):
        extractor = FeatureExtractor()
        pt = _create_synthetic_point("VESSEL_A", "VOY_01", datetime(2023, 1, 15, 12, 0, 0))
        f_vec = extractor.extract(pt)

        assert isinstance(f_vec, MLFeatureVector)
        assert f_vec.vessel_id == "VESSEL_A"
        assert f_vec.voyage_id == "VOY_01"
        assert len(f_vec.features) == len(FEATURE_NAMES)

        # Check all expected feature names exist
        for name in FEATURE_NAMES:
            assert name in f_vec.features, f"Missing feature: {name}"

    def test_cyclical_and_boundary_encodings(self):
        extractor = FeatureExtractor()
        pt = _create_synthetic_point("VESSEL_A", "VOY_01", datetime(2023, 6, 21, 0, 0, 0), lat=-70.0, lon=120.0)
        f_vec = extractor.extract(pt)

        # Sin/cos bounds
        assert -1.0 <= f_vec.features["sin_lat"] <= 1.0
        assert -1.0 <= f_vec.features["cos_lat"] <= 1.0
        assert -1.0 <= f_vec.features["sin_lon"] <= 1.0
        assert -1.0 <= f_vec.features["cos_lon"] <= 1.0
        assert -1.0 <= f_vec.features["sin_day_of_year"] <= 1.0
        assert -1.0 <= f_vec.features["cos_day_of_year"] <= 1.0

        # WMO sea ice threshold flag
        assert f_vec.features["is_ice_covered"] == 1.0
        assert f_vec.features["has_iceberg_within_50km"] == 1.0


class TestTargetGenerator:
    """Test supervised target generation aligned with project optimization functions."""

    def test_target_generation_fields(self):
        generator = TargetGenerator()
        pt = _create_synthetic_point("VESSEL_A", "VOY_01", datetime(2023, 1, 15), risk_score=0.20, depth=1000.0, ib_dist=50.0)
        t_vec = generator.generate(pt)

        assert isinstance(t_vec, MLTargetVector)
        for name in TARGET_NAMES:
            assert name in t_vec.targets, f"Missing target: {name}"

        assert 0.0 <= t_vec.targets["target_risk_cost"] <= 1.0
        assert t_vec.targets["target_safe_movement"] == 1.0
        assert t_vec.targets["target_risk_class"] == 0.0  # LOW (< 0.35)

    def test_risky_condition_triggers_safe_movement_zero(self):
        generator = TargetGenerator(safe_risk_threshold=0.35, min_safe_depth_m=20.0, min_safe_iceberg_dist_km=15.0)

        # Case 1: Shallow water (< 20m)
        pt_shallow = _create_synthetic_point("V1", "VOY_01", datetime(2023, 1, 1), depth=15.0, risk_score=0.10)
        t_shallow = generator.generate(pt_shallow)
        assert t_shallow.targets["target_safe_movement"] == 0.0

        # Case 2: Iceberg within 15 km
        pt_iceberg = _create_synthetic_point("V1", "VOY_01", datetime(2023, 1, 1), depth=2000.0, ib_dist=8.0, risk_score=0.20)
        t_iceberg = generator.generate(pt_iceberg)
        assert t_iceberg.targets["target_safe_movement"] == 0.0

        # Case 3: High risk (> 0.35)
        pt_high_risk = _create_synthetic_point("V1", "VOY_01", datetime(2023, 1, 1), risk_score=0.65)
        t_high = generator.generate(pt_high_risk)
        assert t_high.targets["target_safe_movement"] == 0.0
        assert t_high.targets["target_risk_class"] == 2.0  # HIGH (0.60 to 0.80)


class TestVoyageSplitter:
    """Test strict voyage-level partitioning and anti-leakage verification."""

    def test_multi_voyage_zero_overlap(self):
        base_time = datetime(2023, 1, 1)
        points = []
        # Create 5 distinct voyages with 20 points each
        for v_idx in range(5):
            vid = f"VOYAGE_{v_idx:02d}"
            v_start = base_time + timedelta(days=v_idx * 30)
            for p_idx in range(20):
                points.append(_create_synthetic_point(
                    vessel_id="AURORA",
                    voyage_id=vid,
                    timestamp=v_start + timedelta(hours=p_idx * 2),
                ))

        splitter = VoyageSplitter(train_ratio=0.60, val_ratio=0.20, test_ratio=0.20)
        splits = splitter.split(points)

        assert splits.verify_zero_leakage() is True
        assert len(splits.train_voyages) > 0
        assert len(splits.val_voyages) > 0
        assert len(splits.test_voyages) > 0

        # CRITICAL TEST: Disjoint voyage sets
        assert len(splits.train_voyages.intersection(splits.val_voyages)) == 0
        assert len(splits.train_voyages.intersection(splits.test_voyages)) == 0
        assert len(splits.val_voyages.intersection(splits.test_voyages)) == 0

        # CRITICAL TEST: No point from a train voyage is present in test set
        test_points_vids = {p.voyage_id for p in splits.test_points}
        assert test_points_vids.isdisjoint(splits.train_voyages)

    def test_single_voyage_sequential_temporal_split(self):
        base_time = datetime(2023, 1, 1)
        points = [
            _create_synthetic_point("AURORA", "SINGLE_VOYAGE", base_time + timedelta(hours=i))
            for i in range(100)
        ]

        splitter = VoyageSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
        splits = splitter.split(points)

        assert splits.verify_zero_leakage() is True
        assert len(splits.train_points) == 70
        assert len(splits.val_points) == 15
        assert len(splits.test_points) == 15

        # Check temporal order: train timestamps < val timestamps < test timestamps
        max_train_ts = max(p.timestamp for p in splits.train_points)
        min_val_ts = min(p.timestamp for p in splits.val_points)
        max_val_ts = max(p.timestamp for p in splits.val_points)
        min_test_ts = min(p.timestamp for p in splits.test_points)

        assert max_train_ts <= min_val_ts
        assert max_val_ts <= min_test_ts


class TestMLDatasetGenerator:
    """Test full dataset generation orchestration, scaler fitting on train-only, and exports."""

    def test_dataset_generation_and_scaler_train_only(self):
        base_time = datetime(2023, 1, 1)
        points = []
        for v_idx in range(4):
            vid = f"EXPEDITION_{v_idx}"
            v_start = base_time + timedelta(days=v_idx * 40)
            for p_idx in range(25):
                points.append(_create_synthetic_point(
                    vessel_id=f"VESSEL_{v_idx % 2}",
                    voyage_id=vid,
                    timestamp=v_start + timedelta(hours=p_idx * 3),
                    speed=10.0 + p_idx * 0.2,
                    sic=0.10 * v_idx,
                ))

        generator = MLDatasetGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            train_df, val_df, test_df, summary = generator.generate_from_points(points, output_dir=out_dir)

            # 1. Output files exist
            assert (out_dir / "train.csv").exists()
            assert (out_dir / "val.csv").exists()
            assert (out_dir / "test.csv").exists()
            assert (out_dir / "dataset_summary.json").exists()
            assert (out_dir / "scaler_params.json").exists()

            # 2. DataFrame shapes and columns
            assert not train_df.empty
            assert not test_df.empty
            for feat in FEATURE_NAMES:
                assert feat in train_df.columns
                assert f"scaled_{feat}" in train_df.columns
            for tgt in TARGET_NAMES:
                assert tgt in train_df.columns

            # 3. Scaler was fitted strictly on Train split
            with open(out_dir / "scaler_params.json") as f:
                s_params = json.load(f)
            assert s_params["fitted_on_split"] == "TRAIN_ONLY"
            assert s_params["fitted_sample_count"] == len(train_df)

            # Scaled train features have mean close to 0 and std close to 1
            scaled_speed_train = train_df["scaled_speed_knots"].values
            assert np.isclose(scaled_speed_train.mean(), 0.0, atol=1e-2)
            assert np.isclose(scaled_speed_train.std(), 1.0, atol=1e-2)

            # 4. Summary verification
            assert summary.total_samples == len(points)
            assert summary.leakage_audit["zero_leakage_verified"] is True
            assert summary.leakage_audit["train_test_voyage_overlap"] == []

    def test_reproducibility(self):
        base_time = datetime(2023, 1, 1)
        points = [
            _create_synthetic_point("AURORA", f"VOY_{i // 20}", base_time + timedelta(hours=i))
            for i in range(60)
        ]

        gen1 = MLDatasetGenerator(seed=123)
        train1, val1, test1, _ = gen1.generate_from_points(points)

        gen2 = MLDatasetGenerator(seed=123)
        train2, val2, test2, _ = gen2.generate_from_points(points)

        pd.testing.assert_frame_equal(train1, train2)
        pd.testing.assert_frame_equal(test1, test2)
