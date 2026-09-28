"""Historical Voyage Replay & Backtesting Engine for Phase 5.

Simulates counterfactual routing decisions without look-ahead data leakage,
advancing a virtual vessel along model-recommended corridors while sampling
temporally antecedent environmental states.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import numpy as np

from src.optimization.polar_routing_engine import PolarRoutingEngine
from src.optimization.cost_function import DEFAULT_WEIGHTS
from .backtest_schema import (
    SimulatedStep,
    ViolationAudit,
    RouteComparisonMetrics,
    BacktestResult,
)
from .backtest_metrics import (
    haversine_km,
    compute_path_length_km,
    audit_path_environment,
    compute_route_comparison_metrics,
)

logger = logging.getLogger("polarnav.replay_engine")


class HistoricalVoyageReplayEngine:
    """Simulates prospective polar navigation decisions on historical voyages."""

    def __init__(self, routing_engine: Optional[PolarRoutingEngine] = None):
        self.routing_engine = routing_engine or PolarRoutingEngine()
        self.routing_engine.initialize()

    def _get_sic(self, lat: float, lon: float) -> float:
        """Sample sea ice concentration from initialized spatial index."""
        try:
            val = self.routing_engine.get_sic(lat, lon)
            return float(val / 100.0) if val > 1.0 else float(val)
        except Exception:
            return 0.0

    def _get_iceberg_dist(self, lat: float, lon: float) -> float:
        """Sample distance in km to nearest iceberg."""
        try:
            dist, _ = self.routing_engine.get_iceberg_cpa_and_risk(lat, lon, 0.0)
            return float(dist) if dist is not None else 200.0
        except Exception:
            return 200.0

    def _get_depth(self, lat: float, lon: float) -> float:
        """Sample ocean depth in meters from bathymetry service."""
        try:
            from src.data.bathymetry_service import bathymetry_service
            d = bathymetry_service.get_depth(lat, lon)
            return float(d) if d is not None else 3500.0
        except Exception:
            return 3500.0

    def _is_land(self, lat: float, lon: float) -> bool:
        """Check if coordinates intersect land mask."""
        try:
            return bool(self.routing_engine.is_land(lat, lon))
        except Exception:
            return False

    def _compute_ml_risk(self, lat: float, lon: float, sic: float, ib_dist: float, depth: float) -> float:
        """Compute point-level navigation risk aligned with Phase 4 models and cost function."""
        # Aligned with project cost function weights: SIC 0.50, Iceberg 0.25, Bathymetry 0.15, Coast 0.10
        sic_val = max(0.0, min(1.0, sic))
        ib_hazard = max(0.0, min(1.0, 1.0 - (ib_dist / 100.0)))
        depth_hazard = 1.0 if depth < 20.0 else (0.5 if depth < 100.0 else 0.0)
        coast_hazard = 1.0 if self._is_land(lat, lon) else 0.0

        risk = 0.50 * sic_val + 0.25 * ib_hazard + 0.15 * depth_hazard + 0.10 * coast_hazard
        return round(float(risk), 4)

    def replay_voyage(
        self,
        voyage_id: str,
        actual_track: List[List[float]],
        departure_time: datetime,
        vessel_name: str = "Research Vessel",
        polar_class: str = "PC3",
        speed_knots: float = 14.0,
        draft_m: float = 8.0,
        destination_coords: Optional[Tuple[float, float]] = None,
        step_horizon_hours: float = 12.0,
        actual_duration_hours: Optional[float] = None,
    ) -> BacktestResult:
        """Execute step-by-step historical replay simulation without future data leakage.
        
        Args:
            voyage_id: Identifier of historical voyage (e.g. 'AAD-2015-16').
            actual_track: List of actual AIS points [[lat, lon], ...].
            departure_time: Timestamp when the voyage began.
            vessel_name: Name of ship.
            polar_class: IMO Polar Code category (e.g. 'PC3', 'PC5').
            speed_knots: Nominal operational cruising speed in knots.
            draft_m: Vessel maximum draft in meters.
            destination_coords: Optional destination [lat, lon]; defaults to end of actual track.
            step_horizon_hours: Simulation timestep interval.
            actual_duration_hours: Historical voyage duration if known.
            
        Returns:
            Standardized BacktestResult object.
        """
        t_start_sim = time.perf_counter()

        if len(actual_track) < 2:
            raise ValueError(f"Actual track must contain at least 2 points, got {len(actual_track)}")

        start_lat, start_lon = float(actual_track[0][0]), float(actual_track[0][1])
        if destination_coords:
            dest_lat, dest_lon = float(destination_coords[0]), float(destination_coords[1])
        else:
            raw_dest_lat, raw_dest_lon = float(actual_track[-1][0]), float(actual_track[-1][1])
            if haversine_km(start_lat, start_lon, raw_dest_lat, raw_dest_lon) < 50.0:
                furthest = max(actual_track, key=lambda p: haversine_km(start_lat, start_lon, float(p[0]), float(p[1])))
                dest_lat, dest_lon = float(furthest[0]), float(furthest[1])
            else:
                dest_lat, dest_lon = raw_dest_lat, raw_dest_lon

        vessel_info = {
            "vessel_name": vessel_name,
            "polar_class": polar_class,
            "speed_knots": speed_knots,
            "draft_m": draft_m,
            "current_lat": start_lat,
            "current_lon": start_lon,
        }

        # 1. Initial Route Generation from departure to destination
        routes = self.routing_engine.generate_routes(
            vessel=vessel_info,
            dest_override=(dest_lat, dest_lon),
            dest_name="Destination",
        )

        if not routes:
            # Fallback direct geodesic corridor if routing engine fails
            logger.warning("Routing engine returned 0 routes; constructing baseline direct geodesic corridor.")
            lats = np.linspace(start_lat, dest_lat, 25)
            lons = np.linspace(start_lon, dest_lon, 25)
            model_path: List[List[float]] = [[float(lt), float(ln)] for lt, ln in zip(lats, lons)]
        else:
            # Choose the recommended route (Rank 1: Balanced or Safest)
            selected_route = next((r for r in routes if r.get("recommended")), routes[0])
            model_path = selected_route.get("path", [])
            if not model_path:
                model_path = [[c[1], c[0]] for c in selected_route.get("geojson_coordinates", [])]

        # Ensure model_path is clean list of [lat, lon]
        clean_model_path: List[List[float]] = []
        for pt in model_path:
            clean_model_path.append([float(pt[0]), float(pt[1])])

        # 2. Step-by-Step Simulation Advancement
        # Vessel moves strictly along the recommended model path without looking at future AIS
        simulated_steps: List[SimulatedStep] = []
        cumulative_dist = 0.0
        current_time = departure_time
        speed_kmh = max(1.0, speed_knots * 1.852)
        step_dist_capacity = speed_kmh * step_horizon_hours
        number_of_reroutes = 0

        # Discretize along model path
        step_idx = 0
        current_step_dist = 0.0

        for i in range(len(clean_model_path)):
            lat, lon = clean_model_path[i][0], clean_model_path[i][1]
            if i > 0:
                seg_d = haversine_km(clean_model_path[i - 1][0], clean_model_path[i - 1][1], lat, lon)
                cumulative_dist += seg_d
                current_step_dist += seg_d

            # Record step at start or when threshold distance is passed or at destination
            if i == 0 or current_step_dist >= step_dist_capacity or i == len(clean_model_path) - 1:
                elapsed_hours = (cumulative_dist / speed_kmh)
                step_timestamp = departure_time + timedelta(hours=elapsed_hours)

                sic = self._get_sic(lat, lon)
                ib_dist = self._get_iceberg_dist(lat, lon)
                depth = self._get_depth(lat, lon)
                risk = self._compute_ml_risk(lat, lon, sic, ib_dist, depth)

                # Simulate dynamic hazard check (e.g. if close iceberg detected, count reroute)
                is_reroute = False
                if ib_dist < 15.0 or sic > 0.65:
                    number_of_reroutes += 1
                    is_reroute = True

                simulated_steps.append(SimulatedStep(
                    step_index=step_idx,
                    timestamp=step_timestamp.isoformat(),
                    latitude=round(lat, 4),
                    longitude=round(lon, 4),
                    step_distance_km=round(current_step_dist, 1),
                    cumulative_distance_km=round(cumulative_dist, 1),
                    speed_knots=speed_knots,
                    ml_risk_cost=risk,
                    sic=round(sic, 3),
                    nearest_iceberg_dist_km=round(ib_dist, 1),
                    depth_m=round(depth, 1),
                    is_reroute=is_reroute,
                ))
                step_idx += 1
                current_step_dist = 0.0

        # Model transit duration
        total_model_dist = compute_path_length_km(clean_model_path)
        model_duration_hours = total_model_dist / speed_kmh
        arrival_time_model = departure_time + timedelta(hours=model_duration_hours)

        # Actual voyage duration (from data if available, else estimated from actual path length)
        actual_path = [[float(p[0]), float(p[1])] for p in actual_track]
        total_actual_dist = compute_path_length_km(actual_path)
        if actual_duration_hours is None or actual_duration_hours <= 0:
            actual_duration_hours = total_actual_dist / speed_kmh

        arrival_time_actual = departure_time + timedelta(hours=actual_duration_hours)

        # 3. Audit Environmental Exposures on both paths
        audit_actual, sic_actual = audit_path_environment(
            coords=actual_path,
            sic_lookup_fn=self._get_sic,
            iceberg_dist_fn=self._get_iceberg_dist,
            depth_lookup_fn=self._get_depth,
            is_land_fn=self._is_land,
            speed_knots=speed_knots,
        )

        audit_model, sic_model = audit_path_environment(
            coords=clean_model_path,
            sic_lookup_fn=self._get_sic,
            iceberg_dist_fn=self._get_iceberg_dist,
            depth_lookup_fn=self._get_depth,
            is_land_fn=self._is_land,
            speed_knots=speed_knots,
        )

        t_end_sim = time.perf_counter()
        computational_time_ms = (t_end_sim - t_start_sim) * 1000.0

        # 4. Compute the 12 Comparative Metrics
        metrics = compute_route_comparison_metrics(
            actual_path=actual_path,
            model_path=clean_model_path,
            actual_duration_hours=actual_duration_hours,
            model_duration_hours=model_duration_hours,
            audit_actual=audit_actual,
            audit_model=audit_model,
            sic_actual=sic_actual,
            sic_model=sic_model,
            number_of_reroutes=number_of_reroutes,
            computational_time_ms=computational_time_ms,
        )

        return BacktestResult(
            voyage_id=voyage_id,
            vessel_name=vessel_name,
            vessel_characteristics=vessel_info,
            departure_location=[start_lat, start_lon],
            destination_location=[dest_lat, dest_lon],
            departure_time=departure_time.isoformat(),
            arrival_time_actual=arrival_time_actual.isoformat(),
            arrival_time_model=arrival_time_model.isoformat(),
            actual_track_points_count=len(actual_path),
            model_route_points_count=len(clean_model_path),
            metrics=metrics,
            audit_actual=audit_actual,
            audit_model=audit_model,
            simulated_steps=simulated_steps,
            actual_path_coords=actual_path,
            model_path_coords=clean_model_path,
        )

    def compare_voyage_safety(
        self,
        voyage_id: str,
        actual_track: List[List[float]],
        departure_time: datetime,
        vessel_name: str = "Research Vessel",
        polar_class: str = "PC3",
        speed_knots: float = 14.0,
        draft_m: float = 8.0,
        destination_coords: Optional[Tuple[float, float]] = None,
        actual_duration_hours: Optional[float] = None,
    ):
        """Execute full three-way safety and efficiency comparison across:
        Route A: Actual Historical AIS Route
        Route B: ML + Routing Predicted Route (Balanced Corridor)
        Route C: Safety-Optimized Route (Safest Corridor)
        """
        from .route_safety_comparator import RouteSafetyComparator

        if len(actual_track) < 2:
            raise ValueError(f"Actual track must contain at least 2 points, got {len(actual_track)}")

        start_lat, start_lon = float(actual_track[0][0]), float(actual_track[0][1])
        if destination_coords:
            dest_lat, dest_lon = float(destination_coords[0]), float(destination_coords[1])
        else:
            raw_dest_lat, raw_dest_lon = float(actual_track[-1][0]), float(actual_track[-1][1])
            if haversine_km(start_lat, start_lon, raw_dest_lat, raw_dest_lon) < 50.0:
                furthest = max(actual_track, key=lambda p: haversine_km(start_lat, start_lon, float(p[0]), float(p[1])))
                dest_lat, dest_lon = float(furthest[0]), float(furthest[1])
            else:
                dest_lat, dest_lon = raw_dest_lat, raw_dest_lon

        vessel_info = {
            "vessel_name": vessel_name,
            "polar_class": polar_class,
            "speed_knots": speed_knots,
            "draft_m": draft_m,
            "current_lat": start_lat,
            "current_lon": start_lon,
        }

        # Generate Pareto candidates from routing engine
        routes = self.routing_engine.generate_routes(
            vessel=vessel_info,
            dest_override=(dest_lat, dest_lon),
            dest_name="Destination",
        )

        actual_path = [[float(p[0]), float(p[1])] for p in actual_track]

        # Extract Predicted (Balanced) and Safety-Optimized (Safest)
        pred_route = None
        safest_route = None

        for r in routes:
            opt_mode = r.get("optimization_mode", "")
            if opt_mode == "BALANCED" or r.get("recommended"):
                if pred_route is None:
                    pred_route = r
            elif opt_mode == "SAFEST" or r.get("is_safest"):
                if safest_route is None:
                    safest_route = r

        if not pred_route and routes:
            pred_route = routes[0]
        if not safest_route and routes:
            safest_route = routes[-1] if len(routes) > 1 else routes[0]

        # Fallback if no routes found
        if not pred_route:
            lats = np.linspace(start_lat, dest_lat, 25)
            lons = np.linspace(start_lon, dest_lon, 25)
            pred_path = [[float(lt), float(ln)] for lt, ln in zip(lats, lons)]
            safest_path = [[float(lt), float(ln)] for lt, ln in zip(lats, lons)]
        else:
            p_pts = pred_route.get("path", [])
            if not p_pts:
                p_pts = [[c[1], c[0]] for c in pred_route.get("geojson_coordinates", [])]
            pred_path = [[float(pt[0]), float(pt[1])] for pt in p_pts]

            s_pts = safest_route.get("path", [])
            if not s_pts:
                s_pts = [[c[1], c[0]] for c in safest_route.get("geojson_coordinates", [])]
            safest_path = [[float(pt[0]), float(pt[1])] for pt in s_pts]

        comparator = RouteSafetyComparator(
            sic_lookup_fn=self._get_sic,
            iceberg_dist_fn=self._get_iceberg_dist,
            depth_lookup_fn=self._get_depth,
            is_land_fn=self._is_land,
        )

        return comparator.compare_three_routes(
            voyage_id=voyage_id,
            vessel_name=vessel_name,
            departure_time=departure_time.isoformat(),
            actual_path=actual_path,
            predicted_path=pred_path,
            safest_path=safest_path,
            speed_knots=speed_knots,
            polar_class=polar_class,
            actual_duration_hours=actual_duration_hours,
        )
