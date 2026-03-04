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

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Create directories if they don't exist
os.makedirs("data/match_data", exist_ok=True)

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
    }
}

divisions = {
    1: {
        "2025/26": "Counties 2 Sussex",
        "2024/25": "Counties 1 Surrey/Sussex",
        "2023/24": "Counties 1 Surrey/Sussex",
        "2022/23": "Counties 2 Sussex"
    },
    2: {
        "2025/26": "Counties 3 Sussex",
        "2024/25": "Counties 3 Sussex",
    }
}    

base_url = 'https://www.englandrugby.com/fixtures-and-results/'

def get_url(squad=1, season="2025/26"):
    """Generate URL for fetching match data."""
    
    division = divisions[squad].get(season, None)

    if division is not None:
        season_str = season.replace("/", "-20")
        division_id = division_ids[division][season_str]

        if division in ["Counties 3 Sussex"]:
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

def squad_lookup(season, league):
    """Return the squad number based on season and league."""
    season_key = season.replace('-20', '/')  # Convert 2024-2025 to 2024/25
    for div, seasons in divisions.items():
        if league == seasons.get(season_key):
            return int(div)
    return 1  # Default to squad 1 if not found

def is_match_complete(match_data):
    """Check if match has complete data (score, both team lineups, date)."""
    if not match_data:
        return False
    if not match_data.get('score') or None in match_data.get('score', []):
        return False
    if not match_data.get('players') or len(match_data.get('players', [])) < 2:
        return False
    if not match_data['players'][0] or not match_data['players'][1]:
        return False
    if not match_data.get('date'):
        return False
    return True

def get_existing_match_ids_from_consolidated(consolidated_file="data/matches.json"):
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

def load_consolidated_matches(consolidated_file="data/matches.json"):
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

def get_incomplete_match_ids(consolidated_file="data/matches.json"):
    """Get match IDs that exist but have incomplete data."""
    incomplete_ids = []
    
    matches = load_consolidated_matches(consolidated_file)
    for match in matches:
        if not is_match_complete(match):
            incomplete_ids.append(match['match_id'])
    
    logging.info(f"Found {len(incomplete_ids)} matches with incomplete data")
    return incomplete_ids

def save_consolidated_matches(matches, consolidated_file="data/matches.json"):
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

    # Generate HTML table
    html_table = generate_bootstrap_table(df)

    print(html_table)
    # Save to file (optional)
    os.makedirs("Charts/league", exist_ok=True)
    with open(f"Charts/league/table_{squad}s_{season.replace('/', '-20')}.html", "w") as f:
        f.write(html_table)

    # Output HTML
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
    links = {a['href'].split("=")[-1] for a in soup.find_all('a', href=True) 
             if '/fixtures-and-results/match-centre-community' in a['href']}
    
    logging.info(f"Found {len(links)} match IDs for {season} squad {squad}")
    return list(links)

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

    # Extract score
    score_tag = soup.find(class_='c042-match-score')
    if not score_tag:
        logging.warning(f"Match {match_id} has no score available yet.")
        return None
    
    try:
        score = [int(s) for s in score_tag.text.strip().split(' - ')]
    except ValueError:
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

    # Extract player lineups
    players = get_players(soup)

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
    match_file = f"data/match_data/{match_id}.json"
    try:
        with open(match_file, "w") as f:
            json.dump(match_data, f, indent=4)
        logging.info(f"Saved individual match file: {match_file}")
    except Exception as e:
        logging.warning(f"Could not save individual file for {match_id}: {e}")

    return match_data

def fetch_new_matches_only(squad=1, season="2025/26", consolidated_file="data/matches.json"):
    """Fetch new matches AND re-fetch incomplete ones."""
    
    # Get all match IDs for the season from website
    all_match_ids = fetch_match_ids(squad=squad, season=season)
    
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
        
        match_data = fetch_match_data(match_id)
        if match_data:
            fetched_matches.append(match_data)
        
        # Delay between requests (except for last one)
        if i < len(to_fetch):
            time.sleep(random.uniform(3, 7))
    
    logging.info(f"Successfully fetched {len(fetched_matches)} matches ({len([m for m in fetched_matches if is_match_complete(m)])} complete)")
    return fetched_matches

def update_consolidated_file(new_matches, consolidated_file="data/matches.json"):
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

def update_league_data(squad=1, season="2025/26", consolidated_file="data/matches.json"):
    """Complete workflow: fetch new matches and update consolidated file."""
    
    # Step 1: Fetch only new matches
    new_matches = fetch_new_matches_only(squad=squad, season=season, consolidated_file=consolidated_file)
    
    # Step 2: Update consolidated file with new matches
    all_matches = update_consolidated_file(new_matches, consolidated_file)
    
    # Step 3: Also fetch/update league table
    try:
        table = fetch_league_table(squad=squad, season=season)
        if table is not None:
            os.makedirs("data", exist_ok=True)
            table.to_csv(f"data/league_table_{season.replace('/', '_')}_squad_{squad}.csv", index=False)
            logging.info(f"Saved league table for {season} squad {squad}")
    except Exception as e:
        logging.error(f"Error fetching league table: {e}")
    
    return all_matches, new_matches

def update_multiple_seasons_and_squads(seasons=None, squads=None, consolidated_file="data/matches.json"):
    """Update data for multiple seasons and squads."""
    
    if seasons is None:
        seasons = ["2024/25", "2025/26"]
    if squads is None:
        squads = [1, 2]
    
    total_new_matches = 0
    
    for season in seasons:
        for squad in squads:
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
    
    # Final summary
    final_matches = load_consolidated_matches(consolidated_file)
    logging.info(f"\n=== SUMMARY ===")
    logging.info(f"Total new matches fetched: {total_new_matches}")
    logging.info(f"Total matches in consolidated file: {len(final_matches)}")
    
    return final_matches

def generate_data_report(consolidated_file="data/matches.json"):
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

def save_summary_match_data(matches, output_file="data/matches_summary.csv"):
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

def main():
    """Main function to fetch and save match data."""
    parser = argparse.ArgumentParser(description="Scrape England Rugby match data.")
    parser.add_argument("--squad", required=False, help="Squad (1 or 2)", default=None, type=int)
    parser.add_argument("--season", required=False, help="Season (e.g., 2025/26)", default=None)
    parser.add_argument("--file", required=False, help="Consolidated match data file", default="data/matches.json")
    parser.add_argument("--all", action="store_true", help="Update all seasons and squads")

    args = parser.parse_args()

    if args.all:
        # Update all seasons and squads
        update_multiple_seasons_and_squads(consolidated_file=args.file)
    elif args.squad and args.season:
        # Update specific squad and season
        all_matches, new_matches = update_league_data(
            squad=args.squad, 
            season=args.season, 
            consolidated_file=args.file
        )
        logging.info(f"Update complete: {len(new_matches)} new matches added")
    else:
        # Default: update current season for both squads
        current_season = "2025/26"
        logging.info(f"No specific squad/season specified. Updating {current_season} for both squads...")
        update_multiple_seasons_and_squads(
            seasons=[current_season], 
            squads=[1], 
            consolidated_file=args.file
        )

    # Generate data quality report
    print("\n" + "="*50)
    generate_data_report(args.file)
    print("="*50 + "\n")
    
    # Save summary CSV
    save_summary_match_data(load_consolidated_matches(args.file), output_file="data/matches_summary.csv")

if __name__ == "__main__":
    main()