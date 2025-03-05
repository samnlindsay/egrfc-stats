from data_prep import *
import altair as alt
from charts import *

# Total tries per player (current season)
def totals(df):
    totals = (
        df.groupby("Player")
        .agg({"T": "sum", "TotalGames": "sum"})
        .rename(columns={"TotalGames": "Games", "T": "Tries"})
        .reset_index()
        .astype({"Tries": "int", "Games": "int"})
    )

    games_by_squad = (
        df.groupby(["Player", "Squad"])
        .agg({"TotalGames": "sum"})
        .reset_index()
        .pivot(index="Player", columns="Squad", values="TotalGames")
        .reset_index()
        .rename(columns={"1st": "Games1", "2nd": "Games2"})
        .fillna(0)
        .astype({"Games1": "int", "Games2": "int"})
    )

    totals = totals.merge(games_by_squad, on="Player").fillna(0)

    return totals

def get_positions(df, by=None):

    df["Position"] = df.apply(lambda x: d_specific.get(x["Number"], "Bench"), axis=1)

    df = (
        df.groupby(["Player", "Position", by] if by else ["Player", "Position"])
        .agg({"PF": "count"})
        .reset_index()
        .sort_values(["Player", "PF"], ascending=[True, False])
        .rename(columns={"PF": "Games"})
    )
    df = df[df['Games'] >= 1]

    # Total starts per player (not incl. bench)
    starts = df[df["Position"] != "Bench"].groupby("Player").agg({"Games": "sum"}).reset_index()
    starts = starts.rename(columns={"Games": "Starts"})
    df = df.merge(starts, on="Player", how="left").fillna(0)

    return df

def debuts(df, df_agg):

    df = df.sort_values(["Player", "Squad", "GameSort"])

    first_season = (
        df_agg.groupby("Player")
        .agg({"Season": "min"})
        .reset_index()
        .rename(columns={"Season": "FirstSeason"})
    )

    debut_season1 = (
        df_agg[df_agg["Squad"]=="1st"]
        .groupby("Player")
        .agg({"Season": "min"})
        .reset_index()
        .rename(columns={"Season": "DebutSeason"})
    )

    debut_game1 = (
        df[df["Squad"]=="1st"]
        .groupby(["Player", "Season"])
        .agg({"GameID": "first"})
        .reset_index()
        .rename(columns={"Season": "DebutSeason"})
    )

    debuts = (
        first_season
        .merge(debut_season1, on="Player", how="left")
        .merge(debut_game1, on=["Player","DebutSeason"], how="left")
        .fillna("-")
    )

    return debuts   

def players_table_data(df=None, df_agg=None):

    if df is None:
        df = players(team_sheets())
    if df_agg is None:
        df_agg = players_agg(df)
    
    positions = get_positions(df)
    positions = positions[positions["Games"] >= 0.2 * positions["Starts"]]
    positions = positions[positions["Position"] != "Bench"]
    positions = positions.groupby('Player').agg({'Position': lambda x: ' / '.join(x)}).reset_index()

    current_season = df_agg["Season"].max()

    df_current = totals(df_agg[df_agg["Season"] == current_season])
    df_total = totals(df_agg).rename(columns={
        "Tries": "TotalTries", 
        "Games": "TotalGames", 
        "Games1": "TotalGames1", 
        "Games2": "TotalGames2"
    })

    debuts_df = debuts(df, df_agg)

    df = (
        df_total
        .merge(df_current, on="Player", how="left").fillna(0)
        .merge(positions, on="Player", how="left")
        .merge(debuts_df, on="Player", how="left")
        .astype({"Tries": "int", "Games": "int", "Games1": "int", "Games2": "int"})
    )

    df.to_json("data/player_table.json", orient="records", indent=2)

    return df

def add_player_filter(file):
    
    # Add the following to the HTML file to allow player selection
    filter = """    // Listen for messages from parent page
        window.addEventListener("message", (event) => {
            view.signal("selectedPlayer", event.data.selectedPlayer).run();
        });
        """

    # Read the file content using BeautifulSoup
    with open(file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    script = soup.find_all("script")[-1].string

    script = script.replace(
        'vegaEmbed("#vis", spec, embedOpt)', 
        'vegaEmbed("#vis", spec, embedOpt).then(result => { view = result.view; })'
    )
    soup.find_all("script")[-1].string = script + filter

    # Save the updated file
    with open(file, 'w', encoding='utf-8') as f:
        f.write(str(soup))

def season_squad_chart(df, player=None):
    # Games by season/squad
    base = (
        alt.Chart(df)
        .transform_filter("datum.Player == selectedPlayer || selectedPlayer == null")
        .encode(
            y=alt.Y('Season:N', title=None, axis=alt.Axis(ticks=False, labelPadding=10), sort="descending"),
            x=alt.X('sum(TotalGames):Q', title=None, axis=None, stack="zero"),
            tooltip=['Player', 'Season', 'sum(TotalGames)'],
            order=alt.Order('Squad:N', sort='ascending'),
            text='sum(TotalGames):Q'
        )
    )
    bar = base.mark_bar(stroke="black").encode(
        color=alt.Color('Squad:N', scale=squad_scale, legend=alt.Legend(title="Squad", orient="right")),
    )
    text = base.mark_text(dx=-15, color='white', fontSize=18).encode(detail='Squad:N')

    chart = (bar + text).properties(
        title=alt.Title(
            text="Games per Season", 
            subtitle="Since Pitchero records began in 2017",
            fontSize=36, 
            orient="top",
        )
    )

    if player:
        chart = chart.transform_filter(f"datum.Player == '{player}'")

    return chart

def squad_pie(df, player=None):
    base = (
        alt.Chart(df)
        .encode(
            theta=alt.Theta("sum(TotalGames)").stack(True),
            order=alt.Order("Squad:N", sort="ascending"),
            color=alt.Color(
                "Squad:N", 
                scale=squad_scale, 
                legend=None,
            ),
            tooltip=["Squad", "sum(TotalGames)"],
        )
        .add_params(alt.param(value=None, name="selectedPlayer"))
        .transform_filter("datum.Player == selectedPlayer || selectedPlayer == null")
        .transform_calculate(label="split(datum.Squad + ' XV', ' ')")
    )

    pie = base.mark_arc(outerRadius=120, innerRadius=50, stroke="black")
    text1 = base.mark_text(radius=85, size=36, font="PT Sans Narrow").encode(
        theta=alt.Theta("sum(TotalGames)", stack=True),
        text=alt.Text("sum(TotalGames)"), 
        detail="Squad:N",
        color=alt.value("white")
    )
    text2 = base.mark_text(radius=150, size=28, font="PT Sans Narrow").encode(
        theta=alt.Theta("sum(TotalGames)", stack=True),
        text=alt.Text("label:N"),
        detail="Squad:N",
    )

    chart = (pie + text1 + text2).properties(
        title=alt.Title(
            text="Squad",  
            orient="none",
            anchor="middle",
            dx=100,
            dy=110,
            fontSize=32
        )
    )

    if player:
        chart = chart.transform_filter(f"datum.Player == '{player}'")

    return chart

position_sort = ["Prop", "Hooker", "Second Row", "Flanker", "Number 8", "Scrum Half", "Fly Half", "Centre", "Wing", "Full Back", "Bench"]

def position_pie(df, player=None, position_field="Position_specific"):

    base = (
        alt.Chart(df)
        .encode(
            theta=alt.Theta("count()"),
            order=alt.Order("count()", sort="ascending"),
            color=alt.Color(
                "Position_specific:N",
                scale=alt.Scale(
                    domain=position_sort,
                    range=[
                        "#d71621", "#f23623", "#fc7335", "#fea045", "#fec460",
                        "#b0d0a0", "#80d080", "#45b4c2", "#258bbb", "#225aa5",
                        "darkgray"
                    ]
                ),
                legend=None
            ),
            detail=f"{position_field}:N"
        )
        .add_params(alt.param(value=None, name="selectedPlayer"))
        .transform_filter("datum.Player == selectedPlayer || selectedPlayer == null")
        .transform_calculate(Number="datum.Number <= 15 ? datum.Number : ''")
    )

    if position_field == "Number":
        base = base.transform_calculate(Position_label="split(datum.Position_specific + ' ' + datum.Number, ' ')")
    else:
        base = base.transform_calculate(Position_label="split(datum.Position_specific, ' ')")

    pie = base.mark_arc(outerRadius=120, innerRadius=50, stroke="black")

    text1 = base.mark_text(radius=85, size=36, font="PT Sans Narrow").encode(
        theta=alt.Theta("count()", stack=True, sort="descending"),
        text=alt.Text("count()"), 
        detail=f"{position_field}:N",
        color=alt.value("white")
    )

    text2 = base.mark_text(radius=155, size=24, font="PT Sans Narrow", baseline="line-bottom").encode(
        theta=alt.Theta("count()", stack=True),
        text=alt.Text("Position_label:N"),
        detail="Position_specific:N",
    )

    chart = (pie + text1 + text2).properties(
        title=alt.Title(
            text="Position",  
            orient="none",
            anchor="middle",
            dx=100,
            dy=110,
            fontSize=32
        )
    )

    if player:
        chart = chart.transform_filter(f"datum.Player == '{player}'")

    return chart

def results_pie(df, player=None):

    base = (
        alt.Chart(df)
        .encode(
            theta=alt.Theta("count()"),
            color=alt.Color(
                "Result:N",
                scale=alt.Scale(
                    domain=["W", "D", "L"],
                    range=["#146f14", "#fec460", "#991515"]
                ),
                legend=None
            )
        )
        .add_params(alt.param(value=None, name="selectedPlayer"))
        .transform_filter("datum.Player == selectedPlayer || selectedPlayer == null")
    )

    pie = base.mark_arc(outerRadius=120, innerRadius=50, stroke="black")

    text1 = base.mark_text(radius=85, size=36, font="PT Sans Narrow").encode(
        theta=alt.Theta("count()", stack=True),
        text=alt.Text("count()"), 
        detail="Result:N",
        color=alt.value("white")
    )

    text2 = base.mark_text(radius=140, size=28, font="PT Sans Narrow", fontWeight="bold").encode(
        theta=alt.Theta("count()", stack=True),
        text=alt.Text("Result:N"),
        detail="Result:N",
    )

    chart = (pie + text1 + text2).properties(
        title=alt.Title(
            text="Results",  
            orient="none",
            anchor="middle",
            dx=100,
            dy=110,
            fontSize=32
        )
    )

    if player:
        chart = chart.transform_filter(f"datum.Player == '{player}'")

    return chart

def player_profile_charts(player=None, df=None, df_agg=None, position_field="Position_specific"):

    if df is None:
        df = players(team_sheets())
    if df_agg is None:
        df_agg = players_agg(df)

    chart = (
        alt.vconcat(
            alt.hconcat(
                squad_pie(df_agg, player).properties(height=250), 
                position_pie(df, player, position_field=position_field).properties(height=250),
                results_pie(df, player).properties(height=250),
            ).resolve_scale(color='independent'),
            season_squad_chart(df_agg, player).properties(height=alt.Step(30), width=600),
            spacing=30
        )    
        .resolve_scale(color='independent')
        .configure_view(stroke=None)
        .properties(background="transparent")
    )

    chart.save('Charts/player_appearances.html')

    hack_params_css('Charts/player_appearances.html', params=False)

    add_player_filter('Charts/player_appearances.html')

    return chart