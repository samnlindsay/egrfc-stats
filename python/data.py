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
from urllib.parse import urljoin
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


HISTORIC_PITCHERO_SEASON_IDS = {
    "2016/17": 42025,
    "2017/18": 47693,
    "2018/19": 52304,
    "2019/20": 68499,
}

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
            for row in data[4:]:  # Assuming data starts at row 6
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

            # Build a shirt-number -> column-index map from the header row so we can
            # handle sheet-specific layouts (e.g. optional columns before player 1).
            shirt_col_map = {}
            if len(data) >= 4:
                header_row = data[3]
                for idx, header in enumerate(header_row):
                    header_value = str(header).strip()
                    if header_value.isdigit():
                        shirt_no = int(header_value)
                        if 1 <= shirt_no <= 29:
                            shirt_col_map[shirt_no] = idx
            
            for row in data[4:]:
                if not row[1]:  # Skip if no season
                    continue
                    
                # Extract game info
                date = self._parse_date(row[0])
                opposition = row[3].replace('(H)', '').replace('(A)', '').strip()
                game_id = f"{date}_{squad_name}_{opposition}".replace(' ', '_').replace('/', '')
                captain = row[5]
                vc1 = row[6]
                vc2 = row[7]
                
                # Extract players (positions 1-29) using header-derived column map
                for pos in range(1, 30):
                    col_idx = shirt_col_map.get(pos)
                    if col_idx is None:
                        continue
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

    def extract_pitchero_historic_team_sheets(self, seasons=None, squads=(1, 2), timeout=20):
        """Scrape historic Pitchero fixtures + lineup pages for game and appearance data.

        Google Sheets remains canonical for 2021/22 onwards. This scraper is intended
        for historic supplementation (2019/20 and earlier by default).
        """

        season_map = HISTORIC_PITCHERO_SEASON_IDS if seasons is None else {
            season: HISTORIC_PITCHERO_SEASON_IDS[season]
            for season in seasons
            if season in HISTORIC_PITCHERO_SEASON_IDS
        }

        games_rows = []
        appearance_rows = []

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        })

        for squad in squads:
            squad_label = "1st" if squad == 1 else "2nd"
            team_id = f"14206{8 if squad == 1 else 9}"

            for season, season_id in season_map.items():
                fixtures_url = f"https://www.egrfc.com/teams/{team_id}/fixtures-results?season={season_id}"
                logger.info(f"Scraping historic fixtures: {season} {squad_label} XV -> {fixtures_url}")

                fixtures_soup = self._fetch_soup(session, fixtures_url, timeout=timeout)
                if fixtures_soup is None:
                    continue

                fixtures = fixtures_soup.find_all("div", class_="fixture-overview")
                for fixture in fixtures:
                    fixture_data = self._parse_pitchero_fixture(fixture)
                    if not fixture_data:
                        continue

                    home_team = fixture_data["home_team"]
                    away_team = fixture_data["away_team"]
                    if "east grinstead" not in home_team.lower() and "east grinstead" not in away_team.lower():
                        continue

                    if fixture_data["home_score"] is None or fixture_data["away_score"] is None:
                        continue

                    home_away = "H" if "east grinstead" in home_team.lower() else "A"
                    opposition = away_team if home_away == "H" else home_team
                    pf, pa = (
                        (fixture_data["home_score"], fixture_data["away_score"])
                        if home_away == "H"
                        else (fixture_data["away_score"], fixture_data["home_score"])
                    )

                    result = "W" if pf > pa else "L" if pf < pa else "D"
                    lineup_url = self._normalise_lineup_url(fixture_data.get("match_url"))

                    lineup_soup = None
                    if lineup_url:
                        lineup_soup = self._fetch_soup(session, lineup_url, timeout=timeout)

                    date_obj = self._parse_pitchero_date(fixture_data["date_text"])
                    if date_obj is None and lineup_soup is not None:
                        date_obj = self._extract_pitchero_match_date(lineup_soup)
                    if date_obj is None:
                        continue
                    date_iso = date_obj.strftime("%Y-%m-%d")

                    game_id = f"{date_iso}_{squad_label}_{opposition}".replace(" ", "_").replace("/", "")

                    game_row = {
                        "game_id": game_id,
                        "date": date_iso,
                        "season": season,
                        "squad": squad_label,
                        "competition": fixture_data.get("competition") or "League",
                        "game_type": self._classify_game_type(fixture_data.get("competition") or "League"),
                        "opposition": opposition,
                        "home_away": home_away,
                        "pf": pf,
                        "pa": pa,
                        "result": result,
                        "margin": abs(pf - pa),
                        "captain": None,
                        "vc1": None,
                        "vc2": None,
                    }
                    games_rows.append(game_row)

                    if lineup_soup is None:
                        continue

                    lineup_players = self._parse_pitchero_lineup(lineup_soup)
                    if not lineup_players:
                        continue

                    captain_name = None
                    for player_info in lineup_players:
                        shirt_number = player_info["number"]
                        player_name = player_info["player"]
                        is_captain = player_info["is_captain"]
                        if is_captain and not captain_name:
                            captain_name = player_name

                        appearance_rows.append(
                            {
                                "appearance_id": f"{game_id}_{shirt_number}",
                                "game_id": game_id,
                                "player": player_name,
                                "shirt_number": shirt_number,
                                "position": self._get_position(shirt_number),
                                "position_group": self._get_position_group(shirt_number),
                                "unit": self._get_unit(shirt_number),
                                "is_starter": shirt_number <= 15,
                                "is_captain": is_captain,
                                "is_vc": False,
                                "player_join": clean_name(player_name),
                            }
                        )

                    if captain_name:
                        games_rows[-1]["captain"] = captain_name

        games_df = pd.DataFrame(games_rows).drop_duplicates(subset=["game_id"])
        appearances_df = pd.DataFrame(appearance_rows).drop_duplicates(subset=["appearance_id"])

        return games_df, appearances_df

    def _fetch_soup(self, session, url, timeout=20):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except Exception as exc:
            logger.warning(f"Failed to fetch {url}: {exc}")
            return None

    def _parse_pitchero_fixture(self, fixture_node):
        team_nodes = fixture_node.select(".fixture-overview__teamname")
        if len(team_nodes) < 2:
            return None

        home_team = team_nodes[0].get_text(" ", strip=True)
        away_team = team_nodes[1].get_text(" ", strip=True)

        score_node = fixture_node.select_one(".statusbox__scores")
        home_score = None
        away_score = None
        if score_node:
            score_text = score_node.get_text(" ", strip=True)
            home_score, away_score = self._parse_pitchero_score(score_text)

        match_url = None
        for anchor in fixture_node.find_all("a", href=True):
            if "/match-centre/" in anchor["href"]:
                match_url = urljoin("https://www.egrfc.com", anchor["href"])
                break
        if not match_url:
            parent = fixture_node
            for _ in range(4):
                parent = parent.parent
                if parent is None:
                    break
                if getattr(parent, "name", None) == "a" and parent.get("href") and "/match-centre/" in parent["href"]:
                    match_url = urljoin("https://www.egrfc.com", parent["href"])
                    break
                parent_anchor = parent.find("a", href=True) if hasattr(parent, "find") else None
                if parent_anchor and "/match-centre/" in parent_anchor["href"]:
                    match_url = urljoin("https://www.egrfc.com", parent_anchor["href"])
                    break

        date_text = ""
        date_node = fixture_node.find("time")
        if date_node:
            date_text = date_node.get("datetime") or date_node.get_text(" ", strip=True)
        if not date_text:
            text_blob = fixture_node.get_text(" ", strip=True)
            date_match = re.search(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b", text_blob)
            if date_match:
                date_text = date_match.group(0)

        competition = None
        comp_node = fixture_node.find(class_=re.compile("competition", re.IGNORECASE))
        if comp_node:
            competition = comp_node.get_text(" ", strip=True)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "match_url": match_url,
            "date_text": date_text,
            "competition": competition,
        }

    def _parse_pitchero_score(self, score_text):
        numbers = re.findall(r"\d+", score_text or "")
        if len(numbers) >= 2:
            return int(numbers[0]), int(numbers[1])
        return None, None

    def _normalise_lineup_url(self, match_url):
        if not match_url:
            return None
        if match_url.endswith("/lineup"):
            return match_url
        return match_url.rstrip("/") + "/lineup"

    def _parse_pitchero_date(self, date_text):
        if not date_text:
            return None
        date_text = str(date_text).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
            try:
                return datetime.strptime(date_text, "%Y-%m-%d")
            except ValueError:
                return None
        parsed = pd.to_datetime(date_text, errors="coerce", dayfirst=True)
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()

    def _extract_pitchero_match_date(self, soup):
        next_data = self._extract_next_data_payload(soup)
        if next_data:
            try:
                page_data = (
                    next_data.get("props", {})
                    .get("initialReduxState", {})
                    .get("teams", {})
                    .get("matchCentre", {})
                    .get("pageData", {})
                )
                if page_data:
                    match_entry = next(iter(page_data.values()))
                    overview_date = (match_entry.get("overview") or {}).get("date")
                    parsed = self._parse_pitchero_date(overview_date)
                    if parsed is not None:
                        return parsed
            except Exception:
                pass

        for time_node in soup.find_all("time"):
            candidate = time_node.get("datetime") or time_node.get_text(" ", strip=True)
            parsed = self._parse_pitchero_date(candidate)
            if parsed is not None:
                return parsed

        text_blob = soup.get_text(" ", strip=True)
        date_match = re.search(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b", text_blob)
        if date_match:
            return self._parse_pitchero_date(date_match.group(0))
        return None

    def _extract_next_data_payload(self, soup):
        script_node = soup.find("script", id="__NEXT_DATA__")
        if not script_node:
            return None
        raw = script_node.get_text(strip=True)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _parse_pitchero_lineup(self, lineup_soup):
        next_data = self._extract_next_data_payload(lineup_soup)
        if next_data:
            try:
                page_data = (
                    next_data.get("props", {})
                    .get("initialReduxState", {})
                    .get("teams", {})
                    .get("matchCentre", {})
                    .get("pageData", {})
                )
                if page_data:
                    match_entry = next(iter(page_data.values()))
                    lineup_data = match_entry.get("lineup") or {}
                    lineup = []
                    for player in (lineup_data.get("players") or []) + (lineup_data.get("substitutes") or []):
                        shirt_number = player.get("number")
                        player_name = (player.get("name") or "").strip()
                        if not player_name:
                            continue
                        try:
                            shirt_number = int(shirt_number)
                        except (TypeError, ValueError):
                            continue
                        if shirt_number < 1 or shirt_number > 29:
                            continue
                        lineup.append(
                            {
                                "number": shirt_number,
                                "player": player_name,
                                "is_captain": bool(player.get("captain", False)),
                            }
                        )
                    if lineup:
                        lineup.sort(key=lambda item: item["number"])
                        return lineup
            except Exception:
                pass

        number_nodes = lineup_soup.select(".sc-EHOje.eNiGwT")
        name_nodes = lineup_soup.select(".sc-bwzfXH.iamjnI")

        if not number_nodes or not name_nodes:
            number_nodes = lineup_soup.find_all(class_=re.compile(r"sc-EHOje"))
            name_nodes = lineup_soup.find_all(class_=re.compile(r"sc-bwzfXH"))

        numbers = []
        for node in number_nodes:
            text_value = node.get_text(" ", strip=True)
            if text_value.isdigit():
                numbers.append(int(text_value))

        players = []
        for node in name_nodes:
            player_text = node.get_text(" ", strip=True)
            player_text = re.sub(r"\s*\(C\)\s*$", "", player_text).strip()
            if player_text:
                is_captain = False
                for img in node.find_all("img"):
                    alt = (img.get("alt") or "").lower()
                    src = (img.get("src") or "").lower()
                    if alt == "c" or "captain" in alt or "captain" in src:
                        is_captain = True
                        break
                players.append({"player": player_text, "is_captain": is_captain})

        if not numbers or not players:
            return []

        lineup = []
        for number, player_info in zip(numbers, players):
            lineup.append(
                {
                    "number": number,
                    "player": player_info["player"],
                    "is_captain": player_info["is_captain"],
                }
            )

        return lineup

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
       