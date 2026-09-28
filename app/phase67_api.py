"""Phase 6-7 API integration.

Bridges the antarctic-ai optimization engine with the SIH26059 backend.
Converts JSON grids to xarray for the optimization engine.
"""
import sys
import json
import time
import logging
from pathlib import Path

import numpy as np
import xarray as xr

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
for _p in [str(BACKEND_DIR), str(BACKEND_DIR / "src")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.optimization.route_optimizer import (
    generate_candidate_routes, generate_baseline_route, compare_routes
)
from src.optimization.decision_engine import (
    NavigationRequest, execute_navigation_decision, explain_route
)
from src.optimization.cost_function import DEFAULT_WEIGHTS

logger = logging.getLogger("polarnav.phase67_api")

import threading

ANTARCTIC_DATA = BACKEND_DIR / "data" / "processed" / "verification"

_CACHE_LOCK = threading.Lock()
_CACHED_RISK_DS = None
_RISK_MTIME = 0
_CACHED_SIC_DS = None
_SIC_MTIME = 0
_CACHED_ICEBERGS = None
_ICEBERGS_MTIME = 0
_CACHED_VESSELS = None
_VESSELS_MTIME = 0
_CACHED_ROUTES_DATA = None
_ROUTES_MTIME = 0


def _load(fn):
    fp = ANTARCTIC_DATA / fn
    if fp.exists():
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    return None


def _json_to_xarray_risk():
    """Convert phase4_risk.json to xr.Dataset with thread-safe process caching."""
    global _CACHED_RISK_DS, _RISK_MTIME
    fp = ANTARCTIC_DATA / "phase4_risk.json"
    mtime = fp.stat().st_mtime if fp.exists() else 0

    if _CACHED_RISK_DS is not None and mtime == _RISK_MTIME:
        return _CACHED_RISK_DS

    with _CACHE_LOCK:
        if _CACHED_RISK_DS is not None and mtime == _RISK_MTIME:
            return _CACHED_RISK_DS

        t0 = time.perf_counter()
        data = _load("phase4_risk.json")
        if not data:
            return None
        lats = np.array(data["lats"])
        lons = np.array(data["lons"])
        grid = np.zeros((len(lats), len(lons)))
        for pt in data["risk_points"]:
            li = int(np.argmin(np.abs(lats - pt[0])))
            lo = int(np.argmin(np.abs(lons - pt[1])))
            grid[li, lo] = float(pt[2])
        ds = xr.Dataset(
            {"total_risk": (["lat", "lon"], grid)},
            coords={"lat": lats, "lon": lons}
        )
        _CACHED_RISK_DS = ds
        _RISK_MTIME = mtime
        logger.info(f"DATA_LOAD: risk={(time.perf_counter() - t0) * 1000:.1f}ms")
        return ds


def _json_to_xarray_sic():
    """Convert phase2_sic.json to xr.Dataset with thread-safe process caching."""
    global _CACHED_SIC_DS, _SIC_MTIME
    fp = ANTARCTIC_DATA / "phase2_sic.json"
    mtime = fp.stat().st_mtime if fp.exists() else 0

    if _CACHED_SIC_DS is not None and mtime == _SIC_MTIME:
        return _CACHED_SIC_DS

    with _CACHE_LOCK:
        if _CACHED_SIC_DS is not None and mtime == _SIC_MTIME:
            return _CACHED_SIC_DS

        t0 = time.perf_counter()
        data = _load("phase2_sic.json")
        if not data:
            return None
        lats = np.array(data["lats"])
        lons = np.array(data["lons"])
        grid = np.zeros((len(lats), len(lons)))
        for pt in data["current_points"]:
            li = int(np.argmin(np.abs(lats - pt[0])))
            lo = int(np.argmin(np.abs(lons - pt[1])))
            grid[li, lo] = float(pt[2]) if pt[2] else 0.0
        ds = xr.Dataset(
            {"sic_current": (["lat", "lon"], grid)},
            coords={"lat": lats, "lon": lons}
        )
        _CACHED_SIC_DS = ds
        _SIC_MTIME = mtime
        logger.info(f"DATA_LOAD: sic={(time.perf_counter() - t0) * 1000:.1f}ms")
        return ds


def _load_icebergs_opt():
    """Load icebergs in optimization format with thread-safe process caching."""
    global _CACHED_ICEBERGS, _ICEBERGS_MTIME
    fp = ANTARCTIC_DATA / "phase3_icebergs.json"
    mtime = fp.stat().st_mtime if fp.exists() else 0

    if _CACHED_ICEBERGS is not None and mtime == _ICEBERGS_MTIME:
        return _CACHED_ICEBERGS

    with _CACHE_LOCK:
        if _CACHED_ICEBERGS is not None and mtime == _ICEBERGS_MTIME:
            return _CACHED_ICEBERGS

        t0 = time.perf_counter()
        raw = _load("phase3_icebergs.json")
        if not raw or "icebergs" not in raw:
            return []
        ibs = []
        for ib in raw["icebergs"]:
            ibs.append({
                "id": ib.get("id", ""),
                "latitude": ib.get("current_lat", 0),
                "longitude": ib.get("current_lon", 0),
                "risk": ib.get("risk_level", "LOW"),
                "predictedTrajectory": ib.get("predicted_trajectory", []),
            })
        _CACHED_ICEBERGS = ibs
        _ICEBERGS_MTIME = mtime
        logger.info(f"DATA_LOAD: icebergs={(time.perf_counter() - t0) * 1000:.1f}ms")
        return ibs


def _load_vessel(vessel_id=None):
    """Load vessel data for optimization with thread-safe process caching."""
    global _CACHED_VESSELS, _VESSELS_MTIME
    fp = ANTARCTIC_DATA / "all_vessels.json"
    mtime = fp.stat().st_mtime if fp.exists() else 0

    if _CACHED_VESSELS is None or mtime != _VESSELS_MTIME:
        with _CACHE_LOCK:
            if _CACHED_VESSELS is None or mtime != _VESSELS_MTIME:
                data = _load("all_vessels.json")
                _CACHED_VESSELS = data.get("vessels", []) if data else []
                _VESSELS_MTIME = mtime

    if not _CACHED_VESSELS:
        return None
    for v in _CACHED_VESSELS:
        if vessel_id and v.get("id") == vessel_id:
            return v
    return _CACHED_VESSELS[0]


def run_optimization(
    vessel_id=None,
    start_lat=None, start_lon=None,
    dest_lat=None, dest_lon=None,
    cruising_speed_kn=12.0,
    risk_tolerance=0.7,
    optimization_weights=None,
):
    """Run Phase 6-7 navigation optimization."""
    t0 = time.time()

    # Load datasets
    risk_ds = _json_to_xarray_risk()
    if risk_ds is None:
        return {"status": "ERROR", "errors": ["Phase 4 risk grid unavailable"]}

    sic_ds = _json_to_xarray_sic()
    icebergs = _load_icebergs_opt()

    # Load vessel
    vessel_record = _load_vessel(vessel_id)
    if not vessel_record:
        return {"status": "ERROR", "errors": ["No vessel data"]}

    cp = vessel_record.get("current_position", {})
    s_lat = start_lat if start_lat is not None else cp.get("lat", -66.3)
    s_lon = start_lon if start_lon is not None else cp.get("lon", 110.0)

    # Destination
    global _CACHED_ROUTES_DATA, _ROUTES_MTIME
    fp_r = ANTARCTIC_DATA / "phase5_routes.json"
    mtime_r = fp_r.stat().st_mtime if fp_r.exists() else 0
    if _CACHED_ROUTES_DATA is None or mtime_r != _ROUTES_MTIME:
        with _CACHE_LOCK:
            if _CACHED_ROUTES_DATA is None or mtime_r != _ROUTES_MTIME:
                _CACHED_ROUTES_DATA = _load("phase5_routes.json")
                _ROUTES_MTIME = mtime_r

    routes_data = _CACHED_ROUTES_DATA
    if routes_data and "vessels" in routes_data and routes_data["vessels"]:
        d_lat = dest_lat if dest_lat is not None else routes_data["vessels"][0]["destination"]["lat"]
        d_lon = dest_lon if dest_lon is not None else routes_data["vessels"][0]["destination"]["lon"]
    else:
        d_lat = dest_lat or -60.34
        d_lon = dest_lon or 118.98

    # Build request
    request = NavigationRequest(
        vessel_id=vessel_record.get("id", vessel_id or "unknown"),
        vessel_name=vessel_record.get("name", "Unknown"),
        vessel_type=vessel_record.get("type", "Research Vessel"),
        start_lat=s_lat, start_lon=s_lon,
        dest_lat=d_lat, dest_lon=d_lon,
        cruising_speed_kn=cruising_speed_kn,
        risk_tolerance=risk_tolerance,
        optimization_weights=optimization_weights,
    )

    # Execute
    result = execute_navigation_decision(request, risk_ds, sic_ds, icebergs)
    result["computation_time_ms"] = round((time.time() - t0) * 1000, 1)
    return result
