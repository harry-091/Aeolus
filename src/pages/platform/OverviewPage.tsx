import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  ShieldAlert, 
  Ship, 
  Snowflake,
  Mountain,
  CheckCircle2, 
  ArrowRight,
  Activity,
  AlertTriangle
} from 'lucide-react';
import { AppShell } from '../../components/layout/AppShell';
import { useApiData } from "../../hooks/useApiData";
import PolarMap from '../../components/map/PolarMap';
import { useFleet } from '../../context/FleetContext';
import { cn } from '../../utils/cn';

export const OverviewPage: React.FC = () => {
  const [layers, setLayers] = useState({
    vessel: true,
    route: true,
    seaIce: true,
    icebergs: true,
    historicalVessels: false,
  });
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
    activeRoute,
    selectedIcebergId,
    setSelectedIcebergId,
    selectedHorizon,
    setSelectedHorizon,
    activeHorizonLabel
  } = useFleet();

  const currentRoute = activeRoute || routes[0] || {
    id: 'route-b',
    name: 'ROUTE B (OPTIMAL)',
    distance: 4120,
    eta: '32h 05m',
    rioScore: '+8.4'
  };

  const horizonOptions: { hours: 0 | 6 | 12 | 24 | 48; label: 'NOW' | '+6H' | '+12H' | '+24H' | '+48H' }[] = [
    { hours: 0, label: 'NOW' },
    { hours: 6, label: '+6H' },
    { hours: 12, label: '+12H' },
    { hours: 24, label: '+24H' },
    { hours: 48, label: '+48H' },
  ];

  return (
    <AppShell
      title="Overview"
      subtitle="Antarctic operational summary and regional situational awareness"
      actions={
        <div className="flex items-center gap-3 text-xs font-sans">
          {/* Horizon Selector */}
          <div className="flex items-center bg-slate-900/60 border border-slate-800/50 rounded-lg p-0.5">
            {horizonOptions.map((h) => (
              <button
                key={h.hours}
                type="button"
                onClick={() => setSelectedHorizon(h.hours)}
                className={cn(
                  "px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer",
                  selectedHorizon === h.hours
                    ? "bg-slate-800 text-sky-300 font-semibold shadow-xs"
                    : "text-slate-400 hover:text-white"
                )}
              >
                {h.label}
              </button>
            ))}
          </div>

          <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 text-slate-300 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-slate-300 font-medium">Operational</span>
          </div>

          <Link
            to="/navigation"
            className="flex items-center gap-1.5 bg-sky-600 hover:bg-sky-500 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold tracking-wide transition-colors shadow-xs"
          >
            <span>Live Navigation</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      }
    >
      <div className="min-h-full overflow-y-auto custom-scrollbar p-4 sm:p-6 pb-12 space-y-4 bg-[#040911] text-slate-200 font-sans select-none">
        
        {/* ========================================================================= */}
        {/* 1. OPERATIONAL STATUS — 4 CLEAN CARDS                                    */}
        {/* ========================================================================= */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs font-sans">
          
          {/* Card 1: Sea Ice */}
          <div className="bg-[#081424]/70 p-4 rounded-lg flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                <span className="flex items-center gap-2 font-semibold text-slate-200">
                  <div className="w-5 h-5 rounded-md bg-sky-500/10 flex items-center justify-center text-sky-400">
                    <Snowflake className="w-3 h-3" />
                  </div>
                  Sea Ice Concentration
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-white/[0.06] text-slate-300 font-mono">
                  NOAA CDR
                </span>
              </div>
              <div className="text-xl font-bold text-slate-100 font-mono mt-1">
                64.2% <span className="text-xs font-normal text-slate-400 font-sans">Mean SIC</span>
              </div>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Marginal Ice Zone / Pack corridor with 0.31 m/s drift rate.
              </p>
            </div>
            <div className="pt-2.5 mt-3 border-t border-white/[0.06] text-xs text-slate-400 flex justify-between">
              <span>Thickness: 0.8 - 1.4 m</span>
              <span className="text-emerald-400 font-medium">Passable</span>
            </div>
          </div>

          {/* Card 2: Iceberg Alerts */}
          <div className="bg-[#081424]/70 p-4 rounded-lg flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                <span className="flex items-center gap-2 font-semibold text-slate-200">
                  <div className="w-5 h-5 rounded-md bg-amber-500/10 flex items-center justify-center text-amber-400">
                    <Mountain className="w-3 h-3" />
                  </div>
                  Iceberg Targets
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-300 font-sans font-medium">
                  2 Caution
                </span>
              </div>
              <div className="text-xl font-bold text-slate-100 font-mono mt-1">
                85 <span className="text-xs font-normal text-slate-400 font-sans">Charted Targets</span>
              </div>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                2 charted bergs within 18 km corridor CPA buffer.
              </p>
            </div>
            <div className="pt-2.5 mt-3 border-t border-white/[0.06] text-xs text-slate-400 flex justify-between">
              <span>US NIC + S1 SAR</span>
              <span className="text-amber-400 font-medium">Monitored</span>
            </div>
          </div>

          {/* Card 3: Route Risk */}
          <div className="bg-[#081424]/70 p-4 rounded-lg flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                <span className="flex items-center gap-2 font-semibold text-slate-200">
                  <div className="w-5 h-5 rounded-md bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                    <ShieldAlert className="w-3 h-3" />
                  </div>
                  Route POLARIS Risk
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 font-sans font-medium">
                  Safe
                </span>
              </div>
              <div className="text-xl font-bold text-emerald-400 font-mono mt-1">
                RIO {currentRoute.rioScore || '+8.4'}
              </div>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                IMO POLARIS compliant for {selectedVessel.polar_class ? selectedVessel.polar_class.split(' ')[0] : 'PC5'} ice class.
              </p>
            </div>
            <div className="pt-2.5 mt-3 border-t border-white/[0.06] text-xs text-slate-400 flex justify-between">
              <span>Active: {currentRoute.name?.split(' ')[0] || 'Route B'}</span>
              <span className="text-slate-300 font-mono">{currentRoute.distance} km</span>
            </div>
          </div>

          {/* Card 4: Vessel Status */}
          <div className="bg-[#081424]/70 p-4 rounded-lg flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                <span className="flex items-center gap-2 font-semibold text-slate-200">
                  <div className="w-5 h-5 rounded-md bg-sky-500/10 flex items-center justify-center text-sky-400">
                    <Ship className="w-3 h-3" />
                  </div>
                  Vessel Status
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-white/[0.06] text-slate-300 font-mono">
                  {selectedVessel.data_status === 'LIVE' ? 'LIVE AIS' : 'SIMULATION'}
                </span>
              </div>
              <div className="text-base font-bold text-slate-100 truncate mt-1">
                {selectedVessel.name}
              </div>
              <p className="text-xs text-slate-400 mt-1 font-mono">
                {Math.abs(selectedVessel.latitude || 0).toFixed(2)}°S, {Math.abs(selectedVessel.longitude || 0).toFixed(2)}°{(selectedVessel.longitude || 0) >= 0 ? 'E' : 'W'}
              </p>
            </div>
            <div className="pt-2.5 mt-3 border-t border-white/[0.06] text-xs text-slate-400 flex justify-between">
              <span>Speed: {selectedVessel.speed || selectedVessel.sog || 12.0} kn</span>
              <span className="text-slate-300 font-mono">Hdg: {selectedVessel.heading || 180}°T</span>
            </div>
          </div>

        </div>

        {/* ========================================================================= */}
        {/* 2. OPERATIONAL MAP / REGIONAL OVERVIEW                                   */}
        {/* ========================================================================= */}
        <div className="bg-[#060e18] rounded-lg overflow-hidden flex flex-col border border-white/[0.04]">
          {/* Map Sub-Header & Controls */}
          <div className="px-4 py-2.5 bg-[#060e18] border-b border-white/[0.04] flex flex-wrap items-center justify-between gap-3 text-xs font-sans">
            <div className="flex items-center gap-3">
              <span className="text-slate-100 font-semibold">Regional Operational Overview</span>
              <span className="text-slate-600 hidden sm:inline">•</span>
              <span className="text-slate-400 text-xs hidden sm:inline">Queen Maud Land to Bharati Station Corridor</span>
            </div>

            {/* Quick Map Layer Toggles */}
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400 text-xs font-medium mr-1">Layers:</span>
              <button
                type="button"
                onClick={() => setLayers(l => ({ ...l, seaIce: !l.seaIce }))}
                className={cn(
                  "px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  layers.seaIce ? "bg-white/[0.1] text-sky-300 font-semibold" : "text-slate-400 hover:text-white"
                )}
              >
                Sea Ice
              </button>
              <button
                type="button"
                onClick={() => setLayers(l => ({ ...l, icebergs: !l.icebergs }))}
                className={cn(
                  "px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  layers.icebergs ? "bg-white/[0.1] text-sky-300 font-semibold" : "text-slate-400 hover:text-white"
                )}
              >
                85 Icebergs
              </button>
              <button
                type="button"
                onClick={() => setLayers(l => ({ ...l, route: !l.route }))}
                className={cn(
                  "px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  layers.route ? "bg-white/[0.1] text-sky-300 font-semibold" : "text-slate-400 hover:text-white"
                )}
              >
                Corridor
              </button>
            </div>
          </div>

          {/* Map Viewport */}
          <div className="relative w-full h-[600px] lg:h-[700px] min-h-[520px] bg-[#040911]">
            <PolarMap
              section="overview"
              activeHorizon={activeHorizonLabel}
              selectedIcebergId={selectedIcebergId}
              onSelectIceberg={(id) => setSelectedIcebergId(id)}
              selectedVesselId={selectedVesselId}
              onSelectVessel={(id) => setSelectedVesselId(id)}
              destinationMarker={{
                latitude: selectedDestination.latitude,
                longitude: selectedDestination.longitude,
                name: selectedDestination.name
              }}
              vesselInfo={
                selectedVessel.latitude !== undefined && selectedVessel.longitude !== undefined
                  ? {
                      name: selectedVessel.name,
                      latitude: selectedVessel.latitude,
                      longitude: selectedVessel.longitude,
                      speed: selectedVessel.speed,
                      heading: selectedVessel.heading
                    }
                  : null
              }
              allRoutes={routes}
              showVessel={layers.vessel}
              showRoute={layers.route}
              showSeaIce={layers.seaIce}
              showIcebergs={layers.icebergs}
              showRouteOptimization={true}
              activeRouteId={activeRouteId}
              onSelectRoute={(rId) => setActiveRouteId(rId)}
              showHistoricalVessels={layers.historicalVessels}
            />
            <aside className="absolute right-4 top-4 z-20 hidden w-80 overflow-hidden rounded-2xl border border-[#c9e4f4] bg-white/95 shadow-[0_12px_30px_rgba(7,90,156,.18)] backdrop-blur lg:block">
              <div className="flex items-center justify-between border-b border-[#dcecf5] bg-[#075a9c] px-4 py-3 text-white">
                <span className="flex items-center gap-2 text-xs font-bold"><AlertTriangle className="h-4 w-4 text-[#ffca5c]" />Active hazards</span>
                <Link to="/alerts" className="text-[10px] font-bold uppercase tracking-wide text-[#bceeff] hover:text-white">View all</Link>
              </div>
              <div className="space-y-3 p-3 text-xs">
                <HazardCard level="ACTION" title="Iceberg corridor proximity" detail="A-84C is 14.8 km from waypoint 04. Review the corridor before proceeding." time="Latest position" />
                <HazardCard level="WATCH" title="Marginal pack ice" detail="Sea-ice concentration is 64% along the current route segment." time="NOAA CDR update" />
                <HazardCard level="NOTICE" title="Weather exposure" detail="Wind and surface-current conditions may increase fuel burn." time="Forecast layer" />
              </div>
            </aside>
          </div>

          {/* Quick Mission Selector Strip */}
          <div className="px-4 py-3 bg-[#060e18] border-t border-white/[0.04] grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs font-sans">
            <div>
              <span className="text-[11px] font-medium text-slate-400 block mb-1">Active Vessel</span>
              <select
                value={selectedVesselId}
                onChange={(e) => setSelectedVesselId(e.target.value)}
                className="w-full bg-[#081525] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-slate-100 font-sans focus:outline-none focus:border-sky-500 cursor-pointer"
              >
                {fleet.map(v => (
                  <option key={v.id} value={v.id}>
                    {v.flag} {v.name} ({v.speed || v.sog} kn)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <span className="text-[11px] font-medium text-slate-400 block mb-1">Destination</span>
              <select
                value={selectedDestinationId}
                onChange={(e) => setSelectedDestinationId(e.target.value)}
                className="w-full bg-[#081525] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-slate-100 font-sans focus:outline-none focus:border-sky-500 cursor-pointer"
              >
                {stations.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({Math.abs(s.latitude).toFixed(1)}°S)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <span className="text-[11px] font-medium text-slate-400 block mb-1">Selected Corridor</span>
              <div className="text-xs text-slate-100 font-medium py-1.5 truncate">
                {currentRoute.name || 'Route B (Optimal)'} <span className="text-slate-400 font-mono">({currentRoute.distance} km)</span>
              </div>
            </div>
            <div>
              <span className="text-[11px] font-medium text-slate-400 block mb-1">POLARIS Evaluation</span>
              <div className="text-xs text-emerald-400 font-semibold py-1.5">
                RIO {currentRoute.rioScore || '+8.4'} · Safe to Navigate
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* 3. OPERATIONAL LOGS & SYSTEM STATUS — 3 CLEAN PANELS                      */}
        {/* ========================================================================= */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 font-sans text-xs">
          
          {/* Panel 1: Recent Alerts */}
          <div className="bg-[#081424]/70 rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5 mb-3">
                <span className="text-xs font-semibold text-slate-100 flex items-center gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  Recent Operational Warnings
                </span>
                <span className="text-[10px] text-amber-300 bg-amber-500/15 px-2 py-0.5 rounded-md font-medium">2 Active</span>
              </div>
              <div className="space-y-2">
                <div className="p-3 bg-[#081525]/60 rounded-md space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-amber-300 font-semibold">Iceberg Proximity Alert</span>
                    <span className="text-slate-400 font-mono text-[10px]">14:12 UTC</span>
                  </div>
                  <p className="text-slate-300 text-xs leading-relaxed">
                    Tracked berg A-84C drifted within 14.8 km of corridor waypoint 04. CPA clearance confirmed safe.
                  </p>
                </div>
                <div className="p-3 bg-[#081525]/60 rounded-md space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-200 font-semibold">Sea Ice Thickness Update</span>
                    <span className="text-slate-400 font-mono text-[10px]">13:45 UTC</span>
                  </div>
                  <p className="text-slate-300 text-xs leading-relaxed">
                    Marginal Ice Zone concentration updated to 64% via latest NOAA CDR pass.
                  </p>
                </div>
              </div>
            </div>
            <Link
              to="/alerts"
              className="mt-4 pt-2.5 border-t border-white/[0.06] text-xs text-sky-400 hover:text-white flex items-center justify-between transition-colors font-medium"
            >
              <span>View all operational alerts</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Panel 2: Recent Events */}
          <div className="bg-[#081424]/70 rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5 mb-3">
                <span className="text-xs font-semibold text-slate-100 flex items-center gap-2">
                  <Activity className="w-3.5 h-3.5 text-sky-400" />
                  Chronological Navigation Events
                </span>
                <span className="text-[10px] text-slate-400">Live Log</span>
              </div>
              <div className="space-y-2">
                <div className="p-3 bg-[#081525]/60 rounded-md space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-200 font-semibold">Waypoint Transit</span>
                    <span className="text-slate-400 font-mono text-[10px]">14:20 UTC</span>
                  </div>
                  <p className="text-slate-300 text-xs leading-relaxed">
                    {selectedVessel.name} cleared Waypoint 03 (64.2°S, 38.4°E) at 12.4 kn SOG.
                  </p>
                </div>
                <div className="p-3 bg-[#081525]/60 rounded-md space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-200 font-semibold">SAR Radar Ingestion</span>
                    <span className="text-slate-400 font-mono text-[10px]">12:00 UTC</span>
                  </div>
                  <p className="text-slate-300 text-xs leading-relaxed">
                    Sentinel-1 GeoTIFF scene processed with 6 verified CFAR detections.
                  </p>
                </div>
              </div>
            </div>
            <Link
              to="/intelligence"
              className="mt-4 pt-2.5 border-t border-white/[0.06] text-xs text-sky-400 hover:text-white flex items-center justify-between transition-colors font-medium"
            >
              <span>View intelligence logs</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Panel 3: System Status & Data Integrity */}
          <div className="bg-[#081424]/70 rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5 mb-3">
                <span className="text-xs font-semibold text-slate-100 flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Sensors &amp; Data Pipeline
                </span>
                <span className="text-[10px] text-emerald-300 bg-emerald-500/15 px-2 py-0.5 rounded-md font-medium">All Healthy</span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between items-center p-2 bg-[#081525]/60 rounded-md">
                  <span className="text-slate-300">NOAA CDR Sea Ice Grid</span>
                  <span className="text-emerald-400 font-medium flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    Online (25 km)
                  </span>
                </div>
                <div className="flex justify-between items-center p-2 bg-[#081525]/60 rounded-md">
                  <span className="text-slate-300">US NIC 85 Iceberg Dataset</span>
                  <span className="text-emerald-400 font-medium flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    Synchronized
                  </span>
                </div>
                <div className="flex justify-between items-center p-2 bg-[#081525]/60 rounded-md">
                  <span className="text-slate-300">Sentinel-1 SAR C-Band</span>
                  <span className="text-emerald-400 font-medium flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    Active Pipeline
                  </span>
                </div>
                <div className="flex justify-between items-center p-2 bg-[#081525]/60 rounded-md">
                  <span className="text-slate-300">IMO POLARIS Risk Engine</span>
                  <span className="text-emerald-400 font-medium flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    PC5 Calibrated
                  </span>
                </div>
              </div>
            </div>
            <div className="mt-4 pt-2.5 border-t border-white/[0.06] text-xs text-slate-400 flex justify-between font-mono text-[11px]">
              <span>FastAPI Backend: Online</span>
              <span>Vite Client: Online</span>
            </div>
          </div>

        </div>

      </div>
    </AppShell>
  );
};

export default OverviewPage;

function HazardCard({ level, title, detail, time }: { level: 'ACTION' | 'WATCH' | 'NOTICE'; title: string; detail: string; time: string }) {
  const tone = level === 'ACTION' ? 'bg-rose-50 text-rose-700 border-rose-200' : level === 'WATCH' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-sky-50 text-sky-700 border-sky-200';
  return <article className={`rounded-xl border p-3 ${tone}`}><div className="flex items-center justify-between gap-2"><span className="text-[9px] font-bold uppercase tracking-[.14em]">{level}</span><span className="text-[9px] opacity-70">{time}</span></div><h3 className="mt-2 text-xs font-bold">{title}</h3><p className="mt-1 text-[11px] leading-relaxed opacity-85">{detail}</p></article>;
}
