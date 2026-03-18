import sys
from pathlib import Path
import argparse

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from python.backend import BackendConfig, BackendDatabase
from python.data import *
from python.charts import lineout_success_by_zone as plot_lineout_success_by_zone
from python.charts import squad_size_trend_chart, squad_continuity_average_chart
import altair as alt
from python.chart_helpers import *
import pandas as pd


############################
# Player Appearances Chart #
############################

other_names = {
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

def appearance_chart(db, output_file='data/charts/player_appearances.json'):
    if _using_canonical_backend(db):
        historic_seasons = sorted(HISTORIC_PITCHERO_SEASON_IDS.keys())
        season_list_sql = ", ".join([f"'{season}'" for season in historic_seasons])

        df_modern = db.con.execute(
            """
        SELECT
            player,
            squad,
            season,
            game_type,
            position,
            unit,
            is_starter,
            CASE
                WHEN is_starter THEN 'Start'
                WHEN NOT is_starter THEN 'Bench'
                ELSE 'Unknown'
            END AS start,
            COUNT(*) AS games
        FROM player_appearances
        WHERE season NOT IN (""" + season_list_sql + """)
        GROUP BY player, squad, season, game_type, position, unit, is_starter
        ORDER BY games DESC
        """
        ).df()

        df_historic = db.con.execute(
            """
            SELECT
                player,
                squad,
                season,
                NULL AS game_type,
                'Unknown' AS position,
                'Unknown' AS unit,
                NULL::BOOLEAN AS is_starter,
                'Unknown' AS start,
                CASE
                    WHEN pitchero_appearances > 0 THEN pitchero_appearances
                    ELSE scraped_appearances
                END AS games
            FROM v_season_player_appearances_reconciled
            WHERE season IN (""" + season_list_sql + """)
            """
        ).df()

        df = pd.concat([df_modern, df_historic], ignore_index=True)
        df["games"] = pd.to_numeric(df["games"], errors="coerce").fillna(0).astype(int)
        df = df[df["games"] > 0]
    else:
        df = db.con.execute(
            """
        SELECT
            P.player,
            G.squad,
            G.season,
            G.game_type,
            P.position,
            P.unit,
            P.is_starter,
            IF(P.is_starter, 'Start', IF(NOT(P.is_starter), 'Bench', 'Unknown')) AS start,
            COUNT(*) AS games
        FROM player_appearances P
        LEFT JOIN games G USING (game_id)
        GROUP BY P.player, G.squad, G.season, G.game_type, P.position, P.unit, P.is_starter
        ORDER BY games DESC
        """
        ).df()

        df_pitchero_historic = db.con.execute(
            """
        SELECT
            player_join,
            squad,
            season,
            MAX(A) AS games,
            NULL AS game_type,
            NULL AS position,
            NULL AS unit,
            'Unknown' AS start
        FROM pitchero_stats
        WHERE season < '2020/21'
        GROUP BY player_join, squad, season
        """
        ).df()

        df['player_join'] = df['player'].apply(clean_name)

        name_lookup = df.set_index('player_join')['player'].to_dict()
        name_lookup.update(other_names)

        df.drop(columns=['player_join'], inplace=True)

        df_pitchero_historic['player_join'] = df_pitchero_historic['player_join'].map(lambda x: name_lookup[x] if x in name_lookup else x)
        df_pitchero_historic.rename(columns={'player_join': 'player'}, inplace=True)

        df = pd.concat([df, df_pitchero_historic], ignore_index=True)

    # Add text mark showing total games per player, calculated dynamically in the chart spec
    text = alt.Chart(df).mark_text(
        align='left',
        baseline='middle',
        dx=3,
        fontSize=12
    ).encode(
        y=alt.Y('player:N', sort="-x"),
        x=alt.X('sum(games):Q'),
        text=alt.Text('sum(games):Q')
    )

    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("sum(games):Q", axis=alt.Axis(title=None, orient="top")),
        y=alt.Y("player:N", sort="-x", title=None),
        color=alt.Color('squad:N', title='Squad', scale=squad_scale, legend=alt.Legend(orient="right")),
        opacity=alt.Opacity(
            'start:N',
            scale=alt.Scale(
                domain=['Start', 'Bench', 'Unknown'],
                range=[1.0, 0.7, 0.4]
            ),
            legend=None
        ),
        order=alt.Order('squad:Q', sort='ascending'),
        tooltip=[
            alt.Tooltip('player:N', title='Player'),
            alt.Tooltip('squad:N', title='Squad'),
            alt.Tooltip('sum(games):Q', title='Games'),
            alt.Tooltip('start:N', title='Started?'),
        ]
    ).properties(
        width=400,
        height=alt.Step(15),
        title=alt.Title(text='Player Appearances', subtitle='Historic seasons use Pitchero season tables; modern seasons use team sheets. Positions are unknown for historic aggregate rows.')
    ) + text

    chart.save(output_file)

    return chart


def captains_chart(db, output_file='data/charts/captains.json'):
    vc_col = "is_vice_captain" if _using_canonical_backend(db) else "is_vc"
    df = db.con.execute(
        f"""
        SELECT
            P.player,
            G.squad,
            G.season,
            G.game_type,
            P.is_captain,
            COUNT(*) AS games
        FROM player_appearances P
        LEFT JOIN games G USING (game_id)
        WHERE P.is_captain OR P.{vc_col}
        GROUP BY P.player, G.squad, G.season, G.game_type, P.is_captain
        ORDER BY games DESC
        """
    ).df()

    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("sum(games):Q", axis=alt.Axis(title=None, orient="top")),
        y=alt.Y("player:N", sort="-x", title=None),
        color=alt.Color("is_captain:N",
            scale=alt.Scale(domain=[True, False], range=["#202946", "#7d96e8"]),
            legend=alt.Legend(title=None, orient="none", legendX=300, legendY=50, labelExpr="datum.value ? 'Captain' : 'VC'"),
        ),
        order=alt.Order('is_captain:N', sort='descending'),
        row=alt.Row('squad:N', title=None, header=alt.Header(title=None, labelFontSize=36, labelExpr="datum.value + ' XV'"), spacing=50),
        tooltip=['player', 'squad', 'sum(games)', 'is_captain']
    ).resolve_scale(
        y='independent'
    ).properties(
        title=alt.Title("Match Day Captains", subtitle="Captains and Vice-Captains (if named)."),
        width=350,
        height=alt.Step(15)
    )

    chart.save(output_file)

    return chart

def point_scorers_chart(db, output_file='data/charts/point_scorers.json'):
    if _using_canonical_backend(db):
        df = db.con.execute(
            """
            WITH appearance_lookup AS (
                SELECT
                    squad,
                    season,
                    player,
                    effective_appearances AS A
                FROM v_season_player_appearances_reconciled
            )

            SELECT
                S.player,
                S.squad,
                S.season,
                'Try' AS event,
                S.tries AS count,
                S.tries * 5 AS Points,
                COALESCE(A.A, 0) AS A
            FROM season_scorers S
            LEFT JOIN appearance_lookup A USING (squad, season, player)
            WHERE S.tries > 0

            UNION ALL

            SELECT
                S.player,
                S.squad,
                S.season,
                'Con' AS event,
                S.conversions AS count,
                S.conversions * 2 AS Points,
                COALESCE(A.A, 0) AS A
            FROM season_scorers S
            LEFT JOIN appearance_lookup A USING (squad, season, player)
            WHERE S.conversions > 0

            UNION ALL

            SELECT
                S.player,
                S.squad,
                S.season,
                'Pen' AS event,
                S.penalties AS count,
                S.penalties * 3 AS Points,
                COALESCE(A.A, 0) AS A
            FROM season_scorers S
            LEFT JOIN appearance_lookup A USING (squad, season, player)
            WHERE S.penalties > 0

            UNION ALL

            SELECT
                S.player,
                S.squad,
                S.season,
                'DG' AS event,
                S.drop_goals AS count,
                S.drop_goals * 3 AS Points,
                COALESCE(A.A, 0) AS A
            FROM season_scorers S
            LEFT JOIN appearance_lookup A USING (squad, season, player)
            WHERE S.drop_goals > 0
            """
        ).df()
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
            AND event IN ('T', 'Con', 'PK', 'DG')
            """
        ).df()

        df["Points"] = df.apply(lambda x: x["count"] * (5 if x["event"] == "T" else 2 if x["event"] == "Con" else 3 if x["event"] in ["PK", "DG"] else 0), axis=1)
        df["event"] = df["event"].map(lambda x: "Try" if x == "T" else "Pen" if x == "PK" else x)

    score_selection = alt.selection_point(fields=['event'], bind='legend')

    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("sum(Points):Q", axis=alt.Axis(title="Points", orient="top")),
        y=alt.Y("player:N", sort="-x", title=None),
        color=alt.Color(
            'event:N', 
            scale=alt.Scale(
                domain=["Try", "Con", "Pen", "DG"],
                range=["#202946", "#7d96e8", "#d62728", "#9467bd"]
            ),
            legend=alt.Legend(title='Click to filter', orient="none", legendX=300, legendY=100)
        ),
        order=alt.Order('event_sort:Q', sort='ascending'),
        tooltip=[
            alt.Tooltip('player:N', title='Player'),
            alt.Tooltip('event:N', title='Type'),
            alt.Tooltip('sum(count):Q', title='Count'),
            alt.Tooltip('sum(Points):Q', title='Points'),
            alt.Tooltip('sum(A):Q', title='Games'),
        ]   
    ).add_params(score_selection).transform_filter(score_selection).transform_calculate(
        event_sort = "datum.event == 'Try' ? 1 : datum.event == 'Con' ? 2 : datum.event == 'Pen' ? 3 : datum.event == 'DG' ? 4 : 5"
    ).properties(
        width=400,
        height=alt.Step(15),
        title=alt.Title(text='Point Scorers', subtitle='Based on available Pitchero data. Click on legend to filter by score type.')
    )

    chart.save(output_file)

    return chart

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
                REPLACE(CONCAT_WS(' ', G.game_id, CONCAT('(', G.home_away, ')')), '_', ' ') AS game_label,
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
                REPLACE(CONCAT_WS(' ', G.game_id, CONCAT('(', G.home_away, ')')), '_', ' ') AS game_label,
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
    ).resolve_scale(y='independent', x='independent').properties(
        title=alt.Title("Team Sheets", subtitle="Player appearances by shirt number. Click on a player to highlight their appearances.")
    ).configure_view(strokeWidth=0)

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

    return plot_lineout_success_by_zone(df=df, file=output_file)

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

# Update the main() function
def main(refresh_pitchero=False, backend_mode="canonical", backend_db_path="data/egrfc_backend.duckdb"):
    """Main update function using optimized data"""

    if backend_mode != "canonical":
        raise ValueError("Only canonical backend mode is supported.")

    try:
        db = BackendDatabase(config=BackendConfig(db_path=backend_db_path))
    except RuntimeError as exc:
        default_path = "data/egrfc_backend.duckdb"
        fallback_path = "data/egrfc_backend_alt.duckdb"
        if backend_db_path == default_path and "locked by another process" in str(exc):
            print(f"Default backend DB is locked. Falling back to {fallback_path}...")
            db = BackendDatabase(config=BackendConfig(db_path=fallback_path))
        else:
            raise
    db.build(refresh_pitchero=refresh_pitchero, export=True)
    
    # Load league data
    print("Loading league data...")
    # db.load_league_data(season="2024-2025", league="Counties 1 Surrey/Sussex")
    
    print("Generating charts...")
    
    # Existing charts
    appearance_chart(db)
    captains_chart(db)
    point_scorers_chart(db)
    cards_chart(db)
    team_sheets_chart(db)
    results_chart(db)

    set_piece_df = set_piece_data(db)
    set_piece_chart(set_piece_df, s="Scrum")
    set_piece_chart(set_piece_df, s="Lineout")
    lineout_success_by_zone_chart(db)
    squad_size_trend_chart(db)
    squad_continuity_average_chart(db)

    # New league charts
    # league_results_chart(db)
    # league_squad_analysis_chart(db)

    print("All charts generated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update EGRFC stats and regenerate chart outputs")
    parser.add_argument(
        "--refresh-pitchero",
        action="store_true",
        help="Force refresh of Pitchero stats from the website (otherwise uses local cache if present)",
    )
    parser.add_argument(
        "--backend-mode",
        choices=["canonical"],
        default="canonical",
        help="Data backend to use when building chart outputs",
    )
    parser.add_argument(
        "--db-path",
        default="data/egrfc_backend.duckdb",
        help="DuckDB path for canonical backend mode (falls back to data/egrfc_backend_alt.duckdb if default is locked)",
    )

    args = parser.parse_args()
    main(
        refresh_pitchero=args.refresh_pitchero,
        backend_mode=args.backend_mode,
        backend_db_path=args.db_path,
    )