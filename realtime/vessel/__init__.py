"""POLARNAV Vessel Telemetry & NMEA Layer."""

from .nmea_parser import NMEAParser, calculate_nmea_checksum, verify_nmea_checksum, parse_nmea_coord
from .service import (
    VesselTelemetryService,
    NormalizedVesselTelemetry,
    vessel_telemetry_service,
    DEFAULT_ANTARCTIC_TRACK,
)

__all__ = [
    "NMEAParser",
    "calculate_nmea_checksum",
    "verify_nmea_checksum",
    "parse_nmea_coord",
    "VesselTelemetryService",
    "NormalizedVesselTelemetry",
    "vessel_telemetry_service",
    "DEFAULT_ANTARCTIC_TRACK",
]
