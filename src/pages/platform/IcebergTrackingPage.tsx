import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Mountain, Search, X
} from 'lucide-react';
import { AppShell } from '../../components/layout/AppShell';
import { useApiData } from "../../hooks/useApiData";
import { useFleet } from '../../context/FleetContext';
import PolarMap, { FALLBACK_ICEBERGS } from '../../components/map/PolarMap';
import { api } from '../../services/api';
import { cn } from '../../utils/cn';

interface IcebergForecastPoint {
  horizon: 'NOW' | '+6H' | '+12H' | '+24H' | '+48H';
  timeLabel: string;
  coordinates: [number, number];
  displacementKm: number;
  speedKn: number;
}

interface Iceberg {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  velocity: number;
  direction: string;
  movementTrend: string;
  size: number;
  areaKm2: number;
  draftEstimate: number;
  confidence: number;
  risk: string;
  distanceFromVessel: string;
  lastObserved: string;
  sensorSource: string;
  status?: string;
  region?: string;
  historicalTrajectory?: [number, number][];
  predictedTrajectory?: [number, number][];
  forecastPoints?: IcebergForecastPoint[];
}

const getFallbackIcebergs = (): Iceberg[] => FALLBACK_ICEBERGS.map((iceberg) => ({
  ...iceberg,
  movementTrend: 'Modelled drift',
  size: iceberg.areaKm2,
  distanceFromVessel: 'Unavailable offline',
  lastObserved: 'Built-in safety catalog',
  sensorSource: 'Offline safety catalog',
  status: 'Drifting',
}));

export const IcebergTrackingPage: React.FC = () => {
  const { 
    selectedVesselId, 
    selectedVessel, 
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

  const [icebergs, setIcebergs] = useState<Iceberg[]>(getFallbackIcebergs);
  const [usingFallback, setUsingFallback] = useState(true);
  const [mapFocusTarget, setMapFocusTarget] = useState<[number, number] | null>(null);

  // Filters
  const [filterId, setFilterId] = useState<string>('');
  const [filterRisk, setFilterRisk] = useState<string>('ALL');
  const [filterRegion, setFilterRegion] = useState<string>('ALL');
  const [filterStatus, setFilterStatus] = useState<string>('ALL');

  useApiData();

  // Fetch authentic icebergs from backend (85 BYU/US NIC records)
  const fetchIcebergs = useCallback(async () => {
    try {
      const res = await api.icebergs(activeHorizonLabel);
      if (res?.icebergs?.length) {
        setIcebergs(res.icebergs);
        setUsingFallback(false);
      } else {
        setIcebergs(getFallbackIcebergs());
        setUsingFallback(true);
      }
    } catch (e) {
      // The hosted console must keep the safety layer usable during provider outage.
      setIcebergs(getFallbackIcebergs());
      setUsingFallback(true);
    }
  }, [activeHorizonLabel]);

  useEffect(() => {
    fetchIcebergs();
  }, [fetchIcebergs]);

  // Enrich with region and realistic distance to vessel / route
  const enrichedIcebergs = useMemo(() => {
    const vLat = selectedVessel.latitude || -54.2;
    const vLon = selectedVessel.longitude || 68.4;
    return icebergs.map(ib => {
      const dLat = (ib.latitude - vLat) * 111.0;
      const dLon = (ib.longitude - vLon) * 111.0 * Math.cos((vLat * Math.PI) / 180);
      const dist = Math.round(Math.sqrt(dLat * dLat + dLon * dLon));

      // Classify region based on longitude
      let region = 'Weddell Sea';
      if (ib.longitude > 60 && ib.longitude <= 150) region = 'Prydz Bay / Amery';
      else if (ib.longitude > 150 || ib.longitude <= -130) region = 'Ross Sea';
      else if (ib.longitude > -130 && ib.longitude <= -60) region = 'Bellingshausen';
      else if (ib.longitude > -60 && ib.longitude <= 20) region = 'Weddell Sea';
      else region = 'Queen Maud Shelf';

      return {
        ...ib,
        region,
        status: ib.velocity > 0.4 ? 'Moving' : ib.velocity > 0 ? 'Drifting' : 'Stationary',
        distanceKm: dist,
        distanceToRoute: `${dist} km`
      };
    });
  }, [icebergs, selectedVessel]);

  // Filtered dataset
  const filteredIcebergs = useMemo(() => {
    return enrichedIcebergs.filter(ib => {
      if (filterId && !ib.id.toLowerCase().includes(filterId.toLowerCase()) && !ib.name.toLowerCase().includes(filterId.toLowerCase())) {
        return false;
      }
      if (filterRisk !== 'ALL' && ib.risk !== filterRisk) {
        return false;
      }
      if (filterRegion !== 'ALL' && ib.region !== filterRegion) {
        return false;
      }
      if (filterStatus !== 'ALL' && ib.status !== filterStatus) {
        return false;
      }
      return true;
    });
  }, [enrichedIcebergs, filterId, filterRisk, filterRegion, filterStatus]);

  const selectedIceberg: any = selectedIcebergId 
    ? enrichedIcebergs.find(i => i.id === selectedIcebergId) 
    : undefined;

  const handleSelectRow = (ib: Iceberg) => {
    setSelectedIcebergId(ib.id);
    setMapFocusTarget([ib.latitude, ib.longitude]);
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
      title="ICEBERGS"
      subtitle="Tracked iceberg monitoring and risk assessment"
      actions={
        <div className="flex items-center gap-2 text-xs">
          {/* Horizon Selector */}
          <div className="flex items-center bg-[#081525] rounded-md p-0.5 gap-0.5 border border-white/[0.06]">
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
            <span className="text-slate-300 font-medium">US NIC + BYU</span>
          </div>
        </div>
      }
    >
      <div className="flex flex-col min-h-full bg-[#040911] font-sans pb-12">
        
        {/* ========================================================================= */}
        {/* 1. MAP WORKSPACE & TRACKING VIEW (EXPANDED SPACIOUS VIEWPORT)            */}
        {/* ========================================================================= */}
        <div className="w-full relative flex flex-col">
          
          {/* Top Info Bar */}
          <div className="bg-[#060e18] border-b border-white/[0.04] px-4 sm:px-6 py-2 flex flex-wrap items-center justify-between gap-3 text-xs shrink-0">
            <div className="flex items-center gap-3">
              <span className="text-slate-200 font-semibold flex items-center gap-1.5">
                <Mountain className="w-3.5 h-3.5 text-sky-400" />
                Tracked Iceberg Targets
              </span>
              <span className="text-slate-500 font-mono">|</span>
              <span className="text-slate-400 font-mono text-[11px]">
                {filteredIcebergs.length} of {icebergs.length} Active in View
              </span>
              {usingFallback && <span className="rounded-full border border-amber-300/40 bg-amber-50 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-amber-700">Offline safety catalog</span>}
            </div>

            {selectedIceberg && (
              <div className="flex items-center gap-2 bg-sky-500/10 px-2.5 py-1 rounded-md">
                <span className="text-slate-400 text-xs">Selected:</span>
                <span className="text-sky-300 font-semibold text-xs font-mono">{selectedIceberg.id} ({selectedIceberg.name})</span>
                <button
                  type="button"
                  onClick={() => setSelectedIcebergId(null)}
                  className="text-slate-400 hover:text-slate-200 p-0.5 rounded-md hover:bg-white/10 ml-1 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          <div className="relative w-full h-[580px] lg:h-[650px] bg-[#040911]">
            <PolarMap
              section="icebergs"
              showRoute={true}
              selectedIcebergId={selectedIceberg?.id || null}
              onSelectIceberg={(id) => setSelectedIcebergId(id)}
              activeHorizon={activeHorizonLabel}
              icebergs={filteredIcebergs}
              focusTarget={mapFocusTarget}
              selectedVesselId={selectedVesselId}
              onSelectVessel={(id) => setSelectedVesselId(id)}
              destinationMarker={selectedDestination ? {
                latitude: selectedDestination.latitude,
                longitude: selectedDestination.longitude,
                name: selectedDestination.name
              } : undefined}
              allRoutes={routes}
              activeRouteId={activeRouteId}
              onSelectRoute={(rId) => setActiveRouteId(rId)}
            />

            {/* Selected Iceberg Floating Inspector Card */}
            {selectedIceberg && (
              <div className="absolute top-4 right-4 z-30 max-w-sm w-full bg-[#060e18]/95 backdrop-blur-md border border-white/10 p-4 rounded-lg text-xs space-y-3">
                <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-100 font-bold font-mono text-sm">{selectedIceberg.id}</span>
                    <span className="text-slate-400 text-xs truncate max-w-[130px]">{selectedIceberg.name}</span>
                  </div>
                  <span className={cn(
                    "text-[10px] px-2 py-0.5 rounded-md font-medium",
                    selectedIceberg.risk === 'HIGH' ? "bg-rose-500/15 text-rose-400" :
                    selectedIceberg.risk === 'CAUTION' ? "bg-amber-500/15 text-amber-400" :
                    "bg-emerald-500/15 text-emerald-400"
                  )}>
                    {selectedIceberg.risk} RISK
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2.5 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[11px] mb-0.5">Position</span>
                    <span className="text-slate-200 font-mono">{Math.abs(selectedIceberg.latitude).toFixed(2)}°S, {Math.abs(selectedIceberg.longitude).toFixed(2)}°{selectedIceberg.longitude >= 0 ? 'E' : 'W'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px] mb-0.5">Drift Velocity</span>
                    <span className="text-sky-400 font-semibold font-mono">{selectedIceberg.velocity} kn {selectedIceberg.direction}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px] mb-0.5">Area / Draft</span>
                    <span className="text-slate-200 font-mono">{selectedIceberg.areaKm2} km² · {selectedIceberg.draftEstimate}m</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px] mb-0.5">Corridor Clearance</span>
                    <span className="text-emerald-400 font-semibold font-mono">{selectedIceberg.distanceToRoute}</span>
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 pt-2 border-t border-white/[0.06] flex justify-between">
                  <span>Source: <strong className="text-slate-300 font-normal">{selectedIceberg.sensorSource}</strong></span>
                  <span>Trend: <strong className="text-slate-300 font-normal">{selectedIceberg.movementTrend}</strong></span>
                </div>
              </div>
            )}
          </div>

        </div>

        {/* ========================================================================= */}
        {/* 2. FILTERS BAR: ID, Region, Risk, Status                                 */}
        {/* ========================================================================= */}
        <div className="bg-[#060e18] border-t border-b border-white/[0.04] p-3 text-xs flex flex-wrap items-center justify-between gap-3">
          
          <div className="flex flex-wrap items-center gap-3 flex-1">
            {/* Filter by ID */}
            <div className="relative min-w-[220px] flex-1 max-w-xs">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Filter by target ID or name..."
                value={filterId}
                onChange={(e) => setFilterId(e.target.value)}
                className="w-full bg-[#081525] border border-white/10 rounded-md pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-sky-500/50 transition-colors"
              />
            </div>

            {/* Filter by Region */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-xs">Region:</span>
              <select
                value={filterRegion}
                onChange={(e) => setFilterRegion(e.target.value)}
                className="bg-[#081525] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
              >
                <option value="ALL">All Regions</option>
                <option value="Weddell Sea">Weddell Sea</option>
                <option value="Ross Sea">Ross Sea</option>
                <option value="Prydz Bay / Amery">Prydz Bay / Amery</option>
                <option value="Queen Maud Shelf">Queen Maud Shelf</option>
                <option value="Bellingshausen">Bellingshausen</option>
              </select>
            </div>

            {/* Filter by Risk */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-xs">Risk:</span>
              <select
                value={filterRisk}
                onChange={(e) => setFilterRisk(e.target.value)}
                className="bg-[#081525] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
              >
                <option value="ALL">All Risk Levels</option>
                <option value="HIGH">High</option>
                <option value="CAUTION">Caution</option>
                <option value="LOW">Low</option>
              </select>
            </div>

            {/* Filter by Status */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-xs">Status:</span>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="bg-[#081525] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
              >
                <option value="ALL">All Statuses</option>
                <option value="Moving">Moving</option>
                <option value="Drifting">Drifting</option>
                <option value="Stationary">Stationary</option>
              </select>
            </div>
          </div>

          <div className="text-xs text-slate-400 font-mono">
            Showing <span className="text-slate-200 font-semibold">{filteredIcebergs.length}</span> targets
          </div>

        </div>

        {/* ========================================================================= */}
        {/* 3. CLEAN TABULAR LIST: ID, Lat, Lon, Timestamp, Risk, Distance, Status   */}
        {/* ========================================================================= */}
        <div className="bg-[#060e18] w-full flex flex-col">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[#081424]/80 border-b border-white/[0.04] text-slate-400 text-[11px] uppercase tracking-wider">
                  <th className="py-2.5 px-4 font-semibold">Iceberg ID</th>
                  <th className="py-2.5 px-4 font-semibold">Name / Class</th>
                  <th className="py-2.5 px-4 font-semibold">Latitude</th>
                  <th className="py-2.5 px-4 font-semibold">Longitude</th>
                  <th className="py-2.5 px-4 font-semibold">Observed</th>
                  <th className="py-2.5 px-4 font-semibold">Risk Level</th>
                  <th className="py-2.5 px-4 font-semibold">Distance to Route</th>
                  <th className="py-2.5 px-4 font-semibold">Status</th>
                  <th className="py-2.5 px-4 text-right font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {filteredIcebergs.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-slate-500 text-xs">
                      No icebergs match the specified filters.
                    </td>
                  </tr>
                ) : (
                  filteredIcebergs.map((ib) => {
                    const isSelected = selectedIcebergId === ib.id;
                    return (
                      <tr
                        key={ib.id}
                        onClick={() => handleSelectRow(ib)}
                        className={cn(
                          "cursor-pointer transition-colors",
                          isSelected
                            ? "bg-sky-500/10 text-slate-100 font-medium"
                            : "hover:bg-white/[0.03] text-slate-300"
                        )}
                      >
                        <td className="py-2.5 px-4 text-slate-200 font-bold font-mono flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full inline-block shrink-0"
                            style={{
                              backgroundColor: ib.risk === 'HIGH' ? '#f43f5e' : ib.risk === 'CAUTION' ? '#f59e0b' : '#06b6d4'
                            }}
                          />
                          {ib.id}
                        </td>
                        <td className="py-2.5 px-4 text-slate-300 truncate max-w-[140px]">{ib.name}</td>
                        <td className="py-2.5 px-4 text-slate-400 font-mono text-[11px]">{Math.abs(ib.latitude).toFixed(2)}°S</td>
                        <td className="py-2.5 px-4 text-slate-400 font-mono text-[11px]">{Math.abs(ib.longitude).toFixed(2)}°{ib.longitude >= 0 ? 'E' : 'W'}</td>
                        <td className="py-2.5 px-4 text-slate-400 text-[11px]">{ib.lastObserved || 'Daily 12:00 UTC'}</td>
                        <td className="py-2.5 px-4">
                          <span className={cn(
                            "text-[10px] px-2 py-0.5 rounded-md font-medium",
                            ib.risk === 'HIGH' ? "bg-rose-500/15 text-rose-400" :
                            ib.risk === 'CAUTION' ? "bg-amber-500/15 text-amber-400" :
                            "bg-emerald-500/15 text-emerald-400"
                          )}>
                            {ib.risk}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-sky-400 font-semibold font-mono">{ib.distanceToRoute}</td>
                        <td className="py-2.5 px-4 text-slate-400 text-[11px]">{ib.status}</td>
                        <td className="py-2.5 px-4 text-right">
                          <button
                            type="button"
                            className="text-xs text-sky-400 hover:text-slate-100 px-2.5 py-1 rounded-md bg-white/[0.04] hover:bg-white/[0.08] transition-colors font-medium cursor-pointer"
                          >
                            Focus Target
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-2 bg-[#060e18] border-t border-white/[0.04] text-xs text-slate-400 flex items-center justify-between">
            <span>U.S. National Ice Center (US NIC) + BYU Antarctic Iceberg Database</span>
            <span className="font-mono text-[11px]">Hydrodynamic Drift Model: ERA5 Wind + Currents</span>
          </div>
        </div>

      </div>
    </AppShell>
  );
};

export default IcebergTrackingPage;
