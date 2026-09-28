import { useState } from 'react';
import { 
  Map as MapIcon, Navigation2, ThermometerSnowflake, 
  Target, Route as RouteIcon, CloudRainWind, 
  History, AlertTriangle, FileText, Settings
} from 'lucide-react';
import PolarMap from '../components/map/PolarMap';
import IntelligencePanel from '../components/IntelligencePanel';
import RouteOptimization from '../components/RouteOptimization';
import { cn } from '../utils/cn';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedIcebergId, setSelectedIcebergId] = useState<string | null>(null);
  const [showRouteOptimization, setShowRouteOptimization] = useState(false);
  
  const navItems = [
    { id: 'overview', icon: MapIcon, label: 'Overview' },
    { id: 'navigation', icon: Navigation2, label: 'Navigation' },
    { id: 'sea-ice', icon: ThermometerSnowflake, label: 'Sea-Ice Analysis' },
    { id: 'icebergs', icon: Target, label: 'Iceberg Tracking' },
    { id: 'routes', icon: RouteIcon, label: 'Route Optimization' },
    { id: 'weather', icon: CloudRainWind, label: 'Weather & Ocean' },
    { id: 'history', icon: History, label: 'Historical Data' },
    { id: 'alerts', icon: AlertTriangle, label: 'Alerts' },
    { id: 'reports', icon: FileText, label: 'Reports' },
  ];

  const handleNavClick = (id: string) => {
    setActiveTab(id);
    if (id === 'routes') setShowRouteOptimization(true);
    else setShowRouteOptimization(false);
  };

  return (
    <div className="flex flex-col h-screen bg-[#040B14] text-slate-200 font-sans overflow-hidden">
      {/* Header */}
      <header className="h-12 border-b border-slate-800 bg-[#06111e] flex items-center justify-between px-4 z-20 shrink-0 font-mono">
        <div className="flex items-center gap-4">
          <div className="font-bold tracking-wider text-xs flex items-center gap-2 text-slate-100">
             <div className="w-2 h-2 rounded-xs bg-sky-400" />
             POLARNAV
          </div>
          <div className="hidden md:flex text-xs text-slate-400 border-l border-slate-800 pl-4">
            Sea-Ice · Iceberg · Ocean · Navigation Decision Support
          </div>
        </div>
        <div className="flex items-center gap-6 text-xs text-slate-400">
           <div className="hidden lg:block">{new Date().toISOString().split('T')[1].substring(0, 5)} UTC</div>
           <div className="hidden lg:block">DATA STATUS: <span className="text-emerald-400 font-semibold">OPERATIONAL (SATELLITE / AIS)</span></div>
           <div className="flex items-center gap-2 text-slate-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              SYSTEM OPERATIONAL
           </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-16 md:w-56 border-r border-slate-800 bg-[#06111e] flex flex-col z-20 shrink-0 font-mono">
          <div className="flex-1 py-3 flex flex-col gap-1 px-2">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-xs transition-colors group text-xs",
                  activeTab === item.id 
                    ? "bg-[#12283e] text-sky-300 border-l-2 border-sky-400 font-semibold" 
                    : "text-slate-400 hover:text-slate-200 hover:bg-[#081524] border-l-2 border-transparent"
                )}
              >
                <item.icon className={cn("w-4 h-4 shrink-0", activeTab === item.id ? "text-sky-400" : "")} />
                <span className="hidden md:block text-xs text-left">{item.label}</span>
              </button>
            ))}
          </div>
          <div className="p-3 border-t border-slate-800">
             <button className="flex items-center gap-3 text-slate-400 hover:text-slate-200 transition-colors w-full text-xs">
                <Settings className="w-4 h-4" />
                <span className="hidden md:block text-xs">Settings</span>
             </button>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 relative flex flex-col lg:flex-row bg-[#040B14]">
          
          {/* Map Container */}
          <div className="flex-1 relative h-full">
            <PolarMap 
              section="overview"
              selectedIcebergId={selectedIcebergId} 
              onSelectIceberg={setSelectedIcebergId}
              showRouteOptimization={showRouteOptimization}
            />

            {/* Time Machine / Timeline */}
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[400] bg-[#06111e] border border-slate-800 px-4 py-2 rounded-xs flex items-center gap-4 shadow-lg font-mono">
               <span className="text-[10px] text-slate-400">24H AGO</span>
               <div className="w-36 h-1 bg-[#040B14] border border-slate-800 rounded-full relative">
                  <div className="absolute top-1/2 left-1/3 -translate-y-1/2 w-2 h-2 rounded-full bg-sky-400" />
                  <div className="absolute top-0 left-0 h-full w-1/3 bg-sky-400/40 rounded-l-full" />
               </div>
               <span className="text-[10px] text-slate-100 font-bold">NOW</span>
               <div className="w-36 h-1 bg-[#040B14] border border-slate-800 rounded-full relative">
                  <div className="absolute top-0 left-1/3 w-0.5 h-1.5 -translate-y-0.5 bg-slate-600" />
                  <div className="absolute top-0 left-2/3 w-0.5 h-1.5 -translate-y-0.5 bg-slate-600" />
               </div>
               <span className="text-[10px] text-slate-400">+48H</span>
            </div>
          </div>

          {/* Right Panel or Drawer */}
          <div className={cn(
            "w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-slate-800 bg-[#06111e] z-[500] flex flex-col shrink-0 transition-transform duration-300",
            "h-1/3 lg:h-full lg:static absolute bottom-0", // Mobile drawer behavior
            showRouteOptimization ? "hidden" : "flex"
          )}>
            <IntelligencePanel selectedIcebergId={selectedIcebergId} />
          </div>
          
          {/* Route Optimization Drawer */}
          {showRouteOptimization && (
            <div className="absolute inset-y-0 right-0 w-full lg:w-[420px] bg-[#06111e] border-l border-slate-800 z-[500] shadow-2xl animate-in slide-in-from-right">
              <RouteOptimization onClose={() => setShowRouteOptimization(false)} />
            </div>
          )}

        </main>
      </div>
    </div>
  );
};

export default Dashboard;
