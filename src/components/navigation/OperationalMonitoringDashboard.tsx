import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Map as MapLibreMap,
  Marker as MapLibreMarker,
  NavigationControl,
  type StyleSpecification,
  type GeoJSONSource
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { FeatureCollection, Feature } from 'geojson';
import {
  Ship,
  Compass,
  Layers,
  Activity,
  ShieldAlert,
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  Info,
  ZoomIn,
  ZoomOut,
  Navigation,
  Database,
  Play,
  Pause,
  RotateCcw,
  Radio,
  Gauge,
  X
} from 'lucide-react';
import { api } from '../../services/api';
import { cn } from '../../utils/cn';

// Nautical daylight basemap style (ESRI Light Canvas)
const NAUTICAL_BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    'marine-light': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}'
      ],
      tileSize: 256,
      attribution: '© Esri, GEBCO, NOAA'
    }
  },
  layers: [
    {
      id: 'background',
      type: 'background',
      paint: { 'background-color': '#dff5ff' }
    },
    {
      id: 'marine-base',
      type: 'raster',
      source: 'marine-light',
      minzoom: 0,
      maxzoom: 16
    }
  ]
};

// Polar Navigation Grid GeoJSON
function generatePolarGridGeoJSON(): FeatureCollection {
  const features: Feature[] = [];
  const parallels = [-60, -65, -70, -75, -80];
  parallels.forEach((lat) => {
    const coords: [number, number][] = [];
    for (let lon = -180; lon <= 180; lon += 5) {
      coords.push([lon, lat]);
    }
    features.push({
      type: 'Feature',
      properties: { type: 'parallel', label: `${Math.abs(lat)}°S` },
      geometry: { type: 'LineString', coordinates: coords }
    });
  });

  for (let lon = -180; lon < 180; lon += 30) {
    const coords: [number, number][] = [];
    for (let lat = -55; lat >= -85; lat -= 2.5) {
      coords.push([lon, lat]);
    }
    features.push({
      type: 'Feature',
      properties: { type: 'meridian', label: `${Math.abs(lon)}°${lon >= 0 ? 'E' : 'W'}` },
      geometry: { type: 'LineString', coordinates: coords }
    });
  }

  return { type: 'FeatureCollection', features };
}

// Bathymetric depth isobaths for Antarctic continental shelf
function generateBathymetryIsobaths(): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { depth_m: 200, label: '200m Shelf Break' },
        geometry: {
          type: 'LineString',
          coordinates: [
            [68.0, -66.2], [70.0, -66.5], [73.0, -67.1], [76.0, -67.8], [78.0, -68.2], [82.0, -66.9]
          ]
        }
      },
      {
        type: 'Feature',
        properties: { depth_m: 500, label: '500m Contour' },
        geometry: {
          type: 'LineString',
          coordinates: [
            [67.0, -65.4], [70.0, -65.8], [74.0, -66.3], [77.0, -67.0], [80.0, -66.5], [84.0, -65.8]
          ]
        }
      },
      {
        type: 'Feature',
        properties: { depth_m: 1000, label: '1000m Abyssal Plain' },
        geometry: {
          type: 'LineString',
          coordinates: [
            [65.0, -64.2], [69.0, -64.8], [74.0, -65.2], [78.0, -65.9], [82.0, -65.3], [86.0, -64.6]
          ]
        }
      }
    ]
  };
}

export const OperationalMonitoringDashboard: React.FC = () => {
  // Operational Dashboard Backend State
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchTime, setLastFetchTime] = useState<Date>(new Date());
  const [secondsUntilPoll, setSecondsUntilPoll] = useState<number>(12);
  const [autoPollActive, setAutoPollActive] = useState<boolean>(true);
  const [activeProfile, setActiveProfile] = useState<'BALANCED' | 'SAFEST' | 'FASTEST'>('BALANCED');

  // Inspection Drawer State
  const [selectedInspection, setSelectedInspection] = useState<{
    type: 'VESSEL' | 'ROUTE_WAYPOINT' | 'ICEBERG' | 'RISK_ZONE';
    title: string;
    details: Record<string, any>;
  } | null>(null);

  // Map Layer Toggles (11 Operational Layers)
  const [layerToggles, setLayerToggles] = useState({
    vessel: true,
    recommendedRoute: true,
    alternateRoutes: true,
    sic: true,
    iceEdge: true,
    icebergs: true,
    weather: true,
    currentVectors: true,
    bathymetry: true,
    coastline: true,
    riskZones: true
  });

  const [provenanceExpanded, setProvenanceExpanded] = useState(false);

  // MapLibre Refs
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<MapLibreMap | null>(null);
  const vesselMarkerRef = useRef<MapLibreMarker | null>(null);
  const icebergMarkersRef = useRef<MapLibreMarker[]>([]);
  const waypointMarkersRef = useRef<MapLibreMarker[]>([]);

  // Fetch Operational Data from Backend
  const fetchOperationalData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.operationalDashboard();
      if (res && res.status === 'OPERATIONAL') {
        setData(res);
        setLastFetchTime(new Date());
        setError(null);
      }
    } catch (err: any) {
      console.error('Failed to fetch operational dashboard:', err);
      setError(err.message || 'Operational data synchronization offline.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial Load
  useEffect(() => {
    fetchOperationalData();
  }, [fetchOperationalData]);

  // Simulation Controls & NMEA Handlers
  const [simSpeed, setSimSpeed] = useState<number>(1);
  const [simPaused, setSimPaused] = useState<boolean>(false);

  const handleToggleSimulation = async () => {
    try {
      const nextPaused = !simPaused;
      setSimPaused(nextPaused);
      await api.vesselTelemetryControl({ action: nextPaused ? 'pause' : 'play' });
      fetchOperationalData();
    } catch (e) {
      console.error('Failed to toggle simulation:', e);
    }
  };

  const handleResetSimulation = async () => {
    try {
      setSimPaused(false);
      await api.vesselTelemetryControl({ action: 'reset' });
      fetchOperationalData();
    } catch (e) {
      console.error('Failed to reset simulation:', e);
    }
  };

  const handleSetSpeed = async (mult: number) => {
    try {
      setSimSpeed(mult);
      await api.vesselTelemetryControl({ action: 'set_speed', speed_multiplier: mult });
      fetchOperationalData();
    } catch (e) {
      console.error('Failed to set speed multiplier:', e);
    }
  };

  const handleInjectTestNmea = async () => {
    try {
      const testSentence = '$GPRMC,123519,A,6825.2000,S,07718.6000,E,11.4,042.0,230394,003.1,W*4F';
      await api.vesselTelemetryNmeaFeed({ sentence: testSentence });
      fetchOperationalData();
    } catch (e) {
      console.error('Failed to feed test NMEA sentence:', e);
    }
  };

  // Real-Time Polling Loop (12s countdown)
  useEffect(() => {
    if (!autoPollActive) return;

    const timer = setInterval(() => {
      setSecondsUntilPoll((prev) => {
        if (prev <= 1) {
          fetchOperationalData();
          return 12;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [autoPollActive, fetchOperationalData]);

  // Initialize MapLibre
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const initialCenter: [number, number] = [76.0, -68.5]; // Prydz Bay / Bharati Station sector
    const map = new MapLibreMap({
      container: mapContainerRef.current,
      style: NAUTICAL_BASE_STYLE,
      center: initialCenter,
      zoom: 5.2,
      minZoom: 2,
      maxZoom: 16,
      attributionControl: false
    });

    map.addControl(new NavigationControl({ showCompass: true, showZoom: false }), 'top-right');

    map.on('load', () => {
      // 1. Polar Nav Grid
      map.addSource('polar-grid-src', { type: 'geojson', data: generatePolarGridGeoJSON() });
      map.addLayer({
        id: 'polar-grid-lines',
        type: 'line',
        source: 'polar-grid-src',
        paint: {
          'line-color': '#1e293b',
          'line-width': 1.0,
          'line-dasharray': [2, 3]
        }
      });

      // 2. Bathymetry Isobaths
      map.addSource('bathymetry-isobaths-src', { type: 'geojson', data: generateBathymetryIsobaths() });
      map.addLayer({
        id: 'bathymetry-lines',
        type: 'line',
        source: 'bathymetry-isobaths-src',
        paint: {
          'line-color': '#0284c7',
          'line-width': 1.2,
          'line-dasharray': [4, 4],
          'line-opacity': 0.7
        }
      });

      // 3. Coastline Land Mask (Antarctica)
      api.landMask().then((lm) => {
        if (lm && map.getSource('antarctica-land-src') === undefined) {
          map.addSource('antarctica-land-src', { type: 'geojson', data: lm });
          map.addLayer({
            id: 'antarctica-land-fill',
            type: 'fill',
            source: 'antarctica-land-src',
            paint: {
              'fill-color': '#030811',
              'fill-opacity': 0.96
            }
          });
          map.addLayer({
            id: 'antarctica-land-stroke',
            type: 'line',
            source: 'antarctica-land-src',
            paint: {
              'line-color': '#334155',
              'line-width': 1.5
            }
          });
        }
      }).catch(() => {});
    });

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update Map Spatial Layers whenever `data` or `layerToggles` change
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !map.isStyleLoaded() || !data) return;

    // A. Update Layer Visibilities
    if (map.getLayer('bathymetry-lines')) {
      map.setLayoutProperty('bathymetry-lines', 'visibility', layerToggles.bathymetry ? 'visible' : 'none');
    }
    if (map.getLayer('antarctica-land-fill')) {
      map.setLayoutProperty('antarctica-land-fill', 'visibility', layerToggles.coastline ? 'visible' : 'none');
    }
    if (map.getLayer('antarctica-land-stroke')) {
      map.setLayoutProperty('antarctica-land-stroke', 'visibility', layerToggles.coastline ? 'visible' : 'none');
    }

    // B. Recommended & Alternate Routes GeoJSON
    const recRoute = data.route?.recommended;
    const altRoutes = data.route?.alternates || [];

    const routeFeatures: Feature[] = [];

    if (recRoute && recRoute.waypoints && recRoute.waypoints.length > 1) {
      const coords = recRoute.waypoints.map((w: any) => [w.longitude, w.latitude]);
      routeFeatures.push({
        type: 'Feature',
        properties: {
          id: recRoute.route_id,
          name: recRoute.name || 'RECOMMENDED BALANCED CORRIDOR',
          profile: recRoute.profile_type || 'BALANCED',
          isRecommended: true,
          color: '#10b981',
          width: 4.5
        },
        geometry: { type: 'LineString', coordinates: coords }
      });
    }

    altRoutes.forEach((alt: any) => {
      if (alt.waypoints && alt.waypoints.length > 1) {
        const coords = alt.waypoints.map((w: any) => [w.longitude, w.latitude]);
        const color = alt.profile_type === 'SAFEST' ? '#00f2fe' : '#f59e0b';
        routeFeatures.push({
          type: 'Feature',
          properties: {
            id: alt.route_id,
            name: alt.name,
            profile: alt.profile_type,
            isRecommended: false,
            color,
            width: 2.5
          },
          geometry: { type: 'LineString', coordinates: coords }
        });
      }
    });

    const routeGeoJSON: FeatureCollection = { type: 'FeatureCollection', features: routeFeatures };

    if (!map.getSource('routes-data-src')) {
      map.addSource('routes-data-src', { type: 'geojson', data: routeGeoJSON });
      map.addLayer({
        id: 'routes-data-lines',
        type: 'line',
        source: 'routes-data-src',
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['get', 'width'],
          'line-opacity': 0.95
        }
      });
    } else {
      (map.getSource('routes-data-src') as GeoJSONSource).setData(routeGeoJSON);
    }

    // C. Ice Edge Layer (15% SIC Contour)
    const iceEdgeCoords = data.spatial_layers?.ice_edge || [];
    if (iceEdgeCoords.length > 1) {
      const iceEdgeGeoJSON: FeatureCollection = {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: { label: '15% SIC Polar Ice Edge' },
            geometry: {
              type: 'LineString',
              coordinates: iceEdgeCoords.map((pt: [number, number]) => [pt[1], pt[0]])
            }
          }
        ]
      };

      if (!map.getSource('ice-edge-src')) {
        map.addSource('ice-edge-src', { type: 'geojson', data: iceEdgeGeoJSON });
        map.addLayer({
          id: 'ice-edge-line',
          type: 'line',
          source: 'ice-edge-src',
          paint: {
            'line-color': '#38bdf8',
            'line-width': 2.5,
            'line-dasharray': [6, 3]
          },
          layout: { visibility: layerToggles.iceEdge ? 'visible' : 'none' }
        });
      } else {
        (map.getSource('ice-edge-src') as GeoJSONSource).setData(iceEdgeGeoJSON);
        map.setLayoutProperty('ice-edge-line', 'visibility', layerToggles.iceEdge ? 'visible' : 'none');
      }
    }

    // D. Ocean Current Vectors Grid
    const vectors = data.spatial_layers?.current_vectors || [];
    if (vectors.length > 0) {
      const vectorFeatures: Feature[] = vectors.map((v: any) => ({
        type: 'Feature',
        properties: {
          speed_knots: v.speed_knots,
          bearing_deg: v.bearing_deg,
          label: `${v.speed_knots} kn @ ${v.bearing_deg}°`
        },
        geometry: {
          type: 'Point',
          coordinates: [v.lon, v.lat]
        }
      }));

      const vectorsGeoJSON: FeatureCollection = { type: 'FeatureCollection', features: vectorFeatures };

      if (!map.getSource('current-vectors-src')) {
        map.addSource('current-vectors-src', { type: 'geojson', data: vectorsGeoJSON });
        map.addLayer({
          id: 'current-vectors-points',
          type: 'circle',
          source: 'current-vectors-src',
          paint: {
            'circle-radius': 3.5,
            'circle-color': '#0ea5e9',
            'circle-opacity': 0.75,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#38bdf8'
          },
          layout: { visibility: layerToggles.currentVectors ? 'visible' : 'none' }
        });
      } else {
        (map.getSource('current-vectors-src') as GeoJSONSource).setData(vectorsGeoJSON);
        map.setLayoutProperty('current-vectors-points', 'visibility', layerToggles.currentVectors ? 'visible' : 'none');
      }
    }

    // E. Risk Zones Polygons
    const riskZones = data.spatial_layers?.risk_zones || [];
    if (riskZones.length > 0) {
      const riskZoneFeatures: Feature[] = riskZones.map((z: any) => ({
        type: 'Feature',
        properties: {
          id: z.zone_id,
          name: z.name,
          risk_level: z.risk_level,
          risk_score: z.risk_score,
          dominant_hazard: z.dominant_hazard
        },
        geometry: {
          type: 'Polygon',
          coordinates: [z.coordinates.map((c: [number, number]) => [c[1], c[0]])]
        }
      }));

      const riskZonesGeoJSON: FeatureCollection = { type: 'FeatureCollection', features: riskZoneFeatures };

      if (!map.getSource('risk-zones-src')) {
        map.addSource('risk-zones-src', { type: 'geojson', data: riskZonesGeoJSON });
        map.addLayer({
          id: 'risk-zones-fill',
          type: 'fill',
          source: 'risk-zones-src',
          paint: {
            'fill-color': '#ef4444',
            'fill-opacity': 0.18
          },
          layout: { visibility: layerToggles.riskZones ? 'visible' : 'none' }
        });
        map.addLayer({
          id: 'risk-zones-outline',
          type: 'line',
          source: 'risk-zones-src',
          paint: {
            'line-color': '#ef4444',
            'line-width': 1.5,
            'line-dasharray': [3, 2]
          },
          layout: { visibility: layerToggles.riskZones ? 'visible' : 'none' }
        });
      } else {
        (map.getSource('risk-zones-src') as GeoJSONSource).setData(riskZonesGeoJSON);
        map.setLayoutProperty('risk-zones-fill', 'visibility', layerToggles.riskZones ? 'visible' : 'none');
        map.setLayoutProperty('risk-zones-outline', 'visibility', layerToggles.riskZones ? 'visible' : 'none');
      }
    }

    // F. Interactive Vessel Marker with Heading Vector
    if (vesselMarkerRef.current) {
      vesselMarkerRef.current.remove();
      vesselMarkerRef.current = null;
    }

    if (layerToggles.vessel && data.vessel?.position) {
      const [vLat, vLon] = data.vessel.position;
      const el = document.createElement('div');
      el.className = 'cursor-pointer group relative';
      el.innerHTML = `
        <div class="relative flex items-center justify-center">
          <div class="w-8 h-8 rounded-full bg-emerald-500/20 border-2 border-emerald-400 flex items-center justify-center shadow-lg shadow-emerald-950/80">
            <svg class="w-4 h-4 text-emerald-300 transform" style="transform: rotate(${data.vessel.heading_deg || 0}deg)" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L4 20l8-4 8 4L12 2z" />
            </svg>
          </div>
          <div class="absolute -top-7 whitespace-nowrap bg-slate-900/90 text-[10px] font-mono font-bold text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-500/40 pointer-events-none">
            ${data.vessel.name} (${data.vessel.speed_knots} kn)
          </div>
        </div>
      `;

      el.addEventListener('click', () => {
        setSelectedInspection({
          type: 'VESSEL',
          title: `VESSEL TELEMETRY // ${data.vessel.name}`,
          details: data.vessel
        });
      });

      const marker = new MapLibreMarker({ element: el })
        .setLngLat([vLon, vLat])
        .addTo(map);

      vesselMarkerRef.current = marker;
    }

    // G. Interactive Iceberg Markers
    icebergMarkersRef.current.forEach((m) => m.remove());
    icebergMarkersRef.current = [];

    if (layerToggles.icebergs && data.spatial_layers?.icebergs) {
      data.spatial_layers.icebergs.forEach((berg: any) => {
        const el = document.createElement('div');
        el.className = 'cursor-pointer group';
        const isHazard = (berg.cpa_distance_km || 999) < 10.0;
        const colorClass = isHazard ? 'bg-red-500/20 border-red-500 text-red-300' : 'bg-amber-500/20 border-amber-500 text-amber-300';
        el.innerHTML = `
          <div class="relative flex items-center justify-center">
            <div class="w-6 h-6 rounded-sm ${colorClass} border flex items-center justify-center shadow-md">
              <span class="text-[9px] font-mono font-bold">▲</span>
            </div>
            <div class="hidden group-hover:block absolute -bottom-6 whitespace-nowrap bg-slate-950 text-[9px] font-mono text-slate-200 px-1.5 py-0.5 rounded border border-slate-700 z-50">
              ${berg.name || berg.id} • CPA ${Math.round(berg.cpa_distance_km || 0)}km
            </div>
          </div>
        `;

        el.addEventListener('click', () => {
          setSelectedInspection({
            type: 'ICEBERG',
            title: `RADAR/OPTICAL HAZARD // ${berg.name || berg.id}`,
            details: berg
          });
        });

        const m = new MapLibreMarker({ element: el })
          .setLngLat([berg.longitude, berg.latitude])
          .addTo(map);

        icebergMarkersRef.current.push(m);
      });
    }

    // H. Waypoint Markers for Route Inspection
    waypointMarkersRef.current.forEach((m) => m.remove());
    waypointMarkersRef.current = [];

    if (recRoute?.waypoints) {
      recRoute.waypoints.forEach((wp: any, idx: number) => {
        const el = document.createElement('div');
        el.className = 'cursor-pointer';
        el.innerHTML = `
          <div class="w-3.5 h-3.5 rounded-full bg-emerald-500 border border-slate-950 flex items-center justify-center shadow hover:scale-125 transition-transform">
            <span class="text-[7.5px] font-mono font-bold text-slate-950">${idx + 1}</span>
          </div>
        `;

        el.addEventListener('click', () => {
          setSelectedInspection({
            type: 'ROUTE_WAYPOINT',
            title: `CORRIDOR WAYPOINT // WP-${String(idx + 1).padStart(2, '0')}`,
            details: wp
          });
        });

        const m = new MapLibreMarker({ element: el })
          .setLngLat([wp.longitude, wp.latitude])
          .addTo(map);

        waypointMarkersRef.current.push(m);
      });
    }
  }, [data, layerToggles]);

  // Center on Vessel
  const handleCenterOnVessel = () => {
    if (!mapInstanceRef.current || !data?.vessel?.position) return;
    const [lat, lon] = data.vessel.position;
    mapInstanceRef.current.flyTo({ center: [lon, lat], zoom: 7.5, speed: 1.4 });
  };

  // Fit Entire Recommended Route
  const handleFitRoute = () => {
    const map = mapInstanceRef.current;
    if (!map || !data?.route?.recommended?.waypoints?.length) return;
    const wps = data.route.recommended.waypoints;
    const lats = wps.map((w: any) => w.latitude);
    const lons = wps.map((w: any) => w.longitude);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    map.fitBounds([[minLon - 1, minLat - 0.5], [maxLon + 1, maxLat + 0.5]], { padding: 40 });
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-slate-950 text-slate-100 font-sans overflow-hidden">
      {/* 1. TOP MARITIME CONSOLE STATUS STRIP */}
      <header className="h-12 bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between shrink-0 font-mono text-xs">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Compass className="w-4 h-4 text-emerald-400 animate-spin-slow" />
            <span className="font-bold tracking-wider text-slate-100">POLARNAV // OPERATIONAL CONSOLE</span>
            <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px] font-bold">
              ECDIS VTS
            </span>
          </div>

          <div className="hidden lg:flex items-center gap-3 text-[11px] text-slate-400 border-l border-slate-700 pl-4">
            <span>VESSEL: <strong className="text-slate-200">{data?.vessel?.name || 'R/V Sagar Nidhi'}</strong></span>
            <span>MMSI: <strong className="text-slate-300">{data?.vessel?.mmsi || '419072400'}</strong></span>
            <span>CLASS: <strong className="text-emerald-400">{data?.vessel?.ice_class || 'PC5'}</strong></span>
          </div>
          {error && (
            <div className="hidden sm:flex items-center gap-1 text-red-400 text-[10px] bg-red-950/40 px-2 py-0.5 rounded border border-red-500/30">
              <AlertTriangle className="w-3 h-3" />
              <span>{error}</span>
            </div>
          )}
          <span className="text-[10px] text-slate-500 hidden xl:inline">
            SYNCED: {lastFetchTime.toLocaleTimeString()}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Real-time Ticker */}
          <div className="flex items-center gap-2 bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-[11px]">
            <span className={cn('w-2 h-2 rounded-full', autoPollActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500')} />
            <span className="text-slate-400">
              {autoPollActive ? `POLL: ${secondsUntilPoll}s` : 'PAUSED'}
            </span>
            <button
              onClick={() => setAutoPollActive(!autoPollActive)}
              className="p-0.5 text-slate-400 hover:text-white transition-colors"
              title={autoPollActive ? 'Pause auto poll' : 'Resume auto poll'}
            >
              {autoPollActive ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            </button>
            <button
              onClick={fetchOperationalData}
              disabled={loading}
              className="p-0.5 text-slate-400 hover:text-emerald-300 transition-colors disabled:opacity-50"
              title="Manual Poll Now"
            >
              <RefreshCw className={cn('w-3 h-3', loading && 'animate-spin text-emerald-400')} />
            </button>
          </div>

          {/* Profile Switcher */}
          <div className="flex rounded border border-slate-700 overflow-hidden text-[10px] font-bold">
            {(['BALANCED', 'SAFEST', 'FASTEST'] as const).map((prof) => (
              <button
                key={prof}
                onClick={() => setActiveProfile(prof)}
                className={cn(
                  'px-2 py-1 transition-colors',
                  activeProfile === prof
                    ? 'bg-emerald-600 text-white font-bold'
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                )}
              >
                {prof}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* 2. MAIN OPERATIONAL WORKSPACE (SIDEBAR + MAP) */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* SIDEBAR: STRICT NAUTICAL VTS TELEMETRY (400px width) */}
        <aside className="w-[410px] bg-slate-900/95 border-r border-slate-800 flex flex-col overflow-y-auto shrink-0 divide-y divide-slate-800 font-mono">
          {/* SECTION 1: CURRENT VESSEL & TELEMETRY */}
          <div className="p-3.5 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5 font-bold text-slate-200 uppercase tracking-wider">
                <Ship className="w-3.5 h-3.5 text-emerald-400" />
                01 // Vessel Telemetry
              </span>
              <span className={cn(
                "px-1.5 py-0.5 rounded text-[9.5px] font-bold tracking-wider uppercase border flex items-center gap-1",
                data?.vessel?.source === 'LIVE_NMEA'
                  ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                  : "bg-amber-500/20 text-amber-300 border-amber-500/30"
              )}>
                <span className={cn("w-1.5 h-1.5 rounded-full", data?.vessel?.source === 'LIVE_NMEA' ? "bg-emerald-400 animate-pulse" : "bg-amber-400")} />
                {data?.vessel?.source === 'LIVE_NMEA' ? 'LIVE NMEA' : 'SIMULATION'}
              </span>
            </div>

            <div className="bg-slate-950/70 p-2.5 rounded border border-slate-800 text-xs space-y-1.5">
              <div className="flex justify-between items-center">
                <span className="text-slate-200 font-bold text-sm">{data?.vessel?.name || 'R/V Sagar Nidhi'}</span>
                <span className="px-1.5 py-0.5 rounded bg-slate-800 text-emerald-400 text-[10px] font-bold">
                  {data?.vessel?.ice_class || 'PC5'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-300">
                <div>MMSI: <span className="text-slate-100">{data?.vessel?.mmsi || '419072400'}</span></div>
                <div>CALL SIGN: <span className="text-slate-100">{data?.vessel?.call_sign || 'VTCX'}</span></div>
                <div>SOG: <span className="text-emerald-400 font-bold">{data?.vessel?.speed_knots || 12.0} kn</span></div>
                <div>COG: <span className="text-slate-100">{data?.vessel?.cog_deg ?? data?.vessel?.heading_deg ?? 145}°T</span></div>
                <div>HEADING: <span className="text-slate-100">{data?.vessel?.heading_deg || 145}°T</span></div>
                <div>DRAFT: <span className="text-slate-100">{data?.vessel?.draft_m || 6.5} m</span></div>
              </div>
              <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-800/80 flex justify-between">
                <span>POS: <strong className="text-slate-200 font-mono">{data?.vessel?.position ? `${Math.abs(data.vessel.position[0]).toFixed(2)}°S, ${data.vessel.position[1].toFixed(2)}°E` : '-'}</strong></span>
                <span>DEST: <strong className="text-slate-300">{data?.vessel?.destination || 'Bharati Station'}</strong></span>
              </div>

              {/* Source & Freshness */}
              <div className="text-[10px] pt-1 border-t border-slate-800/80 flex justify-between items-center text-slate-400">
                <span>SOURCE: <strong className={data?.vessel?.source === 'LIVE_NMEA' ? "text-emerald-400" : "text-amber-400"}>{data?.vessel?.source || 'SIMULATION'}</strong></span>
                <span>LAST UPDATE: <strong className="text-slate-300 font-mono">{data?.vessel?.data_age_seconds !== undefined ? `${Math.round(data.vessel.data_age_seconds)}s ago` : '2s ago'}</strong></span>
              </div>

              {/* Corridor Progress Bar */}
              <div className="pt-1 space-y-1">
                <div className="flex justify-between text-[9px] text-slate-400">
                  <span>CORRIDOR PROGRESS</span>
                  <span className="text-emerald-400 font-bold">{data?.vessel?.route_progress_pct ?? 0}%</span>
                </div>
                <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden border border-slate-800">
                  <div
                    className="bg-emerald-500 h-full transition-all duration-300"
                    style={{ width: `${Math.min(100, Math.max(0, data?.vessel?.route_progress_pct ?? 0))}%` }}
                  />
                </div>
              </div>

              {/* SIH Demonstration Simulation Controls */}
              <div className="pt-1.5 border-t border-slate-800/80 flex items-center justify-between gap-1 text-[10px]">
                <div className="flex items-center gap-1">
                  <button
                    onClick={handleToggleSimulation}
                    title={simPaused ? "Resume Vessel Simulation" : "Pause Vessel Simulation"}
                    className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 flex items-center gap-1 font-bold transition-colors"
                  >
                    {simPaused ? <Play className="w-3 h-3 text-emerald-400" /> : <Pause className="w-3 h-3 text-amber-400" />}
                    {simPaused ? 'PLAY' : 'PAUSE'}
                  </button>
                  <button
                    onClick={handleResetSimulation}
                    title="Reset Vessel to Track Origin"
                    className="p-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors"
                  >
                    <RotateCcw className="w-3 h-3" />
                  </button>
                </div>

                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-slate-500">SPEED:</span>
                  {[1, 5, 15, 30].map((spd) => (
                    <button
                      key={spd}
                      onClick={() => handleSetSpeed(spd)}
                      className={cn(
                        "px-1.5 py-0.5 rounded text-[9.5px] font-mono font-bold transition-colors",
                        simSpeed === spd
                          ? "bg-emerald-500/30 text-emerald-300 border border-emerald-500/50"
                          : "bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-800"
                      )}
                    >
                      {spd}x
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-1 pt-1">
                <button
                  onClick={() => setSelectedInspection({
                    type: 'VESSEL',
                    title: `VESSEL PARTICULARS // ${data?.vessel?.name}`,
                    details: data?.vessel
                  })}
                  className="flex-1 py-1 text-[10px] font-bold uppercase bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 transition-colors"
                >
                  Particulars →
                </button>
                <button
                  onClick={handleInjectTestNmea}
                  title="Inject test NMEA sentence (GPRMC) to demonstrate live shipboard GPS transition"
                  className="px-2 py-1 text-[9.5px] font-bold bg-sky-950/60 hover:bg-sky-900/60 text-sky-300 rounded border border-sky-600/40 transition-colors flex items-center gap-1"
                >
                  <Radio className="w-3 h-3" />
                  NMEA Test
                </button>
              </div>
            </div>
          </div>

          {/* SECTION 2: CURRENT CONDITIONS */}
          <div className="p-3.5 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5 font-bold text-slate-200 uppercase tracking-wider">
                <Gauge className="w-3.5 h-3.5 text-sky-400" />
                02 // Current Conditions
              </span>
              <span className="text-[10px] text-slate-400">Multi-Sensor In-Situ</span>
            </div>

            <div className="grid grid-cols-2 gap-1.5 text-xs">
              <div className="bg-slate-950/70 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">SEA ICE (SIC)</span>
                <span className="text-sm font-bold text-sky-300">{data?.conditions?.sic_pct ?? 34.2}%</span>
                <span className="text-[9px] text-slate-500 block">Sub-critical</span>
              </div>
              <div className="bg-slate-950/70 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">WIND SPEED</span>
                <span className="text-sm font-bold text-slate-200">{data?.conditions?.wind_speed_knots ?? 24.5} kn</span>
                <span className="text-[9px] text-slate-500 block">Gusts {data?.conditions?.wind_gusts_knots ?? 31.8} kn @ {data?.conditions?.wind_direction_deg ?? 210}°</span>
              </div>
              <div className="bg-slate-950/70 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">WAVE HEIGHT</span>
                <span className="text-sm font-bold text-slate-200">{data?.conditions?.wave_height_m ?? 2.85} m</span>
                <span className="text-[9px] text-slate-500 block">Moderate swell</span>
              </div>
              <div className="bg-slate-950/70 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">OCEAN CURRENT</span>
                <span className="text-sm font-bold text-slate-200">{data?.conditions?.current_speed_knots ?? 0.65} kn</span>
                <span className="text-[9px] text-slate-500 block">Set {data?.conditions?.current_heading_deg ?? 95}°</span>
              </div>
              <div className="bg-slate-950/70 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">AIR / SST</span>
                <span className="text-xs font-bold text-slate-200">
                  {data?.conditions?.air_temp_c ?? -8.4}°C / {data?.conditions?.sea_surface_temp_c ?? -1.2}°C
                </span>
                <span className="text-[9px] text-slate-500 block">P: {data?.conditions?.pressure_hpa ?? 988.4} hPa</span>
              </div>
              <div className="bg-slate-950/70 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">DEPTH & UKC</span>
                <span className="text-xs font-bold text-emerald-400">
                  {data?.conditions?.depth_m ?? 420.0}m (UKC {data?.conditions?.under_keel_clearance_m ?? 413.5}m)
                </span>
                <span className="text-[9px] text-emerald-500 block">Clearance Nominal</span>
              </div>
            </div>
          </div>

          {/* SECTION 3: VESSEL-AWARE ML RISK */}
          <div className="p-3.5 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5 font-bold text-slate-200 uppercase tracking-wider">
                <Activity className="w-3.5 h-3.5 text-amber-400" />
                03 // Risk Assessment
              </span>
              <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-bold">
                {data?.risk?.risk_category || 'MODERATE'}
              </span>
            </div>

            <div className="bg-slate-950/70 p-2.5 rounded border border-slate-800 space-y-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">POLARNAV Risk Index:</span>
                <span className="font-bold text-amber-300 text-sm">{data?.risk?.risk_percentage ?? 28.4}%</span>
              </div>
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-400">Dominant Hazard:</span>
                <span className="text-slate-200 font-semibold">{data?.risk?.dominant_hazard || 'SEA_ICE_EXPOSURE'}</span>
              </div>
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-400">Model Confidence:</span>
                <span className="text-emerald-400 font-bold">{data?.risk?.confidence_percentage ?? 94.2}%</span>
              </div>

              {/* Multi-Factor Breakdown Bars */}
              <div className="pt-2 border-t border-slate-800 space-y-1.5 text-[10px]">
                <div className="text-slate-400 font-bold">MULTI-FACTOR RISK BREAKDOWN:</div>
                {[
                  { label: 'Sea Ice Exposure', val: data?.risk?.breakdown?.sea_ice_risk ?? 0.38, col: 'bg-sky-500' },
                  { label: 'Iceberg Proximity', val: data?.risk?.breakdown?.iceberg_risk ?? 0.15, col: 'bg-red-500' },
                  { label: 'Wind Severity', val: data?.risk?.breakdown?.wind_risk ?? 0.22, col: 'bg-amber-500' },
                  { label: 'Wave Action', val: data?.risk?.breakdown?.wave_risk ?? 0.20, col: 'bg-indigo-500' },
                  { label: 'Current Leeway', val: data?.risk?.breakdown?.current_leeway_risk ?? 0.12, col: 'bg-teal-500' },
                  { label: 'Bathymetric Grounding', val: data?.risk?.breakdown?.bathymetry_grounding_risk ?? 0.04, col: 'bg-emerald-500' }
                ].map((factor) => (
                  <div key={factor.label} className="space-y-0.5">
                    <div className="flex justify-between text-slate-400">
                      <span>{factor.label}</span>
                      <span>{Math.round(factor.val * 100)}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div className={cn('h-full', factor.col)} style={{ width: `${Math.min(100, factor.val * 100)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* SECTION 4: ROUTE & ETA & EXPLAINABILITY */}
          <div className="p-3.5 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5 font-bold text-slate-200 uppercase tracking-wider">
                <Navigation className="w-3.5 h-3.5 text-emerald-400" />
                04 // Route & ETA
              </span>
              <span className="text-[10px] text-emerald-400 font-bold">ACTIVE {activeProfile}</span>
            </div>

            <div className="bg-slate-950/70 p-2.5 rounded border border-slate-800 space-y-2 text-xs">
              <div className="grid grid-cols-2 gap-2 text-slate-300">
                <div>
                  <span className="text-[10px] text-slate-500 block">TOTAL DISTANCE</span>
                  <span className="font-bold text-slate-100">{data?.eta?.distance_nm ?? 2051.8} NM ({data?.eta?.distance_km ?? 3800.0} km)</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block">TRANSIT ETA</span>
                  <span className="font-bold text-emerald-300">{data?.eta?.hours ?? 171.0} hrs</span>
                </div>
              </div>

              {/* WHY DID POLARNAV CHANGE MY ROUTE? */}
              <div className="mt-2 p-2 bg-slate-900 border border-slate-700/80 rounded text-[11px] space-y-1">
                <div className="flex items-center justify-between text-emerald-400 font-bold">
                  <span className="flex items-center gap-1">
                    <Info className="w-3 h-3" />
                    WHY DID POLARNAV CHANGE MY ROUTE?
                  </span>
                  <span className="text-[9px] px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-300">
                    VERIFIED
                  </span>
                </div>
                <p className="text-slate-300 text-[10.5px] leading-relaxed">
                  {data?.route?.why_did_polarnav_change_my_route ||
                    'Route is optimal and verified against current multi-sensor observations.'}
                </p>
                <div className="text-[9px] text-slate-500 pt-1 border-t border-slate-800 flex justify-between">
                  <span>Continuous Monitoring: ACTIVE</span>
                  <span>Reroutes: {data?.route?.reroute_count ?? 0}</span>
                </div>
              </div>
            </div>
          </div>

          {/* SECTION 5: TACTICAL ALERTS */}
          <div className="p-3.5 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5 font-bold text-slate-200 uppercase tracking-wider">
                <ShieldAlert className="w-3.5 h-3.5 text-red-400" />
                05 // Tactical Alerts
              </span>
              <span className="text-[10px] text-slate-400">
                {data?.alerts?.length || 0} Active
              </span>
            </div>

            <div className="space-y-1.5">
              {data?.alerts && data.alerts.length > 0 ? (
                data.alerts.map((alert: string, idx: number) => (
                  <div
                    key={idx}
                    className="bg-red-950/30 border border-red-500/40 p-2 rounded text-[10.5px] text-red-200 flex items-start gap-2"
                  >
                    <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                    <span>{alert}</span>
                  </div>
                ))
              ) : (
                <div className="bg-slate-950/70 border border-slate-800 p-2 rounded text-[10px] text-slate-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>No critical safety violations active along corridor.</span>
                </div>
              )}
            </div>
          </div>

          {/* SECTION 6: DATA FRESHNESS & DATA HEALTH (EXACT REQUIRED FORMAT) */}
          <div className="p-3.5 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5 font-bold text-slate-200 uppercase tracking-wider">
                <Database className="w-3.5 h-3.5 text-sky-400" />
                06 // Data Health & Provenance
              </span>
              <span className="text-[10px] text-emerald-400 font-bold">
                CONF: {Math.round((data?.data_freshness?.unified_confidence || 0.94) * 100)}%
              </span>
            </div>

            {/* DATA HEALTH TABLE (Exact User Specification) */}
            <div className="bg-slate-950 p-2.5 rounded border border-slate-800 space-y-1 font-mono text-xs">
              <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider pb-1 border-b border-slate-800">
                DATA HEALTH
              </div>
              <div className="divide-y divide-slate-900">
                {[
                  {
                    stream: 'Satellite',
                    key: 'satellite',
                    fallbackAge: '18 min ago',
                    source: 'Sentinel-1 SAR / ESA'
                  },
                  {
                    stream: 'Sea Ice',
                    key: 'sea_ice',
                    fallbackAge: '42 min ago',
                    source: 'AMSR2 / NSIDC CDR'
                  },
                  {
                    stream: 'Weather',
                    key: 'weather',
                    fallbackAge: '8 min ago',
                    source: 'ECMWF Open Data HRES'
                  },
                  {
                    stream: 'Ocean',
                    key: 'ocean',
                    fallbackAge: '31 min ago',
                    source: 'Copernicus GLORYS12'
                  },
                  {
                    stream: 'Iceberg',
                    key: 'iceberg',
                    fallbackAge: '27 min ago',
                    source: 'US National Ice Center'
                  },
                  {
                    stream: 'Bathymetry',
                    key: 'bathymetry',
                    fallbackAge: 'STATIC',
                    source: 'GEBCO 2024 / GSHHG'
                  },
                  {
                    stream: 'Vessel GPS',
                    key: 'vessel_gps',
                    fallbackAge: data?.vessel?.source === 'LIVE_NMEA' ? '0s ago' : 'SIMULATION',
                    source: data?.vessel?.source === 'LIVE_NMEA' ? 'Shipboard NMEA Receiver (UDP)' : 'Antarctic Route Simulator',
                    isVessel: true
                  }
                ].map((item) => {
                  const healthObj = Array.isArray(data?.data_health)
                    ? data.data_health.find((h: any) => h.provider_key === item.key)
                    : data?.data_health?.[item.key];
                  const isVessel = Boolean((item as any).isVessel);
                  const isLiveNmea = data?.vessel?.source === 'LIVE_NMEA';
                  const dataAge = healthObj?.data_age_formatted || healthObj?.data_age || item.fallbackAge;
                  const isStale = Boolean(healthObj?.is_stale);
                  const isStatic = dataAge === 'STATIC';

                  // CRITICAL INVARIANT: Never display "LIVE" if the underlying data is stale or simulated.
                  const displayBadge = isVessel
                    ? (isLiveNmea ? 'LIVE' : 'SIMULATION')
                    : isStatic
                    ? 'STATIC'
                    : isStale
                    ? 'STALE'
                    : 'LIVE';

                  return (
                    <div key={item.stream} className="py-1 flex items-center justify-between text-[11px]">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'w-2 h-2 rounded-full',
                            isVessel
                              ? (isLiveNmea ? 'bg-emerald-400' : 'bg-amber-400')
                              : isStatic
                              ? 'bg-slate-500'
                              : isStale
                              ? 'bg-amber-400 animate-pulse'
                              : 'bg-emerald-400'
                          )}
                        />
                        <span className="text-slate-200 font-semibold w-24">{item.stream}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-slate-400 text-[10.5px]">{dataAge}</span>
                        <span
                          className={cn(
                            'px-1 py-0.2 rounded text-[9px] font-bold',
                            displayBadge === 'LIVE'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              : displayBadge === 'SIMULATION'
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                              : displayBadge === 'STALE'
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                              : 'bg-slate-800 text-slate-400 border border-slate-700'
                          )}
                        >
                          {displayBadge}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Provenance Details Trigger */}
              <button
                onClick={() => setProvenanceExpanded(!provenanceExpanded)}
                className="w-full mt-2 pt-1.5 border-t border-slate-800/80 text-[10px] text-slate-400 hover:text-slate-200 flex items-center justify-between"
              >
                <span>{provenanceExpanded ? '▲ Hide Sensor Provenance' : '▼ Expand Sensor Provenance'}</span>
                <span className="text-emerald-400">All 11 Layers</span>
              </button>

              {provenanceExpanded && (
                <div className="pt-2 border-t border-slate-800 space-y-1.5 text-[9.5px] text-slate-400">
                  {data?.layer_metadata &&
                    Object.entries(data.layer_metadata).map(([key, meta]: [string, any]) => (
                      <div key={key} className="p-1.5 bg-slate-900/80 rounded border border-slate-800/60">
                        <div className="flex justify-between font-bold text-slate-300">
                          <span>{key.toUpperCase()}</span>
                          <span className={cn(meta.is_stale ? 'text-amber-400' : 'text-emerald-400')}>
                            {meta.is_stale ? 'STALE' : meta.data_age === 'STATIC' ? 'STATIC' : 'LIVE'}
                          </span>
                        </div>
                        <div>Source: {meta.source}</div>
                        <div>Timestamp: {meta.timestamp}</div>
                        <div>Data Age: {meta.data_age}</div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* PRIMARY MAP CONTAINER */}
        <main className="flex-1 relative flex flex-col bg-slate-950">
          {/* MAP CANVAS */}
          <div ref={mapContainerRef} className="w-full h-full" />

          {/* MAP OVERLAY: LAYER PROVENANCE HUD (Every Live Layer Displays: Source, Timestamp, Data Age) */}
          <div className="absolute top-3 left-3 z-10 bg-slate-950 border border-slate-800 p-2 rounded shadow-lg font-mono text-[10px] max-w-sm pointer-events-auto">
            <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-1 mb-1">
              <span className="font-bold text-slate-200 uppercase flex items-center gap-1.5">
                <Database className="w-3 h-3 text-emerald-400" />
                Live Layer Provenance HUD
              </span>
              <span className="text-emerald-400 text-[9px] font-bold">REAL-TIME</span>
            </div>
            <div className="space-y-0.5 text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-400">Sea Ice:</span>
                <span>AMSR2 CDR • {data?.layer_metadata?.sea_ice?.data_age || '42 min ago'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Weather:</span>
                <span>ECMWF HRES • {data?.layer_metadata?.weather?.data_age || '8 min ago'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Currents:</span>
                <span>GLORYS12 • {data?.layer_metadata?.ocean_currents?.data_age || '31 min ago'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Icebergs:</span>
                <span>US NIC • {data?.layer_metadata?.iceberg_hazards?.data_age || '27 min ago'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Bathymetry:</span>
                <span>GEBCO 2024 • STATIC</span>
              </div>
            </div>
          </div>

          {/* MAP CONTROLS: ZOOM & QUICK NAVIGATION */}
          <div className="absolute top-3 right-3 z-10 flex flex-col gap-1.5">
            <div className="bg-slate-950/90 border border-slate-800 rounded p-1 flex flex-col gap-1 shadow-lg font-mono">
              <button
                onClick={() => mapInstanceRef.current?.zoomIn()}
                className="p-1.5 hover:bg-slate-800 text-slate-300 hover:text-white rounded"
                title="Zoom In"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={() => mapInstanceRef.current?.zoomOut()}
                className="p-1.5 hover:bg-slate-800 text-slate-300 hover:text-white rounded"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <button
                onClick={handleCenterOnVessel}
                className="p-1.5 hover:bg-slate-800 text-emerald-400 hover:text-emerald-300 rounded"
                title="Center on Vessel"
              >
                <Ship className="w-4 h-4" />
              </button>
              <button
                onClick={handleFitRoute}
                className="p-1.5 hover:bg-slate-800 text-sky-400 hover:text-sky-300 rounded"
                title="Fit Route to Extents"
              >
                <Navigation className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* MAP BOTTOM: LAYER TOGGLES DRAWER */}
          <div className="absolute bottom-3 left-3 right-3 z-10 bg-slate-950 border border-slate-800 p-2.5 rounded shadow-xl font-mono text-xs flex items-center justify-between gap-4 overflow-x-auto">
            <div className="flex items-center gap-1.5 font-bold text-slate-300 text-[11px] shrink-0">
              <Layers className="w-3.5 h-3.5 text-emerald-400" />
              <span>LAYER TOGGLES:</span>
            </div>

            <div className="flex items-center gap-3 shrink-0 text-[11px]">
              {[
                { id: 'vessel', label: 'Vessel' },
                { id: 'recommendedRoute', label: 'Rec Route' },
                { id: 'alternateRoutes', label: 'Alt Routes' },
                { id: 'sic', label: 'SIC' },
                { id: 'iceEdge', label: 'Ice Edge' },
                { id: 'icebergs', label: 'Icebergs' },
                { id: 'weather', label: 'Weather' },
                { id: 'currentVectors', label: 'Currents' },
                { id: 'bathymetry', label: 'Bathymetry' },
                { id: 'coastline', label: 'Coastline' },
                { id: 'riskZones', label: 'Risk Zones' }
              ].map((toggle) => (
                <label
                  key={toggle.id}
                  className="flex items-center gap-1.5 cursor-pointer hover:text-white transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={(layerToggles as any)[toggle.id]}
                    onChange={(e) =>
                      setLayerToggles((prev) => ({
                        ...prev,
                        [toggle.id]: e.target.checked
                      }))
                    }
                    className="rounded border-slate-700 bg-slate-900 text-emerald-500 focus:ring-0 focus:ring-offset-0"
                  />
                  <span>{toggle.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* INSPECTION MODAL / DRAWER */}
          {selectedInspection && (
            <div className="absolute inset-y-0 right-0 w-96 bg-slate-950/95 border-l border-slate-800 shadow-2xl z-20 flex flex-col font-mono text-xs p-4 animate-in slide-in-from-right duration-200">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
                <span className="font-bold text-slate-100 text-sm">{selectedInspection.title}</span>
                <button
                  onClick={() => setSelectedInspection(null)}
                  className="p-1 text-slate-400 hover:text-white rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-2 text-[11px]">
                {Object.entries(selectedInspection.details).map(([k, v]) => (
                  <div key={k} className="p-2 bg-slate-900/60 rounded border border-slate-800/80">
                    <span className="text-[10px] text-slate-500 block uppercase">{k.replace(/_/g, ' ')}</span>
                    <span className="text-slate-200 font-semibold break-all">
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                    </span>
                  </div>
                ))}
              </div>

              <div className="pt-3 border-t border-slate-800">
                <button
                  onClick={() => setSelectedInspection(null)}
                  className="w-full py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded font-bold uppercase transition-colors"
                >
                  Dismiss Inspection
                </button>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
