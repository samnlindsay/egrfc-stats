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
    parser.add_argument("--no-export", action="store_true", help="Skip exporting JSON/Parquet artifacts")
    args = parser.parse_args()

    build_backend(
        refresh_pitchero=args.refresh_pitchero,
        export=not args.no_export,
        db_path=args.db_path,
        export_dir=args.export_dir,
    )


if __name__ == "__main__":
    main()