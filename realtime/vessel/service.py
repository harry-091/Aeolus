"""Vessel Telemetry Service for POLARNAV.

Unified vessel telemetry abstraction supporting two sources:
1. SIMULATION: Realistic, deterministic Antarctic route progression.
2. NMEA: Real-time shipboard GPS / gyro receiver feed (NMEA-0183 via UDP/TCP).

Maintains a single normalized internal telemetry model ensuring consistent
downstream propagation to the navigation map, ML risk engine, sea-ice
avoidance, iceberg clearance, and IMO compliance reporting.
"""
import os
import math
import time
import socket
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from .nmea_parser import NMEAParser

logger = logging.getLogger("polarnav.vessel_telemetry")

# Safe Predefined Antarctic Demonstration Track (Prydz Bay / Bharati Station Corridor)
DEFAULT_ANTARCTIC_TRACK: List[Tuple[float, float]] = [
    (-65.0000, 70.0000),  # Open Southern Ocean entry
    (-65.8500, 71.2000),  # Marginal ice zone approach
    (-66.7000, 72.8000),  # Outer shelf navigation corridor
    (-67.5000, 74.5000),  # Prydz Bay entrance
    (-68.4200, 76.2000),  # Mid-bay approach
    (-69.0000, 76.7000),  # Larsemann Hills channel
    (-69.4000, 76.1900),  # Bharati Research Station anchorage
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers between two coordinates."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def calculate_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from (lat1, lon1) to (lat2, lon2) in degrees [0, 360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return round(bearing, 1)


class NormalizedVesselTelemetry(BaseModel):
    """Unified internal vessel telemetry model."""
    source: str = Field(default="SIMULATION", description="SIMULATION or LIVE_NMEA")
    status: str = Field(default="SIMULATION", description="SIMULATION, LIVE_NMEA, or UNAVAILABLE")
    timestamp: str = Field(default="", description="ISO-8601 observation timestamp")
    latitude: float = Field(default=-65.0, description="Latitude in signed decimal degrees")
    longitude: float = Field(default=70.0, description="Longitude in signed decimal degrees")
    sog_kn: float = Field(default=12.0, description="Speed Over Ground in knots")
    cog_deg: float = Field(default=145.0, description="Course Over Ground in degrees [0, 360)")
    heading_deg: float = Field(default=145.0, description="True heading in degrees [0, 360)")
    position_accuracy: Optional[float] = Field(default=None, description="Estimated position accuracy in meters")
    data_age_seconds: float = Field(default=0.0, description="Telemetry age in seconds")
    # Simulation & corridor tracking metadata
    route_progress_pct: float = Field(default=0.0, description="Progress along active route [0, 100]")
    current_segment_index: int = Field(default=0, description="Active waypoint segment index")
    total_distance_km: float = Field(default=0.0, description="Total corridor distance in km")
    distance_traveled_km: float = Field(default=0.0, description="Cumulative distance traveled in km")
    is_paused: bool = Field(default=False, description="Whether simulation progression is paused")
    speed_multiplier: float = Field(default=1.0, description="Simulation time speed multiplier")
    vessel_id: str = Field(default="rv_sagar_nidhi", description="Vessel identifier")
    vessel_name: str = Field(default="R/V Sagar Nidhi", description="Vessel display name")
    call_sign: str = Field(default="VTCX", description="Vessel radio call sign")
    mmsi: str = Field(default="419072400", description="Maritime Mobile Service Identity")


class VesselTelemetryService:
    """Manages vessel telemetry ingestion, simulation, and NMEA reception."""

    def __init__(self):
        self._lock = threading.Lock()
        self._initialized = False

        # Configuration from environment
        self._nmea_enabled: bool = os.getenv("NMEA_ENABLED", "false").lower() in ("true", "1", "yes")
        self._nmea_host: str = os.getenv("NMEA_HOST", "")
        self._nmea_port: int = int(os.getenv("NMEA_PORT", "10110")) if os.getenv("NMEA_PORT") else 10110
        self._nmea_protocol: str = os.getenv("NMEA_PROTOCOL", "UDP").upper()

        # State storage
        self._source: str = "SIMULATION"
        self._status: str = "SIMULATION"
        self._last_nme_time: Optional[float] = None
        self._nmea_thread: Optional[threading.Thread] = None
        self._nmea_socket: Optional[socket.socket] = None
        self._stop_nmea: bool = False

        # Simulation state
        self._track: List[Tuple[float, float]] = list(DEFAULT_ANTARCTIC_TRACK)
        self._segment_distances: List[float] = []
        self._total_distance_km: float = 0.0
        self._recalculate_track_metrics()

        self._distance_traveled_km: float = 0.0
        self._sog_kn: float = 12.0
        self._cog_deg: float = 145.0
        self._heading_deg: float = 145.0
        self._lat: float = self._track[0][0]
        self._lon: float = self._track[0][1]
        self._is_paused: bool = False
        self._speed_multiplier: float = 1.0
        self._last_sim_update_time: float = time.time()
        self._last_state_timestamp: str = datetime.now(timezone.utc).isoformat()

        # Initialize network listener if enabled
        if self._nmea_enabled and self._nmea_port:
            self._start_nmea_listener()

    def _recalculate_track_metrics(self) -> None:
        """Calculate cumulative distances across current track waypoints."""
        self._segment_distances = []
        tot = 0.0
        for i in range(len(self._track) - 1):
            d = haversine_km(
                self._track[i][0], self._track[i][1],
                self._track[i + 1][0], self._track[i + 1][1]
            )
            self._segment_distances.append(d)
            tot += d
        self._total_distance_km = max(tot, 0.001)

    def set_route(self, waypoints: List[Tuple[float, float]]) -> None:
        """Update the active track to follow a newly generated PolarNav route."""
        if not waypoints or len(waypoints) < 2:
            return
        with self._lock:
            if len(self._track) == len(waypoints):
                matches = True
                for p1, p2 in zip(self._track, waypoints):
                    if abs(p1[0] - p2[0]) > 1e-4 or abs(p1[1] - p2[1]) > 1e-4:
                        matches = False
                        break
                if matches:
                    return

            self._track = list(waypoints)
            self._recalculate_track_metrics()
            self._distance_traveled_km = 0.0
            self._lat = self._track[0][0]
            self._lon = self._track[0][1]
            self._cog_deg = calculate_bearing_deg(
                self._track[0][0], self._track[0][1],
                self._track[1][0], self._track[1][1]
            )
            self._heading_deg = self._cog_deg
            self._last_sim_update_time = time.time()
            logger.info(f"Vessel telemetry route updated with {len(waypoints)} waypoints ({self._total_distance_km:.1f} km)")

    def _advance_simulation(self) -> None:
        """Deterministically advance simulated vessel along track according to elapsed time."""
        now = time.time()
        dt_seconds = now - self._last_sim_update_time
        self._last_sim_update_time = now

        # Skip motion when paused or when receiving live NMEA
        if self._is_paused or self._source == "LIVE_NMEA":
            return

        if dt_seconds <= 0.0 or self._total_distance_km <= 0.0:
            return

        # Cap dt to avoid huge teleports if server was suspended
        dt_seconds = min(dt_seconds, 60.0)

        # Distance step in km: knots * 1.852 km/nm * (hours elapsed) * multiplier
        dist_step_km = (self._sog_kn * 1.852) * (dt_seconds / 3600.0) * self._speed_multiplier
        self._distance_traveled_km += dist_step_km

        # Loop or hold at destination if end of track reached
        if self._distance_traveled_km >= self._total_distance_km:
            self._distance_traveled_km = self._distance_traveled_km % self._total_distance_km

        # Find current segment and interpolate coordinates
        accum = 0.0
        current_seg = 0
        seg_ratio = 0.0

        for i, seg_dist in enumerate(self._segment_distances):
            if accum + seg_dist >= self._distance_traveled_km:
                current_seg = i
                seg_ratio = (self._distance_traveled_km - accum) / max(seg_dist, 0.0001)
                break
            accum += seg_dist
        else:
            current_seg = len(self._segment_distances) - 1
            seg_ratio = 1.0

        p1 = self._track[current_seg]
        p2 = self._track[min(current_seg + 1, len(self._track) - 1)]

        # Linear interpolation between waypoints
        self._lat = round(p1[0] + (p2[0] - p1[0]) * seg_ratio, 6)
        self._lon = round(p1[1] + (p2[1] - p1[1]) * seg_ratio, 6)

        # Update COG and heading towards next waypoint
        if p1 != p2:
            self._cog_deg = calculate_bearing_deg(p1[0], p1[1], p2[0], p2[1])
            # Realistic slight heading yaw/leeway (e.g. ±0.8 deg dynamic wave yaw)
            yaw = math.sin(now * 0.5) * 0.8
            self._heading_deg = round((self._cog_deg + yaw + 360.0) % 360.0, 1)

        self._last_state_timestamp = datetime.now(timezone.utc).isoformat()

    def get_telemetry(self) -> NormalizedVesselTelemetry:
        """Retrieve the current normalized vessel telemetry state."""
        with self._lock:
            # Advance simulation if active
            if self._source != "LIVE_NMEA":
                self._advance_simulation()
                data_age = round(max(0.0, time.time() - self._last_sim_update_time), 1)
                status = "SIMULATION"
            else:
                # Live NMEA: check freshness
                data_age = round(max(0.0, time.time() - (self._last_nme_time or time.time())), 1)
                if data_age > 30.0:
                    status = "UNAVAILABLE"
                else:
                    status = "LIVE_NMEA"

            progress_pct = round(min(100.0, (self._distance_traveled_km / self._total_distance_km) * 100.0), 1)

            return NormalizedVesselTelemetry(
                source=self._source,
                status=status,
                timestamp=self._last_state_timestamp,
                latitude=self._lat,
                longitude=self._lon,
                sog_kn=round(self._sog_kn, 1),
                cog_deg=round(self._cog_deg, 1),
                heading_deg=round(self._heading_deg, 1),
                position_accuracy=2.5 if self._source == "LIVE_NMEA" else None,
                data_age_seconds=data_age,
                route_progress_pct=progress_pct,
                total_distance_km=round(self._total_distance_km, 1),
                distance_traveled_km=round(self._distance_traveled_km, 1),
                is_paused=self._is_paused,
                speed_multiplier=self._speed_multiplier,
                vessel_id="rv_sagar_nidhi",
                vessel_name="R/V Sagar Nidhi",
                call_sign="VTCX",
                mmsi="419072400"
            )

    # -------------------------------------------------------------------------
    # Simulation Control Actions
    # -------------------------------------------------------------------------

    def play(self) -> None:
        """Resume simulation movement."""
        with self._lock:
            self._is_paused = False
            self._last_sim_update_time = time.time()
            if self._source == "LIVE_NMEA":
                self._source = "SIMULATION"
                self._status = "SIMULATION"

    def pause(self) -> None:
        """Pause simulation movement."""
        with self._lock:
            self._is_paused = True

    def reset(self, reset_track: bool = True) -> None:
        """Reset vessel position back to start of corridor."""
        with self._lock:
            if reset_track:
                self._track = list(DEFAULT_ANTARCTIC_TRACK)
                self._recalculate_track_metrics()
            self._distance_traveled_km = 0.0
            self._lat = self._track[0][0]
            self._lon = self._track[0][1]
            if len(self._track) > 1:
                self._cog_deg = calculate_bearing_deg(
                    self._track[0][0], self._track[0][1],
                    self._track[1][0], self._track[1][1]
                )
                self._heading_deg = self._cog_deg
            self._last_sim_update_time = time.time()
            self._is_paused = False
            self._source = "SIMULATION"
            self._status = "SIMULATION"

    def set_speed_multiplier(self, multiplier: float) -> None:
        """Set simulation speed multiplier (e.g. 1.0x, 5.0x, 15.0x)."""
        with self._lock:
            self._speed_multiplier = max(0.1, min(100.0, float(multiplier)))

    def set_sog(self, sog_kn: float) -> None:
        """Set vessel speed over ground in knots."""
        with self._lock:
            self._sog_kn = max(0.0, min(35.0, float(sog_kn)))

    # -------------------------------------------------------------------------
    # NMEA Receiver & Processing
    # -------------------------------------------------------------------------

    def process_nmea_sentence(self, sentence: str) -> bool:
        """Process an incoming NMEA sentence string and update telemetry state.

        Switches active source to LIVE_NMEA upon receiving valid positional fix.
        """
        parsed = NMEAParser.parse_sentence(sentence)
        if not parsed or not parsed.get("valid"):
            return False

        with self._lock:
            stype = parsed.get("sentence_type")
            if stype in ("RMC", "GGA"):
                if parsed.get("latitude") is not None and parsed.get("longitude") is not None:
                    self._lat = parsed["latitude"]
                    self._lon = parsed["longitude"]
                    self._source = "LIVE_NMEA"
                    self._status = "LIVE_NMEA"
                    self._last_nme_time = time.time()
                    self._last_state_timestamp = parsed.get("parsed_at") or datetime.now(timezone.utc).isoformat()

                if "sog_kn" in parsed:
                    self._sog_kn = parsed["sog_kn"]
                if "cog_deg" in parsed:
                    self._cog_deg = parsed["cog_deg"]

            elif stype == "VTG":
                if "sog_kn" in parsed:
                    self._sog_kn = parsed["sog_kn"]
                if "cog_deg" in parsed:
                    self._cog_deg = parsed["cog_deg"]
                self._source = "LIVE_NMEA"
                self._status = "LIVE_NMEA"
                self._last_nme_time = time.time()

            elif stype == "HDT":
                if "heading_deg" in parsed:
                    self._heading_deg = parsed["heading_deg"]
                self._source = "LIVE_NMEA"
                self._status = "LIVE_NMEA"
                self._last_nme_time = time.time()

        return True

    def _start_nmea_listener(self) -> None:
        """Start background daemon thread listening for shipboard UDP/TCP NMEA stream."""
        def _udp_worker():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                host = self._nmea_host if self._nmea_host else "0.0.0.0"
                sock.bind((host, self._nmea_port))
                sock.settimeout(2.0)
                self._nmea_socket = sock
                logger.info(f"NMEA UDP receiver listening on {host}:{self._nmea_port}")

                while not self._stop_nmea:
                    try:
                        data, _ = sock.recvfrom(2048)
                        text = data.decode("ascii", errors="replace")
                        for line in text.splitlines():
                            if line.strip():
                                self.process_nmea_sentence(line.strip())
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if not self._stop_nmea:
                            logger.warning(f"Error in NMEA UDP listener: {e}")
            except Exception as e:
                logger.error(f"Failed to bind NMEA UDP socket on port {self._nmea_port}: {e}")

        self._stop_nmea = False
        self._nmea_thread = threading.Thread(target=_udp_worker, daemon=True, name="polarnav_nmea_listener")
        self._nmea_thread.start()

    def close(self) -> None:
        """Stop background listeners and release resources."""
        self._stop_nmea = True
        if self._nmea_socket:
            try:
                self._nmea_socket.close()
            except Exception:
                pass


# Global singleton instance
vessel_telemetry_service = VesselTelemetryService()
