"""Vessel tracking module - real historical Antarctic vessel tracks."""
from src.vessel_tracking.loader import load_vessel_tracks, get_vessel_list, get_track, get_latest_position
from src.vessel_tracking.ais_schema import (
    AISRecord,
    AISTrackPoint,
    VoyageSegment,
    AISDatasetSummary,
    AISValidationIssue
)
from src.vessel_tracking.ais_validator import (
    validate_raw_record,
    validate_coordinates,
    validate_speed,
    parse_timestamp
)
from src.vessel_tracking.ais_pipeline import (
    AISPipeline,
    haversine_distance_km
)
from src.vessel_tracking.ais_validator_cli import run_ais_validation_report
from src.vessel_tracking.backtest_engine import execute_route_backtest, get_historical_voyages_catalog
