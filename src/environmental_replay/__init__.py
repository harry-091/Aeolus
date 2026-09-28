"""Historical Environmental Replay Package.

Phase 2: Historical Environmental Replay Dataset.
Associates historical AIS observations with leak-free environmental conditions
(SIC, bathymetry, icebergs, coastline proximity, ocean currents, and composite risk).
"""
from src.environmental_replay.replay_schema import (
    EnrichedAISFeaturePoint,
    ReplayDatasetSummary
)
from src.environmental_replay.environmental_matcher import (
    EnvironmentalMatcher
)
from src.environmental_replay.replay_pipeline import (
    EnvironmentalReplayPipeline
)
from src.environmental_replay.dataset_quality_report import (
    run_environmental_quality_report
)

__all__ = [
    "EnrichedAISFeaturePoint",
    "ReplayDatasetSummary",
    "EnvironmentalMatcher",
    "EnvironmentalReplayPipeline",
    "run_environmental_quality_report",
]
