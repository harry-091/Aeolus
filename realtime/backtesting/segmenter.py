"""POLARNAV — Phase 13: Operational Event Segmenter.

Categorizes historical AIS tracks into distinct operational activities:
- scientific stops (e.g. oceanographic CTD stations, mooring deployments)
- weather holds (heaving-to or sheltering in the lee during gales)
- port/station operations (berthing, loading, resupply)
- maneuvering (restricted harbor approaches, low-speed turns)
- data gaps (AIS receiver blackouts, satellite revisit gaps)
- ice avoidance (tactical circumnavigation of heavy pack ice)
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from .models import OperationalSegment, OperationalSegmentType, OperationalEventBreakdown


# Known Antarctic and gateway coordinates for port/station detection
KNOWN_LOCATIONS = [
    {"name": "Hobart Port", "lat": -42.88, "lon": 147.34, "radius_km": 35.0, "is_port": True},
    {"name": "Cape Town Port", "lat": -33.92, "lon": 18.42, "radius_km": 35.0, "is_port": True},
    {"name": "Punta Arenas", "lat": -53.16, "lon": -70.91, "radius_km": 35.0, "is_port": True},
    {"name": "Casey Station", "lat": -66.28, "lon": 110.53, "radius_km": 25.0, "is_port": False},
    {"name": "Davis Station", "lat": -68.58, "lon": 77.97, "radius_km": 25.0, "is_port": False},
    {"name": "Mawson Station", "lat": -67.60, "lon": 62.87, "radius_km": 25.0, "is_port": False},
    {"name": "Bharati Station", "lat": -69.41, "lon": 76.19, "radius_km": 25.0, "is_port": False},
    {"name": "Maitri Station", "lat": -70.77, "lon": 11.73, "radius_km": 25.0, "is_port": False},
    {"name": "Vernadsky Station", "lat": -65.25, "lon": -64.26, "radius_km": 20.0, "is_port": False},
    {"name": "McMurdo Station", "lat": -77.85, "lon": 166.67, "radius_km": 30.0, "is_port": False},
    {"name": "Heard Island", "lat": -53.10, "lon": 73.50, "radius_km": 30.0, "is_port": False},
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two geographic coordinates in km."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


class OperationalEventSegmenter:
    """Segments raw AIS tracks into non-transit and transit operational events."""

    def __init__(self, sic_lookup_fn: Optional[Any] = None):
        self.sic_lookup_fn = sic_lookup_fn or (lambda lat, lon: 0.0)

    def segment_voyage(
        self,
        track: List[List[float]],
        departure_time: datetime,
        nominal_speed_knots: float = 14.0,
        total_duration_hours: Optional[float] = None,
    ) -> OperationalEventBreakdown:
        """Classify every track segment into operational activities."""
        if not track or len(track) < 2:
            return OperationalEventBreakdown(
                total_voyage_hours=0.0,
                transit_hours=0.0,
                scientific_stops_hours=0.0,
                weather_holds_hours=0.0,
                port_station_hours=0.0,
                maneuvering_hours=0.0,
                data_gaps_hours=0.0,
                ice_avoidance_hours=0.0,
                segments=[],
            )

        n = len(track)
        # Compute point-to-point metrics
        point_distances: List[float] = [0.0]
        cumulative_dist: List[float] = [0.0]
        for i in range(1, n):
            d = haversine_km(track[i - 1][0], track[i - 1][1], track[i][0], track[i][1])
            point_distances.append(d)
            cumulative_dist.append(cumulative_dist[-1] + d)

        total_distance = cumulative_dist[-1]
        calc_hours = total_distance / max(1.0, nominal_speed_knots * 1.852)
        voyage_hours = total_duration_hours if (total_duration_hours and total_duration_hours > 0) else calc_hours

        # Estimate time per segment
        hours_per_km = voyage_hours / max(1.0, total_distance)

        segments: List[OperationalSegment] = []
        seg_id_counter = 1

        # We group points into contiguous blocks
        i = 0
        while i < n - 1:
            curr_lat, curr_lon = track[i][0], track[i][1]
            dist_to_next = point_distances[i + 1]

            # 1. Check for DATA GAP (sudden distance jump > 120 km)
            if dist_to_next > 120.0:
                seg_hrs = round(dist_to_next / (nominal_speed_knots * 1.852), 2)
                segments.append(
                    OperationalSegment(
                        segment_id=f"SEG-{seg_id_counter:03d}",
                        segment_type=OperationalSegmentType.DATA_GAP,
                        start_index=i,
                        end_index=i + 1,
                        duration_hours=seg_hrs,
                        distance_km=round(dist_to_next, 1),
                        mean_speed_knots=nominal_speed_knots,
                        mean_sic_pct=round(self.sic_lookup_fn(curr_lat, curr_lon), 1),
                        description=f"AIS tracking gap or satellite blackout ({round(dist_to_next)} km jump).",
                        is_non_transit_delay=False,
                    )
                )
                seg_id_counter += 1
                i += 1
                continue

            # 2. Check for PORT OR STATION OPERATIONS (near known stations/ports with low movement)
            near_loc = next(
                (loc for loc in KNOWN_LOCATIONS if haversine_km(curr_lat, curr_lon, loc["lat"], loc["lon"]) < loc["radius_km"]),
                None,
            )

            # Look ahead to see how many points remain localized
            j = i
            cluster_dist = 0.0
            while j < n - 1:
                step_d = point_distances[j + 1]
                if step_d < 4.0:  # slow drift or static
                    cluster_dist += step_d
                    j += 1
                else:
                    break

            cluster_length = j - i
            if cluster_length >= 3:
                # Localized activity block!
                duration = round(max(2.0, cluster_length * 1.5), 1)
                sic_val = self.sic_lookup_fn(curr_lat, curr_lon)

                if near_loc:
                    seg_type = OperationalSegmentType.PORT_STATION_OPERATIONS
                    desc = f"Berthing, cargo resupply, and scientific turnaround at {near_loc['name']}."
                    is_delay = True
                elif sic_val > 45.0:
                    # Trapped in ice or active ice-ramming
                    seg_type = OperationalSegmentType.ICE_AVOIDANCE
                    desc = f"Heavy pack ice penetration and ramming near {round(curr_lat, 2)}°S, {round(curr_lon, 2)}°E (SIC {round(sic_val)}%)."
                    is_delay = False
                elif cluster_length >= 8:
                    # Extensive deep sea science stop
                    seg_type = OperationalSegmentType.SCIENTIFIC_STOP
                    desc = f"Oceanographic CTD rosette cast / benthic coring station ({round(duration)} hrs)."
                    is_delay = True
                else:
                    # Weather heave-to or maneuvering
                    seg_type = OperationalSegmentType.WEATHER_HOLD
                    desc = "Vessel heaving-to or drifting in adverse weather / heavy swell."
                    is_delay = True

                segments.append(
                    OperationalSegment(
                        segment_id=f"SEG-{seg_id_counter:03d}",
                        segment_type=seg_type,
                        start_index=i,
                        end_index=j,
                        duration_hours=duration,
                        distance_km=round(cluster_dist, 1),
                        mean_speed_knots=round(cluster_dist / max(0.1, duration * 1.852), 1),
                        mean_sic_pct=round(sic_val, 1),
                        description=desc,
                        is_non_transit_delay=is_delay,
                    )
                )
                seg_id_counter += 1
                i = j
                continue

            # 3. Check for ICE AVOIDANCE detour
            sic_val = self.sic_lookup_fn(curr_lat, curr_lon)
            if sic_val >= 35.0:
                # Segment in moderate-to-heavy ice
                k = i
                ice_dist = 0.0
                while k < n - 1 and self.sic_lookup_fn(track[k][0], track[k][1]) >= 20.0 and (k - i) < 15:
                    ice_dist += point_distances[k + 1]
                    k += 1

                if k > i:
                    duration = round(ice_dist * hours_per_km * 1.4, 1)  # Ice transit takes longer
                    segments.append(
                        OperationalSegment(
                            segment_id=f"SEG-{seg_id_counter:03d}",
                            segment_type=OperationalSegmentType.ICE_AVOIDANCE,
                            start_index=i,
                            end_index=k,
                            duration_hours=duration,
                            distance_km=round(ice_dist, 1),
                            mean_speed_knots=round(nominal_speed_knots * 0.65, 1),
                            mean_sic_pct=round(sic_val, 1),
                            description=f"Tactical ice navigation and floe leads transit (SIC {round(sic_val)}%).",
                            is_non_transit_delay=False,
                        )
                    )
                    seg_id_counter += 1
                    i = k
                    continue

            # 4. Standard TRANSIT segment
            t_end = min(n - 1, i + 15)
            trans_d = cumulative_dist[t_end] - cumulative_dist[i]
            trans_hrs = round(trans_d * hours_per_km, 1)
            segments.append(
                OperationalSegment(
                    segment_id=f"SEG-{seg_id_counter:03d}",
                    segment_type=OperationalSegmentType.TRANSIT,
                    start_index=i,
                    end_index=t_end,
                    duration_hours=trans_hrs,
                    distance_km=round(trans_d, 1),
                    mean_speed_knots=nominal_speed_knots,
                    mean_sic_pct=round(self.sic_lookup_fn(curr_lat, curr_lon), 1),
                    description="Continuous open water / standard corridor transit.",
                    is_non_transit_delay=False,
                )
            )
            seg_id_counter += 1
            i = t_end

        # Aggregate time by operational category
        transit_hrs = sum(s.duration_hours for s in segments if s.segment_type == OperationalSegmentType.TRANSIT)
        sci_hrs = sum(s.duration_hours for s in segments if s.segment_type == OperationalSegmentType.SCIENTIFIC_STOP)
        weather_hrs = sum(s.duration_hours for s in segments if s.segment_type == OperationalSegmentType.WEATHER_HOLD)
        port_hrs = sum(s.duration_hours for s in segments if s.segment_type == OperationalSegmentType.PORT_STATION_OPERATIONS)
        man_hrs = sum(s.duration_hours for s in segments if s.segment_type == OperationalSegmentType.MANEUVERING)
        gap_hrs = sum(s.duration_hours for s in segments if s.segment_type == OperationalSegmentType.DATA_GAP)
        avoid_hrs = sum(s.duration_hours for s in segments if s.segment_type == OperationalSegmentType.ICE_AVOIDANCE)

        total_hrs = transit_hrs + sci_hrs + weather_hrs + port_hrs + man_hrs + gap_hrs + avoid_hrs

        return OperationalEventBreakdown(
            total_voyage_hours=round(total_hrs, 1),
            transit_hours=round(transit_hrs, 1),
            scientific_stops_hours=round(sci_hrs, 1),
            weather_holds_hours=round(weather_hrs, 1),
            port_station_hours=round(port_hrs, 1),
            maneuvering_hours=round(man_hrs, 1),
            data_gaps_hours=round(gap_hrs, 1),
            ice_avoidance_hours=round(avoid_hrs, 1),
            segments=segments,
        )
