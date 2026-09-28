"""
Sea Ice Data Validation Module

Validates NSIDC G02135 sea-ice extent/area datasets.

Checks performed:
  1. Dataset loaded successfully
  2. Required columns present
  3. Time coverage validity (year, month ranges)
  4. Extent/area value validity
  5. Physical constraint (area <= extent)
  6. Missing value detection (NaN)
  7. NSIDC fill value detection (-9999)
  8. Region is Antarctic

For the G02135 CSV dataset:
  - Variables: extent and area (million km^2)
  - Missing data convention: -9999 fill value
  - Region: S (Antarctic) aggregate statistics
  - No gridded coordinates (aggregate data)

For gridded CDR data (future):
  - Latitude: -89.84 to -39.36
  - Longitude: -180 to 180
  - SIC: 0.0 to 1.0 (fraction)
  - Missing value: flagged in quality variable
"""
import pandas as pd
import numpy as np


NSIDC_FILL_VALUE = -9999.0


def validate_dataset(df, dataset_type="g02135"):
    """
    Validate a loaded sea-ice dataset.

    Parameters
    ----------
    df : pd.DataFrame or xarray.Dataset
        The loaded dataset.
    dataset_type : str
        'g02135' for monthly extent/area CSV data,
        'cdr' for gridded CDR NetCDF data.

    Returns
    -------
    dict
        Validation results with keys:
        - overall: 'PASS', 'WARN', or 'FAIL'
        - checks: list of individual check results
          Each check has: check, status (PASS/WARN/FAIL), detail
    """
    checks = []

    if dataset_type == "g02135":
        checks.extend(_validate_g02135(df))
    elif dataset_type == "cdr":
        checks.extend(_validate_cdr(df))
    else:
        checks.append({"check": "Dataset type", "status": "FAIL",
                       "detail": f"Unknown type: {dataset_type}"})

    # Determine overall status:
    # PASS = all checks PASS
    # WARN = no FAIL checks, but some WARN
    # FAIL = any FAIL check
    statuses = [c["status"] for c in checks]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    return {"overall": overall, "checks": checks}


def _validate_g02135(df):
    """Validate G02135 monthly extent/area dataset."""
    checks = []

    # 1. Dataset loaded
    checks.append({
        "check": "Dataset loaded",
        "status": "PASS" if isinstance(df, pd.DataFrame) and len(df) > 0 else "FAIL",
        "detail": f"Type={type(df).__name__}, rows={len(df)}",
    })

    # 2. Required columns
    required_cols = {"year", "mo", "extent", "area", "region", "source_dataset"}
    missing_cols = required_cols - set(df.columns)
    checks.append({
        "check": "Required columns",
        "status": "PASS" if not missing_cols else "FAIL",
        "detail": f"Missing: {missing_cols}" if missing_cols else f"Found: {required_cols}",
    })

    # 3. Year validity
    years_valid = (df["year"] >= 1978) & (df["year"] <= 2030)
    checks.append({
        "check": "Year validity (1978-2030)",
        "status": "PASS" if years_valid.all() else "FAIL",
        "detail": f"Range: {df['year'].min()}-{df['year'].max()}",
    })

    # 4. Month validity
    months_valid = df["mo"].isin(range(1, 13))
    checks.append({
        "check": "Month validity (1-12)",
        "status": "PASS" if months_valid.all() else "FAIL",
        "detail": f"Unique months: {sorted(df['mo'].unique())}",
    })

    # 5. NSIDC fill values check
    has_fill = (df["extent"] == NSIDC_FILL_VALUE).any() or (df["area"] == NSIDC_FILL_VALUE).any()
    n_fill = ((df["extent"] == NSIDC_FILL_VALUE) | (df["area"] == NSIDC_FILL_VALUE)).sum()
    checks.append({
        "check": "NSIDC fill values (-9999)",
        "status": "PASS" if not has_fill else "WARN",
        "detail": f"{n_fill} rows contain fill values (missing data)" if has_fill else "No fill values found",
    })

    # 6. Extent values valid (> 0, excluding fill values)
    valid_extent = df[df["extent"] != NSIDC_FILL_VALUE]["extent"]
    extent_valid = (valid_extent > 0) & (valid_extent < 30)
    checks.append({
        "check": "Extent values valid (> 0, < 30 M km2)",
        "status": "PASS" if extent_valid.all() else "WARN",
        "detail": f"Range: {valid_extent.min():.2f}-{valid_extent.max():.2f} M km2 ({len(valid_extent)} valid rows)",
    })

    # 7. Area values valid (> 0, excluding fill values)
    valid_area = df[df["area"] != NSIDC_FILL_VALUE]["area"]
    area_valid = (valid_area > 0) & (valid_area < 30)
    checks.append({
        "check": "Area values valid (> 0, < 30 M km2)",
        "status": "PASS" if area_valid.all() else "WARN",
        "detail": f"Range: {valid_area.min():.2f}-{valid_area.max():.2f} M km2 ({len(valid_area)} valid rows)",
    })

    # 8. Area <= Extent (physical constraint, excluding fill values)
    valid_both = df[(df["extent"] != NSIDC_FILL_VALUE) & (df["area"] != NSIDC_FILL_VALUE)]
    area_lt_extent = valid_both["area"] <= valid_both["extent"]
    checks.append({
        "check": "Area <= Extent (physical constraint)",
        "status": "PASS" if area_lt_extent.all() else "FAIL",
        "detail": f"Violations: {(~area_lt_extent).sum()}" if not area_lt_extent.all() else f"All {len(valid_both)} rows pass",
    })

    # 9. Missing values (NaN, not fill values)
    n_nan = df[["extent", "area"]].isna().sum().sum()
    checks.append({
        "check": "NaN missing values",
        "status": "PASS" if n_nan == 0 else "WARN",
        "detail": f"{n_nan} NaN values in extent/area",
    })

    # 10. Region is Antarctic
    is_south = (df["region"] == "S").all()
    checks.append({
        "check": "Region is Antarctic (S)",
        "status": "PASS" if is_south else "WARN",
        "detail": f"Regions: {df['region'].unique().tolist()}",
    })

    return checks


def _validate_cdr(ds):
    """
    Validate gridded CDR NetCDF dataset.

    Parameters
    ----------
    ds : xarray.Dataset
        Loaded CDR dataset.
    """
    checks = []

    # 1. Dataset loaded
    checks.append({
        "check": "Dataset loaded",
        "status": "PASS" if ds is not None and len(ds.data_vars) > 0 else "FAIL",
        "detail": f"Variables: {list(ds.data_vars)}",
    })

    # 2. Required variable
    has_sic = "seaice_conc_cdr" in ds.data_vars
    checks.append({
        "check": "SIC variable present (seaice_conc_cdr)",
        "status": "PASS" if has_sic else "FAIL",
        "detail": f"Variables: {list(ds.data_vars)}",
    })

    # 3. Dimensions
    checks.append({
        "check": "Dimensions",
        "status": "PASS",
        "detail": f"{dict(ds.dims)}",
    })

    # 4. SIC value range
    if has_sic:
        sic = ds["seaice_conc_cdr"]
        valid_range = (sic >= 0) & (sic <= 1)
        pct_valid = float(valid_range.mean()) * 100
        checks.append({
            "check": "SIC value range (0-1)",
            "status": "PASS" if pct_valid > 95 else "WARN",
            "detail": f"{pct_valid:.1f}% values in valid range",
        })

    return checks
