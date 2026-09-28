"""
PolarNav Database Integration Layer
Connects to PostgreSQL / PostGIS with transparent fallback to local verified datasets.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    _cwd = Path(__file__).resolve().parent
    for _env_f in [_cwd.parent.parent / ".env", _cwd.parent / ".env"]:
        if _env_f.exists():
            load_dotenv(_env_f)
except ImportError:
    pass

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("polarnav.db")

Base = declarative_base()


# =============================================================================
# 1. DATABASE MODELS (PostgreSQL / PostGIS Relational Schema)
# =============================================================================

class VesselEntity(Base):
    """Antarctic Polar Fleet Vessel Telemetry."""
    __tablename__ = "polar_vessels"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    callsign = Column(String(128), nullable=True)
    mmsi = Column(String(128), nullable=True, index=True)
    flag = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    polar_class = Column(String(255), default="PC5")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_kn = Column(Float, default=12.0)
    heading_deg = Column(Float, default=180.0)
    destination = Column(String(255), nullable=True)
    dest_lat = Column(Float, nullable=True)
    dest_lon = Column(Float, nullable=True)
    voyage_origin = Column(String(255), nullable=True)
    status = Column(String(128), default="UNDERWAY")
    is_live_ais = Column(Boolean, default=False)
    fuel_capacity_mt = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StationEntity(Base):
    """COMNAP / BAS Antarctic Research Station Directory."""
    __tablename__ = "polar_stations"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    country = Column(String(64), nullable=True)
    operator = Column(String(128), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation_m = Column(Float, default=0.0)
    station_type = Column(String(32), default="ALL_YEAR")
    is_coastal = Column(Boolean, default=True)
    region = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class IcebergEntity(Base):
    """Tracked BYU/NIC & Sentinel-1A SAR Iceberg Targets."""
    __tablename__ = "polar_icebergs"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    current_lat = Column(Float, nullable=False)
    current_lon = Column(Float, nullable=False)
    velocity_kn = Column(Float, default=0.25)
    direction_deg = Column(Float, default=270.0)
    size_km = Column(Float, default=10.0)
    risk_level = Column(String(32), default="CAUTION")
    cpa_distance_km = Column(Float, nullable=True)
    time_to_cpa_hours = Column(Float, nullable=True)
    drift_forecast_json = Column(Text, nullable=True)
    source = Column(String(64), default="BYU/NIC + Sentinel-1A SAR")
    updated_at = Column(DateTime, default=datetime.utcnow)


class RouteEntity(Base):
    """Pareto-Optimal Multi-Objective Antarctic Navigation Corridors."""
    __tablename__ = "polar_routes"

    id = Column(String(64), primary_key=True, index=True)
    vessel_id = Column(String(64), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    route_type = Column(String(32), default="OPTIMAL")
    recommended = Column(Boolean, default=False)
    distance_km = Column(Float, nullable=False)
    eta_hours = Column(Float, nullable=False)
    rio_score = Column(Float, default=8.4)
    ice_risk = Column(String(32), default="LOW")
    iceberg_risk = Column(String(32), default="LOW")
    weather_risk = Column(String(32), default="LOW")
    fuel_consumption_mt = Column(Float, default=50.0)
    path_geojson = Column(Text, nullable=False)
    waypoints_json = Column(Text, nullable=True)
    costs_json = Column(Text, nullable=True)
    decision_explanation = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AlertEntity(Base):
    """Real-Time Safety & Polar Hazard Alerts."""
    __tablename__ = "polar_alerts"

    id = Column(String(64), primary_key=True, index=True)
    category = Column(String(32), default="ICEBERG")
    severity = Column(String(32), default="CAUTION")
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    location_str = Column(String(64), nullable=True)
    time_relative = Column(String(32), default="Recent")
    mitigation = Column(Text, nullable=True)
    target_id = Column(String(64), nullable=True)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReportEntity(Base):
    """IMO Polar Code Chapter 1.3 Compliance Voyage Reports."""
    __tablename__ = "polar_reports"

    id = Column(String(64), primary_key=True, index=True)
    vessel_id = Column(String(64), nullable=True, index=True)
    vessel_name = Column(String(128), nullable=False)
    departure_port = Column(String(128), nullable=True)
    destination_station = Column(String(128), nullable=True)
    voyage_status = Column(String(32), default="IN_TRANSIT")
    distance_traveled_km = Column(Float, default=0.0)
    fuel_consumed_mt = Column(Float, default=0.0)
    polaris_rio_status = Column(String(32), default="POLARIS_AUTHORIZED")
    mean_rio = Column(Float, default=12.5)
    log_summary = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# 2. CONNECTION MANAGER & CONFIGURATION
# =============================================================================

def get_database_url() -> Optional[str]:
    """
    Construct PostgreSQL database URL from environment variables.
    Supports either standard DATABASE_URL or individual POSTGRES_* credentials.
    """
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if url:
        # Normalize dialect to psycopg (psycopg 3)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    # Check individual credentials
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST")
    port = os.environ.get("POSTGRES_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB") or os.environ.get("POSTGRES_DATABASE", "polarnav")

    if user and host:
        auth = f"{user}:{password}@" if password else f"{user}@"
        return f"postgresql+psycopg://{auth}{host}:{port}/{dbname}"

    return None


_engine = None
_session_factory = None
_db_status_cache = None


def get_db_engine():
    """Get or initialize the SQLAlchemy engine."""
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    db_url = get_database_url()
    if not db_url:
        return None

    try:
        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"connect_timeout": 5}
        )
        _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        return _engine
    except Exception as e:
        logger.warning(f"[PolarNav DB] Could not initialize engine for {db_url}: {e}")
        return None


def get_db_session():
    """Provide a transactional database session context."""
    engine = get_db_engine()
    if not engine or not _session_factory:
        return None
    return _session_factory()


def check_db_connection() -> Dict[str, Any]:
    """
    Probe the PostgreSQL connection status and record counts.
    Returns status metadata. Never throws an exception.
    """
    db_url = get_database_url()
    if not db_url:
        return {
            "status": "NOT_CONFIGURED",
            "connected": False,
            "message": "DATABASE_URL or POSTGRES_* environment variables not configured. Operating in verified file pipeline mode.",
            "mode": "FILE_PIPELINE_FALLBACK"
        }

    engine = get_db_engine()
    if not engine:
        return {
            "status": "CONNECTION_FAILED",
            "connected": False,
            "message": "Failed to initialize SQLAlchemy database engine.",
            "mode": "FILE_PIPELINE_FALLBACK"
        }

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            if result != 1:
                raise ValueError("Unexpected ping response")

            # Check table counts if schema exists
            counts = {}
            for table in ["polar_vessels", "polar_stations", "polar_icebergs", "polar_routes", "polar_alerts", "polar_reports"]:
                try:
                    c = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                    counts[table] = c
                except Exception:
                    counts[table] = "TABLE_NOT_CREATED"

            # Parse sanitized host
            host_str = "postgres"
            if "@" in db_url:
                host_str = db_url.split("@")[-1].split("/")[0]

            return {
                "status": "CONNECTED",
                "connected": True,
                "host": host_str,
                "driver": "SQLAlchemy 2.0 + psycopg 3",
                "counts": counts,
                "mode": "POSTGRESQL_PRIMARY"
            }
    except Exception as e:
        return {
            "status": "OFFLINE",
            "connected": False,
            "error": str(e),
            "message": "PostgreSQL database configured but unreachable. Falling back safely to verified file pipeline.",
            "mode": "FILE_PIPELINE_FALLBACK"
        }
