"""NMEA-0183 Standard Marine Navigation Telemetry Parser.

Parses standard shipboard GPS and gyro sentences:
- GGA: Global Positioning System Fix Data (Position, Fix Quality, HDOP)
- RMC: Recommended Minimum Specific GNSS Data (Position, SOG, COG, Time)
- VTG: Course Over Ground & Ground Speed (True Track, SOG Knots)
- HDT: Heading - True (Ship's gyro/compass true heading)

Features rigorous XOR checksum validation and multi-constellation support
($GP, $GN, $GL, $GA, $IN).
"""
import re
import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple


def calculate_nmea_checksum(sentence: str) -> str:
    """Calculate standard NMEA-0183 2-digit hex XOR checksum."""
    clean = sentence.strip()
    if clean.startswith("$") or clean.startswith("!"):
        clean = clean[1:]
    if "*" in clean:
        clean = clean.split("*")[0]

    csum = 0
    for ch in clean:
        csum ^= ord(ch)
    return f"{csum:02X}"


def verify_nmea_checksum(sentence: str) -> bool:
    """Validate sentence checksum against expected XOR byte."""
    sentence = sentence.strip()
    if "*" not in sentence:
        return False
    body, expected_hex = sentence.rsplit("*", 1)
    if len(expected_hex) < 2:
        return False
    expected_hex = expected_hex[:2].upper()
    calc_hex = calculate_nmea_checksum(body)
    return calc_hex == expected_hex


def parse_nmea_coord(coord_str: str, hemi: str) -> Optional[float]:
    """Convert NMEA DDMM.MMMM / DDDMM.MMMM coordinate to decimal degrees.

    Examples:
        '6825.2000', 'S' -> -68.42
        '07718.6000', 'E' -> 77.31
    """
    if not coord_str or not hemi:
        return None
    try:
        val = float(coord_str)
        # Degrees are everything before the last 2 digits before the decimal point
        deg_part = int(val / 100)
        min_part = val - (deg_part * 100)
        dec_deg = deg_part + (min_part / 60.0)
        if hemi.upper() in ("S", "W"):
            dec_deg = -dec_deg
        return round(dec_deg, 6)
    except (ValueError, TypeError):
        return None


class NMEAParser:
    """Parser for NMEA-0183 marine sentences into normalized vessel metrics."""

    @staticmethod
    def parse_sentence(sentence: str) -> Optional[Dict[str, Any]]:
        """Parse an NMEA sentence and return normalized telemetry attributes.

        Returns None if sentence is malformed or has invalid checksum.
        """
        if not sentence or not isinstance(sentence, str):
            return None

        sentence = sentence.strip()
        if not (sentence.startswith("$") or sentence.startswith("!")):
            return None

        # Verify checksum if present
        if "*" in sentence and not verify_nmea_checksum(sentence):
            return None

        # Strip prefix and checksum
        raw_body = sentence[1:].split("*")[0]
        fields = raw_body.split(",")
        if not fields:
            return None

        tag = fields[0].upper()
        # Sentence identifier is last 3 characters (e.g. GPRMC -> RMC)
        sentence_type = tag[-3:] if len(tag) >= 3 else tag
        talker = tag[:-3] if len(tag) >= 3 else ""

        result: Dict[str, Any] = {
            "sentence_type": sentence_type,
            "talker": talker,
            "raw_sentence": sentence,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            if sentence_type == "RMC":
                # $--RMC,hhmmss.ss,A,llll.ll,a,yyyyy.yy,a,x.x,x.x,ddmmyy,,,a*hh
                if len(fields) < 10:
                    return None
                status = fields[2].upper()
                result["status"] = status  # A = Active/Valid, V = Void/Warning
                if status == "A":
                    result["latitude"] = parse_nmea_coord(fields[3], fields[4])
                    result["longitude"] = parse_nmea_coord(fields[5], fields[6])
                    result["sog_kn"] = float(fields[7]) if fields[7] else 0.0
                    result["cog_deg"] = float(fields[8]) if fields[8] else 0.0
                    result["valid"] = True
                else:
                    result["valid"] = False

            elif sentence_type == "GGA":
                # $--GGA,hhmmss.ss,llll.ll,a,yyyyy.yy,a,x,xx,x.x,x.x,M,x.x,M,x.x,xxxx*hh
                if len(fields) < 10:
                    return None
                fix_quality = int(fields[6]) if fields[6] else 0
                result["fix_quality"] = fix_quality
                result["satellites"] = int(fields[7]) if fields[7] else 0
                result["hdop"] = float(fields[8]) if fields[8] else 1.0
                if fix_quality > 0:
                    result["latitude"] = parse_nmea_coord(fields[2], fields[3])
                    result["longitude"] = parse_nmea_coord(fields[4], fields[5])
                    result["altitude_m"] = float(fields[9]) if fields[9] else 0.0
                    result["valid"] = True
                else:
                    result["valid"] = False

            elif sentence_type == "VTG":
                # $--VTG,x.x,T,x.x,M,x.x,N,x.x,K,a*hh
                if len(fields) < 8:
                    return None
                result["cog_deg"] = float(fields[1]) if fields[1] else 0.0
                result["cog_magnetic_deg"] = float(fields[3]) if fields[3] else None
                result["sog_kn"] = float(fields[5]) if fields[5] else 0.0
                result["sog_kmh"] = float(fields[7]) if fields[7] else 0.0
                result["valid"] = True

            elif sentence_type == "HDT":
                # $--HDT,x.x,T*hh
                if len(fields) < 2 or not fields[1]:
                    return None
                result["heading_deg"] = float(fields[1])
                result["valid"] = True

            else:
                # Unsupported or non-target sentence
                return None

            return result
        except Exception:
            return None
