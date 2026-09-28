"""POLARNAV — Phase 13: Multi-Dimensional Route Evaluator.

Evaluates any route (PolarNav, Historical AIS, Shortest Path) across 9 dimensions:
1. Safety (composite ML risk, hazard counts, IMO Polar Code compliance)
2. Efficiency (distance and speed efficiency ratios)
3. Feasibility (land violations, under-keel clearance UKC > 0m)
4. ETA (gross and net duration in hours)
5. Distance (kilometers and nautical miles)
6. High-SIC Exposure (exposure to SIC >= 15% and >= 60%)
7. Iceberg Clearance (minimum CPA distance in km and NM)
8. Bathymetry Violations (shallow water / grounding violations)
9. Fuel Estimate (empirical fuel consumption in metric tonnes)
"""

import math
from typing import List, Dict, Any, Optional
from .models import RouteEvaluationMetrics


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two geographic coordinates in km."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def compute_track_distance_km(coords: List[List[float]]) -> float:
    """Compute total length along a polyline in km."""
    if not coords or len(coords) < 2:
        return 0.0
    dist = 0.0
    for i in range(1, len(coords)):
        dist += haversine_km(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1])
    return round(dist, 1)


class BacktestEvaluator:
    """Evaluates safety, efficiency, feasibility, and emissions of candidate maritime corridors."""

    def __init__(
        self,
        sic_lookup_fn: Any,
        depth_lookup_fn: Any,
        is_land_fn: Any,
        iceberg_dist_fn: Any,
        risk_predict_fn: Any,
    ):
        self.sic_lookup_fn = sic_lookup_fn
        self.depth_lookup_fn = depth_lookup_fn
        self.is_land_fn = is_land_fn
        self.iceberg_dist_fn = iceberg_dist_fn
        self.risk_predict_fn = risk_predict_fn

    def evaluate_route(
        self,
        route_id: str,
        route_name: str,
        route_type: str,
        coords: List[List[float]],
        vessel_draft_m: float = 8.0,
        nominal_speed_knots: float = 14.0,
        gross_hours_override: Optional[float] = None,
        non_transit_delay_hours: float = 0.0,
    ) -> RouteEvaluationMetrics:
        """Run full 9-dimensional evaluation on a coordinate path."""
        dist_km = compute_track_distance_km(coords)
        dist_nm = round(dist_km / 1.852, 1)

        speed_kmh = max(1.0, nominal_speed_knots * 1.852)
        base_transit_hours = round(dist_km / speed_kmh, 1)

        if gross_hours_override is not None and gross_hours_override > 0:
            gross_hours = round(gross_hours_override, 1)
        else:
            gross_hours = base_transit_hours

        net_hours = max(1.0, round(gross_hours - non_transit_delay_hours, 1))

        if not coords or len(coords) < 2:
            return RouteEvaluationMetrics(
                route_id=route_id,
                route_name=route_name,
                route_type=route_type,
                distance_km=0.0,
                distance_nm=0.0,
                gross_transit_hours=0.0,
                net_transit_hours=0.0,
                nominal_speed_knots=nominal_speed_knots,
                composite_risk_score=0.0,
                risk_category="LOW",
                hazard_encounters_count=0,
                imo_polaris_compliant=True,
                speed_efficiency_ratio=1.0,
                distance_efficiency_ratio=1.0,
                is_physically_feasible=True,
                land_crossings_count=0,
                min_depth_m=3500.0,
                under_keel_clearance_m=3492.0,
                bathymetry_violations_count=0,
                mean_sic_pct=0.0,
                max_sic_pct=0.0,
                distance_in_ice_km=0.0,
                distance_in_heavy_ice_km=0.0,
                high_sic_exposure_pct=0.0,
                min_iceberg_cpa_km=200.0,
                min_iceberg_cpa_nm=107.9,
                iceberg_encounters_count=0,
                estimated_fuel_metric_tonnes=0.0,
                fuel_burn_rate_kg_km=22.0,
            )

        # Sampling step along corridor (sample at least 25 points or every 3rd point)
        step = max(1, len(coords) // 40)
        sample_pts = [coords[i] for i in range(0, len(coords), step)]
        if coords[-1] not in sample_pts:
            sample_pts.append(coords[-1])

        # Environmental Profiling
        sic_values: List[float] = []
        depth_values: List[float] = []
        land_violations = 0
        bathymetry_violations = 0
        min_depth = 9999.0
        min_ib_cpa = 999.0
        ib_encounters = 0
        risk_scores: List[float] = []

        for pt in sample_pts:
            lat, lon = float(pt[0]), float(pt[1])

            # 1. SIC
            sic = self.sic_lookup_fn(lat, lon)
            sic_values.append(sic)

            # 2. Depth & Land
            depth = self.depth_lookup_fn(lat, lon)
            depth_values.append(depth)
            if depth < min_depth:
                min_depth = depth

            is_land = self.is_land_fn(lat, lon)
            if is_land:
                land_violations += 1

            if depth <= vessel_draft_m or depth < 10.0:
                bathymetry_violations += 1

            # 3. Iceberg
            ib_dist = self.iceberg_dist_fn(lat, lon)
            if ib_dist < min_ib_cpa:
                min_ib_cpa = ib_dist
            if ib_dist < 15.0:
                ib_encounters += 1

            # 4. Risk
            r = self.risk_predict_fn(lat, lon, sic, ib_dist, depth)
            risk_scores.append(r)

        mean_sic = round(float(sum(sic_values) / max(1, len(sic_values))), 1)
        max_sic = round(float(max(sic_values)), 1)
        mean_risk = round(float(sum(risk_scores) / max(1, len(risk_scores))), 4)

        # SIC exposure distances
        ice_samples = sum(1 for s in sic_values if s >= 15.0)
        heavy_ice_samples = sum(1 for s in sic_values if s >= 60.0)
        dist_in_ice = round((ice_samples / len(sic_values)) * dist_km, 1)
        dist_in_heavy_ice = round((heavy_ice_samples / len(sic_values)) * dist_km, 1)
        high_sic_pct = round((heavy_ice_samples / len(sic_values)) * 100.0, 1)

        # Under keel clearance
        ukc = round(max(0.0, min_depth - vessel_draft_m), 1)

        # Feasibility check
        is_feasible = (land_violations == 0) and (bathymetry_violations == 0)

        # Risk Category
        if mean_risk < 0.20:
            category = "LOW"
        elif mean_risk < 0.45:
            category = "MODERATE"
        elif mean_risk < 0.70:
            category = "ELEVATED"
        else:
            category = "CRITICAL"

        # Efficiency metrics
        # Shortest direct distance between origin and destination
        direct_dist = haversine_km(coords[0][0], coords[0][1], coords[-1][0], coords[-1][1])
        if direct_dist < 50.0 and len(coords) > 2:
            # Round-trip or survey voyage returning to same port / area
            max_disp = max(haversine_km(coords[0][0], coords[0][1], pt[0], pt[1]) for pt in coords)
            effective_direct = max(10.0, max_disp * 2.0)
        else:
            effective_direct = direct_dist
        dist_efficiency = round(effective_direct / max(1.0, dist_km), 3)
        speed_efficiency = round(dist_km / max(1.0, net_hours * speed_kmh), 3)

        # Fuel consumption estimate (Admiralty modified formula with ice resistance)
        # Base open-water fuel rate for 100m research vessel: ~22 kg/km
        # In ice (SIC > 15%), hull resistance increases fuel burn by 35% to 120%
        base_fuel_rate = 22.0
        open_water_km = max(0.0, dist_km - dist_in_ice)
        ice_km = dist_in_ice
        fuel_tonnes = ((open_water_km * base_fuel_rate) + (ice_km * base_fuel_rate * 1.65)) / 1000.0

        min_ib_cpa_nm = round(min_ib_cpa / 1.852, 1)

        return RouteEvaluationMetrics(
            route_id=route_id,
            route_name=route_name,
            route_type=route_type,
            distance_km=dist_km,
            distance_nm=dist_nm,
            gross_transit_hours=gross_hours,
            net_transit_hours=net_hours,
            nominal_speed_knots=nominal_speed_knots,
            composite_risk_score=mean_risk,
            risk_category=category,
            hazard_encounters_count=ib_encounters + (1 if max_sic > 70.0 else 0),
            imo_polaris_compliant=(mean_risk < 0.50 and land_violations == 0),
            speed_efficiency_ratio=speed_efficiency,
            distance_efficiency_ratio=dist_efficiency,
            is_physically_feasible=is_feasible,
            land_crossings_count=land_violations,
            min_depth_m=round(min_depth, 1),
            under_keel_clearance_m=ukc,
            bathymetry_violations_count=bathymetry_violations,
            mean_sic_pct=mean_sic,
            max_sic_pct=max_sic,
            distance_in_ice_km=dist_in_ice,
            distance_in_heavy_ice_km=dist_in_heavy_ice,
            high_sic_exposure_pct=high_sic_pct,
            min_iceberg_cpa_km=round(min_ib_cpa, 1),
            min_iceberg_cpa_nm=min_ib_cpa_nm,
            iceberg_encounters_count=ib_encounters,
            estimated_fuel_metric_tonnes=round(fuel_tonnes, 1),
            fuel_burn_rate_kg_km=round((fuel_tonnes * 1000.0) / max(1.0, dist_km), 1),
        )
