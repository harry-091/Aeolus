"""
BYU/NIC Antarctic Iceberg Tracking Database Loader.

Dataset: BYU MERS Consolidated Antarctic Iceberg Database
Source: https://www.scp.byu.edu/iceberg/
Format: CSV per iceberg (522 icebergs)
Variables: date (YYYYDDD), lat, lon, interp_flag, major_axis, minor_axis
Temporal: 1978-present
Spatial: Antarctic (lat -90 to -39, lon -180 to 180)
"""
import pandas as pd
import numpy as np
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "iceberg" / "consolidated" / "consolidated"


def load_iceberg_track(iceberg_name, data_dir=None):
    """
    Load a single iceberg track from BYU/NIC CSV.

    Parameters
    ----------
    iceberg_name : str
        Iceberg name (e.g., 'a23', 'b15', 'd15').
    data_dir : str or Path, optional
        Path to directory containing CSV files.

    Returns
    -------
    pd.DataFrame
        Columns: iceberg_id, date, latitude, longitude, interpolated,
                 major_axis_km, minor_axis_km, timestamp
    """
    if data_dir is None:
        data_dir = DATA_DIR
    data_dir = Path(data_dir)

    csv_path = data_dir / f"{iceberg_name}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Iceberg file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    # Parse YYYYDDD date format
    df["date_str"] = df["date"].astype(str)
    df["year"] = df["date_str"].str[:4].astype(int)
    df["day_of_year"] = df["date_str"].str[4:].astype(int)
    df["timestamp"] = pd.to_datetime(
        df["year"].astype(str) + "-" + df["day_of_year"].astype(str),
        format="%Y-%j",
    )

    # Rename columns to standard names
    result = pd.DataFrame({
        "iceberg_id": iceberg_name,
        "timestamp": df["timestamp"],
        "latitude": df["nic_1"],
        "longitude": df["nic_2"],
        "interpolated": df["nic_3"],
        "major_axis_km": df["size_1"],
        "minor_axis_km": df["size_2"],
    })

    # Remove rows with invalid coordinates
    result = result[
        (result["latitude"].notna()) &
        (result["longitude"].notna()) &
        (result["latitude"] < 0) &  # Antarctic
        (result["longitude"] >= -180) &
        (result["longitude"] <= 180)
    ]

    result = result.sort_values("timestamp").reset_index(drop=True)
    return result


def load_all_icebergs(data_dir=None, min_observations=10):
    """
    Load all iceberg tracks that have enough observations.

    Parameters
    ----------
    data_dir : str or Path, optional
        Path to directory containing CSV files.
    min_observations : int
        Minimum observations per iceberg to include.

    Returns
    -------
    pd.DataFrame
        Combined dataframe with all qualifying tracks.
    """
    if data_dir is None:
        data_dir = DATA_DIR
    data_dir = Path(data_dir)

    csv_files = sorted(data_dir.glob("*.csv"))
    tracks = []

    for csv_file in csv_files:
        name = csv_file.stem
        try:
            df = load_iceberg_track(name, data_dir)
            if len(df) >= min_observations:
                tracks.append(df)
        except Exception:
            continue

    if not tracks:
        raise FileNotFoundError("No qualifying iceberg tracks found")

    combined = pd.concat(tracks, ignore_index=True)
    n_icebergs = combined["iceberg_id"].nunique()
    print(f"  Loaded {n_icebergs} icebergs, {len(combined)} observations")
    return combined
