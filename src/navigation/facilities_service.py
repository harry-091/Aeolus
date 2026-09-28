"""Antarctic Facilities and Research Stations Service.

Authoritative source: COMNAP Antarctic Facilities Directory.
Provides station querying, filtering, geographic validation, and GeoJSON conversion.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FACILITIES_PATH = BASE_DIR / "data" / "processed" / "verification" / "comnap_antarctic_facilities.json"

logger = logging.getLogger("polarnav.facilities")


class AntarcticFacilitiesService:
    def __init__(self):
        self._facilities: List[Dict[str, Any]] = []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    def initialize(self):
        if self._initialized:
            return

        if FACILITIES_PATH.exists():
            with open(FACILITIES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._facilities = data.get("facilities", [])
                self._by_id = {f["id"]: f for f in self._facilities}
            logger.info(f"Loaded {len(self._facilities)} authoritative COMNAP Antarctic research facilities.")
        else:
            logger.warning(f"COMNAP facilities dataset not found at {FACILITIES_PATH}")
        self._initialized = True

    def get_stations(
        self,
        region: Optional[str] = None,
        operator: Optional[str] = None,
        coastal_only: bool = False,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search and filter Antarctic research stations."""
        self.initialize()
        results = self._facilities

        if coastal_only:
            results = [f for f in results if f.get("coastal_access", False)]

        if region:
            reg_clean = region.lower().replace("-", " ").replace("_", " ")
            results = [f for f in results if reg_clean in f.get("region", "").lower()]

        if operator:
            op_clean = operator.lower()
            results = [f for f in results if op_clean in f.get("operator", "").lower() or op_clean in f.get("country", "").lower()]

        if query:
            q_clean = query.lower()
            results = [
                f for f in results
                if q_clean in f.get("name", "").lower()
                or q_clean in f.get("id", "").lower()
                or q_clean in f.get("country", "").lower()
                or q_clean in f.get("region", "").lower()
            ]

        return results

    def get_station_by_id(self, station_id: str) -> Optional[Dict[str, Any]]:
        """Get a single research station by identifier."""
        self.initialize()
        if station_id in self._by_id:
            return self._by_id[station_id]
        
        # Fallback case-insensitive match
        for f in self._facilities:
            if f["id"].lower() == station_id.lower() or f["name"].lower() == station_id.lower():
                return f
        return None

    def validate_bharati_reference(self) -> Dict[str, Any]:
        """Validate Bharati station coordinates against authoritative NCPOR reference."""
        self.initialize()
        bharati = self.get_station_by_id("bharati")
        if not bharati:
            return {"valid": False, "error": "Bharati not found in dataset"}

        # NCPOR reference: 69° 24.41' S, 76° 11.72' E
        # Decimal: -(69 + 24.41/60) = -69.40683, (76 + 11.72/60) = 76.19533
        ref_lat = -(69.0 + 24.41 / 60.0)
        ref_lon = 76.0 + 11.72 / 60.0

        lat_diff = abs(bharati["latitude"] - ref_lat)
        lon_diff = abs(bharati["longitude"] - ref_lon)
        is_exact = lat_diff < 0.01 and lon_diff < 0.01

        return {
            "station_id": "bharati",
            "name": bharati["name"],
            "dataset_coordinates": [bharati["latitude"], bharati["longitude"]],
            "ncpor_reference_coordinates": [round(ref_lat, 4), round(ref_lon, 4)],
            "latitude_offset_degrees": round(lat_diff, 5),
            "longitude_offset_degrees": round(lon_diff, 5),
            "is_authoritative_match": is_exact,
            "operator": bharati["operator"],
            "region": bharati["region"]
        }

    def to_geojson(self, coastal_only: bool = False) -> Dict[str, Any]:
        """Convert Antarctic facilities to GeoJSON FeatureCollection for MapLibre rendering."""
        stations = self.get_stations(coastal_only=coastal_only)
        features = []
        for st in stations:
            features.append({
                "type": "Feature",
                "properties": {
                    "id": st["id"],
                    "name": st["name"],
                    "operator": st["operator"],
                    "country": st["country"],
                    "facility_type": st["facility_type"],
                    "status": st["status"],
                    "seasonality": st["seasonality"],
                    "region": st["region"],
                    "coastal_access": st.get("coastal_access", False),
                    "wharf_mooring": st.get("wharf_mooring", False),
                    "airfield": st.get("airfield", False),
                    "description": st.get("description", "")
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [st["longitude"], st["latitude"]]
                }
            })
        return {
            "type": "FeatureCollection",
            "features": features
        }


# Global singleton instance
facilities_service = AntarcticFacilitiesService()
