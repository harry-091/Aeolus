"""Feature Extractor for Phase 3 ML Training Dataset.

Transforms EnrichedAISFeaturePoint instances into standardized, flat ML feature vectors.
Engineers kinematic, spatial cyclical, temporal seasonal, and environmental representations.
"""

from dataclasses import dataclass, asdict
import math
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.environmental_replay.replay_schema import EnrichedAISFeaturePoint


FEATURE_NAMES = [
    # Kinematic features
    "speed_knots",
    "course_deg",
    "heading_deg",
    "sin_course",
    "cos_course",
    # Spatial coordinates & Cyclical encoding
    "latitude",
    "longitude",
    "sin_lat",
    "cos_lat",
    "sin_lon",
    "cos_lon",
    # Temporal Seasonal Cyclical features
    "month",
    "day_of_year",
    "hour",
    "sin_day_of_year",
    "cos_day_of_year",
    # Sea Ice Regime
    "sic",
    "sic_percent",
    "is_ice_covered",
    # Obstacles & Hazard Proximity
    "iceberg_distance_km",
    "has_iceberg_within_50km",
    "has_iceberg_within_15km",
    # Bathymetry & Coastal Topography
    "bathymetry_depth_m",
    "is_shallow",
    "coastline_distance_km",
    "is_on_land",
    # Ocean Hydrodynamics & Atmosphere
    "ocean_current_speed_ms",
    "ocean_current_u_ms",
    "ocean_current_v_ms",
    "sea_surface_temp_c",
    "wind_speed_ms",
    "air_temp_c",
]


@dataclass
class MLFeatureVector:
    """Tabular representation of engineered ML features."""
    features: Dict[str, float]
    vessel_id: str
    voyage_id: str
    timestamp: datetime

    def to_list(self) -> List[float]:
        """Return feature values in fixed, deterministic order."""
        return [self.features.get(name, 0.0) for name in FEATURE_NAMES]

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary containing metadata and all feature values."""
        res = {
            "vessel_id": self.vessel_id,
            "voyage_id": self.voyage_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
        res.update(self.features)
        return res


class FeatureExtractor:
    """Extracts machine learning feature vectors from enriched historical AIS points."""

    def __init__(self, max_iceberg_dist_km: float = 200.0, default_depth_m: float = 3500.0):
        self.max_iceberg_dist_km = max_iceberg_dist_km
        self.default_depth_m = default_depth_m

    def extract(self, point: EnrichedAISFeaturePoint) -> MLFeatureVector:
        """Extract a deterministic feature vector from a single enriched point.
        
        Args:
            point: EnrichedAISFeaturePoint from historical environmental replay.
            
        Returns:
            MLFeatureVector with normalized/cyclical engineered values.
        """
        feats: Dict[str, float] = {}

        # 1. Kinematic features
        speed = float(point.speed_knots) if point.speed_knots is not None else 0.0
        course = float(point.course_deg) if point.course_deg is not None else 0.0
        heading = float(point.heading_deg) if point.heading_deg is not None else course

        course_rad = math.radians(course)
        feats["speed_knots"] = speed
        feats["course_deg"] = course
        feats["heading_deg"] = heading
        feats["sin_course"] = math.sin(course_rad)
        feats["cos_course"] = math.cos(course_rad)

        # 2. Spatial coordinates & cyclical
        lat = float(point.latitude)
        lon = float(point.longitude)
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        feats["latitude"] = lat
        feats["longitude"] = lon
        feats["sin_lat"] = math.sin(lat_rad)
        feats["cos_lat"] = math.cos(lat_rad)
        feats["sin_lon"] = math.sin(lon_rad)
        feats["cos_lon"] = math.cos(lon_rad)

        # 3. Temporal Seasonal Cyclical features
        ts = point.timestamp
        if ts is not None:
            month = ts.month
            day_of_year = ts.timetuple().tm_yday
            hour = ts.hour
            # Full Antarctic seasonal cycle: 365.25 days
            cycle_fraction = 2.0 * math.pi * (day_of_year / 365.25)
            feats["month"] = float(month)
            feats["day_of_year"] = float(day_of_year)
            feats["hour"] = float(hour)
            feats["sin_day_of_year"] = math.sin(cycle_fraction)
            feats["cos_day_of_year"] = math.cos(cycle_fraction)
        else:
            feats["month"] = 1.0
            feats["day_of_year"] = 1.0
            feats["hour"] = 0.0
            feats["sin_day_of_year"] = 0.0
            feats["cos_day_of_year"] = 1.0

        # 4. Sea Ice Regime
        sic = float(point.sic) if point.sic is not None else 0.0
        sic = max(0.0, min(1.0, sic))
        feats["sic"] = sic
        feats["sic_percent"] = sic * 100.0
        # WMO Sea ice threshold is 15% (0.15)
        feats["is_ice_covered"] = 1.0 if sic >= 0.15 else 0.0

        # 5. Obstacles & Hazard Proximity
        ib_dist = point.iceberg_distance_km
        if ib_dist is None or math.isnan(ib_dist):
            ib_dist = self.max_iceberg_dist_km
        ib_dist = max(0.0, min(float(ib_dist), self.max_iceberg_dist_km))
        feats["iceberg_distance_km"] = ib_dist
        feats["has_iceberg_within_50km"] = 1.0 if ib_dist <= 50.0 else 0.0
        feats["has_iceberg_within_15km"] = 1.0 if ib_dist <= 15.0 else 0.0

        # 6. Bathymetry & Coastal Topography
        depth = float(point.bathymetry_depth_m) if point.bathymetry_depth_m is not None else self.default_depth_m
        feats["bathymetry_depth_m"] = depth
        feats["is_shallow"] = 1.0 if (point.is_shallow or depth < 20.0) else 0.0

        coast_dist = float(point.coastline_distance_km) if point.coastline_distance_km is not None else 100.0
        feats["coastline_distance_km"] = coast_dist
        feats["is_on_land"] = 1.0 if point.is_on_land else 0.0

        # 7. Ocean Hydrodynamics & Atmosphere
        feats["ocean_current_speed_ms"] = float(point.ocean_current_speed_ms or 0.0)
        feats["ocean_current_u_ms"] = float(point.ocean_current_u_ms or 0.0)
        feats["ocean_current_v_ms"] = float(point.ocean_current_v_ms or 0.0)
        feats["sea_surface_temp_c"] = float(point.sea_surface_temp_c or 0.0)
        feats["wind_speed_ms"] = float(point.wind_speed_ms or 0.0)
        feats["air_temp_c"] = float(point.air_temp_c or 0.0)

        return MLFeatureVector(
            features=feats,
            vessel_id=point.vessel_id,
            voyage_id=point.voyage_id,
            timestamp=point.timestamp,
        )

    def extract_batch(self, points: List[EnrichedAISFeaturePoint]) -> List[MLFeatureVector]:
        """Batch extract features for a collection of enriched points."""
        return [self.extract(p) for p in points]
