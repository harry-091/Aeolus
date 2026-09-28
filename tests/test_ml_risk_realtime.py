"""POLARNAV — Phase 9: Real-Time Vessel-Aware ML Risk Engine Test Suite.

Rigorously verifies:
1. Validated ML model loading (rf_risk_regressor.joblib).
2. Input mapping from live CurrentMaritimeState + VesselCharacteristics.
3. Prediction outputs: risk_score, risk_category, risk_breakdown, confidence.
4. INVARIANT: The model must NOT predict AIS coordinates.
5. Vessel-aware physics: Ice class capability, draft clearance, and speed adjustments.
6. Operational constraints enforcement (max SIC, min UKC, max wind, max wave).
7. Anti-fabrication confidence gating: When live input confidence is low or stale,
   output confidence is reduced and limitations are explicitly exposed.
8. REST API endpoints.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from realtime import maritime_state_manager, CurrentMaritimeState
from realtime.ml_risk import (
    vessel_ml_risk_engine,
    VesselCharacteristics,
    VesselType,
    PolarIceClass,
    OperationalConstraints,
    RiskCategory,
    RiskBreakdown,
    MLRiskPrediction,
)
from app.server import app

client = TestClient(app)


class TestVesselAwareMLRiskEngine:
    """Validate ML model inference, naval architecture adjustments, and confidence integrity."""

    def test_model_initialization(self):
        """Verify validated historical Random Forest model loads successfully."""
        assert vessel_ml_risk_engine.initialize() is True
        assert vessel_ml_risk_engine._model is not None
        assert len(vessel_ml_risk_engine._feature_names) == 32

    def test_output_contract_and_no_ais_prediction(self):
        """Verify output schema: risk_score, risk_category, risk_breakdown, confidence.
        
        INVARIANT: Under NO circumstance does the model predict AIS coordinates.
        """
        state = maritime_state_manager.get_current_state(lat=-63.0, lon=-58.0)
        vessel = VesselCharacteristics(
            vessel_id="EXP-01",
            name="RRS Sir David",
            vessel_type=VesselType.RESEARCH_VESSEL,
            ice_class=PolarIceClass.PC5,
            draft_m=8.0,
            speed_knots=12.0,
        )

        pred = vessel_ml_risk_engine.predict_risk(state, vessel)

        assert isinstance(pred, MLRiskPrediction)
        assert 0.0 <= pred.risk_score <= 1.0
        assert 0.0 <= pred.risk_score_100 <= 100.0
        assert isinstance(pred.risk_category, RiskCategory)
        assert isinstance(pred.risk_breakdown, RiskBreakdown)
        assert 0.0 <= pred.confidence <= 1.0
        assert isinstance(pred.confidence_explanation, str)
        assert isinstance(pred.exposed_limitations, list)

        # STRICT INVARIANT: Must NOT predict AIS coordinates!
        d = pred.model_dump()
        for forbidden_key in ["predicted_lat", "predicted_lon", "predicted_ais", "target_lat", "target_lon", "ais_trajectory"]:
            assert forbidden_key not in d, f"Forbidden key {forbidden_key} found in MLRiskPrediction output"
        assert pred.model_metadata.get("prediction_type") == "ENVIRONMENTAL_NAVIGATION_RISK (NEVER AIS COORDINATES)"

    def test_vessel_ice_capability_differentiation(self):
        """In identical sea ice conditions, a heavy icebreaker (PC1) must receive
        significantly lower risk than an unstrengthened open-water hull (NON_ICE).
        """
        # Coordinate in Antarctic coastal margin with sea ice
        state = maritime_state_manager.get_current_state(lat=-65.20, lon=64.30)

        vessel_pc1 = VesselCharacteristics(
            vessel_type=VesselType.ICEBREAKER,
            ice_class=PolarIceClass.PC1,
            speed_knots=10.0,
            draft_m=10.0,
        )

        vessel_non_ice = VesselCharacteristics(
            vessel_type=VesselType.CARGO,
            ice_class=PolarIceClass.NON_ICE,
            speed_knots=10.0,
            draft_m=10.0,
            operational_constraints=OperationalConstraints(max_allowed_sic_pct=15.0),
        )

        pred_pc1 = vessel_ml_risk_engine.predict_risk(state, vessel_pc1)
        pred_non_ice = vessel_ml_risk_engine.predict_risk(state, vessel_non_ice)

        # PC1 structural icebreaker has vastly superior capability
        assert pred_pc1.risk_score < pred_non_ice.risk_score
        assert pred_pc1.risk_breakdown.vessel_ice_capability_penalty == 0.0
        assert pred_non_ice.risk_breakdown.vessel_ice_capability_penalty > 0.0

    def test_shallow_water_and_grounding_penalty(self):
        """If vessel draft exceeds water depth (UKC <= 0) or vessel is on land,
        risk must escalate to PROHIBITED (risk_score = 1.0).
        """
        # Coordinate on Antarctic land (depth = 0.0m)
        state_land = maritime_state_manager.get_current_state(lat=-89.0, lon=0.0)
        vessel = VesselCharacteristics(draft_m=8.0)

        pred_grounding = vessel_ml_risk_engine.predict_risk(state_land, vessel)

        assert pred_grounding.risk_score == 1.0
        assert pred_grounding.risk_category == RiskCategory.PROHIBITED
        assert pred_grounding.safe_to_proceed is False
        assert pred_grounding.risk_breakdown.bathymetry_grounding_risk == 1.0
        assert any("GROUNDING" in v or "LAND" in v for v in pred_grounding.risk_breakdown.constraint_violations)

    def test_operational_constraints_enforcement(self):
        """Verify strict constraint breach detection for SIC, wave, and wind limits."""
        state = maritime_state_manager.get_current_state(lat=-63.0, lon=-58.0)
        
        # Extremely restrictive operational limits that trigger breaches
        strict_constraints = OperationalConstraints(
            max_allowed_sic_pct=0.0,
            max_wind_speed_knots=5.0,     # Very low threshold
            max_wave_height_m=0.5,        # Very low threshold
            min_under_keel_clearance_m=500.0, # Unrealistically deep clearance
        )
        vessel = VesselCharacteristics(
            draft_m=8.0,
            operational_constraints=strict_constraints,
        )

        pred = vessel_ml_risk_engine.predict_risk(state, vessel)

        violations = pred.risk_breakdown.constraint_violations
        assert len(violations) > 0
        assert any("BREACH" in v for v in violations)

    def test_non_fabricated_confidence_reduction_and_limitation_exposure(self):
        """Verify that when live input confidence is low or critical inputs are stale:
        1. Output confidence is reduced (never exceeds input confidence).
        2. Data limitations are explicitly exposed in exposed_limitations.
        3. Confidence is NOT fabricated.
        """
        # 1. Fresh state scenario (all sensors fresh with high confidence)
        state_fresh = maritime_state_manager.get_current_state(lat=-63.0, lon=-58.0)
        state_fresh.unified_environmental_confidence = 0.90
        state_fresh.critical_data_stale = False
        state_fresh.has_stale_data = False
        state_fresh.stale_layers = []
        vessel = VesselCharacteristics()
        pred_fresh = vessel_ml_risk_engine.predict_risk(state_fresh, vessel)

        assert pred_fresh.confidence > 0.70
        assert pred_fresh.is_degraded_confidence is False
        assert len(pred_fresh.exposed_limitations) == 0

        # 2. Degraded case: live environmental confidence is low / stale
        state_stale = maritime_state_manager.get_current_state(lat=-63.0, lon=-58.0)
        state_stale.unified_environmental_confidence = 0.35
        state_stale.critical_data_stale = True
        state_stale.stale_layers = ["sea_ice", "iceberg"]

        pred_stale = vessel_ml_risk_engine.predict_risk(state_stale, vessel)

        # Strict anti-fabrication assertions
        assert pred_stale.confidence < pred_fresh.confidence
        assert pred_stale.confidence <= state_stale.unified_environmental_confidence
        assert pred_stale.is_degraded_confidence is True
        assert len(pred_stale.exposed_limitations) > 0

        # Must explicitly disclose staleness / low confidence limitations
        limitations_text = " ".join(pred_stale.exposed_limitations)
        assert "STALENESS" in limitations_text or "CONFIDENCE" in limitations_text
        assert "degraded" in pred_stale.confidence_explanation.lower()

    def test_route_corridor_risk_evaluation(self):
        """Verify risk prediction across multiple waypoints along a voyage corridor."""
        waypoints = [
            (-60.0, -60.0),
            (-61.5, -59.5),
            (-63.0, -58.0),
        ]
        states = [
            maritime_state_manager.get_current_state(lat=lat, lon=lon)
            for lat, lon in waypoints
        ]
        vessel = VesselCharacteristics(draft_m=8.5, speed_knots=12.0)

        preds = vessel_ml_risk_engine.predict_route_risk(states, vessel)

        assert len(preds) == 3
        for p in preds:
            assert isinstance(p, MLRiskPrediction)
            assert 0.0 <= p.risk_score <= 1.0


class TestMLRiskAPIEndpoints:
    """Verify REST API endpoints for Phase 9 ML Risk Engine."""

    def test_api_risk_evaluate_endpoint(self):
        payload = {
            "latitude": -63.0,
            "longitude": -58.0,
            "vessel_id": "V-001",
            "vessel_type": "RESEARCH_VESSEL",
            "ice_class": "PC5",
            "length_m": 105.0,
            "beam_m": 20.0,
            "draft_m": 8.0,
            "speed_knots": 12.0,
            "heading_deg": 180.0,
        }
        res = client.post("/api/realtime/risk/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "risk_score" in data
        assert "risk_category" in data
        assert "risk_breakdown" in data
        assert "confidence" in data
        assert "confidence_explanation" in data
        assert "exposed_limitations" in data

        # Sub-factor decomposition checks
        rb = data["risk_breakdown"]
        assert "sea_ice_risk" in rb
        assert "iceberg_risk" in rb
        assert "wind_risk" in rb
        assert "wave_risk" in rb
        assert "bathymetry_grounding_risk" in rb
        assert "dominant_hazard" in rb

    def test_api_risk_evaluate_route_endpoint(self):
        payload = {
            "waypoints": [
                [-60.0, -60.0],
                [-62.0, -59.0],
            ],
            "vessel_type": "ICEBREAKER",
            "ice_class": "PC3",
            "speed_knots": 14.0,
            "draft_m": 9.0,
        }
        res = client.post("/api/realtime/risk/evaluate-route", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["waypoint_count"] == 2
        assert "maximum_risk_score" in data
        assert "average_risk_score" in data
        assert "is_passage_prohibited" in data
        assert len(data["predictions"]) == 2

    def test_api_risk_model_info_endpoint(self):
        res = client.get("/api/realtime/risk/model-info")
        assert res.status_code == 200
        data = res.json()
        assert data["model_name"] == "rf_risk_regressor"
        assert data["architecture"] == "RandomForestRegressor"
        assert data["feature_count"] == 32
        assert len(data["feature_names"]) == 32
        assert data["status"] == "VALIDATED_PRODUCTION_MODEL"
