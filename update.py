# Executable python script to update data and charts (as in Analysis.ipynb)
# Usage: python update.py

from data_prep import *
from charts import *
from video_analysis import *
from team_sheets import *

# Load data
game_df = team_sheets()
players_df = players(game_df)
players_agg_df = players_agg(players_df)
lineouts_df = lineouts()
pitchero_df = pitchero_stats()
set_piece_df = set_piece_results()
analysis = game_stats()
 
# Save data
game_df.to_csv('data/game.csv', index=False)
players_df.to_csv('data/players.csv', index=False)
players_agg_df.to_csv('data/players_agg.csv', index=False)
set_piece_df.to_csv('data/set_piece.csv', index=False)
analysis.to_csv('data/analysis.csv', index=False)

# Update tables
update_season_summaries(game_df, seasons)
set_piece_summaries(set_piece_df)
top_players_summary(players_agg_df)

# One-off charts (only source data needs updating)
captains_chart(file='Charts/captains.html')
results_chart(file='Charts/results.html')
plot_games_by_player(file='Charts/appearances.html')
plot_starts_by_position(file='Charts/positions.html')
card_chart(file='Charts/cards.html')
points_scorers_chart(file='Charts/points.html')
team_sheets_chart(file='Charts/team-sheets.html')
set_piece_h2h_chart(file='Charts/set-piece.html')
squad_continuity_chart(file='Charts/continuity.html')

# Self-contained charts (chart needs updating)
game_stats_charts(analysis, file='Charts/video_analysis.html')
lineout_success(types=types, file='Charts/lineouts.html')