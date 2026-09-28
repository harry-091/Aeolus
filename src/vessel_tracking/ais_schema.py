"""Canonical data schema for historical AIS and vessel tracking.

Phase 1: Historical AIS Data Layer
Designed for polar maritime navigation and multi-objective routing.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class AISRecord:
    """Normalized individual AIS/GPS position report."""
    vessel_id: str
    timestamp: datetime
    latitude: float
    longitude: float
    speed_knots: Optional[float] = None
    course_deg: Optional[float] = None
    heading_deg: Optional[float] = None
    vessel_type: Optional[str] = "research_icebreaker"
    vessel_name: Optional[str] = None
    mmsi: Optional[str] = None
    source: str = "raw_telemetry"
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if self.timestamp else None
        return d


@dataclass
class AISTrackPoint:
    """Position record enriched with consecutive trajectory metrics."""
    record: AISRecord
    distance_from_prev_km: float = 0.0
    dt_prev_seconds: float = 0.0
    calculated_speed_knots: float = 0.0

    @property
    def timestamp(self) -> datetime:
        return self.record.timestamp

    @property
    def latitude(self) -> float:
        return self.record.latitude

    @property
    def longitude(self) -> float:
        return self.record.longitude

    @property
    def speed_knots(self) -> Optional[float]:
        return self.record.speed_knots

    @property
    def course_deg(self) -> Optional[float]:
        return self.record.course_deg

    @property
    def heading_deg(self) -> Optional[float]:
        return self.record.heading_deg

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "distance_from_prev_km": round(self.distance_from_prev_km, 3),
            "dt_prev_seconds": round(self.dt_prev_seconds, 1),
            "calculated_speed_knots": round(self.calculated_speed_knots, 2),
        }


@dataclass
class VoyageSegment:
    """Coherent reconstructed voyage trip without major transmission gaps."""
    voyage_id: str
    vessel_id: str
    vessel_name: str
    vessel_type: str
    start_time: datetime
    end_time: datetime
    duration_hours: float
    total_distance_km: float
    points: List[AISTrackPoint]
    avg_speed_knots: float
    max_speed_knots: float
    bbox: Dict[str, float]  # min_lat, max_lat, min_lon, max_lon

    def to_dict(self, include_points: bool = True) -> Dict[str, Any]:
        data = {
            "voyage_id": self.voyage_id,
            "vessel_id": self.vessel_id,
            "vessel_name": self.vessel_name,
            "vessel_type": self.vessel_type,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_hours": round(self.duration_hours, 2),
            "total_distance_km": round(self.total_distance_km, 2),
            "point_count": len(self.points),
            "avg_speed_knots": round(self.avg_speed_knots, 2),
            "max_speed_knots": round(self.max_speed_knots, 2),
            "bbox": self.bbox,
        }
        if include_points:
            data["points"] = [p.to_dict() for p in self.points]
        return data


@dataclass
class AISValidationIssue:
    """Diagnostic flag for rejected or sanitized records."""
    record_index: int
    vessel_id: Optional[str]
    issue_type: str  # 'missing_timestamp', 'invalid_coordinates', 'impossible_speed', 'duplicate_timestamp', 'malformed'
    details: str
    raw_snippet: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AISDatasetSummary:
    """Comprehensive diagnostic summary of a historical AIS dataset."""
    vessels_count: int
    voyages_count: int
    points_count: int
    valid_points_count: int
    invalid_records_count: int
    date_range: Dict[str, Optional[str]]  # 'start', 'end'
    missing_data_pct: float  # % of missing optional values across records
    invalid_breakdown: Dict[str, int]
    geographic_coverage: Dict[str, float]  # min_lat, max_lat, min_lon, max_lon
    vessel_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
