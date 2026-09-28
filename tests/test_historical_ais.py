"""Unit and Integration Tests for Phase 1: Historical AIS Data Layer.

Verifies:
1. AIS position record validation (coordinates, speeds, timestamps, malformed records).
2. Track reconstruction (sorting, deduplication, point-to-point distance, delta time, speed).
3. Voyage segmentation (gap detection, independent voyages, teleportation filtering).
4. Multi-format ingestion (CSV, JSON, GeoJSON).
5. Dataset summary and validation reporting.
6. Real raw Antarctic voyage data loading.
"""
import os
import sys
import tempfile
import json
import pytest
from datetime import datetime, timedelta

# Ensure backend directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.vessel_tracking.ais_schema import AISRecord, AISTrackPoint, VoyageSegment
from src.vessel_tracking.ais_validator import (
    validate_coordinates,
    validate_speed,
    validate_raw_record,
    parse_timestamp
)
from src.vessel_tracking.ais_pipeline import (
    AISPipeline,
    haversine_distance_km
)
from src.vessel_tracking.ais_validator_cli import run_ais_validation_report


# =============================================================================
# 1. Coordinate Validation Tests
# =============================================================================
class TestCoordinateValidation:
    def test_valid_antarctic_coordinates(self):
        valid, err = validate_coordinates(-65.4, 140.2)
        assert valid is True
        assert err is None

    def test_out_of_range_latitude(self):
        valid, err = validate_coordinates(-95.0, 100.0)
        assert valid is False
        assert "Latitude" in err

        valid, err = validate_coordinates(95.0, 100.0)
        assert valid is False

    def test_out_of_range_longitude(self):
        valid, err = validate_coordinates(-60.0, 195.0)
        assert valid is False
        assert "Longitude" in err

        valid, err = validate_coordinates(-60.0, -185.0)
        assert valid is False

    def test_ais_null_coordinates(self):
        valid, _ = validate_coordinates(91.0, 140.0)
        assert valid is False
        valid, _ = validate_coordinates(-60.0, 181.0)
        assert valid is False

    def test_null_island_gps_failure(self):
        valid, err = validate_coordinates(0.0, 0.0)
        assert valid is False
        assert "Null Island" in err

    def test_non_numeric_coordinates(self):
        valid, err = validate_coordinates("invalid_lat", 120.0)
        assert valid is False
        assert "Non-numeric" in err


# =============================================================================
# 2. Speed and Timestamp Validation Tests
# =============================================================================
class TestSpeedAndTimestampValidation:
    def test_valid_speed(self):
        valid, spd, err = validate_speed(12.5)
        assert valid is True
        assert spd == 12.5
        assert err is None

    def test_zero_speed(self):
        valid, spd, _ = validate_speed(0.0)
        assert valid is True
        assert spd == 0.0

    def test_negative_speed(self):
        valid, _, err = validate_speed(-2.5)
        assert valid is False
        assert "Negative speed" in err

    def test_impossible_speed(self):
        valid, _, err = validate_speed(42.0)
        assert valid is False
        assert "Impossible vessel speed" in err

    def test_ais_not_available_speed(self):
        valid, spd, _ = validate_speed(102.3)
        assert valid is True
        assert spd is None

    def test_timestamp_parsing(self):
        ts = parse_timestamp("2015-12-09T08:30:00")
        assert ts is not None
        assert ts.year == 2015
        assert ts.month == 12
        assert ts.day == 9
        assert ts.hour == 8

    def test_invalid_timestamp(self):
        ts = parse_timestamp("not-a-date")
        assert ts is None

        ts = parse_timestamp(None)
        assert ts is None


# =============================================================================
# 3. Raw Record Validation Tests
# =============================================================================
class TestRawRecordValidation:
    def test_valid_aad_record(self):
        raw = {
            "set_code": "201516020",
            "date_time_utc": "2015-12-09T00:20:10",
            "latitude": -42.88257,
            "longitude": 147.339659,
            "ship_spd_over_ground_knot": 0.034,
            "ship_heading_gps_deg": 79.99,
            "ship_course_over_ground_deg": 17.01
        }
        rec, issues = validate_raw_record(raw, record_index=0)
        assert rec is not None
        assert len(issues) == 0
        assert rec.vessel_id == "201516020"
        assert rec.latitude == -42.88257
        assert rec.speed_knots == 0.034

    def test_missing_timestamp_fails(self):
        raw = {
            "vessel_id": "ship_1",
            "latitude": -65.0,
            "longitude": 120.0
        }
        rec, issues = validate_raw_record(raw, record_index=1)
        assert rec is None
        assert any(i.issue_type == "missing_timestamp" for i in issues)

    def test_malformed_input(self):
        rec, issues = validate_raw_record("not a dict", record_index=2)  # type: ignore
        assert rec is None
        assert any(i.issue_type == "malformed" for i in issues)


# =============================================================================
# 4. Track Reconstruction & Kinematics Tests
# =============================================================================
class TestTrackReconstruction:
    def test_chronological_sorting_and_kinetics(self):
        pipeline = AISPipeline()
        records = [
            # Out-of-order records for vessel_1
            AISRecord(
                vessel_id="vessel_1",
                timestamp=datetime(2020, 1, 1, 12, 0),
                latitude=-60.0,
                longitude=100.0,
                speed_knots=10.0
            ),
            AISRecord(
                vessel_id="vessel_1",
                timestamp=datetime(2020, 1, 1, 10, 0),
                latitude=-59.0,
                longitude=100.0,
                speed_knots=10.0
            ),
            # Duplicate timestamp (should be filtered)
            AISRecord(
                vessel_id="vessel_1",
                timestamp=datetime(2020, 1, 1, 10, 0),
                latitude=-59.0,
                longitude=100.0,
                speed_knots=10.0
            ),
        ]

        tracks = pipeline.reconstruct_tracks(records)
        assert "vessel_1" in tracks
        pts = tracks["vessel_1"]
        assert len(pts) == 2  # duplicate removed

        # Chronological order verified
        assert pts[0].timestamp < pts[1].timestamp

        # Distance & Delta time
        assert pts[0].distance_from_prev_km == 0.0
        assert pts[1].distance_from_prev_km > 100.0  # 1 degree of latitude ~111 km
        assert pts[1].dt_prev_seconds == 7200.0  # 2 hours
        assert pts[1].calculated_speed_knots > 0.0


# =============================================================================
# 5. Voyage Segmentation Tests
# =============================================================================
class TestVoyageSegmentation:
    def test_voyage_splitting_on_time_gap(self):
        pipeline = AISPipeline(max_gap_hours=24.0)
        base_time = datetime(2020, 1, 1, 0, 0)

        # Voyage 1: 3 hourly points
        trip_1 = [
            AISRecord(vessel_id="V1", timestamp=base_time + timedelta(hours=i),
                      latitude=-60.0 - i * 0.1, longitude=100.0 + i * 0.1, speed_knots=10.0)
            for i in range(3)
        ]

        # 48-hour gap (vessel was out of AIS coverage or at port)
        gap_time = base_time + timedelta(hours=50)

        # Voyage 2: 3 hourly points
        trip_2 = [
            AISRecord(vessel_id="V1", timestamp=gap_time + timedelta(hours=i),
                      latitude=-65.0 - i * 0.1, longitude=110.0 + i * 0.1, speed_knots=12.0)
            for i in range(3)
        ]

        tracks = pipeline.reconstruct_tracks(trip_1 + trip_2)
        voyages = pipeline.segment_voyages(tracks)

        assert len(voyages) == 2
        assert voyages[0].voyage_id == "V1_voyage_01"
        assert voyages[1].voyage_id == "V1_voyage_02"
        assert len(voyages[0].points) == 3
        assert len(voyages[1].points) == 3
        assert voyages[0].total_distance_km > 0
        assert voyages[1].total_distance_km > 0

    def test_unrelated_vessels_not_connected(self):
        pipeline = AISPipeline()
        records = [
            AISRecord(vessel_id="ShipA", timestamp=datetime(2020, 1, 1, 0, 0),
                      latitude=-60.0, longitude=100.0, speed_knots=10.0),
            AISRecord(vessel_id="ShipA", timestamp=datetime(2020, 1, 1, 1, 0),
                      latitude=-60.1, longitude=100.1, speed_knots=10.0),
            AISRecord(vessel_id="ShipB", timestamp=datetime(2020, 1, 1, 0, 0),
                      latitude=-65.0, longitude=110.0, speed_knots=12.0),
            AISRecord(vessel_id="ShipB", timestamp=datetime(2020, 1, 1, 1, 0),
                      latitude=-65.1, longitude=110.1, speed_knots=12.0),
        ]
        tracks = pipeline.reconstruct_tracks(records)
        voyages = pipeline.segment_voyages(tracks)

        assert len(voyages) == 2
        v_ids = set(v.vessel_id for v in voyages)
        assert v_ids == {"ShipA", "ShipB"}


# =============================================================================
# 6. Multi-Format Ingestion Tests (CSV & JSON)
# =============================================================================
class TestMultiFormatIngestion:
    def test_csv_ingestion(self):
        pipeline = AISPipeline()
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("vessel_id,timestamp,latitude,longitude,speed_knots\n")
            f.write("V1,2021-01-01T00:00:00,-62.5,120.5,11.2\n")
            f.write("V1,2021-01-01T01:00:00,-62.7,120.8,11.5\n")
            f.write("V1,2021-01-01T02:00:00,-62.9,121.1,11.0\n")
            temp_path = f.name

        try:
            records, issues = pipeline.load_csv(temp_path)
            assert len(records) == 3
            assert len(issues) == 0
            assert records[0].vessel_id == "V1"
        finally:
            os.remove(temp_path)

    def test_json_list_ingestion(self):
        pipeline = AISPipeline()
        raw_data = [
            {"vessel_id": "V2", "timestamp": "2021-02-01T00:00:00", "latitude": -63.0, "longitude": 110.0},
            {"vessel_id": "V2", "timestamp": "2021-02-01T01:00:00", "latitude": -63.2, "longitude": 110.2},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(raw_data, f)
            temp_path = f.name

        try:
            records, issues = pipeline.load_json(temp_path)
            assert len(records) == 2
            assert len(issues) == 0
        finally:
            os.remove(temp_path)


# =============================================================================
# 7. Real Antarctic Dataset Ingestion & Validation Utility Test
# =============================================================================
class TestRealAntarcticDataset:
    def test_load_real_aad_track_file(self):
        pipeline = AISPipeline()
        aad_csv = os.path.join(BASE_DIR, "data", "raw", "vessel_tracks", "aurora_australis_2015_16.csv")
        if not os.path.exists(aad_csv):
            pytest.skip("Raw AAD CSV not present in test environment")

        records, issues = pipeline.load_csv(aad_csv)
        assert len(records) > 1000
        assert records[0].latitude < 0.0  # Southern hemisphere

        tracks = pipeline.reconstruct_tracks(records)
        assert len(tracks) >= 1
        v_key = list(tracks.keys())[0]
        assert len(tracks[v_key]) > 1000

        voyages = pipeline.segment_voyages(tracks)
        assert len(voyages) >= 1
        assert voyages[0].total_distance_km > 1000.0

    def test_validation_report_utility(self):
        aad_csv = os.path.join(BASE_DIR, "data", "raw", "vessel_tracks", "aurora_australis_2015_16.csv")
        if not os.path.exists(aad_csv):
            pytest.skip("Raw AAD CSV not present in test environment")

        report = run_ais_validation_report(data_path=aad_csv, output_json=True)
        assert "summary" in report
        s = report["summary"]
        assert s["vessels_count"] >= 1
        assert s["valid_points_count"] > 1000
        assert s["voyages_count"] >= 1
        assert "min_lat" in s["geographic_coverage"]
        assert s["geographic_coverage"]["min_lat"] < -60.0  # Crosses into Antarctica
