"""Dynamic Cost Surface Engine (PolarNav Phase 10).

Translates Live Multi-Sensor Maritime Telemetry (CurrentMaritimeState) +
Vessel-Aware ML Risk Engine into a dynamic, physics-informed, multi-objective
traversal cost surface across BALANCED, SAFEST, and FASTEST operational profiles.
"""
import math
from typing import Dict, Tuple, Optional, Any
import numpy as np

from ..state import maritime_state_manager, CurrentMaritimeState
from ..ml_risk.engine import vessel_ml_risk_engine
from ..ml_risk.models import VesselCharacteristics, RiskCategory
from ..bathymetry import navigation_geometry_service
from .models import (
    RouteProfileType,
    RouteProfileConfig,
)


# Canonical Profile Configurations
PROFILE_CONFIGS: Dict[RouteProfileType, RouteProfileConfig] = {
    RouteProfileType.BALANCED: RouteProfileConfig(
        profile_type=RouteProfileType.BALANCED,
        name="Route B — Optimal AI Balanced Corridor",
        description="Pareto-optimal balance between arrival time, fuel burn, and environmental risk.",
        w_distance=1.0,
        w_time=1.5,
        w_risk=2.5,
        w_sic=2.0,
        w_iceberg=3.5,
        w_weather=1.0,
        w_current=1.0,
        w_fuel=1.2,
        max_allowed_sic=75.0,
        min_iceberg_clearance_km=15.0,
        min_under_keel_clearance_m=2.0,
        lateral_bias=2.0,
    ),
    RouteProfileType.SAFEST: RouteProfileConfig(
        profile_type=RouteProfileType.SAFEST,
        name="Route C — Safest Marginal Ice Zone Standoff",
        description="Maximizes ice/iceberg clearance, marginal ice zone standoff, and avoids rough seas.",
        w_distance=0.5,
        w_time=0.8,
        w_risk=6.0,
        w_sic=5.0,
        w_iceberg=7.0,
        w_weather=3.0,
        w_current=0.5,
        w_fuel=1.0,
        max_allowed_sic=45.0,
        min_iceberg_clearance_km=25.0,
        min_under_keel_clearance_m=5.0,
        lateral_bias=5.5,
    ),
    RouteProfileType.FASTEST: RouteProfileConfig(
        profile_type=RouteProfileType.FASTEST,
        name="Route A — Direct Ice-Constrained Transit",
        description="Prioritizes minimum distance and transit time within vessel structural limits.",
        w_distance=2.5,
        w_time=3.0,
        w_risk=1.0,
        w_sic=0.8,
        w_iceberg=1.5,
        w_weather=0.6,
        w_current=1.5,
        w_fuel=0.8,
        max_allowed_sic=90.0,
        min_iceberg_clearance_km=8.0,
        min_under_keel_clearance_m=1.0,
        lateral_bias=0.2,
    ),
}


class DynamicCostSurface:
    """Computes dynamic traversal cost over spatial cells by coupling
    CurrentMaritimeState, VesselCharacteristics, and ML Risk Engine.
    """

    def __init__(self):
        self._cell_cache: Dict[Tuple[float, float, str], float] = {}

    def clear_cache(self):
        """Clear spatial evaluation memoization cache."""
        self._cell_cache.clear()

    def evaluate_cost(
        self,
        lat: float,
        lon: float,
        profile: RouteProfileConfig,
        vessel: VesselCharacteristics,
        dest_lat: float,
        dest_lon: float,
    ) -> Tuple[float, Optional[CurrentMaritimeState], Optional[Any]]:
        """Evaluate the objective traversal cost multiplier for a node.
        
        Returns:
            (cost_multiplier, state, ml_prediction)
            If the point is unnavigable (land, shallow water, draft breach), returns (inf, None, None).
        """
        cache_key = (round(lat, 2), round(lon, 2), profile.profile_type.value)
        if cache_key in self._cell_cache:
            cost = self._cell_cache[cache_key]
            return cost, None, None

        # 1. Hard Static Geometry Feasibility Checks
        # Never traverse land or violate minimal draft clearance
        if navigation_geometry_service.is_land(lat, lon):
            self._cell_cache[cache_key] = float('inf')
            return float('inf'), None, None

        depth = navigation_geometry_service.get_depth(lat, lon)
        ukc = depth - vessel.draft_m
        if ukc <= 0.0 or not navigation_geometry_service.is_navigable(
            lat, lon, vessel.draft_m, min_clearance_m=profile.min_under_keel_clearance_m
        ):
            self._cell_cache[cache_key] = float('inf')
            return float('inf'), None, None

        # 2. Ingest Live Maritime Multi-Sensor State
        state = maritime_state_manager.get_current_state(lat=lat, lon=lon)
        cell = state.cell_state

        # 3. Predict Real-Time ML Navigation Risk (Never AIS coordinates)
        ml_pred = vessel_ml_risk_engine.predict_risk(state, vessel)

        # Grounding or Prohibited Risk immediately makes cell non-viable
        if ml_pred.risk_category == RiskCategory.PROHIBITED or not ml_pred.safe_to_proceed:
            if profile.profile_type == RouteProfileType.SAFEST:
                self._cell_cache[cache_key] = float('inf')
                return float('inf'), state, ml_pred

        # 4. Compute Factorized Profile Cost Multipliers
        sic_pct = float(cell.sic)
        wind_kn = float(cell.wind.speed_knots)
        wave_m = float(cell.wave.height_m)

        # SIC Penalty
        if profile.profile_type == RouteProfileType.SAFEST:
            if sic_pct > 10.0:
                sic_penalty = 1.0 + ((sic_pct / 100.0) ** 2) * profile.w_sic * 8.0
                if sic_pct > profile.max_allowed_sic:
                    excess = (sic_pct - profile.max_allowed_sic) / 10.0
                    sic_penalty += (excess ** 2) * 50.0
            else:
                sic_penalty = 1.0
        elif profile.profile_type == RouteProfileType.FASTEST:
            sic_penalty = 1.0 + ((sic_pct / 100.0) ** 2) * profile.w_sic * 1.5
            if sic_pct > profile.max_allowed_sic:
                excess = (sic_pct - profile.max_allowed_sic) / 10.0
                sic_penalty += (excess ** 2) * 20.0
        else:  # BALANCED
            sic_penalty = 1.0 + ((sic_pct / 100.0) ** 2) * profile.w_sic * 3.0
            if sic_pct > profile.max_allowed_sic:
                excess = (sic_pct - profile.max_allowed_sic) / 10.0
                sic_penalty += (excess ** 2) * 35.0

        # Iceberg Penalty
        if cell.iceberg_risk > 0.0:
            ib_penalty = 1.0 + (cell.iceberg_risk * profile.w_iceberg * 4.0)
        else:
            ib_penalty = 1.0

        # Weather Penalty (Wind & Waves)
        weather_penalty = 1.0 + (
            (wave_m / 4.0) ** 2 * profile.w_weather * 1.5 +
            (wind_kn / 40.0) ** 2 * profile.w_weather * 1.0
        )

        # ML Risk Penalty
        ml_risk_penalty = 1.0 + (ml_pred.risk_score * profile.w_risk * 3.5)

        # Composite cell traversal cost multiplier
        total_cell_mult = (
            profile.w_distance * 1.0 +
            ml_risk_penalty +
            sic_penalty +
            ib_penalty +
            weather_penalty
        )

        self._cell_cache[cache_key] = total_cell_mult
        return total_cell_mult, state, ml_pred

    def evaluate_fast_cost(
        self,
        lat: float,
        lon: float,
        profile: RouteProfileConfig,
        vessel: VesselCharacteristics,
    ) -> float:
        """Sub-millisecond cell cost evaluation used in A* graph search."""
        cache_key = (round(lat, 2), round(lon, 2), profile.profile_type.value)
        if cache_key in self._cell_cache:
            return self._cell_cache[cache_key]

        # 1. Hard static geometry feasibility
        if navigation_geometry_service.is_land(lat, lon):
            self._cell_cache[cache_key] = float('inf')
            return float('inf')

        depth = navigation_geometry_service.get_depth(lat, lon)
        ukc = depth - vessel.draft_m
        if ukc <= 0.0 or not navigation_geometry_service.is_navigable(
            lat, lon, vessel.draft_m, min_clearance_m=profile.min_under_keel_clearance_m
        ):
            self._cell_cache[cache_key] = float('inf')
            return float('inf')

        # 2. Fast Sea Ice from pre-warmed KDTree
        from ..sea_ice import sea_ice_service
        sic_tree = getattr(sea_ice_service, "_current_tree", None)
        sic_arr = getattr(sea_ice_service, "_current_sic", None)
        if sic_tree is not None and sic_arr is not None:
            _, idx = sic_tree.query([lon, lat])
            sic_pct = float(sic_arr[idx]) * 100.0
        else:
            sic_pct = 0.0

        # 3. Fast Iceberg Standoff
        from ..iceberg import iceberg_monitoring_service
        ib_tree = getattr(iceberg_monitoring_service, "_kdtree", None)
        if ib_tree is not None:
            dist_deg, _ = ib_tree.query([lat, lon])
            ib_dist_km = dist_deg * 111.0
        else:
            ib_dist_km = 999.0

        # 4. Profile penalties
        if profile.profile_type == RouteProfileType.SAFEST:
            lat_standoff = max(0.0, (-lat - 61.0)) * 1.2
            if sic_pct > 5.0:
                sic_penalty = 1.0 + ((sic_pct / 100.0) ** 2) * profile.w_sic * 12.0 + lat_standoff * 3.0
                if sic_pct > profile.max_allowed_sic:
                    excess = (sic_pct - profile.max_allowed_sic) / 10.0
                    sic_penalty += (excess ** 2) * 60.0
            else:
                sic_penalty = 1.0 + lat_standoff
        elif profile.profile_type == RouteProfileType.BALANCED:
            lat_standoff = max(0.0, (-lat - 62.0)) * 0.4
            sic_penalty = 1.0 + ((sic_pct / 100.0) ** 2) * profile.w_sic * 3.0 + lat_standoff
            if sic_pct > profile.max_allowed_sic:
                excess = (sic_pct - profile.max_allowed_sic) / 10.0
                sic_penalty += (excess ** 2) * 35.0
        else:  # FASTEST
            sic_penalty = 1.0 + ((sic_pct / 100.0) ** 2) * profile.w_sic * 0.8
            if sic_pct > profile.max_allowed_sic:
                excess = (sic_pct - profile.max_allowed_sic) / 10.0
                sic_penalty += (excess ** 2) * 20.0

        if ib_dist_km < profile.min_iceberg_clearance_km:
            ib_penalty = 1.0 + (math.exp(-0.5 * (ib_dist_km / (profile.min_iceberg_clearance_km * 0.4)) ** 2) * 25.0 * profile.w_iceberg)
        else:
            ib_penalty = 1.0

        total_mult = profile.w_distance * 1.0 + sic_penalty + ib_penalty
        self._cell_cache[cache_key] = total_mult
        return total_mult


# Global singleton instance
dynamic_cost_surface = DynamicCostSurface()

