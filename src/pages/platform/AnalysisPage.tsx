import React from 'react';
import { 
  Activity, Snowflake, ShieldAlert, Clock, BarChart3, Wind, LineChart as LucideLineChart, Ship
} from 'lucide-react';
import {
  ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar, AreaChart, Area
} from 'recharts';
import { AppShell } from '../../components/layout/AppShell';
import { useApiData } from "../../hooks/useApiData";
import { useTimeData } from "../../hooks/useTimeData";
import { useFleet } from "../../context/FleetContext";
import { cn } from '../../utils/cn';

const FORECAST_TREND_DATA = [
  { horizon: 'Now (T+0)', sic: 64, wind: 23.6, temp: -17.9, overallRisk: 50, rio: 6.8 },
  { horizon: '+6H', sic: 67, wind: 25.1, temp: -16.4, overallRisk: 54, rio: 6.1 },
  { horizon: '+12H', sic: 71, wind: 26.6, temp: -14.9, overallRisk: 58, rio: 5.4 },
  { horizon: '+24H', sic: 76, wind: 28.4, temp: -13.4, overallRisk: 63, rio: 4.2 },
  { horizon: '+48H', sic: 82, wind: 29.9, temp: -11.9, overallRisk: 69, rio: 2.8 },
];

const POLAR_CLASS_RIO = [
  { class: 'PC1 (Heavy Icebreaker)', key: 'PC1', limit: -15, authorized: true, safeSpeed: '14 kn' },
  { class: 'PC2 (Heavy Icebreaker)', key: 'PC2', limit: -12, authorized: true, safeSpeed: '13 kn' },
  { class: 'PC3 (Medium Icebreaker)', key: 'PC3', limit: -10, authorized: true, safeSpeed: '12 kn' },
  { class: 'PC4 (Medium Icebreaker)', key: 'PC4', limit: -5, authorized: true, safeSpeed: '11 kn' },
  { class: 'PC5 (Antarctic Research)', key: 'PC5', limit: 0, authorized: true, safeSpeed: '10 kn' },
  { class: 'PC7 (Light Ice-Strengthened)', key: 'PC7', limit: +5, authorized: true, safeSpeed: '8 kn' },
  { class: 'Non-Ice Strengthened', key: 'Non-Ice', limit: +10, authorized: false, safeSpeed: 'N/A (Open water only)' },
];

export const AnalysisPage: React.FC = () => {
  const {
    fleet,
    selectedVessel,
    selectedVesselId,
    setSelectedVesselId,
    selectedHorizon,
    setSelectedHorizon,
    activeHorizonLabel
  } = useFleet();
  useApiData();
  
  const HORIZON_TO_TIMESTEP: Record<number, string> = {
    0: '0',
    6: '6',
    12: '12',
    24: '24',
    48: '48'
  };
  const apiTimeStep = HORIZON_TO_TIMESTEP[selectedHorizon] || '0';
  const { environmental } = useTimeData(apiTimeStep);

  const env = environmental || {
    seaIceConcentration: 64, windSpeed: 18, windDirection: 'NE', temperature: -17,
    overallRisk: 'MODERATE', seaIceRiskScore: 78, icebergRiskScore: 41, weatherRiskScore: 28,
    overallRiskScore: 50, sst: -1.7, waveHeight: 2.4, visibility: 14,
    timestep: 'Now (T+0h)', dataSource: 'Sentinel-1 SAR + ERA5'
  };

  const overallRisk = env.overallRiskScore || Math.round((env.seaIceRiskScore + env.icebergRiskScore + env.weatherRiskScore) / 3);
  const riskLabel = overallRisk < 30 ? 'LOW' : overallRisk < 60 ? 'MODERATE' : overallRisk < 80 ? 'HIGH' : 'CRITICAL';

  const hazardBreakdown = [
    { hazard: 'Sea Ice Pack', score: env.seaIceRiskScore || 78, fill: '#3AA6C8' },
    { hazard: 'Iceberg Proximity', score: env.icebergRiskScore || 41, fill: '#FF6B5E' },
    { hazard: 'Weather & Swell', score: env.weatherRiskScore || 28, fill: '#F2994A' },
    { hazard: 'Bathymetry Hazard', score: 14, fill: '#27AE60' },
  ];

  const currentPolarKey = selectedVessel.polar_class ? selectedVessel.polar_class.split(' ')[0] : 'PC5';

  return (
    <AppShell
      title="RISK & IMO POLARIS"
      subtitle={`Physics-informed environmental simulation & IMO POLARIS verification — ${env.timestep || 'T+0h'}`}
      actions={
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-2 px-2.5 py-1 bg-[#081525] rounded-md text-slate-300 border border-white/[0.06]">
            <Ship className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400">Vessel:</span>
            <span className="text-slate-200 font-medium">{selectedVessel.name.split(' ')[0]}</span>
          </div>
          <div className="flex items-center gap-2 px-2.5 py-1 bg-[#081525] rounded-md text-slate-300 border border-white/[0.06]">
            <Activity className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400">Data:</span>
            <span className="text-slate-200 font-medium">Sentinel-1 + ERA5</span>
          </div>
        </div>
      }
    >
      <div className="h-full overflow-y-auto custom-scrollbar p-4 lg:p-6 space-y-4 bg-[#040911] font-sans">
        
        {/* Time Step Selector */}
        <div className="bg-[#081424]/70 p-3 rounded-lg flex flex-col sm:flex-row items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-2.5">
            <Clock className="w-4 h-4 text-sky-400" />
            <span className="text-slate-400 text-xs font-medium">Operational Horizon:</span>
            <span className="text-sky-300 font-semibold bg-white/[0.06] px-2.5 py-1 rounded-md font-mono">
              {activeHorizonLabel} ({env.timestep})
            </span>
          </div>
          <div className="flex items-center gap-1 w-full sm:w-auto bg-[#081525] p-0.5 rounded-md border border-white/[0.06]">
            {([
              { hours: 0, label: 'NOW' },
              { hours: 6, label: '+6H' },
              { hours: 12, label: '+12H' },
              { hours: 24, label: '+24H' },
              { hours: 48, label: '+48H' }
            ] as const).map(({ hours, label }) => (
              <button
                key={hours}
                type="button"
                onClick={() => setSelectedHorizon(hours)}
                className={cn(
                  "px-2.5 py-1 rounded-sm text-xs font-medium transition-colors uppercase cursor-pointer",
                  selectedHorizon === hours
                    ? "bg-sky-600 text-white font-semibold"
                    : "text-slate-400 hover:text-white"
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Hero Section */}
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-1.5 p-4 bg-[#081424]/70 rounded-lg">
            <div className="text-xs font-medium text-sky-400 tracking-wide uppercase">
              Hydrodynamic Risk Modeling
            </div>
            <h2 className="text-base sm:text-lg font-bold text-slate-100">
              Southern Ocean Dynamic Risk Surface
            </h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              Unified multi-sensor analysis integrating Sentinel-1 SAR pack ice density, 48-hour hydrodynamic iceberg drift kinematics, and ERA5 atmospheric wind-stress fields.
            </p>
          </div>

          <div className="bg-[#081424]/70 p-4 rounded-lg text-center flex flex-col items-center justify-center">
            <span className="text-slate-400 text-xs font-medium tracking-wide block mb-1">
              Composite Risk Score
            </span>
            <span className={cn(
              "font-bold font-mono text-3xl",
              riskLabel === 'LOW' ? "text-emerald-400" : riskLabel === 'MODERATE' ? "text-amber-400" : "text-rose-400"
            )}>
              {overallRisk} / 100
            </span>
            <span className={cn(
              "text-[10px] font-medium px-2.5 py-0.5 rounded-md mt-2",
              riskLabel === 'LOW' ? "text-emerald-400 bg-emerald-500/15" : riskLabel === 'MODERATE' ? "text-amber-400 bg-amber-500/15" : "text-rose-400 bg-rose-500/15"
            )}>
              {riskLabel} RISK ZONE
            </span>
          </div>
        </div>

        {/* 3 Hazard Factor Cards */}
        <div className="grid md:grid-cols-3 gap-4">
          <div className="bg-[#081424]/70 p-4 rounded-lg space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Snowflake className="w-4 h-4 text-sky-400" />
                <h4 className="font-semibold text-slate-200 text-sm">Sea Ice Pack</h4>
              </div>
              <span className="text-xs font-mono font-bold text-sky-400">
                {env.seaIceConcentration > 100 ? (env.seaIceConcentration / 100).toFixed(1) : Number(env.seaIceConcentration).toFixed(1)}%
              </span>
            </div>
            <div className="w-full h-1.5 bg-[#040911] rounded-full overflow-hidden">
              <div className="h-full bg-sky-400 rounded-full" style={{ width: `${env.seaIceRiskScore || 78}%` }} />
            </div>
            <p className="text-xs text-slate-300 leading-relaxed pt-0.5">
              Close pack ice with moderate compression. Route B corridor reduces ice exposure by 52% compared to direct transit.
            </p>
          </div>

          <div className="bg-[#081424]/70 p-4 rounded-lg space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                <h4 className="font-semibold text-slate-200 text-sm">Iceberg Proximity</h4>
              </div>
              <span className="text-xs font-mono font-bold text-rose-400">{env.icebergRiskScore}%</span>
            </div>
            <div className="w-full h-1.5 bg-[#040911] rounded-full overflow-hidden">
              <div className="h-full bg-rose-400 rounded-full" style={{ width: `${env.icebergRiskScore || 41}%` }} />
            </div>
            <p className="text-xs text-slate-300 leading-relaxed pt-0.5">
              Iceberg A-17 closest point of approach is 14.2 km. Active route corridor maintains a safe +28 km clearance perimeter.
            </p>
          </div>

          <div className="bg-[#081424]/70 p-4 rounded-lg space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wind className="w-4 h-4 text-amber-400" />
                <h4 className="font-semibold text-slate-200 text-sm">Weather & Swell</h4>
              </div>
              <span className="text-xs font-mono font-bold text-amber-400">{env.weatherRiskScore}%</span>
            </div>
            <div className="w-full h-1.5 bg-[#040911] rounded-full overflow-hidden">
              <div className="h-full bg-amber-400 rounded-full" style={{ width: `${env.weatherRiskScore || 28}%` }} />
            </div>
            <p className="text-xs text-slate-300 leading-relaxed pt-0.5">
              Sustained winds {env.windSpeed} kn {env.windDirection} with {env.waveHeight}m swell. Attenuation active in marginal ice.
            </p>
          </div>
        </div>

        {/* Graphical Analytics (Recharts) */}
        <div className="grid lg:grid-cols-2 gap-4">
          {/* Forecast Trend Chart */}
          <div className="bg-[#081424]/70 p-4 rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                <LucideLineChart className="w-4 h-4 text-sky-400" />
                48-Hour Sea Ice & Risk Projection
              </h4>
              <span className="text-xs text-slate-400 font-mono">T+0 to T+48H</span>
            </div>
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={FORECAST_TREND_DATA}>
                  <defs>
                    <linearGradient id="sicGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.25}/>
                      <stop offset="95%" stopColor="#38bdf8" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.25}/>
                      <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="horizon" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip contentStyle={{ background: '#081424', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }} />
                  <Area type="monotone" dataKey="sic" name="Sea Ice %" stroke="#38bdf8" fillOpacity={1} fill="url(#sicGrad)" strokeWidth={2} />
                  <Area type="monotone" dataKey="overallRisk" name="Risk Score" stroke="#f43f5e" fillOpacity={1} fill="url(#riskGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Hazard Breakdown Bar Chart */}
          <div className="bg-[#081424]/70 p-4 rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-sky-400" />
                Multi-Hazard Fusion Weights
              </h4>
              <span className="text-xs text-slate-400">POLARIS RIO</span>
            </div>
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hazardBreakdown} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis type="number" stroke="#64748b" fontSize={11} domain={[0, 100]} />
                  <YAxis type="category" dataKey="hazard" stroke="#64748b" fontSize={11} width={120} />
                  <Tooltip contentStyle={{ background: '#081424', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }} />
                  <Bar dataKey="score" name="Hazard Index" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* IMO POLARIS Reference Matrix */}
        <div className="bg-[#081424]/70 p-4 rounded-lg space-y-3">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
            <div>
              <div className="text-xs font-semibold text-slate-200 tracking-wide">
                IMO POLARIS (Polar Operational Limit Assessment Risk Indexing System)
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Evaluated against active vessel: <span className="text-slate-200 font-medium">{selectedVessel.name}</span> ({selectedVessel.polar_class || 'PC5'})
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Vessel:</span>
              <select
                value={selectedVesselId}
                onChange={(e) => setSelectedVesselId(e.target.value)}
                className="bg-[#081525] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
              >
                {fleet.map(v => (
                  <option key={v.id} value={v.id}>
                    {v.flag} {v.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="text-slate-400 border-b border-white/[0.04] bg-[#060e18] text-[11px] uppercase tracking-wider">
                  <th className="py-2.5 px-4 font-semibold">Vessel Polar Class</th>
                  <th className="py-2.5 px-4 font-semibold">RIO Threshold</th>
                  <th className="py-2.5 px-4 font-semibold">Status for Route B</th>
                  <th className="py-2.5 px-4 font-semibold">Speed Limit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {POLAR_CLASS_RIO.map((row) => {
                  const isActive = currentPolarKey.includes(row.key);
                  return (
                    <tr key={row.class} className={cn("transition-colors", isActive ? "bg-sky-500/10 text-slate-100 font-medium" : "hover:bg-white/[0.03] text-slate-300")}>
                      <td className="py-2.5 px-4 font-semibold text-slate-200 flex items-center gap-2">
                        <span>{row.class}</span>
                        {isActive && (
                          <span className="text-[10px] font-medium text-sky-300 bg-sky-500/20 px-2 py-0.5 rounded-md">
                            Active Vessel
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-4 text-slate-400 font-mono">RIO &ge; {row.limit}</td>
                      <td className="py-2.5 px-4">
                        <span className={cn(
                          "px-2.5 py-0.5 rounded-md text-[10px] font-medium",
                          row.authorized ? "text-emerald-400 bg-emerald-500/15" : "text-rose-400 bg-rose-500/15"
                        )}>
                          {row.authorized ? 'AUTHORIZED' : 'RESTRICTED'}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-sky-400 font-mono">{row.safeSpeed}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </AppShell>
  );
};

export default AnalysisPage;
