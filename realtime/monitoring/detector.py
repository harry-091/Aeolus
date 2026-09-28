"""Change Detection and Noise Filtering Engine (PolarNav Phase 11).

Evaluates active route waypoints against updated multi-sensor telemetry:
- Filters out insignificant numerical noise to prevent route flapping
- Evaluates configurable safety thresholds across 7 threat vectors
- Synthesizes transparent human-understandable explanations answering:
  "Why did POLARNAV change my route?"
"""
import math
from typing import List, Dict, Tuple, Optional, Any

from ..state import maritime_state_manager, CurrentMaritimeState
from ..ml_risk.engine import vessel_ml_risk_engine
from ..ml_risk.models import VesselCharacteristics, RiskCategory
from ..bathymetry import navigation_geometry_service
from ..route_optimizer.models import RealtimeOptimizedRoute, RealtimeWaypoint
from .models import (
    RerouteTriggerType,
    MonitoringThresholds,
    EnvironmentalChange,
    RouteAuditResult,
)


class ChangeDetector:
    """Detects meaningful environmental changes along an active route,
    ignoring sensor noise and auditing safety thresholds.
    """

    def __init__(self, thresholds: Optional[MonitoringThresholds] = None):
        self.thresholds = thresholds or MonitoringThresholds()

    def audit_route(
        self,
        route: RealtimeOptimizedRoute,
        vessel: VesselCharacteristics,
        simulated_overrides: Optional[Dict[int, Dict[str, float]]] = None,
    ) -> RouteAuditResult:
        """Audit active route waypoints against current maritime state.
        
        Args:
            route: Currently active RealtimeOptimizedRoute
            vessel: Active vessel characteristics
            simulated_overrides: Optional test dictionary {wp_index: {param: value}}
        
        Returns:
            RouteAuditResult with validity, triggers, and 'Why Changed' narrative.
        """
        meaningful_changes: List[EnvironmentalChange] = []
        compromised_indices: List[int] = []
        primary_trigger = RerouteTriggerType.NO_CHANGE
        max_severity = "INFO"
        
        simulated_overrides = simulated_overrides or {}

        for wp in route.waypoints:
            i = wp.waypoint_index
            lat, lon = wp.latitude, wp.longitude
            overrides = simulated_overrides.get(i, {})

            # 1. Fetch fresh telemetry from multi-sensor state
            fresh_state = maritime_state_manager.get_current_state(lat=lat, lon=lon)
            cell = fresh_state.cell_state
            fresh_ml = vessel_ml_risk_engine.predict_risk(fresh_state, vessel)

            # Extract fresh parameters (allowing simulation overrides for verification)
            fresh_sic = float(overrides.get("sic_pct", cell.sic))
            fresh_wind = float(overrides.get("wind_speed_knots", cell.wind.speed_knots))
            fresh_wave = float(overrides.get("wave_height_m", cell.wave.height_m))
            fresh_depth = float(overrides.get("depth_m", navigation_geometry_service.get_depth(lat, lon)))
            fresh_ukc = fresh_depth - vessel.draft_m
            
            # Iceberg distance
            if "nearest_iceberg_km" in overrides:
                fresh_ib_dist = float(overrides["nearest_iceberg_km"])
            else:
                ib_risk = cell.iceberg_risk
                fresh_ib_dist = 999.0 if ib_risk == 0.0 else max(5.0, 50.0 * (1.0 - ib_risk))

            fresh_current = float(overrides.get("current_speed_knots", cell.current.speed_knots))
            fresh_conf = float(fresh_state.unified_environmental_confidence)

            # -------------------------------------------------------------
            # 2. Check Triggers with Noise Filtering Deadbands
            # -------------------------------------------------------------
            
            # A. Sea Ice Concentration (SIC) Surge
            delta_sic = fresh_sic - wp.sic_pct
            if abs(delta_sic) >= self.thresholds.sic_noise_floor_pct:
                is_meaningful = delta_sic >= self.thresholds.min_sic_delta_pct or fresh_sic > vessel.operational_constraints.max_allowed_sic_pct
                meaningful_changes.append(
                    EnvironmentalChange(
                        parameter="Sea Ice Concentration",
                        waypoint_index=i,
                        latitude=lat,
                        longitude=lon,
                        previous_value=wp.sic_pct,
                        current_value=fresh_sic,
                        delta=round(delta_sic, 1),
                        unit="%",
                        is_meaningful=is_meaningful,
                        description=f"SIC shifted {delta_sic:+.1f}% (from {wp.sic_pct:.1f}% to {fresh_sic:.1f}%)"
                    )
                )
                if is_meaningful:
                    compromised_indices.append(i)
                    if primary_trigger == RerouteTriggerType.NO_CHANGE:
                        primary_trigger = RerouteTriggerType.HIGH_SIC_INCREASE
                        max_severity = "WARNING"

            # B. Iceberg Proximity Buffer Breach
            if fresh_ib_dist < self.thresholds.min_iceberg_cpa_km:
                meaningful_changes.append(
                    EnvironmentalChange(
                        parameter="Iceberg Proximity",
                        waypoint_index=i,
                        latitude=lat,
                        longitude=lon,
                        previous_value=wp.nearest_iceberg_km,
                        current_value=fresh_ib_dist,
                        delta=round(fresh_ib_dist - wp.nearest_iceberg_km, 1),
                        unit="km",
                        is_meaningful=True,
                        description=f"Tracked iceberg drifted to {fresh_ib_dist:.1f} km (safety standoff: {self.thresholds.min_iceberg_cpa_km:.1f} km)"
                    )
                )
                compromised_indices.append(i)
                primary_trigger = RerouteTriggerType.ICEBERG_PROXIMITY_BREACH
                max_severity = "CRITICAL"

            # C. Severe Weather (Wind & Waves)
            delta_wind = fresh_wind - wp.wind_speed_knots
            delta_wave = fresh_wave - wp.wave_height_m
            is_weather_surge = (
                delta_wind >= self.thresholds.max_wind_delta_knots or
                delta_wave >= self.thresholds.max_wave_delta_m or
                fresh_wind > vessel.operational_constraints.max_wind_speed_knots or
                fresh_wave > vessel.operational_constraints.max_wave_height_m
            )
            if is_weather_surge:
                meaningful_changes.append(
                    EnvironmentalChange(
                        parameter="Weather Severity",
                        waypoint_index=i,
                        latitude=lat,
                        longitude=lon,
                        previous_value=wp.wind_speed_knots,
                        current_value=fresh_wind,
                        delta=round(delta_wind, 1),
                        unit="knots",
                        is_meaningful=True,
                        description=f"Wind increased to {fresh_wind:.1f} kn, waves to {fresh_wave:.1f} m"
                    )
                )
                compromised_indices.append(i)
                if primary_trigger in (RerouteTriggerType.NO_CHANGE, RerouteTriggerType.HIGH_SIC_INCREASE):
                    primary_trigger = RerouteTriggerType.SEVERE_WEATHER_ALERT
                    max_severity = "WARNING"

            # D. Unsafe Depth & Grounding Hazard
            if fresh_ukc < self.thresholds.min_ukc_clearance_m or navigation_geometry_service.is_land(lat, lon):
                meaningful_changes.append(
                    EnvironmentalChange(
                        parameter="Bathymetric Clearance",
                        waypoint_index=i,
                        latitude=lat,
                        longitude=lon,
                        previous_value=wp.under_keel_clearance_m,
                        current_value=fresh_ukc,
                        delta=round(fresh_ukc - wp.under_keel_clearance_m, 1),
                        unit="m",
                        is_meaningful=True,
                        description=f"Under-keel clearance degraded to {fresh_ukc:.1f} m (below {self.thresholds.min_ukc_clearance_m:.1f} m safety limit)"
                    )
                )
                compromised_indices.append(i)
                primary_trigger = RerouteTriggerType.UNSAFE_DEPTH_OR_GROUNDING
                max_severity = "CRITICAL"

            # E. Sensor Confidence Degradation (significant drop during transit)
            delta_conf = fresh_conf - wp.confidence
            if delta_conf <= -0.20 and fresh_conf < self.thresholds.min_confidence_floor:
                meaningful_changes.append(
                    EnvironmentalChange(
                        parameter="Sensor Confidence",
                        waypoint_index=i,
                        latitude=lat,
                        longitude=lon,
                        previous_value=wp.confidence,
                        current_value=fresh_conf,
                        delta=round(delta_conf, 2),
                        unit="score",
                        is_meaningful=True,
                        description=f"Sensor confidence degraded by {delta_conf:.2f} (from {wp.confidence:.2f} to {fresh_conf:.2f})"
                    )
                )
                compromised_indices.append(i)

        # -------------------------------------------------------------
        # 3. Determine Threat-Prioritized Trigger
        # Priority: Iceberg > Grounding > SIC Surge > Severe Weather > Current > Confidence
        # -------------------------------------------------------------
        detected_params = {c.parameter for c in meaningful_changes if c.is_meaningful}
        
        if "Iceberg Proximity" in detected_params:
            primary_trigger = RerouteTriggerType.ICEBERG_PROXIMITY_BREACH
            max_severity = "CRITICAL"
        elif "Bathymetric Clearance" in detected_params:
            primary_trigger = RerouteTriggerType.UNSAFE_DEPTH_OR_GROUNDING
            max_severity = "CRITICAL"
        elif "Sea Ice Concentration" in detected_params:
            primary_trigger = RerouteTriggerType.HIGH_SIC_INCREASE
            max_severity = "WARNING"
        elif "Weather Severity" in detected_params:
            primary_trigger = RerouteTriggerType.SEVERE_WEATHER_ALERT
            max_severity = "WARNING"
        elif "Sensor Confidence" in detected_params:
            primary_trigger = RerouteTriggerType.DATA_CONFIDENCE_DEGRADATION
            max_severity = "WARNING"
        else:
            primary_trigger = RerouteTriggerType.NO_CHANGE
            max_severity = "INFO"

        # -------------------------------------------------------------
        # 3. Formulate "Why did POLARNAV change my route?" Narrative
        # -------------------------------------------------------------
        requires_reroute = len(compromised_indices) > 0 and primary_trigger != RerouteTriggerType.NO_CHANGE
        is_valid = not requires_reroute

        why_narrative = self._synthesize_why_narrative(
            trigger=primary_trigger,
            compromised_indices=compromised_indices,
            changes=meaningful_changes,
            route=route,
        )

        alert_banner = None
        if requires_reroute:
            alert_banner = (
                f"[{max_severity}] AUTOMATIC REROUTE TRIGGERED: {primary_trigger.value}. "
                f"{len(compromised_indices)} waypoint(s) compromised. Diverting to preserve maritime safety."
            )

        return RouteAuditResult(
            is_valid=is_valid,
            requires_reroute=requires_reroute,
            trigger=primary_trigger,
            alert_severity=max_severity if requires_reroute else "INFO",
            meaningful_changes=meaningful_changes,
            compromised_waypoint_indices=sorted(list(set(compromised_indices))),
            why_rerouted=why_narrative,
            alert_banner=alert_banner,
        )

    def _synthesize_why_narrative(
        self,
        trigger: RerouteTriggerType,
        compromised_indices: List[int],
        changes: List[EnvironmentalChange],
        route: RealtimeOptimizedRoute,
    ) -> str:
        """Generate crystal-clear, transparent explanation answering:
        'Why did POLARNAV change my route?'
        """
        if trigger == RerouteTriggerType.NO_CHANGE:
            return "No rerouting required. Live telemetry confirms the active corridor remains safe, navigable, and optimal."

        compromised_str = f"waypoint(s) {', '.join(str(i) for i in sorted(list(set(compromised_indices))))}"
        
        # Filter changes related to the primary trigger
        trigger_changes = [c for c in changes if c.is_meaningful]

        if trigger == RerouteTriggerType.ICEBERG_PROXIMITY_BREACH:
            ib_change = next((c for c in trigger_changes if "Iceberg" in c.parameter), None)
            detail = ib_change.description if ib_change else "Iceberg drifted into safety standoff buffer."
            return (
                f"POLARNAV changed your route due to an ICEBERG PROXIMITY BREACH at {compromised_str}. "
                f"{detail} Rerouting steers the vessel around the obstacle's forward projected trajectory "
                f"to restore safe CPA clearance."
            )
        elif trigger == RerouteTriggerType.HIGH_SIC_INCREASE:
            sic_change = next((c for c in trigger_changes if "Sea Ice" in c.parameter), None)
            detail = sic_change.description if sic_change else "Sea ice concentration surged along the active track."
            return (
                f"POLARNAV changed your route due to a HIGH SEA ICE CONCENTRATION INCREASE at {compromised_str}. "
                f"{detail} Rerouting diverts into the marginal ice zone to avoid bespoke pack ice compression "
                f"and prevent hull entrapment."
            )
        elif trigger == RerouteTriggerType.SEVERE_WEATHER_ALERT:
            wx_change = next((c for c in trigger_changes if "Weather" in c.parameter), None)
            detail = wx_change.description if wx_change else "Severe wind/wave conditions developed."
            return (
                f"POLARNAV changed your route due to a SEVERE WEATHER ALERT at {compromised_str}. "
                f"{detail} Rerouting alters heading to reduce wave slamming and minimize structural icing risk."
            )
        elif trigger == RerouteTriggerType.UNSAFE_DEPTH_OR_GROUNDING:
            return (
                f"POLARNAV changed your route due to an UNSAFE DEPTH / GROUNDING HAZARD at {compromised_str}. "
                f"Bathymetric clearance fell below the vessel's required under-keel safety margin. "
                f"Rerouting immediately diverts into deep bathyal waters."
            )
        elif trigger == RerouteTriggerType.DATA_CONFIDENCE_DEGRADATION:
            return (
                f"POLARNAV changed your route due to DATA CONFIDENCE DEGRADATION. Critical telemetry layers expired "
                f"or sensor confidence degraded along the forward track. Rerouting shifts transit into well-surveyed "
                f"satellite corridors."
            )
        else:
            return f"POLARNAV changed your route to maintain operational safety under updated environmental conditions."


# Global singleton change detector
change_detector = ChangeDetector()
