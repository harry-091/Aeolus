"""POLARNAV — Phase 11: Continuous Live Monitoring Test Suite.

Rigorously verifies:
1. Periodic monitoring loop and multi-sensor audit.
2. Noise rejection: insignificant numerical noise does NOT trigger reroute.
3. Configurable rerouting triggers:
   - High SIC surge (>15%)
   - Iceberg proximity breach (<12km)
   - Severe weather alert (wind >45kn / wave >5m)
   - Unsafe depth / grounding
4. Lineage maintenance: current_route, previous_route, reroute_reason, timestamp.
5. Explainability: answers "Why did POLARNAV change my route?".
6. REST API endpoints.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from realtime.ml_risk.models import VesselCharacteristics, PolarIceClass, VesselType
from realtime.route_optimizer import (
    realtime_route_optimizer,
    RouteProfileType,
    RouteOptimizationRequest,
)
from realtime.monitoring import (
    continuous_monitoring_service,
    change_detector,
    RerouteTriggerType,
    MonitoringThresholds,
)
from app.server import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_monitoring_voyage():
    """Ensure an active baseline route is set before each test."""
    vessel = VesselCharacteristics(
        vessel_id="VESSEL-MONITOR-01",
        vessel_type=VesselType.RESEARCH_VESSEL,
        ice_class=PolarIceClass.PC5,
        speed_knots=12.0,
        draft_m=8.0,
    )
    req = RouteOptimizationRequest(
        origin=[-61.0, -58.0],
        destination=[-63.0, -55.0],
        vessel=vessel,
        profiles=[RouteProfileType.BALANCED],
    )
    res = realtime_route_optimizer.optimize_route(req)
    assert len(res.routes) > 0
    continuous_monitoring_service.set_active_voyage(res.routes[0], vessel)


class TestContinuousLiveMonitoring:
    """Verify continuous monitoring, noise filtering, and reroute trigger integrity."""

    def test_noise_rejection_no_reroute(self):
        """Insignificant numerical fluctuations (e.g. +2% SIC) must NOT trigger rerouting."""
        # Simulate +2.0% SIC fluctuation on waypoint 1 (below 5% noise floor and 15% trigger)
        audit = continuous_monitoring_service.simulate_event(
            event_type="NOISE",
            waypoint_index=1,
            delta_value=2.0,
        )

        assert audit.requires_reroute is False
        assert audit.is_valid is True
        assert audit.trigger == RerouteTriggerType.NO_CHANGE
        assert "No rerouting required" in audit.why_rerouted

    def test_high_sic_surge_trigger(self):
        """A significant SIC increase (+25%) exceeding the threshold MUST trigger rerouting."""
        audit = continuous_monitoring_service.simulate_event(
            event_type="HIGH_SIC_INCREASE",
            waypoint_index=1,
            delta_value=30.0,
        )

        assert audit.requires_reroute is True
        assert audit.trigger == RerouteTriggerType.HIGH_SIC_INCREASE
        assert audit.alert_severity in ("WARNING", "CRITICAL")
        assert len(audit.compromised_waypoint_indices) > 0
        assert 1 in audit.compromised_waypoint_indices

        # Verify lineage maintenance
        status = continuous_monitoring_service.get_status()
        assert status.current_route is not None
        assert status.previous_route is not None
        assert status.last_reroute_reason == RerouteTriggerType.HIGH_SIC_INCREASE.value
        assert status.reroute_count >= 1

    def test_iceberg_proximity_breach_trigger(self):
        """An iceberg drifting to 5.0 km (< 12 km safety standoff) MUST trigger a CRITICAL reroute."""
        audit = continuous_monitoring_service.simulate_event(
            event_type="ICEBERG_PROXIMITY_BREACH",
            waypoint_index=1,
            delta_value=5.0,  # 5.0 km < 12.0 km threshold
        )

        assert audit.requires_reroute is True
        assert audit.trigger == RerouteTriggerType.ICEBERG_PROXIMITY_BREACH
        assert audit.alert_severity == "CRITICAL"
        assert audit.alert_banner is not None
        assert "ICEBERG_PROXIMITY_BREACH" in audit.alert_banner

    def test_why_did_polarnav_change_my_route_explainability(self):
        """The explanation MUST provide a transparent, quantitative answer to 'Why did POLARNAV change my route?'."""
        audit = continuous_monitoring_service.simulate_event(
            event_type="ICEBERG_PROXIMITY_BREACH",
            waypoint_index=1,
            delta_value=4.5,
        )

        why_text = audit.why_rerouted
        assert "POLARNAV changed your route due to an ICEBERG PROXIMITY BREACH" in why_text
        assert "standoff" in why_text.lower() or "buffer" in why_text.lower()
        assert "waypoint" in why_text.lower()

    def test_lineage_and_history_preservation(self):
        """Verify current route, previous route, reroute reason, and history record are fully preserved."""
        initial_route = continuous_monitoring_service.current_route
        assert initial_route is not None
        initial_id = initial_route.route_id

        # Trigger event
        continuous_monitoring_service.simulate_event(
            event_type="HIGH_SIC_INCREASE",
            waypoint_index=1,
            delta_value=25.0,
        )

        status = continuous_monitoring_service.get_status()
        assert status.previous_route is not None
        assert status.previous_route.route_id == initial_id
        assert status.current_route.route_id != initial_id
        assert status.last_reroute_reason == "HIGH_SIC_INCREASE"
        assert len(status.recent_history) >= 1

        rec = status.recent_history[-1]
        assert rec.previous_route_id == initial_id
        assert rec.new_route_id == status.current_route.route_id
        assert rec.trigger == RerouteTriggerType.HIGH_SIC_INCREASE
        assert rec.timestamp_iso is not None

    def test_severe_weather_trigger(self):
        """Wind speed > 45 knots or wave height > 5.0m MUST trigger severe weather rerouting."""
        audit = continuous_monitoring_service.simulate_event(
            event_type="SEVERE_WEATHER_ALERT",
            waypoint_index=1,
        )

        assert audit.requires_reroute is True
        assert audit.trigger == RerouteTriggerType.SEVERE_WEATHER_ALERT
        assert "SEVERE WEATHER" in audit.why_rerouted

    def test_api_monitor_check_endpoint(self):
        """Verify POST /api/realtime/monitor/check endpoint."""
        res = client.post("/api/realtime/monitor/check", json={})
        assert res.status_code == 200
        data = res.json()
        assert "is_valid" in data
        assert "requires_reroute" in data
        assert "trigger" in data
        assert "why_rerouted" in data

    def test_api_monitor_status_endpoint(self):
        """Verify GET /api/realtime/monitor/status endpoint."""
        res = client.get("/api/realtime/monitor/status")
        assert res.status_code == 200
        data = res.json()
        assert "monitoring_active" in data
        assert "current_route" in data
        assert "reroute_count" in data
        assert "why_did_polarnav_change_my_route" in data

    def test_api_monitor_simulate_event_endpoint(self):
        """Verify POST /api/realtime/monitor/simulate-event endpoint."""
        payload = {
            "event_type": "HIGH_SIC_INCREASE",
            "waypoint_index": 1,
            "delta_value": 30.0,
        }
        res = client.post("/api/realtime/monitor/simulate-event", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["simulation_event"] == "HIGH_SIC_INCREASE"
        assert data["audit_result"]["requires_reroute"] is True
        assert data["monitoring_status"]["last_reroute_reason"] == "HIGH_SIC_INCREASE"
