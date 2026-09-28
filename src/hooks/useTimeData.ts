import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";

export interface TimeEnvironmental {
  seaIceConcentration: number;
  iceDrift: number;
  windSpeed: number;
  windDirection: string;
  windSpeedMs: number;
  temperature: number;
  pressure: number;
  sst: number;
  visibility: number;
  waveHeight: number;
  oceanCurrent: number;
  overallRisk: string;
  seaIceRiskScore: number;
  icebergRiskScore: number;
  weatherRiskScore: number;
  overallRiskScore: number;
  timestep: string;
  timestepTime: string;
  dataSource: string;
}

export interface SeaIceSector {
  sector: string;
  name: string;
  concentration: number;
  iceType: string;
  thickness: string;
  driftRate: string;
  riskLevel: "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
  sicValue?: number;
}

/**
 * Hook that fetches time-dependent data from the backend.
 * Re-fetches whenever timeStep changes.
 */
export function useTimeData(timeStep: string) {
  const [environmental, setEnvironmental] = useState<TimeEnvironmental | null>(null);
  const [seaIceSectors, setSeaIceSectors] = useState<SeaIceSector[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [envRes, sectorsRes] = await Promise.all([
        api.environmental(timeStep),
        api.seaIceSectors(timeStep),
      ]);
      
      if (envRes) setEnvironmental(envRes as TimeEnvironmental);
      if (sectorsRes?.sectors) setSeaIceSectors(sectorsRes.sectors);
    } catch (e) {
      console.error("[useTimeData] fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, [timeStep]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { environmental, seaIceSectors, loading, refetch: fetchData };
}
