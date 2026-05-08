import csv
import requests
import os
import json
import pandas as pd
import argparse
import logging
from bs4 import BeautifulSoup
import time
import random
import re
import glob
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Use __file__-relative path so this works regardless of working directory
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
os.makedirs(_DATA_DIR / "match_data", exist_ok=True)

competition_ids = {
    "London & SE Division": 261,
    "Harvey's Brewery Sussex Leagues": 206,
    "Women": 1782,
}

division_ids = {
    "Counties 1 Surrey/Sussex": {
        "2025-2026": 66548,
        "2024-2025": 56612,
        "2023-2024": 47017,
    },
    "Counties 2 Sussex": {
        "2025-2026": 66676,
        "2024-2025": 56914,
        "2023-2024": 47022,
        "2022-2023": 39123,
    },
    "Counties 3 Sussex": {
        "2025-2026": 70706,
        "2024-2025": 57767,
    },
    "Counties 4 Sussex": {
        "2023-2024": 56757,
        "2022-2023": 39812,
    },
    "Sussex 1": {
        "2021-2022": 31791,
        "2019-2020": 21526,
        "2018-2019": 14030,
        "2017-2018": 11128,


    },
    "Sussex 3 Premier": {
        "2021-2022": 37770,
    }
}

divisions = {
    1: {
        "2025/26": "Counties 2 Sussex",
        "2024/25": "Counties 1 Surrey/Sussex",
        "2023/24": "Counties 1 Surrey/Sussex",
        "2022/23": "Counties 2 Sussex",
        "2021/22": "Sussex 1",
        "2019/20": "Sussex 1",
        "2018/19": "Sussex 1",
        "2017/18": "Sussex 1",
    },
    2: {
        "2025/26": "Counties 3 Sussex",
        "2024/25": "Counties 3 Sussex",
        "2023/24": "Counties 4 Sussex",
        "2022/23": "Counties 4 Sussex",
        "2021/22": "Sussex 3 Premier"
    }
}    

RFU_LEAGUE_PREFIXES = (
    "Harvey’s Brewery ",
    "Harvey's Brewery ",
    "Harvey’s Olympia ",
    "Harvey's Olympia ",
)

base_url = 'https://www.englandrugby.com/fixtures-and-results/'

def get_url(squad=1, season="2025/26"):
    """Generate URL for fetching match data."""
    
    division = divisions[squad].get(season, None)

    if division is not None:
        season_str = season.replace("/", "-20")
        division_id = division_ids[division][season_str]

        if division in ["Counties 3 Sussex", "Counties 4 Sussex", "Sussex 3 Premier"]:
            competition_id = competition_ids["Harvey's Brewery Sussex Leagues"]
        else:
            competition_id = competition_ids["London & SE Division"]

        url = f'{base_url}search-results?competition={competition_id}&season={season_str}&division={division_id}'
        
        return url

# Add headers to mimic a real browser
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0'
}


def normalize_league_name(league):
    """Normalize RFU league names to the division labels used in this project."""
    if league is None:
        return ""

    league_name = " ".join(str(league).strip().split())
    for prefix in RFU_LEAGUE_PREFIXES:
        if league_name.startswith(prefix):
            return league_name[len(prefix):].strip()
    return league_name


def season_to_short_label(season):
    """Convert season labels to canonical YYYY/YY format."""
    season_dash = _normalize_season(season)
    if not season_dash or "-" not in season_dash:
        return season_dash

    start_year, end_year = season_dash.split("-", 1)
    return f"{start_year}/{end_year[-2:]}"


def _parse_lineup_shirt_number(raw_number):
    """Convert RFU lineup keys like 15 or S1 into shirt numbers."""
    if raw_number is None:
        return None

    value = str(raw_number).strip().upper()
    if not value:
        return None

    if value.isdigit():
        return int(value)

    sub_match = re.match(r"^S(\d+)$", value)
    if sub_match:
        return 15 + int(sub_match.group(1))

    return None


def _rfu_position_from_shirt_number(shirt_number):
    """Map shirt numbers to canonical positions."""
    position_map = {
        1: "Prop",
        2: "Hooker",
        3: "Prop",
        4: "Second Row",
        5: "Second Row",
        6: "Flanker",
        7: "Flanker",
        8: "Number 8",
        9: "Scrum Half",
        10: "Fly Half",
        11: "Wing",
        12: "Centre",
        13: "Centre",
        14: "Wing",
        15: "Full Back",
    }
    return position_map.get(shirt_number, "Bench")


def _rfu_unit_from_shirt_number(shirt_number):
    """Map shirt numbers to canonical units."""
    if shirt_number is None:
        return None
    if shirt_number <= 8:
        return "Forwards"
    if shirt_number <= 15:
        return "Backs"
    return "Bench"


def _coerce_rfu_score_value(value):
    """Return numeric score and walkover flag from consolidated RFU score values."""
    if value is None:
        return pd.NA, False

    text = str(value).strip().upper()
    if not text:
        return pd.NA, False
    if text == "WO":
        return pd.NA, True

    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.notna(numeric_value):
        return int(numeric_value), False

    return pd.NA, False


def build_rfu_games_dataframe(matches=None, consolidated_file=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Build a normalized RFU games dataframe from consolidated scrape output."""
    if matches is None:
        matches = load_consolidated_matches(consolidated_file)

    rows = []
    for match in matches:
        match_id = str(match.get("match_id", "")).strip()
        teams = match.get("teams", []) or []
        if not match_id or len(teams) < 2:
            continue

        season = season_to_short_label(match.get("season"))
        league = normalize_league_name(match.get("league"))
        date_value = pd.to_datetime(match.get("date"), errors="coerce")
        if not season or pd.isna(date_value):
            continue

        score = match.get("score", []) or []
        home_score, home_walkover = _coerce_rfu_score_value(score[0] if len(score) > 0 else None)
        away_score, away_walkover = _coerce_rfu_score_value(score[1] if len(score) > 1 else None)

        players = match.get("players", []) or []
        home_players = players[0] if len(players) > 0 and isinstance(players[0], dict) else {}
        away_players = players[1] if len(players) > 1 and isinstance(players[1], dict) else {}

        tracked_squad = squad_lookup(season, league) if league else None
        tracked_squad_label = f"{tracked_squad}st" if tracked_squad == 1 else f"{tracked_squad}nd" if tracked_squad else None

        rows.append(
            {
                "match_id": match_id,
                "season": season,
                "league": league,
                "tracked_squad": tracked_squad_label,
                "date": date_value.date(),
                "home_team": str(teams[0]).strip(),
                "away_team": str(teams[1]).strip(),
                "home_score": home_score,
                "away_score": away_score,
                "home_walkover": bool(home_walkover),
                "away_walkover": bool(away_walkover),
                "lineup_available_home": bool(home_players),
                "lineup_available_away": bool(away_players),
            }
        )

    columns = [
        "match_id",
        "season",
        "league",
        "tracked_squad",
        "date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "home_walkover",
        "away_walkover",
        "lineup_available_home",
        "lineup_available_away",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows, columns=columns).drop_duplicates(subset=["match_id"]).sort_values(["season", "date", "match_id"])
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce").astype("Int64")
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce").astype("Int64")
    return df


def build_rfu_player_appearances_dataframe(matches=None, consolidated_file=None, games_df=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Build normalized RFU player appearance rows from consolidated scrape output."""
    if matches is None:
        matches = load_consolidated_matches(consolidated_file)
    if games_df is None:
        games_df = build_rfu_games_dataframe(matches=matches, consolidated_file=consolidated_file)

    game_lookup = {}
    for game in games_df.to_dict("records"):
        game_lookup[str(game["match_id"])] = game

    rows = []
    for match in matches:
        match_id = str(match.get("match_id", "")).strip()
        game = game_lookup.get(match_id)
        teams = match.get("teams", []) or []
        players = match.get("players", []) or []
        if game is None or len(teams) < 2 or len(players) < 2:
            continue

        for team_index, home_away in enumerate(["H", "A"]):
            lineup = players[team_index] if isinstance(players[team_index], dict) else {}
            if not lineup:
                continue

            team = str(teams[team_index]).strip()
            opposition = str(teams[1 - team_index]).strip()
            sorted_lineup = sorted(
                lineup.items(),
                key=lambda item: (_parse_lineup_shirt_number(item[0]) is None, _parse_lineup_shirt_number(item[0]) or 999, str(item[0])),
            )

            for raw_number, raw_player in sorted_lineup:
                player = " ".join(str(raw_player).split()).strip()
                shirt_number = _parse_lineup_shirt_number(raw_number)
                if not player or shirt_number is None:
                    continue

                rows.append(
                    {
                        "match_id": match_id,
                        "season": game["season"],
                        "league": game["league"],
                        "tracked_squad": game["tracked_squad"],
                        "date": game["date"],
                        "team": team,
                        "opposition": opposition,
                        "home_away": home_away,
                        "player": player,
                        "shirt_number": shirt_number,
                        "position": _rfu_position_from_shirt_number(shirt_number),
                        "unit": _rfu_unit_from_shirt_number(shirt_number),
                        "is_starter": shirt_number <= 15,
                    }
                )

    columns = [
        "match_id",
        "season",
        "league",
        "tracked_squad",
        "date",
        "team",
        "opposition",
        "home_away",
        "player",
        "shirt_number",
        "position",
        "unit",
        "is_starter",
        "previous_match_id",
        "played_previous_game",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    appearances_df = pd.DataFrame(rows)

    team_games = pd.concat(
        [
            games_df[["match_id", "season", "date", "home_team", "away_team", "lineup_available_home"]].rename(
                columns={
                    "home_team": "team",
                    "away_team": "opposition",
                    "lineup_available_home": "lineup_available",
                }
            ).assign(home_away="H"),
            games_df[["match_id", "season", "date", "home_team", "away_team", "lineup_available_away"]].rename(
                columns={
                    "away_team": "team",
                    "home_team": "opposition",
                    "lineup_available_away": "lineup_available",
                }
            ).assign(home_away="A"),
        ],
        ignore_index=True,
    ).sort_values(["season", "team", "date", "match_id"])

    team_games["previous_match_id"] = team_games.groupby(["season", "team"])["match_id"].shift(1)
    previous_lineups = team_games[["season", "team", "match_id", "lineup_available"]].rename(
        columns={
            "match_id": "previous_match_id",
            "lineup_available": "previous_lineup_available",
        }
    )
    team_games = team_games.merge(previous_lineups, on=["season", "team", "previous_match_id"], how="left")

    appearances_df = appearances_df.merge(
        team_games[["match_id", "season", "team", "previous_match_id", "previous_lineup_available"]],
        on=["match_id", "season", "team"],
        how="left",
    )

    previous_player_keys = {
        (row.match_id, row.team, row.player)
        for row in appearances_df[["match_id", "team", "player"]].itertuples(index=False)
    }

    def _played_previous_game(row):
        previous_match_id = row["previous_match_id"]
        if pd.isna(previous_match_id):
            return pd.NA
        if not bool(row.get("previous_lineup_available")):
            return pd.NA
        return (previous_match_id, row["team"], row["player"]) in previous_player_keys

    appearances_df["played_previous_game"] = appearances_df.apply(_played_previous_game, axis=1)
    appearances_df["shirt_number"] = pd.to_numeric(appearances_df["shirt_number"], errors="coerce").astype("Int64")

    return appearances_df[columns].drop_duplicates(subset=["match_id", "team", "player"]).sort_values(
        ["season", "team", "date", "match_id", "shirt_number", "player"]
    )

def squad_lookup(season, league):
    """Return the squad number based on season and league."""
    season_key = season_to_short_label(season)
    league_normalized = normalize_league_name(league)
    for div, seasons in divisions.items():
        expected_league = seasons.get(season_key)
        if league_normalized == expected_league:
            return int(div)
    return 1  # Default to squad 1 if not found


def _parse_score_text(score_text):
    """Parse score strings from England Rugby pages, including walkovers."""
    if not score_text:
        return [None, None]

    text = score_text.strip().upper()

    if text == "HWO":
        return ["WO", ""]
    if text == "AWO":
        return ["", "WO"]

    score_match = re.match(r"^(\d+)\s*[-–:]\s*(\d+)$", text)
    if score_match:
        return [int(score_match.group(1)), int(score_match.group(2))]

    score_numbers = re.findall(r"\d+", text)
    if len(score_numbers) >= 2:
        return [int(score_numbers[0]), int(score_numbers[1])]

    return [None, None]


def _extract_match_id_from_href(href):
    """Extract matchId from href robustly, handling query strings/fragments."""
    if not href:
        return None

    parsed = urlparse(href)
    query_match_ids = parse_qs(parsed.query).get("matchId")
    if query_match_ids and query_match_ids[0].isdigit():
        return query_match_ids[0]

    match = re.search(r"(?:\?|&)matchId=(\d+)", href)
    if match:
        return match.group(1)

    return None


def _normalize_season(season):
    """Normalize season labels to YYYY-YYYY format."""
    if not season:
        return season

    season = season.strip()

    if re.match(r"^\d{4}-\d{4}$", season):
        return season

    slash_match = re.match(r"^(\d{4})/(\d{2})$", season)
    if slash_match:
        start_year = int(slash_match.group(1))
        end_suffix = int(slash_match.group(2))
        century_base = (start_year // 100) * 100
        end_year = century_base + end_suffix
        if end_year < start_year:
            end_year += 100
        return f"{start_year}-{end_year}"

    return season


def _parse_results_card_score(score_box):
    """Extract score pair from a results card score container."""
    if not score_box:
        return [None, None]

    home_score_node = score_box.select_one('a.coh-style-numeric-score')
    away_score_node = score_box.select_one('a.coh-style-numeric-right')
    if home_score_node and away_score_node:
        home_text = home_score_node.get_text(strip=True)
        away_text = away_score_node.get_text(strip=True)

        # Numeric score first (normal played fixture)
        parsed_pair = _parse_score_text(f"{home_text} - {away_text}")
        if parsed_pair != [None, None]:
            return parsed_pair

        # Explicit walkover encoding only (HWO/AWO) from visible score cells
        home_token = re.sub(r"[^A-Z0-9]", "", home_text.upper())
        away_token = re.sub(r"[^A-Z0-9]", "", away_text.upper())
        if home_token in {"HWO", "AWO"}:
            return _parse_score_text(home_token)
        if away_token in {"HWO", "AWO"}:
            return _parse_score_text(away_token)

        # Support historic visible WO cell format ['', 'WO'] / ['WO', '']
        if home_token in {"WO", "WO"} and not away_token:
            return ["WO", ""]
        if away_token in {"WO", "WO"} and not home_token:
            return ["", "WO"]

    raw_score_text = score_box.get_text(" ", strip=True)
    raw_token = re.sub(r"[^A-Z0-9]", "", raw_score_text.upper())
    if raw_token in {"HWO", "AWO"}:
        return _parse_score_text(raw_token)

    parsed_raw_score = _parse_score_text(raw_score_text)
    if parsed_raw_score != [None, None]:
        return parsed_raw_score

    return [None, None]


def _parse_results_card_date(card):
    """Extract normalized match date from a results card class list."""
    for class_name in card.get('class', []):
        if not class_name.startswith('cardContainer_'):
            continue

        raw_date = class_name.replace('cardContainer_', '')
        for date_format in ("%A,%d%b%Y", "%a,%d%b%Y"):
            try:
                return pd.to_datetime(raw_date, format=date_format).strftime("%Y-%m-%d")
            except ValueError:
                continue

        return None

    return None

def is_match_complete(match_data):
    """Check if match has complete data (score, both team lineups, date)."""
    if not match_data:
        return False
    if not match_data.get('score') or None in match_data.get('score', []):
        return False
    teams = match_data.get('teams', [])
    if not teams or len(teams) < 2:
        return False
    if not match_data.get('date'):
        return False

    season = match_data.get('season')
    league = match_data.get('league')
    squad = squad_lookup(season, league) if season and league else 1
    teams = match_data.get('teams', [])
    includes_eg = any("East Grinstead" in team for team in teams if isinstance(team, str))

    if squad == 1 and includes_eg:
        if not match_data.get('players') or len(match_data.get('players', [])) < 2:
            return False
        if not match_data['players'][0] or not match_data['players'][1]:
            return False

    return True

def get_existing_match_ids_from_consolidated(consolidated_file=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Get set of match IDs from the consolidated matches.json file."""
    existing_ids = set()
    
    if not os.path.exists(consolidated_file):
        logging.info(f"Consolidated file {consolidated_file} doesn't exist yet")
        return existing_ids
    
    try:
        with open(consolidated_file, 'r') as f:
            matches = json.load(f)
        
        for match in matches:
            if 'match_id' in match:
                existing_ids.add(match['match_id'])
        
        logging.info(f"Found {len(existing_ids)} existing matches in consolidated file")
        return existing_ids
        
    except Exception as e:
        logging.error(f"Error reading consolidated file: {e}")
        return existing_ids

def load_consolidated_matches(consolidated_file=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Load all matches from consolidated file."""
    if not os.path.exists(consolidated_file):
        logging.info(f"Consolidated file {consolidated_file} doesn't exist yet")
        return []
    
    try:
        with open(consolidated_file, 'r') as f:
            matches = json.load(f)
        logging.info(f"Loaded {len(matches)} matches from consolidated file")
        return matches
    except Exception as e:
        logging.error(f"Error loading consolidated file: {e}")
        return []

def get_incomplete_match_ids(consolidated_file=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Get match IDs that exist but have incomplete data."""
    incomplete_ids = []
    
    matches = load_consolidated_matches(consolidated_file)
    for match in matches:
        if not is_match_complete(match):
            incomplete_ids.append(match['match_id'])
    
    logging.info(f"Found {len(incomplete_ids)} matches with incomplete data")
    return incomplete_ids

def save_consolidated_matches(matches, consolidated_file=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Save matches to consolidated file, sorted by date."""
    try:
        # Sort by date for consistency
        matches.sort(key=lambda x: x.get('date', ''))
        
        with open(consolidated_file, 'w') as f:
            json.dump(matches, f, indent=4)
        
        logging.info(f"Saved {len(matches)} matches to consolidated file: {consolidated_file}")
        return True
    except Exception as e:
        logging.error(f"Error saving consolidated file: {e}")
        return False

def generate_bootstrap_table(df, title="League Table"):
    # Generate table headers
    headers = ''.join(f'<th id="table{col}">{col}</th>' for col in df.columns)

    # Generate table rows
    rows = ''.join(
        f'<tr{""" class="table-primary fw-bold" """ if row["TEAM"] == "East Grinstead" else ""}>' +
        ''.join(f'<td class="p-1" id="table{{col}}">{row[col]}</td>' for col in df.columns) +
        '</tr>'
        for _, row in df.iterrows()
    )

    # Combine headers and rows into the final HTML table
    table_html = f'''
    <table class="table table-striped table-borderless mx-auto text-center align-middle small" id="leagueTable">
        <thead class="table-danger">
        <tr>{headers}</tr>
        </thead>
        <tbody>
        {rows}
        </tbody>
    </table>
    '''
    return table_html

def get_team_stats_from_table(squad=1, season="2025/26"):
    """Load league table and return dict of team stats."""
    csv_file = f"data/league_table_{season.replace('/', '_')}_squad_{squad}.csv"
    
    if not os.path.exists(csv_file):
        logging.debug(f"No league table found: {csv_file}")
        return {}
    
    try:
        df = pd.read_csv(csv_file)
        
        # Create lookup dict: team name -> {position, points, PD, etc}
        team_stats = {}
        for _, row in df.iterrows():
            team_stats[row['TEAM']] = {
                'position': row.get('#', None),
                'points': row.get('Pts', None),
                'played': row.get('P', None),
                'won': row.get('W', None),
                'drawn': row.get('D', None),
                'lost': row.get('L', None),
                'points_for': row.get('PF', None),
                'points_against': row.get('PA', None),
                'points_difference': row.get('PD', None)
            }
        
        return team_stats
    except Exception as e:
        logging.error(f"Error reading league table {csv_file}: {e}")
        return {}

def fetch_league_table(squad=1, season="2025/26"):
    """Fetch league table from the England Rugby website."""

    url = f"{get_url(squad=squad, season=season)}#tables"
    
    # Add a random delay to avoid being detected as a bot
    time.sleep(random.uniform(1, 3))
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find_all('table')[0]
        df = pd.read_html(str(table))[0]
        df.rename(columns={"+/-": "PD"}, inplace=True)
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None
    except IndexError:
        print("No table found on the page")
        return None   

    return df

def fetch_match_ids(squad=1, season="2025/26"):
    """Fetch match IDs from the England Rugby website."""

    url = f"{get_url(squad=squad, season=season)}#results"
    
    # Add a random delay to avoid being detected as a bot
    time.sleep(random.uniform(1, 3))

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error fetching match list: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    links = {
        match_id
        for a in soup.find_all('a', href=True)
        if '/fixtures-and-results/match-centre-community' in a['href']
        for match_id in [_extract_match_id_from_href(a['href'])]
        if match_id
    }
    
    logging.info(f"Found {len(links)} match IDs for {season} squad {squad}")
    return list(links)


def fetch_matches_from_results_page(squad=2, season="2025/26"):
    """Fetch match summaries directly from the results list page (used for squad 2)."""

    url = f"{get_url(squad=squad, season=season)}#results"

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error fetching results page for squad {squad}, season {season}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    cards = soup.find_all('div', class_=lambda class_list: class_list and 'dataContainer' in class_list)

    league = divisions.get(squad, {}).get(season, f"Squad {squad}")
    season_dash = _normalize_season(season)
    match_data_list = []

    for card in cards:
        match_link = card.find('a', href=lambda href: href and 'match-centre-community' in href)
        if not match_link:
            continue

        match_id = _extract_match_id_from_href(match_link.get('href', ''))
        if not match_id:
            continue

        home_node = card.select_one('.coh-style-hometeam a')
        away_node = card.select_one('.coh-style-away-team a')
        if not home_node or not away_node:
            continue

        teams = [home_node.get_text(strip=True), away_node.get_text(strip=True)]

        score_box = card.select_one('.fnr-scores')
        score = _parse_results_card_score(score_box)

        match_date = _parse_results_card_date(card)

        match_data_list.append({
            "match_id": match_id,
            "season": season_dash,
            "league": league,
            "date": match_date,
            "teams": teams,
            "score": score,
            "logos": [],
            "players": [{}, {}]
        })

    logging.info(f"Parsed {len(match_data_list)} match rows from results page for {season} squad {squad}")
    return match_data_list

def get_players(soup):
    """Extract player lineup from the match page."""
    numbers = [num.text.strip() for num in soup.find_all(class_='c085-lineup-table-player-number')]
    players = [player.text.strip() for player in soup.find_all(class_='c085-lineup-table-player-name-text')]
    
    # Remove duplicates
    players = list(dict.fromkeys(players))

    # Find split index between home and away players
    try:
        split_index = len(numbers) - numbers[::-1].index('15') - 1
        home_players = {n: " ".join(p.split()) for n, p in zip(numbers[:split_index], players[:split_index])}
        away_players = {n: " ".join(p.split()) for n, p in zip(numbers[split_index:], players[split_index:])}
        return [home_players, away_players]
    except ValueError:
        logging.warning("Could not determine team split index.")
        return [{}, {}]

def fetch_match_data(match_id):
    """Fetch and process match details."""
    url = f'{base_url}match-centre-community?matchId={match_id}#lineup'
    
    logging.info(f"Fetching match data for ID {match_id}")

    # Enhanced headers to mimic a real browser
    match_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"'
    }
    
    # Add a random delay to avoid being detected as a bot
    time.sleep(random.uniform(2, 5))

    try:
        response = requests.get(url, headers=match_headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error fetching match {match_id}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract score — normal matches use c042-match-score; walkovers use c042-score
    score_tag = soup.find(class_='c042-match-score') or soup.find(class_='c042-score')
    if not score_tag:
        logging.warning(f"Match {match_id} has no score available yet.")
        return None
    
    score = _parse_score_text(score_tag.text.strip())
    if score == [None, None]:
        logging.warning(f"Match {match_id} has invalid score format.")
        return None

    # Extract date
    date_tag = soup.find(id='c042-event-date')
    if not date_tag:
        logging.warning(f"Match {match_id} has no date available.")
        return None
    
    try:
        date_text = date_tag.text.strip()
        date = pd.to_datetime(date_text[:date_text.rfind('202') + 4], format="%A %d %B %Y").strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        logging.warning(f"Match {match_id} has invalid date format.")
        return None

    # Calculate season (July to June)
    if date[5:] < "07-01":
        season = f"{int(date[:4])-1}-{date[:4]}"
    else:
        season = f"{date[:4]}-{int(date[:4])+1}"

    # Extract competition
    league_tag = soup.find(id='c042-event-champion')
    if not league_tag:
        logging.warning(f"Match {match_id} has no league information.")
        return None
    league = league_tag.text.strip()

    # Extract team names & logos
    teams = [team.text.strip() for team in soup.find_all(class_='c042-team-name')]
    logos = [img['src'] for img in soup.find_all('img', class_='c042-team-logo')]

    if len(teams) != 2:
        logging.warning(f"Match {match_id} doesn't have exactly 2 teams.")
        return None

    # Extract player lineups only for 1st XV matches
    squad = squad_lookup(season, league)
    players = get_players(soup) if squad == 1 else [{}, {}]

    match_data = {
        "match_id": match_id,
        "season": season,
        "league": league,
        "date": date,
        "teams": teams,
        "score": score,
        "logos": logos,
        "players": players
    }

    # Save individual match file as backup
    match_file = str(_DATA_DIR / "match_data" / f"{match_id}.json")
    try:
        with open(match_file, "w") as f:
            json.dump(match_data, f, indent=4)
        logging.info(f"Saved individual match file: {match_file}")
    except Exception as e:
        logging.warning(f"Could not save individual file for {match_id}: {e}")

    return match_data


def _get_match_sources(squad=1, season="2025/26"):
    """Return match ids and optional prefetched match dict for a squad/season."""
    all_match_ids = fetch_match_ids(squad=squad, season=season)

    # Squad 2 historically used results-page summaries because lineups are not required.
    # Keep those summaries as fallback only; match-centre remains the authoritative source
    # for home/away score orientation.
    if squad == 2:
        results_page_matches = fetch_matches_from_results_page(squad=squad, season=season)
        results_by_id = {match["match_id"]: match for match in results_page_matches}
        return all_match_ids, results_by_id

    return all_match_ids, {}


def _fetch_match_for_squad(match_id, squad, results_by_id):
    """Fetch or retrieve a single match based on squad strategy."""
    if squad == 2:
        # Use match-centre parsing only to keep score order aligned with teams.
        # If unavailable, skip update and retain any existing consolidated record.
        return fetch_match_data(match_id)
    return fetch_match_data(match_id)

def fetch_new_matches_only(squad=1, season="2025/26", consolidated_file=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Fetch new matches AND re-fetch incomplete ones."""
    all_match_ids, results_by_id = _get_match_sources(squad=squad, season=season)
    
    if not all_match_ids:
        logging.warning("No match IDs found for the season.")
        return []
    
    # Get existing match IDs from consolidated file
    existing_match_ids = get_existing_match_ids_from_consolidated(consolidated_file)
    
    # Get incomplete match IDs (in file but missing data)
    incomplete_match_ids = get_incomplete_match_ids(consolidated_file)
    
    # New matches: not in consolidated file at all
    new_match_ids = [mid for mid in all_match_ids if mid not in existing_match_ids]
    
    # Incomplete matches: in file but missing data, and still on website
    retry_match_ids = [mid for mid in incomplete_match_ids if mid in all_match_ids]
    
    # Combine both sets (remove duplicates)
    to_fetch = list(set(new_match_ids + retry_match_ids))

    logging.info(f"Season {season} squad {squad}: {len(all_match_ids)} total matches on website")
    logging.info(f"Found {len(existing_match_ids)} existing matches in consolidated file")
    logging.info(f"Need to fetch: {len(new_match_ids)} new + {len(retry_match_ids)} incomplete = {len(to_fetch)} total")
    
    if not to_fetch:
        logging.info("All matches already in consolidated file with complete data!")
        return []
    
    # Fetch matches
    fetched_matches = []
    for i, match_id in enumerate(to_fetch, 1):
        match_type = "new" if match_id in new_match_ids else "retry"
        logging.info(f"Fetching ({match_type}) {i}/{len(to_fetch)}: {match_id}")

        match_data = _fetch_match_for_squad(match_id, squad, results_by_id)

        if match_data and is_match_complete(match_data):
            fetched_matches.append(match_data)

        if squad != 2 and i < len(to_fetch):
            time.sleep(random.uniform(3, 7))
    
    logging.info(f"Successfully fetched {len(fetched_matches)} matches ({len(fetched_matches)} complete)")
    return fetched_matches

def update_consolidated_file(new_matches, consolidated_file=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Add new matches or update existing ones in the consolidated file."""
    
    # Load existing matches
    existing_matches = load_consolidated_matches(consolidated_file)
    
    # Create dict for quick lookup and updating
    matches_dict = {match['match_id']: match for match in existing_matches if 'match_id' in match}
    
    # Update or add matches
    added_count = 0
    updated_count = 0
    
    for match in new_matches:
        match_id = match['match_id']
        if match_id in matches_dict:
            # Update existing match (in case we re-fetched incomplete data)
            matches_dict[match_id] = match
            updated_count += 1
        else:
            # Add new match
            matches_dict[match_id] = match
            added_count += 1
    
    # Convert back to list
    all_matches = list(matches_dict.values())
    
    if added_count == 0 and updated_count == 0:
        logging.info("No changes to consolidated file")
        return all_matches
    
    # Save
    if save_consolidated_matches(all_matches, consolidated_file):
        logging.info(f"Updated consolidated file: {added_count} added, {updated_count} updated")
    else:
        logging.error("Failed to update consolidated file")
    
    return all_matches


def reconcile_consolidated_from_match_cache(consolidated_file=None, cache_dir=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    if cache_dir is None:
        cache_dir = str(_DATA_DIR / "match_data")
    """Reconcile consolidated matches using authoritative cached match-centre files."""
    existing_matches = load_consolidated_matches(consolidated_file)
    if not existing_matches:
        return 0

    matches_by_id = {str(match.get("match_id")): match for match in existing_matches if match.get("match_id")}
    cache_files = glob.glob(os.path.join(cache_dir, "*.json"))

    updates = 0
    for cache_file in cache_files:
        try:
            with open(cache_file, "r") as f:
                cached_match = json.load(f)
        except Exception:
            continue

        match_id = str(cached_match.get("match_id", ""))
        if not match_id or match_id not in matches_by_id:
            continue

        target = matches_by_id[match_id]

        if cached_match.get("teams") and target.get("teams") and cached_match.get("teams") != target.get("teams"):
            continue

        cached_score = cached_match.get("score")
        if not cached_score or len(cached_score) < 2:
            continue

        if target.get("score") != cached_score:
            target["score"] = cached_score
            if cached_match.get("league"):
                target["league"] = cached_match["league"]
            if cached_match.get("date"):
                target["date"] = cached_match["date"]
            if cached_match.get("logos"):
                target["logos"] = cached_match["logos"]
            updates += 1

    if updates > 0:
        save_consolidated_matches(list(matches_by_id.values()), consolidated_file)
        logging.info(f"Reconciled {updates} consolidated matches from cached match-centre files")

    return updates

def update_league_data(squad=1, season="2025/26", consolidated_file=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Complete workflow: fetch new matches and update consolidated file."""
    
    # Step 1: Fetch only new matches
    new_matches = fetch_new_matches_only(squad=squad, season=season, consolidated_file=consolidated_file)
    
    # Step 2: Update consolidated file with new matches
    all_matches = update_consolidated_file(new_matches, consolidated_file)

    # Step 2b: Reconcile cached match-centre files into consolidated scores
    reconcile_consolidated_from_match_cache(consolidated_file=consolidated_file)
    
    # Step 3: Also fetch/update league table
    try:
        table = fetch_league_table(squad=squad, season=season)
        if table is not None:
            table.to_csv(str(_DATA_DIR / f"league_table_{season.replace('/', '_')}_squad_{squad}.csv"), index=False)
            logging.info(f"Saved league table for {season} squad {squad}")
    except Exception as e:
        logging.error(f"Error fetching league table: {e}")
    
    return all_matches, new_matches

def update_multiple_seasons_and_squads(seasons=None, squads=None, consolidated_file=None):
    """Update data for multiple seasons and squads."""
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    
    if squads is None:
        squads = [1, 2]
    if seasons is None:
        # Derive all seasons that have at least one squad defined
        all_seasons = set()
        for squad_seasons in divisions.values():
            all_seasons.update(squad_seasons.keys())
        seasons = sorted(all_seasons)
    
    total_new_matches = 0
    
    for season in seasons:
        for squad in squads:
            # Skip combinations not defined in the divisions mapping
            if season not in divisions.get(squad, {}):
                logging.debug(f"Skipping {season} squad {squad} - not in divisions mapping")
                continue
            try:
                logging.info(f"\n=== Updating {season} Squad {squad} ===")
                all_matches, new_matches = update_league_data(
                    squad=squad, 
                    season=season, 
                    consolidated_file=consolidated_file
                )
                total_new_matches += len(new_matches)
                
            except Exception as e:
                logging.error(f"Error updating {season} squad {squad}: {e}")
    
    # Generate frontend-ready league tables JSON after all updates
    build_league_tables_json(output_file=str(_DATA_DIR / "league_tables.json"))
    
    # Final summary
    final_matches = load_consolidated_matches(consolidated_file)
    logging.info(f"\n=== SUMMARY ===")
    logging.info(f"Total new matches fetched: {total_new_matches}")
    logging.info(f"Total matches in consolidated file: {len(final_matches)}")
    
    return final_matches

def get_current_season_label():
    """Return current season label in YYYY/YY format (season starts in July)."""
    now = datetime.now()
    start_year = now.year if now.month >= 7 else now.year - 1
    return f"{start_year}/{str((start_year + 1) % 100).zfill(2)}"

def normalize_season_arg(season):
    """Normalize CLI season argument to configured YYYY/YY labels (e.g., 2025/26)."""
    if not season:
        return None

    season = season.strip()

    if re.match(r"^\d{4}/\d{2}$", season):
        return season

    dash_match = re.match(r"^(\d{4})-(\d{4})$", season)
    if dash_match:
        start_year = int(dash_match.group(1))
        end_year = int(dash_match.group(2))
        if end_year == start_year + 1:
            return f"{start_year}/{str(end_year % 100).zfill(2)}"

    return season


def get_configured_seasons(squads=None):
    """Return sorted configured seasons, optionally constrained to specific squads."""
    if squads is None:
        squads = divisions.keys()

    configured = set()
    for squad in squads:
        configured.update(divisions.get(squad, {}).keys())
    return sorted(configured)

def ensure_historical_league_table_cache(current_season=None):
    """Ensure historical league table CSVs exist; fetch only missing historical files."""
    if current_season is None:
        current_season = get_current_season_label()

    for squad, squad_seasons in divisions.items():
        for season in sorted(squad_seasons.keys()):
            if season == current_season:
                continue

            csv_file = str(_DATA_DIR / f"league_table_{season.replace('/', '_')}_squad_{squad}.csv")
            if os.path.exists(csv_file):
                continue

            try:
                logging.info(f"Caching historical league table for {season} squad {squad}")
                table = fetch_league_table(squad=squad, season=season)
                if table is not None:
                    os.makedirs(str(_DATA_DIR), exist_ok=True)
                    table.to_csv(csv_file, index=False)
                    logging.info(f"Cached historical table: {csv_file}")
                else:
                    logging.warning(f"No historical table data returned for {season} squad {squad}")
            except Exception as e:
                logging.error(f"Error caching historical table for {season} squad {squad}: {e}")

def update_current_season_with_historical_cache(squads=None, consolidated_file=None):
    """Cache historical league tables once, then update current season only."""
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    if squads is None:
        squads = [1, 2]

    current_season = get_current_season_label()
    logging.info(f"Current season resolved as {current_season}")

    ensure_historical_league_table_cache(current_season=current_season)
    return update_multiple_seasons_and_squads(
        seasons=[current_season],
        squads=squads,
        consolidated_file=consolidated_file,
    )

def generate_data_report(consolidated_file=None):
    if consolidated_file is None:
        consolidated_file = str(_DATA_DIR / "matches.json")
    """Generate a report of data completeness."""
    matches = load_consolidated_matches(consolidated_file)
    
    if not matches:
        print("No matches found in consolidated file")
        return {}
    
    by_league = {}
    complete_count = 0
    
    for match in matches:
        league = match.get('league', 'Unknown')
        season = match.get('season', 'Unknown')
        key = f"{season} - {league}"
        
        if key not in by_league:
            by_league[key] = {'total': 0, 'complete': 0, 'teams': set()}
        
        by_league[key]['total'] += 1
        by_league[key]['teams'].update(match.get('teams', []))
        
        if is_match_complete(match):
            by_league[key]['complete'] += 1
            complete_count += 1
    
    print("\n=== DATA COMPLETENESS REPORT ===")
    print(f"Total matches: {len(matches)}")
    print(f"Complete matches: {complete_count} ({100*complete_count/len(matches) if matches else 0:.1f}%)")
    print(f"Incomplete matches: {len(matches) - complete_count}")
    print("\nBy league/season:")
    
    for key, stats in sorted(by_league.items()):
        completeness = 100 * stats['complete'] / stats['total'] if stats['total'] > 0 else 0
        print(f"\n{key}:")
        print(f"  Matches: {stats['complete']}/{stats['total']} complete ({completeness:.1f}%)")
        print(f"  Teams: {len(stats['teams'])}")
        team_list = sorted(stats['teams'])[:5]
        if len(stats['teams']) > 5:
            print(f"  Sample: {', '.join(team_list)}...")
        else:
            print(f"  Teams: {', '.join(team_list)}")
    
    return by_league

def save_summary_match_data(matches, output_file=None):
    if output_file is None:
        output_file = str(_DATA_DIR / "matches_summary.csv")
    """Save CSV summary with match results (without temporal league table data)."""
    
    rows = []
    for match in matches:
        home_team = match['teams'][0] if len(match.get('teams', [])) > 0 else ''
        away_team = match['teams'][1] if len(match.get('teams', [])) > 1 else ''
        
        rows.append({
            'match_id': match['match_id'],
            'season': match['season'],
            'league': match['league'],
            'date': match['date'],
            'home_team': home_team,
            'away_team': away_team,
            'home_score': match['score'][0] if match.get('score') and match['score'][0] is not None else '',
            'away_score': match['score'][1] if match.get('score') and match['score'][1] is not None else '',
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False)
    logging.info(f"Saved match summary with {len(df)} matches to {output_file}")
    print(f'Created CSV with {len(matches)} matches')
    print(f'Saved to {output_file}')
    print(f'League table data available separately in data/league_table_*.csv files')

def build_league_tables_json(output_file=None):
    if output_file is None:
        output_file = str(_DATA_DIR / "league_tables.json")
    """Build league_tables.json from CSV league table files for frontend display."""
    
    import glob
    
    # Find all league table CSV files
    csv_pattern = "data/league_table_*.csv"
    csv_files = sorted(glob.glob(csv_pattern))
    
    if not csv_files:
        logging.warning(f"No league table CSV files found matching {csv_pattern}")
        return {}
    
    # Dictionary to build JSON structure
    league_data = {"seasons": []}
    
    # Parse each CSV file
    for csv_file in csv_files:
        try:
            # Extract season and squad from filename
            # Format: data/league_table_YYYY_YY_squad_N.csv
            filename = os.path.basename(csv_file)
            parts = filename.replace('league_table_', '').replace('.csv', '').split('_')
            
            if len(parts) < 4:
                logging.warning(f"Skipping file with unexpected format: {filename}")
                continue
            
            # Reconstruct season string (e.g., 2025_26 -> 2025/26)
            season_str = f"{parts[0]}/{parts[1]}"
            
            # Get squad number (last part after 'squad')
            squad = parts[-1]
            
            # Read CSV
            df = pd.read_csv(csv_file)
            
            # Get division info from the divisions mapping
            squad_int = int(squad)
            division = divisions.get(squad_int, {}).get(season_str, "Unknown")
            
            # Map to squad name
            squad_name = f"{'1st' if squad_int == 1 else '2nd'} Team"
            
            # Convert DataFrame rows to dictionaries
            tables = []
            for _, row in df.iterrows():
                tb = int(row.get('TB', 0)) if pd.notna(row.get('TB')) else 0
                lb = int(row.get('LB', 0)) if pd.notna(row.get('LB')) else 0
                table_entry = {
                    "position": int(row.get('#', 0)) if pd.notna(row.get('#')) else 0,
                    "team": row.get('TEAM', ''),
                    "played": int(row.get('P', 0)) if pd.notna(row.get('P')) else 0,
                    "won": int(row.get('W', 0)) if pd.notna(row.get('W')) else 0,
                    "drawn": int(row.get('D', 0)) if pd.notna(row.get('D')) else 0,
                    "lost": int(row.get('L', 0)) if pd.notna(row.get('L')) else 0,
                    "pointsFor": int(row.get('PF', 0)) if pd.notna(row.get('PF')) else 0,
                    "pointsAgainst": int(row.get('PA', 0)) if pd.notna(row.get('PA')) else 0,
                    "pointsDifference": int(row.get('PD', 0)) if pd.notna(row.get('PD')) else 0,
                    "triesBefore": tb,
                    "triesLost": lb,
                    "bonusPoints": tb + lb,
                    "points": int(row.get('Pts', 0)) if pd.notna(row.get('Pts')) else 0,
                }
                tables.append(table_entry)
            
            # Initialize season if needed
            if season_str not in league_data:
                league_data[season_str] = {}
                league_data["seasons"].append(season_str)
            
            # Add squad data
            league_data[season_str][squad] = {
                "squad": squad_name,
                "division": division,
                "tables": tables
            }
            
            logging.info(f"Loaded {len(tables)} teams from {filename}")
            
        except Exception as e:
            logging.error(f"Error processing {csv_file}: {e}")
            continue
    
    # Sort seasons in descending order (newer first)
    league_data["seasons"] = sorted(league_data["seasons"], reverse=True)
    
    # Save to JSON
    try:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(league_data, f, indent=2)
        logging.info(f"Successfully generated {output_file} with {len(league_data['seasons'])} seasons")
        print(f"Generated {output_file}")
        return league_data
    except Exception as e:
        logging.error(f"Error saving {output_file}: {e}")
        return {}

def main():
    """Main function to fetch and save match data."""
    parser = argparse.ArgumentParser(description="Scrape England Rugby match data.")
    parser.add_argument("--squad", required=False, help="Squad (1 or 2)", default=None, type=int)
    parser.add_argument("--season", required=False, help="Season (e.g., 2025/26)", default=None)
    parser.add_argument("--file", required=False, help="Consolidated match data file", default=str(_DATA_DIR / "matches.json"))
    parser.add_argument("--all", action="store_true", help="Full refresh for all configured seasons and squads")

    args = parser.parse_args()

    if args.squad is not None and args.squad not in divisions:
        parser.error(f"Invalid --squad value '{args.squad}'. Valid options: {sorted(divisions.keys())}")

    normalized_season = normalize_season_arg(args.season)

    if normalized_season:
        valid_seasons = get_configured_seasons([args.squad] if args.squad else None)
        if normalized_season not in valid_seasons:
            parser.error(
                f"Invalid --season value '{args.season}'. "
                f"Valid options: {', '.join(valid_seasons)}"
            )

    if args.all:
        # Full refresh for all seasons and squads
        update_multiple_seasons_and_squads(consolidated_file=args.file)
    elif args.squad is not None and normalized_season:
        # Update specific squad and season
        all_matches, new_matches = update_league_data(
            squad=args.squad, 
            season=normalized_season,
            consolidated_file=args.file
        )
        logging.info(f"Update complete: {len(new_matches)} new matches added")
    elif normalized_season:
        # Update all squads configured for a specific season
        logging.info(f"Updating all configured squads for season {normalized_season}")
        update_multiple_seasons_and_squads(
            seasons=[normalized_season],
            squads=None,
            consolidated_file=args.file,
        )
    elif args.squad is not None:
        # Update all seasons configured for a specific squad
        logging.info(f"Updating all configured seasons for squad {args.squad}")
        update_multiple_seasons_and_squads(
            seasons=None,
            squads=[args.squad],
            consolidated_file=args.file,
        )
    else:
        # Default: cache historical seasons once, then update current season only
        logging.info("No specific squad/season specified. Caching historical league tables and updating current season...")
        update_current_season_with_historical_cache(
            squads=[1, 2],
            consolidated_file=args.file,
        )

    # Generate data quality report
    print("\n" + "="*50)
    generate_data_report(args.file)
    print("="*50 + "\n")
    
    # Save summary CSV
    save_summary_match_data(load_consolidated_matches(args.file), output_file=str(_DATA_DIR / "matches_summary.csv"))
    
    # Generate frontend-ready league tables JSON
    print("="*50)
    print("Generating frontend league tables JSON...")
    build_league_tables_json(output_file=str(_DATA_DIR / "league_tables.json"))
    print("="*50 + "\n")

if __name__ == "__main__":
    main()