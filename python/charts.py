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
from python.chart_helpers import hack_params_css, alt_theme, get_embed_options

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

def lineout_success_by_zone(df=None, squad="1st", min_total=20, file=None):

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
        sort=alt.SortField(field='player_total', order='descending'),
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
            player_total='max(player_total)',
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
                legend=alt.Legend(title=None, orient='none', legendX=250, legendY=50)
            ),
            order=alt.Order('stack_order:Q', sort='ascending'),
            tooltip=tooltip,
        )
    )

    totals = (
        alt.Chart(df)
        .transform_aggregate(
            total_games='sum(games)',
            player_total='max(player_total)',
            groupby=['player', 'squad']
        )
        .mark_text(align='left', baseline='middle', dx=4, fontSize=11, color='black')
        .encode(
            x=alt.X('total_games:Q', axis=alt.Axis(title=None, orient='top')),
            y=alt.Y(
                'player:N',
                sort=alt.SortField(field='player_total', order='descending'),
                title=None,
            ),
            text=alt.Text('total_games:Q', format='.0f')
        )
    )

    chart = (
        alt.layer(bars, totals)
        .transform_joinaggregate(player_total='sum(games)', groupby=['player', 'squad'])
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


def player_stats_motm_chart(db, output_file='data/charts/player_stats_motm.json'):
    """Man of the Match awards from the games.motm column.

    Supported filters in the generated Vega spec:
        seasonParam     - [] (all seasons) or an array of season labels
        gameTypesParam  - [] (all) or an array of allowed game_type strings
        squadParam      - 'All', '1st', or '2nd'
    """

    base_df = db.con.execute(
        """
        SELECT
            G.squad,
            G.season,
            COALESCE(G.game_type, 'Unknown') AS game_type,
            G.motm,
            P.position
        FROM games G
        LEFT JOIN players P ON G.motm = P.name
        WHERE motm IS NOT NULL AND TRIM(motm) <> ''
        """
    ).df()

    if base_df.empty:
        df = pd.DataFrame(
            columns=[
                'player', 'position', 'squad', 'season', 'game_type',
                'motm_awards', 'unit', 'unit_sort', 'position_sort', 'position_opacity'
            ]
        )
    else:
        motm_df = base_df.copy()
        motm_df['motm'] = motm_df['motm'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()

        invalid_names = {'', 'none', 'null', 'nan', 'n/a', 'na', 'tbc', '-', 'unknown'}
        motm_df = motm_df[~motm_df['motm'].str.lower().isin(invalid_names)].copy()

        # Some records include joint awards in one string.
        motm_df['player'] = motm_df['motm'].str.split(r'\s*(?:,|/|&|\band\b|\+)\s*', regex=True)
        motm_df = motm_df.explode('player', ignore_index=True)
        motm_df['player'] = motm_df['player'].astype(str).str.strip()
        motm_df = motm_df[motm_df['player'] != ''].copy()
        motm_df['player'] = motm_df['player'].map(lambda name: other_names.get(name, name))

        df = (
            motm_df
            .groupby(['player', 'position', 'squad', 'season', 'game_type'], as_index=False)
            .size()
            .rename(columns={'size': 'motm_awards'})
        )

        df['position'] = df['position'].fillna('Other')

        unit_map = {
            'Prop': 'Forwards',
            'Hooker': 'Forwards',
            'Second Row': 'Forwards',
            'Flanker': 'Forwards',
            'Number 8': 'Forwards',
            'Scrum Half': 'Backs',
            'Fly Half': 'Backs',
            'Centre': 'Backs',
            'Wing': 'Backs',
            'Full Back': 'Backs',
        }
        position_order = [
            'Prop', 'Hooker', 'Second Row', 'Flanker', 'Number 8',
            'Scrum Half', 'Fly Half', 'Centre', 'Wing', 'Full Back',
        ]
        position_sort_map = {pos: idx + 1 for idx, pos in enumerate(position_order)}
        opacity_map = {
            'Prop': 1.00,
            'Hooker': 0.88,
            'Second Row': 0.76,
            'Flanker': 0.64,
            'Number 8': 0.52,
            'Scrum Half': 1.00,
            'Fly Half': 0.88,
            'Centre': 0.76,
            'Wing': 0.64,
            'Full Back': 0.52,
        }

        df['unit'] = df['position'].map(unit_map).fillna('Other')
        df['unit_sort'] = df['unit'].map({'Forwards': 1, 'Backs': 2, 'Other': 3}).fillna(99)
        df['position_sort'] = df['position'].map(position_sort_map).fillna(999)
        df['position_opacity'] = df['position'].map(opacity_map).fillna(0.55)

    season_param = alt.param(name='seasonParam', value=[])
    game_types_param = alt.param(name='gameTypesParam', value=[])
    squad_param = alt.param(name='squadParam', value='All')

    bars = alt.Chart(df).mark_bar().encode(
        x=alt.X('sum(motm_awards):Q', axis=alt.Axis(title=None, orient='top')),
        y=alt.Y(
            'player:N',
            sort=alt.EncodingSortField(field='player_total', order='descending', op='max'),
            title=None,
        ),
        color=alt.Color(
            'squad:N',
            sort=['1st', '2nd'],
            scale=alt.Scale(domain=['1st', '2nd'], range=['#202946', '#7d96e8']),
            legend=alt.Legend(
                title=None, 
                orient="none", 
                legendX=200, 
                legendY=100, 
                direction='vertical', 
                labelExpr="datum.value + ' XV'"
            )
        ),
        tooltip=[
            alt.Tooltip('player:N', title='Player'),
            alt.Tooltip('squad:N', title='Squad'),
            alt.Tooltip('position:N', title='Position'),
            alt.Tooltip('unit:N', title='Unit'),
            alt.Tooltip('sum(motm_awards):Q', title='MOTM Awards'),
            alt.Tooltip('max(player_total):Q', title='Total'),
        ]
    )

    total_labels = alt.Chart(df).transform_aggregate(
        total_awards='sum(motm_awards)',
        player_total='max(player_total)',
        groupby=['player']
    ).mark_text(
        align='left',
        baseline='middle',
        dx=4,
        fontSize=11,
        color='black'
    ).encode(
        x=alt.X('total_awards:Q', axis=alt.Axis(title=None, orient='top', tickCount=3, format='.0f')),
        y=alt.Y(
            'player:N',
            sort=alt.EncodingSortField(field='player_total', order='descending', op='max'),
            title=None,
        ),
        text=alt.Text('total_awards:Q', format='.0f')
    )

    player_panel = (
        alt.layer(bars, total_labels)
        .transform_filter('length(seasonParam) === 0 || indexof(seasonParam, datum.season) >= 0')
        .transform_filter('length(gameTypesParam) === 0 || indexof(gameTypesParam, datum.game_type) >= 0')
        .transform_filter('squadParam === "All" || datum.squad === squadParam')
        .transform_joinaggregate(player_total='sum(motm_awards)', groupby=['player'])
        .transform_filter('datum.player_total > 0')
        .add_params(season_param, game_types_param, squad_param)
        .properties(
            title=alt.Title(text='Man of the Match', subtitle='Number of MOTM awards per player (of those on record).'),
            width=300,
            height=alt.Step(15)
        )
    )

    unit_base = (
        alt.Chart(df)
        .transform_filter('length(seasonParam) === 0 || indexof(seasonParam, datum.season) >= 0')
        .transform_filter('length(gameTypesParam) === 0 || indexof(gameTypesParam, datum.game_type) >= 0')
        .transform_filter('squadParam === "All" || datum.squad === squadParam')
        .transform_aggregate(
            motm_awards='sum(motm_awards)',
            position_sort='min(position_sort)',
            position_opacity='max(position_opacity)',
            groupby=['unit', 'unit_sort', 'position']
        )
        .transform_joinaggregate(unit_total='sum(motm_awards)', groupby=['unit'])
        .transform_calculate(segment_share='datum.unit_total > 0 ? datum.motm_awards / datum.unit_total : 0')
        .transform_calculate(
            segment_color=(
                "datum.unit === 'Forwards' ? "
                "(datum.position === 'Prop' ? '#202946' : "
                " datum.position === 'Hooker' ? '#2e4b8c' : "
                " datum.position === 'Second Row' ? '#4667b0' : "
                " datum.position === 'Flanker' ? '#6f8fda' : '#9eb6ee') : "
                "datum.unit === 'Backs' ? "
                "(datum.position === 'Scrum Half' ? 'black' : "
                " datum.position === 'Fly Half' ? '#1a1a1a' : "
                " datum.position === 'Centre' ? '#2a2a2a' : "
                " datum.position === 'Wing' ? '#3a3a3a' : '#4a4a4a') : '#9ca3af'"
            )
        )
        .transform_calculate(
            label_color=(
                "datum.segment_color === '#ffffff' || datum.segment_color === '#f3f4f6' ? '#111111' : '#ffffff'"
            )
        )
        .transform_filter('datum.motm_awards > 0')
    )

    unit_bars = unit_base.mark_bar(strokeWidth=0.8).encode(
        x=alt.X('motm_awards:Q', axis=alt.Axis(title=None, orient='top', tickCount=3, format='.0f')),
        y=alt.Y('unit:N', sort=['Forwards', 'Backs', 'Other'], title=None),
        color=alt.Color(
            'segment_color:N',
            scale=None,
            legend=None
        ),
        opacity=alt.Opacity(
            'position_opacity:Q',
            scale=None,
            legend=None
        ),
        order=alt.Order('position_sort:Q', sort='ascending'),
        tooltip=[
            alt.Tooltip('unit:N', title='Unit'),
            alt.Tooltip('position:N', title='Position'),
            alt.Tooltip('motm_awards:Q', title='MOTM Awards'),
            alt.Tooltip('unit_total:Q', title='Unit Total'),
            alt.Tooltip('segment_share:Q', title='Share', format='.0%'),
        ]
    )

    segment_labels = (
        unit_base
        .transform_stack(
            stack='motm_awards',
            groupby=['unit'],
            sort=[alt.SortField(field='position_sort', order='ascending')],
            as_=['x0', 'x1']
        )
        .transform_calculate(x_mid='(datum.x0 + datum.x1) / 2')
        .mark_text(fontSize=10, fontWeight='bold', align='center', baseline='middle')
        .encode(
            x=alt.X('x_mid:Q'),
            y=alt.Y('unit:N', sort=['Forwards', 'Backs', 'Other'], title=None),
            text=alt.condition(
                'datum.motm_awards >= 2 || datum.segment_share >= 0.16',
                alt.Text('position:N'),
                alt.value('')
            ),
            color=alt.Color('label_color:N', scale=None, legend=None),
            opacity=alt.condition(
                'datum.motm_awards >= 2 || datum.segment_share >= 0.16',
                alt.value(1),
                alt.value(0)
            )
        )
    )

    unit_total_labels = (
        unit_base
        .transform_aggregate(
            unit_total='max(unit_total)',
            groupby=['unit']
        )
        .mark_text(
            align='left',
            baseline='middle',
            dx=4,
            fontSize=11,
            color='black'
        )
        .encode(
            x=alt.X('unit_total:Q'),
            y=alt.Y('unit:N', sort=['Forwards', 'Backs', 'Other'], title=None),
            text=alt.Text('unit_total:Q', format='.0f')
        )
    )

    aggregated_panel = (
        alt.layer(unit_bars, segment_labels, unit_total_labels)
        .properties(
            width=300,
            height=alt.Step(24)
        )
    )

    chart = (
        alt.vconcat(player_panel, aggregated_panel, spacing=18)
        .add_params(season_param, game_types_param, squad_param)
        .resolve_scale(x='independent')
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
            G.game_type,
            COALESCE(P.position, 'Unknown') AS position,
            CASE WHEN P.is_starter THEN 'Start' ELSE 'Bench' END AS start,
            COUNT(*) AS games
        FROM player_appearances P
        LEFT JOIN games G USING (game_id)
        GROUP BY
            P.player,
            COALESCE(G.squad, P.squad),
            COALESCE(G.season, P.season),
            G.game_type,
            COALESCE(P.position, 'Unknown'),
            CASE WHEN P.is_starter THEN 'Start' ELSE 'Bench' END
        """
    ).df()

    stack_order_map = {
        ('1st', 'Start'): 1,
        ('1st', 'Bench'): 2,
        ('2nd', 'Start'): 3,
        ('2nd', 'Bench'): 4,
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
            legend=alt.Legend(title=None, orient='bottom-right', direction='vertical', labelExpr="datum.value + ' XV'")
        ),
        opacity=alt.Opacity(
            'start:N',
            sort=['Start', 'Bench'],
            scale=alt.Scale(domain=['Start', 'Bench'], range=[1.0, 0.6]),
            legend=alt.Legend(title=None, orient='bottom-right', direction='vertical')
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
            COALESCE(P.position, 'Unknown') AS position,
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

    by_position = base_df[['player', 'season', 'season_sort', 'apps', 'position']].copy()
    by_position['color_mode'] = 'Position'
    by_position['color_value'] = by_position['position']

    palette_by_rank = ['#202946', '#7d96e8', '#146f14', '#991515', '#333333', '#000000']
    bench_color = '#6b7280'
    unknown_color = '#99151520'

    position_totals = (
        by_position
        .groupby(['player', 'position'], as_index=False)['apps']
        .sum()
        .rename(columns={'apps': 'total_apps'})
    )

    position_color_rows = []
    for player, player_df in position_totals.groupby('player', sort=False):
        ranked_df = player_df[
            ~player_df['position'].fillna('').str.lower().isin(['bench', 'unknown', ''])
        ].copy()
        ranked_df = ranked_df.sort_values(['total_apps', 'position'], ascending=[False, True]).reset_index(drop=True)

        for idx, row in ranked_df.iterrows():
            color = palette_by_rank[min(idx, len(palette_by_rank) - 1)]
            position_color_rows.append({
                'player': player,
                'position': row['position'],
                'color_hex': color,
                'sort_order': idx + 1,
            })

        bench_df = player_df[player_df['position'].fillna('').str.lower() == 'bench']
        for _, row in bench_df.iterrows():
            position_color_rows.append({
                'player': player,
                'position': row['position'],
                'color_hex': bench_color,
                'sort_order': 100,
            })

        unknown_df = player_df[player_df['position'].fillna('').str.lower().isin(['unknown', ''])]
        for _, row in unknown_df.iterrows():
            position_color_rows.append({
                'player': player,
                'position': row['position'],
                'color_hex': unknown_color,
                'sort_order': 101,
            })

    position_color_map = pd.DataFrame(position_color_rows)
    if position_color_map.empty:
        position_color_map = pd.DataFrame(columns=['player', 'position', 'color_hex', 'sort_order'])

    by_position = by_position.merge(position_color_map, on=['player', 'position'], how='left')
    by_position['color_hex'] = by_position['color_hex'].fillna(unknown_color)
    by_position['sort_order'] = by_position['sort_order'].fillna(101).astype(int)
    by_position['color_key'] = by_position.apply(
        lambda row: f"{row['player']}|||{row['color_value']}",
        axis=1,
    )

    df = pd.concat([
        by_squad,
        by_result,
        by_position[['player', 'season', 'season_sort', 'apps', 'color_mode', 'color_value']]
    ], ignore_index=True)

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
    }

    def build_mode_chart(mode, sort_values, color_values, allowed_values=None):
        mode_df = df[df['color_mode'] == mode].copy()
        if allowed_values:
            mode_df = mode_df[mode_df['color_value'].isin(allowed_values)].copy()
        
        # Filter sort and color values to only those present in the data
        unique_values = sorted(mode_df['color_value'].unique())
        filtered_sort = [v for v in sort_values if v in unique_values]
        color_map = dict(zip(sort_values, color_values))
        filtered_colors = [color_map[v] for v in filtered_sort]
        
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
                    sort=alt.EncodingSortField(field='sum(apps)', op='sum', order='descending'),
                    scale=alt.Scale(domain=filtered_sort, range=filtered_colors),
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

    def build_position_chart():
        position_df = by_position.copy()
        
        # Build global position-to-color mapping (deduplicated across all players)
        position_totals = position_df.groupby('color_value')['apps'].sum().reset_index(name='total_apps')
        # Separate bench from regular positions
        regular_positions = position_totals[~position_totals['color_value'].str.lower().isin(['bench', 'unknown', ''])]
        regular_positions = regular_positions.sort_values('total_apps', ascending=False).reset_index(drop=True)
        
        bench_positions = position_totals[position_totals['color_value'].str.lower() == 'bench']
        unknown_positions = position_totals[position_totals['color_value'].str.lower().isin(['unknown', ''])]
        
        # Assign colors: regular positions by frequency, then bench, then unknown
        pos_to_color = {}
        for idx, row in regular_positions.iterrows():
            color = palette_by_rank[min(idx, len(palette_by_rank) - 1)]
            pos_to_color[row['color_value']] = color
        
        for _, row in bench_positions.iterrows():
            pos_to_color[row['color_value']] = bench_color
        
        for _, row in unknown_positions.iterrows():
            pos_to_color[row['color_value']] = unknown_color
        
        # Build sorted domain and range
        color_domain = list(pos_to_color.keys())
        color_range = [pos_to_color[pos] for pos in color_domain]
        
        # Calculate stack order per position based on total appearances
        stack_order_map = {}
        stacked = 0
        for _, row in regular_positions.iterrows():
            stack_order_map[row['color_value']] = stacked
            stacked += 1
        # Bench always comes last
        for _, row in bench_positions.iterrows():
            stack_order_map[row['color_value']] = 1000
        for _, row in unknown_positions.iterrows():
            stack_order_map[row['color_value']] = 1001
        
        position_df['stack_order'] = position_df['color_value'].map(stack_order_map)
        
        return (
            alt.Chart(position_df)
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
                    scale=alt.Scale(domain=color_domain, range=color_range),
                    legend=alt.Legend(orient='bottom', title=None)
                ),
                order=alt.Order('stack_order:Q'),
                tooltip=[
                    alt.Tooltip('player:N', title='Player'),
                    alt.Tooltip('season:N', title='Season'),
                    alt.Tooltip('color_value:N', title='Position'),
                    alt.Tooltip('sum(apps):Q', title='Appearances')
                ]
            )
            .properties(
                title=alt.Title('Appearances Breakdown', subtitle='Games per season, coloured by position'),
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

    position_chart = build_position_chart()
    position_chart.save(output_dir / f'{output_stem}_position.json')
    charts['Position'] = position_chart

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


def squad_overlap_chart(db, output_file='data/charts/squad_overlap.json'):
    """Generate a diverging stacked bar chart showing player squad overlap by season.
    
    Categorizes players by their squad appearances in each season:
    - Left (2nd XV focus): "2nd XV only", "Both (mostly 2nd XV)"
    - Neutral: "Both (equal)"
    - Right (1st XV focus): "Both (mostly 1st XV)", "1st XV only"
    
    The chart diverges from a center zero line with the neutral category centered on zero.
    """

    # Get unique players per season and their squads with appearance counts
    df = db.con.execute(
        """
        SELECT
            season,
            player,
            squad,
            COUNT(*) AS appearances
        FROM player_appearances
        WHERE season IS NOT NULL AND player IS NOT NULL
        AND season != '2016/17' -- Exclude first season with incomplete data
        GROUP BY season, player, squad
        """
    ).df()

    if df.empty:
        print("No player appearance data found for squad overlap chart.")
        return None

    # For each player-season combo, determine overlap category
    overlap_data = []
    for (season, player), group_df in df.groupby(['season', 'player']):
        squads = group_df['squad'].unique()
        
        if len(squads) == 1:
            # Player only appeared in one squad
            squad = squads[0]
            category = f"{squad} XV only"
        else:
            # Player appeared in both squads
            first_apps = group_df[group_df['squad'] == '1st']['appearances'].sum()
            second_apps = group_df[group_df['squad'] == '2nd']['appearances'].sum()
            total = first_apps + second_apps
            pct_first = first_apps / total if total > 0 else 0.5
            
            if pct_first > 0.65:
                category = "Both (mostly 1st XV)"
            elif pct_first < 0.35:
                category = "Both (mostly 2nd XV)"
            else:
                category = "Both (equal)"
        
        overlap_data.append({
            'season': season,
            'player': player,
            'category': category
        })
    
    overlap_df = pd.DataFrame(overlap_data)
    
    # Count players per category per season
    summary_df = (
        overlap_df
        .groupby(['season', 'category'], as_index=False)
        .size()
        .rename(columns={'size': 'players'})
    )
    
    # Define category order and mapping
    category_map = {
        "1st XV only": 2,
        "Both (mostly 1st XV)": 1,
        "Both (equal)": 0,
        "Both (mostly 2nd XV)": -1,
        "2nd XV only": -2
    }
    
    category_colors = {
        "1st XV only": "#202946",
        "Both (mostly 1st XV)": "#161d33",
        "Both (equal)": "#000000",
        "Both (mostly 2nd XV)": "#465480",
        "2nd XV only": "#7d96e8"
    }
    
    summary_df['type_code'] = summary_df['category'].map(category_map)
    summary_df['category_group'] = summary_df['category'].map(
        lambda value: 'Both squads' if str(value).startswith('Both') else 'One squad'
    )
    
    # Assign render priority: "One squad" segments render underneath (0), "Both squads" segments on top (1)
    summary_df['render_priority'] = summary_df['category_group'].map(
        {'One squad': 0, 'Both squads': 1}
    )
    
    # Compute percentages and diverging positions per season
    def compute_diverging_positions(group):
        # Sort by type_code to ensure correct order
        group = group.set_index('type_code').sort_index()
        
        # Compute percentage within season
        perc = group['players'] / group['players'].sum()
        group['percentage'] = perc
        
        # Center the neutral category (type_code 0) around zero
        # Offset = sum of left side (-2, -1) + half of neutral (0)
        offset = perc.get(-2, 0) + perc.get(-1, 0) + perc.get(0, 0) / 2
        
        # Compute cumulative sum and apply offset to center on zero
        group['percentage_end'] = perc.cumsum() - offset
        group['percentage_start'] = group['percentage_end'] - perc
        
        return group
    
    # Group by season and compute positions
    summary_df = summary_df.groupby('season', group_keys=False).apply(
        compute_diverging_positions
    ).reset_index()

    summary_df['label_position'] = (summary_df['percentage_start'] + summary_df['percentage_end']) / 2
    summary_df['label_color'] = summary_df['category'].map(
        {
            "1st XV only": "white",
            "Both (mostly 1st XV)": "white",
            "Both (equal)": "white",
            "Both (mostly 2nd XV)": "white",
            "2nd XV only": "#111827",
        }
    )
    
    # Sort for consistent rendering
    summary_df = summary_df.sort_values(['season', 'type_code'])

    # Create interactive selection for highlighting (initially highlights "Both squads")
    appearance_selection = alt.selection_multi(
        fields=['category_group'],
        bind='legend',
        name='appearanceSelect'
    )
    
    # Create the diverging stacked bar chart
    bars = alt.Chart(summary_df).mark_bar().encode(
        x=alt.X(
            'percentage_start:Q',
            title='Percentage',
            axis=alt.Axis(format='%', grid=False),
            scale=alt.Scale(domain=[-0.75, 0.75], nice=False)
        ),
        x2='percentage_end:Q',
        y=alt.Y(
            'season:O',
            sort=alt.SortOrder('descending'),
            title='Season'
        ),
        color=alt.Color(
            'category:N',
            scale=alt.Scale(
                domain=list(category_colors.keys()),
                range=list(category_colors.values())
            ),
            legend=None  # Removed Squad Pattern legend
        ),
        stroke=alt.Stroke(
            'category_group:N',
            scale=alt.Scale(
                domain=['One squad', 'Both squads'],
                range=['#00000000', '#000000']
            ),
            legend=alt.Legend(title='Click to highlight', orient='top', titleOrient='left')
        ),
        strokeWidth=alt.condition(appearance_selection, alt.value(2), alt.value(0)),
        opacity=alt.condition(
            appearance_selection,
            alt.value(1.0),
            alt.value(0.35)
        ),
        order=alt.Order('render_priority:Q', sort='ascending'),
        tooltip=[
            alt.Tooltip('season:O', title='Season'),
            alt.Tooltip('category:N', title='Pattern'),
            alt.Tooltip('category_group:N', title='Appearance'),
            alt.Tooltip('players:Q', title='Players'),
            alt.Tooltip('percentage:Q', title='Percentage', format='.1%')
        ]
    ).add_params(
        appearance_selection
    )

    # Zero line
    zero_line = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(
        color='#000000',
        strokeDash=[2, 2],
        opacity=0.3,
        size=1
    ).encode(x='x:Q')

    # Header labels above the chart area
    label_data = pd.DataFrame([
        {'x': -0.5, 'label': '2nd XV', 'color': category_colors['2nd XV only']},
        {'x': -0.2, 'label': 'Mostly 2nd XV', 'color': category_colors['Both (mostly 2nd XV)']},
        {'x': 0.0, 'label': 'Equal', 'color': category_colors['Both (equal)']},
        {'x': 0.2, 'label': 'Mostly 1st XV', 'color': category_colors['Both (mostly 1st XV)']},
        {'x': 0.5, 'label': '1st XV', 'color': category_colors['1st XV only']}
    ])
    
    header_labels = alt.Chart(label_data).mark_text(
        align='center',
        baseline='middle',
        fontSize=10,
        fontWeight='bold',
        opacity=1.0,
    ).encode(
        x=alt.X(
            'x:Q',
            axis=None
        ),
        text='label:N',
        color=alt.Color('color:N', scale=None, legend=None)
    ).properties(width=400, height=22)

    # Data labels on bars
    labels = alt.Chart(summary_df).transform_filter(
        'datum.percentage >= 0.035'
    ).mark_text(
        align='center',
        baseline='middle',
        fontSize=14,
        fontWeight='bold'
    ).encode(
        x=alt.X('label_position:Q'),
        y=alt.Y(
            'season:O',
            sort=alt.SortOrder('descending'),
            title='Season'
        ),
        text=alt.Text('players:Q', format='.0f'),
        color=alt.Color('label_color:N', scale=None, legend=None),
        opacity=alt.condition(
            appearance_selection,
            alt.value(1.0),
            alt.value(0.35)
        )
    )

    # Combine layers, with labels rendered in a header strip above the plot area
    plot_area = alt.layer(zero_line, bars, labels).properties(
        width=400,
        height=alt.Step(40)
    ).resolve_scale(x='shared')

    charter = alt.vconcat(header_labels, plot_area, spacing=2).properties(
        title=alt.Title(
            text='Squad Overlap',
            subtitle=[
                'How much players overlap between the 1st and 2nd XV each season.',
                'Bigger bars at either end indicate lots of players only appearing for one squad.',
                'Bigger bars in the middle indicate more players appearing for both squads.',
            ]
        )
    )

    charter.save(output_file)
    
    # Post-process the JSON to set initial selection to "Both squads"
    import json
    with open(output_file, 'r') as f:
        spec = json.load(f)
    
    # Find and initialize the appearanceSelect parameter
    if 'params' in spec:
        for param in spec['params']:
            if param.get('name') == 'appearanceSelect':
                param['value'] = [{'category_group': 'Both squads'}]
    
    with open(output_file, 'w') as f:
        json.dump(spec, f)
    
    return charter


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


def opposition_profile_team_sheets_chart(db, output_file='data/charts/opposition_profile_team_sheets.json'):
    """Team sheets chart for Opposition Profile page: merged 1st/2nd XV, faceted by season only."""
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
                    SPLIT_PART(P.player, ' ', 1),
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
    
    # Create merged game label: "1st XV v Opposition (home/away)"
    df['game_label_merged'] = df.apply(
        lambda row: f"{row['squad']} XV v {row['opposition']} ({row['home_away']})",
        axis=1
    )

    # Create a unique identifier combining game_id with label for display
    df['game_id_with_label'] = df['game_id'].astype(str) + '|' + df['game_label_merged']
    
    # Use .encode() with explicit types and field names, avoid ambiguous axis titles
    chart = alt.Chart(df).mark_rect().encode(
        x=alt.X(
            'shirt_number:O',  # Use ordinal for shirt numbers
            title='Shirt Number',
            axis=alt.Axis(labelAngle=0, orient='top', ticks=False)
        ),
        y=alt.Y(
            'game_id_with_label:N',
            sort=alt.EncodingSortField(field='date', order='descending'),
            axis=alt.Axis(
                ticks=False, 
                labelAngle=0, 
                labelPadding=10, 
                labelFontSize=11,
                labelExpr="split(datum.value, '|')[1]"  # Extract label part after |
            ),
            title=None
        ),
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
        y=alt.Y('game_id_with_label:N', sort=alt.EncodingSortField(field='date', order='descending')),
        text=alt.Text('player_label:N'),
        color=alt.value('black'),
        opacity=alt.condition(click_player_highlight, alt.value(1.0), alt.value(0.5)),
        strokeWidth=alt.value(0.5),
        detail='game_id:N'
    )

    opposition_team_sheets = (chart + text).properties(
        width=alt.Step(45),
        height=alt.Step(20),
    ).facet(
        row=alt.Row('season:N', title=None, sort=alt.EncodingSortField(field='season', order='descending'), header=alt.Header(labelFontSize=12)),
        spacing=10
    ).resolve_scale(y='independent').resolve_axis(x='shared').configure_view(strokeWidth=0)

    opposition_team_sheets.save(output_file)

    return opposition_team_sheets


def results_chart(db, output_file='data/charts/results.json', facet_by_season=False):
    if _using_canonical_backend(db):
        df = db.con.execute(
            """
            SELECT
                game_id,
                date,
                squad,
                opposition,
                home_away,
                CONCAT_WS(' ', squad, 'XV v ', opposition, CONCAT('(', home_away, ')')) AS game_label,
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
                CONCAT_WS(' ', squad, 'XV v ', opposition, CONCAT('(', home_away, ')')) AS game_label,
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

    squad_highlight = alt.selection_point(fields=['squad'], on='hover', clear='mouseout', empty='all')
        
    df = df.copy()
    # Exclude fixtures without a confirmed result (e.g. future games entered in Google Sheets)
    df = df[df['result'].isin(['W', 'L', 'D'])]
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['game_label'] = df['game_label'].fillna('Unknown').astype(str)
    df['date_label'] = df['date'].dt.strftime('%d %b %Y').fillna('Unknown')
    df['game_axis_key'] = df.apply(
        lambda row: f"{row['date_label']}||{row['game_label']}||{row['game_id']}",
        axis=1,
    )

    df = df.sort_values(['date', 'game_id'], ascending=[False, False]).reset_index(drop=True)
    df['game_sort_key'] = df.index

    base = alt.Chart(df).encode(
        detail='game_id:N',
        color=alt.Color(
            'result:N',
            scale=alt.Scale(domain=['W', 'L'], range=['#146f14', '#981515']),
            legend=alt.Legend(orient='bottom', title='Result', titleOrient='left', direction='horizontal'),
        ),
        opacity=alt.condition(squad_highlight, alt.value(1.0), alt.value(0.2)),
        tooltip=[
            alt.Tooltip('game_label:N', title='Game'),
            alt.Tooltip('date_label:N', title='Date'),
            alt.Tooltip('pf:Q', title='Points For'),
            alt.Tooltip('pa:Q', title='Points Against'),
            alt.Tooltip('margin:Q', title='Margin'),
            alt.Tooltip('result:N', title='Result'),
            alt.Tooltip('competition:N', title='Competition'),
        ]
    )

    bar = base.mark_bar().encode(
        x=alt.X('pf:Q', title='Points', axis=alt.Axis(orient='bottom', offset=5)),
        x2=alt.X2('pa:Q'),
        y=alt.Y(
            'game_axis_key:N',
            title=None,
            sort=alt.EncodingSortField(field='game_sort_key', order='ascending'),
            axis=alt.Axis(
                title=None,
                orient='left',
                labelExpr="split(datum.label, '||')[1]",
                labelLimit=260,
                labelPadding=10,
                ticks=False,
                domain=False,
            ),
        )
    )

    loser = base.mark_text(align='right', dx=-2, dy=0).encode(
        x=alt.X('loser:Q', title=None, axis=alt.Axis(orient='top', offset=5)),
        y=alt.Y('game_axis_key:N', sort=alt.EncodingSortField(field='game_sort_key', order='ascending'), axis=None),
        text='loser:N',
        color=alt.value('black'),
    )
        
    winner = base.mark_text(align='left', dx=2, dy=0).encode(
        x=alt.X('winner:Q', title=None, axis=alt.Axis(orient='top', offset=5)),
        y=alt.Y(
            'game_axis_key:N',
            sort=alt.EncodingSortField(field='game_sort_key', order='ascending'),
            axis=alt.Axis(
                title=None,
                orient='right',
                labelExpr="split(datum.label, '||')[0]",
                labelLimit=120,
                labelPadding=10,
                ticks=False,
                domain=False,
            ),
        ),
        text='winner:N',
        color=alt.value('black'),
    )

    layer = (bar + loser + winner).add_params(squad_highlight).properties(
        width=400,
        height=alt.Step(18),
    )

    if facet_by_season:
        chart = layer.facet(
            row=alt.Row(
                'season:N',
                sort='descending',
                header=alt.Header(title=None, labelOrient='left', labelFontSize=14),
            ),
        ).resolve_scale(
            y='independent'
        ).properties(
            title=alt.Title(
                'Results',
                subtitle=[
                    'Results of all games, highlighting size of winning margin and the result.',
                    'Hover to highlight games for a specific squad.'],
            )
        ).configure_view(strokeWidth=0)
    else:
        chart = layer.properties(
            title=alt.Title(
                'Results',
                subtitle=[
                    'Results of all games, highlighting size of winning margin and the result.',
                    'Hover to highlight games for a specific squad.'],
            )
        ).configure_view(strokeWidth=0)

    chart.save(output_file)

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
    subtitle_text = "Seasonal success for EGRFC and opposition, with the performance gap highlighted.."

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
        "call": ("call", "Call", None),
        "call_type": ("call_type", "Call Type", None),
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
            L.call,
            L.call_type,
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

    for column in ["squad", "season", "game_type", "opposition", "numbers", "area", "call", "call_type", "jumper", "thrower"]:
        df[column] = df[column].fillna("Unknown").astype(str)
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
            title=alt.Title(text=f"{field_label} Breakdown", subtitle="Usage count (bars) and success rate (line)"),
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
            title=alt.Title(text=f"{field_label} Trend", subtitle="Relative usage (bars) and success rate (line)"),
        )

    chart.save(output_file)
    return chart


def lineout_analysis_panel_chart_suite(db, output_dir="data/charts"):
    """Generate the legacy per-dimension lineout breakdown/trend chart family."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    breakdowns = ["numbers", "area", "call", "thrower", "jumper"]
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


def set_piece_h2h_chart_backend(db, set_piece="Lineout", output_file=None):
    """Game-by-game set piece chart using canonical backend data.

    Exports a head-to-head view with mirrored retained vs turnover bars for
    each team, plus per-team success-rate markers and an aggregate summary.
    Opposition filtering is handled by the frontend by trimming the exported
    datasets before embedding the spec.
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
            S.{metric_total}::DOUBLE AS total
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
    df["opposition_club"] = (
        df["opposition"]
        .str.replace(r"\s+(?:I{1,6}|[1-6](?:st|nd|rd|th)?|A|B)(?:\s+XV)?$", "", regex=True)
        .str.strip()
    )
    df.loc[df["opposition_club"] == "", "opposition_club"] = "Unknown"

    def _ordinal_date_label(value):
        d = pd.to_datetime(value)
        day = int(d.day)
        if 11 <= (day % 100) <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{day}{suffix} {d.strftime('%b %Y')}"

    success_df = df.copy()
    success_df["won"] = success_df["won"].clip(lower=0)
    success_df["total"] = success_df[["total", "won"]].max(axis=1)
    success_df["lost"] = (success_df["total"] - success_df["won"]).clip(lower=0)
    success_df["success_rate"] = success_df.apply(
        lambda row: (row["won"] / row["total"]) if row["total"] else 0.0,
        axis=1,
    )
    success_df["game_axis_key"] = success_df.apply(
        lambda row: f"{row['game_id']}__{row['squad']} XV v {row['opposition']} ({row['home_away']})",
        axis=1,
    )
    success_df["game_label"] = success_df["opposition"] + " (" + success_df["home_away"].astype(str) + ")"
    success_df["team_label"] = success_df["team"].map({"EGRFC": "East Grinstead", "Opposition": "Opposition"})
    success_df["fixture_label"] = success_df["game_axis_key"].str.split("__").str[1]
    success_df["date_label"] = success_df["date"].apply(_ordinal_date_label)
    success_df["y_axis"] = success_df["date_label"] + "||" + success_df["fixture_label"]

    segment_rows = []
    for row in success_df.itertuples(index=False):
        segments = [
            ("Retained", row.won if row.team == "EGRFC" else -row.won, row.won),
            ("Turnover", -row.lost if row.team == "EGRFC" else row.lost, row.lost),
        ]
        for outcome, signed_value, count in segments:
            segment_rows.append(
                {
                    "game_id": row.game_id,
                    "date": row.date,
                    "game_axis_key": row.game_axis_key,
                    "game_label": row.game_label,
                    "y_axis": row.y_axis,
                    "squad": row.squad,
                    "season": row.season,
                    "game_type": row.game_type,
                    "opposition": row.opposition,
                    "opposition_club": row.opposition_club,
                    "team": row.team,
                    "team_label": row.team_label,
                    "outcome": outcome,
                    "count": count,
                    "segment_start": 0.0,
                    "segment_end": signed_value,
                }
            )

    segment_df = pd.DataFrame(segment_rows)

    connector_df = (
        success_df.pivot_table(
            index=["game_id", "game_axis_key", "game_label", "date", "y_axis", "squad", "season", "game_type", "opposition", "opposition_club"],
            columns="team",
            values="success_rate",
            aggfunc="mean",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    connector_df["eg_rate"] = connector_df.get("EGRFC", pd.Series(index=connector_df.index, dtype=float)).fillna(0.0)
    connector_df["opp_rate"] = connector_df.get("Opposition", pd.Series(index=connector_df.index, dtype=float)).fillna(0.0)
    connector_df["success_diff"] = connector_df["eg_rate"] - connector_df["opp_rate"]
    connector_df["winner"] = connector_df["success_diff"].apply(
        lambda diff: "EGRFC" if diff > 0 else ("Opposition" if diff < 0 else "Level")
    )
    success_df = success_df.merge(connector_df[["game_id", "eg_rate", "opp_rate"]], on="game_id", how="left")
    success_df["is_lower"] = (
        ((success_df["team"] == "EGRFC") & (success_df["eg_rate"] < success_df["opp_rate"]))
        | ((success_df["team"] == "Opposition") & (success_df["opp_rate"] < success_df["eg_rate"]))
    )

    count_max = max(1.0, float(segment_df["segment_end"].abs().max()) if not segment_df.empty else 1.0)
    count_domain = [-count_max, count_max]

    color_scale = alt.Scale(domain=["EGRFC", "Opposition"], range=["#202946", "#991515"])
    y_sort = alt.EncodingSortField(field="date", order="descending")

    count_axis_top = alt.Axis(format="d", labelExpr="abs(datum.value)", orient="top", labelPadding=15, titlePadding=8)
    count_axis_bottom = alt.Axis(format="d", labelExpr="abs(datum.value)", orient="bottom")

    zone_df = pd.DataFrame(
        {
            "x1": [-count_max, 0.0],
            "x2": [0.0, count_max],
            "x_mid": [-count_max / 2, count_max / 2],
            "label": ["← Opposition wins", "East Grinstead wins →"],
            "fill": ["#991515", "#202946"],
        }
    )

    outcome_opacity_scale = alt.Scale(domain=["Retained", "Turnover"], range=[0.5, 1.0])

    segment_base = alt.Chart(segment_df)

    bg_rects = alt.Chart(zone_df).mark_rect(opacity=0.1).encode(
        x=alt.X("x1:Q", scale=alt.Scale(domain=count_domain)),
        x2="x2:Q",
        color=alt.Color("fill:N", scale=None, legend=None),
    )

    bg_text = alt.Chart(zone_df).mark_text(
        align="center",
        baseline="middle",
        fontSize=12,
        fontWeight="bold",
        fontStyle="italic",
        opacity=0.7,
    ).encode(
        x=alt.X("x_mid:Q", scale=alt.Scale(domain=count_domain)),
        y=alt.value(-15),
        text="label:N",
        color=alt.Color("fill:N", scale=None, legend=None),
    )

    flow_chart = segment_base.mark_bar(size=12).encode(
        y=alt.Y(
            "y_axis:N",
            sort=y_sort,
            title=None,
            axis=alt.Axis(labelLimit=220, ticks=False, domain=False, labelExpr="split(datum.label, '||')[1]", labelPadding=10),
        ),
        yOffset=alt.YOffset("team:N", sort=["Opposition", "EGRFC"]),
        x=alt.X("segment_start:Q", title=f"{set_piece}s", scale=alt.Scale(domain=count_domain), axis=count_axis_top),
        x2="segment_end:Q",
        color=alt.Color("team:N", scale=color_scale, legend=alt.Legend(title="Attacking Team", titleOrient="left",orient="bottom", direction="horizontal", columns=2)),
        opacity=alt.Opacity(
            "outcome:N",
            scale=outcome_opacity_scale,
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("team_label:N", title="Attacking Team"),
            alt.Tooltip("outcome:N", title="Outcome"),
            alt.Tooltip("count:Q", title="Count", format=",.1f"),
        ],
    ).properties(width=320, height=alt.Step(12))

    success_base = alt.Chart(success_df)

    success_connectors = alt.Chart(connector_df).mark_rule(strokeWidth=3, opacity=0.6).encode(
        y=alt.Y(
            "y_axis:N",
            sort=y_sort,
            title=None,
            axis=alt.Axis(orient="right", labelLimit=220, ticks=False, domain=False, labelExpr="split(datum.label, '||')[0]", labelPadding=10),
        ),
        x=alt.X("eg_rate:Q", title="Success Rate", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", orient="top")),
        x2="opp_rate:Q",
        color=alt.Color(
            "winner:N",
            scale=color_scale,
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("eg_rate:Q", title="EGRFC Success", format=".1%"),
            alt.Tooltip("opp_rate:Q", title="Opposition Success", format=".1%"),
        ],
    ).properties(width=200, height=alt.Step(12))

    success_points_higher = success_base.transform_filter("datum.is_lower == false").mark_point(size=170, filled=True, stroke="transparent", strokeWidth=1.4, opacity=1).encode(
        y=alt.Y("y_axis:N", sort=y_sort, title=None, axis=alt.Axis(orient="right")),
        x=alt.X("success_rate:Q", title="Success Rate", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", orient="top")),
        color=alt.Color("team:N", scale=color_scale, legend=alt.Legend(title="Attacking Team", titleOrient="left", orient="bottom", direction="horizontal", columns=2)),
        tooltip=[
            alt.Tooltip("team_label:N", title="Attacking Team"),
            alt.Tooltip("won:Q", title="Won", format=",.0f"),
            alt.Tooltip("lost:Q", title="Lost", format=",.0f"),
            alt.Tooltip("success_rate:Q", title="Success", format=".1%"),
        ],
    ).properties(width=200, height=alt.Step(12))

    success_points_lower = success_base.transform_filter("datum.is_lower == true").mark_point(size=170, filled=False, strokeWidth=2, opacity=1).encode(
        y=alt.Y("y_axis:N", sort=y_sort, title=None, axis=alt.Axis(orient="right")),
        x=alt.X("success_rate:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", orient="top")),
        stroke=alt.Stroke("team:N", scale=color_scale, legend=None),
        tooltip=[
            alt.Tooltip("team_label:N", title="Attacking Team"),
            alt.Tooltip("won:Q", title="Won", format=",.0f"),
            alt.Tooltip("lost:Q", title="Lost", format=",.0f"),
            alt.Tooltip("success_rate:Q", title="Success", format=".1%"),
        ],
    ).properties(width=200, height=alt.Step(12))

    main_chart = alt.hconcat(
        bg_rects + flow_chart,
        success_connectors + success_points_higher + success_points_lower,
        spacing=10,
    ).resolve_scale(y="shared", color="independent").properties(
        title=alt.Title(
            text=f"{set_piece} Head-to-Head", 
            subtitle=[
                f"{set_piece}s won and lost in each game, with success rates and overall performance gap.",
                "Attacking team is indicated by color (EG in blue, Opposition in red).",
                "Darker shaded bars indicate turnovers, lighter shaded bars indicate retained possession.",
            ]
        ),
    )

    aggregate_segment_base = alt.Chart(segment_df).transform_aggregate(
        count="mean(count)",
        groupby=["team", "team_label", "outcome"],
    ).transform_calculate(
        y_axis="'AVERAGE||AVERAGE'",
        segment_start="0",
        segment_end="((datum.team == 'Opposition' && datum.outcome == 'Turnover') || (datum.team == 'EGRFC' && datum.outcome == 'Retained')) ? datum.count : -datum.count",
    )

    aggregate_flow_chart = aggregate_segment_base.mark_bar(size=14).encode(
        y=alt.Y(
            "y_axis:N",
            title=None,
            axis=alt.Axis(labelExpr="split(datum.label, '||')[1]", labelFontWeight="bold", ticks=False, domain=False, labelPadding=10),
        ),
        yOffset=alt.YOffset("team:N", sort=["Opposition", "EGRFC"]),
        x=alt.X("segment_start:Q", title=f"{set_piece}s", scale=alt.Scale(domain=count_domain), axis=count_axis_bottom),
        x2="segment_end:Q",
        color=alt.Color("team:N", scale=color_scale, legend=alt.Legend(title="Attacking Team", titleOrient="left", orient="right", direction="horizontal", columns=2)),
        opacity=alt.Opacity("outcome:N", scale=outcome_opacity_scale, legend=None),
        tooltip=[
            alt.Tooltip("team_label:N", title="Attacking Team"),
            alt.Tooltip("outcome:N", title="Outcome"),
            alt.Tooltip("count:Q", title="Average Count", format=",.1f"),
        ],
    ).properties(width=320, height=alt.Step(16))

    aggregate_success_base = alt.Chart(success_df).transform_aggregate(
        won="mean(won)",
        lost="mean(lost)",
        total="mean(total)",
        groupby=["team", "team_label"],
    ).transform_calculate(
        y_axis="'AVERAGE||AVERAGE'",
        success_rate="datum.total > 0 ? datum.won / datum.total : 0",
        eg_rate="datum.team == 'EGRFC' ? datum.success_rate : null",
        opp_rate="datum.team == 'Opposition' ? datum.success_rate : null",
    ).transform_joinaggregate(
        aggregate_eg_rate="max(eg_rate)",
        aggregate_opp_rate="max(opp_rate)",
    ).transform_calculate(
        is_lower=(
            "((datum.team == 'EGRFC') && (datum.aggregate_eg_rate < datum.aggregate_opp_rate))"
            " || ((datum.team == 'Opposition') && (datum.aggregate_opp_rate < datum.aggregate_eg_rate))"
        ),
    )

    aggregate_connector = alt.Chart(success_df).transform_calculate(
        eg_won="datum.team == 'EGRFC' ? datum.won : 0",
        eg_total="datum.team == 'EGRFC' ? datum.total : 0",
        opp_won="datum.team == 'Opposition' ? datum.won : 0",
        opp_total="datum.team == 'Opposition' ? datum.total : 0",
    ).transform_aggregate(
        eg_won="mean(eg_won)",
        eg_total="mean(eg_total)",
        opp_won="mean(opp_won)",
        opp_total="mean(opp_total)",
    ).transform_calculate(
        eg_rate="datum.eg_total > 0 ? datum.eg_won / datum.eg_total : 0",
        opp_rate="datum.opp_total > 0 ? datum.opp_won / datum.opp_total : 0",
        success_diff="datum.eg_rate - datum.opp_rate",
        winner="datum.success_diff >= 0 ? 'EGRFC' : 'Opposition'",
        y_axis="'AVERAGE||AVERAGE'",
    ).mark_rule(strokeWidth=3, opacity=0.6).encode(
        y=alt.Y(
            "y_axis:N",
            title=None,
            axis=alt.Axis(orient="right", labelExpr="split(datum.label, '||')[0]", labelFontWeight="bold", ticks=False, domain=False, labelPadding=10),
        ),
        x=alt.X("eg_rate:Q", title="Success Rate", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", orient="bottom")),
        x2="opp_rate:Q",
        color=alt.Color("winner:N", legend=None, scale=color_scale),
        tooltip=[
            alt.Tooltip("eg_rate:Q", title="EGRFC Success", format=".1%"),
            alt.Tooltip("opp_rate:Q", title="Opposition Success", format=".1%"),
        ],
    ).properties(width=200, height=alt.Step(16))

    aggregate_success_points_higher = aggregate_success_base.transform_filter("datum.is_lower == false").mark_point(size=180, filled=True, stroke="transparent", opacity=1).encode(
        x=alt.X("success_rate:Q", scale=alt.Scale(domain=[0, 1])),
        y=alt.Y(
            "y_axis:N",
            title=None,
            axis=alt.Axis(labelExpr="split(datum.label, '||')[1]", labelFontWeight="bold", ticks=False, domain=False, labelPadding=10),
        ),
        color=alt.Color("team:N", scale=color_scale, legend=alt.Legend(title="Attacking Team", titleOrient="left", orient="right", direction="horizontal", columns=2)),
        tooltip=[
            alt.Tooltip("team_label:N", title="Attacking Team"),
            alt.Tooltip("won:Q", title="Avg Won", format=",.1f"),
            alt.Tooltip("lost:Q", title="Avg Lost", format=",.1f"),
            alt.Tooltip("success_rate:Q", title="Avg Success", format=".1%"),
        ],
    ).properties(width=200, height=alt.Step(16))

    aggregate_success_points_lower = aggregate_success_base.transform_filter("datum.is_lower == true").mark_point(size=180, filled=False, strokeWidth=2, opacity=1).encode(
        x=alt.X("success_rate:Q", scale=alt.Scale(domain=[0, 1])),
        stroke=alt.Stroke("team:N", scale=color_scale, legend=None),
        y=alt.Y(
            "y_axis:N",
            title=None,
            axis=alt.Axis(labelExpr="split(datum.label, '||')[1]", labelFontWeight="bold", ticks=False, domain=False, labelPadding=10),
        ),
        tooltip=[
            alt.Tooltip("team_label:N", title="Attacking Team"),
            alt.Tooltip("won:Q", title="Avg Won", format=",.1f"),
            alt.Tooltip("lost:Q", title="Avg Lost", format=",.1f"),
            alt.Tooltip("success_rate:Q", title="Avg Success", format=".1%"),
        ],
    ).properties(width=200, height=alt.Step(16))

    aggregate_chart = alt.hconcat(
        bg_rects + bg_text + aggregate_flow_chart,
        aggregate_connector + aggregate_success_points_higher + aggregate_success_points_lower,
        spacing=10,
    ).resolve_scale(y="shared", color="independent", stroke="independent")

    chart = alt.vconcat(main_chart, aggregate_chart, spacing=10)

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
    team = re.sub(r"[^a-z0-9]+", " ", team_name.strip().lower())
    team = re.sub(r"\s+", " ", team).strip()
    if not any(alias in team for alias in ("east grinstead", "e grinstead", "eg men", "egrfc")):
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


def _derive_unexpected_result(row, rank_map):
    """Classify result novelty based on pre-match table ranking expectations."""

    if row["home_team"] == row["away_team"]:
        return "N/A"

    result_simple = row.get("result_simple")
    if result_simple == "To be played":
        return "To be played"
    if result_simple == "Draw":
        return "Draw"
    if result_simple not in {"Home Win", "Away Win"}:
        return "N/A"

    home_rank = rank_map.get(row.get("home_team"))
    away_rank = rank_map.get(row.get("away_team"))
    if home_rank is None or away_rank is None:
        return "Expected"

    if home_rank == away_rank:
        return "Expected"

    higher_ranked_side = "home" if home_rank < away_rank else "away"
    winner_side = "home" if result_simple == "Home Win" else "away"

    if winner_side == higher_ranked_side:
        return "Expected"

    return "Upset (Away Win)" if winner_side == "away" else "Upset (Home Win)"


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
    matrix_df["unexpected_result"] = matrix_df.apply(lambda row: _derive_unexpected_result(row, rank_map), axis=1)
    matrix_df["unexpected_opacity"] = matrix_df["unexpected_result"].map(
        {
            "Expected": 0.25,
            "Upset (Home Win)": 0.75,
            "Upset (Away Win)": 1.0,
            "Draw": 0.75,
            "To be played": 1.,
            "N/A": 1.,
        }
    ).fillna(0.25)

    highlight = alt.selection_point(fields=["home_team"], on="click", clear="dblclick", empty="none", value=None)
    predicate = f"datum.home_team == {highlight.name}['home_team'] || datum.away_team == {highlight.name}['home_team']"
    visible_predicate = f"{predicate} || !isValid({highlight.name}['home_team'])"
    text_color = alt.condition(
        f"({visible_predicate}) && datum.unexpected_result == 'Expected'",
        alt.value("black"),
        alt.value("white"),
    )

    if rank_map:
        team_order = sorted(teams, key=lambda team: (rank_map.get(team, 999), team))
    else:
        team_order = sorted(teams)

    title_text = f"{league} Results"

    base = alt.Chart(matrix_df)
    heatmap = base.mark_rect().encode(
        x=alt.X("away_team:N", title="Away Team", sort=team_order[::-1], axis=alt.Axis(labelAngle=30, orient="top", ticks=False, domain=False, grid=False)),
        y=alt.Y("home_team:N", title="Home Team", sort=team_order, axis=alt.Axis(ticks=False, domain=False, grid=False)),
        color=alt.Color(
            "unexpected_result:N",
            scale=alt.Scale(
                domain=["Expected", "Upset (Home Win)", "Upset (Away Win)", "Draw", "To be played", "N/A"],
                range=["#146f1444", "#991515bb", "#991515", "goldenrod", "white", "black"],
            ),
            title=None,
            legend=alt.Legend(
                orient="bottom",
                direction="horizontal",
                columns=1,
                symbolStrokeColor="black",
                symbolStrokeWidth=1,
                values=["Upset (Away Win)", "Draw", "Expected"],
                labelExpr="datum.value === 'Upset (Away Win)' ? 'Upset' : datum.value",
                offset=16,
                labelLimit=220,
            )
        ),
        opacity=alt.condition(visible_predicate, alt.value(1.0), alt.value(0.1), legend=None),
        tooltip=[
            alt.Tooltip("home_team:N", title="Home"),
            alt.Tooltip("away_team:N", title="Away"),
            alt.Tooltip("home_score_text:N", title="Home Score"),
            alt.Tooltip("away_score_text:N", title="Away Score"),
            alt.Tooltip("result:N", title="Result"),
            alt.Tooltip("unexpected_result:N", title="Unexpectedness"),
            alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
        ],
    )

    text_base = base.encode(
        x=alt.X("away_team:N", sort=team_order[::-1]),
        y=alt.Y("home_team:N", sort=team_order),
        color=text_color
    )   

    text_home_regular = text_base.transform_filter("datum.home_score_text != '' && datum.home_score_text != 'WO'").mark_text(
        size=15,
        xOffset=-10,
        yOffset=5,
        fontWeight="bold",
    ).encode(
        text=alt.Text("home_score_text:N"),
    )

    text_home_wo = text_base.transform_filter("datum.home_score_text == 'WO'").mark_text(
        size=12,
        xOffset=-10,
        yOffset=5,
    ).encode(
        text=alt.Text("home_score_text:N"),
    )

    text_away_regular = text_base.transform_filter("datum.away_score_text != '' && datum.away_score_text != 'WO'").mark_text(
        size=14,
        xOffset=10,
        yOffset=-5,
        fontStyle="italic",
    ).encode(
        text=alt.Text("away_score_text:N"),
    )

    text_away_wo = text_base.transform_filter("datum.away_score_text == 'WO'").mark_text(
        size=12,
        xOffset=10,
        yOffset=-5,
    ).encode(
        text=alt.Text("away_score_text:N"),
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
                "Summary of every league result with teams sorted by current table position.",
                "Diagonal values are total points difference by team.",
                "Upsets (where the lower-ranked team won) are shaded red, darker for away wins."
            ],
        ),
        padding={"left": 20, "top": 20, "right": 40, "bottom": 120},
    ).configure_view(stroke=None).add_params(highlight)

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
            .mark_text(align="left", baseline="middle", dx=6, fontSize=13, color="white")
            .encode(
                x=alt.XDatum(0),
                y=squad_size_y,
                text="Team:N",
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
            .mark_text(align="left", baseline="middle", dx=6, fontSize=13, color="white")
            .encode(
                x=alt.XDatum(0),
                y=continuity_y,
                text="Team:N",
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
            .mark_area(color="#991515", opacity=0.2)
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
