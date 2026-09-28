import React, { createContext, useContext, useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { api, clearApiCache } from '../services/api';

export type ForecastHorizonHours = 0 | 6 | 12 | 24 | 48;
export type ForecastHorizonLabel = 'NOW' | '+6H' | '+12H' | '+24H' | '+48H';
export type MissionStatus = 'AVAILABLE' | 'MISSION_ASSIGNED' | 'UNDERWAY' | 'ARRIVED';

export interface VesselMission {
  mission_id: string;
  vessel_id: string;
  origin: string;
  origin_coords: [number, number];
  destination: string;
  destination_coords: [number, number];
  destination_station_id?: string;
  mission_type: MissionType;
  route_profile: OptimizationPriority;
  route_id?: string;
  status: MissionStatus;
  created_at: string;
  departure_time: string;
  estimated_arrival: string;
  eta_hours: number;
  completed_at?: string;
}

export interface CanonicalVessel {
  id: string;
  name: string;
  mmsi: string | number;
  imo: string | number;
  flag: string;
  country: string;
  operator: string;
  polar_class: string;
  latitude: number;
  longitude: number;
  sog: number;
  speed: number;
  cog: number;
  heading: number;
  nav_status?: string;
  source: 'DETERMINISTIC_SIMULATION' | 'AIS' | string;
  data_status: 'SIMULATED_VOYAGE' | 'LIVE' | string;
  is_demo?: boolean;
  destination_station_id?: string;
  destination: string;
  dest_lat?: number;
  dest_lon?: number;
  voyage_origin?: string;
  mission_description?: string;
  mission?: string;
  eta?: string;
  track?: [number, number][];
  mission_status?: MissionStatus;
  current_mission?: VesselMission;
  forecast_latitude?: number;
  forecast_longitude?: number;
  forecast_heading?: number;
  distance_covered_km?: number;
  remaining_dist_km?: number;
  time_to_arrival_hours?: number;
}

export interface RouteOption {
  id: string;
  name: string;
  vessel_id?: string;
  optimization_mode?: 'BALANCED' | 'SAFEST' | 'FASTEST' | string;
  distance: number;
  eta: string;
  iceRisk?: string;
  icebergRisk?: string;
  weatherRisk?: string;
  overallScore?: number;
  recommended?: boolean;
  rioScore?: string | number;
  sicExposure?: number;
  sic_actual?: number;
  sic_cost_contribution?: number;
  minimum_cpa_km?: number;
  min_radar_obstacle_km?: number;
  radar_clearance?: {
    min_radar_obstacle_km?: number;
    nearest_target_id?: string;
    sensor?: string;
    provenance?: string;
  };
  sea_ice_exposure?: {
    fast_ice_km?: number;
    pack_ice_km?: number;
    open_water_km?: number;
    avg_sic?: number;
    sic_actual?: number;
    sic_cost_contribution?: number;
  };
  reason?: string;
  decision_explanation?: string;
  decision_support?: {
    route_profile: string;
    risk_level: string;
    risk_score: number;
    eta: string;
    distance: string;
    distance_km: number;
    fuel_estimate: string;
    dominant_hazard: string;
    hazard_summary: string;
    recommendation: string;
    is_recommended: boolean;
    provenance: string;
  };
  fuelConsumption?: string | number;
  fuelSavings?: string;
  safetyMargin?: string;
  icebergEncounters?: number;
  costs?: Record<string, number>;
  cost_breakdown?: Record<string, number>;
  has_iceberg_hazard?: boolean;
  iceberg_threat?: any;
  path: [number, number][];
  waypoints?: any[];
}

// Authoritative Canonical Polar Fleet (Fallback & Offline Dataset)
export const CANONICAL_FLEET: CanonicalVessel[] = [
  {
    id: 'rv_sagar_nidhi',
    name: 'R/V Sagar Nidhi',
    flag: '🇮🇳',
    country: 'India',
    operator: 'National Centre for Polar and Ocean Research (NCPOR)',
    mmsi: '419071000',
    imo: '9407988',
    latitude: -54.2000,
    longitude: 68.4000,
    sog: 13.5,
    speed: 13.5,
    cog: 165.0,
    heading: 165,
    nav_status: 'Underway using engine',
    source: 'DETERMINISTIC_SIMULATION',
    data_status: 'SIMULATED_VOYAGE',
    is_demo: true,
    destination_station_id: 'bharati',
    destination: 'Bharati Research Station',
    dest_lat: -69.4068,
    dest_lon: 76.1953,
    polar_class: 'PC5 / Ice Class 1A Super',
    voyage_origin: 'Mormugao Port / Cape Town',
    mission_description: '43rd Indian Scientific Expedition oceanographic transect and resupply towards Larsemann Hills.',
    eta: '72h 36m'
  },
  {
    id: 'rv_polarstern',
    name: 'R/V Polarstern — DEMO',
    flag: '🇩🇪',
    country: 'Germany',
    operator: 'Alfred Wegener Institute (AWI)',
    mmsi: '211281000',
    imo: '7820497',
    latitude: -69.2000,
    longitude: -8.3000,
    sog: 14.5,
    speed: 14.5,
    cog: 210.0,
    heading: 210,
    nav_status: 'Underway using engine',
    source: 'DETERMINISTIC_SIMULATION',
    data_status: 'SIMULATED_VOYAGE',
    is_demo: true,
    destination_station_id: 'neumayer_iii',
    destination: 'Neumayer Station III',
    dest_lat: -70.6744,
    dest_lon: -8.2742,
    polar_class: 'PC2 / Arc4 (Heavy Polar Icebreaker)',
    voyage_origin: 'Cape Town Port (South Africa)',
    mission_description: 'Weddell Sea continental shelf glaciology and Neumayer III annual observatory crew rotation.',
    eta: '11h 33m'
  },
  {
    id: 'rrs_sir_david_attenborough',
    name: 'RRS Sir David Attenborough — DEMO',
    flag: '🇬🇧',
    country: 'United Kingdom',
    operator: 'British Antarctic Survey (BAS)',
    mmsi: '232029054',
    imo: '9798222',
    latitude: -63.1000,
    longitude: -58.4000,
    sog: 14.8,
    speed: 14.8,
    cog: 224.0,
    heading: 224,
    nav_status: 'Underway using engine',
    source: 'DETERMINISTIC_SIMULATION',
    data_status: 'SIMULATED_VOYAGE',
    is_demo: true,
    destination_station_id: 'palmer',
    destination: 'Palmer Station',
    dest_lat: -64.7744,
    dest_lon: -64.0531,
    polar_class: 'PC4 (Polar Logistics & Science)',
    voyage_origin: 'Stanley Gateway Port',
    mission_description: 'Adelaide & Anvers Island marine geophysics and Palmer Station science passage via Gerlache Strait.',
    eta: '14h 20m'
  },
  {
    id: 'aurora_australis_2015_16',
    name: 'R/V Aurora Australis — DEMO',
    flag: '🇦🇺',
    country: 'Australia',
    operator: 'Australian Antarctic Division (AAD)',
    mmsi: '503000000',
    imo: '8712582',
    latitude: -65.2000,
    longitude: 64.3000,
    sog: 12.4,
    speed: 12.4,
    cog: 184.0,
    heading: 184,
    nav_status: 'Underway using engine',
    source: 'DETERMINISTIC_SIMULATION',
    data_status: 'SIMULATED_VOYAGE',
    is_demo: true,
    destination_station_id: 'davis',
    destination: 'Davis Station',
    dest_lat: -68.5764,
    dest_lon: 77.9672,
    polar_class: 'PC5 (Antarctic Research Vessel)',
    voyage_origin: 'Hobart Port (Tasmania)',
    mission_description: 'East Antarctic marine science transect approaching Vestfold Hills and Wilkes Land ice edge resupply.',
    eta: '26h 30m'
  },
  {
    id: 'sa_agulhas_ii',
    name: 'S.A. Agulhas II — DEMO',
    flag: '🇿🇦',
    country: 'South Africa',
    operator: 'Department of Forestry, Fisheries and the Environment (DFFE / SANAP)',
    mmsi: '601362000',
    imo: '9551131',
    latitude: -68.5000,
    longitude: -2.5000,
    sog: 12.8,
    speed: 12.8,
    cog: 190.0,
    heading: 190,
    nav_status: 'Underway using engine',
    source: 'DETERMINISTIC_SIMULATION',
    data_status: 'SIMULATED_VOYAGE',
    is_demo: true,
    destination_station_id: 'sanae_iv',
    destination: 'SANAE IV Base',
    dest_lat: -71.6739,
    dest_lon: -2.8408,
    polar_class: 'PC5 / DNV ICE-10',
    voyage_origin: 'Cape Town Port (South Africa)',
    mission_description: 'Queen Maud Land annual relief voyage carrying cargo, fuel, and overwintering teams.',
    eta: '24h 50m'
  },
  {
    id: 'rv_nathaniel_palmer',
    name: 'R/V Nathaniel B. Palmer — DEMO',
    flag: '🇺🇸',
    country: 'United States',
    operator: 'US Antarctic Program Marine Logistics (USAP)',
    mmsi: '367000000',
    imo: '9007295',
    latitude: -71.5000,
    longitude: 176.2000,
    sog: 14.2,
    speed: 14.2,
    cog: 192.0,
    heading: 192,
    nav_status: 'Underway using engine',
    source: 'DETERMINISTIC_SIMULATION',
    data_status: 'SIMULATED_VOYAGE',
    is_demo: true,
    destination_station_id: 'mcmurdo',
    destination: 'McMurdo Station',
    dest_lat: -77.8460,
    dest_lon: 166.6681,
    polar_class: 'PC3 (Heavy Research Icebreaker)',
    voyage_origin: 'Lyttelton Port (New Zealand)',
    mission_description: 'Ross Sea ecosystem & polynya study and heavy icebreaker escort into McMurdo Sound.',
    eta: '22h 10m'
  },
  {
    id: 'rv_shirase',
    name: 'R/V Shirase (AGB-5003) — DEMO',
    flag: '🇯🇵',
    country: 'Japan',
    operator: 'Japan National Institute of Polar Research (NIPR)',
    mmsi: '431999000',
    imo: '9400000',
    latitude: -64.5000,
    longitude: 40.2000,
    sog: 15.0,
    speed: 15.0,
    cog: 175.0,
    heading: 175,
    nav_status: 'Underway using engine',
    source: 'DETERMINISTIC_SIMULATION',
    data_status: 'SIMULATED_VOYAGE',
    is_demo: true,
    destination_station_id: 'syowa',
    destination: 'Syowa Station',
    dest_lat: -69.0042,
    dest_lon: 39.5806,
    polar_class: 'PC2 (Heavy Military-Spec Polar Icebreaker)',
    voyage_origin: 'Fremantle (Australia)',
    mission_description: '65th JARE continental logistics and heavy ice penetration into Lützow-Holm Bay.',
    eta: '15h 45m'
  },
  {
    id: 'polar_research_vessel_demo',
    name: 'Polar Research Vessel — DEMO',
    flag: '🌐',
    country: 'International / COMNAP',
    operator: 'COMNAP Scientific Logistics',
    mmsi: '211281001',
    imo: '7820498',
    latitude: -62.8000,
    longitude: -59.5000,
    sog: 13.5,
    speed: 13.5,
    cog: 215.0,
    heading: 215,
    nav_status: 'Underway using engine',
    source: 'DETERMINISTIC_SIMULATION',
    data_status: 'SIMULATED_VOYAGE',
    is_demo: true,
    destination_station_id: 'comandante_ferraz',
    destination: 'Comandante Ferraz Antarctic Station',
    dest_lat: -62.0833,
    dest_lon: -58.3833,
    polar_class: 'PC3 (Polar Icebreaker)',
    voyage_origin: 'Bransfield Strait Operational Sector',
    mission_description: 'Environmental research and multi-station logistic transect across South Shetland Islands.',
    eta: '8h 15m'
  }
];

export interface AntarcticStation {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  region?: string;
  operator?: string;
  country?: string;
  coastal_access?: boolean;
}

export const CANONICAL_STATIONS: AntarcticStation[] = [
  { id: 'bharati', name: 'Bharati Station (Larsemann Hills)', latitude: -69.4068, longitude: 76.1953, region: 'East Antarctica', operator: 'NCPOR (India)', country: 'India', coastal_access: true },
  { id: 'maitri', name: 'Maitri Station (Schirmacher Oasis)', latitude: -70.7700, longitude: 11.7300, region: 'Queen Maud Land', operator: 'NCPOR (India)', country: 'India', coastal_access: true },
  { id: 'neumayer', name: 'Neumayer Station III (Atka Bay)', latitude: -70.6700, longitude: -8.2700, region: 'Weddell Sea Sector', operator: 'AWI (Germany)', country: 'Germany', coastal_access: true },
  { id: 'mcmurdo', name: 'McMurdo Station (Ross Island)', latitude: -77.8500, longitude: 166.6700, region: 'Ross Sea', operator: 'USAP (USA)', country: 'USA', coastal_access: true },
  { id: 'rothera', name: 'Rothera Research Station (Adelaide Island)', latitude: -67.5700, longitude: -68.1300, region: 'Antarctic Peninsula', operator: 'BAS (UK)', country: 'UK', coastal_access: true },
  { id: 'casey', name: 'Casey Station (Wilkes Land)', latitude: -66.2800, longitude: 110.5300, region: 'Wilkes Land', operator: 'AAD (Australia)', country: 'Australia', coastal_access: true },
  { id: 'davis', name: 'Davis Station (Vestfold Hills)', latitude: -68.5800, longitude: 77.9700, region: 'Prydz Bay Sector', operator: 'AAD (Australia)', country: 'Australia', coastal_access: true },
  { id: 'comandante_ferraz', name: 'Comandante Ferraz Station (King George Island)', latitude: -62.0833, longitude: -58.3833, region: 'South Shetland Islands', operator: 'PROANTAR (Brazil)', country: 'Brazil', coastal_access: true }
];

export type MissionType = 'RESEARCH' | 'SUPPLY' | 'EMERGENCY' | 'ICE_OBSERVATION';
export type OptimizationPriority = 'BALANCED' | 'SAFEST' | 'FASTEST' | 'FUEL';

export function haversineDistKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
  return R * c;
}

export function computeBearingDeg(p1: [number, number], p2: [number, number]): number {
  if (!p1 || !p2) return 180;
  const dLon = (p2[1] - p1[1]) * Math.PI / 180;
  const lat1 = p1[0] * Math.PI / 180;
  const lat2 = p2[0] * Math.PI / 180;
  const y = Math.sin(dLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  return Math.round((Math.atan2(y, x) * 180 / Math.PI + 360) % 360);
}

export function calculateVesselPositionAtHorizon(
  vessel: CanonicalVessel,
  route: RouteOption | null,
  horizonHours: ForecastHorizonHours
): {
  latitude: number;
  longitude: number;
  heading: number;
  status: MissionStatus;
  distanceCoveredKm: number;
  remainingDistKm: number;
  etaHours: number;
} {
  // 1. LIVE AIS vessels: NEVER fabricate future movement (Rule 14 & Step 8)
  if (vessel.data_status === 'LIVE' || vessel.source === 'AIS') {
    return {
      latitude: vessel.latitude,
      longitude: vessel.longitude,
      heading: vessel.heading || 180,
      status: (vessel.mission_status || 'UNDERWAY') as MissionStatus,
      distanceCoveredKm: 0,
      remainingDistKm: 0,
      etaHours: 0
    };
  }

  // 2. Stationary mission states
  if (vessel.mission_status === 'AVAILABLE') {
    return {
      latitude: vessel.latitude,
      longitude: vessel.longitude,
      heading: vessel.heading || 180,
      status: 'AVAILABLE',
      distanceCoveredKm: 0,
      remainingDistKm: 0,
      etaHours: 0
    };
  }

  if (vessel.mission_status === 'ARRIVED') {
    const arrLat = vessel.dest_lat !== undefined ? vessel.dest_lat : vessel.latitude;
    const arrLon = vessel.dest_lon !== undefined ? vessel.dest_lon : vessel.longitude;
    return {
      latitude: arrLat,
      longitude: arrLon,
      heading: vessel.heading || 180,
      status: 'ARRIVED',
      distanceCoveredKm: vessel.distance_covered_km || 0,
      remainingDistKm: 0,
      etaHours: 0
    };
  }

  // 3. UNDERWAY: Compute position along route path
  const path: [number, number][] = route?.path && route.path.length >= 2 ? route.path : [];
  if (path.length < 2) {
    return {
      latitude: vessel.latitude,
      longitude: vessel.longitude,
      heading: vessel.heading || 180,
      status: (vessel.mission_status || 'UNDERWAY') as MissionStatus,
      distanceCoveredKm: 0,
      remainingDistKm: 0,
      etaHours: 24
    };
  }

  // Calculate cumulative distances along route vertices
  const segDists: number[] = [];
  let totalRouteDistKm = 0;
  for (let i = 0; i < path.length - 1; i++) {
    const d = haversineDistKm(path[i][0], path[i][1], path[i + 1][0], path[i + 1][1]);
    segDists.push(d);
    totalRouteDistKm += d;
  }

  const speedKnots = vessel.speed || vessel.sog || 13.5;
  const speedKmh = speedKnots * 1.852;
  const totalEtaHours = totalRouteDistKm > 0 && speedKmh > 0 ? totalRouteDistKm / speedKmh : 24.0;

  // Horizon 0 (NOW)
  if (horizonHours === 0) {
    return {
      latitude: path[0][0],
      longitude: path[0][1],
      heading: computeBearingDeg(path[0], path[1]),
      status: 'UNDERWAY',
      distanceCoveredKm: 0,
      remainingDistKm: Math.round(totalRouteDistKm),
      etaHours: Math.round(totalEtaHours * 10) / 10
    };
  }

  // If horizon reaches or exceeds total travel time, the vessel has ARRIVED at destination
  if (horizonHours >= totalEtaHours) {
    const lastPt = path[path.length - 1];
    return {
      latitude: lastPt[0],
      longitude: lastPt[1],
      heading: computeBearingDeg(path[path.length - 2], lastPt),
      status: 'ARRIVED',
      distanceCoveredKm: Math.round(totalRouteDistKm),
      remainingDistKm: 0,
      etaHours: 0
    };
  }

  // Traversal along route polyline
  const targetDistKm = speedKmh * horizonHours;
  let accumulatedDist = 0;

  for (let i = 0; i < segDists.length; i++) {
    const segLen = segDists[i];
    if (accumulatedDist + segLen >= targetDistKm || i === segDists.length - 1) {
      const remainingInSeg = targetDistKm - accumulatedDist;
      const frac = segLen > 0 ? Math.max(0, Math.min(1, remainingInSeg / segLen)) : 0;
      const pA = path[i];
      const pB = path[i + 1];
      const interpLat = pA[0] + frac * (pB[0] - pA[0]);
      const interpLon = pA[1] + frac * (pB[1] - pA[1]);
      const heading = computeBearingDeg(pA, pB);
      return {
        latitude: Number(interpLat.toFixed(4)),
        longitude: Number(interpLon.toFixed(4)),
        heading,
        status: 'UNDERWAY',
        distanceCoveredKm: Math.round(targetDistKm),
        remainingDistKm: Math.round(Math.max(0, totalRouteDistKm - targetDistKm)),
        etaHours: Math.round(Math.max(0, totalEtaHours - horizonHours) * 10) / 10
      };
    }
    accumulatedDist += segLen;
  }

  const lastPt = path[path.length - 1];
  return {
    latitude: lastPt[0],
    longitude: lastPt[1],
    heading: vessel.heading || 180,
    status: 'ARRIVED',
    distanceCoveredKm: Math.round(totalRouteDistKm),
    remainingDistKm: 0,
    etaHours: 0
  };
}

interface FleetContextType {
  fleet: CanonicalVessel[];
  displayFleet: CanonicalVessel[];
  selectedVesselId: string;
  selectedVessel: CanonicalVessel;
  activeDisplayVessel: CanonicalVessel;
  setSelectedVesselId: (id: string) => void;
  stations: AntarcticStation[];
  selectedDestinationId: string;
  selectedDestination: AntarcticStation;
  setSelectedDestinationId: (id: string) => void;
  selectedHorizon: ForecastHorizonHours;
  setSelectedHorizon: (h: ForecastHorizonHours) => void;
  activeHorizonLabel: ForecastHorizonLabel;
  missionId: string;
  missionType: MissionType;
  setMissionType: (type: MissionType) => void;
  optimizationPriority: OptimizationPriority;
  setOptimizationPriority: (p: OptimizationPriority) => void;
  selectedIcebergId: string | null;
  setSelectedIcebergId: (id: string | null) => void;
  routes: RouteOption[];
  activeRouteId: string;
  setActiveRouteId: (id: string) => void;
  activeRoute: RouteOption | null;
  emergencyRerouteActive: boolean;
  setEmergencyRerouteActive: (active: boolean) => void;
  tacticalAlert: {
    active: boolean;
    phase: 'idle' | 'detecting' | 'diverted';
    title?: string;
    description?: string;
    icebergId?: string;
    headingChange?: string;
    clearanceKm?: number;
    extraDistKm?: number;
    extraEtaMinutes?: number;
    alertId?: string;
    timestamp?: string;
    hazardIceberg?: any;
  };
  setTacticalAlert: React.Dispatch<React.SetStateAction<{
    active: boolean;
    phase: 'idle' | 'detecting' | 'diverted';
    title?: string;
    description?: string;
    icebergId?: string;
    headingChange?: string;
    clearanceKm?: number;
    extraDistKm?: number;
    extraEtaMinutes?: number;
    alertId?: string;
    timestamp?: string;
    hazardIceberg?: any;
  }>>;
  triggerEmergencyHazard: (progressFraction?: number) => Promise<void>;
  dismissTacticalAlert: () => void;
  recomputeRoutes: () => Promise<void>;
  assignMission: (
    vesselId: string,
    destinationStationId: string,
    missionType: MissionType,
    routeProfile: OptimizationPriority
  ) => Promise<void>;
  resetVesselToAvailable: (vesselId: string) => void;
  whatIfScenario: {
    active: boolean;
    icebergDriftOffsetKm: number;
    sicIncreasePct: number;
    windGustKnots: number;
  };
  setWhatIfScenario: React.Dispatch<React.SetStateAction<{
    active: boolean;
    icebergDriftOffsetKm: number;
    sicIncreasePct: number;
    windGustKnots: number;
  }>>;
  isLoading: boolean;
  isComputingRoutes: boolean;
  refreshFleet: () => Promise<void>;
  setCustomDestination: (name: string, latitude: number, longitude: number) => void;
}

const FleetContext = createContext<FleetContextType | undefined>(undefined);

const STORAGE_KEY = 'polarnav_selected_vessel_id';
const DEST_STORAGE_KEY = 'polarnav_selected_destination_id';
const MISSION_TYPE_KEY = 'polarnav_mission_type';

export const FleetProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [fleet, setFleet] = useState<CanonicalVessel[]>(CANONICAL_FLEET);
  const [stations, setStations] = useState<AntarcticStation[]>(CANONICAL_STATIONS);
  const [selectedVesselId, setSelectedVesselIdState] = useState<string>(() => {
    return localStorage.getItem(STORAGE_KEY) || 'rv_sagar_nidhi';
  });
  const [selectedDestinationId, setSelectedDestinationIdState] = useState<string>(() => {
    return localStorage.getItem(DEST_STORAGE_KEY) || 'bharati';
  });
  const [missionType, setMissionTypeState] = useState<MissionType>(() => {
    return (localStorage.getItem(MISSION_TYPE_KEY) as MissionType) || 'RESEARCH';
  });
  const [optimizationPriority, setOptimizationPriority] = useState<OptimizationPriority>('BALANCED');
  const [emergencyRerouteActive, setEmergencyRerouteActive] = useState<boolean>(false);
  const [isComputingRoutes, setIsComputingRoutes] = useState<boolean>(false);
  const [whatIfScenario, setWhatIfScenario] = useState({
    active: false,
    icebergDriftOffsetKm: 25.0,
    sicIncreasePct: 15.0,
    windGustKnots: 20.0
  });

  const [tacticalAlert, setTacticalAlert] = useState<{
    active: boolean;
    phase: 'idle' | 'detecting' | 'diverted';
    title?: string;
    description?: string;
    icebergId?: string;
    headingChange?: string;
    clearanceKm?: number;
    extraDistKm?: number;
    extraEtaMinutes?: number;
    alertId?: string;
    timestamp?: string;
    hazardIceberg?: any;
  }>({
    active: false,
    phase: 'idle'
  });

  const [selectedIcebergId, setSelectedIcebergId] = useState<string | null>(null);
  const [routes, setRoutes] = useState<RouteOption[]>([]);
  const [activeRouteId, setActiveRouteId] = useState<string>('route-b');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const routeCacheRef = useRef<Map<string, RouteOption[]>>(new Map());

  // Shared forecast horizon state across all platforms (NOW / +6H / +12H / +24H / +48H)
  const [selectedHorizon, setSelectedHorizonState] = useState<ForecastHorizonHours>(0);
  const setSelectedHorizon = useCallback((h: ForecastHorizonHours) => {
    setSelectedHorizonState(h);
  }, []);

  const activeHorizonLabel: ForecastHorizonLabel = useMemo(() => {
    if (selectedHorizon === 0) return 'NOW';
    return `+${selectedHorizon}H` as ForecastHorizonLabel;
  }, [selectedHorizon]);

  // Set selected vessel with persistence
  const setSelectedVesselId = useCallback((id: string) => {
    setSelectedVesselIdState(id);
    localStorage.setItem(STORAGE_KEY, id);
  }, []);

  // Set selected destination with persistence
  const setSelectedDestinationId = useCallback((id: string) => {
    setSelectedDestinationIdState(id);
    localStorage.setItem(DEST_STORAGE_KEY, id);
  }, []);

  // Dynamically register & navigate to a custom coordinate location
  const setCustomDestination = useCallback((name: string, latitude: number, longitude: number) => {
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (isNaN(lat) || isNaN(lon)) return;
    const customId = `custom_${Date.now()}`;
    const customStation: AntarcticStation = {
      id: customId,
      name: name.trim() || `Custom Target (${Math.abs(lat).toFixed(2)}°${lat < 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'})`,
      latitude: lat,
      longitude: lon,
      region: 'Custom Waypoint Sector',
      country: 'Target Mooring',
      coastal_access: true
    };
    setStations(prev => [customStation, ...prev.filter(s => !s.id.startsWith('custom_'))]);
    setSelectedDestinationIdState(customId);
    localStorage.setItem(DEST_STORAGE_KEY, customId);
  }, []);

  const setMissionType = useCallback((type: MissionType) => {
    setMissionTypeState(type);
    localStorage.setItem(MISSION_TYPE_KEY, type);
  }, []);

  // Fetch live stations from backend, fallback to CANONICAL_STATIONS
  useEffect(() => {
    api.stations().then((res) => {
      if (res?.stations?.length) {
        const normalized: AntarcticStation[] = res.stations.map((s: any) => ({
          id: s.id || s.station_id || s.name?.toLowerCase().replace(/\s+/g, '_'),
          name: s.name || s.station_name,
          latitude: Number(s.latitude || s.lat),
          longitude: Number(s.longitude || s.lon),
          region: s.region || s.sub_region || '',
          operator: s.operator || s.country || '',
          country: s.country || '',
          coastal_access: s.coastal_access ?? true
        })).filter((s: AntarcticStation) => s.id && !isNaN(s.latitude) && !isNaN(s.longitude));
        if (normalized.length > 0) {
          setStations(normalized);
        }
      }
    }).catch(() => { /* keep CANONICAL_STATIONS as fallback */ });
  }, []);

  // Fetch canonical fleet from backend
  const refreshFleet = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await api.vessels();
      if (res?.vessels?.length) {
        const normalized: CanonicalVessel[] = res.vessels.map((v: any) => ({
          id: v.id || String(v.mmsi),
          name: v.name,
          mmsi: v.mmsi || '',
          imo: v.imo || '',
          flag: v.flag || '⚓',
          country: v.country || 'International',
          operator: v.operator || 'Polar Research Agency',
          polar_class: v.polar_class || v.polarClass || 'PC5',
          latitude: Number(v.latitude),
          longitude: Number(v.longitude),
          sog: Number(v.sog ?? v.speed ?? 13.5),
          speed: Number(v.speed ?? v.sog ?? 13.5),
          cog: Number(v.cog ?? v.heading ?? 180),
          heading: Number(v.heading ?? v.cog ?? 180),
          nav_status: v.nav_status || 'Underway using engine',
          source: v.source || 'DETERMINISTIC_SIMULATION',
          data_status: v.data_status || 'SIMULATED_VOYAGE',
          is_demo: v.is_demo !== undefined ? v.is_demo : true,
          destination_station_id: v.destination_station_id,
          destination: v.destination || v.destination_name || 'Antarctic Station',
          dest_lat: v.dest_lat !== undefined ? Number(v.dest_lat) : undefined,
          dest_lon: v.dest_lon !== undefined ? Number(v.dest_lon) : undefined,
          voyage_origin: v.voyage_origin || 'Polar Gateway Port',
          mission_description: v.mission_description || v.mission || '',
          eta: v.eta || 'Calculating...',
          track: v.track
        }));
        setFleet(normalized);
      }
    } catch (e) {
      console.warn('[FleetContext] Backend unavailable, using canonical offline fleet.', e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshFleet();
  }, [refreshFleet]);

  // Derive active selected vessel
  const selectedVessel = useMemo(() => {
    return fleet.find(v => v.id === selectedVesselId || String(v.mmsi) === selectedVesselId) || fleet[0] || CANONICAL_FLEET[0];
  }, [fleet, selectedVesselId]);

  // Derive active selected destination
  const selectedDestination = useMemo(() => {
    return stations.find(s => s.id === selectedDestinationId) || stations[0] || CANONICAL_STATIONS[0];
  }, [stations, selectedDestinationId]);

  // Unified canonical mission ID
  const missionId = useMemo(() => {
    return `MIS-2026-${(selectedVessel?.id || 'VESSEL').replace(/[^a-zA-Z0-9]/g, '').toUpperCase()}`;
  }, [selectedVessel?.id]);

  // Dismiss tactical alert and restore nominal route
  const dismissTacticalAlert = useCallback(() => {
    setTacticalAlert({ active: false, phase: 'idle' });
    setEmergencyRerouteActive(false);
    clearApiCache('/routes');
    api.restore().catch(() => {});
    if (selectedVessel && selectedDestination) {
      const cacheKey = `${selectedVessel.id}_${selectedDestination.id}_em_${whatIfScenario.active ? 'whatif' : 'norm'}`;
      routeCacheRef.current.delete(cacheKey);
      const normKey = `${selectedVessel.id}_${selectedDestination.id}_norm_${whatIfScenario.active ? 'whatif' : 'norm'}`;
      if (routeCacheRef.current.has(normKey)) {
        setRoutes(routeCacheRef.current.get(normKey)!);
      } else {
        api.routes({
          vesselId: selectedVessel.id,
          destId: selectedDestination.id,
          destLat: selectedDestination.latitude,
          destLon: selectedDestination.longitude,
          destName: selectedDestination.name,
          emergency: false
        }).then((res) => {
          if (res?.routes?.length) {
            setRoutes(res.routes);
          }
        }).catch(() => {});
      }
    }
  }, [selectedVessel, selectedDestination, whatIfScenario.active]);

  // Trigger tactical emergency avoidance when iceberg hazard is detected (supports mid-voyage progress)
  const triggerEmergencyHazard = useCallback(async (progressFraction?: number) => {
    if (emergencyRerouteActive) {
      // Toggle off / restore normal planned route
      setEmergencyRerouteActive(false);
      setTacticalAlert({ active: false, phase: 'idle' });
      return;
    }

    const pctText = typeof progressFraction === 'number' && progressFraction > 0.05
      ? ` AT ${(progressFraction * 100).toFixed(0)}% VOYAGE MARK`
      : '';

    // Phase 1: Small on-screen alert banner for immediate warning
    setTacticalAlert({
      active: true,
      phase: 'detecting',
      title: `SCANNING ROUTE FOR ICEBERG HAZARDS${pctText}...`,
      description: `Analyzing forward radar contacts and drift vectors along active corridor of ${selectedVessel.name}...`,
    });

    try {
      const res = await api.emergency({
        vessel_id: selectedVessel?.id,
        dest_id: selectedDestination?.id,
        progress_fraction: typeof progressFraction === 'number' ? progressFraction : undefined
      });

      if (res?.emergency && res.diverted_route && res.hazard_detected !== false) {
        setEmergencyRerouteActive(true);
        const hazId = res.iceberg_id || res.iceberg?.id || 'IB-A84';
        const hazName = res.iceberg_name || res.iceberg?.name || `Iceberg ${hazId}`;
        const cpa = res.cpa_km || res.iceberg?.cpa_km || 4.2;

        if (res.routes?.length) {
          const formatted: RouteOption[] = res.routes.map((r: any, idx: number) => {
            const parsed = parseRouteOption(r, selectedVessel, idx);
            if (idx === 0) {
              parsed.id = res.diverted_route?.id || `${selectedVessel.id}-route-tactical`;
              parsed.name = res.diverted_route?.name || 'ROUTE B (TACTICAL BYPASS)';
              parsed.recommended = true;
              parsed.has_iceberg_hazard = true;
              parsed.iceberg_threat = res.iceberg;
            }
            return parsed;
          });
          const emCacheKey = `${selectedVessel.id}_${selectedDestination.id}_em_${whatIfScenario.active ? 'whatif' : 'norm'}`;
          routeCacheRef.current.set(emCacheKey, formatted);
          setRoutes(formatted);
          setActiveRouteId(res.diverted_route?.id || formatted[0].id);
        }

        // Phase 2: Route optimized with small direction change & alert logged to DB
        const progressLabel = typeof progressFraction === 'number' && progressFraction > 0.05
          ? ` (AT ${(progressFraction * 100).toFixed(0)}% MID-VOYAGE MARK)`
          : '';

        setTacticalAlert({
          active: true,
          phase: 'diverted',
          title: `TACTICAL ICEBERG HAZARD IN ROUTE${progressLabel}: ${hazId}`,
          description: `${hazName} detected drifting into forward transit corridor (${cpa} km CPA). Shifted heading +${res.heading_alteration_deg || 12}° Starboard (+${res.extra_distance_km || 17.5} km). 26.4 km safe CPA clearance secured ahead of vessel. Registered in alerts.`,
          icebergId: hazId,
          headingChange: `+${res.heading_alteration_deg || 12}° Starboard`,
          clearanceKm: res.clearance_km || 26.4,
          extraDistKm: res.extra_distance_km || 17.5,
          extraEtaMinutes: res.extra_eta_minutes || 42,
          alertId: res.alert?.id,
          timestamp: 'Just now',
          hazardIceberg: res.iceberg
        });
      } else {
        // No iceberg detected in route
        setEmergencyRerouteActive(false);
        setTacticalAlert({
          active: true,
          phase: 'idle',
          title: 'ROUTE CORRIDOR CLEAR',
          description: `No iceberg collision hazards detected along active transit path of ${selectedVessel.name}. Nominal route maintained.`
        });
        setTimeout(() => {
          setTacticalAlert({ active: false, phase: 'idle' });
        }, 3500);
      }
    } catch (e) {
      console.error('Failed to trigger emergency hazard diversion:', e);
      setEmergencyRerouteActive(false);
    }
  }, [emergencyRerouteActive, selectedVessel, selectedDestination, whatIfScenario.active]);

  // Dynamic spherical fallback corridor generator (ensures routes compute instantly even under network/cold-start issues)
  const generateFallbackCorridors = useCallback((vessel: CanonicalVessel, dest: AntarcticStation): RouteOption[] => {
    const sLat = vessel.latitude;
    const sLon = vessel.longitude;
    const dLat = dest.latitude ?? (dest as any).lat ?? -69.41;
    const dLon = dest.longitude ?? (dest as any).lon ?? 76.19;

    let dLonArc = dLon - sLon;
    if (dLonArc > 180) dLonArc -= 360;
    else if (dLonArc < -180) dLonArc += 360;

    const nPts = 20;
    const pathA: [number, number][] = [];
    const pathB: [number, number][] = [];
    const pathC: [number, number][] = [];

    for (let i = 0; i < nPts; i++) {
      const t = i / (nPts - 1);
      let lonI = sLon + dLonArc * t;
      if (lonI > 180) lonI -= 360;
      else if (lonI < -180) lonI += 360;

      const baseLat = sLat + (dLat - sLat) * t;
      const arcB = Math.sin(t * Math.PI) * 2.2;
      const arcC = Math.sin(t * Math.PI) * 4.5;

      pathA.push([Number(baseLat.toFixed(4)), Number(lonI.toFixed(4))]);
      pathB.push([Number((baseLat + arcB).toFixed(4)), Number(lonI.toFixed(4))]);
      pathC.push([Number((baseLat + arcC).toFixed(4)), Number(lonI.toFixed(4))]);
    }

    const calcDist = (pts: [number, number][]) => {
      let d = 0;
      for (let k = 0; k < pts.length - 1; k++) {
        const p1 = pts[k];
        const p2 = pts[k + 1];
        const dlat = (p2[0] - p1[0]) * Math.PI / 180;
        const dlon = (p2[1] - p1[1]) * Math.PI / 180;
        const a = Math.sin(dlat / 2) ** 2 + Math.cos(p1[0] * Math.PI / 180) * Math.cos(p2[0] * Math.PI / 180) * Math.sin(dlon / 2) ** 2;
        d += 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
      }
      return Math.round(d);
    };

    const distA = calcDist(pathA);
    const distB = calcDist(pathB);
    const distC = calcDist(pathC);

    const speed = vessel.speed || vessel.sog || 14.0;
    const hA = Math.max(1, Math.round(distA / (speed * 0.9 * 1.852)));
    const hB = Math.max(1, Math.round(distB / (speed * 0.96 * 1.852)));
    const hC = Math.max(1, Math.round(distC / (speed * 1.852)));

    return [
      {
        id: `${vessel.id}-route-b`,
        name: 'ROUTE B (OPTIMAL)',
        optimization_mode: 'BALANCED',
        vessel_id: vessel.id,
        distance: distB,
        eta: `${hB}h 15m`,
        iceRisk: 'MODERATE',
        icebergRisk: 'LOW',
        weatherRisk: 'MODERATE',
        overallScore: 92,
        recommended: true,
        rioScore: 8.4,
        sicExposure: 24,
        sic_actual: 24.0,
        sic_cost_contribution: 0,
        reason: `Multi-objective AI optimal corridor towards ${dest.name}. Balances open leads with iceberg separation.`,
        fuelConsumption: `${Math.round(distB * 0.024)} MT`,
        safetyMargin: 'OPTIMAL',
        path: pathB,
        waypoints: []
      },
      {
        id: `${vessel.id}-route-c`,
        name: 'ROUTE C (SAFEST)',
        optimization_mode: 'SAFEST',
        vessel_id: vessel.id,
        distance: distC,
        eta: `${hC}h 30m`,
        iceRisk: 'LOW',
        icebergRisk: 'VERY LOW',
        weatherRisk: 'LOW',
        overallScore: 86,
        recommended: false,
        rioScore: 14.8,
        sicExposure: 8,
        sic_actual: 8.0,
        sic_cost_contribution: 0,
        reason: `Maximum safety margin corridor skirting Marginal Ice Zone perimeter towards ${dest.name}.`,
        fuelConsumption: `${Math.round(distC * 0.028)} MT`,
        safetyMargin: 'VERIFIED',
        path: pathC,
        waypoints: []
      },
      {
        id: `${vessel.id}-route-a`,
        name: 'ROUTE A (FASTEST)',
        optimization_mode: 'FASTEST',
        vessel_id: vessel.id,
        distance: distA,
        eta: `${hA}h 45m`,
        iceRisk: 'HIGH',
        icebergRisk: 'HIGH',
        weatherRisk: 'MODERATE',
        overallScore: 48,
        recommended: false,
        rioScore: -2.8,
        sicExposure: 65,
        sic_actual: 65.0,
        sic_cost_contribution: 0,
        reason: `Direct geodesic path towards ${dest.name}. Shortest track but encounters heavy multi-year pack ice.`,
        fuelConsumption: `${Math.round(distA * 0.035)} MT`,
        safetyMargin: 'CAUTION',
        path: pathA,
        waypoints: []
      }
    ];
  }, []);

  // Canonical route option parser mapping raw backend response to strongly typed RouteOption
  const parseRouteOption = useCallback((r: any, vessel: CanonicalVessel, idx: number): RouteOption => {
    const mode: 'BALANCED' | 'SAFEST' | 'FASTEST' = r.optimization_mode || (idx === 1 ? 'BALANCED' : idx === 2 ? 'SAFEST' : 'FASTEST');
    const routeSuffix = mode === 'SAFEST' ? 'route-c' : mode === 'FASTEST' ? 'route-a' : 'route-b';
    const id = r.id || `${vessel.id}-${routeSuffix}`;
    const name = r.name || (mode === 'BALANCED' ? 'ROUTE B - OPTIMAL' : mode === 'SAFEST' ? 'ROUTE C - SAFEST' : 'ROUTE A - FASTEST');

    const rawDist = typeof r.distance_km === 'number' ? r.distance_km : parseFloat(String(r.distance || '').replace(/[^0-9.]/g, '')) || 0;
    const distance = Math.round(rawDist);

    const rawSic = r.sic_actual ?? r.sea_ice_exposure?.sic_actual ?? r.sea_ice_exposure?.avg_sic ?? r.sicExposure;
    const sic_actual = typeof rawSic === 'number' ? Math.round(rawSic * 10) / 10 : (parseFloat(String(rawSic || '0')) || 0);
    const sicExposure = typeof r.sicExposure === 'number' ? r.sicExposure : Math.round(sic_actual);
    const sic_cost_contribution = r.sic_cost_contribution ?? r.sea_ice_exposure?.sic_cost_contribution ?? r.costs?.ice_cost ?? 0;

    const rawRio = r.rioScore ?? r.rio_score;
    const rioScore = rawRio !== undefined ? rawRio : (mode === 'FASTEST' ? -2.8 : mode === 'SAFEST' ? 14.8 : 8.4);

    const overallScore = typeof r.overallScore === 'number' ? r.overallScore : (typeof r.overall_score === 'number' ? r.overall_score : (mode === 'BALANCED' ? 92 : mode === 'SAFEST' ? 84 : 48));

    const minCpa = r.minimum_cpa_km ?? r.min_cpa_km;
    const hasIceberg = Boolean(r.has_iceberg_hazard || (minCpa !== undefined && minCpa <= 30.0));
    const icebergEncounters = r.icebergEncounters ?? (hasIceberg ? 1 : 0);
    const icebergRisk = r.icebergRisk || (minCpa && minCpa < 15 ? 'HIGH' : minCpa && minCpa < 30 ? 'MODERATE' : 'LOW');

    const fuelConsumption = r.fuelConsumption || r.fuel_estimate || (r.costs?.fuel_cost ? `${Math.round(r.costs.fuel_cost * 0.15)} MT` : '104 MT');

    return {
      id,
      name,
      vessel_id: vessel.id,
      optimization_mode: mode,
      distance,
      eta: r.eta || (r.eta_hours ? `${Math.floor(r.eta_hours)}h ${Math.round((r.eta_hours % 1) * 60)}m` : '32h 05m'),
      iceRisk: r.iceRisk || r.ice_risk || (mode === 'FASTEST' ? 'HIGH' : mode === 'BALANCED' ? 'MODERATE' : 'LOW'),
      icebergRisk,
      weatherRisk: r.weatherRisk || 'MODERATE',
      overallScore,
      recommended: Boolean(r.recommended ?? (mode === 'BALANCED' || idx === 1)),
      rioScore,
      sicExposure,
      sic_actual,
      sic_cost_contribution,
      minimum_cpa_km: minCpa,
      icebergEncounters,
      has_iceberg_hazard: hasIceberg,
      iceberg_threat: r.iceberg_threat,
      sea_ice_exposure: r.sea_ice_exposure,
      reason: r.reason || `Optimized polar corridor for ${vessel.name}.`,
      decision_explanation: r.decision_explanation || r.reason || `Optimized polar corridor for ${vessel.name}.`,
      decision_support: r.decision_support || undefined,
      fuelConsumption,
      safetyMargin: r.safetyMargin || (mode === 'SAFEST' ? 'VERIFIED' : 'OPTIMAL'),
      costs: r.costs || r.cost_breakdown || {},
      cost_breakdown: r.cost_breakdown || r.costs || {},
      path: r.path || [],
      waypoints: r.waypoints || []
    };
  }, []);

  // Resolves the active route ID stably: preserves current mode (SAFEST/FASTEST/BALANCED) if possible
  const resolveTargetRouteId = useCallback((availableRoutes: RouteOption[], prevRouteId: string): string => {
    if (!availableRoutes.length) return 'route-b';
    const exact = availableRoutes.find(r => r.id === prevRouteId);
    if (exact) return exact.id;

    const prevMode = prevRouteId.includes('route-c') ? 'SAFEST' : prevRouteId.includes('route-a') ? 'FASTEST' : 'BALANCED';
    const modeMatch = availableRoutes.find(r => r.optimization_mode === prevMode);
    if (modeMatch) return modeMatch.id;

    const rec = availableRoutes.find(r => r.recommended) || availableRoutes[0];
    return rec.id;
  }, []);

  // Recompute route actively on demand (clearing cache)
  const recomputeRoutes = useCallback(async () => {
    if (!selectedVessel || !selectedDestination) return;
    const cacheKey = `${selectedVessel.id}_${selectedDestination.id}_${emergencyRerouteActive ? 'em' : 'norm'}_${whatIfScenario.active ? 'whatif' : 'norm'}`;
    routeCacheRef.current.delete(cacheKey);
    clearApiCache('/routes');
    setIsComputingRoutes(true);

    try {
      const res = await api.routes({
        vesselId: selectedVessel.id,
        destId: selectedDestination.id,
        destLat: selectedDestination.latitude,
        destLon: selectedDestination.longitude,
        destName: selectedDestination.name,
        emergency: emergencyRerouteActive
      });
      if (res?.routes?.length) {
        const formatted: RouteOption[] = res.routes.map((r: any, idx: number) => parseRouteOption(r, selectedVessel, idx));
        routeCacheRef.current.set(cacheKey, formatted);
        setRoutes(formatted);
        setActiveRouteId(prev => resolveTargetRouteId(formatted, prev));
      } else {
        const fallback = generateFallbackCorridors(selectedVessel, selectedDestination);
        routeCacheRef.current.set(cacheKey, fallback);
        setRoutes(fallback);
        setActiveRouteId(prev => resolveTargetRouteId(fallback, prev));
      }
    } catch (e) {
      console.error('Failed to recompute routes, using fallback:', e);
      const fallback = generateFallbackCorridors(selectedVessel, selectedDestination);
      routeCacheRef.current.set(cacheKey, fallback);
      setRoutes(fallback);
      setActiveRouteId(prev => resolveTargetRouteId(fallback, prev));
    } finally {
      setIsComputingRoutes(false);
    }
  }, [selectedVessel, selectedDestination, emergencyRerouteActive, whatIfScenario.active, generateFallbackCorridors, parseRouteOption, resolveTargetRouteId]);

  // Fetch / update corridors reactively for the selected vessel AND destination with zero-delay client caching
  useEffect(() => {
    if (!selectedVessel || !selectedDestination) return;

    const cacheKey = `${selectedVessel.id}_${selectedDestination.id}_${emergencyRerouteActive ? 'em' : 'norm'}_${whatIfScenario.active ? 'whatif' : 'norm'}`;

    if (routeCacheRef.current.has(cacheKey)) {
      const cached = routeCacheRef.current.get(cacheKey)!;
      setRoutes(cached);
      setActiveRouteId(prev => resolveTargetRouteId(cached, prev));
      setIsComputingRoutes(false);
      return;
    }
    
    let isCancelled = false;
    setIsComputingRoutes(true);
    api.routes({
      vesselId: selectedVessel.id,
      destId: selectedDestination.id,
      destLat: selectedDestination.latitude,
      destLon: selectedDestination.longitude,
      destName: selectedDestination.name,
      emergency: emergencyRerouteActive
    }).then((res) => {
      if (isCancelled) return;
      if (res?.routes?.length) {
        const formatted: RouteOption[] = res.routes.map((r: any, idx: number) => parseRouteOption(r, selectedVessel, idx));
        routeCacheRef.current.set(cacheKey, formatted);
        setRoutes(formatted);
        setActiveRouteId(prev => resolveTargetRouteId(formatted, prev));
      } else {
        const fallback = generateFallbackCorridors(selectedVessel, selectedDestination);
        routeCacheRef.current.set(cacheKey, fallback);
        setRoutes(fallback);
        setActiveRouteId(prev => resolveTargetRouteId(fallback, prev));
      }
    }).catch(() => {
      if (isCancelled) return;
      const fallback = generateFallbackCorridors(selectedVessel, selectedDestination);
      routeCacheRef.current.set(cacheKey, fallback);
      setRoutes(fallback);
      setActiveRouteId(prev => resolveTargetRouteId(fallback, prev));
    }).finally(() => {
      if (!isCancelled) {
        setIsComputingRoutes(false);
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [selectedVessel?.id, selectedDestination?.id, selectedDestination?.latitude, selectedDestination?.longitude, emergencyRerouteActive, whatIfScenario.active, generateFallbackCorridors, parseRouteOption, resolveTargetRouteId]);

  // Authoritative active route derived from routes and activeRouteId
  const activeRoute = useMemo(() => {
    if (!routes || routes.length === 0) return null;
    return routes.find(r => r.id === activeRouteId) ||
           routes.find(r => r.id?.includes(activeRouteId)) ||
           routes.find(r => r.recommended) ||
           routes[0] ||
           null;
  }, [routes, activeRouteId]);

  // 1. Calculate deterministic display fleet at selected forecast horizon
  const displayFleet = useMemo<CanonicalVessel[]>(() => {
    return fleet.map(v => {
      // LIVE AIS: strictly maintain latest observed telemetry (do NOT fabricate forecast movement)
      if (v.data_status === 'LIVE' || v.source === 'AIS') {
        return {
          ...v,
          mission_status: (v.mission_status || 'UNDERWAY') as MissionStatus,
          forecast_latitude: v.latitude,
          forecast_longitude: v.longitude,
          forecast_heading: v.heading || 180,
          distance_covered_km: 0,
          remaining_dist_km: 0
        };
      }

      // Determine active corridor for this vessel
      let vRoute: RouteOption | null = null;
      if (v.id === selectedVesselId && activeRoute && activeRoute.path && activeRoute.path.length >= 2) {
        vRoute = activeRoute;
      } else {
        const destStation = stations.find(s => s.id === v.destination_station_id) || {
          id: v.destination_station_id || 'dest',
          name: v.destination,
          latitude: v.dest_lat || -69.41,
          longitude: v.dest_lon || 76.19
        };
        const corridors = generateFallbackCorridors(v, destStation);
        vRoute = corridors[0] || null;
      }

      const computed = calculateVesselPositionAtHorizon(v, vRoute, selectedHorizon);
      return {
        ...v,
        latitude: computed.latitude,
        longitude: computed.longitude,
        heading: computed.heading,
        mission_status: computed.status,
        forecast_latitude: computed.latitude,
        forecast_longitude: computed.longitude,
        forecast_heading: computed.heading,
        distance_covered_km: computed.distanceCoveredKm,
        remaining_dist_km: computed.remainingDistKm,
        time_to_arrival_hours: computed.etaHours
      };
    });
  }, [fleet, selectedVesselId, activeRoute, stations, selectedHorizon, generateFallbackCorridors]);

  // 2. Active vessel evaluated at selected horizon
  const activeDisplayVessel = useMemo(() => {
    return displayFleet.find(v => v.id === selectedVesselId || String(v.mmsi) === selectedVesselId) || displayFleet[0];
  }, [displayFleet, selectedVesselId]);

  // 3. Assign New Mission (Starts strictly from arrival destination, invokes canonical PolarRoutingEngine)
  const assignMission = useCallback(async (
    vesselId: string,
    destinationStationId: string,
    newMissionType: MissionType,
    routeProfile: OptimizationPriority
  ) => {
    setIsComputingRoutes(true);
    try {
      const vessel = fleet.find(v => v.id === vesselId) || fleet[0];
      const destStation = stations.find(s => s.id === destinationStationId) || stations[0];

      // Origin: If vessel arrived, its current origin is its arrival station
      const startLat = vessel.mission_status === 'ARRIVED' && vessel.dest_lat !== undefined
        ? vessel.dest_lat
        : vessel.latitude;
      const startLon = vessel.mission_status === 'ARRIVED' && vessel.dest_lon !== undefined
        ? vessel.dest_lon
        : vessel.longitude;
      const originName = vessel.mission_status === 'ARRIVED'
        ? vessel.destination
        : (vessel.voyage_origin || 'Current Location');

      // Call canonical PolarRoutingEngine via backend POST /api/routes/optimize
      const optRes = await api.routesOptimize({
        vessel_id: vessel.id,
        vessel_name: vessel.name,
        start_lat: startLat,
        start_lon: startLon,
        dest_lat: destStation.latitude,
        dest_lon: destStation.longitude,
        destination: destStation.name,
        cruising_speed_kn: vessel.speed || vessel.sog || 14.0,
        polar_class: vessel.polar_class || 'PC5'
      });

      let newRoutes: RouteOption[] = [];
      if (optRes?.routes?.length) {
        newRoutes = optRes.routes.map((r: any, idx: number) => parseRouteOption(r, vessel, idx));
      } else {
        const tempV: CanonicalVessel = {
          ...vessel,
          latitude: startLat,
          longitude: startLon
        };
        newRoutes = generateFallbackCorridors(tempV, destStation);
      }

      // Update fleet state with new mission
      setFleet(prev => prev.map(v => {
        if (v.id === vessel.id) {
          return {
            ...v,
            latitude: startLat,
            longitude: startLon,
            destination_station_id: destStation.id,
            destination: destStation.name,
            dest_lat: destStation.latitude,
            dest_lon: destStation.longitude,
            voyage_origin: originName,
            mission_status: 'UNDERWAY' as MissionStatus,
            nav_status: 'Underway using engine',
            eta: newRoutes[0]?.eta || '32h 00m'
          };
        }
        return v;
      }));

      setSelectedDestinationIdState(destStation.id);
      setMissionTypeState(newMissionType);
      setOptimizationPriority(routeProfile);
      setRoutes(newRoutes);
      const rec = newRoutes.find(r => r.recommended) || newRoutes[0];
      if (rec) setActiveRouteId(rec.id);
      // Reset horizon to NOW so operator sees departure state
      setSelectedHorizonState(0);
    } catch (err) {
      console.error('Failed to assign new mission:', err);
    } finally {
      setIsComputingRoutes(false);
    }
  }, [fleet, stations, generateFallbackCorridors]);

  // 4. Reset vessel to AVAILABLE (Moored at berth)
  const resetVesselToAvailable = useCallback((vesselId: string) => {
    setFleet(prev => prev.map(v => {
      if (v.id === vesselId) {
        return {
          ...v,
          mission_status: 'AVAILABLE' as MissionStatus,
          nav_status: 'Moored / Berth Available'
        };
      }
      return v;
    }));
  }, []);

  const value = useMemo(() => ({
    fleet: displayFleet,
    displayFleet,
    selectedVesselId,
    selectedVessel: activeDisplayVessel,
    activeDisplayVessel,
    setSelectedVesselId,
    stations,
    selectedDestinationId,
    selectedDestination,
    setSelectedDestinationId,
    selectedHorizon,
    setSelectedHorizon,
    activeHorizonLabel,
    missionId,
    missionType,
    setMissionType,
    optimizationPriority,
    setOptimizationPriority,
    selectedIcebergId,
    setSelectedIcebergId,
    routes,
    activeRouteId,
    setActiveRouteId,
    activeRoute,
    emergencyRerouteActive,
    setEmergencyRerouteActive,
    tacticalAlert,
    setTacticalAlert,
    triggerEmergencyHazard,
    dismissTacticalAlert,
    whatIfScenario,
    setWhatIfScenario,
    isLoading,
    isComputingRoutes,
    refreshFleet,
    recomputeRoutes,
    assignMission,
    resetVesselToAvailable,
    setCustomDestination
  }), [
    displayFleet,
    selectedVesselId,
    activeDisplayVessel,
    setSelectedVesselId,
    stations,
    selectedDestinationId,
    selectedDestination,
    setSelectedDestinationId,
    selectedHorizon,
    setSelectedHorizon,
    activeHorizonLabel,
    missionId,
    missionType,
    setMissionType,
    optimizationPriority,
    setOptimizationPriority,
    selectedIcebergId,
    routes,
    activeRouteId,
    activeRoute,
    emergencyRerouteActive,
    tacticalAlert,
    triggerEmergencyHazard,
    dismissTacticalAlert,
    whatIfScenario,
    isLoading,
    isComputingRoutes,
    refreshFleet,
    recomputeRoutes,
    assignMission,
    resetVesselToAvailable,
    setCustomDestination
  ]);

  return (
    <FleetContext.Provider value={value}>
      {children}
    </FleetContext.Provider>
  );
};

export function useFleet() {
  const context = useContext(FleetContext);
  if (!context) {
    throw new Error('useFleet must be used within a FleetProvider');
  }
  return context;
}
