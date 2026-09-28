import React from 'react';
import { AlertTriangle, AlertCircle, RefreshCw, Database } from 'lucide-react';
import { cn } from '../../utils/cn';

interface StateNoticeProps {
  type: 'UNAVAILABLE' | 'STALE' | 'ERROR' | 'LOADING' | 'EMPTY';
  title?: string;
  source?: string;
  reason?: string;
  timestamp?: string;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

/**
 * Standardized loading, unavailable, stale, and error state notice.
 * Never displays blank cards or fabricated numbers when data is absent.
 */
export const StateNotice: React.FC<StateNoticeProps> = ({
  type,
  title,
  source,
  reason,
  timestamp,
  actionText,
  onAction,
  className,
}) => {
  const configs = {
    UNAVAILABLE: {
      icon: Database,
      iconColor: 'text-slate-400',
      borderColor: 'border-slate-800',
      bgColor: 'bg-slate-950/40',
      defaultTitle: 'DATA UNAVAILABLE',
      textColor: 'text-slate-300',
    },
    STALE: {
      icon: AlertTriangle,
      iconColor: 'text-amber-400',
      borderColor: 'border-amber-900/40',
      bgColor: 'bg-amber-950/20',
      defaultTitle: 'DATA STALE',
      textColor: 'text-amber-200',
    },
    ERROR: {
      icon: AlertCircle,
      iconColor: 'text-rose-400',
      borderColor: 'border-rose-900/40',
      bgColor: 'bg-rose-950/20',
      defaultTitle: 'DATA ERROR',
      textColor: 'text-rose-200',
    },
    LOADING: {
      icon: RefreshCw,
      iconColor: 'text-cyan-400 animate-spin',
      borderColor: 'border-cyan-900/30',
      bgColor: 'bg-cyan-950/10',
      defaultTitle: 'INITIALIZING DATA FEED',
      textColor: 'text-cyan-200',
    },
    EMPTY: {
      icon: Database,
      iconColor: 'text-slate-500',
      borderColor: 'border-slate-800/60',
      bgColor: 'bg-slate-950/30',
      defaultTitle: 'NO ACTIVE RECORDS',
      textColor: 'text-slate-400',
    },
  }[type];

  const Icon = configs.icon;

  return (
    <div
      className={cn(
        'p-4 rounded border font-mono text-xs flex flex-col items-center justify-center text-center space-y-2',
        configs.bgColor,
        configs.borderColor,
        className
      )}
    >
      <Icon className={cn('w-5 h-5', configs.iconColor)} />
      <div className={cn('font-bold tracking-wider text-[11px] uppercase', configs.textColor)}>
        {title || configs.defaultTitle}
      </div>

      {(source || reason || timestamp) && (
        <div className="text-[10px] text-slate-400 space-y-0.5 max-w-sm">
          {source && (
            <div>
              <span className="text-slate-500 font-semibold">Source: </span>
              <span className="text-slate-300">{source}</span>
            </div>
          )}
          {reason && (
            <div>
              <span className="text-slate-500 font-semibold">Reason: </span>
              <span className="text-slate-300">{reason}</span>
            </div>
          )}
          {timestamp && (
            <div>
              <span className="text-slate-500 font-semibold">Last Update: </span>
              <span className="text-slate-300">{timestamp}</span>
            </div>
          )}
        </div>
      )}

      {actionText && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-2 px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-semibold rounded border border-slate-700 transition-colors"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};

export default StateNotice;
