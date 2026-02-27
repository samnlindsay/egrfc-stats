"""
Extract data from Google Sheets and load into database
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import duckdb
from datetime import datetime
import re
import requests
from bs4 import BeautifulSoup
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_name(name):
    name_dict = {
        "Sam Lindsay": "S Lindsay 2",
        "Sam Lindsay-McCall": "S Lindsay",
        "James Mitchell": "T Mitchell",
    }
    
    if name in name_dict:
        return name_dict[name]
    
    initial = name.split(" ")[0][0]
    surname = " ".join(name.split(" ")[1:])
    surname = surname.replace("'", "'")
    name_clean = f"{initial} {surname}"
    return name_clean.strip().title()

class DataExtractor:
    def __init__(self, credentials_path='client_secret.json'):
        self.scope = ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/drive']
        # Convert to absolute path if relative
        if not os.path.isabs(credentials_path):
            # Get the directory of this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            credentials_path = os.path.join(script_dir, credentials_path)
        self.creds = Credentials.from_service_account_file(credentials_path, scopes=self.scope)
        self.client = gspread.authorize(self.creds)
        self.sheet_url = "https://docs.google.com/spreadsheets/d/1pcO8iEpZuds9AWs4AFRmqJtx5pv5QGbP4yg2dEkl8fU/edit"
        
    def extract_games_data(self):
        """Extract games data from team sheets"""
        ss = self.client.open_by_url(self.sheet_url)
        
        games_data = []
        
        for squad_name, sheet_name in [("1st", "1st XV Players"), ("2nd", "2nd XV Players")]:
            sheet = ss.worksheet(sheet_name)
            data = sheet.get_all_values()
            
            # Skip header rows
            for row in data[5:]:  # Assuming data starts at row 6
                if not row[1]:  # Skip if no season
                    continue
                    
                game_data = self._parse_game_row(row, squad_name)
                if game_data:
                    games_data.append(game_data)
        
        return pd.DataFrame(games_data)
    
    def _parse_game_row(self, row, squad):
        """Parse a single game row from team sheet"""
        try:
            # Map columns - adjust indices based on your sheet structure
            date = self._parse_date(row[0])
            season = row[1]
            competition = row[2]
            opposition_raw = row[3]
            score = row[4]
            captain = row[5]
            vc1 = row[6]
            vc2 = row[7]
            
            # Parse opposition and home/away
            home_away = 'H' if '(H)' in opposition_raw else 'A'
            opposition = opposition_raw.replace('(H)', '').replace('(A)', '').strip()
            
            if not opposition:
                return None
                
            # Parse score
            pf, pa = self._parse_score(score, home_away)
            
            # Determine result
            if pf is None or pa is None:
                result = None
                margin = None
            else:
                result = 'W' if pf > pa else 'L' if pf < pa else 'D' if pf == pa else None
                margin = abs(pf - pa) if pf is not None and pa is not None else None
            
            game_id = f"{date}_{squad}_{opposition}".replace(' ', '_').replace('/', '')
            
            return {
                'game_id': game_id,
                'date': date,
                'season': season,
                'squad': squad,
                'competition': competition,
                'game_type': self._classify_game_type(competition),
                'opposition': opposition,
                'home_away': home_away,
                'pf': pf,
                'pa': pa,
                'result': result,
                'margin': margin,
                'captain': captain,
                'vc1': vc1,
                'vc2': vc2
            }
        except Exception as e:
            print(f"Error parsing game row: {e}")
            return None
    
    def extract_player_appearances(self, include_pitchero_stats=False):
        """Extract player appearances from team sheets"""
        ss = self.client.open_by_url(self.sheet_url)
        
        appearances_data = []

        for squad_name, sheet_name in [("1st", "1st XV Players"), ("2nd", "2nd XV Players")]:
            sheet = ss.worksheet(sheet_name)
            data = sheet.get_all_values()
            
            for row in data[5:]:
                if not row[1]:  # Skip if no season
                    continue
                    
                # Extract game info
                date = self._parse_date(row[0])
                opposition = row[3].replace('(H)', '').replace('(A)', '').strip()
                game_id = f"{date}_{squad_name}_{opposition}".replace(' ', '_').replace('/', '')
                captain = row[5]
                vc1 = row[6]
                vc2 = row[7]
                
                # Extract players (positions 1-29, columns 8-36)
                for pos in range(1, 30):
                    col_idx = 7 + pos  # Adjust based on your sheet structure
                    if col_idx < len(row):
                        player = row[col_idx].strip()
                        if player:
                            appearance_data = {
                                'appearance_id': f"{game_id}_{pos}",
                                'game_id': game_id,
                                'player': player,
                                'shirt_number': pos,
                                'position': self._get_position(pos),
                                'position_group': self._get_position_group(pos),
                                'unit': self._get_unit(pos),
                                'is_starter': pos <= 15,
                                'is_captain': player == captain,
                                'is_vc': player in [vc1, vc2],
                                'player_join': clean_name(player)
                            }
                            appearances_data.append(appearance_data)
        
        return pd.DataFrame(appearances_data)
    
    def extract_pitchero_stats(self):

        season_ids = {
            "2016/17": 42025,
            "2017/18": 47693,
            "2018/19": 52304,
            "2019/20": 68499,
            "2021/22": 79578,
            "2022/23": 83980,
            "2023/24": 87941,
            "2024/25": 91673,
            "2025/26": 94981,
        }

        score_map = {
            "T": 5,
            "Con": 2,
            "PK": 3,
            "DG": 3,
        }

        dfs = []
        for squad in [1, 2]:
            for season in season_ids.keys():
                url = f"https://www.egrfc.com/teams/14206{8 if squad==1 else 9}/statistics?season={season_ids[season]}"    
                logger.info(f"Fetching Pitchero stats for {season} {squad}nd XV")
                logger.info(f"URL: {url}")

                if season == "2025/26" and squad == 2:
                    logger.info("No 2nd XV Pitchero data for 2025/26")
                    continue

                page = requests.get(url)
                soup = BeautifulSoup(page.content, 'html.parser')

                table = soup.find_all("div", {"class": "no-grid-hide"})[0]

                headers = [h.text for h in table.find_all("div", {"class": "league-table__header"})]
                players = [p.text for p in table.find_all("div", "sc-bwzfXH iWTrZm")]
                data = [int(d.text) for d in table.find_all("div", "sc-ifAKCX") if d.text.isnumeric()]

                # Split the data into columns
                data = [data[i:i+len(headers)-1] for i in range(0, len(data), len(headers)-1)]

                df = pd.DataFrame(data, columns=headers[1:], index=players)\
                    .reset_index().rename(columns={"index": "Player"})

                df = df[["Player", "A", "T", "Con", "PK", "DG", "YC", "RC"]]

                df = df.melt(
                    id_vars=[col for col in df.columns if col not in ["T", "Con", "PK", "DG", "YC", "RC"]],
                    value_vars=["T", "Con", "PK", "DG", "YC", "RC"],
                    var_name="Event",
                    value_name="Count"
                )

                df["Squad"] = "1st" if squad == 1 else "2nd"

                df["Player_join"] = df["Player"].apply(clean_name)

                df.drop(columns=["Player"], inplace=True)

                # Before 2021/22, replace "S Lindsay" with "S Lindsay 2"
                if season < "2021/22":
                    df["Player_join"] = df["Player_join"].replace("S Lindsay", "S Lindsay 2")

                if season == "2024/25" and squad == 1:
                    # remove 1 from YC column for 'Guy Collins' and 'Aaron Boczek'
                    index = df["Player_join"].isin(["G Collins", "A Boczek"]) & (df["Event"] == "YC")
                    df.loc[index, "Count"] = df.loc[index, "Count"] - 1
                    # Add 1 YC for 'C Leggat'
                    index = (df["Player_join"] == "C Leggat") & (df["Event"] == "YC")
                    df.loc[index, "Count"] = df.loc[index, "Count"] + 1

                df["Season"] = season

                dfs.append(df)

        pitchero_df = pd.concat(dfs)

        return pitchero_df[["Season", "Squad", "Player_join", "A", "Event", "Count"]]

    def extract_lineouts_data(self):
        """Extract lineout data"""
        ss = self.client.open_by_url(self.sheet_url)
        
        headers = [
            '#', 'Half', 'Season', 'Date', 'Opposition', 
            'Numbers', 'Call', 'Dummy', 'Front', 'Middle', 'Back',
            'Drive', 'Crusaders', 'Transfer', 'Flyby',
            'Hooker', 'Jumper', 'Won', 'Notes'
        ]
    
        lineouts_data = []
        
        for squad_name, sheet_name in [("1st", "1st XV Lineouts"), ("2nd", "2nd XV Lineouts")]:
            try:
                sheet = ss.worksheet(sheet_name)
                data = sheet.get_all_records(expected_headers=headers, head=3)
                
                for idx, row in enumerate(data):
                    if not row.get('Opposition'):
                        continue
                        
                    # Create game_id to link with games table
                    date = self._parse_date(row.get('Date', ''))
                    opposition = str(row.get('Opposition', '')).strip()
                    game_id = f"{date}_{squad_name}_{opposition}".replace(' ', '_').replace('/', '')
                    
                    lineout_data = {
                        'lineout_id': f"L_{game_id}_{idx}",
                        'game_id': game_id,
                        'numbers': str(row.get('Numbers', '')),
                        'call': str(row.get('Call', '')),
                        'call_type': self._classify_call(row.get('Call', '')),
                        'setup': self._get_setup(row.get('Call', '')),
                        'movement': self._get_movement(row.get('Call', '')),
                        'area': self._get_area(row),
                        'hooker': str(row.get('Hooker', '')),
                        'jumper': str(row.get('Jumper', '')),
                        'won': row.get('Won') in ['Y', True],
                        'drive': row.get('Drive') in ['x', 'Y', True],
                        'crusaders': row.get('Crusaders') in ['x', 'Y', True],
                        'transfer': row.get('Transfer') in ['x', 'Y', True],
                        'flyby': self._safe_int(row.get('Flyby'))
                    }
                    lineouts_data.append(lineout_data)
            except Exception as e:
                print(f"Error extracting lineouts for {squad_name}: {e}")
        
        return pd.DataFrame(lineouts_data)

    def extract_set_piece_stats(self):
        ss = self.client.open_by_url(self.sheet_url)
        
        headers = [
            "", "Season", "Date", "Opposition", "H/A", "F", "A", "PD",
            # Lineouts
            'Won', 'Total', 'Success rate',
            'Won', 'Total', 'Success rate',
            'Total', 'Net gain',
            # Scrums
            'Won', 'Total', 'Success rate',
            'Won', 'Total', 'Success rate',
            'Total', 'Net gain',
        ]

        set_piece_data = []

        for squad_name, sheet_name in [("1st", "1st XV Set piece"), ("2nd", "2nd XV Set piece")]:
            try:
                sheet = ss.worksheet(sheet_name)
                # Extract data from given range (A5:V)
                data = sheet.get("A5:V")
                
                for row in data:
                    if not row[1]: # Skip if no season
                        continue

                    game_data = {
                        'team': ['EG', 'Opp', 'EG', 'Opp'],
                        'set_piece': ['Lineout', 'Lineout', 'Scrum', 'Scrum'],
                        'won': [self._safe_int(row[8]), self._safe_int(row[11]), self._safe_int(row[16]), self._safe_int(row[19])],
                        'total': [self._safe_int(row[9]), self._safe_int(row[12]), self._safe_int(row[17]), self._safe_int(row[20])],
                    }

                    for team, sp, won, total in zip(game_data['team'], game_data['set_piece'], game_data['won'], game_data['total']):
                        set_piece_data.append({
                            'date': self._parse_date(row[2]),
                            'squad': squad_name,
                            'team': team,
                            'set_piece': sp,
                            'won': won,
                            'lost': total - won,
                            'total': total,
                            })
            except Exception as e:
                print(f"Error extracting set piece stats for {squad_name}: {e}")

        # Join to games to get game_id
        df_set_piece = pd.DataFrame(set_piece_data)
        df_games = self.extract_games_data()[['game_id', 'date', 'squad']]
        df_set_piece['date'] = pd.to_datetime(df_set_piece['date'])
        df_games['date'] = pd.to_datetime(df_games['date'])
        # Merge on date and squad
        df_merged = pd.merge(df_set_piece, df_games, on=['date', 'squad'], how='left')
        df_merged.drop(columns=['date', 'squad'], inplace=True) # drop date and squad columns
        df_merged = df_merged[['game_id', 'team', 'set_piece', 'won', 'lost', 'total']]
        df_merged = df_merged[df_merged['game_id'].notnull()] # keep only rows with game_id
        
        return df_merged
    
    def extract_league_data(self, season="2024-2025", league="Counties 1 Surrey/Sussex", comp="London & SE Division"):
        """Extract league data using league_data functions"""
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        from league_data import fetch_match_ids, fetch_match_data, fetch_league_table
        
        # Get league table
        table_df = fetch_league_table(season, league, comp)
        
        # Get all match data
        match_ids = fetch_match_ids(season, league, comp)
        matches_data = []
        
        for match_id in match_ids:
            match_data = fetch_match_data(match_id)
            if match_data:
                matches_data.append(match_data)
        
        return table_df, matches_data
    
    # Helper methods
    def _parse_date(self, date_str):
        """Parse date string to ISO format"""
        # Add your date parsing logic here
        return date_str
    
    def _parse_score(self, score, home_away):
        """Parse score string"""
        if not score or '-' not in score:
            return None, None
        try:
            scores = score.split('-')
            if home_away == 'H':
                return int(scores[0]), int(scores[1])
            else:
                return int(scores[1]), int(scores[0])
        except:
            return None, None
    
    def _classify_game_type(self, competition):
        """Classify game type"""
        if competition == "Friendly":
            return "Friendly"
        elif any(word in competition.lower() for word in ['cup', 'plate', 'vase', 'shield', 'championship', 'trophy']):
            return "Cup"
        else:
            return "League"
        

    def _classify_call(self,call):

        if call in ["Snap", "Yes", "No"]:
            return "4-man only"
        elif call in ["Red", "Orange", "RD", "Even", "Odd", "Green", "Plus", "Even +", "Odd +", "Green +", "Matlow"]:
            return "Old"
        elif call in ["C*", "A*", "C1", "C2", "C3", "H1", "H2", "H3", "A1", "A2", "A3", "W1", "W2", "W3"]:
            return "Sandy"
        # else if call is a string of numbers and +/-
        elif re.match(r'^\d+(\s*[\+\-]\s*\d+)?$', call):
            return "SLM"
        else:
            return "Other"
    
    def _get_movement(self, call):
        if call in ["RD", "Plus", "Even +", "Odd +", "Green +", "C3", "A1", "A2", "A3", "No"]:
            return "Dummy"
        elif call in ["Yes", "C1", "C2"]:
            return "Move"
        # Call starts with multiple numbers
        elif re.match(r'^\d+\s*\d*', call):
            return "Dummy"
        else:
            return "Jump"
        
    def _get_area(self, row):
        if row['Front'] == "x":
            return "Front"
        elif row['Middle'] == "x":
            return "Middle"
        elif row['Back'] == "x":
            return "Back"
        else:
            return "Unknown"
        
    def _get_setup(self, call):
        if call.startswith('A'):
            return "A"
        elif call.startswith('C'):
            return "C"
        elif call.startswith('H'):
            return "H"
        elif call.startswith('W'):
            return "W"
        else:
            return None

    
    def _get_position(self, shirt_number):
        """Get position name from shirt number"""
        position_map = {
            1: "Prop", 2: "Hooker", 3: "Prop", 4: "Second Row", 5: "Second Row",
            6: "Flanker", 7: "Flanker", 8: "Number 8", 9: "Scrum Half", 10: "Fly Half",
            11: "Wing", 12: "Centre", 13: "Centre", 14: "Wing", 15: "Full Back"
        }
        return position_map.get(shirt_number, "Bench")
    
    def _get_position_group(self, shirt_number):
        """Get position group from shirt number"""
        if shirt_number <= 8:
            return "Forwards"
        elif shirt_number <= 15:
            return "Backs"
        else:
            return "Bench"
    
    def _get_unit(self, shirt_number):
        """Get unit from shirt number"""
        return self._get_position_group(shirt_number)
    
    def _safe_int(self, value):
        """Safely convert to int"""
        try:
            return int(value) if value else None
        except:
            return None
       