// @ts-nocheck
import { useEffect, useMemo, useRef, useState } from 'react';
import Globe from 'react-globe.gl';
import { Compass, Eye, RotateCw, Layers } from 'lucide-react';

const FALLBACK = [
  { id: 'ICE-A68-FRAG', name: 'A-68 Fragment', lat: -64.4, lon: -59.8, size: 0.95, color: '#f43f5e', risk: 'CRITICAL', length: 340, mass: '4.82 Mt', speed: '1.45 kts @ 128°', cpa: '1.8 NM (TCPA: 3.2h)' },
  { id: 'ICE-B15-OMEGA', name: 'B-15 Omega', lat: -66.1, lon: -62.4, size: 0.72, color: '#f59e0b', risk: 'MODERATE', length: 165, mass: '1.14 Mt', speed: '0.95 kts @ 142°', cpa: '5.4 NM (TCPA: 7.8h)' },
  { id: 'ICE-A76-NORTH', name: 'A-76 North', lat: -62.8, lon: -54.2, size: 0.82, color: '#38bdf8', risk: 'MONITORED', length: 480, mass: '6.20 Mt', speed: '1.10 kts @ 095°', cpa: '14.2 NM (TCPA: 18h)' },
  { id: 'BERGY-BIT-402', name: 'Bergy Bit 402', lat: -63.7, lon: -60.8, size: 0.5, color: '#00f2fe', risk: 'ADVISORY', length: 42, mass: '0.06 Mt', speed: '1.80 kts @ 110°', cpa: '8.9 NM (TCPA: 11.5h)' },
];

const COLORS = { CRITICAL: '#f43f5e', HIGH: '#fb7185', MODERATE: '#f59e0b', ADVISORY: '#00f2fe', MONITORED: '#38bdf8' };

export default function PolarGlobe({ targets = [], selectedTargetId, onSelectTarget }) {
  const globeRef = useRef(null);
  const [autoRotate, setAutoRotate] = useState(false);
  const [showArcs, setShowArcs] = useState(true);
  const selected = targets.find(t => t.id === selectedTargetId) || targets[0] || FALLBACK[0];
  const globeTargets = targets.length ? targets : FALLBACK;

  useEffect(() => {
    if (!globeRef.current) return;
    globeRef.current.pointOfView({ lat: selected.lat, lng: selected.lon, altitude: 1.45 }, 1000);
    globeRef.current.controls().autoRotate = autoRotate;
    globeRef.current.controls().autoRotateSpeed = 0.55;
  }, [selected.id]);

  useEffect(() => {
    if (globeRef.current) globeRef.current.controls().autoRotate = autoRotate;
  }, [autoRotate]);

  const arcs = useMemo(() => {
    const out = [];
    globeTargets.forEach(t => {
      const forecast = t.forecastPoints || [];
      const p24 = forecast.find(p => Number(p.hours ?? p.hour ?? 0) === 24) || forecast[2];
      const p48 = forecast.find(p => Number(p.hours ?? p.hour ?? 0) === 48) || forecast[3];
      if (p24?.coordinates) out.push({ startLat: t.lat, startLng: t.lon, endLat: p24.coordinates[0], endLng: p24.coordinates[1], color: [COLORS[t.risk] || t.color, '#fb7185'] });
      if (p48?.coordinates) out.push({ startLat: p24?.coordinates?.[0] ?? t.lat, startLng: p24?.coordinates?.[1] ?? t.lon, endLat: p48.coordinates[0], endLng: p48.coordinates[1], color: [COLORS[t.risk] || t.color, '#fda4af'] });
    });
    return out;
  }, [globeTargets]);

  const rings = useMemo(() => globeTargets.map(t => ({ lat: t.lat, lng: t.lon, color: COLORS[t.risk] || t.color || '#00f2fe', maxR: Math.max(0.5, t.size * 2.2) })), [globeTargets]);

  const focus = (t) => {
    onSelectTarget?.(t.id);
    globeRef.current?.pointOfView({ lat: t.lat, lng: t.lon, altitude: 0.82 }, 900);
  };

  return (
    <div className="ops-visual ops-globe">
      <Globe
        ref={globeRef}
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
        bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
        backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
        atmosphereColor="#00f2fe"
        atmosphereAltitude={0.2}
        pointsData={globeTargets}
        pointLat="lat"
        pointLng="lon"
        pointColor={(d) => COLORS[d.risk] || d.color || '#00f2fe'}
        pointAltitude={0.02}
        pointRadius="size"
        pointResolution={24}
        onPointClick={focus}
        pointLabel={(d) => `<div class="globe-tooltip"><b style="color:${COLORS[d.risk] || d.color}">${d.id}</b> — ${d.name}<br/>${d.lat.toFixed(2)}° S, ${Math.abs(d.lon).toFixed(2)}° W<br/>Length: ${d.length}m · ${d.mass}<br/>Velocity: ${d.speed || `${d.driftSpeed || 1.2} kts`}<br/><span>CPA: ${d.cpa || `${d.cpaNm || 2.4} NM`}</span></div>`}
        ringsData={rings}
        ringColor="color"
        ringMaxRadius="maxR"
        ringPropagationSpeed={1.3}
        ringRepeatPeriod={1300}
        arcsData={showArcs ? arcs : []}
        arcColor="color"
        arcDashLength={0.38}
        arcDashGap={0.22}
        arcDashAnimateTime={1900}
        arcStroke={1.4}
        arcAltitude={0.07}
      />

      <div className="ops-overlay ops-observation-card">
        <div className="ops-card-kicker"><span className="ops-dot" /> ANTARCTIC 3D OBSERVATION <span>WGS84 GEODETIC</span></div>
        <strong>{selected.id} — {selected.name}</strong>
        <div className="ops-mono">Lat: {selected.lat.toFixed(2)}° S | Lon: {Math.abs(selected.lon).toFixed(2)}° W</div>
        <div className="ops-mono">Kinematics: {selected.speed || `${selected.driftSpeed || 1.2} kts`}</div>
        <div className={`ops-risk ${String(selected.risk).toLowerCase()}`}>Risk Index: {selected.risk} ({selected.cpa || `${selected.cpaNm || 2.4} NM`})</div>
      </div>

      <div className="ops-overlay ops-target-list">
        <div className="ops-card-kicker">TRACKED TARGETS</div>
        {globeTargets.slice(0, 6).map(t => (
          <button key={t.id} className={t.id === selected.id ? 'ops-target active' : 'ops-target'} onClick={() => focus(t)}>
            <span style={{ background: COLORS[t.risk] || t.color }} /> {t.id}
          </button>
        ))}
      </div>

      <div className="ops-globe-toolbar">
        <button onClick={() => globeRef.current?.pointOfView({ lat: -64.5, lng: -60, altitude: 1.35 }, 900)}><Compass size={14} /> Focus Antarctica</button>
        <button onClick={() => globeRef.current?.pointOfView({ lat: -25, lng: -50, altitude: 2.45 }, 900)}><Eye size={14} /> Global</button>
        <button className={autoRotate ? 'active' : ''} onClick={() => setAutoRotate(v => !v)}><RotateCw size={14} /> Orbit {autoRotate ? 'ON' : 'OFF'}</button>
        <button className={showArcs ? 'active' : ''} onClick={() => setShowArcs(v => !v)}><Layers size={14} /> Drift Vectors</button>
      </div>
    </div>
  );
}
