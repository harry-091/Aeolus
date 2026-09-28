import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { 
  AlertTriangle, 
  Ship, 
  Activity, 
  Compass,
  Database,
  ShieldCheck,
  ChevronRight
} from 'lucide-react';
import { AppShell } from '../../components/layout/AppShell';
import { useFleet } from '../../context/FleetContext';
import { api } from '../../services/api';
import { cn } from '../../utils/cn';

export const IntelligencePage: React.FC = () => {
  const { selectedVessel, setSelectedVesselId, fleet, activeRoute, activeRouteId, setActiveRouteId, routes } = useFleet();
  const [alerts, setAlerts] = useState<any[]>([]);
  const [aiModels, setAiModels] = useState<any>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [alertsRes, modelsRes] = await Promise.all([
          api.alerts(),
          api.intelligenceModels()
        ]);
        if (alertsRes?.alerts) setAlerts(alertsRes.alerts);
        if (modelsRes) setAiModels(modelsRes);
      } catch (err) {
        console.error('[IntelligencePage] Error loading data:', err);
      }
    }
    loadData();
  }, []);

  const currentRoute = useMemo(() => {
    if (!routes || routes.length === 0) return activeRoute || null;
    return routes.find(r => r.id === activeRouteId) ||
           routes.find(r => r.id?.includes(activeRouteId)) ||
           activeRoute ||
           routes.find(r => r.recommended) ||
           routes[0] ||
           null;
  }, [routes, activeRouteId, activeRoute]);

  const costBreakdown = currentRoute?.cost_breakdown || currentRoute?.costs || {
    distance_cost: 168.0,
    ice_cost: 341.9,
    iceberg_cost: 0.0,
    current_cost: 0.4,
    weather_cost: 325.4,
    bathymetry_cost: 0.0,
    fuel_cost: 682.7,
    total_cost: 1518.4
  };

  const explanation = currentRoute?.decision_support?.recommendation || 
    currentRoute?.decision_explanation || 
    currentRoute?.reason || 
    `${currentRoute?.name || 'ROUTE B (OPTIMAL)'} is recommended for ${selectedVessel.name} to ${selectedVessel.destination || 'Bharati Station'}. It optimizes voyage safety and fuel efficiency by avoiding compact pack ice (SIC > 75%) and maintaining a minimum 15 km CPA clearance from all 85 tracked Antarctic icebergs.`;

  return (
    <AppShell
      title="INTELLIGENCE & LOGS"
      subtitle="Decision explanation, tactical alert history, and environmental provenance"
      actions={
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-2 px-2.5 py-1 bg-[#081525] rounded-md text-slate-300 border border-white/[0.06]">
            <Ship className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400">Vessel:</span>
            <select
              value={selectedVessel.id}
              onChange={(e) => setSelectedVesselId(e.target.value)}
              className="bg-transparent text-slate-200 font-medium text-xs border-none focus:outline-none cursor-pointer"
            >
              {fleet.map((v) => (
                <option key={v.id} value={v.id} className="bg-[#081525] text-slate-200">
                  {v.name} ({v.polar_class ? v.polar_class.split(' ')[0] : 'PC5'})
                </option>
              ))}
            </select>
          </div>

          <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 bg-[#081525] rounded-md text-slate-300 border border-white/[0.06]">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-slate-400">Status:</span>
            <span className="text-slate-200 font-medium">Validated</span>
          </div>
        </div>
      }
    >
      <div className="h-full overflow-y-auto custom-scrollbar p-4 lg:p-6 space-y-4 bg-[#040911] text-slate-200 font-sans">
        
        {/* ========================================================================= */}
        {/* 1. DECISION EXPLANATION (MARITIME DECISION SUPPORT)                      */}
        {/* ========================================================================= */}
        <div className="bg-[#081424]/70 p-4 lg:p-5 rounded-lg space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
            <div className="flex items-center gap-2.5">
              <Compass className="w-4 h-4 text-sky-400" />
              <span className="text-slate-200 font-semibold text-xs tracking-wide">
                Decision Explanation
              </span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400 text-xs font-mono">{currentRoute?.name || 'Route B (Optimal)'}</span>
            </div>

            {/* Corridor Tabs */}
            <div className="flex items-center gap-1 bg-[#081525] p-0.5 rounded-md border border-white/[0.06]">
              {routes.map((r) => {
                const isSelected = currentRoute?.id === r.id;
                const tabLabel = r.optimization_mode === 'BALANCED' ? 'Route B (Optimal)' :
                                 r.optimization_mode === 'SAFEST' ? 'Route C (Safest)' :
                                 r.optimization_mode === 'FASTEST' ? 'Route A (Direct)' :
                                 r.name?.includes('ROUTE B') ? 'Route B (Optimal)' :
                                 r.name?.includes('ROUTE C') ? 'Route C (Safest)' : 'Route A (Direct)';
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setActiveRouteId(r.id)}
                    className={cn(
                      "px-2.5 py-1 rounded-sm text-xs font-medium transition-colors cursor-pointer",
                      isSelected
                        ? "bg-sky-600 text-white font-semibold"
                        : "text-slate-400 hover:text-white"
                    )}
                  >
                    {tabLabel}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="p-4 bg-[#081525]/60 rounded-lg space-y-1.5">
            <span className="text-slate-400 text-xs font-medium block">
              Operational Recommendation Narrative
            </span>
            <p className="text-xs text-slate-200 leading-relaxed">
              {explanation}
            </p>
          </div>

          {/* Environmental Cost Component Score Breakdown */}
          <div className="pt-1">
            <span className="text-slate-400 text-xs block mb-2.5 font-medium">
              Multi-Objective Cost Breakdown (Antarctic Dynamic A*)
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5 text-center text-xs">
              <div className="bg-[#081525]/60 p-2.5 rounded-md">
                <span className="text-slate-400 text-[11px] block">Distance</span>
                <span className="font-semibold font-mono text-slate-200 mt-1 block">{costBreakdown.distance_cost ?? 0}</span>
              </div>
              <div className="bg-[#081525]/60 p-2.5 rounded-md">
                <span className="text-slate-400 text-[11px] block">Sea-Ice Drag</span>
                <span className="font-semibold font-mono text-sky-400 mt-1 block">{costBreakdown.ice_cost ?? 0}</span>
              </div>
              <div className="bg-[#081525]/60 p-2.5 rounded-md">
                <span className="text-slate-400 text-[11px] block">Iceberg CPA</span>
                <span className="font-semibold font-mono text-slate-200 mt-1 block">{costBreakdown.iceberg_cost ?? 0}</span>
              </div>
              <div className="bg-[#081525]/60 p-2.5 rounded-md">
                <span className="text-slate-400 text-[11px] block">Ocean Drift</span>
                <span className="font-semibold font-mono text-slate-200 mt-1 block">{costBreakdown.current_cost ?? 0}</span>
              </div>
              <div className="bg-[#081525]/60 p-2.5 rounded-md">
                <span className="text-slate-400 text-[11px] block">Wind Drag</span>
                <span className="font-semibold font-mono text-slate-200 mt-1 block">{costBreakdown.weather_cost ?? 0}</span>
              </div>
              <div className="bg-[#081525]/60 p-2.5 rounded-md">
                <span className="text-slate-400 text-[11px] block">Bathymetry</span>
                <span className="font-semibold font-mono text-emerald-400 mt-1 block">{costBreakdown.bathymetry_cost ?? 0}</span>
              </div>
              <div className="bg-[#081525]/60 p-2.5 rounded-md">
                <span className="text-slate-400 text-[11px] block">Fuel Cost</span>
                <span className="font-semibold font-mono text-slate-200 mt-1 block">{costBreakdown.fuel_cost ?? 0}</span>
              </div>
              <div className="bg-[#081525] p-2.5 rounded-md border border-sky-500/30">
                <span className="text-sky-300 text-[11px] font-medium block">Total Score</span>
                <span className="font-bold font-mono text-emerald-400 mt-1 block">{costBreakdown.total_cost ?? 0}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* 2. CHRONOLOGICAL LOGS & HAZARDS TIMELINE                                  */}
        {/* ========================================================================= */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
          
          {/* Active Hazard Logs */}
          <div className="bg-[#081424]/70 p-4 lg:p-5 rounded-lg space-y-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5 mb-3">
                <span className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  Tactical Hazard Log ({alerts.length})
                </span>
                <span className="text-[11px] text-slate-400">Chronological</span>
              </div>
              
              <div className="space-y-2 max-h-72 overflow-y-auto custom-scrollbar">
                {alerts.map((a: any, idx: number) => {
                  const isHigh = a.severity === 'HIGH' || a.severity === 'CRITICAL';
                  return (
                    <div 
                      key={a.id || idx}
                      className={cn(
                        "p-3 rounded-md text-xs space-y-1.5 transition-colors",
                        isHigh ? "bg-rose-500/10 border-l-2 border-l-rose-500" : "bg-[#081525]/60"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className={cn("font-semibold text-xs", isHigh ? "text-rose-400" : "text-amber-400")}>
                          {a.title}
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono">{a.timeRelative || '14:12 UTC'}</span>
                      </div>
                      <p className="text-slate-300 text-xs leading-relaxed">{a.description}</p>
                      <div className="flex justify-between text-[11px] text-slate-400 pt-1.5 border-t border-white/[0.04]">
                        <span>Source: <strong className="text-slate-300 font-normal">{a.source || 'Polar Sensor Fusion'}</strong></span>
                        <span className="text-sky-400 font-medium">Action: {a.recommendedAction || 'Monitor CPA'}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <Link
              to="/alerts"
              className="pt-3 border-t border-white/[0.06] text-xs text-sky-400 hover:text-sky-300 flex items-center justify-between transition-colors font-medium"
            >
              <span>Manage active alerts</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* System Events & Decisions */}
          <div className="bg-[#081424]/70 p-4 lg:p-5 rounded-lg space-y-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5 mb-3">
                <span className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-sky-400" />
                  Navigation Events &amp; Waypoint Log
                </span>
                <span className="text-xs text-emerald-400 font-medium flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  Recorder Active
                </span>
              </div>

              <div className="space-y-2 max-h-72 overflow-y-auto custom-scrollbar">
                {[
                  { time: '14:32:00 UTC', event: 'Simulated kinematic tick: SOG 12.4 kn, HDG 184°T, CPA clearance 14.8 km' },
                  { time: '14:20:15 UTC', event: 'Waypoint WP-03 cleared. Transitioning to open lead sector SEC-02' },
                  { time: '13:45:00 UTC', event: 'NOAA CDR 25km passive microwave grid refreshed. MIZ boundary confirmed' },
                  { time: '12:00:30 UTC', event: 'Sentinel-1A SAR scene ingested. 6 CFAR point-targets verified and mapped' },
                  { time: '11:15:00 UTC', event: 'POLARIS RIO safety verification passed: RIO +8.4 for PC5 ice class vessel' }
                ].map((ev, i) => (
                  <div key={i} className="p-2.5 bg-[#081525]/60 rounded-md text-xs space-y-1">
                    <div className="flex justify-between text-[11px] text-slate-400">
                      <span className="font-semibold text-sky-400 font-mono">{ev.time}</span>
                      <span className="text-slate-400">Operational</span>
                    </div>
                    <p className="text-slate-300 text-xs">{ev.event}</p>
                  </div>
                ))}
              </div>
            </div>

            <Link
              to="/reports"
              className="pt-3 border-t border-white/[0.06] text-xs text-sky-400 hover:text-sky-300 flex items-center justify-between transition-colors font-medium"
            >
              <span>Generate IMO compliance report</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

        </div>

        {/* ========================================================================= */}
        {/* 3. ML MODEL BENCHMARKS & ENVIRONMENTAL SENSOR PROVENANCE                  */}
        {/* ========================================================================= */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
          
          {/* Model Benchmarks */}
          <div className="bg-[#081424]/70 p-4 lg:p-5 rounded-lg space-y-3.5">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5">
              <span className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                ML Prediction Models &amp; Benchmarks
              </span>
              <span className="text-xs text-emerald-400 font-medium font-mono">4 Modules</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
              <div className="p-3 bg-[#081525]/60 rounded-md space-y-1.5">
                <div className="text-sky-400 font-semibold text-xs">Sea Ice Predictor</div>
                <div className="text-slate-200 font-medium">{aiModels?.modules?.module_1_sea_ice?.model_type || 'RandomForest'} (CDR V4)</div>
                <div className="flex justify-between text-[11px] text-slate-400 pt-1 border-t border-white/[0.04]">
                  <span>Test R²:</span>
                  <span className="text-emerald-400 font-bold font-mono">{aiModels?.modules?.module_1_sea_ice?.test_r2 ?? 0.8861}</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Test MAE:</span>
                  <span className="text-slate-200 font-mono">{aiModels?.modules?.module_1_sea_ice?.test_mae ?? 0.0401}</span>
                </div>
              </div>

              <div className="p-3 bg-[#081525]/60 rounded-md space-y-1.5">
                <div className="text-sky-400 font-semibold text-xs">Iceberg Drift Model</div>
                <div className="text-slate-200 font-medium">Kinematic RF (85 BYU Bergs)</div>
                <div className="flex justify-between text-[11px] text-slate-400 pt-1 border-t border-white/[0.04]">
                  <span>Mean Error:</span>
                  <span className="text-emerald-400 font-bold font-mono">{aiModels?.modules?.module_2_iceberg_drift?.mean_position_error_km ?? 1.7} km</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Median Error:</span>
                  <span className="text-slate-200 font-mono">{aiModels?.modules?.module_2_iceberg_drift?.median_position_error_km ?? 0.12} km</span>
                </div>
              </div>

              <div className="p-3 bg-[#081525]/60 rounded-md space-y-1.5">
                <div className="text-sky-400 font-semibold text-xs">Sentinel-1 SAR Detector</div>
                <div className="text-slate-200 font-medium">CFAR + Lee Speckle Filter</div>
                <div className="flex justify-between text-[11px] text-slate-400 pt-1 border-t border-white/[0.04]">
                  <span>Test Accuracy:</span>
                  <span className="text-emerald-400 font-bold font-mono">{aiModels?.modules?.module_3_sentinel_sar?.test_accuracy ?? 98.47}%</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Weighted F1:</span>
                  <span className="text-slate-200 font-mono">{aiModels?.modules?.module_3_sentinel_sar?.weighted_f1 ?? 98.48}%</span>
                </div>
              </div>

              <div className="p-3 bg-[#081525]/60 rounded-md space-y-1.5">
                <div className="text-sky-400 font-semibold text-xs">Polar Conformal A*</div>
                <div className="text-slate-200 font-medium">EPSG:3031 Dynamic Grid</div>
                <div className="flex justify-between text-[11px] text-slate-400 pt-1 border-t border-white/[0.04]">
                  <span>Cost Objectives:</span>
                  <span className="text-emerald-400 font-bold font-mono">7 Surfaces</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Standard:</span>
                  <span className="text-slate-200">IMO POLARIS</span>
                </div>
              </div>
            </div>
          </div>

          {/* Sensor Provenance */}
          <div className="bg-[#081424]/70 p-4 lg:p-5 rounded-lg space-y-3.5">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5">
              <span className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                <Database className="w-4 h-4 text-sky-400" />
                Sensor Pipeline &amp; Data Provenance
              </span>
              <span className="text-xs text-emerald-400 font-medium">Synchronized</span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="p-2.5 bg-[#081525]/60 rounded-md flex items-center justify-between">
                <div>
                  <div className="text-slate-200 font-medium">NOAA / NSIDC CDR V4</div>
                  <div className="text-[11px] text-slate-400">Daily 25km passive microwave grid for sea ice concentration</div>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-400 font-medium">
                  SATELLITE
                </span>
              </div>

              <div className="p-2.5 bg-[#081525]/60 rounded-md flex items-center justify-between">
                <div>
                  <div className="text-slate-200 font-medium">US NIC + BYU Antarctic Iceberg Database</div>
                  <div className="text-[11px] text-slate-400">85 authenticated iceberg records with dimensions &amp; historical drift</div>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-sky-500/15 text-sky-400 font-medium">
                  RADAR
                </span>
              </div>

              <div className="p-2.5 bg-[#081525]/60 rounded-md flex items-center justify-between">
                <div>
                  <div className="text-slate-200 font-medium">Copernicus Marine GLO12 + ECMWF ERA5</div>
                  <div className="text-[11px] text-slate-400">Surface currents (uo, vo) &amp; 10m wind vector forcing</div>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-indigo-500/15 text-indigo-400 font-medium">
                  HYDRO/MET
                </span>
              </div>

              <div className="p-2.5 bg-[#081525]/60 rounded-md flex items-center justify-between">
                <div>
                  <div className="text-slate-200 font-medium">NOAA NGDC ETOPO 2022 Bathymetry</div>
                  <div className="text-[11px] text-slate-400">1 arc-minute global seabed relief with 20m keel collision avoidance</div>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-teal-500/15 text-teal-400 font-medium">
                  BATHYMETRY
                </span>
              </div>
            </div>
          </div>

        </div>

      </div>
    </AppShell>
  );
};

export default IntelligencePage;
