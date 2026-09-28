function getApiBase(): string {
  const envUrl = (
    (import.meta.env.VITE_API_BASE_URL as string) ||
    (import.meta.env.VITE_API_URL as string) ||
    ""
  ).trim();

  if (!envUrl) {
    return "/api";
  }

  const clean = envUrl.replace(/\/+$/, "");

  if (!clean.endsWith("/api")) {
    return `${clean}/api`;
  }

  return clean;
}

const API_BASE = getApiBase();

// In-flight Promise deduplication map & TTL response cache for GET endpoints
const inFlightRequests = new Map<string, Promise<any>>();
const responseCache = new Map<string, { data: any; expiry: number }>();

// Cache TTL config (routes: 30s, static/semi-static: 60s)
function getCacheTtlMs(endpoint: string): number {
  if (endpoint.startsWith("/routes")) return 30_000;
  if (endpoint.startsWith("/antarctic/stations") || endpoint.startsWith("/antarctic/land-mask")) return 300_000;
  if (endpoint.startsWith("/vessels")) return 15_000;
  if (endpoint.startsWith("/icebergs")) return 20_000;
  if (endpoint.startsWith("/sic") || endpoint.startsWith("/risk")) return 60_000;
  return 10_000;
}

export function clearApiCache(prefix?: string) {
  if (!prefix) {
    responseCache.clear();
    return;
  }
  for (const key of responseCache.keys()) {
    if (key.includes(prefix)) {
      responseCache.delete(key);
    }
  }
}

export async function apiFetch<T>(endpoint: string): Promise<T | null> {
  const cleanEndpoint = endpoint.startsWith("/")
    ? endpoint
    : `/${endpoint}`;

  const cacheKey = cleanEndpoint;

  // 1. Check TTL Cache
  const cached = responseCache.get(cacheKey);

  if (cached && cached.expiry > Date.now()) {
    return cached.data as T;
  }

  // 2. Check In-Flight Request Deduplication
  if (inFlightRequests.has(cacheKey)) {
    return inFlightRequests.get(cacheKey) as Promise<T | null>;
  }

  const fetchPromise = (async () => {
    const url = API_BASE + cleanEndpoint;

    try {
      console.log("[Aeolus API] GET:", url);

      const controller = new AbortController();

      const timeout = window.setTimeout(() => {
        controller.abort();
      }, 15000);

      const res = await fetch(url, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        signal: controller.signal,
      });

      window.clearTimeout(timeout);

      if (!res.ok) {
        console.error(
          `[Aeolus API] HTTP ${res.status} for ${url}`
        );

        return null;
      }

      const contentType =
        res.headers.get("content-type") || "";

      if (!contentType.includes("application/json")) {
        console.error(
          `[Aeolus API] Expected JSON but received ${contentType} from ${url}`
        );

        return null;
      }

      const data = await res.json();

      // Cache successful response
      responseCache.set(cacheKey, {
        data,
        expiry: Date.now() + getCacheTtlMs(cleanEndpoint),
      });

      return data as T;
    } catch (err) {
      console.error(
        `[Aeolus API] Connection error for ${url}:`,
        err
      );

      return null;
    } finally {
      inFlightRequests.delete(cacheKey);
    }
  })();

  inFlightRequests.set(cacheKey, fetchPromise);

  return fetchPromise;
}
export async function apiPost<T>(
  endpoint: string,
  body: any
): Promise<T | null> {
  const cleanEndpoint = endpoint.startsWith("/")
    ? endpoint
    : `/${endpoint}`;

  const url = API_BASE + cleanEndpoint;

  try {
    console.log("[Aeolus API] POST:", url);

    const controller = new AbortController();

    const timeout = window.setTimeout(() => {
      controller.abort();
    }, 20000);

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    window.clearTimeout(timeout);

    if (!res.ok) {
      console.error(
        `[Aeolus API POST] HTTP ${res.status} for ${url}`
      );

      return null;
    }

    const contentType =
      res.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
      console.error(
        `[Aeolus API POST] Expected JSON but received ${contentType} from ${url}`
      );

      return null;
    }

    return await res.json();
  } catch (err) {
    console.error(
      `[Aeolus API POST] Connection error for ${url}:`,
      err
    );

    return null;
  }
}


export const api = {
  health: () => apiFetch<{status: string}>("/health"),
  vessels: () => apiFetch<{vessels: any[]}>("/vessels"),
  vessel: (id: string) => apiFetch<any>(`/vessels/${id}`),
  icebergs: (timeHorizon?: string) => {
    const qs = timeHorizon ? `?time_horizon=${timeHorizon}` : "";
    return apiFetch<{icebergs: any[]}>(`/icebergs${qs}`);
  },
  routes: (params?: { vesselId?: string; destId?: string; destLat?: number; destLon?: number; destName?: string; emergency?: boolean } | string) => {
    if (typeof params === 'string') {
      return apiFetch<{routes: any[]}>(`/routes?vessel_id=${params}`);
    }
    const q = new URLSearchParams();
    if (params?.vesselId) q.append("vessel_id", params.vesselId);
    if (params?.destId) q.append("dest_id", params.destId);
    if (params?.destLat !== undefined) q.append("dest_lat", String(params.destLat));
    if (params?.destLon !== undefined) q.append("dest_lon", String(params.destLon));
    if (params?.destName) q.append("dest_name", params.destName);
    if (params?.emergency) q.append("emergency", "true");
    const qs = q.toString() ? `?${q.toString()}` : "";
    return apiFetch<{routes: any[]}>(`/routes${qs}`);
  },
  emergency: (payload: { vessel_id?: string; dest_id?: string; hazard_type?: string; reason?: string; force_simulation?: boolean; progress_fraction?: number }) => 
    apiPost<{ emergency: boolean; status: string; alert: any; old_route: any; new_route: any; diverted_route: any; routes: any[]; heading_alteration_deg: number; clearance_km: number; extra_distance_km: number; extra_eta_minutes?: number; hazard_detected?: boolean; iceberg?: any; iceberg_id?: string; iceberg_name?: string; cpa_km?: number; tcpa_hours?: number; threat_level?: string; extra_fuel_mt?: number; local_reroute_applied?: boolean; unaffected_points_count?: number }>("/navigation/emergency", payload),
  restore: (payload?: any) => apiPost<{ status: string; corridor_clear: boolean }>("/navigation/restore", payload || {}),
  simulationWhatIf: (payload: { vessel_id?: string; dest_id?: string; iceberg_drift_km?: number; sic_delta_pct?: number; wind_gust_kn?: number; dest_lat?: number; dest_lon?: number; dest_name?: string }) =>
    apiPost<{
      status: string;
      is_what_if_analysis: boolean;
      parameters: { iceberg_drift_km: number; sic_delta_pct: number; wind_gust_kn: number };
      baseline: any;
      scenario: any;
      difference: {
        distance_delta_km: number;
        eta_delta_hours: number;
        fuel_delta_mt: number;
        risk_impact: string;
        baseline_rio: string;
        scenario_rio: string;
      };
      decision_summary: {
        recommended_action: string;
        dominant_threat: string;
        recommendation: string;
      };
      explanation: string;
    }>("/simulation/what-if", payload),
  metrics: () => apiFetch<Record<string, any>>("/metrics"),
  environmental: (timeStep?: string) => {
    const qs = timeStep ? `?time_step=${timeStep}` : "";
    return apiFetch<Record<string, any>>(`/environmental${qs}`);
  },
  seaIceSectors: (timeStep?: string) => {
    const qs = timeStep ? `?time_step=${timeStep}` : "";
    return apiFetch<{sectors: any[]}>(`/sea-ice-sectors${qs}`);
  },
  sicTimesteps: () => apiFetch<{timesteps: any[]}>("/sic/timesteps"),
  sicGrid: (timeStep?: string) => {
    const qs = timeStep ? `?time_step=${timeStep}` : "";
    return apiFetch<Record<string, any>>(`/sic/grid${qs}`);
  },
  riskGrid: (timeStep?: string) => {
    const qs = timeStep ? `?time_step=${timeStep}` : "";
    return apiFetch<Record<string, any>>(`/risk/grid${qs}`);
  },
  waypoints: () => apiFetch<{waypoints: any[]}>("/waypoints"),
  historicalVessels: () => apiFetch<{vessels: any[]}>("/historical-vessels"),
  backtest: (voyageId: string = "AAD-2015-16") => apiFetch<any>(`/routes/backtest?voyage_id=${voyageId}`),
  backtestCatalog: () => apiFetch<{catalog: any[]}>("/routes/backtest/catalog"),
  alerts: () => apiFetch<{alerts: any[]}>("/alerts"),
  reports: () => apiFetch<{reports: any[]}>("/reports"),
  optimize: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return apiFetch<Record<string, any>>("/optimize" + qs);
  },
  stations: (params?: {region?: string; coastal_only?: boolean; query?: string}) => {
    const q = new URLSearchParams();
    if (params?.region) q.append("region", params.region);
    if (params?.coastal_only) q.append("coastal_only", "true");
    if (params?.query) q.append("query", params.query);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return apiFetch<{source: string; total_stations: number; stations: any[]}>(`/antarctic/stations${qs}`);
  },
  station: (id: string) => apiFetch<any>(`/antarctic/stations/${id}`),
  stationGeojson: () => apiFetch<any>("/antarctic/stations/geojson"),
  validateBharati: () => apiFetch<any>("/antarctic/stations/validate/bharati"),
  landMask: () => apiFetch<any>("/antarctic/land-mask"),
  fleet: (preferLive: boolean = true) => apiFetch<{data_status: string; source: string; badge: string; total_vessels: number; vessels: any[]}>(`/antarctic/vessels?prefer_live=${preferLive}`),
  antarcticVessels: (preferLive: boolean = true) => apiFetch<{data_status: string; source: string; badge: string; total_vessels: number; vessels: any[]}>(`/antarctic/vessels?prefer_live=${preferLive}`),
  antarcticVessel: (mmsi: string) => apiFetch<any>(`/antarctic/vessels/${mmsi}`),
  navigationScenario: () => apiFetch<{vessel: any; destination: any; mode: string; source: string; primary_region: string}>("/navigation/scenario"),
  sentinelScenes: () => apiFetch<{scenes: any[]; total_scenes: number}>("/sentinel/scenes"),
  sentinelDetections: (sceneIdx: number = 0) => apiFetch<any>(`/sentinel/detections?scene_idx=${sceneIdx}`),
  radarObstacles: () => apiFetch<{
    type: string;
    status: string;
    source: string;
    label: string;
    observation_date: string;
    provenance: string;
    total_obstacles: number;
    features: any[];
  }>("/radar/obstacles"),
  sentinelMetrics: () => apiFetch<any>("/sentinel/metrics"),
  environmentStatus: () => apiFetch<any>("/environment/status"),
  seaIce: (lat: number = -65.0, lon: number = -64.0) => apiFetch<any>(`/sea-ice?lat=${lat}&lon=${lon}`),
  seaIceForecast: (lat: number = -65.0, lon: number = -64.0) => apiFetch<any>(`/sea-ice/forecast?lat=${lat}&lon=${lon}`),
  oceanCurrents: (lat: number = -65.0, lon: number = -64.0) => apiFetch<any>(`/ocean-currents?lat=${lat}&lon=${lon}`),
  oceanCurrentsGrid: () => apiFetch<any>("/ocean-currents/grid"),
  weather: (lat: number = -65.0, lon: number = -64.0) => apiFetch<any>(`/weather?lat=${lat}&lon=${lon}`),
  bathymetry: (lat: number = -65.0, lon: number = -64.0) => apiFetch<any>(`/bathymetry?lat=${lat}&lon=${lon}`),
  intelligenceModels: () => apiFetch<any>("/intelligence/models"),
  dbStatus: () => apiFetch<any>("/db/status"),
  copilotStatus: () => apiFetch<{status: string; active_provider: string; gemini_authenticated: boolean; model: string}>("/copilot/status"),
  copilot: (decisionData: any, question?: string) => apiPost<any>("/copilot", { decision_data: decisionData, question }),
  routesOptimize: (payload: {
    vessel_id?: string;
    vessel_name?: string;
    start_lat: number;
    start_lon: number;
    dest_lat: number;
    dest_lon: number;
    destination: string;
    cruising_speed_kn?: number;
    polar_class?: string;
  }) => apiPost<{
    status: string;
    vessel_id: string;
    destination: string;
    routes: any[];
    recommended_route_id?: string;
    generated_at: string;
    engine: string;
  }>("/routes/optimize", payload),
  historicalCatalog: () => apiFetch<{ catalog: any[] }>("/routes/backtest/catalog"),
  historicalReplay: (voyageId: string = "AAD-2015-16") => apiFetch<any>(`/historical/replay?voyage_id=${voyageId}`),
  historicalThreeWay: (voyageId: string = "AAD-2015-16") => apiFetch<any>(`/historical/three-way?voyage_id=${voyageId}`),
  historicalEnvironmentSnapshot: (voyageId: string = "AAD-2015-16") => apiFetch<any>(`/historical/environment-snapshot?voyage_id=${voyageId}`),
  realtimeState: (lat: number = -65.20, lon: number = 64.30, vesselHeading: number = 0, vesselDraft: number = 8.0) => 
    apiFetch<any>(`/realtime/state?lat=${lat}&lon=${lon}&vessel_heading=${vesselHeading}&vessel_draft=${vesselDraft}`),
  realtimeHealth: () => apiFetch<any>("/realtime/health"),
  realtimeSatelliteScenes: (params?: { lat?: number; lon?: number; radius_km?: number; max_results?: number; use_live_api?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.lat !== undefined) q.append("lat", String(params.lat));
    if (params?.lon !== undefined) q.append("lon", String(params.lon));
    if (params?.radius_km !== undefined) q.append("radius_km", String(params.radius_km));
    if (params?.max_results !== undefined) q.append("max_results", String(params.max_results));
    if (params?.use_live_api !== undefined) q.append("use_live_api", String(params.use_live_api));
    const qs = q.toString() ? `?${q.toString()}` : "";
    return apiFetch<{ count: number; scenes: any[]; cache_stats: any }>(`/realtime/satellite/scenes${qs}`);
  },
  realtimeSatelliteScene: (sceneId: string) => apiFetch<any>(`/realtime/satellite/scene/${encodeURIComponent(sceneId)}`),
  operationalDashboard: (vesselId?: string, lat?: number, lon?: number) => {
    const q = new URLSearchParams();
    if (vesselId) q.append("vessel_id", vesselId);
    if (typeof lat === 'number') q.append("lat", String(lat));
    if (typeof lon === 'number') q.append("lon", String(lon));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return apiFetch<any>(`/realtime/operational-dashboard${qs}`);
  },
  vesselTelemetry: () => apiFetch<any>("/realtime/vessel/telemetry"),
  vesselTelemetryControl: (payload: { action: string; speed_multiplier?: number; sog_kn?: number }) =>
    apiPost<any>("/realtime/vessel/telemetry/control", payload),
  vesselTelemetryNmeaFeed: (payload: { sentence: string }) =>
    apiPost<any>("/realtime/vessel/telemetry/nmea-feed", payload),
  realtimeBacktestCatalog: () => 
    apiFetch<{ status: string; count: number; catalog: any[]; data_mode: string; anti_lookahead_enforced: boolean }>("/realtime/backtest/catalog"),
  realtimeBacktestVoyage: (voyageId: string, params?: { polar_class?: string; speed_knots?: number; draft_m?: number }) => {
    const q = new URLSearchParams();
    if (params?.polar_class) q.append("polar_class", params.polar_class);
    if (params?.speed_knots !== undefined) q.append("speed_knots", String(params.speed_knots));
    if (params?.draft_m !== undefined) q.append("draft_m", String(params.draft_m));
    const qs = q.toString() ? `?${q.toString()}` : "";
    return apiFetch<any>(`/realtime/backtest/voyage/${encodeURIComponent(voyageId)}${qs}`);
  },
  realtimeBacktestRun: (payload: { voyage_id: string; polar_class?: string; speed_knots?: number; draft_m?: number; beam_m?: number; length_m?: number }) =>
    apiPost<any>("/realtime/backtest/run", payload),
  realtimeGeneralizationCatalog: () => 
    apiFetch<{ unseen_vessels: any[]; novel_corridors: any[]; stress_conditions: string[] }>("/realtime/generalization/catalog"),
  realtimeGeneralizationTest: (payload: { vessel: any; corridor: any; stress_condition?: string; profile?: string }) =>
    apiPost<any>("/realtime/generalization/test", payload),
  realtimeGeneralizationBenchmark: () => 
    apiFetch<any>("/realtime/generalization/benchmark-suite"),
  realtimeReliabilityAudit: () => 
    apiFetch<any>("/realtime/reliability/audit"),
  realtimeReliabilitySimulateFault: (payload: { provider: string; fault_type: string; delay_ms?: number; error_message?: string; force_stale_hours?: number; active?: boolean }) =>
    apiPost<any>("/realtime/reliability/simulate-fault", payload),
  realtimeReliabilityReset: () => 
    apiPost<any>("/realtime/reliability/reset", {}),
  realtimeReliabilityProvider: (providerId: string) => 
    apiFetch<any>(`/realtime/reliability/provider/${encodeURIComponent(providerId)}`),
};


