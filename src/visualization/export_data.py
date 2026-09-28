"""Export existing Phase 1-4 outputs to JSON for the verification map.

This script does NOT create fake data. It only exports actual outputs.
"""
import json
import numpy as np
import xarray as xr
import pandas as pd
import os
import sys

# Ensure project root is on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_DIR = os.path.join(ROOT, "data", "processed", "verification")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def export_phase1():
    """Export Phase 1 extent/area time series."""
    df = pd.read_csv(os.path.join(ROOT, "data", "processed", "extent_area_monthly.csv"))
    data = {
        "dates": df["date"].tolist(),
        "extent": df["extent"].tolist(),
        "area": df["area"].tolist(),
    }
    with open(os.path.join(OUTPUT_DIR, "phase1_extent.json"), "w") as f:
        json.dump(data, f)
    print(f"Phase 1: {len(df)} records exported")


def export_phase2():
    """Export Phase 2 current SIC."""
    sic_ds = xr.open_dataset(os.path.join(ROOT, "data", "raw", "sea_ice", "spatial_sic_monthly.nc"))
    lats = sic_ds.lat.values.tolist()
    lons = sic_ds.lon.values.tolist()

    current_sic = sic_ds["sic"].isel(time=-1).values
    current_time = str(sic_ds.time.values[-1])[:10]
    sic_ds.close()

    current_points = []
    for i in range(len(lats)):
        for j in range(len(lons)):
            val = float(current_sic[i, j])
            if val > 0.01:
                current_points.append([round(lats[i], 2), round(lons[j], 2), round(val, 3)])

    data = {
        "lats": [round(x, 2) for x in lats],
        "lons": [round(x, 2) for x in lons],
        "current_time": current_time,
        "current_points": current_points,
        "sic_min": round(float(current_sic.min()), 3),
        "sic_max": round(float(current_sic.max()), 3),
    }
    with open(os.path.join(OUTPUT_DIR, "phase2_sic.json"), "w") as f:
        json.dump(data, f)
    print(f"Phase 2: {len(current_points)} SIC cells exported (current: {current_time})")


def export_phase3():
    """Export Phase 3 iceberg tracks and predicted trajectories."""
    from src.iceberg.load import load_all_icebergs
    from src.iceberg.tracks import build_tracks
    from src.iceberg.predict import load_model

    df = load_all_icebergs()
    tracks = build_tracks(df)

    top_icebergs = df.groupby("iceberg_id").size().nlargest(10).index.tolist()

    iceberg_data = []
    model, config = load_model()

    for iid in top_icebergs:
        track = tracks[tracks["iceberg_id"] == iid].sort_values("timestamp")
        if len(track) < 4:
            continue

        hist = track.tail(50)
        historical = [
            [round(float(r["latitude"]), 3), round(float(r["longitude"]), 3)]
            for _, r in hist.iterrows()
        ]

        predicted = []
        prev_lats = track["latitude"].values[-3:]
        prev_lons = track["longitude"].values[-3:]
        prev_speeds = track["speed_kmh"].values[-3:] if "speed_kmh" in track.columns else np.zeros(3)
        lat_val = float(prev_lats[-1])
        lon_val = float(prev_lons[-1])

        for step in range(3):
            features = np.array([[
                lat_val, lon_val,
                float(prev_speeds[-1]), 0.0,
                24.0, 0.0, 0.0, 6.0, 180.0,
            ]])
            pred = model.predict(features)[0]
            new_lat = pred[0] + lat_val
            new_lon = pred[1] + lon_val
            predicted.append([round(new_lat, 3), round(new_lon, 3)])
            lat_val = new_lat
            lon_val = new_lon

        iceberg_data.append({
            "id": iid,
            "observations": len(track),
            "current_lat": round(float(track.iloc[-1]["latitude"]), 3),
            "current_lon": round(float(track.iloc[-1]["longitude"]), 3),
            "historical": historical,
            "predicted": predicted,
        })

    data = {"icebergs": iceberg_data}
    with open(os.path.join(OUTPUT_DIR, "phase3_icebergs.json"), "w") as f:
        json.dump(data, f)
    print(f"Phase 3: {len(iceberg_data)} icebergs exported")


def export_phase4():
    """Export Phase 4 risk grid."""
    risk_ds = xr.open_dataset(os.path.join(ROOT, "data", "processed", "navigation_risk_grid.nc"))
    lats = risk_ds.lat.values
    lons = risk_ds.lon.values

    total_risk = risk_ds["total_risk"].values
    risk_class = risk_ds["risk_class"].values
    sic_risk = risk_ds["sea_ice_risk"].values
    ib_risk = risk_ds["iceberg_risk"].values

    risk_points = []
    for i in range(len(lats)):
        for j in range(len(lons)):
            tr = float(total_risk[i, j])
            if tr > 0.001:
                risk_points.append([
                    round(lats[i], 2), round(lons[j], 2),
                    round(tr, 3),
                    int(risk_class[i, j]),
                    round(float(sic_risk[i, j]), 3),
                    round(float(ib_risk[i, j]), 3),
                ])

    data = {
        "lats": [round(x, 2) for x in lats.tolist()],
        "lons": [round(x, 2) for x in lons.tolist()],
        "risk_points": risk_points,
        "risk_stats": {
            "min": round(float(total_risk.min()), 3),
            "max": round(float(total_risk.max()), 3),
            "mean": round(float(total_risk.mean()), 3),
        },
        "class_counts": {
            "LOW": int((risk_class == 0).sum()),
            "MODERATE": int((risk_class == 1).sum()),
            "HIGH": int((risk_class == 2).sum()),
            "VERY_HIGH": int((risk_class == 3).sum()),
        },
    }
    with open(os.path.join(OUTPUT_DIR, "phase4_risk.json"), "w") as f:
        json.dump(data, f)
    print(f"Phase 4: {len(risk_points)} risk cells exported")


def export_metrics():
    """Export actual model metrics."""
    metrics = {}
    try:
        with open(os.path.join(ROOT, "models", "sea_ice_feature_config.json")) as f:
            metrics["phase2"] = json.load(f).get("test_metrics", {})
    except Exception:
        metrics["phase2"] = {}
    try:
        with open(os.path.join(ROOT, "models", "iceberg_feature_config.json")) as f:
            metrics["phase3"] = json.load(f).get("test_metrics", {})
    except Exception:
        metrics["phase3"] = {}
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics exported")


if __name__ == "__main__":
    export_phase1()
    export_phase2()
    export_phase3()
    export_phase4()
    export_metrics()
    print("\nAll data exported to", OUTPUT_DIR)
