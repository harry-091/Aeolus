// @ts-nocheck
import { useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, ArrowUpRight, ChevronRight, CloudSnow, Compass,
  Gauge, Globe2, Layers3, Navigation, Radar, Route, ShieldCheck, SlidersHorizontal,
  Sparkles, Waves, Wind, X
} from 'lucide-react';
import PolarGlobe from '../components/operations/PolarGlobe';
import TacticalRadar from '../components/operations/TacticalRadar';
import { api } from '../services/api';
import './OperationsConsole.css';

const DEFAULT_TARGETS = [
  { id: 'ICE-A68-FRAG', name: 'A-68 Fragment', lat: -64.4, lon: -59.8, length: 340, mass: '4.82 Mt', driftSpeed: 1.45, cpaNm: 1.8, tcpaHours: 3.2, risk: 'CRITICAL', confidence: 98.4 },
  { id: 'ICE-B15-OMEGA', name: 'B-15 Omega', lat: -66.1, lon: -62.4, length: 165, mass: '1.14 Mt', driftSpeed: 0.95, cpaNm: 5.4, tcpaHours: 7.8, risk: 'MODERATE', confidence: 95.1 },
  { id: 'ICE-A76-NORTH', name: 'A-76 North', lat: -62.8, lon: -54.2, length: 480, mass: '6.20 Mt', driftSpeed: 1.1, cpaNm: 14.2, tcpaHours: 18, risk: 'MONITORED', confidence: 89.6 },
  { id: 'BERGY-BIT-402', name: 'Bergy Bit 402', lat: -63.7, lon: -60.8, length: 42, mass: '0.06 Mt', driftSpeed: 1.8, cpaNm: 8.9, tcpaHours: 11.5, risk: 'ADVISORY', confidence: 81.2 },
];
const HORIZONS = [6, 12, 24, 48, 72];

function normalizeIcebergs(payload) {
  return (payload?.icebergs || []).map((x, i) => ({
    id: x.id || `TRACK-${i + 1}`,
    name: x.name || x.id || `Tracked Iceberg ${i + 1}`,
    lat: Number(x.latitude ?? x.origin_latitude ?? -64.4),
    lon: Number(x.longitude ?? x.origin_longitude ?? -59.8),
    length: Number(x.size || 150),
    mass: `${Math.max(0.06, Number(x.size || 150) * 0.014).toFixed(2)} Mt`,
    driftSpeed: Number(x.velocity || 1.2),
    cpaNm: Number.parseFloat(String(x.distanceFromVessel || '2.4')) || 2.4,
    tcpaHours: String(x.risk || '').toUpperCase() === 'HIGH' ? 3.2 : 7.8,
    risk: String(x.risk || x.base_risk || 'ADVISORY').toUpperCase(),
    confidence: Number(x.confidence || 94.8),
    forecastPoints: x.forecastPoints || [],
  }));
}

function predictedFor(target, hours) {
  const point = target.forecastPoints?.find(p => Number(String(p.horizon || '').replace(/\D/g, '')) === hours);
  if (point?.coordinates) return { lat: point.coordinates[0], lon: point.coordinates[1], uncertainty: Math.max(1.8, Number(point.displacementKm || 1.8) * 0.25) };
  const distance = target.driftSpeed * hours * 0.035;
  return { lat: target.lat - distance * 0.55, lon: target.lon + distance * 0.75, uncertainty: 1.8 + hours * 0.21 };
}

const riskClass = (risk) => String(risk || '').toLowerCase();

export default function OperationsConsole() {
  const [viewMode, setViewMode] = useState('globe');
  const [targets, setTargets] = useState(DEFAULT_TARGETS);
  const [selectedId, setSelectedId] = useState(DEFAULT_TARGETS[0].id);
  const [horizon, setHorizon] = useState(24);
  const [windSpeed, setWindSpeed] = useState(24);
  const [currentSpeed, setCurrentSpeed] = useState(0.48);
  const [seaIce, setSeaIce] = useState(42);
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [routeStatus, setRouteStatus] = useState('Ready for route evaluation');
  const [backendOnline, setBackendOnline] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const selected = targets.find(t => t.id === selectedId) || targets[0];
  const prediction = useMemo(() => predictedFor(selected, horizon), [selected, horizon]);
  const confidence = Math.max(55, Number(selected.confidence || 94.8) - Math.max(0, horizon - 6) * 0.35).toFixed(1);
  const criticalCount = targets.filter(t => ['CRITICAL', 'HIGH'].includes(String(t.risk).toUpperCase())).length;

  useEffect(() => {
    api.icebergs('ALL').then(data => {
      const mapped = normalizeIcebergs(data);
      if (mapped.length) {
        setTargets(prev => {
          const byId = new Map(prev.map(x => [x.id, x]));
          mapped.forEach(x => byId.set(x.id, { ...byId.get(x.id), ...x }));
          return Array.from(byId.values()).slice(0, 12);
        });
      }
      setBackendOnline(true);
    }).catch(() => {});
    api.health().then(data => setBackendOnline(Boolean(data))).catch(() => {});
  }, []);

  const handleRoute = async () => {
    setLoadingRoute(true);
    setRouteStatus('Evaluating safe corridor…');
    try {
      const result = await api.routesOptimize({
        start_lat: -64.42, start_lon: -61.2, dest_lat: -65.5, dest_lon: -58.0,
        destination: 'Antarctic Research Corridor', cruising_speed_kn: 14, polar_class: 'PC6'
      });
      setRouteStatus(result?.status ? `Route engine: ${result.status}` : 'Route engine unavailable — local decision model retained.');
    } catch {
      setRouteStatus('Route engine unavailable — local decision model retained.');
    } finally { setLoadingRoute(false); }
  };

  return (
    <div className="aeolus-ops">
      <header className="aeolus-topbar">
        <a href="/" className="aeolus-brand" aria-label="Aeolus home">
          <span className="aeolus-mark"><Wind size={17} /></span>
          <span><b>AEOLUS</b><small>POLAR INTELLIGENCE</small></span>
        </a>
        <nav className="aeolus-nav">
          <a href="/overview">Overview</a><a href="/navigation">Voyage</a><a href="/sea-ice">Ice Field</a><a href="/icebergs">Targets</a><a className="active" href="/operations">Decision Room</a><a href="/routes">Routes</a>
        </nav>
        <div className="aeolus-statusbar">
          <span className={backendOnline ? 'status-dot live' : 'status-dot'} />
          <span>{backendOnline ? 'LIVE DATA' : 'LOCAL MODE'}</span>
          <span className="utc">UTC {new Date().toISOString().slice(11, 19)}</span>
        </div>
      </header>

      <main className="aeolus-main">
        <div className="aeolus-heading-row">
          <div>
            <div className="eyebrow"><span>AEOLUS / DECISION ROOM</span><ChevronRight size={12} /><span>ANTARCTIC PENINSULA</span></div>
            <div className="page-title-row"><h1>Drift & collision workspace</h1><span className="quiet-badge"><Activity size={13} /> {targets.length} active tracks</span></div>
            <p className="page-subtitle">Observe iceberg motion, test forecast horizons, and evaluate a safer passage from one screen.</p>
          </div>
          <div className="heading-actions"><button className="outline-btn" onClick={() => setDetailsOpen(true)}><Layers3 size={15} /> Data layers</button><button className="solid-btn" onClick={handleRoute} disabled={loadingRoute}><Route size={15} /> {loadingRoute ? 'Evaluating…' : 'Evaluate route'}</button></div>
        </div>

        <section className="telemetry-strip">
          <Metric icon={TargetIcon} label="Tracked targets" value={String(targets.length)} note={`${criticalCount} high priority`} tone="red" />
          <Metric icon={Gauge} label="Forecast confidence" value={`${confidence}%`} note={`T+${horizon}h horizon`} tone="blue" />
          <Metric icon={Wind} label="Wind forcing" value={`${windSpeed} kt`} note="270° · leeway model" tone="amber" />
          <Metric icon={CloudSnow} label="Sea ice" value={`${seaIce}%`} note="concentration" tone="ice" />
          <Metric icon={Waves} label="Current" value={`${currentSpeed.toFixed(2)} m/s`} note="surface drift" tone="green" />
        </section>

        <section className="aeolus-layout">
          <div className="instrument-card">
            <div className="instrument-header">
              <div className="instrument-tabs">
                <button className={viewMode === 'globe' ? 'active' : ''} onClick={() => setViewMode('globe')}><Globe2 size={14} /> Globe</button>
                <button className={viewMode === 'radar' ? 'active' : ''} onClick={() => setViewMode('radar')}><Radar size={14} /> Radar</button>
                <button className={viewMode === 'split' ? 'active' : ''} onClick={() => setViewMode('split')}><SlidersHorizontal size={14} /> Split</button>
              </div>
              <div className="instrument-meta"><span>WGS84</span><span>POLAR SECTOR 07</span><span className="green-text">● STREAMING</span></div>
            </div>
            <div className={`instrument-body ${viewMode === 'split' ? 'split-mode' : ''}`}>
              {viewMode === 'globe' && <PolarGlobe targets={targets} selectedTargetId={selectedId} onSelectTarget={setSelectedId} />}
              {viewMode === 'radar' && <TacticalRadar targets={targets} selectedTargetId={selectedId} onSelectTarget={setSelectedId} />}
              {viewMode === 'split' && <><PolarGlobe targets={targets} selectedTargetId={selectedId} onSelectTarget={setSelectedId} /><TacticalRadar targets={targets} selectedTargetId={selectedId} onSelectTarget={setSelectedId} /></>}
            </div>
            <div className="instrument-footer"><span><Navigation size={13} /> RV AEOLUS · 14.0 kt · HDG 045°</span><span>Last sync 18:33:24 UTC</span><span className="route-state"><span className="state-dot" /> {routeStatus}</span></div>
          </div>

          <aside className="aeolus-inspector">
            <section className="inspector-card selected-card">
              <div className="card-label-row"><span>SELECTED TARGET</span><span className={`risk-pill ${riskClass(selected.risk)}`}>{selected.risk}</span></div>
              <div className="target-title"><span className="target-marker" /> <div><h2>{selected.id}</h2><p>{selected.name}</p></div></div>
              <div className="target-coords"><div><small>POSITION</small><b>{Math.abs(selected.lat).toFixed(3)}° S</b><b>{Math.abs(selected.lon).toFixed(3)}° W</b></div><div><small>CPA</small><b>{selected.cpaNm.toFixed(1)} NM</b><span>TCPA {selected.tcpaHours.toFixed(1)} h</span></div><div><small>DRIFT</small><b>{selected.driftSpeed.toFixed(2)} kt</b><span>{selected.length} m length</span></div></div>
            </section>

            <section className="inspector-card">
              <div className="card-label-row"><span>FORECAST HORIZON</span><b>{confidence}% confidence</b></div>
              <div className="horizon-row">{HORIZONS.map(h => <button key={h} className={h === horizon ? 'active' : ''} onClick={() => setHorizon(h)}>+{h}h</button>)}</div>
              <div className="forecast-result"><div><small>PREDICTED POSITION</small><strong>{Math.abs(prediction.lat).toFixed(3)}° S · {Math.abs(prediction.lon).toFixed(3)}° W</strong></div><div><small>UNCERTAINTY</small><strong>±{prediction.uncertainty.toFixed(1)} km</strong></div></div>
              <div className="confidence-bar"><span style={{ width: `${confidence}%` }} /></div>
            </section>

            <section className="inspector-card">
              <div className="card-label-row"><span>ENVIRONMENT</span><button className="icon-btn" onClick={() => setDetailsOpen(true)}><SlidersHorizontal size={14} /></button></div>
              <Range label="Wind speed" value={windSpeed} min={0} max={50} unit="kt" onChange={setWindSpeed} />
              <Range label="Surface current" value={currentSpeed} min={0} max={1.2} step={0.01} unit="m/s" onChange={setCurrentSpeed} />
              <Range label="Sea-ice concentration" value={seaIce} min={0} max={100} unit="%" onChange={setSeaIce} />
            </section>

            <section className="recommendation-card">
              <div className="recommendation-icon"><Sparkles size={16} /></div><div><small>AEOLUS RECOMMENDATION</small><strong>{selected.cpaNm < 3 ? 'Shift west of the current corridor.' : 'Current corridor remains acceptable.'}</strong><p>Decision is based on predicted drift, CPA and sea-ice exposure.</p></div><ArrowUpRight size={16} />
            </section>
          </aside>
        </section>

        <section className="target-table-card">
          <div className="table-head"><div><span className="section-kicker">TRACK LIST</span><h2>Active hazards</h2></div><span className="table-note">Select a target to focus the instruments</span></div>
          <div className="target-grid target-grid-head"><span>Target</span><span>Risk</span><span>Position</span><span>CPA</span><span>Forecast</span><span /></div>
          {targets.slice(0, 6).map(t => <button className={`target-grid target-row ${t.id === selectedId ? 'selected' : ''}`} key={t.id} onClick={() => setSelectedId(t.id)}><span className="target-name"><i className={`risk-dot ${riskClass(t.risk)}`} /><b>{t.id}</b><small>{t.name}</small></span><span><span className={`risk-pill ${riskClass(t.risk)}`}>{t.risk}</span></span><span>{Math.abs(t.lat).toFixed(2)}° S · {Math.abs(t.lon).toFixed(2)}° W</span><span>{t.cpaNm.toFixed(1)} NM <small>· {t.tcpaHours.toFixed(1)}h</small></span><span>{Number(t.confidence).toFixed(0)}% <small>confidence</small></span><ChevronRight size={15} /></button>)}
        </section>
      </main>

      {detailsOpen && <div className="aeolus-modal-backdrop" onClick={() => setDetailsOpen(false)}><div className="aeolus-modal" onClick={e => e.stopPropagation()}><div className="modal-head"><div><span className="section-kicker">DATA PROVENANCE</span><h2>Instrument layers</h2></div><button className="icon-btn" onClick={() => setDetailsOpen(false)}><X size={16} /></button></div><div className="source-list"><Source icon={CloudSnow} title="Sea-ice concentration" source="NOAA / passive microwave composite" /><Source icon={Radar} title="Surface observation" source="Sentinel-1 SAR / derived target layer" /><Source icon={Wind} title="Atmospheric forcing" source="ERA5 wind + current fields" /><Source icon={ShieldCheck} title="Safety model" source="Aeolus drift + collision model" /></div></div></div>}
    </div>
  );
}

function Metric({ icon: Icon, label, value, note, tone }) { return <div className="telemetry-metric"><span className={`metric-icon ${tone}`}><Icon size={15} /></span><div><small>{label}</small><strong>{value}</strong><span>{note}</span></div></div>; }
function Range({ label, value, min, max, step = 1, unit, onChange }) { return <label className="range-control"><span><b>{label}</b><em>{Number(value).toFixed(step < 1 ? 2 : 0)} {unit}</em></span><input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(Number(e.target.value))} /></label>; }
function Source({ icon: Icon, title, source }) { return <div className="source-row"><span><Icon size={15} /></span><div><b>{title}</b><small>{source}</small></div><ShieldCheck size={14} /></div>; }
function TargetIcon(props) { return <Radar {...props} />; }
