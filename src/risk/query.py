"""Risk query and explainability for Phase 4.

Provides location-specific risk queries with component breakdown.
"""
import numpy as np
import xarray as xr
from src.risk.risk_engine import risk_class_label, load_config


def get_location_risk(risk_dataset, lat, lon, config=None):
    """Query risk at a specific location.

    Finds the nearest grid cell and returns component breakdown.

    Args:
        risk_dataset: xr.Dataset from build_risk_dataset.
        lat: target latitude.
        lon: target longitude.
        config: optional risk config.

    Returns:
        dict with component risks, total risk, and class.
    """
    if config is None:
        config = load_config()

    # Find nearest grid cell
    lat_idx = int(np.argmin(np.abs(risk_dataset.lat.values - lat)))
    lon_idx = int(np.argmin(np.abs(risk_dataset.lon.values - lon)))

    actual_lat = float(risk_dataset.lat.values[lat_idx])
    actual_lon = float(risk_dataset.lon.values[lon_idx])

    result = {
        "query_lat": lat,
        "query_lon": lon,
        "nearest_lat": actual_lat,
        "nearest_lon": actual_lon,
    }

    # Extract component risks
    components = {}
    for var in ["sea_ice_risk", "iceberg_risk", "weather_risk", "ocean_risk", "bathymetry_risk"]:
        if var in risk_dataset:
            val = float(risk_dataset[var].values[lat_idx, lon_idx])
            available = bool(risk_dataset[var].attrs.get("available", True))
            components[var] = {"value": val, "available": available}

    result["components"] = components

    # Total risk
    total = float(risk_dataset["total_risk"].values[lat_idx, lon_idx])
    result["total_risk"] = total
    result["risk_class"] = risk_class_label(total, config)

    # Rank contributors by risk value
    ranked = sorted(
        [(k, v["value"]) for k, v in components.items() if v["available"] and v["value"] > 0],
        key=lambda x: x[1],
        reverse=True,
    )
    result["main_contributors"] = [{"layer": k, "risk": v} for k, v in ranked[:3]]

    return result


def explain_risk(query_result):
    """Generate a human-readable risk explanation.

    Args:
        query_result: dict from get_location_risk.

    Returns:
        str with formatted explanation.
    """
    lines = []
    lines.append("=" * 50)
    lines.append("NAVIGATION RISK QUERY RESULT")
    lines.append("=" * 50)
    lines.append(f"  Query Location:  lat={query_result['query_lat']}, lon={query_result['query_lon']}")
    lines.append(f"  Nearest Grid:    lat={query_result['nearest_lat']}, lon={query_result['nearest_lon']}")
    lines.append("")

    for name, comp in query_result["components"].items():
        label = name.replace("_risk", "").replace("_", " ").title()
        status = f"{comp['value']:.3f}" if comp["available"] else "UNAVAILABLE"
        lines.append(f"  {label + ' Risk:':<25} {status}")

    lines.append("")
    lines.append(f"  {'TOTAL RISK:':<25} {query_result['total_risk']:.3f}")
    lines.append(f"  {'RISK CLASS:':<25} {query_result['risk_class']}")
    lines.append("")

    if query_result["main_contributors"]:
        lines.append("  Main Contributors:")
        for i, c in enumerate(query_result["main_contributors"], 1):
            label = c["layer"].replace("_risk", "").replace("_", " ").title()
            lines.append(f"    {i}. {label} ({c['risk']:.3f})")

    lines.append("=" * 50)
    return "\n".join(lines)
