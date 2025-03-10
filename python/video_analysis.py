import altair as alt
import pandas as pd
from math import sqrt

from charts import alt_theme, hack_params_css

alt.themes.register("my_custom_theme", alt_theme)
alt.themes.enable("my_custom_theme")

###########################
### VIDEO ANALYSIS CHARTS
###########################

game_selection = alt.selection_point(fields=["Game"], on="click")

def territory_chart(df):
    game_order = df.sort_values(by="Date", ascending=False)["Game"].unique().tolist()
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
            width=400,
            height=alt.Step(30)
        )
    )

    # Add text overlay to bars showing the percentage 
    text = (
        chart
        .mark_text(align="center", baseline="middle", fontSize=16, fontWeight="bold")
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
    game_order = df.sort_values(by="Date", ascending=False)["Game"].unique().tolist()
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
            width=275,
            height=alt.Step(30)
        )
    )

    if not(axis):
        chart.encoding.y.axis = None

    text = (
        chart
        .mark_text(align="center", baseline="middle", fontSize=18, fontWeight="bold", color="white")
        .encode(
            x=alt.X("text_pos:Q", axis=None),
            text=alt.Text("percentage:Q", format=".0%"),
            color=alt.value("white")
        )
    )
    return (chart + text).resolve_scale(color="independent")

def playmaker_chart(df, axis=True):
    game_order = df.sort_values(by="Date", ascending=False)["Game"].unique().tolist()
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
            width=325,
            height=alt.Step(30)
        )
    )

    if not(axis):
        chart.encoding.y.axis = None

    # Add text overlay to bars showing the percentage
    text = (
        chart
        .mark_text(align="center", baseline="middle", fontSize=18, fontWeight="bold")
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
    game_order = df.sort_values(by="Date", ascending=False)["Game"].unique().tolist()
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

    metric_selection = alt.selection_point(fields=["Metric"], bind="legend")

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
            width=225,
            height=alt.Step(30)
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
        .mark_text(align="center", baseline="middle", fontSize=16)
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
    game_order = df.sort_values(by="Date", ascending=False)["Game"].unique().tolist()
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
            width=240,
            height=alt.Step(30)
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
    game_order = df.sort_values(by="Date", ascending=False)["Game"].unique().tolist()

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
            height=alt.Step(30)
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
        .properties(width=175, height=alt.Step(30))
    )
    pa_text = pa.mark_text(dx=-20, dy=3, fontSize=16).encode(text="PA:Q", fill=alt.value("#981515"))
    pf_text = pf.mark_text(dx=20, dy=3, fontSize=16).encode(text="PF:Q", fill=alt.value("#202947"))

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
    
    game_order = df.sort_values(by="Date", ascending=False)["Game"].unique().tolist()

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
            width=275,
            height=alt.Step(30)
        )
    )

    if not(axis):
        chart.encoding.y.axis = None

    text = (
        chart
        .mark_text(align="left", baseline="middle", fontSize=16)
        .encode(
            x=alt.X("text_pos:Q"),
            text=alt.Text("Value:Q"),
            color=alt.value("white")
        )
    )

    return (chart + text).resolve_scale(color="independent").properties(
        title=alt.Title(
            text="Gain Line Success",
            subtitle="Starter plays that broke the gain line",
            anchor="middle",
            fontSize=36
        )
    )

def game_stats_charts(df, file=None):

    if df is None:
        df = game_stats()

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
            fontSize=48,
            subtitle=["Performance metrics from video analysis on Veo / live streams.", "Click on any chart to highlight a single game throughout all other charts."],
            color="#202946"
        )
    )
    if file:
        chart.save(file, embed_options={'renderer':'svg', 'actions': {'export': True, 'source':False, 'editor':True, 'compiled':False} })
        hack_params_css(file, params=False)

    return chart
