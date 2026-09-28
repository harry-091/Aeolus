import React from 'react';
import { Link } from 'react-router-dom';
import { 
  ShieldAlert, ShieldCheck, AlertTriangle, 
  RotateCcw, X, Mountain, ExternalLink
} from 'lucide-react';
import { useFleet } from '../context/FleetContext';
import { cn } from '../utils/cn';

export const TacticalHazardBanner: React.FC<{ className?: string }> = ({ className }) => {
  const { 
    tacticalAlert, 
    dismissTacticalAlert, 
    setSelectedIcebergId
  } = useFleet();

  if (!tacticalAlert.active) return null;

  const isDetecting = tacticalAlert.phase === 'detecting';
  const hazId = tacticalAlert.icebergId || 'IB-A84';

  const handleInspect = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (hazId) {
      setSelectedIcebergId(hazId);
    }
  };

  const handleRestore = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dismissTacticalAlert();
  };

  const handleDismiss = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dismissTacticalAlert();
  };

  return (
    <div 
      role="alert"
      aria-label="Tactical Iceberg Alert"
      className={cn(
        "z-50 pointer-events-auto transition-all duration-300",
        className
      )}
    >
      <div
        className={cn(
          "bg-[#071322] rounded-md border px-3.5 py-2 shadow-lg font-sans text-xs flex flex-wrap items-center justify-between gap-3",
          isDetecting
            ? "border-amber-600/60 text-slate-100"
            : "border-emerald-600/60 text-slate-100"
        )}
      >
        {/* Left: Status Badge & Concise Telemetry */}
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className={cn(
              "w-5 h-5 rounded border flex items-center justify-center shrink-0",
              isDetecting
                ? "bg-amber-950/40 border-amber-600/60 text-amber-400"
                : "bg-emerald-950/40 border-emerald-600/60 text-emerald-400"
            )}
          >
            {isDetecting ? (
              <AlertTriangle className="w-3.5 h-3.5" />
            ) : (
              <ShieldCheck className="w-3.5 h-3.5" />
            )}
          </div>

          <div className="min-w-0 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
            <span
              className={cn(
                "px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wider border",
                isDetecting
                  ? "bg-amber-950/50 border-amber-600/50 text-amber-300"
                  : "bg-emerald-950/50 border-emerald-600/50 text-emerald-300"
              )}
            >
              {isDetecting ? "DETECTING HAZARD" : "TACTICAL BYPASS"}
            </span>

            <span className="text-slate-100 font-semibold truncate">
              {hazId}
            </span>

            <span className="text-slate-500 text-[11px] hidden sm:inline">
              •
            </span>

            <span className="text-slate-300 text-xs font-medium">
              {tacticalAlert.headingChange || "+12° Starboard"} ({tacticalAlert.clearanceKm || 26.4} km CPA)
            </span>

            {tacticalAlert.extraDistKm && (
              <span className="text-amber-400 text-xs font-mono hidden md:inline">
                (+{tacticalAlert.extraDistKm} km)
              </span>
            )}
          </div>
        </div>

        {/* Right: Functional Action Controls */}
        <div className="flex items-center gap-2 shrink-0 ml-auto font-sans">
          {/* Inspect Iceberg on map */}
          <button
            type="button"
            onClick={handleInspect}
            className="px-2.5 py-1 rounded bg-[#050e18] hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 cursor-pointer transition-colors"
            title="Focus and inspect this iceberg on the polar map"
          >
            <Mountain className="w-3 h-3 text-sky-400" />
            <span>Inspect</span>
          </button>

          {/* View in Alerts Section */}
          <Link
            to="/alerts"
            className="px-2.5 py-1 rounded bg-[#050e18] hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 cursor-pointer transition-colors"
            title="Open incident registry in Alerts page"
          >
            <ShieldAlert className="w-3 h-3 text-amber-400" />
            <span>Alerts</span>
            <ExternalLink className="w-2.5 h-2.5 ml-0.5 opacity-70" />
          </Link>

          {/* Restore Nominal Route */}
          <button
            type="button"
            onClick={handleRestore}
            className="px-2.5 py-1 rounded bg-[#050e18] hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1.5 cursor-pointer transition-colors"
            title="Revert diversion and restore nominal transit corridor"
          >
            <RotateCcw className="w-3 h-3 text-amber-400" />
            <span>Restore</span>
          </button>

          {/* Close / Dismiss */}
          <button
            type="button"
            onClick={handleDismiss}
            className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 cursor-pointer transition-colors ml-0.5"
            title="Dismiss Alert"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
