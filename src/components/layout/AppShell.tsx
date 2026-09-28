import React, { useState, useEffect } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import {
  Anchor,
  LayoutGrid,
  Compass,
  Snowflake,
  Target,
  Route as RouteIcon,
  Layers,
  ChevronDown,
  Menu,
  X,
  Clock,
  Bell,
  Radio,
  FileText,
  Activity,
  Crosshair
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { api } from '../../services/api';

interface AppShellProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

const PRIMARY_NAV = [
  { id: 'overview', path: '/overview', icon: LayoutGrid, label: 'Overview' },
  { id: 'navigation', path: '/navigation', icon: Compass, label: 'Navigation' },
  { id: 'sea-ice', path: '/sea-ice', icon: Snowflake, label: 'Sea-Ice' },
  { id: 'icebergs', path: '/icebergs', icon: Target, label: 'Icebergs' },
  { id: 'routes', path: '/routes', icon: RouteIcon, label: 'Routes' },
  { id: 'operations', path: '/operations', icon: Crosshair, label: 'Ops Console' },
];

const SECONDARY_NAV = [
  { id: 'intelligence', path: '/intelligence', icon: Layers, label: 'Model Intelligence', desc: 'Decision explanations & benchmarks' },
  { id: 'analysis', path: '/analysis', icon: Activity, label: 'Risk & POLARIS', desc: 'IMO Polar Code safety index' },
  { id: 'alerts', path: '/alerts', icon: Bell, label: 'Active Alerts', desc: 'Tactical warning logs' },
  { id: 'reports', path: '/reports', icon: FileText, label: 'Compliance Reports', desc: 'IMO voyage plans & documentation' },
  { id: 'live-data', path: '/live-data', icon: Radio, label: 'Live Data', desc: 'Provider status & API feeds' },
];

export const AppShell: React.FC<AppShellProps> = ({
  children,
  title,
  subtitle,
  actions,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [intelDropdownOpen, setIntelDropdownOpen] = useState(false);
  const [provenanceModalOpen, setProvenanceModalOpen] = useState(false);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [utcTime, setUtcTime] = useState('');
  const [activeAlertsCount, setActiveAlertsCount] = useState(2);
  const location = useLocation();

  const isIntelActive = ['/intelligence', '/analysis', '/alerts', '/reports', '/historical-validation', '/live-data'].some(p => location.pathname.startsWith(p));

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const h = String(now.getUTCHours()).padStart(2, '0');
      const m = String(now.getUTCMinutes()).padStart(2, '0');
      const s = String(now.getUTCSeconds()).padStart(2, '0');
      setUtcTime(`${h}:${m}:${s} UTC`);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);

    // Fetch live alerts count
    api.alerts().then((res) => {
      if (res?.alerts) {
        const count = res.alerts.filter(
          (a: any) => !a.acknowledged && (a.severity === 'HIGH' || a.severity === 'CRITICAL' || a.severity === 'CAUTION')
        ).length;
        setActiveAlertsCount(count);
      }
    }).catch(() => {});

    // Fetch real-time health from backend safely via API client
    api.realtimeHealth()
      .then((data) => {
        if (data) setSystemHealth(data);
      })
      .catch(() => {});

    return () => clearInterval(interval);
  }, []);

  const isSystemHealthy = systemHealth ? (systemHealth?.overall_status === 'ONLINE' || systemHealth?.startup_ready) : true;

  return (
    <div className="aeolus-platform flex flex-col h-screen bg-[#edf8ff] text-[#083b66] font-sans overflow-hidden select-none">
      
      {/* ========================================================================= */}
      {/* 1. CLEAN MODERN MARITIME NAVBAR                                          */}
      {/* ========================================================================= */}
      <header className="h-16 bg-white border-b border-[#d8ebf7] flex items-center justify-between px-4 sm:px-6 z-40 shrink-0 font-sans text-xs shadow-[0_5px_20px_rgba(18,112,158,.08)]">
        
        {/* LEFT: Brand + Clean Primary Horizontal Navigation */}
        <div className="flex items-center gap-6 lg:gap-8">
          <Link
            to="/"
            className="flex items-center gap-2.5 group transition-opacity hover:opacity-90"
            title="Return to Aeolus decision workspace"
          >
            <div className="w-8 h-8 rounded-xl bg-[#075a9c] flex items-center justify-center text-white">
              <Anchor className="w-3.5 h-3.5" />
            </div>
            <span className="font-bold tracking-wider text-sm text-[#075a9c] font-sans uppercase">
              AEOLUS
            </span>
          </Link>

          {/* DESKTOP HORIZONTAL MENU */}
          <nav className="hidden md:flex items-center gap-1">
            {PRIMARY_NAV.map((item) => (
              <NavLink
                key={item.id}
                to={item.path}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                    isActive
                      ? "bg-[#e8f6ff] text-[#075a9c] font-semibold"
                      : "text-[#5e87a5] hover:text-[#075a9c] hover:bg-[#f2faff]"
                  )
                }
              >
                <item.icon className="w-3.5 h-3.5 opacity-80" />
                <span>{item.label}</span>
              </NavLink>
            ))}

            {/* Intelligence & Logs Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setIntelDropdownOpen(!intelDropdownOpen)}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  isIntelActive || intelDropdownOpen
                    ? "bg-[#e8f6ff] text-[#075a9c] font-semibold"
                    : "text-[#5e87a5] hover:text-[#075a9c] hover:bg-[#f2faff]"
                )}
              >
                <Layers className="w-3.5 h-3.5 opacity-80" />
                <span>Intelligence &amp; Logs</span>
                <ChevronDown className={cn("w-3 h-3 transition-transform opacity-60", intelDropdownOpen && "rotate-180")} />
              </button>

              {intelDropdownOpen && (
                <div 
                  className="absolute left-0 mt-1.5 w-60 bg-[#081424] border border-white/10 rounded-md py-1.5 z-50 font-sans"
                  onMouseLeave={() => setIntelDropdownOpen(false)}
                >
                  <div className="px-3.5 py-1 text-[10px] text-slate-400 uppercase font-semibold tracking-wider">
                    Operational Intelligence
                  </div>
                  {SECONDARY_NAV.map((item) => (
                    <NavLink
                      key={item.id}
                      to={item.path}
                      onClick={() => setIntelDropdownOpen(false)}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center justify-between px-3.5 py-2 text-xs transition-colors hover:bg-white/[0.04]",
                          isActive ? "text-sky-300 font-medium bg-white/[0.06]" : "text-slate-300"
                        )
                      }
                    >
                      <div className="flex items-center gap-2.5">
                        <item.icon className="w-3.5 h-3.5 text-slate-400" />
                        <span>{item.label}</span>
                      </div>
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          </nav>
        </div>

        {/* RIGHT: Status, UTC Clock, Alerts, Mobile Menu Toggle */}
        <div className="flex items-center gap-3 sm:gap-4">
          
          {/* SYSTEM HEALTH */}
          <button
            type="button"
            onClick={() => setProvenanceModalOpen(true)}
            className="flex items-center gap-2 px-2.5 py-1 rounded-md text-slate-300 hover:text-white transition-colors cursor-pointer"
            title="System Provider & Sensor Health Audit"
          >
            <span className={cn('w-2 h-2 rounded-full', isSystemHealthy ? 'bg-emerald-400' : 'bg-amber-400')} />
            <span className="text-xs font-medium text-slate-300">
              {isSystemHealthy ? 'Online' : 'Degraded'}
            </span>
          </button>

          {/* UTC CLOCK */}
          <div className="hidden sm:flex items-center gap-1.5 text-slate-400 text-xs font-mono">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-300 font-medium">
              {utcTime || 'UTC --:--:--'}
            </span>
          </div>

          {/* ACTIVE ALERTS */}
          <Link
            to="/alerts"
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer',
              activeAlertsCount > 0
                ? 'bg-amber-950/40 text-amber-300 hover:bg-amber-900/50'
                : 'text-slate-400 hover:text-slate-200'
            )}
            title="Active Operational Warnings"
          >
            <Bell className={cn('w-3.5 h-3.5', activeAlertsCount > 0 ? 'text-amber-400' : 'text-slate-400')} />
            <span className="font-sans">
              {activeAlertsCount > 0 ? `${activeAlertsCount} Alerts` : 'Alerts'}
            </span>
          </Link>

          {/* MOBILE TOGGLE */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-1.5 rounded-md text-slate-300 hover:text-white hover:bg-white/[0.04]"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </header>


      {/* MOBILE DROPDOWN MENU */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-[#060e18] border-b border-white/[0.04] p-2.5 space-y-1 z-50 font-sans text-xs">
          {PRIMARY_NAV.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-md",
                  isActive ? "bg-white/[0.08] text-sky-300 font-semibold" : "text-slate-300 hover:text-white"
                )
              }
            >
              <item.icon className="w-4 h-4" />
              <span>{item.label}</span>
            </NavLink>
          ))}
          <div className="pt-2 border-t border-white/[0.04] text-[10px] text-slate-500 px-3 uppercase font-bold">
            Intelligence Modules
          </div>
          {SECONDARY_NAV.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-md",
                  isActive ? "bg-white/[0.08] text-sky-300 font-semibold" : "text-slate-300 hover:text-white"
                )
              }
            >
              <item.icon className="w-4 h-4" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
      )}


      {/* ========================================================================= */}
      {/* 2. STANDARDIZED PAGE HEADER BAR (If title is provided)                    */}
      {/* ========================================================================= */}
      {title && (
        <div className="h-10 bg-[#f8faf7] border-b border-[#183d59]/10 px-3 sm:px-4 flex items-center justify-between shrink-0 font-sans text-xs z-30">
          <div className="flex items-center gap-3 truncate">
            <h1 className="text-xs font-bold uppercase tracking-wider text-[#183d59] shrink-0">
              {title}
            </h1>
            {subtitle && (
              <>
                <span className="text-slate-600 hidden sm:inline">•</span>
                <span className="text-slate-400 text-[11px] truncate hidden sm:inline font-sans">
                  {subtitle}
                </span>
              </>
            )}
          </div>

          {actions && (
            <div className="flex items-center gap-2 shrink-0">
              {actions}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. MAIN APPLICATION WORKSPACE CONTENT                                    */}
      {/* ========================================================================= */}
      <main className="flex-1 overflow-y-auto relative">
        {children}
      </main>

      {/* DATA AUDIT & PROVENANCE MODAL */}
      {provenanceModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 font-sans">
          <div className="bg-[#081424] border border-white/10 rounded-lg max-w-lg w-full p-4 space-y-3 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
              <span className="font-bold text-slate-100 flex items-center gap-1.5">
                <Radio className="w-4 h-4 text-sky-400" />
                SYSTEM &amp; SENSOR DATA AUDIT
              </span>
              <button
                type="button"
                onClick={() => setProvenanceModalOpen(false)}
                className="text-slate-400 hover:text-white p-0.5 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1.5 text-[11px] text-slate-300">
              <div className="flex items-center justify-between p-2 bg-[#060e18] rounded-md">
                <span className="text-slate-400">Tracked Icebergs</span>
                <span className="text-slate-200 font-bold">85 Records (BYU MERS / US NIC)</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#060e18] rounded-md">
                <span className="text-slate-400">Sea Ice Concentration</span>
                <span className="text-slate-200 font-bold">NOAA CoastWatch CDR V4 AMSR2</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#060e18] rounded-md">
                <span className="text-slate-400">Radar Imagery</span>
                <span className="text-slate-200 font-bold">ESA Sentinel-1 SAR C-Band</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#060e18] rounded-md">
                <span className="text-slate-400">Marine Meteorological</span>
                <span className="text-slate-200 font-bold">ECMWF ERA5 / CMEMS</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#060e18] rounded-md">
                <span className="text-slate-400">Polar Code Compliance</span>
                <span className="text-slate-200 font-bold">IMO POLARIS Res. MSC.385(94)</span>
              </div>
            </div>

            <div className="pt-2 border-t border-white/[0.06] flex justify-end">
              <button
                type="button"
                onClick={() => setProvenanceModalOpen(false)}
                className="px-3 py-1 bg-white/[0.06] hover:bg-white/[0.1] text-slate-200 rounded-md text-xs cursor-pointer font-semibold"
              >
                Close Audit
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default AppShell;
