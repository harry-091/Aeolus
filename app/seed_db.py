"""
PolarNav PostgreSQL Seeding & Migration Utility
Seeds all real scientific datasets (vessels, stations, 85 icebergs, routes, alerts, reports)
into the PostgreSQL database.
"""

import json
import logging
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
for _p in [str(BACKEND_DIR), str(BACKEND_DIR / "src"), str(ROOT_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from backend.app.data_transformer import (
        _load_json,
        get_alerts,
        get_icebergs,
        get_reports,
        get_routes,
        get_vessels,
    )
    from backend.app.db import (
        AlertEntity,
        Base,
        IcebergEntity,
        ReportEntity,
        RouteEntity,
        StationEntity,
        VesselEntity,
        check_db_connection,
        get_database_url,
        get_db_engine,
        get_db_session,
    )
except ImportError:
    from app.data_transformer import (
        _load_json,
        get_alerts,
        get_icebergs,
        get_reports,
        get_routes,
        get_vessels,
    )
    from app.db import (
        AlertEntity,
        Base,
        IcebergEntity,
        ReportEntity,
        RouteEntity,
        StationEntity,
        VesselEntity,
        check_db_connection,
        get_database_url,
        get_db_engine,
        get_db_session,
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("polarnav.seed")


def seed_database():
    """Create tables and migrate data into PostgreSQL."""
    db_url = get_database_url()
    if not db_url:
        logger.error("No DATABASE_URL or POSTGRES_* environment variables found.")
        logger.info("Please set DATABASE_URL=postgresql://user:pass@localhost:5432/polarnav")
        return False

    engine = get_db_engine()
    if not engine:
        logger.error("Failed to connect to PostgreSQL engine.")
        return False

    logger.info("Creating PostgreSQL tables (polar_vessels, polar_stations, polar_icebergs, polar_routes, polar_alerts, polar_reports)...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully.")

    session = get_db_session()
    if not session:
        logger.error("Could not obtain database session.")
        return False

    try:
        # 1. Seed Vessels
        vessels_list = get_vessels()
        for v in vessels_list:
            v_id = v.get("id")
            entity = session.query(VesselEntity).filter_by(id=v_id).first() or VesselEntity(id=v_id)
            entity.name = v.get("name", "Vessel")
            entity.callsign = v.get("callsign")
            entity.mmsi = str(v.get("mmsi")) if v.get("mmsi") else None
            entity.flag = v.get("flag")
            entity.country = v.get("country")
            entity.polar_class = v.get("polar_class") or v.get("polarClass", "PC5")
            entity.latitude = float(v.get("latitude", -65.0))
            entity.longitude = float(v.get("longitude", 60.0))
            entity.speed_kn = float(v.get("speed", 12.0))
            entity.heading_deg = float(v.get("heading", 180.0))
            entity.destination = v.get("destination")
            entity.dest_lat = float(v.get("dest_lat")) if v.get("dest_lat") is not None else None
            entity.dest_lon = float(v.get("dest_lon")) if v.get("dest_lon") is not None else None
            entity.voyage_origin = v.get("voyage_origin")
            entity.status = v.get("status", "UNDERWAY")
            entity.is_live_ais = False
            session.add(entity)
        logger.info(f"Seeded {len(vessels_list)} vessels.")

        # 2. Seed Stations (COMNAP directory)
        from src.navigation.facilities_service import facilities_service
        stations_list = facilities_service.get_stations()
        for s in stations_list:
            s_id = s.get("id")
            coords = s.get("coordinates", {})
            entity = session.query(StationEntity).filter_by(id=s_id).first() or StationEntity(id=s_id)
            entity.name = s.get("name", "Station")
            entity.country = s.get("country")
            entity.operator = s.get("operator")
            entity.latitude = float(coords.get("latitude", -65.0))
            entity.longitude = float(coords.get("longitude", -64.0))
            entity.elevation_m = float(coords.get("elevation_m", 0.0))
            entity.station_type = s.get("type", "ALL_YEAR")
            entity.is_coastal = bool(s.get("is_coastal", True))
            entity.region = s.get("region", "Antarctica")
            session.add(entity)
        logger.info(f"Seeded {len(stations_list)} COMNAP stations.")

        # 3. Seed Icebergs (All 85 Real Tracked Targets)
        iceberg_data = _load_json("phase3_icebergs.json")
        icebergs_list = iceberg_data.get("icebergs", []) if iceberg_data else []
        for ib in icebergs_list:
            ib_id = ib.get("id")
            entity = session.query(IcebergEntity).filter_by(id=ib_id).first() or IcebergEntity(id=ib_id)
            entity.name = ib.get("name", ib_id)
            entity.current_lat = float(ib.get("current_lat", -65.0))
            entity.current_lon = float(ib.get("current_lon", -64.0))
            entity.velocity_kn = float(ib.get("velocity", 0.25))
            
            # Extract clean numeric direction
            dir_str = str(ib.get("direction", "270"))
            dir_clean = "".join([c for c in dir_str if c.isdigit() or c == "."])
            entity.direction_deg = float(dir_clean) if dir_clean else 270.0

            entity.size_km = float(ib.get("size", 10.0))
            entity.risk_level = ib.get("risk", "CAUTION")
            entity.cpa_distance_km = float(ib.get("cpa_distance_km")) if ib.get("cpa_distance_km") is not None else None
            entity.time_to_cpa_hours = float(ib.get("time_to_cpa_hours")) if ib.get("time_to_cpa_hours") is not None else None
            entity.drift_forecast_json = json.dumps(ib.get("drift_forecast", {}))
            session.add(entity)
        logger.info(f"Seeded {len(icebergs_list)} BYU/NIC tracked icebergs.")

        # 4. Seed Routes
        routes_list = get_routes()
        for r in routes_list:
            r_id = r.get("id")
            entity = session.query(RouteEntity).filter_by(id=r_id).first() or RouteEntity(id=r_id)
            entity.vessel_id = r.get("vessel_id")
            entity.name = r.get("name", "Route")
            entity.route_type = "OPTIMAL" if r.get("recommended") else "ALTERNATIVE"
            entity.recommended = bool(r.get("recommended", False))
            entity.distance_km = float(r.get("distance_km", r.get("distance", 1000.0)))
            entity.eta_hours = float(r.get("eta_hours", 72.0))
            entity.rio_score = float(r.get("rioScore", r.get("rio_score", 8.4)))
            entity.ice_risk = r.get("iceRisk", "LOW")
            entity.iceberg_risk = r.get("icebergRisk", "LOW")
            entity.weather_risk = r.get("weatherRisk", "LOW")
            entity.fuel_consumption_mt = float(str(r.get("fuelConsumption", "50")).replace(" MT", "").strip() or 50.0)
            entity.path_geojson = json.dumps(r.get("path", []))
            entity.waypoints_json = json.dumps(r.get("waypoints", []))
            entity.costs_json = json.dumps(r.get("cost_breakdown", r.get("costs", {})))
            entity.decision_explanation = r.get("decision_explanation", r.get("reason"))
            session.add(entity)
        logger.info(f"Seeded {len(routes_list)} multi-objective routes.")

        # 5. Seed Alerts
        alerts_list = get_alerts()
        for a in alerts_list:
            a_id = a.get("id")
            entity = session.query(AlertEntity).filter_by(id=a_id).first() or AlertEntity(id=a_id)
            entity.category = a.get("category", "ICEBERG")
            entity.severity = a.get("severity", "CAUTION")
            entity.title = a.get("title", "Safety Alert")
            entity.description = a.get("description", "")
            entity.location_str = a.get("location")
            entity.time_relative = a.get("timeRelative", "Recent")
            entity.mitigation = a.get("mitigation")
            entity.target_id = a.get("targetId")
            entity.acknowledged = bool(a.get("acknowledged", False))
            session.add(entity)
        logger.info(f"Seeded {len(alerts_list)} safety alerts.")

        # 6. Seed Reports
        reports_list = get_reports()
        for rep in reports_list:
            rep_id = rep.get("id")
            entity = session.query(ReportEntity).filter_by(id=rep_id).first() or ReportEntity(id=rep_id)
            entity.vessel_id = rep.get("vessel_id")
            entity.vessel_name = rep.get("vessel_name", "Vessel")
            entity.departure_port = rep.get("departure_port")
            entity.destination_station = rep.get("destination_station")
            entity.voyage_status = rep.get("voyage_status", "IN_TRANSIT")
            entity.distance_traveled_km = float(rep.get("distance_traveled_km", 0.0))
            entity.fuel_consumed_mt = float(rep.get("fuel_consumed_mt", 0.0))
            entity.polaris_rio_status = rep.get("polaris_rio_status", "POLARIS_AUTHORIZED")
            entity.mean_rio = float(rep.get("mean_rio", 12.5))
            entity.log_summary = rep.get("log_summary")
            session.add(entity)
        logger.info(f"Seeded {len(reports_list)} voyage compliance reports.")

        session.commit()
        logger.info("All records committed to PostgreSQL successfully.")

        status = check_db_connection()
        logger.info(f"Final PostgreSQL Database Status: {json.dumps(status, indent=2)}")
        return True

    except Exception as e:
        session.rollback()
        logger.error(f"Seeding failed: {e}", exc_info=True)
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = seed_database()
    sys.exit(0 if success else 1)
