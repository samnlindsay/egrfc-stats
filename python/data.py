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
    "2021/22": 79578,
    "2022/23": 83980,
    "2023/24": 87941,
    "2024/25": 91673,
    "2025/26": 94981,
}

# ---------------------------------------------------------------------------
# Pitchero opposition name canonicalisation
# ---------------------------------------------------------------------------
# Keys are produced by _normalise_pitchero_key (lowercase, alphanumeric only).
# Values are the canonical EGRFC opposition names used in the games table.
PITCHERO_OPPOSITION_CANONICAL_NAMES: dict[str, str] = {
    # Brighton / Sussex
    "brighton3": "Brighton III",
    "brighton2ndxv": "Brighton II",
    # Bognor
    "bognor2": "Bognor II",
    # Bromley (cup match)
    "papajohnsquarterfinalbromley": "Bromley",
    # Burgess Hill
    "burgesshill2": "Burgess Hill II",
    "burgesshill": "Burgess Hill",
    "burgesshillrfc": "Burgess Hill",
    # Cheshunt (cup match suffix)
    "cheshuntnationalcupquarterfinal": "Cheshunt",
    # Chipstead
    "chipsteadrfc": "Chipstead",
    # Cranleigh
    "cranleighrfc": "Cranleigh",
    # Crawley
    "crawleycupfinal": "Crawley",
    "crawley2": "Crawley II",
    "crawley2s3s": "Crawley II",
    "crawleyii": "Crawley II",
    # Crowborough
    "crowboro2": "Crowborough II",
    "crowborough2ndxv": "Crowborough II",
    "crowborough2s": "Crowborough II",
    "crowboroughii": "Crowborough II",
    # Croydon
    "croydonrfc": "Croydon",
    # Ditchling
    "ditchlingrfc": "Ditchling",
    "ditchling": "Ditchling",
    # Eastbourne
    "eastbourneiirfc": "Eastbourne II",
    "eastbourne2": "Eastbourne II",
    "eastbourne2s": "Eastbourne II",
    "eastbournerfc": "Eastbourne",
    # Haywards Heath
    "haywardsheath2xv": "Haywards Heath II",
    "haywardsheath2xy": "Haywards Heath II",
    "haywardsheath2s": "Haywards Heath II",
    "haywardsheath1stxv": "Haywards Heath",
    # Heathfield
    "heathfield": "Heathfield & Waldron",
    "heathfldwal": "Heathfield & Waldron",
    "heathfield2": "Heathfield & Waldron II",
    "heathfieldii": "Heathfield & Waldron II",
    "heathfield3s": "Heathfield & Waldron III",
    "heathfieldiii": "Heathfield & Waldron III",
    "heathfieldwaldron3": "Heathfield & Waldron III",
    "heathfldwal3": "Heathfield & Waldron III",
    "heathfieldwaldronii": "Heathfield & Waldron II",
    # Hellingly
    "hellingly2": "Hellingly II",
    # Horsham
    "horsham2s": "Horsham II",
    "horshamii": "Horsham II",
    "horshamiiicasuals": "Horsham III",
    # Hove
    "hove2": "Hove II",
    "hove2xv": "Hove II",
    "hove2xy": "Hove II",
    "hoveii": "Hove II",
    "hove3": "Hove III",
    "hove3rdxv": "Hove III",
    # Jersey / Royals
    "jerseyroyals": "Royals",
    "royalsrfc": "Royals",
    # Lewes
    "lewes2": "Lewes II",
    # Midhurst (cup match suffix)
    "sussexcupfinalmidhurst": "Midhurst",
    # Newick
    "newickrfc": "Newick",
    # Oakmedians
    "oakmediansrfc": "Oakmedians",
    # Old Caterhamians
    "oldcaterhamians2s": "Old Caterhamians II",
    # Old Haileyburians (and common misspelling)
    "oldhaileyburians": "Old Haileyburians",
    "oldhaileybarians": "Old Haileyburians",
    # Old Rutlishians
    "oldrutlishians2s": "Old Rutlishians II",
    "oldrutlishiansrfc": "Old Rutlishians",
    # Pulborough
    "pulborough2": "Pulborough II",
    "pulborough3": "Pulborough III",
    "pulborough2ssussexjuniorvase": "Pulborough II",
    # Rye
    "ryerfc": "Rye",
    # Shoreham
    "shoreham2ndxv": "Shoreham II",
    # Trinity
    "trinity2s": "Trinity II",
    # Uckfield
    "uckfieldiirfc": "Uckfield II",
    "uckfield2s": "Uckfield II",
    "uckfield12s": "Uckfield",
    "uckfieldrfc": "Uckfield",
    # Warlingham
    "warlingham3s": "Warlingham III",
    # Wensleydale (cup match suffix)
    "wensleydalepapajohnscupsemifinal": "Wensleydale",
}


def _normalise_pitchero_key(name: str) -> str:
    """Lowercase, strip all non-alphanumeric characters – used as dict lookup key."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def canonical_pitchero_opposition(name: object) -> object:
    """Return the canonical opposition name for a raw Pitchero opposition string.

    Returns the original value unchanged when no mapping is found.
    """
    if name is None or (isinstance(name, float) and name != name):
        return name
    cleaned = str(name).strip()
    canonical = PITCHERO_OPPOSITION_CANONICAL_NAMES.get(_normalise_pitchero_key(cleaned), cleaned)

    # Fallback for unmapped team-suffix shorthand like "Club 2"/"Club 3s".
    if canonical == cleaned:
        suffix_match = re.match(
            r"^(?P<base>.+?)\s*(?P<num>[2-5])(?:st|nd|rd|th)?(?:xv|s)?\s*$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if suffix_match:
            roman = {
                "2": "II",
                "3": "III",
                "4": "IV",
                "5": "V",
            }
            base = suffix_match.group("base").strip()
            canonical = f"{base} {roman[suffix_match.group('num')]}"

    # Strip trailing " RFC" suffix that sometimes leaks through unmapped entries.
    if isinstance(canonical, str) and canonical.upper().endswith(" RFC"):
        canonical = canonical[:-4].strip()
    return canonical


_EGRFC_TEAM_ALIASES = (
    "east grinstead",
    "e grinstead",
    "eg men",
    "egrfc",
)

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

    @staticmethod
    def _normalise_sheet_header(header_value):
        if not isinstance(header_value, str):
            header_value = str(header_value or "")
        return re.sub(r"[^a-z0-9]+", "", header_value.lower())

    def _build_team_sheet_layout(self, header_row, squad_name):
        normalized_headers = [self._normalise_sheet_header(value) for value in header_row]

        shirt_col_map = {}
        for idx, header in enumerate(header_row):
            header_value = str(header).strip()
            shirt_match = re.fullmatch(r"#?(\d{1,2})", header_value)
            if not shirt_match:
                continue
            shirt_no = int(shirt_match.group(1))
            if 1 <= shirt_no <= 29:
                shirt_col_map[shirt_no] = idx

        vc_cols = [idx for idx, header in enumerate(normalized_headers) if header == "vc"]

        layout = {
            "date": normalized_headers.index("date") if "date" in normalized_headers else 0,
            "season": normalized_headers.index("season") if "season" in normalized_headers else 1,
            "competition": normalized_headers.index("competition") if "competition" in normalized_headers else 2,
            "opposition": normalized_headers.index("opposition") if "opposition" in normalized_headers else 3,
            "score": normalized_headers.index("score") if "score" in normalized_headers else 4,
            "captain": normalized_headers.index("captain") if "captain" in normalized_headers else 5,
            "motm": normalized_headers.index("motm") if "motm" in normalized_headers else None,
            "vc_cols": vc_cols,
            "shirt_col_map": shirt_col_map,
        }

        if layout["motm"] is None:
            layout["motm"] = 9 if squad_name == "1st" else 7

        if not layout["vc_cols"]:
            layout["vc_cols"] = [6, 7] if squad_name == "1st" else [6]

        return layout

    @staticmethod
    def _get_row_value(row, column_index):
        if column_index is None or column_index >= len(row):
            return ""
        return row[column_index].strip()

    @staticmethod
    def _normalise_team_name(team_name):
        if not isinstance(team_name, str):
            return ""
        cleaned = re.sub(r"[^a-z0-9]+", " ", team_name.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def _is_egrfc_team_name(team_name):
        normalized = DataExtractor._normalise_team_name(team_name)
        if not normalized:
            return False
        return any(alias in normalized for alias in _EGRFC_TEAM_ALIASES)
        
    def extract_games_data(self):
        """Extract games data from team sheets"""
        ss = self.client.open_by_url(self.sheet_url)
        
        games_data = []
        
        for squad_name, sheet_name in [("1st", "1st XV Players"), ("2nd", "2nd XV Players")]:
            sheet = ss.worksheet(sheet_name)
            data = sheet.get_all_values()
            layout = self._build_team_sheet_layout(data[3] if len(data) >= 4 else [], squad_name)
            
            # Skip header rows
            for row in data[4:]:  # Assuming data starts at row 6
                if not self._get_row_value(row, layout["season"]):  # Skip if no season
                    continue
                    
                game_data = self._parse_game_row(row, squad_name, layout)
                if game_data:
                    games_data.append(game_data)
        
        return pd.DataFrame(games_data)
    
    def _parse_game_row(self, row, squad, layout):
        """Parse a single game row from team sheet"""
        try:
            date = self._parse_date(self._get_row_value(row, layout["date"]))
            season = self._get_row_value(row, layout["season"])
            competition = self._get_row_value(row, layout["competition"])
            opposition_raw = self._get_row_value(row, layout["opposition"])
            score = self._get_row_value(row, layout["score"])
            captain = self._get_row_value(row, layout["captain"])
            vc_values = [self._get_row_value(row, idx) for idx in layout["vc_cols"]]
            vc_values = [value for value in vc_values if value]
            vc1 = vc_values[0] if len(vc_values) >= 1 else None
            vc2 = vc_values[1] if len(vc_values) >= 2 else None
            motm = self._get_row_value(row, layout["motm"]) or None
            
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
                'motm': motm,
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
            layout = self._build_team_sheet_layout(data[3] if len(data) >= 4 else [], squad_name)

            for row in data[4:]:
                if not self._get_row_value(row, layout["season"]):  # Skip if no season
                    continue
                    
                # Extract game info
                date = self._parse_date(self._get_row_value(row, layout["date"]))
                opposition = self._get_row_value(row, layout["opposition"]).replace('(H)', '').replace('(A)', '').strip()
                game_id = f"{date}_{squad_name}_{opposition}".replace(' ', '_').replace('/', '')
                captain = self._get_row_value(row, layout["captain"])
                vice_captains = [self._get_row_value(row, idx) for idx in layout["vc_cols"]]
                vice_captains = [value for value in vice_captains if value]
                
                # Extract players (positions 1-29) using header-derived column map
                for pos in range(1, 30):
                    col_idx = layout["shirt_col_map"].get(pos)
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
                                'is_vc': player in vice_captains,
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
                    home_is_egrfc = self._is_egrfc_team_name(home_team)
                    away_is_egrfc = self._is_egrfc_team_name(away_team)
                    if not home_is_egrfc and not away_is_egrfc:
                        continue

                    if fixture_data["home_score"] is None or fixture_data["away_score"] is None:
                        continue

                    home_away = "H" if home_is_egrfc else "A"
                    opposition = canonical_pitchero_opposition(
                        away_team if home_away == "H" else home_team
                    )
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

                    # Extract scorers from /events endpoint
                    scorers_data = {}
                    motm = None
                    events_url = self._normalise_events_url(fixture_data.get("match_url"))
                    if events_url:
                        events_soup = self._fetch_soup(session, events_url, timeout=timeout)
                        if events_soup:
                            scorers_data = self._parse_pitchero_scorers_from_events_page(events_soup)
                            motm = self._parse_pitchero_motm_from_events_page(events_soup)

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
                        "motm": motm,
                        "vc1": None,
                        "vc2": None,
                        "tries_scorers": json.dumps(scorers_data.get("tries_scorers", {})),
                        "conversions_scorers": json.dumps(scorers_data.get("conversions_scorers", {})),
                        "penalties_scorers": json.dumps(scorers_data.get("penalties_scorers", {})),
                        "drop_goals_scorers": json.dumps(scorers_data.get("drop_goals_scorers", {})),
                        "pitchero_match_url": events_url or None,
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
                        'notes': str(row.get('Notes', '')).strip(),
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
        set_piece_data = []

        for squad_name, sheet_name in [("1st", "1st XV Set piece"), ("2nd", "2nd XV Set piece")]:
            try:
                sheet = ss.worksheet(sheet_name)
                # Extract one wide range so set piece and red zone are handled together.
                data = sheet.get("A5:AH")
                
                for row in data:
                    if len(row) <= 2 or not row[1]:
                        continue

                    eg_entries = self._safe_int(row[24] if len(row) > 24 else None)
                    opp_entries = self._safe_int(row[28] if len(row) > 28 else None)
                    eg_points_per_entry = self._safe_float(row[25] if len(row) > 25 else None)
                    opp_points_per_entry = self._safe_float(row[29] if len(row) > 29 else None)
                    eg_tries = self._safe_int(row[26] if len(row) > 26 else None)
                    opp_tries = self._safe_int(row[30] if len(row) > 30 else None)
                    eg_tries_per_entry = self._safe_float(row[27] if len(row) > 27 else None)
                    opp_tries_per_entry = self._safe_float(row[31] if len(row) > 31 else None)

                    if eg_tries_per_entry is None and eg_entries not in (None, 0) and eg_tries is not None:
                        eg_tries_per_entry = eg_tries / eg_entries
                    if opp_tries_per_entry is None and opp_entries not in (None, 0) and opp_tries is not None:
                        opp_tries_per_entry = opp_tries / opp_entries

                    game_data = {
                        "team": ["EG", "Opp"],
                        "lineouts_won": [self._safe_int(row[8] if len(row) > 8 else None), self._safe_int(row[11] if len(row) > 11 else None)],
                        "lineouts_total": [self._safe_int(row[9] if len(row) > 9 else None), self._safe_int(row[12] if len(row) > 12 else None)],
                        "scrums_won": [self._safe_int(row[16] if len(row) > 16 else None), self._safe_int(row[19] if len(row) > 19 else None)],
                        "scrums_total": [self._safe_int(row[17] if len(row) > 17 else None), self._safe_int(row[20] if len(row) > 20 else None)],
                        "entries_22m": [eg_entries, opp_entries],
                        "points": [self._safe_int(row[5] if len(row) > 5 else None), self._safe_int(row[6] if len(row) > 6 else None)],
                        "tries": [eg_tries, opp_tries],
                        "points_per_entry": [eg_points_per_entry, opp_points_per_entry],
                        "tries_per_entry": [eg_tries_per_entry, opp_tries_per_entry],
                    }

                    for i, team in enumerate(game_data["team"]):
                        set_piece_data.append({
                            "date": self._parse_date(row[2]),
                            "squad": squad_name,
                            "team": team,
                            "lineouts_won": game_data["lineouts_won"][i],
                            "lineouts_total": game_data["lineouts_total"][i],
                            "scrums_won": game_data["scrums_won"][i],
                            "scrums_total": game_data["scrums_total"][i],
                            "entries_22m": game_data["entries_22m"][i],
                            "points": game_data["points"][i],
                            "tries": game_data["tries"][i],
                            "points_per_entry": game_data["points_per_entry"][i],
                            "tries_per_entry": game_data["tries_per_entry"][i],
                        })
            except Exception as e:
                print(f"Error extracting set piece stats for {squad_name}: {e}")

        if not set_piece_data:
            return pd.DataFrame(columns=[
                "game_id",
                "team",
                "lineouts_won",
                "lineouts_total",
                "scrums_won",
                "scrums_total",
                "entries_22m",
                "points",
                "tries",
                "points_per_entry",
                "tries_per_entry",
            ])

        # Join to games to get game_id
        df_set_piece = pd.DataFrame(set_piece_data)
        df_games = self.extract_games_data()[['game_id', 'date', 'squad']]
        df_set_piece['date'] = pd.to_datetime(df_set_piece['date'])
        df_games['date'] = pd.to_datetime(df_games['date'])
        # Merge on date and squad
        df_merged = pd.merge(df_set_piece, df_games, on=['date', 'squad'], how='left')
        df_merged.drop(columns=['date', 'squad'], inplace=True) # drop date and squad columns
        df_merged = df_merged[[
            'game_id',
            'team',
            'lineouts_won',
            'lineouts_total',
            'scrums_won',
            'scrums_total',
            'entries_22m',
            'points',
            'tries',
            'points_per_entry',
            'tries_per_entry',
        ]]
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

    def _safe_float(self, value):
        """Safely convert to float"""
        try:
            return float(value) if value not in (None, "") else None
        except:
            return None

    def _normalise_events_url(self, match_url):
        """Convert match URL to /events endpoint."""
        if not match_url:
            return None
        if "/events" in match_url:
            return match_url
        if match_url.endswith("/lineup"):
            return match_url.rstrip("/").replace("/lineup", "/events")
        # For URL like /teams/142068/match-centre/1-15439074/lineup
        # Convert to /teams/142068/match-centre/1-15439074/events
        if "/match-centre/" in match_url:
            base = match_url.rstrip("/").replace("/lineup", "")
            return base + "/events"
        return match_url.rstrip("/") + "/events"

    def _parse_pitchero_scorers_from_events_page(self, events_soup):
        """Extract scorers from Pitchero /events page payload.

        Preferred source is the structured Next.js payload embedded in
        ``__NEXT_DATA__``. Fall back to loose text parsing only if the payload
        does not expose scorer events.
        """
        if not events_soup:
            return {}
        
        result = {
            "tries_scorers": {},
            "conversions_scorers": {},
            "penalties_scorers": {},
            "drop_goals_scorers": {}
        }
        
        try:
            next_data = self._extract_next_data_payload(events_soup)
            if next_data:
                parsed = self._parse_pitchero_scorers_from_next_data(next_data)
                if any(parsed.values()):
                    return parsed

            full_text = events_soup.get_text(" ", strip=True)
            if "Tries:" in full_text or "Conversions:" in full_text or "Penalties:" in full_text or "Drop Goals:" in full_text:
                self._extract_scorers_from_text(full_text, result)

            return result
        except Exception as e:
            logger.warning(f"Failed to parse Pitchero scorers: {e}")
            return {}

    def _parse_pitchero_scorers_from_next_data(self, next_data):
        """Extract structured scorer summaries from Pitchero Next.js payload."""
        result = {
            "tries_scorers": {},
            "conversions_scorers": {},
            "penalties_scorers": {},
            "drop_goals_scorers": {},
        }

        try:
            page_data = (
                next_data.get("props", {})
                .get("initialReduxState", {})
                .get("teams", {})
                .get("matchCentre", {})
                .get("pageData", {})
            )
            if not page_data:
                return result

            match_entry = next(iter(page_data.values()))
            overview = match_entry.get("overview") or {}
            ha = (overview.get("ha") or "").lower()
            team_side = "home" if ha == "h" else "away" if ha == "a" else None

            if team_side:
                for event_group in ((overview.get(team_side) or {}).get("events") or []):
                    target_key = self._pitchero_event_label_to_scorer_key(event_group.get("label"))
                    if not target_key:
                        continue
                    scorers = {}
                    for player in event_group.get("players") or []:
                        player_name = (player.get("name") or "").strip()
                        count = self._safe_int(player.get("count")) or 0
                        if not player_name or count <= 0:
                            continue
                        scorers[clean_name(player_name)] = count
                    if scorers:
                        result[target_key] = scorers

            if any(result.values()):
                return result

            events_by_period = match_entry.get("eventsByPeriod") or []
            for period in events_by_period:
                for event in period.get("events") or []:
                    event_type = (event.get("eventType") or "").strip()
                    target_key = self._pitchero_event_label_to_scorer_key(event_type)
                    if not target_key:
                        continue
                    if event.get("type") != "event":
                        continue
                    player_name = (event.get("playerName") or "").strip()
                    if not player_name:
                        continue
                    canonical_name = clean_name(player_name)
                    result[target_key][canonical_name] = result[target_key].get(canonical_name, 0) + 1
        except Exception:
            return result

        return result

    def _parse_pitchero_motm_from_events_page(self, events_soup):
        """Extract Star Player / MOTM from Pitchero events page payload."""
        if not events_soup:
            return None
        try:
            next_data = self._extract_next_data_payload(events_soup)
            if not next_data:
                return self._parse_pitchero_motm_from_events_html(events_soup)
            motm = self._parse_pitchero_motm_from_next_data(next_data)
            if motm:
                return motm
            return self._parse_pitchero_motm_from_events_html(events_soup)
        except Exception:
            return None

    def _parse_pitchero_motm_from_events_html(self, events_soup):
        """Fallback parser for Star Player from rendered events HTML."""
        try:
            heading = events_soup.find(
                ["h3", "h4"],
                string=lambda s: isinstance(s, str) and "star player" in s.lower(),
            )
            if heading is None:
                return None

            candidate = heading.find_next(string=True)
            while candidate:
                text = (candidate or "").strip()
                if text and text.lower() != "star player":
                    return text
                candidate = candidate.find_next(string=True)
        except Exception:
            return None
        return None

    def _parse_pitchero_motm_from_next_data(self, next_data):
        """Extract our side's Star Player from Pitchero Next.js payload."""
        try:
            page_data = (
                next_data.get("props", {})
                .get("initialReduxState", {})
                .get("teams", {})
                .get("matchCentre", {})
                .get("pageData", {})
            )
            if not page_data:
                return None

            match_entry = next(iter(page_data.values()))
            overview = match_entry.get("overview") or {}
            ha = (overview.get("ha") or "").lower()
            team_side = "home" if ha == "h" else "away" if ha == "a" else None

            # Pitchero has moved this field between overview and match root.
            raw_players = match_entry.get("playersOfTheMatch")
            if raw_players is None:
                raw_players = overview.get("playersOfTheMatch")
            if raw_players is None:
                return None
            if isinstance(raw_players, dict):
                raw_players = [raw_players]
            if not isinstance(raw_players, list):
                return None

            def _extract_name(entry):
                if isinstance(entry, str):
                    return entry.strip() or None
                if not isinstance(entry, dict):
                    return None

                direct = entry.get("name") or entry.get("playerName") or entry.get("displayName")
                if isinstance(direct, str) and direct.strip():
                    return direct.strip()

                player_obj = entry.get("player")
                if isinstance(player_obj, dict):
                    nested = player_obj.get("name") or player_obj.get("playerName") or player_obj.get("displayName")
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
                return None

            def _entry_side(entry):
                if not isinstance(entry, dict):
                    return None
                value = (
                    entry.get("ha")
                    or entry.get("side")
                    or entry.get("team")
                    or entry.get("homeAway")
                    or entry.get("home_away")
                )
                if isinstance(value, str):
                    value = value.lower().strip()
                    if value in {"h", "home"}:
                        return "home"
                    if value in {"a", "away"}:
                        return "away"
                return None

            if team_side:
                for entry in raw_players:
                    if _entry_side(entry) != team_side:
                        continue
                    name = _extract_name(entry)
                    if name:
                        return name

            for entry in raw_players:
                name = _extract_name(entry)
                if name:
                    return name
        except Exception:
            return None

        return None

    def _pitchero_event_label_to_scorer_key(self, label):
        """Map Pitchero scorer labels/event types to backend scorer columns."""
        normalized = re.sub(r"[^a-z]+", " ", (label or "").lower()).strip()
        mapping = {
            "try": "tries_scorers",
            "tries": "tries_scorers",
            "conversion": "conversions_scorers",
            "conversions": "conversions_scorers",
            "penalty": "penalties_scorers",
            "penalties": "penalties_scorers",
            "drop goal": "drop_goals_scorers",
            "drop goals": "drop_goals_scorers",
        }
        return mapping.get(normalized)

    def _extract_scorers_from_text(self, text, result):
        """Extract individual scorer categories from text like:
        'Tries: A Moffatt (2), A Yaffa, J Radcliffe Conversions: L Maker (2) ...'
        """
        # Split by scorer categories
        categories = {
            "Tries": "tries_scorers",
            "Conversions": "conversions_scorers",
            "Penalties": "penalties_scorers",
            "Drop Goals": "drop_goals_scorers",
        }
        
        for category_name, result_key in categories.items():
            if category_name not in text:
                continue
            
            # Split on this category
            parts = text.split(f"{category_name}:")
            if len(parts) < 2:
                continue
            
            scorers_text = parts[1]
            
            # Find where this category ends (at next category or end of string)
            for next_cat in categories.keys():
                if next_cat != category_name and next_cat in scorers_text:
                    scorers_text = scorers_text.split(next_cat)[0]
                    break
            
            # Parse individual scorers
            scorers = self._parse_scorers_text(scorers_text)
            result[result_key] = scorers

    def _parse_scorers_text(self, text):
        """Parse scorer text like 'A Moffatt (2), A Yaffa, J Radcliffe' into dict.
        
        Returns:
            dict: {"canonical_name": count, ...}
        """
        scorers = {}
        
        if not text:
            return scorers
        
        # Split by comma
        for entry in text.split(","):
            entry = entry.strip()
            if not entry:
                continue
            
            # Try to match "Name (count)" pattern
            match = re.match(r"^(.+?)\s*\((\d+)\)\s*$", entry)
            if match:
                name = match.group(1).strip()
                count = int(match.group(2))
                canonical = clean_name(name)
                scorers[canonical] = count
            elif entry and not entry.startswith("("):
                # Single entry without count (count = 1)
                canonical = clean_name(entry.strip())
                if canonical:  # Only add if non-empty
                    scorers[canonical] = 1
        
        return scorers
       