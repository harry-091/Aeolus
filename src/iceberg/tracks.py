"""
Iceberg Track Construction and Velocity Calculation.

Groups observations by iceberg_id, sorts by time,
computes displacement, speed, and bearing.
"""
import numpy as np
import pandas as pd


EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two points."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return EARTH_RADIUS_KM * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Initial bearing from point 1 to point 2 in degrees (0=N, 90=E)."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = np.sin(dlon) * np.cos(lat2)
    y = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
    return (np.degrees(np.arctan2(x, y)) + 360) % 360


def build_tracks(df):
    """
    Build tracks with displacement, speed, and bearing.

    Parameters
    ----------
    df : pd.DataFrame
        Must have: iceberg_id, timestamp, latitude, longitude

    Returns
    -------
    pd.DataFrame
        Original columns plus: dt_hours, dist_km, speed_kmh, bearing_deg
    """
    tracks = []
    for iceberg_id, group in df.groupby("iceberg_id"):
        g = group.sort_values("timestamp").copy()
        g["dt_hours"] = g["timestamp"].diff().dt.total_seconds() / 3600.0

        # Displacement from previous position
        prev_lat = g["latitude"].shift(1)
        prev_lon = g["longitude"].shift(1)
        g["dist_km"] = haversine_km(prev_lat, prev_lon, g["latitude"], g["longitude"])
        g["speed_kmh"] = np.where(g["dt_hours"] > 0, g["dist_km"] / g["dt_hours"], 0.0)
        g["bearing_deg"] = bearing_deg(prev_lat, prev_lon, g["latitude"], g["longitude"])

        # Displacement vectors
        g["delta_lat"] = g["latitude"].diff()
        g["delta_lon"] = g["longitude"].diff()

        tracks.append(g)

    return pd.concat(tracks, ignore_index=True)
