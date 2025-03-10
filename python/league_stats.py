import json
import os
import pandas as pd
from charts import alt_theme, hack_params_css
import altair as alt

alt.themes.register("my_custom_theme", alt_theme)
alt.themes.enable("my_custom_theme")

# Define file paths
MATCH_DATA_FOLDER = "data/match_data"  # Adjust if needed
OUTPUT_FILE = "season_squad_analysis.csv"

# List to store match data
data = []

# Process each match file
# For each file in data/match_data/ folder
for match_file in os.listdir(MATCH_DATA_FOLDER):

    with open(os.path.join(MATCH_DATA_FOLDER, match_file)) as f:
        # Load match data
        print(match_file)
        match_data = json.load(f)

    # Extract match details
    match_date = match_data["date"]
    teams = match_data["teams"]
    players = match_data["players"]

    for i in range(2):  # Loop over both teams
        team_name = teams[i]
        
        for position, player_name in players[i].items():
            data.append({
                "Match ID": int(match_file[:-5]),
                "Date": match_date,
                "Team": team_name,
                "Player": player_name,
                "Position": position
            })

# Create DataFrame
df = pd.DataFrame(data)

df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values(["Team", "Date"])

df["Unit"] = df["Position"].apply(lambda x: "Bench" if not(x.isnumeric()) else "Forwards" if int(x) <= 8 else "Backs")

# Summary Statistics
appearance_count = (
    df.groupby(["Team", "Player"]).size()
    .reset_index(name="Appearances")
    .sort_values("Appearances", ascending=False)
)
players_per_team = (
    df.groupby(["Team", "Player"])["Unit"]
    .agg(lambda x: "Forwards" if "Forwards" in x.values else "Backs" if "Backs" in x.values else "Bench")
    .reset_index()
    .groupby(["Team", "Unit"])
    .size()
    .reset_index()
    .rename(columns={0: "Total Players"})
)

total_players_per_team = df.groupby("Team")["Player"].nunique().reset_index()
total_players_per_team.columns = ["Team", "Total Players"]
total_players_per_team["Unit"] = "Total"

players_per_team = pd.concat([players_per_team, total_players_per_team], ignore_index=True)

retention_data = []

# Process retention per team
for team, matches in df.groupby("Team"):
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
            "Date": match["Date"].iloc[0],
            "Team": team,
            "Players Retained": retained,
            "Forwards Retained": retained_forwards,
            "Backs Retained": retained_backs
        })
        
        prev_squad = current_squad
        prev_forwards = forwards
        prev_backs = backs

retention_df = pd.DataFrame(retention_data).dropna()  # Remove first match (no previous squad)

# Average squad retention per team
average_retention = (
    retention_df
    .groupby("Team").agg({"Players Retained": "mean", "Forwards Retained": "mean", "Backs Retained": "mean"})
    .reset_index()
    .melt("Team", var_name="Unit", value_name="Average Retention")
)

average_retention["Unit"] = average_retention["Unit"].str.replace(" Retained", "").replace("Players", "Total")

##############
### CHARTS ###
##############

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
}
teams = []
main_colors = []
accent_colors = []

for k, v in colors.items():
    teams.append(k)
    main_colors.append(v[0])
    accent_colors.append(v[1])

selection = alt.selection_point(fields=["Team"], bind="legend", value="East Grinstead")

# Altair Chart: Top 10 Players by Appearances
top_players_chart = (
    alt.Chart(appearance_count.sort_values("Appearances", ascending=False).head(20))
    .mark_bar()
    .encode(
        x=alt.X("Appearances:Q", title="Total Appearances"),
        y=alt.Y("Player:N", sort="-x", title="Player"),
        color=alt.Color("Team:N", scale=alt.Scale(domain=teams, range=main_colors)),
        stroke=alt.Stroke("Team:N", scale=alt.Scale(domain=teams, range=accent_colors), legend=None),
        tooltip=["Player", "Team", "Appearances"],
        opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
    )
    .properties(
        title=alt.Title(
            text="Most Appearances",
            subtitle="Players with the most appearances in the league this season"
        ),
        width=300, height=alt.Step(18))
    # .add_params(selection)
)

players_per_team_chart = (
    alt.Chart(players_per_team)
    .mark_bar(strokeWidth=2)
    .encode(
        x=alt.X("Total Players:Q", title="Total Players"),
        y=alt.Y("Team:N", sort="-x", title=None),
        color=alt.Color("Team:N", scale=alt.Scale(domain=teams, range=main_colors)),
        stroke=alt.Stroke("Team:N", scale=alt.Scale(domain=teams, range=accent_colors), legend=None),
        tooltip=["Team", "Unit", "Total Players"],
        opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
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
    # .add_params(selection)
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
        color=alt.Color(
            "Team:N", 
            title="Team (click to highlight)",
            scale=alt.Scale(domain=teams, range=main_colors), 
            legend=alt.Legend(title=["Team", "(click to highlight)"], orient="none", legendY=500, legendX=1050)
        ),
        tooltip=["Team", "Date", "Players Retained"],
        opacity=alt.condition(selection, alt.value(1), alt.value(0.1)),
    )
    .properties(
        title=alt.Title(
            text="Squad Retention Over Time",
            subtitle="Total number of players retained in the starting XV for the following match."
        ),
        width=1000,
        height=400
    )
    # .add_params(selection)
)


# Average squad retention per team
average_retention_chart = (
    alt.Chart(average_retention)
    .mark_bar()
    .encode(
        x=alt.X("Average Retention:Q", title=None),
        y=alt.Y("Team:N", sort="-x", title=None, axis=alt.Axis(ticks=False, domain=False, labelPadding=10)),
        color=alt.Color("Team:N", scale=alt.Scale(domain=teams, range=main_colors)),
        stroke=alt.Stroke("Team:N", scale=alt.Scale(domain=teams, range=accent_colors), legend=None),
        tooltip=["Team", "Unit:N", "Players Retained:Q"],
        opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
        column=alt.Column("Unit:N", title=None, sort=["Total", "Forwards", "Backs"])
    )
    .resolve_scale(y="independent", x="independent")
    .properties(
        title=alt.Title(
            text="Average Squad Retention",
            subtitle="Average number of players retained from the starting XV from game to game, and split by forwards and backs."
        ), 
        width=240, height=alt.Step(30)
    )
    # .add_params(selection)
)

# Create violin plot data
appearance_count = df.groupby(["Team", "Player"]).size().reset_index(name="Appearances")

# Violin Plot for Player Appearance Distribution
violin_chart = (
    alt.Chart(appearance_count)
    .transform_density(
        density="Appearances",
        groupby=["Team"],
        as_=["Appearances", "Density"]
    ) 
    .mark_area(orient="horizontal", opacity=0.5)
    .encode(
        y=alt.Y("Appearances:Q", title="Appearances"),
        x=alt.X("Density:Q", title="Density", stack="center", axis=alt.Axis(ticks=False, labels=False, offset=10, grid=False), scale=alt.Scale(nice=False)),
        color=alt.Color("Team:N", scale=alt.Scale(domain=teams, range=main_colors)),
        stroke=alt.Stroke("Team:N", scale=alt.Scale(domain=teams, range=accent_colors), legend=None),
        tooltip=["Team", "Appearances"],
        facet=alt.Facet("Team:N", columns=4, title=None, header=alt.Header(labelColor="gray"), spacing={"row": 30}),
        opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
    )
    .properties(
        title=alt.Title(
            text="Player Appearance Distribution", 
            subtitle=["Distribution of appearances per player for each team, from most appearances (top) to least (bottom).", "The wider the area, the more players with that number of appearances. "],
        ),
        width=300, height=200
    )
    # .add_params(selection)
)

# Display charts
chart = (
    (
        players_per_team_chart &
        retention_chart &
        average_retention_chart & 
        violin_chart &
        top_players_chart
    )
    .add_params(selection)
    .configure_scale(bandPaddingInner=0.2).resolve_scale(color="shared")
)




file = "charts/league/squad_analysis.html"
chart.save(file)
hack_params_css(file, params=False)