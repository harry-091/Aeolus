"""Combined Navigation Risk Engine for Phase 4.

Combines all available hazard layers into a single cost/risk grid
using configurable weights.

Prototype for SIH demonstration. NOT official maritime safety system.
"""
import json
import numpy as np
import xarray as xr


def load_config(path="configs/risk_config.json"):
    """Load risk configuration."""
    with open(path) as f:
        return json.load(f)


def risk_class_label(value, config=None):
    """Convert a normalized risk value to a risk class label.

    Args:
        value: float between 0 and 1.
        config: optional risk config.

    Returns:
        One of: LOW, MODERATE, HIGH, VERY_HIGH
    """
    if config is None:
        config = load_config()

    classes = config["risk_classes"]
    if value < classes["LOW"][1]:
        return "LOW"
    elif value < classes["MODERATE"][1]:
        return "MODERATE"
    elif value < classes["HIGH"][1]:
        return "HIGH"
    else:
        return "VERY_HIGH"


def risk_class_array(total_risk, config=None):
    """Convert a 2D risk array to integer class labels.

    0=LOW, 1=MODERATE, 2=HIGH, 3=VERY_HIGH

    Args:
        total_risk: 2D numpy array of normalized risk.
        config: optional risk config.

    Returns:
        2D integer array of risk classes.
    """
    if config is None:
        config = load_config()

    classes = config["risk_classes"]
    result = np.zeros_like(total_risk, dtype=int)
    result[total_risk >= classes["LOW"][1]] = 1
    result[total_risk >= classes["MODERATE"][1]] = 2
    result[total_risk >= classes["HIGH"][1]] = 3
    return result


def compute_total_risk(
    sea_ice_risk,
    iceberg_risk,
    weather_risk=None,
    ocean_risk=None,
    bathymetry_risk=None,
    config=None,
):
    """Combine risk layers into total navigation risk.

    Available layers are weighted. Weights are renormalized if
    optional layers are unavailable.

    Args:
        sea_ice_risk: 2D array, sea-ice risk (0-1).
        iceberg_risk: 2D array, iceberg risk (0-1).
        weather_risk: optional 2D array, weather risk (0-1).
        ocean_risk: optional 2D array, ocean risk (0-1).
        bathymetry_risk: optional 2D array, bathymetry risk (0-1).
        config: optional risk config.

    Returns:
        dict with keys:
            total_risk: 2D array (0-1)
            risk_class: 2D int array
            weights_used: dict of actual weights
            layers: dict of available layer arrays
            availability: dict of booleans
    """
    if config is None:
        config = load_config()

    weights = config["weights"]

    # Determine available layers
    availability = {
        "sea_ice": True,
        "iceberg": True,
        "weather": weather_risk is not None,
        "ocean": ocean_risk is not None,
        "bathymetry": bathymetry_risk is not None,
    }

    layers = {
        "sea_ice": np.asarray(sea_ice_risk, dtype=float),
        "iceberg": np.asarray(iceberg_risk, dtype=float),
    }
    if weather_risk is not None:
        layers["weather"] = np.asarray(weather_risk, dtype=float)
    if ocean_risk is not None:
        layers["ocean"] = np.asarray(ocean_risk, dtype=float)
    if bathymetry_risk is not None:
        layers["bathymetry"] = np.asarray(bathymetry_risk, dtype=float)

    # Collect available weights
    available_weights = {}
    for name in ["sea_ice", "iceberg", "weather", "ocean", "bathymetry"]:
        if availability[name]:
            available_weights[name] = weights[name]

    # Renormalize weights to sum to 1
    wsum = sum(available_weights.values())
    if wsum > 0:
        normalized_weights = {k: v / wsum for k, v in available_weights.items()}
    else:
        normalized_weights = {k: 1.0 / len(available_weights) for k in available_weights}

    # Weighted combination
    shape = sea_ice_risk.shape
    total = np.zeros(shape, dtype=float)
    for name, w in normalized_weights.items():
        total += w * layers[name]

    total = np.clip(total, 0.0, 1.0)

    return {
        "total_risk": total,
        "risk_class": risk_class_array(total, config),
        "weights_used": normalized_weights,
        "layers": layers,
        "availability": availability,
    }


def build_risk_dataset(
    grid_lats,
    grid_lons,
    sea_ice_risk,
    iceberg_risk,
    weather_risk=None,
    ocean_risk=None,
    bathymetry_risk=None,
    timestamp=None,
    config=None,
):
    """Build a complete xarray Dataset of the risk grid.

    Args:
        grid_lats: 1D latitude array.
        grid_lons: 1D longitude array.
        sea_ice_risk: 2D sea-ice risk array.
        iceberg_risk: 2D iceberg risk array.
        weather_risk: optional 2D weather risk.
        ocean_risk: optional 2D ocean risk.
        bathymetry_risk: optional 2D bathymetry risk.
        timestamp: optional timestamp string.
        config: optional risk config.

    Returns:
        xr.Dataset with all risk layers and total risk.
    """
    result = compute_total_risk(
        sea_ice_risk, iceberg_risk, weather_risk, ocean_risk, bathymetry_risk, config
    )

    ds = xr.Dataset(
        {
            "sea_ice_risk": (["lat", "lon"], result["layers"]["sea_ice"]),
            "iceberg_risk": (["lat", "lon"], result["layers"]["iceberg"]),
            "total_risk": (["lat", "lon"], result["total_risk"]),
            "risk_class": (["lat", "lon"], result["risk_class"]),
        },
        coords={
            "lat": grid_lats,
            "lon": grid_lons,
        },
        attrs={
            "description": "Dynamic Antarctic Navigation Risk Grid",
            "weights": str(result["weights_used"]),
            "availability": str(result["availability"]),
            "note": "Prototype for SIH demonstration. NOT official maritime safety.",
        },
    )

    if "weather" in result["layers"]:
        ds["weather_risk"] = (["lat", "lon"], result["layers"]["weather"])
    if "ocean" in result["layers"]:
        ds["ocean_risk"] = (["lat", "lon"], result["layers"]["ocean"])
    if "bathymetry" in result["layers"]:
        ds["bathymetry_risk"] = (["lat", "lon"], result["layers"]["bathymetry"])

    if timestamp is not None:
        ds.attrs["timestamp"] = timestamp

    return ds
