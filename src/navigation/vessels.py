"""Vessel configuration loader and validator."""
import json
import os


def load_vessels(path="configs/vessels.json"):
    """Load vessel configurations from JSON.

    Returns:
        list of vessel dicts.
    """
    with open(path) as f:
        data = json.load(f)
    return data.get("vessels", [])


def validate_vessel(vessel):
    """Validate a single vessel configuration.

    Returns:
        dict with valid (bool), errors (list).
    """
    errors = []
    required = ["id", "name", "type", "start", "destination"]
    for field in required:
        if field not in vessel:
            errors.append(f"Missing required field: {field}")

    if "start" in vessel:
        s = vessel["start"]
        if "lat" not in s or "lon" not in s:
            errors.append("Start missing lat/lon")
        elif not (-90 <= s.get("lat", 0) <= 90):
            errors.append(f"Start lat out of range: {s.get('lat')}")
        elif not (-180 <= s.get("lon", 0) <= 180):
            errors.append(f"Start lon out of range: {s.get('lon')}")

    if "destination" in vessel:
        d = vessel["destination"]
        if "lat" not in d or "lon" not in d:
            errors.append("Destination missing lat/lon")
        elif not (-90 <= d.get("lat", 0) <= 90):
            errors.append(f"Dest lat out of range: {d.get('lat')}")
        elif not (-180 <= d.get("lon", 0) <= 180):
            errors.append(f"Dest lon out of range: {d.get('lon')}")

    return {"valid": len(errors) == 0, "errors": errors}


def get_vessel(vessels, vessel_id):
    """Get a vessel by ID."""
    for v in vessels:
        if v["id"] == vessel_id:
            return v
    return None


def list_vessels(vessels):
    """Return summary list of vessels."""
    return [{"id": v["id"], "name": v["name"], "type": v["type"]} for v in vessels]
