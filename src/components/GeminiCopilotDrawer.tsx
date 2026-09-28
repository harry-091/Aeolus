import React, { useState, useEffect } from 'react';
import { 
  X, Sparkles, Send, ShieldCheck, Cpu, CheckCircle2, 
  AlertTriangle, Compass, Shield, Loader2 
} from 'lucide-react';
import { api } from '../services/api';
import { cn } from '../utils/cn';

interface GeminiCopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  decisionContext?: {
    vessel?: {
      name?: string;
      polar_class?: string;
      destination?: string;
      speed?: number;
    };
    route?: {
      id?: string;
      name?: string;
      distance?: number;
      eta?: string;
      fuelConsumption?: string | number;
      rioScore?: number | string;
      sicExposure?: number;
      cpa_km?: number;
      reason?: string;
    };
  };
}

const SAMPLE_QUESTIONS = [
  "Why was Route B selected over Route A?",
  "Explain the IMO POLARIS RIO score and safety margins.",
  "How does this corridor avoid moving icebergs?",
  "Analyze fuel efficiency and voyage endurance tradeoffs."
];

export const GeminiCopilotDrawer: React.FC<GeminiCopilotDrawerProps> = ({
  isOpen,
  onClose,
  decisionContext
}) => {
  const [question, setQuestion] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [statusInfo, setStatusInfo] = useState<{
    status: string;
    active_provider: string;
    gemini_authenticated: boolean;
    model: string;
  } | null>(null);
  const [copilotResponse, setCopilotResponse] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Fetch Copilot API Health on mount
  useEffect(() => {
    if (isOpen) {
      api.copilotStatus()
        .then(res => setStatusInfo(res))
        .catch(() => setStatusInfo(null));
      
      // Auto-fetch explanation for the currently selected route if empty
      if (!copilotResponse) {
        handleSendPrompt("Why was this route selected, how are ice risks mitigated, and what are the key operational tradeoffs?");
      }
    }
  }, [isOpen]);

  const handleSendPrompt = async (promptText?: string) => {
    const activePrompt = promptText || question;
    if (!activePrompt.trim()) return;

    setIsLoading(true);
    setErrorMsg(null);

    const payload = {
      vessel: {
        name: decisionContext?.vessel?.name || 'SA Agulhas II',
        polar_class: decisionContext?.vessel?.polar_class || 'PC5',
        destination: decisionContext?.vessel?.destination || 'Bharati Station (Larsemann Hills)'
      },
      recommended_route: {
        name: decisionContext?.route?.name || 'Route B (Optimal Corridor)',
        distance_km: decisionContext?.route?.distance || 1680,
        eta: decisionContext?.route?.eta || '32h 05m',
        fuel_estimate: decisionContext?.route?.fuelConsumption || '86 MT',
        rio_score: decisionContext?.route?.rioScore ?? '+8.4',
        sea_ice_exposure: decisionContext?.route?.sicExposure ?? 22,
        minimum_cpa_km: decisionContext?.route?.cpa_km ?? 24.5,
        reason: decisionContext?.route?.reason || ''
      }
    };

    try {
      const res = await api.copilot(payload, activePrompt);
      setCopilotResponse(res);
      setQuestion('');
    } catch (err: any) {
      setErrorMsg(err?.message || 'Failed to reach AI Navigation Copilot endpoint.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const isGeminiLive = copilotResponse?.provider === 'gemini';

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[480px] lg:w-[520px] bg-[#06111e] border-l border-slate-800 shadow-2xl flex flex-col text-slate-100 font-mono">
      
      {/* Header */}
      <div className="p-3.5 border-b border-slate-800 bg-[#081524] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-xs bg-[#12283e] border border-[#214972] flex items-center justify-center text-sky-400">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-bold tracking-wider text-slate-200 uppercase">
                AI Navigation Copilot
              </h2>
              <span className="text-[10px] px-1.5 py-0.5 rounded-xs bg-[#040B14] text-sky-300 border border-slate-800 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                {statusInfo?.model || 'gemini-3.6-flash'}
              </span>
            </div>
            <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
              <span>Grounded Maritime Decision Support System</span>
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-slate-100 hover:bg-[#0c1c2e] rounded-xs transition-colors"
          title="Close Copilot"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Decision Context Bar */}
      <div className="px-3.5 py-2 bg-[#040B14] border-b border-slate-800 text-xs grid grid-cols-3 gap-2">
        <div className="truncate">
          <span className="text-[9px] text-slate-400 block uppercase">VESSEL</span>
          <span className="text-slate-200 font-semibold truncate block">
            {decisionContext?.vessel?.name || 'SA Agulhas II'} ({decisionContext?.vessel?.polar_class || 'PC5'})
          </span>
        </div>
        <div className="truncate">
          <span className="text-[9px] text-slate-400 block uppercase">CORRIDOR</span>
          <span className="text-emerald-400 font-semibold truncate block">
            {decisionContext?.route?.name?.split(' - ')[0] || 'Route B (Optimal)'}
          </span>
        </div>
        <div className="truncate text-right">
          <span className="text-[9px] text-slate-400 block uppercase">RIO / SIC</span>
          <span className="text-sky-300 font-semibold block">
            {String(decisionContext?.route?.rioScore ?? '+8.4')} / {decisionContext?.route?.sicExposure ?? 22}%
          </span>
        </div>
      </div>

      {/* Main Conversation & Output Body */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3.5 space-y-3">
        
        {/* Explanation Card */}
        {isLoading ? (
          <div className="p-6 rounded-xs bg-[#081524] border border-slate-800 flex flex-col items-center justify-center text-center space-y-2.5 py-10">
            <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
            <div className="text-xs text-sky-300">
              Synthesizing polar maritime decision...
            </div>
            <p className="text-[10px] text-slate-400 max-w-xs font-sans">
              Evaluating IMO POLARIS RIO boundaries, bathymetry clearance, and iceberg drift kinematic envelope.
            </p>
          </div>
        ) : copilotResponse ? (
          <div className="space-y-3">
            
            {/* Status & Mode Banner */}
            <div className={cn(
              "p-2 rounded-xs border text-xs flex items-center justify-between",
              isGeminiLive
                ? "bg-[#081524] border-sky-500/30 text-sky-300"
                : "bg-[#081524] border-amber-500/30 text-amber-300"
            )}>
              <div className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5" />
                <span className="font-semibold uppercase text-[10px]">
                  {copilotResponse.explanation_mode || 'GEMINI_AI_GROUNDED'}
                </span>
                <span className="text-slate-400 text-[10px]">({copilotResponse.model})</span>
              </div>
              {copilotResponse.latency_ms && (
                <span className="text-[10px] text-slate-400">
                  {copilotResponse.latency_ms} ms
                </span>
              )}
            </div>

            {/* High Level Executive Summary */}
            <div className="p-3.5 rounded-xs bg-[#081524] border border-slate-800">
              <div className="text-[10px] text-sky-400 uppercase tracking-wider mb-1 flex items-center gap-1 font-semibold">
                <Compass className="w-3 h-3" />
                <span>Executive Decision Summary</span>
              </div>
              <p className="text-xs text-slate-200 leading-relaxed font-sans">
                {copilotResponse.summary}
              </p>
            </div>

            {/* Structured Factors / Reasoning */}
            {copilotResponse.key_factors?.length > 0 && (
              <div className="p-3.5 rounded-xs bg-[#081524] border border-slate-800 space-y-2">
                <div className="text-[10px] text-emerald-400 uppercase tracking-wider mb-1 flex items-center gap-1 font-semibold">
                  <Shield className="w-3 h-3" />
                  <span>Key Navigational &amp; Risk Mitigations</span>
                </div>
                <div className="space-y-1.5">
                  {copilotResponse.key_factors.map((factor: string, idx: number) => (
                    <div key={idx} className="text-xs text-slate-300 flex items-start gap-2 bg-[#040B14] p-2 rounded-xs border border-slate-800">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                      <div className="leading-snug font-sans">
                        {factor.replace(/\*\*/g, '')}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Mathematical Decision Grounding */}
            {copilotResponse.decision_basis && (
              <div className="p-2.5 rounded-xs bg-[#040B14] border border-slate-800 text-[10px] text-slate-400 space-y-1">
                <div className="text-slate-300 font-semibold mb-1 uppercase tracking-wider">
                  Grounding Metadata
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  <div>Vessel: <span className="text-slate-200">{copilotResponse.decision_basis.vessel}</span></div>
                  <div>Polar Class: <span className="text-slate-200">{copilotResponse.decision_basis.polar_class}</span></div>
                  <div>Corridor: <span className="text-emerald-400">{copilotResponse.decision_basis.corridor}</span></div>
                  <div>POLARIS RIO: <span className="text-sky-300">{copilotResponse.decision_basis.rio_score}</span></div>
                  <div>Iceberg CPA: <span className="text-sky-300">{copilotResponse.decision_basis.iceberg_cpa_km} km</span></div>
                  <div>Fuel Est: <span className="text-slate-200">{copilotResponse.decision_basis.fuel_estimate}</span></div>
                </div>
              </div>
            )}
          </div>
        ) : null}

        {errorMsg && (
          <div className="p-2.5 rounded-xs bg-red-950/40 border border-red-500/40 text-red-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Quick Sample Prompts */}
        <div className="pt-2">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-1.5 font-semibold">
            Suggested Master Prompts:
          </div>
          <div className="grid grid-cols-1 gap-1">
            {SAMPLE_QUESTIONS.map((q, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSendPrompt(q)}
                disabled={isLoading}
                className="text-left text-xs text-slate-300 bg-[#081524] hover:bg-[#0c1c2e] hover:text-sky-300 p-2 rounded-xs border border-slate-800 transition-colors disabled:opacity-50"
              >
                "{q}"
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Prompt Input Box */}
      <div className="p-3 border-t border-slate-800 bg-[#081524]">
        <div className="relative flex items-center">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendPrompt();
              }
            }}
            placeholder="Ask Copilot regarding route or polar risk factors..."
            rows={2}
            className="w-full bg-[#040B14] border border-slate-800 rounded-xs p-2 pr-10 text-xs text-slate-100 placeholder-slate-500 font-mono focus:outline-none focus:border-slate-600 resize-none"
          />
          <button
            type="button"
            onClick={() => handleSendPrompt()}
            disabled={isLoading || !question.trim()}
            className="absolute right-2 bottom-2.5 p-1.5 bg-[#12283e] hover:bg-[#1a3857] text-sky-300 border border-[#214972] disabled:opacity-40 rounded-xs transition-colors"
            title="Ask Copilot"
          >
            {isLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
        <div className="flex justify-between items-center mt-1 px-0.5 text-[9px] text-slate-500">
          <span>Press Enter to send</span>
          <span>Maritime Gateway Active</span>
        </div>
      </div>
    </div>
  );
};
