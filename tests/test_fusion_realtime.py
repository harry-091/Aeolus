"""POLARNAV — Phase 8: Real-Time Maritime Data Fusion Engine Test Suite.

Rigorously verifies:
1. Multi-sensor fusion combining Satellite, Sea Ice, Weather, Ocean Currents,
   Waves, Icebergs, Bathymetry, Coastline, and Vessel State into CurrentMaritimeState.
2. Complete coverage of the 13 canonical parameters on every spatial cell / route node.
3. Strict non-simultaneous temporal tracking (individual source timestamps, data age, freshness).
4. Mathematical validity of unified environmental confidence scoring.
5. Strict critical staleness gating: FLAG IT, do NOT silently continue as live.
6. Route corridor multi-node fusion.
7. REST API endpoints.
"""
import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from realtime import (
    CurrentMaritimeState,
    SpatialCellMaritimeState,
    VesselState,
    LayerFreshness,
    LayerTemporalAudit,
    CellWindState,
    CellWaveState,
    CellCurrentState,
    CoastlineObservation,
    maritime_state_manager,
    DataCategory,
)
from app.server import app

client = TestClient(app)


class TestMaritimeFusionEngine:
    """Validate core multi-source fusion mechanics, data contracts, and anti-falsification invariants."""

    def test_fusion_combines_all_required_layers(self):
        """Verify CurrentMaritimeState integrates all 8 environmental layers + Vessel State."""
        v_state = VesselState(speed_knots=14.0, heading_deg=225.0, draft_m=9.0, polar_class="PC4")
        state = maritime_state_manager.get_current_state(
            lat=-65.20,
            lon=64.30,
            vessel_state=v_state,
        )

        assert isinstance(state, CurrentMaritimeState)
        assert state.latitude == -65.20
        assert state.longitude == 64.30
        assert state.vessel_state.speed_knots == 14.0
        assert state.vessel_state.draft_m == 9.0
        assert state.vessel_state.polar_class == "PC4"

        # Verify all autonomous provider layers are present
        assert hasattr(state, "satellite") and state.satellite is not None
        assert hasattr(state, "sea_ice") and state.sea_ice is not None
        assert hasattr(state, "weather") and state.weather is not None
        assert hasattr(state, "ocean") and state.ocean is not None
        assert hasattr(state, "iceberg") and state.iceberg is not None
        assert hasattr(state, "bathymetry") and state.bathymetry is not None
        assert hasattr(state, "coastline") and state.coastline is not None

        # Verify cell state embedded
        assert isinstance(state.cell_state, SpatialCellMaritimeState)

    def test_13_canonical_cell_parameters(self):
        """Verify every spatial cell / route node strictly stores all 13 canonical parameters."""
        cell = maritime_state_manager.get_spatial_cell_state(lat=-63.0, lon=-58.0)
        assert isinstance(cell, SpatialCellMaritimeState)

        # 1. timestamp
        assert isinstance(cell.timestamp, datetime)
        # 2. SIC (Sea Ice Concentration, 0-100%)
        assert 0.0 <= cell.sic <= 100.0
        # 3. ice risk (0.0 - 1.0)
        assert 0.0 <= cell.ice_risk <= 1.0
        # 4. iceberg risk (0.0 - 1.0)
        assert 0.0 <= cell.iceberg_risk <= 1.0
        # 5. wind
        assert isinstance(cell.wind, CellWindState)
        assert cell.wind.speed_knots >= 0.0
        assert 0.0 <= cell.wind.direction_deg <= 360.0
        # 6. wave
        assert isinstance(cell.wave, CellWaveState)
        assert cell.wave.height_m >= 0.0
        assert cell.wave.period_s >= 0.0
        # 7. current
        assert isinstance(cell.current, CellCurrentState)
        assert cell.current.speed_knots >= 0.0
        assert 0.0 <= cell.current.direction_deg <= 360.0
        # 8. SST (Sea Surface Temperature, °C)
        assert -5.0 <= cell.sst <= 35.0
        # 9. air temperature (°C)
        assert -80.0 <= cell.air_temperature <= 40.0
        # 10. pressure (hPa)
        assert 800.0 <= cell.pressure <= 1100.0
        # 11. depth (meters)
        assert cell.depth >= 0.0
        # 12. land status
        assert cell.land_status in ("LAND", "WATER", "ICE_SHELF", "SHALLOW_WATER")
        assert isinstance(cell.is_land, bool)
        # 13. data confidence
        assert 0.0 <= cell.data_confidence <= 1.0

    def test_non_simultaneous_timestamps_never_falsified(self):
        """Verify distinct timestamps across sources; do NOT pretend they were measured simultaneously."""
        state = maritime_state_manager.get_current_state(lat=-64.0, lon=-60.0)
        timestamps = state.cell_state.source_timestamps

        assert len(timestamps) >= 6
        assert "sea_ice" in timestamps
        assert "weather" in timestamps
        assert "bathymetry" in timestamps
        assert "ocean" in timestamps

        # Bathymetry (static relief) and Weather (6-hourly reanalysis/forecast)
        # MUST have completely different timestamps
        bathy_ts = timestamps["bathymetry"]
        wx_ts = timestamps["weather"]
        sic_ts = timestamps["sea_ice"]

        assert bathy_ts != wx_ts, "Static bathymetry and weather must NOT have identical timestamps"
        assert bathy_ts != sic_ts, "Static bathymetry and sea ice must NOT have identical timestamps"

    def test_layer_data_age_and_freshness_calculation(self):
        """Verify elapsed data_age (hours & seconds) and categorical freshness classification."""
        state = maritime_state_manager.get_current_state(lat=-64.0, lon=-60.0)
        audits = state.layer_audits

        for layer_name, audit in audits.items():
            assert isinstance(audit, LayerTemporalAudit)
            assert audit.data_age_seconds >= 0.0
            assert audit.data_age_hours >= 0.0
            assert 0.0 <= audit.confidence <= 1.0
            assert audit.freshness in (
                LayerFreshness.FRESH,
                LayerFreshness.ACCEPTABLE,
                LayerFreshness.STALE,
                LayerFreshness.EXPIRED,
                LayerFreshness.UNAVAILABLE,
            )
            assert isinstance(audit.is_stale, bool)

    def test_unified_environmental_confidence_bounds(self):
        """Verify unified environmental confidence score and data freshness index."""
        state = maritime_state_manager.get_current_state(lat=-64.0, lon=-60.0)
        assert 0.0 <= state.unified_environmental_confidence <= 1.0
        assert 0.0 <= state.data_freshness_index <= 1.0
        # Cell confidence must equal top-level unified confidence
        assert state.cell_state.data_confidence == state.unified_environmental_confidence

    def test_critical_staleness_flagging_and_no_silent_continuation(self):
        """Verify that when critical data becomes stale, it is FLAGGED and operation is degraded."""
        # Create a mock aged metadata for sea ice
        now = datetime.now(timezone.utc)
        aged_time = now - timedelta(hours=36.0)  # > 24.0h threshold
        
        # Save original fetch_current
        original_fetch = maritime_state_manager.sea_ice_provider.fetch_current

        try:
            def aged_fetch(lat, lon):
                obs = original_fetch(lat, lon)
                obs.metadata.timestamp = aged_time
                obs.metadata.valid_until = aged_time + timedelta(hours=24.0)
                obs.metadata.is_stale = True
                return obs

            maritime_state_manager.sea_ice_provider.fetch_current = aged_fetch

            state = maritime_state_manager.get_current_state(lat=-63.0, lon=-58.0)

            # Strict assertions: Must NOT silently continue as live!
            assert state.has_stale_data is True
            assert state.critical_data_stale is True
            assert "sea_ice" in state.stale_layers
            assert state.degraded_operation is True
            assert state.operational_advisory == "DEGRADED_OPERATION_CRITICAL_DATA_STALE"
            assert len(state.staleness_warnings) > 0

            # Warning must explicitly mention sea ice and data age
            warning_text = " ".join(state.staleness_warnings)
            assert "SEA_ICE" in warning_text or "sea_ice" in warning_text
            assert "old" in warning_text.lower() or "exceeds" in warning_text.lower()

            # Confidence must be penalized compared to nominal
            assert state.layer_audits["sea_ice"].freshness in (LayerFreshness.STALE, LayerFreshness.EXPIRED)
            assert state.unified_environmental_confidence < 0.85
        finally:
            # Restore original provider method
            maritime_state_manager.sea_ice_provider.fetch_current = original_fetch

    def test_vessel_state_influence_on_under_keel_clearance(self):
        """Verify vessel draft directly modulates under-keel clearance calculation."""
        v_shallow = VesselState(draft_m=5.0)
        v_deep = VesselState(draft_m=12.0)

        cell_shallow = maritime_state_manager.get_spatial_cell_state(lat=-63.0, lon=-58.0, vessel_state=v_shallow)
        cell_deep = maritime_state_manager.get_spatial_cell_state(lat=-63.0, lon=-58.0, vessel_state=v_deep)

        assert cell_shallow.under_keel_clearance_m > cell_deep.under_keel_clearance_m
        assert pytest.approx(cell_shallow.under_keel_clearance_m - cell_deep.under_keel_clearance_m, abs=0.1) == 7.0

    def test_coastline_proximity_diagnostics(self):
        """Verify coastline distance and maritime proximity zones."""
        # Deep open Drake Passage
        state_open = maritime_state_manager.get_current_state(lat=-58.0, lon=-60.0)
        assert state_open.coastline.is_land is False
        assert state_open.coastline.distance_to_coast_km > 100.0

        # Continental Peninsula land
        state_land = maritime_state_manager.get_current_state(lat=-64.0, lon=-60.0)
        assert state_land.coastline.is_land is True
        assert state_land.coastline.coastal_zone == "INLAND"

    def test_route_node_fusion_multi_waypoint(self):
        """Verify fusion engine evaluates discrete environmental vectors along a route corridor."""
        waypoints = [
            (-60.0, -60.0),
            (-61.5, -59.5),
            (-63.0, -58.0),
        ]
        v_state = VesselState(speed_knots=12.0, draft_m=8.5)
        fused_nodes = maritime_state_manager.fuse_route_nodes(waypoints, vessel_state=v_state)

        assert len(fused_nodes) == 3
        for idx, node in enumerate(fused_nodes):
            assert isinstance(node, SpatialCellMaritimeState)
            assert node.latitude == waypoints[idx][0]
            assert node.longitude == waypoints[idx][1]
            assert node.under_keel_clearance_m == pytest.approx(node.depth - 8.5, abs=0.1)
            assert 0.0 <= node.data_confidence <= 1.0


class TestFusionAPIEndpoints:
    """Verify REST API endpoints for Phase 8 real-time fusion."""

    def test_api_realtime_state_enhanced(self):
        res = client.get("/api/realtime/state?lat=-63.0&lon=-58.0&vessel_heading=180&vessel_draft=8.5")
        assert res.status_code == 200
        data = res.json()
        assert "cell_state" in data
        assert "layer_audits" in data
        assert "unified_environmental_confidence" in data
        assert "data_freshness_index" in data
        assert "coastline" in data

        # Check the 13 canonical parameters in cell_state
        cs = data["cell_state"]
        for param in ["timestamp", "sic", "ice_risk", "iceberg_risk", "wind", "wave", "current",
                      "sst", "air_temperature", "pressure", "depth", "land_status", "data_confidence"]:
            assert param in cs, f"Missing canonical parameter {param} in API cell_state"

    def test_api_fuse_cell_endpoint(self):
        payload = {
            "latitude": -63.0,
            "longitude": -58.0,
            "speed_knots": 15.0,
            "heading_deg": 90.0,
            "draft_m": 8.0,
            "polar_class": "PC3",
        }
        res = client.post("/api/realtime/state/fuse-cell", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["latitude"] == -63.0
        assert data["longitude"] == -58.0
        assert "sic" in data
        assert "wind" in data
        assert "wave" in data
        assert "current" in data
        assert "depth" in data

    def test_api_fuse_route_endpoint(self):
        payload = {
            "waypoints": [
                [-60.0, -60.0],
                [-62.0, -59.0],
            ],
            "speed_knots": 12.0,
            "heading_deg": 180.0,
            "draft_m": 8.0,
            "polar_class": "PC5",
        }
        res = client.post("/api/realtime/state/fuse-route", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["node_count"] == 2
        assert "average_confidence" in data
        assert "has_stale_data" in data
        assert "critical_data_stale" in data
        assert len(data["nodes"]) == 2

    def test_api_temporal_audit_endpoint(self):
        res = client.get("/api/realtime/state/temporal-audit?lat=-63.0&lon=-58.0")
        assert res.status_code == 200
        data = res.json()
        assert "layer_audits" in data
        assert "sea_ice" in data["layer_audits"]
        assert "weather" in data["layer_audits"]
        assert "bathymetry" in data["layer_audits"]
        assert "unified_environmental_confidence" in data
        assert "data_freshness_index" in data
