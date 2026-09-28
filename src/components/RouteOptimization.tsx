import React, { useState, useEffect } from 'react';
import { X, Network, Cpu, Clock, Navigation } from 'lucide-react';
import { getData, subscribeData } from '../data/dataService';
import { cn } from '../utils/cn';

interface RouteOptimizationProps {
  onClose: () => void;
}

const RouteOptimization: React.FC<RouteOptimizationProps> = ({ onClose }) => {
  const [data, setData] = useState(getData());
  const [selectedRouteId, setSelectedRouteId] = useState<string>(data.routes[0]?.id || 'route-b');

  useEffect(() => {
    return subscribeData(() => {
      const d = getData();
      setData({ ...d });
      if (d.routes.length > 0 && !d.routes.some(r => r.id === selectedRouteId)) {
        setSelectedRouteId(d.routes[0].id);
      }
    });
  }, [selectedRouteId]);

  return (
    <div className="flex flex-col h-full bg-[#06111e] text-slate-200 shadow-2xl relative font-mono text-xs">
      <div className="p-3.5 border-b border-slate-800 flex justify-between items-center bg-[#081524]">
        <h2 className="font-semibold tracking-wider flex items-center gap-2 text-xs uppercase text-slate-200">
          <Network className="w-4 h-4 text-sky-400" />
          ROUTE OPTIMIZATION
        </h2>
        <button onClick={onClose} className="p-1 hover:bg-[#0c1c2e] rounded-xs transition-colors text-slate-400 hover:text-slate-200">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-3.5 bg-[#081524] border-b border-slate-800">
         <div className="flex justify-between items-center mb-1.5">
            <span className="text-[10px] text-slate-400 uppercase">ORIGIN</span>
            <span className="text-xs text-slate-200">{data.vessels[0]?.name || 'Active Polar Vessel'}</span>
         </div>
         <div className="flex justify-between items-center">
            <span className="text-[10px] text-slate-400 uppercase">DESTINATION</span>
            <span className="text-xs text-slate-200">{data.vessels[0]?.destination || 'Antarctic Station'}</span>
         </div>
         
         <div className="mt-2.5 pt-2.5 border-t border-slate-800 flex items-center gap-2">
            <Cpu className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-[10px] text-sky-400 font-semibold uppercase">AI OPTIMIZATION READY</span>
         </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2.5">
        {data.routes.map((route) => {
          const isSelected = selectedRouteId === route.id;
          
          return (
            <div 
              key={route.id}
              onClick={() => setSelectedRouteId(route.id)}
              className={cn(
                "p-3 border rounded-xs cursor-pointer transition-colors space-y-2",
                isSelected 
                  ? "border-sky-500/50 bg-[#0c1c2e]" 
                  : "border-slate-800 bg-[#081524] hover:border-slate-700"
              )}
            >
              <div className="flex justify-between items-center">
                <h3 className="font-semibold text-xs text-slate-200 flex items-center gap-2">
                  {route.name}
                  {route.recommended && (
                    <span className="text-[9px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded-xs border border-emerald-500/30 font-semibold">
                      RECOMMENDED
                    </span>
                  )}
                </h3>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs bg-[#040B14] p-2 rounded-xs border border-slate-800">
                <div>
                  <span className="text-slate-400 block text-[9px] uppercase">DISTANCE</span>
                  <span className="text-slate-200">{route.distance} km</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[9px] uppercase">ESTIMATED TIME</span>
                  <span className="flex items-center gap-1 text-slate-200">
                    <Clock className="w-3 h-3 text-slate-400" />
                    {route.eta}
                  </span>
                </div>
              </div>

              {route.reason && (
                <div className="text-xs text-slate-300 font-sans border-t border-slate-800 pt-1.5 leading-relaxed">
                  {route.reason}
                </div>
              )}

              <div className="space-y-1 pt-1.5 border-t border-slate-800 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-slate-400">Sea Ice Risk</span>
                  <span className={cn(
                    "font-semibold",
                    route.iceRisk === 'LOW' ? "text-emerald-400" :
                    route.iceRisk === 'MODERATE' ? "text-amber-400" : "text-red-400"
                  )}>{route.iceRisk}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Iceberg Risk</span>
                  <span className={cn(
                    "font-semibold",
                    route.icebergRisk === 'LOW' || route.icebergRisk === 'VERY LOW' ? "text-emerald-400" :
                    route.icebergRisk === 'MODERATE' ? "text-amber-400" : "text-red-400"
                  )}>{route.icebergRisk}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Weather Risk</span>
                  <span className={cn(
                    "font-semibold",
                    route.weatherRisk === 'LOW' ? "text-emerald-400" :
                    route.weatherRisk === 'MODERATE' ? "text-amber-400" : "text-red-400"
                  )}>{route.weatherRisk}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="p-3 border-t border-slate-800 bg-[#081524] flex gap-2">
         <button className="flex-1 py-2 px-3 bg-[#12283e] hover:bg-[#1a3857] text-sky-300 border border-[#214972] font-semibold text-xs tracking-wider rounded-xs transition-colors flex items-center justify-center gap-1.5 uppercase cursor-pointer">
           <Navigation className="w-3.5 h-3.5" />
           EXECUTE ROUTE
         </button>
      </div>
    </div>
  );
};

export default RouteOptimization;
