import { api } from "../services/api";
import {
  mockVessel, mockIcebergs, mockRoutes, mockWaypoints,
  mockAlerts, mockIceSectors, mockReports, mockEnvironmental,
  type Vessel, type Iceberg, type RouteOption, type NavigationWaypoint,
  type OperationalAlert, type SeaIceSector, type AssessmentReport
} from "./mock";

interface AppData {
  vessels: Vessel[];
  icebergs: Iceberg[];
  routes: RouteOption[];
  waypoints: NavigationWaypoint[];
  alerts: OperationalAlert[];
  seaIceSectors: SeaIceSector[];
  reports: AssessmentReport[];
  environmental: typeof mockEnvironmental;
  dataSource: "api" | "mock";
}

const defaultData: AppData = {
  vessels: [mockVessel],
  icebergs: mockIcebergs,
  routes: mockRoutes,
  waypoints: mockWaypoints,
  alerts: mockAlerts,
  seaIceSectors: mockIceSectors,
  reports: mockReports,
  environmental: mockEnvironmental,
  dataSource: "mock",
};

let currentData: AppData = { ...defaultData };
let listeners: Array<() => void> = [];

export function subscribeData(cb: () => void) {
  listeners.push(cb);
  return () => { listeners = listeners.filter(l => l !== cb); };
}

function notify() { listeners.forEach(l => l()); }

export function getData(): AppData { return currentData; }

export async function loadData(): Promise<void> {
  const [vesselsRes, icebergsRes, routesRes, _metricsRes, envRes, sectorsRes, wpRes, alertsRes, reportsRes] =
    await Promise.all([
      api.vessels(),
      api.icebergs(),
      api.routes("rv_sagar_nidhi"),
      api.metrics(),
      api.environmental(),
      api.seaIceSectors(),
      api.waypoints(),
      api.alerts(),
      api.reports(),
    ]);

  const hasApiData = vesselsRes?.vessels?.length || icebergsRes?.icebergs?.length;

  if (hasApiData) {
    const vessels: Vessel[] = (vesselsRes?.vessels || [mockVessel]).map((v: any) => ({
      id: v.id, name: v.name, latitude: v.latitude, longitude: v.longitude,
      heading: v.heading, speed: v.speed, destination: v.destination, eta: v.eta,
    }));

    const icebergs: Iceberg[] = (icebergsRes?.icebergs || mockIcebergs).map((ib: any) => ({
      ...ib,
      historicalTrajectory: ib.historicalTrajectory || [],
      predictedTrajectory: ib.predictedTrajectory || [],
      forecastPoints: ib.forecastPoints || [],
      routeIntersection: ib.routeIntersection || { hasIntersection: false, riskLevel: "NONE", proximity: "", estimatedTime: "", recommendedAction: "" },
      confidenceFactors: ib.confidenceFactors || { recentObservations: 0, historicalMovement: 0, oceanCurrentConditions: 0, windConditions: 0, summary: "" },
    }));

    currentData = {
      vessels,
      icebergs,
      routes: routesRes?.routes || mockRoutes,
      waypoints: wpRes?.waypoints || mockWaypoints,
      alerts: alertsRes?.alerts || mockAlerts,
      seaIceSectors: sectorsRes?.sectors || mockIceSectors,
      reports: reportsRes?.reports || mockReports,
      environmental: (envRes as any) || mockEnvironmental,
      dataSource: "api",
    };
  }

  notify();
}

// Auto-load on module import
loadData().catch(() => {});
