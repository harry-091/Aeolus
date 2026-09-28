"""PolarNav // Sentinel-1 SAR Radar Obstacle Service.

Provides normalized georeferenced radar obstacle targets extracted from
calibrated Sentinel-1 C-SAR GeoTIFF scenes via CFAR target detection
and machine learning segmentation.
Source: Microsoft Planetary Computer / ESA Copernicus Sentinel-1A C-SAR.
"""

import os
import json
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
RAW_S1_DIR = BACKEND_DIR / "data" / "raw" / "sentinel" / "real_s1_scenes"
MANIFEST_PATH = RAW_S1_DIR / "manifest.json"
CACHE_DIR = BACKEND_DIR / "data" / "cache" / "sentinel"
CACHE_FILE = CACHE_DIR / "radar_obstacles_geojson.json"


class SentinelRadarService:
    """Service providing georeferenced radar obstacles from Sentinel-1 SAR acquisitions."""

    def __init__(self):
        self._cached_geojson: Optional[Dict[str, Any]] = None

    def initialize(self) -> Dict[str, Any]:
        """Load cached radar obstacles or compute and cache them from real scenes."""
        if self._cached_geojson is not None:
            return self._cached_geojson

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self._cached_geojson = json.load(f)
                    return self._cached_geojson
            except Exception:
                pass

        # If cache is missing or corrupt, extract from real scenes
        self._cached_geojson = self._extract_radar_obstacles()
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cached_geojson, f, indent=2)
        except Exception:
            pass

        return self._cached_geojson

    def _extract_radar_obstacles(self) -> Dict[str, Any]:
        """Extract georeferenced radar obstacles across available Sentinel-1 scenes."""
        from src.sentinel.predict import detect_sar_icebergs

        if not MANIFEST_PATH.exists():
            return {
                "type": "FeatureCollection",
                "status": "error",
                "message": "Sentinel-1 manifest not found",
                "total_obstacles": 0,
                "features": []
            }

        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        tifs = sorted(glob.glob(str(RAW_S1_DIR / "*.tif")))
        features: List[Dict[str, Any]] = []

        for t in tifs:
            t_path = Path(t)
            name = t_path.name
            prefix = name.split("_hh.tif")[0]
            matched_m = next((m for m in manifest if m.get("id", "").startswith(prefix)), None)
            if not matched_m:
                continue

            bbox = matched_m.get("bbox", [160.0, -75.0, 170.0, -70.0])
            dt = matched_m.get("datetime", "2024-06-30T10:30:46Z")
            platform = matched_m.get("platform", "SENTINEL-1A")

            try:
                res = detect_sar_icebergs(t, target_size=(256, 256))
                dets = res.get("detections", [])
                for d in dets:
                    cy, cx = d.get("pixel_centroid", [128.0, 128.0])
                    frac_y = float(cy) / 256.0
                    frac_x = float(cx) / 256.0

                    # Latitude interpolation (y=0 is top/max_lat, y=256 is bottom/min_lat)
                    min_lat, max_lat = float(bbox[1]), float(bbox[3])
                    lat = max_lat - frac_y * (max_lat - min_lat)

                    # Longitude interpolation handling antimeridian crossing
                    min_lon, max_lon = float(bbox[0]), float(bbox[2])
                    if max_lon < min_lon:
                        span = (max_lon + 360.0) - min_lon
                        lon = min_lon + frac_x * span
                        if lon > 180.0:
                            lon -= 360.0
                    else:
                        lon = min_lon + frac_x * (max_lon - min_lon)

                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [round(lon, 4), round(lat, 4)]
                        },
                        "properties": {
                            "target_id": f"S1-OBSTACLE-{len(features)+1:03d}",
                            "scene_id": matched_m.get("id", ""),
                            "latitude": round(lat, 4),
                            "longitude": round(lon, 4),
                            "area_km2": d.get("area_km2", 0.05),
                            "dimensions_km": d.get("dimensions_km", "0.2 x 0.1 km"),
                            "peak_sigma0_db": d.get("peak_sigma0_db", -5.0),
                            "mean_sigma0_db": d.get("mean_sigma0_db", -7.0),
                            "confidence": d.get("confidence", 0.78),
                            "classification": d.get("classification", "Bergy Bit / Ice Floe Contact"),
                            "observation_time": dt,
                            "sensor": f"{platform} C-SAR (HH)",
                            "source": "Microsoft Planetary Computer / Copernicus Sentinel-1",
                            "provenance": "OBSERVED_SAR_CFAR"
                        }
                    })
            except Exception:
                continue

        return {
            "type": "FeatureCollection",
            "status": "success",
            "source": "Microsoft Planetary Computer / Copernicus Sentinel-1 C-SAR",
            "label": "Latest available Sentinel-1 observation",
            "observation_date": "2024-06-30T10:30:46Z",
            "provenance": "OBSERVED_SAR_CFAR",
            "total_obstacles": len(features),
            "features": features
        }

    def get_obstacles_geojson(self) -> Dict[str, Any]:
        """Return the normalized GeoJSON radar obstacle collection."""
        return self.initialize()

    def get_obstacles_list(self) -> List[Dict[str, Any]]:
        """Return a simple list of obstacle objects for backend routing and proximity evaluation."""
        geojson = self.initialize()
        return [f.get("properties", {}) for f in geojson.get("features", [])]


radar_obstacle_service = SentinelRadarService()
