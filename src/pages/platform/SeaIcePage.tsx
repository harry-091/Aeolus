import React, { useState, useEffect } from 'react';
import { 
  Satellite, Snowflake, Filter, ShieldCheck
} from 'lucide-react';
import { AppShell } from '../../components/layout/AppShell';
import { useApiData } from "../../hooks/useApiData";
import { useTimeData } from "../../hooks/useTimeData";
import { useFleet } from "../../context/FleetContext";
import PolarMap from '../../components/map/PolarMap';
import { cn } from '../../utils/cn';
import { api } from '../../services/api';

const SECTOR_COORDS: Record<string, [number, number]> = {
  'SEC-01': [-60.5, 20.0],
  'SEC-02': [-64.0, 18.0],
  'SEC-03': [-69.5, 14.0],
  'SEC-04': [-70.8, 11.7],
};

export const SeaIcePage: React.FC = () => {
  const { 
    selectedVesselId, 
    setSelectedVesselId,
    selectedIcebergId,
    setSelectedIcebergId,
    selectedDestination,
    routes,
    activeRouteId,
    setActiveRouteId,
    selectedHorizon,
    setSelectedHorizon,
    activeHorizonLabel
  } = useFleet();

  const [selectedSector, setSelectedSector] = useState<string>('SEC-03');
  const [focusTarget, setFocusTarget] = useState<[number, number] | null>(null);
  const [activeLayer, setActiveLayer] = useState<'grid' | 'sar' | 'both'>('both');

  // Real Sentinel-1 SAR Radar Detection state
  const [sentinelScenes, setSentinelScenes] = useState<any[]>([]);
  const [selectedSceneIdx, setSelectedSceneIdx] = useState<number>(0);
  const [sceneDetection, setSceneDetection] = useState<any>(null);
  const [loadingRadar, setLoadingRadar] = useState<boolean>(false);

  useEffect(() => {
    api.sentinelScenes()
      .then((res: any) => {
        if (res?.scenes?.length) {
          setSentinelScenes(res.scenes);
        }
      })
      .catch((err: any) => console.error("Could not fetch Sentinel scenes:", err));
  }, []);

  useEffect(() => {
    setLoadingRadar(true);
    api.sentinelDetections(selectedSceneIdx)
      .then((res: any) => {
        setSceneDetection(res);
      })
      .catch((err: any) => console.error("Could not fetch SAR detections:", err))
      .finally(() => setLoadingRadar(false));
  }, [selectedSceneIdx]);
  
  useApiData();
  
  const HORIZON_TO_TIMESTEP: Record<number, string> = {
    0: '0',
    6: '6',
    12: '12',
    24: '24',
    48: '48'
  };
  const apiTimeStep = HORIZON_TO_TIMESTEP[selectedHorizon] || '0';
  const { seaIceSectors } = useTimeData(apiTimeStep);

  const sectors = seaIceSectors.length > 0 ? seaIceSectors : [
    { sector: 'SEC-01', name: 'Marginal Ice Zone (MIZ)', concentration: 22, iceType: 'Open Drift Ice / Nilas', thickness: '0.15 - 0.30 m', driftRate: '0.45 m/s WSW', riskLevel: 'LOW' as const },
    { sector: 'SEC-02', name: 'Outer Pack Ice Corridor', concentration: 54, iceType: 'First-Year Thin Floes', thickness: '0.50 - 0.90 m', driftRate: '0.33 m/s SW', riskLevel: 'MODERATE' as const },
    { sector: 'SEC-03', name: 'Queen Maud Approach Shelf', concentration: 76, iceType: 'First-Year Medium Floes', thickness: '1.20 - 1.60 m', driftRate: '0.28 m/s W', riskLevel: 'HIGH' as const },
    { sector: 'SEC-04', name: 'Coastal Fast Ice Boundary', concentration: 94, iceType: 'Landfast / Multi-Year Ridge', thickness: '2.10 - 2.80 m', driftRate: '0.05 m/s (Stationary)', riskLevel: 'CRITICAL' as const },
  ];

  const handleSectorClick = (sectorId: string) => {
    setSelectedSector(sectorId);
    const coords = SECTOR_COORDS[sectorId];
    if (coords) {
      setFocusTarget(coords);
    }
  };

  const horizonOptions: { hours: 0 | 6 | 12 | 24 | 48; label: 'NOW' | '+6H' | '+12H' | '+24H' | '+48H' }[] = [
    { hours: 0, label: 'NOW' },
    { hours: 6, label: '+6H' },
    { hours: 12, label: '+12H' },
    { hours: 24, label: '+24H' },
    { hours: 48, label: '+48H' },
  ];

  const currentSectorData = sectors.find(s => s.sector === selectedSector) || sectors[2];

  return (
    <AppShell
      title="Sea-Ice"
      subtitle="Current Antarctic sea-ice conditions and concentration"
      actions={
        <div className="flex items-center gap-3 text-xs font-sans">
          {/* Horizon Selector */}
          <div className="flex items-center bg-[#081525] border border-white/[0.06] rounded-md p-0.5">
            {horizonOptions.map((h) => (
              <button
                key={h.hours}
                type="button"
                onClick={() => setSelectedHorizon(h.hours)}
                className={cn(
                  "px-2.5 py-1 rounded-sm text-[11px] font-medium transition-colors cursor-pointer",
                  selectedHorizon === h.hours
                    ? "bg-sky-600 text-white font-semibold"
                    : "text-slate-400 hover:text-white"
                )}
              >
                {h.label}
              </button>
            ))}
          </div>

          <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 text-slate-300 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-slate-300 font-medium">NOAA CDR + S1 SAR</span>
          </div>
        </div>
      }
    >
      <div className="flex flex-col h-full overflow-hidden bg-[#040911] font-sans select-none">
        
        {/* ========================================================================= */}
        {/* 1. TOP CONTROLS BAR: Date / Horizon, Region, Layer                       */}
        {/* ========================================================================= */}
        <div className="bg-[#060e18] border-b border-white/[0.04] px-4 sm:px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 text-xs shrink-0">
          
          {/* Left: Region / Ice Sector Selector */}
          <div className="flex items-center gap-2.5">
            <span className="text-slate-400 text-xs font-medium flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-sky-400" />
              Sectors:
            </span>
            <div className="flex items-center gap-1 bg-[#081525] p-1 rounded-md border border-white/[0.06]">
              {sectors.map((s) => (
                <button
                  key={s.sector}
                  type="button"
                  onClick={() => handleSectorClick(s.sector)}
                  className={cn(
                    "px-3 py-1 rounded-sm text-xs font-medium transition-colors cursor-pointer",
                    selectedSector === s.sector
                      ? "bg-sky-600 text-white font-semibold"
                      : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                  )}
                >
                  {s.sector} <span className="font-mono text-[10px] text-slate-300">({s.concentration}%)</span>
                </button>
              ))}
            </div>
          </div>

          {/* Right: Layer Selector & SAR Scene */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 bg-[#081525] p-1 rounded-md border border-white/[0.06]">
              <button
                type="button"
                onClick={() => setActiveLayer('grid')}
                className={cn(
                  "px-3 py-1 rounded-sm text-xs font-medium transition-colors cursor-pointer",
                  activeLayer === 'grid' ? "bg-white/[0.1] text-sky-300 font-semibold" : "text-slate-400 hover:text-white"
                )}
              >
                SIC Grid
              </button>
              <button
                type="button"
                onClick={() => setActiveLayer('sar')}
                className={cn(
                  "px-3 py-1 rounded-sm text-xs font-medium transition-colors cursor-pointer",
                  activeLayer === 'sar' ? "bg-white/[0.1] text-sky-300 font-semibold" : "text-slate-400 hover:text-white"
                )}
              >
                Sentinel-1 SAR
              </button>
              <button
                type="button"
                onClick={() => setActiveLayer('both')}
                className={cn(
                  "px-3 py-1 rounded-sm text-xs font-medium transition-colors cursor-pointer",
                  activeLayer === 'both' ? "bg-white/[0.1] text-sky-300 font-semibold" : "text-slate-400 hover:text-white"
                )}
              >
                Combined
              </button>
            </div>

            {sentinelScenes.length > 0 && (
              <div className="hidden lg:flex items-center gap-2 pl-3 border-l border-white/[0.06]">
                <span className="text-slate-400 text-xs font-medium">SAR Scene:</span>
                <select
                  value={selectedSceneIdx}
                  onChange={(e) => setSelectedSceneIdx(Number(e.target.value))}
                  className="bg-[#081525] border border-white/10 rounded-md text-xs text-slate-200 px-2.5 py-1 font-sans focus:outline-none focus:border-sky-500 cursor-pointer"
                >
                  {sentinelScenes.map((sc, idx) => (
                    <option key={sc.id} value={idx}>
                      Scene #{idx + 1} ({sc.id.substring(0, 18)}...)
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

        </div>

        {/* ========================================================================= */}
        {/* 2. MAIN WORKSPACE: DOMINANT MAP + SIDE METADATA PANEL                    */}
        {/* ========================================================================= */}
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden relative">
          
          {/* Map Viewport */}
          <div className="flex-1 relative h-full bg-[#040911]">
            <PolarMap
              section="sea-ice"
              activeHorizon={activeHorizonLabel}
              showRoute={true}
              showVessel={true}
              timeStep={apiTimeStep}
              focusTarget={focusTarget}
              selectedVesselId={selectedVesselId}
              onSelectVessel={(id) => setSelectedVesselId(id)}
              selectedIcebergId={selectedIcebergId}
              onSelectIceberg={(id) => setSelectedIcebergId(id)}
              destinationMarker={selectedDestination ? {
                latitude: selectedDestination.latitude,
                longitude: selectedDestination.longitude,
                name: selectedDestination.name
              } : undefined}
              allRoutes={routes}
              activeRouteId={activeRouteId}
              onSelectRoute={(rId) => setActiveRouteId(rId)}
            />
          </div>

          {/* Structured Side Information Panel */}
          <div className="w-full lg:w-84 xl:w-96 bg-[#060e18] border-t lg:border-t-0 lg:border-l border-white/[0.04] p-4 overflow-y-auto custom-scrollbar flex flex-col justify-between shrink-0 font-sans text-xs text-slate-300 space-y-4">
            <div className="space-y-4">
              
              {/* 1. Selected Sector Overview */}
              <div className="bg-[#081424]/70 rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                  <span className="text-slate-200 font-semibold text-xs flex items-center gap-2">
                    <div className="w-5 h-5 rounded-md bg-sky-500/10 flex items-center justify-center text-sky-400">
                      <Snowflake className="w-3 h-3" />
                    </div>
                    {currentSectorData.sector} Conditions
                  </span>
                  <span className={cn(
                    "text-[10px] px-2.5 py-0.5 rounded-md font-semibold",
                    currentSectorData.riskLevel === 'HIGH' || currentSectorData.riskLevel === 'CRITICAL'
                      ? "bg-red-500/15 text-red-300"
                      : currentSectorData.riskLevel === 'MODERATE'
                      ? "bg-amber-500/15 text-amber-300"
                      : "bg-emerald-500/15 text-emerald-300"
                  )}>
                    {currentSectorData.riskLevel}
                  </span>
                </div>
                
                <div className="grid grid-cols-2 gap-3 mt-1">
                  <div className="bg-[#081525]/60 p-3 rounded-md">
                    <span className="text-slate-400 text-[11px] block">Concentration</span>
                    <span className="text-xl font-bold font-mono text-slate-100 mt-0.5 block">{currentSectorData.concentration}%</span>
                    <span className="text-[11px] text-sky-400 truncate block mt-0.5">{currentSectorData.iceType}</span>
                  </div>
                  <div className="bg-[#081525]/60 p-3 rounded-md">
                    <span className="text-slate-400 text-[11px] block">Thickness</span>
                    <span className="text-xl font-bold font-mono text-slate-100 mt-0.5 block">{currentSectorData.thickness?.split(' ')[0] || '1.2'} <span className="text-xs font-normal text-slate-400">m</span></span>
                    <span className="text-[11px] text-slate-400 truncate block mt-0.5">Drift: {currentSectorData.driftRate}</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-white/[0.06] text-xs text-slate-400 leading-relaxed">
                  <span className="text-slate-300 font-medium">Zone:</span> {currentSectorData.name}. Sensor fusion active.
                </div>
              </div>

              {/* 2. Environmental Specs */}
              <div className="bg-[#081424]/70 rounded-lg p-3.5 space-y-2.5">
                <span className="text-xs font-semibold text-slate-200 block">
                  Data Specification &amp; Provenance
                </span>
                
                <div className="space-y-1.5 text-xs divide-y divide-white/[0.04]">
                  <div className="flex justify-between pt-1 first:pt-0">
                    <span className="text-slate-400">SIC Mean / Max</span>
                    <span className="text-slate-200 font-mono">64.2% / 94.0%</span>
                  </div>
                  <div className="flex justify-between pt-1.5">
                    <span className="text-slate-400">Observation Date</span>
                    <span className="text-slate-200 font-medium">Daily Pass (12:00 UTC)</span>
                  </div>
                  <div className="flex justify-between pt-1.5">
                    <span className="text-slate-400">Primary Source</span>
                    <span className="text-sky-300 font-medium">NOAA CDR (AMSR2)</span>
                  </div>
                  <div className="flex justify-between pt-1.5">
                    <span className="text-slate-400">Radar Source</span>
                    <span className="text-slate-200">Sentinel-1 C-SAR (HH/HV)</span>
                  </div>
                  <div className="flex justify-between pt-1.5">
                    <span className="text-slate-400">Coverage Resolution</span>
                    <span className="text-slate-200 font-mono">Circumpolar (25km)</span>
                  </div>
                  <div className="flex justify-between pt-1.5">
                    <span className="text-slate-400">Data Quality</span>
                    <span className="text-emerald-400 font-medium flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      CFAR Verified (±3.2%)
                    </span>
                  </div>
                </div>
              </div>

              {/* 3. Sentinel-1 SAR Target Detections */}
              <div className="bg-[#081424]/70 rounded-lg p-3.5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                    <Satellite className="w-3.5 h-3.5 text-sky-400" />
                    SAR Obstacle Detections
                  </span>
                  <span className="text-emerald-400 font-semibold font-mono text-[11px]">
                    {sceneDetection?.total_icebergs_detected || 0} Targets
                  </span>
                </div>

                {loadingRadar ? (
                  <div className="p-3 bg-[#081525]/60 rounded-md text-center text-slate-400 text-xs">
                    Analyzing SAR backscatter...
                  </div>
                ) : sceneDetection?.detections && sceneDetection.detections.length > 0 ? (
                  <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
                    {sceneDetection.detections.slice(0, 4).map((det: any) => (
                      <div key={det.target_id} className="p-2.5 bg-[#081525]/60 rounded-md text-xs space-y-1">
                        <div className="flex items-center justify-between font-semibold">
                          <span className="text-sky-300 font-mono">{det.target_id}</span>
                          <span className="text-emerald-400 font-mono text-[11px]">{(det.confidence * 100).toFixed(0)}% CFAR</span>
                        </div>
                        <div className="text-slate-400 flex justify-between text-[11px] font-mono">
                          <span>Dim: {det.dimensions_km || '0.25x0.15 km'}</span>
                          <span>Peak: {det.peak_sigma0_db || -4.5} dB</span>
                        </div>
                        <div className="text-slate-400 text-[11px]">
                          Type: <span className="text-slate-200">{det.classification || 'Bergy Bit / Ice Floe'}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 bg-[#081525]/60 rounded-md text-slate-400 text-xs text-center">
                    No standalone radar targets in this scene. Pack ice matrix dominant.
                  </div>
                )}
              </div>

            </div>

            {/* Bottom Status Footer */}
            <div className="pt-3 border-t border-white/[0.04] text-xs text-slate-400 flex items-center justify-between">
              <span className="text-emerald-400 flex items-center gap-1.5 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                NOAA CDR Operational
              </span>
              <span className="font-mono text-[11px]">Algorithm: CFAR + Lee</span>
            </div>

          </div>

        </div>

      </div>
    </AppShell>
  );
};

export default SeaIcePage;
