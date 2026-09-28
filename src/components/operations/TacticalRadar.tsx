// @ts-nocheck
import { useEffect, useRef, useState } from 'react';
import { Crosshair } from 'lucide-react';

const RANGE_OPTIONS = [3, 6, 12, 24];

export default function TacticalRadar({ targets = [], selectedTargetId, onSelectTarget }) {
  const canvasRef = useRef(null);
  const [range, setRange] = useState(12);
  const [sweep, setSweep] = useState(0);
  const [orientation, setOrientation] = useState('NORTH_UP');
  const selected = targets.find(t => t.id === selectedTargetId) || targets[0];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    const ctx = canvas.getContext('2d');
    let raf = 0;
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = parent.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    let last = performance.now();
    const draw = (now) => {
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      setSweep(v => (v + dt * 0.9) % (Math.PI * 2));
      const rect = parent.getBoundingClientRect();
      const w = rect.width, h = rect.height;
      const cx = w / 2, cy = h / 2;
      const radius = Math.min(w, h) * 0.42;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#020813';
      ctx.fillRect(0, 0, w, h);

      ctx.strokeStyle = 'rgba(0,242,254,.28)';
      ctx.lineWidth = 1;
      [1, .75, .5, .25].forEach(s => { ctx.beginPath(); ctx.arc(cx, cy, radius * s, 0, Math.PI * 2); ctx.stroke(); });
      for (let a = 0; a < Math.PI * 2; a += Math.PI / 12) {
        ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * (radius - 8), cy + Math.sin(a) * (radius - 8)); ctx.lineTo(cx + Math.cos(a) * radius, cy + Math.sin(a) * radius); ctx.stroke();
      }
      ctx.beginPath(); ctx.moveTo(cx - radius, cy); ctx.lineTo(cx + radius, cy); ctx.moveTo(cx, cy - radius); ctx.lineTo(cx, cy + radius); ctx.strokeStyle = 'rgba(0,242,254,.4)'; ctx.stroke();

      const grad = ctx.createConicGradient(sweep, cx, cy);
      grad.addColorStop(0, 'rgba(0,242,254,.42)'); grad.addColorStop(.08, 'rgba(0,242,254,.06)'); grad.addColorStop(.2, 'rgba(0,242,254,0)');
      ctx.fillStyle = grad; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, radius, sweep, sweep + .75); ctx.closePath(); ctx.fill();

      // Own ship
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(cx, cy - 12); ctx.lineTo(cx + 6, cy + 8); ctx.lineTo(cx, cy + 4); ctx.lineTo(cx - 6, cy + 8); ctx.closePath(); ctx.stroke();

      const plotted = targets.slice(0, 8).map((t, i) => {
        const bearing = ((i * 67 + 35) % 360) * Math.PI / 180;
        const nm = [1.8, 5.4, 8.9, 10.5, 6.7, 3.9][i % 6];
        return { t, bearing, nm };
      });
      plotted.forEach(({ t, bearing, nm }) => {
        const d = Math.min(nm / range, 1) * radius;
        const a = orientation === 'HEAD_UP' ? bearing - Math.PI / 4 : bearing - Math.PI / 2;
        const x = cx + Math.cos(a) * d, y = cy + Math.sin(a) * d;
        const active = t.id === selectedTargetId;
        const color = t.risk === 'CRITICAL' ? '#f43f5e' : t.risk === 'MODERATE' ? '#f59e0b' : '#38bdf8';
        ctx.strokeStyle = active ? '#00f2fe' : 'rgba(255,255,255,.45)'; ctx.lineWidth = active ? 2 : 1;
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 22 * Math.cos(a), y + 22 * Math.sin(a)); ctx.stroke();
        ctx.shadowColor = color; ctx.shadowBlur = active ? 16 : 8; ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, active ? 6 : 4, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
        if (active) {
          ctx.strokeStyle = '#00f2fe'; ctx.lineWidth = 1.5; ctx.strokeRect(x - 13, y - 13, 26, 26);
          ctx.fillStyle = '#fff'; ctx.font = '11px monospace'; ctx.fillText(`[${t.id}] CPA: ${t.cpaNm || 1.8}NM`, x + 18, y - 5);
          ctx.fillStyle = '#94a3b8'; ctx.fillText(`TCPA: ${t.tcpaHours || 3.2}h · ${t.driftSpeed || 1.2}kts`, x + 18, y + 9);
        }
      });

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, [targets, selectedTargetId, range, orientation]);

  return (
    <div className="ops-visual ops-radar">
      <div className="ops-radar-header"><div><Crosshair size={16} /> <b>ARPA TACTICAL RADAR</b> <span>RANGE: {range} NM</span> <span>MODE: {orientation}</span></div><span className="ops-radar-band"><i /> BAND: 9.4 GHz X-BAND / 3.0 GHz S-BAND</span></div>
      <div className="ops-radar-screen"><canvas ref={canvasRef} />
        <div className="ops-overlay ops-ownship"><b>OWN SHIP: RV AEOLUS</b><span>HDG: 045.0° T | SPD: 12.4 KTS</span><span>LAT: 64° 25.4' S | LON: 059° 50.2' W</span><strong>ALERT: 2 TARGETS WITHIN COLLISION CORRIDOR</strong></div>
      </div>
      <div className="ops-radar-controls">
        <div><label>RANGE</label>{RANGE_OPTIONS.map(r => <button key={r} className={range === r ? 'active' : ''} onClick={() => setRange(r)}>{r}NM</button>)}</div>
        <div><button onClick={() => setOrientation(v => v === 'NORTH_UP' ? 'HEAD_UP' : 'NORTH_UP')}>{orientation === 'NORTH_UP' ? 'NORTH UP' : 'HEAD UP'}</button><button>VECTORS: RELATIVE</button></div>
        <div>{targets.slice(0, 4).map(t => <button key={t.id} className={t.id === selectedTargetId ? 'active' : ''} onClick={() => onSelectTarget?.(t.id)}><i style={{ background: t.risk === 'CRITICAL' ? '#f43f5e' : '#f59e0b' }} />{t.id}</button>)}</div>
      </div>
    </div>
  );
}
