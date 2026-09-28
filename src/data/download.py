"""
NSIDC Sea Ice Data Download Module

Downloads real Antarctic Sea-Ice Extent/Area data from NSIDC.

Dataset: NOAA/NSIDC Sea Ice Index, Version 3 (G02135)
  - DOI: 10.7265/N5K072F8
  - Source: https://noaadata.apps.nsidc.org/NOAA/G02135/
  - Format: CSV (monthly extent/area per hemisphere)
  - Spatial: Antarctic (S) and Arctic (N) regions
  - Temporal: 1979-present, monthly resolution
  - Units: million km^2 (extent and area)
  - Missing data: None (all values present)
  - License: Public Domain (CC0 1.0)

Dataset: NOAA/NSIDC CDR of Passive Microwave SIC, Version 4 (G02202)
  - DOI: 10.7265/efmz-2t65
  - Source: https://polarwatch.noaa.gov/erddap/ (ERDDAP)
  - Format: NetCDF (monthly gridded SIC)
  - Grid: 25 km polar stereographic south (EPSG:3412)
  - Variable: seaice_conc_cdr (fraction 0-1)
  - Temporal: 1978-10-25 to present, daily and monthly
  - Coverage: Antarctic lat -89.84 to -39.36

Access Method:
  - G02135 CSVs: Direct HTTP download from noaadata.apps.nsidc.org (no auth)
  - G02202 CDR: ERDDAP griddap API (no auth required for subsetting)
"""
import os
import requests
import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "sea_ice"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# G02135 monthly extent/area CSVs
G02135_BASE_URL = os.environ.get("NSIDC_G02135_BASE_URL", "https://noaadata.apps.nsidc.org/NOAA/G02135").rstrip("/")
MONTHS = list(range(1, 13))

# CDR ERDDAP
_raw_erddap = (
    os.environ.get("NOAA_POLARWATCH_ERDDAP_URL")
    or os.environ.get("NOAA_ERDDAP_BASE_URL", "https://polarwatch.noaa.gov/erddap")
).rstrip("/")
CDR_ERDDAP_URL = _raw_erddap if _raw_erddap.endswith("/griddap") else f"{_raw_erddap}/griddap"
CDR_SOUTH_MONTHLY = "nsidcCDRiceSQsh1month"


# ---------------------------------------------------------------------------
# G02135 Monthly Extent/Area Download
# ---------------------------------------------------------------------------

def download_g02135_monthly(hemisphere="south", months=None, force=False):
    """
    Download monthly sea-ice extent and area CSV files from NSIDC G02135.

    Parameters
    ----------
    hemisphere : str
        'south' for Antarctic, 'north' for Arctic.
    months : list of int, optional
        Months to download (1-12). Default: all months.
    force : bool
        If True, re-download even if file exists.

    Returns
    -------
    list of Path
        Paths to downloaded CSV files.
    """
    if months is None:
        months = MONTHS

    out_dir = RAW_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []
    for mo in months:
        fname = f"S_{mo:02d}_extent_v4.0.csv"
        url = f"{G02135_BASE_URL}/{hemisphere}/monthly/data/{fname}"
        out_path = out_dir / fname

        if out_path.exists() and not force:
            print(f"  [EXISTS] {fname}")
            downloaded.append(out_path)
            continue

        print(f"  Downloading {fname}...")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            out_path.write_bytes(resp.content)
            print(f"  [OK] {fname} ({len(resp.content)} bytes)")
            downloaded.append(out_path)
        except requests.RequestException as e:
            print(f"  [FAIL] {fname}: {e}")

    return downloaded


def load_g02135_csv(filepath):
    """
    Load a single G02135 monthly extent CSV file.

    Returns
    -------
    pd.DataFrame
        Columns: year, mo, source_dataset, region, extent, area
    """
    df = pd.read_csv(filepath, skipinitialspace=True)
    # Ensure column names are clean
    df.columns = df.columns.str.strip()
    return df


def load_all_g02135(months=None):
    """
    Load all downloaded G02135 CSV files into a single DataFrame.

    Returns
    -------
    pd.DataFrame
        Combined monthly extent/area data from 1979 to present.
    """
    if months is None:
        months = MONTHS

    frames = []
    for mo in months:
        fname = f"S_{mo:02d}_extent_v4.0.csv"
        fpath = RAW_DIR / fname
        if fpath.exists():
            frames.append(load_g02135_csv(fpath))
        else:
            print(f"  [SKIP] {fname} not found")

    if not frames:
        raise FileNotFoundError("No G02135 CSV files found. Run download first.")

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(["year", "mo"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# CDR ERDDAP Download (Gridded SIC)
# ---------------------------------------------------------------------------

def download_cdr_monthly_south(start_date, end_date, variables=None,
                                output_path=None, force=False):
    """
    Download monthly gridded Antarctic SIC from NSIDC CDR via ERDDAP.

    Parameters
    ----------
    start_date : str
        Start date in 'YYYY-MM-DD' format.
    end_date : str
        End date in 'YYYY-MM-DD' format.
    variables : list of str, optional
        Variables to download. Default: ['seaice_conc_cdr'].
    output_path : str or Path, optional
        Where to save the NetCDF file.
    force : bool
        If True, re-download even if file exists.

    Returns
    -------
    Path or None
        Path to downloaded file, or None if failed.
    """
    if variables is None:
        variables = ["seaice_conc_cdr"]

    if output_path is None:
        output_path = PROCESSED_DIR / "cdr_south_monthly.nc"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not force:
        print(f"  [EXISTS] {output_path}")
        return output_path

    var_str = ",".join(variables)
    url = (
        f"{CDR_ERDDAP_URL}/{CDR_SOUTH_MONTHLY}.nc?"
        f"{var_str}[({start_date}T00:00:00Z):1:({end_date}T00:00:00Z)]"
        f"[(-89.875):1:(-39.625)]"
        f"[(-179.875):1:(179.875)]"
    )

    print(f"  Downloading CDR SIC from ERDDAP...")
    try:
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  [OK] Saved to {output_path} ({output_path.stat().st_size} bytes)")
        return output_path
    except requests.RequestException as e:
        print(f"  [FAIL] ERDDAP download failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def download_all(force=False):
    """Download all available datasets. Returns dict of results."""
    results = {}

    print("=== Downloading G02135 Monthly Extent/Area ===")
    csvs = download_g02135_monthly(force=force)
    results["g02135_csvs"] = csvs

    print("\n=== Loading combined extent/area data ===")
    df = load_all_g02135()
    results["extent_data"] = df
    print(f"  Loaded {len(df)} monthly records, {df['year'].min()}-{df['year'].max()}")

    return results


if __name__ == "__main__":
    download_all()
