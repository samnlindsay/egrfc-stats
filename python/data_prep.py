import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import duckdb
import json
import re
import requests
from bs4 import BeautifulSoup

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

pd.options.mode.chained_assignment = None

con = duckdb.connect()

# Google Sheets setup
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('client_secret.json', scopes=scope)
client = gspread.authorize(creds)

# Use the optimized sheets
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1pcO8iEpZuds9AWs4AFRmqJtx5pv5QGbP4yg2dEkl8fU/edit#gid=2100247664").worksheets()

#####################################################
### OPTIMIZED DATA LOADING FUNCTIONS
#####################################################

def load_matches():
    """Load match data from optimized Matches sheet"""
    try:
        matches_sheet = next(ws for ws in sheet if ws.title == "Matches")
        data = matches_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Convert data types
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['PF'] = pd.to_numeric(df['PF'], errors='coerce')
        df['PA'] = pd.to_numeric(df['PA'], errors='coerce')
        df['Margin'] = pd.to_numeric(df['Margin'], errors='coerce')
        
        # Convert retention columns to numeric
        retention_cols = ['ForwardsRetained', 'BacksRetained', 'StartersRetained', 'FullSquadRetained']
        for col in retention_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        print(f"Error loading matches: {e}")
        return pd.DataFrame()

def load_player_appearances():
    """Load player appearances from optimized PlayerAppearances sheet"""
    try:
        appearances_sheet = next(ws for ws in sheet if ws.title == "PlayerAppearances")
        data = appearances_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Convert data types
        df['ShirtNumber'] = pd.to_numeric(df['ShirtNumber'], errors='coerce')
        bool_cols = ['IsStarter', 'IsCaptain', 'IsVC']
        for col in bool_cols:
            df[col] = df[col].astype(bool)
        
        return df
    except Exception as e:
        print(f"Error loading player appearances: {e}")
        return pd.DataFrame()

def load_lineouts():
    """Load lineout data from optimized LineoutsData sheet"""
    try:
        lineouts_sheet = next(ws for ws in sheet if ws.title == "LineoutsData")
        data = lineouts_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Convert data types
        df['Won'] = df['Won'].astype(bool)
        bool_cols = ['Drive', 'Crusaders', 'Transfer']
        for col in bool_cols:
            df[col] = df[col].astype(bool)
        
        df['Flyby'] = pd.to_numeric(df['Flyby'], errors='coerce')
        
        return df
    except Exception as e:
        print(f"Error loading lineouts: {e}")
        return pd.DataFrame()

def load_set_piece():
    """Load set piece data from optimized SetPieceData sheet"""
    try:
        setpiece_sheet = next(ws for ws in sheet if ws.title == "SetPieceData")
        data = setpiece_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Convert numeric columns
        numeric_cols = [col for col in df.columns if any(x in col for x in ['Won', 'Total', 'Pct', 'Gain'])]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    except Exception as e:
        print(f"Error loading set piece data: {e}")
        return pd.DataFrame()

#####################################################
### ENHANCED DATA PROCESSING FUNCTIONS
#####################################################

def players_agg_optimized():
    """Create aggregated player statistics using optimized data"""
    appearances_df = load_player_appearances()
    matches_df = load_matches()
    
    if appearances_df.empty or matches_df.empty:
        return pd.DataFrame()
    
    # Join with match data for game type information
    df = appearances_df.merge(
        matches_df[['GameID', 'GameType', 'Date']], 
        on='GameID', 
        how='left'
    )
    
    # Use DuckDB for efficient aggregation
    players_agg = con.query("""
    SELECT
        Squad,
        Season, 
        Player,
        -- Game type breakdowns
        SUM(CASE WHEN GameType = 'Cup' AND IsStarter = 1 THEN 1 ELSE 0 END) AS CupStarts,
        SUM(CASE WHEN GameType = 'Cup' AND IsStarter = 0 THEN 1 ELSE 0 END) AS CupBench,
        SUM(CASE WHEN GameType = 'League' AND IsStarter = 1 THEN 1 ELSE 0 END) AS LeagueStarts,
        SUM(CASE WHEN GameType = 'League' AND IsStarter = 0 THEN 1 ELSE 0 END) AS LeagueBench,
        SUM(CASE WHEN GameType = 'Friendly' AND IsStarter = 1 THEN 1 ELSE 0 END) AS FriendlyStarts,
        SUM(CASE WHEN GameType = 'Friendly' AND IsStarter = 0 THEN 1 ELSE 0 END) AS FriendlyBench,
        -- Totals
        SUM(CASE WHEN IsStarter = 1 THEN 1 ELSE 0 END) AS TotalStarts,
        SUM(CASE WHEN IsStarter = 0 THEN 1 ELSE 0 END) AS TotalBench,
        COUNT(*) AS TotalGames,
        -- Leadership
        SUM(IsCaptain) AS TimesCaptain,
        SUM(IsVC) AS TimesVC,
        -- Most common positions
        MODE(Position) AS MostCommonPosition,
        MODE(PositionGroup) AS MostCommonPositionGroup,
        MODE(CASE WHEN Unit != 'Bench' THEN Unit END) AS MostCommonUnit
    FROM df
    GROUP BY Squad, Season, Player
    """).to_df()
    
    return players_agg

def lineout_success_enhanced():
    """Enhanced lineout analysis with optimized data"""
    lineouts_df = load_lineouts()
    
    if lineouts_df.empty:
        return pd.DataFrame()
    
    # Calculate success rates by various dimensions
    success_analysis = con.query("""
    SELECT
        Squad,
        Season,
        Opposition,
        Area,
        Setup,
        Movement,
        CallType,
        Hooker,
        Jumper,
        COUNT(*) as Total,
        SUM(Won) as Won,
        AVG(Won) as SuccessRate,
        COUNT(CASE WHEN Drive = 1 THEN 1 END) as DriveLineouts,
        AVG(CASE WHEN Drive = 1 THEN Won END) as DriveSuccessRate
    FROM lineouts_df
    WHERE Squad IS NOT NULL AND Season IS NOT NULL
    GROUP BY Squad, Season, Opposition, Area, Setup, Movement, CallType, Hooker, Jumper
    HAVING Total >= 1
    ORDER BY Season DESC, Squad, Total DESC
    """).to_df()
    
    return success_analysis

def set_piece_h2h_optimized():
    """Enhanced set piece head-to-head analysis"""
    setpiece_df = load_set_piece()
    
    if setpiece_df.empty:
        return pd.DataFrame()
    
    # Transform to long format for analysis
    h2h_data = con.query("""
    SELECT 
        GameID,
        Squad,
        Season,
        Date,
        Opposition,
        HomeAway,
        'Lineout' as SetPiece,
        'EG' as Team,
        EG_Lineout_Won as Won,
        EG_Lineout_Total as Total,
        EG_Lineout_Total - EG_Lineout_Won as Lost
    FROM setpiece_df
    WHERE EG_Lineout_Total > 0
    
    UNION ALL
    
    SELECT 
        GameID,
        Squad,
        Season,
        Date,
        Opposition,
        HomeAway,
        'Lineout' as SetPiece,
        'Opposition' as Team,
        Opp_Lineout_Won as Won,
        Opp_Lineout_Total as Total,
        Opp_Lineout_Total - Opp_Lineout_Won as Lost
    FROM setpiece_df
    WHERE Opp_Lineout_Total > 0
    
    UNION ALL
    
    SELECT 
        GameID,
        Squad,
        Season,
        Date,
        Opposition,
        HomeAway,
        'Scrum' as SetPiece,
        'EG' as Team,
        EG_Scrum_Won as Won,
        EG_Scrum_Total as Total,
        EG_Scrum_Total - EG_Scrum_Won as Lost
    FROM setpiece_df
    WHERE EG_Scrum_Total > 0
    
    UNION ALL
    
    SELECT 
        GameID,
        Squad,
        Season,
        Date,
        Opposition,
        HomeAway,
        'Scrum' as SetPiece,
        'Opposition' as Team,
        Opp_Scrum_Won as Won,
        Opp_Scrum_Total as Total,
        Opp_Scrum_Total - Opp_Scrum_Won as Lost
    FROM setpiece_df
    WHERE Opp_Scrum_Total > 0
    """).to_df()
    
    return h2h_data

#####################################################
### COMPATIBILITY FUNCTIONS (for existing charts)
#####################################################

def team_sheets():
    """Legacy compatibility function - maps to optimized matches data"""
    matches_df = load_matches()
    appearances_df = load_player_appearances()
    
    if matches_df.empty:
        return pd.DataFrame()
    
    # For charts that expect the old format, we can reconstruct it
    # This is a temporary bridge while updating chart functions
    return matches_df

def players(df=None):
    """Legacy compatibility function - maps to optimized player appearances"""
    return load_player_appearances()

def players_agg(df=None):
    """Legacy compatibility function"""
    return players_agg_optimized()

def lineouts():
    """Legacy compatibility function"""
    return load_lineouts()

def set_piece_results():
    """Legacy compatibility function"""
    return set_piece_h2h_optimized()

#####################################################
### NEW ANALYSIS FUNCTIONS
#####################################################

def squad_continuity_analysis():
    """Enhanced squad continuity analysis"""
    matches_df = load_matches()
    
    return con.query("""
    SELECT
        Squad,
        Season,
        AVG(ForwardsRetained) as AvgForwardsRetained,
        AVG(BacksRetained) as AvgBacksRetained,
        AVG(StartersRetained) as AvgStartersRetained,
        AVG(FullSquadRetained) as AvgFullSquadRetained,
        COUNT(*) as Games
    FROM matches_df
    WHERE Season IS NOT NULL
    GROUP BY Squad, Season
    ORDER BY Season DESC, Squad
    """).to_df()

def player_positional_analysis():
    """Analyze player position flexibility"""
    appearances_df = load_player_appearances()
    
    return con.query("""
    SELECT
        Player,
        Season,
        Squad,
        COUNT(DISTINCT Position) as PositionsPlayed,
        COUNT(DISTINCT PositionGroup) as PositionGroupsPlayed,
        MODE(Position) as PrimaryPosition,
        MODE(PositionGroup) as PrimaryPositionGroup,
        COUNT(*) as TotalAppearances,
        SUM(IsStarter) as Starts
    FROM appearances_df
    WHERE Season IS NOT NULL
    GROUP BY Player, Season, Squad
    HAVING TotalAppearances >= 3
    ORDER BY PositionsPlayed DESC, TotalAppearances DESC
    """).to_df()

def game_stats():
    """Load video analysis data (keeping existing function)"""
    try:
        analysis = sheet[0].batch_get(['B4:AZ'])[0]
        df = pd.DataFrame(analysis, columns=analysis.pop(0)).replace("", pd.NA)
        
        df.loc[:,"Date"] = pd.to_datetime(df["Date"], format="%d %b %Y")
        
        for c in df.columns:
            if "%" in c:
                df.loc[:,c] = df[c].str.replace("%", "").astype(float)*0.01
        
        df["Game"] = df.apply(lambda x: x["Opposition"] + " (" + x["Home/Away"] + ")", axis=1)
        
        id_cols = ["Date", "Game", "Opposition", "Home/Away"]
        df = df.melt(id_vars=id_cols, var_name="Metric", value_name="Value")
        
        return df
    except Exception as e:
        print(f"Error loading game stats: {e}")
        return pd.DataFrame()

# Keep existing helper functions for compatibility
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
    surname = surname.replace("'", "'")
    name_clean = f"{initial} {surname}"
    return name_clean.strip().title()

def pitchero_stats():

    season_ids = {
        # "2016/17": 42025, 
        "2017/18": 47693,
        "2018/19": 52304,
        "2019/20": 68499,
        "2021/22": 79578,
        "2022/23": 83980,
        "2023/24": 87941,
        "2024/25": 91673,
        # "2025/26": 94981,
    }

    dfs = []
    for squad in [1, 2]:
        for season in season_ids.keys():
            url = f"https://www.egrfc.com/teams/14206{8 if squad==1 else 9}/statistics?season={season_ids[season]}"            

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

            # Before 2021/22, replace "S Lindsay" with "S Lindsay 2"
            if season < "2021/22":
                df["Player_join"] = df["Player_join"].replace("S Lindsay", "S Lindsay 2")

            if season == "2024/25" and squad == 1:
                # remove 1 from YC column for 'Guy Collins' and 'Aaron Boczek'
                df.loc[df["Player_join"].isin(["G Collins", "A Boczek"]), "YC"] = df.loc[df["Player_join"].isin(["G Collins", "A Boczek"]), "YC"] - 1
                # Add 1 YC for 'C Leggat'
                df.loc[df["Player_join"] == "C Leggat", "YC"] = df.loc[df["Player_join"] == "C Leggat", "YC"] + 1

            dfs.append(df)

    pitchero_df = pd.concat(dfs)

    pitchero_df = pitchero_df.groupby(["Squad", "Season", "Player_join"]).sum().reset_index()
    
    return pitchero_df

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
### SEASON SUMMARY TABLES
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

    return summaries

def set_piece_summaries(df):
    df_agg = df.groupby(["Season", "Squad", "SetPiece", "Metric"])["Count"].agg(["sum", "count"]).reset_index()

    # Replace "_l_" and "_s_" with "_"
    df_agg["Metric"] = df_agg["Metric"].str.replace("_l_", "_").str.replace("_s_", "_")

    df_agg = df_agg.pivot_table(
        index=["Season", "Squad", "SetPiece", "count"], 
        columns="Metric", values="sum", fill_value=0
    ).reset_index().rename_axis(None, axis=1)

    df_agg["T_won"] = df_agg["Opp_lost"] / df_agg["count"]
    df_agg["T_lost"] = df_agg["EG_lost"] / df_agg["count"]
    df_agg["EG_total"] = (df_agg["EG_won"] + df_agg["EG_lost"]) / df_agg["count"]
    df_agg["Opp_total"] = (df_agg["Opp_won"] + df_agg["Opp_lost"]) / df_agg["count"]
    df_agg["EG_success"] = df_agg["EG_won"] / df_agg["EG_total"] / df_agg["count"]
    df_agg["Opp_success"] = df_agg["Opp_won"] / df_agg["Opp_total"] / df_agg["count"]

    df_agg = df_agg[[
        "Season", 
        "Squad", 
        "SetPiece", 
        "count", 
        "EG_total", 
        "EG_success", 
        "Opp_total", 
        "Opp_success",
        "T_won",
        "T_lost"
    ]]

    # Convert to dictionary for easy JS manipulation
    d = {}
    for (x, y, z), group in df_agg.groupby(["Season", "Squad", "SetPiece"]):
        d.setdefault(x, {}).setdefault(y, {})[z] = group.drop(columns=["Season", "Squad", "SetPiece"]).to_dict(orient="records")[0]

    # Save to JSON
    with open("data/set_piece_summaries.json", "w") as f:
        json.dump(d, f, indent=4)

    return df_agg


def top_players_summary(df):

    # Squads
    df_squad = (
        df.groupby(["Season", "Squad"])
        .agg(PlayersUsed=("Player", "nunique"), TotalGames=("TotalGames", "max"), T=("T", "max"))
        .reset_index()
    )

    top_players = df.groupby(["Season", "Squad", "TotalGames"]).agg(
        Players_A=("Player", lambda x: " / ".join(x))
    ).reset_index()

    top_tries = df.groupby(["Season", "Squad", "T"]).agg(
        Players_T=("Player", lambda x: " / ".join(x))
    ).reset_index()


    df_squad = df_squad.merge(top_players, on=["Season", "Squad", "TotalGames"], how="left")
    df_squad = df_squad.merge(top_tries, on=["Season", "Squad", "T"], how="left")

    # Total
    df_total = (
        df.groupby(["Season", "Player"])
        .agg(TotalGames=("TotalGames", "sum"), T=("T", "sum"))
        .reset_index()
        .groupby(["Season"])
        .agg(PlayersUsed=("Player", "nunique"), TotalGames=("TotalGames", "max"), T=("T", "max"))
        .reset_index()
    )
    top_players = df.groupby(["Season", "Player"]).agg(
        TotalGames=("TotalGames", "sum"), 
        T=("T", "sum")
    ).reset_index()

    top_tries = top_players.groupby(["Season", "T"]).agg(
        Players_T=("Player", lambda x: " / ".join(x))
    ).reset_index()

    top_players = top_players.groupby(["Season", "TotalGames"]).agg(
        Players_A=("Player", lambda x: " / ".join(x))
    ).reset_index()

    df_total = df_total.merge(top_players, on=["Season", "TotalGames"], how="left")
    df_total = df_total.merge(top_tries, on=["Season", "T"], how="left")
    df_total["Squad"] = "Total"

    df_final = pd.concat([df_squad, df_total])

    df_final["Players_A"] = df_final["Players_A"] + "  (" + df_final["TotalGames"].astype(int).astype(str) + ")"
    df_final["Players_T"] = df_final["Players_T"] + "  (" + df_final["T"].astype(int).astype(str) + ")"
    df_final = df_final[["Season", "Squad", "PlayersUsed", "Players_A", "Players_T"]].sort_values(["Season", "Squad"])

    # Convert to dictionary for easy JS manipulation
    d = {}
    for (x, y), group in df_final.groupby(["Season", "Squad"]):
        d.setdefault(x, {})[y] = group.drop(columns=["Season", "Squad"]).to_dict(orient="records")[0]


    with open("data/top_players.json", "w") as f:
        json.dump(d, f, indent=4)

    return df_final


