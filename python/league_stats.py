#!/usr/bin/env python3
"""
League Statistics Generator

Reads match data from matches_summary.csv and generates analysis charts
for a specific squad and season.

Usage:
    python league_stats.py --squad 1 --season 2025/26
    python league_stats.py --all  # Generate for all squads and seasons
"""

import sys
import json
import os
import pandas as pd
import altair as alt
import argparse
import logging
from pathlib import Path
from bs4 import BeautifulSoup

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from python.chart_helpers import hack_params_css, alt_theme


# Division definitions
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

def squad_lookup(season, league):
    """Return the squad number based on season and league"""
    season_key = season.replace('-20', '/')  # Convert 2024-2025 to 2024/25
    for div, seasons in divisions.items():
        if league == seasons.get(season_key):
            return int(div)
    return 2

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Register Altair theme from charts.py
alt.themes.register("my_custom_theme", alt_theme)
alt.themes.enable("my_custom_theme")

# Define file paths (relative to project root)
MATCHES_SUMMARY_CSV = project_root / "data" / "matches_summary.csv"
MATCHES_JSON = project_root / "data" / "matches.json"

def load_match_data():
    """Load match data from CSV and JSON files."""
    # Load summary CSV
    if not MATCHES_SUMMARY_CSV.exists():
        raise FileNotFoundError(f"Match summary file '{MATCHES_SUMMARY_CSV}' not found. Run league_data.py first.")
    
    df_summary = pd.read_csv(MATCHES_SUMMARY_CSV)
    logging.info(f"Loaded {len(df_summary)} matches from {MATCHES_SUMMARY_CSV}")
    
    # Load full JSON for player data
    if not MATCHES_JSON.exists():
        logging.warning(f"Match JSON file '{MATCHES_JSON}' not found. Player data will be unavailable.")
        matches_json = []
    else:
        with open(MATCHES_JSON, 'r') as f:
            matches_json = json.load(f)
        logging.info(f"Loaded {len(matches_json)} matches from {MATCHES_JSON}")
    
    return df_summary, matches_json

def get_available_seasons_and_squads(df_players):
    """Get list of available seasons and squads from player data."""
    if df_players.empty:
        return [], []
    
    available_squads = sorted([int(s) for s in df_players["Squad"].dropna().unique() if pd.notna(s)])
    available_seasons = sorted(df_players["Season"].unique())
    
    return available_seasons, available_squads

# Color scheme from css/variables.css
EG_PRIMARY = "#202946"  # --primary-color (dark blue)
EG_ACCENT = "#7d96e8"   # --accent-color (light blue)
EG_GREEN = "#146f14"    # --green-color
EG_RED = "#991515"      # --red-color

# Generic colors for other teams
GENERIC_FILL = "#cccccc"   # Light gray fill
GENERIC_STROKE = "#666666" # Dark gray stroke

def get_team_colors(team_name):
    """Return fill and stroke colors for a team.
    East Grinstead teams use brand colors, all others use generic gray."""
    if "East Grinstead" in team_name:
        return [EG_PRIMARY, EG_ACCENT]
    else:
        return [GENERIC_FILL, GENERIC_STROKE]

def prepare_player_data(matches_json):
    """Extract player appearance data from JSON matches."""
    data = []
    
    for match in matches_json:
        match_id = match["match_id"]
        match_date = match["date"]
        teams = match["teams"]
        players = match.get("players", [{}, {}])
        season = match["season"]
        league = match["league"]
        
        # Determine squad from league
        squad = squad_lookup(season, league)

        for i in range(2):  # Loop over both teams
            team_name = teams[i]
            
            # Check if players data exists and is valid
            if players and len(players) > i and isinstance(players[i], dict):
                for position, player_name in players[i].items():
                    data.append({
                        "Match ID": match_id,
                        "Season": season,
                        "League": league,
                        "Date": match_date,
                        "Squad": squad,
                        "Team": team_name,
                        "Player": player_name,
                        "Position": position,
                        "Color1": get_team_colors(team_name)[0], 
                        "Color2": get_team_colors(team_name)[1]
                    })

    df = pd.DataFrame(data)
    
    if not df.empty:
        # Convert date to datetime and sort
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values(["Team", "Date"])
    
    return df

def classify_unit(position):
    """Classify position into unit, handling both numeric and text positions."""
    if pd.isna(position) or position == "":
        return "Bench"
    
    position_str = str(position).strip()
    
    # Handle numeric positions
    if position_str.isdigit():
        pos_num = int(position_str)
        if pos_num <= 8:
            return "Forwards"
        elif pos_num <= 15:
            return "Backs"
        else:
            return "Bench"
    else:
        # Handle text positions (substitutes, etc.)
        return "Bench"

def create_squad_charts(df, squad_number, season_filter=None):
    """Create charts for a specific squad"""
    
    if df.empty:
        logging.warning("No player data available for squad charts")
        return None, None
    
    # Add unit classification
    df["Unit"] = df["Position"].apply(classify_unit)
    
    # Filter data for specific squad
    squad_df = df[df["Squad"] == squad_number].copy()
    
    if squad_df.empty:
        logging.warning(f"No data found for squad {squad_number}")
        return None, None
    
    # Further filter by season if specified
    if season_filter:
        squad_df = squad_df[squad_df["Season"] == season_filter]
        if squad_df.empty:
            logging.warning(f"No data found for squad {squad_number} in season {season_filter}")
            return None, None
    
    logging.info(f"Creating charts for Squad {squad_number} with {len(squad_df)} player records")
    
    # Summary Statistics for this squad
    appearance_count = (
        squad_df.groupby(["Season", "Team", "Color1", "Color2", "Player"]).size()
        .reset_index(name="Appearances")
        .sort_values("Appearances", ascending=False)
    )
    
    players_per_team = (
        squad_df.groupby(["Season", "Team", "Color1", "Color2", "Player"])["Unit"]
        .agg(lambda x: "Forwards" if "Forwards" in x.values else "Backs" if "Backs" in x.values else "Bench")
        .reset_index()
        .groupby(["Season", "Team", "Color1", "Color2", "Unit"])
        .size()
        .reset_index()
        .rename(columns={0: "Total Players"})
    )

    total_players_per_team = squad_df.groupby(["Season", "Team", "Color1", "Color2"])["Player"].nunique().reset_index()
    total_players_per_team.columns = ["Season", "Team", "Color1", "Color2", "Total Players"]
    total_players_per_team["Unit"] = "Total"

    players_per_team = pd.concat([players_per_team, total_players_per_team], ignore_index=True)

    # Retention data for this squad
    retention_data = []
    for (team, season), matches in squad_df.sort_values("Date", ascending=True).groupby(["Team", "Season"]):
        prev_squad = set()
        prev_forwards = set()
        prev_backs = set()
        
        for match_id, match in matches.groupby("Match ID"):
            current_squad = set(match[match["Unit"] != "Bench"]["Player"])
            forwards = set(match[match["Unit"] == "Forwards"]["Player"])
            backs = set(match[match["Unit"] == "Backs"]["Player"])
            
            # Find opposition team - get all teams in this match that aren't the current team
            all_teams_in_match = squad_df[squad_df["Match ID"] == match_id]["Team"].unique()
            opposition = [t for t in all_teams_in_match if t != team]
            opposition_name = opposition[0] if opposition else "Unknown"
            
            if prev_squad:
                retained = len(current_squad & prev_squad)
                retained_forwards = len(forwards & prev_forwards)
                retained_backs = len(backs & prev_backs)
            else:
                retained = None
                retained_forwards = None
                retained_backs = None

            retention_data.append({
                "Match ID": match_id,
                "Season": season,
                "Date": match["Date"].iloc[0],
                "Team": team,
                "Opposition": opposition_name,
                "Players Retained": retained,
                "Forwards Retained": retained_forwards,
                "Backs Retained": retained_backs,
                "Color1": match["Color1"].iloc[0],
                "Color2": match["Color2"].iloc[0]
            })
            
            prev_squad = current_squad
            prev_forwards = forwards
            prev_backs = backs

    retention_df = pd.DataFrame(retention_data).dropna()

    # Average squad retention per team
    average_retention = (
        retention_df
        .groupby(["Season", "Team", "Color1", "Color2"])
        .agg({"Players Retained": "mean", "Forwards Retained": "mean", "Backs Retained": "mean"})
        .reset_index()
        .melt(["Season", "Team", "Color1", "Color2"], var_name="Unit", value_name="Average Retention")
    )
    average_retention["Unit"] = average_retention["Unit"].str.replace(" Retained", "").replace("Players", "Total")

    ##############
    ### CHARTS ###
    ##############

    # Unit selection (Total/Forwards/Backs)
    unit_radio = alt.binding_radio(
        options=["Total", "Forwards", "Backs"], 
        name="Unit"
    )
    unit_select = alt.selection_point(fields=["Unit"], bind=unit_radio, value="Total")

    team_dropdown = alt.binding_select(
        options=[None] + sorted(squad_df["Team"].unique().tolist()), 
        name="Highlighted Team",
        labels=["All"] + sorted(squad_df["Team"].unique())
    )
    team_select = alt.selection_point(fields=["Team"], bind=team_dropdown, value="East Grinstead")

    # Radio button season selection
    # Note: We'll use the first season as default to avoid filter issues with "All Seasons"
    season_options = sorted(squad_df["Season"].unique().tolist())
    season_labels = [f"{s[:4]}/{s[7:]}" for s in sorted(squad_df["Season"].unique())]
    season_radio = alt.binding_radio(
        options=season_options, 
        name="Season", 
        labels=season_labels
    )
    # Set default to the most recent season
    default_season = sorted(squad_df["Season"].unique().tolist())[-1]
    season_select = alt.selection_point(fields=["Season"], bind=season_radio, value=default_season)

    # Players per team chart
    squad_label = f"{squad_number}st XV" if squad_number == 1 else f"{squad_number}nd XV"
    
    players_per_team_chart = (
        alt.Chart(players_per_team)
        .mark_bar(strokeWidth=2)
        .encode(
            x=alt.X("Total Players:Q", title="Total Players"),
            y=alt.Y("Team:N", sort="-x", title=None),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Team", "Unit", "Total Players"],
        )
        .properties(
            title=alt.Title(
                text=f"Squad Size - {squad_label}", 
                subtitle="Total players representing each team across the season."
            ),
            width=500, height=300
        )
        .add_params(season_select, unit_select)
        .transform_filter(season_select)
        .transform_filter(unit_select)
    )

    # Reshape retention data for unit selection
    retention_long = retention_df.melt(
        id_vars=["Match ID", "Season", "Date", "Team", "Opposition", "Color1", "Color2"],
        value_vars=["Players Retained", "Forwards Retained", "Backs Retained"],
        var_name="Unit",
        value_name="Retained"
    )
    retention_long["Unit"] = retention_long["Unit"].str.replace(" Retained", "").replace("Players", "Total")

    # Retention chart
    retention_chart = (
        alt.Chart(retention_long)
        .mark_line(point={"size": 50})
        .encode(
            x=alt.X("Date:T", title="Match Date"),
            y=alt.Y(
                "Retained:Q", 
                title="Players Retained", 
            ),
            color=alt.Color("Color1:N", scale=None, legend=None),
            detail="Team:N",
            tooltip=[
                alt.Tooltip("Team:N", title="Team"),
                alt.Tooltip("Opposition:N", title="Opposition"),
                alt.Tooltip("Date:T", title="Date", format="%d %b %Y"),
                alt.Tooltip("Unit:N", title="Unit"),
                alt.Tooltip("Retained:Q", title="Players Retained")
            ],
        )
        .properties(
            title=alt.Title(
                text=f"Squad Retention Over Time - {squad_label}",
                subtitle="Number of players retained in the starting XV from the previous match."
            ),
            width=1000,
            height=400
        )
        .add_params(season_select, unit_select)
        .transform_filter(season_select)
        .transform_filter(unit_select)
    )

    # Average retention chart
    average_retention_chart = (
        alt.Chart(average_retention)
        .mark_bar()
        .encode(
            x=alt.X("Average Retention:Q", title="Average Players Retained"),
            y=alt.Y("Team:N", sort="-x", title=None, axis=alt.Axis(ticks=False, domain=False, labelPadding=10)),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Team", "Unit:N", alt.Tooltip("Average Retention:Q", format=".2f")],
        )
        .properties(
            title=alt.Title(
                text=f"Average Squad Retention - {squad_label}",
                subtitle="Average players retained from the starting XV."
            ), 
            width=500, height=300
        )
        .add_params(season_select, unit_select)
        .transform_filter(season_select)
        .transform_filter(unit_select)
    )

    # Return individual chart components for combining later
    return {
        'players_per_team': players_per_team_chart,
        'average_retention': average_retention_chart,
        'retention': retention_chart,
        'squad_df': squad_df
    }

def league_results_chart(matches_json, squad_number, season, table_order=False):
    """Create league results chart for a specific squad and season showing ALL teams in that league."""
    
    # Filter matches for this squad and season
    squad_matches = []
    for match in matches_json:
        match_squad = squad_lookup(match["season"], match["league"])
        
        if match_squad == squad_number and match["season"] == season:
            squad_matches.append(match)
    
    if not squad_matches:
        logging.warning(f"No data found for squad {squad_number} in season {season}")
        return None
    
    # Create results dataframe
    df_results = pd.DataFrame(squad_matches)
    df_results = df_results[["season", "league", "date", "teams", "score"]]
    
    df_results["Home"] = df_results["teams"].apply(lambda x: x[0])
    df_results["Away"] = df_results["teams"].apply(lambda x: x[1])
    df_results["PF"] = df_results["score"].apply(lambda x: x[0])
    df_results["PA"] = df_results["score"].apply(lambda x: x[1])
    df_results["PD"] = df_results["PF"] - df_results["PA"]
    df_results["score"] = df_results["score"].apply(lambda x: f"{x[0]}-{x[1]}")

    def result(x):
        # Check for diagonal cells first (before checking if PD is NaN)
        if x["Home"] == x["Away"]:
            return "N/A"
            
        if pd.isna(x["PD"]):
            return "To be played"
            
        result = None
        if x["PD"] > 0:
            result = "Home Win"
        elif x["PD"] < 0:
            result = "Away Win"
        elif x["PD"] == 0:
            return "Draw"

        if abs(x["PD"]) < 8:
            result += " (LBP)"

        return result

    # Get all teams in this league
    teams = list(set(df_results["Home"].unique()) | set(df_results["Away"].unique()))
    
    # Calculate points difference for each team BEFORE filling missing combinations
    pd_data = []
    for team in teams:
        home_games = df_results[(df_results["Home"] == team) & (~df_results["PD"].isna())]
        away_games = df_results[(df_results["Away"] == team) & (~df_results["PD"].isna())]
        
        home_pd = home_games["PD"].sum()
        away_pd = -away_games["PD"].sum()  # Flip sign for away games
        total_pd = home_pd + away_pd
        
        pd_data.append([team, total_pd])
        
    pd_df = (
        pd.DataFrame(pd_data, columns=["Team", "PD"])
        .sort_values("PD", ascending=False)
        .reset_index(drop=True)
        .reset_index()
        .rename(columns={"index": "Rank"})
    )
    
    # Fill in missing combinations of teams (create complete matrix)
    all_combinations = pd.MultiIndex.from_product([teams, teams], names=["Home", "Away"])
    df_results = df_results.set_index(["Home", "Away"]).reindex(all_combinations).reset_index()
    
    df_results["Result"] = df_results.apply(result, axis=1)
    df_results["color_R"] = df_results.apply(
        lambda x: "black" if x["Home"] == x["Away"] 
        else "#146f14" if x["Result"] == "Home Win" 
        else "#991515" if x["Result"] == "Away Win" 
        else "gray" if x["Result"] == "Draw" 
        else "white", axis=1
    )
    
    df_results["score"] = df_results["score"].fillna("")
    df_results["PF"] = df_results["PF"].fillna("")
    df_results["PA"] = df_results["PA"].fillna("")

    # Try to use league table order if available
    if table_order:
        # Season is in format "2025-2026", table file uses same format
        table_file = project_root / "Charts" / "league" / f"table_{squad_number}s_{season}.html"
        if table_file.exists():
            try:
                table_df = pd.read_html(str(table_file))[0]
                teams = table_df["TEAM"].tolist()
            except:
                teams = pd_df["Team"].tolist()
        else:
            teams = pd_df["Team"].tolist()
    else:
        teams = pd_df["Team"].tolist()

    # Color scale
    color_scale = alt.Scale(
        domain=['Home Win', 'Home Win (LBP)', 'Away Win', 'Away Win (LBP)', 'Draw', 'To be played', 'N/A'],
        range=['#146f14', '#146f14a0', '#991515', '#991515a0', 'goldenrod', 'white', 'black']
    )

    # Highlight selection
    highlight = alt.selection_point(on='click', fields=['Home', 'Away'], empty='none', nearest=True, value=None)
    predicate = f"datum.Home == {highlight.name}['Home'] | datum.Away == {highlight.name}['Home']"
    text_color = alt.condition(f"{predicate} | !isValid({highlight.name}['Home'])", alt.value('white'), alt.value('black'))

    # Heatmap
    heatmap = alt.Chart(df_results).mark_rect().encode(
        x=alt.X('Away:N', title="Away Team", sort=teams[::-1],
               axis=alt.Axis(ticks=False, domain=False, labelAngle=30, orient="top", titleFontSize=32)),
        y=alt.Y('Home:N', title="Home Team", sort=teams,
               axis=alt.Axis(ticks=False, domain=False, labelAngle=0, labelFontSize=14, titleFontSize=32, labelFontWeight="bold")),
        tooltip=['Home:N', 'Away:N', alt.Tooltip('score:N', title="Score"), alt.Tooltip('date:T', title="Date", format="%d %b %Y")],
        opacity=alt.condition(f"{predicate} | !isValid({highlight.name}['Home'])", alt.value(1.0), alt.value(0.2)),
        color=alt.Color('Result:N', scale=color_scale, title="Result", 
                       legend=alt.Legend(orient="none", direction="horizontal", titleOrient="left",
                                       legendX=50, legendY=430, symbolStrokeColor="black", symbolStrokeWidth=1,
                                       values=['Home Win', 'Away Win', 'Draw', 'To be played'])),
    ).properties(width=alt.Step(50), height=alt.Step(35))

    # Text annotations for scores
    textH = alt.Chart(df_results).mark_text(size=15, xOffset=-10, yOffset=5, fontWeight="bold").encode(
        x=alt.X('Away:N', title=None, sort=teams[::-1], axis=alt.Axis(ticks=False, domain=False, labels=False)),
        y=alt.Y('Home:N', title=None, sort=teams, axis=alt.Axis(ticks=False, domain=False, labels=False)),
        text=alt.Text('PF:N'), color=text_color,
        opacity=alt.condition(f"{predicate} | !isValid({highlight.name}['Home'])", alt.value(1.0), alt.value(0.5)),
    )
    
    textA = alt.Chart(df_results).mark_text(size=14, xOffset=10, yOffset=-5, fontStyle="italic").encode(
        x=alt.X('Away:N', title=None, sort=teams[::-1], axis=alt.Axis(ticks=False, domain=False, labels=False)),
        y=alt.Y('Home:N', title=None, sort=teams, axis=alt.Axis(ticks=False, domain=False, labels=False)),
        text=alt.Text('PA:N'), color=text_color,
        opacity=alt.condition(f"{predicate} | !isValid({highlight.name}['Home'])", alt.value(0.8), alt.value(0.4)),
    )

    # Points difference on diagonal
    textPD = alt.Chart(pd_df).mark_text(size=16, color="white", fontWeight="bold").encode(
        x=alt.X('Team:N', title=None, sort=teams[::-1], axis=alt.Axis(ticks=False, domain=False, labels=False)),
        y=alt.Y('Team:N', title=None, sort=teams, axis=alt.Axis(ticks=False, domain=False, labels=False)),
        text=alt.Text('PD:N', format="+d"),
        tooltip=[alt.Tooltip('Team:N', title="Team"), alt.Tooltip('PD:Q', title="Points Difference", format="+d")]
    )

    # Final chart
    season_short = season.replace('-20', '/')  # Convert 2025-2026 to 2025/26
    league_name = divisions.get(squad_number, {}).get(season_short, f"Squad {squad_number}")
    
    final_chart = (
        (heatmap + textA + textH + textPD)
        .add_params(highlight)
        .resolve_scale(color="independent", x="independent", y="independent", opacity="independent")
        .properties(
            title=alt.Title(
                text=f"{league_name} Results", 
                subtitle=[
                    "Diagonal shows total points difference for each team.",
                    "Lighter shaded results were within 7 points (losing bonus point).",
                    "Click on a cell to highlight all of the home team's results. (Double click to reset)",
                ],
            ),
            background="#f2f1f4"
        )
    )
    
    output_dir = project_root / "Charts" / "league"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"results_{squad_number}s_{season}.html"
    final_chart.save(str(filename), embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False}})
    hack_params_css(str(filename), params=False)
    
    logging.info(f"Saved squad {squad_number} results chart to {filename}")
    return final_chart


def patch_combined_results_html(file_path, squad):
    """Inject runtime season filtering and title updates into combined results HTML."""
    with open(file_path, "r", encoding="utf-8") as file_handle:
        soup = BeautifulSoup(file_handle, "html.parser")

    script_tags = soup.find_all("script")
    if not script_tags:
        return

    runtime_script = script_tags[-1]
    script_content = runtime_script.string or ""

    start_marker = "/* league_results_runtime_start */"
    end_marker = "/* league_results_runtime_end */"
    if start_marker in script_content and end_marker in script_content:
        before_marker = script_content.split(start_marker)[0]
        after_marker = script_content.split(end_marker)[-1]
        script_content = f"{before_marker}{after_marker}"

    squad_label = f"{squad}st XV" if squad == 1 else f"{squad}nd XV"

    runtime_injection = f"""

            {start_marker}
            const queryParams = new URLSearchParams(window.location.search);
            const selectedSeason = queryParams.get('season');

            const ensureTightLayout = () => {{
                if (document.getElementById('league-results-tight-layout')) {{
                    return;
                }}

                const styleEl = document.createElement('style');
                styleEl.id = 'league-results-tight-layout';
                styleEl.textContent = `
                    html, body {{
                        margin: 0 !important;
                        padding: 0 !important;
                        overflow: hidden !important;
                        height: auto !important;
                        min-height: 0 !important;
                    }}

                    #vis, #vis.vega-embed, .vega-embed {{
                        height: auto !important;
                        min-height: 0 !important;
                    }}
                `;

                document.head.appendChild(styleEl);
            }};

            const trimBodyToVis = () => {{
                const visEl = document.getElementById('vis');
                if (!visEl) {{
                    return;
                }}

                const visRect = visEl.getBoundingClientRect();
                const visHeight = Math.ceil(visRect.height || 0);
                if (visHeight <= 0) {{
                    return;
                }}

                const targetHeight = visHeight + 4;
                document.body.style.height = `${{targetHeight}}px`;
                document.documentElement.style.height = `${{targetHeight}}px`;
                document.body.style.overflow = 'hidden';
                document.documentElement.style.overflow = 'hidden';
            }};

            const formatSeasonLabel = (seasonValue) => {{
                if (!seasonValue || !seasonValue.includes('-')) {{
                    return seasonValue;
                }}

                const [startYear, endYear] = seasonValue.split('-');
                return `${{startYear}}/${{String(endYear).slice(-2)}}`;
            }};

            const applySeasonFilter = (targetSpec, seasonValue) => {{
                const seasonFilter = `datum.Season == '${{seasonValue}}' || datum.season == '${{seasonValue}}'`;

                if (Array.isArray(targetSpec.layer)) {{
                    targetSpec.layer.forEach((layer) => {{
                        layer.transform = layer.transform || [];
                        layer.transform = layer.transform.filter((transform) => {{
                            if (!transform || !transform.filter) {{
                                return true;
                            }}
                            if (typeof transform.filter === 'object' && transform.filter.param) {{
                                return false;
                            }}
                            if (typeof transform.filter === 'string' && transform.filter.includes('datum.Season')) {{
                                return false;
                            }}
                            return true;
                        }});
                        layer.transform.push({{ filter: seasonFilter }});
                    }});
                    return;
                }}

                targetSpec.transform = targetSpec.transform || [];
                targetSpec.transform = targetSpec.transform.filter((transform) => {{
                    if (!transform || !transform.filter) {{
                        return true;
                    }}
                    if (typeof transform.filter === 'object' && transform.filter.param) {{
                        return false;
                    }}
                    if (typeof transform.filter === 'string' && transform.filter.includes('datum.Season')) {{
                        return false;
                    }}
                    return true;
                }});
                targetSpec.transform.push({{ filter: seasonFilter }});
            }};

            if (selectedSeason) {{
                applySeasonFilter(spec, selectedSeason);

                const seasonLabel = formatSeasonLabel(selectedSeason);
                if (spec.title && seasonLabel) {{
                    spec.title.text = '{squad_label} League Results ' + seasonLabel;
                }}
            }}

            ensureTightLayout();
            [120, 350, 800, 1400, 2200].forEach((delay) => {{
                window.setTimeout(trimBodyToVis, delay);
            }});
            {end_marker}
    """

    insertion_anchor = "const el = document.getElementById('vis');"
    if insertion_anchor in script_content:
        runtime_script.string = script_content.replace(insertion_anchor, f"{runtime_injection}\n\n      {insertion_anchor}")
    else:
        runtime_script.string = script_content + runtime_injection

    with open(file_path, "w", encoding="utf-8") as file_handle:
        file_handle.write(str(soup))


def patch_combined_squad_analysis_html(file_path):
    """Inject runtime season filtering and layout tightening into combined squad analysis HTML."""
    with open(file_path, "r", encoding="utf-8") as file_handle:
        soup = BeautifulSoup(file_handle, "html.parser")

    script_tags = soup.find_all("script")
    if not script_tags:
        return

    runtime_script = script_tags[-1]
    script_content = runtime_script.string or ""

    start_marker = "/* league_analysis_runtime_start */"
    end_marker = "/* league_analysis_runtime_end */"
    if start_marker in script_content and end_marker in script_content:
        before_marker = script_content.split(start_marker)[0]
        after_marker = script_content.split(end_marker)[-1]
        script_content = f"{before_marker}{after_marker}"

    runtime_injection = f"""

            {start_marker}
            const queryParams = new URLSearchParams(window.location.search);
            const selectedSeason = queryParams.get('season');

            const ensureTightLayout = () => {{
                if (document.getElementById('league-analysis-tight-layout')) {{
                    return;
                }}

                const styleEl = document.createElement('style');
                styleEl.id = 'league-analysis-tight-layout';
                styleEl.textContent = `
                    html, body {{
                        margin: 0 !important;
                        padding: 0 !important;
                        overflow: hidden !important;
                        height: auto !important;
                        min-height: 0 !important;
                    }}

                    #vis, #vis.vega-embed, .vega-embed {{
                        height: auto !important;
                        min-height: 0 !important;
                    }}
                `;

                document.head.appendChild(styleEl);
            }};

            const trimBodyToVis = () => {{
                const visEl = document.getElementById('vis');
                if (!visEl) {{
                    return;
                }}

                const visRect = visEl.getBoundingClientRect();
                const visHeight = Math.ceil(visRect.height || 0);
                if (visHeight <= 0) {{
                    return;
                }}

                const targetHeight = visHeight + 4;
                document.body.style.height = `${{targetHeight}}px`;
                document.documentElement.style.height = `${{targetHeight}}px`;
                document.body.style.overflow = 'hidden';
                document.documentElement.style.overflow = 'hidden';
            }};

            const findSeasonParam = (targetSpec) => {{
                if (!targetSpec || !Array.isArray(targetSpec.params)) {{
                    return null;
                }}

                return targetSpec.params.find((paramDef) =>
                    paramDef
                    && paramDef.bind
                    && typeof paramDef.bind.name === 'string'
                    && paramDef.bind.name.toLowerCase().includes('season')
                ) || null;
            }};

            if (selectedSeason) {{
                const seasonParam = findSeasonParam(spec);
                if (seasonParam) {{
                    seasonParam.value = {{ Season: selectedSeason }};
                    delete seasonParam.bind;
                }}
            }}

            ensureTightLayout();
            [120, 350, 800, 1400, 2200].forEach((delay) => {{
                window.setTimeout(trimBodyToVis, delay);
            }});
            {end_marker}
    """

    insertion_anchor = "const el = document.getElementById('vis');"
    if insertion_anchor in script_content:
        runtime_script.string = script_content.replace(insertion_anchor, f"{runtime_injection}\n\n      {insertion_anchor}")
    else:
        runtime_script.string = script_content + runtime_injection

    with open(file_path, "w", encoding="utf-8") as file_handle:
        file_handle.write(str(soup))

def create_combined_results_chart(squad=1):
    """Create a combined results chart for all available seasons."""
    
    # Load match data
    _, matches_json = load_match_data()
    
    # Find all seasons for this squad
    squad_seasons = []
    for match in matches_json:
        match_squad = squad_lookup(match["season"], match["league"])
        if match_squad == squad and match["season"] not in squad_seasons:
            squad_seasons.append(match["season"])
    
    squad_seasons = sorted(squad_seasons)
    
    if not squad_seasons:
        logging.warning(f"No seasons found for squad {squad}")
        return None
    
    logging.info(f"Creating combined results chart for squad {squad} with {len(squad_seasons)} seasons")
    
    # Combine all results data from all seasons
    all_results = []
    all_pd_data = []
    
    for season in squad_seasons:
        squad_matches = []
        for match in matches_json:
            match_squad = squad_lookup(match["season"], match["league"])
            if match_squad == squad and match["season"] == season:
                squad_matches.append(match)
        
        if not squad_matches:
            continue
        
        # Create results dataframe for this season
        df_results = pd.DataFrame(squad_matches)
        df_results = df_results[["season", "league", "date", "teams", "score"]]
        
        df_results["Home"] = df_results["teams"].apply(lambda x: x[0])
        df_results["Away"] = df_results["teams"].apply(lambda x: x[1])
        df_results["PF"] = df_results["score"].apply(lambda x: x[0] if x[0] is not None else None)
        df_results["PA"] = df_results["score"].apply(lambda x: x[1] if x[1] is not None else None)
        df_results["PD"] = df_results["PF"] - df_results["PA"]
        df_results["score_str"] = df_results["score"].apply(lambda x: f"{x[0]}-{x[1]}" if x[0] is not None and x[1] is not None else "")
        
        # Get all teams in this league/season
        teams = list(set(df_results["Home"].unique()) | set(df_results["Away"].unique()))
        
        # Calculate points difference for each team
        for team in teams:
            home_games = df_results[(df_results["Home"] == team) & (~df_results["PD"].isna())]
            away_games = df_results[(df_results["Away"] == team) & (~df_results["PD"].isna())]
            
            home_pd = home_games["PD"].sum()
            away_pd = -away_games["PD"].sum()
            total_pd = home_pd + away_pd
            
            all_pd_data.append({"Season": season, "Team": team, "PD": total_pd})
        
        # Fill in missing combinations
        all_combinations = pd.MultiIndex.from_product([teams, teams], names=["Home", "Away"])
        df_season = df_results.drop_duplicates(subset=["Home", "Away"]).set_index(["Home", "Away"]).reindex(all_combinations).reset_index()
        df_season["Season"] = season
        
        # Preserve score data from original df_results
        if "score_str" not in df_season.columns:
            df_season["score_str"] = ""
        if "PF" not in df_season.columns:
            df_season["PF"] = ""
        if "PA" not in df_season.columns:
            df_season["PA"] = ""
        if "PD" not in df_season.columns:
            df_season["PD"] = None
        if "date" not in df_season.columns:
            df_season["date"] = None
            
        df_season["score_str"] = df_season["score_str"].fillna("")
        df_season["PF"] = df_season["PF"].fillna("")
        df_season["PA"] = df_season["PA"].fillna("")
        
        all_results.append(df_season)
    
    # Combine all seasons
    combined_df = pd.concat(all_results, ignore_index=True)
    pd_df = pd.DataFrame(all_pd_data)
    
    def result(x):
        if x["Home"] == x["Away"]:
            return "N/A"
        if pd.isna(x["PD"]):
            return "To be played"
        
        result = None
        if x["PD"] > 0:
            result = "Home Win"
        elif x["PD"] < 0:
            result = "Away Win"
        elif x["PD"] == 0:
            return "Draw"
        
        if abs(x["PD"]) < 8:
            result += " (LBP)"
        
        return result
    
    combined_df["Result"] = combined_df.apply(result, axis=1)
    
    # Color scale
    color_scale = alt.Scale(
        domain=['Home Win', 'Home Win (LBP)', 'Away Win', 'Away Win (LBP)', 'Draw', 'To be played', 'N/A'],
        range=['#146f14', '#146f14a0', '#991515', '#991515a0', 'goldenrod', 'white', 'black']
    )
    
    # Highlight selection
    highlight = alt.selection_point(on='click', fields=['Home', 'Away'], empty='none', nearest=True, value=None)
    predicate = f"datum.Home == {highlight.name}['Home'] | datum.Away == {highlight.name}['Home']"
    text_color = alt.condition(f"{predicate} | !isValid({highlight.name}['Home'])", alt.value('white'), alt.value('black'))
    
    # Add PD data to combined_df for sorting (rename to avoid conflicts)
    pd_df_home = pd_df[['Season', 'Team', 'PD']].rename(columns={'Team': 'Home', 'PD': 'Home_PD'})
    pd_df_away = pd_df[['Season', 'Team', 'PD']].rename(columns={'Team': 'Away', 'PD': 'Away_PD'})
    combined_df = combined_df.merge(pd_df_home, on=['Season', 'Home'], how='left')
    combined_df = combined_df.merge(pd_df_away, on=['Season', 'Away'], how='left')
    
    # Heatmap - sorted by points difference (descending)
    heatmap = alt.Chart(combined_df).mark_rect().encode(
        x=alt.X('Away:N', title="Away Team", sort=alt.EncodingSortField(field='Away_PD', op='max', order='ascending'),
               axis=alt.Axis(ticks=False, domain=False, labelAngle=30, orient="top", titleFontSize=32)),
        y=alt.Y('Home:N', title="Home Team", sort=alt.EncodingSortField(field='Home_PD', op='max', order='descending'),
               axis=alt.Axis(ticks=False, domain=False, labelAngle=0, labelFontSize=14, titleFontSize=32, labelFontWeight="bold")),
        tooltip=['Home:N', 'Away:N', alt.Tooltip('score_str:N', title="Score"), alt.Tooltip('date:T', title="Date", format="%d %b %Y")],
        opacity=alt.condition(f"{predicate} | !isValid({highlight.name}['Home'])", alt.value(1.0), alt.value(0.2)),
        color=alt.Color('Result:N', scale=color_scale, title="Result",
                       legend=alt.Legend(orient="none", direction="horizontal", titleOrient="left",
                                       legendX=50, legendY=430, symbolStrokeColor="black", symbolStrokeWidth=1,
                                       values=['Home Win', 'Away Win', 'Draw', 'To be played'])),
    ).properties(width=alt.Step(50), height=alt.Step(35))
    
    # Text annotations
    textH = alt.Chart(combined_df).mark_text(size=15, xOffset=-10, yOffset=5, fontWeight="bold").encode(
        x=alt.X('Away:N', title=None, sort=alt.EncodingSortField(field='Away_PD', op='max', order='ascending'),
                axis=alt.Axis(ticks=False, domain=False, labels=False)),
        y=alt.Y('Home:N', title=None, sort=alt.EncodingSortField(field='Home_PD', op='max', order='descending'),
                axis=alt.Axis(ticks=False, domain=False, labels=False)),
        text=alt.Text('PF:N'), color=text_color,
        opacity=alt.condition(f"{predicate} | !isValid({highlight.name}['Home'])", alt.value(1.0), alt.value(0.5)),
    )
    
    textA = alt.Chart(combined_df).mark_text(size=14, xOffset=10, yOffset=-5, fontStyle="italic").encode(
        x=alt.X('Away:N', title=None, sort=alt.EncodingSortField(field='Away_PD', op='max', order='ascending'),
                axis=alt.Axis(ticks=False, domain=False, labels=False)),
        y=alt.Y('Home:N', title=None, sort=alt.EncodingSortField(field='Home_PD', op='max', order='descending'),
                axis=alt.Axis(ticks=False, domain=False, labels=False)),
        text=alt.Text('PA:N'), color=text_color,
        opacity=alt.condition(f"{predicate} | !isValid({highlight.name}['Home'])", alt.value(0.8), alt.value(0.4)),
    )
    
    # Add PD for sorting to pd_df
    pd_df['Team_PD'] = pd_df['PD']
    
    # Points difference on diagonal
    textPD = alt.Chart(pd_df).mark_text(size=16, color="white", fontWeight="bold").encode(
        x=alt.X('Team:N', title=None, sort=alt.EncodingSortField(field='Team_PD', op='max', order='ascending'),
                axis=alt.Axis(ticks=False, domain=False, labels=False)),
        y=alt.Y('Team:N', title=None, sort=alt.EncodingSortField(field='Team_PD', op='max', order='descending'),
                axis=alt.Axis(ticks=False, domain=False, labels=False)),
        text=alt.Text('PD:N', format="+d"),
        tooltip=[alt.Tooltip('Team:N', title="Team"), alt.Tooltip('PD:Q', title="Points Difference", format="+d")]
    )
    
    # Final chart
    squad_label = f"{squad}st XV" if squad == 1 else f"{squad}nd XV"
    
    final_chart = (
        (heatmap + textA + textH + textPD)
        .add_params(highlight)
        .resolve_scale(color="independent", x="independent", y="independent", opacity="independent")
        .properties(
            title=alt.Title(
                text=f"{squad_label} League Results",
                subtitle=[
                    "Diagonal shows total points difference for each team.",
                    "Lighter shaded results were within 7 points (losing bonus point).",
                    "Click on a cell to highlight all of the home team's results. (Double click to reset)",
                ],
            ),
            padding={"left": 20, "top": 20, "right": 50, "bottom": 20}
        )
    )
    
    # Save chart
    output_dir = project_root / "Charts" / "league"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"results_{squad}s_combined.html"
    final_chart.save(str(filename), embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False}})
    hack_params_css(str(filename), params=False)
    patch_combined_results_html(str(filename), squad)
    
    logging.info(f"Saved combined results chart for squad {squad} to {filename}")
    return final_chart


def _season_dash_to_slash_short(season_dash):
    """Convert season format from YYYY-YYYY to YYYY/YY."""
    if not season_dash or "-" not in season_dash:
        return season_dash

    start_year, end_year = season_dash.split("-", 1)
    return f"{start_year}/{end_year[-2:]}"


def _load_combined_league_table_data(squad):
    """Load all available league table files for a squad keyed by YYYY-YYYY season."""
    table_data = {}
    csv_pattern = f"league_table_*_squad_{squad}.csv"

    for csv_file in sorted((project_root / "data").glob(csv_pattern)):
        stem = csv_file.stem
        season_token = stem.replace(f"_squad_{squad}", "").replace("league_table_", "")
        season_parts = season_token.split("_")
        if len(season_parts) != 2:
            continue

        start_year = season_parts[0]
        end_short = season_parts[1]
        end_year = f"20{end_short}"
        season_dash = f"{start_year}-{end_year}"

        try:
            table_df = pd.read_csv(csv_file)
        except Exception as exc:
            logging.warning(f"Could not read league table CSV {csv_file}: {exc}")
            continue

        table_data[season_dash] = {
            "league": divisions.get(squad, {}).get(_season_dash_to_slash_short(season_dash), f"Squad {squad}"),
            "columns": table_df.columns.tolist(),
            "rows": table_df.to_dict(orient="records"),
        }

    if table_data:
        return table_data

    html_pattern = f"table_{squad}s_*.html"
    for html_file in sorted((project_root / "Charts" / "league").glob(html_pattern)):
        if html_file.name.endswith("_combined.html"):
            continue

        season_dash = html_file.stem.replace(f"table_{squad}s_", "")
        if not season_dash or "-" not in season_dash:
            continue

        try:
            table_df = pd.read_html(str(html_file))[0]
        except Exception as exc:
            logging.warning(f"Could not read league table HTML {html_file}: {exc}")
            continue

        table_data[season_dash] = {
            "league": divisions.get(squad, {}).get(_season_dash_to_slash_short(season_dash), f"Squad {squad}"),
            "columns": table_df.columns.tolist(),
            "rows": table_df.to_dict(orient="records"),
        }

    return table_data


def create_combined_league_table_html(squad=1):
    """Create a combined HTML league table and filter it using ?season=YYYY-YYYY."""
    table_data = _load_combined_league_table_data(squad)
    if not table_data:
        logging.warning(f"No league table data found for squad {squad}")
        return None

    sorted_seasons = sorted(table_data.keys())
    default_season = sorted_seasons[-1]
    squad_label = f"{squad}st XV" if squad == 1 else f"{squad}nd XV"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{squad_label} League Table</title>
    <link href=\"../../css/variables.css\" rel=\"stylesheet\" />
    <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css\" rel=\"stylesheet\" />
    <link href=\"https://fonts.googleapis.com/css?family=PT+Sans+Narrow:400,700\" rel=\"stylesheet\" />
    <link href=\"https://fonts.googleapis.com/css?family=Lato:100,300,400,700,900\" rel=\"stylesheet\" />
    <style>
        body {{
            margin: 0;
            background: #f2f1f4;
            font-family: Lato, sans-serif;
            color: #202946;
        }}

        .table-wrap {{
            padding: 12px 16px;
            background: #ffffff;
        }}

        .table-title {{
            margin: 0 0 10px 0;
            font-family: 'PT Sans Narrow', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 32px;
            font-weight: 700;
            color: #202946;
        }}

        table.league-table {{
            --bs-table-bg: #ffffff;
            --bs-table-color: #202946;
            --bs-table-striped-bg: #f2f1f4;
            --bs-table-striped-color: #202946;
            --bs-table-accent-bg: transparent;
            border-collapse: separate;
            border-spacing: 0;
        }}

        thead th {{
            background: var(--primary-color, #202946);
            color: #f2f1f4;
            font-family: 'PT Sans Narrow', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 1rem;
            white-space: nowrap;
            border: none !important;
            border-bottom: 2px solid var(--primary-color, #202946) !important;
        }}

        tbody td {{
            white-space: nowrap;
            font-size: 0.9rem;
            border: none !important;
        }}

        table.league-table tbody tr:nth-child(even) {{
            background: #f2f1f4 !important;
        }}

        tbody.table-group-divider {{
            border-top: none !important;
        }}

        tbody.table-group-divider tr:first-child td {{
            border-top: 2px solid var(--primary-color, #202946) !important;
        }}

        .team-col {{
            text-align: left !important;
            font-weight: 700;
        }}

        tbody tr.eg-row,
        tbody tr.eg-row td {{
            background: #7d96e8 !important;
            color: #ffffff;
            font-weight: 700;
        }}

        .empty {{
            border: 1px solid #e5e4e7;
            padding: 14px;
            background: #fff;
            color: #202946;
        }}
    </style>
</head>
<body>
    <div class=\"table-wrap\">
        <h2 id=\"tableTitle\" class=\"table-title\">{squad_label} League Table</h2>
        <div id=\"tableRoot\"></div>
    </div>

    <script>
        const tableDataBySeason = {json.dumps(table_data)};
        const defaultSeason = {json.dumps(default_season)};

        const queryParams = new URLSearchParams(window.location.search);
        const selectedSeason = queryParams.get('season');
        const activeSeason = selectedSeason && tableDataBySeason[selectedSeason] ? selectedSeason : defaultSeason;

        const seasonLabel = (seasonValue) => {{
            if (!seasonValue || !seasonValue.includes('-')) return seasonValue;
            const [startYear, endYear] = seasonValue.split('-');
            return `${{startYear}}/${{String(endYear).slice(-2)}}`;
        }};

        const tableRoot = document.getElementById('tableRoot');
        const tableTitle = document.getElementById('tableTitle');
        if (activeSeason) {{
            const leagueName = (tableDataBySeason[activeSeason] && tableDataBySeason[activeSeason].league)
                ? tableDataBySeason[activeSeason].league
                : '{squad_label} League';
            tableTitle.textContent = leagueName + ' Table ' + seasonLabel(activeSeason);
        }}

        const activeData = tableDataBySeason[activeSeason];

        if (!activeData || !Array.isArray(activeData.rows) || activeData.rows.length === 0) {{
            tableRoot.innerHTML = '<div class="empty">No league table data is available for this season.</div>';
        }} else {{
            const headers = activeData.columns
                .map((col) => {{
                    const thClass = col === 'TEAM' ? ' class="text-start"' : '';
                    return `<th${{thClass}}>${{col}}</th>`;
                }})
                .join('');

            const formatValue = (col, value) => {{
                if (value == null) return '';
                if (col === 'PD') {{
                    const numericValue = Number(value);
                    if (!Number.isNaN(numericValue) && numericValue > 0) {{
                        return `+${{numericValue}}`;
                    }}
                }}
                return value;
            }};

            const rows = activeData.rows
                .map((row) => {{
                    const teamName = String(row['TEAM'] || '');
                    const rowClass = teamName.includes('East Grinstead') ? ' class="eg-row"' : '';
                    const cells = activeData.columns
                        .map((col) => {{
                            const cellClass = col === 'TEAM' ? ' class="team-col"' : '';
                            return `<td${{cellClass}}>${{formatValue(col, row[col])}}</td>`;
                        }})
                        .join('');
                    return `<tr${{rowClass}}>${{cells}}</tr>`;
                }})
                .join('');

            tableRoot.innerHTML = `<table class="table table-borderless table-striped table-sm align-middle mb-0 league-table"><thead><tr>${{headers}}</tr></thead><tbody class="table-group-divider">${{rows}}</tbody></table>`;
        }}
    </script>
</body>
</html>
"""

    output_dir = project_root / "Charts" / "league"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"table_{squad}s_combined.html"

    with open(output_file, "w", encoding="utf-8") as file_handle:
        file_handle.write(html_content)

    logging.info(f"Saved combined league table HTML for squad {squad} to {output_file}")
    return output_file

def create_combined_league_charts(squad=1):
    """Create combined league charts for all available seasons for a given squad."""
    
    # Load all data
    df_summary, matches_json = load_match_data()
    df_players = prepare_player_data(matches_json)
    
    if df_players.empty:
        logging.error("No player data available")
        return None
    
    # Filter for this squad
    squad_df = df_players[df_players["Squad"] == squad].copy()
    
    if squad_df.empty:
        logging.error(f"No data found for squad {squad}")
        return None
    
    # Get available seasons for this squad
    available_seasons = sorted(squad_df["Season"].unique())
    
    if not available_seasons:
        logging.error(f"No seasons found for squad {squad}")
        return None
    
    logging.info(f"Creating combined charts for squad {squad} with {len(available_seasons)} seasons")
    
    # Add unit classification
    squad_df["Unit"] = squad_df["Position"].apply(classify_unit)
    
    # Prepare all data for charts
    
    players_per_team = (
        squad_df.groupby(["Season", "Team", "Color1", "Color2", "Player"])["Unit"]
        .agg(lambda x: "Forwards" if "Forwards" in x.values else "Backs" if "Backs" in x.values else "Bench")
        .reset_index()
        .groupby(["Season", "Team", "Color1", "Color2", "Unit"])
        .size()
        .reset_index()
        .rename(columns={0: "Total Players"})
    )

    total_players_per_team = squad_df.groupby(["Season", "Team", "Color1", "Color2"])["Player"].nunique().reset_index()
    total_players_per_team.columns = ["Season", "Team", "Color1", "Color2", "Total Players"]
    total_players_per_team["Unit"] = "Total"

    players_per_team = pd.concat([players_per_team, total_players_per_team], ignore_index=True)

    # Retention data
    retention_data = []
    for (team, season), matches in squad_df.sort_values("Date", ascending=True).groupby(["Team", "Season"]):
        prev_squad = set()
        prev_forwards = set()
        prev_backs = set()
        
        for match_id, match in matches.groupby("Match ID"):
            current_squad = set(match[match["Unit"] != "Bench"]["Player"])
            forwards = set(match[match["Unit"] == "Forwards"]["Player"])
            backs = set(match[match["Unit"] == "Backs"]["Player"])
            
            # Find opposition team - get all teams in this match that aren't the current team
            all_teams_in_match = squad_df[squad_df["Match ID"] == match_id]["Team"].unique()
            opposition = [t for t in all_teams_in_match if t != team]
            opposition_name = opposition[0] if opposition else "Unknown"
            
            if prev_squad:
                retained = len(current_squad & prev_squad)
                retained_forwards = len(forwards & prev_forwards)
                retained_backs = len(backs & prev_backs)
            else:
                retained = None
                retained_forwards = None
                retained_backs = None

            retention_data.append({
                "Match ID": match_id,
                "Season": season,
                "Date": match["Date"].iloc[0],
                "Team": team,
                "Opposition": opposition_name,
                "Players Retained": retained,
                "Forwards Retained": retained_forwards,
                "Backs Retained": retained_backs,
                "Color1": match["Color1"].iloc[0],
                "Color2": match["Color2"].iloc[0]
            })
            
            prev_squad = current_squad
            prev_forwards = forwards
            prev_backs = backs

    retention_df = pd.DataFrame(retention_data).dropna()

    # Average squad retention per team
    average_retention = (
        retention_df
        .groupby(["Season", "Team", "Color1", "Color2"])
        .agg({"Players Retained": "mean", "Forwards Retained": "mean", "Backs Retained": "mean"})
        .reset_index()
        .melt(["Season", "Team", "Color1", "Color2"], var_name="Unit", value_name="Average Retention")
    )
    average_retention["Unit"] = average_retention["Unit"].str.replace(" Retained", "").replace("Players", "Total")
    # Sort so East Grinstead appears last (plotted on top)
    average_retention = average_retention.sort_values('Team', key=lambda x: x == 'East Grinstead')

    # Create interactive selectors
    # Unit selection (Total/Forwards/Backs)
    unit_radio = alt.binding_radio(
        options=["Total", "Forwards", "Backs"], 
        name="Unit"
    )
    unit_select = alt.selection_point(fields=["Unit"], bind=unit_radio, value="Total")

    # Season selection - default to most recent season
    season_options = sorted(squad_df["Season"].unique().tolist())
    season_labels = [f"{s[:4]}/{s[7:]}" for s in sorted(squad_df["Season"].unique())]
    season_radio = alt.binding_radio(
        options=season_options, 
        name="Season", 
        labels=season_labels
    )
    default_season = sorted(squad_df["Season"].unique().tolist())[-1]
    season_select = alt.selection_point(fields=["Season"], bind=season_radio, value=default_season)

    # Create charts
    squad_label = f"{squad}st XV" if squad == 1 else f"{squad}nd XV"
    
    # Squad size chart with league average
    players_bars = (
        alt.Chart(players_per_team)
        .mark_bar(strokeWidth=2)
        .encode(
            x=alt.X("Total Players:Q", title="Total Players"),
            y=alt.Y("Team:N", sort="-x", title=None, axis=alt.Axis(labelPadding=10, labelLimit=200)),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Team", "Unit", "Total Players"],
        )
    )
    
    players_average = (
        alt.Chart(players_per_team)
        .mark_rule(color='gray', strokeDash=[5, 5], strokeWidth=2)
        .encode(
            x=alt.X("mean(Total Players):Q"),
            tooltip=[alt.Tooltip("mean(Total Players):Q", title="League Average", format=".1f")]
        )
    )
    
    players_per_team_chart = (
        (players_bars + players_average)
        .properties(
            title=alt.Title(
                text=f"Squad Size", 
                subtitle="Total players representing each team across the season."
            ),
            width=250, height=300
        )
        .add_params(season_select, unit_select)
        .transform_filter(season_select)
        .transform_filter(unit_select)
    )

    # Reshape retention data for unit selection
    retention_long = retention_df.melt(
        id_vars=["Match ID", "Season", "Date", "Team", "Opposition", "Color1", "Color2"],
        value_vars=["Players Retained", "Forwards Retained", "Backs Retained"],
        var_name="Unit",
        value_name="Retained"
    )
    retention_long["Unit"] = retention_long["Unit"].str.replace(" Retained", "").replace("Players", "Total")
    # Sort so East Grinstead appears last (plotted on top)
    retention_long = retention_long.sort_values('Team', key=lambda x: x == 'East Grinstead')

    retention_chart = (
        alt.Chart(retention_long)
        .mark_line(point={"size": 50})
        .encode(
            x=alt.X("Date:T", title="Match Date"),
            y=alt.Y(
                "Retained:Q", 
                title="Players Retained", 
            ),
            color=alt.Color("Color1:N", scale=None, legend=None),
            detail="Team:N",
            tooltip=[
                alt.Tooltip("Team:N", title="Team"),
                alt.Tooltip("Opposition:N", title="Opposition"),
                alt.Tooltip("Date:T", title="Date", format="%d %b %Y"),
                alt.Tooltip("Unit:N", title="Unit"),
                alt.Tooltip("Retained:Q", title="Players Retained")
            ],
        )
        .properties(
            title=alt.Title(
                text=f"Squad Retention by Game",
                subtitle="Number of players retained in the starting XV from the previous match.",
            ),
            width=900,
            height=400
        )
        .add_params(season_select, unit_select)
        .transform_filter(season_select)
        .transform_filter(unit_select)
    )

    # Average retention chart with league average
    retention_bars = (
        alt.Chart(average_retention)
        .mark_bar(strokeWidth=2)
        .encode(
            x=alt.X("Average Retention:Q", title="Average Players Retained"),
            y=alt.Y("Team:N", sort="-x", title=None, axis=alt.Axis(ticks=False, domain=False, labelPadding=10, labelLimit=200)),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Team", "Unit:N", alt.Tooltip("Average Retention:Q", format=".2f")],
        )
    )
    
    retention_average = (
        alt.Chart(average_retention)
        .mark_rule(color='gray', strokeDash=[5, 5], strokeWidth=2)
        .encode(
            x=alt.X("mean(Average Retention):Q"),
            tooltip=[alt.Tooltip("mean(Average Retention):Q", title="League Average", format=".2f")]
        )
    )
    
    average_retention_chart = (
        (retention_bars + retention_average)
        .properties(
            title=alt.Title(
                text=f"Squad Retention",
                subtitle="Average players retained from the starting XV."
            ), 
            width=250, height=300
        )
        .add_params(season_select, unit_select)
        .transform_filter(season_select)
        .transform_filter(unit_select)
    )

    # Create season-to-league mapping for info panel
    season_league_map = []
    for season in season_options:
        season_display = f"{season[:4]}/{season[7:]}"
        league = divisions.get(squad, {}).get(season_display, "Unknown League")
        season_league_map.append({
            "Season": season,
            "SeasonDisplay": season_display,
            "League": league,
            "Squad": squad_label,
            "Unit": "Total"  # Will be used for filtering
        })
    
    # Add unit options to data for dynamic title
    unit_data = []
    for item in season_league_map:
        for unit in ["Total", "Forwards", "Backs"]:
            unit_item = item.copy()
            unit_item["Unit"] = unit
            unit_data.append(unit_item)
    
    # Create info panel with three text rows
    info_data = pd.DataFrame(unit_data)
    
    # Background rectangle for the info panel
    info_bg = (
        alt.Chart(pd.DataFrame({'x': [0]}))
        .mark_rect(
            color=EG_ACCENT,
            stroke=EG_PRIMARY,
            strokeWidth=2,
            cornerRadius=4
        )
        .encode(
            x=alt.value(-50),
            y=alt.value(-50),
            x2=alt.value(150),
            y2=alt.value(400)
        )
    )
    
    # Squad label (always displays "1st XV" or "2nd XV")
    squad_text = (
        alt.Chart(info_data)
        .mark_text(
            align='left',
            baseline='bottom',
            fontSize=60,
            fontWeight='bold',
            font='PT Sans Narrow, Helvetica Neue, Helvetica, Arial, sans-serif',
            color=EG_PRIMARY,
            dx=-80,
            dy=10
        )
        .encode(text='Squad:N')
        .transform_filter(season_select)
        .transform_filter(unit_select)
    )
    
    # Unit label (displays "Squad", "Forwards", or "Backs")
    unit_text = (
        alt.Chart(info_data)
        .mark_text(
            align='left',
            baseline='bottom',
            fontSize=48,
            fontWeight='bold',
            font='PT Sans Narrow, Helvetica Neue, Helvetica, Arial, sans-serif',
            color=EG_PRIMARY,
            dx=-80,
            dy=50
        )
        .encode(text='UnitLabel:N')
        .transform_filter(season_select)
        .transform_filter(unit_select)
        .transform_calculate(
            UnitLabel="datum.Unit == 'Total' ? 'Squad' : datum.Unit"
        )
    )
    
    # Season label
    season_text = (
        alt.Chart(info_data)
        .mark_text(
            align='left',
            baseline='top',
            fontSize=32,
            font='PT Sans Narrow, Helvetica Neue, Helvetica, Arial, sans-serif',
            color=EG_PRIMARY,
            dx=-80,
            dy=80
        )
        .encode(text='SeasonDisplay:N')
        .transform_filter(season_select)
        .transform_filter(unit_select)
    )
    
    # League label
    league_text = (
        alt.Chart(info_data)
        .mark_text(
            align='left',
            baseline='top',
            fontSize=20,
            font='PT Sans Narrow, Helvetica Neue, Helvetica, Arial, sans-serif',
            color='white',
            dx=-80,
            dy=130
        )
        .encode(text='League:N')
        .transform_filter(season_select)
        .transform_filter(unit_select)
    )
    
    # Combine info panel elements
    info_panel = (info_bg + squad_text + unit_text + season_text + league_text).properties(
        width=100,
        height=100
    )
    
    # Create trend charts for squad size and retention over seasons
    # Merge squad size and retention data
    trend_data = players_per_team.merge(
        average_retention,
        on=["Season", "Team", "Color1", "Color2", "Unit"],
        how="inner"
    )
    
    # Calculate league statistics per season
    league_stats_size = (
        trend_data.groupby(["Season", "Unit"])["Total Players"]
        .agg(["min", "max", "mean"])
        .reset_index()
    )
    
    league_stats_retention = (
        trend_data.groupby(["Season", "Unit"])["Average Retention"]
        .agg(["min", "max", "mean"])
        .reset_index()
    )
    
    # East Grinstead data
    eg_data = trend_data[trend_data["Team"] == "East Grinstead"].copy()
    
    # Squad Size Over Time Chart
    # Min/Max range band
    size_band = (
        alt.Chart(league_stats_size)
        .mark_area(opacity=0.2, color="gray")
        .encode(
            x=alt.X("SeasonDisplay:N", title="Season"),
            y=alt.Y("min:Q", title="Squad Size"),
            y2=alt.Y2("max:Q"),
            tooltip=[
                alt.Tooltip("SeasonDisplay:N", title="Season"),
                alt.Tooltip("min:Q", title="League Min", format=".0f"),
                alt.Tooltip("max:Q", title="League Max", format=".0f"),
                alt.Tooltip("mean:Q", title="League Average", format=".1f")
            ]
        )
        .transform_calculate(
            SeasonDisplay="substring(datum.Season, 2, 4) + '/' + substring(datum.Season, 7, 9)"
        )
        .transform_filter(unit_select)
    )
    
    # League average line
    size_avg = (
        alt.Chart(league_stats_size)
        .mark_line(color="gray", strokeDash=[5, 5], strokeWidth=2)
        .encode(
            x=alt.X("SeasonDisplay:N"),
            y=alt.Y("mean:Q", axis=alt.Axis(orient="right")),
            tooltip=[
                alt.Tooltip("SeasonDisplay:N", title="Season"),
                alt.Tooltip("mean:Q", title="League Average", format=".1f")
            ]
        )
        .transform_calculate(
            SeasonDisplay="substring(datum.Season, 2, 4) + '/' + substring(datum.Season, 7, 9)"
        )
        .transform_filter(unit_select)
    )
    
    # East Grinstead line
    size_eg = (
        alt.Chart(eg_data)
        .mark_line(point={"size": 100}, strokeWidth=3)
        .encode(
            x=alt.X("SeasonDisplay:N"),
            y=alt.Y("Total Players:Q"),
            color=alt.Color("Color1:N", scale=None, legend=None),
            tooltip=[
                alt.Tooltip("SeasonDisplay:N", title="Season"),
                alt.Tooltip("Team:N", title="Team"),
                alt.Tooltip("Unit:N", title="Unit"),
                alt.Tooltip("Total Players:Q", title="Squad Size")
            ]
        )
        .transform_calculate(
            SeasonDisplay="substring(datum.Season, 2, 4) + '/' + substring(datum.Season, 7, 9)"
        )
        .transform_filter(unit_select)
    )
    
    squad_size_trend = (
        (size_band + size_avg + size_eg)
        .properties(
            title=alt.Title(
                text="by Season",
                subtitle="EG compared to league average/min/max"
            ),
            width=200,
            height=300
        )
        .add_params(unit_select)
        .transform_filter(unit_select)
    )
    
    # Squad Retention Over Time Chart
    # Min/Max range band
    retention_band = (
        alt.Chart(league_stats_retention)
        .mark_area(opacity=0.2, color="gray")
        .encode(
            x=alt.X("SeasonDisplay:N", title="Season"),
            y=alt.Y("min:Q", title="Average Retention"),
            y2=alt.Y2("max:Q"),
            tooltip=[
                alt.Tooltip("SeasonDisplay:N", title="Season"),
                alt.Tooltip("min:Q", title="League Min", format=".2f"),
                alt.Tooltip("max:Q", title="League Max", format=".2f"),
                alt.Tooltip("mean:Q", title="League Average", format=".2f")
            ]
        )
        .transform_calculate(
            SeasonDisplay="substring(datum.Season, 2, 4) + '/' + substring(datum.Season, 7, 9)"
        )
        .transform_filter(unit_select)
    )
    
    # League average line
    retention_avg = (
        alt.Chart(league_stats_retention)
        .mark_line(color="gray", strokeDash=[5, 5], strokeWidth=2)
        .encode(
            x=alt.X("SeasonDisplay:N"),
            y=alt.Y("mean:Q", axis=alt.Axis(orient="right")),
            tooltip=[
                alt.Tooltip("SeasonDisplay:N", title="Season"),
                alt.Tooltip("mean:Q", title="League Average", format=".2f")
            ]
        )
        .transform_calculate(
            SeasonDisplay="substring(datum.Season, 2, 4) + '/' + substring(datum.Season, 7, 9)"
        )
        .transform_filter(unit_select)
    )
    
    # East Grinstead line
    retention_eg = (
        alt.Chart(eg_data)
        .mark_line(point={"size": 100}, strokeWidth=3)
        .encode(
            x=alt.X("SeasonDisplay:N"),
            y=alt.Y("Average Retention:Q"),
            color=alt.Color("Color1:N", scale=None, legend=None),
            tooltip=[
                alt.Tooltip("SeasonDisplay:N", title="Season"),
                alt.Tooltip("Team:N", title="Team"),
                alt.Tooltip("Unit:N", title="Unit"),
                alt.Tooltip("Average Retention:Q", title="Avg Retention", format=".2f")
            ]
        )
        .transform_calculate(
            SeasonDisplay="substring(datum.Season, 2, 4) + '/' + substring(datum.Season, 7, 9)"
        )
        .transform_filter(unit_select)
    )
    
    squad_retention_trend = (
        (retention_band + retention_avg + retention_eg)
        .properties(
            title=alt.Title(
                text="by Season",
                subtitle="EG compared to league average/min/max"
            ),
            width=200,
            height=300
        )
        .add_params(unit_select)
        .transform_filter(unit_select)
    )
    
    # Combine all charts in new layout
    final_chart = (
        alt.vconcat(
            alt.hconcat(
                info_panel,
                retention_chart,
                spacing=20,
            ),
            alt.hconcat(
                alt.hconcat(
                    players_per_team_chart,
                    squad_size_trend,
                    spacing=0
                ),
                alt.hconcat(
                    average_retention_chart,
                    squad_retention_trend,
                    spacing=0
                ),
                spacing=25
            ),
            spacing=15
        )
        .configure_scale(bandPaddingInner=0.1).resolve_scale(color="shared")
    )

    # Save combined chart
    output_dir = project_root / "Charts" / "league"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"squad_analysis_{squad}s.html"
    final_chart.save(str(filename), embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False}})
    hack_params_css(str(filename), params=True)
    patch_combined_squad_analysis_html(str(filename))
    
    logging.info(f"Saved combined squad {squad} charts to {filename}")
    
    return final_chart

def generate_stats(squad=1, season="2025/26"):
    """Generate statistics for a specific squad and season."""
    
    # Load data
    df_summary, matches_json = load_match_data()
    
    # Convert season format for filtering (2025/26 -> 2025-2026)
    season_filter = season.replace('/', '-20')
    
    # Filter summary data for this squad and season
    league_name = divisions.get(squad, {}).get(season)
    if not league_name:
        logging.error(f"No league found for squad {squad} in season {season}")
        return
    
    matches_filtered = df_summary[
        (df_summary['season'] == season_filter) & 
        (df_summary['league'] == league_name)
    ]
    
    logging.info(f"Found {len(matches_filtered)} matches for squad {squad} in {season}")
    
    if matches_filtered.empty:
        logging.warning(f"No matches found for squad {squad} in season {season}")
        return
    
    # Generate results chart
    if matches_json:
        try:
            results_chart = league_results_chart(matches_json, squad, season_filter, table_order=True)
        except Exception as e:
            logging.error(f"Error creating results chart: {e}")
    
    # Generate squad analysis charts (requires player data)
    df_players = prepare_player_data(matches_json)
    if not df_players.empty:
        try:
            chart, squad_data = create_squad_charts(df_players, squad, season_filter)
        except Exception as e:
            logging.error(f"Error creating squad analysis charts: {e}")
    else:
        logging.warning("No player data available for squad analysis")
    
    logging.info(f"Completed stats generation for squad {squad}, season {season}")

def export_web_charts(squad=1):
    """Export chart specifications as JSON for web integration (matching existing chart approach)."""
    logging.info(f"Exporting web charts for Squad {squad}")
    
    # Load data
    df_summary, matches_json = load_match_data()
    df_players = prepare_player_data(matches_json)
    
    if df_players.empty:
        logging.error("No player data available")
        return
    
    # Filter for this squad
    squad_df = df_players[df_players["Squad"] == squad].copy()
    
    if squad_df.empty:
        logging.error(f"No data found for squad {squad}")
        return
    
    available_seasons = sorted(squad_df["Season"].dropna().unique())
    
    if not available_seasons:
        logging.error(f"No seasons found for squad {squad}")
        return
    
    logging.info(f"Creating web charts for squad {squad} with {len(available_seasons)} seasons")
    
    # Add unit classification
    squad_df["Unit"] = squad_df["Position"].apply(classify_unit)
    
    # Prepare all data for charts (same as combined charts but without filtering)
    players_per_team = (
        squad_df.groupby(["Season", "Team", "Color1", "Color2", "Player"])["Unit"]
        .agg(lambda x: "Forwards" if "Forwards" in x.values else "Backs" if "Backs" in x.values else "Bench")
        .reset_index()
        .groupby(["Season", "Team", "Color1", "Color2", "Unit"])
        .size()
        .reset_index()
        .rename(columns={0: "Total Players"})
    )

    total_players_per_team = squad_df.groupby(["Season", "Team", "Color1", "Color2"])["Player"].nunique().reset_index()
    total_players_per_team.columns = ["Season", "Team", "Color1", "Color2", "Total Players"]
    total_players_per_team["Unit"] = "Total"

    players_per_team = pd.concat([players_per_team, total_players_per_team], ignore_index=True)

    # Retention data
    retention_data = []
    for (team, season), matches in squad_df.sort_values("Date", ascending=True).groupby(["Team", "Season"]):
        prev_squad = set()
        prev_forwards = set()
        prev_backs = set()
        
        for match_id, match in matches.groupby("Match ID"):
            current_squad = set(match[match["Unit"] != "Bench"]["Player"])
            forwards = set(match[match["Unit"] == "Forwards"]["Player"])
            backs = set(match[match["Unit"] == "Backs"]["Player"])
            
            all_teams_in_match = squad_df[squad_df["Match ID"] == match_id]["Team"].unique()
            opposition = [t for t in all_teams_in_match if t != team]
            opposition_name = opposition[0] if opposition else "Unknown"
            
            if prev_squad:
                retained = len(current_squad & prev_squad)
                retained_forwards = len(forwards & prev_forwards)
                retained_backs = len(backs & prev_backs)
            else:
                retained = None
                retained_forwards = None
                retained_backs = None

            retention_data.append({
                "Match ID": match_id,
                "Season": season,
                "Date": match["Date"].iloc[0],
                "Team": team,
                "Opposition": opposition_name,
                "Players Retained": retained,
                "Forwards Retained": retained_forwards,
                "Backs Retained": retained_backs,
                "Color1": match["Color1"].iloc[0],
                "Color2": match["Color2"].iloc[0]
            })
            
            prev_squad = current_squad
            prev_forwards = forwards
            prev_backs = backs

    retention_df = pd.DataFrame(retention_data).dropna()

    # Average squad retention per team
    average_retention = (
        retention_df
        .groupby(["Season", "Team", "Color1", "Color2"])
        .agg({"Players Retained": "mean", "Forwards Retained": "mean", "Backs Retained": "mean"})
        .reset_index()
        .melt(["Season", "Team", "Color1", "Color2"], var_name="Unit", value_name="Average Retention")
    )
    average_retention["Unit"] = average_retention["Unit"].str.replace(" Retained", "").replace("Players", "Total")
    average_retention = average_retention.sort_values('Team', key=lambda x: x == 'East Grinstead')

    # Reshape retention data
    retention_long = retention_df.melt(
        id_vars=["Match ID", "Season", "Date", "Team", "Opposition", "Color1", "Color2"],
        value_vars=["Players Retained", "Forwards Retained", "Backs Retained"],
        var_name="Unit",
        value_name="Retained"
    )
    retention_long["Unit"] = retention_long["Unit"].str.replace(" Retained", "").replace("Players", "Total")
    retention_long = retention_long.sort_values('Team', key=lambda x: x == 'East Grinstead')
    
    # Create Altair charts WITHOUT parameters (data will be filtered in JS)
    # Squad Size Chart
    squad_size_chart = (
        alt.Chart(players_per_team)
        .mark_bar(strokeWidth=2)
        .encode(
            x=alt.X("Total Players:Q", title="Squad Size"),
            y=alt.Y("Team:N", sort="-x", title=None, axis=alt.Axis(labelPadding=10, labelLimit=200)),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Team", "Season", "Unit", "Total Players"],
        )
        .properties(
            title="Squad Size",
            width=420,
            height=alt.Step(25)
        )
    )
    
    # Average Retention Chart
    avg_retention_chart = (
        alt.Chart(average_retention)
        .mark_bar(strokeWidth=2)
        .encode(
            x=alt.X("Average Retention:Q", title="Average Retention"),
            y=alt.Y("Team:N", sort="-x", title=None, axis=alt.Axis(labelPadding=10, labelLimit=200)),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Team", "Season", "Unit:N", alt.Tooltip("Average Retention:Q", format=".2f")],
        )
        .properties(
            title="Average Retention",
            width=420,
            height=alt.Step(25)
        )
    )
    
    # Retention Timeline Chart
    retention_timeline_chart = (
        alt.Chart(retention_long)
        .mark_line(point={"size": 50})
        .encode(
            x=alt.X("Date:T", title="Match Date"),
            y=alt.Y("Retained:Q", title="Players Retained"),
            color=alt.Color("Color1:N", scale=None, legend=None),
            detail="Team:N",
            tooltip=[
                alt.Tooltip("Team:N"),
                alt.Tooltip("Opposition:N"),
                alt.Tooltip("Date:T", format="%d %b %Y"),
                alt.Tooltip("Season:N"),
                alt.Tooltip("Unit:N"),
                alt.Tooltip("Retained:Q", title="Players Retained")
            ],
        )
        .properties(
            title="Squad Retention Over Time",
            width=900,
            height=400
        )
    )
    
    # Export chart specs as JSON files
    output_dir = project_root / "data" / "charts"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    squad_size_chart.save(str(output_dir / f"league_squad_size_{squad}s.json"))
    avg_retention_chart.save(str(output_dir / f"league_avg_retention_{squad}s.json"))
    retention_timeline_chart.save(str(output_dir / f"league_retention_timeline_{squad}s.json"))
    
    logging.info(f"Exported web chart specs for squad {squad} to {output_dir}")

def main():
    """Main function to generate league statistics."""
    parser = argparse.ArgumentParser(
        description="Generate league statistics and charts from match data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python league_stats.py                      # Default: combined charts for squad 1
  python league_stats.py --squad 2            # Combined charts for squad 2
  python league_stats.py --season 2024/25     # Single season for squad 1
  python league_stats.py --all                # Combined charts for all squads
        """
    )
    parser.add_argument("--squad", type=int, default=None, help="Squad number (1 or 2)")
    parser.add_argument("--season", type=str, default=None, help="Season (e.g., 2025/26) - creates single season charts")
    parser.add_argument("--all", action="store_true", help="Generate combined charts for all available squads")
    parser.add_argument("--combined", action="store_true", default=True, help="Generate combined charts with all seasons (default)")
    
    args = parser.parse_args()
    
    if args.all:
        # Generate combined charts for all squads
        logging.info("Generating combined charts for all squads")
        
        df_summary, matches_json = load_match_data()
        df_players = prepare_player_data(matches_json)
        
        if not df_players.empty:
            available_squads = sorted([int(s) for s in df_players["Squad"].dropna().unique() if pd.notna(s)])
            
            for squad in available_squads:
                try:
                    logging.info(f"\n=== Generating combined charts for Squad {squad} ===")
                    create_combined_league_charts(squad=squad)
                    create_combined_results_chart(squad=squad)
                    create_combined_league_table_html(squad=squad)
                    
                except Exception as e:
                    logging.error(f"Error processing squad {squad}: {e}")
        else:
            logging.error("No player data available")
    
    elif args.season:
        # Generate for specific squad and season (legacy mode)
        squad = args.squad if args.squad else 1
        generate_stats(squad=squad, season=args.season)
    
    else:
        # Default: generate combined charts for specified or default squad
        squad = args.squad if args.squad else 1
        logging.info(f"Generating combined charts for Squad {squad}")
        
        # Generate combined squad analysis
        create_combined_league_charts(squad=squad)
        create_combined_results_chart(squad=squad)
        create_combined_league_table_html(squad=squad)
        
        # Export web charts (data files for JavaScript integration)
        export_web_charts(squad=squad)
        
        # Generate individual results charts for each season
        df_summary, matches_json = load_match_data()
        df_players = prepare_player_data(matches_json)
        
        if not df_players.empty:
            squad_seasons = sorted(df_players[df_players["Squad"] == squad]["Season"].unique())
            for season in squad_seasons:
                try:
                    league_results_chart(matches_json, squad, season, table_order=True)
                except Exception as e:
                    logging.error(f"Error creating results chart for season {season}: {e}")

if __name__ == "__main__":
    main()
