import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  AlertTriangle, 
  ShieldAlert, 
  Route as RouteIcon,
  CheckCircle2,
  Ship
} from 'lucide-react';
import { AppShell } from '../../components/layout/AppShell';
import { useApiData } from "../../hooks/useApiData";
import { useFleet } from "../../context/FleetContext";
import { api } from '../../services/api';
import { cn } from '../../utils/cn';

interface AlertItem {
  id: string;
  type: string;
  title: string;
  description: string;
  severity: 'HIGH' | 'CAUTION' | 'RESOLVED' | 'INFO';
  timestamp: string;
  location: string;
  source: string;
  acknowledged: boolean;
  recommendedAction: string;
}

const FALLBACK_ALERTS: AlertItem[] = [
  {
    id: 'ALT-2026-001',
    type: 'ICEBERG_CPA_VIOLATION',
    title: 'Iceberg A-17 Within 15km CPA Threshold',
    description: 'Drift trajectory intersects planned route at WP-03 in 8.4 hours. Current separation: 14.2 km.',
    severity: 'HIGH',
    timestamp: '14:23 UTC',
    location: '67.8°S, 54.2°W',
    source: 'Radar & NIC Satellite Tracking',
    acknowledged: false,
    recommendedAction: 'Execute Route B deviation (+4.4% distance) to maintain 28km safe perimeter.'
  },
  {
    id: 'ALT-2026-002',
    type: 'SEA_ICE_COMPRESSION',
    title: 'Rapid Pack Ice Compaction in Sector SEC-03',
    description: 'Sustained 24 kn NE winds driving first-year floes against coastal fast ice boundary.',
    severity: 'CAUTION',
    timestamp: '12:05 UTC',
    location: '69.5°S, 14.0°E',
    source: 'Sentinel-1 SAR + ERA5 Wind Stress',
    acknowledged: false,
    recommendedAction: 'Reduce vessel transit speed to 8.5 kn. Engage Polar Class PC5 power boost.'
  }
];

export const AlertsPage: React.FC = () => {
  const { selectedVessel } = useFleet();
  const [filterSeverity, setFilterSeverity] = useState<string>('ALL');
  const [alerts, setAlerts] = useState<AlertItem[]>(FALLBACK_ALERTS);
  useApiData();

  useEffect(() => {
    async function loadAlerts() {
      try {
        const res = await api.alerts();
        if (res?.alerts?.length) {
          const normalized = res.alerts.map((a: any) => ({
            id: a.id || 'ALT-001',
            type: a.type || a.category || 'HAZARD',
            title: a.title || 'Navigation Alert',
            description: a.description || '',
            severity: a.severity || 'CAUTION',
            timestamp: a.timeRelative || (a.timestamp ? a.timestamp.slice(11, 16) + ' UTC' : 'Recent'),
            location: a.location || 'Current Sector',
            source: a.source || 'Polar Radar & Satellite Sensor Fusion',
            acknowledged: Boolean(a.acknowledged),
            recommendedAction: a.recommendedAction || a.mitigation || 'Maintain active radar watch and adjust heading as necessary.'
          }));
          setAlerts(normalized);
        }
      } catch (e) {
        console.error('Failed to load alerts:', e);
      }
    }
    loadAlerts();
  }, []);

  const toggleAcknowledge = (id: string) => {
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: !a.acknowledged } : a));
  };

  const filteredAlerts = alerts.filter(a => {
    if (filterSeverity === 'ALL') return true;
    if (filterSeverity === 'ACTIVE') return !a.acknowledged && a.severity !== 'RESOLVED';
    return a.severity === filterSeverity;
  });

  const activeCriticalCount = alerts.filter(a => !a.acknowledged && (a.severity === 'HIGH' || a.severity === 'CAUTION')).length;

  return (
    <AppShell
      title="TACTICAL ALERTS"
      subtitle={`Real-time proximity warnings & incident mitigation • Fleet context: ${selectedVessel.name}`}
      actions={
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-2 px-2.5 py-1 bg-[#081525] rounded-md text-slate-300 border border-white/[0.06]">
            <Ship className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400">Vessel:</span>
            <span className="text-slate-200 font-medium">{selectedVessel.name.split(' ')[0]}</span>
          </div>
          <div className="flex items-center gap-2 px-2.5 py-1 bg-[#081525] rounded-md border border-white/[0.06]">
            <span className="text-slate-400">Status:</span>
            <span className={cn("font-medium", activeCriticalCount > 0 ? "text-rose-400" : "text-emerald-400")}>
              {activeCriticalCount > 0 ? `${activeCriticalCount} Active Threats` : "All Hazards Mitigated"}
            </span>
          </div>
        </div>
      }
    >
      <div className="h-full overflow-y-auto custom-scrollbar p-4 lg:p-6 max-w-5xl mx-auto space-y-4 bg-[#040911] font-sans">
        
        {/* Top Header & Filter Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.04] pb-3">
          <div>
            <h3 className="font-semibold text-sm text-slate-200 tracking-wide">Active Navigation Hazards</h3>
            <p className="text-xs text-slate-400 mt-0.5">{activeCriticalCount > 0 ? `${activeCriticalCount} unacknowledged — immediate attention required` : 'All hazards acknowledged or resolved'}</p>
          </div>

          <div className="flex items-center gap-1 text-xs bg-[#081525] p-0.5 rounded-md border border-white/[0.06]">
            {(['ALL', 'ACTIVE', 'HIGH', 'CAUTION', 'RESOLVED'] as const).map((sev) => (
              <button
                key={sev}
                type="button"
                onClick={() => setFilterSeverity(sev)}
                className={cn(
                  "px-2.5 py-1 rounded-sm text-xs font-medium transition-colors uppercase cursor-pointer",
                  filterSeverity === sev
                    ? "bg-sky-600 text-white font-semibold"
                    : "text-slate-400 hover:text-white"
                )}
              >
                {sev}
              </button>
            ))}
          </div>
        </div>

        {/* Alert Cards */}
        <div className="space-y-3">
          {filteredAlerts.map((alert) => {
            const isHigh = alert.severity === 'HIGH';
            const isCaution = alert.severity === 'CAUTION';

            return (
              <div
                key={alert.id}
                className={cn(
                  "rounded-lg p-4 lg:p-5 space-y-3 transition-colors",
                  alert.acknowledged
                    ? "bg-[#081424]/40 opacity-60"
                    : isHigh
                    ? "bg-[#081424]/80 border-l-2 border-l-rose-500"
                    : isCaution
                    ? "bg-[#081424]/80 border-l-2 border-l-amber-500"
                    : "bg-[#081424]/70"
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div className={cn(
                      "p-2 rounded-md mt-0.5",
                      isHigh ? "bg-rose-500/15 text-rose-400" : isCaution ? "bg-amber-500/15 text-amber-400" : "bg-sky-500/15 text-sky-400"
                    )}>
                      {isHigh ? <ShieldAlert className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400 font-mono">{alert.id}</span>
                        <span className={cn(
                          "px-2 py-0.5 rounded-md text-[10px] font-medium",
                          isHigh ? "text-rose-400 bg-rose-500/15" : isCaution ? "text-amber-400 bg-amber-500/15" : "text-emerald-400 bg-emerald-500/15"
                        )}>
                          {alert.severity}
                        </span>
                        {alert.acknowledged && (
                          <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Acknowledged
                          </span>
                        )}
                      </div>
                      <h4 className="font-semibold text-sm text-slate-100 mt-1">{alert.title}</h4>
                      <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">{alert.description}</p>
                    </div>
                  </div>

                  <span className="text-xs text-slate-400 font-mono shrink-0">{alert.timestamp}</span>
                </div>

                <div className="bg-[#081525]/60 p-3 rounded-md flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div className="space-y-0.5">
                    <div className="text-slate-400 text-[11px] font-medium uppercase tracking-wide">Recommended Mitigation</div>
                    <div className="text-sky-400 text-xs">{alert.recommendedAction}</div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => toggleAcknowledge(alert.id)}
                      className="px-3 py-1.5 rounded-md bg-white/[0.04] text-slate-300 hover:text-slate-100 hover:bg-white/[0.08] transition-colors text-xs font-medium cursor-pointer"
                    >
                      {alert.acknowledged ? "Unmark" : "Acknowledge"}
                    </button>
                    <Link
                      to="/navigation"
                      className="flex items-center gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-medium px-3.5 py-1.5 rounded-md text-xs transition-colors cursor-pointer"
                    >
                      <RouteIcon className="w-3.5 h-3.5" />
                      <span>Mitigate Route</span>
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

      </div>
    </AppShell>
  );
};

export default AlertsPage;
