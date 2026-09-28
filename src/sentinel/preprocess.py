"""
Sentinel-1 SAR and Sentinel-2 Optical Preprocessing & Feature Extraction.

Extracts calibrated backscatter sigma0 (dB), Lee speckle filtered backscatter,
local variance/texture, and optical NDSI features for ML classification.
"""
import numpy as np
from scipy.ndimage import uniform_filter
import rasterio
from pathlib import Path


def calibrate_sar_sigma0(dn_array):
    """
    Convert raw SAR Digital Numbers (DN) to calibrated backscatter sigma0 in decibels (dB).
    Sentinel-1 GRD calibrated backscatter:
    sigma0_dB = 20 * log10(DN + eps) - calibration_constant (65.0 dB)
    """
    dn = dn_array.astype(np.float32)
    eps = 1e-4
    sigma0_db = 20.0 * np.log10(np.maximum(dn, eps)) - 65.0
    return np.clip(sigma0_db, -40.0, 5.0)


def apply_lee_filter(img, size=5):
    """
    Apply Adaptive Lee Speckle Filter on SAR intensity array.
    Preserves edges while smoothing speckle noise in sea-ice clutter.
    """
    img_mean = uniform_filter(img, (size, size))
    img_sqr_mean = uniform_filter(img**2, (size, size))
    img_variance = np.maximum(img_sqr_mean - img_mean**2, 1e-5)

    overall_variance = np.var(img)
    if overall_variance == 0:
        return img

    img_weights = img_variance / (img_variance + overall_variance)
    img_output = img_mean + img_weights * (img - img_mean)
    return img_output


def compute_sar_texture_features(sigma0_db, window_size=7):
    """
    Extract spatial radar texture features (local mean, local variance, local gradient).
    Icebergs exhibit bright specular backscatter and high local variance compared to pack ice.
    """
    local_mean = uniform_filter(sigma0_db, size=window_size)
    local_sqr = uniform_filter(sigma0_db**2, size=window_size)
    local_var = np.maximum(local_sqr - local_mean**2, 0.0)
    local_std = np.sqrt(local_var)
    
    # Gradient magnitude for edge & ridge detection
    gy, gx = np.gradient(sigma0_db)
    grad_mag = np.sqrt(gx**2 + gy**2)

    # CFAR target-to-clutter ratio (TCR) in dB
    cfar_ratio = sigma0_db - local_mean

    return {
        "sigma0_db": sigma0_db,
        "local_mean": local_mean,
        "local_std": local_std,
        "gradient_mag": grad_mag,
        "cfar_ratio": cfar_ratio,
    }


def compute_ndsi(green_band, swir_band):
    """
    Normalized Difference Snow/Ice Index (NDSI) from Sentinel-2 Optical bands.
    NDSI = (B03_Green - B11_SWIR) / (B03_Green + B11_SWIR + eps)
    """
    g = green_band.astype(np.float32)
    s = swir_band.astype(np.float32)
    eps = 1e-6
    ndsi = (g - s) / (g + s + eps)
    return np.clip(ndsi, -1.0, 1.0)


def preprocess_sar_scene(tif_path, target_size=(512, 512)):
    """
    Load a Sentinel-1 GeoTIFF scene, resize if needed, and extract full feature tensor.
    """
    tif_path = Path(tif_path)
    if not tif_path.exists():
        raise FileNotFoundError(f"SAR GeoTIFF not found: {tif_path}")

    with rasterio.open(tif_path) as src:
        arr = src.read(
            1,
            out_shape=target_size,
            resampling=rasterio.enums.Resampling.bilinear
        )

    sigma0_db = calibrate_sar_sigma0(arr)
    filtered_db = apply_lee_filter(sigma0_db, size=5)
    features = compute_sar_texture_features(filtered_db)
    return features
