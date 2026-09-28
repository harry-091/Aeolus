"""Target Generator for Phase 3 ML Training Dataset.

Generates ground-truth supervised targets directly aligned with the project's existing
cost function (src/optimization/cost_function.py) and risk engine (src/risk/risk_engine.py).
"""

from dataclasses import dataclass, asdict
import math
from typing import Dict, List, Any, Optional

from src.environmental_replay.replay_schema import EnrichedAISFeaturePoint


TARGET_NAMES = [
    "target_risk_cost",          # Continuous navigation risk cost [0.0, 1.0]
    "target_safe_movement",       # Binary safe (1) vs risky (0) movement classification
    "target_risk_class",          # Discrete risk category: 0=LOW, 1=MODERATE, 2=HIGH, 3=VERY_HIGH
    "target_speed_efficiency",    # Operational speed efficiency ratio [0.0, 1.0] (SOG / nominal 14 knots)
]


@dataclass
class MLTargetVector:
    """Supervised learning targets for a single trajectory observation."""
    targets: Dict[str, float]
    vessel_id: str
    voyage_id: str

    def to_list(self) -> List[float]:
        """Return target values in fixed, deterministic order."""
        return [self.targets.get(name, 0.0) for name in TARGET_NAMES]

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of targets."""
        res = {
            "vessel_id": self.vessel_id,
            "voyage_id": self.voyage_id,
        }
        res.update(self.targets)
        return res


class TargetGenerator:
    """Computes reproducible ground-truth targets derived from project navigation rules."""

    def __init__(
        self,
        nominal_speed_knots: float = 14.0,
        safe_risk_threshold: float = 0.35,
        min_safe_depth_m: float = 20.0,
        min_safe_iceberg_dist_km: float = 15.0,
    ):
        self.nominal_speed_knots = nominal_speed_knots
        self.safe_risk_threshold = safe_risk_threshold
        self.min_safe_depth_m = min_safe_depth_m
        self.min_safe_iceberg_dist_km = min_safe_iceberg_dist_km

    def generate(self, point: EnrichedAISFeaturePoint) -> MLTargetVector:
        """Derive supervised navigation targets for a single point.
        
        Args:
            point: EnrichedAISFeaturePoint
            
        Returns:
            MLTargetVector
        """
        targets: Dict[str, float] = {}

        # 1. target_risk_cost: Normalized multi-objective navigation hazard [0.0, 1.0]
        # Uses environmental_risk_score if computed; else aligns with risk_engine weights
        if point.environmental_risk_score is not None and point.environmental_risk_score > 0.0:
            risk_cost = float(point.environmental_risk_score)
        else:
            # Fallback computation aligned with risk_engine.py weights (SIC: 0.50, Iceberg: 0.25, Bathy: 0.15, Coast: 0.10)
            sic_val = max(0.0, min(1.0, float(point.sic or 0.0)))
            
            # Iceberg proximity penalty
            ib_dist = point.iceberg_distance_km if point.iceberg_distance_km is not None else 200.0
            ib_hazard = max(0.0, min(1.0, 1.0 - (ib_dist / 100.0)))
            
            # Shallow water penalty
            depth = float(point.bathymetry_depth_m or 3500.0)
            depth_hazard = 1.0 if depth < 20.0 else (0.5 if depth < 100.0 else 0.0)
            
            # Coastline hazard
            coast_dist = float(point.coastline_distance_km or 100.0)
            coast_hazard = 1.0 if (point.is_on_land or coast_dist < 5.0) else max(0.0, min(1.0, 1.0 - (coast_dist / 50.0)))

            risk_cost = (
                0.50 * sic_val +
                0.25 * ib_hazard +
                0.15 * depth_hazard +
                0.10 * coast_hazard
            )

        risk_cost = max(0.0, min(1.0, risk_cost))
        targets["target_risk_cost"] = round(risk_cost, 4)

        # 2. target_risk_class: Integer classes per risk_engine.py
        # 0=LOW (<0.35), 1=MODERATE (0.35 - 0.60), 2=HIGH (0.60 - 0.80), 3=VERY_HIGH (>=0.80)
        if risk_cost < 0.35:
            risk_class = 0
        elif risk_cost < 0.60:
            risk_class = 1
        elif risk_cost < 0.80:
            risk_class = 2
        else:
            risk_class = 3
        targets["target_risk_class"] = float(risk_class)

        # 3. target_safe_movement: Binary 1 (Safe) vs 0 (Risky)
        depth = float(point.bathymetry_depth_m or 3500.0)
        ib_dist = point.iceberg_distance_km if point.iceberg_distance_km is not None else 200.0
        
        is_safe = (
            (risk_cost < self.safe_risk_threshold) and
            (depth >= self.min_safe_depth_m) and
            (ib_dist >= self.min_safe_iceberg_dist_km) and
            (not point.is_on_land)
        )
        targets["target_safe_movement"] = 1.0 if is_safe else 0.0

        # 4. target_speed_efficiency: Observed speed vs nominal polar cruise speed
        sog = float(point.speed_knots or 0.0)
        speed_ratio = max(0.0, min(1.0, sog / self.nominal_speed_knots))
        targets["target_speed_efficiency"] = round(speed_ratio, 4)

        return MLTargetVector(
            targets=targets,
            vessel_id=point.vessel_id,
            voyage_id=point.voyage_id,
        )

    def generate_batch(self, points: List[EnrichedAISFeaturePoint]) -> List[MLTargetVector]:
        """Batch generate targets for points."""
        return [self.generate(p) for p in points]
