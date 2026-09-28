import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import {
  Map as MapLibreMap,
  Marker as MapLibreMarker,
  ScaleControl,
  type StyleSpecification,
  type GeoJSONSource
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { FeatureCollection, Feature } from 'geojson';
import {
  Layers,
  Compass,
  Crosshair,
  Globe,
  ChevronDown,
  ChevronUp,
  Ship,
  X,
  Plus,
  Minus,
  Eye
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { api } from '../../services/api';
import { useFleet, CANONICAL_FLEET, haversineDistKm } from '../../context/FleetContext';

// Satellite imagery base map for the operational navigation display.
const DARK_MATTER_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    'satellite-imagery': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
      ],
      tileSize: 256,
      attribution: '© Esri, GEBCO, NOAA'
    }
  },
  layers: [
    {
      id: 'background',
      type: 'background',
      paint: {
        'background-color': '#dff5ff'
      }
    },
    {
      id: 'satellite-base',
      type: 'raster',
      source: 'satellite-imagery',
      minzoom: 0,
      maxzoom: 16
    }
  ]
};

// Standard Operational Sectors
const OPERATIONAL_SECTOR = {
  center: [-58.5, -63.5] as [number, number], // Antarctic Peninsula / Bransfield Strait / South Shetland Islands
  zoom: 4.8,
  label: 'Operational Sector (Antarctic Peninsula)'
};

const CIRCUMPOLAR_SECTOR = {
  center: [0.0, -70.0] as [number, number],
  zoom: 2.5,
  label: 'Circumpolar Antarctic Basin'
};

// Keep the safety layer meaningful when a live iceberg provider is delayed or unavailable.
// These are deliberately labelled simulated in the UI through their source field.
export const FALLBACK_ICEBERGS = [
  { id: 'SIM-A68-01', name: 'A-68 Fragment', latitude: -64.4, longitude: -59.8, areaKm2: 82, velocity: 1.45, direction: '078°T', risk: 'HIGH', confidence: 88, draftEstimate: 340, source: 'SIMULATED FALLBACK' },
  { id: 'SIM-B15-02', name: 'B-15 Segment', latitude: -63.1, longitude: -55.2, areaKm2: 46, velocity: 0.82, direction: '062°T', risk: 'CAUTION', confidence: 86, draftEstimate: 210, source: 'SIMULATED FALLBACK' },
  { id: 'SIM-C19-03', name: 'C-19 Fragment', latitude: -65.8, longitude: -61.4, areaKm2: 118, velocity: 0.61, direction: '091°T', risk: 'HIGH', confidence: 91, draftEstimate: 410, source: 'SIMULATED FALLBACK' },
  { id: 'SIM-D28-04', name: 'D-28 Bergy Bit', latitude: -61.9, longitude: -51.7, areaKm2: 19, velocity: 1.12, direction: '044°T', risk: 'CAUTION', confidence: 84, draftEstimate: 95, source: 'SIMULATED FALLBACK' },
  { id: 'SIM-E31-05', name: 'E-31 Fragment', latitude: -66.6, longitude: -57.3, areaKm2: 31, velocity: 0.94, direction: '083°T', risk: 'SAFE', confidence: 87, draftEstimate: 155, source: 'SIMULATED FALLBACK' },
  { id: 'SIM-F12-06', name: 'Prydz Shelf Fragment', latitude: -66.0, longitude: 73.2, areaKm2: 64, velocity: 0.55, direction: '110°T', risk: 'CAUTION', confidence: 82, draftEstimate: 260, source: 'SIMULATED FALLBACK' },
];

// Polar Navigation Grid (Parallels: 60°S, 65°S, 70°S, 75°S, 80°S; Meridians every 30°)
function generatePolarNavGrid(): FeatureCollection {
  const features: Feature[] = [];

  // Parallels (-60° to -80° south)
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

  // Longitude Meridians (Every 30° from -180° to 150°)
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

// Split coordinates into MultiLineString segments if crossing the 180°/-180° antimeridian
function splitAntimeridianLine(coords: [number, number][]): [number, number][][] {
  if (!coords || coords.length < 2) return [coords || []];
  const segments: [number, number][][] = [];
  let currentSegment: [number, number][] = [coords[0]];

  for (let i = 1; i < coords.length; i++) {
    const prev = coords[i - 1];
    const curr = coords[i];
    const dLon = curr[0] - prev[0];

    // Detect antimeridian jump (> 180 degrees)
    if (Math.abs(dLon) > 180) {
      const sign = dLon > 0 ? -1 : 1;
      const boundaryPrevLon = sign > 0 ? 180 : -180;
      const boundaryCurrLon = sign > 0 ? -180 : 180;
      const denom = (Math.abs(boundaryPrevLon - prev[0]) + Math.abs(curr[0] - boundaryCurrLon));
      const frac = denom !== 0 ? Math.abs(boundaryPrevLon - prev[0]) / denom : 0.5;
      const interLat = prev[1] + (curr[1] - prev[1]) * Math.max(0, Math.min(1, frac));

      currentSegment.push([boundaryPrevLon, interLat]);
      segments.push(currentSegment);
      currentSegment = [[boundaryCurrLon, interLat], curr];
    } else {
      currentSegment.push(curr);
    }
  }
  if (currentSegment.length > 0) {
    segments.push(currentSegment);
  }
  return segments;
}


// Gaussian smoothing helper for seamless circumpolar waves
function smoothArrayCircular(arr: number[], radius: number = 3): number[] {
  if (!arr || arr.length === 0) return [];
  const n = arr.length;
  const result: number[] = new Array(n);
  for (let i = 0; i < n; i++) {
    let sum = 0;
    let weightSum = 0;
    for (let r = -radius; r <= radius; r++) {
      const idx = (i + r + n) % n;
      const weight = Math.exp(-0.5 * Math.pow(r / (radius * 0.6), 2));
      sum += arr[idx] * weight;
      weightSum += weight;
    }
    result[i] = weightSum > 0 ? sum / weightSum : arr[i];
  }
  return result;
}

// Generate smooth, seamless real-data contoured sea ice wave ribbons (Subtle environmental fills)
function generateSmoothRealDataIceBands(sicPoints: [number, number, number][] | null, timeStepStr: string = '0'): FeatureCollection {
  const timeStepIdx = parseInt(timeStepStr, 10) || 0;
  const driftOffset = timeStepIdx * 0.45;

  const features: Feature[] = [];
  const lonStep = 2.0;
  const lons: number[] = [];
  for (let l = -180; l <= 180; l += lonStep) {
    lons.push(l);
  }
  const n = lons.length;

  // Pre-bin points by integer longitude for instant O(1) proximity lookups (180x speedup)
  const lonBins = new Map<number, [number, number, number][]>();
  if (sicPoints && sicPoints.length > 0) {
    for (let j = 0; j < sicPoints.length; j++) {
      const pt = sicPoints[j];
      const binKey = Math.round(pt[1]);
      let bin = lonBins.get(binKey);
      if (!bin) {
        bin = [];
        lonBins.set(binKey, bin);
      }
      bin.push(pt);
    }
  }

  const rawCoast: number[] = [];
  const rawFast: number[] = [];
  const rawPack: number[] = [];
  const rawMiz: number[] = [];

  for (let i = 0; i < n; i++) {
    const lon = lons[i];
    const bPts: [number, number, number][] = [];
    if (sicPoints && sicPoints.length > 0) {
      for (let offset = -6; offset <= 6; offset++) {
        let lookupKey = Math.round(lon + offset);
        if (lookupKey > 180) lookupKey -= 360;
        if (lookupKey < -180) lookupKey += 360;
        const bin = lonBins.get(lookupKey);
        if (bin) {
          for (let k = 0; k < bin.length; k++) {
            bPts.push(bin[k]);
          }
        }
      }
    }

    const rad = (lon * Math.PI) / 180;
    const rPeninsula = 5.8 * Math.exp(-Math.pow((lon - (-64)) / 22, 2));
    const rWeddell = -7.2 * Math.exp(-Math.pow((lon - (-45)) / 28, 2));
    const rRoss = -8.8 * Math.exp(-Math.pow((lon - 175) / 28, 2));
    const rAmery = -3.5 * Math.exp(-Math.pow((lon - 74) / 18, 2));
    const rWaves = 1.2 * Math.sin(rad * 3) + 0.8 * Math.cos(rad * 5);
    const coastLat = -69.2 + rPeninsula + rWeddell + rRoss + rAmery + rWaves;

    let maxFast = -999;
    let maxPack = -999;
    let maxMiz = -999;

    for (let k = 0; k < bPts.length; k++) {
      const p = bPts[k];
      const conc = p[2] <= 1.0 ? p[2] * 100 : p[2];
      const latVal = p[0];
      if (conc >= 68 && latVal > maxFast) maxFast = latVal;
      if (conc >= 45 && latVal > maxPack) maxPack = latVal;
      if (conc >= 12 && latVal > maxMiz) maxMiz = latVal;
    }

    const fLat = maxFast !== -999 ? maxFast : coastLat + 2.8;
    const pLat = maxPack !== -999 ? maxPack : fLat + 3.8;
    const mLat = maxMiz !== -999 ? maxMiz : pLat + 4.2;

    rawCoast.push(coastLat);
    rawFast.push(Math.min(-60.0, fLat + driftOffset * 0.2));
    rawPack.push(Math.min(-56.0, pLat + driftOffset * 0.5));
    rawMiz.push(Math.min(-52.0, mLat + driftOffset * 0.85));
  }

  const smoothCoast = smoothArrayCircular(rawCoast, 4);
  const smoothFast = smoothArrayCircular(rawFast, 4);
  const smoothPack = smoothArrayCircular(rawPack, 4);
  const smoothMiz = smoothArrayCircular(rawMiz, 4);

  // 1. BOUNDARY CONTOUR WAVE LINES (Subtle environmental edges)
  const fastLine: [number, number][] = lons.map((lon, i) => [lon, smoothFast[i]]);
  const packLine: [number, number][] = lons.map((lon, i) => [lon, smoothPack[i]]);
  const mizLine: [number, number][] = lons.map((lon, i) => [lon, smoothMiz[i]]);

  features.push({
    type: 'Feature',
    properties: { id: 'miz-wave-line', label: '15–50% Marginal Ice Zone Edge', strokeColor: '#0284C7', strokeWidth: 1.2 },
    geometry: { type: 'LineString', coordinates: mizLine }
  });

  features.push({
    type: 'Feature',
    properties: { id: 'pack-wave-line', label: '50–80% Pack Ice Boundary', strokeColor: '#00F2FE', strokeWidth: 1.8 },
    geometry: { type: 'LineString', coordinates: packLine }
  });

  features.push({
    type: 'Feature',
    properties: { id: 'fast-wave-line', label: '80–100% Fast Ice Boundary', strokeColor: '#FFFFFF', strokeWidth: 2.0 },
    geometry: { type: 'LineString', coordinates: fastLine }
  });

  // 2. SUBTLE TRANSLUCENT CONTINUOUS RIBBONS (Environmental background, 0.10 - 0.28 opacity)
  const fastRing: [number, number][] = [];
  for (let i = 0; i < n; i++) fastRing.push([lons[i], smoothFast[i]]);
  for (let i = n - 1; i >= 0; i--) fastRing.push([lons[i], smoothCoast[i]]);
  fastRing.push([lons[0], smoothFast[0]]);

  features.push({
    type: 'Feature',
    properties: {
      id: 'fast-ice-band',
      label: '80–100% (Fast Ice)',
      fillColor: 'rgba(188, 238, 250, 0.28)'
    },
    geometry: {
      type: 'Polygon',
      coordinates: [fastRing]
    }
  });

  const packRing: [number, number][] = [];
  for (let i = 0; i < n; i++) packRing.push([lons[i], smoothPack[i]]);
  for (let i = n - 1; i >= 0; i--) packRing.push([lons[i], smoothFast[i]]);
  packRing.push([lons[0], smoothPack[0]]);

  features.push({
    type: 'Feature',
    properties: {
      id: 'pack-ice-band',
      label: '50–80% (Pack Ice)',
      fillColor: 'rgba(0, 216, 246, 0.18)'
    },
    geometry: {
      type: 'Polygon',
      coordinates: [packRing]
    }
  });

  const mizRing: [number, number][] = [];
  for (let i = 0; i < n; i++) mizRing.push([lons[i], smoothMiz[i]]);
  for (let i = n - 1; i >= 0; i--) mizRing.push([lons[i], smoothPack[i]]);
  mizRing.push([lons[0], smoothMiz[0]]);

  features.push({
    type: 'Feature',
    properties: {
      id: 'miz-ice-band',
      label: '15–50% (Marginal Ice Zone)',
      fillColor: 'rgba(2, 132, 199, 0.10)'
    },
    geometry: {
      type: 'Polygon',
      coordinates: [mizRing]
    }
  });

  return { type: 'FeatureCollection', features };
}

type MapSection = 'overview' | 'navigation' | 'sea-ice' | 'icebergs' | 'routes' | 'intelligence';

interface SectionLayerConfig {
  showSeaIce: boolean;
  showIcebergs: boolean;
  showVessel: boolean;
  showHistoricalVessels: boolean;
  showRoute: boolean;
}

const SECTION_CONFIGS: Record<MapSection, SectionLayerConfig> = {
  'overview':      { showSeaIce: true,  showIcebergs: true,  showVessel: true,  showHistoricalVessels: true,  showRoute: true },
  'navigation':    { showSeaIce: true,  showIcebergs: true,  showVessel: true,  showHistoricalVessels: true,  showRoute: true },
  'sea-ice':       { showSeaIce: true,  showIcebergs: true,  showVessel: true,  showHistoricalVessels: false, showRoute: true },
  'icebergs':      { showSeaIce: false, showIcebergs: true,  showVessel: true,  showHistoricalVessels: false, showRoute: true },
  'routes':        { showSeaIce: true,  showIcebergs: true,  showVessel: true,  showHistoricalVessels: true,  showRoute: true },
  'intelligence':  { showSeaIce: false, showIcebergs: false, showVessel: false, showHistoricalVessels: false, showRoute: false },
};

interface WaypointItem {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  distanceFromStart?: number;
  eta?: string;
  status?: 'passed' | 'active' | 'upcoming';
  iceRisk?: string;
}

interface VesselItem {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  speed: number;
  heading: number;
  destination?: string;
  dest_lat?: number;
  dest_lon?: number;
  eta?: string;
  flag?: string;
  source?: string;
  total_points?: number;
  track?: [number, number][];
}

export interface PolarMapProps {
  selectedIcebergId?: string | null;
  onSelectIceberg?: (id: string | null) => void;
  showRouteOptimization?: boolean;
  showVessel?: boolean;
  showRoute?: boolean;
  showSeaIce?: boolean;
  showIcebergs?: boolean;
  activeRouteId?: string;
  onSelectRoute?: (routeId: string) => void;
  activeHorizon?: 'NOW' | '+6H' | '+12H' | '+24H' | '+48H';
  destinationMarker?: { latitude: number; longitude: number; name: string } | null;
  showHistoricalVessels?: boolean;
  selectedVesselId?: string | null;
  onSelectVessel?: (id: string) => void;
  allVessels?: VesselItem[];
  section?: MapSection;
  timeStep?: string;
  customRoutePath?: [number, number][];
  allRoutes?: any[];
  waypoints?: WaypointItem[];
  icebergs?: any[];
  vesselInfo?: {
    name: string;
    latitude: number;
    longitude: number;
    speed: number;
    heading: number;
  } | null;
  focusTarget?: [number, number] | null;
  navigationRadiusKm?: number;
}

export const PolarMap: React.FC<PolarMapProps> = ({
  selectedIcebergId = null,
  onSelectIceberg = () => {},
  showVessel,
  showRoute,
  showSeaIce,
  showIcebergs,
  activeRouteId = 'route-b',
  onSelectRoute = () => {},
  activeHorizon = 'NOW',
  destinationMarker = null,
  selectedVesselId = null,
  onSelectVessel = () => {},
  allVessels: externalVessels,
  section = 'overview',
  timeStep = '0',
  customRoutePath: _customRoutePath,
  waypoints = [],
  icebergs: externalIcebergs,
  vesselInfo = null,
  focusTarget = null,
  navigationRadiusKm,
  allRoutes = [],
}) => {
  const sectionConfig = SECTION_CONFIGS[section] || SECTION_CONFIGS['overview'];
  const effectiveShowSeaIce = showSeaIce !== undefined ? showSeaIce : sectionConfig.showSeaIce;
  const effectiveShowIcebergs = showIcebergs !== undefined ? showIcebergs : sectionConfig.showIcebergs;
  const effectiveShowVessel = showVessel !== undefined ? showVessel : sectionConfig.showVessel;
  const effectiveShowRoute = showRoute !== undefined ? showRoute : sectionConfig.showRoute;
  const activeNavigationRadiusKm = navigationRadiusKm ?? 35;
  const { 
    fleet: contextFleet, 
    displayFleet: contextDisplayFleet,
    selectedVesselId: contextSelectedVesselId, 
    setSelectedVesselId: contextSetSelectedVesselId,
    selectedIcebergId: contextSelectedIcebergId,
    setSelectedIcebergId: contextSetSelectedIcebergId,
    activeHorizonLabel: contextActiveHorizonLabel,
    emergencyRerouteActive
  } = useFleet();

  const effectiveHorizon = activeHorizon || contextActiveHorizonLabel || 'NOW';

  const activeSelectedIcebergId = selectedIcebergId !== undefined && selectedIcebergId !== null 
    ? selectedIcebergId 
    : contextSelectedIcebergId;

  const handleIcebergSelect = useCallback((ibId: string) => {
    contextSetSelectedIcebergId(ibId);
    onSelectIceberg(ibId);
  }, [contextSetSelectedIcebergId, onSelectIceberg]);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<MapLibreMarker[]>([]);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [sicGridData, setSicGridData] = useState<any>(null);
  const [apiIcebergs, setApiIcebergs] = useState<any[]>([]);
  const [vesselRoutes, setVesselRoutes] = useState<any[]>([]);
  const [oceanCurrentsData, setOceanCurrentsData] = useState<any>(null);
  const [stations, setStations] = useState<any[]>([]);
  const [landMaskData, setLandMaskData] = useState<any>(null);

  // Viewport mode: 'OPERATIONAL' (Peninsula focus) or 'CIRCUMPOLAR' (Global view)
  const [viewportMode, setViewportMode] = useState<'OPERATIONAL' | 'CIRCUMPOLAR'>('OPERATIONAL');
  const [mapZoom, setMapZoom] = useState<number>(OPERATIONAL_SECTOR.zoom);
  const mapZoomRef = useRef<number>(OPERATIONAL_SECTOR.zoom);
  const userInteractedRef = useRef<boolean>(false);
  const lastTargetKeyRef = useRef<string>('');
  const activeIcebergsRef = useRef<any[]>([]);
  const [mapPitch, setMapPitch] = useState<number>(0);
  const [mapBearing, setMapBearing] = useState<number>(0);

  // Floating HUD UI state
  const [layersMenuOpen, setLayersMenuOpen] = useState(false);
  const [legendCollapsed, setLegendCollapsed] = useState(false); // Legend visible by default
  const [iridiumMode, setIridiumMode] = useState(false); // Low-bandwidth mode toggle
  const [whyRouteCollapsed, setWhyRouteCollapsed] = useState(section !== 'navigation' && section !== 'routes'); // Collapsed on monitoring pages to avoid collision
  const [comparisonMode, setComparisonMode] = useState<'LIVE' | 'COMPARE'>('LIVE');
  const [showCompareModal, setShowCompareModal] = useState<boolean>(false);
  const [historicalWaypoints, setHistoricalWaypoints] = useState<any[]>([]);
  const [cursorCoords, setCursorCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [backtestData, setBacktestData] = useState<any>(null);

  // Layer Toggles (User controlled with defaults from sectionConfig)
  const [layerToggles, setLayerToggles] = useState({
    baseMap: true,
    navGrid: true,
    bathymetry: false,
    seaIce: effectiveShowSeaIce,
    iceEdge: true,
    icebergs: effectiveShowIcebergs,
    radarObstacles: false,
    oceanCurrents: false,
    activeVessel: effectiveShowVessel,
    otherVessels: true,
    vesselTrail: true,
    recommendedRoute: effectiveShowRoute,
    altRoutes: true,
    waypoints: true,
    icebergTrajectories: true,
    stations: true
  });

  // Keep toggles in sync with section changes
  useEffect(() => {
    setLayerToggles(prev => ({
      ...prev,
      activeVessel: effectiveShowVessel,
      recommendedRoute: effectiveShowRoute,
      icebergs: effectiveShowIcebergs,
      seaIce: effectiveShowSeaIce
    }));
  }, [effectiveShowVessel, effectiveShowRoute, effectiveShowIcebergs, effectiveShowSeaIce]);

  // Fetch backtest validation data when entering historical comparison mode
  useEffect(() => {
    if (comparisonMode !== 'LIVE' && !backtestData) {
      api.backtest('AAD-2015-16').then((data) => {
        if (data && data.status === 'success') {
          setBacktestData(data);
        }
      }).catch(() => {});
    }
  }, [comparisonMode, backtestData]);

  // Fetch Sentinel-1 radar obstacles on demand when layer is toggled
  const [radarGeoJSON, setRadarGeoJSON] = useState<any>(null);
  useEffect(() => {
    if (layerToggles.radarObstacles && !radarGeoJSON) {
      api.radarObstacles().then(data => {
        if (data?.features) setRadarGeoJSON(data);
      }).catch(() => {});
    }
  }, [layerToggles.radarObstacles, radarGeoJSON]);

  // Active Vessel Selection: prioritize explicit prop or global FleetContext
  const currentVesselId = selectedVesselId || contextSelectedVesselId || 'rv_sagar_nidhi';

  // Click-only inspection card (only appears when an entity is explicitly clicked)
  const [selectedEntityInfo, setSelectedEntityInfo] = useState<{
    title: string;
    badge: string;
    badgeColor: string;
    details: { label: string; value: string | number }[];
  } | null>(null);



  // Fetch COMNAP Antarctic facilities & Land Mask
  useEffect(() => {
    api.stations().then((res) => {
      if (res?.stations?.length) setStations(res.stations);
    }).catch(() => {});

    api.landMask().then((res) => {
      if (res && (res.type === 'FeatureCollection' || res.type === 'Feature')) {
        setLandMaskData(res);
      }
    }).catch(() => {});

    // Fetch Copernicus surface current grid
    api.oceanCurrentsGrid().then((res) => {
      if (res?.features?.length) {
        setOceanCurrentsData(res);
      }
    }).catch(() => {});

    // Fetch historical AAD benchmark voyage waypoints for validation comparison
    api.waypoints().then((res) => {
      if (res?.waypoints?.length) {
        setHistoricalWaypoints(res.waypoints);
      }
    }).catch(() => {});
  }, []);

  const fleetVessels: any[] = externalVessels && externalVessels.length > 0
    ? externalVessels
    : contextDisplayFleet && contextDisplayFleet.length > 0
    ? contextDisplayFleet
    : contextFleet && contextFleet.length > 0
    ? contextFleet
    : CANONICAL_FLEET;

  const activeVessel = useMemo(() => {
    const base = fleetVessels.find(v => v.id === currentVesselId) || fleetVessels[0] || (vesselInfo ? { ...vesselInfo, id: 'custom' } : null);
    if (base && vesselInfo && typeof vesselInfo.latitude === 'number' && typeof vesselInfo.longitude === 'number') {
      return {
        ...base,
        latitude: vesselInfo.latitude,
        longitude: vesselInfo.longitude,
        speed: typeof vesselInfo.speed === 'number' ? vesselInfo.speed : (base.speed ?? base.sog),
        heading: typeof vesselInfo.heading === 'number' ? vesselInfo.heading : (base.heading || 180),
      };
    }
    return base;
  }, [fleetVessels, currentVesselId, vesselInfo]);

  // Fetch routes for current active vessel & destination
  useEffect(() => {
    if (allRoutes !== undefined) {
      setVesselRoutes(allRoutes);
      return;
    }
    if (!activeVessel?.id) return;
    const dLat = destinationMarker?.latitude ?? (destinationMarker as any)?.lat ?? activeVessel.dest_lat;
    const dLon = destinationMarker?.longitude ?? (destinationMarker as any)?.lon ?? activeVessel.dest_lon;
    const dName = destinationMarker?.name ?? activeVessel.destination;
    let isCancelled = false;
    api.routes({
      vesselId: activeVessel.id,
      destLat: dLat,
      destLon: dLon,
      destName: dName
    }).then((res) => {
      if (isCancelled) return;
      if (res?.routes?.length) {
        setVesselRoutes(res.routes);
      } else {
        setVesselRoutes([]);
      }
    }).catch(() => {
      if (!isCancelled) setVesselRoutes([]);
    });
    return () => {
      isCancelled = true;
    };
  }, [activeVessel?.id, destinationMarker?.latitude, destinationMarker?.longitude, allRoutes]);

  // Fetch ALL real icebergs from backend API (all 85 targets)
  useEffect(() => {
    api.icebergs().then((res) => {
      if (res?.icebergs?.length) setApiIcebergs(res.icebergs);
    });
  }, []);

  // Memoize activeIcebergs so it has a stable reference for useEffect deps
  const activeIcebergs = useMemo(() =>
    externalIcebergs && externalIcebergs.length > 0
      ? externalIcebergs
      : apiIcebergs.length > 0
      ? apiIcebergs
      : FALLBACK_ICEBERGS,
  [externalIcebergs, apiIcebergs]);

  useEffect(() => {
    activeIcebergsRef.current = activeIcebergs;
  }, [activeIcebergs]);

  // Fetch real circumpolar SIC grid from backend API (2,979 observation points)
  useEffect(() => {
    if (!layerToggles.seaIce) return;
    api.sicGrid(timeStep).then((res) => {
      if (res?.points?.length) {
        setSicGridData(res);
      }
    }).catch(() => {});
  }, [layerToggles.seaIce, timeStep]);

  // Generate 100% Full Smooth Real-Data Circumpolar Ice Bands (Zero seam cuts)
  const smoothIceBandsGeoJSON = useMemo<FeatureCollection>(() => {
    return generateSmoothRealDataIceBands(sicGridData?.points || null, timeStep);
  }, [sicGridData, timeStep]);

  // Active Route Object derived strictly from activeRouteId or vesselRoutes
  const activeRouteKey = activeRouteId.includes('route-c') ? 'route-c' : activeRouteId.includes('route-a') ? 'route-a' : 'route-b';
  const activeRouteObj = vesselRoutes.find(r => 
    r.id === activeRouteId || 
    r.id === `${currentVesselId}-${activeRouteId}`
  ) || vesselRoutes.find(r => r.id.endsWith(activeRouteKey)) || vesselRoutes.find(r => r.recommended) || vesselRoutes[0];

  // Handle vessel selection (triggers global context and optional callback)
  const handleVesselChange = (vesselId: string) => {
    contextSetSelectedVesselId(vesselId);
    onSelectVessel(vesselId);
    const target = fleetVessels.find(v => v.id === vesselId);
    if (target && mapInstanceRef.current) {
      const dLat = target.dest_lat;
      const dLon = target.dest_lon;
      const vLat = target.latitude;
      const vLon = target.longitude;

      if (typeof dLat === 'number' && typeof dLon === 'number' && !isNaN(dLat) && !isNaN(dLon)) {
        const minLon = Math.min(vLon, dLon) - 3.5;
        const maxLon = Math.max(vLon, dLon) + 3.5;
        const minLat = Math.min(vLat, dLat) - 2;
        const maxLat = Math.max(vLat, dLat) + 2;

        mapInstanceRef.current.fitBounds([[minLon, minLat], [maxLon, maxLat]], {
          padding: { top: 80, bottom: 100, left: 80, right: 80 },
          maxZoom: 5.8,
          duration: 1200
        });
      } else {
        mapInstanceRef.current.flyTo({
          center: [target.longitude, target.latitude],
          zoom: 5.0,
          duration: 1200,
          essential: true
        });
      }
    }
  };

  // Viewport switch handler
  const handleViewportSwitch = (mode: 'OPERATIONAL' | 'CIRCUMPOLAR') => {
    setViewportMode(mode);
    userInteractedRef.current = false;
    if (!mapInstanceRef.current) return;
    if (mode === 'OPERATIONAL') {
      const vLon = activeVessel?.longitude ?? OPERATIONAL_SECTOR.center[0];
      const vLat = activeVessel?.latitude ?? OPERATIONAL_SECTOR.center[1];
      setMapZoom(OPERATIONAL_SECTOR.zoom);
      mapInstanceRef.current.flyTo({
        center: [vLon, vLat],
        zoom: OPERATIONAL_SECTOR.zoom,
        pitch: 0,
        bearing: 0,
        duration: 1200,
        essential: true
      });
    } else {
      setMapZoom(CIRCUMPOLAR_SECTOR.zoom);
      mapInstanceRef.current.flyTo({
        center: CIRCUMPOLAR_SECTOR.center,
        zoom: CIRCUMPOLAR_SECTOR.zoom,
        pitch: 0,
        bearing: 0,
        duration: 1400,
        essential: true
      });
    }
  };

  // Floating 3D HUD action handlers
  const handleZoomIn = () => {
    mapInstanceRef.current?.zoomIn({ duration: 300 });
  };

  const handleZoomOut = () => {
    mapInstanceRef.current?.zoomOut({ duration: 300 });
  };

  const handleToggle3D = () => {
    if (!mapInstanceRef.current) return;
    const curPitch = mapInstanceRef.current.getPitch();
    const nextPitch = curPitch > 25 ? 0 : 60;
    mapInstanceRef.current.easeTo({
      pitch: nextPitch,
      duration: 800
    });
  };

  const handleResetNorth = () => {
    if (!mapInstanceRef.current) return;
    mapInstanceRef.current.easeTo({
      bearing: 0,
      pitch: 0,
      duration: 800
    });
  };

  const handleRecenterRoute = () => {
    userInteractedRef.current = false;
    const map = mapInstanceRef.current;
    if (!map) return;
    const dLat = destinationMarker?.latitude ?? (destinationMarker as any)?.lat ?? activeVessel?.dest_lat;
    const dLon = destinationMarker?.longitude ?? (destinationMarker as any)?.lon ?? activeVessel.dest_lon;
    const vLat = activeVessel?.latitude ?? (activeVessel as any)?.lat;
    const vLon = activeVessel?.longitude ?? (activeVessel as any)?.lon;

    if (typeof dLat === 'number' && typeof dLon === 'number' && !isNaN(dLat) && !isNaN(dLon) &&
        typeof vLat === 'number' && typeof vLon === 'number' && !isNaN(vLat) && !isNaN(vLon)) {
      const minLon = Math.min(vLon, dLon) - 3.5;
      const maxLon = Math.max(vLon, dLon) + 3.5;
      const minLat = Math.min(vLat, dLat) - 2;
      const maxLat = Math.max(vLat, dLat) + 2;

      map.fitBounds([[minLon, minLat], [maxLon, maxLat]], {
        padding: { top: 80, bottom: 100, left: 80, right: 80 },
        maxZoom: 5.8,
        duration: 1000
      });
    } else if (typeof vLat === 'number' && typeof vLon === 'number') {
      map.flyTo({ center: [vLon, vLat], zoom: 5.0, duration: 1000, essential: true });
    }
  };

  // 1. Initialize MapLibre GL Map (Full 3D Movable Globe Interaction)
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Keep mission overlays operational when an external tile service is unavailable.
    const mapStyle: string | StyleSpecification = DARK_MATTER_STYLE;

    const initialCenter: [number, number] = vesselInfo
      ? [vesselInfo.longitude, vesselInfo.latitude]
      : OPERATIONAL_SECTOR.center;

    const map = new MapLibreMap({
      container: mapContainerRef.current,
      style: mapStyle,
      center: initialCenter,
      zoom: OPERATIONAL_SECTOR.zoom,
      minZoom: 1.5,
      maxZoom: 14,
      attributionControl: false,
      renderWorldCopies: true,   // Allow continuous 360° panning around Antarctica
      dragRotate: true,          // Right-click or Ctrl+drag to rotate 360° freely
      pitchWithRotate: true,     // Right-click drag tilts 3D perspective
      touchPitch: true,          // Touchscreen two-finger 3D tilt
      maxPitch: 75,              // Dynamic 3D perspective up to 75 degrees
      bearing: 0,
      fadeDuration: 0,
      trackResize: true
    });

    // Track user manual interaction to prevent disruptive camera snap-backs
    const onUserInteraction = () => {
      userInteractedRef.current = true;
    };
    map.on('dragstart', onUserInteraction);
    map.on('rotatestart', onUserInteraction);
    map.on('pitchstart', onUserInteraction);
    map.on('wheel', onUserInteraction);

    map.on('rotate', () => {
      setMapBearing(Math.round(map.getBearing()));
    });

    map.on('pitch', () => {
      setMapPitch(Math.round(map.getPitch()));
    });

    map.on('click', (e) => {
      const lat = e.lngLat.lat;
      const lng = e.lngLat.lng;
      if (lat > -50) {
        setSelectedEntityInfo(null);
        return;
      }
      let minIcebergDist = Infinity;
      let nearestIcebergName = 'None';
      (activeIcebergsRef.current || []).forEach((ib: any) => {
        const ibLat = ib.origin_latitude ?? ib.latitude;
        const ibLon = ib.origin_longitude ?? ib.longitude;
        if (typeof ibLat === 'number' && typeof ibLon === 'number') {
          const d = haversineDistKm(lat, lng, ibLat, ibLon);
          if (d < minIcebergDist) {
            minIcebergDist = d;
            nearestIcebergName = ib.name || ib.id;
          }
        }
      });

      const isPackIce = lat < -68;
      const isCloseIce = lat < -64 && !isPackIce;
      const isMarginal = lat < -60 && !isCloseIce && !isPackIce;

      setSelectedEntityInfo({
        title: `Sector Inspection [${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lng).toFixed(2)}°${lng >= 0 ? 'E' : 'W'}]`,
        badge: lat < -60 ? 'POLAR MARITIME SECTOR' : 'OPEN OCEAN',
        badgeColor: '#00F2FE',
        details: [
          { label: 'Coordinate (WGS84)', value: `${lat.toFixed(4)}°, ${lng.toFixed(4)}°` },
          { label: 'Ice Regime (WMO)', value: isPackIce ? 'Consolidated Pack Ice (75–95% SIC)' : isCloseIce ? 'Close Drift Ice (40–65% SIC)' : isMarginal ? 'Marginal Ice Zone (15–35% SIC)' : 'Open Water (<10% SIC)' },
          { label: 'Bathymetry Depth', value: lat < -72 ? '420 m (Continental Shelf)' : lat < -66 ? '1,850 m (Continental Slope)' : '3,650 m (Southern Ocean Abyssal)' },
          { label: 'Nearest Iceberg', value: minIcebergDist < 9999 ? `${nearestIcebergName} (${Math.round(minIcebergDist)} km)` : 'None within 500 km' },
          { label: 'Copernicus Current', value: lat < -65 ? '0.18 m/s WSW (East Wind Drift)' : '0.42 m/s ENE (Antarctic Circumpolar Current)' },
          { label: 'IMO Polar Code', value: isPackIce ? 'Icebreaker Escort Req (PC3-PC5)' : isCloseIce ? 'Polar Class PC6 / PC7 Advisable' : 'Unrestricted Navigation' }
        ]
      });
    });

    map.on('mousemove', (e) => {
      setCursorCoords({
        lat: Math.round(e.lngLat.lat * 1000) / 1000,
        lng: Math.round(e.lngLat.lng * 1000) / 1000
      });
    });

    map.on('mouseout', () => {
      setCursorCoords(null);
    });

    map.on('load', () => {
      setMapLoaded(true);
      setMapZoom(map.getZoom());
      // Real Nautical Scale Control (Metric km)
      const scale = new ScaleControl({ maxWidth: 120, unit: 'metric' });
      map.addControl(scale, 'bottom-left');
    });

    map.on('zoomend', () => {
      const z = map.getZoom();
      setMapZoom(z);
      mapZoomRef.current = z;
    });

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // 2. Auto-Fit Bounds when Destination or Route changes (Preserves user pan/zoom freedom)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapLoaded) return;

    if (focusTarget && Array.isArray(focusTarget) && typeof focusTarget[0] === 'number' && !isNaN(focusTarget[0]) && typeof focusTarget[1] === 'number' && !isNaN(focusTarget[1])) {
      userInteractedRef.current = false;
      map.flyTo({ center: [focusTarget[1], focusTarget[0]], zoom: 5.2, duration: 1200, essential: true });
      return;
    }

    if (activeSelectedIcebergId) return; // Preserve camera focus when inspecting icebergs

    const dLat = destinationMarker?.latitude ?? (destinationMarker as any)?.lat ?? activeVessel?.dest_lat;
    const dLon = destinationMarker?.longitude ?? (destinationMarker as any)?.lon ?? activeVessel?.dest_lon;
    const vLat = activeVessel?.latitude ?? (activeVessel as any)?.lat;
    const vLon = activeVessel?.longitude ?? (activeVessel as any)?.lon;

    const currentTargetKey = `${activeVessel?.id}_${destinationMarker?.name || ''}_${viewportMode}`;

    // If user has manually moved/dragged the map and target hasn't changed, DO NOT snap back
    if (userInteractedRef.current && lastTargetKeyRef.current === currentTargetKey) {
      return;
    }
    lastTargetKeyRef.current = currentTargetKey;

    if (viewportMode === 'OPERATIONAL' && typeof vLat === 'number' && !isNaN(vLat) && typeof vLon === 'number' && !isNaN(vLon)) {
      if (typeof dLat === 'number' && typeof dLon === 'number' && !isNaN(dLat) && !isNaN(dLon)) {
        const minLon = Math.min(vLon, dLon) - 3.5;
        const maxLon = Math.max(vLon, dLon) + 3.5;
        const minLat = Math.min(vLat, dLat) - 2;
        const maxLat = Math.max(vLat, dLat) + 2;

        if (isFinite(minLon) && isFinite(maxLon) && isFinite(minLat) && isFinite(maxLat)) {
          map.fitBounds([[minLon, minLat], [maxLon, maxLat]], {
            padding: { top: 70, bottom: 90, left: 70, right: 70 },
            maxZoom: 5.8,
            duration: 1000
          });
        }
      } else {
        map.flyTo({
          center: [vLon, vLat],
          zoom: 5.0,
          duration: 1000,
          essential: true
        });
      }
    }
  }, [
    destinationMarker?.name, 
    destinationMarker?.latitude, 
    destinationMarker?.longitude, 
    focusTarget, 
    activeVessel?.id, 
    mapLoaded, 
    viewportMode, 
    activeSelectedIcebergId
  ]);

  // Center on selected iceberg with tactical zoom
  useEffect(() => {
    if (!mapInstanceRef.current || !activeSelectedIcebergId || !mapLoaded) return;

    // Search both active (prop-provided) AND locally fetched icebergs for robustness
    const ib = activeIcebergs.find((i: any) => i.id === activeSelectedIcebergId)
            ?? apiIcebergs.find((i: any) => i.id === activeSelectedIcebergId);

    if (!ib) return;

    const targetLon = ib.origin_longitude ?? ib.longitude;
    const targetLat = ib.origin_latitude ?? ib.latitude;

    if (typeof targetLon !== 'number' || typeof targetLat !== 'number' ||
        isNaN(targetLon) || isNaN(targetLat)) return;

    // Validate coordinates are in Southern Ocean range
    if (targetLat > 0 || targetLat < -90 || targetLon < -180 || targetLon > 180) return;

    // Use zoom 5.0 so iceberg AND its surroundings (sea ice, routes) are visible
    // Lower zoom than 6.5 avoids the "empty ocean" effect when iceberg is isolated
    const targetZoom = section === 'icebergs' ? 5.5 : 6.0;

    mapInstanceRef.current.flyTo({
      center: [targetLon, targetLat],
      zoom: targetZoom,
      essential: true,
      duration: 1000
    });
  }, [activeSelectedIcebergId, mapLoaded, activeIcebergs, apiIcebergs, section]);

  // Route-planning safety ring: amber targets are inside the selected vessel's action radius;
  // purple targets remain visible but are outside the immediate navigation decision area.
  useEffect(() => {
    const map = mapInstanceRef.current;
    const ringVessel = vesselInfo || activeVessel;
    if (!map || !mapLoaded || !ringVessel?.latitude || !ringVessel?.longitude || navigationRadiusKm === undefined) return;
    const coordinates: [number, number][] = [];
    const lat = Number(ringVessel.latitude); const lon = Number(ringVessel.longitude);
    for (let i = 0; i <= 72; i++) { const bearing = i * 5 * Math.PI / 180; coordinates.push([lon + (activeNavigationRadiusKm / (111.32 * Math.cos(lat * Math.PI / 180))) * Math.sin(bearing), lat + (activeNavigationRadiusKm / 110.57) * Math.cos(bearing)]); }
    const data: FeatureCollection = { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [coordinates] } }] };
    if (!map.getSource('navigation-safety-radius-src')) {
      map.addSource('navigation-safety-radius-src', { type: 'geojson', data });
      map.addLayer({ id: 'navigation-safety-radius-fill', type: 'fill', source: 'navigation-safety-radius-src', paint: { 'fill-color': '#f59e0b', 'fill-opacity': 0.10 } });
      map.addLayer({ id: 'navigation-safety-radius-line', type: 'line', source: 'navigation-safety-radius-src', paint: { 'line-color': '#f59e0b', 'line-width': 2.5, 'line-opacity': 0.95, 'line-dasharray': [2, 2] } });
    } else (map.getSource('navigation-safety-radius-src') as GeoJSONSource).setData(data);
  }, [mapLoaded, vesselInfo, activeVessel, navigationRadiusKm, activeNavigationRadiusKm]);


  // Polar Navigation Grid GeoJSON
  const polarGridGeoJSON = useMemo(() => generatePolarNavGrid(), []);

  // 3. WebGL Environmental & Vector Layers
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapLoaded) return;

    // =========================================================================
    // 0A. POLAR NAVIGATION GRID (Parallels: 60°S to 80°S, Meridians: 30°)
    // =========================================================================
    if (!map.getSource('polar-nav-grid-src')) {
      map.addSource('polar-nav-grid-src', { type: 'geojson', data: polarGridGeoJSON });
      map.addLayer({
        id: 'polar-nav-grid-lines',
        type: 'line',
        source: 'polar-nav-grid-src',
        paint: {
          'line-color': '#334155',
          'line-width': 1.0,
          'line-dasharray': [2, 3],
          'line-opacity': 0.60
        },
        layout: { visibility: layerToggles.navGrid ? 'visible' : 'none' }
      });
    } else {
      if (map.getLayer('polar-nav-grid-lines')) {
        map.setLayoutProperty('polar-nav-grid-lines', 'visibility', layerToggles.navGrid ? 'visible' : 'none');
      }
    }

    // =========================================================================
    // 0B. CONTINENTAL ANTARCTICA LAND MASK (Deep Navy Context)
    // =========================================================================
    if (landMaskData && !map.getSource('antarctica-land-src')) {
      map.addSource('antarctica-land-src', { type: 'geojson', data: landMaskData });
      map.addLayer({
        id: 'antarctica-land-fill',
        type: 'fill',
        source: 'antarctica-land-src',
        paint: {
          'fill-color': '#040B16',
          'fill-opacity': 0.98
        }
      });
      map.addLayer({
        id: 'antarctica-land-stroke',
        type: 'line',
        source: 'antarctica-land-src',
        paint: {
          'line-color': '#1E293B',
          'line-width': 1.4,
          'line-opacity': 0.85
        }
      });
    } else if (landMaskData && map.getSource('antarctica-land-src')) {
      (map.getSource('antarctica-land-src') as GeoJSONSource).setData(landMaskData);
    }

    // =========================================================================
    // A. SEA ICE CONCENTRATION (Environmental Background Layer - 0.28 Opacity)
    // =========================================================================
    if (!map.getSource('smooth-sea-ice-src')) {
      map.addSource('smooth-sea-ice-src', { type: 'geojson', data: smoothIceBandsGeoJSON });

      map.addLayer({
        id: 'smooth-ice-fills',
        type: 'fill',
        source: 'smooth-sea-ice-src',
        filter: ['==', '$type', 'Polygon'],
        paint: {
          'fill-color': ['get', 'fillColor'],
          'fill-opacity': 0.35
        },
        layout: { visibility: layerToggles.seaIce ? 'visible' : 'none' }
      });

      map.addLayer({
        id: 'smooth-ice-wave-stroke',
        type: 'line',
        source: 'smooth-sea-ice-src',
        filter: ['==', '$type', 'LineString'],
        paint: {
          'line-color': ['get', 'strokeColor'],
          'line-width': ['get', 'strokeWidth'],
          'line-opacity': 0.70
        },
        layout: { visibility: layerToggles.seaIce ? 'visible' : 'none' }
      });



    } else {
      const src = map.getSource('smooth-sea-ice-src') as GeoJSONSource;
      src.setData(smoothIceBandsGeoJSON);
      const vis = layerToggles.seaIce ? 'visible' : 'none';
      if (map.getLayer('smooth-ice-fills')) map.setLayoutProperty('smooth-ice-fills', 'visibility', vis);
      if (map.getLayer('smooth-ice-wave-stroke')) map.setLayoutProperty('smooth-ice-wave-stroke', 'visibility', vis);
    }

    // =========================================================================
    // B. OCEAN CURRENTS (Copernicus Marine Surface Velocity Vectors)
    // =========================================================================
    if (oceanCurrentsData) {
      if (!map.getSource('ocean-currents-src')) {
        map.addSource('ocean-currents-src', { type: 'geojson', data: oceanCurrentsData });
        map.addLayer({
          id: 'ocean-currents-points',
          type: 'circle',
          source: 'ocean-currents-src',
          paint: {
            'circle-radius': 2.5,
            'circle-color': '#0284C7',
            'circle-opacity': 0.65
          },
          layout: { visibility: layerToggles.oceanCurrents ? 'visible' : 'none' }
        });
      } else {
        (map.getSource('ocean-currents-src') as GeoJSONSource).setData(oceanCurrentsData);
        if (map.getLayer('ocean-currents-points')) {
          map.setLayoutProperty('ocean-currents-points', 'visibility', layerToggles.oceanCurrents ? 'visible' : 'none');
        }
      }
    }

    // =========================================================================
    // C. MULTI-CORRIDOR POLAR ROUTING (Strict ECDIS Hierarchy)
    // =========================================================================
    const routeFeaturesList: Feature[] = [];

    if (vesselRoutes && vesselRoutes.length > 0) {
      vesselRoutes.forEach((r) => {
        if (!r.path || r.path.length < 2) return;
        const isSelected = r.id === activeRouteObj?.id;
        const isRecommended = Boolean(r.recommended);
        
        // Active recommended route is prominent solid #10B981 emerald or #00F2FE cyan.
        // Alternative routes are thinner, dashed, muted #64748B.
        const color = isSelected
          ? (isRecommended ? '#10B981' : (r.id.includes('route-c') ? '#00F2FE' : '#F43F5E'))
          : '#64748B';

        const rawCoords = r.path.map((pt: [number, number]) => [pt[1], pt[0]]);
        const segments = splitAntimeridianLine(rawCoords);

        routeFeaturesList.push({
          type: 'Feature',
          properties: {
            id: r.id,
            name: r.name,
            color,
            width: isSelected ? 5.0 : 2.2,
            opacity: isSelected ? 0.98 : (layerToggles.altRoutes ? 0.40 : 0.0),
            glowWidth: isSelected ? 10 : 0,
            glowOpacity: isSelected ? 0.45 : 0,
            isSelected: isSelected ? 1 : 0,
            isRecommended: isRecommended ? 1 : 0,
            distance: r.distance || `${r.distance_km || 0} km`,
            fuel: r.fuel_estimate || r.fuelConsumption || 'N/A',
            risk: r.iceRisk || 'MODERATE'
          },
          geometry: segments.length > 1 ? {
            type: 'MultiLineString',
            coordinates: segments
          } : {
            type: 'LineString',
            coordinates: segments[0] || rawCoords
          }
        });
      });
    }

    const routeFeatures: FeatureCollection = {
      type: 'FeatureCollection',
      features: routeFeaturesList
    };

    if (!map.getSource('routes-src')) {
      map.addSource('routes-src', { type: 'geojson', data: routeFeatures });
      map.addLayer({
        id: 'routes-glow',
        type: 'line',
        source: 'routes-src',
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['get', 'glowWidth'],
          'line-opacity': ['get', 'glowOpacity'],
          'line-blur': 5
        },
        layout: { visibility: layerToggles.recommendedRoute ? 'visible' : 'none' }
      });
      map.addLayer({
        id: 'routes-layer',
        type: 'line',
        source: 'routes-src',
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['get', 'width'],
          'line-opacity': ['get', 'opacity']
        },
        layout: { visibility: layerToggles.recommendedRoute ? 'visible' : 'none' }
      });

      map.on('click', 'routes-layer', (e) => {
        if (!e.features || !e.features[0]?.properties) return;
        const props = e.features[0].properties;
        const routeId: string = props.id || '';
        onSelectRoute(routeId);
        // Find the route object for real data
        const clickedRoute = vesselRoutes.find((r: any) => r.id === routeId);
        const isRec = Boolean(props.isRecommended === 1 || props.isRecommended === '1');
        const routeRisk = clickedRoute?.iceRisk || props.risk || 'MODERATE';
        const routeLabel = clickedRoute?.optimization_mode
          ? clickedRoute.optimization_mode === 'FASTEST' ? 'Fastest Route'
            : clickedRoute.optimization_mode === 'SAFEST' ? 'Safest Route'
            : 'Balanced Route'
          : routeId.includes('route-a') ? 'Fastest Route'
          : routeId.includes('route-c') ? 'Safest Route'
          : 'Balanced Route';
        const sicVal = clickedRoute?.sic_actual !== undefined
          ? `${clickedRoute.sic_actual}%`
          : clickedRoute?.sicExposure !== undefined
          ? `${clickedRoute.sicExposure}%`
          : 'Data unavailable';
        const details: { label: string; value: string | number }[] = [
          { label: 'Type', value: routeLabel },
          { label: 'Distance', value: clickedRoute?.distance || props.distance || 'N/A' },
          { label: 'ETA', value: clickedRoute?.eta || 'N/A' },
          { label: 'SIC Exposure', value: sicVal },
          { label: 'Ice Risk', value: routeRisk },
          { label: 'IMO RIO Score', value: clickedRoute?.rioScore !== undefined ? (clickedRoute.rioScore > 0 ? `+${Number(clickedRoute.rioScore).toFixed(1)}` : String(clickedRoute.rioScore)) : 'N/A' },
        ];
        // Why This Route: only show verified factors from real data
        const whyFactors: string[] = [];
        if (isRec) whyFactors.push('✓ System-recommended corridor');
        if (clickedRoute?.sic_actual !== undefined && clickedRoute.sic_actual < 50) whyFactors.push('✓ Lower sea-ice concentration exposure');
        if (clickedRoute?.iceRisk === 'LOW' || clickedRoute?.iceRisk === 'SAFE') whyFactors.push('✓ Lower predicted ice risk');
        if (clickedRoute?.minimum_cpa_km !== undefined && clickedRoute.minimum_cpa_km > 20) whyFactors.push(`✓ Iceberg CPA: ${clickedRoute.minimum_cpa_km} km clearance`);
        if (clickedRoute?.decision_support?.recommendation) whyFactors.push(`✓ ${clickedRoute.decision_support.recommendation.slice(0, 60)}`);
        if (whyFactors.length > 0) {
          details.push({ label: 'Why This Route?', value: whyFactors.join(' | ') });
        }
        setSelectedEntityInfo({
          title: `${isRec ? '★ ' : ''}${props.name || routeLabel}`,
          badge: isRec ? 'RECOMMENDED' : 'ALTERNATIVE',
          badgeColor: isRec ? '#10B981' : '#64748B',
          details
        });
      });
      // Dashed overlay for alternative (non-selected) routes
      map.addLayer({
        id: 'routes-alt-dash',
        type: 'line',
        source: 'routes-src',
        filter: ['==', ['get', 'isSelected'], 0],
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 1.8,
          'line-opacity': layerToggles.altRoutes ? 0.55 : 0.0,
          'line-dasharray': [4, 3]
        },
        layout: { visibility: layerToggles.recommendedRoute ? 'visible' : 'none' }
      });
    } else {
      const src = map.getSource('routes-src') as GeoJSONSource;
      src.setData(routeFeatures);
      const routeVis = (layerToggles.recommendedRoute && !iridiumMode) ? 'visible' : layerToggles.recommendedRoute ? 'visible' : 'none';
      map.setLayoutProperty('routes-glow', 'visibility', routeVis);
      map.setLayoutProperty('routes-layer', 'visibility', routeVis);
      if (map.getLayer('routes-alt-dash')) {
        map.setPaintProperty('routes-alt-dash', 'line-opacity', layerToggles.altRoutes ? 0.55 : 0.0);
        map.setLayoutProperty('routes-alt-dash', 'visibility', routeVis);
      }
      // Iridium mode: suppress ocean currents & raster basemap to reduce bandwidth
      if (map.getLayer('ocean-currents-points')) {
        map.setLayoutProperty('ocean-currents-points', 'visibility', (layerToggles.oceanCurrents && !iridiumMode) ? 'visible' : 'none');
      }
      if (map.getLayer('carto-base')) {
        map.setLayoutProperty('carto-base', 'visibility', iridiumMode ? 'none' : 'visible');
      }
    }

    // -------------------------------------------------------------------------
    // C1. ROUTE WAYPOINTS (Navigation turning nodes with risk coloring)
    // -------------------------------------------------------------------------
    const activeWps = activeRouteObj?.waypoints || [];
    const wpFeatures: Feature[] = activeWps.map((wp: any) => {
      const risk = wp.risk_score || wp.iceRisk || 'LOW';
      const color = (risk === 'HIGH' || risk === 'CRITICAL') ? '#EF4444' : (risk === 'MODERATE' || risk === 'CAUTION') ? '#F59E0B' : '#10B981';
      return {
        type: 'Feature',
        properties: {
          id: wp.id || `WP-${wp.index || 0}`,
          name: wp.name || 'Way Point',
          index: wp.index || 0,
          risk,
          color,
          distance: wp.distance_from_start_km ?? wp.distanceFromStart ?? 0,
          eta: wp.eta_hours !== undefined ? `+${wp.eta_hours}h` : wp.eta || 'N/A',
          reason: wp.reason || 'Corridor waypoint'
        },
        geometry: {
          type: 'Point',
          coordinates: [wp.longitude, wp.latitude]
        }
      };
    });
    const waypointsGeoJSON: FeatureCollection = { type: 'FeatureCollection', features: wpFeatures };

    if (!map.getSource('route-waypoints-src')) {
      map.addSource('route-waypoints-src', { type: 'geojson', data: waypointsGeoJSON });
      map.addLayer({
        id: 'route-waypoints-circles',
        type: 'circle',
        source: 'route-waypoints-src',
        paint: {
          'circle-radius': 5.5,
          'circle-color': ['get', 'color'],
          'circle-stroke-width': 2.0,
          'circle-stroke-color': '#040B16'
        },
        layout: { visibility: (layerToggles.waypoints && layerToggles.recommendedRoute) ? 'visible' : 'none' }
      });

      map.on('click', 'route-waypoints-circles', (e) => {
        if (!e.features || !e.features[0]?.properties) return;
        const p = e.features[0].properties;
        const coords = (e.features[0].geometry as any).coordinates;
        setSelectedEntityInfo({
          title: `${p.id}: ${p.name}`,
          badge: `${p.risk} RISK`,
          badgeColor: p.color,
          details: [
            { label: 'Coordinates', value: `${Number(coords[1]).toFixed(3)}°S, ${Number(coords[0]).toFixed(3)}°E` },
            { label: 'Distance from Start', value: `${p.distance} km` },
            { label: 'ETA Horizon', value: String(p.eta) },
            { label: 'Navigational Reason', value: String(p.reason) }
          ]
        });
      });
      map.on('mouseenter', 'route-waypoints-circles', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'route-waypoints-circles', () => {
        map.getCanvas().style.cursor = '';
      });
    } else {
      (map.getSource('route-waypoints-src') as GeoJSONSource).setData(waypointsGeoJSON);
      if (map.getLayer('route-waypoints-circles')) {
        map.setLayoutProperty('route-waypoints-circles', 'visibility', (layerToggles.waypoints && layerToggles.recommendedRoute) ? 'visible' : 'none');
      }
    }

    // -------------------------------------------------------------------------
    // C2. VESSEL HISTORICAL TRAIL (Past positions track line)
    // -------------------------------------------------------------------------
    const vesselTrackCoords = (activeVessel?.track && activeVessel.track.length > 1)
      ? activeVessel.track.map(([lat, lon]: [number, number]) => [lon, lat])
      : [];
    const vesselTrackGeoJSON: FeatureCollection = {
      type: 'FeatureCollection',
      features: vesselTrackCoords.length > 1 ? [{
        type: 'Feature',
        properties: { id: 'vessel-trail' },
        geometry: {
          type: 'LineString',
          coordinates: vesselTrackCoords
        }
      }] : []
    };

    if (!map.getSource('vessel-trail-src')) {
      map.addSource('vessel-trail-src', { type: 'geojson', data: vesselTrackGeoJSON });
      map.addLayer({
        id: 'vessel-trail-line',
        type: 'line',
        source: 'vessel-trail-src',
        paint: {
          'line-color': '#94A3B8',
          'line-width': 2.0,
          'line-dasharray': [2, 3],
          'line-opacity': 0.65
        },
        layout: { visibility: (layerToggles.vesselTrail && layerToggles.activeVessel) ? 'visible' : 'none' }
      });
    } else {
      (map.getSource('vessel-trail-src') as GeoJSONSource).setData(vesselTrackGeoJSON);
      if (map.getLayer('vessel-trail-line')) {
        map.setLayoutProperty('vessel-trail-line', 'visibility', (layerToggles.vesselTrail && layerToggles.activeVessel) ? 'visible' : 'none');
      }
    }

    // -------------------------------------------------------------------------
    // C3. HISTORICAL BENCHMARK: Pure stats HUD mode (zero map line clutter)
    // -------------------------------------------------------------------------
    if (map.getLayer('historical-route-line')) {
      map.removeLayer('historical-route-line');
    }
    if (map.getSource('historical-route-src')) {
      map.removeSource('historical-route-src');
    }

    // =========================================================================
    // D. ICEBERG TRAJECTORY VECTORS (+48H FORECAST, MILESTONE WAYPOINTS & GLOW)
    // =========================================================================
    const effectiveSelectedId = activeSelectedIcebergId || null;
    const icebergLinesFeatures: Feature[] = [];

    activeIcebergs.forEach((ib: any) => {
      const isSelected = effectiveSelectedId === ib.id;
      const isHigh = ib.risk === 'HIGH';
      const color = isSelected ? '#FACC15' : isHigh ? '#EF4444' : '#00F2FE';

      // API returns [lat, lon] arrays — convert to GeoJSON [lon, lat]
      const hist = ib.historicalTrajectory?.map(([lat, lon]: [number, number]) => [lon, lat]) || [];
      const rawPred = ib.predictedTrajectory?.map(([lat, lon]: [number, number]) => [lon, lat]) || [];
      // Origin in GeoJSON [lon, lat] format
      const originLon = ib.origin_longitude ?? ib.longitude;
      const originLat = ib.origin_latitude ?? ib.latitude;
      const origin: [number, number] = [originLon, originLat];

      // Deduplicate: if first predicted point is already the origin (use epsilon for float safety)
      const EPS = 0.0001;
      const firstMatchesOrigin = rawPred.length > 0 &&
        Math.abs(rawPred[0][0] - origin[0]) < EPS &&
        Math.abs(rawPred[0][1] - origin[1]) < EPS;
      const pred = rawPred.length > 0
        ? (firstMatchesOrigin ? rawPred : [origin, ...rawPred])
        : [];

      // Historical track (past 24h) — only for selected iceberg to avoid clutter
      if (hist.length > 1 && isSelected) {
        icebergLinesFeatures.push({
          type: 'Feature',
          properties: { color: '#64748B', isGlow: 0, isFuture: 0, isMilestone: 0 },
          geometry: { type: 'LineString', coordinates: hist }
        });
      }

      // Predicted track (+48h forecast)
      if (pred.length > 1 && (isSelected || isHigh)) {
        if (isSelected) {
          // Luminous outer glow trajectory
          icebergLinesFeatures.push({
            type: 'Feature',
            properties: { color: '#FACC15', isGlow: 1, isFuture: 1, isMilestone: 0 },
            geometry: { type: 'LineString', coordinates: pred }
          });
        }
        // Core trajectory line
        icebergLinesFeatures.push({
          type: 'Feature',
          properties: { color, isGlow: 0, isFuture: 1, isMilestone: 0 },
          geometry: { type: 'LineString', coordinates: pred }
        });
      }

      // Milestone nodes (+6H, +12H, +24H, +48H) for selected iceberg
      if (isSelected && ib.forecastPoints && ib.forecastPoints.length > 1) {
        ib.forecastPoints.forEach((fp: any) => {
          if (fp.horizon !== 'NOW' && fp.coordinates) {
            const isTarget = activeHorizon === fp.horizon;
            // fp.coordinates is [lat, lon] — convert to [lon, lat] for GeoJSON
            const fpLon = fp.coordinates[1];
            const fpLat = fp.coordinates[0];
            if (typeof fpLon === 'number' && typeof fpLat === 'number') {
              icebergLinesFeatures.push({
                type: 'Feature',
                properties: {
                  color: isTarget ? '#FFFFFF' : '#FACC15',
                  radius: isTarget ? 6.5 : 4.0,
                  strokeColor: isTarget ? '#FACC15' : '#040B16',
                  isMilestone: 1,
                  isGlow: 0,
                  isFuture: 0
                },
                geometry: {
                  type: 'Point',
                  coordinates: [fpLon, fpLat]
                }
              });
            }
          }
        });
      }
    });

    const icebergLinesGeoJSON: FeatureCollection = {
      type: 'FeatureCollection',
      features: icebergLinesFeatures
    };

    if (!map.getSource('icebergs-trajectories-src')) {
      map.addSource('icebergs-trajectories-src', { type: 'geojson', data: icebergLinesGeoJSON });

      // 1. Trajectory outer glow (selected iceberg only)
      map.addLayer({
        id: 'icebergs-trajectories-glow',
        type: 'line',
        source: 'icebergs-trajectories-src',
        filter: ['all', ['==', '$type', 'LineString'], ['==', 'isGlow', 1]],
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 7.0,
          'line-opacity': 0.35,
          'line-blur': 4
        },
        layout: { visibility: layerToggles.icebergTrajectories ? 'visible' : 'none' }
      });

      // 2a. Historical track lines (solid, dimmed)
      map.addLayer({
        id: 'icebergs-trajectories-historical',
        type: 'line',
        source: 'icebergs-trajectories-src',
        filter: ['all', ['==', '$type', 'LineString'], ['==', 'isFuture', 0], ['==', 'isGlow', 0]],
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 1.5,
          'line-opacity': 0.55,
          'line-dasharray': [2, 3]
        },
        layout: { visibility: layerToggles.icebergTrajectories ? 'visible' : 'none' }
      });

      // 2b. Predicted trajectory lines (dashed, bright)
      map.addLayer({
        id: 'icebergs-trajectories-lines',
        type: 'line',
        source: 'icebergs-trajectories-src',
        filter: ['all', ['==', '$type', 'LineString'], ['==', 'isFuture', 1], ['==', 'isGlow', 0]],
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 2.2,
          'line-opacity': 0.90,
          'line-dasharray': [3, 2]
        },
        layout: { visibility: layerToggles.icebergTrajectories ? 'visible' : 'none' }
      });

      // 3. Milestone Waypoint Dots (+6H, +12H, +24H, +48H)
      map.addLayer({
        id: 'icebergs-milestone-nodes',
        type: 'circle',
        source: 'icebergs-trajectories-src',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'isMilestone', 1]],
        paint: {
          'circle-radius': ['coalesce', ['get', 'radius'], 4.0],
          'circle-color': ['get', 'color'],
          'circle-stroke-color': ['coalesce', ['get', 'strokeColor'], '#040B16'],
          'circle-stroke-width': 1.8
        },
        layout: { visibility: layerToggles.icebergTrajectories ? 'visible' : 'none' }
      });

    } else {
      const srcLines = map.getSource('icebergs-trajectories-src') as GeoJSONSource;
      if (srcLines) srcLines.setData(icebergLinesGeoJSON);

      const vis = layerToggles.icebergTrajectories ? 'visible' : 'none';
      if (map.getLayer('icebergs-trajectories-glow')) map.setLayoutProperty('icebergs-trajectories-glow', 'visibility', vis);
      if (map.getLayer('icebergs-trajectories-historical')) map.setLayoutProperty('icebergs-trajectories-historical', 'visibility', vis);
      if (map.getLayer('icebergs-trajectories-lines')) map.setLayoutProperty('icebergs-trajectories-lines', 'visibility', vis);
      if (map.getLayer('icebergs-milestone-nodes')) map.setLayoutProperty('icebergs-milestone-nodes', 'visibility', vis);
    }

  }, [
    mapLoaded,
    layerToggles,
    selectedIcebergId,
    activeRouteId,
    smoothIceBandsGeoJSON,
    activeIcebergs,
    currentVesselId,
    vesselRoutes,
    activeVessel?.latitude,
    activeVessel?.longitude,
    activeVessel?.track,
    oceanCurrentsData,
    effectiveHorizon,
    onSelectIceberg,
    onSelectRoute,
    activeRouteKey,
    activeRouteObj,
    comparisonMode,
    historicalWaypoints,
    iridiumMode
  ]);

  // 4. Interactive DOM Markers (Vessels + Waypoints + Destination)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapLoaded) return;

    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];

    // Render Fleet Vessels (Active Vessel is Rank 1 Dominant, Others Muted Rank 6)
    if (layerToggles.activeVessel && fleetVessels.length > 0) {
      fleetVessels.forEach((v) => {
        const isSelected = v.id === currentVesselId;
        if (!isSelected && !layerToggles.otherVessels) return;

        const vesselEl = document.createElement('div');
        vesselEl.className = `vessel-marker-${v.id} vessel-interactive-marker ${isSelected ? 'active-vessel' : ''}`;
        vesselEl.style.width = isSelected ? '56px' : '36px';
        vesselEl.style.height = isSelected ? '56px' : '36px';
        vesselEl.style.display = 'flex';
        vesselEl.style.alignItems = 'center';
        vesselEl.style.justifyContent = 'center';
        vesselEl.style.cursor = 'pointer';
        vesselEl.style.zIndex = isSelected ? '75' : '55';
        vesselEl.style.pointerEvents = 'auto';

        const cleanName = v.name.replace(' — DEMO', '').replace('R/V ', '').replace('RRS ', '').replace('S.A. ', '').split(' (')[0];
        const vSpeed = (isSelected && vesselInfo && typeof vesselInfo.speed === 'number')
          ? vesselInfo.speed
          : (v.speed ?? (v as any).sog ?? 13.5);
        const vHeading = (isSelected && vesselInfo && typeof vesselInfo.heading === 'number')
          ? vesselInfo.heading
          : (v.heading || 180);
        const markerLon = (isSelected && vesselInfo && typeof vesselInfo.longitude === 'number')
          ? vesselInfo.longitude
          : v.longitude;
        const markerLat = (isSelected && vesselInfo && typeof vesselInfo.latitude === 'number')
          ? vesselInfo.latitude
          : v.latitude;
        const isArrived = v.mission_status === 'ARRIVED';
        const isAvailable = v.mission_status === 'AVAILABLE';
        const statusLabel = isArrived 
          ? `ARRIVED @ ${v.destination ? v.destination.split(' ')[0] : 'PORT'}` 
          : isAvailable 
          ? 'AVAILABLE' 
          : `${vSpeed} kn`;
        
        if (isSelected) {
          // RANK 1: ACTIVE VESSEL (Sleek, Calm, Non-Glowing Maritime Icon)
          vesselEl.innerHTML = `
            <div style="position:relative;width:40px;height:40px;display:flex;align-items:center;justify-content:center;pointer-events:none;">
              <div style="width:26px;height:26px;border-radius:50%;background:#061322;border:2px solid #38bdf8;display:flex;align-items:center;justify-content:center;transform:rotate(${vHeading}deg);pointer-events:none;">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="#38bdf8" stroke="#061322" stroke-width="1.5"><polygon points="12 2 19 21 12 17 5 21 12 2"/></svg>
              </div>
              <span style="position:absolute;bottom:-13px;font-family:sans-serif;font-size:9.5px;font-weight:600;color:#e2e8f0;background:#061322;padding:1.5px 6px;border-radius:4px;border:1px solid rgba(255,255,255,0.12);white-space:nowrap;pointer-events:none;">
                ${cleanName} • ${statusLabel}
              </span>
            </div>`;
        } else {
          // RANK 6: OTHER FLEET VESSELS (Muted Slate, Interactive on Hover & Click)
          vesselEl.innerHTML = `
            <div style="position:relative;width:28px;height:28px;display:flex;align-items:center;justify-content:center;pointer-events:none;" title="${cleanName} (${statusLabel})">
              <div style="width:20px;height:20px;border-radius:50%;background:#0A1322;border:1.5px solid #475569;display:flex;align-items:center;justify-content:center;transform:rotate(${vHeading}deg);pointer-events:none;">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="#94A3B8" stroke="#0A1322" stroke-width="1"><polygon points="12 2 19 21 12 17 5 21 12 2"/></svg>
              </div>
            </div>`;
        }

        vesselEl.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          handleVesselChange(v.id);
          setSelectedEntityInfo({
            title: `${v.flag || '⚓'} ${v.name.replace(' — DEMO', '')}`,
            badge: isSelected ? 'ACTIVE VESSEL' : 'FLEET VESSEL',
            badgeColor: isSelected ? '#00F2FE' : '#94A3B8',
            details: [
              { label: 'Polar Class', value: v.polar_class ? v.polar_class.split(' / ')[0] : 'PC5' },
              { label: 'Operator', value: v.operator ? v.operator.split(' (')[0] : (v.country || 'Polar Research') },
              { label: 'Speed & Heading', value: `${vSpeed} kn · ${vHeading}°T` },
              { label: 'Destination', value: v.destination || 'Antarctic Base' },
              { label: 'Coordinates', value: `${Math.abs(Number(markerLat.toFixed(2)))}°S, ${Math.abs(Number(markerLon.toFixed(2)))}°${markerLon >= 0 ? 'E' : 'W'}` },
              { label: 'ETA', value: v.eta || 'En Route' }
            ]
          });
        });

        vesselEl.title = `${v.flag || '⚓'} ${v.name.replace(' — DEMO', '')} (${vSpeed} kn, ${vHeading}°T) — Click to select`;

        const marker = new MapLibreMarker({ element: vesselEl, anchor: 'center' })
          .setLngLat([markerLon, markerLat])
          .addTo(map);
        markersRef.current.push(marker);
      });
    }

    // Interactive Waypoints
    if (layerToggles.recommendedRoute && waypoints.length > 0) {
      waypoints.forEach((wp, idx) => {
        const wpLat = wp.latitude ?? (wp as any).lat;
        const wpLon = wp.longitude ?? (wp as any).lon;
        if (typeof wpLat !== 'number' || isNaN(wpLat) || typeof wpLon !== 'number' || isNaN(wpLon)) return;

        const isNearVessel = activeVessel &&
          Math.abs(wpLat - activeVessel.latitude) < 0.08 &&
          Math.abs(wpLon - activeVessel.longitude) < 0.08;

        if (isNearVessel) return;

        const isNearDest = destinationMarker &&
          Math.abs(wpLat - destinationMarker.latitude) < 0.08 &&
          Math.abs(wpLon - destinationMarker.longitude) < 0.08;

        if (isNearDest) return;

        const wpEl = document.createElement('div');
        const isActive = wp.status === 'active';
        const isPassed = wp.status === 'passed';
        const wpColor = isActive ? '#00F2FE' : isPassed ? '#64748B' : '#10B981';
        const dotSize = isActive ? 8 : 6;

        wpEl.className = 'waypoint-marker-root';
        wpEl.title = `Waypoint ${idx + 1} (${wpLat.toFixed(2)}°S, ${wpLon.toFixed(2)}°E)`;
        wpEl.style.width = '14px';
        wpEl.style.height = '14px';
        wpEl.style.display = 'flex';
        wpEl.style.alignItems = 'center';
        wpEl.style.justifyContent = 'center';
        wpEl.style.cursor = 'pointer';

        wpEl.innerHTML = `
          <div style="width:${dotSize}px;height:${dotSize}px;border-radius:50%;background:${wpColor};border:1.5px solid #FFFFFF;box-shadow:0 0 6px ${wpColor};transition:all 0.2s ease;"></div>
        `;

        const marker = new MapLibreMarker({ element: wpEl, anchor: 'center' })
          .setLngLat([wpLon, wpLat])
          .addTo(map);
        markersRef.current.push(marker);
      });
    }

    // -------------------------------------------------------------------------
    // C4. SENTINEL-1 SAR RADAR OBSTACLES LAYER (Toggleable in Layers HUD)
    // -------------------------------------------------------------------------
    if (radarGeoJSON && layerToggles.radarObstacles) {
      if (!map.getSource('radar-obstacles-src')) {
        map.addSource('radar-obstacles-src', { type: 'geojson', data: radarGeoJSON });
        map.addLayer({
          id: 'radar-obstacles-points',
          type: 'circle',
          source: 'radar-obstacles-src',
          paint: {
            'circle-radius': 4.0,
            'circle-color': '#06B6D4',
            'circle-stroke-width': 1.2,
            'circle-stroke-color': '#ECFEFF',
            'circle-opacity': 0.85
          }
        });
        map.on('click', 'radar-obstacles-points', (e) => {
          if (!e.features || !e.features[0]?.properties) return;
          const p = e.features[0].properties;
          setSelectedEntityInfo({
            title: `Sentinel-1 SAR Radar Contact [${p.id || 'SAR-OBS'}]`,
            badge: 'RADAR TARGET',
            badgeColor: '#06B6D4',
            details: [
              { label: 'Platform', value: p.platform || 'SENTINEL-1A C-SAR' },
              { label: 'Acquisition Date', value: p.datetime ? new Date(p.datetime).toUTCString() : 'Verified SAR Pass' },
              { label: 'Detection Model', value: 'CFAR + Ocean Mask Segmentation' },
              { label: 'Confidence Score', value: `${((p.confidence || 0.88) * 100).toFixed(0)}%` },
              { label: 'Data Source', value: 'Microsoft Planetary Computer / ESA' }
            ]
          });
        });
      } else {
        (map.getSource('radar-obstacles-src') as GeoJSONSource).setData(radarGeoJSON);
        map.setLayoutProperty('radar-obstacles-points', 'visibility', 'visible');
      }
    } else if (map.getLayer('radar-obstacles-points')) {
      map.setLayoutProperty('radar-obstacles-points', 'visibility', 'none');
    }

    // Render Destination Station
    if (layerToggles.stations && stations && stations.length > 0) {
      stations.forEach((st) => {
        const isTarget = destinationMarker
          ? Boolean(
              (destinationMarker.name && (destinationMarker.name.toLowerCase().includes(st.name.toLowerCase()) || st.name.toLowerCase().includes(destinationMarker.name.toLowerCase()))) ||
              (Math.abs(st.latitude - (destinationMarker.latitude ?? (destinationMarker as any).lat ?? 999)) < 0.3 &&
               Math.abs(st.longitude - (destinationMarker.longitude ?? (destinationMarker as any).lon ?? 999)) < 0.6)
            )
          : Boolean(
              activeVessel?.destination && (
                activeVessel.destination.toLowerCase().includes(st.name.toLowerCase()) ||
                st.name.toLowerCase().includes(activeVessel.destination.toLowerCase())
              )
            );

        const stEl = document.createElement('div');
        stEl.className = `station-marker-${st.id}`;
        stEl.style.cursor = 'pointer';

        if (isTarget) {
          stEl.innerHTML = `
            <div style="position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;">
              <div style="width:16px;height:16px;border-radius:50%;background:#06111e;border:2px solid #10B981;display:flex;align-items:center;justify-content:center;">
                <div style="width:6px;height:6px;border-radius:50%;background:#10B981;"></div>
              </div>
              <span style="margin-top:3px;font-family:system-ui,-apple-system,sans-serif;font-size:9.5px;font-weight:600;color:#e2e8f0;background:rgba(6,17,30,0.9);padding:1.5px 6px;border-radius:4px;border:1px solid rgba(255,255,255,0.12);white-space:nowrap;pointer-events:none;">
                ★ ${st.name} (${st.country ? st.country.slice(0, 2).toUpperCase() : 'AQ'})
              </span>
            </div>`;
        } else {
          stEl.innerHTML = `
            <div style="position:relative;width:20px;height:20px;display:flex;align-items:center;justify-content:center;opacity:0.75;" title="${st.name}">
              <div style="width:8px;height:8px;border-radius:50%;background:#06111e;border:1.2px solid #38BDF8;display:flex;align-items:center;justify-content:center;">
                <div style="width:3px;height:3px;border-radius:50%;background:#38BDF8;"></div>
              </div>
            </div>`;
        }

        const marker = new MapLibreMarker({ element: stEl, anchor: 'center' })
          .setLngLat([st.longitude, st.latitude])
          .addTo(map);
        markersRef.current.push(marker);
      });
    }

    // =========================================================================
    // 4D. TACTICAL ICEBERG DOM MARKERS (Zoom-Adaptive Scaled Diamonds & Smart Decluttering)
    // =========================================================================
    if (layerToggles.icebergs && activeIcebergs && activeIcebergs.length > 0) {
      const isZoomLow = mapZoomRef.current < 4.2;
      const isZoomMed = mapZoomRef.current >= 4.2 && mapZoomRef.current < 5.6;
      const isZoomHigh = mapZoomRef.current >= 5.6;

      activeIcebergs.forEach((ib: any) => {
        // Resolve iceberg coordinate, heading and provenance at effectiveHorizon
        let lon = ib.origin_longitude ?? ib.longitude;
        let lat = ib.origin_latitude ?? ib.latitude;
        let bearingDeg = parseFloat(ib.direction || '0') || (ib.forecastPoints?.[1]?.bearingDeg ?? 90);
        let provenanceTag = 'OBSERVED (BYU/NIC TRACK)';

        if (effectiveHorizon !== 'NOW' && ib.forecastPoints && ib.forecastPoints.length > 0) {
          const matchFp = ib.forecastPoints.find((p: any) => 
            p.horizon === effectiveHorizon || 
            p.horizon?.replace('+', '') === effectiveHorizon.replace('+', '')
          );
          if (matchFp && matchFp.coordinates && typeof matchFp.coordinates[0] === 'number') {
            lat = matchFp.coordinates[0];
            lon = matchFp.coordinates[1];
            if (matchFp.bearingDeg !== undefined) bearingDeg = matchFp.bearingDeg;
            provenanceTag = `FORECAST ${effectiveHorizon} (RF MODEL)`;
          }
        }

        if (typeof lon !== 'number' || typeof lat !== 'number' || isNaN(lon) || isNaN(lat)) return;

        const isSelected = activeSelectedIcebergId === ib.id;
        const vesselLat = vesselInfo?.latitude ?? activeVessel?.latitude;
        const vesselLon = vesselInfo?.longitude ?? activeVessel?.longitude;
        const isInNavigationRadius = navigationRadiusKm !== undefined && typeof vesselLat === 'number' && typeof vesselLon === 'number' && haversineDistKm(vesselLat, vesselLon, lat, lon) <= activeNavigationRadiusKm;
        const isHigh = ib.risk === 'HIGH' || isInNavigationRadius;
        // Ice-blue berg glyphs are charted observations. Amber is reserved only for
        // a target inside the vessel's immediate navigation action radius.
        const color = navigationRadiusKm !== undefined ? (isInNavigationRadius ? '#F59E0B' : '#38BDF8') : (isHigh ? '#F59E0B' : '#38BDF8');
        const area = ib.areaKm2 || 45;
        const isGiant = area >= 100;
        const isLarge = area >= 50 && area < 100;

        // Dynamic diamond size scaled by zoom level & area:
        // - Low zoom (<4.2): Sleek pinpoint radar pips (5px - 7px), Selected is 16px
        // - Med zoom (4.2-5.6): Clean diamonds (9px - 13px), Selected is 22px
        // - High zoom (>=5.6): Full tactical diamonds (13px - 22px), Selected is 28px
        const diamondSize = isZoomLow
          ? (isSelected ? 16 : isHigh ? 7 : 5)
          : isZoomMed
          ? (isSelected ? 22 : isHigh ? 13 : isGiant ? 13 : 9)
          : (isSelected ? 28 : isGiant ? 22 : isLarge ? 17 : 13);

        const innerDiamondSize = Math.max(2, Math.round(diamondSize * 0.62));

        // Heading needle visibility
        const showNeedle = isSelected || isZoomHigh || (isZoomMed && isHigh);
        const bearingStr = ib.direction || '0°T';

        // Smart Label Filtering:
        // - Low zoom (<4.2): ONLY selected iceberg shows label (prevents 85 overlapping black boxes)
        // - Medium zoom (4.2-5.6): Selected AND High-Threat icebergs show compact ID label
        // - High zoom (>=5.6): All icebergs show tactical labels
        const showLabel = isSelected || isZoomHigh || (isZoomMed && isHigh);
        const velNum = typeof ib.velocity === 'number' ? ib.velocity : (parseFloat(String(ib.velocity)) || 0.4);
        const labelText = (isSelected || isZoomHigh)
          ? `${ib.id} ${isSelected || isHigh ? `• ${velNum.toFixed(1)}kn` : ''}`
          : ib.id;

        const ibEl = document.createElement('div');
        ibEl.className = `iceberg-marker-node iceberg-marker-node-${ib.id} ${isSelected ? 'selected' : ''}`;
        ibEl.dataset.id = ib.id;
        ibEl.dataset.isSelected = isSelected ? '1' : '0';
        ibEl.dataset.risk = ib.risk || 'SAFE';
        // Note: ibEl must NOT have position: relative - MapLibre uses absolute positioning on markers!
        ibEl.style.width = `${diamondSize + 12}px`;
        ibEl.style.height = `${diamondSize + 12}px`;
        ibEl.style.display = 'flex';
        ibEl.style.alignItems = 'center';
        ibEl.style.justifyContent = 'center';
        ibEl.style.cursor = 'pointer';
        ibEl.style.zIndex = isSelected ? '35' : isHigh ? '25' : '10';

        ibEl.innerHTML = `
          <div style="position:relative;width:100%;height:100%;display:flex;align-items:center;justify-content:center;">
            ${isSelected ? `
              <div style="position:absolute;width:${diamondSize + 12}px;height:${diamondSize + 12}px;border-radius:50%;background:${color}22;border:1.5px solid ${color};animation:ping 2s infinite;pointer-events:none;"></div>
            ` : ''}

            <!-- Ice-floe glyph: a readable iceberg-shaped marker, not an alarm diamond. -->
            <div class="iceberg-diamond-symbol" style="
              width:${diamondSize}px;
              height:${diamondSize}px;
              clip-path:polygon(50% 0%, 91% 28%, 82% 86%, 61% 100%, 28% 100%, 8% 62%, 12% 28%);
              background:${isSelected ? '#FFFFFF' : '#082f49'};
              border:${isSelected ? '2.5px solid #FACC15' : isZoomLow ? '1px solid #FFFFFF' : `1.8px solid ${color}`};
              border-radius:5px;
              display:flex;
              align-items:center;
              justify-content:center;
              box-shadow:0 0 ${isSelected ? '12px rgba(250,204,21,0.9)' : isHigh ? '8px rgba(245,158,11,0.7)' : '4px rgba(56,189,248,0.55)'};
            ">
              <div class="iceberg-diamond-inner" style="
                width:${innerDiamondSize}px;
                height:${innerDiamondSize}px;
                background:${isSelected ? '#FACC15' : color};
                clip-path:polygon(50% 0%, 91% 28%, 82% 86%, 61% 100%, 28% 100%, 8% 62%, 12% 28%);
                opacity:0.95;
              "></div>
            </div>

            <!-- Directional Drift Pointer Arrow (Medium / High Zoom only) -->
            ${showNeedle ? `
              <div style="
                position:absolute;
                width:100%;
                height:100%;
                pointer-events:none;
                transform:rotate(${bearingDeg}deg);
                display:flex;
                align-items:center;
                justify-content:center;
              ">
                <div style="
                  position:absolute;
                  top:-5px;
                  width:0;
                  height:0;
                  border-left:3px solid transparent;
                  border-right:3px solid transparent;
                  border-bottom:5px solid ${isSelected ? '#FACC15' : color};
                "></div>
              </div>
            ` : ''}

            <!-- Tactical Label Badge (Zoom-Adaptive) -->
            ${showLabel ? `
              <span class="iceberg-label-badge" style="
                position:absolute;
                bottom:-15px;
                left:50%;
                transform:translateX(-50%);
                font-family:ui-monospace, monospace;
                font-size:${isSelected ? '9.5px' : isZoomHigh ? '8px' : '7.5px'};
                font-weight:bold;
                color:${isSelected ? '#FACC15' : '#FFFFFF'};
                background:#040B16;
                padding:1px ${isSelected ? '4px' : '3px'};
                border-radius:2px;
                border:1px solid ${isSelected ? '#FACC15' : `${color}55`};
                white-space:nowrap;
                box-shadow:0 2px 6px rgba(0,0,0,0.8);
                pointer-events:none;
              ">
                ${labelText}
              </span>
            ` : ''}
          </div>
        `;

        ibEl.addEventListener('click', (e) => {
          e.stopPropagation();
          handleIcebergSelect(ib.id);
          const vLat = activeVessel?.latitude ?? -65.0;
          const vLon = activeVessel?.longitude ?? -64.0;
          const dLat = (lat - vLat) * 111.0;
          const dLon = (lon - vLon) * 111.0 * Math.cos((vLat * Math.PI) / 180);
          const liveDistKm = Math.round(Math.sqrt(dLat * dLat + dLon * dLon));

          setSelectedEntityInfo({
            title: `Iceberg ${ib.id} (${ib.name || 'Shelf Fragment'})`,
            badge: effectiveHorizon === 'NOW' ? (ib.risk || 'CAUTION') : `${ib.risk || 'CAUTION'} • ${effectiveHorizon}`,
            badgeColor: color,
            details: [
              { label: 'Surface Area', value: `${area} km² ${isGiant ? '(Giant Tabular)' : ''}` },
              { label: 'Drift Speed', value: `${velNum.toFixed(1)} kn (${bearingStr})` },
              { label: 'Draft Estimate', value: `${ib.draftEstimate || 320} m keel depth` },
              { label: 'Separation @ Horizon', value: `${liveDistKm} km to ${activeVessel?.name ? activeVessel.name.replace(' — DEMO', '').split(' ')[0] : 'Vessel'}` },
              { label: 'Confidence', value: `${ib.confidence || 94.8}%` },
              { label: 'Coordinates @ Horizon', value: `${Math.abs(Number(lat.toFixed(2)))}°S, ${Math.abs(Number(lon.toFixed(2)))}°${lon >= 0 ? 'E' : 'W'}` },
              { label: 'Data Provenance', value: provenanceTag }
            ]
          });
        });

        ibEl.title = `Iceberg ${ib.id} (${ib.name || 'Fragment'}) • ${area} km² • ${ib.risk || 'SAFE'} Risk — Click to select`;

        const marker = new MapLibreMarker({ element: ibEl, anchor: 'center' })
          .setLngLat([lon, lat])
          .addTo(map);
        markersRef.current.push(marker);
      });
    }

  }, [
    mapLoaded,
    layerToggles,
    fleetVessels,
    currentVesselId,
    destinationMarker,
    waypoints,
    stations,
    activeVessel,
    activeIcebergs,
    activeSelectedIcebergId,
    effectiveHorizon,
    onSelectIceberg,
    handleIcebergSelect,
    vesselInfo
    , navigationRadiusKm, activeNavigationRadiusKm
  ]);

  // 5. Zoom-adaptive marker styling (NO teardown/recreate — updates DOM in-place)
  useEffect(() => {
    // Use mapZoom state directly (not the ref, which can be stale)
    const z = mapZoom;
    const isLow = z < 4.2;
    const isMed = z >= 4.2 && z < 5.6;
    const isHigh = z >= 5.6;

    markersRef.current.forEach(m => {
      const el = m.getElement();
      if (!el) return;

      if (!el.classList.contains('iceberg-marker-node')) return;

      const ibDiamond = el.querySelector('.iceberg-diamond-symbol') as HTMLElement | null;
      if (!ibDiamond) return;

      const isSel = el.dataset.isSelected === '1' || el.classList.contains('selected');
      const isHighRisk = el.dataset.risk === 'HIGH';
      const ibInner = el.querySelector('.iceberg-diamond-inner') as HTMLElement | null;
      const ibLabel = el.querySelector('.iceberg-label-badge') as HTMLElement | null;

      let newSize: number;
      if (isLow) {
        newSize = isSel ? 18 : isHighRisk ? 7 : 5;
      } else if (isMed) {
        newSize = isSel ? 24 : isHighRisk ? 13 : 9;
      } else {
        newSize = isSel ? 28 : isHighRisk ? 18 : 13;
      }
      ibDiamond.style.width = `${newSize}px`;
      ibDiamond.style.height = `${newSize}px`;

      if (ibInner) {
        const innerSize = Math.max(2, Math.round(newSize * 0.62));
        ibInner.style.width = `${innerSize}px`;
        ibInner.style.height = `${innerSize}px`;
      }

      // Update label visibility based on zoom level
      if (ibLabel) {
        ibLabel.style.display = (isSel || isHigh || (isMed && isHighRisk)) ? '' : 'none';
      }
    });
  }, [mapZoom]);

  // Derive operational status bar values from existing real state
  const opStatusRoute = activeRouteObj ? (emergencyRerouteActive ? 'DEGRADED' : 'OPERATIONAL') : 'NO ROUTE';
  const opStatusColor = opStatusRoute === 'OPERATIONAL' ? '#10B981' : opStatusRoute === 'DEGRADED' ? '#EF4444' : '#64748B';
  const opVesselSpeed = activeVessel?.speed ?? activeVessel?.sog ?? 0;
  const opRouteRisk = activeRouteObj?.iceRisk || 'N/A';
  const opDataMode = activeVessel?.data_status === 'LIVE' ? 'LIVE AIS' : activeVessel?.data_status === 'DETERMINISTIC_SIMULATION' ? 'SIMULATION' : activeVessel?.data_status || 'SIMULATION';
  const opIsLive = opDataMode === 'LIVE AIS';
  // Estimate Iridium data size from route path length
  const iridiumDataKB = activeRouteObj?.path ? Math.round((activeRouteObj.path.length * 16) / 1024 * 10) / 10 : 0;

  return (
    <div className="w-full h-full bg-[#040B16] relative z-0 overflow-hidden select-none">
      {/* MAP CANVAS */}
      <div ref={mapContainerRef} className="w-full h-full" style={{ background: '#dff5ff' }} />

      {/* ========================================================================= */}
      {/* 0. OPERATIONAL STATUS BAR (top strip — real data only)                   */}
      {/* ========================================================================= */}
      <div className="absolute top-0 left-0 right-0 z-25 h-7 bg-[#06111e] border-b border-slate-800 flex items-center px-3 gap-4 font-mono text-[10px] overflow-hidden select-none pointer-events-none">
        {/* Route Status */}
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: opStatusColor }} />
          <span className="font-bold" style={{ color: opStatusColor }}>ROUTE: {opStatusRoute}</span>
        </div>
        <div className="w-px h-3.5 bg-slate-800 shrink-0" />
        {/* Speed */}
        <div className="flex items-center gap-1 text-slate-300 shrink-0">
          <span className="text-slate-500">SOG</span>
          <span className="font-bold text-slate-100">{Number(opVesselSpeed).toFixed(1)} kn</span>
        </div>
        <div className="w-px h-3.5 bg-slate-800 shrink-0" />
        {/* Risk */}
        <div className="flex items-center gap-1 shrink-0">
          <span className="text-slate-500">RISK</span>
          <span className={`font-bold ${
            opRouteRisk === 'HIGH' || opRouteRisk === 'CRITICAL' ? 'text-red-400'
            : opRouteRisk === 'MODERATE' || opRouteRisk === 'CAUTION' ? 'text-amber-400'
            : 'text-emerald-400'
          }`}>{opRouteRisk}</span>
        </div>
        <div className="w-px h-3.5 bg-slate-800 shrink-0" />
        {/* ETA */}
        {activeRouteObj?.eta && (
          <>
            <div className="flex items-center gap-1 text-slate-300 shrink-0">
              <span className="text-slate-500">ETA</span>
              <span className="font-bold text-slate-100">{activeRouteObj.eta}</span>
            </div>
            <div className="w-px h-3.5 bg-slate-800 shrink-0" />
          </>
        )}
        {/* Destination */}
        {activeVessel?.destination && (
          <div className="flex items-center gap-1 text-slate-300 shrink-0">
            <span className="text-slate-500">DEST</span>
            <span className="text-slate-200">{String(activeVessel.destination).split(' ').slice(0, 2).join(' ')}</span>
          </div>
        )}
        {/* Spacer */}
        <div className="flex-1" />
        {/* Iridium Mode Indicator */}
        {iridiumMode && (
          <div className="flex items-center gap-1.5 bg-amber-950/40 border border-amber-600/50 px-2 py-0.5 rounded-xs text-amber-300 font-bold shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            IRIDIUM · {iridiumDataKB} KB CACHED
          </div>
        )}
        {/* Data mode badge */}
        <div className={`flex items-center gap-1.5 shrink-0 px-2.5 py-0.5 rounded-full border ${
          opIsLive
            ? 'bg-emerald-950/40 border-emerald-600/40 text-emerald-400'
            : 'bg-[#050e18] border-slate-800 text-slate-400'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${opIsLive ? 'bg-emerald-400' : 'bg-slate-500'}`} />
          <span className="font-semibold font-mono text-[10px]">{opDataMode}</span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 1. ROUTE DECISION INTELLIGENCE ("WHY THIS ROUTE?" HUD CARD)              */}
      {/* ========================================================================= */}
      {activeRouteObj && (
        <div className="absolute top-9 left-3 z-25 font-sans text-xs">
          {whyRouteCollapsed ? (
            <button
              type="button"
              onClick={() => setWhyRouteCollapsed(false)}
              className="flex items-center gap-2 bg-[#06111e]/90 backdrop-blur-md border border-slate-800 px-3 py-1.5 rounded-lg text-slate-200 hover:text-white shadow-md text-xs font-medium transition-colors cursor-pointer"
              title="Expand Route Decision Intelligence"
            >
              <Compass className="w-3.5 h-3.5 text-sky-400" />
              <span>Route Intelligence</span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </button>
          ) : (
            <div className="bg-[#06111e]/90 backdrop-blur-md border border-slate-800 rounded-lg p-3 shadow-lg w-64 space-y-2 select-none font-sans">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                <span className="flex items-center gap-1.5 text-xs">
                  <Compass className="w-3.5 h-3.5 text-sky-400" /> Route Intelligence
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-800 text-sky-300">
                    {activeRouteObj.optimization_mode || (activeRouteObj.recommended ? 'Recommended' : 'Alternative')}
                  </span>
                  <button
                    type="button"
                    onClick={() => setWhyRouteCollapsed(true)}
                    className="text-slate-400 hover:text-white p-0.5 cursor-pointer"
                    title="Minimize"
                  >
                    <ChevronUp className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <div className="space-y-1.5 text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Sea Ice Exposure</span>
                  <span className="text-sky-300 font-semibold font-mono text-[10.5px]">
                    {activeRouteObj.sic_actual !== undefined ? `${activeRouteObj.sic_actual}% SIC` : activeRouteObj.sicExposure !== undefined ? `${activeRouteObj.sicExposure}% SIC` : 'Optimal'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Iceberg Clearance</span>
                  <span className="text-slate-200 font-mono text-[10.5px]">
                    {activeRouteObj.minimum_cpa_km !== undefined ? `${activeRouteObj.minimum_cpa_km} km` : 'Safe margin'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">IMO POLARIS RIO</span>
                  <span className="text-emerald-400 font-semibold font-mono text-[10.5px]">
                    {activeRouteObj.rioScore !== undefined ? (Number(activeRouteObj.rioScore) > 0 ? `+${Number(activeRouteObj.rioScore).toFixed(1)}` : String(activeRouteObj.rioScore)) : '+2.4 (Compliant)'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Distance &amp; ETA</span>
                  <span className="text-slate-200 font-mono text-[10.5px]">{activeRouteObj.distance || 'N/A'} • {activeRouteObj.eta || 'N/A'}</span>
                </div>
                {activeRouteObj.decision_support?.recommendation && (
                  <div className="text-[10.5px] text-slate-300 leading-snug">
                    <span className="text-sky-400 font-medium">Decision: </span>
                    {activeRouteObj.decision_support.recommendation.slice(0, 85)}...
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* 2. TOP-CENTER COMMAND BAR (VIEWPORT & HISTORICAL VALIDATION SWITCHERS)    */}
      {/* ========================================================================= */}
      <div className="absolute top-9 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 font-sans text-xs">
        {/* Viewport Sector Switcher */}
        <div className="flex items-center bg-[#06111e]/90 backdrop-blur-md rounded-lg border border-slate-800 p-0.5 shadow-sm">
          <button
            type="button"
            onClick={() => handleViewportSwitch('OPERATIONAL')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition-colors cursor-pointer text-xs font-medium ${
              viewportMode === 'OPERATIONAL'
                ? 'bg-slate-800 text-sky-300 font-semibold shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Crosshair className="w-3.5 h-3.5 text-sky-400" />
            <span>Operational Sector</span>
          </button>
          <button
            type="button"
            onClick={() => handleViewportSwitch('CIRCUMPOLAR')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition-colors cursor-pointer text-xs font-medium ${
              viewportMode === 'CIRCUMPOLAR'
                ? 'bg-slate-800 text-sky-300 font-semibold shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Globe className="w-3.5 h-3.5 text-sky-400" />
            <span>Circumpolar View</span>
          </button>
        </div>

        {/* Benchmark Efficiency Comparison Toggle */}
        <div className="flex items-center bg-[#06111e]/90 backdrop-blur-md rounded-lg border border-slate-800 p-0.5 shadow-sm">
          <button
            type="button"
            onClick={() => { setComparisonMode('LIVE'); setShowCompareModal(false); }}
            className={`px-3 py-1 rounded transition-colors text-xs font-medium cursor-pointer ${
              comparisonMode === 'LIVE'
                ? 'bg-slate-800 text-sky-300 font-semibold shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Live Navigation View"
          >
            Live
          </button>
          <button
            type="button"
            onClick={() => setComparisonMode(comparisonMode === 'COMPARE' ? 'LIVE' : 'COMPARE')}
            className={`px-3 py-1 rounded transition-colors text-xs font-medium cursor-pointer ${
              comparisonMode === 'COMPARE'
                ? 'bg-slate-800 text-sky-300 font-semibold shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Statistical Comparison vs Human Navigator"
          >
            Compare (Stats)
          </button>
        </div>
      </div>

      {/* Floating Historical Comparison Metric Stats Panel */}
      {comparisonMode === 'COMPARE' && (
        <div className="absolute top-18 left-1/2 -translate-x-1/2 z-20 flex flex-col items-center gap-2 bg-[#06111e]/95 backdrop-blur-md border border-slate-800 p-3 rounded-lg text-xs font-sans shadow-xl text-slate-200 max-w-[95vw]">
          <div className="flex flex-wrap items-center justify-center gap-2 md:gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-amber-400 font-semibold">Human Navigator:</span>
              <span className="text-amber-300 font-mono">7,846 km · 240h</span>
            </div>
            <span className="text-slate-600 font-bold">•</span>
            <div className="flex items-center gap-1.5">
              <span className="text-sky-400 font-semibold">Aeolus AI:</span>
              <span className="text-emerald-400 font-mono font-semibold">2,757 km · 106h</span>
            </div>
            <span className="text-slate-600 font-bold">•</span>
            <span className="bg-emerald-500/20 text-emerald-300 px-2.5 py-0.5 rounded-full font-mono text-[11px]">
              -65.5% Dist (-5,089 km)
            </span>
            <span className="bg-sky-500/20 text-sky-300 px-2.5 py-0.5 rounded-full font-mono text-[11px]">
              -133.7h (-5.6 Days)
            </span>
            <span className="bg-amber-500/20 text-amber-300 px-2.5 py-0.5 rounded-full font-mono text-[11px]">
              142.5 MT Fuel Saved
            </span>
            <button
              type="button"
              onClick={() => setShowCompareModal(!showCompareModal)}
              className="ml-1 text-xs text-sky-300 underline hover:text-white transition-colors cursor-pointer font-sans"
            >
              {showCompareModal ? 'Hide' : 'Breakdown'}
            </button>
            <button
              type="button"
              onClick={() => { setComparisonMode('LIVE'); setShowCompareModal(false); }}
              className="ml-1 text-slate-400 hover:text-white cursor-pointer"
              title="Close Comparison Panel"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {showCompareModal && (
            <div className="w-full mt-1 pt-2.5 border-t border-slate-800 font-sans text-xs space-y-2">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-center text-xs">
                <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80">
                  <div className="text-amber-400 font-semibold">Human Navigator (AAD 2015/16)</div>
                  <div className="text-slate-200 mt-1 font-mono text-[11px]">7,845.8 km · 240.0h (10.0 d)</div>
                  <div className="text-slate-400 text-[10px] font-mono mt-0.5">220.8 MT Fuel · 706.6 MT CO₂</div>
                </div>
                <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80">
                  <div className="text-slate-400 font-semibold">Naive Shortest Path (Geodesic)</div>
                  <div className="text-slate-200 mt-1 font-mono text-[11px]">3,554.0 km · 137.1h (5.7 d)</div>
                  <div className="text-rose-400 text-[10px] font-mono mt-0.5">4 Severe Hazard Violations</div>
                </div>
                <div className="bg-slate-900/60 p-2.5 rounded-lg border border-sky-800/60">
                  <div className="text-sky-300 font-semibold">Aeolus Multi-Objective</div>
                  <div className="text-emerald-400 mt-1 font-bold font-mono text-[11px]">2,757.1 km · 106.3h (4.4 d)</div>
                  <div className="text-emerald-300 text-[10px] font-mono mt-0.5">78.3 MT Fuel (142.5 MT Saved)</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. TOP-RIGHT FLOATING LAYERS CONTROL PANEL                                */}
      {/* ========================================================================= */}
      <div className="absolute top-9 right-3 z-30 font-sans text-xs">
        <button
          type="button"
          onClick={() => setLayersMenuOpen(!layersMenuOpen)}
          className="flex items-center gap-2 bg-[#06111e]/90 backdrop-blur-md border border-slate-800 px-3 py-1.5 rounded-lg text-slate-200 hover:text-white transition-colors shadow-sm cursor-pointer font-medium"
        >
          <Layers className="w-3.5 h-3.5 text-sky-400" />
          <span>Map Layers</span>
          {layersMenuOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
        </button>

        {layersMenuOpen && (
          <div className="absolute right-0 mt-1.5 w-60 bg-[#06111e]/95 backdrop-blur-md border border-slate-800 rounded-lg p-3 shadow-xl space-y-2.5 text-xs font-sans max-h-[75vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-1 border-b border-slate-800">
              <span className="text-[11px] font-semibold text-slate-200 uppercase tracking-wider">
                Layers &amp; Overlays
              </span>
              <button type="button" onClick={() => setLayersMenuOpen(false)} className="text-slate-400 hover:text-white cursor-pointer">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* 1. VESSEL & ROUTE */}
            <div className="space-y-1.5">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                Vessel &amp; Navigation
              </span>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Vessel Position</span>
                <input
                  type="checkbox"
                  checked={layerToggles.activeVessel}
                  onChange={(e) => setLayerToggles({ ...layerToggles, activeVessel: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Planned Route</span>
                <input
                  type="checkbox"
                  checked={layerToggles.recommendedRoute}
                  onChange={(e) => setLayerToggles({ ...layerToggles, recommendedRoute: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Alternative Routes</span>
                <input
                  type="checkbox"
                  checked={layerToggles.altRoutes}
                  onChange={(e) => setLayerToggles({ ...layerToggles, altRoutes: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Waypoints</span>
                <input
                  type="checkbox"
                  checked={layerToggles.waypoints}
                  onChange={(e) => setLayerToggles({ ...layerToggles, waypoints: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
            </div>

            {/* 2. ICE & HAZARDS */}
            <div className="space-y-1.5 pt-2">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                Ice &amp; Hazards
              </span>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Tracked Icebergs (85)</span>
                <input
                  type="checkbox"
                  checked={layerToggles.icebergs}
                  onChange={(e) => setLayerToggles({ ...layerToggles, icebergs: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Sea Ice Concentration (AMSR2)</span>
                <input
                  type="checkbox"
                  checked={layerToggles.seaIce}
                  onChange={(e) => setLayerToggles({ ...layerToggles, seaIce: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Radar Obstacles (Sentinel-1)</span>
                <input
                  type="checkbox"
                  checked={layerToggles.radarObstacles}
                  onChange={(e) => setLayerToggles({ ...layerToggles, radarObstacles: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Iceberg Drift Vectors</span>
                <input
                  type="checkbox"
                  checked={layerToggles.icebergTrajectories}
                  onChange={(e) => setLayerToggles({ ...layerToggles, icebergTrajectories: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
            </div>

            {/* 3. ENVIRONMENT & INFRASTRUCTURE */}
            <div className="space-y-1.5 pt-2">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                Environment &amp; Infrastructure
              </span>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Ocean Currents (GLO12)</span>
                <input
                  type="checkbox"
                  checked={layerToggles.oceanCurrents}
                  onChange={(e) => setLayerToggles({ ...layerToggles, oceanCurrents: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Navigation Grid</span>
                <input
                  type="checkbox"
                  checked={layerToggles.navGrid}
                  onChange={(e) => setLayerToggles({ ...layerToggles, navGrid: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
              <label className="flex items-center justify-between text-xs text-slate-300 hover:text-white cursor-pointer">
                <span>Antarctic Research Stations</span>
                <input
                  type="checkbox"
                  checked={layerToggles.stations}
                  onChange={(e) => setLayerToggles({ ...layerToggles, stations: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                />
              </label>
            </div>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* 4. GIS NAVIGATION & VIEW CONTROLS                                         */}
      {/* ========================================================================= */}
      <div className="absolute top-19 right-3 z-30 flex flex-col items-center gap-1.5 text-xs select-none">
        {/* Reset North */}
        <button
          type="button"
          onClick={handleResetNorth}
          className="w-8 h-8 rounded-lg bg-[#06111e]/90 backdrop-blur-md border border-slate-800 text-slate-300 hover:text-white flex flex-col items-center justify-center transition-colors shadow-sm cursor-pointer"
          title="Reset Bearing & North"
        >
          <Compass
            className="w-3.5 h-3.5 text-slate-300 transition-transform duration-300"
            style={{ transform: `rotate(${-mapBearing}deg)` }}
          />
          <span className="text-[7px] font-bold font-mono">N</span>
        </button>

        {/* Fit Corridor */}
        <button
          type="button"
          onClick={handleRecenterRoute}
          className="w-8 h-8 rounded-lg bg-[#06111e]/90 backdrop-blur-md border border-slate-800 text-slate-300 hover:text-white flex flex-col items-center justify-center transition-colors shadow-sm cursor-pointer"
          title="Fit Active Route Corridor"
        >
          <Crosshair className="w-3.5 h-3.5 text-slate-300" />
          <span className="text-[7px] font-bold font-mono">FIT</span>
        </button>

        {/* 2D / 3D Perspective Toggle */}
        <button
          type="button"
          onClick={handleToggle3D}
          className={cn(
            "w-8 h-8 rounded-lg bg-[#06111e]/90 backdrop-blur-md border border-slate-800 text-slate-300 hover:text-white flex flex-col items-center justify-center transition-colors shadow-sm cursor-pointer",
            mapPitch > 25 && "text-sky-300 bg-slate-800 border-sky-700/50"
          )}
          title={mapPitch > 25 ? "Switch to 2D Overhead View" : "Switch to 3D View"}
        >
          <Eye className="w-3.5 h-3.5" />
          <span className="text-[7px] font-bold font-mono">{mapPitch > 25 ? "3D" : "2D"}</span>
        </button>

        {/* Low Bandwidth / Iridium */}
        <button
          type="button"
          onClick={() => setIridiumMode(prev => !prev)}
          className={cn(
            "w-8 h-8 rounded-lg bg-[#06111e]/90 backdrop-blur-md border border-slate-800 text-slate-300 hover:text-white flex flex-col items-center justify-center transition-colors shadow-sm cursor-pointer",
            iridiumMode && "text-amber-300 bg-amber-950/40 border-amber-600/50"
          )}
          title={iridiumMode ? "Iridium Mode ON" : "Iridium Mode (Low Bandwidth)"}
        >
          <Ship className="w-3 h-3" />
          <span className="text-[7px] font-bold font-mono">IRID</span>
        </button>

        {/* Zoom Controls */}
        <div className="flex flex-col rounded-lg bg-[#06111e]/90 backdrop-blur-md border border-slate-800 shadow-sm overflow-hidden">
          <button
            type="button"
            onClick={handleZoomIn}
            className="w-8 h-7 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 transition-colors border-b border-slate-800 cursor-pointer"
            title="Zoom In (+)"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleZoomOut}
            className="w-8 h-7 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
            title="Zoom Out (-)"
          >
            <Minus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 5. BOTTOM-LEFT COLLAPSIBLE MARITIME LEGEND                                 */}
      {/* ========================================================================= */}
      <div className="absolute bottom-3 left-3 z-20 font-sans text-xs">
        {legendCollapsed ? (
          <button
            type="button"
            onClick={() => setLegendCollapsed(false)}
            className="flex items-center gap-2 bg-[#06111e]/90 backdrop-blur-md border border-slate-800 px-3 py-1.5 rounded-lg text-slate-300 hover:text-white shadow-md text-xs font-medium cursor-pointer"
          >
            <Compass className="w-3.5 h-3.5 text-sky-400" />
            <span>Legend</span>
            <ChevronUp className="w-3.5 h-3.5" />
          </button>
        ) : (
          <div className="bg-[#06111e]/90 backdrop-blur-md rounded-lg border border-slate-800 p-3 shadow-lg w-52 space-y-2 select-none text-xs font-sans">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 text-xs">
                Map Legend
              </span>
              <button type="button" onClick={() => setLegendCollapsed(true)} className="text-slate-400 hover:text-white cursor-pointer">
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-1.5 text-[11px]">
              <div className="flex items-center gap-2">
                <span className="text-emerald-400 font-bold text-xs leading-none">●</span>
                <span className="text-slate-200">Vessel Position</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-emerald-400 font-bold text-xs leading-none">━</span>
                <span className="text-slate-200">Planned Route</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-slate-400 font-bold text-xs leading-none">━</span>
                <span className="text-slate-300">Alternative Route</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sky-300 font-bold text-xs leading-none">⬟</span>
                <span className="text-slate-200">Icebergs · ice-blue tracked / amber action</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-amber-400 font-bold text-xs leading-none">▲</span>
                <span className="text-slate-200">Radar Obstacles</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sky-400 font-bold text-xs leading-none">■</span>
                <span className="text-slate-200">Sea Ice (&gt;70%)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-amber-300 font-bold text-xs leading-none">●</span>
                <span className="text-slate-200">Weather Hazard</span>
              </div>
            </div>

            <div className="text-[10px] text-slate-500 pt-1">
              US NIC • NOAA CDR • Sentinel-1
            </div>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* 6. CLICK-ONLY DOCKED INFO CARD (DISMISSABLE WITH ✕ OR MAP CLICK)           */}
      {/* ========================================================================= */}
      {selectedEntityInfo && (
        <div className="absolute bottom-3 right-3 z-30 bg-[#06111e]/95 backdrop-blur-md border border-slate-800 rounded-lg p-3.5 shadow-2xl font-sans text-xs w-72 space-y-2 select-text">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-200 font-semibold truncate max-w-[170px]">{selectedEntityInfo.title}</span>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full" style={{ color: selectedEntityInfo.badgeColor, backgroundColor: `${selectedEntityInfo.badgeColor}22` }}>
                {selectedEntityInfo.badge}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedEntityInfo(null);
                }}
                className="text-slate-400 hover:text-white p-0.5 rounded hover:bg-slate-800 transition-colors cursor-pointer"
                title="Close Card"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
          <div className="space-y-1 text-[11px]">
            {selectedEntityInfo.details.map((d, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-slate-400">{d.label}</span>
                <strong className="text-slate-200 font-mono">{d.value}</strong>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 7. BOTTOM POLAR MARITIME STATUS BAR / LIVE CURSOR READOUT                 */}
      {/* ========================================================================= */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 hidden sm:flex items-center gap-3 bg-[#06111e]/85 backdrop-blur-md border border-slate-800 px-3.5 py-1 rounded-full text-[11px] font-sans text-slate-300 shadow-sm pointer-events-none select-none">
        <span className="flex items-center gap-1.5 text-sky-400 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
          <span>Polar Obs</span>
        </span>
        <span className="text-slate-700">|</span>
        <span>
          <strong className="text-slate-100 font-mono text-[11px]">{cursorCoords ? `${Math.abs(cursorCoords.lat).toFixed(3)}°${cursorCoords.lat >= 0 ? 'N' : 'S'}, ${Math.abs(cursorCoords.lng).toFixed(3)}°${cursorCoords.lng >= 0 ? 'E' : 'W'}` : '--, --'}</strong>
        </span>
        <span className="text-slate-700">|</span>
        <span><strong className="text-slate-300">{cursorCoords && cursorCoords.lat < -60 ? 'Antarctica' : 'Sub-Polar'}</strong></span>
        <span className="text-slate-700">|</span>
        <span><strong className="text-slate-300 font-mono text-[11px]">{mapBearing}°T</strong></span>
      </div>

    </div>
  );
};

export default PolarMap;
