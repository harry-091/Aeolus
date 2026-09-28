"""POLARNAV — Phase 15: Production Reliability Service.

Provides a thread-safe singleton interface for system audits, fault simulations,
and resilience telemetry queries.
"""

from typing import Dict, List, Optional, Any

from .models import (
    ProviderId,
    HealthStatus,
    DataAvailabilityState,
    FaultType,
    FaultInjectionConfig,
    ProviderReliabilityRecord,
    SystemReliabilityAudit,
)
from .circuit_breaker import fault_registry, retry_with_backoff, with_timeout
from .audit import ReliabilityAuditor


class ReliabilityService:
    """Singleton service for real-time reliability and failure handling."""

    def __init__(self):
        self._auditor = ReliabilityAuditor()

    def audit_system(self) -> SystemReliabilityAudit:
        """Run full system reliability audit."""
        return self._auditor.audit_full_system()

    def audit_provider(self, provider_id: ProviderId) -> ProviderReliabilityRecord:
        """Audit a single provider."""
        return self._auditor.audit_provider(provider_id)

    def simulate_fault(self, fault: FaultInjectionConfig) -> SystemReliabilityAudit:
        """Inject a simulated failure into a provider and return updated system audit."""
        fault_registry.inject_fault(fault)
        return self._auditor.audit_full_system()

    def reset_faults(self) -> SystemReliabilityAudit:
        """Clear all simulated failures and return refreshed system audit."""
        fault_registry.clear_all_faults()
        return self._auditor.audit_full_system()


# Global Singleton Instance
reliability_service = ReliabilityService()
