import React, { useState, useEffect } from 'react';
import { Ship, Wind, Waves, Thermometer, Eye, Target } from 'lucide-react';
import { getData, subscribeData } from '../data/dataService';

interface IntelligencePanelProps {
  selectedIcebergId: string | null;
}

const IntelligencePanel: React.FC<IntelligencePanelProps> = ({ selectedIcebergId }) => {
  const [data, setData] = useState(getData());

  useEffect(() => {
    return subscribeData(() => setData({ ...getData() }));
  }, []);

  const activeVessel = data.vessels[0] || {
    name: 'R/V Polarstern',
    latitude: -69.2,
    longitude: -8.3,
    heading: 210,
    speed: 14.5,
    eta: '18h 40m'
  };

  const selectedIceberg = selectedIcebergId 
    ? data.icebergs.find(i => i.id === selectedIcebergId) 
    : null;

  const env = data.environmental || {
    seaIceConcentration: 64,
    windSpeed: 18,
    windDirection: 'NE',
    oceanCurrent: 0.22,
    visibility: 14,
    seaIceRiskScore: 78,
    icebergRiskScore: 41,
    weatherRiskScore: 28
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto custom-scrollbar bg-[#06111e] text-slate-200 font-mono">
      {/* Vessel Header */}
      <div className="p-3.5 border-b border-slate-800">
         <div className="flex items-center gap-2.5 mb-3">
            <div className="w-8 h-8 rounded-xs bg-[#081524] border border-slate-800 flex items-center justify-center">
              <Ship className="w-4 h-4 text-sky-400" />
            </div>
            <div>
              <div className="text-[10px] tracking-wider text-slate-400">ACTIVE POLAR VESSEL</div>
              <div className="font-semibold text-xs text-slate-100">{activeVessel.name}</div>
            </div>
         </div>
         
         <div className="grid grid-cols-2 gap-3 text-xs">
           <div>
             <span className="text-slate-400 block text-[10px] uppercase">POSITION</span>
             <span>{Math.abs(activeVessel.latitude).toFixed(2)}° {activeVessel.latitude < 0 ? 'S' : 'N'}</span><br/>
             <span>{Math.abs(activeVessel.longitude).toFixed(2)}° {activeVessel.longitude < 0 ? 'W' : 'E'}</span>
           </div>
           <div>
             <span className="text-slate-400 block text-[10px] uppercase">HEADING &amp; SPEED</span>
             <span>{(activeVessel.heading || 0).toString().padStart(3, '0')}° / {activeVessel.speed} kn</span>
             <span className="block mt-1 text-slate-400 text-[10px]">ETA: {activeVessel.eta || '18h 40m'}</span>
           </div>
         </div>
      </div>

      {/* Selected Iceberg Context (if any) */}
      {selectedIceberg && (
        <div className="p-3.5 border-b border-slate-800 bg-[#081524]">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-semibold text-slate-200 flex items-center gap-1.5 text-xs">
              <Target className="w-3.5 h-3.5 text-red-400" />
              ICEBERG {selectedIceberg.id}
            </h3>
            <span className="text-[9px] bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded-xs border border-red-500/30 font-semibold">
              {selectedIceberg.risk} RISK
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-slate-800 pb-1.5">
              <span className="text-slate-400">Velocity / Dir</span>
              <span>{selectedIceberg.velocity} kn / {selectedIceberg.direction}</span>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-1.5">
              <span className="text-slate-400">Est. Size</span>
              <span>{selectedIceberg.size} km</span>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-1.5">
              <span className="text-slate-400">48H Forecast Disp.</span>
              <span className="text-red-400 font-semibold">+37.1 km</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400 flex items-center gap-1">Prediction Conf.</span>
              <span className="text-sky-400 font-semibold">{selectedIceberg.confidence}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Environmental Conditions */}
      <div className="p-3.5 border-b border-slate-800">
         <h3 className="text-[10px] tracking-wider text-slate-400 uppercase font-semibold mb-2.5">ENVIRONMENTAL CONDITIONS</h3>
         
         <div className="grid grid-cols-2 gap-2">
            <div className="bg-[#081524] border border-slate-800 p-2 rounded-xs">
               <div className="flex items-center gap-1.5 text-slate-400 text-[10px] mb-0.5">
                 <Thermometer className="w-3 h-3 text-sky-400" /> SEA ICE
               </div>
               <div className="text-base font-bold text-slate-100">
                  {env.seaIceConcentration > 100 ? (env.seaIceConcentration / 100).toFixed(1) : Number(env.seaIceConcentration).toFixed(1)}%
                </div>
            </div>
            <div className="bg-[#081524] border border-slate-800 p-2 rounded-xs">
               <div className="flex items-center gap-1.5 text-slate-400 text-[10px] mb-0.5">
                 <Wind className="w-3 h-3 text-amber-400" /> WIND
               </div>
               <div className="text-base font-bold text-slate-100">{env.windSpeed} <span className="text-xs text-slate-400">kn {env.windDirection}</span></div>
            </div>
            <div className="bg-[#081524] border border-slate-800 p-2 rounded-xs">
               <div className="flex items-center gap-1.5 text-slate-400 text-[10px] mb-0.5">
                 <Waves className="w-3 h-3 text-sky-400" /> CURRENT
               </div>
               <div className="text-base font-bold text-slate-100">{env.oceanCurrent} <span className="text-xs text-slate-400">m/s</span></div>
            </div>
            <div className="bg-[#081524] border border-slate-800 p-2 rounded-xs">
               <div className="flex items-center gap-1.5 text-slate-400 text-[10px] mb-0.5">
                 <Eye className="w-3 h-3 text-emerald-400" /> VISIBILITY
               </div>
               <div className="text-base font-bold text-slate-100">{env.visibility} <span className="text-xs text-slate-400">km</span></div>
            </div>
         </div>
      </div>

      {/* Navigation Risk Analysis */}
      <div className="p-3.5 flex-1">
        <div className="flex justify-between items-center mb-3">
          <h3 className="text-[10px] tracking-wider text-slate-400 uppercase font-semibold">NAVIGATION RISK</h3>
          <span className="text-[9px] text-amber-400 font-semibold bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded-xs">
            MODERATE
          </span>
        </div>

        <div className="space-y-3">
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300">Sea Ice</span>
              <span className="text-slate-400">{env.seaIceRiskScore}%</span>
            </div>
            <div className="w-full h-1 bg-[#040B14] rounded-full overflow-hidden border border-slate-800">
               <div className="h-full bg-red-400" style={{ width: `${env.seaIceRiskScore}%` }} />
            </div>
          </div>
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300">Iceberg</span>
              <span className="text-slate-400">{env.icebergRiskScore}%</span>
            </div>
            <div className="w-full h-1 bg-[#040B14] rounded-full overflow-hidden border border-slate-800">
               <div className="h-full bg-amber-400" style={{ width: `${env.icebergRiskScore}%` }} />
            </div>
          </div>
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300">Weather</span>
              <span className="text-slate-400">{env.weatherRiskScore}%</span>
            </div>
            <div className="w-full h-1 bg-[#040B14] rounded-full overflow-hidden border border-slate-800">
               <div className="h-full bg-emerald-400" style={{ width: `${env.weatherRiskScore}%` }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IntelligencePanel;
