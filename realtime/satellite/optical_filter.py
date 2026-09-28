"""PolarNav // Sentinel-2 Optical Usability & Solar Elevation Filter.

Evaluates polar astronomical daylight, solar elevation angles, and cloud
cover limitations to determine if Sentinel-2 optical imagery is operationally viable.
When unusable, the system explicitly advises switching to all-weather Sentinel-1 SAR.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, Tuple


def calculate_solar_elevation(lat_deg: float, lon_deg: float, dt: datetime) -> float:
    """Calculate the approximate solar elevation angle (degrees above horizon).
    
    Uses standard astronomical approximation:
    - Declination of the Sun
    - Equation of Time
    - Solar Hour Angle
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Day of the year
    day_of_year = dt.timetuple().tm_yday
    hour_utc = dt.hour + dt.minute / 60.0 + dt.second / 3600.0

    # Solar declination delta in radians
    # Cooper (1969) approximation
    declination_rad = math.radians(23.45 * math.sin(math.radians(360.0 / 365.0 * (284 + day_of_year))))

    # Equation of time in minutes
    b = math.radians(360.0 / 365.0 * (day_of_year - 81))
    eot_minutes = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

    # Solar time in hours
    solar_time_hours = hour_utc + (lon_deg / 15.0) + (eot_minutes / 60.0)
    hour_angle_deg = 15.0 * (solar_time_hours - 12.0)
    hour_angle_rad = math.radians(hour_angle_deg)

    lat_rad = math.radians(lat_deg)

    # Solar elevation angle: sin(alpha) = sin(lat)*sin(dec) + cos(lat)*cos(dec)*cos(ha)
    sin_elev = (
        math.sin(lat_rad) * math.sin(declination_rad) +
        math.cos(lat_rad) * math.cos(declination_rad) * math.cos(hour_angle_rad)
    )
    sin_elev = max(-1.0, min(1.0, sin_elev))
    elevation_deg = math.degrees(math.asin(sin_elev))
    return round(elevation_deg, 2)


class OpticalUsabilityEvaluator:
    """Rigorous operational filter for optical remote sensing."""
    
    # Thresholds for maritime navigation
    MIN_SOLAR_ELEVATION_DEG = 5.0      # Minimum sun angle for clear optical sea ice discrimination
    MAX_ACCEPTABLE_CLOUD_PCT = 20.0    # 20% cloud cover limit

    @classmethod
    def evaluate(
        cls,
        lat: float,
        lon: float,
        acquisition_time: datetime,
        cloud_cover_pct: float = 0.0,
    ) -> Dict[str, Any]:
        """Determine if a Sentinel-2 optical scene is operationally usable."""
        solar_elev = calculate_solar_elevation(lat, lon, acquisition_time)

        # 1. Polar Night Check
        if solar_elev < -6.0:
            return {
                "is_usable": False,
                "status": "POLAR_NIGHT_OBSCURED",
                "solar_elevation_deg": solar_elev,
                "cloud_cover_pct": cloud_cover_pct,
                "recommendation": "USE_SENTINEL1_SAR_INSTEAD",
                "explanation": (
                    f"Sun elevation is {solar_elev}° (polar darkness). "
                    "Surface is completely dark; optical sensors cannot detect ice or water. "
                    "Operational navigation must rely exclusively on active Sentinel-1 C-Band SAR."
                ),
            }

        # 2. Twilight / Marginal Sunlight
        if solar_elev < cls.MIN_SOLAR_ELEVATION_DEG:
            return {
                "is_usable": False,
                "status": "LOW_SOLAR_ANGLE",
                "solar_elevation_deg": solar_elev,
                "cloud_cover_pct": cloud_cover_pct,
                "recommendation": "USE_SENTINEL1_SAR_INSTEAD",
                "explanation": (
                    f"Sun elevation of {solar_elev}° provides grazing shadows and weak illumination. "
                    "Optical ice classification is unreliable."
                ),
            }

        # 3. Cloud Cover Limitation
        if cloud_cover_pct > cls.MAX_ACCEPTABLE_CLOUD_PCT:
            return {
                "is_usable": False,
                "status": "CLOUD_OBSCURED",
                "solar_elevation_deg": solar_elev,
                "cloud_cover_pct": cloud_cover_pct,
                "recommendation": "USE_SENTINEL1_SAR_INSTEAD",
                "explanation": (
                    f"Cloud cover is {cloud_cover_pct:.1f}% (exceeds {cls.MAX_ACCEPTABLE_CLOUD_PCT}% threshold). "
                    "Maritime obstacles and floes are obscured by cloud deck. "
                    "Switching to cloud-penetrating Sentinel-1 SAR."
                ),
            }

        # 4. Optimal Optical Scene
        return {
            "is_usable": True,
            "status": "OPTIMAL_OPTICAL_ACQUISITION",
            "solar_elevation_deg": solar_elev,
            "cloud_cover_pct": cloud_cover_pct,
            "recommendation": "VALIDATED_OPTICAL_OBSERVATION",
            "explanation": (
                f"Sufficient solar elevation ({solar_elev}°) and low cloud cover ({cloud_cover_pct:.1f}%). "
                "Optical multi-spectral bands (RGB + NIR/SWIR NDSI) are operationally valid."
            ),
        }


optical_evaluator = OpticalUsabilityEvaluator()
