#!/usr/bin/env python3
"""Fail-fast health check for PolarNav real-data configuration."""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    load_dotenv(root / "backend" / ".env")
except Exception:
    pass

checks = [
    ("POLARNAV_REAL_DATA_ONLY", os.getenv("POLARNAV_REAL_DATA_ONLY")),
    ("OPEN_WATERS_API_KEY", os.getenv("OPEN_WATERS_API_KEY") or os.getenv("AIS_API_KEY")),
    ("STAC_API_URL", os.getenv("STAC_API_URL")),
    ("COPERNICUS_MARINE_USERNAME", os.getenv("COPERNICUS_MARINE_USERNAME")),
    ("COPERNICUS_MARINE_PASSWORD", os.getenv("COPERNICUS_MARINE_PASSWORD")),
    ("EARTHDATA_USERNAME", os.getenv("EARTHDATA_USERNAME")),
    ("EARTHDATA_PASSWORD", os.getenv("EARTHDATA_PASSWORD")),
]

failed = False
for key, value in checks:
    if key == "POLARNAV_REAL_DATA_ONLY":
        ok = str(value).lower() in {"1", "true", "yes", "on"}
    else:
        ok = bool(value) and not str(value).startswith("YOUR_")
    print(f"{'OK' if ok else 'MISSING':8} {key}")
    failed |= not ok

backend_data = Path(__file__).resolve().parents[1] / "data"
for rel in [
    "raw/ocean/copernicus_currents_live.nc",
    "raw/ocean/copernicus_sst_live.nc",
    "raw/sea_ice/real_cdr_sic.nc",
    "processed/verification/phase3_icebergs.json",
]:
    p = backend_data / rel
    print(f"{'OK' if p.exists() else 'MISSING':8} {rel}")

print("\nNote: missing ocean/sea-ice/iceberg files are data-ingestion steps, not Python-code errors.")
sys.exit(1 if failed else 0)
