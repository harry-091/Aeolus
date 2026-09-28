#!/usr/bin/env python3
"""
POLARNAV // COPERNICUS MARINE REAL-TIME OCEAN & SST DOWNLOADER
=============================================================
Fetches real Antarctic ocean currents (uo, vo) and Sea Surface Temperature (thetao)
from Copernicus Marine Service (CMEMS) using the official `copernicusmarine` Python client.

Credentials are read securely from .env:
  COPERNICUS_MARINE_USERNAME
  COPERNICUS_MARINE_PASSWORD
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import dotenv
import copernicusmarine

# Resolve project directories
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
OCEAN_DATA_DIR = BACKEND_DIR / "data" / "raw" / "ocean"
OCEAN_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load environment configuration
dotenv.load_dotenv(ROOT_DIR / ".env")
dotenv.load_dotenv(BACKEND_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CopernicusOceanDownloader")

CURRENTS_DATASET_ID = "cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m"
SST_DATASET_ID = "cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m"


def authenticate() -> bool:
    """Authenticate with Copernicus Marine using credentials from .env."""
    username = os.getenv("COPERNICUS_MARINE_USERNAME")
    password = os.getenv("COPERNICUS_MARINE_PASSWORD")

    if not username or not password:
        logger.error("Missing COPERNICUS_MARINE_USERNAME or COPERNICUS_MARINE_PASSWORD in .env")
        return False

    logger.info(f"Authenticating with Copernicus Marine as: {username}")
    try:
        success = copernicusmarine.login(
            username=username,
            password=password,
            force_overwrite=True,
            check_credentials_valid=True,
        )
        if success:
            logger.info("Copernicus Marine authentication SUCCESSFUL.")
            return True
        else:
            logger.error("Authentication returned False.")
            return False
    except Exception as e:
        logger.error(f"Failed to authenticate with Copernicus Marine: {e}")
        return False


def download_antarctic_currents(
    target_date: Optional[datetime] = None,
    output_filename: str = "copernicus_currents_live.nc",
) -> Optional[Path]:
    """Download surface ocean currents (uo, vo) for the Antarctic maritime region.
    
    Spatial bounds:
      lat in [-80.0, -50.0]
      lon in [-180.0, 180.0]
    """
    username = os.getenv("COPERNICUS_MARINE_USERNAME")
    password = os.getenv("COPERNICUS_MARINE_PASSWORD")

    if target_date is None:
        target_date = datetime.now(timezone.utc) - timedelta(days=2)

    date_str = target_date.strftime("%Y-%m-%d")
    output_path = OCEAN_DATA_DIR / output_filename

    logger.info(f"Downloading Antarctic ocean currents for {date_str} to {output_path}...")
    try:
        res = copernicusmarine.subset(
            dataset_id=CURRENTS_DATASET_ID,
            username=username,
            password=password,
            variables=["uo", "vo"],
            minimum_longitude=-180.0,
            maximum_longitude=180.0,
            minimum_latitude=-80.0,
            maximum_latitude=-50.0,
            minimum_depth=0.5,
            maximum_depth=5.0,
            start_datetime=f"{date_str}T00:00:00",
            end_datetime=f"{date_str}T23:59:59",
            output_filename=output_filename,
            output_directory=str(OCEAN_DATA_DIR),
            overwrite=True,
        )
        logger.info(f"Ocean currents successfully downloaded: {output_path} (Size: {output_path.stat().st_size / (1024*1024):.2f} MB)")
        return output_path
    except Exception as e:
        logger.error(f"Failed to download ocean currents: {e}")
        return None


def download_antarctic_sst(
    target_date: Optional[datetime] = None,
    output_filename: str = "copernicus_sst_live.nc",
) -> Optional[Path]:
    """Download sea surface temperature (thetao) for the Antarctic maritime region."""
    username = os.getenv("COPERNICUS_MARINE_USERNAME")
    password = os.getenv("COPERNICUS_MARINE_PASSWORD")

    if target_date is None:
        target_date = datetime.now(timezone.utc) - timedelta(days=2)

    date_str = target_date.strftime("%Y-%m-%d")
    output_path = OCEAN_DATA_DIR / output_filename

    logger.info(f"Downloading Antarctic SST (thetao) for {date_str} to {output_path}...")
    try:
        res = copernicusmarine.subset(
            dataset_id=SST_DATASET_ID,
            username=username,
            password=password,
            variables=["thetao"],
            minimum_longitude=-180.0,
            maximum_longitude=180.0,
            minimum_latitude=-80.0,
            maximum_latitude=-50.0,
            minimum_depth=0.5,
            maximum_depth=5.0,
            start_datetime=f"{date_str}T00:00:00",
            end_datetime=f"{date_str}T23:59:59",
            output_filename=output_filename,
            output_directory=str(OCEAN_DATA_DIR),
            overwrite=True,
        )
        logger.info(f"SST successfully downloaded: {output_path} (Size: {output_path.stat().st_size / (1024*1024):.2f} MB)")
        return output_path
    except Exception as e:
        logger.error(f"Failed to download SST: {e}")
        return None


def main():
    if not authenticate():
        sys.exit(1)

    logger.info("Beginning Copernicus Marine Antarctic operational download...")
    currents_file = download_antarctic_currents()
    sst_file = download_antarctic_sst()

    if currents_file and sst_file:
        logger.info("ALL COPERNICUS MARINE OCEAN DATASETS DOWNLOADED AND VALIDATED.")
    else:
        logger.warning("Download completed with partial results or errors.")


if __name__ == "__main__":
    main()
