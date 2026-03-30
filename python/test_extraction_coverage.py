#!/usr/bin/env python3
"""
Extract scorers from sample Pitchero matches and analyze coverage improvement.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pandas as pd
from python.data import DataExtractor, HISTORIC_PITCHERO_SEASON_IDS
import logging
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_sample_fixtures(squad=1, season="2024/25", max_fixtures=5):
    """Fetch sample fixtures from Pitchero to test extraction."""
    
    if season not in HISTORIC_PITCHERO_SEASON_IDS:
        logger.warning(f"Season {season} not in HISTORIC_PITCHERO_SEASON_IDS")
        return []
    
    season_id = HISTORIC_PITCHERO_SEASON_IDS[season]
    squad_label = "1st" if squad == 1 else "2nd"
    team_id = f"14206{8 if squad == 1 else 9}"
    
    fixtures_url = f"https://www.egrfc.com/teams/{team_id}/fixtures-results?season={season_id}"
    
    logger.info(f"Fetching fixtures from: {fixtures_url}")
    
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        response = session.get(fixtures_url, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        fixtures = soup.find_all("div", class_="fixture-overview")
        
        logger.info(f"Found {len(fixtures)} fixtures")
        
        return fixtures[:max_fixtures]
    
    except Exception as e:
        logger.error(f"Failed to fetch fixtures: {e}")
        return []

def test_extraction_on_sample_fixtures():
    """Extract and test scorers from sample fixtures."""
    
    print("=" * 80)
    print("TESTING SCORERS EXTRACTION ON SAMPLE FIXTURES")
    print("=" * 80)
    
    extractor = DataExtractor.__new__(DataExtractor)
    
    # Get sample fixtures
    print("\n📍 Fetching sample 2024/25 1st XV fixtures...\n")
    fixtures = get_sample_fixtures(squad=1, season="2024/25", max_fixtures=3)
    
    if not fixtures:
        print("❌ Could not fetch sample fixtures. Network issue or season not available.")
        return
    
    print(f"✅ Found {len(fixtures)} fixture(s) to test\n")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    
    extraction_results = []
    
    for i, fixture in enumerate(fixtures, 1):
        print(f"\n{'='*80}")
        print(f"FIXTURE {i}")
        print('='*80)
        
        # Parse fixture info
        fixture_data = extractor._parse_pitchero_fixture(fixture)
        if not fixture_data:
            print("❌ Could not parse fixture")
            continue
        
        print(f"  {fixture_data['home_team']} {fixture_data.get('home_score', '?')} vs " 
              f"{fixture_data['away_team']} {fixture_data.get('away_score', '?')}")
        print(f"  Date: {fixture_data.get('date_text', 'Unknown')}")
        print(f"  Match URL: {fixture_data.get('match_url', 'N/A')}")
        
        # Get /events URL
        events_url = extractor._normalise_events_url(fixture_data.get("match_url"))
        if not events_url:
            print("  ❌ Could not determine events URL")
            continue
        
        print(f"  Events URL: {events_url}")
        
        # Fetch and extract scorers
        print(f"\n  📥 Fetching /events page...")
        try:
            response = session.get(events_url, timeout=20)
            response.raise_for_status()
            events_soup = BeautifulSoup(response.content, "html.parser")
            
            scorers_data = extractor._parse_pitchero_scorers_from_events_page(events_soup)
            
            print(f"  ✅ Successfully extracted scorers\n")
            
            # Display results
            for category in ["tries_scorers", "conversions_scorers", "penalties_scorers", "drop_goals_scorers"]:
                category_name = category.replace("_scorers", "").title()
                scorers = scorers_data.get(category, {})
                if scorers:
                    scorers_str = ", ".join([f"{name} ({count})" for name, count in scorers.items()])
                    print(f"    {category_name}: {scorers_str}")
                else:
                    print(f"    {category_name}: (none)")
            
            extraction_results.append({
                "home_team": fixture_data.get("home_team"),
                "away_team": fixture_data.get("away_team"),
                "tries": bool(scorers_data.get("tries_scorers")),
                "conversions": bool(scorers_data.get("conversions_scorers")),
                "penalties": bool(scorers_data.get("penalties_scorers")),
                "drop_goals": bool(scorers_data.get("drop_goals_scorers")),
                "any_scorers": any([
                    scorers_data.get("tries_scorers"),
                    scorers_data.get("conversions_scorers"),
                    scorers_data.get("penalties_scorers"),
                    scorers_data.get("drop_goals_scorers"),
                ])
            })
        
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Failed to fetch events page: {e}")
        except Exception as e:
            print(f"  ❌ Error extracting scorers: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    
    if extraction_results:
        df = pd.DataFrame(extraction_results)
        
        total = len(df)
        with_scorers = df['any_scorers'].sum()
        with_tries = df['tries'].sum()
        with_conversions = df['conversions'].sum()
        with_penalties = df['penalties'].sum()
        
        print(f"\n✅ Extraction Results:")
        print(f"  Total fixtures tested: {total}")
        print(f"  With any scorer data: {with_scorers}/{total} ({with_scorers/total*100:.1f}%)")
        print(f"    - With tries: {with_tries}/{total}")
        print(f"    - With conversions: {with_conversions}/{total}")
        print(f"    - With penalties: {with_penalties}/{total}")
    
    return extraction_results

def analyze_coverage_improvement():
    """Compare coverage before and after extraction."""
    
    print("\n\n" + "=" * 80)
    print("COVERAGE ANALYSIS: BEFORE vs AFTER EXTRACTION")
    print("=" * 80)
    
    # Load current backend games
    games_json = Path("data/backend/games.json")
    if not games_json.exists():
        print("❌ games.json not found")
        return
    
    with open(games_json) as f:
        games = json.load(f)
    
    df = pd.DataFrame(games)
    
    # Current coverage (before extraction would have happened)
    print("\n📊 CURRENT BACKEND COVERAGE:\n")
    
    # Check what's populated
    df['tries_scorers_exists'] = df['tries_scorers'].notna() & (df['tries_scorers'] != '{}')
    df['conv_scorers_exists'] = df['conversions_scorers'].notna() & (df['conversions_scorers'] != '{}')
    df['pen_scorers_exists'] = df['penalties_scorers'].notna() & (df['penalties_scorers'] != '{}')
    df['any_scorers'] = df['tries_scorers_exists'] | df['conv_scorers_exists'] | df['pen_scorers_exists']
    
    summary = df.groupby(['season', 'squad']).agg({
        'game_id': 'count',
        'any_scorers': 'sum',
        'tries_scorers_exists': 'sum',
        'conv_scorers_exists': 'sum',
        'pen_scorers_exists': 'sum',
    }).round(0).astype(int)
    
    summary.columns = ['Total Games', 'Games w/ Any Scorers', 'Tries', 'Conversions', 'Penalties']
    
    print(summary.to_string())
    
    # Overall stats
    print("\n\n📈 OVERALL STATISTICS:\n")
    
    total_games = len(df)
    games_with_scorers = df['any_scorers'].sum()
    games_with_tries = df['tries_scorers_exists'].sum()
    games_with_conversions = df['conv_scorers_exists'].sum()
    games_with_penalties = df['pen_scorers_exists'].sum()
    
    print(f"  Total games in backend: {total_games}")
    print(f"  Games with ANY scorer data: {games_with_scorers}/{total_games} ({games_with_scorers/total_games*100:.1f}%)")
    print(f"  Games with TRIES scorers: {games_with_tries}/{total_games} ({games_with_tries/total_games*100:.1f}%)")
    print(f"  Games with CONVERSIONS scorers: {games_with_conversions}/{total_games} ({games_with_conversions/total_games*100:.1f}%)")
    print(f"  Games with PENALTIES scorers: {games_with_penalties}/{total_games} ({games_with_penalties/total_games*100:.1f}%)")
    
    # Check which seasons have gaps
    print("\n\n🎯 SEASONS WITH MISSING SCORER DATA:\n")
    
    gaps_found = False
    for season in sorted(df['season'].unique()):
        season_df = df[df['season'] == season]
        missing = season_df[season_df['any_scorers'] == False]
        if len(missing) > 0:
            gaps_found = True
            print(f"  {season}: {len(missing)} games missing scorer data")
    
    if not gaps_found:
        print("  ✅ No gaps found! All games have scorer data.")
    
    return df

if __name__ == "__main__":
    # Test extraction on sample fixtures
    extraction_results = test_extraction_on_sample_fixtures()
    
    # Analyze overall coverage
    df = analyze_coverage_improvement()
    
    print("\n" + "=" * 80)
    print("INVESTIGATION COMPLETE")
    print("=" * 80)
    print("\n📝 Next steps:")
    print("  1. Code is ready in python/data.py for full extraction")
    print("  2. To enable full extraction, call extract_pitchero_historic_team_sheets()")
    print("  3. Integration with backend pipeline via python/update.py")
