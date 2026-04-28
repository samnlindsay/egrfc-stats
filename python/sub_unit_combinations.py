"""Generate charts for most common sub-unit (bench) combinations."""

import json
from pathlib import Path
import pandas as pd
import altair as alt
from python.chart_helpers import hack_params_css, alt_theme

alt.themes.register("my_custom_theme", alt_theme)
alt.themes.enable("my_custom_theme")


def _to_short_name(full_name):
    """Convert full name to short form, e.g. 'Guy Collins' -> 'G Collins'."""
    if not full_name:
        return "Unknown"
    parts = str(full_name).strip().split()
    if len(parts) < 2:
        return str(full_name).strip()
    initial = parts[0][0]
    surname = " ".join(parts[1:])
    return f"{initial} {surname}"


def _get_granular_unit(shirt_number):
    """
    Classify shirt numbers into granular tactical units for substitutes.
    Shirt numbers 1-15 are starters; 16+ are bench/subs.
    
    Returns: (unit_key, unit_label)
    """
    num = int(shirt_number) if shirt_number else 0
    
    if num in [1, 2, 3]:
        return ("front_row", "Front Row (1, 2, 3)")
    elif num in [4, 5]:
        return ("second_row", "Second Row (4, 5)")
    elif num in [6, 7, 8]:
        return ("back_row", "Back Row (6, 7, 8)")
    elif num in [9, 10]:
        return ("half_backs", "Half Backs (9, 10)")
    elif num in [12, 13]:
        return ("centres", "Centres (12, 13)")
    elif num in [11, 14, 15]:
        return ("back_three", "Back Three (11, 14, 15)")
    else:
        return (None, None)


def sub_unit_combinations_chart(db, output_dir="data/charts", output_file=None):
    """
    Generate charts showing the most common playing unit combinations (starters only).
    
    For each tactical unit (Front Row, Second Row, etc.), group all starters
    by game and find the most common player combinations that appeared together.
    
    Args:
        db: Database connection with player_appearances table
        output_dir: Directory to save charts
        output_file: Optional - if provided, saves all data to a single JSON file
        
    Returns:
        dict: {'unit_key': chart_object, ...}
    """
    
    # Define unit groups (using shirt numbers for starters)
    units = {
        "front_row": {"positions": [1, 2, 3], "label": "Front Row (1, 2, 3)"},
        "second_row": {"positions": [4, 5], "label": "Second Row (4, 5)"},
        "back_row": {"positions": [6, 7, 8], "label": "Back Row (6, 7, 8)"},
        "half_backs": {"positions": [9, 10], "label": "Half Backs (9, 10)"},
        "centres": {"positions": [12, 13], "label": "Centres (12, 13)"},
        "back_three": {"positions": [11, 14, 15], "label": "Back Three (11, 14, 15)"},
    }
    
    # Query for starters (on-field players)
    query = """
    SELECT
        squad,
        date,
        game_id,
        player,
        number,
        season,
        game_type
    FROM player_appearances
    WHERE is_starter = TRUE
    AND number IS NOT NULL
    AND number >= 1
    AND number <= 15
    ORDER BY game_id, number
    """
    
    df = db.con.execute(query).df()
    
    if df.empty:
        print("No starter data available")
        return {}
    
    # Process each unit
    charts = {}
    all_data_for_export = []
    
    for unit_key, unit_info in units.items():
        positions = unit_info["positions"]
        label = unit_info["label"]
        
        # Filter to players in this unit
        unit_df = df[df["number"].isin(positions)].copy()
        
        if unit_df.empty:
            print(f"No data for {label}")
            continue
        
        # Group by game_id to find player combinations
        combinations = []
        
        for game_id, group in unit_df.groupby("game_id"):
            # Get players sorted by position (shirt number)
            players = group.sort_values("number")
            
            # Create combination key in shirt-number order using short-name formatting
            player_names = players["player"].tolist()
            short_player_names = [_to_short_name(name) for name in player_names]
            combo_str = " / ".join(short_player_names)
            
            combination_data = {
                "game_id": game_id,
                "squad": group["squad"].iloc[0],
                "date": group["date"].iloc[0],
                "season": group["season"].iloc[0],
                "game_type": group["game_type"].iloc[0],
                "unit": label,
                "unit_key": unit_key,
                "combination": combo_str,
                "player_count": len(players),
                "players": short_player_names,
            }
            combinations.append(combination_data)
            all_data_for_export.append(combination_data)
        
        if not combinations:
            continue
        
        # Count frequency of each combination
        combo_df = pd.DataFrame(combinations)
        combo_counts = (
            combo_df
            .groupby("combination")
            .agg({
                "game_id": "count",
                "squad": "first",
                "unit": "first",
            })
            .rename(columns={"game_id": "frequency"})
            .reset_index()
            .sort_values("frequency", ascending=False)
        )
        
        # Add rank
        combo_counts["rank"] = range(1, len(combo_counts) + 1)
        
        # Create bar chart
        chart = alt.Chart(combo_counts).mark_bar().encode(
            x=alt.X(
                "frequency:Q",
                title="Number of Appearances",
            ),
            y=alt.Y(
                "combination:N",
                sort="-x",
                title=None,
                axis=alt.Axis(labelLimit=300),
            ),
            color=alt.Color(
                "squad:N",
                scale=alt.Scale(domain=["1st", "2nd"], range=["#202946", "#7d96e8"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("combination:N", title="Players"),
                alt.Tooltip("frequency:Q", title="Appearances"),
                alt.Tooltip("squad:N", title="Squad"),
            ],
        ).properties(
            width=400,
            height=alt.Step(25),
            title=alt.Title(
                text=label,
                subtitle=f"{len(combo_counts)} unique combinations"
            ),
        )
        
        # Save chart
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        chart_file = output_path / f"sub_unit_combinations_{unit_key}.json"
        chart.save(str(chart_file))
        
        # Apply CSS hack for responsive styling
        try:
            hack_params_css(str(chart_file))
        except Exception as e:
            print(f"Warning: Could not apply CSS hack to {chart_file}: {e}")
        
        charts[unit_key] = chart
        print(f"Generated chart for {label}: {len(combo_counts)} combinations")
    
    # Optionally export all data to a single JSON file
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Serialize date objects
        for item in all_data_for_export:
            item["date"] = str(item["date"])
        
        with open(output_path, "w") as f:
            json.dump(all_data_for_export, f, indent=2)
        print(f"Exported all data to {output_file}")
    
    return charts


if __name__ == "__main__":
    # Example usage
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from python.backend import BackendDatabase
    
    db = BackendDatabase()
    charts = sub_unit_combinations_chart(db)
    
    print(f"\nGenerated {len(charts)} charts")
