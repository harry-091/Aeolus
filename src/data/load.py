"""
Sea Ice Data Loader Module

Provides reusable functions for loading NSIDC sea-ice datasets.

Dataset: NOAA/NSIDC Sea Ice Index, Version 3 (G02135)
  - DOI: 10.7265/N5K072F8
  - Format: CSV (monthly extent/area per hemisphere)
  - Variables: extent (million km^2), area (million km^2)
  - Temporal: 1978/1979-present, monthly

Functions:
  - load_sea_ice(path): Load from local CSV path
  - get_dataset_metadata(ds): Inspect dataset structure
"""
import pandas as pd
import numpy as np
from pathlib import Path


# ---------------------------------------------------------------------------
# Load Functions
# ---------------------------------------------------------------------------

def load_sea_ice(path=None):
    """
    Load Antarctic sea-ice extent/area data from NSIDC G02135 CSV files.

    Parameters
    ----------
    path : str or Path, optional
        Path to a single CSV file, or directory containing CSV files.
        If None, loads all files from the default data/raw/sea_ice/ directory.

    Returns
    -------
    pd.DataFrame
        Columns: year, mo, source_dataset, region, extent, area
        Sorted by (year, mo).
    """
    if path is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        path = base_dir / "data" / "raw" / "sea_ice"
    path = Path(path)

    if path.is_file():
        return _load_single_csv(path)
    elif path.is_dir():
        return _load_csv_directory(path)
    else:
        raise FileNotFoundError(f"Path not found: {path}")


def _load_single_csv(filepath):
    """Load a single G02135 CSV file."""
    df = pd.read_csv(filepath, skipinitialspace=True)
    df.columns = df.columns.str.strip()
    return df


def _load_csv_directory(directory):
    """Load and concatenate all G02135 CSV files in a directory."""
    csv_files = sorted(directory.glob("S_*_extent_v4.0.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No G02135 CSV files found in {directory}. "
            "Run src/data/download.py first."
        )

    frames = []
    for f in csv_files:
        frames.append(_load_single_csv(f))

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(["year", "mo"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Metadata Inspection
# ---------------------------------------------------------------------------

def get_dataset_metadata(df):
    """
    Inspect and return metadata about the loaded dataset.

    Parameters
    ----------
    df : pd.DataFrame
        Loaded sea-ice data from load_sea_ice().

    Returns
    -------
    dict
        Metadata summary including dimensions, variables, time range,
        spatial coverage, units, and missing data info.
    """
    meta = {
        "dimensions": {
            "n_records": len(df),
            "n_years": df["year"].nunique(),
            "n_months": df["mo"].nunique(),
        },
        "variables": list(df.columns),
        "time_range": {
            "start_year": int(df["year"].min()),
            "end_year": int(df["year"].max()),
            "start_month": int(df.loc[df["year"].idxmin(), "mo"]),
            "end_month": int(df.loc[df["year"].idxmax(), "mo"]),
        },
        "spatial_coverage": {
            "region": df["region"].unique().tolist(),
            "description": "Antarctic (S) and/or Arctic (N) aggregate statistics",
        },
        "units": {
            "extent": "million km^2",
            "area": "million km^2",
        },
        "source_dataset": df["source_dataset"].unique().tolist(),
        "missing_values": {
            "extent": int(df["extent"].isna().sum()),
            "area": int(df["area"].isna().sum()),
        },
        "value_ranges": {
            "extent_min": float(df["extent"].min()),
            "extent_max": float(df["extent"].max()),
            "area_min": float(df["area"].min()),
            "area_max": float(df["area"].max()),
        },
        "doi": "10.7265/N5K072F8",
        "citation": (
            "Fetterer, F., Knowles, K., Meier, W. N., Savoie, M. & "
            "Windnagel, A. K. (2017). Sea Ice Index. (G02135, Version 3). "
            "[Data Set]. Boulder, Colorado USA. National Snow and Ice Data Center."
        ),
    }
    return meta
