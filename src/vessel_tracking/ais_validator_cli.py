"""Validation and Diagnostic Reporting Utility for Historical AIS Datasets.

Phase 1: Historical AIS Data Layer
Reports vessel counts, voyages, point counts, date ranges, data completeness,
invalid records breakdown, and geographic coverage.
"""
import os
import sys
import argparse
import json
from typing import Optional, Dict, Any

from src.vessel_tracking.ais_pipeline import AISPipeline
from src.vessel_tracking.ais_schema import AISDatasetSummary


def run_ais_validation_report(
    data_path: Optional[str] = None,
    max_gap_hours: float = 24.0,
    output_json: bool = False
) -> Dict[str, Any]:
    """Run validation pipeline on an AIS dataset or directory and generate a diagnostic report."""
    if data_path is None:
        # Default to raw vessel tracks directory
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_path = os.path.join(base_dir, "data", "raw", "vessel_tracks")

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"AIS data path does not exist: {data_path}")

    pipeline = AISPipeline(max_gap_hours=max_gap_hours)
    voyages, summary, issues = pipeline.process(data_path)

    report = {
        "dataset_path": os.path.abspath(data_path),
        "summary": summary.to_dict(),
        "voyage_details": [
            {
                "voyage_id": v.voyage_id,
                "vessel_name": v.vessel_name,
                "points": len(v.points),
                "distance_km": round(v.total_distance_km, 1),
                "duration_hours": round(v.duration_hours, 1),
                "avg_speed_kn": round(v.avg_speed_knots, 1),
                "start": v.start_time.isoformat() if v.start_time else None,
                "end": v.end_time.isoformat() if v.end_time else None,
                "bbox": v.bbox
            }
            for v in voyages
        ],
        "top_issues_sample": [iss.to_dict() for iss in issues[:10]]
    }

    if not output_json:
        _print_human_report(report)

    return report


def _print_human_report(report: Dict[str, Any]) -> None:
    """Format and print an operational terminal report."""
    s = report["summary"]
    geo = s.get("geographic_coverage", {})
    dr = s.get("date_range", {})
    issues = s.get("invalid_breakdown", {})

    print("\n" + "=" * 76)
    print("      POLARNAV HISTORICAL AIS DATA VALIDATION & RECONSTRUCTION REPORT      ")
    print("=" * 76)
    print(f" Dataset Path:      {report['dataset_path']}")
    print(f" Unique Vessels:    {s['vessels_count']} ({', '.join(s.get('vessel_names', [])[:4])}...)")
    print(f" Total Raw Records: {s['points_count']:,}")
    print(f" Valid AIS Points:  {s['valid_points_count']:,} ({round((s['valid_points_count']/max(1, s['points_count']))*100, 1)}%)")
    print(f" Segmented Voyages: {s['voyages_count']}")
    print("-" * 76)
    print(f" Date Range:        {dr.get('start', 'N/A')}  -->  {dr.get('end', 'N/A')}")
    print(f" Geographic Extent: Lat [{geo.get('min_lat', 0.0):.2f}°, {geo.get('max_lat', 0.0):.2f}°] | Lon [{geo.get('min_lon', 0.0):.2f}°, {geo.get('max_lon', 0.0):.2f}°]")
    print(f" Missing Field Pct: {s['missing_data_pct']}% (speed/heading/course)")
    print("-" * 76)
    print(f" Invalid Records:   {s['invalid_records_count']:,}")
    if issues:
        for issue_type, count in issues.items():
            print(f"   • {issue_type:<24}: {count:,}")
    else:
        print("   • Zero critical schema violations detected.")
    print("-" * 76)
    print(" Reconstructed Voyages Sample:")
    for idx, v in enumerate(report["voyage_details"][:5], 1):
        print(f"   {idx}. {v['voyage_id']:<32} | {v['points']:>5} pts | {v['distance_km']:>8.1f} km | {v['duration_hours']:>6.1f} h | Avg {v['avg_speed_kn']:>4.1f} kn")
    if len(report["voyage_details"]) > 5:
        print(f"   ... and {len(report['voyage_details']) - 5} additional segmented voyages.")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate and report historical AIS datasets.")
    parser.add_argument("--data-path", type=str, default=None, help="Path to AIS file or directory.")
    parser.add_argument("--max-gap-hours", type=float, default=24.0, help="Max gap hours before segmenting voyages.")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    args = parser.parse_args()

    report_data = run_ais_validation_report(
        data_path=args.data_path,
        max_gap_hours=args.max_gap_hours,
        output_json=args.json
    )

    if args.json:
        print(json.dumps(report_data, indent=2))
