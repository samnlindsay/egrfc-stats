import json# Create custom style for altair charts
import altair as alt
import pandas as pd
from data_prep import *
from copy import deepcopy

# Set the default configuration for altair
def alt_theme():

    title_font="PT Sans Narrow, Helvetica Neue, Helvetica, Arial, sans-serif"
    font="Lato, sans-serif"
    
    return {
        "config": {
            "axis": {
                "labelFont": font,
                "titleFont": title_font,
                "labelFontSize": 13,
                "titleFontSize": 24,
                "gridColor":"#202947",
                "gridOpacity": 0.2,
            },
            "header": {
                "labelFont": title_font,
                "titleFont": title_font,
                "labelFontSize": 24,
                "titleFontSize": 28,
                "labelFontWeight": "bold",
                "orient": "left",
            },
            "legend": {
                "labelFont": font,
                "titleFont": title_font,
                "labelFontSize": 14,
                "titleFontSize": 16,
                "titlePadding": 5,
                "fillColor": "white",
                "strokeColor": "black", 
                "padding": 10,
                "titleFontWeight": "lighter",
                "titleFontStyle": "italic",
                "titleColor": "gray",
                "offset": 10,
            },
            "title": {
                "font": title_font,
                "fontSize": 48,
                "fontWeight": "bold",
                "anchor": "start",
                "align": "center",
                "titlePadding": 20,
                "subtitlePadding": 10,
                "subtitleFontWeight": "lighter",
                "subtitleFontSize": 12,
                "subtitleColor": "",
                "subtitleFontStyle": "italic",
                "offset": 15,
                "color": "black",
            },
            "axisX": {
                "labelAngle": 0
            },
            "facet": {
                "title": None,
                "header": None,
                "align": {"row": "each", "column": "each"},  
            },
            "resolve": {
                "scale": {
                    "y": "independent",
                    "facet": "independent"
                }
            },
            "background": "#20294710"
        }
    }

alt.themes.register("my_custom_theme", alt_theme)
alt.themes.enable("my_custom_theme")

game_type_scale = alt.Scale(
    domain=["League", "Cup", "Friendly"], 
    range=["#202947", "#981515", "#146f14"]                
)

squad_scale = alt.Scale(
    domain=["1st", "2nd"],
    range=["#202947", "#146f14"]
)

def squad_row(squad, **kwargs):
    row = alt.Row(
        'Squad:N', 
        header=alt.Header(title=None, labelExpr="datum.value + ' XV'", labelFontSize=40, labels=squad==0),
        sort=alt.SortOrder('ascending'),
        **kwargs
    )
    return row

def season_column(season, **kwargs):
    column = alt.Column(
        'Season:N',
        header=alt.Header(title=None, labelFontSize=40, labels=season is None),
        sort=alt.SortOrder('ascending'),
        **kwargs
    )
    return column

position_order = ["Prop", "Hooker", "Second Row", "Back Row", "Scrum Half", "Fly Half", "Centre", "Back Three"]

def plot_starts_by_position(squad=1, season="2024/25", fb_only=False, df=None, min=0):

    # Filter by squad/season/starts only
    if df is None:
        df = players()
    if squad == 1:
        df = df[df["Squad"] == "1st"]
    elif squad == 2:
        df = df[df["Squad"] == "2nd"]
    if season:
        df = df[df["Season"] == season]
    df = df[df["Number"] <= 15]

    # legend selection filter
    legend = alt.selection_point(fields=["GameType"], bind="legend", on="click")

    title = f"{'1st XV' if squad==1 else '2nd XV' if squad == 2 else 'Total'} Starts (by position)"

    # altair bar chart of starts by position
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X('count()', axis=alt.Axis(title="Starts", orient="bottom")),
            y=alt.Y('Player:N', sort='-x', title=None),
            # facet=facet,
            column=alt.Column(
                f"Position{'Type' if fb_only else ''}", 
                title=None, 
                header=alt.Header(title=None, labelFontSize=36), 
                align="each",
                sort=["Forwards", "Backs"] if fb_only else position_order
            ),
            row=squad_row(squad, align="each"),
            tooltip=[
                "Player", 
                "Position", 
                alt.Tooltip("count()", title="Starts"), 
                'GameType:N'
            ],      
            color=alt.Color(
                "GameType:N",
                scale=game_type_scale,
                legend=alt.Legend(title=None, orient="bottom", direction="horizontal", titleOrient="left")
            ),
            order=alt.Order('GameType:N', sort='descending')
        )
        .resolve_scale(y="independent", x="shared")
        .properties(width=150, height=alt.Step(14), title=alt.Title(text=title, subtitle="Not including bench appearances."))
        .add_params(legend)
        .transform_joinaggregate(TotalGames="count()", groupby=["Player", "PositionType" if fb_only else "Position"])
        .transform_filter(f"datum.TotalGames >= {min}")
        .transform_filter(legend)
    )

    return chart    

# Plot the number of games played by each player in the 2024/25 season
def plot_games_by_player(squad=1, season="2024/25", min=5, agg=False, df=None):

    # Filter by squad/season/starts only
    if df is None:
        df = players()
    if squad == 1:
        df = df[df["Squad"] == "1st"]
    elif squad == 2:
        df = df[df["Squad"] == "2nd"]
    if season:
        df = df[df["Season"] == season]

    c = alt.Color(
        f"GameType:N",
        scale=game_type_scale,
        legend=alt.Legend(
            title=None, orient="bottom", direction="horizontal", titleOrient="left"
        )
    )
    o = alt.Order("GameType", sort="descending")

    # legend selection filter
    legend = alt.selection_point(fields=["GameType" if squad != 0 else "Squad"], bind="legend", on="click")
    
    chart = (
        alt.Chart(df)
        .mark_bar(strokeWidth=2)
        .encode(
            x=alt.X("count()", axis=alt.Axis(title=None, orient="top")),
            y=alt.Y("Player", sort="-x", title=None),
            color=c,
            order=o,
            opacity=alt.Opacity(
                "PositionType:N",
                scale=alt.Scale(domain=["Start", "Bench"], range=[1.0, 0.6]), 
                legend=None if squad==0 else alt.Legend(title="Game Type", orient="bottom", direction="horizontal", titleOrient="left")
            ),
            column=alt.Column(
                "Season:N" if season is None else "Squad:N", 
                title=None, 
                header=alt.Header(
                    title=None, 
                    labelFontSize=36, 
                    labelExpr="datum.value + ' XV'" if (season is not None and squad==0) else ""
                ) if (season is None or squad==0) else None
            ),
            tooltip=[
                "Player:N", 
                "Season:N",
                "GameType:N",
                "Squad:N",
                alt.Tooltip("count()", title="Games"), 
                alt.Tooltip("TotalGames:Q", title="Total Games")
            ]
        )
        .transform_filter(legend)
        .add_params(legend)
        .transform_joinaggregate(TotalGames="count()", groupby=["Player", "Season"])
        .resolve_scale(y="independent")
        .transform_filter(f"datum.TotalGames >= {min}")
        .properties(
            title=alt.Title(
                text=f"Appearances by {'Squad' if season else 'Season'}",
                subtitle=f"Minimum {min} appearances per squad per season. Lighter shaded bars represent bench appearances.",
                subtitleFontStyle="italic"  
            ),
            width=400 if (season and squad>0) else 250,
            height=alt.Step(15)
        )
    )
    
    if season is not None:
        chart = chart.transform_filter(alt.datum.Season == season)
    
    if agg and (season is None or squad == 0):

        agg_chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("count()", axis=alt.Axis(title=None, orient="top")),
                y=alt.Y("Player:N", title=None, sort="-x"),
                color=alt.Color(
                    "Squad:N", 
                    scale=squad_scale, 
                    legend=alt.Legend(title="Squad", orient="right", titleOrient="top")
                ),
                order=alt.Order("Squad", sort="ascending"),
                opacity=alt.Opacity(
                    "PositionType:N",
                    scale=alt.Scale(domain=["Start", "Bench"], range=[1.0, 0.6]),
                    legend=None
                ),
                tooltip=[
                    "Player:N",
                    "Squad:N",
                    alt.Tooltip("count()", title="Games"), 
                    alt.Tooltip("TotalGames:Q", title="Total Games")
                ]
            )
            .transform_filter(legend)
            .add_params(legend)
            .transform_joinaggregate(TotalGames="count()", groupby=["Player"])
            .transform_filter(f"datum.TotalGames >= {2*min if season is None else min}")
            .properties(
                width=500,
                height=alt.Step(15),
                title=alt.Title(
                    text=f"{'1st XV' if squad==1 else ('2nd XV' if squad==2 else 'Total')} Appearances{' (since 2021)' if season is None else ''}",
                    subtitle=f"Minimum {2*min if season is None else min} appearances total). Lighter shaded bars represent bench appearances.",
                    subtitleFontStyle="italic",
                ),
            )
        )

        if season is not None:
            agg_chart = agg_chart.transform_filter(alt.datum.Season == season)

        return alt.vconcat(chart, agg_chart).resolve_scale(color="independent")
    else:
        return chart


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
def team_sheet_chart(
        squad=1, 
        names=None, 
        captain=None, 
        vc=None, 
        opposition=None, 
        home=True, 
        competition="Counties 1 Sussex",
        season="2024/25"
    ):

    if names is None:
        df = team_sheets(squad=1) 

        # Last row as dict
        team = df.iloc[-1].to_dict()


        label = f'{"1st" if squad==1 else "2nd"} XV vs {team["Opposition"]}({team["Home/Away"]})'
        captain = team["Captain"]
        vc = team["VC"]
        season = team["Season"]
        competition = team["Competition"]

        # Keep keys that can be converted to integers
        team = {int(k): v for k, v in team.items() if k.isnumeric() and v}

        # Convert team to dataframe with Number and Player columns
        team = pd.DataFrame(team.items(), columns=["Number", "Player"])

    else:
        label = f'{"1st" if squad==1 else "2nd"} XV vs {opposition} ({"H" if home else "A"})'

        # Convert names to Player column of a dataframe with Number column (1-len(names))
        team = pd.DataFrame({"Player": names, "Number": range(1, len(names)+1)})

    coords = pd.DataFrame([
                {"n": 1, "x": 10, "y": 81},
                {"n": 2, "x": 25, "y": 81},
                {"n": 3, "x": 40, "y": 81},
                {"n": 4, "x": 18, "y": 69},
                {"n": 5, "x": 32, "y": 69},
                {"n": 6, "x": 6, "y": 61},
                {"n": 7, "x": 44, "y": 61},
                {"n": 8, "x": 25, "y": 56},
                {"n": 9, "x": 20, "y": 42},
                {"n": 10, "x": 38, "y": 36},
                {"n": 11, "x": 8, "y": 18},
                {"n": 12, "x": 56, "y": 30},
                {"n": 13, "x": 74, "y": 24},
                {"n": 14, "x": 92, "y": 18},
                {"n": 15, "x": 50, "y": 10},
                {"n": 16, "x": 80, "y": 82},
                {"n": 17, "x": 80, "y": 74},
                {"n": 18, "x": 80, "y": 66},
                {"n": 19, "x": 80, "y": 58},
                {"n": 20, "x": 80, "y": 50},
                {"n": 21, "x": 80, "y": 42},
                {"n": 22, "x": 80, "y": 34},
                {"n": 23, "x": 80, "y": 26},
            ])
    team = team.merge(coords, left_on="Number", right_on="n", how="inner").drop(columns="n")

    # Add captain (C) and vice captain (VC) else None
    team["Captain"] = team["Player"].apply(lambda x: "C" if x == captain else "VC" if x == vc else None)

    team["Player"] = team["Player"].str.split(" ")

    team.to_dict(orient="records")

    with open("team-sheet-lineup.json") as f:
        chart = json.load(f)
    chart["data"]["values"] = team.to_dict(orient="records")
    chart["title"]["text"] = label
    chart["title"]["subtitle"] = f"{season} - {competition}"

    n_replacements = len(team) - 15
    
    y = 126 + (n_replacements * 64)
    chart["layer"][0]["mark"]["y2"] = y
    # return chart
    return alt.Chart.from_dict(chart)
# LINEOUTS

# Color scales
n_scale = {
    "domain": ["4", "5", "6", "7"], 
    "range": ["#ca0020", "#f4a582", "#92c5de", "#0571b0"]
}

calls4 = ["Yes", "No", "Snap"]
cols4 = ["#146f14", "#981515", "#981515"]
calls7 = ["A*", "C*", "A1", "H1", "C1", "W1", "A2", "H2", "C2", "W2", "A3", "H3", "C3", "W3"]
cols7 = 2*["orange"] + 4*["#146f14"] + 4*["#981515"] + 4*["orange"]
calls = ["Matlow", "Red", "Orange", "Plus", "Even +", "RD", "Even", "Odd", "Odd +", "Green +", "", "Green"]
cols = 5*["#981515"] + 6*["orange"] + ["#146f14"]

call_scale = {
    "domain": calls4 + calls7 + calls,
    "range": cols4 + cols7 + cols
}
setup_scale = {
    "domain": ["A", "C", "H", "W"],
    "range": ["dodgerblue", "crimson", "midnightblue", "black"]
}
setups = {"A": "Auckland", "C": "Canterbury", "H": "Highlanders", "W": "Waikato"}

# Sort orders
area_order = ["Front", "Middle", "Back"]
area_scale = {
    "domain": area_order, 
    "range": ['#981515', 'orange', '#146f14']
}



def counts(type, squad=1, season=None, df=None):
    
    if df is None:
        df = lineouts()

    df = df[df["Squad"] == ("1st" if squad == 1 else "2nd")]
    if season:
        df = df[df["Season"] == season]

    df = df.groupby([type, "Season"]).agg(
        Won = pd.NamedAgg(column="Won", aggfunc="sum"),
        Lost = pd.NamedAgg(column="Won", aggfunc="sum"),
        Total = pd.NamedAgg(column="Won", aggfunc="count")
    ).reset_index()
    df["Success"] = df.loc[:,"Won"] / df["Total"]
    # Add column of sum(total) for each season
    df["SeasonTotal"] = df.groupby("Season")["Total"].transform("sum")
    df['Proportion'] = df['Total'] / df['SeasonTotal']
    # "Won" / "Total" as a string
    df["SuccessText"] = df.apply(lambda x: str(x["Won"]) + " / " + str(x["Total"]), axis=1)

    return df

def count_success_chart(type, squad=1, season=None, as_dict=False, min=1, df=None):
    
    if df is None:
        df = lineouts()
    
    df = df[df["Squad"] == ("1st" if squad == 1 else "2nd")]
    if season:
        df = df[df["Season"] == season]
    
    with open("lineout-template.json") as f:
        chart = json.load(f)

    if season is None:
        chart["title"]["text"] = f"Lineout Stats by {type}"

        subtitle = {
            "Area": "Area of the lineout targeted",
            "Numbers": "Number of players in the lineout (not including the hooker and receiver)",
            "Jumper": [f"Minimum {min} lineouts", "NOTE: Jumper success is dependent on other factors, such as the throw and lift."],
            "Hooker": [f"Minimum {min} lineouts", "NOTE: Hooker success is dependent on other factors, such as the jumper and lifting pod winning the ball."],
            "Call": [f"Minimum {min} lineouts", "Colour denotes calls to the front (red), middle (orange), or back (green)."],
            "Setup": "Lineout setups introduced in the 2023/24 season - Auckland, Canterbury, Highlanders, Waikato.",
            "Movement": [
                "Type of movements:", 
                "    - 'Jump' - the jumper is lifted where he stands",
                "    - 'Move' - moves to the jumping position after entering the lineout",
                "    - 'Dummy' - there is a dummy jump first"
            ]
        }
        chart["title"]["subtitle"] = subtitle[type]

    chart["spec"]["layer"][0]["layer"][0]["params"][0]["name"] = f"select{type}"
    chart["spec"]["layer"][0]["layer"][0]["params"][0]["select"]["fields"] = [type]
    chart["spec"]["encoding"]["opacity"]["condition"]["param"] = f"select{type}"
    chart["spec"]["encoding"]["x"]["field"] = type
    chart["spec"]["encoding"]["color"]["field"] = type
    chart["spec"]["encoding"]["tooltip"][0]["field"] = type
    chart["resolve"]["scale"]["x"] = "independent"
    chart["resolve"]["scale"]["color"] = "shared"
    chart["transform"][0]["groupby"].append(type)
    chart["transform"][2]["groupby"].append(type)

    # Unique IDs for Jumper/Hooker/Setup/Movement/Call
    df["JumperID"] = df.loc[:,"Jumper"].astype("category").cat.codes
    df["HookerID"] = df.loc[:,"Hooker"].astype("category").cat.codes
    df["SetupID"] = df.loc[:,"Setup"].astype("category").cat.codes
    df["MovementID"] = df.loc[:,"Movement"].astype("category").cat.codes
    df["CallID"] = df.loc[:,"Call"].astype("category").cat.codes
    if type in ["Jumper", "Hooker", "Setup", "Movement", "Call"]:
        chart["transform"].append({"calculate": f"datum.Total + datum.Success + 0.01*datum.{type}ID", "as": "sortcol"})
        chart["transform"][0]["groupby"].append(f"{type}ID")
        chart["transform"][2]["groupby"].append(f"{type}ID")
        

    if type == "Area":
        chart["spec"]["encoding"]["color"]["scale"] = area_scale
        chart["spec"]["encoding"]["color"]["sort"] = "descending"
        chart["spec"]["encoding"]["x"]["sort"] = area_order
        chart["spec"]["encoding"]["x"]["title"] = f"Target {type}"


    if type == "Numbers":
        chart["spec"]["encoding"]["color"]["scale"] = n_scale

    if type in ["Jumper", "Hooker"]:
        if type=="Jumper":
            chart["spec"]["width"]["step"] = 40
        chart["spec"]["encoding"]["color"]["scale"] = {"scheme": "tableau20"}
        chart["spec"]["encoding"]["color"]["sort"] = {"field": "Total", "order": "descending"}
        chart["spec"]["encoding"]["x"]["sort"] = {"field": "sortcol", "order": "descending"}

    if type == "Call":
        chart["spec"]["width"]["step"] = 30 if season is None else 40
        chart["spec"]["encoding"]["x"]["sort"] = {"field": "sortcol", "order": "descending"}
        chart["spec"]["encoding"]["x"]["title"] = None
        chart["spec"]["encoding"]["color"]["scale"] = call_scale
        chart["transform"][0]["groupby"].append("CallType")
        chart["transform"][2]["groupby"].append("CallType")

    if type == "Setup":
        chart["spec"]["encoding"]["x"]["sort"] = {"field": "sortcol", "order": "descending"}
        chart["spec"]["encoding"]["color"]["scale"] = setup_scale
        chart["spec"]["encoding"]["color"]["legend"] = None if season else {"title": "Setup", "orient": "right", "labelExpr": "datum.label == 'A' ? 'Auckland' : (datum.label == 'C' ? 'Canterbury' : (datum.label == 'H' ? 'Highlanders' : 'Waikato'))"}
        chart["transform"].append({"filter": "datum.Setup != null"})
    
    if type == "Movement":
        chart["spec"]["encoding"]["x"]["sort"] = {"field": "sortcol", "order": "descending"}
        chart["spec"]["encoding"]["color"]["scale"] = {"range": ["#981515", "#146f14", "black"]}            
        chart["spec"]["encoding"]["x"]["axis"] = {
            "ticks": False,
            "labelExpr": "datum.label == 'D' ? 'Dummy' : (datum.label == 'M' ? 'Move' : 'Jump')",
            "labelFontSize": 12,
            "labelPadding": 10
        }


    chart["transform"].insert(0, deepcopy(chart["transform"][0]))
    chart["transform"][0]["joinaggregate"][0]["as"] = "TotalOverall"
    chart["transform"][1]["joinaggregate"][0]["as"] = "Total"
    chart["transform"].insert(1, {"filter": f"datum.TotalOverall >= {min}"})

    if season:
        if type == "Call":
            chart["facet"] = {
                "field": "CallType", 
                "header": {"title": "Call", "orient": "bottom"},
                "sort": ["Standard", "4-man only", "6/7-man only"]
            }
        else:
            chart.update(chart["spec"])
            chart["resolve"]["scale"]["x"] = "shared"
            del chart["facet"]
            del chart["spec"]
    
    chart["data"]["values"] = df.to_dict(orient="records")
    
    if as_dict:
        return chart
    else:
        return alt.Chart.from_dict(chart)

def lineout_chart(squad=1, season=None, df=None):

    if df is None:
        df = lineouts()

    df = df[df["Squad"] == ("1st" if squad == 1 else "2nd")]
    if season:
        df = df[df["Season"] == season]

    types = ["Numbers", "Area", "Hooker", "Jumper", "Setup"]

    movement_chart = count_success_chart("Movement", squad, season, df=df)
    movement_chart["transform"][2:2] = [{"filter": {"param": f"select{f}"}} for f in types]
    movement_chart["layer"][1]["encoding"]["y"]["axis"]["labels"] = False
    movement_chart["layer"][1]["encoding"]["y"]["title"] = None

    call_chart = count_success_chart("Call", squad, season, df=df)
    call_chart["transform"][2:2] = [{"filter": {"param": f"select{f}"}} for f in types + ["Movement"]]
    call_chart["spec"]["layer"][0]["encoding"]["y"]["axis"]["labels"] = False
    call_chart["spec"]["layer"][0]["encoding"]["y"]["title"] = None
    
    charts = []
    for i,t in enumerate(types):
        min = 3 if t in ["Hooker", "Jumper"] else 1
        chart = count_success_chart(t, squad, season, as_dict=True, min=min, df=df)

        filters = [{"filter": {"param": f"select{f}"}} for f in types + ["Movement"] if f != t]
        chart["transform"][2:2] = filters

        if i < len(types) - 1:
            chart["layer"][1]["encoding"]["y"]["axis"]["labels"] = False
            chart["layer"][1]["encoding"]["y"]["title"] = None
        
        if i > 0:
            chart["layer"][0]["encoding"]["y"]["axis"]["labels"] = False
            chart["layer"][0]["encoding"]["y"]["title"] = None
        
        charts.append(alt.Chart.from_dict(chart))

    bottom = alt.hconcat(movement_chart, call_chart).resolve_scale(color='independent', y="shared")
    top = alt.hconcat(*charts).resolve_scale(color='independent', y="shared")

    chart = alt.vconcat(top, bottom).resolve_scale(color='independent')

    chart["title"] = {
        "text": f"{'1st' if squad==1 else '2nd'} XV Lineouts",
        "subtitle": [
            "Distribution of lineouts (bar), and success rate (line). Click to highlight and filter.",
            "Success is defined as retaining possession when the lineout ends, and does not distinguish between an unsuccessful throw, a knock-on, or a penalty."
        ]  
    }
    
    return chart


def points_scorers_chart(squad=1, season="2024/25", df=None):

    if df is None:
        df = pitchero_stats()
    if squad != 0:
        df = df[df["Squad"] == ("1st" if squad == 1 else "2nd")]
    if season:
        df = df[df["Season"] == season]
    
    scorers = df[df["Points"] > 0]

    scorers = scorers.drop("Points", axis=1)
    scorers = scorers.melt(
        id_vars=[c for c in scorers.columns if c not in ["Tries", "Pens", "Cons"]], 
        var_name="Type", 
        value_name="Points"
    )

    selection = alt.selection_point(fields=['Type'], bind='legend')

    chart = (
        alt.Chart(scorers)
        .add_params(selection)
        .transform_filter(selection)
        .transform_filter("datum.Points > 0")
        .transform_calculate(label="if(datum.T>0, datum.T + 'T ','') + if(datum.PK>0, datum.PK + 'P ', '') + if(datum.Con>0, datum.Con + 'C ', '')")
        .mark_bar()
        .encode(
            x=alt.X("sum(Points):Q", axis=alt.Axis(orient="top", title="Points")),
            y=alt.Y(
                "Player:N", 
                sort=alt.EncodingSortField(field="sortfield", order="descending"), 
                title=None
            ),
            tooltip=[
                alt.Tooltip("Player:N", title=" "), 
                alt.Tooltip("A:Q", title="Games"),
                alt.Tooltip("label:N", title="Scores"),
                alt.Tooltip("sortfield:Q", title="Points")
            ],
        )
        .transform_joinaggregate(
            sortfield="sum(Points)",    
            groupby=["Type", "Player", "Season", "Squad"]
        )
        .transform_joinaggregate(
            totalpoints="sum(Points)",    
            groupby=["Player", "Season", "Squad"]
        )
        .properties(width=400 if season else 200, height=alt.Step(16))
    )
    
    text = (
        chart    
        .mark_text(align="left", dx=5, color="black")
        .encode(
            y=alt.Y(
                "Player:N", 
                sort=alt.EncodingSortField(field="sortfield", order="descending"), 
                title=None
            ),
            x=alt.X("totalpoints:Q", axis=alt.Axis(orient="bottom", title="Points")),
            text=alt.Text("label:N")
        )
    )

    chart = chart.encode(
        color=alt.Color(
                "Type:N", 
                legend=alt.Legend(
                    title="Click to filter",
                    titleOrient="left",
                    orient="bottom",
                ), 
                scale=alt.Scale(domain=['Tries', 'Pens', 'Cons'], range=["#202947", "#981515", "#146f14"])
            ),
        order=alt.Order("Type:N", sort="descending"),
    )


    chart = (
        (chart + text)
        # chart
        .facet(
            row=alt.Row(
                "Squad:N", 
                header=alt.Header(title=None, labelExpr="datum.value + ' XV'", labelFontSize=36) if squad == 0 else None
            ),
            column=alt.Column(
                "Season:O", 
                header=alt.Header(title=None, labelFontSize=28) if season is None else None, 
            ),
            spacing=20,
            align="each"
        )
        .properties(
            title=alt.Title(
                text=("1st XV " if squad==1 else "2nd XV " if squad==2 else "") + "Points Scorers",
                subtitle="According to Pitchero data"
            )
        )
        .resolve_scale(y="independent")
    )

    return chart

def card_chart(squad=0, season="2024/25", df=None):

    if df is None:
        df = pitchero_stats()
    if squad != 0:
        df = df[df["Squad"] == ("1st" if squad == 1 else "2nd")]
    if season:
        df = df[df["Season"] == season]

    df.loc[:, "Cards"] = df.loc[:,"YC"] + df.loc[:,"RC"]
    df = (df[df["Cards"] > 0])[["Player","A","YC","RC", "Cards", "Season", "Squad"]]
        
    df = df.sort_values(["Season", "Cards", "RC"], ascending=[True, False, True])

    title = f"{'1st XV' if squad==1 else ('2nd XV' if squad==2 else 'Total')} Cards"

    selection = alt.selection_point(fields=["Player"], on="mouseover")

    chart = (
        alt.Chart(df).mark_bar(stroke="black", strokeOpacity=0.2).encode(
            y=alt.Y("Player:N", title=None, sort=alt.EncodingSortField(field="Cards", order="descending")),
            x=alt.X("value:Q", title="Cards", axis=alt.Axis(values=[0,1,2,3,4,5], format="d")),        
            color=alt.Color(
                "key:N", 
                title=None, 
                legend=alt.Legend(orient="bottom")
            ).scale(domain=["YC", "RC"], range=["#e6c719", "#981515"]),
            tooltip=["Player:N", alt.Tooltip("A:Q", title="Appearances"), "YC:Q", "RC:Q", "Squad:N"],
            column=season_column(season),
            opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
        )
        .add_params(selection)
        .transform_fold(["YC", "RC"])
        .resolve_scale(y="independent")
        .properties(
            title=alt.Title(
                text=title, 
                subtitle=[
                    "According to Pitchero data", 
                    "2 YC leading to a RC in a game is shown as 1 YC + 1 RC (2 cards total)"
                ]
            ), 
            width=200 if season else 120
        )
    )

    return chart

def captains_chart(season="2024/25", df=None):

    if df is None:
        df = team_sheets()
    
    df = df.rename(columns={"VC1":"VC"})

    captains = df[["Squad", "Season", "Captain", "VC", "GameType"]].melt(
        id_vars=["Squad", "Season", "GameType"], 
        value_vars=["Captain", "VC"],
        var_name="Role",
        value_name="Player"
    ).dropna()
        
    if season:
        captains = captains[captains["Season"]==season]

    chart = (
        alt.Chart(captains)
        .mark_bar()
        .encode(
            y=alt.X("Player:N", title=None, sort="-x"),
            x=alt.X("count()", title="Games", sort=alt.EncodingSortField(field="Role", order="descending")),
            color=alt.Color("Role:N",
                scale=alt.Scale(domain=["Captain", "VC"], range=["#202947", "#146f14"]),
                legend=alt.Legend(title=None, direction="horizontal", orient="bottom")
            ), 
            row=squad_row(0),
            column=season_column(season),
            order=alt.Order("order:N", sort="ascending"),
            opacity=alt.condition("datum.GameType == 'Friendly'", alt.value(0.5), alt.value(1)),
            tooltip=[
                alt.Tooltip("Player:N", title="Player"),
                alt.Tooltip("count()", title="Games"),
                alt.Tooltip("Role:N", title="Role"),
                alt.Tooltip("GameType:N", title="Game Type"),
            ]
        )
        .transform_calculate(order = "(datum.Role=='Captain' ? 'a' : 'b') + (datum.GameType == 'Friendly' ? 'b' : 'a')")
        .properties(
            title=alt.Title("Match Day Captains", subtitle="Captains and Vice-Captains (if named). Friendly games are shaded lighter."),
            width=400 if season else 250,
        )
        .resolve_scale(x="shared", y="independent", opacity="shared")
    )

    return chart

def results_chart(squad=1, season=None, df=None):

    if df is None:
        df = team_sheets()

    if season is not None:
        df = df[df["Season"]==season]
    if squad != 0:
        df = df[df["Squad"]==("1st" if squad==1 else "2nd")]

    df.loc[:,"loser"] = df.apply(lambda x: x["PF"] if x["Result"] == "L" else x["PA"], axis=1)
    df.loc[:,"winner"] = df.apply(lambda x: x["PF"] if x["Result"] == "W" else x["PA"], axis=1)

    selection = alt.selection_point(fields=['Result'], bind='legend')
    base = alt.Chart(df).encode(
        y=alt.Y(
            'GameID:N', 
            sort=None, 
            axis=alt.Axis(
                title=None, 
                offset=15, 
                grid=False, 
                ticks=False, 
                domain=False, 
                # labelExpr="split(datum.value,'-__-')[1]"
            )
        ),
        color=alt.Color(
            'Result:N', 
            scale=alt.Scale(domain=['W', 'L'], range=['#146f14', '#981515']), 
            legend=alt.Legend(offset=20, orient="bottom", title="Click to highlight", titleOrient="left")
        ),
        opacity=alt.condition(
            selection, 
            # alt.condition(team_filter, alt.value(1), alt.value(0.2)), 
            alt.value(1),
            alt.value(0.2)
        )
    )

    bar = base.mark_bar(point=True).encode(
        x=alt.X('PF:Q', title="Points", axis=alt.Axis(orient='bottom', offset=5)),
        x2='PA:Q'
    ).properties(height=alt.Step(15), width=400)

    loser = base.mark_text(align='right', dx=-2, dy=0).encode(
        x=alt.X('loser:Q', title=None, axis=alt.Axis(orient='top', offset=5)),
        text='loser:N',
        color=alt.value('black')
    )

    winner = base.mark_text(align='left', dx=2, dy=0).encode(
        x=alt.X('winner:Q', title=None, axis=alt.Axis(orient='top', offset=5)),
        text='winner:N',
        color=alt.value('black')
    )

    chart = (
        (bar + loser + winner)
        .add_params(selection, team_filter)
        .facet(
            row=squad_row(squad), 
            column=season_column(season)
        )
        .resolve_scale(y='independent')
        .properties(
            title=alt.Title(
                text=f"{('1st XV ' if squad==1 else ('2nd XV ' if squad==2 else ''))}Results",
                subtitle=[
                    "Match scores visualised by winning margin. Small bars reflect close games, colour reflects the result.",
                    "Click the legend to highlight wins or losses. Click a bar to highlight results against that team."  
                ],
                offset=20
            )
        )
    )
    
    return chart

seasons = ["2021/22", "2022/23", "2023/24", "2024/25"]

turnover_filter = alt.selection_point(fields=["Turnover"], bind="legend")
put_in_filter = alt.selection_point(fields=["Team"], bind="legend")
team_filter = alt.selection_point(fields=["Opposition"])

color_scale = alt.Scale(domain=["EG", "Opposition"], range=["#202946", "#981515"])
opacity_scale = alt.Scale(domain=["Turnover", "Retained"], range=[1, 0.5])

def set_piece_h2h_chart(squad, season=None, df=None):
    
    if df is None:
        df = set_piece_results()

    if season is not None:
        df = df[df["Season"]==season]

    df = df[df["Squad"]==("1st" if squad==1 else "2nd")]

    base = (
        alt.Chart(df).encode(
            y=alt.Y(
                "GameID:N", 
                axis=None, 
                sort=alt.EncodingSortField(field="Date", order="ascending"), 
                scale=alt.Scale(padding=0)
            ),
            yOffset=alt.YOffset(
                "Team:N",
                scale=alt.Scale(paddingOuter=0.2)
            ),
            color=alt.Color(
                "Team:N", 
                scale=color_scale, 
                legend=alt.Legend(
                    title="Attacking team",
                    orient="bottom", 
                    direction="horizontal",
                )
            ),
            opacity=alt.Opacity(
                "Turnover:N", 
                scale=opacity_scale, 
                legend=alt.Legend(
                    title="Result", 
                    orient="bottom", 
                    direction="horizontal",
                )
            ),
            tooltip=[
                alt.Tooltip("Opposition:N", title="Opposition"),
                alt.Tooltip("Date:T", title="Date"),
                alt.Tooltip("Team:N", title="Attacking team"),
                alt.Tooltip("Winner:N"),
                "Count:Q",
            ]
        )
        .properties(height=alt.Step(10), width=120)
    )

    eg = (
        base.mark_bar(stroke="#202946", )
        .encode(
            x=alt.X(
                "Count:Q",
                axis=alt.Axis(title="EG wins", orient="top", titleColor="#202946"),
                scale=alt.Scale(domain=[0, df["Count"].max()]),
            )
        )
        .transform_filter("datum.Winner == 'EG'")
    )
    opp = (
        base.mark_bar(stroke="#981515")
        .encode(
            x=alt.X(
                "Count:Q",
                scale=alt.Scale(domain=[0, df["Count"].max()], reverse=True),
                axis=alt.Axis(title="Opposition wins", orient="top", titleColor="#981515")
            ),
            y=alt.Y(
                "GameID:N", 
                title=None, 
                axis=alt.Axis(orient="left"), 
                sort=alt.EncodingSortField(field="Date", order="ascending"),
                scale=alt.Scale(padding=0)
            ),
        )
        .transform_filter("datum.Winner == 'Opposition'")
    )

    chart = (
        alt.hconcat(opp, eg, spacing=0)
        .resolve_scale(yOffset="independent")
    )

    return chart

def set_piece_h2h_charts(squad, season=None, df=None):

    chart = set_piece_h2h_chart(squad, season, df)

    if season is not None:
        df = df[df["Season"]==season]
    if squad > 0:
        df = df[df["Squad"]==("1st" if squad==1 else "2nd")]

    seasons = df["Season"].unique()

    scrum_panels = []
    lineout_panels = []
    for s in seasons:
        scrum = chart.transform_filter(f"datum.Season == '{s}' & datum.SetPiece == 'Scrum'")
        lineout = chart.transform_filter(f"datum.Season == '{s}' & datum.SetPiece == 'Lineout'")

        if len(seasons)>1:
            title=alt.Title(text=s, anchor="middle", orient="top", fontSize=36)
            scrum = scrum.properties(title=title)
            # lineout = lineout.properties(title=title)

        scrum_panels.append(scrum)
        lineout_panels.append(lineout)

    
    lineout_chart = alt.hconcat(*lineout_panels).resolve_scale(
        x="shared", color="shared", y="independent", opacity="shared", yOffset="shared"
    )

    scrum_chart = alt.hconcat(*scrum_panels).resolve_scale(
        x="shared", color="shared", y="independent", opacity="shared"
    )

    if squad>0:
        titles=[alt.Title(
                    text=t, 
                    anchor="middle",
                    align="left" if season is None else "center", 
                    orient="left" if season is None else "top", 
                    fontSize=60 if season is None else 36
                ) for t in ["Scrum", "Lineout"]]
        scrum_chart = scrum_chart.properties(title=titles[0])
        lineout_chart = lineout_chart.properties(title=titles[1])
        
    if season is not None:
        lineout_chart.hconcat[0].hconcat[0].encoding.y.axis = None
        lineout_chart = lineout_chart.properties(title = alt.Title(text="Lineout", anchor="middle", fontSize=36))
        scrum_chart = scrum_chart.properties(title = alt.Title(text="Scrum", anchor="middle", fontSize=36))
        final_chart = alt.hconcat(scrum_chart, lineout_chart, spacing=10).resolve_scale(y="shared")
    else:
        final_chart = alt.vconcat(scrum_chart, lineout_chart, spacing=30).resolve_scale(y="shared")

    return (
        final_chart
        .add_params(turnover_filter, put_in_filter, team_filter)
        .transform_filter(turnover_filter)
        .transform_filter(put_in_filter)
        .transform_filter(team_filter)
        .properties(
            title=alt.Title(
                text=f"{'1st XV ' if squad==1 else ('2nd XV ' if squad==2 else '')}Set Piece Head-to-Head Results",
                subtitle=[
                    "Numbers of set piece and turnovers for both teams in each game.", 
                    "Click the legends to view only turnovers.", 
                    "Click the bar charts to select all games against that specific opposition."
                ]
            )
        )
    )

def squad_set_piece_chart(squad=0, season=None, df=None):
    if squad == 0:
        c1 = set_piece_h2h_charts(squad=1, season=season, df=df)
        c2 = set_piece_h2h_charts(squad=2, season=season, df=df)

        c1 = c1.properties(title=alt.Title(text="1st XV", orient="left", anchor="middle", align="right"))
        c2 = c2.properties(title=alt.Title(text="2nd XV", orient="left", anchor="middle", align="right"))

        chart = alt.vconcat(c1, c2, spacing=50).properties(
            title=alt.Title(
                text=f"Set Piece Head-to-Head Results", 
                subtitle=[
                    "Numbers of set piece and turnovers for both teams in each game.", 
                    "Click the legends to view only turnovers.", 
                    "Click the bar charts to select all games against that specific opposition."
                ]
            )
        )
    else:
        chart = set_piece_h2h_charts(squad, season, df)

    return chart


###########################
### VIDEO ANALYSIS CHARTS
###########################

game_selection = alt.selection_point(fields=["Game"], on="click")

def territory_chart(df):
    game_order = df.sort_values(by="Date")["Game"].unique().tolist()
    territory_cols = ["Own 22m (%)", "22m - Half (%)", "Half - 22m (%)", "Opp 22m (%)"]
    df = df[df["Metric"].isin(territory_cols)]
    
    chart = (
        alt.Chart(df)
        .add_params(game_selection)
        .transform_window(
            frame=[None, 0],
            cumulative_value="sum(Value)",
            groupby=["Date"]
        )
        .transform_calculate(
            text_pos="datum.cumulative_value - datum.Value/2",
            territory="replace(datum.Metric, ' (%)', '')",
        )
        .mark_bar()
        .encode(
            y=alt.Y("Game:O", sort=game_order, title=None),
            x=alt.X("sum(Value):Q", title="Percentage", stack="normalize", axis=None),
            color=alt.Color(
                "territory:N", 
                scale=alt.Scale(
                    domain=["Own 22m", "22m - Half", "Half - 22m", "Opp 22m"],
                    range=["#981515", "#da8", "#ad8", "#146f14"]
                ),
                legend=alt.Legend(
                    title="Territory",
                    titleOrient="left", 
                    orient="bottom", 
                    titlePadding=20
                )
            ),
            order=alt.Order("stack_order:O"),
            opacity=alt.condition(game_selection, alt.value(1), alt.value(0.4)),
            tooltip=[
                alt.Tooltip("Game:N"),
                alt.Tooltip("Date:T"),
                alt.Tooltip("territory:N", title="Territory"),
                alt.Tooltip("Value:Q", title="Percentage", format=".0%")
            ]
        )
        .properties(
            title=alt.Title(
                text="Territory",
                subtitle="Ball in play time by area of the pitch.",
                anchor="middle",
                fontSize=36
            ),
            width=450,
            height=alt.Step(35)
        )
    )

    # Add text overlay to bars showing the percentage 
    text = (
        chart
        .mark_text(align="center", baseline="middle", fontSize=20, fontWeight="bold")
        .encode(
            x=alt.X("text_pos:Q", axis=None),
            text=alt.Text("sum(Value):Q", format=".0%"),
            color=alt.Color(
                "territory:N", 
                scale=alt.Scale(
                    range=["white", "black", "black", "white"], 
                    domain=["Own 22m", "22m - Half", "Half - 22m", "Opp 22m"]
                ),
                legend=None
            )
        )
    )

    # Add vertical rule on 0.5 to show the 50% mark
    rule = (
        alt.Chart(pd.DataFrame({"x": [0.5]}))
        .mark_rule(color="black", strokeDash=[5,5])
        .encode(
            x=alt.X("x:Q", axis=None)
        )
    )

    return (chart + text + rule).resolve_scale(color="independent")

def tackle_chart(df, axis=True):
    game_order = df.sort_values(by="Date")["Game"].unique().tolist()
    df = df[df["Metric"].isin(["Tackles Made", "Tackles Missed"])]
    
    chart = (
        alt.Chart(df)
        .add_params(game_selection)
        .transform_joinaggregate(
            total="sum(Value)",
            groupby=["Date"]
        )
        .transform_calculate(
            percentage="datum.Value/datum.total",
            opacity="datum.Metric == 'Tackles Made' ? sqrt(datum.percentage) : 1.0",
            text_pos="datum.Metric == 'Tackles Made' ? datum.percentage/2 : 1 - datum.percentage/2",
        )
        .mark_bar()
        .encode(
            y=alt.Y("Game:O", sort=game_order, title=None),
            x=alt.X("Value:Q", stack="normalize", title="Tackle Success (%)"),
            color=alt.Color(
                "Metric:N", 
                scale=alt.Scale(
                    domain=["Tackles Made", "Tackles Missed"], 
                    range=["#146f14", "#981515"]
                ), 
                legend=alt.Legend(
                    title="Tackles",
                    titleOrient="left", 
                    orient="bottom",
                    labelExpr="split(datum.label, ' ')[1]",
                    titlePadding=20
                )
            ),
            opacity=alt.condition(game_selection, alt.value(1), alt.value(0.4)),
            tooltip=[
                alt.Tooltip("Game:N"),
                alt.Tooltip("Date:T"),
                alt.Tooltip("Value:Q", title="Tackles"),
                alt.Tooltip("percentage:Q", title="Percentage", format=".0%")
            ]
        )
        .properties(
            title=alt.Title(
                text="Tackles", 
                subtitle="Tackles made and tackles missed", 
                anchor="middle",
                fontSize=36
            ),
            width=300,
            height=alt.Step(35)
        )
    )

    if not(axis):
        chart.encoding.y.axis = None

    text = (
        chart
        .mark_text(align="center", baseline="middle", fontSize=20, fontWeight="bold", color="white")
        .encode(
            x=alt.X("text_pos:Q", axis=None),
            text=alt.Text("percentage:Q", format=".0%"),
            color=alt.value("white")
        )
    )
    return (chart + text).resolve_scale(color="independent")

def playmaker_chart(df, axis=True):
    game_order = df.sort_values(by="Date")["Game"].unique().tolist()
    df = df[df["Metric"].isin(["Off 9 (%)", "Off 10 (%)", "Off 12 (%)"])]

    chart = (
        alt.Chart(df)
        .add_params(game_selection)
        .transform_window(
            frame=[None, 0],
            cumulative_value="sum(Value)",
            groupby=["Date"]
        )
        .transform_calculate(
            text_pos="datum.cumulative_value - datum.Value/2",
            playmaker="toNumber(split(datum.Metric, ' ')[1])"
        )
        .mark_bar()
        .encode(
            y=alt.Y("Game:O", sort=game_order, title=None),
            x=alt.X("sum(Value):Q", title="Percentage", stack="normalize", axis=None),
            color=alt.Color(
                "playmaker:O", 
                legend=alt.Legend(title="Playmaker", orient="bottom", titleOrient="left", titlePadding=20),
                scale=alt.Scale(
                    range=["#d0b060", "#b06030", "#981515"],
                )
            ),
            order=alt.Order("stack_order:O"),
            opacity=alt.condition(game_selection, alt.value(1), alt.value(0.4)),
            tooltip=[
                alt.Tooltip("Game:N"),
                alt.Tooltip("Date:T"),
                alt.Tooltip("playmaker:N", title="Playmaker"),
                alt.Tooltip("Value:Q", title="Percentage", format=".0%")
            ]
        )
        .properties(
            title=alt.Title(
                text="Playmakers",
                subtitle="Distribution of plays off 9, 10 or 12",
                anchor="middle",
                fontSize=36,
            ),
            width=350,
            height=alt.Step(35)
        )
    )

    if not(axis):
        chart.encoding.y.axis = None

    # Add text overlay to bars showing the percentage
    text = (
        chart
        .mark_text(align="center", baseline="middle", fontSize=20, fontWeight="bold")
        .encode(
            x=alt.X("text_pos:Q", axis=None),
            text=alt.Text("sum(Value):Q", format=".0%"),
            color=alt.Color(
                "playmaker:O", 
                scale=alt.Scale(
                    range=["black", "white", "white"], 
                    domain=[9, 10, 12]
                ),
                legend=None
            ),
            opacity=alt.condition(game_selection, alt.value(1), alt.value(0.4))
        )
    )

    return (chart + text).resolve_scale(color="independent", x="shared")

def penalties_chart(df, axis=True):
    game_order = df.sort_values(by="Date")["Game"].unique().tolist()
    penalty_cols = [
        "Penalties For", 
        "Ruck Attack",
        "Ruck Defence",
        "Scrum",
        "Lineout",
        "Maul",
        "Offside",
        "Foul play",
        "Tackle",
        "Blocking"
    ]

    penalties = df[df["Metric"].isin(penalty_cols)]
    penalties.loc[:,"stack_order"] = penalties.loc[:,"Metric"].apply(lambda x: penalty_cols.index(x))

    penalties.loc[:,"Offence"] = penalties.loc[:,"Metric"].apply(lambda x: "Total" if x == "Penalties For" else x)
    penalties.loc[:,"Team"] = penalties.loc[:,"Metric"].apply(lambda x: "Won" if x == "Penalties For" else "Conceded")

    # Generate list of 9 discrete colors from "yelloworangered" diverging color scheme
    colors = [
        "#146f14", # Penalties For
        "#611", # Ruck Attack
        "#981515", # Ruck Defence
        "#b33", # Scrum
        "#c63", # Lineout
        "#d64", # Maul
        "#e85", # Offside
        "#fa6", # Foul play
        "#fc7", # Tackle
        "#fd9" # Blocking
    ]

    metric_selection = alt.selection_multi(fields=["Metric"], bind="legend")

    chart = (
        alt.Chart(penalties)
        .add_params(game_selection)
        .add_params(metric_selection)
        .transform_calculate(offset="datum.Metric == 'Penalties For' ? -1 : 1")
        .transform_window(
                frame=[None, 0],
                cumulative_value="sum(Value)",
                groupby=["Date", "offset", "Team"]
        )
        .transform_calculate(text_pos="datum.cumulative_value - datum.Value/2")
        .mark_bar()
        .encode(
            x=alt.X("Value:Q", title=None),
            y=alt.Y("Game:O", sort=game_order, title=None),
            color=alt.Color(
                "Metric:N", 
                scale=alt.Scale(domain=penalty_cols, range=colors),
                sort=penalty_cols,
                legend=alt.Legend(
                    title=["Penalty", "Offence"], 
                    titlePadding=10,
                    titleFontSize=14,
                    titleOrient="left",
                    orient="bottom", 
                    values=penalty_cols[1:], 
                    labelFontSize=12,
                    columns=3
                )
            ),
            order=alt.Order("stack_order:Q", sort="ascending"),
            opacity=alt.condition(game_selection, alt.value(1), alt.value(0.4)),
            tooltip=[
                alt.Tooltip("Game:N"),
                alt.Tooltip("Date:T"),
                alt.Tooltip("Team:N", title="Penalties"),
                alt.Tooltip("Offence:N"),
                alt.Tooltip("Value:Q", title="Count")
            ]
        )
        .properties(
            width=250,
            height=alt.Step(35)
        )
    )

    if not(axis):
        chart.encoding.y.axis = None

    # Add text labels to the bars
    text = (
        alt.Chart(penalties)
        .transform_calculate(offset="datum.Metric == 'Penalties For' ? -1 : 1")
        .transform_window(
                frame=[None, 0],
                cumulative_value="sum(Value)",
                groupby=["Date", "offset"]
        )
        .transform_calculate(text_pos="datum.cumulative_value - datum.Value/2")
        .mark_text(align="center", baseline="middle", fontSize=18)
        .encode(
            y=alt.Y("Game:O", sort=game_order, title=None),
            text=alt.condition(
                alt.datum.Value > 0,
                alt.Text("Value:Q", format="d"),
                alt.value("")
            ),
            x=alt.X("text_pos:Q"),
            color=alt.value("white"),
            opacity=alt.value(0.8)
        )
    )

    return (
        (chart + text)
        .transform_filter(metric_selection)
        .resolve_scale(opacity="independent", y="shared", x="shared")
        .facet(column=alt.Column("Team:O", header=alt.Header(title=None), sort=["Won", "Conceded"]), spacing=5)
        .resolve_scale(x="shared", y="shared")
        .properties(
            title=alt.Title(
                text="Penalty Counts",
                subtitle="Penalty counts by offence (click on legend to filter).",
                anchor="middle",
                fontSize=36
            )
        )
    )


def efficiency_chart(df, axis=True):
    game_order = df.sort_values(by="Date")["Game"].unique().tolist()
    efficiency_cols = [
        "Opposition Entries", 
        "Opposition Tries", 
        "Opposition Efficiency (%)",
        "Attacking Entries",
        "Attacking Tries",
        "Attacking Efficiency (%)",
    ]
    id_cols = ["Date", "Game", "Opposition", "Home/Away"]
    
    df = df[df["Metric"].isin(efficiency_cols)]

    df.loc[:,"Team"] = df.loc[:,"Metric"].str.split(" ", expand=True)[0]
    df.loc[:,"Metric"] = df.loc[:,"Metric"].str.split(" ", expand=True)[1]
    df = df.pivot(index=id_cols + ["Team"], columns="Metric", values="Value").reset_index()

    # Replace "Attacking" with "EG"
    df.loc[:,"Team"] = df.loc[:,"Team"].replace("Attacking", "EG")

    df.loc[:,"label"] = df.loc[:,"Tries"] + "T / " + df["Entries"]

    chart = (
        alt.Chart(df)
        .add_params(game_selection)
        .mark_bar()
        .encode(
            x=alt.X("Efficiency", axis=alt.Axis(title="Conversion Rate (%)", format=".0%"), scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("Game:O", sort=game_order, title=None),
            color=alt.Color(
                "Team", 
                scale=alt.Scale(domain=["Opposition", "EG"], range=["#981515", "#202946"]),
                legend=None
            ),
            opacity=alt.condition(game_selection, alt.value(1), alt.value(0.4)),
            tooltip=[
                alt.Tooltip("Game:N"),
                alt.Tooltip("Date:T"),
                alt.Tooltip("Team:N"),
                alt.Tooltip("Entries:Q", title="22m Entries"),
                alt.Tooltip("Tries:Q"),
            ]
        )
        .properties(
            width=250,
            height=alt.Step(35)
        )
    )

    if not(axis):
        chart.encoding.y.axis = None

    text1 = (
        chart
        .mark_text(fontSize=16, align="right", baseline="middle", dx=-5)
        .encode(text=alt.Text("Efficiency:Q", format=".0%"), color=alt.value("white"))
    )

    text2 = chart.mark_text(fontSize=12, align="left", baseline="middle", dx=5).encode(text=alt.Text("label:N"))

    return (
        (chart + (text1 + text2))
        .facet(column=alt.Column("Team:O", sort=["Opposition", "EG"], header=alt.Header(title=None)), spacing=5)
        .resolve_scale(x="shared")
        .properties(
            title=alt.Title(
                text="Red Zone Efficiency", 
                subtitle="Conversion rate of 22m entries into tries",
                anchor="middle",
                fontSize=36
            ),
        )
    )

def score_chart(df):

    df = df[df["Metric"].isin(["PF", "PA"])]

    max_score = df["Value"].astype(int).max() + 10
    game_order = df.sort_values(by="Date")["Game"].unique().tolist()

    df = df.pivot(index="Game", columns="Metric", values="Value").reset_index()
    df.loc[:,"Result"] = df.apply(lambda x: "W" if x["PF"] > x["PA"] else ("D" if x["PF"] == x["PA"] else "L"), axis=1)

    pf = (
        alt.Chart(df)
        .add_params(game_selection)
        .mark_bar(color="#202947")
        .encode(
            x=alt.X("PF:Q", title="Points For", scale=alt.Scale(domain=[0, max_score])),
            y=alt.Y("Game:N", sort=game_order, axis=None),
            tooltip=["Date:T", "Game", "PF", "PA"],
            opacity=alt.condition(game_selection, alt.value(1), alt.value(0.2)),
            fill=alt.condition(alt.datum.Result == "W", alt.value("#202947"), alt.value("#20294780")),
            stroke=alt.value("#202947")
        )
        .properties(
            width=200,
            height=alt.Step(35)
        )
    )
    pa = (
        alt.Chart(df)
        .mark_bar(color="#981515")
        .encode(
            x=alt.X("PA:Q", title="Points Against", scale=alt.Scale(reverse=True, domain=[0, max_score])),
            y=alt.Y("Game:N", sort=game_order, title=None),
            tooltip=["Date:T", "Game", "PF", "PA"],
            opacity=alt.condition(game_selection, alt.value(1), alt.value(0.2)),
            fill=alt.condition(alt.datum.Result == "L", alt.value("#981515"), alt.value("#98151580")),
            stroke=alt.value("#981515")
        )
        .properties(width=200, height=alt.Step(35))
    )
    pa_text = pa.mark_text(dx=-20, dy=3, fontSize=18).encode(text="PA:Q", fill=alt.value("#981515"))
    pf_text = pf.mark_text(dx=20, dy=3, fontSize=18).encode(text="PF:Q", fill=alt.value("#202947"))

    return (
        ((pa + pa_text) | (pf + pf_text))
        .add_params(game_selection)
        .properties(
            spacing=0,
            title=alt.Title(
                text="Scores", 
                subtitle="Points for and against EG. Winning team shaded darker.", 
                anchor="middle",
                fontSize=36
            )
        )
    )


def gainline_chart(df, axis=True):
    
    game_order = df.sort_values(by="Date")["Game"].unique().tolist()

    chart = (
        alt.Chart(df[df["Metric"].isin(["Gain line +", "Gain line -"])])
        .add_params(game_selection)
        .transform_joinaggregate(
            total="sum(Value)",
            groupby=["Date"]
        )
        .transform_calculate(
            gain_line="datum.Metric == 'Gain line +' ? 'Yes' : 'No'",
            percentage="datum.Value/datum.total",
            text_pos="datum.Metric == 'Gain line +' ? datum.percentage/2 : 1 - datum.percentage/2",
        )
        .mark_bar()
        .encode(
            opacity=alt.condition(game_selection, alt.value(1), alt.value(0.2)),
            y=alt.Y("Game:O", sort=game_order, title=None),
            x=alt.X("Value:Q", title=None, stack="normalize", axis=None),
            color=alt.Color(
                "gain_line:N", 
                scale=alt.Scale(
                    range=["#146f14", "#981515"], 
                    domain=["Yes", "No"]
                ),
                sort=["Yes", "No"],
                legend=alt.Legend(orient="bottom", title="Gain line?", titleOrient="left", titlePadding=20)
            ),
            order=alt.Order("stack_order:O"),
            tooltip=[
                "Game",
                "Date",
                alt.Tooltip("gain_line:N", title="Gain line?"),
                alt.Tooltip("Value:Q", title="Plays"),
                alt.Tooltip("percentage:Q", title="Gain line success", format=".0%")
            ]
        ).properties(
            width=300,
            height=alt.Step(35)
        )
    )

    if not(axis):
        chart.encoding.y.axis = None

    text = (
        chart
        .mark_text(align="left", baseline="middle", fontSize=18)
        .encode(
            x=alt.X("text_pos:Q"),
            text=alt.Text("Value:Q"),
            color=alt.value("white")
        )
    )

    return (chart + text).resolve_scale(color="independent").properties(
        title=alt.Title(
            text="Gain Line Success",
            subtitle="Starter plays that broke the gain line or otherwise.",
            anchor="middle",
            fontSize=36
        )
    )

def game_stats_charts(df):
    score=score_chart(df)
    territory=territory_chart(df)
    tackle=tackle_chart(df, axis=False)
    playmaker=playmaker_chart(df, axis=False)
    penalties=penalties_chart(df, axis=False)
    efficiency=efficiency_chart(df, axis=False)
    gainline=gainline_chart(df, axis=False)

    a=alt.hconcat(score, efficiency, penalties, spacing=30).resolve_scale(color="independent")
    b=alt.hconcat(territory, tackle, playmaker, gainline, spacing=30).resolve_scale(color="independent")

    chart = (a & b).properties(
        spacing=40,
        title=alt.Title(
            text="1st XV Video Analysis", 
            fontSize=64,
            subtitle=["Performance metrics from video analysis on Veo / live streams.", "Click on any chart to highlight a single game throughout all other charts."],
            subtitleFontSize=14,
            color="#202946"
        )
    )
    return chart
