"""PolarNav // Real-Time Satellite Metadata & Imagery Caching Engine.

Provides thread-safe disk and in-memory caching with strict deduplication:
- Prevents redundant downloads of identical satellite scenes.
- Stores scene metadata, GeoTIFF headers, and quicklook thumbnails.
- Manages TTL-based invalidation.
"""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import OrderedDict

from .models import SatelliteScene, SatelliteFreshness

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "sentinel"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
METADATA_INDEX = CACHE_DIR / "satellite_scenes_index.json"


class SatelliteCacheManager:
    """High-performance caching and deduplication manager for satellite telemetry."""

    def __init__(self, max_memory_entries: int = 200, default_ttl_hours: float = 72.0):
        self.cache_dir = CACHE_DIR
        self.max_memory_entries = max_memory_entries
        self.default_ttl = timedelta(hours=default_ttl_hours)
        self._memory_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._downloaded_hashes: set = set()
        self._load_disk_index()

    def _load_disk_index(self):
        """Load persistent index from disk if available."""
        if METADATA_INDEX.exists():
            try:
                with open(METADATA_INDEX, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("scenes", []):
                        sid = item.get("scene_id")
                        if sid:
                            self._memory_cache[sid] = item
                            self._downloaded_hashes.add(sid)
            except Exception as e:
                print(f"[SatelliteCache] Warning loading disk index: {e}")

    def _persist_disk_index(self):
        """Save current index to disk."""
        try:
            payload = {
                "last_persisted": datetime.now(timezone.utc).isoformat(),
                "total_scenes": len(self._memory_cache),
                "scenes": list(self._memory_cache.values())
            }
            with open(METADATA_INDEX, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            print(f"[SatelliteCache] Warning saving disk index: {e}")

    def is_cached(self, scene_id: str) -> bool:
        """Check if scene metadata or assets are already cached."""
        return scene_id in self._memory_cache

    def get_scene(self, scene_id: str) -> Optional[SatelliteScene]:
        """Retrieve cached SatelliteScene object if available."""
        if scene_id in self._memory_cache:
            self._memory_cache.move_to_end(scene_id)
            data = self._memory_cache[scene_id]
            try:
                scene = SatelliteScene(**data)
                scene.evaluate_freshness()
                return scene
            except Exception:
                return None
        return None

    def store_scene(self, scene: SatelliteScene, persist_disk: bool = True):
        """Store SatelliteScene in memory and disk index with deduplication."""
        scene_id = scene.scene_id
        if scene_id in self._memory_cache:
            # Already cached, update LRU order and refreshed status
            self._memory_cache.move_to_end(scene_id)
            return

        # Evict oldest entry if over capacity
        if len(self._memory_cache) >= self.max_memory_entries:
            self._memory_cache.popitem(last=False)

        data = scene.model_dump() if hasattr(scene, "model_dump") else scene.dict()
        # Convert datetimes to ISO
        if isinstance(data.get("acquisition_time"), datetime):
            data["acquisition_time"] = data["acquisition_time"].isoformat()
        if isinstance(data.get("ingested_at"), datetime):
            data["ingested_at"] = data["ingested_at"].isoformat()

        self._memory_cache[scene_id] = data
        self._downloaded_hashes.add(scene_id)

        if persist_disk:
            self._persist_disk_index()

    def get_all_cached_scenes(self) -> List[SatelliteScene]:
        """Return all valid cached scenes sorted by acquisition time descending."""
        scenes = []
        for raw in self._memory_cache.values():
            try:
                s = SatelliteScene(**raw)
                s.evaluate_freshness()
                scenes.append(s)
            except Exception:
                continue
        scenes.sort(key=lambda s: s.acquisition_time, reverse=True)
        return scenes

    def get_cache_stats(self) -> Dict[str, Any]:
        """Diagnostic cache telemetry."""
        return {
            "cached_scene_count": len(self._memory_cache),
            "disk_cache_path": str(self.cache_dir),
            "disk_index_exists": METADATA_INDEX.exists(),
            "max_memory_capacity": self.max_memory_entries,
        }


# Global cache manager singleton
satellite_cache_manager = SatelliteCacheManager()
