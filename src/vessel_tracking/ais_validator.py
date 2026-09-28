"""Data validation rules for AIS telemetry records.

Phase 1: Historical AIS Data Layer
Filters corrupt entries, sensor dropouts, teleports, and invalid telemetry.
"""
from datetime import datetime
from typing import Tuple, List, Optional, Dict, Any
import math
import dateutil.parser

from src.vessel_tracking.ais_schema import AISRecord, AISValidationIssue


# Maximum reasonable physical speed for Antarctic research icebreakers (knots)
# Polarstern max ~18.5 kn, Aurora Australis ~16.8 kn, fast patrol ~28 kn.
MAX_FEASIBLE_SOG_KNOTS = 35.0

# AIS standard missing/null coordinate indicators
AIS_NULL_LAT = 91.0
AIS_NULL_LON = 181.0


def parse_timestamp(val: Any) -> Optional[datetime]:
    """Parse various timestamp representations into a Python datetime object."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        if math.isnan(val):
            return None
        # Unix timestamp (seconds or milliseconds)
        if val > 1e11:  # Milliseconds
            return datetime.utcfromtimestamp(val / 1000.0)
        return datetime.utcfromtimestamp(val)
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str or val_str.lower() in ("null", "none", "nan", "nat", ""):
            return None
        try:
            return dateutil.parser.parse(val_str)
        except (ValueError, OverflowError):
            return None
    return None


def validate_coordinates(lat: Any, lon: Any, southern_ocean_focus: bool = False) -> Tuple[bool, Optional[str]]:
    """Validate latitude and longitude against geographic and AIS specifications."""
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False, "Non-numeric coordinate values"

    if math.isnan(lat_f) or math.isnan(lon_f) or math.isinf(lat_f) or math.isinf(lon_f):
        return False, "NaN or Infinite coordinates"

    # AIS standard null signals
    if abs(lat_f - AIS_NULL_LAT) < 0.001 or abs(lon_f - AIS_NULL_LON) < 0.001:
        return False, "AIS standard missing coordinate indicator (91.0/181.0)"

    # Physical Earth bounds
    if not (-90.0 <= lat_f <= 90.0):
        return False, f"Latitude {lat_f} outside [-90.0, 90.0]"

    if not (-180.0 <= lon_f <= 180.0):
        return False, f"Longitude {lon_f} outside [-180.0, 180.0]"

    # Null Island check (0.0, 0.0 often indicates GPS fix acquisition failure)
    if abs(lat_f) < 0.0001 and abs(lon_f) < 0.0001:
        return False, "Null Island (0.0, 0.0) GPS fix failure"

    if southern_ocean_focus and lat_f > 0.0:
        return False, f"Latitude {lat_f} is in Northern Hemisphere (outside Southern Ocean domain)"

    return True, None


def validate_speed(speed: Any, max_knots: float = MAX_FEASIBLE_SOG_KNOTS) -> Tuple[bool, Optional[float], Optional[str]]:
    """Validate speed over ground (SOG)."""
    if speed is None:
        return True, None, None

    try:
        spd_f = float(speed)
    except (TypeError, ValueError):
        return False, None, "Non-numeric speed over ground"

    if math.isnan(spd_f) or math.isinf(spd_f):
        return True, None, None  # Treat NaN speed as unknown, not fatal

    if spd_f < 0.0:
        return False, None, f"Negative speed over ground: {spd_f} kn"

    # AIS code 102.3 indicates speed not available
    if abs(spd_f - 102.3) < 0.01:
        return True, None, None

    if spd_f > max_knots:
        return False, None, f"Impossible vessel speed: {spd_f} kn (max feasible {max_knots} kn)"

    return True, spd_f, None


def validate_course_heading(deg: Any) -> Tuple[bool, Optional[float]]:
    """Validate course or heading angle [0.0, 360.0]."""
    if deg is None:
        return True, None

    try:
        val_f = float(deg)
    except (TypeError, ValueError):
        return False, None

    if math.isnan(val_f) or math.isinf(val_f):
        return True, None

    # AIS 511 indicates heading not available, 360 indicates not available
    if abs(val_f - 511.0) < 0.01 or abs(val_f - 360.0) < 0.01:
        return True, None

    if 0.0 <= val_f < 360.0:
        return True, val_f

    return False, None


def validate_raw_record(
    raw: Dict[str, Any],
    record_index: int = 0,
    southern_ocean_focus: bool = False
) -> Tuple[Optional[AISRecord], List[AISValidationIssue]]:
    """Validate a single raw dict representation of an AIS position report."""
    issues: List[AISValidationIssue] = []

    if not isinstance(raw, dict):
        issues.append(AISValidationIssue(
            record_index=record_index,
            vessel_id=None,
            issue_type="malformed",
            details="Input record is not a dictionary",
            raw_snippet=None
        ))
        return None, issues

    # Extract vessel identifier
    vessel_id = raw.get("vessel_id") or raw.get("mmsi") or raw.get("set_code") or raw.get("ship_name") or raw.get("vessel_name")
    if not vessel_id:
        vessel_id = "unknown_vessel"

    vessel_id_str = str(vessel_id).strip()
    if not vessel_id_str or vessel_id_str.lower() in ("none", "nan", "null"):
        vessel_id_str = "unknown_vessel"

    # Validate timestamp
    raw_ts = (
        raw.get("timestamp")
        or raw.get("date_time_utc")
        or raw.get("timestamp_gps_utc")
        or raw.get("time")
        or raw.get("datetime")
    )
    parsed_ts = parse_timestamp(raw_ts)
    if parsed_ts is None:
        issues.append(AISValidationIssue(
            record_index=record_index,
            vessel_id=vessel_id_str,
            issue_type="missing_timestamp",
            details=f"Missing or unparseable timestamp: {raw_ts}",
            raw_snippet={"raw_ts": str(raw_ts)}
        ))
        return None, issues

    # Validate coordinates
    raw_lat = raw.get("latitude") if "latitude" in raw else raw.get("lat")
    raw_lon = raw.get("longitude") if "longitude" in raw else raw.get("lon")

    coords_valid, coord_err = validate_coordinates(raw_lat, raw_lon, southern_ocean_focus=southern_ocean_focus)
    if not coords_valid:
        issues.append(AISValidationIssue(
            record_index=record_index,
            vessel_id=vessel_id_str,
            issue_type="invalid_coordinates",
            details=coord_err or "Invalid coordinates",
            raw_snippet={"lat": raw_lat, "lon": raw_lon}
        ))
        return None, issues

    lat_f = float(raw_lat)
    lon_f = float(raw_lon)

    # Validate speed
    raw_spd = (
        raw.get("speed_knots")
        or raw.get("speed")
        or raw.get("ship_spd_over_ground_knot")
        or raw.get("sog")
    )
    spd_valid, spd_f, spd_err = validate_speed(raw_spd)
    if not spd_valid:
        issues.append(AISValidationIssue(
            record_index=record_index,
            vessel_id=vessel_id_str,
            issue_type="impossible_speed",
            details=spd_err or "Speed rejected",
            raw_snippet={"speed": raw_spd}
        ))
        return None, issues

    # Validate course & heading
    raw_course = (
        raw.get("course_deg")
        or raw.get("course")
        or raw.get("ship_course_over_ground_deg")
        or raw.get("cog")
    )
    _, course_f = validate_course_heading(raw_course)

    raw_heading = (
        raw.get("heading_deg")
        or raw.get("heading")
        or raw.get("ship_heading_gps_deg")
        or raw.get("ship_heading_gyro_deg")
    )
    _, heading_f = validate_course_heading(raw_heading)

    record = AISRecord(
        vessel_id=vessel_id_str,
        timestamp=parsed_ts,
        latitude=lat_f,
        longitude=lon_f,
        speed_knots=spd_f,
        course_deg=course_f,
        heading_deg=heading_f,
        vessel_type=raw.get("vessel_type", "research_icebreaker"),
        vessel_name=raw.get("vessel_name") or raw.get("ship_name") or vessel_id_str,
        mmsi=str(raw.get("mmsi")) if raw.get("mmsi") else None,
        source=raw.get("source", "historical_ais_dataset"),
        extra_metadata={k: v for k, v in raw.items() if k not in (
            "vessel_id", "timestamp", "latitude", "longitude", "speed_knots",
            "course_deg", "heading_deg", "vessel_type", "vessel_name", "mmsi"
        )}
    )

    return record, issues
