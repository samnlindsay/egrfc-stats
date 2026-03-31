import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from python.backend import build_backend


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canonical EGRFC backend database")
    parser.add_argument(
        "--refresh-pitchero",
        action="store_true",
        help="Refresh Pitchero web-derived caches from source (season stats + historic team sheets)",
    )
    parser.add_argument(
        "--db-path",
        default="data/egrfc_backend.duckdb",
        help="DuckDB output path (useful if default DB file is locked)",
    )
    parser.add_argument(
        "--export-dir",
        default="data/backend",
        help="Directory for JSON/Parquet exports",
    )
    parser.add_argument(
        "--strict-duplicate-audit",
        action="store_true",
        help=(
            "Fail the build if duplicate fixture groups are detected "
            "(same date/squad/venue/score but different opposition names)."
        ),
    )
    parser.add_argument("--no-export", action="store_true", help="Skip exporting JSON/Parquet artifacts")
    parser.add_argument(
        "--no-supplemental-enrichment",
        action="store_true",
        help="Skip post-build URL/scorer supplementation from reconciliation artifacts",
    )
    args = parser.parse_args()

    build_backend(
        refresh_pitchero=args.refresh_pitchero,
        export=not args.no_export,
        db_path=args.db_path,
        export_dir=args.export_dir,
        strict_duplicate_audit=args.strict_duplicate_audit,
        apply_supplemental_enrichment=not args.no_supplemental_enrichment,
    )


if __name__ == "__main__":
    main()