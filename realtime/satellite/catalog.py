"""PolarNav // Real Satellite STAC Catalog Query Engine.

Queries real STAC catalogues (Microsoft Planetary Computer & ESA Copernicus)
for Antarctic Sentinel-1 SAR and Sentinel-2 optical imagery passes.
Extracts rigorous orbital, swath geometry, polarization, and sensor telemetry.
Incorporates local verified Antarctic scene manifests for robust resilience.
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import requests
try:
    import pystac_client
    HAS_PYSTAC = True
except ImportError:
    HAS_PYSTAC = False

from .models import SatelliteScene, SatelliteFreshness, SatelliteProductType
from .optical_filter import optical_evaluator
from .cache import satellite_cache_manager

logger = logging.getLogger("polarnav.satellite.catalog")

PLANETARY_COMPUTER_STAC_URL = os.environ.get("STAC_API_URL") or os.environ.get(
    "PLANETARY_COMPUTER_STAC_URL", "https://planetarycomputer.microsoft.com/api/stac/v1"
)
RAW_SENTINEL_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "sentinel"
S1_MANIFEST_PATH = RAW_SENTINEL_DIR / "real_s1_scenes" / "manifest.json"

# Key Antarctic Operational Maritime Sectors [lon_min, lat_min, lon_max, lat_max]
ANTARCTIC_SECTORS = {
    "PRYDZ_BAY_BHARATI": [65.0, -72.0, 85.0, -65.0],
    "QUEEN_MAUD_LAND_MAITRI": [8.0, -73.0, 20.0, -68.0],
    "ROSS_SEA_MCMURDO": [160.0, -78.0, 180.0, -70.0],
    "WEDDELL_SEA_PENINSULA": [-70.0, -75.0, -50.0, -62.0],
    "CIRCUMPOLAR_SOUTHERN_OCEAN": [-180.0, -85.0, 180.0, -55.0],
}


class SatelliteCatalogClient:
    """Production client for querying live and archived remote sensing scenes."""

    def __init__(self, stac_url: str = PLANETARY_COMPUTER_STAC_URL):
        self.stac_url = stac_url
        self._seed_local_manifest()

    def _seed_local_manifest(self):
        """Seed cache from verified real Sentinel-1 GeoTIFF manifest."""
        if S1_MANIFEST_PATH.exists():
            try:
                with open(S1_MANIFEST_PATH, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                    for item in manifest_data:
                        scene = self._parse_manifest_item(item)
                        if scene:
                            satellite_cache_manager.store_scene(scene, persist_disk=False)
            except Exception as e:
                logger.warning(f"Error seeding local Sentinel manifest: {e}")

    def _parse_manifest_item(self, item: Dict[str, Any]) -> Optional[SatelliteScene]:
        """Convert a manifest record to a validated SatelliteScene."""
        try:
            sid = item.get("id", "UNKNOWN_SCENE")
            dt_str = item.get("datetime")
            if dt_str:
                acq_time = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            else:
                acq_time = datetime.now(timezone.utc) - timedelta(hours=24)

            geom = item.get("geometry", {})
            bbox = item.get("bbox", [0.0, -70.0, 0.0, -70.0])
            
            # Product type classification
            if "EW_GRDM" in sid:
                ptype = SatelliteProductType.SENTINEL_1_GRD_EW.value
                res = 40.0
            elif "IW_GRDH" in sid:
                ptype = SatelliteProductType.SENTINEL_1_GRD_IW.value
                res = 10.0
            else:
                ptype = "S1_SAR_GRD"
                res = 20.0

            scene = SatelliteScene(
                scene_id=sid,
                source="ESA Copernicus Sentinel-1A (Planetary Computer STAC Archive)",
                acquisition_time=acq_time,
                geometry=geom,
                bbox=bbox,
                product_type=ptype,
                resolution_meters=res,
                processing_status="PROCESSED",
                quality="HIGH",
                availability=SatelliteFreshness.RECENT,
                orbit_direction=item.get("orbit_direction", "ascending"),
                relative_orbit=item.get("relative_orbit", 54),
                polarizations=["HH"],
                cloud_independent=True,
                cloud_cover_pct=0.0,
                is_optical_usable=True,
                assets=item.get("assets", ["hh", "thumbnail"]),
                tile_url=item.get("hh_href"),
                file_size_mb=round(float(item.get("file_size_mb", 18.5)), 2),
            )
            scene.evaluate_freshness()
            return scene
        except Exception as e:
            logger.debug(f"Failed to parse manifest item: {e}")
            return None

    def search_scenes(
        self,
        bbox: Optional[List[float]] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: float = 150.0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        collections: Optional[List[str]] = None,
        max_results: int = 15,
        use_live_api: bool = True,
    ) -> List[SatelliteScene]:
        """Search STAC catalog for Sentinel scenes matching geographic criteria."""
        now = datetime.now(timezone.utc)
        
        # 1. Resolve bounding box
        if bbox is None:
            if lat is not None and lon is not None:
                # Approximate degree box around coordinate
                delta_lat = radius_km / 111.0
                delta_lon = radius_km / (111.0 * max(0.1, abs(math.cos(math.radians(lat)))))
                bbox = [
                    round(lon - delta_lon, 3),
                    round(lat - delta_lat, 3),
                    round(lon + delta_lon, 3),
                    round(lat + delta_lat, 3),
                ]
            else:
                bbox = ANTARCTIC_SECTORS["PRYDZ_BAY_BHARATI"]

        if collections is None:
            collections = ["sentinel-1-grd", "sentinel-2-l2a"]

        time_end = end_date or now
        time_start = start_date or (time_end - timedelta(days=30))
        time_range_str = f"{time_start.strftime('%Y-%m-%d')}/{time_end.strftime('%Y-%m-%d')}"

        results: List[SatelliteScene] = []

        # 2. Query Live STAC if requested
        if use_live_api:
            try:
                results.extend(self._query_stac_api(bbox, time_range_str, collections, max_results))
            except Exception as e:
                logger.info(f"STAC live query unreachable ({e}), retrieving from indexed cache")

        # In production/real-data-only mode, never silently substitute cached scenes
        # when the live external catalogue did not answer.
        real_data_only = os.environ.get("POLARNAV_REAL_DATA_ONLY", "false").lower() in ("1", "true", "yes", "on")
        if real_data_only:
            results.sort(key=lambda s: s.acquisition_time, reverse=True)
            return results[:max_results]

        # 3. If live query yielded fewer than max_results, supplement with cached local scenes
        if len(results) < max_results:
            cached_scenes = satellite_cache_manager.get_all_cached_scenes()
            for cs in cached_scenes:
                if len(results) >= max_results:
                    break
                # Check spatial overlap with bbox
                if self._bbox_intersects(cs.bbox, bbox):
                    if not any(r.scene_id == cs.scene_id for r in results):
                        cs.evaluate_freshness()
                        results.append(cs)

        # 4. Sort by acquisition time descending (most recent first)
        results.sort(key=lambda s: s.acquisition_time, reverse=True)
        return results[:max_results]

    def _query_stac_api(
        self,
        bbox: List[float],
        time_range: str,
        collections: List[str],
        max_items: int,
    ) -> List[SatelliteScene]:
        """Direct REST query to STAC /search endpoint."""
        scenes: List[SatelliteScene] = []
        headers = {"Accept": "application/geo+json"}
        
        payload = {
            "bbox": bbox,
            "datetime": time_range,
            "collections": collections,
            "limit": max_items,
        }

        resp = requests.post(f"{self.stac_url}/search", json=payload, headers=headers, timeout=6.0)
        if resp.status_code == 200:
            data = resp.json()
            for feature in data.get("features", []):
                scene = self._parse_stac_feature(feature)
                if scene:
                    satellite_cache_manager.store_scene(scene)
                    scenes.append(scene)
        return scenes

    def _parse_stac_feature(self, feature: Dict[str, Any]) -> Optional[SatelliteScene]:
        """Convert a raw GeoJSON STAC feature into SatelliteScene."""
        try:
            sid = feature.get("id")
            props = feature.get("properties", {})
            collection = feature.get("collection", "")
            
            dt_str = props.get("datetime")
            if dt_str:
                acq_time = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            else:
                acq_time = datetime.now(timezone.utc)

            geom = feature.get("geometry", {})
            bbox = feature.get("bbox", [0.0, 0.0, 0.0, 0.0])
            center_lat = (bbox[1] + bbox[3]) / 2.0 if len(bbox) >= 4 else -70.0
            center_lon = (bbox[0] + bbox[2]) / 2.0 if len(bbox) >= 4 else 70.0

            # Sentinel-1 vs Sentinel-2 classification
            if "sentinel-1" in collection or "S1" in sid:
                ptype = SatelliteProductType.SENTINEL_1_GRD_EW.value if "EW" in sid else SatelliteProductType.SENTINEL_1_GRD_IW.value
                res = 40.0 if "EW" in sid else 10.0
                cloud_indep = True
                cloud_pct = 0.0
                usable = True
                source = f"ESA Copernicus Sentinel-1 ({props.get('platform', 'S1A')}) C-Band SAR"
            else:
                ptype = SatelliteProductType.SENTINEL_2_MSI_L2A.value
                res = 10.0
                cloud_indep = False
                cloud_pct = float(props.get("eo:cloud_cover", 0.0))
                # Evaluate optical daylight and cloud limitations
                opt_diag = optical_evaluator.evaluate(center_lat, center_lon, acq_time, cloud_pct)
                usable = opt_diag["is_usable"]
                source = f"ESA Copernicus Sentinel-2 ({props.get('platform', 'S2A')}) Multi-Spectral"

            scene = SatelliteScene(
                scene_id=sid,
                source=source,
                acquisition_time=acq_time,
                geometry=geom,
                bbox=bbox,
                product_type=ptype,
                resolution_meters=res,
                processing_status="PROCESSED",
                quality="HIGH" if usable else "DEGRADED_CLOUD_COVER",
                availability=SatelliteFreshness.RECENT,
                orbit_direction=props.get("sat:orbit_state", props.get("orbit_direction", "ascending")),
                relative_orbit=props.get("sat:relative_orbit"),
                polarizations=props.get("sar:polarizations", ["HH"]),
                cloud_independent=cloud_indep,
                cloud_cover_pct=round(cloud_pct, 1),
                is_optical_usable=usable,
                assets=list(feature.get("assets", {}).keys()),
            )
            scene.evaluate_freshness()
            return scene
        except Exception as e:
            logger.debug(f"Failed to parse STAC feature: {e}")
            return None

    def _bbox_intersects(self, b1: List[float], b2: List[float]) -> bool:
        """Check if two bounding boxes [lon_min, lat_min, lon_max, lat_max] intersect."""
        if not b1 or not b2 or len(b1) < 4 or len(b2) < 4:
            return False
        return not (
            b1[2] < b2[0] or  # b1 is left of b2
            b1[0] > b2[2] or  # b1 is right of b2
            b1[3] < b2[1] or  # b1 is below b2
            b1[1] > b2[3]     # b1 is above b2
        )


import math

satellite_catalog = SatelliteCatalogClient()
