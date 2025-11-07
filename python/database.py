"""
Database operations and query functions
"""
import duckdb
import pandas as pd
from new_data import DataExtractor

"""
Database schema definitions for EGRFC stats
"""

CORE_TABLES = {
    'games': {
        'description': 'One row per game with basic match information',
        'columns': [
            'game_id TEXT PRIMARY KEY',
            'date DATE',
            'season TEXT',
            'squad TEXT',  # '1st' or '2nd'
            'competition TEXT',
            'game_type TEXT',  # 'League', 'Cup', 'Friendly'
            'opposition TEXT',
            'home_away TEXT',  # 'H' or 'A'
            'pf INTEGER',  # Points For
            'pa INTEGER',  # Points Against
            'result TEXT',  # 'W', 'L', 'D'
            'margin INTEGER',
            'captain TEXT',
            'vc1 TEXT',
            'vc2 TEXT'
        ]
    },
    
    'player_appearances': {
        'description': 'One row per player per game',
        'columns': [
            'appearance_id TEXT PRIMARY KEY',
            'game_id TEXT',
            'player TEXT',
            'shirt_number INTEGER',
            'position TEXT',
            'position_group TEXT',
            'unit TEXT',  # 'Forwards', 'Backs', 'Bench'
            'is_starter BOOLEAN',
            'is_captain BOOLEAN',
            'is_vc BOOLEAN',
            'player_join TEXT',
            'FOREIGN KEY (game_id) REFERENCES games(game_id)'
        ]
    },
    
    'lineouts': {
        'description': 'One row per lineout',
        'columns': [
            'lineout_id TEXT PRIMARY KEY',
            'game_id TEXT',
            'numbers TEXT',
            'call TEXT',
            'call_type TEXT',
            'setup TEXT',
            'movement TEXT',
            'area TEXT',  # Front, Middle, Back
            'hooker TEXT',
            'jumper TEXT',
            'won BOOLEAN',
            'drive BOOLEAN',
            'crusaders BOOLEAN',
            'transfer BOOLEAN',
            'flyby INTEGER',
            'FOREIGN KEY (game_id) REFERENCES games(game_id)'
        ]
    },

    'pitchero_stats': {
        'description': 'Season statistics per player (from Pitchero)',
        'columns': [
            'season TEXT', 
            'squad TEXT',
            'player_join TEXT', 
            'A INTEGER', 
            'event TEXT',
            'count INTEGER'
        ]
    },
    
    'set_piece_stats': {
        'description': 'Set piece statistics per game',
        'columns': [
            'game_id TEXT',
            'team TEXT',  # 'EG' or 'Opp'
            'set_piece TEXT',  # 'Lineout' or 'Scrum'
            # other columns...
            'PRIMARY KEY (game_id, team, set_piece)',
            'won INTEGER',
            'lost INTEGER',
            'total INTEGER',
            'FOREIGN KEY (game_id) REFERENCES games(game_id)'
        ]
    },

    'league_matches': {
        'description': 'League match data from England Rugby website',
        'columns': [
            'match_id TEXT PRIMARY KEY',
            'season TEXT',
            'league TEXT', 
            'date DATE',
            'home_team TEXT',
            'away_team TEXT',
            'home_score INTEGER',
            'away_score INTEGER',
            'home_logo TEXT',
            'away_logo TEXT',
            'eg_squad TEXT',  # Which EG squad (1st/2nd) if applicable
            'eg_home_away TEXT',  # H/A from EG perspective
            'eg_score INTEGER',  # EG score
            'opp_score INTEGER'  # Opposition score
        ]
    },
    
    'league_players': {
        'description': 'Player appearances in league matches',
        'columns': [
            'appearance_id TEXT PRIMARY KEY',
            'match_id TEXT',
            'team TEXT',
            'player TEXT',
            'position TEXT',
            'shirt_number TEXT',
            'unit TEXT',  # Forwards, Backs, Bench
            'FOREIGN KEY (match_id) REFERENCES league_matches(match_id)'
        ]
    }
    
    # 'squad_continuity': {
    #     'description': 'Squad retention between games',
    #     'columns': [
    #         'game_id TEXT PRIMARY KEY',
    #         'forwards_retained INTEGER',
    #         'backs_retained INTEGER',
    #         'starters_retained INTEGER',
    #         'full_squad_retained INTEGER',
    #         'FOREIGN KEY (game_id) REFERENCES games(game_id)'
    #     ]
    # },
    
    # 'player_stats': {
    #     'description': 'Season statistics per player (from Pitchero)',
    #     'columns': [
    #         'stat_id TEXT PRIMARY KEY',
    #         'season TEXT',
    #         'squad TEXT',
    #         'player TEXT',
    #         'appearances INTEGER',
    #         'tries INTEGER',
    #         'conversions INTEGER',
    #         'penalties INTEGER',
    #         'drop_goals INTEGER',
    #         'yellow_cards INTEGER',
    #         'red_cards INTEGER',
    #         'points INTEGER'
    #     ]
    # }
}

def create_database_schema(con):
    """Create all tables in the database"""
    for table_name, table_info in CORE_TABLES.items():
        columns_sql = ', '.join(table_info['columns'])
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_sql})"
        con.execute(sql)
        print(f"Created table: {table_name}") 


class DatabaseManager:
    def __init__(self, db_path=":memory:"):
        self.con = duckdb.connect(db_path)
        create_database_schema(self.con)
        
    def load_source_data(self):
        """Load all source data from Google Sheets"""
        extractor = DataExtractor()
        
        # Extract and load games
        games_df = extractor.extract_games_data()
        self.con.execute("DELETE FROM games")
        self.con.execute("INSERT INTO games SELECT * FROM games_df")
        print(f"Loaded {len(games_df)} games")
        
        # Extract and load player appearances
        appearances_df = extractor.extract_player_appearances()
        self.con.execute("DELETE FROM player_appearances")
        self.con.execute("INSERT INTO player_appearances SELECT * FROM appearances_df")
        print(f"Loaded {len(appearances_df)} player appearances")

        # Extract and load Pitchero stats
        pitchero_df = extractor.extract_pitchero_stats()
        self.con.execute("DELETE FROM pitchero_stats")
        self.con.execute("INSERT INTO pitchero_stats SELECT * FROM pitchero_df")
        print(f"Loaded {len(pitchero_df)} Pitchero stats")

        # Extract and load set piece stats
        set_piece_df = extractor.extract_set_piece_stats()
        self.con.execute("DELETE FROM set_piece_stats")
        self.con.execute("INSERT INTO set_piece_stats SELECT * FROM set_piece_df")
        print(f"Loaded {len(set_piece_df)} set piece stats")
        
        # # Extract and load lineouts
        # lineouts_df = extractor.extract_lineouts_data()
        # self.con.execute("DELETE FROM lineouts")
        # self.con.execute("INSERT INTO lineouts SELECT * FROM lineouts_df")
        # print(f"Loaded {len(lineouts_df)} lineouts")
        
        print("Source data loaded successfully")
