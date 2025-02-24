import json
import altair as alt
import pandas as pd
from data_prep import *
from copy import deepcopy
import os
from bs4 import BeautifulSoup


def hack_params_css(file, overlay=False):

  # Define the CSS to be added
  css_to_add = f'''

      body {{
          margin: 0;
      }}
  
      /* Default size for larger screens */
      .vega-embed {{
          width: 100%;
          height: 100%;
          transform-origin: top left;
      }}

      /* Scale for tablet devices */
      @media (max-width: 768px) {{
          .vega-embed {{
              transform: scale(0.75);
              width: 100%;
              height: 100%;
          }}
      }}

      /* Scale for mobile devices */
      @media (max-width: 480px) {{
          .vega-embed {{
              transform: scale(0.5);
              width: 100%;
              height: 100%;
          }}
      }}

      .vega-bindings {{
        border: 2px solid black;
        background-color: #e5e4e7;
        color: #202946;
        width: fit-content;
        height: fit-content;
        position: {"static" if not overlay else "fixed; top: 1rem; right: 1rem"};
        display: block;
        justify-content: center;
        gap: 20px;
        padding: 10px;
        font-size: large;
      }}
      .chart-wrapper {{
          display: grid;
          grid-template-columns: 1fr 1fr; /* Chart takes 3x space, form takes 1x */
      }}

      .vega-bind {{
        font-family: 'Lato', sans-serif;
        padding: 10px;
        padding-top: 5px;
        width: min-content;
      }}
            
      .vega-bind-name {{
        font-family: 'Lato', sans-serif;
        font-weight: bold;
        font-size: larger;
        color: #202946; 
      }}

      .vega-bind-radio input {{
        width: 1rem;
        height: 1rem;
      }}

      .vega-bind-radio label {{
        font-family: 'Lato', sans-serif;
        display: flex;
        padding: 0.1rem;
        cursor: pointer;
        transition: all 0.3s;
        font-size: medium;
      }}

      .vega-bind-radio input:checked+label {{
        background-color: #202946;
        color: #e5e4e7;
    }}
  '''

  # Read the file content using BeautifulSoup
  with open(file, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

  # Find the <style> tag or create it if it doesn't exist
  style_tag = soup.find('style')
  if not style_tag:
      style_tag = soup.new_tag('style')
      soup.head.append(style_tag)

  # Append the new CSS to the <style> tag
  style_tag.append(css_to_add)

  # Add google fonts
  soup.head.append(soup.new_tag("link", rel="stylesheet", href="https://fonts.googleapis.com/css?family=PT+Sans+Narrow:400,700"))
  soup.head.append(soup.new_tag("link", rel="stylesheet", href="https://fonts.googleapis.com/css?family=Lato:100,300,400,700,900"))          
  
  # Write the modified HTML back to the file
  with open(file, 'w', encoding='utf-8') as f:
      f.write(str(soup))
  print(f"Updated {file}")


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
                "subtitleFontSize": 13,
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

def plot_starts_by_position(df=None, min=0, file=None):

    # legend selection filter
    legend = alt.selection_point(fields=["GameType"], bind="legend", on="click")

    season_selection = alt.param(
        bind=alt.binding_radio(options=[*seasons, "All"], name="Season"), 
        value="All" 
    )
    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Total"], name="Squad"),
        value="Total"
    )

    min_selection = alt.param(
        bind=alt.binding_range(name="Minimum Starts", min=1, max=20, step=1),
        value=min
    )

    # altair bar chart of starts by position
    chart = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/players.csv',"format":{'type':"csv"}})
        .mark_bar()
        .encode(
            x=alt.X('count()', axis=alt.Axis(title=None, orient="top")),
            y=alt.Y('Player:N', sort='-x', title=None),
            facet=alt.Facet(
                "Position:O", 
                columns=4,  
                header=alt.Header(title=None, labelFontSize=36, labelOrient="top"), 
                spacing=20, 
                sort=position_order,
                align="each"
            ),
            tooltip=[
                "Player:N", 
                "Position:N", 
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
        .resolve_scale(y="independent", x="independent")
        .transform_filter("datum.Number <= 15")
        .properties(width=150, height=alt.Step(14), title=alt.Title(text="Starts (by position)", subtitle="Not including bench appearances."))
        .add_params(legend, season_selection, squad_selection, min_selection)
        .transform_joinaggregate(TotalGames="count()", groupby=["Player", "Position"])
        .transform_filter(f"datum.TotalGames >= {min_selection.name}")
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Total'")
        .transform_filter(legend)
    )
    if file:
        chart.save(file)
        hack_params_css(file)

    return chart  


def plot_games_by_player(min=5, df=None, file=None):

    c = alt.Color(
        f"GameType:N",
        scale=game_type_scale,
        legend=alt.Legend(
            title=None, orient="bottom", direction="horizontal", titleOrient="left"
        )
    )
    o = alt.Order("GameType:N", sort="descending")

    # legend selection filter
    legend = alt.selection_point(fields=["GameType"], bind="legend", on="click")

    season_selection = alt.param(
        bind=alt.binding_radio(options=[*seasons, "Total"], name="Season"), 
        value="2024/25" 
    )
    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Total"], name="Squad"),
        value="Total"
    )

    chart = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/players.csv',"format":{'type':"csv"}})
        .mark_bar(strokeWidth=2)
        .encode(
            x=alt.X("count()", axis=alt.Axis(title=None, orient="top")),
            y=alt.Y("Player:N", sort="-x", title=None),
            color=c,
            order=o,
            opacity=alt.Opacity(
                "PositionType:N",
                scale=alt.Scale(domain=["Start", "Bench"], range=[1.0, 0.6]), 
                legend=None
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
        .add_params(legend, season_selection, squad_selection)
        .resolve_scale(y="independent")
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'Total'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Total'")
        .transform_joinaggregate(TotalGames="count()", groupby=["Player"])
        .transform_filter(f"datum.TotalGames >= {min}")
        .properties(
            title=alt.Title(
                text=f"Appearances",
                subtitle=f"Minimum {min} appearances. Lighter shaded bars represent bench appearances.",
                subtitleFontStyle="italic"  
            ),
            width=400,
            height=alt.Step(15)
        )
    )
    if file:
        chart.save(file)
        hack_params_css(file)

    return chart

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
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/lineouts.csv',"format":{'type':"csv"}})
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
        chart.save(file)
        hack_params_css(file)
    return chart



def points_scorers_chart(df=None, file=None):

    selection = alt.selection_point(fields=['Type'], bind='legend')

    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Total"], name="Squad"),
        value="Total"
    )

    season_selection = alt.param(
        bind=alt.binding_radio(options=[*seasons, "All"], name="Season"), 
        value="All" 
    )

    chart = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/players_agg.csv',"format":{'type':"csv"}})
        .mark_bar()
        .transform_filter("datum.Points > 0")
        .transform_fold(["Tries", "Pens", "Cons"], as_=["Type", "Points"])
        .transform_joinaggregate(
            sortfield="sum(Points)",    
            T="sum(T)",
            PK="sum(PK)",
            Con="sum(Con)",
            groupby=["Player", "Season", "Type"]
        )
        .transform_filter("datum.sortfield > 0")
        .transform_calculate(label="if(datum.T>0, datum.T + 'T ','') + if(datum.PK>0, datum.PK + 'P ', '') + if(datum.Con>0, datum.Con + 'C ', '')")
        .transform_joinaggregate(
            label="max(label)",
            totalpoints="sum(Points)",    
            groupby=["Player", "Season"]
        )
        .encode(
            x=alt.X("sum(Points):Q", axis=alt.Axis(orient="top", title="Points")),
            y=alt.Y(
                "Player:N", 
                sort="-x",
                title=None
            ),
            order=alt.Order("Points:Q", sort="descending"),
            tooltip=[
                alt.Tooltip("Player:N", title=" "), 
                # alt.Tooltip("A:Q", title="Games"),
                alt.Tooltip("label:N", title="Scores"),
                alt.Tooltip("totalpoints:Q", title="Total Points"),
                alt.Tooltip("Type:N", title=None),
                alt.Tooltip("Points:Q", title="Points"),
                # "T:Q", "PK:Q", "Con:Q"
            ],
        )
        .properties(width=400, height=alt.Step(16))
    )
    
    text = (
        chart    
        .mark_text(align="left", dx=5, color="black")
        .encode(
            y=alt.Y(
                "Player:N", 
                sort="-x",
                title=None
            ),
            x=alt.X("totalpoints:Q"),
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
    )


    chart = (
        (chart + text).resolve_scale(x="shared")
        .facet(column=alt.Column("Season:O", title=None, header=alt.Header(labelFontSize=36)), spacing=20)
        .add_params(selection, season_selection, squad_selection)
        .transform_filter(selection)
        .transform_filter("datum.Points > 0")
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Total'")
        .properties(title=alt.Title(text="Points Scorers", subtitle="According to Pitchero data"))
        .resolve_scale(y="independent", x="independent")
    )

    if file:
        chart.save(file)
        hack_params_css(file, overlay=True)

    return chart

def card_chart(df=None, file=None):

    season_selection = alt.param(
        bind=alt.binding_radio(options=[*seasons, "All"], name="Season"), 
        value="All" 
    )

    chart = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/players_agg.csv',"format":{'type':"csv"}})
        .transform_calculate(Cards="datum.YC + datum.RC")
        .transform_filter("datum.YC > 0 || datum.RC > 0")
        .add_params(season_selection)
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'All'")
        .transform_fold(["YC", "RC"], as_=["key", "value"])
        .transform_aggregate(
            A="sum(A)", 
            # YC="sum(YC)",
            # RC="sum(RC)",
            value="sum(value)",
            groupby=["Player", "Season", "key"])
        .mark_bar(stroke="black", strokeOpacity=0.2).encode(
            y=alt.Y("Player:N", title=None, sort="-x"),
            x=alt.X("value:Q", title=None, axis=alt.Axis(values=[0,1,2,3,4,5], format="d", orient="top")),        
            color=alt.Color(
                "key:N", 
                title=None, 
                legend=alt.Legend(orient="bottom")
            ).scale(domain=["YC", "RC"], range=["#e6c719", "#981515"]),
            column=alt.Column("Season:N", title=None, header=alt.Header(labelFontSize=36), spacing=10),
            tooltip=[
                "Player:N", 
                alt.Tooltip("A:Q", title="Appearances"),
                alt.Tooltip("key:N", title="Card Type"),
                alt.Tooltip("value:Q", title="Cards")
            ],
        )
        .resolve_scale(y="independent")
        .properties(
            title=alt.Title(
                text="Cards",
                fontSize=48, 
                subtitle=[
                    "According to Pitchero data (both 1st and 2nd XV)", 
                    "2 YC leading to a RC in a game is shown as 1 YC + 1 RC (2 cards total)"
                ]
            ),
            width=120,
        )
    )
    if file:
        chart.save(file)
        hack_params_css(file)

    return chart

def captains_chart(df=None, file=None):

    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Both"], name="Squad"),
        value="Both"
    )

    season_selection = alt.param(
        bind=alt.binding_radio(options=[*seasons, "Total"], name="Season"), 
        value="Total" 
    )

    chart = (
       alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/game.csv',"format":{'type':"csv"}})
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
            row=alt.Row("Squad:N", header=alt.Header(title=None, labelFontSize=36, labelExpr="datum.value + ' XV'"), spacing=20),
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
        .add_params(season_selection, squad_selection)
        .transform_filter(f"datum.Season == {season_selection.name} | {season_selection.name} == 'Total'")
        .transform_filter(f"datum.Squad == {squad_selection.name} | {squad_selection.name} == 'Both'")
        .properties(
            title=alt.Title("Match Day Captains", subtitle="Captains and Vice-Captains (if named). Friendly games are shaded lighter."),
            width=400,
            height=alt.Step(20)
        )
        .resolve_scale(x="shared", y="independent", opacity="shared")
    )
    if file:
        chart.save(file)
        hack_params_css(file)

    return chart

def results_chart(df=None, file=None):

    selection = alt.selection_point(fields=['Result'], bind='legend')

    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd", "Both"], name="Squad"),
        value="Both"
    )
    season_selection = alt.param(
        bind=alt.binding_radio(options=[*seasons, "All"], name="Season"),
        value="All"
    )

    base = (
        alt.Chart(df if df is not None else {"name": "df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/game.csv',"format":{'type':"csv"}})
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
        chart.save(file)
        hack_params_css(file)
    
    return chart

seasons = ["2021/22", "2022/23", "2023/24", "2024/25"]

turnover_filter = alt.selection_point(fields=["Turnover"], bind="legend")
put_in_filter = alt.selection_point(fields=["Team"], bind="legend")
team_filter = alt.selection_point(fields=["Opposition"])

color_scale = alt.Scale(domain=["EG", "Opposition"], range=["#202946", "#981515"])
opacity_scale = alt.Scale(domain=["Turnover", "Retained"], range=[1, 0.5])

def set_piece_h2h_chart(df=None, file=None):

    season_selection = alt.param(
        bind=alt.binding_radio(options=[*seasons], name="Season"),
        value="2024/25"
    )

    squad_selection = alt.param(
        bind=alt.binding_radio(options=["1st", "2nd"], name="Squad"),
        value="1st"
    )
    
    base = (
        alt.Chart(df if df is not None else {"name":"df", "url":'https://raw.githubusercontent.com/samnlindsay/egrfc-stats/main/data/set_piece.csv',"format":{'type':"csv"}})
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
        chart.save(file)
        hack_params_css(file)

    return chart