#!/usr/bin/env python3
"""
Investigate Pitchero match pages to understand scorer data availability.
Fetches sample matches from 2024/25 and earlier seasons to understand:
1. Where scorer data appears in the Redux state
2. Data quality and completeness
3. Extraction difficulty
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from pathlib import Path
import sys
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from python.data import DataExtractor

def fetch_pitchero_match_page(match_url: str, timeout=20) -> dict:
    """Fetch a match centre page and extract Redux state."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    
    try:
        response = session.get(match_url, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        script_node = soup.find("script", id="__NEXT_DATA__")
        if not script_node:
            return {"error": "No __NEXT_DATA__ found"}
        
        raw = script_node.get_text(strip=True)
        if not raw:
            return {"error": "Empty __NEXT_DATA__"}
        
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}


def extract_scorers_from_match_data(next_data: dict, match_url: str) -> dict:
    """Extract scorer information from Redux state."""
    try:
        page_data = (
            next_data.get("props", {})
            .get("initialReduxState", {})
            .get("teams", {})
            .get("matchCentre", {})
            .get("pageData", {})
        )
        
        if not page_data:
            return {"error": "No pageData found", "available_keys": list(next_data.keys())}
        
        # Get the match entry (there's typically one)
        match_entry = next(iter(page_data.values()))
        
        overview = match_entry.get("overview", {})
        lineup = match_entry.get("lineup", {})
        
        result = {
            "match_url": match_url,
            "overview": {
                "home_team": overview.get("home_team"),
                "away_team": overview.get("away_team"),
                "home_score": overview.get("home_score"),
                "away_score": overview.get("away_score"),
                "date": overview.get("date"),
            },
            "lineup_available": bool(lineup),
            "available_keys_in_match_entry": list(match_entry.keys()),
            "scorer_data": {},
        }
        
        # Check for scorers in various possible locations
        if "scorers" in match_entry:
            result["scorer_data"]["scorers_key"] = match_entry["scorers"]
        
        if "stats" in match_entry:
            stats = match_entry["stats"]
            result["scorer_data"]["stats"] = {
                "type": type(stats).__name__,
                "keys": list(stats.keys()) if isinstance(stats, dict) else "not a dict"
            }
        
        if "match_stats" in match_entry:
            result["scorer_data"]["match_stats"] = {
                "type": type(match_entry["match_stats"]).__name__,
                "keys": list(match_entry["match_stats"].keys()) if isinstance(match_entry["match_stats"], dict) else "not a dict"
            }
        
        # Look through all keys for anything scorer-related
        for key in match_entry.keys():
            if any(term in key.lower() for term in ["score", "point", "try", "con", "penalty"]):
                val = match_entry[key]
                result["scorer_data"][f"found_key_{key}"] = {
                    "type": type(val).__name__,
                    "preview": str(val)[:200] if isinstance(val, str) else val
                }
        
        return result
    except Exception as e:
        return {"error": f"Extraction failed: {e}"}


def find_sample_matches_2024_25():
    """Find some 2024/25 matches to investigate."""
    # These are sample Pitchero match URLs for 2024/25 season
    # You would need to populate these from actual match data
    
    # Format: https://www.egrfc.com/matches/{match_id}
    # Or: https://www.egrfc.com/match-centre/{match_id}
    
    # Let's try to get them from the fixtures page
    sample_urls = []
    
    # Try fixture pages for different squads
    for squad, team_id in [(1, "142068"), (2, "142069")]:
        for season_id in ["91673"]:  # 2024/25
            fixtures_url = f"https://www.egrfc.com/teams/{team_id}/fixtures-results?season={season_id}"
            print(f"\n📍 Fetching fixtures list: {fixtures_url}")
            
            try:
                session = requests.Session()
                session.headers.update({
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                })
                response = session.get(fixtures_url, timeout=20)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                
                # Find match links
                for fixture_div in soup.find_all("div", class_="fixture-overview"):
                    for link in fixture_div.find_all("a", href=True):
                        if "/match-centre/" in link["href"]:
                            match_url = link["href"]
                            if not match_url.startswith("http"):
                                match_url = "https://www.egrfc.com" + match_url
                            sample_urls.append(match_url)
                            if len(sample_urls) >= 4:
                                break
                    if len(sample_urls) >= 4:
                        break
            except Exception as e:
                print(f"  ❌ Failed to fetch fixtures: {e}")
    
    return sample_urls


def main():
    print("=" * 80)
    print("PITCHERO SCORERS DATA INVESTIGATION")
    print("=" * 80)
    
    # Try to find actual match URLs
    print("\n🔍 Searching for 2024/25 match URLs...")
    sample_urls = find_sample_matches_2024_25()
    
    if not sample_urls:
        print("⚠️  No match URLs found automatically. Using hardcoded examples...")
        # Fallback: Use known 2024/25 matches if available
        sample_urls = [
            "https://www.egrfc.com/match-centre/2024-09-07-egrfc-vs-becceham",
            "https://www.egrfc.com/match-centre/2024-10-05-seaford-vs-egrfc",
        ]
    
    print(f"📋 Found {len(sample_urls)} sample match URLs to investigate\n")
    
    # Investigate each match
    investigation_results = []
    for i, match_url in enumerate(sample_urls[:3], 1):
        print(f"\n{'='*80}")
        print(f"MATCH {i}: {match_url}")
        print('='*80)
        
        print("📥 Fetching match page...")
        next_data = fetch_pitchero_match_page(match_url)
        
        if "error" in next_data:
            print(f"❌ Error: {next_data['error']}")
            if "available_keys" in next_data:
                print(f"   Available keys in response: {next_data['available_keys']}")
            continue
        
        print("✅ Match page fetched, extracting scorer data...")
        result = extract_scorers_from_match_data(next_data, match_url)
        investigation_results.append(result)
        
        # Pretty print results
        print(f"\n📊 Match Overview:")
        print(f"  {result['overview']['home_team']} {result['overview']['home_score']}")
        print(f"  vs")
        print(f"  {result['overview']['away_team']} {result['overview']['away_score']}")
        print(f"  Date: {result['overview']['date']}")
        
        print(f"\n📋 Available keys in match entry:")
        for key in result['available_keys_in_match_entry']:
            print(f"  - {key}")
        
        if result['scorer_data']:
            print(f"\n🎯 Scorer data found:")
            for key, value in result['scorer_data'].items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                else:
                    print(f"  {key}: {value}")
        else:
            print("\n⚠️  No scorer data keys found in match entry")
        
        # Save raw Redux state for inspection
        output_file = Path(__file__).parent.parent / f"data/pitchero_redux_sample_{i}.json"
        with open(output_file, "w") as f:
            json.dump(next_data, f, indent=2)
        print(f"\n💾 Full Redux state saved to: {output_file}")
    
    # Summary
    print("\n" + "=" * 80)
    print("INVESTIGATION SUMMARY")
    print("=" * 80)
    
    if investigation_results:
        print(f"\n✅ Successfully investigated {len(investigation_results)} matches")
        
        # Check for common keys
        all_keys = set()
        for result in investigation_results:
            if "error" not in result:
                all_keys.update(result['available_keys_in_match_entry'])
        
        print(f"\n🔑 Keys found across all match entries:")
        for key in sorted(all_keys):
            count = sum(1 for r in investigation_results if key in r.get('available_keys_in_match_entry', []))
            print(f"  - {key}: {count}/{len(investigation_results)} matches")
        
        # Check for scorers
        scorer_keys_found = set()
        for result in investigation_results:
            if "scorer_data" in result and result["scorer_data"]:
                for key in result["scorer_data"].keys():
                    scorer_keys_found.add(key)
        
        if scorer_keys_found:
            print(f"\n🎯 Scorer-related keys found:")
            for key in scorer_keys_found:
                print(f"  - {key}")
        else:
            print("\n⚠️  No scorer-related keys found. The data may be elsewhere or stored differently.")
    
    print("\n📝 Next steps:")
    print("  1. Check the saved Redux state JSON files to understand the structure")
    print("  2. Look for 'scorers', 'match_stats', or 'stats' keys in the match entry")
    print("  3. If found, design extraction logic based on the actual structure")
    print("  4. Test on multiple seasons to identify schema variations")


if __name__ == "__main__":
    main()
