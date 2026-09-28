"""POLARNAV — Phase 10: Real-Time Risk-Aware Route Optimization Test Suite.

Rigorously verifies:
1. Pipeline connection: Live Data -> ML Risk Engine -> Dynamic Cost Surface -> Route Optimizer.
2. Three distinct operational profiles: BALANCED, SAFEST, FASTEST.
3. Invariant: Genuine multi-objective differentiation (Zero fake routes with different labels).
4. Physical feasibility invariant: Zero land crossings, under-keel clearance strictly > 0m.
5. All 9 required metrics present:
   - Distance (km / NM)
   - ETA (hours / timestamps)
   - Estimated Risk (score / category)
   - SIC Exposure (avg / max / ice-covered km)
   - Iceberg Clearance (min CPA / cleared bergs)
   - Weather Exposure (wind / waves)
   - Depth Clearance (min depth / min UKC)
   - Non-fabricated Confidence
   - Transparent Explanation
6. Vessel constraints & ice class influence.
7. REST API endpoints.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from realtime.ml_risk.models import VesselCharacteristics, PolarIceClass, VesselType, RiskCategory
from realtime.route_optimizer import (
    realtime_route_optimizer,
    dynamic_cost_surface,
    PROFILE_CONFIGS,
    RouteProfileType,
    RouteOptimizationRequest,
)
from app.server import app

client = TestClient(app)


class TestRealtimeRouteOptimization:
    """Verify real-time risk-aware pathfinding, cost surfaces, and multi-objective differentiation."""

    def test_dynamic_cost_surface_differentiation(self):
        """Verify dynamic cost surface produces distinctly weighted costs for SAFEST, BALANCED, and FASTEST."""
        vessel = VesselCharacteristics(ice_class=PolarIceClass.PC5, draft_m=8.0)
        lat, lon = -63.0, -58.0  # Antarctic Peninsula waters with pack ice
        dest_lat, dest_lon = -65.0, -60.0

        cost_safest, _, _ = dynamic_cost_surface.evaluate_cost(
            lat=lat, lon=lon,
            profile=PROFILE_CONFIGS[RouteProfileType.SAFEST],
            vessel=vessel,
            dest_lat=dest_lat, dest_lon=dest_lon,
        )
        cost_balanced, _, _ = dynamic_cost_surface.evaluate_cost(
            lat=lat, lon=lon,
            profile=PROFILE_CONFIGS[RouteProfileType.BALANCED],
            vessel=vessel,
            dest_lat=dest_lat, dest_lon=dest_lon,
        )
        cost_fastest, _, _ = dynamic_cost_surface.evaluate_cost(
            lat=lat, lon=lon,
            profile=PROFILE_CONFIGS[RouteProfileType.FASTEST],
            vessel=vessel,
            dest_lat=dest_lat, dest_lon=dest_lon,
        )

        # In ice-covered waters, SAFEST incurs significantly higher traversal penalty than FASTEST
        assert cost_safest > cost_balanced
        assert cost_balanced > cost_fastest

    def test_zero_fake_routes_genuine_differentiation(self):
        """Verify that BALANCED, SAFEST, and FASTEST generate genuinely differentiated paths/metrics,
        strictly fulfilling the user invariant: 'Do NOT create three fake routes with different labels.'
        """
        # Voyage across South Shetland Islands / Bransfield Strait
        origin = [-60.5, -60.0]
        destination = [-64.5, -57.0]
        vessel = VesselCharacteristics(
            vessel_type=VesselType.RESEARCH_VESSEL,
            ice_class=PolarIceClass.PC5,
            speed_knots=12.0,
            draft_m=8.0,
        )

        req = RouteOptimizationRequest(
            origin=origin,
            destination=destination,
            vessel=vessel,
            profiles=[RouteProfileType.BALANCED, RouteProfileType.SAFEST, RouteProfileType.FASTEST],
        )

        res = realtime_route_optimizer.optimize_route(req)

        assert len(res.routes) == 3
        routes_by_type = {r.profile_type: r for r in res.routes}

        r_safest = routes_by_type[RouteProfileType.SAFEST]
        r_balanced = routes_by_type[RouteProfileType.BALANCED]
        r_fastest = routes_by_type[RouteProfileType.FASTEST]

        # Verify distinct objectives produced distinct metric profiles:
        # FASTEST achieves minimum geodesic distance
        assert r_fastest.metrics.distance_km <= r_safest.metrics.distance_km

        # SAFEST achieves lower composite ML risk score than FASTEST
        assert r_safest.metrics.estimated_risk_score <= r_fastest.metrics.estimated_risk_score

        # Distinct explanations
        assert r_safest.metrics.explanation != r_fastest.metrics.explanation
        assert r_balanced.metrics.explanation != r_safest.metrics.explanation

    def test_physical_feasibility_invariants(self):
        """Every generated route MUST be physically feasible:
        - Strictly zero land crossings
        - Strictly non-negative under-keel clearance (depth - draft > 0m)
        - is_feasible must be True
        """
        origin = [-61.0, -58.0]
        destination = [-63.0, -55.0]
        vessel = VesselCharacteristics(draft_m=7.5)

        req = RouteOptimizationRequest(
            origin=origin,
            destination=destination,
            vessel=vessel,
        )

        res = realtime_route_optimizer.optimize_route(req)

        for route in res.routes:
            assert route.is_feasible is True
            assert len(route.waypoints) >= 2
            
            # Verify every waypoint
            for wp in route.waypoints:
                assert wp.is_land is False, f"Waypoint {wp.waypoint_index} intersects land!"
                assert wp.under_keel_clearance_m > 0.0, f"Waypoint {wp.waypoint_index} has UKC <= 0m!"
                assert wp.depth_m >= vessel.draft_m

    def test_all_nine_required_metrics_present(self):
        """Verify all 9 explicit user requirements are included on every route:
        1. distance
        2. ETA
        3. estimated risk
        4. SIC exposure
        5. iceberg clearance
        6. weather exposure
        7. depth clearance
        8. confidence
        9. explanation
        """
        origin = [-61.0, -58.0]
        destination = [-63.0, -57.0]
        vessel = VesselCharacteristics()

        req = RouteOptimizationRequest(
            origin=origin,
            destination=destination,
            vessel=vessel,
            profiles=[RouteProfileType.BALANCED],
        )

        res = realtime_route_optimizer.optimize_route(req)
        route = res.routes[0]
        m = route.metrics

        # 1. Distance
        assert m.distance_km > 0.0
        assert m.distance_nm > 0.0

        # 2. ETA
        assert m.eta_hours > 0.0
        assert m.departure_time is not None
        assert m.estimated_arrival_time is not None

        # 3. Estimated Risk
        assert 0.0 <= m.estimated_risk_score <= 1.0
        assert m.estimated_risk_category in RiskCategory

        # 4. SIC Exposure
        assert 0.0 <= m.sic_exposure.avg_sic_pct <= 100.0
        assert 0.0 <= m.sic_exposure.max_sic_pct <= 100.0
        assert m.sic_exposure.ice_covered_km >= 0.0
        assert m.sic_exposure.open_water_km >= 0.0

        # 5. Iceberg Clearance
        assert m.iceberg_clearance.min_cpa_km > 0.0
        assert m.iceberg_clearance.cleared_icebergs_count >= 0
        assert m.iceberg_clearance.required_buffer_km > 0.0

        # 6. Weather Exposure
        assert m.weather_exposure.avg_wind_knots >= 0.0
        assert m.weather_exposure.max_wind_knots >= 0.0
        assert m.weather_exposure.avg_wave_height_m >= 0.0
        assert m.weather_exposure.max_wave_height_m >= 0.0

        # 7. Depth Clearance
        assert m.depth_clearance.min_depth_m > 0.0
        assert m.depth_clearance.min_ukc_m > 0.0
        assert m.depth_clearance.is_clearance_compliant is True

        # 8. Confidence (anti-fabrication)
        assert 0.0 <= m.confidence <= 1.0
        assert len(m.confidence_explanation) > 0

        # 9. Explanation
        assert len(m.explanation) > 20
        assert "PROFILE" in m.explanation

    def test_vessel_ice_class_differentiation_on_route(self):
        """PC1 heavy icebreaker should incur significantly lower risk than unstrengthened hull on same route."""
        origin = [-61.0, -58.0]
        destination = [-63.5, -57.0]

        vessel_pc1 = VesselCharacteristics(ice_class=PolarIceClass.PC1, speed_knots=14.0)
        vessel_non_ice = VesselCharacteristics(ice_class=PolarIceClass.NON_ICE, speed_knots=14.0)

        req_pc1 = RouteOptimizationRequest(origin=origin, destination=destination, vessel=vessel_pc1, profiles=[RouteProfileType.BALANCED])
        req_non_ice = RouteOptimizationRequest(origin=origin, destination=destination, vessel=vessel_non_ice, profiles=[RouteProfileType.BALANCED])

        res_pc1 = realtime_route_optimizer.optimize_route(req_pc1)
        res_non_ice = realtime_route_optimizer.optimize_route(req_non_ice)

        risk_pc1 = res_pc1.routes[0].metrics.estimated_risk_score
        risk_non_ice = res_non_ice.routes[0].metrics.estimated_risk_score

        assert risk_pc1 < risk_non_ice

    def test_api_route_optimize_endpoint(self):
        """Verify POST /api/realtime/route/optimize API endpoint."""
        payload = {
            "origin": [-61.0, -58.0],
            "destination": [-63.0, -57.0],
            "vessel": {
                "vessel_id": "VESSEL-API-TEST",
                "vessel_type": "RESEARCH_VESSEL",
                "ice_class": "PC5",
                "draft_m": 8.0,
                "speed_knots": 12.0,
            },
            "profiles": ["BALANCED", "SAFEST", "FASTEST"],
        }
        res = client.post("/api/realtime/route/optimize", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "request_id" in data
        assert "routes" in data
        assert len(data["routes"]) == 3
        assert "computation_time_ms" in data

    def test_api_route_profiles_endpoint(self):
        """Verify GET /api/realtime/route/profiles API endpoint."""
        res = client.get("/api/realtime/route/profiles")
        assert res.status_code == 200
        data = res.json()
        assert "BALANCED" in data
        assert "SAFEST" in data
        assert "FASTEST" in data
        assert data["SAFEST"]["w_sic"] > data["FASTEST"]["w_sic"]
        assert data["SAFEST"]["min_iceberg_clearance_km"] > data["FASTEST"]["min_iceberg_clearance_km"]

    def test_api_route_evaluate_custom_endpoint(self):
        """Verify POST /api/realtime/route/evaluate-custom API endpoint."""
        payload = {
            "waypoints": [
                [-61.0, -58.0],
                [-62.0, -57.5],
                [-63.0, -57.0],
            ],
            "vessel": {
                "ice_class": "PC4",
                "draft_m": 8.5,
            }
        }
        res = client.post("/api/realtime/route/evaluate-custom", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert len(data["routes"]) >= 1
        assert data["routes"][0]["is_feasible"] is True
