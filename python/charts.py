import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json
from collections import defaultdict
import altair as alt
import pandas as pd
import re
import duckdb
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
        gameTypesParam  – [] (all) or an array of allowed game_type strings
        squadParam      – 'All', '1st', or '2nd'
        scoreTypeParam  – 'Total', 'Tries', or 'Kicks'
    """

    base_df = db.con.execute(
        """
        SELECT
            squad,
            season,
            player,
            COALESCE(game_type, 'Unknown') AS game_type,
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
    game_types_param = alt.param(name='gameTypesParam', value=[])
    # Optional companion param for frontend compatibility; filtering is driven by gameTypesParam.
    game_type_param = alt.param(name='gameTypeParam', value='All games')
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
            alt.Tooltip('game_type:N', title='Game Type'),
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
        .transform_filter('length(gameTypesParam) === 0 || indexof(gameTypesParam, datum.game_type) >= 0')
        .transform_filter('squadParam === "All" || datum.squad === squadParam')
        .transform_filter('scoreTypeParam === datum.score_type')
        .transform_joinaggregate(player_total='sum(value)', groupby=['player'])
        .transform_filter('datum.player_total > 0')
        .add_params(season_param, game_types_param, game_type_param, squad_param, score_type_param)
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


def player_full_profile_appearances_per_season_chart(db, output_file='data/charts/player_full_profile_appearances_per_season'):
    """Generate per-player appearances-by-season specs for the full profile page.

    Writes three standalone Vega-Lite specs with fixed colour scales:
        *_squad.json
        *_result.json
        *_position.json
    Frontend code filters the chosen spec to a single player based on the Colour By selector.
    """

    base_df = db.con.execute(
        """
        SELECT
            P.player,
            COALESCE(G.season, P.season) AS season,
            COALESCE(G.squad, P.squad, 'Unknown') AS squad,
            CASE
                WHEN COALESCE(G.result, '') = 'W' THEN 'Win'
                WHEN COALESCE(G.result, '') = 'L' THEN 'Loss'
                WHEN COALESCE(G.result, '') = 'D' THEN 'Draw'
                ELSE 'Unknown'
            END AS result,
            CASE
                WHEN P.is_backfill THEN 'Unknown'
                ELSE COALESCE(P.position, 'Unknown')
            END AS position,
            COUNT(*) AS apps
        FROM player_appearances P
        LEFT JOIN games G USING (game_id)
        GROUP BY 1, 2, 3, 4, 5
        """
    ).df()

    if base_df.empty:
        base_df = pd.DataFrame(columns=['player', 'season', 'squad', 'result', 'position', 'apps', 'season_sort'])

    def season_sort_key(value):
        text = str(value or '')
        match = re.match(r'^(\d{4})/(\d{2}|\d{4})$', text)
        if not match:
            return 0
        return int(match.group(1))

    base_df['season_sort'] = base_df['season'].map(season_sort_key)

    by_squad = base_df[['player', 'season', 'season_sort', 'apps']].copy()
    by_squad['color_mode'] = 'Squad'
    by_squad['color_value'] = base_df['squad'].map(
        lambda v: f"{v} XV" if str(v) in {'1st', '2nd'} else str(v)
    )

    by_result = base_df[['player', 'season', 'season_sort', 'apps']].copy()
    by_result['color_mode'] = 'Result'
    by_result['color_value'] = base_df['result']

    by_position = base_df[['player', 'season', 'season_sort', 'apps']].copy()
    by_position['color_mode'] = 'Position'
    by_position['color_value'] = base_df['position']

    df = pd.concat([by_squad, by_result, by_position], ignore_index=True)

    chart_configs = {
        'Squad': {
            'sort': ['1st XV', '2nd XV', 'Unknown'],
            'colors': ['#202946', '#7d96e8', '#99151520'],
        },
        'Result': {
            'sort': ['Win', 'Loss', 'Draw'],
            'colors': ['#146f14', '#981515', 'goldenrod'],
            'allowed': ['Win', 'Loss', 'Draw'],
        },
        'Position': {
            'sort': [
                'Prop', 'Hooker', 'Second Row', 'Flanker', 'Number 8',
                'Scrum Half', 'Fly Half', 'Centre', 'Wing', 'Full Back',
                'Bench', 'Unknown'
            ],
            'colors': [
                '#1f2f5f', '#264073', '#2f4e87', '#3a5f9f', '#4a72ba',
                '#4b5563', '#5a6473', '#697486', '#7c8799', '#909caf',
                '#e5e7eb', '#99151520'
            ],
        },
    }

    def build_mode_chart(mode, sort_values, color_values, allowed_values=None):
        mode_df = df[df['color_mode'] == mode].copy()
        if allowed_values:
            mode_df = mode_df[mode_df['color_value'].isin(allowed_values)].copy()
        return (
            alt.Chart(mode_df)
            .mark_bar()
            .encode(
                x=alt.X('sum(apps):Q', title='Appearances'),
                y=alt.Y(
                    'season:N',
                    title='Season',
                    sort=alt.EncodingSortField(field='season_sort', order='descending', op='max')
                ),
                color=alt.Color(
                    'color_value:N',
                    sort=sort_values,
                    scale=alt.Scale(range=color_values),
                    legend=alt.Legend(orient='bottom', title=None)
                ),
                tooltip=[
                    alt.Tooltip('player:N', title='Player'),
                    alt.Tooltip('season:N', title='Season'),
                    alt.Tooltip('color_value:N', title='Group'),
                    alt.Tooltip('sum(apps):Q', title='Appearances')
                ]
            )
            .properties(
                title=alt.Title('Appearances Breakdown', subtitle=f'Games per season, coloured by {mode.lower()}'),
                width=400,
                height=alt.Step(30),
            )
        )

    output_path = Path(output_file)
    output_dir = output_path.parent
    output_stem = output_path.stem
    charts = {}
    for mode, config in chart_configs.items():
        chart = build_mode_chart(mode, config['sort'], config['colors'], config.get('allowed'))
        chart.save(output_dir / f'{output_stem}_{mode.lower()}.json')
        charts[mode] = chart

    return charts

seasons = ["2021/22", "2022/23", "2023/24", "2024/25", "2025/26"]
seasons_hist = ["2016/17", "2017/18", "2018/19", "2019/20"]

turnover_filter = alt.selection_point(fields=["Turnover"], bind="legend")
put_in_filter = alt.selection_point(fields=["Team"], bind="legend")
team_filter = alt.selection_point(fields=["Opposition"])

color_scale = alt.Scale(domain=["EG", "Opposition"], range=["#202946", "#981515"])
opacity_scale = alt.Scale(domain=["Turnover", "Retained"], range=[1, 0.5])

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
    selection = alt.selection_point(fields=['result'], empty='all')

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
                alt.Tooltip("lineouts_total:Q", title=f"Total {alt.datum.set_piece_type}", format=",.0f"),
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

    type_targets = [
        ("Lineout", "set_piece_success_lineout.json"),
        ("Scrum", "set_piece_success_scrum.json"),
    ]

    squad_param = alt.param(name="spSquadParam", value="1st")
    subtitle_text = "Seasonal success for EGRFC and opposition, with crossover-shaded advantage."

    charts = {}
    for set_piece_type, filename in type_targets:
        type_df = dense_long_df[dense_long_df["set_piece_type"].eq(set_piece_type)].copy()

        if type_df.empty:
            print(f"Skipping {filename}: no rows for {set_piece_type}.")
            continue

        chart = (
            _build_chart(type_df, width=200, height=300)
            .add_params(squad_param)
            .transform_filter("datum.squad == (spSquadParam + ' XV')")
            .properties(title=alt.Title(text=f"{set_piece_type} Success", subtitle=subtitle_text))
        )

        chart_path = output_root / filename
        chart.save(str(chart_path))
        charts[set_piece_type.lower()] = chart

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


def lineout_analysis_panel_chart(db, breakdown="numbers", panel="breakdown", output_file=None, bind_params=False):
    """Export one legacy lineout panel chart as a standalone Vega-Lite spec.

    These outputs back the Lineout Deep Dive page and follow the historical file
    contract: lineout_breakdown_<dimension>.json and lineout_trend_<dimension>.json.
    """
    breakdown_map = {
        "numbers": ("numbers", "Numbers", ["4", "5", "6", "7"]),
        "area": ("area", "Zone", ["Front", "Middle", "Back"]),
        "call_type": ("call_type", "Call Type", None),
        "dummy": ("dummy", "Dummy", ["Dummy", "Live"]),
        "jumper": ("jumper", "Jumper", None),
        "thrower": ("thrower", "Thrower", None),
    }
    width_map = {
        "numbers": 60,
        "area": 75,
        "dummy": 100,
        "jumper": 25,
        "thrower": 40,
    }

    if breakdown not in breakdown_map:
        raise ValueError(f"Unsupported breakdown '{breakdown}'.")
    if panel not in {"breakdown", "trend"}:
        raise ValueError("panel must be 'breakdown' or 'trend'")

    field, field_label, sort_order = breakdown_map[breakdown]
    if output_file is None:
        output_file = f"data/charts/lineout_{panel}_{breakdown}.json"

    df = db.con.execute(
        """
        SELECT
            L.game_id,
            G.date,
            G.squad,
            G.season,
            G.game_type,
            G.opposition,
            L.numbers,
            L.area,
            L.call_type,
            L.dummy,
            L.jumper,
            L.thrower,
            L.won
        FROM lineouts L
        JOIN games G USING (game_id)
        WHERE L.won IS NOT NULL
        """
    ).df()

    if df.empty:
        print(f"Skipping lineout_analysis_panel_chart ({breakdown}, {panel}): no rows available.")
        return None

    for column in ["squad", "season", "game_type", "opposition", "numbers", "area", "call_type", "jumper", "thrower"]:
        df[column] = df[column].fillna("Unknown").astype(str)
    df["dummy"] = df["dummy"].fillna(False).astype(bool).map({True: "Dummy", False: "Live"})
    df["won"] = df["won"].astype(int)

    def _opts(column_name):
        return ["All", *sorted(df[column_name].unique().tolist())]

    def _param(name, value, options=None, label=None):
        bind = alt.binding_select(options=options, name=label) if bind_params and options is not None else None
        if bind is not None:
            return alt.param(name=name, bind=bind, value=value)
        return alt.param(name=name, value=value)

    squad_param = _param("loSquad", "All", _opts("squad"), "Squad ")
    season_param = _param("loSeason", "All", _opts("season"), "Season ")
    game_type_param = _param("loGameType", "All", ["All", "League + Cup", "League only", *_opts("game_type")[1:]], "Game Type ")
    opposition_param = _param("loOpposition", "All", _opts("opposition"), "Opposition ")
    thrower_param = _param("loThrower", "All", _opts("thrower"), "Thrower ")
    jumper_param = _param("loJumper", "All", _opts("jumper"), "Jumper ")
    area_param = _param("loArea", "All", _opts("area"), "Area ")
    numbers_param = _param("loNumbers", "All", _opts("numbers"), "Numbers ")
    call_type_param = _param("loCallType", "All", _opts("call_type"), "Call Type ")

    params = [
        squad_param,
        season_param,
        game_type_param,
        opposition_param,
        thrower_param,
        jumper_param,
        area_param,
        numbers_param,
        call_type_param,
    ]

    shared_filter_expr = (
        f"({squad_param.name} == 'All' || datum.squad == {squad_param.name})"
        f" && ("
        f"{game_type_param.name} == 'All'"
        f" || ({game_type_param.name} == 'League + Cup' && (datum.game_type == 'League' || datum.game_type == 'Cup'))"
        f" || ({game_type_param.name} == 'League only' && datum.game_type == 'League')"
        f" || datum.game_type == {game_type_param.name}"
        f")"
        f" && ({opposition_param.name} == 'All' || datum.opposition == {opposition_param.name})"
        f" && ({thrower_param.name} == 'All' || datum.thrower == {thrower_param.name})"
        f" && ({jumper_param.name} == 'All' || datum.jumper == {jumper_param.name})"
        f" && ({area_param.name} == 'All' || datum.area == {area_param.name})"
        f" && ({numbers_param.name} == 'All' || datum.numbers == {numbers_param.name})"
        f" && ({call_type_param.name} == 'All' || datum.call_type == {call_type_param.name})"
    )
    season_filter_expr = f"({season_param.name} == 'All' || datum.season == {season_param.name})"

    if panel == "breakdown":
        grouped = (
            alt.Chart(df)
            .add_params(*params)
            .transform_filter(shared_filter_expr)
            .transform_filter(season_filter_expr)
            .transform_aggregate(attempts="count()", won="sum(won)", groupby=[field])
            .transform_calculate(success_rate="datum.won / datum.attempts")
        )

        x_encoding = alt.X(
            f"{field}:N",
            title=field_label,
            sort=sort_order if sort_order is not None else "-y",
            axis=alt.Axis(labelAngle=-30),
        )

        chart = alt.layer(
            grouped.mark_bar(color="#7d96e8", opacity=0.55).encode(
                x=x_encoding,
                y=alt.Y("attempts:Q", title="Count", axis=alt.Axis(format=",.0f", orient="left")),
                tooltip=[
                    alt.Tooltip(f"{field}:N", title=field_label),
                    alt.Tooltip("won:Q", title="Won", format=",.0f"),
                    alt.Tooltip("attempts:Q", title="Attempts", format=",.0f"),
                    alt.Tooltip("success_rate:Q", title="Success Rate", format=".1%"),
                ],
            ),
            grouped.mark_line(point=True, color="#202946", strokeWidth=2.5).encode(
                x=x_encoding,
                y=alt.Y("success_rate:Q", title="Success Rate", axis=alt.Axis(format="%", orient="right"), scale=alt.Scale(domain=[0, 1])),
                tooltip=[
                    alt.Tooltip(f"{field}:N", title=field_label),
                    alt.Tooltip("won:Q", title="Won", format=",.0f"),
                    alt.Tooltip("attempts:Q", title="Attempts", format=",.0f"),
                    alt.Tooltip("success_rate:Q", title="Success Rate", format=".1%"),
                ],
            ),
        ).resolve_scale(y="independent").properties(
            width=alt.Step(width_map.get(breakdown, 40)),
            height=250,
            title=alt.Title(text=f"{field_label} Breakdown", subtitle="Bars: attempts  ·  Line: success %"),
        )
    else:
        season_order = sorted(df["season"].unique().tolist())
        grouped = (
            alt.Chart(df)
            .add_params(*params)
            .transform_filter(shared_filter_expr)
            .transform_aggregate(attempts="count()", won="sum(won)", groupby=["season", field])
            .transform_joinaggregate(season_attempts="sum(attempts)", groupby=["season"])
            .transform_calculate(norm_count="datum.attempts / datum.season_attempts", success_rate="datum.won / datum.attempts")
        )

        chart = alt.layer(
            grouped.mark_bar(opacity=0.35).encode(
                x=alt.X("season:N", title="Season", sort=season_order),
                xOffset=alt.XOffset(f"{field}:N", sort=sort_order),
                y=alt.Y("norm_count:Q", title="Norm Count", axis=alt.Axis(format="%", orient="left"), scale=alt.Scale(domain=[0, 1])),
                color=alt.Color(f"{field}:N", title=field_label, sort=sort_order),
                tooltip=[
                    alt.Tooltip("season:N", title="Season"),
                    alt.Tooltip(f"{field}:N", title=field_label),
                    alt.Tooltip("won:Q", title="Won", format=",.0f"),
                    alt.Tooltip("attempts:Q", title="Attempts", format=",.0f"),
                    alt.Tooltip("norm_count:Q", title="Norm Count", format=".1%"),
                    alt.Tooltip("success_rate:Q", title="Success Rate", format=".1%"),
                ],
            ),
            grouped.mark_line(point=True, strokeWidth=2).encode(
                x=alt.X("season:N", title="Season", sort=season_order),
                y=alt.Y("success_rate:Q", title="Success Rate", axis=alt.Axis(format="%", orient="right"), scale=alt.Scale(domain=[0, 1])),
                color=alt.Color(f"{field}:N", title=field_label, sort=sort_order),
                detail=alt.Detail(f"{field}:N"),
                tooltip=[
                    alt.Tooltip("season:N", title="Season"),
                    alt.Tooltip(f"{field}:N", title=field_label),
                    alt.Tooltip("won:Q", title="Won", format=",.0f"),
                    alt.Tooltip("attempts:Q", title="Attempts", format=",.0f"),
                    alt.Tooltip("norm_count:Q", title="Norm Count", format=".1%"),
                    alt.Tooltip("success_rate:Q", title="Success Rate", format=".1%"),
                ],
            ),
        ).resolve_scale(y="independent").properties(
            width=430,
            height=260,
            title=alt.Title(text=f"{field_label} Trend", subtitle="Bars: season share  ·  Line: success %"),
        )

    chart.save(output_file)
    return chart


def lineout_analysis_panel_chart_suite(db, output_dir="data/charts"):
    """Generate the legacy per-dimension lineout breakdown/trend chart family."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    breakdowns = ["numbers", "area", "call_type", "dummy", "thrower", "jumper"]
    charts = {}
    for breakdown in breakdowns:
        for panel in ("breakdown", "trend"):
            output_file = output_root / f"lineout_{panel}_{breakdown}.json"
            chart = lineout_analysis_panel_chart(
                db,
                breakdown=breakdown,
                panel=panel,
                output_file=str(output_file),
                bind_params=False,
            )
            if chart is not None:
                charts[(breakdown, panel)] = chart

    return charts


def set_piece_h2h_chart_backend(db, set_piece="Lineout", output_file=None, bind_params=True):
    """Game-by-game set piece chart using canonical backend data.

    Exports a legacy-style head-to-head view with retained vs turnover events by
    attacking team, plus per-team success rate points for each match.
    """
    if output_file is None:
        output_file = f"data/charts/{set_piece.lower()}_h2h.json"

    if str(set_piece).strip().lower() not in {"lineout", "scrum"}:
        raise ValueError("set_piece must be 'Lineout' or 'Scrum'")

    metric_won = "lineouts_won" if set_piece.lower() == "lineout" else "scrums_won"
    metric_total = "lineouts_total" if set_piece.lower() == "lineout" else "scrums_total"

    df = db.con.execute(
        f"""
        SELECT
            G.game_id,
            G.date,
            G.squad,
            G.season,
            G.game_type,
            G.opposition,
            G.home_away,
            CASE WHEN S.team = 'EGRFC' THEN 'EGRFC' ELSE 'Opposition' END AS team,
            S.{metric_won}::DOUBLE AS won,
            (S.{metric_total} - S.{metric_won})::DOUBLE AS lost,
            S.{metric_total}::DOUBLE AS total,
            S.{metric_won}::DOUBLE / NULLIF(S.{metric_total}, 0) AS success_rate,
            CONCAT_WS(' ', G.opposition, CONCAT('(', G.home_away, ')')) AS game_label
        FROM set_piece S
        JOIN games G USING (game_id)
        WHERE S.{metric_total} > 0
        ORDER BY G.date DESC
        """
    ).df()

    if df.empty:
        print(f"Skipping set_piece_h2h_chart_backend ({set_piece}): no rows available.")
        return None

    df["season"] = df["season"].astype(str)
    df["squad"] = df["squad"].astype(str)
    df["game_type"] = df["game_type"].fillna("Unknown").astype(str)
    df["opposition"] = df["opposition"].fillna("Unknown").astype(str)

    squad_options = ["All", *sorted(df["squad"].unique().tolist())]
    season_options = ["All", *sorted(df["season"].unique().tolist(), reverse=True)]
    game_type_options = ["All", "League + Cup", "League only"]
    opposition_options = ["All", *sorted(df["opposition"].unique().tolist())]

    def _param(name, value, options=None, label=None):
        bind = alt.binding_select(options=options, name=label) if bind_params and options is not None else None
        if bind is not None:
            return alt.param(name=name, bind=bind, value=value)
        return alt.param(name=name, value=value)

    squad_param = _param("h2hSquadFilter", "All", squad_options, "Squad ")
    season_param = _param("h2hSeasonFilter", "All", season_options, "Season ")
    game_type_param = _param("h2hGameTypeFilter", "All", game_type_options, "Game Type ")
    opposition_param = _param("h2hOppositionFilter", "All", opposition_options, "Opposition ")
    team_highlight_param = _param("h2hTeamHighlight", "All", ["All", "EGRFC", "Opposition"], "Team ")
    outcome_highlight_param = _param("h2hOutcomeHighlight", "Turnover", ["All", "Retained", "Turnover"], "Outcome ")

    filter_expr = (
        f"({squad_param.name} == 'All' || datum.squad == {squad_param.name})"
        f" && ({season_param.name} == 'All' || datum.season == {season_param.name})"
        f" && ("
        f"{game_type_param.name} == 'All'"
        f" || ({game_type_param.name} == 'League + Cup' && (datum.game_type == 'League' || datum.game_type == 'Cup'))"
        f" || ({game_type_param.name} == 'League only' && datum.game_type == 'League')"
        f" || datum.game_type == {game_type_param.name}"
        f")"
        f" && ({opposition_param.name} == 'All' || datum.opposition == {opposition_param.name})"
    )

    event_rows = []
    success_rows = []
    for row in df.itertuples(index=False):
        attacking_team = row.team
        other_team = "Opposition" if attacking_team == "EGRFC" else "EGRFC"
        won = max(0.0, float(row.won or 0))
        raw_total = max(0.0, float(row.total or 0))
        # Guard against inconsistent source rows where won > total.
        total = max(raw_total, won)
        lost = max(0.0, total - won)
        success_rate = (won / total) if total > 0 else 0.0

        success_rows.append(
            {
                "game_id": row.game_id,
                "game_axis_key": f"{row.game_id}__{row.squad} XV v {row.opposition} ({row.home_away})",
                "date": row.date,
                "squad": row.squad,
                "season": row.season,
                "game_type": row.game_type,
                "opposition": row.opposition,
                "game_label": row.game_label,
                "attacking_team": attacking_team,
                "won": won,
                "lost": lost,
                "total": total,
                "success_rate": success_rate,
            }
        )

        for outcome, winner, count in (
            ("Retained", attacking_team, won),
            ("Turnover", other_team, lost),
        ):
            event_rows.append(
                {
                    "game_id": row.game_id,
                    "game_axis_key": f"{row.game_id}__{row.squad} XV v {row.opposition} ({row.home_away})",
                    "date": row.date,
                    "squad": row.squad,
                    "season": row.season,
                    "game_type": row.game_type,
                    "opposition": row.opposition,
                    "game_label": row.game_label,
                    "attacking_team": attacking_team,
                    "winner_team": winner,
                    "outcome": outcome,
                    "count": count,
                    "signed_count": count if winner == "EGRFC" else -count,
                }
            )

    event_df = pd.DataFrame(event_rows)
    success_df = pd.DataFrame(success_rows)
    connector_df = (
        success_df.pivot_table(
            index=["game_id", "game_axis_key", "game_label", "date", "squad", "season", "game_type", "opposition"],
            columns="attacking_team",
            values="success_rate",
            aggfunc="mean",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    connector_df["eg_rate"] = connector_df.get("EGRFC", pd.Series(index=connector_df.index, dtype=float)).fillna(0.0)
    connector_df["opp_rate"] = connector_df.get("Opposition", pd.Series(index=connector_df.index, dtype=float)).fillna(0.0)
    connector_df["min_rate"] = connector_df[["eg_rate", "opp_rate"]].min(axis=1)
    connector_df["max_rate"] = connector_df[["eg_rate", "opp_rate"]].max(axis=1)
    connector_df["success_diff"] = connector_df["eg_rate"] - connector_df["opp_rate"]
    connector_df["winner"] = connector_df["success_diff"].apply(
        lambda diff: "EGRFC" if diff > 0 else ("Opposition" if diff < 0 else "Level")
    )
    success_df = success_df.merge(connector_df[["game_id", "winner"]], on="game_id", how="left")

    y_sort = alt.EncodingSortField(field="date", order="ascending")
    max_abs_count = float(event_df["signed_count"].abs().max() if not event_df.empty else 1.0)
    flow_domain = [-max_abs_count, max_abs_count]
    event_focus_filter = (
        f"({team_highlight_param.name} == 'All' || datum.attacking_team == {team_highlight_param.name})"
        f" && ({outcome_highlight_param.name} == 'All' || datum.outcome == {outcome_highlight_param.name})"
    )
    success_team_filter = f"({team_highlight_param.name} == 'All' || datum.attacking_team == {team_highlight_param.name})"

    event_base = (
        alt.Chart(event_df)
        .add_params(
            squad_param,
            season_param,
            game_type_param,
            opposition_param,
            team_highlight_param,
            outcome_highlight_param,
        )
        .transform_filter(filter_expr)
        .transform_filter(event_focus_filter)
        .transform_calculate(
            has_single_focus=(
                f"({team_highlight_param.name} != 'All' || {outcome_highlight_param.name} != 'All')"
            )
        )
        .transform_calculate(y_offset_group="datum.has_single_focus ? 'Single' : datum.attacking_team")
    )

    flow_chart = event_base.mark_bar().encode(
        y=alt.Y(
            "game_axis_key:N",
            sort=y_sort,
            title=None,
            axis=alt.Axis(labelLimit=220, ticks=False, domain=False, labelExpr="split(datum.label, '__')[1]"),
        ),
        x=alt.X(
            "signed_count:Q",
            title=f"{set_piece}s Won",
            axis=alt.Axis(format="d", labelExpr="abs(datum.value)", orient="top", labelPadding=15),
            scale=alt.Scale(domain=flow_domain),
        ),
        yOffset=alt.YOffset("y_offset_group:N", sort=["Opposition", "EGRFC", "Single"], bandPosition=0.5),
        size=alt.condition(
            f"{team_highlight_param.name} == 'All' && {outcome_highlight_param.name} == 'All'",
            alt.value(8),
            alt.value(12),
        ),
        color=alt.Color(
            "attacking_team:N",
            title="Attacking Team",
            scale=alt.Scale(domain=["EGRFC", "Opposition"], range=["#202946", "#981515"]),
        ),
        opacity=alt.Opacity("outcome:N", scale=alt.Scale(domain=["Retained", "Turnover"], range=[0.5, 1.0]), legend=None),
        tooltip=[
            alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
            alt.Tooltip("squad:N", title="Squad"),
            alt.Tooltip("season:N", title="Season"),
            alt.Tooltip("game_type:N", title="Game Type"),
            alt.Tooltip("opposition:N", title="Opposition"),
            alt.Tooltip("game_label:N", title="Fixture"),
            alt.Tooltip("attacking_team:N", title="Attacking Team"),
            alt.Tooltip("outcome:N", title="Outcome"),
            alt.Tooltip("winner_team:N", title="Won By"),
            alt.Tooltip("count:Q", title="Count", format=",.0f"),
        ],
    ).properties(width=300, height=alt.Step(15))

    zero_line = alt.Chart(pd.DataFrame({"zero": [0]})).mark_rule(stroke="#222", strokeWidth=2, opacity=1).encode(x="zero:Q")

    success_base = (
        alt.Chart(success_df)
        .add_params(
            squad_param,
            season_param,
            game_type_param,
            opposition_param,
            team_highlight_param,
            outcome_highlight_param,
        )
        .transform_filter(filter_expr)
        .transform_filter(success_team_filter)
    )

    success_connectors = (
        alt.Chart(connector_df)
        .add_params(
            squad_param,
            season_param,
            game_type_param,
            opposition_param,
            team_highlight_param,
            outcome_highlight_param,
        )
        .transform_filter(filter_expr)
        .mark_rule(strokeWidth=3)
        .encode(
            y=alt.Y("game_axis_key:N", sort=y_sort, title=None, axis=alt.Axis(labelLimit=220, ticks=False, domain=False, orient="right", labelPadding=10,labelExpr="timeFormat(toDate(split(datum.label,'_')[0]), '%d %b %Y')")),
            x=alt.X("eg_rate:Q", title="Success Rate", axis=alt.Axis(format="%", orient="top"), scale=alt.Scale(domain=[0, 1])),
            x2="opp_rate:Q",
            color=alt.Color(
                "winner:N",
                title="Higher Success",
                legend=None,
                scale=alt.Scale(domain=["EGRFC", "Opposition", "Level"], range=["#202946", "#981515", "#666666"]),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
                alt.Tooltip("game_label:N", title="Fixture"),
                alt.Tooltip("eg_rate:Q", title="EGRFC Success", format=".1%"),
                alt.Tooltip("opp_rate:Q", title="Opposition Success", format=".1%"),
                alt.Tooltip("success_diff:Q", title="Difference (EGRFC - Opp)", format=".1%"),
            ],
        )
        .properties(width=200, height=alt.Step(15))
    )

    success_point_encoding = {
        "y": alt.Y("game_axis_key:N", sort=y_sort, title=None, axis=alt.Axis(orient="right")),
        "x": alt.X("success_rate:Q", title="Success Rate", axis=alt.Axis(format="%", orient="top"), scale=alt.Scale(domain=[0, 1])),
        "color": alt.Color(
            "attacking_team:N",
            title="Team",
            scale=alt.Scale(domain=["EGRFC", "Opposition"], range=["#202946", "#981515"]),
        ),
        "tooltip": [
            alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
            alt.Tooltip("game_label:N", title="Game"),
            alt.Tooltip("attacking_team:N", title="Attacking Team"),
            alt.Tooltip("winner:N", title="Higher Success"),
            alt.Tooltip("won:Q", title=f"{set_piece}s Won", format=",.0f"),
            alt.Tooltip("lost:Q", title=f"{set_piece}s Lost", format=",.0f"),
            alt.Tooltip("total:Q", title=f"{set_piece}s Total", format=",.0f"),
            alt.Tooltip("success_rate:Q", title="Success Rate", format=".1%"),
        ],
        "strokeWidth": alt.value(1.6),
    }

    success_losing_points = success_base.transform_filter(
        "datum.winner == 'Level' || datum.attacking_team != datum.winner"
    ).mark_point(size=160, filled=False, opacity=0.9).encode(
        **success_point_encoding
    ).properties(width=200, height=alt.Step(15))

    success_winning_points = success_base.transform_filter(
        "datum.attacking_team == datum.winner"
    ).mark_point(size=190, filled=True, opacity=1.0).encode(
        **success_point_encoding
    ).properties(width=200, height=alt.Step(15))

    main_chart = alt.hconcat((zero_line + flow_chart), success_connectors + success_losing_points + success_winning_points, spacing=10).resolve_scale(y="shared").properties(
        title=alt.Title(
            text=f"{set_piece}s Head-to-Head",
            subtitle=f"{set_piece}s retained or turned over, and success-rate difference by game. Use filters to slice squad, season, game type, and matchup focus.",
        )
    )

    opposition_selected_expr = f"{opposition_param.name} != 'All'"

    aggregate_event_base = (
        alt.Chart(event_df)
        .add_params(
            squad_param,
            season_param,
            game_type_param,
            opposition_param,
            team_highlight_param,
            outcome_highlight_param,
        )
        .transform_filter(filter_expr)
        .transform_filter(opposition_selected_expr)
        .transform_filter(event_focus_filter)
        .transform_aggregate(
            count="sum(count)",
            signed_count="sum(signed_count)",
            groupby=["attacking_team", "winner_team", "outcome"],
        )
        .transform_calculate(
            game_axis_key="'aggregate__TOTAL'",
            game_label="'TOTAL'",
        )
        .transform_calculate(
            has_single_focus=(
                f"({team_highlight_param.name} != 'All' || {outcome_highlight_param.name} != 'All')"
            )
        )
        .transform_calculate(y_offset_group="datum.has_single_focus ? 'Single' : datum.attacking_team")
    )

    aggregate_max_abs = float(
        event_df["signed_count"].abs().max() if not event_df.empty else 1.0
    )
    aggregate_flow_domain = [-aggregate_max_abs, aggregate_max_abs]

    aggregate_flow_chart = aggregate_event_base.mark_bar().encode(
        y=alt.Y(
            "game_axis_key:N",
            title=None,
            axis=alt.Axis(
                labelLimit=220,
                ticks=False,
                domain=False,
                labelExpr="split(datum.label, '__')[1]",
                labelFontWeight="bold",
            ),
        ),
        x=alt.X(
            "signed_count:Q",
            title=None,
            axis=alt.Axis(format="d", labelExpr="abs(datum.value)", orient="bottom", labelPadding=10),
            scale=alt.Scale(domain=aggregate_flow_domain),
        ),
        yOffset=alt.YOffset("y_offset_group:N", sort=["Opposition", "EGRFC", "Single"], bandPosition=0.5),
        size=alt.condition(
            f"{team_highlight_param.name} == 'All' && {outcome_highlight_param.name} == 'All'",
            alt.value(8),
            alt.value(12),
        ),
        color=alt.Color(
            "attacking_team:N",
            title="Attacking Team",
            scale=alt.Scale(domain=["EGRFC", "Opposition"], range=["#202946", "#981515"]),
        ),
        opacity=alt.Opacity("outcome:N", scale=alt.Scale(domain=["Retained", "Turnover"], range=[0.5, 1.0]), legend=None),
        tooltip=[
            alt.Tooltip("attacking_team:N", title="Attacking Team"),
            alt.Tooltip("outcome:N", title="Outcome"),
            alt.Tooltip("winner_team:N", title="Won By"),
            alt.Tooltip("count:Q", title="Count", format=",.0f"),
        ],
    ).properties(width=300, height=alt.Step(10))

    aggregate_success_base = (
        alt.Chart(success_df)
        .add_params(
            squad_param,
            season_param,
            game_type_param,
            opposition_param,
            team_highlight_param,
            outcome_highlight_param,
        )
        .transform_filter(filter_expr)
        .transform_filter(opposition_selected_expr)
        .transform_filter(success_team_filter)
        .transform_aggregate(
            won="sum(won)",
            lost="sum(lost)",
            total="sum(total)",
            groupby=["attacking_team"],
        )
        .transform_calculate(
            success_rate="datum.total > 0 ? datum.won / datum.total : 0",
            game_axis_key="'aggregate__TOTAL'",
        )
        .transform_calculate(
            winner=(
                "datum.success_rate == 0 ? 'Level' : null"
            )
        )
    )

    aggregate_connector = (
        alt.Chart(success_df)
        .add_params(
            squad_param,
            season_param,
            game_type_param,
            opposition_param,
            team_highlight_param,
            outcome_highlight_param,
        )
        .transform_filter(filter_expr)
        .transform_filter(opposition_selected_expr)
        .transform_calculate(
            eg_won="datum.attacking_team == 'EGRFC' ? datum.won : 0",
            eg_total="datum.attacking_team == 'EGRFC' ? datum.total : 0",
            opp_won="datum.attacking_team == 'Opposition' ? datum.won : 0",
            opp_total="datum.attacking_team == 'Opposition' ? datum.total : 0",
        )
        .transform_aggregate(
            eg_won="sum(eg_won)",
            eg_total="sum(eg_total)",
            opp_won="sum(opp_won)",
            opp_total="sum(opp_total)",
        )
        .transform_calculate(
            eg_rate="datum.eg_total > 0 ? datum.eg_won / datum.eg_total : 0",
            opp_rate="datum.opp_total > 0 ? datum.opp_won / datum.opp_total : 0",
            success_diff="datum.eg_rate - datum.opp_rate",
            winner="datum.success_diff > 0 ? 'EGRFC' : (datum.success_diff < 0 ? 'Opposition' : 'Level')",
            game_axis_key="'aggregate__TOTAL'",
            game_label="'TOTAL'",
        )
        .mark_rule(strokeWidth=3)
        .encode(
            y=alt.Y(
                "game_axis_key:N",
                title=None,
                axis=alt.Axis(
                    labelLimit=220,
                    ticks=False,
                    domain=False,
                    orient="right",
                    labelPadding=10,
                    labelExpr="split(datum.label, '__')[1]",
                    labelFontWeight="bold",
                ),
            ),
            x=alt.X(
                "eg_rate:Q",
                title=None,
                axis=alt.Axis(format="%", orient="bottom", labelPadding=10),
                scale=alt.Scale(domain=[0, 1]),
            ),
            x2="opp_rate:Q",
            color=alt.Color(
                "winner:N",
                title="Higher Success",
                legend=None,
                scale=alt.Scale(domain=["EGRFC", "Opposition", "Level"], range=["#202946", "#981515", "#666666"]),
            ),
            tooltip=[
                alt.Tooltip("game_label:N", title="Fixture"),
                alt.Tooltip("eg_rate:Q", title="EGRFC Success", format=".1%"),
                alt.Tooltip("opp_rate:Q", title="Opposition Success", format=".1%"),
                alt.Tooltip("success_diff:Q", title="Difference (EGRFC - Opp)", format=".1%"),
            ],
        )
        .properties(width=200, height=alt.Step(10))
    )

    aggregate_success_points = aggregate_success_base.mark_point(size=190, filled=True, opacity=1.0).encode(
        y=alt.Y("game_axis_key:N", title=None, axis=alt.Axis(orient="right", labelFontWeight="bold")),
        x=alt.X(
            "success_rate:Q",
            title=None,
            scale=alt.Scale(domain=[0, 1]),
        ),
        color=alt.Color(
            "attacking_team:N",
            title="Team",
            scale=alt.Scale(domain=["EGRFC", "Opposition"], range=["#202946", "#981515"]),
        ),
        tooltip=[
            alt.Tooltip("attacking_team:N", title="Attacking Team"),
            alt.Tooltip("won:Q", title=f"{set_piece}s Won", format=",.0f"),
            alt.Tooltip("lost:Q", title=f"{set_piece}s Lost", format=",.0f"),
            alt.Tooltip("total:Q", title=f"{set_piece}s Total", format=",.0f"),
            alt.Tooltip("success_rate:Q", title="Success Rate", format=".1%"),
        ],
        strokeWidth=alt.value(1.6),
    ).properties(width=200, height=alt.Step(10))

    aggregate_chart = alt.hconcat(
        zero_line + aggregate_flow_chart,
        aggregate_connector + aggregate_success_points,
        spacing=10,
    ).resolve_scale(y="shared")

    chart = alt.vconcat(main_chart, aggregate_chart, spacing=18)

    chart.save(output_file)
    return chart


def red_zone_performance_chart(db, metric="points", output_file=None, bind_params=False):
    """Generate red-zone performance scatter chart from canonical backend data.

    metric:
    - "points" -> y axis is points_per_entry
    - "tries" -> y axis is tries_per_entry
    """
    metric_key = str(metric).strip().lower()
    if metric_key not in {"points", "tries"}:
        raise ValueError("metric must be 'points' or 'tries'")

    if output_file is None:
        output_file = "data/charts/red_zone_points.json" if metric_key == "points" else "data/charts/red_zone_tries.json"

    df = db.con.execute(
        """
        SELECT
            r.game_id,
            r.date,
            r.season,
            r.squad,
            COALESCE(g.game_type, 'Unknown') AS game_type,
            r.opposition,
            COALESCE(g.home_away, '?') AS home_away,
            r.opposition || ' (' || COALESCE(g.home_away, '?') || ')' AS label,
            CASE WHEN r.team = 'EGRFC' THEN 'EGRFC' ELSE 'Opposition' END AS team,
            r.entries_22m::DOUBLE AS entries_22m,
            r.points::DOUBLE AS points,
            r.tries::DOUBLE AS tries,
            r.points_per_entry::DOUBLE AS points_per_entry,
            r.tries_per_entry::DOUBLE AS tries_per_entry
        FROM v_red_zone r
        LEFT JOIN games g USING (game_id)
        WHERE r.entries_22m IS NOT NULL
        ORDER BY r.date DESC, r.squad, r.team
        """
    ).df()

    if df.empty:
        print(f"Skipping red_zone_performance_chart ({metric_key}): no rows available.")
        return None

    df = df.dropna(subset=["entries_22m", "points_per_entry", "tries_per_entry"]).copy()
    if df.empty:
        print(f"Skipping red_zone_performance_chart ({metric_key}): no valid rows after null filtering.")
        return None

    df["season"] = df["season"].fillna("Unknown").astype(str)
    df["squad"] = df["squad"].fillna("Unknown").astype(str)
    df["game_type"] = df["game_type"].fillna("Unknown").astype(str)
    df["opposition"] = df["opposition"].fillna("Unknown").astype(str)

    y_field = "points_per_entry" if metric_key == "points" else "tries_per_entry"
    y_title = "Points per Entry" if metric_key == "points" else "Tries per Entry"

    x_max = float(df["entries_22m"].max()) if not df.empty else 0.0
    y_max = float(df[y_field].max()) if not df.empty else 0.0
    x_domain_max = max(20.0, float(int((x_max * 1.18) + 0.9999)))
    if metric_key == "points":
        y_domain_max = 7.0
    else:
        y_domain_max = max(1.0, float(int((y_max * 1.22) + 0.9999)))

    seasons = sorted(df["season"].unique().tolist(), reverse=True)

    def _param(name, value, options=None, label=None):
        bind = alt.binding_select(options=options, name=label) if bind_params and options is not None else None
        if bind is not None:
            return alt.param(name=name, bind=bind, value=value)
        return alt.param(name=name, value=value)

    squad_param = _param("rzSquad", "1st", ["All", "1st", "2nd"], "Squad ")
    season_param = _param("rzSeason", "All", ["All", *seasons], "Season ")
    game_type_param = _param("rzGameType", "All", ["All", "League + Cup", "League only"], "Game Type ")
    highlight = alt.selection_point(fields=["team"], bind="legend")

    filter_expr = (
        f"({squad_param.name} == 'All' || datum.squad == {squad_param.name})"
        f" && ({season_param.name} == 'All' || datum.season == {season_param.name})"
        f" && ("
        f"{game_type_param.name} == 'All'"
        f" || ({game_type_param.name} == 'League + Cup' && (datum.game_type == 'League' || datum.game_type == 'Cup'))"
        f" || ({game_type_param.name} == 'League only' && datum.game_type == 'League')"
        f" || datum.game_type == {game_type_param.name}"
        f")"
    )

    df_wide = (
        df.pivot_table(index=["game_id", "date", "season", "squad", "game_type", "opposition", "label"], columns="team", values=["entries_22m", y_field, "points", "tries"], aggfunc="first")
        .reset_index()
    )
    if not df_wide.empty:
        df_wide.columns = [
            "_".join([str(part) for part in col if str(part) != ""]).strip("_") if isinstance(col, tuple) else str(col)
            for col in df_wide.columns
        ]
        rename_map = {
            f"entries_22m_EGRFC": "entries_22m_egrfc",
            f"entries_22m_Opposition": "entries_22m_opp",
            f"{y_field}_EGRFC": "metric_egrfc",
            f"{y_field}_Opposition": "metric_opp",
            "points_EGRFC": "points_egrfc",
            "points_Opposition": "points_opp",
            "tries_EGRFC": "tries_egrfc",
            "tries_Opposition": "tries_opp",
        }
        df_wide = df_wide.rename(columns=rename_map)
        for col in ["entries_22m_egrfc", "entries_22m_opp", "metric_egrfc", "metric_opp"]:
            if col not in df_wide.columns:
                df_wide[col] = None
        df_wide = df_wide.dropna(subset=["entries_22m_egrfc", "entries_22m_opp", "metric_egrfc", "metric_opp"])
    else:
        df_wide = pd.DataFrame(columns=["game_id", "entries_22m_egrfc", "entries_22m_opp", "metric_egrfc", "metric_opp"])

    quadrant_df = pd.DataFrame(
        {
            "x": [x_domain_max * 0.86, x_domain_max * 0.86, x_domain_max * 0.14, x_domain_max * 0.14, x_domain_max * 0.86, x_domain_max * 0.86, x_domain_max * 0.14, x_domain_max * 0.14],
            "y": [y_domain_max * 0.94, y_domain_max * 0.10, y_domain_max * 0.94, y_domain_max * 0.10, y_domain_max * 0.90, y_domain_max * 0.06, y_domain_max * 0.90, y_domain_max * 0.06],
            "label": [
                "High Efficiency",
                "Low Efficiency",
                "High Efficiency",
                "Low Efficiency",
                "High Territory",
                "High Territory",
                "Low Territory",
                "Low Territory",
            ],
            "opacity": [1, 0.5, 1, 0.5, 1, 1, 0.5, 0.5],
        }
    )

    reference_layers = []
    if metric_key == "points":
        def ref_line_coords(point_total=20):
            coords = []
            for x in range(1, 200):
                entries = x * 0.1
                points_per_entry = point_total / entries
                if (points_per_entry <= 6) and (entries <= x_domain_max or points_per_entry >= 1):
                    coords.append({"x": entries, "y": points_per_entry})
            return coords

        ref_line_10 = alt.Chart(pd.DataFrame(ref_line_coords(10))).mark_line(color="black", opacity=0.1, clip=True).encode(x="x:Q", y="y:Q")
        ref_line_20 = alt.Chart(pd.DataFrame(ref_line_coords(20))).mark_line(color="black", opacity=0.1, clip=True).encode(x="x:Q", y="y:Q")
        ref_line_50 = alt.Chart(pd.DataFrame(ref_line_coords(50))).mark_line(color="black", opacity=0.1, clip=True).encode(x="x:Q", y="y:Q")
        ref_line_labels = alt.Chart(
            pd.DataFrame(
                {
                    "y": [6, 5.3, 5],
                    "x": [50 / 6, 20 / 5.3, 10 / 5],
                    "label": ["50 pts", "20 pts", "10 pts"],
                }
            )
        ).mark_text(size=10, color="black", opacity=0.5, fontStyle="italic").encode(x="x:Q", y="y:Q", text="label:N")
        reference_layers = [ref_line_10, ref_line_20, ref_line_50, ref_line_labels]

    points = (
        alt.Chart(df)
        .transform_filter(filter_expr)
        .mark_point(filled=True, size=70)
        .encode(
            x=alt.X("entries_22m:Q", scale=alt.Scale(zero=True, domain=[0, x_domain_max]), axis=alt.Axis(title="22m Entries", tickCount=4, grid=False)),
            y=alt.Y(f"{y_field}:Q", scale=alt.Scale(zero=True, domain=[0, y_domain_max]), axis=alt.Axis(title=y_title, tickCount=7, grid=False)),
            color=alt.Color("team:N", scale=alt.Scale(domain=["EGRFC", "Opposition"], range=["#202946", "#991515"]), legend=alt.Legend(title=None, orient="top")),
            tooltip=[
                alt.Tooltip("label:N", title="Game"),
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("points:Q", title="Points"),
                alt.Tooltip("tries:Q", title="Tries"),
                alt.Tooltip("entries_22m:Q", title="22m Entries"),
                alt.Tooltip("points_per_entry:Q", title="Points per Entry", format=".1f"),
                alt.Tooltip("tries_per_entry:Q", title="Tries per Entry", format=".1f"),
            ],
            opacity=alt.condition(highlight, alt.value(1), alt.value(0.1), legend=None),
        )
    )

    averages = (
        alt.Chart(df)
        .transform_filter(filter_expr)
        .transform_aggregate(
            entries_22m="mean(entries_22m)",
            points="mean(points)",
            tries="mean(tries)",
            points_per_entry="mean(points_per_entry)",
            tries_per_entry="mean(tries_per_entry)",
            groupby=["team"],
        )
        .mark_point(filled=True, opacity=1, shape="diamond", stroke="black")
        .encode(
            x=alt.X("entries_22m:Q"),
            y=alt.Y(f"{y_field}:Q"),
            color=alt.Color("team:N", scale=alt.Scale(domain=["EGRFC", "Opposition"], range=["#202946", "#991515"])),
            tooltip=[
                alt.Tooltip("points:Q", title="Average Points", format=".1f"),
                alt.Tooltip("tries:Q", title="Average Tries", format=".1f"),
                alt.Tooltip("entries_22m:Q", title="Average 22m Entries", format=".1f"),
                alt.Tooltip("points_per_entry:Q", title="Average Points per Entry", format=".1f"),
                alt.Tooltip("tries_per_entry:Q", title="Average Tries per Entry", format=".1f"),
            ],
            size=alt.value(200),
            opacity=alt.condition(highlight, alt.value(1), alt.value(0.1)),
        )
    )

    color_test = "datum.points_egrfc > datum.points_opp" if metric_key == "points" else "datum.tries_egrfc > datum.tries_opp"
    lines = (
        alt.Chart(df_wide)
        .transform_filter(filter_expr)
        .mark_rule(strokeWidth=1.2)
        .encode(
            x=alt.X("entries_22m_egrfc:Q"),
            y=alt.Y("metric_egrfc:Q"),
            x2=alt.X2("entries_22m_opp:Q"),
            y2=alt.Y2("metric_opp:Q"),
            color=alt.condition(color_test, alt.value("#202946"), alt.value("#991515")),
            detail="game_id:N",
            opacity=alt.condition(highlight, alt.value(0.8), alt.value(0.1)),
        )
    )

    quadrant_labels = alt.Chart(quadrant_df).mark_text(size=12, color="black", fontStyle="italic").encode(
        x=alt.X("x:Q"),
        y=alt.Y("y:Q"),
        opacity=alt.Opacity("opacity:Q", legend=None),
        text=alt.Text("label:N"),
    )

    subtitle_metric = "points per entry" if metric_key == "points" else "tries per entry"
    layer_parts = [*reference_layers, quadrant_labels, points, averages, lines]
    chart = alt.layer(*layer_parts).add_params(squad_param, season_param, game_type_param, highlight).properties(
        title=alt.TitleParams(
            text="Red Zone Success",
            subtitle=[
                f"Attacking territory (22m entries) vs Scoring efficiency ({subtitle_metric})",
                "Each point represents a game. Lines connect EGRFC to their opposition in the same game.",
                "Diamond points show the average for EGRFC and their opposition across all games.",
            ],
        ),
        width=450,
        height=400,
    ).resolve_scale(color="shared", x="shared", y="shared")

    chart.save(output_file)
    return chart


def lineout_analysis_chart(db, breakdown="numbers", output_file=None, bind_params=True):
    """Lineout analysis explorer for one breakdown field with combined filters.

    Includes:
    - selected-slice bars (normalised attempts) + line (success rate)
    - season trend for normalised attempts and success rate
    """
    breakdown_map = {
        "numbers": ("numbers", "Numbers"),
        "area": ("area", "Area"),
        "zone": ("area", "Area"),
        "call": ("call", "Call"),
        "call_type": ("call_type", "Call Type"),
        "dummy": ("dummy", "Dummy"),
        "jumper": ("jumper", "Jumper"),
        "thrower": ("thrower", "Thrower"),
    }

    # Define a c
    color_scale = alt.Scale(
        domain=["Home Win", "Home Win (LBP)", "Away Win", "Away Win (LBP)", "Draw", "To be played", "N/A"],
        range=["#146f14", "#146f14a0", "#991515", "#991515a0", "goldenrod", "white", "#202946"],
    )

    if breakdown not in breakdown_map:
        raise ValueError(f"Unsupported breakdown '{breakdown}'. Expected one of: {', '.join(breakdown_map)}")

    field, field_label = breakdown_map[breakdown]
    if output_file is None:
        output_file = f"data/charts/lineout_analysis_{breakdown}.json"

    df = db.con.execute(
        """
        SELECT
            L.game_id,
            G.date,
            G.squad,
            G.season,
            G.game_type,
            G.opposition,
            L.numbers,
            L.area,
            L.call,
            L.call_type,
            L.dummy,
            L.jumper,
            L.thrower,
            L.won
        FROM lineouts L
        JOIN games G USING (game_id)
        WHERE won IS NOT NULL
        """
    ).df()

    if df.empty:
        print(f"Skipping lineout_analysis_chart ({breakdown}): no lineout rows available.")
        return None

    for col in ["squad", "season", "game_type", "opposition", "numbers", "area", "call", "call_type", "jumper", "thrower"]:
        df[col] = df[col].fillna("Unknown").astype(str)
    df["dummy"] = df["dummy"].fillna(False).astype(bool).map({True: "Dummy", False: "Live"})
    df["won"] = df["won"].astype(int)

    def _opts(column_name):
        return ["All", *sorted(df[column_name].unique().tolist())]

    # Primary slice filters
    def _param(name, value, options=None, label=None):
        bind = alt.binding_select(options=options, name=label) if bind_params and options is not None else None
        if bind is not None:
            return alt.param(name=name, bind=bind, value=value)
        return alt.param(name=name, value=value)

    squad_param = _param("loSquad", "All", _opts("squad"), "Squad ")
    season_param = _param("loSeason", "All", _opts("season"), "Season ")
    game_type_param = _param("loGameType", "All", ["All", "League + Cup", "League only", *_opts("game_type")[1:]], "Game Type ")
    opposition_param = _param("loOpposition", "All", _opts("opposition"), "Opposition ")

    # Combination filters for detailed slicing
    thrower_param = _param("loThrower", "All", _opts("thrower"), "Thrower ")
    jumper_param = _param("loJumper", "All", _opts("jumper"), "Jumper ")
    area_param = _param("loArea", "All", _opts("area"), "Area ")
    numbers_param = _param("loNumbers", "All", _opts("numbers"), "Numbers ")
    call_param = _param("loCall", "All", _opts("call"), "Call ")
    call_type_param = _param("loCallType", "All", _opts("call_type"), "Call Type ")

    shared_filter_expr = (
        f"({squad_param.name} == 'All' || datum.squad == {squad_param.name})"
        f" && ("
        f"{game_type_param.name} == 'All'"
        f" || ({game_type_param.name} == 'League + Cup' && (datum.game_type == 'League' || datum.game_type == 'Cup'))"
        f" || ({game_type_param.name} == 'League only' && datum.game_type == 'League')"
        f" || datum.game_type == {game_type_param.name}"
        f")"
        f" && ({opposition_param.name} == 'All' || datum.opposition == {opposition_param.name})"
        f" && ({thrower_param.name} == 'All' || datum.thrower == {thrower_param.name})"
        f" && ({jumper_param.name} == 'All' || datum.jumper == {jumper_param.name})"
        f" && ({area_param.name} == 'All' || datum.area == {area_param.name})"
        f" && ({numbers_param.name} == 'All' || datum.numbers == {numbers_param.name})"
        f" && ({call_param.name} == 'All' || datum.call == {call_param.name})"
        f" && ({call_type_param.name} == 'All' || datum.call_type == {call_type_param.name})"
    )
    season_filter_expr = f"({season_param.name} == 'All' || datum.season == {season_param.name})"

    params = [
        squad_param,
        season_param,
        game_type_param,
        opposition_param,
        thrower_param,
        jumper_param,
        area_param,
        numbers_param,
        call_param,
        call_type_param,
    ]

    snapshot_base = (
        alt.Chart(df)
        .add_params(*params)
        .transform_filter(shared_filter_expr)
        .transform_filter(season_filter_expr)
        .transform_aggregate(attempts="count()", won="sum(won)", groupby=[field])
        .transform_joinaggregate(total_attempts="sum(attempts)")
        .transform_calculate(share="datum.attempts / datum.total_attempts", success_rate="datum.won / datum.attempts")
    )

    snapshot_counts = snapshot_base.mark_bar(color="#7d96e8").encode(
        x=alt.X(f"{field}:N", title=field_label, sort="-y"),
        y=alt.Y("share:Q", title="Normalised Count", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        tooltip=[
            alt.Tooltip(f"{field}:N", title=field_label),
            alt.Tooltip("attempts:Q", title="Lineouts", format=",.0f"),
            alt.Tooltip("share:Q", title="Normalised Count", format=".1%"),
        ],
    ).properties(width=320, height=240, title="Selected Slice: Normalised Counts")

    snapshot_success = snapshot_base.mark_line(point=True, color="#202946", strokeWidth=2.5).encode(
        x=alt.X(f"{field}:N", title=field_label, sort="-y"),
        y=alt.Y("success_rate:Q", title="Success Rate", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        tooltip=[
            alt.Tooltip(f"{field}:N", title=field_label),
            alt.Tooltip("won:Q", title="Won", format=",.0f"),
            alt.Tooltip("attempts:Q", title="Lineouts", format=",.0f"),
            alt.Tooltip("success_rate:Q", title="Success Rate", format=".1%"),
        ],
    ).properties(width=alt.Step(30), height=250, title="Selected Slice: Success Rate")

    trend_base = (
        alt.Chart(df)
        .add_params(*params)
        .transform_filter(shared_filter_expr)
        .transform_aggregate(attempts="count()", won="sum(won)", groupby=["season", field])
        .transform_joinaggregate(season_attempts="sum(attempts)", groupby=["season"])
        .transform_calculate(norm_count="datum.attempts / datum.season_attempts", success_rate="datum.won / datum.attempts")
    )

    trend_counts = trend_base.mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("season:N", title="Season", sort="-x"),
        y=alt.Y("norm_count:Q", title="Normalised Count", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        color=alt.Color(f"{field}:N", title=field_label),
        tooltip=[
            alt.Tooltip("season:N", title="Season"),
            alt.Tooltip(f"{field}:N", title=field_label),
            alt.Tooltip("attempts:Q", title="Lineouts", format=",.0f"),
            alt.Tooltip("norm_count:Q", title="Normalised Count", format=".1%"),
        ],
    ).properties(width=320, height=250, title="Trend: Normalised Count")

    trend_success = trend_base.mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("season:N", title="Season", sort="-x"),
        y=alt.Y("success_rate:Q", title="Success Rate", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        color=alt.Color(f"{field}:N", title=field_label),
        tooltip=[
            alt.Tooltip("season:N", title="Season"),
            alt.Tooltip(f"{field}:N", title=field_label),
            alt.Tooltip("won:Q", title="Won", format=",.0f"),
            alt.Tooltip("attempts:Q", title="Lineouts", format=",.0f"),
            alt.Tooltip("success_rate:Q", title="Success Rate", format=".1%"),
        ],
    ).properties(width=320, height=250, title="Trend: Success Rate")

    chart = alt.vconcat(
        alt.hconcat(snapshot_counts, snapshot_success, spacing=16),
        alt.hconcat(trend_counts, trend_success, spacing=16),
        spacing=22,
    ).properties(
        title=alt.Title(
            text=f"Lineout Analysis by {field_label}",
            subtitle="Use filter controls to slice by squad/season/game type and combine thrower/jumper/area/call filters.",
        )
    )

    chart.save(output_file)
    return chart


def lineout_analysis_chart_suite(db, output_dir="data/charts"):
    """Generate backend-native lineout analysis charts for key breakdown variables."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    breakdowns = ["numbers", "area", "call", "call_type", "dummy", "jumper", "thrower"]
    charts = {}
    for breakdown in breakdowns:
        output_file = output_root / f"lineout_analysis_{breakdown}.json"
        chart = lineout_analysis_chart(db, breakdown=breakdown, output_file=str(output_file), bind_params=False)
        if chart is not None:
            charts[breakdown] = chart

    return charts


#################################
# League Analysis Charts
#################################
def _infer_egr_squad(team_name):
    if not isinstance(team_name, str):
        return None
    team = team_name.strip().lower()
    if "east grinstead" not in team:
        return None
    if re.search(r"\b(ii|2nd|second)\b", team):
        return 2
    return 1


def _is_truthy_walkover(value):
    """Return True only for explicit walkover flags, not NaN/None placeholders."""

    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value == 1

    token = re.sub(r"[^A-Z0-9]", "", str(value).upper())
    return token in {"TRUE", "T", "YES", "Y", "1", "HWO", "AWO", "WO", "WALKOVER"}


def _is_future_unplayed_fixture(row):
    """Treat future fixtures without scores as unplayed even if walkover flags are noisy."""

    home_score = row.get("home_score")
    away_score = row.get("away_score")
    if pd.notna(home_score) and pd.notna(away_score):
        return False

    match_date = pd.to_datetime(row.get("date"), errors="coerce")
    if pd.isna(match_date):
        return False

    return match_date.normalize() > pd.Timestamp.today().normalize()


def _load_league_table_rank_map(squad, season):
    """Load team->rank mapping from the same CSV league tables used by league_stats.py."""

    if squad not in (1, 2):
        return {}

    season_text = _normalize_rfu_season_label(season)
    season_match = re.match(r"^(\d{4})-(\d{4})$", season_text)
    if season_match:
        start_year, end_year = season_match.groups()
        season_token = f"{start_year}_{end_year[-2:]}"
    else:
        short_match = re.match(r"^(\d{4})-(\d{2})$", season_text)
        if not short_match:
            return {}
        start_year, end_short = short_match.groups()
        season_token = f"{start_year}_{end_short}"

    csv_file = Path(__file__).resolve().parent.parent / "data" / f"league_table_{season_token}_squad_{squad}.csv"
    if not csv_file.exists():
        return {}

    try:
        table_df = pd.read_csv(csv_file)
    except Exception:
        return {}

    if table_df.empty:
        return {}

    sample_cols = set(table_df.columns)
    team_col = "TEAM" if "TEAM" in sample_cols else "Team" if "Team" in sample_cols else None
    rank_col = "#" if "#" in sample_cols else "Rank" if "Rank" in sample_cols else "Pos" if "Pos" in sample_cols else None
    if not team_col or not rank_col:
        return {}

    rank_map = {}
    for _, row in table_df.iterrows():
        team_name = row.get(team_col)
        rank_value = pd.to_numeric(row.get(rank_col), errors="coerce")
        if pd.isna(rank_value) or not team_name:
            continue
        rank_map[str(team_name)] = int(rank_value)

    return rank_map


def _derive_league_result(row):
    if row["home_team"] == row["away_team"]:
        return "N/A"

    if _is_future_unplayed_fixture(row):
        return "To be played"

    if _is_truthy_walkover(row.get("home_walkover")):
        return "Home Win"
    if _is_truthy_walkover(row.get("away_walkover")):
        return "Away Win"

    home_score = row.get("home_score")
    away_score = row.get("away_score")
    if pd.isna(home_score) or pd.isna(away_score):
        return "To be played"

    pdiff = int(home_score) - int(away_score)
    if pdiff > 0:
        return "Home Win (LBP)" if pdiff <= 7 else "Home Win"
    if pdiff < 0:
        return "Away Win (LBP)" if abs(pdiff) <= 7 else "Away Win"
    return "Draw"


def _normalize_rfu_season_label(season):
    """Normalise RFU season labels for stable filenames/index keys.

    Examples:
    - 2021/22 -> 2021-2022
    - 2021-22 -> 2021-2022
    - 2024-2025 -> 2024-2025
    """

    text = str(season or "").strip()
    match_short = re.match(r"^(\d{4})[/-](\d{2})$", text)
    if match_short:
        start = int(match_short.group(1))
        end = int(match_short.group(2))
        end_full = (start // 100) * 100 + end
        if end_full < start:
            end_full += 100
        return f"{start}-{end_full}"

    match_long = re.match(r"^(\d{4})[/-](\d{4})$", text)
    if match_long:
        return f"{match_long.group(1)}-{match_long.group(2)}"

    return text.replace("/", "-")


def _league_score_coverage(con):
    """Return (total_league_rows, rows_with_scores) for games_rfu in a connection."""

    total_rows, with_scores = con.execute(
        """
        SELECT
            COUNT(*) AS total_rows,
            SUM(CASE WHEN home_score IS NOT NULL AND away_score IS NOT NULL THEN 1 ELSE 0 END) AS with_scores
        FROM games_rfu
        WHERE league IS NOT NULL
        """
    ).fetchone()

    return int(total_rows or 0), int(with_scores or 0)


def _select_league_source_connection(db):
    """Pick the backend DB connection with the best games_rfu score coverage.

    This prevents league chart specs being generated from a stale primary DB when
    the fallback backend DB has fresher RFU scores.
    """

    active_con = db.con
    best_con = active_con
    best_label = "active"
    best_total, best_scores = _league_score_coverage(active_con)
    opened_connections = []

    root = Path(__file__).resolve().parent.parent
    candidate_paths = [
        root / "data" / "egrfc_backend.duckdb",
        root / "data" / "egrfc_backend_alt.duckdb",
    ]

    active_db_path = None
    if hasattr(db, "config") and getattr(db.config, "db_path", None):
        active_db_path = (root / db.config.db_path).resolve()

    for candidate in candidate_paths:
        try:
            resolved_candidate = candidate.resolve()
        except FileNotFoundError:
            continue

        if active_db_path is not None and resolved_candidate == active_db_path:
            continue
        if not candidate.exists():
            continue

        try:
            con = duckdb.connect(str(candidate), read_only=True)
            opened_connections.append(con)
            total_rows, with_scores = _league_score_coverage(con)
        except Exception:
            continue

        if with_scores > best_scores:
            best_con = con
            best_label = candidate.name
            best_total = total_rows
            best_scores = with_scores

    return best_con, best_label, best_total, best_scores, opened_connections


def league_results_chart(db, season="2024-2025", league="Counties 1 Surrey/Sussex", output_file="data/charts/league_results.json", squad=None):
    """Create league results matrix chart from canonical backend data."""

    df = db.con.execute(
        """
        SELECT
            match_id,
            date,
            home_team,
            away_team,
            home_score,
            away_score,
            home_walkover,
            away_walkover
        FROM games_rfu
        WHERE season = ? AND league = ?
        ORDER BY date DESC
        """,
        [season, league],
    ).df()

    if df.empty:
        print(f"No league data found for {season} {league}")
        return None

    teams = sorted(set(df["home_team"].dropna().unique()) | set(df["away_team"].dropna().unique()))

    import itertools

    matrix_df = pd.DataFrame(list(itertools.product(teams, repeat=2)), columns=["home_team", "away_team"])
    matrix_df = matrix_df.merge(df, on=["home_team", "away_team"], how="left")

    matrix_df["result"] = matrix_df.apply(_derive_league_result, axis=1)

    def _score_parts(row):
        if row["home_team"] == row["away_team"]:
            return ("", "", "")

        if _is_future_unplayed_fixture(row):
            return ("", "", "")

        if _is_truthy_walkover(row.get("home_walkover")):
            return ("WO", "", "HWO")
        if _is_truthy_walkover(row.get("away_walkover")):
            return ("", "WO", "AWO")

        home_score = row.get("home_score")
        away_score = row.get("away_score")
        if pd.notna(home_score) and pd.notna(away_score):
            return (str(int(home_score)), str(int(away_score)), "")

        return ("", "", "")

    score_parts = matrix_df.apply(_score_parts, axis=1)
    matrix_df[["home_score_text", "away_score_text", "wo_result"]] = pd.DataFrame(
        score_parts.tolist(), index=matrix_df.index
    )
    matrix_df["score_text"] = matrix_df.apply(
        lambda row: f"{row['home_score_text']}-{row['away_score_text']}"
        if row["home_score_text"] and row["away_score_text"]
        else row["home_score_text"] or row["away_score_text"],
        axis=1,
    )

    completed_df = df.dropna(subset=["home_score", "away_score"]).copy()
    if completed_df.empty:
        pd_map = {}
    else:
        completed_df["home_pd"] = completed_df["home_score"] - completed_df["away_score"]
        completed_df["away_pd"] = completed_df["away_score"] - completed_df["home_score"]
        home_pd = completed_df.groupby("home_team", as_index=True)["home_pd"].sum()
        away_pd = completed_df.groupby("away_team", as_index=True)["away_pd"].sum()
        pd_map = home_pd.add(away_pd, fill_value=0).to_dict()

    matrix_df["display_text"] = matrix_df["score_text"]
    matrix_df["is_diagonal"] = matrix_df["home_team"] == matrix_df["away_team"]
    diagonal_mask = matrix_df["home_team"] == matrix_df["away_team"]
    matrix_df.loc[diagonal_mask, "display_text"] = matrix_df.loc[diagonal_mask, "home_team"].map(
        lambda team: f"{int(pd_map.get(team, 0)):+d}"
    )

    matrix_df["result_simple"] = matrix_df["result"].map(
        lambda value: "Home Win" if str(value).startswith("Home Win")
        else "Away Win" if str(value).startswith("Away Win")
        else "Draw" if value == "Draw"
        else "To be played" if value == "To be played"
        else "N/A"
    )

    rank_map = _load_league_table_rank_map(squad, season)
    if rank_map:
        team_order = sorted(teams, key=lambda team: (rank_map.get(team, 999), team))
    else:
        team_order = sorted(teams)
    preferred_eg_team = "East Grinstead II" if squad == 2 else "East Grinstead"
    default_eg_team = preferred_eg_team if preferred_eg_team in team_order else next(
        (team for team in team_order if str(team).startswith("East Grinstead")),
        None,
    )
    default_highlight = [{"home_team": default_eg_team}] if default_eg_team else None

    color_scale = alt.Scale(
        domain=["Home Win", "Home Win (LBP)", "Away Win", "Away Win (LBP)", "Draw", "To be played", "N/A"],
        range=["#146f14", "#146f14a0", "#991515", "#991515a0", "goldenrod", "white", "#202946"],
    )

    result_legend = alt.Legend(
        orient="bottom",
        direction="horizontal",
        columns=4,
        symbolStrokeColor="black",
        symbolStrokeWidth=1,
        values=["Home Win", "Away Win", "Draw", "To be played"],
        offset=16,
        labelLimit=200,
    )

    highlight = alt.selection_point(fields=["home_team"], on="click", clear="dblclick", empty="none", value=default_highlight)
    predicate = f"datum.home_team == {highlight.name}['home_team'] || datum.away_team == {highlight.name}['home_team']"
    visible_predicate = f"{predicate} || !isValid({highlight.name}['home_team'])"
    text_color = alt.condition(visible_predicate, alt.value("white"), alt.value("black"))

    title_text = f"{league} Results"

    base = alt.Chart(matrix_df).add_params(highlight)
    heatmap = base.mark_rect().encode(
        x=alt.X("away_team:N", title="Away Team", sort=team_order[::-1], axis=alt.Axis(labelAngle=30, orient="top", ticks=False, domain=False, grid=False)),
        y=alt.Y("home_team:N", title="Home Team", sort=team_order, axis=alt.Axis(ticks=False, domain=False, grid=False)),
        color=alt.Color(
            "result:N",
            scale=color_scale,
            title="Result",
            legend=result_legend,
        ),
        opacity=alt.condition(visible_predicate, alt.value(1.0), alt.value(0.2)),
        tooltip=[
            alt.Tooltip("home_team:N", title="Home"),
            alt.Tooltip("away_team:N", title="Away"),
            alt.Tooltip("home_score_text:N", title="Home Score"),
            alt.Tooltip("away_score_text:N", title="Away Score"),
            alt.Tooltip("result:N", title="Result"),
            alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
        ],
    )

    text_home_regular = base.transform_filter("datum.home_score_text != '' && datum.home_score_text != 'WO'").mark_text(
        size=15,
        xOffset=-10,
        yOffset=5,
        fontWeight="bold",
    ).encode(
        x=alt.X("away_team:N", sort=team_order[::-1]),
        y=alt.Y("home_team:N", sort=team_order),
        text=alt.Text("home_score_text:N"),
        color=text_color,
        opacity=alt.condition(visible_predicate, alt.value(1.0), alt.value(0.5)),
    )

    text_home_wo = base.transform_filter("datum.home_score_text == 'WO'").mark_text(
        size=12,
        xOffset=-10,
        yOffset=5,
    ).encode(
        x=alt.X("away_team:N", sort=team_order[::-1]),
        y=alt.Y("home_team:N", sort=team_order),
        text=alt.Text("home_score_text:N"),
        color=text_color,
        opacity=alt.condition(visible_predicate, alt.value(1.0), alt.value(0.5)),
    )

    text_away_regular = base.transform_filter("datum.away_score_text != '' && datum.away_score_text != 'WO'").mark_text(
        size=14,
        xOffset=10,
        yOffset=-5,
        fontStyle="italic",
    ).encode(
        x=alt.X("away_team:N", sort=team_order[::-1]),
        y=alt.Y("home_team:N", sort=team_order),
        text=alt.Text("away_score_text:N"),
        color=text_color,
        opacity=alt.condition(visible_predicate, alt.value(0.8), alt.value(0.4)),
    )

    text_away_wo = base.transform_filter("datum.away_score_text == 'WO'").mark_text(
        size=12,
        xOffset=10,
        yOffset=-5,
    ).encode(
        x=alt.X("away_team:N", sort=team_order[::-1]),
        y=alt.Y("home_team:N", sort=team_order),
        text=alt.Text("away_score_text:N"),
        color=text_color,
        opacity=alt.condition(visible_predicate, alt.value(0.8), alt.value(0.4)),
    )

    diagonal_df = matrix_df[matrix_df["is_diagonal"]].copy()
    diagonal_df = diagonal_df.where(pd.notna(diagonal_df), None)
    text_pd = alt.Chart(diagonal_df).mark_text(size=16, color="white", fontWeight="bold").encode(
        x=alt.X("away_team:N", sort=team_order[::-1]),
        y=alt.Y("home_team:N", sort=team_order),
        text=alt.Text("display_text:N"),
        tooltip=[
            alt.Tooltip("home_team:N", title="Team"),
            alt.Tooltip("display_text:N", title="Points Difference"),
        ],
    )

    chart = alt.layer(
        heatmap,
        text_away_regular,
        text_away_wo,
        text_home_regular,
        text_home_wo,
        text_pd,
    ).properties(
        width=alt.Step(50),
        height=alt.Step(35),
        title=alt.Title(
            text=title_text,
            subtitle=[
                f"Season {season}",
                "Diagonal values are total points difference by team.",
                "Lighter shading indicates results within 7 points (losing bonus point).",
                "Click a cell to highlight a team's results; double-click to reset.",
            ],
        ),
        padding={"left": 20, "top": 20, "right": 40, "bottom": 120},
    ).configure_view(stroke=None)

    chart.save(output_file)
    return chart


def export_league_context_chart_specs(db, output_dir="data/charts", squads=("1st",)):
    """Export league squad-size and continuity context specs for squad-stats page."""

    def _parse_squad(value):
        text = str(value).strip().lower()
        if text in {"1", "1st", "first"}:
            return 1, "1st"
        if text in {"2", "2nd", "second"}:
            return 2, "2nd"
        raise ValueError(f"Unsupported squad value: {value}")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    exports = {}

    for squad in squads:
        squad_num, squad_label = _parse_squad(squad)

        players_per_team = db.con.execute(
            """
            SELECT
                season AS Season,
                team AS Team,
                unit AS Unit,
                players AS "Total Players"
            FROM v_rfu_squad_size
            WHERE squad = ?
            ORDER BY season, team, unit
            """,
            [squad_label],
        ).df()

        average_retention = db.con.execute(
            """
            SELECT
                season AS Season,
                team AS Team,
                unit AS Unit,
                average_retention AS "Average Retention"
            FROM v_rfu_average_retention
            WHERE squad = ?
            ORDER BY season, team, unit
            """,
            [squad_label],
        ).df()

        if players_per_team.empty or average_retention.empty:
            print(f"Skipping league context chart specs for {squad_label}: no RFU context rows available.")
            continue

        players_per_team["IsEGR"] = players_per_team["Team"].astype(str).str.startswith("East Grinstead")
        average_retention["IsEGR"] = average_retention["Team"].astype(str).str.startswith("East Grinstead")

        eg_players = players_per_team[players_per_team["IsEGR"]].copy()
        eg_retention = average_retention[average_retention["IsEGR"]].copy()
        if eg_players.empty or eg_retention.empty:
            print(f"Skipping league context chart specs for {squad_label}: no East Grinstead rows available.")
            continue

        squad_size_trend = (
            players_per_team
            .groupby(["Season", "Unit"], as_index=False)
            .agg(
                **{
                    "League Min": ("Total Players", "min"),
                    "League Max": ("Total Players", "max"),
                    "League Average": ("Total Players", "mean"),
                }
            )
            .merge(
                eg_players[["Season", "Unit", "Team", "Total Players", "IsEGR"]],
                on=["Season", "Unit"],
                how="inner",
            )
        )

        continuity_trend = (
            average_retention
            .groupby(["Season", "Unit"], as_index=False)
            .agg(
                **{
                    "League Min": ("Average Retention", "min"),
                    "League Max": ("Average Retention", "max"),
                    "League Average": ("Average Retention", "mean"),
                }
            )
            .merge(
                eg_retention[["Season", "Unit", "Team", "Average Retention", "IsEGR"]],
                on=["Season", "Unit"],
                how="inner",
            )
        )

        squad_size_y = alt.Y(
            "Team:N",
            sort=alt.SortField(field="Total Players", order="descending"),
            title=None,
            axis=alt.Axis(labels=False, ticks=False, domain=False),
        )

        continuity_y = alt.Y(
            "Team:N",
            sort=alt.SortField(field="Average Retention", order="descending"),
            title=None,
            axis=alt.Axis(labels=False, ticks=False, domain=False),
        )

        squad_size_chart = alt.layer(
            alt.Chart(players_per_team)
            .mark_bar(strokeWidth=2)
            .encode(
                x=alt.X("Total Players:Q", title="Squad Size"),
                y=squad_size_y,
                color=alt.condition(
                    alt.datum.IsEGR,
                    alt.value("#202946"),
                    alt.value("#991515"),
                ),
                tooltip=["Team", "Season", "Unit", alt.Tooltip("Total Players:Q", title="Total Players")],
            ),
            alt.Chart(players_per_team)
            .mark_text(align="left", baseline="middle", dx=6, fontSize=13)
            .encode(
                x=alt.XDatum(0),
                y=squad_size_y,
                text="Team:N",
                color=alt.condition(
                    alt.datum.IsEGR,
                    alt.value("#7d96e8"),
                    alt.value("white"),
                ),
                opacity=alt.condition(
                    alt.datum.IsEGR,
                    alt.value(1),
                    alt.value(0.5),
                ),
            ),
        ).properties(width=240, height=400)

        continuity_chart = alt.layer(
            alt.Chart(average_retention)
            .mark_bar(strokeWidth=2)
            .encode(
                x=alt.X("Average Retention:Q", title="Average Continuity"),
                y=continuity_y,
                color=alt.condition(
                    alt.datum.IsEGR,
                    alt.value("#202946"),
                    alt.value("#991515"),
                ),
                tooltip=[
                    "Team",
                    "Season",
                    "Unit",
                    alt.Tooltip("Average Retention:Q", title="Average Players Retained", format=".2f"),
                ],
            ),
            alt.Chart(average_retention)
            .mark_text(align="left", baseline="middle", dx=6, fontSize=13)
            .encode(
                x=alt.XDatum(0),
                y=continuity_y,
                text="Team:N",
                color=alt.condition(
                    alt.datum.IsEGR,
                    alt.value("#7d96e8"),
                    alt.value("white"),
                ),
                opacity=alt.condition(
                    alt.datum.IsEGR,
                    alt.value(1),
                    alt.value(0.5),
                ),
            ),
        ).properties(width=240, height=400)

        squad_size_trend_chart = alt.layer(
            alt.Chart(squad_size_trend)
            .mark_area(color="#991515", opacity=0.2)
            .encode(
                x=alt.X("Season:N", title="Season"),
                y=alt.Y("League Min:Q", title="Squad Size"),
                y2="League Max:Q",
                tooltip=[
                    alt.Tooltip("Season:N", title="Season"),
                    alt.Tooltip("Unit:N", title="Unit"),
                    alt.Tooltip("League Min:Q", title="League Min", format=".0f"),
                    alt.Tooltip("League Max:Q", title="League Max", format=".0f"),
                    alt.Tooltip("League Average:Q", title="League Average", format=".1f"),
                ],
            ),
            alt.Chart(squad_size_trend)
            .mark_line(color="gray", strokeDash=[5, 5], strokeWidth=2)
            .encode(
                x=alt.X("Season:N"),
                y=alt.Y("League Average:Q", axis=alt.Axis(orient="right")),
                detail="Unit:N",
            ),
            alt.Chart(squad_size_trend)
            .mark_line(point={"size": 100}, strokeWidth=3)
            .encode(
                x=alt.X("Season:N"),
                y=alt.Y("Total Players:Q"),
                color=alt.condition(
                    alt.datum.IsEGR,
                    alt.value("#202946"),
                    alt.value("#991515"),
                ),
                detail="Unit:N",
                tooltip=[
                    alt.Tooltip("Season:N", title="Season"),
                    alt.Tooltip("Unit:N", title="Unit"),
                    alt.Tooltip("Total Players:Q", title="East Grinstead", format=".0f"),
                ],
            ),
        ).properties(width=300, height=400)

        continuity_trend_chart = alt.layer(
            alt.Chart(continuity_trend)
            .mark_area(color="gray", opacity=0.2)
            .encode(
                x=alt.X("Season:N", title="Season"),
                y=alt.Y("League Min:Q", title="Average Continuity"),
                y2="League Max:Q",
                tooltip=[
                    alt.Tooltip("Season:N", title="Season"),
                    alt.Tooltip("Unit:N", title="Unit"),
                    alt.Tooltip("League Min:Q", title="League Min", format=".2f"),
                    alt.Tooltip("League Max:Q", title="League Max", format=".2f"),
                    alt.Tooltip("League Average:Q", title="League Average", format=".2f"),
                ],
            ),
            alt.Chart(continuity_trend)
            .mark_line(color="gray", strokeDash=[5, 5], strokeWidth=2)
            .encode(
                x=alt.X("Season:N"),
                y=alt.Y("League Average:Q", axis=alt.Axis(orient="right")),
                detail="Unit:N",
            ),
            alt.Chart(continuity_trend)
            .mark_line(point={"size": 100}, strokeWidth=3)
            .encode(
                x=alt.X("Season:N"),
                y=alt.Y("Average Retention:Q"),
                color=alt.condition(
                    alt.datum.IsEGR,
                    alt.value("#202946"),
                    alt.value("#991515"),
                ),
                opacity=alt.condition(
                    alt.datum.IsEGR,
                    alt.value(1),
                    alt.value(0.5),
                ),

                detail="Unit:N",
                tooltip=[
                    alt.Tooltip("Season:N", title="Season"),
                    alt.Tooltip("Unit:N", title="Unit"),
                    alt.Tooltip("Average Retention:Q", title="East Grinstead", format=".2f"),
                ],
            ),
        ).properties(width=300, height=400)

        squad_size_context_chart = alt.hconcat(
            squad_size_chart,
            squad_size_trend_chart,
            spacing=18,
        ).resolve_scale(y="independent").properties(
            title=alt.Title(
                text="League Squad Size",
                subtitle="Comparison for the selected season alongside East Grinstead trend by unit.",
            )
        )

        continuity_context_chart = alt.hconcat(
            continuity_chart,
            continuity_trend_chart,
            spacing=18,
        ).resolve_scale(y="independent").properties(
            title=alt.Title(
                text="League Squad Continuity",
                subtitle="Comparison for the selected season alongside East Grinstead trend by unit.",
            )
        )

        size_file = output_root / f"league_squad_size_context_{squad_num}s.json"
        continuity_file = output_root / f"league_continuity_context_{squad_num}s.json"
        squad_size_context_chart.save(str(size_file))
        continuity_context_chart.save(str(continuity_file))

        exports[f"{squad_num}s"] = {
            "squad_size_file": size_file.name,
            "continuity_file": continuity_file.name,
        }

    return exports


def export_league_results_chart_specs(db, output_dir="data/charts"):
    """Export season/squad league results matrix specs from backend data."""

    source_con, source_label, total_rows, scored_rows, opened_connections = _select_league_source_connection(db)
    if source_label != "active":
        print(
            "League chart export is using "
            f"{source_label} for games_rfu scores ({scored_rows}/{total_rows} scored fixtures)."
        )

    try:
        league_rows = source_con.execute(
        """
        SELECT season, league, home_team, away_team
        FROM games_rfu
        WHERE league IS NOT NULL
        """
        ).df()

        if league_rows.empty:
            print("No league fixtures found in games_rfu; skipping league results chart exports.")
            return {}

        pairs = []
        for _, row in league_rows.iterrows():
            season = row["season"]
            league = row["league"]
            squads = {
                _infer_egr_squad(row["home_team"]),
                _infer_egr_squad(row["away_team"]),
            }
            for squad in squads:
                if squad in (1, 2):
                    pairs.append({"season": season, "league": league, "squad": squad})

        if not pairs:
            print("No East Grinstead league fixtures found; skipping league results chart exports.")
            return {}

        pair_df = pd.DataFrame(pairs)
        pair_df = (
            pair_df.groupby(["season", "squad", "league"], as_index=False)
            .size()
            .rename(columns={"size": "egr_matches"})
            .sort_values(["season", "squad", "egr_matches"], ascending=[True, True, False])
        )
        selected_pairs = pair_df.drop_duplicates(["season", "squad"], keep="first")

        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        exports = {}

        # Build a thin proxy so league_results_chart can use the selected connection.
        source_db = db if source_con is db.con else type("_LeagueSourceDB", (), {"con": source_con})()

        for _, row in selected_pairs.iterrows():
            season = row["season"]
            season_key = _normalize_rfu_season_label(season)
            squad = int(row["squad"])
            league = row["league"]

            filename = f"league_results_{squad}s_{season_key}.json"
            output_file = output_root / filename

            chart = league_results_chart(
                source_db,
                season=season,
                league=league,
                output_file=str(output_file),
                squad=squad,
            )

            if chart is not None:
                exports.setdefault(season_key, {})[str(squad)] = {
                    "league": league,
                    "file": filename,
                }

        if exports:
            index_file = output_root / "league_results_index.json"
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(exports, f, indent=2)

        return exports
    finally:
        for con in opened_connections:
            try:
                con.close()
            except Exception:
                pass

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
        WITH scorer_totals AS (
            SELECT
                season,
                squad,
                player,
                SUM(points) AS points,
                SUM(tries) AS tries,
                SUM(conversions) AS conversions,
                SUM(penalties) AS penalties,
                SUM(drop_goals) AS drop_goals
            FROM season_scorers
            GROUP BY season, squad, player
        )
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
        FROM scorer_totals s
        WHERE points > 0
        ORDER BY s.season DESC, s.squad, s.points DESC
        """
    ).df()
    
    # Get top try scorers per season/squad
    try_scorers = db.con.execute(
        """
        WITH scorer_totals AS (
            SELECT
                season,
                squad,
                player,
                SUM(points) AS points,
                SUM(tries) AS tries
            FROM season_scorers
            GROUP BY season, squad, player
        )
        SELECT
            s.season,
            s.squad,
            s.player,
            s.tries,
            s.points,
            ROW_NUMBER() OVER (PARTITION BY s.season, s.squad ORDER BY s.tries DESC) as rank
        FROM scorer_totals s
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
            ROUND(AVG(s.points_per_entry), 2) as avg_points_per_22m_entry,
            ROUND(AVG(s.tries_per_entry), 2) as avg_tries_per_22m_entry,
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
            SUM(COALESCE(points, 0)) AS points,
            SUM(COALESCE(tries, 0)) AS tries,
            SUM(COALESCE(conversions, 0)) AS conversions,
            SUM(COALESCE(penalties, 0)) AS penalties,
            SUM(COALESCE(drop_goals, 0)) AS drop_goals
        FROM season_scorers
        GROUP BY player, season, squad
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
