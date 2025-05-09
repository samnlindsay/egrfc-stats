import requests
import os
import json
import pandas as pd
import argparse
import logging
from bs4 import BeautifulSoup

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
        "2024-2025": 56612,
        "2023-2024": 47017,
    },
    "Counties 2 Sussex": {
        "2024-2025": 56914,
        "2023-2024": 47022,
        "2022-2023": 39123,
    },
    "Counties 3 Sussex": {
        "2024-2025": 57767,
    },
    "Women's NC 2 South East (South)": {
        "2024-2025": 56677,
    },
}

def fetch_league_table(season="2024-2025", league="Counties 1 Surrey/Sussex", comp="London & SE Division"):
    """Fetch league table from the England Rugby website."""

    # If string arg can be coerced to int, use it as competition ID
    competition = comp if comp.isdigit() else competition_ids[comp]
    division = league if league.isdigit() else division_ids[league][season]

    url = f'https://www.englandrugby.com/fixtures-and-results/search-results?competition={competition}&season={season}&division={division}#tables'
    logging.info(f"Fetching match list from: {url}")

    response = requests.get(url)

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find_all('table')[0]
    df = pd.read_html(str(table))[0]
    df.rename(columns={"+/-":"PD"}, inplace=True)

    def generate_bootstrap_table(df, title="League Table"):
        table_html = f'''
        <table class="table table-striped table-borderless mx-auto text-center align-middle small" id="leagueTable">
            <thead class="table-danger">
                <tr>{''.join(f'<th {'id="table'+col+'"'}>{col}</th>' for col in df.columns)}</tr>
            </thead>
            <tbody>
                {
                    ''.join(
                        f'<tr{' class="table-primary fw-bold"' if row["TEAM"]=="East Grinstead" else ''}>' + ''.join(
                            f'<td class="p-1" {'id="table'+col+'"'}>{row[col]}</td>' for col in df.columns
                        ) + '</tr>' for _, row in df.iterrows()
                    )
                }
            </tbody>
        </table>
        '''
        return table_html

    # Generate HTML table
    html_table = generate_bootstrap_table(df)

    # Save to file (optional)
    with open(f"Charts/league/table_{season}.html", "w") as f:
        f.write(html_table)

    # Output HTML
    return df


def fetch_match_ids(season="2024-2025", league="Counties 1 Surrey/Sussex", comp="London & SE Division"):
    """Fetch match IDs from the England Rugby website."""

    competition = comp if comp.isdigit() else competition_ids[comp]
    division = league if league.isdigit() else division_ids[league][season]

    url = f'https://www.englandrugby.com/fixtures-and-results/search-results?competition={competition}&season={season}&division={division}#results'
    logging.info(f"Fetching match list from: {url}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error fetching match list: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    links = {a['href'].split("=")[-1] for a in soup.find_all('a', href=True) 
             if '/fixtures-and-results/match-centre-community' in a['href']}
    
    logging.info(f"Found {len(links)} match IDs.")
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
    url = f'https://www.englandrugby.com/fixtures-and-results/match-centre-community?matchId={match_id}#lineup'
    logging.info(f"Fetching match data for ID {match_id}")

    # Check if match data already exists
    if os.path.exists(f"data/match_data/{match_id}.json"):
        logging.info(f"Match {match_id} already exists. Skipping.")
        return None

    try:
        response = requests.get(url, timeout=30)
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
    
    score = [int(s) for s in score_tag.text.strip().split(' - ')]

    # Extract date
    date_tag = soup.find(id='c042-event-date')
    if not date_tag:
        logging.warning(f"Match {match_id} has no date available.")
        return None
    
    date_text = date_tag.text.strip()
    date = pd.to_datetime(date_text[:date_text.rfind('202') + 4], format="%A %d %B %Y").strftime("%Y-%m-%d")

    # Calculate season (July to June)
    if date[5:] < "07-01":
        season = f"{int(date[:4])-1}-{date[:4]}"
    else:
        season = f"{date[:4]}-{int(date[:4])+1}"

    # Extract competition
    league = soup.find(id='c042-event-champion').text.strip()

    # Extract team names & logos
    teams = [team.text.strip() for team in soup.find_all(class_='c042-team-name')]
    logos = [img['src'] for img in soup.find_all('img', class_='c042-team-logo')]

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

    return match_data

def save_match_data(matches, filename="data/matches.json"):
    """Save match data to a JSON file."""
    if os.path.exists(filename):
        with open(filename, "r") as f:
            existing_data = json.load(f)
    else:
        existing_data = []

    # Avoid duplicates
    existing_ids = {m["match_id"] for m in existing_data}
    new_matches = [m for m in matches if m and m["match_id"] not in existing_ids]

    if new_matches:
        existing_data.extend(new_matches)
        with open(filename, "w") as f:
            json.dump(existing_data, f, indent=4)
        logging.info(f"Saved {len(new_matches)} new matches.")
    else:
        logging.info("No new match data to save.")

def main():
    """Main function to fetch and save match data."""
    parser = argparse.ArgumentParser(description="Scrape England Rugby match data.")
    parser.add_argument("--season", required=False, help="Season (e.g., 2024-2025)", default="2024-2025")
    parser.add_argument("--league", required=False, help="League (e.g., Counties 1 Surrey/Sussex)", default="Counties 1 Surrey/Sussex")
    parser.add_argument("--comp", required=False, help="Competition (e.g., London & SE Division)", default="London & SE Division")
    parser.add_argument("--file", required=False, help="Output file for match data", default="data/matches.json")

    args = parser.parse_args()

    table = fetch_league_table(args.season, args.league, args.comp)

    match_ids = fetch_match_ids(args.season, args.league, args.comp)
    if not match_ids:
        logging.error("No match IDs found. Exiting.")
        return

    matches = [fetch_match_data(match_id) for match_id in match_ids]
    save_match_data(matches, filename=args.file)

if __name__ == "__main__":
    main()
