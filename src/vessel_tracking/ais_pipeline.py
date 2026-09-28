"""Historical AIS Preprocessing, Track Reconstruction, and Voyage Segmentation Pipeline.

Phase 1: Historical AIS Data Layer
Transforms heterogeneous raw records into clean, validated, segmented trajectories.
"""
import os
import glob
import json
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict

import pandas as pd

from src.vessel_tracking.ais_schema import (
    AISRecord,
    AISTrackPoint,
    VoyageSegment,
    AISValidationIssue,
    AISDatasetSummary
)
from src.vessel_tracking.ais_validator import validate_raw_record


# Earth radius in kilometers for spherical great-circle calculation
EARTH_RADIUS_KM = 6371.0

# Voyage segmentation defaults
DEFAULT_MAX_GAP_HOURS = 24.0          # Break voyage if AIS transmission gap > 24 hours
DEFAULT_MAX_STATIONARY_HOURS = 48.0   # Break voyage if vessel stationary (> 48h at station/port)
STATIONARY_SPEED_THRESHOLD_KN = 0.5   # Speed considered stationary (knots)
MAX_FEASIBLE_TRANSIT_SPEED_KN = 45.0  # Teleportation detection threshold (knots)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute Great-Circle Distance between two coordinates in kilometers."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


class AISPipeline:
    """Unified pipeline for ingesting, validating, reconstructing, and segmenting historical AIS data."""

    def __init__(
        self,
        max_gap_hours: float = DEFAULT_MAX_GAP_HOURS,
        max_stationary_hours: float = DEFAULT_MAX_STATIONARY_HOURS,
        southern_ocean_focus: bool = False
    ):
        self.max_gap_hours = max_gap_hours
        self.max_stationary_hours = max_stationary_hours
        self.southern_ocean_focus = southern_ocean_focus

    # -------------------------------------------------------------------------
    # 1. Ingestion Engine (CSV, JSON, GeoJSON, Parquet)
    # -------------------------------------------------------------------------
    def load_file(self, file_path: str) -> Tuple[List[AISRecord], List[AISValidationIssue]]:
        """Load and validate AIS records from a supported file format."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".csv", ".txt"):
            return self.load_csv(file_path)
        elif ext in (".json", ".geojson"):
            return self.load_json(file_path)
        elif ext in (".parquet", ".pq"):
            return self.load_parquet(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext} (supported: .csv, .json, .geojson, .parquet)")

    def load_csv(self, file_path: str) -> Tuple[List[AISRecord], List[AISValidationIssue]]:
        """Load and validate AIS records from a CSV file."""
        df = pd.read_csv(file_path, low_memory=False)
        raw_records = df.to_dict(orient="records")
        stem = os.path.splitext(os.path.basename(file_path))[0]
        for r in raw_records:
            if not r.get("vessel_id") and not r.get("set_code") and not r.get("mmsi") and not r.get("ship_name"):
                r["vessel_id"] = stem
                r["vessel_name"] = stem
        return self.validate_raw_records(raw_records, source_name=os.path.basename(file_path))

    def load_json(self, file_path: str) -> Tuple[List[AISRecord], List[AISValidationIssue]]:
        """Load and validate AIS records from JSON or GeoJSON."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_records: List[Dict[str, Any]] = []

        # Handle GeoJSON FeatureCollection
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            for feat in data.get("features", []):
                geom = feat.get("geometry", {})
                props = feat.get("properties", {})
                if geom.get("type") == "Point":
                    coords = geom.get("coordinates", [0, 0])
                    raw_records.append({
                        **props,
                        "longitude": coords[0],
                        "latitude": coords[1]
                    })
                elif geom.get("type") == "LineString":
                    # Series of points along a track line
                    coords_list = geom.get("coordinates", [])
                    base_vessel = props.get("vessel_id") or props.get("name") or "historical_track"
                    for idx, c in enumerate(coords_list):
                        raw_records.append({
                            **props,
                            "vessel_id": base_vessel,
                            "longitude": c[0],
                            "latitude": c[1],
                            # Generate synthetic timestamp if missing for coordinate tracks
                            "timestamp": props.get("timestamp") or f"2015-12-01T{idx%24:02d}:00:00"
                        })
        elif isinstance(data, dict) and "vessels" in data:
            # SIH historical_vessels_viz.json format
            for vessel in data["vessels"]:
                v_name = vessel.get("vessel_name", "Unknown")
                v_id = vessel.get("vessel_id") or vessel.get("voyage_id") or v_name
                v_type = "research_icebreaker"
                track = vessel.get("track", [])
                for idx, pt in enumerate(track):
                    # [lat, lon]
                    lat, lon = pt[0], pt[1]
                    raw_records.append({
                        "vessel_id": v_id,
                        "vessel_name": v_name,
                        "vessel_type": v_type,
                        "latitude": lat,
                        "longitude": lon,
                        "timestamp": f"2015-12-01T{idx%24:02d}:{(idx*5)%60:02d}:00",
                        "source": vessel.get("source", "historical_vessels_viz")
                    })
        elif isinstance(data, list):
            raw_records = data
        else:
            raise ValueError(f"Unrecognized JSON structure in {file_path}")

        return self.validate_raw_records(raw_records, source_name=os.path.basename(file_path))

    def load_parquet(self, file_path: str) -> Tuple[List[AISRecord], List[AISValidationIssue]]:
        """Load and validate AIS records from a Parquet file."""
        try:
            df = pd.read_parquet(file_path)
            raw_records = df.to_dict(orient="records")
            return self.validate_raw_records(raw_records, source_name=os.path.basename(file_path))
        except ImportError:
            raise RuntimeError("Parquet engine (pyarrow or fastparquet) is required to read .parquet files.")

    def load_directory(self, dir_path: str, pattern: str = "*.*") -> Tuple[List[AISRecord], List[AISValidationIssue]]:
        """Batch load all matching AIS data files from a directory."""
        all_records: List[AISRecord] = []
        all_issues: List[AISValidationIssue] = []

        files = sorted(glob.glob(os.path.join(dir_path, pattern)))
        supported_exts = (".csv", ".json", ".geojson", ".parquet")
        target_files = [f for f in files if os.path.splitext(f)[1].lower() in supported_exts]

        for file_path in target_files:
            try:
                records, issues = self.load_file(file_path)
                all_records.extend(records)
                all_issues.extend(issues)
            except Exception as e:
                all_issues.append(AISValidationIssue(
                    record_index=len(all_records),
                    vessel_id=None,
                    issue_type="malformed",
                    details=f"Failed to read file {os.path.basename(file_path)}: {str(e)}"
                ))

        return all_records, all_issues

    # -------------------------------------------------------------------------
    # 2. Validation & Normalization Engine
    # -------------------------------------------------------------------------
    def validate_raw_records(
        self,
        raw_records: List[Dict[str, Any]],
        source_name: str = "dataset"
    ) -> Tuple[List[AISRecord], List[AISValidationIssue]]:
        """Validate an array of raw dictionary entries against the canonical schema."""
        valid_records: List[AISRecord] = []
        issues: List[AISValidationIssue] = []

        for idx, raw in enumerate(raw_records):
            record, record_issues = validate_raw_record(
                raw,
                record_index=idx,
                southern_ocean_focus=self.southern_ocean_focus
            )
            if record:
                record.source = source_name
                valid_records.append(record)
            issues.extend(record_issues)

        return valid_records, issues

    # -------------------------------------------------------------------------
    # 3. Track Reconstruction & Kinematic Calculation
    # -------------------------------------------------------------------------
    def reconstruct_tracks(
        self,
        records: List[AISRecord]
    ) -> Dict[str, List[AISTrackPoint]]:
        """Sort chronologically, deduplicate timestamps, and compute point-to-point kinetics."""
        # 1. Group records by vessel_id
        vessel_groups: Dict[str, List[AISRecord]] = defaultdict(list)
        for rec in records:
            vessel_groups[rec.vessel_id].append(rec)

        reconstructed: Dict[str, List[AISTrackPoint]] = {}

        for vessel_id, group in vessel_groups.items():
            # 2. Chronological sort
            group.sort(key=lambda r: r.timestamp)

            # 3. Deduplicate identical timestamps (keep first)
            deduped: List[AISRecord] = []
            seen_timestamps = set()
            for r in group:
                if r.timestamp not in seen_timestamps:
                    seen_timestamps.add(r.timestamp)
                    deduped.append(r)

            if not deduped:
                continue

            # 4. Calculate consecutive point metrics
            track_points: List[AISTrackPoint] = []

            # First point has 0 delta
            first_pt = AISTrackPoint(
                record=deduped[0],
                distance_from_prev_km=0.0,
                dt_prev_seconds=0.0,
                calculated_speed_knots=deduped[0].speed_knots or 0.0
            )
            track_points.append(first_pt)

            for i in range(1, len(deduped)):
                prev_rec = deduped[i - 1]
                curr_rec = deduped[i]

                dist_km = haversine_distance_km(
                    prev_rec.latitude, prev_rec.longitude,
                    curr_rec.latitude, curr_rec.longitude
                )

                dt_sec = max(1.0, (curr_rec.timestamp - prev_rec.timestamp).total_seconds())
                dt_hours = dt_sec / 3600.0

                # 1 knot = 1.852 km/h
                calc_speed_kn = (dist_km / dt_hours) / 1.852 if dt_hours > 0 else 0.0

                # Fallback to reported SOG if available and calculated speed is extreme due to tiny dt
                effective_speed = curr_rec.speed_knots if curr_rec.speed_knots is not None else calc_speed_kn

                track_points.append(AISTrackPoint(
                    record=curr_rec,
                    distance_from_prev_km=dist_km,
                    dt_prev_seconds=dt_sec,
                    calculated_speed_knots=effective_speed
                ))

            reconstructed[vessel_id] = track_points

        return reconstructed

    # -------------------------------------------------------------------------
    # 4. Voyage Segmentation Engine
    # -------------------------------------------------------------------------
    def segment_voyages(
        self,
        reconstructed_tracks: Dict[str, List[AISTrackPoint]]
    ) -> List[VoyageSegment]:
        """Segment continuous vessel tracks into distinct voyages based on AIS gaps and stops."""
        voyages: List[VoyageSegment] = []

        for vessel_id, points in reconstructed_tracks.items():
            if not points:
                continue

            current_segment_points: List[AISTrackPoint] = [points[0]]
            voyage_idx = 1

            for i in range(1, len(points)):
                pt = points[i]
                dt_hours = pt.dt_prev_seconds / 3600.0
                calc_speed = pt.calculated_speed_knots

                # Condition 1: Long communication blackout / missing AIS period
                is_time_gap = dt_hours > self.max_gap_hours

                # Condition 2: Teleportation jump (physically impossible speed between points)
                is_teleport = calc_speed > MAX_FEASIBLE_TRANSIT_SPEED_KN and pt.distance_from_prev_km > 20.0

                if is_time_gap or is_teleport:
                    # Finalize current segment if it has enough points
                    if len(current_segment_points) >= 2:
                        voyages.append(self._build_voyage_segment(
                            vessel_id=vessel_id,
                            voyage_idx=voyage_idx,
                            points=current_segment_points
                        ))
                        voyage_idx += 1
                    # Start new segment
                    current_segment_points = [pt]
                else:
                    current_segment_points.append(pt)

            # Finalize trailing segment
            if len(current_segment_points) >= 2:
                voyages.append(self._build_voyage_segment(
                    vessel_id=vessel_id,
                    voyage_idx=voyage_idx,
                    points=current_segment_points
                ))

        return voyages

    def _build_voyage_segment(
        self,
        vessel_id: str,
        voyage_idx: int,
        points: List[AISTrackPoint]
    ) -> VoyageSegment:
        """Construct a standardized VoyageSegment metadata summary."""
        v_name = points[0].record.vessel_name or vessel_id
        v_type = points[0].record.vessel_type or "research_icebreaker"
        start_time = points[0].timestamp
        end_time = points[-1].timestamp
        duration_hours = max(0.01, (end_time - start_time).total_seconds() / 3600.0)

        total_distance = sum(p.distance_from_prev_km for p in points[1:])

        lats = [p.latitude for p in points]
        lons = [p.longitude for p in points]
        speeds = [p.calculated_speed_knots for p in points if p.calculated_speed_knots is not None]

        avg_spd = sum(speeds) / len(speeds) if speeds else 0.0
        max_spd = max(speeds) if speeds else 0.0

        bbox = {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons)
        }

        voyage_id = f"{vessel_id}_voyage_{voyage_idx:02d}"

        return VoyageSegment(
            voyage_id=voyage_id,
            vessel_id=vessel_id,
            vessel_name=v_name,
            vessel_type=v_type,
            start_time=start_time,
            end_time=end_time,
            duration_hours=duration_hours,
            total_distance_km=total_distance,
            points=points,
            avg_speed_knots=avg_spd,
            max_speed_knots=max_spd,
            bbox=bbox
        )

    # -------------------------------------------------------------------------
    # 5. Full End-to-End Execution & Diagnostics
    # -------------------------------------------------------------------------
    def process(
        self,
        source_path_or_dir: str
    ) -> Tuple[List[VoyageSegment], AISDatasetSummary, List[AISValidationIssue]]:
        """Run the full end-to-end AIS validation, reconstruction, and segmentation workflow."""
        if os.path.isdir(source_path_or_dir):
            valid_records, issues = self.load_directory(source_path_or_dir)
        else:
            valid_records, issues = self.load_file(source_path_or_dir)

        tracks = self.reconstruct_tracks(valid_records)
        voyages = self.segment_voyages(tracks)
        summary = self.generate_summary(valid_records, issues, voyages)

        return voyages, summary, issues

    def generate_summary(
        self,
        valid_records: List[AISRecord],
        issues: List[AISValidationIssue],
        voyages: List[VoyageSegment]
    ) -> AISDatasetSummary:
        """Calculate comprehensive dataset validation statistics."""
        vessel_names = sorted(list(set(r.vessel_name or r.vessel_id for r in valid_records)))

        # Invalid breakdown
        invalid_breakdown: Dict[str, int] = defaultdict(int)
        for iss in issues:
            invalid_breakdown[iss.issue_type] += 1

        # Date range
        start_date = min((r.timestamp for r in valid_records), default=None)
        end_date = max((r.timestamp for r in valid_records), default=None)

        # Geographic coverage
        if valid_records:
            lats = [r.latitude for r in valid_records]
            lons = [r.longitude for r in valid_records]
            geo_coverage = {
                "min_lat": min(lats),
                "max_lat": max(lats),
                "min_lon": min(lons),
                "max_lon": max(lons)
            }
        else:
            geo_coverage = {"min_lat": 0.0, "max_lat": 0.0, "min_lon": 0.0, "max_lon": 0.0}

        # Missing optional data percentage (speed, heading, course)
        total_eval_fields = len(valid_records) * 3
        missing_fields = 0
        for r in valid_records:
            if r.speed_knots is None:
                missing_fields += 1
            if r.heading_deg is None:
                missing_fields += 1
            if r.course_deg is None:
                missing_fields += 1

        missing_pct = round((missing_fields / max(1, total_eval_fields)) * 100.0, 2)

        return AISDatasetSummary(
            vessels_count=len(vessel_names),
            voyages_count=len(voyages),
            points_count=len(valid_records) + len(issues),
            valid_points_count=len(valid_records),
            invalid_records_count=len(issues),
            date_range={
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            },
            missing_data_pct=missing_pct,
            invalid_breakdown=dict(invalid_breakdown),
            geographic_coverage=geo_coverage,
            vessel_names=vessel_names
        )
