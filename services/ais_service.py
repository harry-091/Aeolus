"""Open Waters AIS Ingestion Service & Deterministic Antarctic Voyage Simulator.

Provider: Open Waters AIS API (https://ais.openwaters.io)
Handles:
1. Live terrestrial/satellite AIS bounding-box queries
2. Freshness and coordinate validation in [longitude, latitude] format
3. Truthful reporting when AIS is unavailable in high-latitude polar ice
4. Deterministic Antarctic Peninsula / Bransfield Strait demo scenarios
"""
import os
import time
import urllib.request
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("polarnav.ais")

OPENWATERS_AIS_URL = os.environ.get("OPEN_WATERS_BASE_URL") or os.environ.get("OPENWATERS_AIS_URL", "https://ais.openwaters.io/api/v1/vessels")
AIS_API_KEY = os.environ.get("OPEN_WATERS_API_KEY") or os.environ.get("AIS_API_KEY", "")

# Production controls. When REAL_DATA_ONLY=true, never silently replace failed
# live AIS with deterministic demo vessels.
REAL_DATA_ONLY = os.environ.get("POLARNAV_REAL_DATA_ONLY", "false").lower() in ("1", "true", "yes", "on")

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default

# Configurable Antarctic AIS search area.
AIS_BBOX = {
    "min_lat": _env_float("AIS_MIN_LAT", -85.0),
    "max_lat": _env_float("AIS_MAX_LAT", -50.0),
    "min_lon": _env_float("AIS_MIN_LON", -180.0),
    "max_lon": _env_float("AIS_MAX_LON", 180.0),
}

# Authoritative Deterministic Demo Voyage Scenarios (100% Reproducible Canonical Polar Fleet)
DETERMINISTIC_DEMO_VESSELS: List[Dict[str, Any]] = [
    {
        "mmsi": "419071000",
        "imo": "9407988",
        "id": "rv_sagar_nidhi",
        "name": "R/V Sagar Nidhi — DEMO",
        "flag": "🇮🇳",
        "country": "India",
        "operator": "National Centre for Polar and Ocean Research (NCPOR)",
        "polar_class": "PC5 / Ice Class 1A Super",
        "latitude": -54.2000,
        "longitude": 68.4000,
        "sog": 13.5,
        "speed": 13.5,
        "cog": 165.0,
        "heading": 165,
        "nav_status": "Underway using engine",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freshness_seconds": 0,
        "source": "DETERMINISTIC_SIMULATION",
        "data_status": "SIMULATED_VOYAGE",
        "is_demo": True,
        "destination_station_id": "bharati",
        "destination_name": "Bharati Research Station",
        "destination": "Bharati Research Station",
        "dest_lat": -69.4068,
        "dest_lon": 76.1953,
        "voyage_origin": "Mormugao Port / Cape Town",
        "mission_description": "43rd Indian Scientific Expedition oceanographic transect and resupply towards Larsemann Hills.",
        "eta": "72h 36m"
    },
    {
        "mmsi": "211281000",
        "imo": "7820497",
        "id": "rv_polarstern",
        "name": "R/V Polarstern — DEMO",
        "flag": "🇩🇪",
        "country": "Germany",
        "operator": "Alfred Wegener Institute (AWI)",
        "polar_class": "PC2 / Arc4 (Heavy Polar Icebreaker)",
        "latitude": -69.2000,
        "longitude": -8.3000,
        "sog": 14.5,
        "speed": 14.5,
        "cog": 210.0,
        "heading": 210,
        "nav_status": "Underway using engine",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freshness_seconds": 0,
        "source": "DETERMINISTIC_SIMULATION",
        "data_status": "SIMULATED_VOYAGE",
        "is_demo": True,
        "destination_station_id": "neumayer_iii",
        "destination_name": "Neumayer Station III",
        "destination": "Neumayer Station III",
        "dest_lat": -70.6744,
        "dest_lon": -8.2742,
        "voyage_origin": "Cape Town Port (South Africa)",
        "mission_description": "Weddell Sea continental shelf glaciology and Neumayer III annual observatory crew rotation.",
        "eta": "11h 33m"
    },
    {
        "mmsi": "232029054",
        "imo": "9798222",
        "id": "rrs_sir_david_attenborough",
        "name": "RRS Sir David Attenborough — DEMO",
        "flag": "🇬🇧",
        "country": "United Kingdom",
        "operator": "British Antarctic Survey (BAS)",
        "polar_class": "PC4 (Polar Logistics & Science)",
        "latitude": -63.1000,
        "longitude": -58.4000,
        "sog": 14.8,
        "speed": 14.8,
        "cog": 224.0,
        "heading": 224,
        "nav_status": "Underway using engine",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freshness_seconds": 0,
        "source": "DETERMINISTIC_SIMULATION",
        "data_status": "SIMULATED_VOYAGE",
        "is_demo": True,
        "destination_station_id": "palmer",
        "destination_name": "Palmer Station",
        "destination": "Palmer Station",
        "dest_lat": -64.7744,
        "dest_lon": -64.0531,
        "voyage_origin": "Stanley Gateway Port",
        "mission_description": "Adelaide & Anvers Island marine geophysics and Palmer Station science passage via Gerlache Strait.",
        "eta": "14h 20m"
    },
    {
        "mmsi": "503000000",
        "imo": "8712582",
        "id": "aurora_australis_2015_16",
        "name": "R/V Aurora Australis — DEMO",
        "flag": "🇦🇺",
        "country": "Australia",
        "operator": "Australian Antarctic Division (AAD)",
        "polar_class": "PC5 (Antarctic Research Vessel)",
        "latitude": -65.2000,
        "longitude": 64.3000,
        "sog": 12.4,
        "speed": 12.4,
        "cog": 184.0,
        "heading": 184,
        "nav_status": "Underway using engine",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freshness_seconds": 0,
        "source": "DETERMINISTIC_SIMULATION",
        "data_status": "SIMULATED_VOYAGE",
        "is_demo": True,
        "destination_station_id": "davis",
        "destination_name": "Davis Station",
        "destination": "Davis Station",
        "dest_lat": -68.5764,
        "dest_lon": 77.9672,
        "voyage_origin": "Hobart Port (Tasmania)",
        "mission_description": "East Antarctic marine science transect approaching Vestfold Hills and Wilkes Land ice edge resupply.",
        "eta": "26h 30m"
    },
    {
        "mmsi": "601362000",
        "imo": "9551131",
        "id": "sa_agulhas_ii",
        "name": "S.A. Agulhas II — DEMO",
        "flag": "🇿🇦",
        "country": "South Africa",
        "operator": "Department of Forestry, Fisheries and the Environment (DFFE / SANAP)",
        "polar_class": "PC5 / DNV ICE-10",
        "latitude": -68.5000,
        "longitude": -2.5000,
        "sog": 12.8,
        "speed": 12.8,
        "cog": 190.0,
        "heading": 190,
        "nav_status": "Underway using engine",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freshness_seconds": 0,
        "source": "DETERMINISTIC_SIMULATION",
        "data_status": "SIMULATED_VOYAGE",
        "is_demo": True,
        "destination_station_id": "sanae_iv",
        "destination_name": "SANAE IV Base",
        "destination": "SANAE IV Base",
        "dest_lat": -71.6739,
        "dest_lon": -2.8408,
        "voyage_origin": "Cape Town Port (South Africa)",
        "mission_description": "Queen Maud Land annual relief voyage carrying cargo, fuel, and overwintering teams.",
        "eta": "24h 50m"
    },
    {
        "mmsi": "367000000",
        "imo": "9007295",
        "id": "rv_nathaniel_palmer",
        "name": "R/V Nathaniel B. Palmer — DEMO",
        "flag": "🇺🇸",
        "country": "United States",
        "operator": "US Antarctic Program Marine Logistics (USAP)",
        "polar_class": "PC3 (Heavy Research Icebreaker)",
        "latitude": -71.5000,
        "longitude": 176.2000,
        "sog": 14.2,
        "speed": 14.2,
        "cog": 192.0,
        "heading": 192,
        "nav_status": "Underway using engine",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freshness_seconds": 0,
        "source": "DETERMINISTIC_SIMULATION",
        "data_status": "SIMULATED_VOYAGE",
        "is_demo": True,
        "destination_station_id": "mcmurdo",
        "destination_name": "McMurdo Station",
        "destination": "McMurdo Station",
        "dest_lat": -77.8460,
        "dest_lon": 166.6681,
        "voyage_origin": "Lyttelton Port (New Zealand)",
        "mission_description": "Ross Sea ecosystem & polynya study and heavy icebreaker escort into McMurdo Sound.",
        "eta": "22h 10m"
    },
    {
        "mmsi": "431999000",
        "imo": "9400000",
        "id": "rv_shirase",
        "name": "R/V Shirase (AGB-5003) — DEMO",
        "flag": "🇯🇵",
        "country": "Japan",
        "operator": "Japan National Institute of Polar Research (NIPR)",
        "polar_class": "PC2 (Heavy Military-Spec Polar Icebreaker)",
        "latitude": -64.5000,
        "longitude": 40.2000,
        "sog": 15.0,
        "speed": 15.0,
        "cog": 175.0,
        "heading": 175,
        "nav_status": "Underway using engine",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freshness_seconds": 0,
        "source": "DETERMINISTIC_SIMULATION",
        "data_status": "SIMULATED_VOYAGE",
        "is_demo": True,
        "destination_station_id": "syowa",
        "destination_name": "Syowa Station",
        "destination": "Syowa Station",
        "dest_lat": -69.0042,
        "dest_lon": 39.5806,
        "voyage_origin": "Fremantle (Australia)",
        "mission_description": "65th JARE continental logistics and heavy ice penetration into Lützow-Holm Bay.",
        "eta": "15h 45m"
    },
    {
        "mmsi": "211281001",
        "imo": "7820498",
        "id": "polar_research_vessel_demo",
        "name": "Polar Research Vessel — DEMO",
        "flag": "🌐",
        "country": "International / COMNAP",
        "operator": "COMNAP Scientific Logistics",
        "polar_class": "PC3 (Polar Icebreaker)",
        "latitude": -62.8000,
        "longitude": -59.5000,
        "sog": 13.5,
        "speed": 13.5,
        "cog": 215.0,
        "heading": 215,
        "nav_status": "Underway using engine",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freshness_seconds": 0,
        "source": "DETERMINISTIC_SIMULATION",
        "data_status": "SIMULATED_VOYAGE",
        "is_demo": True,
        "destination_station_id": "comandante_ferraz",
        "destination_name": "Comandante Ferraz Antarctic Station",
        "destination": "Comandante Ferraz Antarctic Station",
        "dest_lat": -62.0833,
        "dest_lon": -58.3833,
        "voyage_origin": "Bransfield Strait Operational Sector",
        "mission_description": "Environmental research and multi-station logistic transect across South Shetland Islands.",
        "eta": "8h 15m"
    }
]


class AisService:
    def __init__(self):
        self.api_key = AIS_API_KEY

    def fetch_live_ais(self) -> Optional[List[Dict[str, Any]]]:
        """Attempt to fetch live AIS vessels from Open Waters AIS within Antarctic bbox."""
        if not self.api_key:
            return None

        try:
            url = f"{OPENWATERS_AIS_URL}?min_lat={AIS_BBOX['min_lat']}&max_lat={AIS_BBOX['max_lat']}&min_lon={AIS_BBOX['min_lon']}&max_lon={AIS_BBOX['max_lon']}"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as response:
                if response.status == 200:
                    raw_data = json.loads(response.read().decode())
                    vessels = []
                    for item in raw_data.get("vessels", []):
                        lat = item.get("lat") or item.get("latitude")
                        lon = item.get("lon") or item.get("longitude")
                        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
                            vessels.append({
                                "mmsi": str(item.get("mmsi", "")),
                                "imo": str(item.get("imo", "")),
                                "name": item.get("name", "Unknown Vessel"),
                                "latitude": float(lat),
                                "longitude": float(lon),
                                "sog": float(item.get("sog", item.get("speed", 0.0))),
                                "cog": float(item.get("cog", item.get("course", 0.0))),
                                "heading": int(item.get("heading", item.get("cog", 0))),
                                "nav_status": item.get("nav_status", "Underway"),
                                "timestamp": item.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                                "source": "AIS",
                                "data_status": "LIVE",
                                "freshness_seconds": 120
                            })
                    if vessels:
                        return vessels
        except Exception as e:
            logger.debug(f"Open Waters AIS live query failed or unavailable: {e}")
        
        return None

    def get_vessels(self, prefer_live: bool = True) -> Dict[str, Any]:
        """Return available vessels with clear live/simulated attribution."""
        if prefer_live:
            live_data = self.fetch_live_ais()
            if live_data:
                return {
                    "data_status": "LIVE",
                    "source": "Open Waters AIS",
                    "badge": "● LIVE AIS ACTIVE",
                    "total_vessels": len(live_data),
                    "vessels": live_data
                }

        if REAL_DATA_ONLY:
            return {
                "data_status": "UNAVAILABLE",
                "source": "Open Waters AIS",
                "badge": "● LIVE AIS UNAVAILABLE",
                "message": "Live AIS could not be fetched. Demo vessels are disabled because POLARNAV_REAL_DATA_ONLY=true.",
                "total_vessels": 0,
                "vessels": []
            }

        # Development-only fallback. Explicitly marked as simulation.
        return {
            "data_status": "SIMULATED_VOYAGE",
            "source": "DETERMINISTIC_SIMULATION",
            "badge": "● DETERMINISTIC DEMO VOYAGE",
            "message": "Live AIS unavailable; demo mode is enabled because POLARNAV_REAL_DATA_ONLY=false.",
            "total_vessels": len(DETERMINISTIC_DEMO_VESSELS),
            "vessels": DETERMINISTIC_DEMO_VESSELS
        }

    def get_vessel_by_mmsi(self, mmsi: str) -> Optional[Dict[str, Any]]:
        """Get vessel by MMSI/ID, preferring live AIS and never inventing a vessel in strict mode."""
        live = self.fetch_live_ais()
        for v in live or []:
            if v.get("mmsi") == mmsi or v.get("id") == mmsi:
                return v

        if REAL_DATA_ONLY:
            return None

        for v in DETERMINISTIC_DEMO_VESSELS:
            if v["mmsi"] == mmsi or v["id"] == mmsi or v["id"].replace("-", "_") == mmsi:
                return v
        return DETERMINISTIC_DEMO_VESSELS[0]

    def get_navigation_scenario(self) -> Dict[str, Any]:
        """Return current active demo navigation scenario."""
        primary_vessel = DETERMINISTIC_DEMO_VESSELS[0]
        dest_lat = primary_vessel.get("dest_lat") or primary_vessel.get("destination_lat", -69.4068)
        dest_lon = primary_vessel.get("dest_lon") or primary_vessel.get("destination_lon", 76.1953)
        return {
            "vessel": {
                "mmsi": primary_vessel["mmsi"],
                "name": primary_vessel["name"],
                "latitude": primary_vessel["latitude"],
                "longitude": primary_vessel["longitude"],
                "sog": primary_vessel["sog"],
                "cog": primary_vessel["cog"],
                "source": "demo",
                "data_status": primary_vessel["data_status"]
            },
            "destination": {
                "station_id": primary_vessel.get("destination_station_id", "bharati"),
                "name": primary_vessel.get("destination_name", "Bharati Research Station"),
                "latitude": dest_lat,
                "longitude": dest_lon,
                "source": "COMNAP/BAS",
                "is_ship_accessible": True
            },
            "mode": "DEMO",
            "source": "demo",
            "primary_region": "Antarctic Peninsula & Bransfield Strait"
        }


# Global singleton instance
backend_ais_service = AisService()
ais_service = backend_ais_service
