from data_prep import *

# Position dictionary
d = {
    1: "Prop",
    2: "Hooker",
    3: "Prop",
    4: "Second Row",
    5: "Second Row",
    6: "Flanker",
    7: "Flanker",
    8: "Number 8",
    9: "Scrum Half",
    10: "Fly Half",
    11: "Wing",
    12: "Centre",
    13: "Centre",
    14: "Wing",
    15: "Full Back",
}


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

    df["Position"] = df.apply(lambda x: d.get(x["Number"]), axis=1)


    df = (
        df.groupby(["Player", "Position", by] if by else ["Player", "Position"])
        .agg({"PF": "count"})
        .reset_index()
        .sort_values(["Player", "PF"], ascending=[True, False])
    )

    df = df[df['PF'] >= 1]

    return df

def debuts(df, df_agg):

    df = df.sort_values(["Player", "Squad", "GameSort"])

    debut = df.groupby(["Player","Squad"]).agg({"GameID": "first", "Season": "first"}).reset_index()
    debut["Debut1"] = list(zip(debut["GameID"], debut["Season"]))
    debut = debut[debut["Squad"] == "1st"].drop(columns=["Squad", "GameID", "Season"])


    first_season = df_agg.groupby("Player").agg({"Season": "min"}).reset_index()
    first_season = first_season.rename(columns={"Season": "FirstSeason"})

    debuts = first_season.merge(debut, on="Player", how="left")

    return debuts

def players_table_data(df=None, df_agg=None):

    if df is None:
        df = players(team_sheets())
    if df_agg is None:
        df_agg = players_agg(df)
    
    positions = get_positions(df)
    positions = positions[
        positions.groupby('Player')['PF'].transform('sum') * 0.2 <= positions[~positions['Position'].isna()]['PF']
    ]
    positions = positions.groupby('Player').agg({'Position': lambda x: ' / '.join(x)}).reset_index()

    players_agg_df = players_agg(df)
    current_season = players_agg_df["Season"].max()

    df_current = totals(players_agg_df[players_agg_df["Season"] == current_season])
    df_total = totals(players_agg_df).rename(columns={
        "Tries": "TotalTries", 
        "Games": "TotalGames", 
        "Games1": "TotalGames1", 
        "Games2": "TotalGames2"
    })

    debuts_df = debuts(df, players_agg_df)

    df = (
        df_total
        .merge(df_current, on="Player", how="left").fillna(0)
        .merge(positions, on="Player", how="left")
        .merge(debuts_df, on="Player", how="left")
        .astype({"Tries": "int", "Games": "int", "Games1": "int", "Games2": "int"})
    )

    df.to_json("data/player_table.json", orient="records", indent=2)

    return df
