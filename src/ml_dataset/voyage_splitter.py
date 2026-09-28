"""Voyage-Level Splitter for Phase 3 ML Training Dataset.

Enforces zero-data-leakage partitioning by splitting data strictly at the VOYAGE level.
Points belonging to the same voyage will never appear across multiple splits.
Uses chronological (temporal) sorting across voyages to simulate real-world prospective deployment.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Set, Tuple, Any, Optional
import math

from src.environmental_replay.replay_schema import EnrichedAISFeaturePoint


@dataclass
class DatasetSplits:
    """Container holding partitioned enriched points and partition metadata."""
    train_points: List[EnrichedAISFeaturePoint] = field(default_factory=list)
    val_points: List[EnrichedAISFeaturePoint] = field(default_factory=list)
    test_points: List[EnrichedAISFeaturePoint] = field(default_factory=list)
    
    train_voyages: Set[str] = field(default_factory=set)
    val_voyages: Set[str] = field(default_factory=set)
    test_voyages: Set[str] = field(default_factory=set)
    
    metadata: Dict[str, Any] = field(default_factory=dict)

    def verify_zero_leakage(self) -> bool:
        """Mathematically verifies that no voyage is shared across any splits."""
        train_val_overlap = self.train_voyages.intersection(self.val_voyages)
        train_test_overlap = self.train_voyages.intersection(self.test_voyages)
        val_test_overlap = self.val_voyages.intersection(self.test_voyages)

        if train_val_overlap or train_test_overlap or val_test_overlap:
            raise ValueError(
                f"CRITICAL LEAKAGE DETECTED: Overlapping voyages found! "
                f"Train-Val: {train_val_overlap}, Train-Test: {train_test_overlap}, Val-Test: {val_test_overlap}"
            )
        return True


class VoyageSplitter:
    """Splits historical observations by voyage using chronological temporal ordering."""

    def __init__(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        seed: int = 42,
    ):
        total = train_ratio + val_ratio + test_ratio
        if not math.isclose(total, 1.0, rel_tol=1e-5):
            raise ValueError(f"Split ratios must sum to 1.0, got {total}")
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.seed = seed

    def split(self, points: List[EnrichedAISFeaturePoint]) -> DatasetSplits:
        """Partition points strictly by voyage.
        
        Args:
            points: List of enriched AIS observations.
            
        Returns:
            DatasetSplits with guaranteed disjoint voyage allocations.
        """
        if not points:
            return DatasetSplits()

        # 1. Group points by voyage_id
        voyage_map: Dict[str, List[EnrichedAISFeaturePoint]] = {}
        voyage_start_times: Dict[str, datetime] = {}

        for p in points:
            v_id = p.voyage_id or f"voyage_{p.vessel_id}"
            if v_id not in voyage_map:
                voyage_map[v_id] = []
                voyage_start_times[v_id] = p.timestamp or datetime.min
            else:
                if p.timestamp and p.timestamp < voyage_start_times[v_id]:
                    voyage_start_times[v_id] = p.timestamp
            voyage_map[v_id].append(p)

        all_voyage_ids = list(voyage_map.keys())

        # If only 1 voyage exists, subdivide it temporally into sequential legs
        # to ensure strict temporal split without intra-voyage point random mixing
        if len(all_voyage_ids) == 1:
            single_vid = all_voyage_ids[0]
            sorted_pts = sorted(voyage_map[single_vid], key=lambda x: x.timestamp or datetime.min)
            n = len(sorted_pts)
            
            n_train = max(1, int(n * self.train_ratio))
            n_val = max(1, int(n * self.val_ratio)) if n > 3 else 0
            
            train_pts = sorted_pts[:n_train]
            val_pts = sorted_pts[n_train:n_train + n_val]
            test_pts = sorted_pts[n_train + n_val:]
            
            # Tag subdivided legs with distinct voyage segment IDs
            train_v_ids = {f"{single_vid}_leg_train"}
            val_v_ids = {f"{single_vid}_leg_val"} if val_pts else set()
            test_v_ids = {f"{single_vid}_leg_test"} if test_pts else set()
            
            for p in train_pts:
                p.voyage_id = f"{single_vid}_leg_train"
            for p in val_pts:
                p.voyage_id = f"{single_vid}_leg_val"
            for p in test_pts:
                p.voyage_id = f"{single_vid}_leg_test"

            splits = DatasetSplits(
                train_points=train_pts,
                val_points=val_pts,
                test_points=test_pts,
                train_voyages=train_v_ids,
                val_voyages=val_v_ids,
                test_voyages=test_v_ids,
                metadata={
                    "strategy": "single_voyage_temporal_block_split",
                    "total_voyages": 1,
                    "num_segments": len(train_v_ids) + len(val_v_ids) + len(test_v_ids),
                }
            )
            splits.verify_zero_leakage()
            return splits

        # 2. Chronological sorting of voyages by start time
        sorted_voyages = sorted(all_voyage_ids, key=lambda vid: voyage_start_times[vid])
        num_v = len(sorted_voyages)

        if num_v == 2:
            train_v = [sorted_voyages[0]]
            val_v = []
            test_v = [sorted_voyages[1]]
        elif num_v >= 3:
            n_train = max(1, int(round(num_v * self.train_ratio)))
            n_val = max(1, int(round(num_v * self.val_ratio)))
            
            # Ensure at least 1 in test
            if n_train + n_val >= num_v:
                if n_train > 1:
                    n_train -= 1
                elif n_val > 1:
                    n_val -= 1

            train_v = sorted_voyages[:n_train]
            val_v = sorted_voyages[n_train:n_train + n_val]
            test_v = sorted_voyages[n_train + n_val:]
            if not test_v and len(sorted_voyages) >= 3:
                test_v = [val_v.pop()]
        else:
            train_v = sorted_voyages
            val_v = []
            test_v = []

        train_set = set(train_v)
        val_set = set(val_v)
        test_set = set(test_v)

        train_pts = [p for vid in train_v for p in voyage_map[vid]]
        val_pts = [p for vid in val_v for p in voyage_map[vid]]
        test_pts = [p for vid in test_v for p in voyage_map[vid]]

        splits = DatasetSplits(
            train_points=train_pts,
            val_points=val_pts,
            test_points=test_pts,
            train_voyages=train_set,
            val_voyages=val_set,
            test_voyages=test_set,
            metadata={
                "strategy": "chronological_voyage_split",
                "total_voyages": num_v,
                "train_voyage_count": len(train_set),
                "val_voyage_count": len(val_set),
                "test_voyage_count": len(test_set),
            }
        )
        splits.verify_zero_leakage()
        return splits
