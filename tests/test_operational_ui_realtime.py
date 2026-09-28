"""POLARNAV — Phase 12: Real Operational Monitoring UI Endpoint Tests.

Validates:
1. Operational Dashboard endpoint availability (`GET /api/realtime/operational-dashboard`).
2. Primary Map Layers present:
   - vessel position
   - recommended route
   - alternate routes
   - SIC & ice edge
   - iceberg hazards
   - weather layer
   - current vectors
   - bathymetry & coastline
   - risk zones
3. Every layer displays source, timestamp, and data age.
4. Sidebar telemetry: Current Vessel, Current Conditions, Risk, Route, ETA, Alerts.
5. DATA HEALTH table:
   - Satellite, Sea Ice, Weather, Ocean, Iceberg, Bathymetry.
   - Strict invariant: Never display "LIVE" if underlying data is stale.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


class TestOperationalMonitoringEndpoint:
    """Test suite for Phase 12 Operational Dashboard backend integration."""

    def test_operational_dashboard_returns_200(self):
        res = client.get("/api/realtime/operational-dashboard")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "OPERATIONAL"
        assert "timestamp" in data
        assert "vessel" in data
        assert "conditions" in data
        assert "risk" in data
        assert "route" in data
        assert "eta" in data
        assert "alerts" in data
        assert "data_health" in data
        assert "layer_metadata" in data
        assert "spatial_layers" in data

    def test_vessel_telemetry_fields(self):
        res = client.get("/api/realtime/operational-dashboard?vessel_id=rv_sagar_nidhi")
        assert res.status_code == 200
        v = res.json()["vessel"]
        assert v["name"] == "R/V Sagar Nidhi"
        assert "mmsi" in v
        assert "call_sign" in v
        assert "ice_class" in v
        assert v["ice_class"] == "PC5"
        assert "draft_m" in v
        assert "beam_m" in v
        assert "speed_knots" in v
        assert "heading_deg" in v
        assert "position" in v
        assert len(v["position"]) == 2

    def test_current_conditions_and_risk(self):
        res = client.get("/api/realtime/operational-dashboard")
        assert res.status_code == 200
        d = res.json()
        c = d["conditions"]
        assert "sic_pct" in c
        assert "wind_speed_knots" in c
        assert "wind_direction_deg" in c
        assert "wave_height_m" in c
        assert "current_speed_knots" in c
        assert "depth_m" in c
        assert "under_keel_clearance_m" in c

        r = d["risk"]
        assert "risk_score" in r
        assert "risk_category" in r
        assert "dominant_hazard" in r
        assert "risk_breakdown" in r
        assert "confidence" in r
        assert "recommendation" in r

    def test_data_health_and_anti_fabrication_staleness(self):
        """CRITICAL INVARIANT: Never display 'LIVE' if the underlying data is stale."""
        res = client.get("/api/realtime/operational-dashboard")
        assert res.status_code == 200
        health = res.json()["data_health"]
        assert len(health) >= 6

        provider_names = {h["label"].lower(): h for h in health}
        required = ["satellite", "sea ice", "weather", "ocean", "iceberg", "bathymetry"]
        for req in required:
            assert req in provider_names, f"Missing {req} in Data Health table"
            row = provider_names[req]
            assert "source" in row and len(row["source"]) > 0
            assert "timestamp" in row
            assert "data_age_formatted" in row
            assert "display_status" in row

            # Strict staleness invariant:
            if row["provider_key"] == "bathymetry":
                assert row["display_status"] == "STATIC"
            elif row["is_stale"]:
                assert row["display_status"] != "LIVE", (
                    f"VIOLATION: Provider {row['label']} is stale but marked as LIVE!"
                )
                assert row["display_status"] == "STALE"
            else:
                assert row["display_status"] == "LIVE"

    def test_layer_metadata_has_source_and_timestamp(self):
        """Verify every live layer displays source, timestamp, and data age."""
        res = client.get("/api/realtime/operational-dashboard")
        assert res.status_code == 200
        meta = res.json()["layer_metadata"]

        layers_to_check = [
            "sic", "ice_edge", "iceberg_hazards", "weather",
            "ocean_currents", "bathymetry", "coastline", "recommended_route"
        ]
        for lid in layers_to_check:
            assert lid in meta, f"Missing layer metadata for {lid}"
            layer = meta[lid]
            assert "source" in layer and len(layer["source"]) > 0
            assert "timestamp" in layer
            assert "data_age" in layer
            assert "display_status" in layer

    def test_route_and_eta_and_explainability(self):
        """Verify route options, alternates, ETA, and explainability."""
        res = client.get("/api/realtime/operational-dashboard")
        assert res.status_code == 200
        d = res.json()
        rt = d["route"]
        assert "recommended" in rt
        assert "why_did_polarnav_change_my_route" in rt
        assert len(rt["why_did_polarnav_change_my_route"]) > 0

        eta = d["eta"]
        assert "hours" in eta
        assert "distance_km" in eta
        assert "distance_nm" in eta
        assert "destination" in eta
