"""Canonical data backend for EGRFC stats.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from python.data import HISTORIC_PITCHERO_SEASON_IDS, DataExtractor, clean_name
from python.league_data import (
    build_rfu_games_dataframe,
    build_rfu_player_appearances_dataframe,
    load_consolidated_matches,
)


PITCHERO_TO_GOOGLE_CANONICAL_NAMES = {
    "Daniel Arnold": "Dan Arnold",
    "Christopher Pentney": "Chris Pentney",
    "Joshua Brimecombe": "Josh Brimecombe",
    "Matthew EDWARDS": "Matthew Edwards",
    "Oliver Adams": "Ollie Adams",
    "Peter Morley": "Pete Morley",
    "Thomas Byron": "Tom Byron",
    "Thomas Halligey": "Tom Halligey",
}

PITCHERO_OPPOSITION_CANONICAL_NAMES = {
    "brighton3": "Brighton III",
    "burgesshill2": "Burgess Hill",
    "crawleycupfinal": "Crawley",
    "crawley2s3s": "Crawley II",
    "ditchlingrfc": "Ditchling",
    "eastbourneiirfc": "Eastbourne II",
    "eastbourne2": "Eastbourne II",
    "eastbourne2s": "Eastbourne II",
    "haywardsheath2xv": "Haywards Heath II",
    "heathfield3s": "Heathfield III",
    "heathfieldwaldron3": "Heathfield & Waldron III",
    "hellingly2": "Hellingly II",
    "hove2": "Hove II",
    "hove2xv": "Hove II",
    "hove3": "Hove III",
    "pulborough2": "Pulborough II",
    "pulborough3": "Pulborough III",
    "uckfieldiirfc": "Uckfield II",
    "uckfield2s": "Uckfield II",
    "uckfieldrfc": "Uckfield",
    "warlingham3s": "Warlingham III",
}


def _mode_or_none(series: pd.Series) -> str | None:
    values = series.dropna()
    if values.empty:
        return None
    modes = values.mode()
    if modes.empty:
        return None
    return str(modes.iloc[0])


def _safe_date(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", format="%Y-%m-%d")
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(series.loc[missing], errors="coerce", dayfirst=True)
    return parsed.dt.date


def _yes_no_to_bool(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.upper().isin(["Y", "YES", "TRUE", "X", "1"])


def _normalise_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _canonical_player_name(name: Any) -> Any:
    if pd.isna(name):
        return name
    return PITCHERO_TO_GOOGLE_CANONICAL_NAMES.get(str(name).strip(), str(name).strip())


def _canonical_pitchero_opposition_name(name: Any) -> Any:
    if pd.isna(name):
        return name
    cleaned = str(name).strip()
    return PITCHERO_OPPOSITION_CANONICAL_NAMES.get(_normalise_key(cleaned), cleaned)


@dataclass
class BackendConfig:
    db_path: str = "data/egrfc_backend.duckdb"
    export_dir: str = "data/backend"
    pitchero_cache_path: str = "data/pitchero_stats_cache.json"
    historic_pitchero_cache_path: str = "data/pitchero_historic_team_sheets_cache.json"
    credentials_path: str = "client_secret.json"
    rfu_matches_path: str = "data/matches.json"


class BackendDatabase:
    def __init__(self, config: BackendConfig | None = None):
        self.config = config or BackendConfig()
        self.project_root = Path(__file__).resolve().parent.parent
        self.db_file = self.project_root / self.config.db_path
        self.export_root = self.project_root / self.config.export_dir
        self.pitchero_cache_file = self.project_root / self.config.pitchero_cache_path
        self.historic_pitchero_cache_file = self.project_root / self.config.historic_pitchero_cache_path
        self.rfu_matches_file = self.project_root / self.config.rfu_matches_path
        try:
            self.con = duckdb.connect(str(self.db_file))
        except duckdb.IOException as exc:
            if "Could not set lock on file" in str(exc):
                raise RuntimeError(
                    "Backend DB is locked by another process. Close notebooks/scripts using "
                    f"{self.db_file.as_posix()} or run with an alternate path using --db-path."
                ) from exc
            raise

    def close(self) -> None:
        self.con.close()

    def reset_schema(self) -> None:
        self.con.execute("DROP VIEW IF EXISTS v_player_profiles")
        self.con.execute("DROP VIEW IF EXISTS v_player_appearance_discrepancy_summary")
        self.con.execute("DROP VIEW IF EXISTS v_season_player_appearances_reconciled")
        self.con.execute("DROP VIEW IF EXISTS v_pitchero_appearance_mismatches")
        self.con.execute("DROP VIEW IF EXISTS v_lineout_summary")
        self.con.execute("DROP VIEW IF EXISTS v_set_piece_summary")
        self.con.execute("DROP VIEW IF EXISTS v_season_results")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_lineup_coverage")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_average_retention")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_match_retention")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_squad_size")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_team_games")
        self.con.execute("DROP TABLE IF EXISTS pitchero_appearance_backfill")
        self.con.execute("DROP TABLE IF EXISTS pitchero_appearance_reconciliation")
        self.con.execute("DROP TABLE IF EXISTS player_appearances_rfu")
        self.con.execute("DROP TABLE IF EXISTS players")
        self.con.execute("DROP TABLE IF EXISTS season_scorers")
        self.con.execute("DROP TABLE IF EXISTS lineouts")
        self.con.execute("DROP TABLE IF EXISTS set_piece")
        self.con.execute("DROP TABLE IF EXISTS player_appearances")
        self.con.execute("DROP TABLE IF EXISTS games_rfu")
        self.con.execute("DROP TABLE IF EXISTS games")

        self.con.execute(
            """
            CREATE TABLE games (
                game_id TEXT PRIMARY KEY,
                squad TEXT NOT NULL,
                date DATE NOT NULL,
                season TEXT,
                competition TEXT,
                game_type TEXT,
                opposition TEXT,
                home_away TEXT,
                score_for INTEGER,
                score_against INTEGER,
                result TEXT,
                captain TEXT,
                vice_captain_1 TEXT,
                vice_captain_2 TEXT,
                UNIQUE(squad, date, opposition)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE player_appearances (
                squad TEXT NOT NULL,
                date DATE NOT NULL,
                player TEXT NOT NULL,
                number INTEGER,
                position TEXT,
                unit TEXT,
                is_captain BOOLEAN,
                is_vice_captain BOOLEAN,
                game_id TEXT,
                season TEXT,
                game_type TEXT,
                is_starter BOOLEAN,
                PRIMARY KEY(squad, date, player)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE games_rfu (
                match_id TEXT PRIMARY KEY,
                season TEXT NOT NULL,
                league TEXT,
                tracked_squad TEXT,
                date DATE NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_score INTEGER,
                away_score INTEGER,
                home_walkover BOOLEAN,
                away_walkover BOOLEAN,
                lineup_available_home BOOLEAN,
                lineup_available_away BOOLEAN
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE player_appearances_rfu (
                match_id TEXT NOT NULL,
                season TEXT NOT NULL,
                league TEXT,
                tracked_squad TEXT,
                date DATE NOT NULL,
                team TEXT NOT NULL,
                opposition TEXT,
                home_away TEXT,
                player TEXT NOT NULL,
                shirt_number INTEGER,
                position TEXT,
                unit TEXT,
                is_starter BOOLEAN,
                previous_match_id TEXT,
                played_previous_game BOOLEAN,
                PRIMARY KEY(match_id, team, player)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE lineouts (
                squad TEXT NOT NULL,
                date DATE NOT NULL,
                seq_id INTEGER NOT NULL,
                half TEXT,
                numbers TEXT,
                call TEXT,
                call_type TEXT,
                dummy BOOLEAN,
                area TEXT,
                drive BOOLEAN,
                crusaders BOOLEAN,
                transfer BOOLEAN,
                flyby BOOLEAN,
                thrower TEXT,
                jumper TEXT,
                won BOOLEAN,
                game_id TEXT,
                season TEXT,
                opposition TEXT,
                PRIMARY KEY(squad, date, seq_id)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE set_piece (
                squad TEXT NOT NULL,
                date DATE NOT NULL,
                team TEXT NOT NULL,
                lineouts_won INTEGER,
                lineouts_total INTEGER,
                lineouts_success_rate DOUBLE,
                scrums_won INTEGER,
                scrums_total INTEGER,
                scrums_success_rate DOUBLE,
                entries_22m INTEGER,
                points_per_22m_entry DOUBLE,
                tries_per_22m_entry DOUBLE,
                game_id TEXT,
                season TEXT,
                opposition TEXT,
                PRIMARY KEY(squad, date, team)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE season_scorers (
                squad TEXT NOT NULL,
                season TEXT NOT NULL,
                player TEXT NOT NULL,
                tries BIGINT,
                conversions BIGINT,
                penalties BIGINT,
                drop_goals BIGINT,
                points BIGINT,
                source TEXT,
                PRIMARY KEY(squad, season, player)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE players (
                name TEXT PRIMARY KEY,
                short_name TEXT,
                position TEXT,
                squad TEXT,
                first_appearance_date DATE,
                first_appearance_squad TEXT,
                first_appearance_opposition TEXT,
                photo_url TEXT,
                sponsor TEXT,
                total_appearances INTEGER,
                total_starts INTEGER,
                total_captaincies INTEGER,
                total_vc_appointments INTEGER,
                total_lineouts_jumped INTEGER,
                lineouts_won_as_jumper INTEGER,
                career_points BIGINT
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE pitchero_appearance_reconciliation (
                squad TEXT NOT NULL,
                season TEXT NOT NULL,
                player_join TEXT NOT NULL,
                player TEXT,
                pitchero_appearances INTEGER,
                scraped_appearances INTEGER,
                delta INTEGER,
                abs_delta INTEGER,
                status TEXT,
                fix_type TEXT,
                PRIMARY KEY(squad, season, player_join)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE pitchero_appearance_backfill (
                squad TEXT NOT NULL,
                season TEXT NOT NULL,
                player_join TEXT NOT NULL,
                player TEXT,
                missing_appearances INTEGER,
                applied_fix BOOLEAN,
                PRIMARY KEY(squad, season, player_join)
            )
            """
        )

    def build(self, refresh_pitchero: bool = False, export: bool = True) -> None:
        self.reset_schema()
        extractor = DataExtractor(credentials_path=self.config.credentials_path)

        games_raw = extractor.extract_games_data()
        appearances_raw = extractor.extract_player_appearances()

        historic_games_raw, historic_appearances_raw = self._load_historic_pitchero_team_sheets(
            extractor=extractor,
            refresh_pitchero=refresh_pitchero,
        )
        if not historic_games_raw.empty:
            games_raw = pd.concat([games_raw, historic_games_raw], ignore_index=True)
        if not historic_appearances_raw.empty:
            appearances_raw = pd.concat([appearances_raw, historic_appearances_raw], ignore_index=True)

        lineouts_raw = self._extract_lineouts(extractor)
        set_piece_raw = extractor.extract_set_piece_stats()
        pitchero_raw = self._load_pitchero(extractor, refresh_pitchero)
        scorers_2526_raw = self._extract_2526_scorers(extractor)
        rfu_matches_raw = load_consolidated_matches(self.rfu_matches_file.as_posix())

        games = self._build_games(games_raw, appearances_raw)
        appearances = self._build_player_appearances(appearances_raw, games)
        lineouts = self._build_lineouts(lineouts_raw, games)
        set_piece = self._build_set_piece(set_piece_raw, games)
        season_scorers = self._build_season_scorers(scorers_2526_raw, pitchero_raw, appearances)
        reconciliation, backfill = self._build_pitchero_appearance_reconciliation(pitchero_raw, appearances)
        players = self._build_players(appearances, games, lineouts, season_scorers, reconciliation)
        games_rfu = build_rfu_games_dataframe(
            matches=rfu_matches_raw,
            consolidated_file=self.rfu_matches_file.as_posix(),
        )
        appearances_rfu = build_rfu_player_appearances_dataframe(
            matches=rfu_matches_raw,
            consolidated_file=self.rfu_matches_file.as_posix(),
            games_df=games_rfu,
        )

        self._insert("games", games)
        self._insert("player_appearances", appearances)
        self._insert("games_rfu", games_rfu)
        self._insert("player_appearances_rfu", appearances_rfu)
        self._insert("lineouts", lineouts)
        self._insert("set_piece", set_piece)
        self._insert("season_scorers", season_scorers)
        self._insert("players", players)
        self._insert("pitchero_appearance_reconciliation", reconciliation)
        self._insert("pitchero_appearance_backfill", backfill)

        self.create_views()

        if export:
            self.export_tables()

    def create_views(self) -> None:
        self.con.execute(
            """
            CREATE VIEW v_season_results AS
            SELECT
                season,
                squad,
                game_type,
                COUNT(*) AS played,
                SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) AS won,
                SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) AS lost,
                SUM(CASE WHEN result = 'D' THEN 1 ELSE 0 END) AS drawn,
                SUM(score_for) AS points_for,
                SUM(score_against) AS points_against
            FROM games
            GROUP BY season, squad, game_type
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_set_piece_summary AS
            SELECT
                squad,
                season,
                team,
                AVG(lineouts_success_rate) AS avg_lineouts_success_rate,
                AVG(scrums_success_rate) AS avg_scrums_success_rate,
                AVG(points_per_22m_entry) AS avg_points_per_22m_entry,
                AVG(tries_per_22m_entry) AS avg_tries_per_22m_entry,
                COUNT(*) AS games
            FROM set_piece
            GROUP BY squad, season, team
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_lineout_summary AS
            SELECT
                squad,
                season,
                area,
                call_type,
                thrower,
                jumper,
                COUNT(*) AS total,
                SUM(CASE WHEN won THEN 1 ELSE 0 END) AS won,
                AVG(CASE WHEN won THEN 1.0 ELSE 0.0 END) AS success_rate
            FROM lineouts
            GROUP BY squad, season, area, call_type, thrower, jumper
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_player_profiles AS
            SELECT
                p.*,
                COALESCE(ss.points, 0) AS latest_season_points,
                COALESCE(ss.tries, 0) AS latest_season_tries,
                COALESCE(ss.conversions, 0) AS latest_season_conversions,
                COALESCE(ss.penalties, 0) AS latest_season_penalties
            FROM players p
            LEFT JOIN (
                SELECT
                    x.player,
                    x.points,
                    x.tries,
                    x.conversions,
                    x.penalties,
                    x.season
                FROM season_scorers x
                INNER JOIN (
                    SELECT player, MAX(season) AS season
                    FROM season_scorers
                    GROUP BY player
                ) y
                ON x.player = y.player AND x.season = y.season
            ) ss
            ON p.name = ss.player
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_rfu_team_games AS
            WITH team_games AS (
                SELECT
                    match_id,
                    season,
                    league,
                    tracked_squad AS squad,
                    date,
                    home_team AS team,
                    away_team AS opposition,
                    'H' AS home_away,
                    home_score AS score_for,
                    away_score AS score_against,
                    home_walkover AS team_walkover,
                    away_walkover AS opposition_walkover,
                    lineup_available_home AS lineup_available
                FROM games_rfu

                UNION ALL

                SELECT
                    match_id,
                    season,
                    league,
                    tracked_squad AS squad,
                    date,
                    away_team AS team,
                    home_team AS opposition,
                    'A' AS home_away,
                    away_score AS score_for,
                    home_score AS score_against,
                    away_walkover AS team_walkover,
                    home_walkover AS opposition_walkover,
                    lineup_available_away AS lineup_available
                FROM games_rfu
            )
            SELECT
                *,
                LAG(match_id) OVER (PARTITION BY season, team ORDER BY date, match_id) AS previous_match_id
            FROM team_games
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_rfu_squad_size AS
            WITH player_units AS (
                SELECT
                    season,
                    league,
                    tracked_squad AS squad,
                    team,
                    player,
                    CASE
                        WHEN MAX(CASE WHEN unit = 'Forwards' THEN 1 ELSE 0 END) = 1 THEN 'Forwards'
                        WHEN MAX(CASE WHEN unit = 'Backs' THEN 1 ELSE 0 END) = 1 THEN 'Backs'
                        ELSE 'Bench'
                    END AS unit
                FROM player_appearances_rfu
                GROUP BY season, league, tracked_squad, team, player
            )
            SELECT season, league, squad, team, unit, COUNT(*) AS players
            FROM player_units
            WHERE unit IN ('Forwards', 'Backs')
            GROUP BY season, league, squad, team, unit

            UNION ALL

            SELECT season, league, squad, team, 'Total' AS unit, COUNT(*) AS players
            FROM player_units
            GROUP BY season, league, squad, team
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_rfu_match_retention AS
            WITH starters AS (
                SELECT
                    match_id,
                    previous_match_id,
                    season,
                    league,
                    tracked_squad AS squad,
                    date,
                    team,
                    opposition,
                    player,
                    unit
                FROM player_appearances_rfu
                WHERE is_starter = TRUE
            ),
            starter_units AS (
                SELECT match_id, previous_match_id, season, league, squad, date, team, opposition, player, 'Total' AS unit
                FROM starters

                UNION ALL

                SELECT match_id, previous_match_id, season, league, squad, date, team, opposition, player, unit
                FROM starters
                WHERE unit IN ('Forwards', 'Backs')
            ),
            lineup_flags AS (
                SELECT match_id, team, COUNT(*) > 0 AS lineup_available
                FROM starters
                GROUP BY match_id, team
            )
            SELECT
                curr.season,
                curr.league,
                curr.squad,
                curr.team,
                curr.opposition,
                curr.date,
                curr.match_id,
                curr.previous_match_id,
                curr.unit,
                COALESCE(MAX(CASE WHEN prev_lineup.lineup_available THEN 1 ELSE 0 END), 0) AS previous_lineup_available,
                COUNT(DISTINCT CASE WHEN prev.player IS NOT NULL THEN curr.player END) AS retained
            FROM starter_units curr
            LEFT JOIN lineup_flags prev_lineup
                ON prev_lineup.match_id = curr.previous_match_id
                AND prev_lineup.team = curr.team
            LEFT JOIN starter_units prev
                ON prev.match_id = curr.previous_match_id
                AND prev.team = curr.team
                AND prev.unit = curr.unit
                AND prev.player = curr.player
            GROUP BY
                curr.season,
                curr.league,
                curr.squad,
                curr.team,
                curr.opposition,
                curr.date,
                curr.match_id,
                curr.previous_match_id,
                curr.unit
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_rfu_average_retention AS
            SELECT
                season,
                league,
                squad,
                team,
                unit,
                AVG(retained) AS average_retention,
                COUNT(*) AS game_pairs
            FROM v_rfu_match_retention
            WHERE previous_match_id IS NOT NULL
              AND previous_lineup_available = 1
            GROUP BY season, league, squad, team, unit
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_rfu_lineup_coverage AS
            SELECT
                season,
                league,
                squad,
                team,
                COUNT(*) AS total_games,
                SUM(CASE WHEN lineup_available THEN 1 ELSE 0 END) AS games_with_lineups
            FROM v_rfu_team_games
            GROUP BY season, league, squad, team
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_pitchero_appearance_mismatches AS
            SELECT *
            FROM pitchero_appearance_reconciliation
            WHERE delta <> 0
            ORDER BY abs_delta DESC, season DESC, squad, player_join
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_season_player_appearances_reconciled AS
            SELECT
                squad,
                season,
                player_join,
                player,
                scraped_appearances,
                pitchero_appearances,
                CASE
                    WHEN delta > 0 THEN pitchero_appearances
                    ELSE scraped_appearances
                END AS effective_appearances,
                delta AS reconciliation_delta,
                delta > 0 AS adjusted_by_pitchero
            FROM pitchero_appearance_reconciliation
            """
        )

        self.con.execute(
            """
            CREATE VIEW v_player_appearance_discrepancy_summary AS
            SELECT
                player,
                player_join,
                SUM(pitchero_appearances) AS pitchero_appearances,
                SUM(scraped_appearances) AS scraped_appearances,
                SUM(delta) AS net_delta,
                SUM(abs_delta) AS total_abs_delta,
                SUM(CASE WHEN delta > 0 THEN delta ELSE 0 END) AS missing_from_scrape,
                SUM(CASE WHEN delta < 0 THEN -delta ELSE 0 END) AS excess_in_scrape,
                COUNT(*) FILTER (WHERE delta <> 0) AS seasons_with_mismatch
            FROM pitchero_appearance_reconciliation
            GROUP BY player, player_join
            HAVING SUM(abs_delta) > 0
            ORDER BY total_abs_delta DESC, net_delta DESC, player_join
            """
        )

    def query(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        return self.con.execute(sql, params or []).df()

    def export_tables(self) -> None:
        self.export_root.mkdir(parents=True, exist_ok=True)
        table_names = [
            "games",
            "games_rfu",
            "player_appearances",
            "player_appearances_rfu",
            "lineouts",
            "set_piece",
            "season_scorers",
            "players",
            "pitchero_appearance_reconciliation",
            "pitchero_appearance_backfill",
        ]
        view_names = [
            "v_season_results",
            "v_set_piece_summary",
            "v_lineout_summary",
            "v_player_profiles",
            "v_pitchero_appearance_mismatches",
            "v_season_player_appearances_reconciled",
            "v_player_appearance_discrepancy_summary",
            "v_rfu_team_games",
            "v_rfu_squad_size",
            "v_rfu_match_retention",
            "v_rfu_average_retention",
            "v_rfu_lineup_coverage",
        ]

        for name in table_names + view_names:
            df = self.con.execute(f"SELECT * FROM {name}").df()
            df.to_json(self.export_root / f"{name}.json", orient="records", date_format="iso")
            self.con.execute(
                f"COPY (SELECT * FROM {name}) TO '{(self.export_root / f'{name}.parquet').as_posix()}' (FORMAT PARQUET)"
            )

    def _insert(self, table_name: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        self.con.execute(f"INSERT INTO {table_name} SELECT * FROM df")

    def _load_pitchero(self, extractor: DataExtractor, refresh: bool) -> pd.DataFrame:
        expected_columns = ["Season", "Squad", "Player_join", "A", "Event", "Count"]

        if self.pitchero_cache_file.exists() and not refresh:
            cached = pd.read_json(self.pitchero_cache_file)
            if all(c in cached.columns for c in expected_columns):
                return cached[expected_columns]

        pitchero = extractor.extract_pitchero_stats()[expected_columns]
        self.pitchero_cache_file.parent.mkdir(parents=True, exist_ok=True)
        pitchero.to_json(self.pitchero_cache_file, orient="records")
        return pitchero

    def _load_historic_pitchero_team_sheets(
        self,
        extractor: DataExtractor,
        refresh_pitchero: bool,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        cache_games_cols = [
            "game_id",
            "date",
            "season",
            "squad",
            "competition",
            "game_type",
            "opposition",
            "home_away",
            "pf",
            "pa",
            "result",
            "margin",
            "captain",
            "vc1",
            "vc2",
        ]
        cache_apps_cols = [
            "appearance_id",
            "game_id",
            "player",
            "shirt_number",
            "position",
            "position_group",
            "unit",
            "is_starter",
            "is_captain",
            "is_vc",
            "player_join",
        ]

        if refresh_pitchero:
            games_df, apps_df = extractor.extract_pitchero_historic_team_sheets(
                seasons=sorted(HISTORIC_PITCHERO_SEASON_IDS.keys()),
                squads=(1, 2),
            )
            if not games_df.empty or not apps_df.empty:
                self._write_historic_pitchero_cache(games_df, apps_df)
            return games_df.reindex(columns=cache_games_cols), apps_df.reindex(columns=cache_apps_cols)

        if self.historic_pitchero_cache_file.exists():
            cached_games, cached_apps = self._read_historic_pitchero_cache()
            return cached_games.reindex(columns=cache_games_cols), cached_apps.reindex(columns=cache_apps_cols)

        boot_games, boot_apps = self._bootstrap_historic_cache_from_local_backend()
        if not boot_games.empty or not boot_apps.empty:
            self._write_historic_pitchero_cache(boot_games, boot_apps)
            return boot_games.reindex(columns=cache_games_cols), boot_apps.reindex(columns=cache_apps_cols)

        raise FileNotFoundError(
            "Historic Pitchero cache not found. Run with --refresh-pitchero once to create "
            f"{self.historic_pitchero_cache_file.as_posix()}"
        )

    def _read_historic_pitchero_cache(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        with self.historic_pitchero_cache_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        games = pd.DataFrame(payload.get("games", []))
        appearances = pd.DataFrame(payload.get("appearances", []))
        return games, appearances

    def _write_historic_pitchero_cache(self, games_df: pd.DataFrame, apps_df: pd.DataFrame) -> None:
        payload = {
            "games": games_df.to_dict(orient="records"),
            "appearances": apps_df.to_dict(orient="records"),
        }
        self.historic_pitchero_cache_file.parent.mkdir(parents=True, exist_ok=True)
        with self.historic_pitchero_cache_file.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def _bootstrap_historic_cache_from_local_backend(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        historic_seasons_sql = ", ".join([f"'{season}'" for season in HISTORIC_PITCHERO_SEASON_IDS.keys()])
        candidate_paths = [
            self.project_root / "data" / "egrfc_backend.duckdb",
            self.project_root / "data" / "egrfc_backend_reconcile.duckdb",
        ]

        for candidate in candidate_paths:
            if not candidate.exists() or candidate.resolve() == self.db_file.resolve():
                continue
            try:
                with duckdb.connect(str(candidate), read_only=True) as con:
                    games = con.execute(
                        f"""
                        SELECT
                            game_id,
                            CAST(date AS TEXT) AS date,
                            season,
                            squad,
                            competition,
                            game_type,
                            opposition,
                            home_away,
                            score_for AS pf,
                            score_against AS pa,
                            result,
                            ABS(score_for - score_against) AS margin,
                            captain,
                            vice_captain_1 AS vc1,
                            vice_captain_2 AS vc2
                        FROM games
                        WHERE season IN ({historic_seasons_sql})
                        """
                    ).df()

                    appearances = con.execute(
                        f"""
                        SELECT
                            CONCAT(game_id, '_', number) AS appearance_id,
                            game_id,
                            player,
                            number AS shirt_number,
                            position,
                            NULL::TEXT AS position_group,
                            unit,
                            is_starter,
                            is_captain,
                            is_vice_captain AS is_vc,
                            player AS player_join
                        FROM player_appearances
                        WHERE season IN ({historic_seasons_sql})
                        """
                    ).df()
                    if not appearances.empty:
                        appearances["player_join"] = appearances["player"].map(clean_name)
                    if not games.empty or not appearances.empty:
                        return games, appearances
            except Exception:
                continue

        return pd.DataFrame(), pd.DataFrame()

    def _extract_2526_scorers(self, extractor: DataExtractor) -> pd.DataFrame:
        spreadsheet = extractor.client.open_by_url(extractor.sheet_url)
        worksheet = spreadsheet.worksheet("25/26 Scorers")
        values = worksheet.get_all_values()
        if not values:
            return pd.DataFrame(columns=["Squad", "Date", "Opposition", "Score", "Player", "Points"])

        rows: list[dict[str, Any]] = []
        for row in values[1:]:
            if len(row) < 7:
                continue
            squad = row[1].strip()
            date = row[2].strip()
            opposition = row[3].strip()
            score = row[4].strip()
            player = row[5].strip()
            points = row[6].strip()
            if not squad or not player:
                continue
            rows.append(
                {
                    "Squad": squad,
                    "Date": date,
                    "Opposition": opposition,
                    "Score": score,
                    "Player": player,
                    "Points": points,
                }
            )

        return pd.DataFrame(rows)

    def _extract_lineouts(self, extractor: DataExtractor) -> pd.DataFrame:
        spreadsheet = extractor.client.open_by_url(extractor.sheet_url)
        rows: list[dict[str, Any]] = []
        for squad, sheet_name in [("1st", "1st XV Lineouts"), ("2nd", "2nd XV Lineouts")]:
            worksheet = spreadsheet.worksheet(sheet_name)
            values = worksheet.get_all_values()
            if len(values) <= 3:
                continue

            for idx, row in enumerate(values[3:], start=1):
                if len(row) < 18:
                    continue
                opposition = str(row[4]).strip()
                if not opposition:
                    continue
                call_raw = str(row[6]).strip()
                date_value = pd.to_datetime(row[3], errors="coerce", format="%Y-%m-%d")
                if pd.isna(date_value):
                    date_value = pd.to_datetime(row[3], errors="coerce", dayfirst=True)
                if pd.isna(date_value):
                    continue

                helper_row = {
                    "Front": str(row[8]).strip(),
                    "Middle": str(row[9]).strip(),
                    "Back": str(row[10]).strip(),
                }
                rows.append(
                    {
                        "lineout_id": f"{squad}_{date_value.date()}_{idx}",
                        "squad": squad,
                        "date": date_value.date(),
                        "season": str(row[2]).strip(),
                        "half": str(row[1]).strip(),
                        "opposition": opposition,
                        "numbers": str(row[5]).strip(),
                        "call": call_raw,
                        "call_type": extractor._classify_call(call_raw),
                        "dummy": str(row[7]).strip().lower() == "x",
                        "area": extractor._get_area(helper_row),
                        "drive": str(row[11]).strip().lower() == "x",
                        "crusaders": str(row[12]).strip().lower() == "x",
                        "transfer": str(row[13]).strip().lower() == "x",
                        "flyby": str(row[14]).strip() in {"1", "2", "x", "X"},
                        "hooker": str(row[15]).strip(),
                        "jumper": str(row[16]).strip(),
                        "won": str(row[17]).strip().upper() == "Y",
                    }
                )

        return pd.DataFrame(rows)

    def _build_games(self, games_raw: pd.DataFrame, appearances_raw: pd.DataFrame | None = None) -> pd.DataFrame:
        df = games_raw.copy()
        df["date"] = _safe_date(df["date"])
        historic_seasons = set(HISTORIC_PITCHERO_SEASON_IDS.keys())
        historic_mask = df["season"].isin(historic_seasons)
        df.loc[historic_mask, "opposition"] = df.loc[historic_mask, "opposition"].map(_canonical_pitchero_opposition_name)
        df["pf"] = pd.to_numeric(df["pf"], errors="coerce").astype("Int64")
        df["pa"] = pd.to_numeric(df["pa"], errors="coerce").astype("Int64")
        df["game_id"] = df["game_id"].astype(str)

        if appearances_raw is not None and not appearances_raw.empty and "game_id" in appearances_raw.columns:
            appearance_counts = appearances_raw["game_id"].astype(str).value_counts().to_dict()
            df["appearance_count"] = df["game_id"].map(appearance_counts).fillna(0).astype(int)
        else:
            df["appearance_count"] = 0

        df["has_score"] = (df["pf"].notna() & df["pa"].notna()).astype(int)
        df["has_result"] = df["result"].notna().astype(int)

        df = (
            df.dropna(subset=["squad", "date", "opposition"])
            .sort_values(
                ["squad", "date", "opposition", "has_score", "appearance_count", "has_result", "game_id"],
                ascending=[True, True, True, False, False, False, True],
            )
            .drop_duplicates(subset=["game_id"])
            .drop_duplicates(subset=["squad", "date", "opposition"])
        )
        return df[
            [
                "game_id",
                "squad",
                "date",
                "season",
                "competition",
                "game_type",
                "opposition",
                "home_away",
                "pf",
                "pa",
                "result",
                "captain",
                "vc1",
                "vc2",
            ]
        ].rename(
            columns={
                "pf": "score_for",
                "pa": "score_against",
                "vc1": "vice_captain_1",
                "vc2": "vice_captain_2",
            }
        )

    def _build_player_appearances(self, appearances_raw: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
        if appearances_raw.empty:
            return pd.DataFrame(
                columns=[
                    "squad",
                    "date",
                    "player",
                    "number",
                    "position",
                    "unit",
                    "is_captain",
                    "is_vice_captain",
                    "game_id",
                    "season",
                    "game_type",
                    "is_starter",
                ]
            )

        df = appearances_raw.copy()
        df = df.merge(games[["game_id", "squad", "date", "season", "game_type"]], on="game_id", how="left")
        df = df[df["player"].notna()]
        df["player"] = df["player"].map(_canonical_player_name)
        df["shirt_number"] = pd.to_numeric(df["shirt_number"], errors="coerce").astype("Int64")
        df["is_captain"] = df["is_captain"].fillna(False).astype(bool)
        df["is_vc"] = df["is_vc"].fillna(False).astype(bool)
        df["is_starter"] = df["is_starter"].fillna(False).astype(bool)
        df = df.dropna(subset=["squad", "date", "player"]).drop_duplicates(subset=["squad", "date", "player"])
        return df[
            [
                "squad",
                "date",
                "player",
                "shirt_number",
                "position",
                "unit",
                "is_captain",
                "is_vc",
                "game_id",
                "season",
                "game_type",
                "is_starter",
            ]
        ].rename(columns={"shirt_number": "number", "is_vc": "is_vice_captain"})

    def _build_lineouts(self, lineouts_raw: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
        if lineouts_raw.empty:
            return pd.DataFrame(
                columns=[
                    "squad",
                    "date",
                    "seq_id",
                    "half",
                    "numbers",
                    "call",
                    "call_type",
                    "dummy",
                    "area",
                    "drive",
                    "crusaders",
                    "transfer",
                    "flyby",
                    "thrower",
                    "jumper",
                    "won",
                    "game_id",
                    "season",
                    "opposition",
                ]
            )

        df = lineouts_raw.copy()
        df["date"] = _safe_date(df["date"])
        game_lookup = games[["game_id", "squad", "date", "season", "opposition"]].copy()
        game_lookup["opposition"] = game_lookup["opposition"].astype(str).str.strip()
        df["opposition"] = df["opposition"].astype(str).str.strip()
        df = df.merge(
            game_lookup,
            on=["squad", "date", "opposition", "season"],
            how="left",
            suffixes=("", "_game"),
        )
        df = df[df["squad"].notna() & df["date"].notna()].copy()
        df["dummy"] = df["dummy"].fillna(False).astype(bool)
        df["won"] = df["won"].fillna(False).astype(bool)
        df["drive"] = df["drive"].fillna(False).astype(bool)
        df["crusaders"] = df["crusaders"].fillna(False).astype(bool)
        df["transfer"] = df["transfer"].fillna(False).astype(bool)
        df["flyby"] = df["flyby"].fillna(False).astype(bool)
        df = df.sort_values(["squad", "date", "lineout_id"]).copy()
        df["seq_id"] = df.groupby(["squad", "date"]).cumcount() + 1
        return df[
            [
                "squad",
                "date",
                "seq_id",
                "half",
                "numbers",
                "call",
                "call_type",
                "dummy",
                "area",
                "drive",
                "crusaders",
                "transfer",
                "flyby",
                "hooker",
                "jumper",
                "won",
                "game_id",
                "season",
                "opposition",
            ]
        ].rename(columns={"hooker": "thrower"})

    def _build_set_piece(self, set_piece_raw: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
        if set_piece_raw.empty:
            return pd.DataFrame(
                columns=[
                    "squad",
                    "date",
                    "team",
                    "lineouts_won",
                    "lineouts_total",
                    "lineouts_success_rate",
                    "scrums_won",
                    "scrums_total",
                    "scrums_success_rate",
                    "entries_22m",
                    "points_per_22m_entry",
                    "tries_per_22m_entry",
                    "game_id",
                    "season",
                    "opposition",
                ]
            )

        merged = set_piece_raw.merge(games[["game_id", "squad", "date", "season", "opposition"]], on="game_id", how="left")
        merged = merged[merged["squad"].notna()]

        lineouts = merged[merged["set_piece"].eq("Lineout")].copy()
        lineouts = lineouts.rename(columns={"won": "lineouts_won", "total": "lineouts_total"})
        scrums = merged[merged["set_piece"].eq("Scrum")].copy()
        scrums = scrums.rename(columns={"won": "scrums_won", "total": "scrums_total"})

        key = ["squad", "date", "team", "game_id", "season", "opposition"]
        df = lineouts[key + ["lineouts_won", "lineouts_total"]].merge(
            scrums[key + ["scrums_won", "scrums_total"]], on=key, how="outer"
        )
        df["team"] = df["team"].replace({"EG": "EGRFC", "Opp": "Opposition"})

        df["lineouts_won"] = pd.to_numeric(df["lineouts_won"], errors="coerce").fillna(0).astype(int)
        df["lineouts_total"] = pd.to_numeric(df["lineouts_total"], errors="coerce").fillna(0).astype(int)
        df["scrums_won"] = pd.to_numeric(df["scrums_won"], errors="coerce").fillna(0).astype(int)
        df["scrums_total"] = pd.to_numeric(df["scrums_total"], errors="coerce").fillna(0).astype(int)
        df["lineouts_success_rate"] = (df["lineouts_won"] / df["lineouts_total"].replace(0, pd.NA)).fillna(0.0)
        df["scrums_success_rate"] = (df["scrums_won"] / df["scrums_total"].replace(0, pd.NA)).fillna(0.0)
        df["entries_22m"] = pd.NA
        df["points_per_22m_entry"] = pd.NA
        df["tries_per_22m_entry"] = pd.NA

        return df[
            [
                "squad",
                "date",
                "team",
                "lineouts_won",
                "lineouts_total",
                "lineouts_success_rate",
                "scrums_won",
                "scrums_total",
                "scrums_success_rate",
                "entries_22m",
                "points_per_22m_entry",
                "tries_per_22m_entry",
                "game_id",
                "season",
                "opposition",
            ]
        ].drop_duplicates(subset=["squad", "date", "team"])

    def _build_season_scorers(
        self,
        scorers_2526_raw: pd.DataFrame,
        pitchero_raw: pd.DataFrame,
        appearances: pd.DataFrame,
    ) -> pd.DataFrame:
        scorer_type_map = {
            "TRY": "tries",
            "T": "tries",
            "CON": "conversions",
            "CONVERSION": "conversions",
            "PK": "penalties",
            "PEN": "penalties",
            "PENALTY": "penalties",
            "DG": "drop_goals",
            "DROP GOAL": "drop_goals",
        }

        df_2526 = scorers_2526_raw.copy()
        if not df_2526.empty:
            df_2526 = df_2526.rename(
                columns={
                    "Squad": "squad",
                    "Date": "date",
                    "Opposition": "opposition",
                    "Score": "score_type",
                    "Player": "player",
                    "Points": "points",
                }
            )
            df_2526["season"] = "2025/26"
            df_2526["score_type"] = df_2526["score_type"].fillna("").astype(str).str.strip().str.upper()
            df_2526["metric"] = df_2526["score_type"].map(scorer_type_map)
            df_2526 = df_2526[df_2526["metric"].notna()]

            agg_2526 = (
                df_2526.pivot_table(
                    index=["squad", "season", "player"],
                    columns="metric",
                    values="points",
                    aggfunc="count",
                    fill_value=0,
                )
                .reset_index()
                .rename_axis(None, axis=1)
            )
            for col in ["tries", "conversions", "penalties", "drop_goals"]:
                if col not in agg_2526.columns:
                    agg_2526[col] = 0
            agg_2526["points"] = (
                agg_2526["tries"] * 5
                + agg_2526["conversions"] * 2
                + agg_2526["penalties"] * 3
                + agg_2526["drop_goals"] * 3
            )
            agg_2526["source"] = "google_2526"
        else:
            agg_2526 = pd.DataFrame(columns=["squad", "season", "player", "tries", "conversions", "penalties", "drop_goals", "points", "source"])

        pitchero = pitchero_raw.copy()
        pitchero = pitchero.rename(columns={"Season": "season", "Squad": "squad", "Player_join": "player_join", "Event": "event", "Count": "count"})
        pitchero = pitchero[pitchero["season"] != "2025/26"]
        pitchero = pitchero[pitchero["event"].isin(["T", "Con", "PK", "DG"])]
        join_lookup = appearances[["player"]].drop_duplicates().copy()
        join_lookup["player_join"] = join_lookup["player"].map(clean_name)
        join_lookup = join_lookup.drop_duplicates(subset=["player_join"]) 
        pitchero = pitchero.merge(join_lookup, on="player_join", how="left")
        pitchero["player"] = pitchero["player"].fillna(pitchero["player_join"])

        pivot = (
            pitchero.pivot_table(
                index=["squad", "season", "player"],
                columns="event",
                values="count",
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )

        for source_col, target_col in [("T", "tries"), ("Con", "conversions"), ("PK", "penalties"), ("DG", "drop_goals")]:
            if source_col not in pivot.columns:
                pivot[source_col] = 0
            pivot[target_col] = pivot[source_col]

        pivot["points"] = pivot["tries"] * 5 + pivot["conversions"] * 2 + pivot["penalties"] * 3 + pivot["drop_goals"] * 3
        pivot["source"] = "pitchero"
        pitchero_out = pivot[["squad", "season", "player", "tries", "conversions", "penalties", "drop_goals", "points", "source"]]

        out = pd.concat([pitchero_out, agg_2526], ignore_index=True)
        for col in ["tries", "conversions", "penalties", "drop_goals", "points"]:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
        return out.groupby(["squad", "season", "player"], as_index=False).agg(
            tries=("tries", "sum"),
            conversions=("conversions", "sum"),
            penalties=("penalties", "sum"),
            drop_goals=("drop_goals", "sum"),
            points=("points", "sum"),
            source=("source", lambda s: "+".join(sorted(set(s)))),
        )

    def _build_players(
        self,
        appearances: pd.DataFrame,
        games: pd.DataFrame,
        lineouts: pd.DataFrame,
        season_scorers: pd.DataFrame,
        reconciliation: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if appearances.empty:
            return pd.DataFrame(
                columns=[
                    "name",
                    "short_name",
                    "position",
                    "squad",
                    "first_appearance_date",
                    "first_appearance_squad",
                    "first_appearance_opposition",
                    "photo_url",
                    "sponsor",
                    "total_appearances",
                    "total_starts",
                    "total_captaincies",
                    "total_vc_appointments",
                    "total_lineouts_jumped",
                    "lineouts_won_as_jumper",
                    "career_points",
                ]
            )

        base = appearances.copy()
        base = base.merge(games[["game_id", "opposition"]], on="game_id", how="left")
        base = base.sort_values(["player", "date"])

        first = base.groupby("player", as_index=False).first()[["player", "date", "squad", "opposition"]]
        first = first.rename(
            columns={
                "player": "name",
                "date": "first_appearance_date",
                "squad": "first_appearance_squad",
                "opposition": "first_appearance_opposition",
            }
        )

        agg = base.groupby("player", as_index=False).agg(
            short_name=("player", lambda s: str(s.iloc[0]).replace(" ", " ", 1)),
            position=("position", _mode_or_none),
            squad=("squad", lambda s: _mode_or_none(s) if s.nunique() == 1 else "Both"),
            total_appearances=("game_id", "count"),
            total_starts=("is_starter", "sum"),
            total_captaincies=("is_captain", "sum"),
            total_vc_appointments=("is_vice_captain", "sum"),
        ).rename(columns={"player": "name"})

        jumper = lineouts.groupby("jumper", as_index=False).agg(
            total_lineouts_jumped=("won", "count"),
            lineouts_won_as_jumper=("won", "sum"),
        ).rename(columns={"jumper": "name"})

        points = season_scorers.groupby("player", as_index=False).agg(career_points=("points", "sum")).rename(columns={"player": "name"})

        players = agg.merge(first, on="name", how="left").merge(jumper, on="name", how="left").merge(points, on="name", how="left")

        if reconciliation is not None and not reconciliation.empty:
            historic_seasons = set(HISTORIC_PITCHERO_SEASON_IDS.keys())

            modern_apps = appearances[~appearances["season"].isin(historic_seasons)].copy()
            modern_apps = (
                modern_apps.groupby("player", as_index=False)
                .agg(modern_appearances=("game_id", "count"))
                .rename(columns={"player": "name"})
            )

            historic = reconciliation[reconciliation["season"].isin(historic_seasons)].copy()
            historic["effective_appearances"] = historic.apply(
                lambda row: row["pitchero_appearances"] if row["pitchero_appearances"] > 0 else row["scraped_appearances"],
                axis=1,
            )
            historic_apps = (
                historic.groupby("player", as_index=False)
                .agg(historic_appearances=("effective_appearances", "sum"))
                .rename(columns={"player": "name"})
            )

            corrected_apps = modern_apps.merge(historic_apps, on="name", how="outer")
            corrected_apps["modern_appearances"] = pd.to_numeric(
                corrected_apps["modern_appearances"], errors="coerce"
            ).fillna(0)
            corrected_apps["historic_appearances"] = pd.to_numeric(
                corrected_apps["historic_appearances"], errors="coerce"
            ).fillna(0)
            corrected_apps["corrected_total_appearances"] = (
                corrected_apps["modern_appearances"] + corrected_apps["historic_appearances"]
            ).astype(int)

            players = players.merge(
                corrected_apps[["name", "corrected_total_appearances"]],
                on="name",
                how="left",
            )
            players["total_appearances"] = players["corrected_total_appearances"].fillna(players["total_appearances"]).astype(int)
            players = players.drop(columns=["corrected_total_appearances"])

        players["short_name"] = players["name"].map(self._short_name)
        players["photo_url"] = players["name"].map(self._photo_for_player)
        players["sponsor"] = players["name"].map(self._sponsor_for_player)
        for c in ["total_lineouts_jumped", "lineouts_won_as_jumper", "career_points"]:
            players[c] = players[c].fillna(0).astype(int)

        return players[
            [
                "name",
                "short_name",
                "position",
                "squad",
                "first_appearance_date",
                "first_appearance_squad",
                "first_appearance_opposition",
                "photo_url",
                "sponsor",
                "total_appearances",
                "total_starts",
                "total_captaincies",
                "total_vc_appointments",
                "total_lineouts_jumped",
                "lineouts_won_as_jumper",
                "career_points",
            ]
        ].drop_duplicates(subset=["name"])

    def _build_pitchero_appearance_reconciliation(
        self,
        pitchero_raw: pd.DataFrame,
        appearances: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        empty_reconciliation = pd.DataFrame(
            columns=[
                "squad",
                "season",
                "player_join",
                "player",
                "pitchero_appearances",
                "scraped_appearances",
                "delta",
                "abs_delta",
                "status",
                "fix_type",
            ]
        )
        empty_backfill = pd.DataFrame(
            columns=["squad", "season", "player_join", "player", "missing_appearances", "applied_fix"]
        )

        if pitchero_raw.empty:
            return empty_reconciliation, empty_backfill

        pitchero = pitchero_raw.copy()
        pitchero = pitchero.rename(columns={"Season": "season", "Squad": "squad", "Player_join": "player_join", "A": "A"})
        historic_seasons = set(HISTORIC_PITCHERO_SEASON_IDS.keys())
        pitchero = pitchero[pitchero["season"].isin(historic_seasons)].copy()
        if pitchero.empty:
            return empty_reconciliation, empty_backfill
        pitchero["A"] = pd.to_numeric(pitchero["A"], errors="coerce").fillna(0).astype(int)
        pitchero = (
            pitchero.groupby(["squad", "season", "player_join"], as_index=False)
            .agg(pitchero_appearances=("A", "max"))
        )

        scraped = appearances.copy()
        if scraped.empty:
            reconciliation = pitchero.copy()
            reconciliation["player"] = reconciliation["player_join"]
            reconciliation["scraped_appearances"] = 0
        else:
            scraped["player"] = scraped["player"].map(_canonical_player_name)
            scraped["player_join"] = scraped["player"].map(clean_name)

            preferred_name_lookup = (
                scraped.groupby("player_join", as_index=False)
                .agg(player=("player", _mode_or_none))
                .set_index("player_join")["player"]
                .to_dict()
            )

            scraped = scraped[scraped["season"].isin(historic_seasons)].copy()
            if scraped.empty:
                reconciliation = pitchero.copy()
                reconciliation["player"] = reconciliation["player_join"].map(
                    lambda pj: preferred_name_lookup.get(pj, pj)
                )
                reconciliation["scraped_appearances"] = 0
                reconciliation["pitchero_appearances"] = (
                    pd.to_numeric(reconciliation["pitchero_appearances"], errors="coerce").fillna(0).astype(int)
                )
                reconciliation["delta"] = reconciliation["pitchero_appearances"]
                reconciliation["abs_delta"] = reconciliation["delta"].abs()
                reconciliation["status"] = "missing_scraped_player"
                reconciliation["fix_type"] = "season_count_backfill"
                backfill = reconciliation[["squad", "season", "player_join", "player", "delta"]].copy()
                backfill = backfill.rename(columns={"delta": "missing_appearances"})
                backfill["applied_fix"] = True
                backfill["missing_appearances"] = backfill["missing_appearances"].astype(int)
                return reconciliation[
                    [
                        "squad",
                        "season",
                        "player_join",
                        "player",
                        "pitchero_appearances",
                        "scraped_appearances",
                        "delta",
                        "abs_delta",
                        "status",
                        "fix_type",
                    ]
                ], backfill

            scraped = (
                scraped.groupby(["squad", "season", "player_join"], as_index=False)
                .agg(
                    player=("player", _mode_or_none),
                    scraped_appearances=("game_id", "count"),
                )
            )

            reconciliation = pitchero.merge(scraped, on=["squad", "season", "player_join"], how="outer")
            reconciliation["player"] = reconciliation.apply(
                lambda row: row["player"]
                if pd.notna(row["player"]) and str(row["player"]).strip()
                else preferred_name_lookup.get(row["player_join"], row["player_join"]),
                axis=1,
            )
            reconciliation["pitchero_appearances"] = (
                pd.to_numeric(reconciliation["pitchero_appearances"], errors="coerce").fillna(0).astype(int)
            )
            reconciliation["scraped_appearances"] = (
                pd.to_numeric(reconciliation["scraped_appearances"], errors="coerce").fillna(0).astype(int)
            )

        reconciliation["delta"] = reconciliation["pitchero_appearances"] - reconciliation["scraped_appearances"]
        reconciliation["abs_delta"] = reconciliation["delta"].abs()

        reconciliation["status"] = "matched"
        reconciliation.loc[
            (reconciliation["delta"] > 0) & (reconciliation["scraped_appearances"] == 0),
            "status",
        ] = "missing_scraped_player"
        reconciliation.loc[
            (reconciliation["delta"] > 0) & (reconciliation["scraped_appearances"] > 0),
            "status",
        ] = "under_counted_scraped"
        reconciliation.loc[reconciliation["delta"] < 0, "status"] = "over_counted_scraped"

        reconciliation["fix_type"] = "none"
        reconciliation.loc[reconciliation["delta"] > 0, "fix_type"] = "season_count_backfill"
        reconciliation.loc[reconciliation["delta"] < 0, "fix_type"] = "investigate_duplicate_or_mapping"

        reconciliation = reconciliation[
            [
                "squad",
                "season",
                "player_join",
                "player",
                "pitchero_appearances",
                "scraped_appearances",
                "delta",
                "abs_delta",
                "status",
                "fix_type",
            ]
        ].sort_values(["abs_delta", "season", "squad", "player_join"], ascending=[False, False, True, True])

        backfill = reconciliation[reconciliation["delta"] > 0][
            ["squad", "season", "player_join", "player", "delta"]
        ].copy()
        if backfill.empty:
            return reconciliation, empty_backfill

        backfill = backfill.rename(columns={"delta": "missing_appearances"})
        backfill["applied_fix"] = True
        backfill["missing_appearances"] = backfill["missing_appearances"].astype(int)
        return reconciliation, backfill

    def _short_name(self, full_name: str) -> str:
        parts = str(full_name).strip().split()
        if len(parts) < 2:
            return full_name
        return f"{parts[0]} {parts[-1][0]}"

    def _photo_for_player(self, player_name: str) -> str | None:
        headshots_dir = self.project_root / "img" / "headshots"
        if not headshots_dir.exists():
            return None
        key = _normalise_key(player_name)
        for photo_file in headshots_dir.glob("*.*"):
            if _normalise_key(photo_file.stem) == key:
                return f"img/headshots/{photo_file.name}"
        return None

    def _sponsor_for_player(self, player_name: str) -> str | None:
        sponsor_path = self.project_root / "data" / "sponsors.json"
        if not sponsor_path.exists():
            return None
        with sponsor_path.open("r", encoding="utf-8") as handle:
            sponsors = json.load(handle)

        seasons = sorted(sponsors.keys(), reverse=True)
        for season in seasons:
            season_data = sponsors.get(season, {})
            if player_name in season_data:
                return season_data[player_name]
        return None


def build_backend(
    refresh_pitchero: bool = False,
    export: bool = True,
    db_path: str | None = None,
    export_dir: str | None = None,
) -> None:
    config = BackendConfig(
        db_path=db_path or BackendConfig.db_path,
        export_dir=export_dir or BackendConfig.export_dir,
    )
    backend = BackendDatabase(config=config)
    try:
        backend.build(refresh_pitchero=refresh_pitchero, export=export)
    finally:
        backend.close()


if __name__ == "__main__":
    refresh = os.getenv("EGRFC_REFRESH_PITCHERO", "false").lower() in {"1", "true", "yes"}
    build_backend(refresh_pitchero=refresh, export=True)