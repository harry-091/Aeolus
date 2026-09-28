"""Normalization utilities for risk layers.

All risk layers are normalized to 0-1 before combination.
"""
import numpy as np
import xarray as xr


def normalize_risk(risk_array):
    """Normalize a risk array to [0, 1] range.

    Uses min-max normalization. Preserves relative ordering.

    Args:
        risk_array: xr.DataArray or np.ndarray.

    Returns:
        Normalized array with same shape.
    """
    if isinstance(risk_array, xr.DataArray):
        vals = risk_array.values
    else:
        vals = np.asarray(risk_array, dtype=float)

    vmin = np.nanmin(vals)
    vmax = np.nanmax(vals)

    if vmax == vmin:
        return np.zeros_like(vals)

    return (vals - vmin) / (vmax - vmin)
