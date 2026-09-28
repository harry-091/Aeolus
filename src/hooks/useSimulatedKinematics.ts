import { useMemo, useState, useEffect, useRef } from 'react';

export type ScenarioType = 'NORMAL' | 'ICEBERG_ENCOUNTER' | 'RADAR_OBSTACLE' | 'HIGH_SEA_ICE' | 'MULTI_HAZARD';

export interface ClimaticConditions {
  sicPct: number;              // Sea Ice Concentration [0-100%]
  iceThicknessM: number;       // Ice Thickness in meters
  iceStage: string;            // WMO stage of development
  windSpeedKnots: number;      // True Wind Speed
  windDirectionDeg: number;    // True Wind Direction
  waveHeightM: number;         // Significant Wave Height (m)
  wavePeriodSec: number;       // Wave peak period (s)
  seaSurfaceTempC: number;     // Sea surface temperature (°C)
  airTempC: number;            // Ambient air temperature (°C)
  currentSpeedKnots: number;   // Ocean surface current (kn)
  currentDirectionDeg: number; // Current set / drift direction
  underKeelClearanceM: number; // Bathymetric UKC (m)
}

export interface VesselKinematics {
  sogKnots: number;            // Speed Over Ground
  stwKnots: number;            // Speed Through Water
  headingDeg: number;          // True Heading
  cogDeg: number;              // Course Over Ground
  engineRpm: number;           // Shaft RPM (nominal 80-120)
  engineLoadPct: number;       // Main Engine Load %
  shaftPowerKw: number;        // Shaft Power (kW)
  fuelRateMtDay: number;       // Fuel burn rate in Metric Tons / day
  cumulativeFuelTons: number;  // Total fuel consumed so far
  rudderAngleDeg: number;      // Autopilot Rudder Angle
  rollDeg: number;             // Vessel Roll angle (degrees)
  pitchDeg: number;            // Vessel Pitch angle (degrees)
  heaveM: number;              // Hydrodynamic Heave (m)
  iceResistanceKn: number;     // Bow ice crushing resistance force (kN)
  hullStressKn: number;        // Hull frame dynamic impact load (kN)
  hullStressLimitKn: number;   // Polar Class yield threshold (PC5 = 2,200 kN)
  rioScore: number;            // IMO POLARIS Risk Index Outcome
  polarCodeStatus: 'PERMITTED' | 'ICE_WATCH' | 'ESCORT_REQUIRED' | 'OPERATION_SUSPENDED';
}

export interface DynamicIceberg {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  origin_latitude: number;
  origin_longitude: number;
  initialLatitude: number;
  initialLongitude: number;
  driftSpeedKnots: number;
  driftBearingDeg: number;
  quadrant: string;
  sizeKm: number;
  areaKm2: number;
  draftM: number;
  distanceToShipKm: number;
  distanceToShipNm: number;
  distanceToRouteKm: number;
  distanceToRouteNm: number;
  cpaDistanceNm: number;
  tcpaMinutes: number;
  threatLevel: 'CLEAR' | 'CAUTION' | 'WARNING' | 'COLLISION_ALERT';
  routeThreatLevel: 'CLEAR' | 'CAUTION' | 'WARNING' | 'CRITICAL';
  isNearest: boolean;
  [key: string]: any;
}

export interface SimulationEvent {
  id: string;
  timestampSec: number;
  timeStr: string;
  category: 'NAVIGATION' | 'ICEBERG' | 'SEA_ICE' | 'RADAR' | 'REROUTE' | 'STATUS';
  title: string;
  detail: string;
  severity: 'INFO' | 'CAUTION' | 'WARNING' | 'CRITICAL';
}

export interface TelemetryDataPoint {
  timeStr: string;
  distanceKm: number;
  sogKnots: number;
  stwKnots: number;
  engineRpm: number;
  engineLoadPct: number;
  fuelRateMtDay: number;
  sicPct: number;
  iceThicknessM: number;
  windSpeedKnots: number;
  waveHeightM: number;
  hullStressKn: number;
  hullLimitKn: number;
  rioScore: number;
  nearestBergDistKm: number;
  nearestBergCpaNm: number;
  rollDeg: number;
  pitchDeg: number;
}

// Great-circle distance in kilometers
export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = 6371.0;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
  return r * c;
}

// Initial bearing between two coordinates
export function calculateBearingDeg(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

// Minimum distance from a point to a polyline route in kilometers
export function minDistanceToPolylineKm(
  pointLat: number,
  pointLon: number,
  polyline: [number, number][]
): number {
  if (!polyline || polyline.length === 0) return 9999;
  if (polyline.length === 1) return haversineKm(pointLat, pointLon, polyline[0][0], polyline[0][1]);

  let minDist = Infinity;
  for (let i = 0; i < polyline.length - 1; i++) {
    const pA = polyline[i];
    const pB = polyline[i + 1];

    // Sample along segment for great-circle approximation
    const samples = 6;
    for (let s = 0; s <= samples; s++) {
      const frac = s / samples;
      const sLat = pA[0] + frac * (pB[0] - pA[0]);
      const sLon = pA[1] + frac * (pB[1] - pA[1]);
      const d = haversineKm(pointLat, pointLon, sLat, sLon);
      if (d < minDist) {
        minDist = d;
      }
    }
  }
  return minDist;
}

interface UseSimulatedKinematicsProps {
  simDistanceKm: number;
  totalDistanceKm: number;
  cruisingSpeedKnots?: number;
  shipLat: number;
  shipLon: number;
  shipHeading: number;
  rawIcebergs: any[];
  polarClass?: string;
  routePath?: [number, number][];
  activeScenario?: ScenarioType;
  simStartTimeUtcSec?: number;
}

export function useSimulatedKinematics({
  simDistanceKm,
  totalDistanceKm,
  cruisingSpeedKnots = 13.5,
  shipLat,
  shipLon,
  shipHeading,
  rawIcebergs,
  polarClass = 'PC5',
  routePath = [],
  activeScenario = 'NORMAL',
  simStartTimeUtcSec = 1773143520 // Base UTC reference
}: UseSimulatedKinematicsProps) {
  // 1. Voyage progress fraction [0, 1]
  const progressFrac = useMemo(() => {
    if (!totalDistanceKm || totalDistanceKm <= 0) return 0;
    return Math.max(0, Math.min(1, simDistanceKm / totalDistanceKm));
  }, [simDistanceKm, totalDistanceKm]);

  // 2. Simulated Elapsed Time (hours)
  const elapsedSimHours = useMemo(() => {
    return simDistanceKm / Math.max(8.0, cruisingSpeedKnots * 1.852);
  }, [simDistanceKm, cruisingSpeedKnots]);

  // Current simulation UTC clock (advances with elapsedSimHours)
  const currentSimUtcStr = useMemo(() => {
    const totalSec = simStartTimeUtcSec + elapsedSimHours * 3600;
    const date = new Date(totalSec * 1000);
    const h = String(date.getUTCHours()).padStart(2, '0');
    const m = String(date.getUTCMinutes()).padStart(2, '0');
    const s = String(date.getUTCSeconds()).padStart(2, '0');
    return `${h}:${m}:${s} UTC`;
  }, [simStartTimeUtcSec, elapsedSimHours]);

  // 3. Dynamic Climatic Conditions along Route Profile (influenced by active scenario)
  const climaticConditions = useMemo<ClimaticConditions>(() => {
    let baseSic = 2.0;
    let baseThickness = 0.05;
    let stage = 'OPEN_WATER';
    let waveM = 3.8;
    let sst = 1.2;
    let airT = 0.5;
    let ukc = 3450;

    if (progressFrac < 0.25) {
      baseSic = 3.0 + progressFrac * 15.0;
      baseThickness = 0.1;
      stage = 'OPEN_WATER';
      waveM = 3.6 - progressFrac * 1.2;
      sst = 1.0 - progressFrac * 1.5;
      airT = -1.0 - progressFrac * 3.0;
      ukc = 3200;
    } else if (progressFrac < 0.60) {
      const fracInZone = (progressFrac - 0.25) / 0.35;
      baseSic = 8.0 + fracInZone * 42.0;
      baseThickness = 0.2 + fracInZone * 0.7;
      stage = baseSic > 40 ? 'OPEN_PACK' : 'VERY_OPEN_PACK';
      waveM = 2.8 - fracInZone * 1.8;
      sst = -0.5 - fracInZone * 1.2;
      airT = -4.0 - fracInZone * 6.0;
      ukc = 1850;
    } else {
      const fracInCoastal = (progressFrac - 0.60) / 0.40;
      baseSic = 50.0 + fracInCoastal * 26.0;
      baseThickness = 0.9 + fracInCoastal * 0.65;
      stage = baseSic > 70 ? 'CLOSE_PACK' : 'OPEN_PACK';
      waveM = 0.8 - fracInCoastal * 0.4;
      sst = -1.8;
      airT = -10.0 - fracInCoastal * 5.0;
      ukc = 420 + (1 - fracInCoastal) * 500;
    }

    // SCENARIO OVERRIDES: High Sea Ice Surge
    if (activeScenario === 'HIGH_SEA_ICE') {
      baseSic = Math.max(baseSic, 78.5);
      baseThickness = Math.max(baseThickness, 1.35);
      stage = 'CONSOLIDATED_PACK';
      waveM = 0.3;
      airT = -14.5;
    } else if (activeScenario === 'MULTI_HAZARD') {
      baseSic = Math.max(baseSic, 68.0);
      baseThickness = Math.max(baseThickness, 1.15);
      stage = 'CLOSE_PACK';
    }

    const timeSec = elapsedSimHours * 3600;
    const windNoise = Math.sin(timeSec / 800) * 3.5;
    const windSpeed = Math.max(12.0, 24.5 + (progressFrac > 0.7 ? 6.0 : 0) + windNoise);
    const windDir = (125.0 + Math.cos(timeSec / 1200) * 15.0 + 360) % 360;

    return {
      sicPct: Math.round(baseSic * 10) / 10,
      iceThicknessM: Math.round(baseThickness * 100) / 100,
      iceStage: stage,
      windSpeedKnots: Math.round(windSpeed * 10) / 10,
      windDirectionDeg: Math.round(windDir),
      waveHeightM: Math.max(0.4, Math.round(waveM * 10) / 10),
      wavePeriodSec: Math.round(8.5 + waveM * 1.1),
      seaSurfaceTempC: Math.round(sst * 10) / 10,
      airTempC: Math.round(airT * 10) / 10,
      currentSpeedKnots: Math.round((0.45 + Math.sin(progressFrac * Math.PI) * 0.75) * 10) / 10,
      currentDirectionDeg: (265 + Math.round(progressFrac * 30)) % 360,
      underKeelClearanceM: Math.round(ukc)
    };
  }, [progressFrac, elapsedSimHours, activeScenario]);

  // 4. Dynamic Vessel Kinematics Under Climatic Resistance & Polar Code Constraints
  const vesselKinematics = useMemo<VesselKinematics>(() => {
    const sic = climaticConditions.sicPct / 100;
    const thickness = climaticConditions.iceThicknessM;

    // A. Ice resistance slows vessel down exponentially in high pack ice
    const iceSlowdownFactor = Math.max(0.35, 1.0 - (0.58 * Math.pow(sic, 1.35)));
    const targetSog = cruisingSpeedKnots * iceSlowdownFactor;
    
    const wavePenalty = climaticConditions.waveHeightM > 3.0 ? (climaticConditions.waveHeightM - 3.0) * 0.4 : 0;
    const effectiveSog = Math.max(3.5, targetSog - wavePenalty);
    
    const currentAngleRad = ((climaticConditions.currentDirectionDeg - shipHeading) * Math.PI) / 180;
    const currentAlongTrack = climaticConditions.currentSpeedKnots * Math.cos(currentAngleRad);
    const effectiveStw = Math.max(3.2, effectiveSog - currentAlongTrack);

    // B. Engine load & power surge in heavy ice
    const nominalPower = 4200.0;
    const icePowerSurge = sic * 5200.0 * (thickness / 1.0);
    const shaftPowerKw = Math.min(9800.0, nominalPower + icePowerSurge);
    const engineLoadPct = Math.min(99.0, 48.0 + (shaftPowerKw / 9800.0) * 51.0);
    const engineRpm = Math.round(82.0 + (engineLoadPct / 100) * 38.0);

    // C. Fuel consumption: Admiralty cube law + ice crushing energy
    const baseFuelMtDay = 14.2;
    const fuelRateMtDay = baseFuelMtDay * Math.pow(effectiveStw / cruisingSpeedKnots, 2.2) * (1.0 + 1.3 * sic);
    const cumulativeFuelTons = (simDistanceKm / (effectiveSog * 1.852)) * (fuelRateMtDay / 24.0);

    // D. Hydrodynamic Motion (Roll, Pitch, Heave)
    const timeT = elapsedSimHours * 3600;
    const rollDamping = Math.max(0.08, 1.0 - sic * 0.92);
    const rollDeg = Math.sin(timeT / 5.2) * (climaticConditions.waveHeightM * 1.6) * rollDamping;
    const pitchDeg = Math.cos(timeT / 4.1) * (climaticConditions.waveHeightM * 0.65) * rollDamping;
    const heaveM = Math.abs(Math.sin(timeT / 3.8)) * (climaticConditions.waveHeightM * 0.35) * rollDamping;
    const rudderAngleDeg = Math.sin(timeT / 12.0) * 2.8 + (climaticConditions.windSpeedKnots > 25 ? 1.5 : 0);

    // E. Hull dynamic impact stress vs Polar Class yield threshold
    const hullStressLimitKn = polarClass === 'PC3' ? 3200 : polarClass === 'PC5' ? 2200 : 1600;
    const iceCrushingForceKn = Math.round(sic * 1450.0 * (thickness / 1.0) + Math.abs(Math.sin(timeT / 15)) * 180.0);
    const hullStressKn = Math.min(hullStressLimitKn + 150, 180 + iceCrushingForceKn);

    // F. IMO POLARIS RIO (Risk Index Outcome)
    let rio = 12.0;
    if (sic > 0.70) {
      rio = 3.0 - (sic - 0.70) * 24.0;
    } else if (sic > 0.40) {
      rio = 8.5 - (sic - 0.40) * 14.0;
    } else if (sic > 0.15) {
      rio = 11.0 - (sic - 0.15) * 8.0;
    }

    let polarCodeStatus: 'PERMITTED' | 'ICE_WATCH' | 'ESCORT_REQUIRED' | 'OPERATION_SUSPENDED' = 'PERMITTED';
    if (rio < -2.0 || hullStressKn >= hullStressLimitKn) {
      polarCodeStatus = 'OPERATION_SUSPENDED';
    } else if (rio < 0.0) {
      polarCodeStatus = 'ESCORT_REQUIRED';
    } else if (rio < 6.0 || sic > 0.35) {
      polarCodeStatus = 'ICE_WATCH';
    }

    return {
      sogKnots: Math.round(effectiveSog * 10) / 10,
      stwKnots: Math.round(effectiveStw * 10) / 10,
      headingDeg: Math.round(shipHeading),
      cogDeg: Math.round((shipHeading + (rudderAngleDeg * 0.3) + 360) % 360),
      engineRpm,
      engineLoadPct: Math.round(engineLoadPct),
      shaftPowerKw: Math.round(shaftPowerKw),
      fuelRateMtDay: Math.round(fuelRateMtDay * 10) / 10,
      cumulativeFuelTons: Math.round(cumulativeFuelTons * 10) / 10,
      rudderAngleDeg: Math.round(rudderAngleDeg * 10) / 10,
      rollDeg: Math.round(rollDeg * 10) / 10,
      pitchDeg: Math.round(pitchDeg * 10) / 10,
      heaveM: Math.round(heaveM * 100) / 100,
      iceResistanceKn: iceCrushingForceKn,
      hullStressKn,
      hullStressLimitKn,
      rioScore: Math.round(rio * 10) / 10,
      polarCodeStatus
    };
  }, [climaticConditions, cruisingSpeedKnots, shipHeading, elapsedSimHours, simDistanceKm, polarClass]);

  // 5. DYNAMIC ICEBERG DRIFT ENGINE (85 records from dataset with geodesic distance to ship and route)
  const dynamicIcebergs = useMemo<DynamicIceberg[]>(() => {
    if (!rawIcebergs || rawIcebergs.length === 0) return [];

    let minDistance = Infinity;
    let nearestIdx = -1;

    const driftedList = rawIcebergs.map((ib: any, idx: number) => {
      const initialLat = Number(ib.latitude ?? ib.current_lat ?? -66.0);
      const initialLon = Number(ib.longitude ?? ib.current_lon ?? 75.0);

      let driftBearing = 275.0;
      let driftSpeed = 0.35; // knots

      const q = (ib.quadrant || '').toUpperCase();
      if (q.includes('A') || q.includes('WEDDELL')) {
        driftBearing = 28.0;
        driftSpeed = 0.42;
      } else if (q.includes('B') || q.includes('BELLINGSHAUSEN')) {
        driftBearing = 265.0;
        driftSpeed = 0.32;
      } else if (q.includes('C') || q.includes('ROSS')) {
        driftBearing = 318.0;
        driftSpeed = 0.38;
      } else {
        driftBearing = 278.0;
        driftSpeed = 0.36;
      }

      if (ib.movement?.speed_knots) driftSpeed = ib.movement.speed_knots;
      if (ib.movement?.bearing_deg) driftBearing = ib.movement.bearing_deg;
      else if (ib.direction) {
        const parsedDir = parseFloat(ib.direction);
        if (!isNaN(parsedDir)) driftBearing = parsedDir;
      }

      // Compute total drift distance over elapsed simulated hours
      const driftDistanceKm = driftSpeed * elapsedSimHours * 1.852;
      const radBearing = (driftBearing * Math.PI) / 180;
      const dLat = (driftDistanceKm * Math.cos(radBearing)) / 111.0;
      const avgLat = initialLat + dLat / 2;
      const cosLat = Math.max(0.15, Math.cos((avgLat * Math.PI) / 180));
      const dLon = (driftDistanceKm * Math.sin(radBearing)) / (111.0 * cosLat);

      let currentLat = Math.max(-85.0, Math.min(-50.0, initialLat + dLat));
      let currentLon = initialLon + dLon;
      if (currentLon > 180) currentLon -= 360;
      if (currentLon < -180) currentLon += 360;

      // SCENARIO ENCOUNTER MODIFIER: steer iceberg across forward path during ICEBERG_ENCOUNTER
      if ((activeScenario === 'ICEBERG_ENCOUNTER' || activeScenario === 'MULTI_HAZARD') && idx === 0) {
        // Position A-68A or lead berg right near the forward route corridor (~8.4 km off ship bow)
        const forwardBearingRad = (shipHeading * Math.PI) / 180;
        const forwardOffsetKm = 8.4;
        currentLat = shipLat + (forwardOffsetKm * Math.cos(forwardBearingRad)) / 111.0;
        currentLon = shipLon + (forwardOffsetKm * Math.sin(forwardBearingRad)) / (111.0 * Math.cos((shipLat * Math.PI) / 180));
      }

      const distKm = haversineKm(shipLat, shipLon, currentLat, currentLon);
      const distNm = distKm / 1.852;

      if (distKm < minDistance) {
        minDistance = distKm;
        nearestIdx = idx;
      }

      // Geodesic distance to planned route polyline
      const distToRouteKm = routePath.length > 1 ? minDistanceToPolylineKm(currentLat, currentLon, routePath) : distKm;
      const distToRouteNm = distToRouteKm / 1.852;

      const relBearing = calculateBearingDeg(shipLat, shipLon, currentLat, currentLon);
      const angleDiffRad = ((shipHeading - relBearing) * Math.PI) / 180;
      const cpaDistanceNm = Math.abs(distNm * Math.sin(angleDiffRad));
      const closingSpeedKn = Math.max(1.0, vesselKinematics.sogKnots * Math.cos(angleDiffRad) + driftSpeed);
      const tcpaMinutes = (distNm * Math.cos(angleDiffRad)) > 0 
        ? Math.round(((distNm * Math.cos(angleDiffRad)) / closingSpeedKn) * 60) 
        : 0;

      // Rigorous geodesic distance thresholds (Phase 7):
      // SAFE (> 25 NM / 46 km)
      // CAUTION (15 - 25 NM / 28 - 46 km)
      // WARNING (8 - 15 NM / 15 - 28 km)
      // COLLISION_ALERT (< 8 NM / 15 km or CPA < 3 NM)
      let threatLevel: 'CLEAR' | 'CAUTION' | 'WARNING' | 'COLLISION_ALERT' = 'CLEAR';
      if (distNm < 5.0 || (cpaDistanceNm < 2.5 && tcpaMinutes > 0 && tcpaMinutes < 30)) {
        threatLevel = 'COLLISION_ALERT';
      } else if (distNm < 15.0 || (cpaDistanceNm < 5.0 && tcpaMinutes > 0 && tcpaMinutes < 60)) {
        threatLevel = 'WARNING';
      } else if (distNm < 25.0 || cpaDistanceNm < 10.0) {
        threatLevel = 'CAUTION';
      }

      let routeThreatLevel: 'CLEAR' | 'CAUTION' | 'WARNING' | 'CRITICAL' = 'CLEAR';
      if (distToRouteKm < 10.0) {
        routeThreatLevel = 'CRITICAL';
      } else if (distToRouteKm < 25.0) {
        routeThreatLevel = 'WARNING';
      } else if (distToRouteKm < 45.0) {
        routeThreatLevel = 'CAUTION';
      }

      return {
        ...ib,
        id: ib.id || `IB-${idx}`,
        name: ib.name || `Iceberg ${ib.id}`,
        latitude: Math.round(currentLat * 10000) / 10000,
        longitude: Math.round(currentLon * 10000) / 10000,
        origin_latitude: Math.round(currentLat * 10000) / 10000,
        origin_longitude: Math.round(currentLon * 10000) / 10000,
        initialLatitude: initialLat,
        initialLongitude: initialLon,
        driftSpeedKnots: driftSpeed,
        driftBearingDeg: driftBearing,
        quadrant: q || 'D_DAVIS',
        sizeKm: ib.size || 14.5,
        areaKm2: ib.areaKm2 || 185.0,
        draftM: ib.draftM || ib.draftEstimate || 240.0,
        distanceToShipKm: Math.round(distKm * 10) / 10,
        distanceToShipNm: Math.round(distNm * 10) / 10,
        distanceToRouteKm: Math.round(distToRouteKm * 10) / 10,
        distanceToRouteNm: Math.round(distToRouteNm * 10) / 10,
        cpaDistanceNm: Math.round(cpaDistanceNm * 10) / 10,
        tcpaMinutes: Math.max(0, tcpaMinutes),
        threatLevel,
        routeThreatLevel,
        isNearest: false
      };
    });

    if (nearestIdx >= 0 && driftedList[nearestIdx]) {
      driftedList[nearestIdx].isNearest = true;
    }

    return driftedList;
  }, [rawIcebergs, elapsedSimHours, shipLat, shipLon, shipHeading, vesselKinematics.sogKnots, routePath, activeScenario]);

  // 6. Chronological Simulation Event History (Phase 12)
  const [events, setEvents] = useState<SimulationEvent[]>([
    {
      id: 'ev-init',
      timestampSec: simStartTimeUtcSec,
      timeStr: '12:00:00 UTC',
      category: 'NAVIGATION',
      title: 'Voyage Commenced',
      detail: 'Departure clearance logged; optimal polar corridor initialized.',
      severity: 'INFO'
    }
  ]);

  const nearestIceberg = useMemo(() => {
    return dynamicIcebergs.find(b => b.isNearest) || dynamicIcebergs[0] || null;
  }, [dynamicIcebergs]);

  // State-driven event generator (appends when simulation state crosses operational thresholds)
  const lastLoggedStateRef = useRef<{
    loggedSicZone?: boolean;
    loggedPackZone?: boolean;
    loggedBergAlert?: string;
    loggedPolarCode?: string;
    loggedScenario?: string;
  }>({});

  useEffect(() => {
    const s = lastLoggedStateRef.current;
    const newEvents: SimulationEvent[] = [];
    const nowSec = Math.round(simStartTimeUtcSec + elapsedSimHours * 3600);

    // Scenario switch event
    if (s.loggedScenario !== activeScenario) {
      s.loggedScenario = activeScenario;
      if (activeScenario === 'ICEBERG_ENCOUNTER') {
        newEvents.push({
          id: `ev-scen-${nowSec}`,
          timestampSec: nowSec,
          timeStr: currentSimUtcStr,
          category: 'ICEBERG',
          title: 'Emergency Scenario: Iceberg Approach',
          detail: 'Drifting iceberg tracked on collision course with active corridor.',
          severity: 'WARNING'
        });
      } else if (activeScenario === 'HIGH_SEA_ICE') {
        newEvents.push({
          id: `ev-scen-${nowSec}`,
          timestampSec: nowSec,
          timeStr: currentSimUtcStr,
          category: 'SEA_ICE',
          title: 'Emergency Scenario: Heavy Sea Ice Pack',
          detail: 'Rapid sea-ice consolidation encountered (>78% SIC). Hull stress surging.',
          severity: 'CRITICAL'
        });
      } else if (activeScenario === 'RADAR_OBSTACLE') {
        newEvents.push({
          id: `ev-scen-${nowSec}`,
          timestampSec: nowSec,
          timeStr: currentSimUtcStr,
          category: 'RADAR',
          title: 'Sentinel-1 Radar Obstacle Contact',
          detail: 'SAR radar contact SAR-OBS-01 detected 3.8 km ahead on track line.',
          severity: 'CRITICAL'
        });
      }
    }

    // Ice regime transitions
    if (climaticConditions.sicPct >= 15 && !s.loggedSicZone) {
      s.loggedSicZone = true;
      newEvents.push({
        id: `ev-miz-${nowSec}`,
        timestampSec: nowSec,
        timeStr: currentSimUtcStr,
        category: 'SEA_ICE',
        title: 'Entered Marginal Ice Zone (MIZ)',
        detail: `Sea ice concentration reached ${climaticConditions.sicPct}%. Speed adjusted for ice drift.`,
        severity: 'CAUTION'
      });
    }

    if (climaticConditions.sicPct >= 50 && !s.loggedPackZone) {
      s.loggedPackZone = true;
      newEvents.push({
        id: `ev-pack-${nowSec}`,
        timestampSec: nowSec,
        timeStr: currentSimUtcStr,
        category: 'SEA_ICE',
        title: 'Entered Heavy Pack Ice Field',
        detail: `Consolidated pack ice (${climaticConditions.sicPct}% SIC, ${climaticConditions.iceThicknessM}m). Ice resistance active.`,
        severity: 'WARNING'
      });
    }

    // Nearest iceberg threat escalation
    if (nearestIceberg) {
      if (nearestIceberg.threatLevel === 'COLLISION_ALERT' && s.loggedBergAlert !== 'COLLISION_ALERT') {
        s.loggedBergAlert = 'COLLISION_ALERT';
        newEvents.push({
          id: `ev-berg-crit-${nowSec}`,
          timestampSec: nowSec,
          timeStr: currentSimUtcStr,
          category: 'ICEBERG',
          title: `CRITICAL: Proximity Alert — ${nearestIceberg.name}`,
          detail: `Iceberg within ${nearestIceberg.distanceToShipKm} km (CPA ${nearestIceberg.cpaDistanceNm} NM). Route diversion advised.`,
          severity: 'CRITICAL'
        });
      } else if (nearestIceberg.threatLevel === 'WARNING' && s.loggedBergAlert !== 'WARNING' && s.loggedBergAlert !== 'COLLISION_ALERT') {
        s.loggedBergAlert = 'WARNING';
        newEvents.push({
          id: `ev-berg-warn-${nowSec}`,
          timestampSec: nowSec,
          timeStr: currentSimUtcStr,
          category: 'ICEBERG',
          title: `Iceberg Approaching Corridor — ${nearestIceberg.name}`,
          detail: `Distance: ${nearestIceberg.distanceToShipKm} km, Route clearance: ${nearestIceberg.distanceToRouteKm} km.`,
          severity: 'WARNING'
        });
      }
    }

    // Polar Code regulatory trigger
    if (vesselKinematics.polarCodeStatus !== s.loggedPolarCode) {
      s.loggedPolarCode = vesselKinematics.polarCodeStatus;
      if (vesselKinematics.polarCodeStatus === 'OPERATION_SUSPENDED') {
        newEvents.push({
          id: `ev-polaris-${nowSec}`,
          timestampSec: nowSec,
          timeStr: currentSimUtcStr,
          category: 'STATUS',
          title: 'IMO POLARIS: Operation Suspended',
          detail: `RIO Score ${vesselKinematics.rioScore} is negative. Hull stress (${vesselKinematics.hullStressKn} kN) requires immediate reroute.`,
          severity: 'CRITICAL'
        });
      } else if (vesselKinematics.polarCodeStatus === 'ICE_WATCH') {
        newEvents.push({
          id: `ev-polaris-watch-${nowSec}`,
          timestampSec: nowSec,
          timeStr: currentSimUtcStr,
          category: 'STATUS',
          title: 'IMO POLARIS: Ice Watch Required',
          detail: `Entering elevated ice risk corridor. Continuous radar/visual watch established.`,
          severity: 'CAUTION'
        });
      }
    }

    if (newEvents.length > 0) {
      setEvents(prev => [...prev, ...newEvents].slice(-40));
    }
  }, [climaticConditions, nearestIceberg, vesselKinematics, activeScenario, elapsedSimHours, currentSimUtcStr, simStartTimeUtcSec]);

  // 7. Time-Series Buffer for Telemetry Charts
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryDataPoint[]>([]);
  const lastRecordedDistRef = useRef<number>(-1);

  useEffect(() => {
    const distDelta = Math.abs(simDistanceKm - lastRecordedDistRef.current);
    if (distDelta >= 12.0 || lastRecordedDistRef.current === -1) {
      lastRecordedDistRef.current = simDistanceKm;

      const nearestBerg = dynamicIcebergs.find(b => b.isNearest) || dynamicIcebergs[0];
      const hours = Math.floor(elapsedSimHours);
      const mins = Math.floor((elapsedSimHours - hours) * 60);
      const timeLabel = `T+${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;

      const newPoint: TelemetryDataPoint = {
        timeStr: timeLabel,
        distanceKm: Math.round(simDistanceKm),
        sogKnots: vesselKinematics.sogKnots,
        stwKnots: vesselKinematics.stwKnots,
        engineRpm: vesselKinematics.engineRpm,
        engineLoadPct: vesselKinematics.engineLoadPct,
        fuelRateMtDay: vesselKinematics.fuelRateMtDay,
        sicPct: climaticConditions.sicPct,
        iceThicknessM: climaticConditions.iceThicknessM,
        windSpeedKnots: climaticConditions.windSpeedKnots,
        waveHeightM: climaticConditions.waveHeightM,
        hullStressKn: vesselKinematics.hullStressKn,
        hullLimitKn: vesselKinematics.hullStressLimitKn,
        rioScore: vesselKinematics.rioScore,
        nearestBergDistKm: nearestBerg?.distanceToShipKm ?? 120.0,
        nearestBergCpaNm: nearestBerg?.cpaDistanceNm ?? 24.5,
        rollDeg: vesselKinematics.rollDeg,
        pitchDeg: vesselKinematics.pitchDeg
      };

      setTelemetryHistory(prev => {
        const filtered = prev.filter(p => p.distanceKm <= simDistanceKm);
        const updated = [...filtered, newPoint];
        return updated.slice(-60);
      });
    }
  }, [simDistanceKm, elapsedSimHours, vesselKinematics, climaticConditions, dynamicIcebergs]);

  return {
    progressFrac,
    elapsedSimHours,
    currentSimUtcStr,
    climaticConditions,
    vesselKinematics,
    dynamicIcebergs,
    nearestIceberg,
    events,
    telemetryHistory
  };
}
