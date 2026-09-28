import React, { useState, useEffect, useMemo } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Radio,
  Compass,
  Ship,
  Activity,
  TrendingUp
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine
} from 'recharts';

import { AppShell } from '../../components/layout/AppShell';
import { PolarMap } from '../../components/map/PolarMap';
import { useFleet, computeBearingDeg } from '../../context/FleetContext';
import { useApiData } from '../../hooks/useApiData';
import { useSimulatedKinematics } from '../../hooks/useSimulatedKinematics';
import { api } from '../../services/api';
import { cn } from '../../utils/cn';

export const TelemetryPage: React.FC = () => {
  useApiData();
  const {
    selectedVessel,
    activeRoute,
    routes,
    activeRouteId,
    setActiveRouteId,
    activeHorizonLabel
  } = useFleet();

  // Simulation state
  const [simPaused, setSimPaused] = useState<boolean>(false);
  const [simSpeed, setSimSpeed] = useState<number>(20);
  const [simDistanceKm, setSimDistanceKm] = useState<number>(0);
  const [telemetrySource, setTelemetrySource] = useState<'SIMULATION' | 'LIVE_NMEA'>('SIMULATION');
  const [nmeaInput, setNmeaInput] = useState<string>('');
  const [isNmeaOpen, setIsNmeaOpen] = useState<boolean>(false);
  const [nmeaFix, setNmeaFix] = useState<{ latitude: number; longitude: number; speed: number; heading: number } | null>(null);

  // Raw catalog icebergs
  const [rawIcebergs, setRawIcebergs] = useState<any[]>([]);
  useEffect(() => {
    api.icebergs().then((res) => {
      if (res?.icebergs?.length) setRawIcebergs(res.icebergs);
    }).catch(() => {});
  }, []);

  const totalDistKm = useMemo(() => {
    return activeRoute?.distance || 3500;
  }, [activeRoute?.distance]);

  const cruisingSpeed = selectedVessel?.speed ?? 13.5;

  // Active vessel geographic position interpolated along corridor
  const simulatedVessel = useMemo(() => {
    if (telemetrySource === 'LIVE_NMEA' && nmeaFix) {
      return {
        name: selectedVessel?.name || 'R/V Sagar Nidhi',
        latitude: nmeaFix.latitude,
        longitude: nmeaFix.longitude,
        heading: nmeaFix.heading,
        speed: nmeaFix.speed
      };
    }

    const path = activeRoute?.path || [];
    if (!path || path.length < 2) {
      return {
        name: selectedVessel?.name || 'R/V Sagar Nidhi',
        latitude: selectedVessel?.latitude ?? -65.2,
        longitude: selectedVessel?.longitude ?? 70.0,
        heading: selectedVessel?.heading ?? 145,
        speed: cruisingSpeed
      };
    }

    const frac = Math.max(0, Math.min(1, simDistanceKm / totalDistKm));
    const targetIdx = frac * (path.length - 1);
    const lowIdx = Math.floor(targetIdx);
    const highIdx = Math.min(path.length - 1, lowIdx + 1);
    const t = targetIdx - lowIdx;

    const p1 = path[lowIdx];
    const p2 = path[highIdx];

    const lat = p1[0] + (p2[0] - p1[0]) * t;
    const lon = p1[1] + (p2[1] - p1[1]) * t;

    const heading = computeBearingDeg(p1, p2);

    return {
      name: selectedVessel?.name || 'R/V Sagar Nidhi',
      latitude: lat,
      longitude: lon,
      heading,
      speed: cruisingSpeed
    };
  }, [telemetrySource, nmeaFix, activeRoute?.path, simDistanceKm, totalDistKm, selectedVessel, cruisingSpeed]);

  // Integrated kinematics hook with dynamic iceberg drift
  const {
    progressFrac,
    elapsedSimHours,
    climaticConditions,
    vesselKinematics,
    dynamicIcebergs,
    nearestIceberg,
    telemetryHistory
  } = useSimulatedKinematics({
    simDistanceKm,
    totalDistanceKm: totalDistKm,
    cruisingSpeedKnots: cruisingSpeed,
    shipLat: simulatedVessel.latitude,
    shipLon: simulatedVessel.longitude,
    shipHeading: simulatedVessel.heading,
    rawIcebergs,
    polarClass: selectedVessel?.polar_class || 'PC5'
  });

  // Simulation advance ticker
  useEffect(() => {
    if (simPaused || telemetrySource === 'LIVE_NMEA') return;

    const interval = setInterval(() => {
      setSimDistanceKm((prev) => {
        const speedKmh = vesselKinematics.sogKnots * 1.852;
        const stepKm = (speedKmh * 0.2 / 3600) * simSpeed;
        const next = prev + stepKm;
        return next >= totalDistKm ? totalDistKm : next;
      });
    }, 200);

    return () => clearInterval(interval);
  }, [simPaused, telemetrySource, vesselKinematics.sogKnots, simSpeed, totalDistKm]);

  const handleToggleSimulation = () => {
    setSimPaused(!simPaused);
  };

  const handleResetSimulation = () => {
    setSimDistanceKm(0);
    setSimPaused(false);
  };

  const handleInjectNmea = (e: React.FormEvent) => {
    e.preventDefault();
    if (!nmeaInput.trim()) return;
    setNmeaFix({
      latitude: -67.45,
      longitude: 74.20,
      speed: 11.8,
      heading: 152
    });
    setTelemetrySource('LIVE_NMEA');
    setIsNmeaOpen(false);
  };

  const remainingKm = Math.max(0, Math.round(totalDistKm - simDistanceKm));
  const etaHours = Math.round(remainingKm / (vesselKinematics.sogKnots * 1.852));

  const tooltipStyle = {
    backgroundColor: '#0B192C',
    borderColor: '#334155',
    color: '#F8FAFC',
    borderRadius: '2px',
    fontSize: '11px',
    fontFamily: 'monospace'
  };

    return (
    <AppShell
      title="VESSEL TELEMETRY & SIMULATION"
      subtitle={`Climatic Kinematics & Dynamic Iceberg Tracking — ${selectedVessel?.name || 'R/V Sagar Nidhi'}`}
      actions={
        <div className="flex items-center gap-2 font-mono text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-[#06111e] border border-slate-800 rounded-xs text-slate-300">
            <Ship className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400">ACTIVE:</span>
            <span className="text-slate-200 font-semibold">{selectedVessel?.name?.split(' ')[0]}</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-[#06111e] border border-slate-800 rounded-xs text-slate-300">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">SOURCE:</span>
            <span className="text-emerald-400 font-semibold">{telemetrySource === 'SIMULATION' ? 'SIMULATION' : 'LIVE NMEA'}</span>
          </div>
        </div>
      }
    >
      <div className="h-full overflow-y-auto custom-scrollbar p-3.5 lg:p-5 space-y-3.5 bg-[#040B14] font-mono text-slate-200">
        
        {/* ========================================================================= */}
        {/* 1. TOP SIMULATION CONTROLS BAR (Clean & Simple)                           */}
        {/* ========================================================================= */}
        <div className="bg-[#06111e] p-3 rounded-xs border border-slate-800 space-y-2.5 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className="text-slate-200 font-bold">{selectedVessel?.name || 'R/V Sagar Nidhi'}</span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-400">Heading: <strong className="text-slate-200">{simulatedVessel.heading}°</strong></span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-400">Position: <strong className="text-sky-300">{Math.abs(simulatedVessel.latitude).toFixed(2)}°S, {Math.abs(simulatedVessel.longitude).toFixed(2)}°E</strong></span>
            </div>

            {/* Transport Buttons */}
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleToggleSimulation}
                className={cn(
                  "px-3 py-1 rounded-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer",
                  simPaused 
                    ? "bg-emerald-700 hover:bg-emerald-600 text-slate-100" 
                    : "bg-[#12283e] hover:bg-[#1a3857] text-sky-300 border border-[#214972]"
                )}
              >
                {simPaused ? <Play className="w-3.5 h-3.5 fill-current" /> : <Pause className="w-3.5 h-3.5 fill-current" />}
                <span>{simPaused ? 'Resume' : 'Pause'}</span>
              </button>

              <button
                type="button"
                onClick={handleResetSimulation}
                className="p-1 rounded-xs bg-[#081524] hover:bg-[#0c1c2e] text-slate-300 border border-slate-800 cursor-pointer"
                title="Reset simulation"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>

              {/* Speed Multiplier */}
              <div className="flex items-center bg-[#040B14] border border-slate-800 rounded-xs p-0.5 ml-1">
                <span className="text-slate-400 px-1.5 text-[10px]">SPEED:</span>
                {([1, 5, 20, 50, 100] as const).map(mult => (
                  <button
                    key={mult}
                    type="button"
                    onClick={() => setSimSpeed(mult)}
                    className={cn(
                      "px-1.5 py-0.5 rounded-xs text-[10px] font-semibold transition-colors cursor-pointer",
                      simSpeed === mult ? "bg-[#12283e] text-sky-300 border border-[#214972]" : "text-slate-400 hover:text-slate-200"
                    )}
                  >
                    {mult}x
                  </button>
                ))}
              </div>

              {/* NMEA Toggle */}
              <button
                type="button"
                onClick={() => setIsNmeaOpen(!isNmeaOpen)}
                className="px-2 py-1 rounded-xs bg-[#081524] hover:bg-[#0c1c2e] text-slate-300 text-[10px] border border-slate-800 flex items-center gap-1 cursor-pointer ml-1"
              >
                <Radio className="w-3 h-3 text-sky-400" />
                <span>NMEA</span>
              </button>
            </div>
          </div>

          {/* Scrubber Range Bar */}
          <div className="space-y-1 pt-1 border-t border-slate-800">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="text-slate-300">
                Progress: <strong className="text-emerald-400 font-bold">{(progressFrac * 100).toFixed(1)}%</strong> ({Math.round(simDistanceKm)} / {Math.round(totalDistKm)} km)
              </span>
              <span>
                Elapsed: T+{Math.floor(elapsedSimHours)}h {Math.floor((elapsedSimHours % 1) * 60)}m • ETA: ~{etaHours}h
              </span>
            </div>

            <input
              type="range"
              min={0}
              max={totalDistKm}
              step={5}
              value={Math.round(simDistanceKm)}
              onChange={(e) => setSimDistanceKm(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-400"
            />
          </div>

          {/* Simple NMEA Input Form */}
          {isNmeaOpen && (
            <form onSubmit={handleInjectNmea} className="pt-2 border-t border-slate-800 flex gap-2">
              <input
                type="text"
                placeholder="$GPRMC,123519,A,6727.00,S,07412.00,E,12.5,145.0,230324,003.1,W*4F"
                value={nmeaInput}
                onChange={(e) => setNmeaInput(e.target.value)}
                className="flex-1 bg-[#040B14] border border-slate-800 rounded-xs px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-slate-600"
              />
              <button
                type="submit"
                className="px-3 py-1 bg-[#12283e] hover:bg-[#1a3857] text-sky-300 border border-[#214972] font-semibold rounded-xs text-xs cursor-pointer"
              >
                Feed NMEA
              </button>
              <button
                type="button"
                onClick={() => {
                  setTelemetrySource('SIMULATION');
                  setNmeaFix(null);
                  setIsNmeaOpen(false);
                }}
                className="px-2 py-1 bg-[#081524] hover:bg-[#0c1c2e] text-slate-400 border border-slate-800 rounded-xs text-xs cursor-pointer"
              >
                Clear
              </button>
            </form>
          )}
        </div>

        {/* ========================================================================= */}
        {/* 2. SIMPLE METRICS CARDS (Just like OverviewPage / SeaIcePage)              */}
        {/* ========================================================================= */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {/* Card 1: Speed */}
          <div className="bg-[#06111e] p-2.5 rounded-xs border border-slate-800 space-y-1">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Speed Over Ground</span>
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-sky-300">{vesselKinematics.sogKnots.toFixed(1)}</span>
              <span className="text-[11px] text-slate-400">kn</span>
            </div>
            <span className="text-[10px] text-slate-400 block pt-1 border-t border-slate-800">
              STW: {vesselKinematics.stwKnots.toFixed(1)} kn
            </span>
          </div>

          {/* Card 2: Engine RPM */}
          <div className="bg-[#06111e] p-2.5 rounded-xs border border-slate-800 space-y-1">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Engine Load</span>
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-slate-200">{vesselKinematics.engineRpm}</span>
              <span className="text-[11px] text-slate-400">RPM ({vesselKinematics.engineLoadPct}%)</span>
            </div>
            <span className="text-[10px] text-slate-400 block pt-1 border-t border-slate-800">
              Power: {vesselKinematics.shaftPowerKw} kW
            </span>
          </div>

          {/* Card 3: Fuel Rate */}
          <div className="bg-[#06111e] p-2.5 rounded-xs border border-slate-800 space-y-1">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Fuel Burn</span>
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-amber-400">{vesselKinematics.fuelRateMtDay.toFixed(1)}</span>
              <span className="text-[11px] text-slate-400">MT/day</span>
            </div>
            <span className="text-[10px] text-slate-400 block pt-1 border-t border-slate-800">
              Total: {vesselKinematics.cumulativeFuelTons.toFixed(1)} T
            </span>
          </div>

          {/* Card 4: Sea Ice */}
          <div className="bg-[#06111e] p-2.5 rounded-xs border border-slate-800 space-y-1">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Sea Ice (SIC)</span>
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-sky-400">{climaticConditions.sicPct}%</span>
              <span className="text-[10px] text-slate-400 truncate">{climaticConditions.iceStage}</span>
            </div>
            <span className="text-[10px] text-slate-400 block pt-1 border-t border-slate-800">
              Thickness: {climaticConditions.iceThicknessM} m
            </span>
          </div>

          {/* Card 5: Hull Load */}
          <div className="bg-[#06111e] p-2.5 rounded-xs border border-slate-800 space-y-1">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Hull Stress</span>
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-slate-200">{vesselKinematics.hullStressKn}</span>
              <span className="text-[11px] text-slate-400">/ 2200 kN</span>
            </div>
            <span className="text-[10px] text-slate-400 block pt-1 border-t border-slate-800">
              RIO: <strong className={vesselKinematics.rioScore >= 0 ? "text-emerald-400" : "text-red-400"}>
                {vesselKinematics.rioScore >= 0 ? `+${vesselKinematics.rioScore}` : vesselKinematics.rioScore}
              </strong> ({vesselKinematics.polarCodeStatus})
            </span>
          </div>

          {/* Card 6: Nearest Berg */}
          <div className="bg-[#06111e] p-2.5 rounded-xs border border-slate-800 space-y-1">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Nearest Iceberg</span>
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-sky-400">
                {nearestIceberg ? `${nearestIceberg.distanceToShipKm.toFixed(1)}` : 'N/A'}
              </span>
              <span className="text-[11px] text-slate-400">km</span>
            </div>
            <span className="text-[10px] text-slate-400 block pt-1 border-t border-slate-800 truncate">
              {nearestIceberg?.name || 'None'} • {nearestIceberg?.cpaDistanceNm.toFixed(1)} NM CPA
            </span>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* 3. POLAR MAP (Clean Nautical Presentation)                                */}
        {/* ========================================================================= */}
        <div className="bg-[#06111e] rounded-xs border border-slate-800 overflow-hidden space-y-2">
          <div className="px-3.5 py-2 border-b border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-200 font-semibold flex items-center gap-1.5 uppercase">
              <Compass className="w-3.5 h-3.5 text-sky-400" />
              Circumpolar Navigation &amp; Dynamic Iceberg Drift Map
            </span>
            <div className="flex items-center gap-3 text-[11px] text-slate-400">
              <span>Ship • Moving on Route</span>
              <span>•</span>
              <span>All 85 Icebergs • Drifting with Ocean Current</span>
            </div>
          </div>

          <div className="h-[400px] w-full relative">
            <PolarMap
              section="navigation"
              activeHorizon={activeHorizonLabel}
              activeRouteId={activeRoute?.id || activeRouteId}
              onSelectRoute={(id) => setActiveRouteId(id)}
              customRoutePath={activeRoute?.path}
              allRoutes={routes}
              icebergs={dynamicIcebergs}
              vesselInfo={{
                name: simulatedVessel.name,
                latitude: simulatedVessel.latitude,
                longitude: simulatedVessel.longitude,
                heading: simulatedVessel.heading,
                speed: vesselKinematics.sogKnots
              }}
              selectedVesselId={selectedVessel?.id}
            />
          </div>
        </div>

        {/* ========================================================================= */}
        {/* 4. CLEAN LONG-PAGE TELEMETRY GRAPHS (Just like AnalysisPage)               */}
        {/* ========================================================================= */}
        <div className="space-y-3">
          <div className="border-b border-slate-800 pb-2">
            <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-sky-400" />
              Voyage Environmental &amp; Hull Telemetry History
            </span>
            <span className="text-[11px] text-slate-400">
              Real-time progression curves along the corridor ({telemetryHistory.length} checkpoints recorded)
            </span>
          </div>

          {/* Graph 1: Speed & Propulsion */}
          <div className="bg-[#06111e] p-3.5 rounded-xs border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-200 uppercase">
                01 // Speed (SOG/STW), Engine RPM &amp; Fuel Rate
              </span>
              <div className="flex items-center gap-3 text-[11px] text-slate-400">
                <span className="text-sky-300">SOG: {vesselKinematics.sogKnots} kn</span>
                <span className="text-emerald-400">RPM: {vesselKinematics.engineRpm}</span>
                <span className="text-amber-300">Fuel: {vesselKinematics.fuelRateMtDay} MT/d</span>
              </div>
            </div>

            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={telemetryHistory} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                  <XAxis dataKey="distanceKm" stroke="#64748B" unit=" km" fontSize={10} />
                  <YAxis yAxisId="speed" stroke="#38BDF8" domain={[0, 18]} unit=" kn" fontSize={10} />
                  <YAxis yAxisId="rpm" orientation="right" stroke="#10B981" domain={[60, 140]} unit=" rpm" fontSize={10} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                  <Line yAxisId="speed" type="monotone" dataKey="sogKnots" name="SOG (kn)" stroke="#38BDF8" strokeWidth={1.8} dot={false} />
                  <Line yAxisId="speed" type="monotone" dataKey="stwKnots" name="STW (kn)" stroke="#94A3B8" strokeWidth={1.2} strokeDasharray="3 3" dot={false} />
                  <Line yAxisId="rpm" type="monotone" dataKey="engineRpm" name="Engine RPM" stroke="#10B981" strokeWidth={1.5} dot={false} />
                  <Line yAxisId="speed" type="monotone" dataKey="fuelRateMtDay" name="Fuel (MT/d)" stroke="#F59E0B" strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Graph 2: Hull Stress & RIO Safety Margin */}
          <div className="bg-[#06111e] p-3.5 rounded-xs border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-200 uppercase">
                02 // Hull Dynamic Stress &amp; Polar Class 5 Limit
              </span>
              <div className="flex items-center gap-3 text-[11px] text-slate-400">
                <span className="text-slate-300">Bow Load: {vesselKinematics.hullStressKn} kN</span>
                <span className="text-emerald-400">Limit: 2200 kN</span>
              </div>
            </div>

            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={telemetryHistory} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                  <XAxis dataKey="distanceKm" stroke="#64748B" unit=" km" fontSize={10} />
                  <YAxis stroke="#F87171" domain={[0, 2600]} unit=" kN" fontSize={10} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                  <ReferenceLine y={2200} stroke="#EF4444" strokeDasharray="4 4" label={{ value: 'PC5 LIMIT (2200 kN)', fill: '#EF4444', fontSize: 10 }} />
                  <Area type="monotone" dataKey="hullStressKn" name="Hull Stress (kN)" stroke="#F87171" fill="#F87171" fillOpacity={0.2} strokeWidth={1.8} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Graph 3: Sea Ice, Wind & Wave Height */}
          <div className="bg-[#06111e] p-3.5 rounded-xs border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-200 uppercase">
                03 // Climatic Conditions (Sea Ice Conc, Wind &amp; Swell)
              </span>
              <div className="flex items-center gap-3 text-[11px] text-slate-400">
                <span className="text-sky-300">SIC: {climaticConditions.sicPct}%</span>
                <span className="text-amber-400">Wind: {climaticConditions.windSpeedKnots} kn</span>
                <span className="text-purple-300">Wave: {climaticConditions.waveHeightM} m</span>
              </div>
            </div>

            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={telemetryHistory} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                  <XAxis dataKey="distanceKm" stroke="#64748B" unit=" km" fontSize={10} />
                  <YAxis yAxisId="pct" stroke="#38BDF8" domain={[0, 100]} unit="%" fontSize={10} />
                  <YAxis yAxisId="wave" orientation="right" stroke="#A855F7" domain={[0, 6]} unit=" m" fontSize={10} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                  <Line yAxisId="pct" type="monotone" dataKey="sicPct" name="Sea Ice Conc (%)" stroke="#38BDF8" strokeWidth={1.8} dot={false} />
                  <Line yAxisId="pct" type="monotone" dataKey="windSpeedKnots" name="Wind Speed (kn)" stroke="#F59E0B" strokeWidth={1.5} dot={false} />
                  <Line yAxisId="wave" type="monotone" dataKey="waveHeightM" name="Wave Height (m)" stroke="#A855F7" strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Graph 4: Nearest Iceberg & Dynamic CPA */}
          <div className="bg-[#06111e] p-3.5 rounded-xs border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-200 uppercase">
                04 // Iceberg Proximity &amp; Closest Point of Approach (CPA)
              </span>
              <div className="flex items-center gap-3 text-[11px] text-slate-400">
                <span className="text-sky-300">Dist: {nearestIceberg?.distanceToShipKm.toFixed(1)} km</span>
                <span className="text-amber-400">CPA: {nearestIceberg?.cpaDistanceNm.toFixed(1)} NM</span>
              </div>
            </div>

            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={telemetryHistory} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                  <XAxis dataKey="distanceKm" stroke="#64748B" unit=" km" fontSize={10} />
                  <YAxis yAxisId="dist" stroke="#38BDF8" unit=" km" fontSize={10} />
                  <YAxis yAxisId="cpa" orientation="right" stroke="#F59E0B" domain={[0, 40]} unit=" NM" fontSize={10} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                  <ReferenceLine yAxisId="cpa" y={5.0} stroke="#EF4444" strokeDasharray="3 3" label={{ value: 'SAFE MARGIN 5 NM', fill: '#EF4444', fontSize: 10 }} />
                  <Line yAxisId="dist" type="monotone" dataKey="nearestBergDistKm" name="Distance to Berg (km)" stroke="#38BDF8" strokeWidth={1.5} dot={false} />
                  <Line yAxisId="cpa" type="monotone" dataKey="nearestBergCpaNm" name="Dynamic CPA (NM)" stroke="#F59E0B" strokeWidth={1.8} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

      </div>
    </AppShell>
  );
};

export default TelemetryPage;
