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

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from python.chart_helpers import hack_params_css

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

# Define Altair theme inline to avoid import issues
def alt_theme():
    return {
        "config": {
            "view": {"continuousWidth": 400, "continuousHeight": 300},
            "font": "PT Sans Narrow",
            "title": {"fontSize": 22, "fontWeight": "bold", "color": "#202946"},
        }
    }

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Register Altair theme
alt.themes.register("my_custom_theme", alt_theme)
alt.themes.enable("my_custom_theme")

# Define file paths
MATCHES_SUMMARY_CSV = "data/matches_summary.csv"
MATCHES_JSON = "data/matches.json"

def load_match_data():
    """Load match data from CSV and JSON files."""
    # Load summary CSV
    if not os.path.exists(MATCHES_SUMMARY_CSV):
        raise FileNotFoundError(f"Match summary file '{MATCHES_SUMMARY_CSV}' not found. Run league_data.py first.")
    
    df_summary = pd.read_csv(MATCHES_SUMMARY_CSV)
    logging.info(f"Loaded {len(df_summary)} matches from {MATCHES_SUMMARY_CSV}")
    
    # Load full JSON for player data
    if not os.path.exists(MATCHES_JSON):
        logging.warning(f"Match JSON file '{MATCHES_JSON}' not found. Player data will be unavailable.")
        matches_json = []
    else:
        with open(MATCHES_JSON, 'r') as f:
            matches_json = json.load(f)
        logging.info(f"Loaded {len(matches_json)} matches from {MATCHES_JSON}")
    
    return df_summary, matches_json

# Team colors for visualization
colors = {
    "East Grinstead": ["darkblue", "white"],
    "East Grinstead II": ["darkblue", "white"],
    "East Grinstead Ladies": ["darkblue", "white"],
    "Hove": ["dodgerblue", "maroon"],
    "Eastbourne": ["royalblue", "yellow"],
    "Haywards Heath": ["red", "black"],
    "Old Haileyburians": ["#89273a", "white"],
    "Old Rutlishians": ["gold", "navy"],
    "Trinity": ["lightsteelblue", "darkblue"],
    "Weybridge Vandals": ["purple", "green"],
    "London Cornish": ["black", "gold"],
    "Cobham": ["navy", "crimson"],
    "KCS Old Boys": ["red", "yellow"],
    "Twickenham": ["black", "red"],
    "Ealing Trailfinders 1871": ["darkgreen", "orange"],
    # previous teams
    "Kingston": ["maroon", "white"],
    "Old Tiffinians": ["rebeccapurple", "darkblue"],
    "Old Walcountians": ["deepskyblue", "gold"],
    "Old Cranleighans": ["darkblue", "gold"],
    "Teddington": ["gold", "darkblue"],
    "Pulborough": ["black", "white"],
    "Shoreham": ["forestgreen", "gold"],
    "Seaford": ["red", "darkblue"],
    "Lewes": ["blue", "white"],
    "Uckfield": ["purple", "gold"],
    "Crawley": ["maroon", "deepskyblue"],
    "Burgess Hill": ["black", "gold"],
    "Ditchling": ["black", "white"],
    "Brighton II": ["skyblue", "white"],
}

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
                        "Color1": colors.get(team_name, ["gray", "black"])[0], 
                        "Color2": colors.get(team_name, ["gray", "black"])[1]
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

    team_dropdown = alt.binding_select(
        options=[None] + sorted(squad_df["Team"].unique().tolist()), 
        name="Highlighted Team",
        labels=["All"] + sorted(squad_df["Team"].unique())
    )
    team_select = alt.selection_point(fields=["Team"], bind=team_dropdown, value="East Grinstead")

    # Radio button season selection
    season_radio = alt.binding_radio(
        options=sorted(squad_df["Season"].unique().tolist()), 
        name="Season", 
        labels=[f"{s[:4]}/{s[7:]}" for s in sorted(squad_df["Season"].unique())]
    )
    latest_season = sorted(squad_df["Season"].unique())[-1] if not squad_df.empty else "2025-2026"
    season_select = alt.selection_point(fields=["Season"], bind=season_radio, value=latest_season)

    # Top players chart
    top_players_chart = (
        alt.Chart(appearance_count.sort_values("Appearances", ascending=False))
        .mark_bar()
        .encode(
            x=alt.X("Appearances:Q", title="Total Appearances", axis=alt.Axis(orient="top")),
            y=alt.Y("Player:N", sort="-x", title=None),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Player", "Team", "Appearances"],
            opacity=alt.condition(team_select, alt.value(1), alt.value(0.2)),
        )
        .properties(
            title=alt.Title(
                text="Most Appearances",
                subtitle=f"Players with the most appearances - Squad {squad_number}"
            ),
            width=300, height=alt.Step(15))
        .add_params(season_select, team_select)
        .transform_filter(season_select)
        .transform_window(rank="rank(Appearances)", sort=[alt.SortField("Appearances", order="descending")])
        .transform_filter(alt.datum.rank <= 40)
    )

    # Players per team chart
    players_per_team_chart = (
        alt.Chart(players_per_team)
        .mark_bar(strokeWidth=2)
        .encode(
            x=alt.X("Total Players:Q", title="Total Players"),
            y=alt.Y("Team:N", sort="-x", title=None),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Team", "Unit", "Total Players"],
            opacity=alt.condition(team_select, alt.value(1), alt.value(0.2)),
            column=alt.Column("Unit:N", title=None, sort=["Total", "Forwards", "Backs", "Bench"]),
        )
        .resolve_scale(y="independent", x="independent")
        .properties(
            title=alt.Title(
                text=f"Squad Size - Squad {squad_number}", 
                subtitle="Total players representing each team across the season, by forwards, backs, and bench."
            ),
            width=180, height=alt.Step(25)
        )
        .add_params(season_select, team_select)
        .transform_filter(season_select)
    )

    # Retention chart
    retention_chart = (
        alt.Chart(retention_df)
        .mark_line(point={"size": 50})
        .encode(
            x=alt.X("Date:T", title="Match Date"),
            y=alt.Y(
                "Players Retained:Q", 
                title="Players Retained", 
                scale=alt.Scale(domain=[0, 15])
            ),
            color=alt.Color("Color1:N", scale=None, legend=None),
            detail="Team:N",
            tooltip=["Team", "Date", "Players Retained"],
            opacity=alt.condition(team_select, alt.value(1), alt.value(0.1)),
        )
        .properties(
            title=alt.Title(
                text=f"Squad Retention Over Time - Squad {squad_number}",
                subtitle="Number of players retained in the starting XV from the previous match."
            ),
            width=1000,
            height=400
        )
        .add_params(season_select, team_select)
        .transform_filter(season_select)
    )

    # Average retention chart
    average_retention_chart = (
        alt.Chart(average_retention)
        .mark_bar()
        .encode(
            x=alt.X("Average Retention:Q", title=None),
            y=alt.Y("Team:N", sort="-x", title=None, axis=alt.Axis(ticks=False, domain=False, labelPadding=10)),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Team", "Unit:N", alt.Tooltip("Average Retention:Q", format=".2f")],
            opacity=alt.condition(team_select, alt.value(1), alt.value(0.2)),
            column=alt.Column("Unit:N", title=None, sort=["Total", "Forwards", "Backs"])
        )
        .resolve_scale(y="independent", x="independent")
        .properties(
            title=alt.Title(
                text=f"Average Squad Retention - Squad {squad_number}",
                subtitle="Average players retained from the starting XV, by forwards and backs."
            ), 
            width=180, height=alt.Step(25)
        )
        .add_params(season_select, team_select)
        .transform_filter(season_select)
    )

    # Violin chart
    appearance_count_violin = (
        squad_df.groupby(["Season", "Team", "Color1", "Color2", "Player"])
        .size()
        .reset_index(name="Appearances")
    )

    violin_chart = (
        alt.Chart(appearance_count_violin)
        .add_params(season_select, team_select)
        .transform_filter(season_select)
        .transform_density(
            density="Appearances",
            groupby=["Team", "Color1", "Color2"],
            extent=[1, 25],
            steps=21,
            as_=["Appearances", "Density"],
        ) 
        .mark_area(orient="horizontal", opacity=0.5)
        .encode(
            y=alt.Y("Appearances:Q", title="Appearances"),
            x=alt.X("Density:Q", title="Density", stack="center", 
                   axis=alt.Axis(ticks=False, labels=False, offset=10, grid=False), 
                   scale=alt.Scale(nice=False)),
            color=alt.Color("Color1:N", scale=None, legend=None),
            stroke=alt.Stroke("Color2:N", scale=None, legend=None),
            tooltip=["Team", "Appearances", alt.Tooltip("Density:Q", format=".1%")],
            facet=alt.Facet("Team:N", columns=3, title=None, 
                           header=alt.Header(labelColor="gray", labelFontSize=18), 
                           spacing={"row": 30, "column": 0}),
            opacity=alt.condition(team_select, alt.value(1), alt.value(0.2)),
        )
        .properties(
            title=alt.Title(
                text=f"Player Appearance Distribution - Squad {squad_number}", 
                subtitle=["Distribution of appearances per player for each team.", "Wider areas = more players with that number of appearances."]
            ),
            width=180, height=200
        )
    )

    # Combine charts
    chart = (
        alt.vconcat(
            players_per_team_chart,
            average_retention_chart,
            retention_chart,
            alt.hconcat(violin_chart, top_players_chart)
        )
        .configure_scale(bandPaddingInner=0.1).resolve_scale(color="shared")
    )

    # Save chart
    os.makedirs("Charts/league", exist_ok=True)
    file = f"Charts/league/squad_analysis_{squad_number}s_{latest_season}.html"
    chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False}})
    hack_params_css(file, params=True)
    
    logging.info(f"Saved squad {squad_number} charts to {file}")
    
    return chart, squad_df

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
        if pd.isna(x["PD"]):
            return "To be played"
            
        if x["Home"] == x["Away"]:
            return "N/A"
            
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
        table_file = f"Charts/league/table_{squad_number}s_{season.replace('-', '_')}.html"
        if os.path.exists(table_file):
            try:
                table_df = pd.read_html(table_file)[0]
                teams = table_df["TEAM"].tolist()
            except:
                teams = pd_df["Team"].tolist()
        else:
            teams = pd_df["Team"].tolist()
    else:
        teams = pd_df["Team"].tolist()

    # Color scale
    color_scale = alt.Scale(
        domain=['Home Win', 'Home Win (LBP)', 'Away Win', 'Away Win (LBP)', 'Draw', 'To be played', None],
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
    textPD = alt.Chart(pd_df).mark_text(size=14, color="white", opacity=0.8).encode(
        x=alt.X('Team:N', title=None, sort=teams[::-1], axis=alt.Axis(ticks=False, domain=False, labels=False)),
        y=alt.Y('Team:N', title=None, sort=teams, axis=alt.Axis(ticks=False, domain=False, labels=False)),
        text=alt.Text('PD:N', format="+d")
    )

    # Final chart
    final_chart = (
        (heatmap + textA + textH + textPD)
        .add_params(highlight)
        .resolve_scale(color="independent", x="independent", y="independent", opacity="independent")
        .properties(
            title=alt.Title(
                text=f"League Results - Squad {squad_number} - {season[:4]}/{season[7:]}", 
                subtitle=[
                    "Complete league matrix showing all teams in the division.",
                    "Each row = team's home games, each column = away games.",
                    "Diagonal shows total points difference for each team.",
                    "Lighter shaded results were within 7 points (losing bonus point).",
                    "Click on a cell to highlight all of the home team's results. (Double click to reset)",
                ]
            ),
            background="white"
        )
    )
    
    os.makedirs("Charts/league", exist_ok=True)
    filename = f"Charts/league/results_{squad_number}s_{season}.html"
    final_chart.save(filename, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False}})
    hack_params_css(filename, params=False)
    
    logging.info(f"Saved squad {squad_number} results chart to {filename}")
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

def main():
    """Main function to generate league statistics."""
    parser = argparse.ArgumentParser(
        description="Generate league statistics and charts from match data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python league_stats.py                      # Default: squad 1, season 2025/26
  python league_stats.py --squad 2            # Squad 2, season 2025/26
  python league_stats.py --season 2024/25     # Squad 1, season 2024/25
  python league_stats.py --all                # All squads and seasons
        """
    )
    parser.add_argument("--squad", type=int, default=1, help="Squad number (1 or 2)")
    parser.add_argument("--season", type=str, default="2025/26", help="Season (e.g., 2025/26)")
    parser.add_argument("--all", action="store_true", help="Generate for all available squads and seasons")
    
    args = parser.parse_args()
    
    if args.all:
        # Generate for all available combinations
        logging.info("Generating stats for all squads and seasons")
        
        df_summary, matches_json = load_match_data()
        df_players = prepare_player_data(matches_json)
        
        if not df_players.empty:
            available_squads = sorted([int(s) for s in df_players["Squad"].dropna().unique() if pd.notna(s)])
            available_seasons = sorted(df_players["Season"].unique())
            
            for season in available_seasons:
                season_short = season.replace('-20', '/')
                for squad in available_squads:
                    try:
                        logging.info(f"\n=== Processing Squad {squad}, Season {season_short} ===")
                        generate_stats(squad=squad, season=season_short)
                    except Exception as e:
                        logging.error(f"Error processing squad {squad}, season {season_short}: {e}")
        else:
            logging.error("No player data available")
    else:
        # Generate for specific squad and season
        generate_stats(squad=args.squad, season=args.season)

if __name__ == "__main__":
    main()
