"""Continuous Live Monitoring Service (PolarNav Phase 11).

Maintains live voyage operational monitoring:
- Periodically checks updated satellite passes, SIC, icebergs, weather, and ocean currents
- Recalculates local risks and audits active route validity
- Filters out insignificant numerical noise
- Triggers automatic rerouting when safety thresholds are breached
- Maintains complete lineage: current route, previous route, reroute reason, timestamp
- Answers: "Why did POLARNAV change my route?"
"""
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from ..route_optimizer.optimizer import realtime_route_optimizer
from ..route_optimizer.models import (
    RealtimeOptimizedRoute,
    RouteOptimizationRequest,
    RouteProfileType,
)
from ..ml_risk.models import VesselCharacteristics, PolarIceClass
from .models import (
    RerouteTriggerType,
    MonitoringThresholds,
    RouteAuditResult,
    RerouteHistoryRecord,
    MonitoringStatusResponse,
    SimulateEventRequest,
)
from .detector import change_detector, ChangeDetector

logger = logging.getLogger("polarnav.monitoring")


class ContinuousMonitoringService:
    """Production real-time voyage monitoring service."""

    def __init__(self, detector: Optional[ChangeDetector] = None):
        self.detector = detector or change_detector
        self.current_route: Optional[RealtimeOptimizedRoute] = None
        self.previous_route: Optional[RealtimeOptimizedRoute] = None
        self.active_vessel: VesselCharacteristics = VesselCharacteristics()
        self.last_reroute_reason: Optional[str] = None
        self.why_changed_explanation: Optional[str] = None
        self.last_checked_iso: str = datetime.now(timezone.utc).isoformat()
        self.reroute_history: List[RerouteHistoryRecord] = []
        self.active_alerts: List[str] = []
        self.check_interval_seconds: float = 60.0
        self.is_monitoring_active: bool = False

    def set_active_voyage(
        self,
        route: RealtimeOptimizedRoute,
        vessel: Optional[VesselCharacteristics] = None,
    ) -> None:
        """Initialize or update the currently active voyage corridor under monitoring."""
        self.previous_route = self.current_route
        self.current_route = route
        if vessel is not None:
            self.active_vessel = vessel
        self.is_monitoring_active = True
        self.last_checked_iso = datetime.now(timezone.utc).isoformat()
        logger.info(f"Active monitoring set for route: {route.route_id} ({route.profile_type.value})")

    def check_and_update(
        self,
        vessel: Optional[VesselCharacteristics] = None,
        simulated_overrides: Optional[Dict[int, Dict[str, float]]] = None,
    ) -> RouteAuditResult:
        """Periodically audit the active route against fresh observations and trigger rerouting if required."""
        self.last_checked_iso = datetime.now(timezone.utc).isoformat()
        
        # Fallback to default active voyage if none exists yet
        if self.current_route is None:
            v_init = vessel or self.active_vessel
            req = RouteOptimizationRequest(
                origin=[-61.0, -58.0],
                destination=[-63.0, -55.0],
                vessel=v_init,
                profiles=[RouteProfileType.BALANCED],
            )
            res = realtime_route_optimizer.optimize_route(req)
            if res.routes:
                self.set_active_voyage(res.routes[0], v_init)

        active_vessel = vessel or self.active_vessel
        current = self.current_route

        # 1. Audit active route against live multi-sensor observations
        audit = self.detector.audit_route(
            route=current,
            vessel=active_vessel,
            simulated_overrides=simulated_overrides,
        )

        # 2. If valid and no safety breach, update ETA and local risk without rerouting
        if not audit.requires_reroute:
            logger.debug("Monitoring check: active route remains safe and valid. No reroute needed.")
            return audit

        # 3. If safety threshold breached, execute automatic reroute
        logger.warning(f"Monitoring check: Triggering reroute due to {audit.trigger.value}. Rationale: {audit.why_rerouted}")
        
        # Preserve previous route before replacement
        prev_route = self.current_route
        self.previous_route = prev_route

        # Determine origin for reroute (vessel's forward position or start)
        reroute_origin = current.origin
        reroute_dest = current.destination

        # Execute optimization with the revised dynamic cost surface
        opt_req = RouteOptimizationRequest(
            origin=reroute_origin,
            destination=reroute_dest,
            vessel=active_vessel,
            profiles=[current.profile_type],
        )
        opt_res = realtime_route_optimizer.optimize_route(opt_req)

        if opt_res.routes:
            new_route = opt_res.routes[0]
            self.current_route = new_route
            self.last_reroute_reason = audit.trigger.value
            self.why_changed_explanation = audit.why_rerouted

            # Record audit history
            rec_id = f"REROUTE-REC-{uuid.uuid4().hex[:8].upper()}"
            record = RerouteHistoryRecord(
                record_id=rec_id,
                timestamp_iso=datetime.now(timezone.utc).isoformat(),
                trigger=audit.trigger,
                primary_catalyst=audit.trigger.value,
                why_changed=audit.why_rerouted,
                previous_route_id=prev_route.route_id,
                new_route_id=new_route.route_id,
                previous_distance_km=prev_route.metrics.distance_km,
                new_distance_km=new_route.metrics.distance_km,
                delta_distance_km=round(new_route.metrics.distance_km - prev_route.metrics.distance_km, 2),
                previous_eta_hours=prev_route.metrics.eta_hours,
                new_eta_hours=new_route.metrics.eta_hours,
                delta_eta_hours=round(new_route.metrics.eta_hours - prev_route.metrics.eta_hours, 2),
                previous_risk_score=prev_route.metrics.estimated_risk_score,
                new_risk_score=new_route.metrics.estimated_risk_score,
            )
            self.reroute_history.append(record)

            # Emit active alert
            if audit.alert_banner:
                self.active_alerts.insert(0, audit.alert_banner)
                if len(self.active_alerts) > 10:
                    self.active_alerts = self.active_alerts[:10]

        return audit

    def simulate_event(
        self,
        event_type: str,
        waypoint_index: int = 1,
        delta_value: float = 25.0,
        vessel: Optional[VesselCharacteristics] = None,
    ) -> RouteAuditResult:
        """Inject a simulated dynamic environmental hazard to test reroute triggers."""
        overrides: Dict[str, float] = {}
        
        if event_type == "HIGH_SIC_INCREASE":
            base_sic = self.current_route.waypoints[waypoint_index].sic_pct if self.current_route and waypoint_index < len(self.current_route.waypoints) else 30.0
            overrides["sic_pct"] = min(100.0, base_sic + delta_value)
        elif event_type == "ICEBERG_PROXIMITY_BREACH":
            # Place an iceberg within the 12km safety buffer
            overrides["nearest_iceberg_km"] = max(2.0, delta_value if delta_value < 12.0 else 6.0)
        elif event_type == "SEVERE_WEATHER_ALERT":
            overrides["wind_speed_knots"] = 48.0
            overrides["wave_height_m"] = 5.2
        elif event_type == "UNSAFE_DEPTH_OR_GROUNDING":
            overrides["depth_m"] = 5.0  # Draft 8m -> UKC -3m
        elif event_type == "NOISE":
            # Insignificant fluctuation (+2% SIC)
            base_sic = self.current_route.waypoints[waypoint_index].sic_pct if self.current_route and waypoint_index < len(self.current_route.waypoints) else 20.0
            overrides["sic_pct"] = base_sic + 2.0

        return self.check_and_update(
            vessel=vessel,
            simulated_overrides={waypoint_index: overrides},
        )

    def get_status(self) -> MonitoringStatusResponse:
        """Retrieve full real-time monitoring status and explainability narrative."""
        current = self.current_route
        previous = self.previous_route

        return MonitoringStatusResponse(
            monitoring_active=self.is_monitoring_active,
            active_route_id=current.route_id if current else None,
            active_profile=current.profile_type if current else None,
            last_checked_iso=self.last_checked_iso,
            check_interval_seconds=self.check_interval_seconds,
            reroute_count=len(self.reroute_history),
            current_route=current,
            previous_route=previous,
            last_reroute_reason=self.last_reroute_reason,
            why_did_polarnav_change_my_route=self.why_changed_explanation or "Active corridor conforms to all safety thresholds.",
            active_alerts=self.active_alerts,
            recent_history=self.reroute_history[-5:],
        )


# Global singleton continuous monitoring service
continuous_monitoring_service = ContinuousMonitoringService()
