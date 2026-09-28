"""POLARNAV — Phase 15: Production Reliability and Failure Handling Test Suite.

Validates:
1. Provider health tracking across all 6 ingestion providers.
2. Resilient circuit-breaker retries with exponential backoff and timeouts.
3. Explicit fallback labeling (never silently pass fallback data as live).
4. Strict stale data detection (never display 'LIVE' when data is stale).
5. Anti-fabrication invariant (never fabricate missing environmental numbers).
6. Severe route confidence reduction when critical data is unavailable or stale.
7. REST API endpoints: audit, simulate-fault, reset, and provider detail.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.server import app
from realtime.reliability.service import reliability_service
from realtime.reliability.models import (
    ProviderId,
    HealthStatus,
    DataAvailabilityState,
    FaultType,
    FaultInjectionConfig,
)
from realtime.reliability.circuit_breaker import retry_with_backoff, with_timeout, fault_registry


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient for reliability endpoints."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_faults():
    """Ensure all simulated faults are cleared before and after each test."""
    fault_registry.clear_all_faults()
    yield
    fault_registry.clear_all_faults()


class TestProductionReliability:
    """Core reliability, failure handling, and anti-fabrication test suite."""

    def test_system_reliability_audit_baseline(self):
        """Verify baseline audit reports all 6 providers healthy with zero fabrication."""
        audit = reliability_service.audit_system()
        assert audit.total_providers == 6
        assert audit.healthy_providers_count == 6
        assert audit.zero_fabrication_guaranteed is True
        assert audit.critical_data_unavailable is False
        assert audit.critical_data_stale is False
        assert audit.max_allowable_route_confidence == 1.0

        for pid in ProviderId:
            assert pid.value in audit.providers
            rec = audit.providers[pid.value]
            assert rec.health_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            assert rec.freshness_threshold_hours > 0.0

    def test_api_failure_and_anti_fabrication_handling(self):
        """Simulate API failure and verify DATA UNAVAILABLE is reported without fabricating numbers."""
        fault = FaultInjectionConfig(
            provider=ProviderId.SATELLITE,
            fault_type=FaultType.API_FAILURE,
            error_message="Connection timed out to Sentinel-1 STAC API",
        )
        audit = reliability_service.simulate_fault(fault)
        
        sat_rec = audit.providers[ProviderId.SATELLITE.value]
        assert sat_rec.health_status == HealthStatus.UNAVAILABLE
        assert sat_rec.availability_state == DataAvailabilityState.DATA_UNAVAILABLE
        assert sat_rec.confidence_multiplier == 0.0
        assert len(sat_rec.limitation_notes) > 0
        assert "forbids synthesizing/fabricating" in sat_rec.limitation_notes[0]

    def test_circuit_breaker_retry_with_backoff(self):
        """Verify retry_with_backoff decorator retries specified times before raising."""
        attempts = 0

        @retry_with_backoff(max_retries=3, initial_delay_sec=0.01, backoff_factor=1.5)
        def failing_remote_query():
            nonlocal attempts
            attempts += 1
            raise ConnectionResetError("Remote server closed socket")

        with pytest.raises(ConnectionResetError):
            failing_remote_query()

        assert attempts == 3, "Circuit breaker must retry exactly 3 times before failing"

    def test_timeout_handling_and_fallback_labeling(self):
        """STRICT INVARIANT: Verify timeout triggers fallback that is EXPLICITLY labelled."""
        fault = FaultInjectionConfig(
            provider=ProviderId.WEATHER,
            fault_type=FaultType.TIMEOUT,
            delay_ms=2500.0,
            force_stale_hours=12.0,
            error_message="ECMWF CDS Gateway read timeout",
        )
        audit = reliability_service.simulate_fault(fault)

        wx_rec = audit.providers[ProviderId.WEATHER.value]
        assert wx_rec.health_status == HealthStatus.DEGRADED
        assert wx_rec.availability_state == DataAvailabilityState.FALLBACK_ACTIVE
        assert wx_rec.is_fallback_active is True
        assert wx_rec.fallback_label == "FALLBACK_CACHE"
        assert wx_rec.confidence_multiplier == 0.50
        assert "explicitly tagged local cache fallback" in wx_rec.limitation_notes[0]

    def test_stale_sic_detection_and_labeling(self):
        """STRICT INVARIANT: Verify sea ice older than 48h displays DATA STALE and never LIVE."""
        fault = FaultInjectionConfig(
            provider=ProviderId.SEA_ICE,
            fault_type=FaultType.STALE_DATA,
            force_stale_hours=72.0,  # Exceeds 48h limit
            error_message="AMSR2 downlink interrupted",
        )
        audit = reliability_service.simulate_fault(fault)

        sic_rec = audit.providers[ProviderId.SEA_ICE.value]
        assert sic_rec.health_status == HealthStatus.STALE
        assert sic_rec.availability_state == DataAvailabilityState.DATA_STALE
        assert sic_rec.availability_state != DataAvailabilityState.LIVE
        assert sic_rec.is_stale is True
        assert audit.critical_data_stale is True
        assert audit.max_allowable_route_confidence <= 0.55

    def test_stale_iceberg_detection_and_labeling(self):
        """STRICT INVARIANT: Verify iceberg data older than 7 days displays DATA STALE."""
        fault = FaultInjectionConfig(
            provider=ProviderId.ICEBERG,
            fault_type=FaultType.STALE_DATA,
            force_stale_hours=210.0,  # > 168h (7 days)
            error_message="NIC weekly consolidation delayed",
        )
        audit = reliability_service.simulate_fault(fault)

        ib_rec = audit.providers[ProviderId.ICEBERG.value]
        assert ib_rec.health_status == HealthStatus.STALE
        assert ib_rec.availability_state == DataAvailabilityState.DATA_STALE
        assert ib_rec.availability_state != DataAvailabilityState.LIVE
        assert ib_rec.is_stale is True

    def test_critical_data_unavailable_route_confidence_reduction(self):
        """Verify that when critical data is UNAVAILABLE, route confidence drops to <= 0.35."""
        fault = FaultInjectionConfig(
            provider=ProviderId.SEA_ICE,
            fault_type=FaultType.NETWORK_FAILURE,
            error_message="Satellite ground station downlink severed",
        )
        audit = reliability_service.simulate_fault(fault)

        assert audit.critical_data_unavailable is True
        assert audit.degraded_routing_operation is True
        assert audit.max_allowable_route_confidence <= 0.35
        assert audit.route_confidence_penalty_pct >= 60.0
        assert "CRITICAL WARNING" in audit.recommendation

    def test_malformed_data_rejection(self):
        """Verify malformed sensor payload is rejected with diagnostics rather than crashing."""
        fault = FaultInjectionConfig(
            provider=ProviderId.OCEAN,
            fault_type=FaultType.MALFORMED_DATA,
            error_message="Corrupted GLO12 NetCDF header",
        )
        audit = reliability_service.simulate_fault(fault)

        ocn_rec = audit.providers[ProviderId.OCEAN.value]
        assert ocn_rec.health_status == HealthStatus.DEGRADED
        assert "MALFORMED DATA" in ocn_rec.limitation_notes[0]

    def test_fault_reset_restores_nominal_operation(self):
        """Verify reset_faults() clears all injected faults and restores nominal status."""
        fault = FaultInjectionConfig(
            provider=ProviderId.WEATHER,
            fault_type=FaultType.API_FAILURE,
        )
        reliability_service.simulate_fault(fault)
        
        # Reset
        clean_audit = reliability_service.reset_faults()
        assert clean_audit.healthy_providers_count == 6
        assert clean_audit.unavailable_providers_count == 0
        assert len(clean_audit.active_fault_injections) == 0
        assert clean_audit.critical_data_unavailable is False


class TestReliabilityAPIEndpoints:
    """Verification suite for Phase 15 Reliability REST API endpoints."""

    def test_api_reliability_audit_endpoint(self, client):
        """Test GET /api/realtime/reliability/audit returns complete system audit."""
        resp = client.get("/api/realtime/reliability/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_providers" in data
        assert "healthy_providers_count" in data
        assert "providers" in data
        assert len(data["providers"]) == 6
        assert data["zero_fabrication_guaranteed"] is True

    def test_api_simulate_fault_and_reset_endpoints(self, client):
        """Test POST /api/realtime/reliability/simulate-fault and POST /api/realtime/reliability/reset."""
        payload = {
            "provider": "weather",
            "fault_type": "TIMEOUT",
            "delay_ms": 2100.0,
            "force_stale_hours": 18.0,
            "error_message": "Upstream ECMWF timeout",
        }
        resp = client.post("/api/realtime/reliability/simulate-fault", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["active_fault_injections"]) > 0
        assert data["providers"]["weather"]["is_fallback_active"] is True
        assert data["providers"]["weather"]["fallback_label"] == "FALLBACK_CACHE"

        # Test Reset
        resp_reset = client.post("/api/realtime/reliability/reset")
        assert resp_reset.status_code == 200
        data_reset = resp_reset.json()
        assert len(data_reset["active_fault_injections"]) == 0
        assert data_reset["healthy_providers_count"] == 6

    def test_api_provider_endpoint(self, client):
        """Test GET /api/realtime/reliability/provider/{provider_id}."""
        resp = client.get("/api/realtime/reliability/provider/sea_ice")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_id"] == "sea_ice"
        assert "availability_state" in data
        assert "freshness_threshold_hours" in data
