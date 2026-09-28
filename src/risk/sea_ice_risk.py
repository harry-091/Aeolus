"""Sea-ice risk layer for Phase 4.

Converts predicted SIC into normalized navigation risk (0-1).

Prototype thresholds documented in configs/risk_config.json.
These are NOT official maritime safety thresholds.
"""
import json
import numpy as np
import xarray as xr


def load_config(path="configs/risk_config.json"):
    """Load risk configuration."""
    with open(path) as f:
        return json.load(f)


def sic_to_risk(sic, config=None):
    """Convert sea-ice concentration to navigation risk.

    Higher SIC => higher risk. Monotonic transformation.

    Args:
        sic: array-like of SIC values (0-1).
        config: optional risk config dict.

    Returns:
        array-like of risk values (0-1).
    """
    if config is None:
        config = load_config()

    thresholds = config["sea_ice_thresholds"]
    low_max = thresholds["low_max"]
    mod_max = thresholds["moderate_max"]
    high_max = thresholds["high_max"]

    sic = np.asarray(sic, dtype=float)
    risk = np.zeros_like(sic)

    # LOW: SIC 0 to low_max => risk 0 to 0.25
    mask_low = sic <= low_max
    risk[mask_low] = 0.25 * (sic[mask_low] / low_max)

    # MODERATE: low_max to mod_max => risk 0.25 to 0.50
    mask_mod = (sic > low_max) & (sic <= mod_max)
    frac_mod = (sic[mask_mod] - low_max) / (mod_max - low_max)
    risk[mask_mod] = 0.25 + 0.25 * frac_mod

    # HIGH: mod_max to high_max => risk 0.50 to 0.75
    mask_high = (sic > mod_max) & (sic <= high_max)
    frac_high = (sic[mask_high] - mod_max) / (high_max - mod_max)
    risk[mask_high] = 0.50 + 0.25 * frac_high

    # VERY HIGH: > high_max => risk 0.75 to 1.0
    mask_vhigh = sic > high_max
    frac_vhigh = np.clip((sic[mask_vhigh] - high_max) / (1.0 - high_max), 0, 1)
    risk[mask_vhigh] = 0.75 + 0.25 * frac_vhigh

    return risk


def compute_sea_ice_risk_layer(sic_values):
    """Compute the sea-ice risk layer as an xarray DataArray.

    Args:
        sic_values: xr.DataArray of SIC values (0-1).

    Returns:
        xr.DataArray of sea-ice risk (0-1).
    """
    risk_data = sic_to_risk(sic_values.values)
    return xr.DataArray(
        risk_data,
        dims=sic_values.dims,
        coords=sic_values.coords,
        attrs={
            "name": "sea_ice_risk",
            "description": "Navigation risk from sea-ice concentration",
            "units": "normalized 0-1",
            "note": "Prototype thresholds for SIH demonstration",
        },
    )
