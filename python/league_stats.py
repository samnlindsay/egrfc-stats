import json
import os
import pandas as pd
from charts import alt_theme, hack_params_css
import altair as alt

alt.themes.register("my_custom_theme", alt_theme)
alt.themes.enable("my_custom_theme")

import os
import json
import pandas as pd

# Define file paths
MATCH_DATA_FILE = "data/matches.json"  # Updated to read from a single JSON file
OUTPUT_FILE = "season_squad_analysis.csv"

# Load all match data from the JSON file
if not os.path.exists(MATCH_DATA_FILE):
    raise FileNotFoundError(f"Match data file '{MATCH_DATA_FILE}' not found.")

with open(MATCH_DATA_FILE, "r") as f:
    matches = json.load(f)

# List to store structured match data
data = []

colors = {
    "East Grinstead": ["darkblue", "white"],
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
}

# Process each match entry
for match in matches:
    match_id = match["match_id"]
    match_date = match["date"]
    teams = match["teams"]
    players = match["players"]
    season = match["season"]
    league = match["league"]

    for i in range(2):  # Loop over both teams
        team_name = teams[i]
        
        for position, player_name in players[i].items():
            data.append({
                "Match ID": match_id,
                "Season": season,
                "League": league,
                "Date": match_date,
                "Team": team_name,
                "Player": player_name,
                "Position": position,
                "Color1": colors.get(team_name, ["gray", "black"])[0], 
                "Color2": colors.get(team_name, ["gray", "black"])[1]
            })

# Create DataFrame
df = pd.DataFrame(data)

# Save to CSV
df.to_csv(OUTPUT_FILE, index=False)

print(f"Season squad analysis saved to {OUTPUT_FILE}")


df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values(["Team", "Date"])

df["Unit"] = df["Position"].apply(lambda x: "Bench" if not(x.isnumeric()) else "Forwards" if int(x) <= 8 else "Backs")

# Summary Statistics
appearance_count = (
    df.groupby(["Season", "Team", "Color1", "Color2", "Player"]).size()
    .reset_index(name="Appearances")
    .sort_values("Appearances", ascending=False)
)
players_per_team = (
    df.groupby(["Season", "Team", "Color1", "Color2", "Player"])["Unit"]
    .agg(lambda x: "Forwards" if "Forwards" in x.values else "Backs" if "Backs" in x.values else "Bench")
    .reset_index()
    .groupby(["Season", "Team", "Color1", "Color2", "Unit"])
    .size()
    .reset_index()
    .rename(columns={0: "Total Players"})
)

total_players_per_team = df.groupby(["Season", "Team", "Color1", "Color2", ])["Player"].nunique().reset_index()
total_players_per_team.columns = ["Season", "Team", "Color1", "Color2", "Total Players"]
total_players_per_team["Unit"] = "Total"

players_per_team = pd.concat([players_per_team, total_players_per_team], ignore_index=True)

retention_data = []

# Process retention per team
for team, matches in df.sort_values("Date", ascending=True).groupby(["Team", "Season"]):
    prev_squad = set()
    prev_forwards = set()
    prev_backs = set()
    
    for match_id, match in matches.groupby("Match ID"):
        current_squad = set(match[match["Unit"]!="Bench"]["Player"])  # Exclude substitutes
        forwards = set(match[match["Unit"]=="Forwards"]["Player"])
        backs = set(match[match["Unit"]=="Backs"]["Player"])
        
        if prev_squad:
            retained = len(current_squad & prev_squad)
            retained_forwards = len(forwards & prev_forwards)
            retained_backs = len(backs & prev_backs)
        else:
            retained = None  # No previous match to compare
            retained_forwards = None
            retained_backs = None

        retention_data.append({
            "Match ID": match_id,
            "Season": team[1],
            "Date": match["Date"].iloc[0],
            "Team": team[0],
            "Players Retained": retained,
            "Forwards Retained": retained_forwards,
            "Backs Retained": retained_backs,
            "Color1": match["Color1"].iloc[0],
            "Color2": match["Color2"].iloc[0]
        })
        
        prev_squad = current_squad
        prev_forwards = forwards
        prev_backs = backs

retention_df = pd.DataFrame(retention_data).dropna()  # Remove first match (no previous squad)

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
    options=[None] + sorted(df["Team"].unique().tolist()), 
    name="Highlighted Team",
    labels=["All"] + sorted(df["Team"].unique())
)
team_select = alt.selection_point(fields=["Team"], bind=team_dropdown, value="East Grinstead")

# Radio button season/league selection
season_radio = alt.binding_radio(options=sorted(df["Season"].unique().tolist()), name="Season", labels=[f"{s[:4]}/{s[7:]}" for s in sorted(df["Season"].unique())])
season_select = alt.selection_point(fields=["Season"], bind=season_radio, value="2024-2025")

# Altair Chart: Top 10 Players by Appearances
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
            subtitle="Players with the most appearances in the league this season"
        ),
        width=300, height=alt.Step(18))
    .add_params(season_select, team_select)
    .transform_filter(season_select)
    # Filter top 20 players
    .transform_window(rank="rank(Appearances)", sort=[alt.SortField("Appearances", order="descending")])
    .transform_filter(alt.datum.rank <= 40)
)

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
            text="Squad Size", 
            subtitle="Total players representing each team across the season, and split by forwards, backs, and bench-only players."
        ),
        width=180,height=alt.Step(30)
    )
    .add_params(season_select, team_select)
    .transform_filter(season_select)
)

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
            text="Squad Retention Over Time",
            subtitle="Total number of players retained in the starting XV for the following match."
        ),
        width=1000,
        height=400
    )
    .add_params(season_select, team_select)
    .transform_filter(season_select)
)


# Average squad retention per team
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
            text="Average Squad Retention",
            subtitle="Average number of players retained from the starting XV from game to game, and split by forwards and backs."
        ), 
        width=180, height=alt.Step(30)
    )
    .add_params(season_select, team_select)
    .transform_filter(season_select)
)

# Create violin plot data
appearance_count = (
    df.groupby(["Season", "Team", "Color1", "Color2", "Player"])
    .size()
    .reset_index(name="Appearances")
)

# Violin Plot for Player Appearance Distribution
violin_chart = (
    alt.Chart(appearance_count)
    .add_params(season_select,team_select)
    .transform_filter(season_select)
    .transform_density(
        density="Appearances",
        groupby=["Team", "Color1", "Color2"],
        extent=[1, 22],
        steps=21,
        as_=["Appearances", "Density"],
    ) 
    .mark_area(orient="horizontal", opacity=0.5)
    .encode(
        y=alt.Y("Appearances:Q", title="Appearances"),
        x=alt.X("Density:Q", title="Density", stack="center", axis=alt.Axis(ticks=False, labels=False, offset=10, grid=False), scale=alt.Scale(nice=False)),
        color=alt.Color("Color1:N", scale=None, legend=None),
        stroke=alt.Stroke("Color2:N", scale=None, legend=None),
        tooltip=["Team", "Appearances",alt.Tooltip("Density:Q", format=".1%")],
        facet=alt.Facet("Team:N", columns=3, title=None, header=alt.Header(labelColor="gray", labelFontSize=18), spacing={"row": 30, "column": 0}),
        opacity=alt.condition(team_select, alt.value(1), alt.value(0.2)),
    )
    .properties(
        title=alt.Title(
            text="Player Appearance Distribution", 
            subtitle=["Distribution of appearances per player for each team, from most appearances (top) to least (bottom).", "The wider the area, the more players with that number of appearances. "],
        ),
        width=180, height=200
    )
)

# Display charts
chart = (
    alt.vconcat(
        players_per_team_chart,
        average_retention_chart,
        retention_chart,
        alt.hconcat(violin_chart, top_players_chart),
        center=True
    )
    .configure_scale(bandPaddingInner=0.2).resolve_scale(color="shared")
)

file = "charts/league/squad_analysis.html"
chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
hack_params_css(file, params=True)