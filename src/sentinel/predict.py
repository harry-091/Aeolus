"""
Sentinel-1 SAR & Optical Inference Module.
Provides real-time iceberg detection, area segmentation, and sea-ice classification.
"""
import json
import joblib
import numpy as np
from scipy.ndimage import label as nd_label, center_of_mass
from pathlib import Path
import rasterio

from src.sentinel.preprocess import (
    calibrate_sar_sigma0,
    apply_lee_filter,
    compute_sar_texture_features,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "sentinel_sar_detector.joblib"
CONFIG_PATH = MODELS_DIR / "sentinel_feature_config.json"


def load_sentinel_model():
    """Load the trained Sentinel SAR detector model and config."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Sentinel model not found at {MODEL_PATH}. Please run train.py first.")
    model = joblib.load(MODEL_PATH)
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    return model, config


def detect_sar_icebergs(tif_path, min_pixel_size=4, max_pixel_size=2000, target_size=(512, 512)):
    """
    Perform SAR segmentation and iceberg target extraction from a Sentinel-1 GeoTIFF scene.

    Returns
    -------
    dict with:
      - detections: list of detected iceberg objects (centroid, area_km2, rcs_db, confidence, bbox)
      - total_icebergs: count of verified radar contacts
      - classified_grid: 2D classified map (0=water, 1=MIZ, 2=pack ice, 3=iceberg)
      - sea_ice_concentration: estimated scene sea-ice coverage percentage
    """
    model, config = load_sentinel_model()
    tif_path = Path(tif_path)

    with rasterio.open(tif_path) as src:
        arr = src.read(1, out_shape=target_size, resampling=rasterio.enums.Resampling.bilinear)

    # 1. Preprocess SAR backscatter and texture
    sigma0_db = calibrate_sar_sigma0(arr)
    filtered_db = apply_lee_filter(sigma0_db, size=5)
    text_feats = compute_sar_texture_features(filtered_db)

    # 2. Build feature matrix for inference
    feature_matrix = np.column_stack([
        text_feats["sigma0_db"].ravel(),
        filtered_db.ravel(),
        text_feats["local_mean"].ravel(),
        text_feats["local_std"].ravel(),
        text_feats["gradient_mag"].ravel(),
        text_feats["cfar_ratio"].ravel(),
        np.full(filtered_db.size, 0.70)  # Standard polar NDSI prior
    ])

    # 3. Model classification
    preds = model.predict(feature_matrix)
    probs = model.predict_proba(feature_matrix)
    
    classified_2d = preds.reshape(target_size)
    iceberg_mask = (classified_2d == 3).astype(int)

    # 4. Extract connected components for iceberg targets
    labeled_array, num_features = nd_label(iceberg_mask)
    detections = []

    pixel_res_km = 0.05  # Approximate 50m per downsampled pixel

    for fid in range(1, num_features + 1):
        component_mask = (labeled_array == fid)
        component_size = int(np.sum(component_mask))

        if min_pixel_size <= component_size <= max_pixel_size:
            cy, cx = center_of_mass(component_mask)
            y_indices, x_indices = np.where(component_mask)
            min_y, max_y = int(np.min(y_indices)), int(np.max(y_indices))
            min_x, max_x = int(np.min(x_indices)), int(np.max(x_indices))

            # Target radar cross section (peak sigma0)
            peak_rcs = float(np.max(sigma0_db[component_mask]))
            mean_rcs = float(np.mean(sigma0_db[component_mask]))

            # Probability of target class (Class 3)
            comp_indices = np.where(component_mask.ravel())[0]
            avg_conf = float(np.mean(probs[comp_indices, 3]))

            # Approximate physical dimensions
            area_km2 = round(component_size * (pixel_res_km ** 2), 3)
            length_km = round((max_y - min_y + 1) * pixel_res_km, 2)
            width_km = round((max_x - min_x + 1) * pixel_res_km, 2)

            detections.append({
                "target_id": f"SAR-IB-{len(detections)+1:03d}",
                "pixel_centroid": [round(float(cy), 1), round(float(cx), 1)],
                "bbox_pixels": [min_x, min_y, max_x, max_y],
                "area_km2": max(area_km2, 0.05),
                "dimensions_km": f"{length_km} x {width_km} km",
                "peak_sigma0_db": round(peak_rcs, 1),
                "mean_sigma0_db": round(mean_rcs, 1),
                "confidence": round(avg_conf, 3),
                "classification": "Tabular Iceberg" if area_km2 > 1.0 else "Bergy Bit / Ice Floe Contact"
            })

    # Sea-ice concentration = fraction of pixels in classes 1, 2, 3
    ice_pixels = np.sum(classified_2d >= 1)
    sic_percent = round((ice_pixels / classified_2d.size) * 100.0, 1)

    return {
        "scene_name": tif_path.name,
        "total_icebergs_detected": len(detections),
        "detections": detections,
        "sea_ice_concentration_pct": sic_percent,
        "class_breakdown": {
            "open_water_pct": round(float(np.mean(classified_2d == 0) * 100), 1),
            "marginal_ice_pct": round(float(np.mean(classified_2d == 1) * 100), 1),
            "pack_ice_pct": round(float(np.mean(classified_2d == 2) * 100), 1),
            "iceberg_targets_pct": round(float(np.mean(classified_2d == 3) * 100), 1),
        }
    }


def classify_sar_sea_ice(tif_path, target_size=(256, 256)):
    """Classify sea ice concentration from SAR scene."""
    res = detect_sar_icebergs(tif_path, target_size=target_size)
    return {
        "scene": Path(tif_path).name,
        "sea_ice_concentration": res["sea_ice_concentration_pct"],
        "class_breakdown": res["class_breakdown"],
        "total_icebergs": res["total_icebergs_detected"]
    }
