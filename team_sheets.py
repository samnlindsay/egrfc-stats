import pandas as pd
import altair as alt
import json
from charts import *

def most_common_players(df, by="Position"):
    mcp = df.groupby(["Player", by]).size().reset_index(name=f"Count{by}")\
        .sort_values(f"Count{by}", ascending=False)\
        .groupby(by).head(4).reset_index(drop=True)\
        .sort_values([by, f"Count{by}"], ascending=[True,False]).reset_index(drop=True)
    
    if by == "Position":
        return mcp  
    else:
        mcp["Position"]=mcp["Number"].map(d)
        return mcp[mcp["Number"] <= 15]

# Function to get top N players in each position (by total starts):
# 1 for hooker/scrum half/fly half
# 2 for prop/second row/centre
# 3 for back row/back three
def top_by_position(x):
    if x["Position"].iloc[0] in ["Hooker", "Scrum Half", "Fly Half"]:
        return x.nlargest(1, "CountPosition", "first")
    elif x["Position"].iloc[0] in ["Prop", "Second Row", "Centre"]:
        return x.nlargest(2, "CountPosition", "first")
    else:
        return x.nlargest(3, "CountPosition", "first")

def team_of_the_season(squad=1, season="2024/25", bench_forwards=2, bench_backs=1):

    df = players(squad)
    df = df[df["Season"] == season]

    mcp = most_common_players(df, by='Position')
    mcn = most_common_players(df, by='Number')

    #### STARTERS ####
    starters = mcp.groupby("Position").apply(top_by_position)\
        .reset_index(drop=True)

    starters = starters.merge(mcn, on=["Player","Position"], how="left")
    starters = starters.sort_values(["CountPosition", "CountNumber"], ascending=[False,False])

    # If a Player appears only once, delete all other rows with their Number
    unique = starters.groupby("Player").filter(lambda x: len(x) == 1)

    starters = pd.concat([unique, starters[~starters["Number"].isin(unique["Number"])]])

    # If a Number appears only once, delete all other rows for that Player
    unique = starters.groupby("Number").filter(lambda x: len(x) == 1)

    starters = pd.concat([unique, starters[~starters["Player"].isin(unique["Player"])]])
    if len(starters) > len(set(starters["Player"])):
        starters.sort_values(["CountPosition", "CountNumber"], ascending=[False,False])
        for p in set(starters["Player"]):
            # Keep only the row with the highest Count for each Player
            # Delete other rows for that player from starters
            p_row = starters[starters["Player"] == p].nlargest(1, "CountPosition")
            starters = pd.concat([p_row, starters[(starters["Player"] != p) & (starters["Number"] != p_row["Number"].iloc[0])]])

        starters = starters[["Number", "Position", "Player", "CountPosition", "CountNumber"]].sort_values("Number")

    #### BENCH ####
    apps = players_agg(squad)
    apps = apps[apps["Season"]==season].sort_values(["TotalGames", "TotalStarts"], ascending=False)
    apps = apps[['Player', 'MostCommonPosition', 'MostCommonPositionType', 'TotalGames', 'TotalStarts']]


    # Keep first 2 rows with MostCommonPositionType=="Forwards" and first row with "Backs"
    bench = apps[~apps["Player"].isin(starters["Player"])]
    bench = bench.groupby("MostCommonPositionType")\
        .apply(lambda x: x.nlargest(
            bench_forwards if all(x["MostCommonPositionType"]=="Forwards") else bench_backs, 
            "TotalGames", "all"))\
        .reset_index(drop=True)\
        .sort_values("MostCommonPositionType", ascending=False)\
        .reset_index(drop=True)

    bench["Number"] = bench.index + 16
    bench = bench[["Number", "Player", "TotalStarts", "TotalGames"]]
    # bench.rename(columns={"TotalStarts": "Count_p", "TotalGames":"Count"}, inplace=True)

    # Count per Player
    apps = apps.groupby("Player").agg({"TotalGames":"sum", "TotalStarts":"sum"}).reset_index()
    coords = pd.DataFrame([
            {"Position": "Prop", "n": 1, "x": 10, "y": 95},
            {"Position": "Hooker", "n": 2, "x": 25, "y": 95},
            {"Position": "Prop", "n": 3, "x": 40, "y": 95},
            {"Position": "Second Row", "n": 4, "x": 17, "y": 82},
            {"Position": "Second Row", "n": 5, "x": 33, "y": 82},
            {"Position": "Back Row", "n": 6, "x": 6, "y": 72},
            {"Position": "Back Row", "n": 7, "x": 44, "y": 72},
            {"Position": "Back Row", "n": 8, "x": 25, "y": 67},
            {"Position": "Scrum Half", "n": 9, "x": 25, "y": 50},
            {"Position": "Fly Half", "n": 10, "x": 42, "y": 45},
            {"Position": "Back Three", "n": 11, "x": 8, "y": 20},
            {"Position": "Centre", "n": 12, "x": 59, "y": 38},
            {"Position": "Centre", "n": 13, "x": 75, "y": 30},
            {"Position": "Back Three", "n": 14, "x": 92, "y": 20},
            {"Position": "Back Three", "n": 15, "x": 50, "y": 10},
            {"Position": None, "n": 16, "x": 75, "y": 86},
            {"Position": None, "n": 17, "x": 75, "y": 78},
            {"Position": None, "n": 18, "x": 75, "y": 70},
            {"Position": None, "n": 19, "x": 75, "y": 62},
            {"Position": None, "n": 20, "x": 75, "y": 54},
            {"Position": None, "n": 21, "x": 75, "y": 46},
            {"Position": None, "n": 22, "x": 75, "y": 38},
            {"Position": None, "n": 23, "x": 75, "y": 30},
        ])
    bench = bench.merge(coords, left_on="Number", right_on="n", how="inner").drop(columns="n")

    starters = starters.merge(coords, left_on="Number", right_on="n", how="inner").sort_values("Number").drop(columns="n")
    starters = starters.merge(apps, left_on="Player", right_on="Player", how="inner").sort_values("Number", ascending=False)
    starters = pd.concat([starters, bench]).sort_values("Number")

    return starters

def team_of_the_season_chart(squad=1, season="2024/25", **kwargs):
    
    top = team_of_the_season(squad, season, **kwargs)

    top_count = top["TotalStarts"].sum() 
    p = players(squad)
    season_count = len(p[(p["Season"]==season) & (p["Number"]<=15)])

    prop = top_count/season_count

    with open("tots_lineup.json") as f:
        chart = json.load(f)
    
    chart["title"]["text"] = f"{'1st' if squad==1 else '2nd'} XV Team of the Season"
    chart["title"]["subtitle"][1] = chart["title"]["subtitle"][1].replace("XXX", f"{prop:.0%}")
    chart["data"]["values"] = top.to_dict(orient="records")
    
    return alt.Chart.from_dict(chart)

def team_sheets_chart(df=None, file=None):

    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd"], name="Squad"),
        value="1st"
    )

    season_selection = alt.param(
        bind=alt.binding_radio(options=[*seasons, "All"], name="Season"), 
        value="All" 
    )

    players_selection = alt.selection_single(fields=["Player"], name="Player", on="mouseover", clear="mouseout")

    team_selection = alt.selection_single(fields=["Opposition"], name="Opposition", on="click")

    def team_sheet_part(df, position_type):

        base = (
            alt.Chart(df if df is not None else {"url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/players.csv',"format":{'type':"csv"}})
            .transform_calculate(
                P="split(datum.Player, ' ')[0][0] + ' ' + split(datum.Player, ' ')[1]",
            )
            .transform_joinaggregate(
                game_sort="min(index)",
                groupby=["GameID", "Season", "Squad"]
            )
            .encode(
                x=alt.X(
                    "Number:N", 
                    axis=alt.Axis(
                        ticks=False, 
                        labelFontStyle="bold", 
                        labelFontSize=24, 
                        orient="top", 
                        title=position_type,
                        titleFontSize=36,
                    )
                ),
                y=alt.Y(
                    "GameID:O", 
                    axis=alt.Axis(title=None, orient="left", labelLimit=130, labelFontSize=12) if position_type=="Forwards" else None, 
                    sort=alt.EncodingSortField(field="game_sort", order="descending"),
                ),
                opacity=alt.condition(players_selection, alt.value(1), alt.value(0.5)),
            ).properties(
                width=alt.Step(75),
                height=alt.Step(15)
            ).transform_filter(f"datum.PositionType == '{position_type}'")
        )

        rect = base.mark_rect().encode(
            color=alt.Color("Player:N", legend=None, scale=alt.Scale(scheme="category20b")),
            stroke=alt.condition(players_selection, alt.value("black", empty=False), alt.value(None)),
        )

        text=base.mark_text(baseline='middle', fontSize=9).encode(
            text=alt.Text("P:N"),
            color=alt.Color("Player:N", legend=None, scale=alt.Scale(range=["white", "white", "black", "black"])),
        )

        chart = (
            (rect + text).resolve_scale(color="independent", y="shared")
            .add_selection(squad_selection, season_selection, players_selection, team_selection)
            .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
            .transform_filter(f"datum.Squad == {squad_selection.name}")
            .transform_filter(team_selection)
            .facet(
                row=alt.Row("Season:N", header=alt.Header(title=None) if position_type=="Forwards" else None, sort="descending"),
                spacing=20,
                align="each"
            )
            .resolve_scale(x="shared", y="independent", color="shared")
        )
    
        return chart


    chart = (
        alt.hconcat(
            team_sheet_part(df, "Forwards"),
            team_sheet_part(df, "Backs"),
            team_sheet_part(df, "Bench")
        )
        .properties(title=alt.Title(text="Team Sheets", subtitle=["Hover over a player to highlight their appearances", "Click anywhere to filter by the selected opposition."]))
    )

    if file:
        chart.save(file)
        hack_params_css(file, overlay=True)
    
    return chart