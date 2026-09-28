"""POLARNAV — Phase 14: Generalization Service Singleton.

Provides thread-safe access to the generalization test engine and benchmark suite.
"""

from .engine import (
    GeneralizationTestEngine,
    UNSEEN_VESSEL_CATALOG,
    NOVEL_CORRIDOR_CATALOG,
)
from .models import (
    UnseenVesselConfig,
    NovelCorridorConfig,
    GeneralizationTestRequest,
    GeneralizationTestResult,
    GeneralizationBenchmarkReport,
    EnvironmentalStressType,
)


class GeneralizationService:
    """Service wrapper for offline and live generalization testing."""

    def __init__(self):
        self._engine = GeneralizationTestEngine()

    @property
    def engine(self) -> GeneralizationTestEngine:
        return self._engine

    def get_catalog(self):
        """Return catalog of standard unseen vessels and novel corridors."""
        return {
            "unseen_vessels": [v.model_dump() for v in UNSEEN_VESSEL_CATALOG.values()],
            "novel_corridors": [c.model_dump() for c in NOVEL_CORRIDOR_CATALOG.values()],
            "stress_conditions": [e.value for e in EnvironmentalStressType],
        }

    def run_test(self, req: GeneralizationTestRequest) -> GeneralizationTestResult:
        """Run custom generalization test scenario."""
        return self._engine.test_scenario(
            vessel=req.vessel,
            corridor=req.corridor,
            stress=req.stress_condition,
            profile=req.profile,
        )

    def run_benchmark(self) -> GeneralizationBenchmarkReport:
        """Run full standard generalization benchmark suite."""
        return self._engine.run_benchmark_suite()


# Global Singleton Instance
generalization_service = GeneralizationService()
