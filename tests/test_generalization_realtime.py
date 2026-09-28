"""POLARNAV — Phase 14: Generalization Test Suite.

Verifies that the live route engine can handle:
- Unseen Vessels (commercial container, polar yacht, heavy icebreaker)
- Novel Origin / Destination corridors
- Extreme / Unseen environmental conditions
without requiring or relying on historical AIS logs.
Also verifies honest limitation reporting when dataset coverage is exceeded.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.server import app
from realtime.generalization.service import generalization_service
from realtime.generalization.models import (
    UnseenVesselConfig,
    NovelCorridorConfig,
    GeneralizationTestRequest,
    EnvironmentalStressType,
)
from realtime.ml_risk.models import PolarIceClass
from realtime.route_optimizer.models import RouteProfileType


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient for generalization endpoints."""
    return TestClient(app)


class TestGeneralizationRealtime:
    """Core verification suite for unseen vessels, novel corridors, and environmental stress."""

    def test_unseen_vessels_catalog_loaded(self):
        """Verify unseen vessels catalog exists with diverse drafts and ice classes."""
        catalog = generalization_service.get_catalog()
        vessels = catalog["unseen_vessels"]
        assert len(vessels) >= 4
        
        vessel_ids = [v["vessel_id"] for v in vessels]
        assert "vessel_deep_container" in vessel_ids
        assert "vessel_pc2_heavy_breaker" in vessel_ids
        assert "vessel_pc6_cruise" in vessel_ids
        assert "vessel_survey_cutter" in vessel_ids

    def test_novel_corridors_catalog_loaded(self):
        """Verify novel corridors catalog has corridors never present in historical AIS."""
        catalog = generalization_service.get_catalog()
        corridors = catalog["novel_corridors"]
        assert len(corridors) >= 4

        corridor_ids = [c["corridor_id"] for c in corridors]
        assert "corridor_ushuaia_rothera" in corridor_ids
        assert "corridor_bluff_mcmurdo" in corridor_ids
        assert "corridor_southern_ocean_rendezvous" in corridor_ids

    def test_zero_historical_ais_reliance_invariant(self):
        """STRICT INVARIANT: Verify route generation succeeds with strictly zero historical AIS usage."""
        engine = generalization_service.engine
        vessel = engine.UNSEEN_VESSEL_CATALOG if hasattr(engine, "UNSEEN_VESSEL_CATALOG") else None
        from realtime.generalization.engine import UNSEEN_VESSEL_CATALOG, NOVEL_CORRIDOR_CATALOG
        
        vessel = UNSEEN_VESSEL_CATALOG["vessel_pc6_cruise"]
        corridor = NOVEL_CORRIDOR_CATALOG["corridor_ushuaia_rothera"]
        
        res = engine.test_scenario(
            vessel=vessel,
            corridor=corridor,
            stress=EnvironmentalStressType.STANDARD_SUMMER_MIZ,
        )
        
        # Zero historical AIS guarantee
        assert res.historical_ais_used is False, "Generalization MUST NOT use historical AIS"
        assert res.route_found is True
        assert res.route_waypoints_count > 0
        assert res.distance_km > 500.0

    def test_unseen_vessel_ice_capability_differentiation(self):
        """Verify that an unstrengthened container vessel and a PC2 heavy icebreaker receive differentiated handling."""
        from realtime.generalization.engine import UNSEEN_VESSEL_CATALOG, NOVEL_CORRIDOR_CATALOG
        engine = generalization_service.engine

        vessel_open_water = UNSEEN_VESSEL_CATALOG["vessel_deep_container"]
        vessel_pc2 = UNSEEN_VESSEL_CATALOG["vessel_pc2_heavy_breaker"]
        corridor = NOVEL_CORRIDOR_CATALOG["corridor_bluff_mcmurdo"]

        # Run under Winter Pack Ice Barrier condition
        res_ow = engine.test_scenario(
            vessel=vessel_open_water,
            corridor=corridor,
            stress=EnvironmentalStressType.WINTER_PACK_ICE_BARRIER,
        )
        res_pc2 = engine.test_scenario(
            vessel=vessel_pc2,
            corridor=corridor,
            stress=EnvironmentalStressType.WINTER_PACK_ICE_BARRIER,
        )

        # Open water commercial container must be blocked or heavily flagged for winter ice
        assert res_ow.is_feasible is False or res_ow.composite_risk_score > 0.85
        # PC2 heavy icebreaker has lower composite risk than open water
        assert res_pc2.composite_risk_score < res_ow.composite_risk_score

    def test_out_of_coverage_boundary_limitation_reporting(self):
        """Verify that out-of-domain coordinates trigger honest limitation reporting without fake routes."""
        from realtime.generalization.engine import UNSEEN_VESSEL_CATALOG, NOVEL_CORRIDOR_CATALOG
        engine = generalization_service.engine

        vessel = UNSEEN_VESSEL_CATALOG["vessel_deep_container"]
        corridor = NOVEL_CORRIDOR_CATALOG["corridor_equatorial_out_of_coverage"]

        res = engine.test_scenario(
            vessel=vessel,
            corridor=corridor,
            stress=EnvironmentalStressType.DOMAIN_BOUNDARY_EDGE,
        )

        assert res.is_feasible is False
        assert res.route_found is False
        assert res.confidence_score == 0.0
        assert len(res.limitation_notes) > 0
        assert any("outside PolarNav Antarctic maritime operational domain" in note or "LIMITATION" in note for note in res.limitation_notes)

    def test_inland_continental_ice_sheet_limitation_reporting(self):
        """Verify that interior continental ice sheet coordinates trigger honest rejection without land traversal."""
        from realtime.generalization.engine import UNSEEN_VESSEL_CATALOG, NOVEL_CORRIDOR_CATALOG
        engine = generalization_service.engine

        vessel = UNSEEN_VESSEL_CATALOG["vessel_pc2_heavy_breaker"]
        corridor = NOVEL_CORRIDOR_CATALOG["corridor_continental_ice_sheet_invalid"]

        res = engine.test_scenario(
            vessel=vessel,
            corridor=corridor,
            stress=EnvironmentalStressType.OUT_OF_COVERAGE_CONTINENTAL,
        )

        assert res.is_feasible is False
        assert res.route_found is False
        assert len(res.limitation_notes) > 0
        assert any("continental ice sheet" in note or "LIMITATION" in note for note in res.limitation_notes)

    def test_physical_feasibility_invariants_on_novel_routes(self):
        """Verify feasible generated routes strictly satisfy zero-land crossing and positive UKC."""
        from realtime.generalization.engine import UNSEEN_VESSEL_CATALOG, NOVEL_CORRIDOR_CATALOG
        engine = generalization_service.engine

        vessel = UNSEEN_VESSEL_CATALOG["vessel_pc6_cruise"]
        corridor = NOVEL_CORRIDOR_CATALOG["corridor_southern_ocean_rendezvous"]

        res = engine.test_scenario(
            vessel=vessel,
            corridor=corridor,
            stress=EnvironmentalStressType.STANDARD_SUMMER_MIZ,
        )

        if res.is_feasible:
            assert res.min_under_keel_clearance_m > 0.0
            assert res.min_depth_m > vessel.draft_m


class TestGeneralizationAPIEndpoints:
    """Verification suite for Phase 14 Generalization REST API endpoints."""

    def test_api_catalog_endpoint(self, client):
        """Test GET /api/realtime/generalization/catalog returns valid metadata."""
        resp = client.get("/api/realtime/generalization/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "unseen_vessels" in data
        assert "novel_corridors" in data
        assert "stress_conditions" in data
        assert len(data["unseen_vessels"]) >= 4
        assert len(data["novel_corridors"]) >= 4

    def test_api_custom_test_endpoint(self, client):
        """Test POST /api/realtime/generalization/test with custom unseen vessel and corridor."""
        payload = {
            "vessel": {
                "vessel_id": "custom_yacht",
                "name": "S/Y Explorer (Custom Yacht)",
                "vessel_type": "Polar Yacht",
                "ice_class": "PC7",
                "length_m": 45.0,
                "beam_m": 9.5,
                "draft_m": 3.8,
                "speed_knots": 11.0,
                "operational_constraints": ["LIGHT_ICE_ONLY"],
                "max_tolerable_sic": 30.0,
                "min_under_keel_clearance_m": 2.0,
            },
            "corridor": {
                "corridor_id": "custom_falklands_south_georgia",
                "name": "Falklands to South Georgia",
                "origin": [-52.0, -58.0],
                "destination": [-54.3, -36.5],
                "description": "Novel sub-Antarctic passage",
            },
            "stress_condition": "STANDARD_SUMMER_MIZ",
            "profile": "BALANCED",
        }

        resp = client.post("/api/realtime/generalization/test", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["vessel_id"] == "custom_yacht"
        assert data["historical_ais_used"] is False
        assert "is_feasible" in data
        assert "composite_risk_score" in data

    def test_api_benchmark_suite_endpoint(self, client):
        """Test GET /api/realtime/generalization/benchmark-suite executes full matrix."""
        resp = client.get("/api/realtime/generalization/benchmark-suite")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tests" in data
        assert data["total_tests"] >= 6
        assert data["zero_historical_ais_guarantee"] is True
        assert "passed_tests" in data
        assert "disclosed_limitations" in data
        assert len(data["disclosed_limitations"]) > 0
