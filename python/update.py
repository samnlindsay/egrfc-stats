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
    squad_position_composition_chart,
    squad_size_trend_chart,
    squad_continuity_average_chart,
    squad_overlap_chart,
    captains_chart,
    player_stats_motm_chart,
    player_stats_appearances_chart,
    player_stats_starting_combinations_chart,
    player_full_profile_appearances_per_season_chart,
    player_full_profile_position_donut_chart,
    player_full_profile_career_timeline_chart,
    points_scorers_chart,
    team_sheets_chart,
    opposition_profile_team_sheets_chart,
    results_chart,
    team_stats_results_chart,
    set_piece_success_by_season_chart,
    lineout_success_by_zone_chart,
    lineout_breakdown_chart_suite,
    lineout_trend_chart_suite,
    set_piece_h2h_chart_backend,
    season_match_metric_trends_chart,
    match_metric_compare_scatter_chart,
    red_zone_performance_chart,
    set_piece_attacking_volume_chart,
    red_zone_entries_efficiency_chart,
    lineout_analysis_chart_suite,
    league_history_progression_chart,
    export_league_context_chart_specs,
    export_league_results_chart_specs,
)

from python.sync_headshots import run_sync, HEADSHOTS_DIR, TARGET_FILES
from python.logos import export_logos_manifest
from python.league_data import (
    build_league_tables_json,
    get_active_season_squad_pairs,
    get_current_season_label,
    normalize_season_arg,
    update_league_data,
    update_multiple_seasons_and_squads,
)
import altair as alt
from python.chart_helpers import *
import pandas as pd


############################
# Player Appearances Chart #
############################

def main(
    refresh_pitchero=False,
    backend_mode="canonical",
    backend_db_path="data/egrfc_backend.duckdb",
    run_rfu_refresh=True,
    rfu_all=False,
    rfu_squad=None,
    rfu_season=None,
    rfu_all_teams=False,
    rfu_matches_file="data/matches.json",
):
    """Main update function using optimized data"""

    # Generate logos manifest for frontend
    export_logos_manifest(Path("data") / "logos.json", Path("img") / "logos")

    print("Loading League History...")
    extractor = DataExtractor()
    league_history_df = extractor.extract_league_history()

    normalized_rfu_season = normalize_season_arg(rfu_season) if rfu_season else None
    table_refresh_seasons = None

    if run_rfu_refresh:
        print("Refreshing RFU matches/team sheets before backend build...")
        selected_pairs = get_active_season_squad_pairs(league_history_df=league_history_df)

        if rfu_squad is not None:
            valid_squads = sorted({squad for _, squad in selected_pairs})
            if valid_squads and rfu_squad not in valid_squads:
                raise ValueError(f"Invalid --rfu-squad value '{rfu_squad}'. Valid options: {valid_squads}")

        if normalized_rfu_season:
            valid_seasons = sorted({season for season, squad in selected_pairs if rfu_squad is None or squad == rfu_squad})
            if valid_seasons and normalized_rfu_season not in valid_seasons:
                raise ValueError(
                    f"Invalid --rfu-season value '{rfu_season}'. "
                    f"Valid options: {', '.join(valid_seasons)}"
                )

        if rfu_all:
            table_refresh_seasons = [normalized_rfu_season] if normalized_rfu_season else None
            update_multiple_seasons_and_squads(
                seasons=[normalized_rfu_season] if normalized_rfu_season else None,
                squads=[rfu_squad] if rfu_squad is not None else None,
                consolidated_file=rfu_matches_file,
                league_history_df=league_history_df,
                refresh_missing_lineups=rfu_all_teams,
            )
        elif rfu_squad is not None and normalized_rfu_season:
            table_refresh_seasons = [normalized_rfu_season]
            update_league_data(
                squad=rfu_squad,
                season=normalized_rfu_season,
                consolidated_file=rfu_matches_file,
                league_history_df=league_history_df,
                refresh_missing_lineups=rfu_all_teams,
            )
        elif normalized_rfu_season:
            table_refresh_seasons = [normalized_rfu_season]
            update_multiple_seasons_and_squads(
                seasons=[normalized_rfu_season],
                squads=[rfu_squad] if rfu_squad is not None else None,
                consolidated_file=rfu_matches_file,
                league_history_df=league_history_df,
                refresh_missing_lineups=rfu_all_teams,
            )
        elif rfu_squad is not None:
            table_refresh_seasons = None
            update_multiple_seasons_and_squads(
                seasons=None,
                squads=[rfu_squad],
                consolidated_file=rfu_matches_file,
                league_history_df=league_history_df,
                refresh_missing_lineups=rfu_all_teams,
            )
        else:
            # Default RFU behavior in update.py: refresh current season across active squads.
            table_refresh_seasons = [get_current_season_label()]
            update_multiple_seasons_and_squads(
                seasons=[get_current_season_label()],
                squads=None,
                consolidated_file=rfu_matches_file,
                league_history_df=league_history_df,
                refresh_missing_lineups=rfu_all_teams,
            )

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
    player_stats_motm_chart(db)
    player_stats_appearances_chart(db)
    player_stats_starting_combinations_chart(db)
    player_full_profile_appearances_per_season_chart(db)
    player_full_profile_position_donut_chart(db)
    player_full_profile_career_timeline_chart(db)
    points_scorers_chart(db)
    team_sheets_chart(db)
    opposition_profile_team_sheets_chart(db)
    results_chart(db)
    results_chart(db, output_file='data/charts/opposition_results.json', facet_by_season=True)
    team_stats_results_chart(db)

    set_piece_success_by_season_chart(db, layout="separate")
    set_piece_attacking_volume_chart(db, layout="separate", bind_params=False)
    set_piece_h2h_chart_backend(db, set_piece="Lineout", output_file="data/charts/lineout_h2h.json")
    set_piece_h2h_chart_backend(db, set_piece="Scrum", output_file="data/charts/scrum_h2h.json")
    season_match_metric_trends_chart(db, output_file="data/charts/season_match_metric_trends.json")
    match_metric_compare_scatter_chart(db, output_file="data/charts/match_metric_compare_scatter.json")
    red_zone_performance_chart(db, metric="points", output_file="data/charts/red_zone_points.json", bind_params=False)
    red_zone_entries_efficiency_chart(db, output_file="data/charts/red_zone_entries_efficiency.json", bind_params=False)
    lineout_success_by_zone_chart(db)
    lineout_breakdown_chart_suite(db)
    lineout_trend_chart_suite(db)
    lineout_analysis_chart_suite(db)
    squad_size_trend_chart(db)
    squad_position_composition_chart(db)
    squad_overlap_chart(db)
    squad_continuity_average_chart(db)
    league_history_progression_chart(db)
    export_league_context_chart_specs(db, squads=("1st",))
    export_league_results_chart_specs(db)
    if run_rfu_refresh:
        build_league_tables_json(
            league_history_df=league_history_df,
            seasons=table_refresh_seasons,
            squads=[rfu_squad] if rfu_squad is not None else None,
            preserve_existing=True,
        )
    else:
        print("Skipping league table refresh (RFU refresh disabled).")

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
    parser.add_argument(
        "--skip-rfu-refresh",
        action="store_true",
        help="Skip RFU match/team-sheet refresh step and build backend/charts from existing data/matches.json",
    )
    parser.add_argument(
        "--rfu-all",
        action="store_true",
        help="Refresh all available RFU seasons/squads (or constrained by --rfu-season/--rfu-squad)",
    )
    parser.add_argument(
        "--rfu-season",
        default=None,
        help="RFU season to refresh (YYYY/YY or YYYY-YYYY), e.g. 2025/26",
    )
    parser.add_argument(
        "--rfu-squad",
        type=int,
        default=None,
        help="RFU squad number to refresh, e.g. 1 or 2",
    )
    parser.add_argument(
        "--rfu-all-teams",
        action="store_true",
        help="Retry played fixtures missing one/both lineups to improve league-wide squad size/returners coverage",
    )
    parser.add_argument(
        "--rfu-matches-file",
        default="data/matches.json",
        help="Path to consolidated RFU match store used by backend build",
    )

    args = parser.parse_args()
    main(
        refresh_pitchero=args.refresh_pitchero,
        backend_mode=args.backend_mode,
        backend_db_path=args.db_path,
        run_rfu_refresh=not args.skip_rfu_refresh,
        rfu_all=args.rfu_all,
        rfu_squad=args.rfu_squad,
        rfu_season=args.rfu_season,
        rfu_all_teams=args.rfu_all_teams,
        rfu_matches_file=args.rfu_matches_file,
    )