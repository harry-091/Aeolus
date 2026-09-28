"""NASA Earthdata Downloader for PolarNav.

Authenticates against NASA Earthdata Login (URS) using user credentials
and downloads authentic Antarctic Sea Ice Concentration (NSIDC DAAC) datasets.

Datasets:
- NSIDC-0051: Nimbus-7 SMMR and DMSP SSM/I-SSMIS Daily Polar Gridded Sea Ice Concentrations
- NSIDC-0081: Near-Real-Time DMSP SSMIS Daily Polar Gridded Sea Ice Concentrations (NRT)
"""
import os
import sys
import logging
from pathlib import Path
import dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("polarnav.nasa_earthdata")

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
dotenv.load_dotenv(ROOT_DIR / ".env")
dotenv.load_dotenv(ROOT_DIR / "backend" / ".env")

DEST_DIR = ROOT_DIR / "backend" / "data" / "raw" / "sea_ice"
DEST_DIR.mkdir(parents=True, exist_ok=True)


def download_nsidc_sea_ice():
    import earthaccess

    username = os.environ.get("EARTHDATA_USERNAME") or os.environ.get("NASA_EARTHDATA_USERNAME")
    password = os.environ.get("EARTHDATA_PASSWORD") or os.environ.get("NASA_EARTHDATA_PASSWORD")

    if not username or not password:
        logger.error("NASA Earthdata credentials missing in .env (EARTHDATA_USERNAME, EARTHDATA_PASSWORD)")
        sys.exit(1)

    # Ensure environment variables are set for earthaccess
    os.environ["EARTHDATA_USERNAME"] = username
    os.environ["EARTHDATA_PASSWORD"] = password

    logger.info(f"Authenticating with NASA Earthdata as user: {username}...")
    auth = earthaccess.login(strategy="environment", persist=True)
    if not auth.authenticated:
        logger.error("Failed to authenticate with NASA Earthdata.")
        sys.exit(1)
    logger.info("Successfully authenticated with NASA Earthdata Login (URS).")

    # Search for Antarctic (South) Sea Ice granules
    logger.info("Searching NASA CMR for Antarctic Sea Ice (NSIDC-0051 / NSIDC-0081)...")
    granules = earthaccess.search_data(
        short_name="NSIDC-0051",
        granule_name="*S25km*",
        temporal=("2024-01-01", "2024-01-05"),
        count=1
    )

    if not granules:
        logger.warning("No NSIDC-0051 Southern hemisphere granules found, searching NRT NSIDC-0081...")
        granules = earthaccess.search_data(
            short_name="NSIDC-0081",
            granule_name="*S25km*",
            count=1
        )

    if not granules:
        logger.error("No granules found matching Antarctic search criteria.")
        sys.exit(1)

    granule_name = granules[0]["umm"]["GranuleUR"]
    logger.info(f"Target Antarctic granule identified: {granule_name}")
    logger.info(f"Downloading granule to {DEST_DIR}...")

    downloaded = earthaccess.download(granules, str(DEST_DIR))
    logger.info(f"Successfully downloaded: {downloaded}")
    return downloaded


if __name__ == "__main__":
    download_nsidc_sea_ice()
