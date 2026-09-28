"""
Sea Ice Preprocessing Module

Reusable preprocessing functions for NSIDC sea-ice data.

Pipeline:
  RAW DATA
  -> Handle documented missing values (-9999 fill value)
  -> Validate values
  -> Select Antarctic region
  -> Select required variables
  -> Preserve coordinates
  -> Return processed dataset

For G02135 CSV data:
  - Filter to Antarctic region (S)
  - Replace -9999 fill values with NaN
  - Select year, month, extent, area
  - Create datetime index
  - Compute derived fields (ice_efficiency = area/extent)
  - Drop rows with NaN in extent/area

For gridded CDR data (future):
  - Handle land mask and missing values
  - Subset to Antarctic region
  - Select SIC variable
  - Preserve lat/lon coordinates
"""
import pandas as pd
import numpy as np
from pathlib import Path


# NSIDC fill value convention
NSIDC_FILL_VALUE = -9999.0


def preprocess_sea_ice(df, region="S", output_path=None):
    """
    Preprocess NSIDC G02135 sea-ice extent/area data.

    Parameters
    ----------
    df : pd.DataFrame
        Raw data from load_sea_ice().
    region : str
        Region to keep ('S' for Antarctic, 'N' for Arctic, 'both').
    output_path : str or Path, optional
        Where to save the processed dataset. If None, returns only.

    Returns
    -------
    pd.DataFrame
        Processed dataset with columns:
        - date: datetime (first day of month)
        - year: int
        - month: int
        - extent: float (million km^2)
        - area: float (million km^2)
        - ice_efficiency: float (area/extent, 0-1)
    """
    # Step 1: Select region
    if region != "both":
        df = df[df["region"] == region].copy()

    if len(df) == 0:
        raise ValueError(f"No data found for region '{region}'")

    # Step 2: Replace NSIDC fill values with NaN
    df = df.copy()
    for col in ["extent", "area"]:
        df[col] = df[col].replace(NSIDC_FILL_VALUE, np.nan)

    # Step 3: Select required variables
    processed = df[["year", "mo", "extent", "area"]].copy()
    processed = processed.rename(columns={"mo": "month"})

    # Step 4: Create datetime index (first day of each month)
    processed["date"] = pd.to_datetime(
        processed[["year", "month"]].assign(day=1)
    )

    # Step 5: Drop rows with missing extent/area
    n_before = len(processed)
    processed = processed.dropna(subset=["extent", "area"])
    n_dropped = n_before - len(processed)
    if n_dropped > 0:
        print(f"  [INFO] Dropped {n_dropped} rows with fill values (missing data)")

    # Step 6: Compute derived fields
    processed["ice_efficiency"] = np.where(
        processed["extent"] > 0,
        processed["area"] / processed["extent"],
        0.0,
    )

    # Step 7: Sort by date
    processed = processed.sort_values("date").reset_index(drop=True)

    # Step 8: Save if requested
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        processed.to_csv(output_path, index=False)
        print(f"  [OK] Saved processed data to {output_path}")

    return processed


def preprocess_cdr_to_csv(nc_path, output_csv_path):
    """
    Preprocess gridded CDR NetCDF data to a summary CSV.

    Extracts time-averaged Antarctic sea-ice concentration statistics.

    Parameters
    ----------
    nc_path : str or Path
        Path to the CDR NetCDF file.
    output_csv_path : str or Path
        Where to save the summary CSV.

    Returns
    -------
    pd.DataFrame
        Summary with columns: date, mean_sic, max_sic, extent_km2
    """
    import xarray as xr

    nc_path = Path(nc_path)
    if not nc_path.exists():
        raise FileNotFoundError(f"CDR file not found: {nc_path}")

    ds = xr.open_dataset(nc_path)
    sic = ds["seaice_conc_cdr"]

    # Compute spatial statistics per time step
    stats = []
    for t in range(len(sic.time)):
        sic_t = sic.isel(time=t)
        valid = sic_t.where(sic_t <= 1.0)  # mask invalid values
        stats.append({
            "date": pd.Timestamp(sic_t.time.values),
            "mean_sic": float(valid.mean()),
            "max_sic": float(valid.max()),
            "extent_km2": float((valid >= 0.15).sum()) * 25 * 25,  # 25km grid
        })

    df = pd.DataFrame(stats)

    # Save
    output_csv_path = Path(output_csv_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv_path, index=False)
    print(f"  [OK] Saved CDR summary to {output_csv_path}")

    return df
