import React from 'react';
import { cn } from '../../utils/cn';

export type StandardDataStatus =
  | 'LIVE'
  | 'RECENT'
  | 'CACHED'
  | 'SIMULATED'
  | 'STALE'
  | 'UNAVAILABLE'
  | 'ERROR';

export type ScientificProvenance =
  | 'OBSERVATION'
  | 'MODEL_ANALYSIS'
  | 'REANALYSIS'
  | 'CLIMATOLOGY'
  | 'STATIC_DATABASE'
  | 'SIMULATED';

interface StatusBadgeProps {
  status: StandardDataStatus | string;
  provenance?: ScientificProvenance | string;
  timestamp?: string;
  className?: string;
  size?: 'xs' | 'sm' | 'md';
}

/**
 * Standard Operational Status Badge for Aeolus.
 * Enforces the unified status vocabulary across all pages:
 * LIVE | RECENT | CACHED | SIMULATED | STALE | UNAVAILABLE | ERROR
 */
export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  provenance,
  timestamp,
  className,
  size = 'sm',
}) => {
  const normStatus = (status || 'UNAVAILABLE').toUpperCase().trim();

  let dotColor = 'bg-slate-500';
  let textColor = 'text-slate-400';
  let bgColor = 'bg-slate-800/40';
  let borderColor = 'border-slate-700/50';
  let label = normStatus;
  let symbol = '●';

  switch (normStatus) {
    case 'LIVE':
      dotColor = 'bg-emerald-400';
      textColor = 'text-emerald-300';
      bgColor = 'bg-emerald-500/15';
      borderColor = 'border-emerald-500/30';
      label = 'LIVE';
      symbol = '●';
      break;
    case 'RECENT':
      dotColor = 'bg-cyan-400';
      textColor = 'text-cyan-300';
      bgColor = 'bg-cyan-500/15';
      borderColor = 'border-cyan-500/30';
      label = 'RECENT';
      symbol = '●';
      break;
    case 'CACHED':
      dotColor = 'bg-sky-400';
      textColor = 'text-sky-300';
      bgColor = 'bg-sky-500/15';
      borderColor = 'border-sky-500/30';
      label = 'CACHED';
      symbol = '●';
      break;
    case 'SIMULATED':
    case 'SIMULATION':
      dotColor = 'bg-amber-400';
      textColor = 'text-amber-300';
      bgColor = 'bg-amber-500/15';
      borderColor = 'border-amber-500/30';
      label = 'SIMULATION';
      symbol = '●';
      break;
    case 'STALE':
      dotColor = 'bg-amber-500';
      textColor = 'text-amber-300';
      bgColor = 'bg-amber-500/20';
      borderColor = 'border-amber-500/40';
      label = 'STALE';
      symbol = '⚠';
      break;
    case 'UNAVAILABLE':
    case 'OFFLINE':
      dotColor = 'bg-slate-500';
      textColor = 'text-slate-400';
      bgColor = 'bg-slate-800/40';
      borderColor = 'border-slate-700/30';
      label = 'UNAVAILABLE';
      symbol = '○';
      break;
    case 'ERROR':
    case 'CRITICAL':
      dotColor = 'bg-rose-500';
      textColor = 'text-rose-300';
      bgColor = 'bg-rose-500/20';
      borderColor = 'border-rose-500/40';
      label = 'ERROR';
      symbol = '✕';
      break;
    default:
      label = normStatus;
      break;
  }

  const sizeClasses = {
    xs: 'px-2 py-0.5 text-[10px] gap-1',
    sm: 'px-2.5 py-0.5 text-[11px] gap-1.5',
    md: 'px-3 py-1 text-xs gap-2',
  }[size];

  return (
    <span
      className={cn(
        'inline-flex items-center font-sans font-medium rounded-full border select-none transition-colors',
        sizeClasses,
        bgColor,
        borderColor,
        textColor,
        className
      )}
      title={provenance ? `Provenance: ${provenance}${timestamp ? ` • Updated: ${timestamp}` : ''}` : undefined}
    >
      {symbol === '●' ? (
        <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', dotColor)} />
      ) : (
        <span className="text-[11px] leading-none shrink-0">{symbol}</span>
      )}
      <span>{label}</span>
      {provenance && (
        <span className="text-slate-400 text-[10px] font-normal border-l border-slate-700/60 pl-1.5 ml-0.5">
          {provenance}
        </span>
      )}
    </span>
  );
};

export default StatusBadge;
