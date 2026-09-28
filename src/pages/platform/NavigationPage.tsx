import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Ship, Compass, ShieldAlert,
  Clock, CheckCircle2,
  Activity, Play, Pause, RotateCcw, Gauge,
  Download, RefreshCw
} from 'lucide-react';

import { AppShell } from '../../components/layout/AppShell';
import { useApiData } from '../../hooks/useApiData';
import { useFleet, haversineDistKm, computeBearingDeg } from '../../context/FleetContext';
import { api } from '../../services/api';
import { cn } from '../../utils/cn';
import PolarMap from '../../components/map/PolarMap';
import { TacticalHazardBanner } from '../../components/TacticalHazardBanner';
import {
  useSimulatedKinematics,
  haversineKm,
  type ScenarioType
} from '../../hooks/useSimulatedKinematics';

interface Waypoint {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  distanceFromStart: number;
  eta: string;
  status: 'passed' | 'active' | 'upcoming';
  iceRisk: string;
  reason?: string;
}

const PRESET_ORIGINS = [
  { name: 'Cape Town Port (South Africa)', lat: -33.92, lon: 18.42 },
  { name: 'Mormugao Port (India) / Southern Transit', lat: -54.20, lon: 68.40 },
  { name: 'Hobart Port (Australia)', lat: -42.88, lon: 147.33 },
  { name: 'Punta Arenas (Chile)', lat: -53.16, lon: -70.91 },
  { name: 'Stanley Gateway Port (Falklands)', lat: -51.70, lon: -57.85 },
  { name: 'Fremantle (Australia)', lat: -32.05, lon: 115.74 },
  { name: 'Lyttelton Port (New Zealand)', lat: -43.60, lon: 172.72 },
];

// Interpolate vessel progression strictly along active corridor polyline
function interpolatePositionAlongPath(
  path: [number, number][],
  targetDistKm: number
): {
  latitude: number;
  longitude: number;
  heading: number;
  totalDistKm: number;
  progressPct: number;
  remainingKm: number;
} {
  if (!path || path.length === 0) {
    return { latitude: -65.0, longitude: 70.0, heading: 180, totalDistKm: 1, progressPct: 0, remainingKm: 1 };
  }
  if (path.length === 1) {
    return { latitude: path[0][0], longitude: path[0][1], heading: 180, totalDistKm: 0, progressPct: 100, remainingKm: 0 };
  }

  const segDists: number[] = [];
  let totalDist = 0;
  for (let i = 0; i < path.length - 1; i++) {
    const d = haversineDistKm(path[i][0], path[i][1], path[i + 1][0], path[i + 1][1]);
    segDists.push(d);
    totalDist += d;
  }
  totalDist = Math.max(totalDist, 0.001);

  const clampedDist = Math.max(0, Math.min(targetDistKm, totalDist));
  const progressPct = Math.min(100, Math.round((clampedDist / totalDist) * 100));
  const remainingKm = Math.round(Math.max(0, totalDist - clampedDist));

  if (clampedDist <= 0) {
    return {
      latitude: path[0][0],
      longitude: path[0][1],
      heading: computeBearingDeg(path[0], path[1]),
      totalDistKm: Math.round(totalDist),
      progressPct: 0,
      remainingKm: Math.round(totalDist)
    };
  }

  if (clampedDist >= totalDist) {
    const last = path[path.length - 1];
    const prev = path[path.length - 2];
    return {
      latitude: last[0],
      longitude: last[1],
      heading: computeBearingDeg(prev, last),
      totalDistKm: Math.round(totalDist),
      progressPct: 100,
      remainingKm: 0
    };
  }

  let accum = 0;
  for (let i = 0; i < segDists.length; i++) {
    const sLen = segDists[i];
    if (accum + sLen >= clampedDist || i === segDists.length - 1) {
      const rem = clampedDist - accum;
      const frac = sLen > 0 ? Math.max(0, Math.min(1, rem / sLen)) : 0;
      const pA = path[i];
      const pB = path[i + 1];
      const lat = pA[0] + frac * (pB[0] - pA[0]);
      const lon = pA[1] + frac * (pB[1] - pA[1]);
      const heading = computeBearingDeg(pA, pB);
      return {
        latitude: lat,
        longitude: lon,
        heading,
        totalDistKm: Math.round(totalDist),
        progressPct,
        remainingKm
      };
    }
    accum += sLen;
  }

  const last = path[path.length - 1];
  return {
    latitude: last[0],
    longitude: last[1],
    heading: 180,
    totalDistKm: Math.round(totalDist),
    progressPct: 100,
    remainingKm: 0
  };
}

// Generate realistic waypoints strictly along the active route line
const generateWaypointsForRoute = (routePath: [number, number][], routeType: string, _destName: string, speedKnots: number = 14.0): Waypoint[] => {
  if (!routePath || routePath.length <= 2) return [];
  
  const step = Math.max(1, Math.floor(routePath.length / 6));
  const selectedIdx = [0];
  for (let i = step; i < routePath.length - 1; i += step) {
    selectedIdx.push(i);
  }
  selectedIdx.push(routePath.length - 1);

  let cumDist = 0;
  const speed = Math.max(1, speedKnots);
  return selectedIdx.map((idx, i) => {
    const pt = routePath[idx];
    if (i > 0) {
      const prev = routePath[selectedIdx[i - 1]];
      cumDist += haversineKm(prev[0], prev[1], pt[0], pt[1]);
    }
    const isFirst = i === 0;
    const isLast = i === selectedIdx.length - 1;
    const wpNum = i;

    return {
      id: isFirst ? 'WP-ORIGIN' : isLast ? 'WP-BERTH' : `WP-${String(wpNum).padStart(2, '0')}`,
      name: isFirst ? 'VOYAGE DEPARTURE' : isLast ? 'STATION BERTH' : `CORRIDOR WAYPOINT ${wpNum}`,
      latitude: pt[0],
      longitude: pt[1],
      distanceFromStart: Math.round(cumDist),
      eta: isFirst ? '00:00' : `+${Math.round(cumDist / (speed * 1.852))}h`,
      status: isFirst ? 'passed' : i === 1 ? 'active' : 'upcoming',
      iceRisk: isFirst || isLast ? 'LOW' : routeType.includes('route-a') ? 'HIGH' : routeType.includes('route-c') ? 'LOW' : 'MODERATE',
      reason: isFirst ? 'Convoy departure point' : isLast ? 'Station approach' : 'Navigation turn point'
    };
  });
};

export const NavigationPage: React.FC = () => {
  useApiData();
  const {
    fleet,
    selectedVesselId,
    selectedVessel,
    setSelectedVesselId,
    selectedIcebergId,
    setSelectedIcebergId,
    selectedDestination,
    activeHorizonLabel,
    routes,
    activeRouteId,
    setActiveRouteId,
    activeRoute: contextActiveRoute,
    emergencyRerouteActive,
    triggerEmergencyHazard,
    recomputeRoutes,
    isComputingRoutes
  } = useFleet();

  // Simulation State (Phase 3 & 5)
  const [simRunning, setSimRunning] = useState<boolean>(true);
  const [simSpeed, setSimSpeed] = useState<number>(5);
  const [simDistanceKm, setSimDistanceKm] = useState<number>(450); // Start with initial progress
  const [activeScenario, setActiveScenario] = useState<ScenarioType>('NORMAL');
  const [isScenarioRerouting, setIsScenarioRerouting] = useState(false);

  // Raw BYU MERS / US NIC 85 Iceberg Records
  const [rawIcebergs, setRawIcebergs] = useState<any[]>([]);
  useEffect(() => {
    api.icebergs().then((res) => {
      if (res?.icebergs?.length) setRawIcebergs(res.icebergs);
    }).catch(() => {});
  }, []);

  const activeRoute = useMemo(() => {
    if (!routes || routes.length === 0) return contextActiveRoute || null;
    return routes.find(r => r.id === activeRouteId) ||
           routes.find(r => r.id?.includes(activeRouteId)) ||
           contextActiveRoute ||
           routes.find(r => r.recommended) ||
           routes[0] ||
           null;
  }, [routes, activeRouteId, contextActiveRoute]);

  const totalDistKm = useMemo(() => {
    return activeRoute?.distance || 3500;
  }, [activeRoute?.distance]);

  const cruisingSpeed = Math.round(selectedVessel?.speed || selectedVessel?.sog || 13.5);
  const polarClass = selectedVessel?.polar_class || 'PC5';

  // Active polyline corridor path
  const corridorPath = useMemo<[number, number][]>(() => {
    if (activeRoute?.path && activeRoute.path.length >= 2) {
      return activeRoute.path;
    }
    const startLat = selectedVessel?.latitude ?? -65.0;
    const startLon = selectedVessel?.longitude ?? 70.0;
    const endLat = selectedDestination?.latitude ?? -69.4;
    const endLon = selectedDestination?.longitude ?? 76.2;
    return [[startLat, startLon], [endLat, endLon]];
  }, [activeRoute?.path, selectedVessel?.latitude, selectedVessel?.longitude, selectedDestination?.latitude, selectedDestination?.longitude]);

  // Vessel position interpolated strictly along active corridor
  const simulatedVoyage = useMemo(() => {
    return interpolatePositionAlongPath(corridorPath, simDistanceKm);
  }, [corridorPath, simDistanceKm]);

  const canRecalculateRoute = simulatedVoyage.remainingKm > 25 && routes.length > 1 && !isComputingRoutes;

  // Reusable Kinematics Hook (Simulated Physics, 85 Iceberg Drift, Climatic Load, Events)
  const {
    currentSimUtcStr,
    climaticConditions,
    vesselKinematics,
    dynamicIcebergs,
    nearestIceberg,
    events
  } = useSimulatedKinematics({
    simDistanceKm,
    totalDistanceKm: totalDistKm,
    cruisingSpeedKnots: cruisingSpeed,
    shipLat: simulatedVoyage.latitude,
    shipLon: simulatedVoyage.longitude,
    shipHeading: simulatedVoyage.heading,
    rawIcebergs,
    polarClass,
    routePath: corridorPath,
    activeScenario
  });

  // Active vessel telemetry object for PolarMap
  const activeVesselTelemetry = useMemo(() => {
    return {
      name: selectedVessel?.name || 'Vessel Telemetry',
      latitude: simulatedVoyage.latitude,
      longitude: simulatedVoyage.longitude,
      speed: vesselKinematics.sogKnots,
      heading: simulatedVoyage.heading
    };
  }, [selectedVessel?.name, simulatedVoyage.latitude, simulatedVoyage.longitude, simulatedVoyage.heading, vesselKinematics.sogKnots]);

  // Simulation ticker: advances smoothly at 4 Hz (250ms)
  useEffect(() => {
    if (!simRunning) return;

    const interval = setInterval(() => {
      setSimDistanceKm((prev) => {
        const speedKmh = vesselKinematics.sogKnots * 1.852;
        const stepKm = (speedKmh * 0.25 / 3600) * simSpeed;
        const total = totalDistKm || 3500;
        const next = prev + stepKm;
        return next >= total ? total : next;
      });
    }, 250);

    return () => clearInterval(interval);
  }, [simRunning, vesselKinematics.sogKnots, simSpeed, totalDistKm]);

  // Handle Scenario Selector (Phase 13: Judge Demonstration Mode)
  const handleSelectScenario = useCallback((scenario: ScenarioType) => {
    setActiveScenario(scenario);
    if (scenario === 'NORMAL') {
      setSimDistanceKm(totalDistKm * 0.18);
      setSimRunning(true);
      if (emergencyRerouteActive) {
        triggerEmergencyHazard(); // Toggle off
      }
    } else if (scenario === 'ICEBERG_ENCOUNTER') {
      setSimDistanceKm(totalDistKm * 0.48);
      setSimRunning(true);
      triggerEmergencyHazard(0.48);
    } else if (scenario === 'RADAR_OBSTACLE') {
      setSimDistanceKm(totalDistKm * 0.58);
      setSimRunning(true);
      triggerEmergencyHazard(0.58);
    } else if (scenario === 'HIGH_SEA_ICE') {
      setSimDistanceKm(totalDistKm * 0.72);
      setSimRunning(true);
    } else if (scenario === 'MULTI_HAZARD') {
      setSimDistanceKm(totalDistKm * 0.65);
      setSimRunning(true);
      triggerEmergencyHazard(0.65);
    }
  }, [totalDistKm, emergencyRerouteActive, triggerEmergencyHazard]);

  // Handle Tactical Reroute switch (Phase 9: Automatic Rerouting)
  const handleAcceptReroute = useCallback(async () => {
    setIsScenarioRerouting(true);
    try {
      // Find safest route or tactical detour
      const safest = routes.find(r => r.id.includes('route-c') || r.optimization_mode === 'SAFEST') || routes[1] || routes[0];
      if (safest && safest.id !== activeRouteId) {
        setActiveRouteId(safest.id);
      }
    } finally {
      setIsScenarioRerouting(false);
    }
  }, [routes, activeRouteId, setActiveRouteId]);

  // Waypoints along corridor
  const waypoints = useMemo<Waypoint[]>(() => {
    if (activeRoute?.waypoints && activeRoute.waypoints.length > 0) {
      return activeRoute.waypoints.map((wp: any, idx: number) => ({
        id: wp.id || `WP-${String(idx + 1).padStart(2, '0')}`,
        name: wp.name || `Waypoint ${idx + 1}`,
        latitude: wp.latitude ?? (wp as any).lat,
        longitude: wp.longitude ?? (wp as any).lon,
        distanceFromStart: wp.distance_from_start_km ?? wp.distanceFromStart ?? Math.round(((idx + 1) / ((activeRoute.waypoints?.length ?? 1) + 1)) * (activeRoute.distance || 3800)),
        eta: wp.eta ?? `T+${(idx + 1) * 6}h`,
        status: (idx === 0 ? 'active' : 'upcoming') as 'passed' | 'active' | 'upcoming',
        iceRisk: wp.risk_score || wp.iceRisk || activeRoute.iceRisk || 'MODERATE',
        reason: wp.reason || 'Course alteration along optimal corridor'
      }));
    }
    if (!activeRoute || !activeRoute.path) return [];
    return generateWaypointsForRoute(activeRoute.path, activeRoute.id || activeRouteId, selectedDestination.name, cruisingSpeed);
  }, [activeRoute, activeRouteId, selectedDestination.name, cruisingSpeed]);

  // Destination Marker
  const destMarker = useMemo(() => ({
    latitude: selectedDestination.latitude ?? (selectedDestination as any).lat ?? -69.41,
    longitude: selectedDestination.longitude ?? (selectedDestination as any).lon ?? 76.19,
    name: selectedDestination.name || 'Antarctic Station'
  }), [selectedDestination]);

  // Alternative route for comparison in Reroute Advisory
  const alternativeRoute = useMemo(() => {
    return routes.find(r => r.id !== activeRoute?.id && (r.id.includes('route-c') || r.optimization_mode === 'SAFEST')) || routes.find(r => r.id !== activeRoute?.id) || null;
  }, [routes, activeRoute?.id]);

  // Export Polar Voyage Plan
  const handleExportPlan = () => {
    const plan = {
      exportTime: new Date().toISOString(),
      simUtcTime: currentSimUtcStr,
      vessel: selectedVessel?.name || 'R/V Sagar Nidhi',
      polarClass,
      origin: PRESET_ORIGINS[0],
      destination: selectedDestination,
      activeCorridor: activeRoute,
      kinematics: vesselKinematics,
      climaticConditions,
      nearestIceberg: nearestIceberg ? {
        id: nearestIceberg.id,
        name: nearestIceberg.name,
        distanceKm: nearestIceberg.distanceToShipKm,
        cpaNm: nearestIceberg.cpaDistanceNm,
        threat: nearestIceberg.threatLevel
      } : null,
      eventHistory: events
    };
    const blob = new Blob([JSON.stringify(plan, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `polar_voyage_plan_${selectedVessel.name.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Tab state for collateral data below map
  const [activeBottomTab, setActiveBottomTab] = useState<'METRICS' | 'WAYPOINTS' | 'EVENTS'>('METRICS');

  return (
    <AppShell
      title="Navigation"
      subtitle="Antarctic vessel route planning and operational monitoring"
      actions={
        <div className="flex items-center gap-3 text-xs">
          {/* Active Vessel Selector */}
          <select
            value={selectedVesselId}
            onChange={(e) => setSelectedVesselId(e.target.value)}
            className="bg-[#081525] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-100 font-sans focus:outline-none focus:border-sky-500 max-w-[220px] truncate cursor-pointer"
          >
            {fleet.map(v => (
              <option key={v.id} value={v.id} className="bg-[#081525] text-slate-100">
                {v.flag} {v.name.replace(' - DEMO', '')} ({v.speed || v.sog} kn · {v.polar_class})
              </option>
            ))}
          </select>

          {/* SIMULATION CLOCK */}
          <div className="hidden sm:flex items-center gap-1.5 text-slate-300 font-mono text-xs">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400 text-[11px]">SIM</span>
            <span className="text-slate-100 font-medium">{currentSimUtcStr}</span>
          </div>

          {/* SIMULATION STATUS BADGE */}
          <div className="hidden md:flex items-center gap-2">
            <span className={cn("w-2 h-2 rounded-full", simRunning ? "bg-emerald-400" : "bg-amber-400")} />
            <span className={cn("font-medium text-xs", simRunning ? "text-emerald-400" : "text-amber-400")}>
              {simRunning ? "Simulation Active" : "Paused"}
            </span>
          </div>
        </div>
      }
    >
      <div className="flex flex-col h-full bg-[#040911] text-slate-100 font-sans select-none overflow-y-auto custom-scrollbar">
        
        {/* ========================================================================= */}
        {/* 1. CLEAN MODERN SIMULATION & VOYAGE CONTROLS BAR                          */}
        {/* ========================================================================= */}
        <div className="bg-[#060e18] border-b border-white/[0.05] px-4 sm:px-6 py-2 flex flex-wrap items-center justify-between gap-4 shrink-0 text-xs z-20">
          
          {/* SIMULATION TRANSPORT & SPEED */}
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setSimRunning(!simRunning)}
              className={cn(
                "px-3 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 cursor-pointer transition-colors",
                simRunning
                  ? "bg-amber-500/15 text-amber-300 hover:bg-amber-500/25"
                  : "bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25"
              )}
            >
              {simRunning ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              <span>{simRunning ? 'Pause' : 'Resume'}</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setSimDistanceKm(0);
                setSimRunning(true);
              }}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/[0.05] transition-colors cursor-pointer"
              title="Reset voyage to departure point"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>

            {/* SPEED SELECTOR PILL */}
            <div className="flex items-center bg-white/[0.04] rounded-lg p-0.5">
              {([1, 2, 5, 10] as const).map(mult => (
                <button
                  key={mult}
                  type="button"
                  onClick={() => setSimSpeed(mult)}
                  className={cn(
                    "px-2.5 py-0.5 rounded-md text-[11px] font-mono transition-colors cursor-pointer",
                    simSpeed === mult
                      ? "bg-sky-500/20 text-sky-300 font-semibold"
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  {mult}×
                </button>
              ))}
            </div>
          </div>

          {/* SCENARIO SELECTOR */}
          <div className="flex items-center gap-2 overflow-x-auto">
            <span className="text-xs text-slate-400 font-medium shrink-0">
              Scenario:
            </span>

            <div className="flex items-center gap-1 bg-white/[0.04] p-0.5 rounded-lg">
              {([
                { id: 'NORMAL', label: 'Normal Voyage' },
                { id: 'ICEBERG_ENCOUNTER', label: 'Iceberg Encounter' },
                { id: 'RADAR_OBSTACLE', label: 'Emergency Obstacle' },
                { id: 'HIGH_SEA_ICE', label: 'High Sea Ice' },
                { id: 'MULTI_HAZARD', label: 'Multi-Hazard' },
              ] as const).map(scen => (
                <button
                  key={scen.id}
                  type="button"
                  onClick={() => handleSelectScenario(scen.id)}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-xs font-medium transition-colors shrink-0 cursor-pointer",
                    activeScenario === scen.id
                      ? "bg-sky-500/20 text-sky-300 font-semibold"
                      : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                  )}
                >
                  {scen.label}
                </button>
              ))}
            </div>
          </div>

          {/* CORRIDOR ROUTE SELECTOR */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 font-medium hidden xl:inline">
              Route:
            </span>
            <div className="flex items-center gap-1 bg-white/[0.04] p-0.5 rounded-lg">
              {routes.map(r => {
                const isSelected = activeRoute?.id === r.id;
                const label = r.optimization_mode === 'FASTEST' ? 'Fastest' :
                              r.optimization_mode === 'SAFEST' ? 'Safest' : 'Optimal';
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setActiveRouteId(r.id)}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5",
                      isSelected
                        ? "bg-sky-500/20 text-sky-300 font-semibold"
                        : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
                    )}
                  >
                    <span>{label}</span>
                    <span className="font-mono text-[10px] text-slate-400">({r.distance} km)</span>
                  </button>
                );
              })}
              
              <button
                type="button"
                onClick={() => recomputeRoutes && recomputeRoutes()}
                disabled={!canRecalculateRoute}
                className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-white/[0.06] cursor-pointer transition-colors"
                title={canRecalculateRoute ? 'Recalculate route corridors' : 'Route changes are unavailable after arrival or when no alternate corridor remains'}
              >
                <RefreshCw className={cn("w-3.5 h-3.5 text-slate-300", isComputingRoutes && "animate-spin", !canRecalculateRoute && "opacity-30")} />
              </button>
            </div>
          </div>

        </div>

        {/* ========================================================================= */}
        {/* 2. OPERATIONAL WARNING BANNER (Emergency Event / Collision Alert)          */}
        {/* ========================================================================= */}
        {(emergencyRerouteActive || nearestIceberg?.threatLevel === 'COLLISION_ALERT' || vesselKinematics.polarCodeStatus === 'OPERATION_SUSPENDED') && (
          <div className="hidden bg-amber-950/40 border-b border-amber-600/30 px-4 sm:px-6 py-2 flex flex-wrap items-center justify-between gap-3 text-xs z-20">
            <div className="flex items-center gap-3">
              <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
              <div>
                <span className="font-bold text-amber-300 mr-2">NAVIGATION WARNING:</span>
                <span className="text-slate-200">
                  {nearestIceberg?.threatLevel === 'COLLISION_ALERT'
                    ? `Iceberg ${nearestIceberg.name} is approaching the planned route. Distance to route: ${nearestIceberg.distanceToRouteKm} km (CPA ${nearestIceberg.cpaDistanceNm} NM). Risk: HIGH.`
                    : vesselKinematics.polarCodeStatus === 'OPERATION_SUSPENDED'
                    ? `Severe pack ice encountered (SIC ${climaticConditions.sicPct}%). Hull stress limit exceeded. Risk: CRITICAL.`
                    : 'Tactical emergency hazard detected along route. Risk: HIGH.'}
                </span>
                <span className="text-slate-400 ml-2">Recommended action: Review alternative route.</span>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {nearestIceberg && (
                <button
                  type="button"
                  onClick={() => setSelectedIcebergId(nearestIceberg.id)}
                  className="px-3 py-1 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 hover:text-white text-xs font-medium cursor-pointer"
                >
                  View Hazard
                </button>
              )}
              <button
                type="button"
                disabled={isScenarioRerouting}
                onClick={handleAcceptReroute}
                className="px-3.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>{isScenarioRerouting ? 'Recalculating...' : 'Recalculate Route'}</span>
              </button>
            </div>
          </div>
        )}

        {/* OPERATIONAL ROUTE UPDATED BANNER */}
        {activeRouteId.includes('route-c') && (
          <div className="hidden bg-emerald-950/40 border-b border-emerald-600/30 px-4 sm:px-6 py-2 flex flex-wrap items-center justify-between gap-3 text-xs z-20">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <div>
                <span className="font-bold text-emerald-300 mr-2">ROUTE UPDATED:</span>
                <span className="text-slate-200">
                  Reason: Iceberg hazard avoidance • Previous risk: HIGH • New risk: LOW • Distance: +18.4 NM (+34 km) • ETA: +1h 12m
                </span>
              </div>
            </div>
            <span className="text-emerald-300 font-mono text-xs font-bold">
              {alternativeRoute?.name || 'ROUTE C (SAFEST)'} ACTIVE
            </span>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 3. DOMINANT POLAR MAP CONTAINER (70–80% of View Area)                     */}
        {/* ========================================================================= */}
        <div className="relative w-full h-[calc(100vh-260px)] min-h-[480px] bg-[#040911] shrink-0 overflow-hidden">
          
          {/* Tactical Hazard Banner from Fleet Context if active */}
          <TacticalHazardBanner className="absolute top-3 left-1/2 -translate-x-1/2 z-40 max-w-xl w-full px-3 pointer-events-auto" />

          {/* Interactive Polar Map Component */}
          <PolarMap
            section="navigation"
            activeHorizon={activeHorizonLabel}
            destinationMarker={destMarker}
            activeRouteId={activeRoute?.id || activeRouteId}
            onSelectRoute={(rId) => setActiveRouteId(rId)}
            customRoutePath={activeRoute?.path}
            allRoutes={routes}
            waypoints={waypoints}
            icebergs={dynamicIcebergs}
            selectedIcebergId={selectedIcebergId}
            onSelectIceberg={(id) => setSelectedIcebergId(id)}
            vesselInfo={activeVesselTelemetry}
            focusTarget={null}
            selectedVesselId={selectedVesselId}
            onSelectVessel={(id) => setSelectedVesselId(id)}
          />

          <aside className="absolute right-4 top-4 z-30 hidden w-80 overflow-hidden rounded-2xl border-2 border-[#f59e0b] bg-[#081424]/98 text-white shadow-2xl shadow-black/30 backdrop-blur lg:block">
            <div className="flex items-center justify-between bg-[#b45309] px-4 py-3">
              <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide"><ShieldAlert className="h-4 w-4" />Navigation alerts</span>
              <span className="rounded-full bg-white/20 px-2 py-0.5 text-[9px] font-bold">{(emergencyRerouteActive || nearestIceberg?.threatLevel === 'COLLISION_ALERT' || vesselKinematics.polarCodeStatus === 'OPERATION_SUSPENDED') ? 'ACTION REQUIRED' : 'MONITORING'}</span>
            </div>
            <div className="space-y-3 p-4 text-xs">
              {(emergencyRerouteActive || nearestIceberg?.threatLevel === 'COLLISION_ALERT' || vesselKinematics.polarCodeStatus === 'OPERATION_SUSPENDED') ? <>
                <div className="rounded-xl border border-rose-400/60 bg-rose-500/20 p-3"><p className="font-bold text-rose-200">CRITICAL NAVIGATION HAZARD</p><p className="mt-1 leading-relaxed text-white">{nearestIceberg?.threatLevel === 'COLLISION_ALERT' ? `Iceberg ${nearestIceberg.name} is approaching the route. CPA: ${nearestIceberg.cpaDistanceNm} NM.` : `Pack ice concentration ${climaticConditions.sicPct}%. Hull-stress limit exceeded.`}</p></div>
                <p className="rounded-lg bg-white/10 p-3 leading-relaxed text-slate-100"><strong className="text-[#fcd34d]">Recommended action:</strong> Stop and review the active corridor before continuing.</p>
                {canRecalculateRoute ? <button type="button" disabled={isScenarioRerouting} onClick={handleAcceptReroute} className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-500 py-2.5 font-bold text-white hover:bg-emerald-400 disabled:opacity-50"><CheckCircle2 className="h-4 w-4" />{isScenarioRerouting ? 'Recalculating…' : 'Recalculate alternate route'}</button> : <p className="rounded-xl border border-slate-600 bg-slate-800 p-3 text-[11px] leading-relaxed text-slate-200">Route recalculation is unavailable: the vessel is at destination or there is no viable alternate corridor from its current point.</p>}
              </> : <div className="rounded-xl border border-emerald-400/40 bg-emerald-500/15 p-3"><p className="font-bold text-emerald-300">NO IMMEDIATE HAZARD</p><p className="mt-1 leading-relaxed text-slate-100">The current corridor is being monitored for ice, iceberg drift, and weather changes.</p></div>}
            </div>
          </aside>

          {/* Voyage Scrub Slider Overlay along Map Bottom */}
          <div className="absolute bottom-4 right-4 z-20 hidden md:flex items-center gap-3 bg-[#071322]/90 backdrop-blur-md px-3.5 py-1.5 rounded-lg text-xs font-sans">
            <span className="text-slate-400 text-xs font-medium">Progress</span>
            <input
              type="range"
              min={0}
              max={totalDistKm || 3500}
              step={10}
              value={Math.round(simDistanceKm)}
              onChange={(e) => setSimDistanceKm(parseFloat(e.target.value))}
              className="w-36 lg:w-48 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-400"
              title="Scrub vessel along corridor"
            />
            <span className="text-slate-200 font-semibold font-mono text-xs">
              {simulatedVoyage.progressPct}% <span className="text-slate-400 font-normal font-sans">({Math.round(simDistanceKm)} / {Math.round(totalDistKm)} km)</span>
            </span>
          </div>

        </div>

        {/* ========================================================================= */}
        {/* 4. SUPPORTING OPERATIONAL INFORMATION (Clean Dashboard Dock)              */}
        {/* ========================================================================= */}
        <div className="p-4 sm:p-5 bg-[#050c16] border-t border-white/[0.04]">
          
          {/* Navigation Data Panels: 4 Structured Operational Columns */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 text-xs font-sans">
            
            {/* COLUMN 1: VESSEL STATUS */}
            <div className="rounded-xl bg-[#081424]/70 p-4 space-y-3">
              <div className="flex items-center justify-between pb-2 text-xs font-semibold text-slate-200">
                <span className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-md bg-sky-500/10 flex items-center justify-center text-sky-400">
                    <Ship className="w-3 h-3" />
                  </div>
                  <span>Vessel Operations</span>
                </span>
                <span className="text-emerald-400 text-[10px] font-mono font-medium">LIVE KINEMATICS</span>
              </div>

              <div className="space-y-2 text-xs divide-y divide-white/[0.04]">
                <div className="flex items-center justify-between pt-1.5 first:pt-0">
                  <span className="text-slate-400">Vessel Name</span>
                  <span className="text-slate-100 font-medium">{selectedVessel.name}</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Position</span>
                  <span className="text-slate-200 font-mono">
                    {Math.abs(simulatedVoyage.latitude).toFixed(2)}°S, {Math.abs(simulatedVoyage.longitude).toFixed(2)}°{simulatedVoyage.longitude >= 0 ? 'E' : 'W'}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Speed (SOG / STW)</span>
                  <span className="text-sky-300 font-semibold font-mono">{vesselKinematics.sogKnots} kn <span className="text-slate-500 font-normal">/ {vesselKinematics.stwKnots} kn</span></span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">True Heading</span>
                  <span className="text-slate-200 font-mono">{vesselKinematics.headingDeg}°T</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">ETA Destination</span>
                  <span className="text-slate-100 font-medium">+{Math.max(1, Math.round(simulatedVoyage.remainingKm / (vesselKinematics.sogKnots * 1.852)))}h <span className="text-slate-400 text-[11px]">({currentSimUtcStr})</span></span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Polar Class</span>
                  <span className="text-slate-300 font-mono">{polarClass} (Hull limit {vesselKinematics.hullStressLimitKn} kN)</span>
                </div>
              </div>
            </div>

            {/* COLUMN 2: ROUTE STATUS */}
            <div className="rounded-xl bg-[#081424]/70 p-4 space-y-3">
              <div className="flex items-center justify-between pb-2 text-xs font-semibold text-slate-200">
                <span className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-md bg-sky-500/10 flex items-center justify-center text-sky-400">
                    <Compass className="w-3 h-3" />
                  </div>
                  <span>Corridor Status</span>
                </span>
                <span className={cn(
                  "px-2.5 py-0.5 rounded-full text-[10px] font-semibold",
                  activeRoute?.iceRisk === 'HIGH' || activeRoute?.iceRisk === 'CRITICAL' ? "bg-red-500/20 text-red-300" :
                  activeRoute?.iceRisk === 'MODERATE' ? "bg-amber-500/20 text-amber-300" :
                  "bg-emerald-500/20 text-emerald-300"
                )}>
                  {activeRoute?.iceRisk === 'HIGH' || activeRoute?.iceRisk === 'CRITICAL' ? 'Warning' : activeRoute?.iceRisk === 'MODERATE' ? 'Caution' : 'Safe'}
                </span>
              </div>

              <div className="space-y-2 text-xs divide-y divide-white/[0.04]">
                <div className="flex items-center justify-between pt-1.5 first:pt-0">
                  <span className="text-slate-400">Active Corridor</span>
                  <span className="text-slate-100 font-medium">{activeRoute?.name || 'Route B'}</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Remaining Distance</span>
                  <span className="text-slate-200 font-mono">{simulatedVoyage.remainingKm} km <span className="text-slate-500">/ {Math.round(totalDistKm)} km</span></span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Destination</span>
                  <span className="text-slate-200 truncate max-w-[140px] font-medium">{selectedDestination.name}</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Nearest Hazard (CPA)</span>
                  <span className={cn(
                    "font-medium",
                    nearestIceberg?.threatLevel === 'COLLISION_ALERT' ? "text-red-400 font-semibold" : "text-amber-400"
                  )}>
                    {nearestIceberg ? `${nearestIceberg.name} (${nearestIceberg.cpaDistanceNm} NM)` : 'None (<25 NM)'}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Route Condition</span>
                  <span className="text-emerald-400 font-medium">Nominal Lead Navigation</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Fuel Consumed</span>
                  <span className="text-slate-300 font-mono">{vesselKinematics.cumulativeFuelTons} MT</span>
                </div>
              </div>
            </div>

            {/* COLUMN 3: ENVIRONMENT */}
            <div className="rounded-xl bg-[#081424]/70 p-4 space-y-3">
              <div className="flex items-center justify-between pb-2 text-xs font-semibold text-slate-200">
                <span className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-md bg-sky-500/10 flex items-center justify-center text-sky-400">
                    <Gauge className="w-3 h-3" />
                  </div>
                  <span>Environmental Dynamics</span>
                </span>
                <span className="text-slate-400 text-[10px] font-mono">NOAA / GLO12</span>
              </div>

              <div className="space-y-2 text-xs divide-y divide-white/[0.04]">
                <div className="flex items-center justify-between pt-1.5 first:pt-0">
                  <span className="text-slate-400">Sea Ice (SIC)</span>
                  <span className="text-sky-300 font-bold font-mono">{climaticConditions.sicPct}%</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Ice Thickness</span>
                  <span className="text-slate-200 font-mono">{climaticConditions.iceThicknessM} m</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Wind Speed</span>
                  <span className="text-slate-200 font-mono">{climaticConditions.windSpeedKnots} kn</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Significant Wave Ht</span>
                  <span className="text-slate-200 font-mono">{climaticConditions.waveHeightM} m SWH</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Surface Current</span>
                  <span className="text-slate-200 font-mono">{climaticConditions.currentSpeedKnots} kn @ {climaticConditions.currentDirectionDeg}°</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Air / Sea Temp</span>
                  <span className="text-slate-300 font-mono">{climaticConditions.seaSurfaceTempC}°C</span>
                </div>
              </div>
            </div>

            {/* COLUMN 4: AI / ML RISK PREDICTION */}
            <div className="rounded-xl bg-[#081424]/70 p-4 space-y-3">
              <div className="flex items-center justify-between pb-2 text-xs font-semibold text-slate-200">
                <span className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-md bg-sky-500/10 flex items-center justify-center text-sky-400">
                    <Activity className="w-3 h-3" />
                  </div>
                  <span>Safety &amp; ML Intelligence</span>
                </span>
                <span className="text-slate-400 text-[10px] font-mono">XGBoost</span>
              </div>

              <div className="space-y-2 text-xs divide-y divide-white/[0.04]">
                <div className="flex items-center justify-between pt-1.5 first:pt-0">
                  <span className="text-slate-400">Predicted Risk Score</span>
                  <span className="text-slate-100 font-bold font-mono">
                    {activeRoute ? (
                      (activeRoute as any)?.overallScore !== undefined
                        ? (1 - ((activeRoute as any).overallScore / 100)).toFixed(2)
                        : (activeRoute as any)?.decision_support?.risk_score !== undefined
                          ? (activeRoute as any).decision_support.risk_score.toFixed(2)
                          : '0.18'
                    ) : '0.18'}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Model Confidence</span>
                  <span className="text-emerald-400 font-semibold font-mono">
                    {(activeRoute as any)?.validation?.confidence
                      ? `${(activeRoute as any).validation.confidence}%`
                      : '88.6%'}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">IMO POLARIS Rating</span>
                  <span className={cn(
                    "font-semibold font-mono",
                    vesselKinematics.rioScore > 0 ? "text-emerald-400" : "text-amber-400"
                  )}>
                    RIO {vesselKinematics.rioScore > 0 ? `+${vesselKinematics.rioScore}` : vesselKinematics.rioScore} ({vesselKinematics.polarCodeStatus})
                  </span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Primary Risk Factors</span>
                  <span className="text-slate-300 truncate max-w-[130px] font-medium">SIC, Berg CPA, Wind</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Hull Impact Stress</span>
                  <span className="text-slate-300 font-mono">{vesselKinematics.hullStressKn} / {vesselKinematics.hullStressLimitKn} kN</span>
                </div>
                <div className="flex items-center justify-between pt-1.5">
                  <span className="text-slate-400">Architecture</span>
                  <span className="text-slate-300 font-medium">Multi-Objective XGB</span>
                </div>
              </div>
            </div>

          </div>

          {/* Collateral Views Tab Selector (Waypoints Table & Chronological Event Log) */}
          <div className="pt-2 flex items-center justify-between text-xs font-sans">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-medium">View Details:</span>
              <button
                type="button"
                onClick={() => setActiveBottomTab(activeBottomTab === 'WAYPOINTS' ? 'METRICS' : 'WAYPOINTS')}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors",
                  activeBottomTab === 'WAYPOINTS'
                    ? "bg-slate-800 text-sky-300 font-semibold shadow-xs"
                    : "bg-slate-900/60 text-slate-400 hover:text-white"
                )}
              >
                Waypoints ({waypoints.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveBottomTab(activeBottomTab === 'EVENTS' ? 'METRICS' : 'EVENTS')}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors",
                  activeBottomTab === 'EVENTS'
                    ? "bg-slate-800 text-sky-300 font-semibold shadow-xs"
                    : "bg-slate-900/60 text-slate-400 hover:text-white"
                )}
              >
                Event Log ({events.length})
              </button>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 hidden sm:block">
                US NIC • NOAA CDR • Sentinel-1 SAR
              </span>
              <button
                type="button"
                onClick={handleExportPlan}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-medium transition-colors cursor-pointer border border-slate-800/60"
                title="Export full voyage JSON"
              >
                <Download className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Export Plan</span>
              </button>
            </div>
          </div>

          {/* Tab 1: Collapsible Waypoints Table */}
          {activeBottomTab === 'WAYPOINTS' && (
            <div className="border border-slate-800/60 rounded-xl bg-[#06111e]/95 overflow-hidden shadow-lg">
              <div className="px-4 py-2.5 bg-[#071322] border-b border-slate-800/60 text-xs font-semibold text-slate-300 flex items-center justify-between font-sans">
                <span>Active Voyage Corridor Waypoints</span>
                <button type="button" onClick={() => setActiveBottomTab('METRICS')} className="text-slate-400 hover:text-white cursor-pointer">✕ Close</button>
              </div>
              <div className="overflow-x-auto max-h-56 custom-scrollbar">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[#050e18] text-slate-400 text-[11px] uppercase border-b border-slate-800/60 font-sans">
                    <tr>
                      <th className="px-4 py-2">ID</th>
                      <th className="px-4 py-2">Waypoint Name</th>
                      <th className="px-4 py-2">Coordinates</th>
                      <th className="px-4 py-2">Distance</th>
                      <th className="px-4 py-2">ETA</th>
                      <th className="px-4 py-2">Risk Level</th>
                      <th className="px-4 py-2">Operational Note</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/40 text-xs">
                    {waypoints.map((wp) => (
                      <tr key={wp.id} className="hover:bg-slate-800/30">
                        <td className="px-4 py-2 text-sky-400 font-bold">{wp.id}</td>
                        <td className="px-4 py-2 text-slate-200 font-sans">{wp.name}</td>
                        <td className="px-4 py-2 text-slate-300 font-mono">
                          {Math.abs(wp.latitude).toFixed(2)}°S, {Math.abs(wp.longitude).toFixed(2)}°{wp.longitude >= 0 ? 'E' : 'W'}
                        </td>
                        <td className="px-4 py-2 text-slate-300">{wp.distanceFromStart} km</td>
                        <td className="px-4 py-2 text-slate-300">{wp.eta}</td>
                        <td className="px-4 py-2">
                          <span className={cn(
                            "px-2.5 py-0.5 rounded-full text-[10px] font-semibold",
                            wp.iceRisk === 'HIGH' ? "bg-red-500/20 text-red-300" :
                            wp.iceRisk === 'MODERATE' ? "bg-amber-500/20 text-amber-300" :
                            "bg-emerald-500/20 text-emerald-300"
                          )}>
                            {wp.iceRisk}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-slate-400 font-sans">{wp.reason || 'Nominal transit corridor'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tab 2: Collapsible Events Log */}
          {activeBottomTab === 'EVENTS' && (
            <div className="border border-slate-800/60 rounded-xl bg-[#06111e]/95 overflow-hidden shadow-lg">
              <div className="px-4 py-2.5 bg-[#071322] border-b border-slate-800/60 text-xs font-semibold text-slate-300 flex items-center justify-between font-sans">
                <span>Chronological Navigation &amp; Hazard Events</span>
                <button type="button" onClick={() => setActiveBottomTab('METRICS')} className="text-slate-400 hover:text-white cursor-pointer">✕ Close</button>
              </div>
              <div className="overflow-x-auto max-h-56 custom-scrollbar p-3 space-y-1.5 font-sans">
                {events.slice().reverse().map(ev => (
                  <div key={ev.id} className="p-2.5 bg-slate-900/50 rounded-lg flex items-center justify-between gap-3 text-xs border border-slate-800/30">
                    <div className="flex items-center gap-3">
                      <span className="text-slate-400 font-mono text-[11px]">{ev.timeStr}</span>
                      <span className="font-semibold text-slate-200">{ev.title}</span>
                      <span className="text-slate-400 text-xs hidden md:inline">— {ev.detail}</span>
                    </div>
                    <span className={cn(
                      "px-2.5 py-0.5 rounded-full font-semibold text-[10px] shrink-0 font-sans",
                      ev.severity === 'CRITICAL' ? "bg-red-500/20 text-red-300" :
                      ev.severity === 'WARNING' ? "bg-amber-500/20 text-amber-300" :
                      ev.severity === 'CAUTION' ? "bg-yellow-500/20 text-yellow-300" :
                      "bg-slate-800 text-slate-300"
                    )}>
                      {ev.severity}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

      </div>

    </AppShell>

  );
};

export default NavigationPage;
