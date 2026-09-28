"""Environmental Replay Pipeline.

Phase 2: Historical Environmental Replay Dataset.
Transforms Phase 1 AIS trajectories into co-located, leak-free environmental training sets.
"""
import os
import json
import logging
from typing import List, Dict, Tuple, Optional, Any
import pandas as pd

from src.vessel_tracking.ais_schema import AISRecord, VoyageSegment
from src.vessel_tracking.ais_pipeline import AISPipeline
from src.environmental_replay.replay_schema import EnrichedAISFeaturePoint, ReplayDatasetSummary
from src.environmental_replay.environmental_matcher import EnvironmentalMatcher

logger = logging.getLogger("polarnav.replay_pipeline")


class EnvironmentalReplayPipeline:
    """End-to-end pipeline generating historical environmental replay datasets."""

    def __init__(self, matcher: Optional[EnvironmentalMatcher] = None):
        self.matcher = matcher or EnvironmentalMatcher()
        self.ais_pipeline = AISPipeline()

    def process_records(
        self,
        records: List[AISRecord],
        voyage_id: str = "voyage_01"
    ) -> List[EnrichedAISFeaturePoint]:
        """Enrich a list of validated AIS records with leak-free environmental features."""
        enriched_points: List[EnrichedAISFeaturePoint] = []
        for r in records:
            pt = self.matcher.match_point(r, voyage_id=voyage_id)
            enriched_points.append(pt)
        return enriched_points

    def process_voyages(
        self,
        voyages: List[VoyageSegment]
    ) -> List[EnrichedAISFeaturePoint]:
        """Process reconstructed voyage segments and associate environmental conditions."""
        all_enriched: List[EnrichedAISFeaturePoint] = []
        for v in voyages:
            for track_pt in v.points:
                rec = track_pt.record
                pt = self.matcher.match_point(rec, voyage_id=v.voyage_id)
                all_enriched.append(pt)
        return all_enriched

    def process_file_or_dir(
        self,
        source_path: str
    ) -> Tuple[List[EnrichedAISFeaturePoint], ReplayDatasetSummary]:
        """Run full Phase 1 + Phase 2 ingestion, reconstruction, segmentation, and environmental replay."""
        voyages, ais_summary, issues = self.ais_pipeline.process(source_path)
        enriched_points = self.process_voyages(voyages)
        summary = self.generate_summary(enriched_points, total_raw_points=ais_summary.points_count)
        return enriched_points, summary

    def export_dataset(
        self,
        enriched_points: List[EnrichedAISFeaturePoint],
        output_path: str,
        format: str = "json"
    ) -> str:
        """Export standardized enriched dataset to JSON, CSV, or Parquet."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        dicts = [p.to_dict() for p in enriched_points]

        if format.lower() == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"features": dicts}, f, indent=2)
        elif format.lower() == "csv":
            df = pd.DataFrame(dicts)
            # Flatten quality_flags and missing_variables
            df["quality_flags"] = df["quality_flags"].apply(json.dumps)
            df["missing_variables"] = df["missing_variables"].apply(json.dumps)
            df.to_csv(output_path, index=False)
        elif format.lower() in ("parquet", "pq"):
            df = pd.DataFrame(dicts)
            df["quality_flags"] = df["quality_flags"].apply(json.dumps)
            df["missing_variables"] = df["missing_variables"].apply(json.dumps)
            df.to_parquet(output_path, index=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        return output_path

    def generate_summary(
        self,
        enriched_points: List[EnrichedAISFeaturePoint],
        total_raw_points: Optional[int] = None
    ) -> ReplayDatasetSummary:
        """Calculate quality and coverage diagnostics over enriched feature points."""
        total = total_raw_points if total_raw_points is not None else len(enriched_points)
        matched = len(enriched_points)
        unmatched = max(0, total - matched)
        match_rate = round((matched / max(1, total)) * 100.0, 2)

        missing_breakdown: Dict[str, int] = {}
        quality_breakdown: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "DEGRADED": 0}

        sics = []
        depths = []
        risks = []

        start_time = None
        end_time = None

        min_lat, max_lat = 90.0, -90.0
        min_lon, max_lon = 180.0, -180.0

        for pt in enriched_points:
            sics.append(pt.sic_percent)
            depths.append(pt.bathymetry_depth_m)
            risks.append(pt.environmental_risk_score)

            q = pt.quality_flags.get("overall", "MEDIUM")
            quality_breakdown[q] = quality_breakdown.get(q, 0) + 1

            for mv in pt.missing_variables:
                missing_breakdown[mv] = missing_breakdown.get(mv, 0) + 1

            if start_time is None or pt.timestamp < start_time:
                start_time = pt.timestamp
            if end_time is None or pt.timestamp > end_time:
                end_time = pt.timestamp

            min_lat = min(min_lat, pt.latitude)
            max_lat = max(max_lat, pt.latitude)
            min_lon = min(min_lon, pt.longitude)
            max_lon = max(max_lon, pt.longitude)

        mean_sic = round(sum(sics) / len(sics), 2) if sics else 0.0
        mean_depth = round(sum(depths) / len(depths), 1) if depths else 0.0
        mean_risk = round(sum(risks) / len(risks), 3) if risks else 0.0

        if not enriched_points:
            min_lat, max_lat, min_lon, max_lon = 0.0, 0.0, 0.0, 0.0

        return ReplayDatasetSummary(
            total_points=total,
            matched_points=matched,
            unmatched_points=unmatched,
            match_rate_pct=match_rate,
            missing_variables_breakdown=missing_breakdown,
            temporal_coverage={
                "start": start_time.isoformat() if start_time else None,
                "end": end_time.isoformat() if end_time else None
            },
            spatial_coverage={
                "min_lat": round(min_lat, 2),
                "max_lat": round(max_lat, 2),
                "min_lon": round(min_lon, 2),
                "max_lon": round(max_lon, 2)
            },
            quality_breakdown=quality_breakdown,
            mean_sic_pct=mean_sic,
            mean_depth_m=mean_depth,
            mean_risk_score=mean_risk
        )
