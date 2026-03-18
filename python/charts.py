import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json
import altair as alt
import pandas as pd
from python.data_prep import *
from python.chart_helpers import hack_params_css, alt_theme
from copy import deepcopy
import os
from bs4 import BeautifulSoup

pitchero_caveat = f"Using Pitchero data from 2017 to 2019/20. Manually updated records from 2021 onwards"

alt.themes.register("my_custom_theme", alt_theme)
alt.themes.enable("my_custom_theme")

game_type_scale = alt.Scale(
    domain=["League", "Cup", "Friendly", "NA"],
    range=["#202947", "#981515", "#146f14", "#20294780"]                
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

def plot_starts_by_position(df=None, min=0, file=None):

    # legend selection filter
    legend = alt.selection_point(fields=["GameType"], bind="legend", on="click")

    season_selection = alt.param(
        bind=alt.binding_radio(options=["All", *seasons[::-1]], name="Season"), 
        value=max(seasons) 
    )
    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Total"], name="Squad"),
        value="Total"
    )

    min_selection = alt.param(
        bind=alt.binding_range(name="Minimum Starts", min=1, max=20, step=1),
        value=min
    )

    chart = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/players.json',"format":{'type':"json"}})
        .mark_bar()
        .encode(
            x=alt.X('count()', axis=alt.Axis(title=None, orient="top")),
            y=alt.Y('Player:N', sort='-x', title=None),
            facet=alt.Facet(
                "Position:O", 
                columns=4,  
                header=alt.Header(title=None, labelFontSize=36, labelOrient="top"), 
                spacing=0, 
                sort=position_order,
                align="each"
            ),
            tooltip=[
                "Player:N", 
                "Position:N", 
                alt.Tooltip("count()", title="Starts"), 
                'GameType:N',
                "Rank:N",
            ],      
            color=alt.Color(
                "GameType:N",
                scale=game_type_scale,
                legend=alt.Legend(title=None, orient="bottom", direction="horizontal", titleOrient="left")
            ),
            order=alt.Order('GameType:N', sort='descending'),
            opacity=alt.condition(
                "(datum.Rank <= 3 && (datum.Position == 'Back Row' | datum.Position == 'Back Three')) || (datum.Rank <= 2 && (datum.Position == 'Prop' | datum.Position == 'Second Row' || datum.Position == 'Centre' )) || datum.Rank <= 1",
                alt.value(1),
                alt.value(0.5)
            )
        )
        .resolve_scale(y="independent", x="independent")
        .transform_filter("datum.Number <= 15")
        .properties(width=150, height=alt.Step(14), title=alt.Title(text="Starts by Position)", subtitle="Not including bench appearances."))
        .add_params(legend, season_selection, squad_selection, min_selection)
        .transform_joinaggregate(TotalGames="count()", groupby=["Player", "Position"])
        .transform_window(
            Rank="rank(count())",
            groupby=["Position"],
            sort=[alt.SortField("count()", order="descending")]
        )
        .transform_filter(f"datum.TotalGames >= {min_selection.name}")
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Total'")
        .transform_filter(legend)
        .transform_joinaggregate(Games="count()", groupby=["Player", "Position"])
        .transform_window(
            Rank="dense_rank(Games)",
            groupby=["Position"],
            sort=[{"field": "Games", "order": "descending"}]
        )
    )
    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        if str(file).lower().endswith('.html'):
            hack_params_css(file)

    return chart  


def plot_games_by_player(min=5, df=None, file=None):
    # Use optimized data if df not provided
    if df is None:
        df = players_agg_optimized()

    c = alt.Color(
        "GameType:N",
        scale=game_type_scale,
        legend=alt.Legend(title=None, orient="bottom", direction="horizontal", titleOrient="left")
    )

    # legend selection filter
    legend = alt.selection_point(fields=["GameType"], bind="legend", on="click")

    season_selection = alt.param(
        bind=alt.binding_select(options=["All", *seasons[::-1], *seasons_hist[::-1]], name="Season"), 
        value=max(seasons), 
    )
    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Total"], name="Squad"),
        value="Total"
    )

    min_selection = alt.param(
        bind=alt.binding_range(name="Minimum Games", min=1, max=20, step=1),
        value=min
    )

    chart = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/players_agg.json',"format":{'type':"json"}})
        .mark_bar(strokeWidth=2)
        .encode(
            x=alt.X("Games:Q", axis=alt.Axis(title=None, orient="top")),
            y=alt.Y("Player:N", sort="-x", title=None),
            color=c,
            order="order:Q",
            tooltip=[
                "Player:N", 
                "GameType:N",
                "Games:Q",
                "Total:Q",
                "order:Q"
            ]
        )
        .add_params(season_selection, squad_selection, min_selection, legend)
        .resolve_scale(y="independent")
        .transform_calculate(
            Cup="datum.CupStarts + datum.CupBench",
            League="datum.LeagueStarts + datum.LeagueBench",
            Friendly="datum.FriendlyStarts + datum.FriendlyBench",
            NA="datum.TotalGames - datum.Cup - datum.League - datum.Friendly",
        )
        .transform_fold(["Cup", "League", "Friendly", "NA"], as_=["GameType", "Games"])
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Total'")
        .transform_aggregate(Games="sum(Games)", groupby=["Player", "GameType"])
        .transform_joinaggregate(Total="sum(Games)", groupby=["Player"])
        .transform_filter(f"datum.Total >= {min_selection.name}")
        .transform_calculate(order="datum.GameType == 'League' ? 0 : (datum.GameType == 'Cup' ? 1 : 2)")
        .transform_filter(legend)
        .properties(
            title=alt.Title(
                text=f"Appearances",
                subtitle=pitchero_caveat,
                subtitleFontStyle="italic"  
            ),
            width=400,
            height=alt.Step(15)
        )
    )
    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        if str(file).lower().endswith('.html'):
            hack_params_css(file)

    return chart

# LINEOUTS

calls4 = ["Yes", "No", "Snap"]
cols4 = ["#146f14", "#981515", "#981515"]
calls7 = ["A*", "C*", "A1", "H1", "C1", "W1", "A2", "H2", "C2", "W2", "A3", "H3", "C3", "W3"]
cols7 = 2*["orange"] + 4*["#146f14"] + 4*["#981515"] + 4*["orange"]
calls = ["Matlow", "Red", "Orange", "Plus", "Even +", "RD", "Even", "Odd", "Odd +", "Green +", "", "Green"]
cols = 5*["#981515"] + 6*["orange"] + ["#146f14"]

sort_orders = {
    "Area": ["Front", "Middle", "Back"],
    "Numbers": ["4", "5", "6", "7"],
    "Setup": ["A", "C", "H", "W"],
    "Movement": ["Jump", "Move", "Dummy"],
}

color_scales = {
    "Area": alt.Scale(domain=sort_orders["Area"], range=['#981515', 'orange', '#146f14']),
    "Numbers": alt.Scale(domain=sort_orders["Numbers"], range=["#ca0020", "#f4a582", "#92c5de", "#0571b0"]),
    "Call": alt.Scale(domain=calls4+calls7+calls,range=cols4+cols7+cols),
    "Setup": alt.Scale(domain=["A","C","H","W"], range=["dodgerblue", "crimson", "midnightblue", "black"]),
    "Movement": alt.Scale(range=["#981515", "#146f14", "black"], domain=sort_orders["Movement"][::-1]),
}

types = ["Numbers", "Area", "Hooker", "Jumper", "Setup", "Movement", "Call"]
type_selections = {type: alt.selection_point(fields=[type], empty="all") for type in types}

squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd"], name="Squad"),
        value="1st"
    )

def lineout_success_by_type(type, df=None, top=True, standalone=False):

    color_scale = color_scales.get(type, alt.Scale(scheme="tableau20"))

    min_count = 5 if type in ["Hooker", "Jumper", "Call"] else 0      

    prop_y = alt.Y(
        "Proportion:Q", 
        title="Proportion", 
        axis=alt.Axis(orient="left", format=".0%",), 
        scale=alt.Scale(domain=[0, 1])
    )
    success_y = alt.Y(
        "Success:Q", 
        title="Success Rate", 
        axis=alt.Axis(orient="right", format=".0%"),
        scale=alt.Scale(domain=[0, 1])
    )
    
    # Base chart
    base = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/lineouts.json',"format":{'type':"json"}})
        .add_selection(type_selections[type])
    )
    if standalone:
        base = base.add_selection(squad_selection)

    for t,f in type_selections.items():
        if t != type:
            base = base.transform_filter(f)

    base = (
     base
        .transform_aggregate(
            Total="count()",
            Success="mean(Won)",
            groupby=[type, "Season", "Squad"]
        )
        .transform_joinaggregate(
            SeasonTotal="sum(Total)",
            groupby=["Season", "Squad"],
        )
        .transform_calculate(
            Proportion="datum.Total / datum.SeasonTotal",
            Won="round(datum.Success * datum.Total)",
            SuccessText="format(datum.Success * datum.Total, '.0f') + ' / ' + format(datum.Total, '.0f')",
            SuccessTooltip="'Won ' + format(datum.Won, '.0f') + ' of ' + format(datum.Total, '.0f') + ' lineouts (' + format(datum.Success, '.0%') + ')'",
            ProportionTooltip="datum.Total + ' of ' + datum.SeasonTotal + ' lineouts total (' + format(datum.Proportion, '.0%') + ')'",
        )
        .transform_window(
            ID="row_number()",
            groupby=["Season", "Squad"],
            sort=[alt.SortField("Total", order="descending"), alt.SortField("Success", order="descending")],
        )
        .transform_filter(f"datum.Total >= {min_count} & datum.{type}!=''")
        .encode(
            x=alt.X(
                f"{type}:N", 
                title=None, 
                sort=sort_orders.get(type, alt.SortField(field="ID")),
                axis=alt.Axis(labelFontSize=18 if type=="Numbers" else 13)
            ),
            color=alt.Color(f"{type}:N", legend=None, scale=color_scale),
            opacity=alt.condition(type_selections[type], alt.value(0.8), alt.value(0.2)),
            tooltip=[
                f"{type}:N", 
                alt.Tooltip("SuccessTooltip:N", title="Success"),
                alt.Tooltip("ProportionTooltip:N", title="Proportion")
            ] 
        )
    )

    # Proportion of total
    bars = (
        base.mark_bar(opacity=0.8, stroke="black")
        .encode(
            y=prop_y,            
            strokeWidth=alt.condition(
                type_selections[type],
                alt.value(1.5),
                alt.value(0)
            )
        )
    )
    bar_text = (
        base.mark_text(align="center", baseline="bottom", dy=-5, strokeWidth=1, clip=True)
        .encode(y=prop_y, text=alt.Text("SuccessText:N"))
    )
    proportion = alt.layer(bars, bar_text)

    # Success rate
    line = (
        base.mark_line(strokeWidth=1)
        .encode(
            y=success_y, 
            color=alt.value("black"), 
            opacity=alt.condition(type_selections[type], alt.value(0.5), alt.value(0))
        )
    )
    points = (
        base.mark_point(stroke="black", filled=True, size=50, fillOpacity=1.0)
        .encode(y=success_y, color=alt.Color(f"{type}:N", legend=None))
    )
    line_text = (
        base.mark_text(yOffset=-15, fontSize=13, clip=True)
        .encode(y=success_y, text=alt.Text("Success:Q", format=".0%"), color=alt.value("black"))
    )
    success = alt.layer(line, points, line_text)

    # Facet by Season
    facet_chart = (
        alt.layer(proportion, success)
        .properties(width=225, height=275)
        .facet(
            column=alt.Column(
                "Season:N", 
                header=alt.Header(title=None, labels=top, labelFontSize=40, labelColor="#20294688")
            ),
            spacing=10
        )
        .resolve_scale(x="independent" if type in ["Call", "Jumper", "Hooker"] else "shared")
        .transform_filter(f"datum.Squad == {squad_selection.name}")
        .properties(
            title=alt.Title(
                text=f"{type}", 
                orient="left",
                anchor="middle", 
                color="#20294688", 
                offset=30, 
                fontSize=64
            )
        )
    )

    return facet_chart  

def lineout_success(types=types, df=None, file=None):
    # Use optimized data if df not provided
    if df is None:
        df = load_lineouts()

    charts = [lineout_success_by_type(t, df=df, top=(i==0)) for i,t in enumerate(types)]

    chart = (
        alt.vconcat(*charts, spacing=10)
        .resolve_scale(color="independent")
        .add_params(squad_selection)
        .properties(
            title=alt.Title(
                text="Lineout Success", 
                subtitle = [
                    "Distribution of lineouts (bar), and success rate (line). Click to highlight and filter.",
                    "Success is defined as being in possession when the lineout ends, and does not necessarily mean clean ball or perfect execution."
                ]
            )
        )
    )
    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        if str(file).lower().endswith('.html'):
            hack_params_css(file)
    return chart


def lineout_success_by_zone(df=None, squad="1st", min_total=20, file=None):
    if df is None:
        df = load_lineouts()

    if df is None or len(df) == 0:
        return alt.Chart(pd.DataFrame({"x": [], "y": []})).mark_point()

    data = df.copy()

    rename_map = {
        "area": "Area",
        "won": "Won",
        "squad": "Squad",
        "jumper": "Jumper",
        "hooker": "Hooker",
        "thrower": "Hooker",
    }
    for src, dst in rename_map.items():
        if src in data.columns and dst not in data.columns:
            data[dst] = data[src]

    required = ["Area", "Won", "Squad", "Jumper", "Hooker"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"lineout_success_by_zone missing columns: {missing}")

    zone_map = {"Front": 1, "Middle": 2, "Back": 3}

    data = data.copy()
    data["Area"] = data["Area"].astype(str).str.strip().str.title()
    data = data[data["Squad"].astype(str).str.strip() == str(squad)]
    data = data[data["Area"].isin(zone_map.keys())].copy()
    data["zone"] = data["Area"].map(zone_map)
    data["Won"] = data["Won"].fillna(False).astype(bool)

    if data.empty:
        return alt.Chart(pd.DataFrame({"x": [], "y": []})).mark_point()

    zone = (
        data.groupby("zone", as_index=False)
        .agg(total=("Won", "size"), won=("Won", "sum"))
    )
    zone["pct_won"] = zone["won"] / zone["total"]

    def _player_agg(frame, column, player_type):
        out = (
            frame.dropna(subset=[column])
            .groupby(column, as_index=False)
            .agg(
                total=("Won", "size"),
                won=("Won", "sum"),
                zone_sum=("zone", "sum"),
            )
            .rename(columns={column: "player"})
        )
        out = out[out["total"] >= min_total].copy()
        out["player_type"] = player_type
        out["pct_won"] = out["won"] / out["total"]
        out["error_margin"] = ((out["pct_won"] * (1 - out["pct_won"])) / out["total"]).pow(0.5)
        out["avg_zone"] = out["zone_sum"] / out["total"]
        return out[["player_type", "player", "total", "won", "pct_won", "error_margin", "avg_zone"]]

    jumpers = _player_agg(data, "Jumper", "Jumper")
    throwers = _player_agg(data, "Hooker", "Thrower")
    players = pd.concat([jumpers, throwers], ignore_index=True)

    size_scale = alt.Scale(domain=[10, 1000], range=[10, 400])

    base = alt.Chart(zone).encode(
        x=alt.X(
            "zone:Q",
            title="Average Lineout Zone",
            axis=alt.Axis(
                tickCount=3,
                values=[1, 2, 3],
                labelExpr="datum.value == 1 ? 'Front' : datum.value == 2 ? 'Middle' : 'Back'",
                grid=False,
                ticks=False,
                labelFontSize=16,
            ),
            scale=alt.Scale(domain=[0.75, 3.25], nice=False),
        ),
        y=alt.Y(
            "pct_won:Q",
            title="Success Rate",
            scale=alt.Scale(domain=[0.5, 1.0]),
            axis=alt.Axis(format="%", tickCount=5),
        ),
    )

    avg_points = base.encode(size=alt.Size("total:Q", legend=None, scale=size_scale)).mark_point(color="#991515", fill="red", fillOpacity=0.9)
    avg_line = base.mark_line(color="#991515")
    avg_total_labels = avg_points.encode(text="total:Q", size=alt.value(12)).mark_text(align="right", dx=-10, dy=5, opacity=0.5, color="#991515")

    points = alt.Chart(players).encode(
        x=alt.X("avg_zone:Q", title="Average Lineout Zone"),
        y=alt.Y("pct_won:Q", title="Success Rate"),
        size=alt.Size("total:Q", legend=None, scale=size_scale),
        color=alt.Color(
            "player_type:N",
            scale=alt.Scale(domain=["Thrower", "Jumper"], range=["#146f14", "#202946"]),
            title=None,
            legend=alt.Legend(orient="top-right"),
        ),
        tooltip=["player_type", "player", "total", "won", alt.Tooltip("pct_won:Q", format=".1%"), "avg_zone"],
    )

    errorbars = points.mark_errorbar(opacity=0.5).encode(
        x="avg_zone:Q",
        y=alt.Y("ymin:Q", scale=alt.Scale(clamp=True), title="Success Rate"),
        y2=alt.Y2("ymax:Q", title=None),
    ).transform_calculate(
        ymin="datum.pct_won - datum.error_margin",
        ymax="datum.pct_won + datum.error_margin",
    )

    labels = points.encode(text="player:N", size=alt.value(12)).mark_text(align="left", dx=10)
    total_labels = points.encode(text="total:Q", size=alt.value(12), color=alt.value("black")).mark_text(align="right", dx=-10, opacity=0.5)

    chart = (
        avg_line
        + avg_points
        + avg_total_labels
        + errorbars
        + points.mark_circle(size=100, opacity=1.0, fillOpacity=0.9)
        + labels
        + total_labels
    ).resolve_scale(
        y="shared", x="shared"
    ).properties(
        title=alt.Title(
            text="Lineout Success by Zone",
            subtitle=[
                f"{squad} XV average success rate by zone (red), with individual players by their average zone.",
                "Size and numbers indicate total lineouts taken. Error bars show uncertainty based on sample size.",
            ],
        ),
        width=500,
        height=600,
    )

    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        if str(file).lower().endswith('.html'):
            hack_params_css(file)

    return chart



def points_scorers_chart(df=None, file=None):

    selection = alt.selection_point(fields=['Type'], bind='legend')

    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Total"], name="Squad"),
        value="Total",
        name="squadSelection"
    )

    season_selection = alt.param(
        bind=alt.binding_select(options=["All", *seasons[::-1], *seasons_hist[::-1]], name="Season"), 
        value="2024/25",
        name="seasonSelection"
    )

    base = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/players_agg.json',"format":{'type':"json"}})
        .transform_filter("datum.Points > 0")
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Total'")
        .transform_aggregate(
            Games="sum(A)",
            T="sum(T)",
            PK="sum(PK)",
            Con="sum(Con)",
            Tries="sum(Tries)",
            Pens="sum(Pens)",
            Cons="sum(Cons)",
            Points="sum(Points)",
            groupby=["Player"]
        )
        .transform_fold(["Tries", "Pens", "Cons"], as_=["Type", "Points"])
        .transform_filter(selection)
        .transform_calculate(
            label="if(datum.T>0, datum.T + 'T ','') + if(datum.PK>0, datum.PK + 'P ', '') + if(datum.Con>0, datum.Con + 'C ', '')"
        )
        .transform_joinaggregate(
            label="max(label)",
            totalpoints="sum(Points)",
            groupby=["Player"]
        )
        .transform_calculate(
            PPG="datum.totalpoints / datum.Games"
        )
        .transform_filter("datum.totalpoints > 0")
        .encode(
            order=alt.Order("Type:N", sort="descending"),
            y=alt.Y("Player:N", sort="-x", title=None),
            text=alt.Text("label:N")
        )
    )

    bar = (
        base.mark_bar()
        .encode(
            x=alt.X("sum(Points):Q", axis=alt.Axis(orient="top", title="Points")),
            color=alt.Color(
                "Type:N", 
                legend=alt.Legend(
                    title="Click to filter",
                    titleOrient="top",
                    orient="none",
                    legendX=300,
                    legendY=100
                ), 
                scale=alt.Scale(domain=['Tries', 'Pens', 'Cons'], range=["#202947", "#981515", "#146f14"])
            ),
            tooltip=[
                alt.Tooltip("Player:N", title=" "), 
                alt.Tooltip("label:N", title="Scores"),
                alt.Tooltip("Type:N", title=None),
                alt.Tooltip("Points:Q", title="Points"),
                alt.Tooltip("Games:Q", title="Games"),
                alt.Tooltip("totalpoints:Q", title="Total Points"),
                alt.Tooltip("PPG:Q", title="Points per game", format=".2f")
            ],
        )
        .properties(width=400, height=alt.Step(16))
    )
    
    text = (
        base
        .transform_aggregate(
            totalpoints="max(totalpoints)",
            label="max(label)",
            groupby=["Player"]
        )
        .mark_text(align="left", dx=5, color="black")
        .encode(
            y=alt.Y(
                "Player:N", 
                sort="-x",
                title=None,
                axis=None
            ),
            x=alt.X("totalpoints:Q")
        )
    )

    chart = (
        (bar + text).resolve_scale(x="shared", y="independent")
        .add_params(selection, season_selection, squad_selection)
        .properties(title=alt.Title(text="Points Scorers", subtitle="According to Pitchero data"))
    )

    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        hack_params_css(file, params=True)

    return chart

def captains_chart(df=None, file=None):

    selection = alt.selection_point(fields=['Role'], bind='legend')

    season_selection = alt.param(
        bind=alt.binding_select(options=["All", *seasons[::-1]], name="Season"), 
        value="All",
        name="seasonSelection"
    )

    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Both"], name="Squad"),
        value="Both",
        name="squadSelection"
    )

    chart = (
       alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/game.json',"format":{'type':"json"}})
        .transform_fold(["Captain", "VC1", "VC2"], as_=["Role", "Player"])
        .transform_calculate(Role="datum.Role == 'Captain' ? 'Captain' : 'VC'")
        .transform_filter("datum.Player != null && datum.Player != ''")
        .mark_bar()
        .encode(
            y=alt.X("Player:N", title=None, sort="-x"),
            x=alt.X("count()", title="Games", sort=alt.EncodingSortField(field="Role", order="descending"), axis=alt.Axis(orient="top")),
            color=alt.Color("Role:N",
                scale=alt.Scale(domain=["Captain", "VC"], range=["#202947", "#146f14"]),
                legend=alt.Legend(title=None, direction="horizontal", orient="bottom")
            ), 
            row=alt.Row("Squad:N", header=alt.Header(title=None, labelFontSize=36, labelExpr="datum.value + ' XV'"), spacing=50),
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
        .add_params(season_selection, squad_selection, selection)
        .transform_filter(selection)
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Both'")
        .properties(
            title=alt.Title("Match Day Captains", subtitle="Captains and Vice-Captains (if named). Friendly games are shaded lighter."),
            width=350,
            height=alt.Step(16)
        )
        .resolve_scale(x="shared", y="independent", opacity="shared")
    )
    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        hack_params_css(file)

    return chart

def results_chart(df=None, file=None):

    selection = alt.selection_point(fields=['Result'], bind='legend')

    season_selection = alt.param(
        bind=alt.binding_select(options=["All", *seasons[::-1]], name="Season"), 
        value="All",
        name="seasonSelection"
    )

    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Both"], name="Squad"),
        value="Both",
        name="squadSelection"
    )

    base = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/game.json',"format":{'type':"json"}})
        .transform_calculate(
            loser="datum.Result == 'L' ? datum.PF : datum.PA",
            winner="datum.Result == 'W' ? datum.PF : datum.PA",
            index="datum.index"
        )
        .transform_window(
            ID="row_number()",
            groupby=["Season", "Squad"],
        )
        .encode(
            y=alt.Y(
                'GameID:N', 
                sort=alt.EncodingSortField(field="ID", order="descending"),
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
            opacity=alt.condition(team_filter, alt.value(1), alt.value(0.2))
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
        .resolve_scale(y='shared')
        .add_params(selection, team_filter, season_selection, squad_selection)
        .transform_filter(selection)
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Both'")
        .facet(
            row=alt.Row('Season:N', title=None, header=alt.Header(labelFontSize=36), sort="descending"),
            column=alt.Column('Squad:N', title=None, header=alt.Header(labelFontSize=36, labelExpr="datum.value + ' XV'")),
            align="each",
            spacing=20,
        )
        .resolve_scale(y='independent')
        .properties(
            title=alt.Title(
                text="Results",
                subtitle=[
                    "Match scores visualised by winning margin. Small bars reflect close games, colour reflects the result.",
                    "Click the legend to highlight wins or losses. Click a bar to highlight results against that team."  
                ],
                offset=20
            )
        )
    )

    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        hack_params_css(file)
    
    return chart

seasons = ["2021/22", "2022/23", "2023/24", "2024/25"]
seasons_hist = ["2016/17", "2017/18", "2018/19", "2019/20"]

turnover_filter = alt.selection_point(fields=["Turnover"], bind="legend")
put_in_filter = alt.selection_point(fields=["Team"], bind="legend")
team_filter = alt.selection_point(fields=["Opposition"])

color_scale = alt.Scale(domain=["EG", "Opposition"], range=["#202946", "#981515"])
opacity_scale = alt.Scale(domain=["Turnover", "Retained"], range=[1, 0.5])

def set_piece_h2h_chart(df=None, file=None):
    # Use optimized data if df not provided
    if df is None:
        df = set_piece_h2h_optimized()

    season_selection = alt.param(
        bind=alt.binding_select(options=seasons[::-1], name="Season"), 
        value="2024/25",
        name="seasonSelection"
    )

    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd"], name="Squad"),
        value="1st",
        name="squadSelection"
    )
    
    base = (
        alt.Chart(df if df is not None else {"name":"df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/set_piece.json',"format":{'type':"json"}})
        .add_params(
            alt.param(
                name="x_max",
                # Max value of "Count"
                expr="parseInt(data('df')[0].Count)",
            )
        )
        .encode(
            y=alt.Y(
                "GameID:N", 
                axis=None,
                sort=alt.EncodingSortField(field="Date", order="descending"), 
                scale=alt.Scale(padding=0),
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
        .properties(height=alt.Step(10), width=160)
    )

    eg = (
        base.mark_bar(stroke="#202946")
        .encode(
            x=alt.X(
                "Count:Q",
                axis=alt.Axis(title="EG wins", orient="top", titleColor="#202946"),
                scale=alt.Scale(domain={"expr": "[0, 15]"}),
            )
        )
        .transform_filter("datum.Winner == 'EG'")
    )
    opp = (
        base.mark_bar(stroke="#981515")
        .encode(
            x=alt.X(
                "Count:Q",
                scale=alt.Scale(reverse=True, domain={"expr": "[0, 15]"}),
                axis=alt.Axis(title="Opposition wins", orient="top", titleColor="#981515")
            ),
            y=alt.Y(
                "GameID:N", 
                title=None, 
                axis=alt.Axis(orient="left"), 
                sort=alt.EncodingSortField(field="Date", order="descending"),
                scale=alt.Scale(padding=0)
            ),
        )
        .transform_filter("datum.Winner == 'Opposition'")
    )

    scrum_chart = (
        alt.hconcat(opp, eg, spacing=0)
        .transform_filter(f"datum.SetPiece == 'Scrum'")
        .resolve_scale(yOffset="independent")
        .properties(title=alt.Title("Scrum", fontSize=36, anchor="middle", align="left"))
    )

    lineout_chart = (
        alt.hconcat(opp, eg, spacing=0)
        .transform_filter(f"datum.SetPiece == 'Lineout'")
        .resolve_scale(yOffset="independent")
        .properties(title=alt.Title("Lineout", fontSize=36, anchor="middle", align="left"))
    )

    chart = (
        alt.hconcat(scrum_chart, lineout_chart, spacing=20)
        .add_params(season_selection, squad_selection, turnover_filter, team_filter, put_in_filter)
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Both'")
        .transform_filter(turnover_filter)
        .transform_filter(put_in_filter)
        .transform_filter(team_filter)
        .resolve_scale(y="shared")
        .properties(
            title=alt.Title(
                text=f"Set Piece Head-to-Head Results", 
                subtitle=[
                    "Numbers of set piece and turnovers for both teams in each game.", 
                    "Click the legends to view only turnovers.", 
                    "Click the bar charts to select all games against that specific opposition."
                ]
            )
        )
    )

    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        hack_params_css(file)

    return chart

def squad_continuity_chart(df=None, file=None):
    season_selection = alt.selection_point(on="mouseover", name="Season", fields=["Season"], empty=True)

    base = (
        alt.Chart(df if df is not None else {"name":"df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/game.json',"format":{'type':"json"}})
        .mark_bar(stroke="black", strokeWidth=1, strokeOpacity=0.5, size=20)
        .transform_calculate(Starters_retained="toNumber(datum.Starters_retained)")
        .transform_filter(season_selection)
        .transform_filter("datum.Starters_retained > 0")
        .properties(width=200, height=400)
    )

    b1 = (
        base.transform_filter("datum.Squad == '1st'")
        .encode(
            y=alt.Y(
                "Starters_retained:O",
                axis=alt.Axis(title=None, orient="right", ticks=False, labelAlign="center", labelPadding=10),
                scale=alt.Scale(domain=list(range(1, 16)), reverse=True),
            ),
            x=alt.X("count()", axis=alt.Axis(title="Games", grid=False, tickMinStep=1.0), scale=alt.Scale(reverse=True)),
            color=alt.Color(
                "Starters_retained:Q",
                scale=alt.Scale(scheme="blues"), 
                legend=None
            )
        )
        .properties(title=alt.Title(text="1st XV", anchor="middle", fontSize=36, color=squad_scale.range[0]))
    )

    b2 = (
        base.transform_filter("datum.Squad == '2nd'")
        .transform_filter(season_selection)
        .encode(
            y=alt.Y(
                "Starters_retained:O",
                axis=alt.Axis(title=None, orient="left", grid=False, ticks=False, labelAlign="center", labelPadding=10, tickMinStep=1.0),
                scale=alt.Scale(domain=list(range(1, 16)), reverse=True),
            ),
            x=alt.X("count()", axis=alt.Axis(title="Games", grid=False)),
            color=alt.Color(
                "Starters_retained:Q",
                scale=alt.Scale(scheme="greens"), 
                legend=None
            )
        )
        .properties(title=alt.Title(text="2nd XV", anchor="middle", fontSize=36, color=squad_scale.range[1]))
    )

    trend = (
        alt.Chart(df if df is not None else {"name":"df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/game.json',"format":{'type':"json"}})
        .transform_aggregate(
            Starters="mean(Starters_retained)", 
            Forwards="mean(Forwards_retained)",
            Backs="mean(Backs_retained)",
            groupby=["Squad", "Season"]
        )
        .transform_fold(["Starters", "Forwards", "Backs"], as_=["Type", "Retained"])
        .encode(
            x=alt.X("Season:O", axis=alt.Axis(title="Season", labelExpr="substring(datum.label, 2, 7)")),
            y=alt.Y("Retained:Q", title=None, scale=alt.Scale(domain=[0.5, 15.5]), axis=alt.Axis(labels=False, ticks=False)),
            color=alt.Color(
                "Squad:N", 
                scale=squad_scale,
                legend=alt.Legend(orient="top-left", labelExpr="datum.label + ' XV'", title=None, direction="horizontal")
            ),
            opacity=alt.condition(season_selection, alt.value(1), alt.value(0.1)),
            tooltip=[
                alt.Tooltip("Season:O", title="Season"),
                alt.Tooltip("Squad:N", title="Squad"),
                alt.Tooltip("Starters:Q", title="Starters retained", format=".1f"),
                alt.Tooltip("Forwards:Q", title="Forwards retained", format=".1f"),
                alt.Tooltip("Backs:Q", title="Backs retained", format=".1f"),
            ]
        )
        .properties(
            width=200, height=400,
            title=alt.Title(
                text="Average by Season", 
                fontSize=24, 
                anchor="middle", 
                subtitle="Hover over a season to filter",
                subtitlePadding=5,
                offset=5
            )
        )
    )

    line = trend.mark_line(point=False).encode(
        strokeDash=alt.StrokeDash(
            "Type:N", 
            scale=alt.Scale(
                domain=["Starters", "Forwards", "Backs"], 
                range=[[0, 0], [15, 5], [2, 2]]
            ), 
            legend=None
        ),
        opacity=alt.Opacity("Type:N", scale=alt.Scale(domain=["Starters", "Forwards", "Backs"], range=[1, 0.5])),
    )
    point = (
        trend.mark_point(filled=True, size=100)
        .add_params(season_selection)
        .transform_filter("datum.Type == 'Starters'")
    )
    text = (
        trend.mark_text(dy=-15, fontSize=13)
        .encode(text=alt.Text("Starters:Q", format=".1f"))
        .transform_filter("datum.Type == 'Starters'")
    )
    trends = alt.layer(line, point, text)


    chart = (
        alt.hconcat(b1, trends, b2, spacing=0)
        .resolve_scale(y="shared")
        .properties(
            title=alt.Title(
                text="Squad Continuity", 
                subtitle=[
                    "Number of players in the starting XV retained from the previous game", 
                    "Dashed lines (forwards) and dotted lines (backs) show average by season"
                ]
            )
        )
    )

    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        hack_params_css(file, params=False)

    return chart