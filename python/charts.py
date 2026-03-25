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
from python.chart_helpers import hack_params_css, alt_theme, get_embed_options
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
        chart.save(file, embed_options=get_embed_options())
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
        chart.save(file, embed_options=get_embed_options())
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
        chart.save(file, embed_options=get_embed_options())
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
        chart.save(file, embed_options=get_embed_options())
        if str(file).lower().endswith('.html'):
            hack_params_css(file)

    return chart



def points_scorers_chart(db, output_file='data/charts/point_scorers.json'):
    """Canonical Player Stats scoring chart.

    Supported filters in the generated Vega spec:
        seasonParam     – [] (all seasons) or an array of season labels
        squadParam      – 'All', '1st', or '2nd'
        scoreTypeParam  – 'Total', 'Tries', or 'Kicks'

    Game type and position are not available from the season_scorers source, so those
    UI filters are intentionally not applied to this chart.
    """

    base_df = db.con.execute(
        """
        SELECT
            squad,
            season,
            player,
            COALESCE(tries, 0) AS tries,
            COALESCE(conversions, 0) AS conversions,
            COALESCE(penalties, 0) AS penalties,
            COALESCE(drop_goals, 0) AS drop_goals,
            COALESCE(points, 0) AS total_points
        FROM season_scorers
        """
    ).df()

    if base_df.empty:
        base_df = pd.DataFrame(
            columns=['player', 'squad', 'season', 'score_type', 'component', 'value', 'component_order']
        )

    total_rows = pd.concat([
        base_df.assign(
            score_type='Total',
            component='Tries',
            value=base_df['tries'] * 5,
            component_order=1,
        ),
        base_df.assign(
            score_type='Total',
            component='Conversions',
            value=base_df['conversions'] * 2,
            component_order=2,
        ),
        base_df.assign(
            score_type='Total',
            component='Penalties',
            value=base_df['penalties'] * 3,
            component_order=3,
        ),
        base_df.assign(
            score_type='Total',
            component='Drop Goals',
            value=base_df['drop_goals'] * 3,
            component_order=4,
        ),
    ], ignore_index=True)

    tries_rows = base_df.assign(
        score_type='Tries',
        component='Tries',
        value=base_df['tries'],
        component_order=1,
    )

    kicks_rows = pd.concat([
        base_df.assign(
            score_type='Kicks',
            component='Conversions',
            value=base_df['conversions'] * 2,
            component_order=2,
        ),
        base_df.assign(
            score_type='Kicks',
            component='Penalties',
            value=base_df['penalties'] * 3,
            component_order=3,
        ),
        base_df.assign(
            score_type='Kicks',
            component='Drop Goals',
            value=base_df['drop_goals'] * 3,
            component_order=4,
        ),
    ], ignore_index=True)

    df = pd.concat([total_rows, tries_rows, kicks_rows], ignore_index=True)
    df = df[df['value'] > 0].copy()

    season_param = alt.param(name='seasonParam', value=[])
    squad_param = alt.param(name='squadParam', value='All')
    score_type_param = alt.param(name='scoreTypeParam', value='Total')

    value_axis = alt.Axis(orient='top', title='Points')

    color_scale = alt.Scale(
        domain=['Tries', 'Conversions', 'Penalties', 'Drop Goals'],
        range=[ '#981515', '#202946', '#7d96e8', '#4b5563']
    )

    bars = alt.Chart(df).mark_bar().encode(
        x=alt.X('sum(value):Q', axis=value_axis),
        y=alt.Y(
            'player:N',
            sort=alt.EncodingSortField(field='player_total', order='descending', op='max'),
            title=None,
        ),
        color=alt.Color(
            'component:N',
            scale=color_scale,
            legend=alt.Legend(title=None, orient='bottom-right')
        ),
        order=alt.Order('component_order:Q', sort='ascending'),
        tooltip=[
            alt.Tooltip('player:N', title='Player'),
            alt.Tooltip('component:N', title='Score Type'),
            alt.Tooltip('sum(value):Q', title='Value'),
            alt.Tooltip('max(player_total):Q', title='Total'),
        ]
    )

    total_labels = alt.Chart(df).transform_aggregate(
        total_value='sum(value)',
        player_total='max(player_total)',
        groupby=['player']
    ).mark_text(
        align='left',
        baseline='middle',
        dx=4,
        fontSize=11,
        color='black'
    ).encode(
        x=alt.X('total_value:Q', axis=value_axis),
        y=alt.Y(
            'player:N',
            sort=alt.EncodingSortField(field='player_total', order='descending', op='max'),
            title=None,
        ),
        text=alt.Text('total_value:Q', format='.0f')
    )

    chart = (
        alt.layer(bars, total_labels)
        .transform_filter('length(seasonParam) === 0 || indexof(seasonParam, datum.season) >= 0')
        .transform_filter('squadParam === "All" || datum.squad === squadParam')
        .transform_filter('scoreTypeParam === datum.score_type')
        .transform_joinaggregate(player_total='sum(value)', groupby=['player'])
        .transform_filter('datum.player_total > 0')
        .add_params(season_param, squad_param, score_type_param)
        .properties(
            title=alt.Title(
                'Top Scorers'
            ),
            width=400,
            height=alt.Step(15)
        )
    )

    chart.save(output_file)
    return chart

def captains_chart(db, output_file='data/charts/player_stats_captains.json'):
    """Captains and vice-captains, faceted by squad. Captain=full opacity, VC=reduced opacity."""

    df = db.con.execute(
        """
        WITH base AS (
            SELECT
                P.player,
                G.squad,
                G.season,
                G.game_type,
                CASE
                    WHEN P.is_captain THEN 'Captain'
                    ELSE 'Vice Captain'
                END AS role,
                COUNT(*) AS games
            FROM player_appearances P
            LEFT JOIN games G USING (game_id)
            WHERE P.is_captain OR P.is_vice_captain
            GROUP BY P.player, G.squad, G.season, G.game_type, role
        )
        SELECT player, squad, season, game_type, role, games
        FROM base

        UNION ALL

        SELECT
            player,
            squad,
            'Total' AS season,
            game_type,
            role,
            SUM(games) AS games
        FROM base
        GROUP BY player, squad, game_type, role
        """
    ).df()

    # Sort within each facet panel by that squad's total (so 1st XV and 2nd XV rank independently).
    sort_totals = (
        df[df['season'] == 'Total']
        .groupby(['player', 'squad'])['games']
        .sum()
        .rename('sort_total')
        .reset_index()
    )
    df = df.merge(sort_totals, on=['player', 'squad'], how='left')
    df['sort_total'] = df['sort_total'].fillna(0)

    role_order = {'Captain': 1, 'Vice Captain': 2}
    df['stack_order'] = df['role'].map(role_order).fillna(99)

    color_enc = alt.Color(
        'squad:N',
        sort=['1st', '2nd'],
        scale=alt.Scale(domain=['1st', '2nd'], range=['#202946', '#7d96e8']),
        legend=None
    )
    y_enc = alt.Y(
        'player:N',
        sort=alt.SortField(field='sort_total', order='descending'),
        title=None,
    )
    tooltip = [
        alt.Tooltip('player:N', title='Player'),
        alt.Tooltip('squad:N', title='Squad'),
        alt.Tooltip('role:N', title='Role'),
        alt.Tooltip('games_agg:Q', title='Games'),
    ]

    bars = (
        alt.Chart(df)
        .transform_aggregate(
            games_agg='sum(games)',
            sort_total='max(sort_total)',
            groupby=['player', 'squad', 'role', 'stack_order']
        )
        .transform_window(
            x2='sum(games_agg)',
            groupby=['player', 'squad'],
            sort=[alt.SortField(field='stack_order', order='ascending')],
            frame=[None, 0]
        )
        .transform_calculate(x0='datum.x2 - datum.games_agg')
        .mark_bar()
        .encode(
            x=alt.X('x0:Q', axis=alt.Axis(title=None, orient='top')),
            x2=alt.X2('x2:Q'),
            y=y_enc,
            color=color_enc,
            opacity=alt.Opacity(
                'role:N',
                sort=['Captain', 'Vice Captain'],
                scale=alt.Scale(domain=['Captain', 'Vice Captain'], range=[1.0, 0.45]),
                legend=alt.Legend(title=None, orient='none', legendX=250, legendY=100)
            ),
            order=alt.Order('stack_order:Q', sort='ascending'),
            tooltip=tooltip,
        )
    )

    totals = (
        alt.Chart(df)
        .transform_aggregate(
            total_games='sum(games)',
            sort_total='max(sort_total)',
            groupby=['player', 'squad']
        )
        .mark_text(align='left', baseline='middle', dx=4, fontSize=11, color='black')
        .encode(
            x=alt.X('total_games:Q', axis=alt.Axis(title=None, orient='top')),
            y=alt.Y(
                'player:N',
                sort=alt.SortField(field='sort_total', order='descending'),
                title=None,
            ),
            text=alt.Text('total_games:Q', format='.0f')
        )
    )

    chart = (
        alt.layer(bars, totals)
        .properties(width=400, height=alt.Step(15))
        .facet(
            row=alt.Row(
                'squad:N',
                sort=['1st', '2nd'],
                title=None,
                header=alt.Header(title=None, labelFontSize=30, labelExpr="datum.value + ' XV'")
            )
        )
        .resolve_scale(y='independent')
        .properties(
            title=alt.Title(
                'Captains and Vice-Captains',
                subtitle='Named captains and vice-captains, since Pitchero records began in 2016/17.',
            )
        )
    )

    chart.save(output_file)
    return chart

def player_stats_appearances_chart(db, output_file='data/charts/player_stats_appearances.json'):
    """Player appearances split by start/bench for each squad.

    Filtering and sort-order are computed entirely within Vega-Lite using params and transforms,
    so the JS only needs to set param values before calling vegaEmbed — no manual dataset
    manipulation required.  The five params are:
        seasonParam     – [] (all seasons) or an array of season labels
        gameTypesParam  – [] (all) or an array of allowed game_type strings
        squadParam      – 'All', '1st', or '2nd'
        positionsParam  – [] (all) or an array of position strings
        minAppsParam    – minimum total appearances threshold (integer)
    """
    df = db.con.execute(
        """
        SELECT
            P.player,
            COALESCE(G.squad, P.squad) AS squad,
            COALESCE(G.season, P.season) AS season,
            CASE WHEN P.is_backfill THEN 'Unknown' ELSE G.game_type END AS game_type,
            CASE WHEN P.is_backfill THEN 'Unknown' ELSE COALESCE(P.position, 'Unknown') END AS position,
            CASE
                WHEN P.is_backfill THEN 'Unknown'
                WHEN P.is_starter THEN 'Start'
                ELSE 'Bench'
            END AS start,
            COUNT(*) AS games
        FROM player_appearances P
        LEFT JOIN games G USING (game_id)
        GROUP BY
            P.player,
            COALESCE(G.squad, P.squad),
            COALESCE(G.season, P.season),
            CASE WHEN P.is_backfill THEN 'Unknown' ELSE G.game_type END,
            CASE WHEN P.is_backfill THEN 'Unknown' ELSE COALESCE(P.position, 'Unknown') END,
            CASE WHEN P.is_backfill THEN 'Unknown' WHEN P.is_starter THEN 'Start' ELSE 'Bench' END
        """
    ).df()

    stack_order_map = {
        ('1st', 'Start'): 1,
        ('1st', 'Bench'): 2,
        ('1st', 'Unknown'): 3,
        ('2nd', 'Start'): 4,
        ('2nd', 'Bench'): 5,
        ('2nd', 'Unknown'): 6,
    }
    df['stack_order'] = df.apply(
        lambda row: stack_order_map.get((row['squad'], row['start']), 99),
        axis=1
    )

    # Vega-Lite params — JS updates `.value` on these before calling vegaEmbed.
    season_param = alt.param(name='seasonParam', value=[])
    game_types_param = alt.param(name='gameTypesParam', value=[])
    squad_param = alt.param(name='squadParam', value='All')
    positions_param = alt.param(name='positionsParam', value=[])
    min_apps_param = alt.param(name='minAppsParam', value=5)

    bars = alt.Chart(df).mark_bar().encode(
        x=alt.X('sum(games):Q', axis=alt.Axis(title=None, orient='top')),
        y=alt.Y(
            'player:N',
            sort=alt.EncodingSortField(field='player_total', order='descending', op='max'),
            title=None,
        ),
        color=alt.Color(
            'squad:N',
            sort=['1st', '2nd'],
            scale=alt.Scale(domain=['1st', '2nd'], range=['#202946', '#7d96e8']),
            legend=alt.Legend(title='Squad', orient='top', labelExpr="datum.value + ' XV'", titleOrient='left')
        ),
        opacity=alt.Opacity(
            'start:N',
            sort=['Start', 'Bench', 'Unknown'],
            scale=alt.Scale(domain=['Start', 'Bench', 'Unknown'], range=[1.0, 0.35, 0.2]),
            legend=alt.Legend(title='Selection', orient='bottom')
        ),
        order=alt.Order('stack_order:Q', sort='ascending'),
        tooltip=[
            alt.Tooltip('player:N', title='Player'),
            alt.Tooltip('squad:N', title='Squad'),
            alt.Tooltip('start:N', title='Selection'),
            alt.Tooltip('sum(games):Q', title='Games'),
            alt.Tooltip('max(player_total):Q', title='Total'),
        ]
    ).properties(
        width=400,
        height=alt.Step(15)
    )

    # One row per player after per-layer aggregate; sort matches bars layer.
    total_labels = alt.Chart(df).transform_aggregate(
        total_games='sum(games)',
        player_total='max(player_total)',
        groupby=['player']
    ).mark_text(
        align='left',
        baseline='middle',
        dx=4,
        fontSize=11,
        color='black'
    ).encode(
        x=alt.X('total_games:Q', axis=alt.Axis(title=None, orient='top')),
        y=alt.Y(
            'player:N',
            sort=alt.EncodingSortField(field='player_total', order='descending', op='max'),
            title=None,
        ),
        text=alt.Text('total_games:Q', format='.0f')
    )

    # Top-level transforms run before any layer-level transforms.
    # Vega therefore filters → joins → filters again, then both layers sort by the
    # explicit post-filter player_total field.
    chart = (
        alt.layer(bars, total_labels)
        .transform_filter('length(seasonParam) === 0 || indexof(seasonParam, datum.season) >= 0')
        .transform_filter('length(gameTypesParam) === 0 || indexof(gameTypesParam, datum.game_type) >= 0')
        .transform_filter('squadParam === "All" || datum.squad === squadParam')
        .transform_filter('length(positionsParam) === 0 || indexof(positionsParam, datum.position) >= 0')
        .transform_joinaggregate(player_total='sum(games)', groupby=['player'])
        .transform_filter('datum.player_total >= minAppsParam')
        .add_params(season_param, game_types_param, squad_param, positions_param, min_apps_param)
        .properties(
            title=alt.Title('Appearances', subtitle='Since Pitchero data began in 2016/17 season')
        )
    )

    chart.save(output_file)
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
        chart.save(file, embed_options=get_embed_options())
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
        chart.save(file, embed_options=get_embed_options())
        hack_params_css(file)

    return chart

def squad_continuity_chart(df=None, file=None):
    """Legacy continuity chart - kept for compatibility."""
    pass

# Text labels anchored per-facet at the maximum point of each line.
def _unit_label(base, unit, color, value_field):
    label_dy = {
        "Total": -20,
        "Forwards": -12,
        "Backs": 10,
    }
    label_dx = {
        "Total": 0,
        "Forwards": 0,
        "Backs": 0,
    }

    aggregate_field = "min_value" if unit == "Backs" else "max_value"
    baseline = "top" if unit == "Backs" else "bottom"

    return (
        base.transform_filter(alt.datum.unit == unit)
        .transform_calculate(season_order="toNumber(split(datum.season, '/')[0])")
        .transform_joinaggregate(
            max_value=f"max({value_field})",
            min_value=f"min({value_field})",
            groupby=["squad"],
        )
        .transform_filter(f"datum.{value_field} > 0")
        .transform_filter(f"datum.{value_field} == datum.{aggregate_field}")
        .transform_window(
            rank="row_number()",
            groupby=["squad"],
            sort=[alt.SortField("season_order", order="descending")],
        )
        .transform_filter("datum.rank == 1")
        .mark_text(
            align="center",
            baseline=baseline,
            dy=label_dy.get(unit, -8),
            dx=label_dx.get(unit, 0),
            fontSize=14 if unit == "Total" else 12,
            color=color,
            fontWeight="bold" if unit == "Total" else "normal",
        )
        .encode(
            x=alt.X("season:O"),
            y=alt.Y(f"{value_field}:Q"),
            text=alt.value(unit),
        )
    )

def squad_continuity_average_chart(db, output_file='data/charts/squad_continuity_average.json'):
    """Generate squad continuity average chart (avg players retained per season) from canonical backend data."""

    # Get all player appearances ordered by game date
    appearances_df = db.con.execute(
        """
        SELECT 
            pa.game_id,
            pa.player,
            pa.squad,
            pa.unit,
            g.date,
            g.season
        FROM player_appearances pa
        JOIN games g ON pa.game_id = g.game_id
        WHERE pa.is_starter = TRUE
        ORDER BY pa.squad, g.season, g.date, g.game_id
        """
    ).df()

    if appearances_df.empty:
        print("No starter appearance data found for continuity chart.")
        return None

    # Calculate retention for each consecutive game pair
    retention_records = []
    
    for squad in ['1st', '2nd']:
        squad_data = appearances_df[appearances_df['squad'] == squad].copy()
        
        # Group by season and game
        for season in squad_data['season'].unique():
            season_data = squad_data[squad_data['season'] == season]
            games = season_data.groupby('game_id')
            game_list = list(games)
            
            if len(game_list) < 2:
                continue
            
            # Calculate retention between consecutive games
            retentions_by_unit = {'Total': [], 'Forwards': [], 'Backs': []}
            
            for i in range(1, len(game_list)):
                prev_game_id, prev_game_data = game_list[i - 1]
                curr_game_id, curr_game_data = game_list[i]
                
                # Get players from each game by unit
                prev_players = {
                    'Total': set(prev_game_data['player'].unique()),
                    'Forwards': set(prev_game_data[prev_game_data['unit'] == 'Forwards']['player'].unique()),
                    'Backs': set(prev_game_data[prev_game_data['unit'] == 'Backs']['player'].unique()),
                }
                
                curr_players = {
                    'Total': set(curr_game_data['player'].unique()),
                    'Forwards': set(curr_game_data[curr_game_data['unit'] == 'Forwards']['player'].unique()),
                    'Backs': set(curr_game_data[curr_game_data['unit'] == 'Backs']['player'].unique()),
                }
                
                # Count retained players
                for unit in ['Total', 'Forwards', 'Backs']:
                    if len(prev_players[unit]) > 0:
                        retained = len(prev_players[unit] & curr_players[unit])
                        retentions_by_unit[unit].append(retained)
            
            # Average retention for the season
            for unit in ['Total', 'Forwards', 'Backs']:
                if retentions_by_unit[unit]:
                    avg_retention = sum(retentions_by_unit[unit]) / len(retentions_by_unit[unit])
                    retention_records.append({
                        'season': season,
                        'squad': squad,
                        'unit': unit,
                        'retained': avg_retention
                    })
    
    df = pd.DataFrame(retention_records)
    
    if df.empty:
        print("No continuity data calculated.")
        return None

    base = alt.Chart(df).encode(
        x=alt.X(
            "season:O",
            sort=alt.SortOrder("ascending"),
            title="Season",
            axis=alt.Axis(
                labelAngle=0,
                labelOverlap="parity"
            )
        ),
        y=alt.Y(
            "retained:Q",
            title="Average Players Retained",
            scale=alt.Scale(zero=True),
            axis=alt.Axis(tickMinStep=1),
        ),
        detail=[alt.Detail("unit:N")],
        tooltip=[
            alt.Tooltip("season:O", title="Season"),
            alt.Tooltip("squad:N", title="Squad"),
            alt.Tooltip("unit:N", title="Unit"),
            alt.Tooltip("retained:Q", title="Avg Retained", format=".1f"),
        ],
    )

    total_line = (
        base.transform_filter(alt.datum.unit == "Total")
        .mark_line(opacity=0.8, color="#202946", point={"filled": True, "color": "#7d96e8", "stroke":"#202946", "size": 75, "strokeWidth":2}, strokeWidth=3)
    )

    forwards_line = (
        base.transform_filter(alt.datum.unit == "Forwards")
        .mark_line(opacity=0.8, color="blue", point={"filled": True, "color": "blue", "stroke":"darkblue", "size": 50, "strokeWidth":2}, strokeWidth=2)
    )

    backs_line = (
        base.transform_filter(alt.datum.unit == "Backs")
        .mark_line(opacity=0.8, color="black", point={"filled": True, "color": "white", "stroke": "black", "size": 50, "strokeWidth": 2}, strokeWidth=2)
    )

    label_total    = _unit_label(base, "Total", "#202946", "retained")
    label_forwards = _unit_label(base, "Forwards", "darkblue", "retained")
    label_backs    = _unit_label(base, "Backs", "black", "retained")

    chart = (
        alt.layer(total_line, forwards_line, backs_line, label_total, label_forwards, label_backs)
        .properties(width=200, height=400)
        .facet(
            column=alt.Column(
                "squad:N",
                sort=["1st", "2nd"],
                title=None,
                header=alt.Header(
                    labelFontSize=24,
                    labelExpr="datum.value + ' XV'",
                ),
            ),
            spacing=30
        )
        .properties(
            title=alt.Title(
                text="Squad Continuity",
                subtitle=["Average number of players retained from game to game."],
            )
        )
    )

    chart.save(output_file)
    return chart


def squad_size_trend_chart(db, output_file='data/charts/squad_size_trend.json'):
    """Generate squad size trend chart template from canonical backend data."""

    df = db.con.execute(
        """
        SELECT season, squad, unit, COUNT(DISTINCT player) AS players
        FROM player_appearances
        WHERE unit IN ('Forwards', 'Backs')
        GROUP BY season, squad, unit

        UNION ALL

        SELECT season, squad, 'Total' AS unit, COUNT(DISTINCT player) AS players
        FROM player_appearances
        GROUP BY season, squad

        ORDER BY season, squad, unit
        """
    ).df()

    if df.empty:
        print("No player appearance data found for squad size trend chart.")
        return None

    base = alt.Chart(df).encode(
        x=alt.X(
            "season:O",
            sort=alt.SortOrder("ascending"),
            title="Season",
            axis=alt.Axis(
                labelAngle=0,
                labelOverlap="parity"
            )
        ),
        y=alt.Y(
            "players:Q",
            title="Players",
            scale=alt.Scale(zero=True),
            axis=alt.Axis(tickMinStep=1),
        ),
        detail=[alt.Detail("unit:N")],
        tooltip=[
            alt.Tooltip("season:O", title="Season"),
            alt.Tooltip("squad:N", title="Squad"),
            alt.Tooltip("unit:N", title="Unit"),
            alt.Tooltip("players:Q", title="Players"),
        ],
    )

    total_line = (
        base.transform_filter(alt.datum.unit == "Total")
        .mark_line(opacity=0.8,color="#202946", point={"filled": True, "color": "#7d96e8", "stroke":"#202946", "size": 75, "strokeWidth":2}, strokeWidth=3)
    )

    forwards_line = (
        base.transform_filter(alt.datum.unit == "Forwards")
        .mark_line(opacity=0.8, color="blue", point={"filled": True, "color": "blue", "stroke":"darkblue", "size": 50, "strokeWidth":2}, strokeWidth=2)
    )

    backs_line = (
        base.transform_filter(alt.datum.unit == "Backs")
        .mark_line(opacity=0.8, color="black",point={"filled": True, "color":"white", "stroke": "black", "size": 50, "strokeWidth": 2}, strokeWidth=2)
    )

    label_total    = _unit_label(base, "Total", "#202946", "players")
    label_forwards = _unit_label(base, "Forwards", "darkblue", "players")
    label_backs    = _unit_label(base, "Backs", "black", "players")

    chart = (
        alt.layer(total_line, forwards_line, backs_line, label_total, label_forwards, label_backs)
        .properties(width=200, height=400)
        .facet(
            column=alt.Column(
                "squad:N",
                sort=["1st", "2nd"],
                title=None,
                header=alt.Header(
                    labelFontSize=24,
                    labelExpr="datum.value + ' XV'",
                ),
            ),
            spacing=30
        )
        .properties(
            title=alt.Title(
                text="Squad Size",
                subtitle=["Total, forwards and backs representing each squad each season.", "Select Game Type or Min Apps to filter which games count towards the totals."],
            )
        )
    )

    chart.save(output_file)
    return chart


# ===== MIGRATED FROM update.py ===== (Helper functions and chart generation)
other_names = {
    "A Moffatt": "Ali Moffatt",
    "B Beanland": "Bertie Beanland",
    "S Cooke": "Steve Cooke",
    "R Andrews": "Ruari Andrews",
    "R Perry": "Ross Perry",
    "J Stokes": "James Stokes",
    "C Champain": "Callum Champain",
    "M Dewing": "Max Dewing",
    "A Schofield": "Ali Schofield",
    "J Gibbs": "Johnny Gibbs",
    "M Taylor": "Mark Taylor",
    "M Evans": "Max Evans",
    "J Carr": "Josh Carr",
    "Z Roberts": "Zach Roberts",
    "W Blackledge": "Will Blackledge",
    "T Sandys": "Tom Sandys",
    "B Swadling": "Ben Swadling",
    "O Waite": "Oscar Waite",
    "S Anderson": "Scott Anderson",
    "M Ansboro": "Martyn Ansboro",
    "M Tomkinson": "Matt Tomkinson",
    "B Meyerratken": "Ben Meyerratken",
    "L Cammish": "Leo Cammish",
    "C Lear": "Charlie Lear",
}

def clean_name(name):

    name_dict = {
        "Sam Lindsay": "S Lindsay 2",
        "Sam Lindsay-McCall": "S Lindsay",
        "James Mitchell": "T Mitchell",
    }

    if name in name_dict:
        return name_dict[name]

    initial = name.split(" ")[0][0]
    surname = " ".join(name.split(" ")[1:])
    surname = surname.replace("’", "'")
    name_clean = f"{initial} {surname}"
    # trim and title case
    return name_clean.strip().title()


def _table_exists(con, table_name: str) -> bool:
    query = """
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_name = ?
    """
    return con.execute(query, [table_name]).fetchone()[0] > 0


def _using_canonical_backend(db) -> bool:
    con = db.con
    return _table_exists(con, "season_scorers") and _table_exists(con, "players")

def cards_chart(db, output_file='data/charts/cards.json'):
    if _using_canonical_backend(db):
        pitchero_cache_file = db.pitchero_cache_file if hasattr(db, "pitchero_cache_file") else None
        if not pitchero_cache_file or not Path(pitchero_cache_file).exists():
            print("Skipping cards_chart in canonical mode: Pitchero cache not found.")
            return None

        pitchero_df = pd.read_json(pitchero_cache_file)
        expected_cols = {"Season", "Squad", "Player_join", "A", "Event", "Count"}
        if not expected_cols.issubset(set(pitchero_df.columns)):
            print("Skipping cards_chart in canonical mode: Pitchero cache missing required columns.")
            return None

        pitchero_df = pitchero_df[pitchero_df["Event"].isin(["RC", "YC"])].copy()
        pitchero_df["Count"] = pd.to_numeric(pitchero_df["Count"], errors="coerce").fillna(0)
        pitchero_df = pitchero_df[pitchero_df["Count"] > 0]
        if pitchero_df.empty:
            print("Skipping cards_chart in canonical mode: No card data in Pitchero cache.")
            return None

        player_lookup = db.con.execute("SELECT DISTINCT player FROM player_appearances").df()
        player_lookup["Player_join"] = player_lookup["player"].apply(clean_name)
        player_lookup = player_lookup.drop_duplicates(subset=["Player_join"])

        name_lookup = player_lookup.set_index("Player_join")["player"].to_dict()
        name_lookup.update(other_names)

        pitchero_df["player"] = pitchero_df["Player_join"].map(lambda name: name_lookup.get(name, name))
        pitchero_df["event"] = pitchero_df["Event"].map(lambda x: "Red" if x == "RC" else "Yellow" if x == "YC" else x)
        pitchero_df["count"] = pitchero_df["Count"]
        pitchero_df["A"] = pd.to_numeric(pitchero_df["A"], errors="coerce").fillna(0)

        df = pitchero_df[["player", "event", "count", "A", "Season", "Squad"]].rename(
            columns={"Season": "season", "Squad": "squad"}
        )
        
    else:
        df = db.con.execute(
        """
        SELECT 
            A.player,
            P.*
        FROM pitchero_stats P 
        LEFT JOIN (SELECT DISTINCT player, player_join FROM player_appearances) A
        ON A.player_join = P.player_join
        WHERE A.player IS NOT NULL
        AND count > 0
        AND event IN ('RC', 'YC')
        """).df()

        df["event"] = df["event"].map(lambda x: "Red" if x == "RC" else "Yellow" if x == "YC" else x)

    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("sum(count):Q", axis=alt.Axis(title=None, orient="top", format='d')),
        y=alt.Y("player:N", sort="-x", title=None),
        color=alt.Color(
            'event:N', 
            scale=alt.Scale(
                domain=["Red", "Yellow"],
                range=["#d62728", "goldenrod"]
            ),
            legend=alt.Legend(title='Click to filter', orient="none", legendX=300, legendY=100)
        ),
        tooltip=[
            alt.Tooltip('player:N', title='Player'),
            alt.Tooltip('event:N', title='Card Type'),
            alt.Tooltip('sum(count):Q', title='Cards'),
            alt.Tooltip('sum(A):Q', title='Games'),
        ]   
    ).properties(
        width=400,
        height=alt.Step(15),
        title=alt.Title(text='Cards', subtitle='Based on available Pitchero data. Click on legend to filter by card type.')
    )

    chart.save(output_file)

    return chart

def team_sheets_chart(db, output_file='data/charts/team_sheets.json'):
    if _using_canonical_backend(db):
        df = db.con.execute(
            """
            SELECT DISTINCT
                P.player,
                P.number AS shirt_number,
                P.position,
                P.game_id,
                G.date,
                G.opposition,
                G.season,
                G.game_type,
                G.squad,
                G.home_away,
                strftime(G.date, '%Y %m %d') || ' ' || G.squad || ' ' || G.opposition || ' (' || G.home_away || ')' AS game_label,
                CONCAT_WS(' ', G.opposition, CONCAT('(', G.home_away, ')')) AS game_label_short,
                CONCAT_WS(' ', P.position, CONCAT('(', P.number, ')')) AS position_label,
                CONCAT_WS(
                    ' ',
                    SPLIT_PART(P.player, ' ', 1),
                    ARRAY_TO_STRING(
                        LIST_TRANSFORM(SPLIT(SPLIT_PART(P.player, ' ', 2), '-'), x -> SUBSTR(x, 1, 1)),
                        ''
                    )
                ) AS player_label
            FROM player_appearances P
            LEFT JOIN games G USING (game_id)
            ORDER BY G.date DESC, P.number ASC
            """
        ).df()
    else:
        df = db.con.execute(
            """
            SELECT DISTINCT
                P.*,
                G.game_id,
                G.date,
                G.opposition,
                G.season,
                G.game_type,
                G.squad,
                G.home_away,
                strftime(G.date, '%Y %m %d') || ' ' || G.squad || ' ' || G.opposition || ' (' || G.home_away || ')' AS game_label,
                CONCAT_WS(' ', G.opposition, CONCAT('(', G.home_away, ')')) AS game_label_short,
                CONCAT_WS(' ', P.position, CONCAT('(', P.shirt_number, ')')) AS position_label,
                CONCAT_WS(
                    ' ',
                    SPLIT_PART(P.player, ' ', 1), -- FIRST NAME
                    ARRAY_TO_STRING(
                        LIST_TRANSFORM(SPLIT(SPLIT_PART(P.player, ' ', 2), '-'), x -> SUBSTR(x, 1, 1)),
                        ''
                    )
                ) AS player_label
            FROM player_appearances P
            LEFT JOIN games G USING (game_id)
            ORDER BY G.date DESC, P.shirt_number ASC
            """
        ).df()

    player_position_agg = df.groupby(['player', 'position']).size().reset_index(name='count')
    player_primary_position = player_position_agg.loc[player_position_agg.groupby('player')['count'].idxmax()][['player', 'position']]

    # Merge primary position back into main df
    df = df.merge(player_primary_position, on=['player'], how='left', suffixes=('', '_primary'))

    # Selection for player highlighting
    player_highlight = alt.selection_point(
        fields=['player'], 
        on="mouseover",
        clear='mouseout',
        empty='all'
    )
    click_player_highlight = alt.selection_point(
        fields=['player'], 
        on="click",
        clear='dblclick',
        empty='all'
    )

    # Format date as string (e.g., '2024-08-23' -> '23 Aug 2024')
    df['date_str'] = df['date'].dt.strftime('%d %b %Y')

    # Use .encode() with explicit types and field names, avoid ambiguous axis titles
    chart = alt.Chart(df).mark_rect().encode(
        x=alt.X(
            'shirt_number:O',  # Use ordinal for shirt numbers
            title='Shirt Number',
            axis=alt.Axis(labelAngle=0, orient='top', ticks=False)
        ),
        y=alt.Y(
            'game_label:N',
            sort=alt.EncodingSortField(field='date', order='descending'),
            axis=alt.Axis(labelExpr="slice(datum.value,15)", ticks=False, labelAngle=0, labelPadding=10, labelFontSize=11),
            title=None
        ),
        detail='game_id:N',
        color=alt.Color('player:N', scale=alt.Scale(scheme='category20c', domain=player_primary_position.sort_values('position', ascending=True)["player"].unique()), legend=None),
        opacity=alt.condition(click_player_highlight, alt.value(1.0), alt.value(0)),
        stroke=alt.condition(click_player_highlight, alt.value('black'), alt.value(None)),
        tooltip=[
            alt.Tooltip('player:N', title='Player'),
            alt.Tooltip('position_label:N', title='Position'),
            alt.Tooltip('game_type:N', title='Competition'),
            alt.Tooltip('date_str:N', title='Date'),
            alt.Tooltip('game_label_short:N', title='Opposition'),
        ]
    ).add_params(
        player_highlight, click_player_highlight
    )

    # Player name text
    text = alt.Chart(df).mark_text(
        fontSize=12,
        baseline='middle',
        align='center',
        font='PT Sans Narrow'
    ).encode(
        x=alt.X('shirt_number:O', title=None),
        y=alt.Y('game_label:N', sort=alt.EncodingSortField(field='date', order='descending')),
        text=alt.Text('player_label:N'),
        color=alt.value('black'),
        opacity=alt.condition(click_player_highlight, alt.value(1.0), alt.value(0.5)),
        strokeWidth=alt.value(0.5),
        detail='game_id:N'
    )

    team_sheets = (chart + text).properties(
        width=alt.Step(45),
        height=alt.Step(20),
    ).facet(
        row=alt.Row('season:N', title=None, sort=alt.EncodingSortField(field='season', order='descending')),
        column=alt.Column('squad:N', title=None, header=alt.Header(title=None, labelFontSize=36, labelExpr="datum.value + ' XV'", labelAnchor="start")),
        spacing=10
    ).resolve_scale(y='independent', x='independent').configure_view(strokeWidth=0)

    team_sheets.save(output_file)

    return team_sheets


def results_chart(db, output_file='data/charts/results.json'):
    if _using_canonical_backend(db):
        df = db.con.execute(
            """
            SELECT
                game_id,
                date,
                squad,
                opposition,
                home_away,
                CONCAT_WS(' ', opposition, CONCAT('(', home_away, ')')) AS game_label,
                season,
                score_for AS pf,
                score_against AS pa,
                result,
                competition,
                game_type,
                CASE
                    WHEN score_for >= score_against THEN score_for
                    ELSE score_against
                END AS winner,
                CASE
                    WHEN score_for < score_against THEN score_for
                    ELSE score_against
                END AS loser,
                ABS(score_for - score_against) AS margin
            FROM games
            """
        ).df()
    else:
        df = db.con.execute(
            """
            SELECT
                game_id,
                date,
                squad,
                opposition,
                home_away,
                CONCAT_WS(' ', opposition, CONCAT('(', home_away, ')')) AS game_label,
                season,
                pf,
                pa,
                result,
                competition,
                game_type,
                CASE
                    WHEN pf >= pa THEN pf
                    ELSE pa
                END AS winner,
                CASE
                    WHEN pf < pa THEN pf
                    ELSE pa
                END AS loser,
                ABS(pf - pa) AS margin
            FROM games
            """
        ).df()

    team_filter = alt.selection_point(fields=["opposition"], on="hover", clear="mouseout", empty="all")
    selection = alt.selection_point(fields=['result'], bind='legend')

    base = alt.Chart(df).encode(
        y=alt.Y(
            "game_label:N", 
            title=None, 
            sort=alt.EncodingSortField(field='date', order='descending'), 
            axis=alt.Axis(
                title=None, 
                offset=15, 
                grid=False,
                ticks=False, 
                domain=False, 
            )
        ),
        detail='game_id:N',
        color=alt.Color('result:N', scale=alt.Scale(domain=['W', 'L'], range=['#146f14', '#981515']), 
                    legend=alt.Legend(orient="right", title="Result", titleOrient="top")),
        opacity=alt.condition(team_filter, alt.value(1.0), alt.value(0.2)),
    )

    bar = base.mark_bar().encode(
        x=alt.X('pf:Q', title="Points", axis=alt.Axis(orient='bottom', offset=5)),
        x2=alt.X2("pa:Q"),
    ).properties(
        width=400,
        height=alt.Step(15),
    )
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

    chart = (bar + loser + winner).transform_filter(selection).facet(
        row=alt.Row('season:N', title=None, sort=alt.EncodingSortField(field='season', order='descending')),
        column=alt.Column('squad:N', title=None, header=alt.Header(title=None, labelFontSize=36, labelExpr="datum.value + ' XV'", labelAnchor="start")),
        spacing=10
    ).resolve_scale(
        x='independent', y='independent'
    ).add_params(
        team_filter, selection
    ).properties(
        title=alt.Title("Results", subtitle="Points for and against in each game. Hover to highlight all games against a team. Click on legend to filter by result.")
    ).configure_view(strokeWidth=0)
    
    chart.save(output_file)

    return chart

def set_piece_data(db):
    if _using_canonical_backend(db):
        df = db.con.execute(
            """
            WITH base AS (
                SELECT
                    S.game_id,
                    G.squad,
                    G.date,
                    G.opposition,
                    G.home_away,
                    G.season,
                    G.game_type,
                    CASE WHEN S.team = 'EGRFC' THEN 'EG' ELSE 'Opp' END AS team,
                    'Lineout' AS set_piece,
                    S.lineouts_won AS won,
                    S.lineouts_total - S.lineouts_won AS lost
                FROM set_piece S
                JOIN games G USING (game_id)

                UNION ALL

                SELECT
                    S.game_id,
                    G.squad,
                    G.date,
                    G.opposition,
                    G.home_away,
                    G.season,
                    G.game_type,
                    CASE WHEN S.team = 'EGRFC' THEN 'EG' ELSE 'Opp' END AS team,
                    'Scrum' AS set_piece,
                    S.scrums_won AS won,
                    S.scrums_total - S.scrums_won AS lost
                FROM set_piece S
                JOIN games G USING (game_id)
            )
            SELECT
                *,
                REPLACE(CONCAT_WS(' ', game_id, CONCAT('(', home_away, ')')), '_', ' ') AS game_label,
                CONCAT_WS(' ', opposition, CONCAT('(', home_away, ')')) AS game_label_short
            FROM base
            ORDER BY date DESC, set_piece ASC
            """
        ).df()
    else:
        df = db.con.execute(
            """
            SELECT
                S.*,
                G.squad,
                G.date,
                G.opposition,
                G.home_away,
                REPLACE(CONCAT_WS(' ', G.game_id, CONCAT('(', G.home_away, ')')), '_', ' ') AS game_label,
                CONCAT_WS(' ', G.opposition, CONCAT('(', G.home_away, ')')) AS game_label_short,
                G.season,
                G.game_type
            FROM set_piece_stats S
            LEFT JOIN games G USING (game_id)
            ORDER BY G.date DESC, S.set_piece ASC
            """
        ).df()
    return df

def set_piece_chart(df, s="Scrum", output_file=None):

    df_s = df[df['set_piece'] == s].melt(
        id_vars=['game_id', 'date', 'squad', 'opposition', 'game_label', 'game_label_short', 'season', 'game_type', 'team'], 
        value_vars=['won', 'lost'], 
        var_name='outcome', 
        value_name='count'
    )
    df_s["team_out"] = df_s.apply(
        lambda x: "EG" if (x["team"] == "EG" and x["outcome"].lower() == "won") or (x["team"] == "Opp" and x["outcome"].lower() == "lost") else "Opp",
        axis=1
    )
    df_s["Turnover"] = df_s.apply(lambda x: "Retained" if x['team_out']==x['team'] else "Turnover", axis=1)
    df_s["game_id"] = df_s.apply(lambda x: f"{x['game_label_short']}_{x['game_id']}", axis=1)

    df_s["team_total"] = df_s.groupby(['game_id', 'team'])['count'].transform('sum')
    df_s["rate"] = df_s["count"] / df_s["team_total"]
    df_s["team_name"] = df_s["team"].apply(lambda x: "East Grinstead" if x == "EG" else "Opposition")
    df_s["team_out_name"] = df_s["team_out"].apply(lambda x: "East Grinstead" if x == "EG" else "Opposition")
    df_s["success_rate"] = df_s.apply(lambda x: x["count"] / x["team_total"] if x["outcome"] == "won" else 1 - (x["count"] / x["team_total"]), axis=1)

    # Pre-sort the dataframe to avoid complex sorting in Altair
    df_s = df_s.sort_values(['date', 'squad'], ascending=[False, False]).reset_index(drop=True)
    df_s["sort_order"] = df_s.index + 1
    games_list = df_s['game_id'].unique().tolist()

    turnover_filter = alt.selection_point(fields=["Turnover"], bind="legend")
    put_in_filter = alt.selection_point(fields=["team"], bind="legend")
    team_filter = alt.selection_point(fields=["opposition"])

    #################
    ## Won vs Lost ##
    #################
    base = alt.Chart(df_s).encode(
        y=alt.Y(
            'game_id:N', 
            axis=None, 
            sort=games_list,
            scale=alt.Scale(padding=0),
            title=None
        ),
        opacity=alt.Opacity(
            "Turnover:N", 
            scale=alt.Scale(domain=["Turnover", "Retained"], range=[1.0, 0.5]),
            legend=alt.Legend(
                title="Result", 
                orient="right", 
                direction="vertical",
            ),
        ),
        tooltip=[
            alt.Tooltip('squad:N', title='Squad'),
            alt.Tooltip('season:N', title='Season'),
            alt.Tooltip('date:T', title='Date', format='%d %b %Y'),
            alt.Tooltip('game_label_short:N', title='Game'),
            alt.Tooltip('team_name:N', title='Attacking Team'),
            alt.Tooltip('team_out_name:N', title='Winning Team'),
            alt.Tooltip('count:Q', title='Count'),
        ],
        detail="opposition:N",
    ).properties(
        width=150,
        height=alt.Step(10),
    ).add_params(team_filter, turnover_filter, put_in_filter
    ).transform_filter(team_filter).transform_filter(turnover_filter).transform_filter(put_in_filter)

    eg = base.mark_bar(stroke="#202946").encode(
        x=alt.X(
            'count:Q', 
            title=f'{s}s Won', 
            axis=alt.Axis(format='d', title="EG wins", titleColor="#202946", orient='top'), 
            scale=alt.Scale(domain=[0, df_s['count'].max()+1])
        ),
        yOffset=alt.YOffset('team:N', scale=alt.Scale(paddingOuter=0.2)),
        color=alt.Color(
            "team:N", 
            scale=alt.Scale(domain=['EG', 'Opp'], range=['#202946', '#981515']),
            legend=alt.Legend(title="Attacking team", orient="right", direction="horizontal")
        )
    ).transform_filter(alt.datum.team_out == 'EG')

    opp = base.mark_bar(stroke="#981515").encode(
        x=alt.X(
            'count:Q', 
            title=f'{s}s Won', 
            axis=alt.Axis(format='d', title="Opposition wins", titleColor="#981515", orient='top'), 
            scale=alt.Scale(reverse=True, domain=[0, df_s['count'].max()+1]), 
            sort='descending'
        ),
        yOffset=alt.YOffset('team:N', scale=alt.Scale(paddingOuter=0.2)),
        color=alt.Color(
            "team:N", 
            scale=alt.Scale(domain=['EG', 'Opp'], range=['#202946', '#981515']),
            legend=alt.Legend(title="Attacking team", orient="right", direction="horizontal")
        ),
        y=alt.Y(
            'game_id:N', 
            axis=alt.Axis(orient="left", labelExpr="split(datum.value, '_')[0]", ticks=False, domain=False),
            sort=games_list,
            scale=alt.Scale(padding=0),
            title=None
        )
    ).transform_filter(alt.datum.team_out == 'Opp')

    ##################
    ## Success Rate ##
    ##################

    df_success = df_s[df_s['outcome'] == 'won'].copy()
    # Add a sort order field based on games_list position
    game_sort_order = {game_id: i for i, game_id in enumerate(games_list)}
    df_success['sort_order'] = df_success['game_id'].map(game_sort_order)

    success_rate_eg = alt.Chart(df_success[df_success['team'] == 'EG']).mark_area(
        line={'color': '#202946'},
        point={'filled': True, 'color': '#202946'},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color='white', offset=0), alt.GradientStop(color='#202946', offset=1)],
        )
    ).encode(
        x=alt.X("success_rate:Q", title="Success Rate", axis=alt.Axis(format='.0%', titleColor='black', orient='top'), scale=alt.Scale(domain=[0, 1])),
        y=alt.Y('game_id:N', axis=alt.Axis(orient="left", labels=False, ticks=False), sort=games_list, scale=alt.Scale(padding=0), title=None),
        yOffset=alt.YOffset('team:N', scale=alt.Scale(paddingOuter=0.2)),
        opacity=alt.value(0.75),
        tooltip=[
            alt.Tooltip('squad:N', title='Squad'),
            alt.Tooltip('season:N', title='Season'),
            alt.Tooltip('date:T', title='Date', format='%d %b %Y'),
            alt.Tooltip('game_label_short:N', title='Game'),
            alt.Tooltip('team_name:N', title='Attacking Team'),
            alt.Tooltip('team_total:Q', title=f'{s}s', format=',d'),
            alt.Tooltip('success_rate:Q', title='Success Rate', format='.0%')
        ],
    )

    success_rate_opp = alt.Chart(df_success[df_success['team'] == 'Opp']).mark_area(
        line={'color': '#981515'},
        point={'filled': True, 'color': '#981515'},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color='white', offset=0), alt.GradientStop(color='#981515', offset=1)],
        )
    ).encode(
        x=alt.X("success_rate:Q", title="Success Rate", axis=alt.Axis(format='.0%', titleColor='black', orient='top'), scale=alt.Scale(domain=[0, 1])),
        y=alt.Y('game_id:N', axis=alt.Axis(orient="left", labels=False, ticks=False), sort=games_list, scale=alt.Scale(padding=0), title=None),
        yOffset=alt.YOffset('team:N', scale=alt.Scale(paddingOuter=0.2)),
        opacity=alt.value(0.75),
        tooltip=[
            alt.Tooltip('squad:N', title='Squad'),
            alt.Tooltip('season:N', title='Season'),
            alt.Tooltip('date:T', title='Date', format='%d %b %Y'),
            alt.Tooltip('game_label_short:N', title='Game'),
            alt.Tooltip('team_name:N', title='Attacking Team'),
            alt.Tooltip('team_total:Q', title=f'{s}s', format=',d'),
            alt.Tooltip('success_rate:Q', title='Success Rate', format='.0%')
        ],
    )

    success_rate_eg = success_rate_eg.transform_filter(team_filter).transform_filter(put_in_filter)
    success_rate_opp = success_rate_opp.transform_filter(team_filter).transform_filter(put_in_filter)

    ###########
    ## FINAL ##
    ###########
    chart = (
        opp | eg | 
        (success_rate_eg + success_rate_opp).add_params(team_filter, put_in_filter)
    ).resolve_scale(
        x='independent', y='shared'
    ).properties(
        title=alt.Title(f"{s} Success", subtitle=[f"{s} results in terms of attacking team (EG in blue, opposition in red), and which team won the ball.", "Games are listed in chronological order with most recent at the top.", "Click the chart to filter by opposition. Click the legends to filter by attacking team or result."],)
    )
    
    if output_file:
        chart.save(output_file)
    else:
        chart.save(f'data/charts/{s.lower()}_success.json')

    return chart


def set_piece_success_by_season_chart(
    db,
    output_file="data/charts/set_piece_success_by_season.json",
    output_dir="data/charts",
    layout="separate",
):
    """Generate seasonal set-piece success charts with crossover-aware area shading.

    layout="faceted" writes one faceted chart to output_file.
    layout="separate" writes four charts split by squad and set piece type.
    """

    if _using_canonical_backend(db):
        set_piece_df = db.con.execute(
            """
            WITH totals AS (
                SELECT
                    team,
                    season,
                    squad,
                    SUM(lineouts_won) AS lineouts_won,
                    SUM(lineouts_total) AS lineouts_total,
                    SUM(scrums_won) AS scrums_won,
                    SUM(scrums_total) AS scrums_total
                FROM set_piece
                GROUP BY team, season, squad
            )
            SELECT
                team,
                CONCAT(squad, ' XV') AS squad,
                season,
                'Lineout' AS set_piece_type,
                lineouts_won::DOUBLE / NULLIF(lineouts_total, 0) AS success_rate,
                lineouts_total AS lineouts_total
            FROM totals

            UNION ALL

            SELECT
                team,
                CONCAT(squad, ' XV') AS squad,
                season,
                'Scrum' AS set_piece_type,
                scrums_won::DOUBLE / NULLIF(scrums_total, 0) AS success_rate,
                lineouts_total AS lineouts_total
            FROM totals

            ORDER BY team, season, squad, set_piece_type
            """
        ).df()
    else:
        # Legacy backend is unsupported for update flow, but keep a safe fallback.
        set_piece_df = pd.DataFrame(
            columns=["team", "squad", "season", "set_piece_type", "success_rate", "lineouts_total"]
        )

    if set_piece_df.empty:
        print("Skipping set_piece_success_by_season_chart: no set piece data available.")
        return None

    set_piece_df = set_piece_df.dropna(subset=["success_rate"]).copy()
    if set_piece_df.empty:
        print("Skipping set_piece_success_by_season_chart: no valid success-rate rows available.")
        return None

    color_scale = alt.Scale(domain=["EGRFC", "Opposition"], range=["#202946", "#991515"])

    def _season_sort_key(value):
        season_text = str(value)
        year_prefix = "".join(ch for ch in season_text[:4] if ch.isdigit())
        return (int(year_prefix) if year_prefix else 0, season_text)

    season_order = sorted(set_piece_df["season"].astype(str).unique(), key=_season_sort_key)
    season_pos = {season: i for i, season in enumerate(season_order)}
    season_ticks = list(season_pos.values())
    season_label_expr = " : ".join(
        [f"datum.value == {idx} ? '{season}'" for season, idx in season_pos.items()] + ["''"]
    )

    wide_rates = (
        set_piece_df
        .pivot_table(
            index=["squad", "set_piece_type", "season"],
            columns="team",
            values="success_rate",
            aggfunc="first",
        )
        .reset_index()
    )

    wide_lineouts = (
        set_piece_df
        .pivot_table(
            index=["squad", "set_piece_type", "season"],
            columns="team",
            values="lineouts_total",
            aggfunc="first",
        )
        .reset_index()
        .rename(columns={"EGRFC": "EGRFC_lineouts", "Opposition": "Opposition_lineouts"})
    )

    wide = wide_rates.merge(wide_lineouts, on=["squad", "set_piece_type", "season"], how="left")
    wide["season"] = wide["season"].astype(str)
    wide["season_pos"] = wide["season"].map(season_pos)
    wide = wide.dropna(subset=["EGRFC", "Opposition"]).sort_values(["squad", "set_piece_type", "season_pos"])

    long_rows = []
    steps_per_segment = 30

    for (squad, set_piece_type), grp in wide.groupby(["squad", "set_piece_type"], sort=False):
        grp = grp.sort_values("season_pos").reset_index(drop=True)
        if grp.empty:
            continue

        if len(grp) == 1:
            anchors = [(grp.iloc[0], grp.iloc[0], 0, 1)]
        else:
            anchors = []
            for i in range(len(grp) - 1):
                a = grp.iloc[i]
                b = grp.iloc[i + 1]
                start = 0 if i == 0 else 1
                anchors.append((a, b, start, steps_per_segment))

        for a, b, start, end in anchors:
            for t_i in range(start, end + 1):
                t = 0.0 if end == 0 else (t_i / end)
                season_pos_i = float(a["season_pos"] + t * (b["season_pos"] - a["season_pos"]))
                egrfc_i = float(a["EGRFC"] + t * (b["EGRFC"] - a["EGRFC"]))
                opposition_i = float(a["Opposition"] + t * (b["Opposition"] - a["Opposition"]))
                egrfc_lineouts = float(a["EGRFC_lineouts"] + t * (b["EGRFC_lineouts"] - a["EGRFC_lineouts"]))
                opposition_lineouts = float(a["Opposition_lineouts"] + t * (b["Opposition_lineouts"] - a["Opposition_lineouts"]))
                y_high = max(egrfc_i, opposition_i)
                y_low = min(egrfc_i, opposition_i)
                leading_team = "EGRFC" if egrfc_i >= opposition_i else "Opposition"
                is_anchor = (t_i == 0) or (t_i == end)

                long_rows.append(
                    {
                        "squad": squad,
                        "set_piece_type": set_piece_type,
                        "season_pos": season_pos_i,
                        "team": "EGRFC",
                        "success_rate": egrfc_i,
                        "lineouts_total": egrfc_lineouts,
                        "y_high": y_high,
                        "y_low": y_low,
                        "leading_team": leading_team,
                        "is_anchor": is_anchor,
                    }
                )
                long_rows.append(
                    {
                        "squad": squad,
                        "set_piece_type": set_piece_type,
                        "season_pos": season_pos_i,
                        "team": "Opposition",
                        "success_rate": opposition_i,
                        "lineouts_total": opposition_lineouts,
                        "y_high": y_high,
                        "y_low": y_low,
                        "leading_team": leading_team,
                        "is_anchor": is_anchor,
                    }
                )

    dense_long_df = pd.DataFrame(long_rows)
    if dense_long_df.empty:
        print("Skipping set_piece_success_by_season_chart: insufficient grouped rows for charting.")
        return None

    def _build_chart(df, width=220, height=260):
        base = alt.Chart(df).properties(width=width, height=height)

        between_areas = base.transform_filter(
            alt.datum.team == "EGRFC"
        ).mark_area(opacity=0.28).encode(
            x=alt.X(
                "season_pos:Q",
                title="Season",
                scale=alt.Scale(domain=[min(season_ticks), max(season_ticks)]),
                axis=alt.Axis(values=season_ticks, labelExpr=season_label_expr, grid=False),
            ),
            y=alt.Y(
                "y_high:Q",
                title="Success Rate",
                scale=alt.Scale(domain=[0.0, 1.0]),
                axis=alt.Axis(format="%", orient="left"),
            ),
            y2="y_low:Q",
            color=alt.Color(
                "leading_team:N",
                title="Team",
                scale=color_scale,
                legend=alt.Legend(orient="right", title=None, labelFont="PT Sans Narrow"),
            ),
        )

        lines = base.mark_line(size=2).encode(
            x=alt.X(
                "season_pos:Q",
                title="Season",
                scale=alt.Scale(domain=[min(season_ticks), max(season_ticks)]),
                axis=alt.Axis(values=season_ticks, labelExpr=season_label_expr),
            ),
            y=alt.Y(
                "success_rate:Q",
                title=None,
                scale=alt.Scale(domain=[0.0, 1.0]),
                axis=alt.Axis(format="%", orient="right"),
            ),
            color=alt.Color("team:N", title="Team", scale=color_scale),
        )

        points = base.transform_filter(
            alt.datum.is_anchor
        ).mark_point(size=55, filled=True, opacity=1.0).encode(
            x=alt.X("season_pos:Q", title="Season"),
            y=alt.Y("success_rate:Q", title="Success Rate", scale=alt.Scale(domain=[0.0, 1.0]), axis=None),
            color=alt.Color("team:N", title="Team", scale=color_scale),
            tooltip=[
                alt.Tooltip("team:N", title="Team"),
                alt.Tooltip("squad:N", title="Squad"),
                alt.Tooltip("set_piece_type:N", title="Set Piece"),
                alt.Tooltip("lineouts_total:Q", title="Total Lineouts", format=",.0f"),
                alt.Tooltip("success_rate:Q", title="Success Rate", format=".0%"),
            ],
        )

        return between_areas + lines + points

    layout_value = str(layout).strip().lower()
    if layout_value == "faceted":
        chart = _build_chart(dense_long_df, width=150, height=220).facet(
            row=alt.Row("set_piece_type:N", title=None),
            column=alt.Column("squad:N", title=None, header=alt.Header(labelFontSize=24)),
        ).properties(
            title=alt.Title(
                text="Set Piece Success",
                subtitle="Percentage of lineouts and scrums won for EGRFC and their opposition.",
            )
        )
        chart.save(output_file)
        return chart

    if layout_value != "separate":
        raise ValueError("layout must be either 'separate' or 'faceted'")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    chart_targets = [
        ("1st XV", "Scrum", "set_piece_success_1st_scrum.json"),
        ("1st XV", "Lineout", "set_piece_success_1st_lineout.json"),
        ("2nd XV", "Scrum", "set_piece_success_2nd_scrum.json"),
        ("2nd XV", "Lineout", "set_piece_success_2nd_lineout.json"),
    ]

    charts = {}
    for squad_label, set_piece_type, filename in chart_targets:
        subset = dense_long_df[
            dense_long_df["squad"].eq(squad_label) & dense_long_df["set_piece_type"].eq(set_piece_type)
        ].copy()

        if subset.empty:
            print(f"Skipping {filename}: no rows for {squad_label} {set_piece_type}.")
            continue

        title_text = f"{set_piece_type} Success"
        subtitle_text = "Seasonal success for EGRFC and opposition, with crossover-shaded advantage."
        chart = _build_chart(subset, width=200, height=300).properties(
            title=alt.Title(text=title_text, subtitle=subtitle_text)
        )

        chart_path = output_root / filename
        chart.save(str(chart_path))
        charts[f"{squad_label}_{set_piece_type}".replace(" ", "_").lower()] = chart

    return charts


def lineout_success_by_zone_chart(db, output_file='data/charts/lineout_success_by_zone.json'):
    if _using_canonical_backend(db):
        df = db.con.execute(
            """
            SELECT
                squad AS Squad,
                area AS Area,
                thrower AS Hooker,
                jumper AS Jumper,
                won AS Won
            FROM lineouts
            """
        ).df()
    else:
        df = db.con.execute(
            """
            SELECT
                G.squad AS Squad,
                L.area AS Area,
                L.hooker AS Hooker,
                L.jumper AS Jumper,
                L.won AS Won
            FROM lineouts L
            JOIN games G ON G.game_id = L.game_id
            """
        ).df()

    return lineout_success_by_zone(df=df, file=output_file)

#################################
# League Analysis Charts
#################################
def league_results_chart(db, season="2024-2025", league="Counties 1 Surrey/Sussex", output_file='data/charts/league_results.json'):
    """Create league results matrix chart"""
    
    # Query league match data
    df = db.con.execute(
        """
        SELECT 
            match_id,
            date,
            home_team,
            away_team,
            home_score,
            away_score,
            (home_score - away_score) as point_difference,
            CASE 
                WHEN home_score > away_score THEN 'Home Win'
                WHEN home_score < away_score THEN 'Away Win'
                WHEN home_score = away_score THEN 'Draw'
                ELSE 'To be played'
            END as result,
            CASE 
                WHEN ABS(home_score - away_score) <= 7 AND home_score != away_score THEN TRUE
                ELSE FALSE
            END as losing_bonus_point
        FROM league_matches 
        WHERE season = ? AND league = ?
        ORDER BY date DESC
        """, [season, league]
    ).df()
    
    if df.empty:
        print(f"No league data found for {season} {league}")
        return None
    
    # Get all teams
    teams = sorted(set(df['home_team'].unique()) | set(df['away_team'].unique()))
    
    # Create full matrix (all team combinations)
    import itertools
    all_combinations = list(itertools.product(teams, repeat=2))
    matrix_df = pd.DataFrame(all_combinations, columns=['home_team', 'away_team'])
    
    # Merge with actual results
    matrix_df = matrix_df.merge(df, on=['home_team', 'away_team'], how='left')
    matrix_df['result'] = matrix_df['result'].fillna('To be played')
    matrix_df['score_text'] = matrix_df.apply(
        lambda x: f"{x['home_score']}-{x['away_score']}" if pd.notna(x['home_score']) else "",
        axis=1
    )
    
    # Color scale
    color_scale = alt.Scale(
        domain=['Home Win', 'Away Win', 'Draw', 'To be played'],
        range=['#146f14', '#991515', 'goldenrod', 'white']
    )
    
    # Team highlight selection
    team_highlight = alt.selection_point(
        fields=['home_team'], 
        on='click',
        clear='dblclick'
    )
    
    # Base chart
    base = alt.Chart(matrix_df).add_params(team_highlight)
    
    # Heatmap
    heatmap = base.mark_rect(stroke='black', strokeWidth=1).encode(
        x=alt.X('away_team:N', title='Away Team', sort=teams, axis=alt.Axis(labelAngle=45)),
        y=alt.Y('home_team:N', title='Home Team', sort=teams[::-1]),
        color=alt.Color('result:N', scale=color_scale, legend=alt.Legend(title='Result')),
        opacity=alt.condition(
            alt.expr(f"datum.home_team == {team_highlight.name}['home_team'] || datum.away_team == {team_highlight.name}['home_team']"),
            alt.value(1.0),
            alt.value(0.3)
        ),
        tooltip=[
            'home_team:N',
            'away_team:N', 
            'score_text:N',
            'result:N',
            alt.Tooltip('date:T', format='%d %b %Y')
        ]
    )
    
    # Score text
    score_text = base.mark_text(fontSize=12, fontWeight='bold').encode(
        x=alt.X('away_team:N', sort=teams),
        y=alt.Y('home_team:N', sort=teams[::-1]),
        text='score_text:N',
        color=alt.value('white'),
        opacity=alt.condition(
            alt.expr(f"datum.home_team == {team_highlight.name}['home_team'] || datum.away_team == {team_highlight.name}['home_team']"),
            alt.value(1.0),
            alt.value(0.7)
        )
    )
    
    chart = (heatmap + score_text).properties(
        width=alt.Step(50),
        height=alt.Step(35),
        title=alt.Title(
            text=f"League Results - {season}",
            subtitle=["Click on a cell to highlight all games for that team", "Double-click to reset"]
        )
    )
    
    chart.save(output_file)
    return chart

def league_squad_analysis_chart(db, season="2024-2025", league="Counties 1 Surrey/Sussex", output_file='data/charts/league_squad_analysis.json'):
    """Create squad analysis charts"""
    
    # Get appearance data
    df = db.con.execute(
        """
        SELECT 
            lp.team,
            lp.player,
            lp.unit,
            COUNT(*) as appearances,
            lm.date,
            lm.season,
            lm.league
        FROM league_players lp
        JOIN league_matches lm ON lp.match_id = lm.match_id
        WHERE lm.season = ? AND lm.league = ?
        GROUP BY lp.team, lp.player, lp.unit, lm.season, lm.league
        ORDER BY appearances DESC
        """, [season, league]
    ).df()
    
    if df.empty:
        print(f"No league player data found for {season} {league}")
        return None
    
    # Team selection
    team_select = alt.selection_point(
        fields=['team'],
        bind=alt.binding_select(
            options=[None] + sorted(df['team'].unique()),
            labels=['All Teams'] + sorted(df['team'].unique()),
            name='Team'
        )
    )
    
    # Most appearances chart
    appearances_chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('appearances:Q', title='Appearances'),
        y=alt.Y('player:N', sort='-x', title=None),
        color=alt.Color('team:N', legend=None),
        opacity=alt.condition(team_select, alt.value(1.0), alt.value(0.2)),
        tooltip=['player:N', 'team:N', 'appearances:Q']
    ).add_params(team_select).transform_filter(
        team_select
    ).transform_window(
        rank='rank(appearances)',
        sort=[alt.SortField('appearances', order='descending')]
    ).transform_filter(
        alt.datum.rank <= 20
    ).properties(
        width=400,
        height=300,
        title='Most Appearances'
    )
    
    # Squad size by team
    squad_size = df.groupby(['team', 'unit']).size().reset_index(name='player_count')
    
    squad_size_chart = alt.Chart(squad_size).mark_bar().encode(
        x=alt.X('player_count:Q', title='Number of Players'),
        y=alt.Y('team:N', sort='-x', title=None),
        color=alt.Color('unit:N', legend=alt.Legend(title='Unit')),
        opacity=alt.condition(team_select, alt.value(1.0), alt.value(0.2)),
        tooltip=['team:N', 'unit:N', 'player_count:Q']
    ).add_params(team_select).properties(
        width=400,
        height=300,
        title='Squad Size by Unit'
    )
    
    chart = alt.hconcat(appearances_chart, squad_size_chart).resolve_scale(
        color='independent'
    ).properties(
        title=alt.Title(
            text=f"League Squad Analysis - {season}",
            subtitle=f"{league}"
        )
    )
    
    chart.save(output_file)
    return chart

def season_summary_data(db, output_file='data/season_summary.json'):
    """Generate comprehensive season summary statistics for all seasons, squads, and game types."""
    
    # Get games results data (wins/losses/draws)
    results_data = db.con.execute(
        """
        SELECT
            season,
            squad,
            game_type,
            COUNT(*) as games_played,
            SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as games_won,
            SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) as games_lost,
            SUM(CASE WHEN result = 'D' THEN 1 ELSE 0 END) as games_drawn,
            ROUND(AVG(CASE WHEN home_away = 'H' THEN score_for ELSE NULL END), 2) as avg_pf_home,
            ROUND(AVG(CASE WHEN home_away = 'H' THEN score_against ELSE NULL END), 2) as avg_pa_home,
            ROUND(AVG(CASE WHEN home_away = 'A' THEN score_for ELSE NULL END), 2) as avg_pf_away,
            ROUND(AVG(CASE WHEN home_away = 'A' THEN score_against ELSE NULL END), 2) as avg_pa_away,
            ROUND(AVG(score_for), 2) as avg_pf_overall,
            ROUND(AVG(score_against), 2) as avg_pa_overall,
            SUM(CASE WHEN home_away = 'H' THEN 1 ELSE 0 END) as home_games,
            SUM(CASE WHEN home_away = 'A' THEN 1 ELSE 0 END) as away_games
        FROM games
        GROUP BY season, squad, game_type
        ORDER BY season DESC, squad, game_type
        """
    ).df()
    
    # Get top point scorers per season/squad
    point_scorers = db.con.execute(
        """
        SELECT
            s.season,
            s.squad,
            s.player,
            s.points,
            s.tries,
            s.conversions,
            s.penalties,
            s.drop_goals,
            ROW_NUMBER() OVER (PARTITION BY s.season, s.squad ORDER BY s.points DESC) as rank
        FROM season_scorers s
        WHERE points > 0
        ORDER BY s.season DESC, s.squad, s.points DESC
        """
    ).df()
    
    # Get top try scorers per season/squad
    try_scorers = db.con.execute(
        """
        SELECT
            s.season,
            s.squad,
            s.player,
            s.tries,
            s.points,
            ROW_NUMBER() OVER (PARTITION BY s.season, s.squad ORDER BY s.tries DESC) as rank
        FROM season_scorers s
        WHERE tries > 0
        ORDER BY s.season DESC, s.squad, s.tries DESC
        """
    ).df()
    
    # Get most appearances per season/squad/game_type
    # Reconciliation backfill rows are emitted as game_type='Unknown' with starts=0.
    appearances = db.con.execute(
            """
            WITH base AS (
                SELECT
                    COALESCE(G.season, P.season) AS season,
                    COALESCE(G.squad, P.squad) AS squad,
                    CASE WHEN P.is_backfill THEN 'Unknown' ELSE G.game_type END AS game_type,
                    P.player,
                    COUNT(*) AS appearances,
                    SUM(CASE WHEN P.is_backfill = FALSE AND P.is_starter = TRUE THEN 1 ELSE 0 END) AS starts
                FROM player_appearances P
                LEFT JOIN games G USING (game_id)
                GROUP BY
                    COALESCE(G.season, P.season),
                    COALESCE(G.squad, P.squad),
                    CASE WHEN P.is_backfill THEN 'Unknown' ELSE G.game_type END,
                    P.player
            )
            SELECT
                season,
                squad,
                game_type,
                player,
                appearances,
                starts,
                ROW_NUMBER() OVER (
                    PARTITION BY season, squad, game_type
                    ORDER BY appearances DESC, player ASC
                ) AS rank
            FROM base
            ORDER BY season DESC, squad, game_type, appearances DESC
            """
    ).df()
    
    # Get average set piece stats per season/squad
    set_piece_stats = db.con.execute(
        """
        SELECT
            g.season,
            g.squad,
            ROUND(AVG(s.lineouts_success_rate), 3) as avg_lineout_success_rate,
            ROUND(AVG(s.scrums_success_rate), 3) as avg_scrum_success_rate,
            ROUND(AVG(s.points_per_22m_entry), 2) as avg_points_per_22m_entry,
            ROUND(AVG(s.tries_per_22m_entry), 2) as avg_tries_per_22m_entry,
            COUNT(*) as games_with_set_piece_data
        FROM set_piece s
        JOIN games g ON s.game_id = g.game_id
        WHERE s.team = 'EGRFC'
        GROUP BY g.season, g.squad
        ORDER BY g.season DESC, g.squad
        """
    ).df()
    
    # Convert DataFrames to dictionaries, replacing NaN with None
    def df_to_records(df):
        """Convert DataFrame to records, replacing NaN with None."""
        records = []
        for _, row in df.iterrows():
            record = {}
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    record[col] = None
                else:
                    record[col] = val
            records.append(record)
        return records
    
    # Build output dictionary
    summary = {
        "games_results": df_to_records(results_data),
        "top_point_scorers": df_to_records(point_scorers),
        "top_try_scorers": df_to_records(try_scorers),
        "most_appearances": df_to_records(appearances),
        "set_piece_stats": df_to_records(set_piece_stats)
    }
    
    # Save to JSON
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Season summary data saved to {output_file}")
    return summary


def player_profiles_data(db, output_file='data/player_profiles.json'):
    """Build frontend-ready player profile data from canonical backend tables."""
    profiles_df = db.con.execute(
        """
        SELECT
            name,
            short_name,
            position,
            squad,
            first_appearance_date,
            first_appearance_squad,
            first_appearance_opposition,
            photo_url,
            sponsor,
            total_appearances,
            total_starts,
            total_captaincies,
            total_vc_appointments,
            total_lineouts_jumped,
            lineouts_won_as_jumper,
            career_points,
            latest_season_points,
            latest_season_tries,
            latest_season_conversions,
            latest_season_penalties
        FROM v_player_profiles
        ORDER BY total_appearances DESC, name ASC
        """
    ).df()

    season_apps_df = db.con.execute(
        """
        SELECT
            player AS name,
            season,
            squad,
            COUNT(*) AS appearances,
            SUM(CASE WHEN is_starter THEN 1 ELSE 0 END) AS starts
        FROM player_appearances
        GROUP BY player, season, squad
        ORDER BY season DESC, squad ASC
        """
    ).df()

    season_points_df = db.con.execute(
        """
        SELECT
            player AS name,
            season,
            squad,
            COALESCE(points, 0) AS points,
            COALESCE(tries, 0) AS tries,
            COALESCE(conversions, 0) AS conversions,
            COALESCE(penalties, 0) AS penalties,
            COALESCE(drop_goals, 0) AS drop_goals
        FROM season_scorers
        ORDER BY season DESC, squad ASC
        """
    ).df()

    def _clean_int(value):
        if pd.isna(value):
            return 0
        return int(value)

    def _clean_text(value):
        if pd.isna(value):
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned else None

    def _normalise_date(value):
        if pd.isna(value):
            return None
        try:
            return pd.to_datetime(value).strftime("%Y-%m-%d")
        except Exception:
            return str(value)

    # De-duplicate by player name while preserving strongest aggregate totals.
    deduped = {}
    for _, row in profiles_df.iterrows():
        name = _clean_text(row.get("name"))
        if not name:
            continue

        candidate = {
            "name": name,
            "short_name": _clean_text(row.get("short_name")),
            "position": _clean_text(row.get("position")) or "Unknown",
            "squad": _clean_text(row.get("squad")) or "Unknown",
            "first_appearance_date": _normalise_date(row.get("first_appearance_date")),
            "first_appearance_squad": _clean_text(row.get("first_appearance_squad")),
            "first_appearance_opposition": _clean_text(row.get("first_appearance_opposition")),
            "photo_url": _clean_text(row.get("photo_url")),
            "sponsor": _clean_text(row.get("sponsor")),
            "total_appearances": _clean_int(row.get("total_appearances")),
            "total_starts": _clean_int(row.get("total_starts")),
            "total_captaincies": _clean_int(row.get("total_captaincies")),
            "total_vc_appointments": _clean_int(row.get("total_vc_appointments")),
            "total_lineouts_jumped": _clean_int(row.get("total_lineouts_jumped")),
            "lineouts_won_as_jumper": _clean_int(row.get("lineouts_won_as_jumper")),
            "career_points": _clean_int(row.get("career_points")),
            "latest_season_points": _clean_int(row.get("latest_season_points")),
            "latest_season_tries": _clean_int(row.get("latest_season_tries")),
            "latest_season_conversions": _clean_int(row.get("latest_season_conversions")),
            "latest_season_penalties": _clean_int(row.get("latest_season_penalties")),
        }

        existing = deduped.get(name)
        if not existing or candidate["total_appearances"] > existing["total_appearances"]:
            deduped[name] = candidate

    appearances_by_player = defaultdict(list)
    for _, row in season_apps_df.iterrows():
        name = _clean_text(row.get("name"))
        season = _clean_text(row.get("season"))
        squad = _clean_text(row.get("squad"))
        if not name or not season:
            continue
        appearances_by_player[name].append(
            {
                "season": season,
                "squad": squad,
                "appearances": _clean_int(row.get("appearances")),
                "starts": _clean_int(row.get("starts")),
            }
        )

    points_by_player = defaultdict(list)
    for _, row in season_points_df.iterrows():
        name = _clean_text(row.get("name"))
        season = _clean_text(row.get("season"))
        squad = _clean_text(row.get("squad"))
        if not name or not season:
            continue
        points_by_player[name].append(
            {
                "season": season,
                "squad": squad,
                "points": _clean_int(row.get("points")),
                "tries": _clean_int(row.get("tries")),
                "conversions": _clean_int(row.get("conversions")),
                "penalties": _clean_int(row.get("penalties")),
                "drop_goals": _clean_int(row.get("drop_goals")),
            }
        )

    profiles = []
    for profile in deduped.values():
        name = profile["name"]
        profile["season_appearances"] = appearances_by_player.get(name, [])
        profile["season_points"] = points_by_player.get(name, [])
        profiles.append(profile)

    profiles.sort(key=lambda row: (-row["total_appearances"], row["name"]))

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(profiles, handle, indent=2)

    print(f"Player profiles data saved to {output_file} ({len(profiles)} players)")
    return profiles

# Update the main() function
