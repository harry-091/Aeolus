"""
Feature Engineering for Sea-Ice Concentration Forecasting.

Creates ML-ready features from spatial SIC data.

Features:
- lat, lon (spatial coordinates)
- month (seasonal cycle)
- day_of_year (annual cycle)
- sic_lag_1, sic_lag_2, sic_lag_3 (temporal lags)
- sic_mean_3month (rolling mean)

Target: next-month SIC at same grid cell.

For monthly data:
- lag_1 = previous month
- lag_2 = 2 months ago
- lag_3 = 3 months ago
"""
import numpy as np
import pandas as pd
import xarray as xr


def create_features_from_xarray(ds, target_lead=1):
    """
    Convert xarray Dataset to flat DataFrame with ML features.

    Parameters
    ----------
    ds : xarray.Dataset
        Must contain 'sic' variable with time, lat, lon dims.
    target_lead : int
        Lead time in months for target variable.

    Returns
    -------
    pd.DataFrame
        Columns: lat, lon, month, day_of_year, sic_lag_1, sic_lag_2,
                 sic_lag_3, sic_mean_3month, target_sic
    """
    sic = ds["sic"]
    times = pd.to_datetime(sic.time.values)
    lats = sic.lat.values
    lons = sic.lon.values

    records = []

    for t_idx in range(3, len(times) - target_lead):
        current_time = times[t_idx]
        target_time = times[t_idx + target_lead]

        for lat_idx, lat in enumerate(lats):
            for lon_idx, lon in enumerate(lons):
                sic_current = float(sic.values[t_idx, lat_idx, lon_idx])
                sic_lag1 = float(sic.values[t_idx - 1, lat_idx, lon_idx])
                sic_lag2 = float(sic.values[t_idx - 2, lat_idx, lon_idx])
                sic_lag3 = float(sic.values[t_idx - 3, lat_idx, lon_idx])
                sic_target = float(sic.values[t_idx + target_lead, lat_idx, lon_idx])

                # Rolling mean
                sic_mean_3m = np.mean([sic_lag1, sic_lag2, sic_lag3])

                records.append({
                    "lat": lat,
                    "lon": lon,
                    "month": current_time.month,
                    "day_of_year": current_time.timetuple().tm_yday,
                    "sic_lag_1": sic_lag1,
                    "sic_lag_2": sic_lag2,
                    "sic_lag_3": sic_lag3,
                    "sic_mean_3month": sic_mean_3m,
                    "target_sic": sic_target,
                })

    df = pd.DataFrame(records)
    return df


def create_features_from_cdr(nc_path=None, sample_step=2, target_lead=1):
    """
    Convert authentic NOAA/NSIDC CDR NetCDF series to flat ML features DataFrame.

    Parameters
    ----------
    nc_path : str or Path, optional
        Path to real_cdr_series_18m.nc.
    sample_step : int
        Subsampling step for spatial grid to control sample size.
    target_lead : int
        Lead time in months for forecast target.
    """
    from pathlib import Path
    import pyproj

    if nc_path is None:
        nc_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "sea_ice" / "real_cdr_series_18m.nc"
    nc_path = Path(nc_path)

    if not nc_path.exists():
        raise FileNotFoundError(f"Real CDR series file not found at {nc_path}")

    ds = xr.open_dataset(nc_path)
    var_name = "cdr_seaice_conc_monthly" if "cdr_seaice_conc_monthly" in ds else list(ds.data_vars.keys())[0]
    da = ds[var_name]

    times = pd.to_datetime(ds.time.values)
    x = ds.xgrid.values[::sample_step]
    y = ds.ygrid.values[::sample_step]
    vals = da.values[:, ::sample_step, ::sample_step]  # (time, y, x)
    ds.close()

    gx, gy = np.meshgrid(x, y)
    trans = pyproj.Transformer.from_crs("EPSG:3412", "EPSG:4326", always_xy=True)
    lons, lats = trans.transform(gx, gy)

    # Clean flags (> 1.0 indicates flags like pole hole, coast, or land in NOAA CDR)
    vals = np.where((vals >= 0.0) & (vals <= 1.0), vals, np.nan)

    # Oceanic points in Southern Ocean
    ocean_mask = (lats <= -50.0) & (np.sum(~np.isnan(vals), axis=0) >= (len(times) - 2))
    y_idxs, x_idxs = np.where(ocean_mask)

    records = []
    n_times = len(times)

    for t_idx in range(3, n_times - target_lead):
        cur_t = times[t_idx]
        cur_m = cur_t.month
        cur_doy = cur_t.dayofyear

        v_target = vals[t_idx + target_lead, y_idxs, x_idxs]
        v_lag1 = vals[t_idx, y_idxs, x_idxs]
        v_lag2 = vals[t_idx - 1, y_idxs, x_idxs]
        v_lag3 = vals[t_idx - 2, y_idxs, x_idxs]

        # Valid rows where none of the values is NaN
        valid_row = ~np.isnan(v_target) & ~np.isnan(v_lag1) & ~np.isnan(v_lag2) & ~np.isnan(v_lag3)

        sub_lats = lats[y_idxs[valid_row], x_idxs[valid_row]]
        sub_lons = lons[y_idxs[valid_row], x_idxs[valid_row]]
        sub_lag1 = v_lag1[valid_row]
        sub_lag2 = v_lag2[valid_row]
        sub_lag3 = v_lag3[valid_row]
        sub_mean3 = (sub_lag1 + sub_lag2 + sub_lag3) / 3.0
        sub_target = v_target[valid_row]

        n_pts = len(sub_target)
        if n_pts > 0:
            sub_df = pd.DataFrame({
                "lat": sub_lats,
                "lon": sub_lons,
                "month": cur_m,
                "day_of_year": cur_doy,
                "sic_lag_1": sub_lag1,
                "sic_lag_2": sub_lag2,
                "sic_lag_3": sub_lag3,
                "sic_mean_3month": sub_mean3,
                "target_sic": sub_target,
            })
            records.append(sub_df)

    if not records:
        raise ValueError("No valid features could be extracted from CDR dataset")

    df = pd.concat(records, ignore_index=True)
    return df


def get_feature_columns():
    """Return list of feature column names."""
    return ["lat", "lon", "month", "day_of_year",
            "sic_lag_1", "sic_lag_2", "sic_lag_3", "sic_mean_3month"]


def get_target_column():
    """Return target column name."""
    return "target_sic"
