"""Download real NOAA/NSIDC CDR V4 Southern Hemisphere Sea Ice Concentration Series.

Fetches 18 months of monthly passive microwave satellite CDR data from CoastWatch ERDDAP.
Saves to data/raw/sea_ice/real_cdr_series_18m.nc.
"""
import os
import urllib.request
import logging
from pathlib import Path

logger = logging.getLogger("polarnav.downloader")
logging.basicConfig(level=logging.INFO)

TARGET_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "sea_ice"
TARGET_DIR.mkdir(parents=True, exist_ok=True)
TARGET_FILE = TARGET_DIR / "real_cdr_series_18m.nc"

# CoastWatch ERDDAP URL: 18 months (Jan 2023 - Jun 2024), 50km resolution grid
ERDDAP_BASE = (
    os.environ.get("NOAA_COASTWATCH_ERDDAP_BASE_URL")
    or os.environ.get("NOAA_ERDDAP_BASE_URL", "https://coastwatch.pfeg.noaa.gov/erddap")
).rstrip("/")
ERDDAP_URL = (
    f"{ERDDAP_BASE}/griddap/nsidcG02202v4shmday.nc?"
    "cdr_seaice_conc_monthly[(2023-01-01T00:00:00Z):1:(2024-06-01T00:00:00Z)]"
    "[(4350000.0):2:(-3950000.0)][(-3950000.0):2:(3950000.0)]"
)


def download_cdr_series(force=False):
    """Download the 18-month NOAA CDR dataset."""
    if TARGET_FILE.exists() and not force:
        logger.info(f"Dataset already exists at {TARGET_FILE} ({TARGET_FILE.stat().st_size} bytes)")
        return TARGET_FILE

    logger.info(f"Downloading 18 months of NOAA/NSIDC CDR sea ice from CoastWatch ERDDAP...")
    req = urllib.request.Request(ERDDAP_URL, headers={"User-Agent": "PolarNav-Antarctic-AI/1.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        content = resp.read()

    with open(TARGET_FILE, "wb") as f:
        f.write(content)

    logger.info(f"Successfully saved {len(content)} bytes to {TARGET_FILE}")
    return TARGET_FILE


if __name__ == "__main__":
    download_cdr_series()
