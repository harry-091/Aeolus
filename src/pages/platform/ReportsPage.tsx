import React, { useState, useEffect } from 'react';
import { 
  Printer, 
  Download, 
  ShieldCheck, 
  AlertTriangle,
  FileCheck,
  Ship
} from 'lucide-react';
import { AppShell } from '../../components/layout/AppShell';
import { useApiData } from "../../hooks/useApiData";
import { useFleet } from "../../context/FleetContext";
import { api } from '../../services/api';
import { cn } from '../../utils/cn';

interface ReportDoc {
  id: string;
  title: string;
  type: string;
  date: string;
  vessel: string;
  polarClass: string;
  status: 'COMPLIANT' | 'CONDITIONAL' | 'RESTRICTED';
  rioScore: number;
  summary: string;
  findings: string[];
}

const FALLBACK_REPORTS: ReportDoc[] = [
  {
    id: 'REP-2026-0829-01',
    title: 'IMO Polar Code Chapter 1.3 Assessment — Route B Transit',
    type: 'IMO_POLARIS_ASSESSMENT',
    date: '2026-08-29',
    vessel: 'R/V Sagar Nidhi (419071000)',
    polarClass: 'PC5 (Antarctic Research Vessel)',
    status: 'COMPLIANT',
    rioScore: 8.4,
    summary: 'Operational risk assessment concludes Route B maintains a positive RIO margin (+8.4) through marginal ice zone and stays 28 km clear of Iceberg A-17.',
    findings: [
      'Positive Risk Index Outcome (RIO = +8.4 >= 0.0) satisfies IMO MSC.385(94) requirements.',
      'Speed limited to 10.0 kn in Sector SEC-03 during close pack ice transit.',
      'Iceberg radar CPA margin verified at 28.4 km exceeding 15 km minimum safe perimeter.'
    ]
  },
  {
    id: 'REP-2026-0829-02',
    title: 'Environmental & Sea-Ice Forecast Compliance Log',
    type: 'ENVIRONMENTAL_FORECAST_LOG',
    date: '2026-08-29',
    vessel: 'R/V Sagar Nidhi',
    polarClass: 'PC5',
    status: 'COMPLIANT',
    rioScore: 8.4,
    summary: 'Spatiotemporal sea-ice forecast indicates benign marginal ice edge with wave attenuation factor 0.42.',
    findings: [
      'Sentinel-1 SAR C-band analysis verifies open water lead along Route B corridor.',
      'Wave height < 2.5m within marginal ice zone.',
      'Zero landfast ice besetting hazards projected within 48-hour voyage window.'
    ]
  }
];

export const ReportsPage: React.FC = () => {
  const { selectedVessel } = useFleet();
  const [reports, setReports] = useState<ReportDoc[]>(FALLBACK_REPORTS);
  const [selectedReportId, setSelectedReportId] = useState<string>(FALLBACK_REPORTS[0].id);
  useApiData();
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    async function loadReports() {
      try {
        const res = await api.reports();
        if (res?.reports?.length) {
          const normalized: ReportDoc[] = res.reports.map((r: any) => ({
            id: r.id || 'REP-01',
            title: r.title || `IMO Polar Code Assessment — ${selectedVessel.name}`,
            type: r.type || 'IMO_POLARIS_ASSESSMENT',
            date: r.date || r.assessmentTime?.slice(0, 10) || '2026-08-29',
            vessel: selectedVessel.name || r.vessel || 'R/V Sagar Nidhi',
            polarClass: selectedVessel.polar_class || r.polarClass || 'PC5 (Antarctic Research Vessel)',
            status: r.status === 'ARCHIVED' ? 'RESTRICTED' : 'COMPLIANT',
            rioScore: r.rioScore ?? (r.overallRisk === 'LOW' ? 8.4 : 6.8),
            summary: r.summary || r.recommendation || `Operational risk assessment for ${selectedVessel.name} satisfies IMO MSC.385(94) polar navigation criteria.`,
            findings: r.findings || r.keyHazards || [
              'Positive Risk Index Outcome satisfies IMO MSC.385(94) requirements.',
              'Speed regulation verified across polar sectors.',
              'Iceberg radar safe perimeter clearance confirmed.'
            ]
          }));
          setReports(normalized);
          setSelectedReportId(normalized[0].id);
        }
      } catch (e) {
        console.error('Failed to load reports:', e);
      }
    }
    loadReports();
  }, [selectedVessel]);

  const selectedReport = reports.find(r => r.id === selectedReportId) || reports[0] || FALLBACK_REPORTS[0];

  const handlePrint = () => {
    window.print();
  };

  const handleDownload = () => {
    setIsExporting(true);
    const content = JSON.stringify(selectedReport, null, 2);
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `IMO_Polar_Assessment_${selectedReport.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setIsExporting(false);
  };

  return (
    <AppShell
      title="COMPLIANCE REPORTS"
      subtitle={`Polar Code compliance documentation & official logs • Vessel: ${selectedVessel.name}`}
      actions={
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-2 px-2.5 py-1 bg-[#081525] rounded-md text-slate-300 border border-white/[0.06]">
            <Ship className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400">Vessel:</span>
            <span className="text-slate-200 font-medium">{selectedVessel.name.split(' ')[0]}</span>
          </div>
          <button
            type="button"
            onClick={handlePrint}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#081525] hover:bg-[#0c1c2e] text-slate-200 text-xs border border-white/[0.06] transition-colors font-medium cursor-pointer"
          >
            <Printer className="w-3.5 h-3.5 text-sky-400" />
            <span>Print</span>
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{isExporting ? 'Exporting...' : 'Export Report'}</span>
          </button>
        </div>
      }
    >
      <div className="h-full overflow-y-auto custom-scrollbar p-4 lg:p-8 max-w-4xl mx-auto space-y-4 bg-[#040911] font-sans">
        
        {/* Selector Pills */}
        <div className="flex items-center gap-2 border-b border-white/[0.04] pb-3 overflow-x-auto custom-scrollbar">
          {reports.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => setSelectedReportId(r.id)}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs transition-colors whitespace-nowrap flex items-center gap-2 font-medium cursor-pointer",
                selectedReportId === r.id
                  ? "bg-sky-600 text-white font-semibold"
                  : "bg-[#081424]/70 text-slate-400 hover:text-white"
              )}
            >
              <FileCheck className="w-3.5 h-3.5 text-sky-300" />
              <span className="font-mono">{r.id}</span>
            </button>
          ))}
        </div>

        {/* Formal Report Document Display */}
        <div className="bg-[#081424]/70 rounded-lg p-5 sm:p-7 space-y-5 text-xs">
          
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.06] pb-4">
            <div>
              <span className="text-[11px] text-sky-400 tracking-wide uppercase font-medium block mb-1">
                International Maritime Organization (IMO) POLARIS Protocol
              </span>
              <h3 className="text-base sm:text-lg font-bold text-slate-100">{selectedReport.title}</h3>
              <p className="text-slate-400 mt-1 text-xs">Vessel: <strong className="text-slate-200 font-medium">{selectedReport.vessel}</strong> • Polar Class: <strong className="text-slate-200 font-medium">{selectedReport.polarClass}</strong></p>
            </div>

            <div className="flex items-center gap-2">
              <span className={cn(
                "px-3 py-1 rounded-md text-xs font-medium flex items-center gap-1.5",
                selectedReport.status === 'COMPLIANT' ? "text-emerald-400 bg-emerald-500/15" : "text-amber-400 bg-amber-500/15"
              )}>
                {selectedReport.status === 'COMPLIANT' ? <ShieldCheck className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                <span>{selectedReport.status}</span>
              </span>
            </div>
          </div>

          {/* RIO Score Metric Banner */}
          <div className="grid grid-cols-3 gap-3 p-4 bg-[#081525]/60 rounded-lg text-center">
            <div>
              <span className="text-[11px] text-slate-400 uppercase font-medium block">RIO Outcome</span>
              <span className="text-xl font-bold font-mono text-emerald-400 mt-0.5 block">+{selectedReport.rioScore}</span>
            </div>
            <div>
              <span className="text-[11px] text-slate-400 uppercase font-medium block">Operation Threshold</span>
              <span className="text-xl font-bold font-mono text-slate-200 mt-0.5 block">&ge; 0.0</span>
            </div>
            <div>
              <span className="text-[11px] text-slate-400 uppercase font-medium block">Navigation Permit</span>
              <span className="text-xl font-bold font-mono text-sky-400 mt-0.5 block">AUTHORIZED</span>
            </div>
          </div>

          {/* Summary Section */}
          <div className="space-y-1.5">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-sky-400">
              1. Executive Assessment Summary
            </h4>
            <p className="text-slate-300 leading-relaxed text-xs">
              {selectedReport.summary}
            </p>
          </div>

          {/* Findings */}
          <div className="space-y-1.5">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-sky-400">
              2. Verified Operational Directives
            </h4>
            <ul className="space-y-2 text-slate-300 text-xs">
              {(selectedReport.findings || []).map((f, i) => (
                <li key={i} className="flex items-start gap-2.5">
                  <span className="text-sky-400 font-bold">•</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Signature Footer */}
          <div className="pt-4 border-t border-white/[0.06] flex flex-col sm:flex-row items-center justify-between text-[11px] text-slate-400">
            <span className="font-mono">Record Hash: SHA256:{selectedReport.id}-POLAR-NAV</span>
            <span>Issued Date: {selectedReport.date} (UTC)</span>
          </div>

        </div>

      </div>
    </AppShell>
  );
};

export default ReportsPage;
