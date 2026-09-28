"""Unified Historical Antarctic Vessel Track Loader.

Ingests real historical Antarctic research vessel tracks across international sources:
1. Australian Antarctic Data Centre (AAD): Aurora Australis voyages
2. PANGAEA (Alfred Wegener Institute): RV Polarstern expeditions (PS118, ANT-XX/3, ANT-V/2)
3. US Antarctic Program (USAP): RV Nathaniel B. Palmer expeditions (NBP-2010)

Standardizes all feeds into a consistent, validated DataFrame schema using vectorized operations.
"""
import os
import glob
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
AAD_TRACKS_DIR = RAW_DIR / "vessel_tracks"
HISTORICAL_TRACKS_DIR = RAW_DIR / "vessels_historical"

VOYAGE_NAMES = {
    '201516020': 'Aurora Australis V2 2015/16',
    '201718030': 'Aurora Australis V3 2017/18',
    '201011040': 'Aurora Australis V4 2010/11',
    '201819020': 'Aurora Australis V2 2018/19',
    '200809020': 'Aurora Australis V2 2008/09',
    'PS118-2018': 'RV Polarstern PS118',
    'NBP-2010': 'RV Nathaniel B. Palmer 2009/10',
    'ANT-XX-3-2003': 'RV Polarstern ANT-XX/3',
    'ANT-V-2-1986': 'RV Polarstern ANT-V/2',
}


def load_vessel_tracks(data_dir: Optional[str] = None, include_historical: bool = True) -> pd.DataFrame:
    """Load and unify all real historical vessel track data across international repositories."""
    vessel_tracks_path = Path(data_dir) if data_dir else AAD_TRACKS_DIR
    all_tracks: List[pd.DataFrame] = []

    # 1. Ingest AAD Tracks
    if vessel_tracks_path.exists():
        csv_files = sorted(glob.glob(str(vessel_tracks_path / "voyage_*.csv")))
        orig = vessel_tracks_path / "aurora_australis_2015_16.csv"
        if orig.exists():
            csv_files = [str(orig)] + csv_files

        for csv_path in csv_files:
            try:
                df = pd.read_csv(csv_path)
                if df.empty or 'latitude' not in df.columns or 'longitude' not in df.columns:
                    continue

                set_code = str(df['set_code'].iloc[0]) if 'set_code' in df.columns else Path(csv_path).stem
                df = df.dropna(subset=['latitude', 'longitude'])
                df = df[(df['latitude'] >= -90) & (df['latitude'] <= 0) & (df['longitude'] >= -180) & (df['longitude'] <= 180)]

                track_df = pd.DataFrame({
                    'vessel_id': set_code,
                    'vessel_name': VOYAGE_NAMES.get(set_code, f'Voyage {set_code}'),
                    'timestamp': pd.to_datetime(df['date_time_utc'], errors='coerce'),
                    'latitude': df['latitude'].astype(float),
                    'longitude': df['longitude'].astype(float),
                    'speed_knots': df['ship_spd_over_ground_knot'].astype(float) if 'ship_spd_over_ground_knot' in df.columns else None,
                    'heading_deg': df['ship_heading_gps_deg'].astype(float) if 'ship_heading_gps_deg' in df.columns else None,
                    'course_deg': df['ship_course_over_ground_deg'].astype(float) if 'ship_course_over_ground_deg' in df.columns else None,
                    'source': 'Australian Antarctic Data Centre (AAD)',
                    'data_type': 'historical_vessel_track',
                }).dropna(subset=['timestamp'])

                track_df = track_df.sort_values('timestamp').drop_duplicates(subset=['vessel_id', 'timestamp']).reset_index(drop=True)
                if not track_df.empty:
                    all_tracks.append(track_df)
            except Exception as e:
                print(f"Warning: Failed to load AAD track {csv_path}: {e}")

    # 2. Ingest PANGAEA & USAP Tracks
    if include_historical and HISTORICAL_TRACKS_DIR.exists():
        hist_files = sorted(glob.glob(str(HISTORICAL_TRACKS_DIR / "*.csv")))
        for csv_path in hist_files:
            try:
                file_stem = Path(csv_path).stem
                df = pd.read_csv(csv_path)
                if df.empty or 'latitude' not in df.columns or 'longitude' not in df.columns:
                    continue

                if "Polarstern" in file_stem or "PS" in file_stem or "ANT" in file_stem:
                    src_name = "Alfred Wegener Institute (PANGAEA)"
                    v_name = VOYAGE_NAMES.get(file_stem, f"RV Polarstern {file_stem}")
                elif "NBP" in file_stem or "Palmer" in file_stem:
                    src_name = "US Antarctic Program (USAP)"
                    v_name = VOYAGE_NAMES.get(file_stem, f"RV Nathaniel B. Palmer {file_stem}")
                else:
                    src_name = "International Polar Archive"
                    v_name = VOYAGE_NAMES.get(file_stem, f"Vessel {file_stem}")

                df = df.dropna(subset=['latitude', 'longitude'])
                df = df[(df['latitude'] >= -90) & (df['latitude'] <= 0) & (df['longitude'] >= -180) & (df['longitude'] <= 180)]

                track_df = pd.DataFrame({
                    'vessel_id': file_stem,
                    'vessel_name': v_name,
                    'timestamp': pd.to_datetime(df['timestamp'], errors='coerce'),
                    'latitude': df['latitude'].astype(float),
                    'longitude': df['longitude'].astype(float),
                    'speed_knots': df['speed'].astype(float) if 'speed' in df.columns else None,
                    'heading_deg': df['heading'].astype(float) if 'heading' in df.columns else None,
                    'course_deg': df['heading'].astype(float) if 'heading' in df.columns else None,
                    'source': src_name,
                    'data_type': 'historical_vessel_track',
                }).dropna(subset=['timestamp'])

                track_df = track_df.sort_values('timestamp').drop_duplicates(subset=['vessel_id', 'timestamp']).reset_index(drop=True)
                if not track_df.empty:
                    all_tracks.append(track_df)
            except Exception as e:
                print(f"Warning: Failed to load historical track {csv_path}: {e}")

    if all_tracks:
        return pd.concat(all_tracks, ignore_index=True)
    return pd.DataFrame()


def get_vessel_list(tracks: pd.DataFrame) -> pd.DataFrame:
    """Get aggregated summary list of unique vessels in the dataset."""
    if tracks.empty:
        return pd.DataFrame()
    return tracks.groupby('vessel_id').agg({
        'vessel_name': 'first',
        'source': 'first',
        'timestamp': ['min', 'max', 'count'],
        'latitude': ['min', 'max'],
        'longitude': ['min', 'max']
    }).reset_index()


def get_track(tracks: pd.DataFrame, vessel_id: str) -> pd.DataFrame:
    """Get full track for a specific vessel, sorted chronologically."""
    if tracks.empty:
        return pd.DataFrame()
    t = tracks[tracks['vessel_id'] == str(vessel_id)].copy()
    return t.sort_values('timestamp').reset_index(drop=True)


def get_latest_position(tracks: pd.DataFrame, vessel_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest position of a vessel."""
    t = get_track(tracks, vessel_id)
    if len(t) == 0:
        return None
    return t.iloc[-1].to_dict()


def get_position_at_time(tracks: pd.DataFrame, vessel_id: str, timestamp: Any) -> Optional[Dict[str, Any]]:
    """Get vessel position closest to a given timestamp."""
    t = get_track(tracks, vessel_id)
    if len(t) == 0:
        return None
    ts = pd.to_datetime(timestamp)
    idx = (t['timestamp'] - ts).abs().idxmin()
    return t.iloc[idx].to_dict()


def get_track_coords(tracks: pd.DataFrame, vessel_id: str) -> List[List[float]]:
    """Get track as list of [lat, lon] coordinates."""
    t = get_track(tracks, vessel_id)
    if t.empty:
        return []
    return t[['latitude', 'longitude']].values.tolist()
