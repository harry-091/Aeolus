"""POLARNAV — Phase 14: Generalization Testing Package."""

from .models import (
    EnvironmentalStressType,
    UnseenVesselConfig,
    NovelCorridorConfig,
    GeneralizationTestRequest,
    GeneralizationTestResult,
    GeneralizationBenchmarkReport,
)
from .engine import (
    GeneralizationTestEngine,
    UNSEEN_VESSEL_CATALOG,
    NOVEL_CORRIDOR_CATALOG,
)
from .service import generalization_service, GeneralizationService

__all__ = [
    "EnvironmentalStressType",
    "UnseenVesselConfig",
    "NovelCorridorConfig",
    "GeneralizationTestRequest",
    "GeneralizationTestResult",
    "GeneralizationBenchmarkReport",
    "GeneralizationTestEngine",
    "UNSEEN_VESSEL_CATALOG",
    "NOVEL_CORRIDOR_CATALOG",
    "generalization_service",
    "GeneralizationService",
]
