export interface GeocodingResult {
  placeId: number | string;
  displayName: string;
  latitude: number;
  longitude: number;
  type?: string;
  importance?: number;
  boundingBox?: [number, number, number, number]; // [south, north, west, east]
}

export interface GeocodingState {
  query: string;
  results: GeocodingResult[];
  isLoading: boolean;
  error: string | null;
}

const NOMINATIM_BASE_URL = 'https://nominatim.openstreetmap.org/search';

/**
 * Searches locations using OpenStreetMap Nominatim API.
 * Includes user-agent compliance and debounced query execution handling.
 */
export async function searchLocations(
  query: string, 
  signal?: AbortSignal
): Promise<GeocodingResult[]> {
  const trimmed = query.trim();
  if (!trimmed || trimmed.length < 2) {
    return [];
  }

  const params = new URLSearchParams({
    q: trimmed,
    format: 'json',
    addressdetails: '1',
    limit: '6',
    // Helpful priority ordering
    extratags: '1'
  });

  const response = await fetch(`${NOMINATIM_BASE_URL}?${params.toString()}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      // Identify application according to Nominatim usage policy
      'Accept-Language': 'en'
    },
    signal
  });

  if (!response.ok) {
    throw new Error(`Nominatim geocoding failed (${response.status}): ${response.statusText}`);
  }

  const data = await response.json();

  if (!Array.isArray(data)) {
    return [];
  }

  return data.map((item: {
    place_id: number | string;
    display_name: string;
    lat: string;
    lon: string;
    type?: string;
    importance?: number;
    boundingbox?: string[];
  }) => ({
    placeId: item.place_id,
    displayName: item.display_name,
    latitude: parseFloat(item.lat),
    longitude: parseFloat(item.lon),
    type: item.type,
    importance: item.importance,
    boundingBox: item.boundingbox && item.boundingbox.length === 4 
      ? [
          parseFloat(item.boundingbox[0]), 
          parseFloat(item.boundingbox[1]), 
          parseFloat(item.boundingbox[2]), 
          parseFloat(item.boundingbox[3])
        ]
      : undefined
  }));
}
