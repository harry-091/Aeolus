"""PolarNav // Real Satellite Monitoring Data Models & Schemas.

Defines the SatelliteScene schema, freshness classification (LIVE, RECENT, STALE, UNAVAILABLE),
product types, and remote sensing telemetry containers.
"""

from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class SatelliteFreshness(str, Enum):
    """Rigorous satellite scene freshness classification.
    
    RULES:
    - LIVE: Acquired within the last 6 hours.
    - RECENT: Acquired between 6 and 48 hours ago.
    - STALE: Older than 48 hours. Historical reference only.
    - UNAVAILABLE: Outside active sensor swath or feed offline.
    - Never imply that a scene represents conditions after its acquisition time.
    """
    LIVE = "LIVE"                  # < 6 hours old
    RECENT = "RECENT"              # 6h - 48h old
    STALE = "STALE"                # > 48h old
    UNAVAILABLE = "UNAVAILABLE"    # Outside footprint or sensor unreachable


class SatelliteProductType(str, Enum):
    """Standard ESA Copernicus & NASA remote sensing product types."""
    SENTINEL_1_GRD_EW = "S1_GRD_EW"    # Extra Wide Swath (400km, 20m/40m res)
    SENTINEL_1_GRD_IW = "S1_GRD_IW"    # Interferometric Wide (250km, 10m res)
    SENTINEL_2_MSI_L2A = "S2_MSI_L2A"  # Multi-Spectral Instrument Bottom-of-Atmosphere
    SIC_PASSIVE_MICROWAVE = "SIC_PASSIVE_MICROWAVE" # AMSR2 / SSMIS 12.5km grid
    ALTIMETRY_CRYOSAT2 = "CRYOSAT2_SIRAL"           # Radar altimetry sea ice thickness


class SatelliteScene(BaseModel):
    """Production-grade remote sensing scene metadata container.
    
    Contains spatial geometry, acquisition timestamps, sensor telemetry,
    and operational usability flags.
    """
    scene_id: str
    source: str                        # e.g., "ESA Copernicus Sentinel-1A / Microsoft Planetary Computer STAC"
    acquisition_time: datetime         # Exact UTC timestamp of satellite pass
    geometry: Dict[str, Any]           # GeoJSON Polygon of sensor swath footprint
    bbox: List[float]                  # [lon_min, lat_min, lon_max, lat_max]
    product_type: str                  # e.g. "S1_GRD_EW", "S1_GRD_IW", "S2_MSI_L2A"
    resolution_meters: float           # Spatial resolution in meters (e.g. 10.0, 40.0)
    processing_status: str             # "PROCESSED", "RAW_ARCHIVED", "CATALOG_INDEXED"
    quality: str                       # "NOMINAL", "HIGH", "DEGRADED_CLOUD_COVER", "LOW_BACKSCATTER"
    availability: SatelliteFreshness   # LIVE, RECENT, STALE, UNAVAILABLE
    
    # Sentinel-1 SAR Specific Fields
    orbit_direction: Optional[str] = None       # "ascending" or "descending"
    relative_orbit: Optional[int] = None        # Track / relative orbit number
    polarizations: List[str] = Field(default_factory=lambda: ["HH"]) # e.g. ["HH"], ["HH", "HV"]
    cloud_independent: bool = True              # SAR is all-weather / cloud-penetrating
    
    # Sentinel-2 Optical Specific Fields
    cloud_cover_pct: Optional[float] = None     # Cloud cover fraction [0.0 - 100.0%]
    is_optical_usable: bool = True              # False if polar night or cloud cover > 20%
    solar_elevation_deg: Optional[float] = None # Solar elevation angle above horizon
    
    # Asset Links & Diagnostics
    assets: List[str] = Field(default_factory=list)
    tile_url: Optional[str] = None              # Download or WMS/TMS preview URL
    file_size_mb: Optional[float] = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def evaluate_freshness(self, ref_time: Optional[datetime] = None) -> SatelliteFreshness:
        """Dynamically grade scene freshness against current UTC wall-clock time."""
        now = ref_time or datetime.now(timezone.utc)
        acq = self.acquisition_time
        if acq.tzinfo is None:
            acq = acq.replace(tzinfo=timezone.utc)
        
        age_hours = (now - acq).total_seconds() / 3600.0
        if age_hours < 0:
            # Future timestamp guard
            self.availability = SatelliteFreshness.UNAVAILABLE
        elif age_hours <= 6.0:
            self.availability = SatelliteFreshness.LIVE
        elif age_hours <= 48.0:
            self.availability = SatelliteFreshness.RECENT
        else:
            self.availability = SatelliteFreshness.STALE
        return self.availability

    def to_summary_dict(self) -> Dict[str, Any]:
        """Compact summary representation for UI map overlays."""
        return {
            "scene_id": self.scene_id,
            "source": self.source,
            "acquisition_time": self.acquisition_time.isoformat(),
            "product_type": self.product_type,
            "resolution_meters": self.resolution_meters,
            "availability": self.availability.value,
            "cloud_independent": self.cloud_independent,
            "cloud_cover_pct": self.cloud_cover_pct,
            "is_optical_usable": self.is_optical_usable,
            "polarizations": self.polarizations,
            "orbit_direction": self.orbit_direction,
            "bbox": self.bbox,
        }
