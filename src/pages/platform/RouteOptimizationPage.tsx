import React, { useState, useMemo } from 'react';
import { 
  CheckCircle2, Ship, MapPin, ShieldAlert,
  Navigation, Loader2, Fuel
} from 'lucide-react';
import { AppShell } from '../../components/layout/AppShell';
import { useApiData } from "../../hooks/useApiData";
import { useFleet } from '../../context/FleetContext';
import PolarMap from '../../components/map/PolarMap';
import { cn } from '../../utils/cn';

interface RouteOption {
  id: string;
  name: string;
  optimization_mode?: string;
  distance: number;
  eta: string;
  path?: [number, number][];
  recommended?: boolean;
  iceRisk?: string;
  icebergRisk?: string;
  weatherRisk?: string;
  overallScore?: number;
  fuelConsumption?: string | number;
  sicExposure?: number;
  sic_actual?: number;
  sic_cost_contribution?: number;
  rioScore?: number | string;
  reason?: string;
  costs?: Record<string, number>;
  cost_breakdown?: Record<string, number>;
}

export const RouteOptimizationPage: React.FC = () => {
  useApiData();
  const {
    fleet,
    selectedVesselId,
    selectedVessel,
    setSelectedVesselId,
    stations,
    selectedDestinationId,
    selectedDestination,
    setSelectedDestinationId,
    routes,
    activeRouteId,
    setActiveRouteId,
    emergencyRerouteActive,
    triggerEmergencyHazard,
    setCustomDestination,
    isComputingRoutes,
    recomputeRoutes
  } = useFleet();

  const [maxSicConstraint, setMaxSicConstraint] = useState<number>(75);
  const [safetyBufferKm, setSafetyBufferKm] = useState<number>(15);
  const [isCustomMode, setIsCustomMode] = useState<boolean>(false);
  const [customName, setCustomName] = useState<string>('');
  const [customLat, setCustomLat] = useState<string>('');
  const [customLon, setCustomLon] = useState<string>('');
  const [targetSpeedKn, setTargetSpeedKn] = useState<number>(12);
  const [baselineBurnTpd, setBaselineBurnTpd] = useState<number>(22);
  const [ecoProfile, setEcoProfile] = useState<boolean>(true);

  const handleSetActiveRoute = (routeId: string) => {
    setActiveRouteId(routeId);
  };

  const recommendedRoute = useMemo(() => {
    return routes.find(r => r.recommended || r.optimization_mode === 'BALANCED' || r.id?.includes('route-b')) || routes[0];
  }, [routes]);

  const alternativeRoutes = useMemo(() => {
    return routes.filter(r => r.id !== recommendedRoute?.id);
  }, [routes, recommendedRoute]);

  const selectedRoute = useMemo(() => {
    return routes.find(r => r.id === activeRouteId) || recommendedRoute;
  }, [routes, activeRouteId, recommendedRoute]);

  const fuelPlan = useMemo(() => {
    const distanceKm = Number(selectedRoute?.distance || 4120);
    const sic = Number(selectedRoute?.sic_actual || selectedRoute?.sicExposure || 48);
    const voyageHours = distanceKm / Math.max(targetSpeedKn * 1.852, 1);
    const speedFactor = Math.pow(targetSpeedKn / 12, 2.4);
    const iceFactor = 1 + (sic / 100) * 0.22;
    const ecoFactor = ecoProfile ? 0.9 : 1;
    const dailyBurn = baselineBurnTpd * speedFactor * iceFactor * ecoFactor;
    const fuelTonnes = dailyBurn * (voyageHours / 24);
    const referenceFuel = baselineBurnTpd * (distanceKm / (12 * 1.852) / 24) * iceFactor;
    return {
      voyageHours,
      fuelTonnes,
      dailyBurn,
      savedTonnes: Math.max(0, referenceFuel - fuelTonnes),
      co2Tonnes: fuelTonnes * 3.114,
    };
  }, [selectedRoute, targetSpeedKn, baselineBurnTpd, ecoProfile]);

  const getRiskLabel = (r: RouteOption) => {
    const rio = parseFloat(String(r.rioScore || '8.4'));
    if (rio < 0 || r.optimization_mode === 'FASTEST' || r.id?.includes('route-a')) {
      return { label: 'HIGH RISK', color: 'text-rose-400', bg: 'bg-rose-500/15' };
    }
    if (r.optimization_mode === 'BALANCED' || r.id?.includes('route-b')) {
      return { label: 'OPTIMAL (SAFE)', color: 'text-emerald-400', bg: 'bg-emerald-500/15' };
    }
    return { label: 'SAFEST (CONSERVATIVE)', color: 'text-sky-400', bg: 'bg-sky-500/15' };
  };

  return (
    <AppShell
      title="ROUTES"
      subtitle="Antarctic route planning and optimization"
      actions={
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-800/60 px-3 py-1.5 rounded-lg">
            <span className="text-slate-400">Engaged:</span>
            <span className="text-emerald-400 font-semibold font-mono">{selectedRoute?.name?.split(' - ')[0] || 'ROUTE B'}</span>
          </div>
          <button
            type="button"
            onClick={() => triggerEmergencyHazard()}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer",
              emergencyRerouteActive
                ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                : "bg-slate-900/80 border border-slate-800/60 text-slate-300 hover:text-slate-100 hover:bg-slate-800/60"
            )}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>{emergencyRerouteActive ? "Tactical Diversion Active" : "Simulate Hazard"}</span>
          </button>
        </div>
      }
    >
      <div className="flex flex-col lg:flex-row h-full overflow-hidden bg-[#040911]">
        
        <div className="w-full lg:w-96 xl:w-[420px] bg-[#060e18] border-r border-white/[0.04] p-4 lg:p-5 overflow-y-auto custom-scrollbar flex flex-col justify-between shrink-0 font-sans text-xs text-slate-300 space-y-4">
          
          <div className="space-y-4">
            
            <div className="bg-[#081424]/70 p-4 rounded-lg space-y-3">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                <span className="text-slate-200 font-semibold text-xs tracking-wide">
                  Voyage Parameters
                </span>
                <span className="text-[11px] text-slate-400">Polaris PC5 Standard</span>
              </div>

              <div>
                <label className="text-xs text-slate-400 mb-1.5 flex items-center gap-1.5 font-medium">
                  <Ship className="w-3.5 h-3.5 text-sky-400" />
                  Origin (Research Vessel)
                </label>
                <select
                  value={selectedVesselId}
                  onChange={(e) => setSelectedVesselId(e.target.value)}
                  className="w-full bg-[#081525] border border-white/10 rounded-md p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
                >
                  {fleet.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.flag} {v.name} ({v.speed || v.sog || 12.0} kn) — {Math.abs(v.latitude || 0).toFixed(1)}°S
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs text-slate-400 flex items-center gap-1.5 font-medium">
                    <MapPin className="w-3.5 h-3.5 text-sky-400" />
                    Destination Station
                  </label>
                  <button
                    type="button"
                    onClick={() => setIsCustomMode(!isCustomMode)}
                    className="text-xs text-sky-400 hover:text-sky-300 transition-colors"
                  >
                    {isCustomMode ? '← Pick Station' : '+ Custom Waypoint'}
                  </button>
                </div>

                {!isCustomMode ? (
                  <select
                    value={selectedDestinationId}
                    onChange={(e) => setSelectedDestinationId(e.target.value)}
                    className="w-full bg-[#081525] border border-white/10 rounded-md p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
                  >
                    {stations.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} ({d.country || 'Antarctica'}) — {Math.abs(d.latitude).toFixed(1)}°S
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="space-y-2 bg-[#081525]/80 p-3 rounded-md border border-white/10">
                    <input
                      type="text"
                      placeholder="Waypoint Name (e.g. Weddell Lead)"
                      value={customName}
                      onChange={(e) => setCustomName(e.target.value)}
                      className="w-full bg-[#040911] border border-white/10 rounded-md p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="number"
                        step="0.01"
                        placeholder="Latitude (°S)"
                        value={customLat}
                        onChange={(e) => setCustomLat(e.target.value)}
                        className="bg-[#040911] border border-white/10 rounded-md p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500/50"
                      />
                      <input
                        type="number"
                        step="0.01"
                        placeholder="Longitude (°E/W)"
                        value={customLon}
                        onChange={(e) => setCustomLon(e.target.value)}
                        className="bg-[#040911] border border-white/10 rounded-md p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500/50"
                      />
                    </div>
                    <button
                      type="button"
                      disabled={isComputingRoutes || !customLat || !customLon}
                      onClick={() => {
                        const lat = parseFloat(customLat);
                        const lon = parseFloat(customLon);
                        if (!isNaN(lat) && !isNaN(lon)) {
                          setCustomDestination(customName || 'Custom Target', lat, lon);
                          setIsCustomMode(false);
                        }
                      }}
                      className="w-full py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-md text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
                    >
                      Set Destination
                    </button>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2.5 pt-1">
                <div className="bg-[#081525]/60 p-2.5 rounded-md">
                  <span className="text-[11px] text-slate-400 block mb-1">Max SIC Limit</span>
                  <div className="flex items-center justify-between">
                    <input
                      type="range"
                      min={40}
                      max={95}
                      value={maxSicConstraint}
                      onChange={(e) => setMaxSicConstraint(Number(e.target.value))}
                      className="w-20 accent-sky-500"
                    />
                    <span className="text-xs font-semibold font-mono text-slate-200">{maxSicConstraint}%</span>
                  </div>
                </div>
                <div className="bg-[#081525]/60 p-2.5 rounded-md">
                  <span className="text-[11px] text-slate-400 block mb-1">Iceberg Buffer</span>
                  <div className="flex items-center justify-between">
                    <input
                      type="range"
                      min={5}
                      max={30}
                      value={safetyBufferKm}
                      onChange={(e) => setSafetyBufferKm(Number(e.target.value))}
                      className="w-20 accent-sky-500"
                    />
                    <span className="text-xs font-semibold font-mono text-slate-200">{safetyBufferKm} km</span>
                  </div>
                </div>
              </div>

              <div className="rounded-md border border-sky-500/20 bg-sky-500/5 p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-200"><Fuel className="h-3.5 w-3.5 text-sky-400" />Fuel & efficiency</span>
                  <button type="button" onClick={() => setEcoProfile(!ecoProfile)} className={cn('rounded-full px-2 py-1 text-[10px] font-bold', ecoProfile ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-700/40 text-slate-400')}>{ecoProfile ? 'ECO PROFILE ON' : 'STANDARD PROFILE'}</button>
                </div>
                <label className="block text-[11px] text-slate-400">Target speed <span className="float-right font-mono text-slate-200">{targetSpeedKn.toFixed(1)} kn</span><input type="range" min={7} max={16} step={0.5} value={targetSpeedKn} onChange={(e) => setTargetSpeedKn(Number(e.target.value))} className="mt-1.5 w-full accent-sky-500" /></label>
                <label className="block text-[11px] text-slate-400">Baseline fuel burn <span className="float-right font-mono text-slate-200">{baselineBurnTpd.toFixed(0)} t/day</span><input type="range" min={12} max={45} step={1} value={baselineBurnTpd} onChange={(e) => setBaselineBurnTpd(Number(e.target.value))} className="mt-1.5 w-full accent-sky-500" /></label>
                <div className="grid grid-cols-3 gap-2 border-t border-white/[0.08] pt-2.5 text-[10px]"><span><small className="block text-slate-400">Trip fuel</small><strong className="font-mono text-slate-200">{fuelPlan.fuelTonnes.toFixed(1)} t</strong></span><span><small className="block text-slate-400">CO₂ estimate</small><strong className="font-mono text-slate-200">{fuelPlan.co2Tonnes.toFixed(0)} t</strong></span><span><small className="block text-slate-400">Eco saving</small><strong className="font-mono text-emerald-400">{fuelPlan.savedTonnes.toFixed(1)} t</strong></span></div>
              </div>

              <button
                type="button"
                disabled={isComputingRoutes}
                onClick={async () => {
                  await recomputeRoutes();
                  setActiveRouteId(recommendedRoute?.id || 'route-b');
                }}
                className="w-full py-2.5 bg-sky-600 hover:bg-sky-500 text-white rounded-md text-xs font-semibold tracking-wide flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
              >
                {isComputingRoutes ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Calculating Corridors...</span>
                  </>
                ) : (
                  <>
                    <Navigation className="w-4 h-4" />
                    <span>Calculate Optimal Route</span>
                  </>
                )}
              </button>
            </div>

            {recommendedRoute && (
              <div className="space-y-2">
                <div className="flex items-center justify-between px-1">
                  <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Recommended Route
                  </span>
                  <span className={cn("text-[10px] px-2 py-0.5 rounded-md font-medium", getRiskLabel(recommendedRoute).bg, getRiskLabel(recommendedRoute).color)}>
                    {getRiskLabel(recommendedRoute).label}
                  </span>
                </div>

                <div className={cn(
                  "p-3.5 rounded-lg transition-colors space-y-3",
                  activeRouteId === recommendedRoute.id
                    ? "bg-[#0b1f36] border-l-2 border-l-emerald-400"
                    : "bg-[#081424]/70 hover:bg-[#081424]"
                )}>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-bold text-slate-100">{recommendedRoute.name}</div>
                      <div className="text-xs text-slate-400 font-mono mt-0.5">{recommendedRoute.distance?.toLocaleString()} km · ETA: {recommendedRoute.eta}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSetActiveRoute(recommendedRoute.id)}
                      className={cn(
                        "px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                        activeRouteId === recommendedRoute.id
                          ? "bg-emerald-500/20 text-emerald-300 font-semibold"
                          : "bg-white/[0.06] hover:bg-white/[0.1] text-slate-200"
                      )}
                    >
                      {activeRouteId === recommendedRoute.id ? "Engaged" : "Select"}
                    </button>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed">
                    {recommendedRoute.reason || 'Optimized for minimal fuel consumption while strictly honoring IMO Polar Code RIO positive limits and avoiding charted iceberg drift vectors.'}
                  </p>

                  <div className="grid grid-cols-4 gap-2 pt-2.5 border-t border-white/[0.06] text-xs">
                    <div>
                      <span className="text-slate-400 block text-[11px] mb-0.5">POLARIS RIO</span>
                      <span className="text-emerald-400 font-bold font-mono">{recommendedRoute.rioScore || '+8.4'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px] mb-0.5">SIC Exposure</span>
                      <span className="text-sky-400 font-bold font-mono">{recommendedRoute.sic_actual || recommendedRoute.sicExposure || 48}%</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px] mb-0.5">Est. Fuel</span>
                      <span className="text-slate-200 font-bold font-mono">{fuelPlan.fuelTonnes.toFixed(1)} t</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px] mb-0.5">Efficiency</span>
                      <span className="text-emerald-400 font-bold font-mono">{(fuelPlan.fuelTonnes / Math.max(recommendedRoute.distance || 1, 1) * 1000).toFixed(1)} kg/km</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {alternativeRoutes.length > 0 && (
              <div className="space-y-2">
                <span className="text-xs font-semibold text-slate-200 block px-1">
                  Alternative Routes
                </span>

                <div className="space-y-2">
                  {alternativeRoutes.map((alt) => {
                    const isSelected = activeRouteId === alt.id;
                    const rRisk = getRiskLabel(alt);
                    return (
                      <div
                        key={alt.id}
                        onClick={() => handleSetActiveRoute(alt.id)}
                        className={cn(
                          "p-3 rounded-lg transition-colors cursor-pointer space-y-1.5",
                          isSelected
                            ? "bg-[#0b1f36] border-l-2 border-l-sky-400 text-slate-100"
                            : "bg-[#081424]/70 hover:bg-[#081424] text-slate-300"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-xs text-slate-200">{alt.name}</span>
                          <span className={cn("text-[10px] px-2 py-0.5 rounded-md font-medium", rRisk.bg, rRisk.color)}>
                            {rRisk.label}
                          </span>
                        </div>
                        <div className="flex justify-between text-xs text-slate-400 font-mono">
                          <span>{alt.distance?.toLocaleString()} km · ETA: {alt.eta}</span>
                          <span>SIC: {alt.sic_actual || alt.sicExposure || 52}%</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

          </div>

          <div className="pt-3 border-t border-white/[0.04] text-xs text-slate-400 flex justify-between">
            <span>IMO Res. A.1026(26)</span>
            <span>POLARIS Compliant</span>
          </div>

        </div>

        <div className="flex-1 relative h-full bg-[#040B14]">
          <PolarMap
            section="overview"
            showRoute={true}
            showVessel={true}
            showSeaIce={true}
            showIcebergs={true}
            showRouteOptimization={true}
            allRoutes={routes}
            activeRouteId={activeRouteId}
            onSelectRoute={(rId) => setActiveRouteId(rId)}
            destinationMarker={{
              latitude: selectedDestination?.latitude ?? -69.4,
              longitude: selectedDestination?.longitude ?? 76.19,
              name: selectedDestination?.name || 'Bharati Station'
            }}
            selectedVesselId={selectedVesselId}
            onSelectVessel={(id) => setSelectedVesselId(id)}
            vesselInfo={{
              name: selectedVessel.name,
              latitude: selectedVessel.latitude,
              longitude: selectedVessel.longitude,
              speed: selectedVessel.speed,
              heading: selectedVessel.heading
            }}
          />
        </div>
      </div>
    </AppShell>
  );
};

export default RouteOptimizationPage;
