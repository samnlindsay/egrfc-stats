#!/usr/bin/env python3
"""
Analyze current scorer data availability across all seasons and squads.
"""

import json
import pandas as pd
from pathlib import Path

def analyze_scorer_coverage():
    """Analyze which games have scorer data."""
    
    games_json = Path("data/backend/games.json")
    if not games_json.exists():
        print("❌ games.json not found")
        return
    
    with open(games_json) as f:
        games = json.load(f)
    
    df = pd.DataFrame(games)
    
    # Check which seasons/squads have scorers
    df['tries_scorers_exists'] = df['tries_scorers'].notna() & (df['tries_scorers'] != '{}')
    df['conv_scorers_exists'] = df['conversions_scorers'].notna() & (df['conversions_scorers'] != '{}')
    df['pen_scorers_exists'] = df['penalties_scorers'].notna() & (df['penalties_scorers'] != '{}')
    df['any_scorers'] = df['tries_scorers_exists'] | df['conv_scorers_exists'] | df['pen_scorers_exists']
    
    print("=" * 80)
    print("CURRENT SCORER DATA AVAILABILITY")
    print("=" * 80)
    
    print("\n📊 GAMES WITH SCORER DATA BY SEASON/SQUAD:\n")
    
    summary = df.groupby(['season', 'squad']).agg({
        'game_id': 'count',
        'any_scorers': 'sum',
        'tries_scorers_exists': 'sum',
        'conv_scorers_exists': 'sum',
        'pen_scorers_exists': 'sum',
    }).round(0).astype(int)
    
    summary.columns = ['Total Games', 'Games w/ Any Scorers', 'Games w/ Tries', 'Games w/ Conversions', 'Games w/ Penalties']
    
    print(summary.to_string())
    
    print("\n\n📋 DETAILED BREAKDOWN:\n")
    for (season, squad), group in df.groupby(['season', 'squad']):
        total = len(group)
        with_scorers = group['any_scorers'].sum()
        pct = (with_scorers / total * 100) if total > 0 else 0
        print(f"  {season} {squad}XV: {with_scorers:3d}/{total:3d} games ({pct:5.1f}%) have scorer data")
    
    print("\n\n🎯 MISSING SCORER DATA BY SEASON:\n")
    for season in sorted(df['season'].unique()):
        season_df = df[df['season'] == season]
        missing = season_df[season_df['any_scorers'] == False]
        if len(missing) > 0:
            print(f"  {season}: {len(missing)} games missing ANY scorer data")
            # Show a few examples
            for i, (_, game) in enumerate(missing.iterrows()):
                if i < 3:
                    print(f"    • {game['date']} {game['squad']}XV vs {game['opposition']}")
            if len(missing) > 3:
                print(f"    ... and {len(missing) - 3} more")
        else:
            print(f"  {season}: ✅ All games have scorer data")

if __name__ == "__main__":
    analyze_scorer_coverage()
