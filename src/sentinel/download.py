"""
Sentinel-1 SAR and Sentinel-2 Optical Downloader & STAC Catalog Integration.
"""
import json
import os
import requests
import pystac_client
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SENTINEL_RAW_DIR = BASE_DIR / "data" / "raw" / "sentinel"
S1_DIR = SENTINEL_RAW_DIR / "real_s1_scenes"
S2_DIR = SENTINEL_RAW_DIR / "real_s2_scenes"

S2_DIR.mkdir(parents=True, exist_ok=True)
S1_DIR.mkdir(parents=True, exist_ok=True)


def search_sentinel_scenes(
    bbox=[-65.0, -70.0, -50.0, -62.0],
    start_date="2024-01-01",
    end_date="2024-06-30",
    max_items=5
):
    """
    Search Planetary Computer STAC for Antarctic Sentinel-1 and Sentinel-2 scenes.
    """
    try:
        stac_url = os.environ.get("STAC_API_URL") or os.environ.get(
            "PLANETARY_COMPUTER_STAC_URL", "https://planetarycomputer.microsoft.com/api/stac/v1"
        )
        catalog = pystac_client.Client.open(stac_url)
        
        # 1. Search Sentinel-1 GRD SAR
        s1_search = catalog.search(
            collections=["sentinel-1-grd"],
            bbox=bbox,
            datetime=f"{start_date}/{end_date}",
            max_items=max_items
        )
        s1_items = list(s1_search.items())

        # 2. Search Sentinel-2 L2A Optical (low cloud cover)
        s2_search = catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            datetime=f"{start_date}/{end_date}",
            query={"eo:cloud_cover": {"lt": 25}},
            max_items=max_items
        )
        s2_items = list(s2_search.items())

        catalog_summary = {
            "sentinel1_sar_scenes": [
                {
                    "id": item.id,
                    "datetime": str(item.datetime),
                    "platform": item.properties.get("platform", "SENTINEL-1"),
                    "bbox": item.bbox,
                    "polarizations": item.properties.get("sar:polarizations", ["HH"]),
                    "assets": list(item.assets.keys())
                }
                for item in s1_items
            ],
            "sentinel2_optical_scenes": [
                {
                    "id": item.id,
                    "datetime": str(item.datetime),
                    "cloud_cover": item.properties.get("eo:cloud_cover", 0.0),
                    "bbox": item.bbox,
                    "assets": list(item.assets.keys())
                }
                for item in s2_items
            ]
        }

        out_path = SENTINEL_RAW_DIR / "sentinel_scenes_catalog.json"
        with open(out_path, "w") as f:
            json.dump(catalog_summary, f, indent=2)

        return catalog_summary
    except Exception as e:
        print(f"STAC search warning: {e}")
        return {}


def get_available_local_scenes():
    """
    List all physically downloaded and available Sentinel-1 and Sentinel-2 scenes.
    """
    s1_tifs = sorted(list(S1_DIR.glob("*.tif")))
    
    scenes = []
    for tif in s1_tifs:
        sz_mb = tif.stat().st_size / (1024 * 1024)
        scenes.append({
            "filename": tif.name,
            "path": str(tif),
            "size_mb": round(sz_mb, 2),
            "sensor": "Sentinel-1 C-SAR",
            "mode": "EW/IW GRD",
            "polarization": "HH",
            "status": "READY_FOR_TRAINING"
        })
    return scenes
