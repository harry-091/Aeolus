export interface Vessel {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  heading: number;
  speed: number;
  destination: string;
  eta: string;
}

export interface IcebergForecastPoint {
  horizon: 'NOW' | '+6H' | '+12H' | '+24H' | '+48H';
  timeLabel: string;
  coordinates: [number, number];
  displacementKm: number;
  speedKn: number;
}

export interface IcebergRouteIntersection {
  hasIntersection: boolean;
  riskLevel: 'HIGH' | 'MODERATE' | 'LOW' | 'NONE';
  proximity: string;
  estimatedTime: string;
  closestPointCoordinates?: [number, number];
  recommendedAction: string;
}

export interface IcebergConfidenceFactors {
  recentObservations: number;
  historicalMovement: number;
  oceanCurrentConditions: number;
  windConditions: number;
  summary: string;
}

export interface Iceberg {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  velocity: number;
  direction: string;
  movementTrend: string;
  size: number; // in km
  areaKm2: number;
  draftEstimate: number; // in meters
  confidence: number; // %
  risk: 'SAFE' | 'CAUTION' | 'HIGH' | 'CRITICAL';
  distanceFromVessel: string;
  lastObserved: string;
  sensorSource: string;
  historicalTrajectory: [number, number][];
  predictedTrajectory: [number, number][];
  forecastPoints: IcebergForecastPoint[];
  routeIntersection: IcebergRouteIntersection;
  confidenceFactors: IcebergConfidenceFactors;
}

export interface RouteOption {
  id: string;
  name: string;
  distance: number;
  eta: string;
  iceRisk: string;
  icebergRisk: string;
  weatherRisk: string;
  overallScore: number;
  recommended: boolean;
  reason?: string;
  path: [number, number][];
}

export const mockVessel: Vessel = {
  id: 'rv_sagar_nidhi',
  name: 'R/V Sagar Nidhi — DEMO',
  latitude: -54.20,
  longitude: 68.40,
  heading: 188,
  speed: 13.5,
  destination: 'Bharati Research Station',
  eta: '32h 05m',
};

export const mockIcebergs: Iceberg[] = [];

export interface NavigationWaypoint {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  distanceFromStart: number;
  eta: string;
  status: 'passed' | 'active' | 'upcoming';
  iceRisk: 'LOW' | 'MODERATE' | 'HIGH';
}

export const mockWaypoints: NavigationWaypoint[] = [
  { id: 'wp-01', name: 'WP-01 Cape Agulhas Departure', latitude: -34.83, longitude: 20.01, distanceFromStart: 0, eta: 'Passed', status: 'passed', iceRisk: 'LOW' },
  { id: 'wp-02', name: 'WP-02 Polar Front Crossing', latitude: -56.50, longitude: 16.20, distanceFromStart: 2410, eta: 'Passed', status: 'passed', iceRisk: 'LOW' },
  { id: 'wp-03', name: 'WP-03 Marginal Ice Edge Entry', latitude: -68.31, longitude: 12.48, distanceFromStart: 3820, eta: 'Current', status: 'active', iceRisk: 'MODERATE' },
  { id: 'wp-04', name: 'WP-04 Queen Maud Sounding', latitude: -69.50, longitude: 5.50, distanceFromStart: 4120, eta: '+11h 20m', status: 'upcoming', iceRisk: 'LOW' },
  { id: 'wp-05', name: 'WP-05 Shelf Approach Point', latitude: -70.80, longitude: -5.20, distanceFromStart: 4450, eta: '+23h 40m', status: 'upcoming', iceRisk: 'MODERATE' },
  { id: 'wp-06', name: 'WP-06 Bharati / Maitri Terminus', latitude: -73.10, longitude: -20.50, distanceFromStart: 4699, eta: '+32h 05m', status: 'upcoming', iceRisk: 'LOW' },
];

export interface OperationalAlert {
  id: string;
  severity: 'CRITICAL' | 'HIGH' | 'CAUTION' | 'ADVISORY' | 'RESOLVED';
  category: 'ICEBERG' | 'SEA_ICE' | 'WEATHER' | 'NAVIGATION';
  title: string;
  description: string;
  location: string;
  timestamp: string;
  timeRelative: string;
  mitigation?: string;
  targetId?: string;
  acknowledged?: boolean;
}

export const mockAlerts: OperationalAlert[] = [
  {
    id: 'ALT-1092',
    severity: 'HIGH',
    category: 'ICEBERG',
    title: 'Iceberg A-17 Trajectory Intersect Warning',
    description: 'Iceberg A-17 projected 48h trajectory intersects Route A corridor. Closest Point of Approach (CPA) is 14.2 km at T+18.6h with 87% model confidence.',
    location: '72°28\'S, 18°16\'W (Sector 3)',
    timestamp: '2026-08-29T12:45:00Z',
    timeRelative: '18m ago',
    mitigation: 'Implement Recommended Route B diversion via Waypoint WP-04 (+37 km, 52% lower exposure).',
    targetId: 'A-17',
    acknowledged: false,
  },
  {
    id: 'ALT-1091',
    severity: 'CAUTION',
    category: 'SEA_ICE',
    title: 'Sea-Ice Compaction Increase in Sector 3',
    description: 'Convergent wind stress (18 kn NE) is driving ice compaction along the northern shelf boundary. Average concentration rising from 58% to 74%.',
    location: '69°30\'S to 71°00\'S',
    timestamp: '2026-08-29T11:30:00Z',
    timeRelative: '1h 33m ago',
    mitigation: 'Maintain minimum vessel speed at 8.5 kn to prevent besetting in medium floes.',
    acknowledged: true,
  },
  {
    id: 'ALT-1089',
    severity: 'ADVISORY',
    category: 'WEATHER',
    title: 'Katabatic Wind Squall Window Forecast',
    description: 'Coastal gravity flow expected off Queen Maud Land ice shelf starting at T+26h. Gusts up to 38 kn with rapid visibility reduction to 2.5 km.',
    location: 'Approach Corridor WP-05',
    timestamp: '2026-08-29T09:15:00Z',
    timeRelative: '3h 48m ago',
    mitigation: 'Plan speed adjustments to transit open water section prior to squall onset.',
    acknowledged: true,
  },
  {
    id: 'ALT-1082',
    severity: 'RESOLVED',
    category: 'NAVIGATION',
    title: 'Bergy Bit Cluster Cleared in Sector 1',
    description: 'Small growler and bergy bit field detected by SAR imagery has dispersed westward away from track.',
    location: '68°10\'S, 14°00\'E',
    timestamp: '2026-08-29T04:20:00Z',
    timeRelative: '8h ago',
    acknowledged: true,
  }
];

export interface SeaIceSector {
  sector: string;
  name: string;
  concentration: number;
  iceType: string;
  thickness: string;
  driftRate: string;
  riskLevel: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
}

export const mockIceSectors: SeaIceSector[] = [
  { sector: 'SEC-01', name: 'Marginal Ice Zone (MIZ)', concentration: 22, iceType: 'Open Drift Ice / Nilas', thickness: '0.15 - 0.30 m', driftRate: '0.45 m/s WSW', riskLevel: 'LOW' },
  { sector: 'SEC-02', name: 'Outer Pack Ice Corridor', concentration: 54, iceType: 'First-Year Thin Floes', thickness: '0.50 - 0.90 m', driftRate: '0.33 m/s SW', riskLevel: 'MODERATE' },
  { sector: 'SEC-03', name: 'Queen Maud Approach Shelf', concentration: 76, iceType: 'First-Year Medium / Compacting', thickness: '1.20 - 1.60 m', driftRate: '0.28 m/s W', riskLevel: 'HIGH' },
  { sector: 'SEC-04', name: 'Coastal Fast Ice Boundary', concentration: 94, iceType: 'Landfast / Multi-Year Ridge', thickness: '2.10 - 2.80 m', driftRate: '0.05 m/s (Stationary)', riskLevel: 'CRITICAL' },
];

export interface AssessmentReport {
  id: string;
  vessel: string;
  voyageCode: string;
  destination: string;
  assessmentTime: string;
  assessor: string;
  overallRisk: 'LOW' | 'MODERATE' | 'HIGH';
  recommendedRoute: string;
  keyHazards: string[];
  recommendation: string;
  polarCodeCompliant: boolean;
  status: 'ACTIVE' | 'ARCHIVED';
}

export const mockReports: AssessmentReport[] = [
  {
    id: 'REP-2026-0829-01',
    vessel: 'RV SARASWATI (IMO 9842104)',
    voyageCode: 'EXP-45-WEDDELL',
    destination: 'Antarctic Research Station (Maitri / Bharati)',
    assessmentTime: '2026-08-29 12:00 UTC',
    assessor: 'Antarctic Nav Decision Support Engine v3.4',
    overallRisk: 'MODERATE',
    recommendedRoute: 'ROUTE B (879 km · ETA 32h 05m · Score 82/100)',
    keyHazards: [
      'Iceberg A-17 trajectory intersecting direct Route A within 18.6 hours',
      'Rising sea ice concentration (76%) in Queen Maud Approach Shelf',
      'Katabatic wind squalls forecast at coastal shelf transit (T+26h)'
    ],
    recommendation: 'Adopt Route B navigation plan. Divert around Iceberg A-17 via Waypoint WP-04. Maintain continuous 3cm radar watch and reduce speed to 9.5 kn upon entering Sector 3.',
    polarCodeCompliant: true,
    status: 'ACTIVE'
  },
  {
    id: 'REP-2026-0828-02',
    vessel: 'RV SARASWATI (IMO 9842104)',
    voyageCode: 'EXP-45-WEDDELL',
    destination: 'Antarctic Research Station (Maitri / Bharati)',
    assessmentTime: '2026-08-28 12:00 UTC',
    assessor: 'Antarctic Nav Decision Support Engine v3.4',
    overallRisk: 'LOW',
    recommendedRoute: 'ROUTE A (Open Water Leg)',
    keyHazards: [
      'Polar Front crossing turbulence',
      'Isolated bergy bits in marginal zone'
    ],
    recommendation: 'Maintain standard open ocean transit speed of 13 kn along bearing 074°.',
    polarCodeCompliant: true,
    status: 'ARCHIVED'
  }
];

export const mockRoutes: RouteOption[] = [
  {
    id: 'route-a',
    name: 'ROUTE A',
    distance: 842,
    eta: '31h 20m',
    iceRisk: 'HIGH',
    icebergRisk: 'HIGH',
    weatherRisk: 'MODERATE',
    overallScore: 45,
    recommended: false,
    path: [
      [-68.31, 12.48],
      [-70.1, 0.5],
      [-71.5, -10.2],
      [-73.1, -20.5]
    ]
  },
  {
    id: 'route-b',
    name: 'ROUTE B',
    distance: 879,
    eta: '32h 05m',
    iceRisk: 'LOW',
    icebergRisk: 'LOW',
    weatherRisk: 'MODERATE',
    overallScore: 82,
    recommended: true,
    reason: 'Route B adds 4.4% distance while reducing projected ice-related exposure by 52%.',
    path: [
      [-68.31, 12.48],
      [-69.5, 5.5],
      [-70.8, -5.2],
      [-73.1, -20.5]
    ]
  },
  {
    id: 'route-c',
    name: 'ROUTE C',
    distance: 925,
    eta: '34h 10m',
    iceRisk: 'VERY LOW',
    icebergRisk: 'LOW',
    weatherRisk: 'LOW',
    overallScore: 78,
    recommended: false,
    path: [
      [-68.31, 12.48],
      [-68.8, 8.5],
      [-70.2, -2.2],
      [-73.1, -20.5]
    ]
  }
];

export const mockEnvironmental = {
  seaIceConcentration: 64, // percentage
  iceDrift: 0.31, // m/s
  windSpeed: 18, // knots
  windDirection: 'NE',
  oceanCurrent: 0.22, // m/s
  visibility: 14, // km
  temperature: -17, // celsius
  overallRisk: 'MODERATE',
  seaIceRiskScore: 78,
  icebergRiskScore: 41,
  weatherRiskScore: 28
};


// ===== API DATA LOADING =====
// When the backend is available, this replaces mock data with real antarctic-ai data
import { api } from '../services/api';

// Version counter for reactive updates
export let dataVersion = 0;
export function getDataVersion() { return dataVersion; }

async function loadRealData() {
  try {
    const tasks = [
      api.vessels().then(vesselsRes => {
        if (vesselsRes?.vessels?.length) {
          const v = vesselsRes.vessels[0];
          Object.assign(mockVessel, {
            id: v.id, name: v.name, latitude: v.latitude, longitude: v.longitude,
            heading: v.heading, speed: v.speed, destination: v.destination, eta: v.eta,
          });
          dataVersion++;
        }
      }).catch(() => {}),

      api.icebergs().then(icebergsRes => {
        if (icebergsRes?.icebergs?.length) {
          mockIcebergs.length = 0;
          icebergsRes.icebergs.forEach((ib: any) => mockIcebergs.push(ib));
          dataVersion++;
        }
      }).catch(() => {}),

      api.routes("rv_sagar_nidhi").then(routesRes => {
        if (routesRes?.routes?.length) {
          mockRoutes.length = 0;
          routesRes.routes.forEach((r: any) => mockRoutes.push(r));
          dataVersion++;
        }
      }).catch(() => {}),

      api.environmental().then(envRes => {
        if (envRes) {
          Object.assign(mockEnvironmental, envRes);
          dataVersion++;
        }
      }).catch(() => {}),

      api.seaIceSectors().then(sectorsRes => {
        if (sectorsRes?.sectors?.length) {
          mockIceSectors.length = 0;
          sectorsRes.sectors.forEach((s: any) => mockIceSectors.push(s));
          dataVersion++;
        }
      }).catch(() => {}),

      api.waypoints().then(wpRes => {
        if (wpRes?.waypoints?.length) {
          mockWaypoints.length = 0;
          wpRes.waypoints.forEach((w: any) => mockWaypoints.push(w));
          dataVersion++;
        }
      }).catch(() => {}),

      api.alerts().then(alertsRes => {
        if (alertsRes?.alerts?.length) {
          mockAlerts.length = 0;
          alertsRes.alerts.forEach((a: any) => mockAlerts.push(a));
          dataVersion++;
        }
      }).catch(() => {}),

      api.reports().then(reportsRes => {
        if (reportsRes?.reports?.length) {
          mockReports.length = 0;
          reportsRes.reports.forEach((r: any) => mockReports.push(r));
          dataVersion++;
        }
      }).catch(() => {}),

      api.metrics().catch(() => {})
    ];

    await Promise.allSettled(tasks);
    console.log('[Aeolus] Real data streaming loaded from backend API (v' + dataVersion + ')');
  } catch (e) {
    console.log('[Aeolus] Backend unavailable, using mock data');
  }
}

// Auto-load on module import
loadRealData();
