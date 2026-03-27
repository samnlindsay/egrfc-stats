import sys
from pathlib import Path
import argparse
import os
from collections import defaultdict
import json

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Always resolve relative paths from the project root, regardless of cwd
os.chdir(project_root)

from python.backend import BackendConfig, BackendDatabase
from python.data import *
from python.charts import (
    squad_size_trend_chart,
    squad_continuity_average_chart,
    captains_chart,
    player_stats_appearances_chart,
    points_scorers_chart,
    cards_chart,
    team_sheets_chart,
    results_chart,
    set_piece_success_by_season_chart,
    lineout_success_by_zone_chart,
    lineout_breakdown_chart,
    set_piece_h2h_chart_backend,
    red_zone_performance_chart,
    lineout_analysis_chart_suite,
    lineout_analysis_panel_chart_suite,
    export_league_results_chart_specs,
)

from python.sync_headshots import run_sync, HEADSHOTS_DIR, TARGET_FILES
import altair as alt
from python.chart_helpers import *
import pandas as pd


############################
# Player Appearances Chart #
############################

def main(refresh_pitchero=False, backend_mode="canonical", backend_db_path="data/egrfc_backend.duckdb"):
    """Main update function using optimized data"""

    if backend_mode != "canonical":
        raise ValueError("Only canonical backend mode is supported.")

    try:
        db = BackendDatabase(config=BackendConfig(db_path=backend_db_path))
    except RuntimeError as exc:
        default_path = "data/egrfc_backend.duckdb"
        fallback_path = "data/egrfc_backend_alt.duckdb"
        if backend_db_path == default_path and "locked by another process" in str(exc):
            print(f"Default backend DB is locked. Falling back to {fallback_path}...")
            db = BackendDatabase(config=BackendConfig(db_path=fallback_path))
        else:
            raise
    db.build(refresh_pitchero=refresh_pitchero, export=True)

    # Keep backend player exports aligned with current headshot files and crop rules.
    recrop_result, sync_results, sync_total_updates = run_sync(
        write=True,
        headshots_dir=HEADSHOTS_DIR,
        targets=TARGET_FILES,
    )
    print(
        "Headshot sync: "
        f"checked={recrop_result.checked}, "
        f"needs_recrop={recrop_result.needs_recrop}, "
        f"recropped={recrop_result.recropped}, "
        f"updates={sync_total_updates}"
    )
    for result in sync_results:
        print(f"  - {result.path.relative_to(project_root)}: updates={result.updated_rows}")
    
    # Load league data
    print("Loading league data...")
    # db.load_league_data(season="2024-2025", league="Counties 1 Surrey/Sussex")
    
    print("Generating charts and data...")
    
    # Existing charts
    captains_chart(db)
    player_stats_appearances_chart(db)
    points_scorers_chart(db)
    cards_chart(db)
    team_sheets_chart(db)
    results_chart(db)

    set_piece_success_by_season_chart(db, layout="separate")
    set_piece_h2h_chart_backend(db, set_piece="Lineout", output_file="data/charts/lineout_h2h.json", bind_params=False)
    set_piece_h2h_chart_backend(db, set_piece="Scrum", output_file="data/charts/scrum_h2h.json", bind_params=False)
    red_zone_performance_chart(db, metric="points", output_file="data/charts/red_zone_points.json", bind_params=False)
    lineout_success_by_zone_chart(db)
    lineout_breakdown_chart(db, squad="1st")
    lineout_breakdown_chart(db, squad="2nd")
    lineout_analysis_chart_suite(db)
    lineout_analysis_panel_chart_suite(db)
    squad_size_trend_chart(db)
    squad_continuity_average_chart(db)
    export_league_results_chart_specs(db)

    print("All charts and data generated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update EGRFC stats and regenerate chart outputs")
    parser.add_argument(
        "--refresh-pitchero",
        action="store_true",
        help="Force refresh of Pitchero stats from the website (otherwise uses local cache if present)",
    )
    parser.add_argument(
        "--backend-mode",
        choices=["canonical"],
        default="canonical",
        help="Data backend to use when building chart outputs",
    )
    parser.add_argument(
        "--db-path",
        default="data/egrfc_backend.duckdb",
        help="DuckDB path for canonical backend mode (falls back to data/egrfc_backend_alt.duckdb if default is locked)",
    )

    args = parser.parse_args()
    main(
        refresh_pitchero=args.refresh_pitchero,
        backend_mode=args.backend_mode,
        backend_db_path=args.db_path,
    )