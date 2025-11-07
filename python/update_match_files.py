import os
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def calculate_season_from_date(date_str):
    """Calculate season from date string (YYYY-MM-DD format)."""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        year = date.year
        month = date.month
        
        # Season runs July to June
        if month >= 7:  # July onwards = start of new season
            return f"{year}-{year + 1}"
        else:  # January to June = end of previous season
            return f"{year - 1}-{year}"
    except (ValueError, TypeError):
        logging.warning(f"Could not parse date: {date_str}")
        return None

def determine_league_from_teams_and_date(teams, date_str):
    """Determine league based on teams and date."""
    # This is a simplified approach - you might need to adjust based on your data
    
    season = calculate_season_from_date(date_str)
    if not season:
        return None
    
    # Common league patterns (adjust these based on your data)
    league_mappings = {
        "2024-2025": "Counties 1 Surrey/Sussex",  # Default for 2024-25
        "2023-2024": "Counties 1 Surrey/Sussex",  # Default for 2023-24
        "2022-2023": "Counties 2 Sussex",         # Default for 2022-23
        "2025-2026": "Counties 2 Sussex",         # Default for 2025-26
    }
    
    return league_mappings.get(season, "Unknown League")

def update_match_files(match_data_dir="data/match_data", dry_run=False):
    """Update all match JSON files with missing fields."""
    
    if not os.path.exists(match_data_dir):
        logging.error(f"Directory {match_data_dir} does not exist")
        return
    
    json_files = [f for f in os.listdir(match_data_dir) if f.endswith('.json')]
    
    if not json_files:
        logging.warning("No JSON files found")
        return
    
    logging.info(f"Found {len(json_files)} JSON files to process")
    
    updated_count = 0
    error_count = 0
    
    for filename in json_files:
        filepath = os.path.join(match_data_dir, filename)
        match_id = filename.replace('.json', '')
        
        try:
            # Load existing data
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Track what we're updating
            updates = []
            
            # 1. Add match_id if missing
            if 'match_id' not in data:
                data['match_id'] = match_id
                updates.append('match_id')
            elif data['match_id'] != match_id:
                data['match_id'] = match_id
                updates.append('match_id (corrected)')
            
            # 2. Add season if missing (calculate from date)
            if 'season' not in data:
                if 'date' in data:
                    season = calculate_season_from_date(data['date'])
                    if season:
                        data['season'] = season
                        updates.append('season')
                    else:
                        logging.warning(f"Could not determine season for {filename}")
                else:
                    logging.warning(f"No date field found in {filename}")
            
            # 3. Add league if missing (determine from teams and date)
            if 'league' not in data:
                if 'teams' in data and 'date' in data:
                    league = determine_league_from_teams_and_date(data['teams'], data['date'])
                    if league:
                        data['league'] = league
                        updates.append('league')
                else:
                    logging.warning(f"Cannot determine league for {filename} - missing teams or date")
            
            # Save updates if any were made
            if updates:
                if not dry_run:
                    # Create backup
                    backup_path = filepath + '.backup'
                    with open(backup_path, 'w') as f:
                        json.dump(json.load(open(filepath, 'r')), f, indent=4)
                    
                    # Save updated data
                    with open(filepath, 'w') as f:
                        json.dump(data, f, indent=4)
                    
                    logging.info(f"✅ Updated {filename}: {', '.join(updates)}")
                else:
                    logging.info(f"[DRY RUN] Would update {filename}: {', '.join(updates)}")
                
                updated_count += 1
            else:
                logging.debug(f"No updates needed for {filename}")
                
        except Exception as e:
            logging.error(f"❌ Error processing {filename}: {e}")
            error_count += 1
    
    logging.info(f"Processing complete: {updated_count} files updated, {error_count} errors")
    
    if dry_run:
        logging.info("This was a dry run. Use dry_run=False to make actual changes.")

def validate_updated_files(match_data_dir="data/match_data"):
    """Validate that all files have the required fields."""
    
    if not os.path.exists(match_data_dir):
        logging.error(f"Directory {match_data_dir} does not exist")
        return
    
    json_files = [f for f in os.listdir(match_data_dir) if f.endswith('.json')]
    required_fields = ['match_id', 'season', 'league']
    
    missing_fields = {}
    valid_count = 0
    
    for filename in json_files:
        filepath = os.path.join(match_data_dir, filename)
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            missing = []
            for field in required_fields:
                if field not in data:
                    missing.append(field)
            
            if missing:
                missing_fields[filename] = missing
            else:
                valid_count += 1
                
        except Exception as e:
            logging.error(f"Error validating {filename}: {e}")
    
    logging.info(f"Validation complete: {valid_count}/{len(json_files)} files have all required fields")
    
    if missing_fields:
        logging.warning("Files with missing fields:")
        for filename, missing in missing_fields.items():
            logging.warning(f"  {filename}: missing {', '.join(missing)}")
    
    return missing_fields

def fix_specific_leagues(match_data_dir="data/match_data", dry_run=False):
    """Fix league assignments based on more specific criteria."""
    
    # Define more specific league mappings based on your knowledge
    league_corrections = {
        # Format: "season": {"default_league": "Counties X", "exceptions": {"team_name": "Different League"}}
        "2025-2026": {
            "default": "Counties 2 Sussex",
            "2nd_team": "Counties 3 Sussex"
        },
        "2024-2025": {
            "default": "Counties 1 Surrey/Sussex",
            "2nd_team": "Counties 3 Sussex"
        },
        "2023-2024": {
            "default": "Counties 1 Surrey/Sussex",
            "2nd_team": "Counties 2 Sussex"
        },
        "2022-2023": {
            "default": "Counties 2 Sussex",
            "2nd_team": "Counties 3 Sussex"
        }
    }
    
    if not os.path.exists(match_data_dir):
        logging.error(f"Directory {match_data_dir} does not exist")
        return
    
    json_files = [f for f in os.listdir(match_data_dir) if f.endswith('.json')]
    corrections_made = 0
    
    for filename in json_files:
        filepath = os.path.join(match_data_dir, filename)
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if 'season' in data and 'teams' in data:
                season = data['season']
                teams = data['teams']
                
                if season in league_corrections:
                    # Determine if this is likely a 2nd team match
                    # You can adjust this logic based on your team naming conventions
                    is_2nd_team = any('2nd' in team or 'II' in team or 'Development' in team for team in teams)
                    
                    if is_2nd_team:
                        correct_league = league_corrections[season]["2nd_team"]
                    else:
                        correct_league = league_corrections[season]["default"]
                    
                    # Update if different
                    if data.get('league') != correct_league:
                        old_league = data.get('league', 'None')
                        
                        if not dry_run:
                            data['league'] = correct_league
                            
                            with open(filepath, 'w') as f:
                                json.dump(data, f, indent=4)
                        
                        logging.info(f"{'[DRY RUN] ' if dry_run else ''}Corrected {filename}: {old_league} → {correct_league}")
                        corrections_made += 1
                        
        except Exception as e:
            logging.error(f"Error correcting {filename}: {e}")
    
    logging.info(f"League corrections complete: {corrections_made} files corrected")

def main():
    """Main function with options."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Update match JSON files with required fields")
    parser.add_argument("--dir", default="data/match_data", help="Directory containing match JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")
    parser.add_argument("--validate", action="store_true", help="Only validate files (don't update)")
    parser.add_argument("--fix-leagues", action="store_true", help="Apply specific league corrections")
    
    args = parser.parse_args()
    
    if args.validate:
        validate_updated_files(args.dir)
    elif args.fix_leagues:
        fix_specific_leagues(args.dir, dry_run=args.dry_run)
    else:
        # Run the main update
        update_match_files(args.dir, dry_run=args.dry_run)
        
        # Validate after updating
        if not args.dry_run:
            logging.info("\nValidating updated files...")
            validate_updated_files(args.dir)

if __name__ == "__main__":
    main()