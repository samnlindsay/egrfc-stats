from data_prep import *
from charts import *
from players import *
from video_analysis import *
from team_sheets import *

def main():
    """Main update function using optimized data"""
    print("Loading optimized data...")
    
    # Load optimized data
    matches_df = load_matches()
    appearances_df = load_player_appearances()
    players_agg_df = players_agg_optimized()
    lineouts_df = load_lineouts()
    setpiece_df = load_set_piece()
    analysis = game_stats()
    
    print(f"Loaded {len(matches_df)} matches")
    print(f"Loaded {len(appearances_df)} player appearances")
    print(f"Loaded {len(lineouts_df)} lineouts")
    
    # Save optimized data to JSON
    matches_df.to_json('data/matches.json', orient='records')
    appearances_df.to_json('data/appearances.json', orient='records')
    players_agg_df.to_json('data/players_agg.json', orient='records')
    lineouts_df.to_json('data/lineouts.json', orient='records')
    setpiece_df.to_json('data/set_piece.json', orient='records')
    analysis.to_json('data/analysis.json', orient='records')
    
    print("Data saved to JSON files")
    
    # Update summary tables
    seasons = ["2021/22", "2022/23", "2023/24", "2024/25"]
    update_season_summaries(matches_df, seasons)
    
    # Generate charts with optimized data
    print("Generating charts...")
    plot_games_by_player(df=players_agg_df, file='Charts/appearances.html')
    game_stats_charts(analysis, file='Charts/video_analysis.html')
    player_profile_charts()
    
    # Enhanced analysis with new data structure
    continuity_df = squad_continuity_analysis()
    continuity_df.to_json('data/squad_continuity.json', orient='records')
    
    positional_df = player_positional_analysis()
    positional_df.to_json('data/positional_analysis.json', orient='records')
    
    print("Update complete!")

if __name__ == "__main__":
    main()