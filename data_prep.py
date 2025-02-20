import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import duckdb
import json
import re
import requests
from bs4 import BeautifulSoup

pd.options.mode.chained_assignment = None  # default='warn'

# Position dictionary
d = {
    1: "Prop",
    2: "Hooker",
    3: "Prop",
    4: "Second Row",
    5: "Second Row",
    6: "Back Row",
    7: "Back Row",
    8: "Back Row",
    9: "Scrum Half",
    10: "Fly Half",
    11: "Back Three",
    12: "Centre",
    13: "Centre",
    14: "Back Three",
    15: "Back Three",
}

def position_category(x):
    if x <= 8:
        return "Forwards"
    elif x <= 15:
        return "Backs"
    else:
        return "Bench"

con = duckdb.connect()

import gspread
from google.oauth2.service_account import Credentials
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('client_secret.json', scopes=scope)
client = gspread.authorize(creds)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1pcO8iEpZuds9AWs4AFRmqJtx5pv5QGbP4yg2dEkl8fU/edit#gid=2100247664").worksheets()

my_sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1keX2eGbyiBejpfMPMbL7aXYLy7IDJZDBXQqiKVQavz0/edit#gid=390656160").worksheets()

#####################################################
### TEAM SHEETS - 4th and 7th sheets in the workbook
#####################################################
def team_sheets():

    t1, t2 = [
        pd.DataFrame(
            sheet[s].batch_get(['B5:AK'])[0], 
            columns=["Season", "Competition", "Opposition", "Score", "Captain", "VC1", "VC2", *list(map(str,range(1, 30)))]
        ).replace('', pd.NA)
        for s in [4, 7]
    ]
    t1["Squad"] = "1st"
    t2["Squad"] = "2nd"
    team = pd.concat([t1, t2]).dropna(subset=['Season','Score'])

    team["GameID"] = team["Opposition"] + team.groupby(["Squad", "Opposition", "Season"]).cumcount().add(1).replace(1, "").astype(str)
    team['Home/Away'] = team['Opposition'].apply(lambda x: "H" if "(H)" in x else "A")
    team["Opposition"] = team["Opposition"].apply(lambda x: x.replace("(H)","").replace("(A)","").strip())
    team["GameType"] = team["Competition"].apply(
        lambda x: "Friendly" if x=="Friendly" else ("Cup" if re.search("Cup|Plate|Vase", x) else "League")
    )
    team["PF"] = team.apply(lambda x: int(x["Score"].split("-")[0 if x["Home/Away"] == "H" else 1]), axis=1)
    team["PA"] = team.apply(lambda x: int(x["Score"].split("-")[1 if x["Home/Away"] == "H" else 0]), axis=1)

    team["Result"] = team.apply(lambda x: "W" if x["PF"] > x["PA"] else ("L" if x["PF"] < x["PA"] else "D"), axis=1)

    # All column names to string
    team.columns = team.columns.astype(str)

    return team


# PLAYERS (1 row per player per game)
###########################################
def players(df=None):

    if df is None:
        df = team_sheets()

    players = df.melt(
        id_vars=["GameID", "Squad", "Season", "Competition", "GameType", "Opposition", "Home/Away", "PF", "PA", "Result", "Captain", "VC1", "VC2"], 
        value_vars=list(map(str,range(1, 26))), 
        value_name="Player",
        var_name="Number"
    ).dropna(subset=["Player"])
    players["Number"] = players["Number"].astype("int")
    players["Position"] = players["Number"].map(d).astype("category", )
    # If Position in ("Back Three", "Centre", "Fly Half", "Scrum Half"), then it's a Back, else it's a Forward
    players["PositionType"] = players["Number"].apply(position_category) 
    # positions_start = positions_start[positions_start["Position"].notna()]
    return players

# PLAYERS_AGG (1 row per player per season)
###########################################
def players_agg(df=None):
    if df is None:
        df = players()
    
    players_agg = con.query("""
    SELECT
        Squad,
        Season, 
        Player, 
        -- Cup games
        SUM(CASE WHEN GameType = 'Cup' AND Number <= 15 THEN 1 ELSE 0 END) AS CupStarts,
        SUM(CASE WHEN GameType = 'Cup' AND Number > 15 THEN 1 ELSE 0 END) AS CupBench,
        -- League games
        SUM(CASE WHEN GameType = 'League' AND Number <= 15 THEN 1 ELSE 0 END) AS LeagueStarts,
        SUM(CASE WHEN GameType = 'League' AND Number > 15 THEN 1 ELSE 0 END) AS LeagueBench,
        -- Friendlies
        SUM(CASE WHEN GameType = 'Friendly' AND Number <= 15 THEN 1 ELSE 0 END) AS FriendlyStarts,
        SUM(CASE WHEN GameType = 'Friendly' AND Number > 15 THEN 1 ELSE 0 END) AS FriendlyBench, 
        -- Competitive Totals
        SUM(CASE WHEN GameType != 'Friendly' AND Number <= 15 THEN 1 ELSE 0 END) AS CompetitiveStarts,
        SUM(CASE WHEN GameType != 'Friendly' AND Number > 15 THEN 1 ELSE 0 END) AS CompetitiveBench,
        -- Totals
        SUM(CASE WHEN Number <= 15 THEN 1 ELSE 0 END) AS TotalStarts,
        SUM(CASE WHEN Number > 15 THEN 1 ELSE 0 END) AS TotalBench,                          
        COUNT(*) AS TotalGames,      
        -- Most common Positions
        MODE(Position) AS MostCommonPosition,
        MODE(NULLIF(PositionType,'Bench')) AS MostCommonPositionType
    FROM df
    GROUP BY Squad, Season, Player
    """).to_df()

    return players_agg

##################################################
### LINEOUTS - 6th and 9th sheets in the workbook
##################################################

def call_type(call):

    if call in ["Snap", "Yes", "No"]:
        return "4-man only"
    elif call in ["Red", "Orange", "RD", "Even", "Odd", "Green", "Plus", "Even +", "Odd +", "Green +", "Matlow"]:
        return "Old"
    elif call in ["C*", "A*", "C1", "C2", "C3", "H1", "H2", "H3", "A1", "A2", "A3", "W1", "W2", "W3"]:
        return "New"    
    else:
        return "Other"
    
def dummy_movement(call):
    if call in ["RD", "Plus", "Even +", "Odd +", "Green +", "C3", "A1", "A2", "A3", "No"]:
        return "Dummy"
    elif call in ["Yes", "C1", "C2"]:
        return "Move"
    else:
        return "Jump"

def lineouts():
    l1, l2 = [sheet[s].batch_get(['B3:R'])[0] for s in [6, 9]]
    l1 = pd.DataFrame(l1, columns=l1.pop(0))
    l1["Squad"] = "1st"
    l2 = pd.DataFrame(l2, columns=l2.pop(0))
    l2["Squad"] = "2nd"
    df = pd.concat([l1, l2]).replace("", pd.NA).fillna("")

    df["Area"] = df.apply(lambda x: "Front" if x["Front"] == "x" else ("Middle" if x["Middle"]=="x" else "Back"), axis=1)
    df["Won"] = df.apply(lambda x: 1 if x["Won"] == "Y" else 0, axis=1)
    df["Drive"] = df.apply(lambda x: True if x["Drive"] == "x" else False, axis=1)
    df["Crusaders"] = df.apply(lambda x: True if x["Crusaders"] == "x" else False, axis=1)
    df["Transfer"] = df.apply(lambda x: True if x["Transfer"] == "x" else False, axis=1)
    df["Flyby"] = df.apply(lambda x: None if x["Flyby"] == "" else int(x["Flyby"]), axis=1)
    df["Movement"] = df.apply(lambda x: dummy_movement(x["Call"]), axis=1)

    df["CallType"] = df["Call"].apply(call_type)
    df["Setup"] = df["Call"].apply(lambda x: (x[0] if x[0] in ["A", "C", "H", "W"] else None) if len(x) > 0 else None)

    df = df[['Squad', 'Season', 'Opposition', 'Numbers', 'Call', 'CallType', 'Setup', 'Movement', 'Area', 'Drive', 'Crusaders', 'Transfer', 'Flyby', 'Hooker', 'Jumper', 'Won']]

    return df


########################
### PITCHERO TEAM STATS
########################

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


def pitchero_stats():

    dfs = []
    for squad in [1, 2]:
        for season in ["2021/22", "2022/23", "2023/24", "2024/25"]:
            url = f"https://www.egrfc.com/teams/14206{8 if squad==1 else 9}/statistics"
            seasonID = {
                "2021/22": 79578,
                "2022/23": 83980,
                "2023/24": 87941,
                "2024/25": 91673,
            }[season]

            url += f"?season={seasonID}"
            

            page = requests.get(url)
            soup = BeautifulSoup(page.content, 'html.parser')


            table = soup.find_all("div", {"class": "no-grid-hide"})[0]

            headers = [h.text for h in table.find_all("div", {"class": "league-table__header"})]
            players = [p.text for p in table.find_all("div", "sc-bwzfXH iWTrZm")]
            data = [int(d.text) for d in table.find_all("div", "sc-ifAKCX") if d.text.isnumeric()]

            # Split the data into columns
            data = [data[i:i+len(headers)-1] for i in range(0, len(data), len(headers)-1)]

            df = pd.DataFrame(data, columns=headers[1:], index=players)\
                .reset_index().rename(columns={"index": "Player"})

            df = df[["Player", "A", "T", "Con", "PK", "DG", "YC", "RC"]]

            df["Points"] = df["T"]*5 + df["Con"]*2 + df["DG"]*3 + df["PK"]*3 
            df["PPG"] = df["Points"] / df["A"]
            df["Season"] = season
            df["Squad"] = "1st" if squad == 1 else "2nd"

            df['Tries'] = df['T'].astype(int)*5
            df['Cons'] = df['Con'].astype(int)*2
            df['Pens'] = df['PK'].astype(int)*3

            df["Player_join"] = df["Player"].apply(clean_name)

            df.drop(columns=["Player"], inplace=True)

            if season == "2024/25" and squad == 1:
                # remove 1 from YC column for 'Guy Collins' and 'Aaron Boczek'
                df.loc[df["Player_join"].isin(["G Collins", "A Boczek"]), "YC"] = df.loc[df["Player_join"].isin(["G Collins", "A Boczek"]), "YC"] - 1
                # Add 1 YC for 'C Leggat'
                df.loc[df["Player_join"] == "C Leggat", "YC"] = df.loc[df["Player_join"] == "C Leggat", "YC"] + 1

            dfs.append(df)

    pitchero_df = pd.concat(dfs)
    players_agg_df = players_agg()[["Player", "Season", "Squad", "TotalGames"]]
    players_agg_df["Player_join"] = players_agg_df["Player"].apply(clean_name)

    
    return players_agg_df.merge(
        pitchero_df, 
        on=["Squad", "Season", "Player_join"], 
        how="left"
    )

########################
### SET PIECE SUMMARY
########################

def set_piece_results():

    columns=[
        "Season",
        "Date",
        "Opposition",
        "Home/Away",
        "PF",
        "PA",
        "PD",
        "EG_l_won",
        "EG_l_total",
        "EG_l_%",
        "Opp_l_won",
        "Opp_l_total",
        "Opp_l_%",
        "l_total",
        "l_gain",
        "EG_s_won",
        "EG_s_total",
        "EG_s_%",
        "Opp_s_won",
        "Opp_s_total",
        "Opp_s_%",
        "s_total",
        "s_gain",
    ]

    df1 = pd.DataFrame(sheet[5].batch_get(['B10:X'])[0], columns=columns).replace("", pd.NA).dropna(subset=["Season"])
    df2 = pd.DataFrame(sheet[8].batch_get(['B10:X'])[0], columns=columns).replace("", pd.NA).dropna(subset=["Season"])

    df1["Squad"] = "1st"
    df2["Squad"] = "2nd"

    df = pd.concat([df1, df2])

    # Convert columns to numeric where possible
    for c in df.columns:
        if c in ["Squad", "Season", "Date", "Opposition", "Home/Away"]:
            continue
        if "%" in c:
            df[c] = df[c].str.replace("%", "").astype(float)*0.01
        else:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["GameID"] = df["Opposition"] + " (" + df["Home/Away"] + ")" + df.groupby(["Squad", "Opposition", "Home/Away", "Season"]).cumcount().add(1).replace(1,"").astype(str)

    # Create "_lost" columns (_total - _won) and drop the _total columns
    for c in df.columns:
        if "_total" in c and ("_l" in c or "_s" in c):
            prefix=c[:-6]
            df[f"{prefix}_lost"] = df[f"{prefix}_total"] - df[f"{prefix}_won"]
            df.drop(columns=[c], inplace=True)

    id_cols=["Squad", "Season", "GameID", "Opposition", "Home/Away", "Date"]
    var_cols=["EG_l_won", "EG_l_lost", "EG_s_won", "EG_s_lost", "Opp_l_won", "Opp_l_lost", "Opp_s_won", "Opp_s_lost"]

    # df = df[id_cols + var_cols]

    df = df.melt(id_vars=id_cols, value_vars=var_cols, var_name="Metric", value_name="Count")

    df["SetPiece"] = df["Metric"].apply(lambda x: "Lineout" if "_l_" in x else "Scrum")
    df["Turnover"] = df["Metric"].apply(lambda x: "Retained" if "won" in x else "Turnover")
    df["Team"] = df["Metric"].apply(lambda x: "EG" if "EG" in x else "Opposition")
    df["Winner"] = df.apply(lambda x: x["Team"] if "won" in x["Metric"] else "Opposition" if x["Team"] == "EG" else "EG", axis=1)

    return df

#################################
### GAME STATS (Video Analysis)
#################################
def game_stats():
    analysis = sheet[0].batch_get(['B4:AZ'])[0]

    df = pd.DataFrame(analysis, columns=analysis.pop(0)).replace("", pd.NA)

    # Convert Date (7 Sep 2024) to vega-compatible date
    df.loc[:,"Date"] = pd.to_datetime(df["Date"], format="%d %b %Y")

    # Convert all percentage columns to floats
    for c in df.columns:
        if "%" in c:
            df.loc[:,c] = df[c].str.replace("%", "").astype(float)*0.01

    df["Game"] = df.apply(lambda x: x["Opposition"] + " (" + x["Home/Away"] + ")", axis=1)

    id_cols = ["Date", "Game", "Opposition", "Home/Away"]
    df = df.melt(id_vars=id_cols, var_name="Metric", value_name="Value")

    return df


#################################
### SEASON SUMMARY TABLE
#################################

from IPython.core.display import display, HTML
import pandas as pd

# Calculate summary statistics
def generate_season_summary(df, season):
    season_data = df[df["Season"] == season]
    summary = season_data.groupby("Squad").agg(
        Played=("GameID", "count"),
        Won=("Result", lambda x: (x == "W").sum()),
        Lost=("Result", lambda x: (x == "L").sum()),
        Avg_PF=("PF", "mean"),
        Avg_PA=("PA", "mean"),
    ).reset_index()
    
    # Convert to dictionary for easy JS manipulation
    summary_dict = summary.set_index("Squad").T.to_dict()
    
    return summary_dict

def update_season_summaries(df, seasons):
    summaries = {}
    for s in seasons:
        summaries[s] = generate_season_summary(df, s)
    with open("data/season_summaries.json", "w") as f:
        json.dump(summaries, f, indent=4)
