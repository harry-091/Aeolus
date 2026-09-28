"""Unit & Integration Tests for PolarNav Phase 2: Real Satellite Monitoring.

Validates:
1. SatelliteScene model schema, attributes, and serialization.
2. Dynamic freshness classification (LIVE, RECENT, STALE, UNAVAILABLE).
3. OpticalUsabilityEvaluator: solar elevation and cloud cover limitations.
4. SatelliteCacheManager: storage, retrieval, and deduplication.
5. SatelliteCatalogClient: real scene parsing and spatial footprint intersection.
6. SatelliteProvider: BaseDataProvider contract compliance and live observation fetching.
7. REST API Endpoints: /api/realtime/satellite/scenes and /api/realtime/satellite/scene/{id}.
"""

import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from realtime.satellite import (
    SatelliteProvider,
    SatelliteObservation,
    SatelliteScene,
    SatelliteFreshness,
    SatelliteProductType,
    optical_evaluator,
    satellite_catalog,
    satellite_cache_manager,
)
from realtime.base import BaseDataProvider, DataCategory, ProviderStatus
from app.server import app

client = TestClient(app)


class TestSatelliteSceneModel:
    """Validate SatelliteScene schema and freshness evaluation."""

    def test_satellite_scene_fields(self):
        now = datetime.now(timezone.utc)
        scene = SatelliteScene(
            scene_id="S1A_EW_GRDM_TEST_001",
            source="ESA Copernicus Sentinel-1A C-SAR",
            acquisition_time=now - timedelta(hours=2),
            geometry={"type": "Polygon", "coordinates": [[[65.0, -70.0], [70.0, -70.0], [70.0, -68.0], [65.0, -68.0], [65.0, -70.0]]]},
            bbox=[65.0, -70.0, 70.0, -68.0],
            product_type="S1_GRD_EW",
            resolution_meters=40.0,
            processing_status="PROCESSED",
            quality="HIGH",
            availability=SatelliteFreshness.LIVE,
            orbit_direction="ascending",
            relative_orbit=54,
            polarizations=["HH", "HV"],
            cloud_independent=True,
        )
        assert scene.scene_id == "S1A_EW_GRDM_TEST_001"
        assert scene.resolution_meters == 40.0
        assert scene.cloud_independent is True
        summary = scene.to_summary_dict()
        assert "acquisition_time" in summary
        assert summary["availability"] == "LIVE"

    def test_freshness_classification_tiers(self):
        now = datetime.now(timezone.utc)

        # 1. LIVE (< 6 hours old)
        s_live = SatelliteScene(
            scene_id="LIVE_TEST",
            source="Test",
            acquisition_time=now - timedelta(hours=3),
            geometry={},
            bbox=[0, 0, 0, 0],
            product_type="S1_GRD_IW",
            resolution_meters=10.0,
            processing_status="RAW",
            quality="NOMINAL",
            availability=SatelliteFreshness.UNAVAILABLE,
        )
        assert s_live.evaluate_freshness(now) == SatelliteFreshness.LIVE

        # 2. RECENT (6h to 48h old)
        s_recent = SatelliteScene(
            scene_id="RECENT_TEST",
            source="Test",
            acquisition_time=now - timedelta(hours=20),
            geometry={},
            bbox=[0, 0, 0, 0],
            product_type="S1_GRD_IW",
            resolution_meters=10.0,
            processing_status="RAW",
            quality="NOMINAL",
            availability=SatelliteFreshness.UNAVAILABLE,
        )
        assert s_recent.evaluate_freshness(now) == SatelliteFreshness.RECENT

        # 3. STALE (> 48h old)
        s_stale = SatelliteScene(
            scene_id="STALE_TEST",
            source="Test",
            acquisition_time=now - timedelta(days=5),
            geometry={},
            bbox=[0, 0, 0, 0],
            product_type="S1_GRD_IW",
            resolution_meters=10.0,
            processing_status="RAW",
            quality="NOMINAL",
            availability=SatelliteFreshness.UNAVAILABLE,
        )
        assert s_stale.evaluate_freshness(now) == SatelliteFreshness.STALE


class TestOpticalUsabilityFilter:
    """Validate solar elevation and cloud cover limitations."""

    def test_polar_night_rejection(self):
        # Antarctic winter: June 21 at 70°S
        winter_dt = datetime(2024, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
        res = optical_evaluator.evaluate(lat=-70.0, lon=70.0, acquisition_time=winter_dt, cloud_cover_pct=5.0)
        assert res["is_usable"] is False
        assert "POLAR_NIGHT" in res["status"] or "LOW_SOLAR" in res["status"]
        assert res["recommendation"] == "USE_SENTINEL1_SAR_INSTEAD"

    def test_cloud_obscured_rejection(self):
        # Summer daylight with heavy cloud cover (85%)
        summer_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        res = optical_evaluator.evaluate(lat=-66.0, lon=70.0, acquisition_time=summer_dt, cloud_cover_pct=85.0)
        assert res["is_usable"] is False
        assert res["status"] == "CLOUD_OBSCURED"
        assert res["recommendation"] == "USE_SENTINEL1_SAR_INSTEAD"

    def test_optimal_daylight_clear_scene(self):
        # Summer daylight with clear skies (5% cloud cover)
        summer_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        res = optical_evaluator.evaluate(lat=-66.0, lon=70.0, acquisition_time=summer_dt, cloud_cover_pct=5.0)
        assert res["is_usable"] is True
        assert res["status"] == "OPTIMAL_OPTICAL_ACQUISITION"


class TestSatelliteCaching:
    """Validate cache storage, retrieval, and deduplication."""

    def test_store_and_deduplicate(self):
        now = datetime.now(timezone.utc)
        test_scene = SatelliteScene(
            scene_id="TEST_DEDUP_001",
            source="Sentinel-1A Test",
            acquisition_time=now - timedelta(hours=10),
            geometry={},
            bbox=[65.0, -70.0, 75.0, -66.0],
            product_type="S1_GRD_EW",
            resolution_meters=40.0,
            processing_status="PROCESSED",
            quality="HIGH",
            availability=SatelliteFreshness.RECENT,
        )
        initial_count = satellite_cache_manager.get_cache_stats()["cached_scene_count"]
        
        # First store
        satellite_cache_manager.store_scene(test_scene, persist_disk=False)
        assert satellite_cache_manager.is_cached("TEST_DEDUP_001")
        
        # Second store of identical scene (must deduplicate)
        satellite_cache_manager.store_scene(test_scene, persist_disk=False)
        retrieved = satellite_cache_manager.get_scene("TEST_DEDUP_001")
        assert retrieved is not None
        assert retrieved.scene_id == "TEST_DEDUP_001"


class TestSatelliteCatalogClient:
    """Validate catalog search, footprint extraction, and local fallback."""

    def test_search_antarctic_scenes(self):
        # Prydz Bay / Bharati region
        scenes = satellite_catalog.search_scenes(
            lat=-69.41,
            lon=76.19,
            radius_km=300.0,
            max_results=5,
            use_live_api=False,
        )
        assert len(scenes) >= 1
        for s in scenes:
            assert isinstance(s, SatelliteScene)
            assert s.scene_id != ""
            assert s.resolution_meters > 0
            assert s.availability in SatelliteFreshness


class TestSatelliteProviderIntegration:
    """Validate BaseDataProvider contract and observation generation."""

    def test_provider_contract(self):
        provider = SatelliteProvider()
        assert isinstance(provider, BaseDataProvider)
        
        # get_coverage()
        cov = provider.get_coverage()
        assert cov.contains(-66.0, 70.0)
        assert not cov.contains(0.0, 0.0)

        # get_status()
        health = provider.get_status()
        assert health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
        assert health.category == "SATELLITE"

        # fetch_current() in Antarctic zone
        obs = provider.fetch_current(-69.41, 76.19)
        assert isinstance(obs, SatelliteObservation)
        assert obs.metadata.provenance in (DataCategory.OBSERVED, DataCategory.STALE)
        assert obs.acquisition_timestamp is not None
        assert obs.sar_backscatter_hh_db < 0.0

        # fetch_recent()
        recent = provider.fetch_recent(-69.41, 76.19, hours=48.0)
        assert isinstance(recent, list)
        assert len(recent) >= 1

    def test_out_of_bounds_marked_unavailable(self):
        provider = SatelliteProvider()
        obs = provider.fetch_current(0.0, 0.0)
        assert obs.metadata.provenance == DataCategory.UNAVAILABLE
        assert obs.satellite_freshness == SatelliteFreshness.UNAVAILABLE


class TestSatelliteRESTEndpoints:
    """Validate FastAPI REST endpoints."""

    def test_get_satellite_scenes(self):
        response = client.get("/api/realtime/satellite/scenes?lat=-69.41&lon=76.19&radius_km=300")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "scenes" in data
        assert "cache_stats" in data
        assert data["count"] >= 1
        
        first_scene = data["scenes"][0]
        assert "scene_id" in first_scene
        assert "acquisition_time" in first_scene
        assert "availability" in first_scene
        assert "product_type" in first_scene

    def test_get_satellite_scene_detail(self):
        # Fetch scenes list first
        list_res = client.get("/api/realtime/satellite/scenes")
        assert list_res.status_code == 200
        scenes = list_res.json().get("scenes", [])
        assert len(scenes) > 0
        target_id = scenes[0]["scene_id"]

        # Fetch detail
        detail_res = client.get(f"/api/realtime/satellite/scene/{target_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["scene_id"] == target_id

    def test_get_nonexistent_scene_returns_404(self):
        response = client.get("/api/realtime/satellite/scene/NON_EXISTENT_SCENE_99999")
        assert response.status_code == 404
