"""Unit and Integration Tests for POLARNAV Vessel Telemetry & NMEA Layer.

Tests:
1. NMEA-0183 Parser: XOR checksums, coordinate conversion, GGA, RMC, VTG, HDT.
2. VesselTelemetryService: Simulation progression, play/pause/reset, speed multiplier.
3. Dual-source switching: SIMULATION -> LIVE_NMEA on authentic sentence ingestion -> Reset.
4. Operational Dashboard Integration: Verified telemetry fields and Data Health table.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.server import app
from realtime.vessel import (
    NMEAParser,
    calculate_nmea_checksum,
    verify_nmea_checksum,
    parse_nmea_coord,
    vessel_telemetry_service,
)

client = TestClient(app)


class TestNMEAParser:
    """Test standard NMEA-0183 sentence parsing and coordinate decoding."""

    def test_coordinate_conversion(self):
        # 68°25.2000' S -> -(68 + 25.2/60) = -68.42°
        lat = parse_nmea_coord("6825.2000", "S")
        assert lat == -68.42

        # 077°18.6000' E -> +(77 + 18.6/60) = 77.31°
        lon = parse_nmea_coord("07718.6000", "E")
        assert lon == 77.31

        # North and West
        assert parse_nmea_coord("5030.0000", "N") == 50.5
        assert parse_nmea_coord("01030.0000", "W") == -10.5

    def test_checksum_calculation_and_validation(self):
        s = "GPRMC,123519,A,6825.2000,S,07718.6000,E,11.4,042.0,230394,003.1,W"
        csum = calculate_nmea_checksum(s)
        assert csum == "4F"
        assert verify_nmea_checksum(f"${s}*{csum}") is True
        assert verify_nmea_checksum(f"${s}*00") is False

    def test_rmc_parsing(self):
        s = "$GPRMC,123519,A,6825.2000,S,07718.6000,E,11.4,042.0,230394,003.1,W*4F"
        res = NMEAParser.parse_sentence(s)
        assert res is not None
        assert res["sentence_type"] == "RMC"
        assert res["valid"] is True
        assert res["latitude"] == -68.42
        assert res["longitude"] == 77.31
        assert res["sog_kn"] == 11.4
        assert res["cog_deg"] == 42.0

    def test_gga_parsing(self):
        # Fix quality 1 (GPS SPS), 8 satellites, HDOP 0.9, Altitude 12.0m
        raw = "GPGGA,123519,6825.2000,S,07718.6000,E,1,08,0.9,12.0,M,0.0,M,,"
        csum = calculate_nmea_checksum(raw)
        s = f"${raw}*{csum}"
        res = NMEAParser.parse_sentence(s)
        assert res is not None
        assert res["sentence_type"] == "GGA"
        assert res["valid"] is True
        assert res["latitude"] == -68.42
        assert res["longitude"] == 77.31
        assert res["fix_quality"] == 1
        assert res["satellites"] == 8
        assert res["hdop"] == 0.9

    def test_vtg_parsing(self):
        raw = "GPVTG,045.5,T,,M,12.5,N,23.2,K"
        csum = calculate_nmea_checksum(raw)
        s = f"${raw}*{csum}"
        res = NMEAParser.parse_sentence(s)
        assert res is not None
        assert res["sentence_type"] == "VTG"
        assert res["cog_deg"] == 45.5
        assert res["sog_kn"] == 12.5

    def test_hdt_parsing(self):
        raw = "GPHDT,045.0,T"
        csum = calculate_nmea_checksum(raw)
        s = f"${raw}*{csum}"
        res = NMEAParser.parse_sentence(s)
        assert res is not None
        assert res["sentence_type"] == "HDT"
        assert res["heading_deg"] == 45.0

    def test_malformed_and_invalid_sentences(self):
        assert NMEAParser.parse_sentence("") is None
        assert NMEAParser.parse_sentence("NOT_NMEA") is None
        # Invalid checksum
        assert NMEAParser.parse_sentence("$GPRMC,123519,A,6825.2000,S,07718.6000,E*99") is None


class TestVesselTelemetryService:
    """Test VesselTelemetryService state machine and dual-source switching."""

    def setup_method(self):
        vessel_telemetry_service.reset()

    def test_initial_simulation_state(self):
        t = vessel_telemetry_service.get_telemetry()
        assert t.source == "SIMULATION"
        assert t.status == "SIMULATION"
        assert -75.0 <= t.latitude <= -50.0
        assert 0.0 <= t.longitude <= 180.0
        assert t.sog_kn >= 0.0
        assert 0.0 <= t.cog_deg <= 360.0
        assert 0.0 <= t.heading_deg <= 360.0

    def test_simulation_controls(self):
        # Pause
        vessel_telemetry_service.pause()
        assert vessel_telemetry_service.get_telemetry().is_paused is True

        # Play
        vessel_telemetry_service.play()
        assert vessel_telemetry_service.get_telemetry().is_paused is False

        # Speed multiplier
        vessel_telemetry_service.set_speed_multiplier(15.0)
        assert vessel_telemetry_service.get_telemetry().speed_multiplier == 15.0

    def test_dual_source_transition_to_live_nmea(self):
        # Feed authentic NMEA RMC sentence
        s = "$GPRMC,123519,A,6825.2000,S,07718.6000,E,11.4,042.0,230394,003.1,W*4F"
        ok = vessel_telemetry_service.process_nmea_sentence(s)
        assert ok is True

        t = vessel_telemetry_service.get_telemetry()
        assert t.source == "LIVE_NMEA"
        assert t.status == "LIVE_NMEA"
        assert t.latitude == -68.42
        assert t.longitude == 77.31
        assert t.sog_kn == 11.4
        assert t.cog_deg == 42.0

        # Reset returns to SIMULATION
        vessel_telemetry_service.reset()
        t_reset = vessel_telemetry_service.get_telemetry()
        assert t_reset.source == "SIMULATION"
        assert t_reset.status == "SIMULATION"


class TestVesselTelemetryAPI:
    """Test API endpoints for telemetry querying, control, and NMEA test feed."""

    def setup_method(self):
        vessel_telemetry_service.reset()

    def test_get_telemetry_endpoint(self):
        res = client.get("/api/realtime/vessel/telemetry")
        assert res.status_code == 200
        d = res.json()
        assert "source" in d
        assert "status" in d
        assert "latitude" in d
        assert "longitude" in d
        assert "sog_kn" in d
        assert "cog_deg" in d
        assert "heading_deg" in d
        assert d["source"] == "SIMULATION"

    def test_control_endpoint(self):
        # Pause
        res = client.post("/api/realtime/vessel/telemetry/control", json={"action": "pause"})
        assert res.status_code == 200
        assert res.json()["telemetry"]["is_paused"] is True

        # Play with speed
        res2 = client.post("/api/realtime/vessel/telemetry/control", json={
            "action": "set_speed",
            "speed_multiplier": 5.0,
            "sog_kn": 14.0
        })
        assert res2.status_code == 200
        t = res2.json()["telemetry"]
        assert t["speed_multiplier"] == 5.0
        assert t["sog_kn"] == 14.0

    def test_nmea_feed_endpoint(self):
        s = "$GPRMC,123519,A,6825.2000,S,07718.6000,E,11.4,042.0,230394,003.1,W*4F"
        res = client.post("/api/realtime/vessel/telemetry/nmea-feed", json={"sentence": s})
        assert res.status_code == 200
        d = res.json()
        assert d["status"] == "ACCEPTED"
        assert d["source"] == "LIVE_NMEA"
        assert d["telemetry"]["latitude"] == -68.42
        assert d["telemetry"]["longitude"] == 77.31

    def test_operational_dashboard_vessel_telemetry(self):
        res = client.get("/api/realtime/operational-dashboard")
        assert res.status_code == 200
        d = res.json()
        v = d["vessel"]

        # Ensure normalized telemetry is surfaced in the vessel card
        assert "source" in v
        assert "status" in v
        assert "speed_knots" in v
        assert "heading_deg" in v
        assert "cog_deg" in v
        assert "position" in v
        assert len(v["position"]) == 2

        # Check Data Health Table contains Vessel GPS with honest status
        gps_health = [h for h in d.get("data_health", []) if h.get("provider_key") == "vessel_gps"]
        assert len(gps_health) == 1
        assert gps_health[0]["display_status"] in ("SIMULATION", "LIVE_NMEA")
