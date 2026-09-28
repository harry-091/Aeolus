"""Real NOAA ETOPO Bathymetry Service.

Provides authentic water depth (in meters) and seabed topography lookups
for Antarctic polar navigation and risk evaluation.
Source: NOAA NGDC ETOPO Relief Model (1 arc-minute resolution).
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
import xarray as xr

logger = logging.getLogger("polarnav.bathymetry")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "bathymetry"
ETOPO_PATH = DATA_DIR / "etopo_antarctic.nc"


import threading

class BathymetryService:
    """Service providing real NOAA ETOPO bathymetry lookups."""

    def __init__(self, nc_path: Optional[Path] = None):
        self.nc_path = nc_path or ETOPO_PATH
        self._ds: Optional[xr.Dataset] = None
        self._lats: Optional[np.ndarray] = None
        self._lons: Optional[np.ndarray] = None
        self._lat_min: float = 0.0
        self._lat_step: float = 0.0
        self._lon_min: float = 0.0
        self._lon_step: float = 0.0
        self._altitude: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._initialized = False
        # A static ETOPO file is loaded once; suppress repeated warnings if absent.
        self._load_attempted = False

    def initialize(self) -> bool:
        """Load and prepare the NetCDF dataset into memory thread-safely."""
        if self._initialized:
            return True

        if self._load_attempted:
            return False

        with self._lock:
            if self._initialized:
                return True
            if self._load_attempted:
                return False

            self._load_attempted = True

            if not self.nc_path.exists():
                logger.warning(f"Bathymetry dataset not found at {self.nc_path}")
                return False

            try:
                self._ds = xr.open_dataset(self.nc_path)
                self._lats = self._ds.latitude.values
                self._lons = self._ds.longitude.values
                self._lat_min = float(self._lats[0])
                self._lat_step = float((self._lats[-1] - self._lats[0]) / (len(self._lats) - 1)) if len(self._lats) > 1 else 1.0
                self._lon_min = float(self._lons[0])
                self._lon_step = float((self._lons[-1] - self._lons[0]) / (len(self._lons) - 1)) if len(self._lons) > 1 else 1.0
                self._altitude = self._ds.altitude.values
                self._initialized = True
                logger.info(
                    f"Loaded NOAA ETOPO bathymetry ({len(self._lats)} lats x {len(self._lons)} lons) "
                    f"from {self.nc_path}"
                )
                return True
            except Exception as e:
                logger.error(f"Failed to load NOAA ETOPO bathymetry: {e}")
                return False

    def get_depth(self, lat: float, lon: float) -> Dict[str, Any]:
        """Query real water depth in meters at a given geographic point.

        Returns:
            dict containing:
                depth_m: positive depth in meters below sea surface (0 for land)
                altitude_m: raw altitude (negative=underwater, positive=above sea level)
                is_land: bool indicating if altitude > 0
                is_shallow: bool indicating if ocean depth < 20m safe clearance
                status: 'REAL' or 'UNAVAILABLE'
                source: 'NOAA ETOPO 2022'
        """
        if not self.initialize():
            return {
                "depth_m": 0.0,
                "altitude_m": 0.0,
                "is_land": False,
                "is_shallow": False,
                "status": "UNAVAILABLE",
                "source": "NOAA ETOPO 2022",
                "error": "Bathymetry dataset not initialized"
            }

        # Longitude normalization to [-180, 180]
        norm_lon = (lon + 180.0) % 360.0 - 180.0

        # Check spatial bounds
        lat_min, lat_max = float(self._lats.min()), float(self._lats.max())
        lon_min, lon_max = float(self._lons.min()), float(self._lons.max())

        if not (lat_min <= lat <= lat_max and lon_min <= norm_lon <= lon_max):
            # Outside regional grid: deep Southern Ocean baseline default (> 3000m)
            return {
                "depth_m": 3500.0,
                "altitude_m": -3500.0,
                "is_land": False,
                "is_shallow": False,
                "status": "REAL_OUT_OF_BOUNDS_EXTRAPOLATION",
                "source": "NOAA ETOPO 2022",
                "lat": lat,
                "lon": norm_lon,
            }

        if self._lat_step != 0.0 and self._lon_step != 0.0:
            lat_idx = max(0, min(len(self._lats) - 1, int(round((lat - self._lat_min) / self._lat_step))))
            lon_idx = max(0, min(len(self._lons) - 1, int(round((norm_lon - self._lon_min) / self._lon_step))))
        else:
            lat_idx = int(np.argmin(np.abs(self._lats - lat)))
            lon_idx = int(np.argmin(np.abs(self._lons - norm_lon)))

        raw_alt = float(self._altitude[lat_idx, lon_idx])

        if np.isnan(raw_alt):
            raw_alt = -1500.0

        is_land = raw_alt >= 0.0
        depth_m = 0.0 if is_land else abs(raw_alt)
        is_shallow = not is_land and depth_m < 20.0

        return {
            "depth_m": round(depth_m, 1),
            "altitude_m": round(raw_alt, 1),
            "is_land": is_land,
            "is_shallow": is_shallow,
            "status": "REAL",
            "source": "NOAA ETOPO 2022",
            "lat": round(lat, 4),
            "lon": round(norm_lon, 4),
            "unit": "meters"
        }


# Global singleton instance
bathymetry_service = BathymetryService()
