"""Canonical data backend for EGRFC stats.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
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
    "Alistair Moffatt": "Ali Moffatt",
    "Bertram Beanland": "Bertie Beanland",
}

PITCHERO_OPPOSITION_CANONICAL_NAMES = {
    "brighton3": "Brighton III",
    "bognor2": "Bognor II",
    "burgesshill2": "Burgess Hill II",
    "burgesshill": "Burgess Hill",
    "crawleycupfinal": "Crawley",
    "crawley2s3s": "Crawley II",
    "ditchlingrfc": "Ditchling",
    "ditchling": "Ditchling",
    "eastbourneiirfc": "Eastbourne II",
    "eastbourne2": "Eastbourne II",
    "eastbourne2s": "Eastbourne II",
    "eastbourneiirfc": "Eastbourne II",
    "haywardsheath2xv": "Haywards Heath II",
    "haywardsheath2xy": "Haywards Heath II",
    "heathfield2": "Heathfield II",
    "heathfield3s": "Heathfield III",
    "heathfieldwaldron3": "Heathfield & Waldron III",
    "hellingly2": "Hellingly II",
    "hove2": "Hove II",
    "hove2xv": "Hove II",
    "hove2xy": "Hove II",
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


def _normalise_dates_for_json(df: pd.DataFrame) -> pd.DataFrame:
    """Render all date-like values as YYYY-MM-DD strings for JSON exports."""
    if df.empty:
        return df

    normalized = df.copy()
    for column in normalized.columns:
        series = normalized[column]

        if pd.api.types.is_datetime64_any_dtype(series):
            normalized[column] = series.dt.strftime("%Y-%m-%d").where(series.notna(), None)
            continue

        if series.dtype == "object":
            # Handle Python date/datetime objects and ISO datetime strings in object columns.
            if series.map(lambda value: isinstance(value, (date, datetime))).any():
                normalized[column] = series.map(
                    lambda value: value.strftime("%Y-%m-%d") if isinstance(value, (date, datetime)) else value
                )
            elif str(column).lower() == "date" or str(column).lower().endswith("_date"):
                parsed = pd.to_datetime(series, errors="coerce")
                if parsed.notna().any():
                    normalized[column] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), series)

    return normalized


def _yes_no_to_bool(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.upper().isin(["Y", "YES", "TRUE", "X", "1"])


def _normalise_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _season_sort_key(season: Any) -> tuple[int, str]:
    season_text = str(season or "").strip()
    match = re.match(r"^(\d{4})-(\d{4})$", season_text)
    if match:
        return (int(match.group(1)), season_text)
    return (-1, season_text)


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
        self.con.execute("DROP VIEW IF EXISTS v_red_zone")
        self.con.execute("DROP VIEW IF EXISTS v_lineout_summary")
        self.con.execute("DROP VIEW IF EXISTS v_set_piece_summary")
        self.con.execute("DROP VIEW IF EXISTS v_season_results")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_lineup_coverage")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_average_retention")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_match_retention")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_squad_size")
        self.con.execute("DROP VIEW IF EXISTS v_rfu_team_games")
        self.con.execute("DROP TABLE IF EXISTS squad_continuity_enriched")
        self.con.execute("DROP TABLE IF EXISTS squad_position_profiles_enriched")
        self.con.execute("DROP TABLE IF EXISTS squad_stats_enriched")
        self.con.execute("DROP TABLE IF EXISTS squad_stats_with_thresholds_enriched")
        self.con.execute("DROP TABLE IF EXISTS season_summary_enriched")
        self.con.execute("DROP TABLE IF EXISTS player_profiles_canonical")
        self.con.execute("DROP TABLE IF EXISTS pitchero_appearance_backfill")
        self.con.execute("DROP TABLE IF EXISTS pitchero_appearance_reconciliation")
        self.con.execute("DROP TABLE IF EXISTS player_profiles_enriched")
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
                tries_scorers TEXT,
                conversions_scorers TEXT,
                penalties_scorers TEXT,
                drop_goals_scorers TEXT,
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
                is_backfill BOOLEAN DEFAULT FALSE,
                club_appearance_number INTEGER,
                first_xv_appearance_number INTEGER,
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
                points INTEGER,
                tries INTEGER,
                points_per_entry DOUBLE,
                tries_per_entry DOUBLE,
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
                game_type TEXT,
                tries BIGINT,
                conversions BIGINT,
                penalties BIGINT,
                drop_goals BIGINT,
                points BIGINT,
                source TEXT,
                PRIMARY KEY(squad, season, player, game_type)
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

        self.con.execute(
            """
            CREATE TABLE squad_stats_enriched (
                season TEXT NOT NULL,
                gameTypeMode TEXT NOT NULL,
                squad TEXT NOT NULL,
                unit TEXT NOT NULL,
                playerCounts TEXT,
                playersUsed INTEGER,
                PRIMARY KEY(season, gameTypeMode, squad, unit)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE squad_position_profiles_enriched (
                season TEXT NOT NULL,
                gameTypeMode TEXT NOT NULL,
                squad TEXT NOT NULL,
                position TEXT NOT NULL,
                playerCounts TEXT,
                playersUsed INTEGER,
                PRIMARY KEY(season, gameTypeMode, squad, position)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE squad_continuity_enriched (
                season TEXT NOT NULL,
                gameTypeMode TEXT NOT NULL,
                squad TEXT NOT NULL,
                unit TEXT NOT NULL,
                retained DOUBLE,
                gamePairs INTEGER,
                PRIMARY KEY(season, gameTypeMode, squad, unit)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE squad_stats_with_thresholds_enriched (
                season TEXT NOT NULL,
                gameTypeMode TEXT NOT NULL,
                squad TEXT NOT NULL,
                unit TEXT NOT NULL,
                minimumAppearances INTEGER NOT NULL,
                playerCount INTEGER,
                totalPlayed INTEGER,
                PRIMARY KEY(season, gameTypeMode, squad, unit, minimumAppearances)
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE player_profiles_canonical (
                name TEXT PRIMARY KEY,
                short_name TEXT,
                squad TEXT,
                position TEXT,
                photo_url TEXT,
                sponsor TEXT,
                totalAppearances INTEGER,
                totalStarts INTEGER,
                firstXVAppearances INTEGER,
                firstXVStarts INTEGER,
                seasonAppearances INTEGER,
                seasonStarts INTEGER,
                seasonCompetitiveAppearances INTEGER,
                scoringCareer TEXT,
                scoringThisSeason TEXT,
                debutOverall TEXT,
                debutFirstXV TEXT,
                hasDifferentFirstXVDebut BOOLEAN,
                otherPositions TEXT,
                isActive BOOLEAN,
                lastAppearanceDate DATE
            )
            """
        )

        self.con.execute(
            """
            CREATE TABLE season_summary_enriched (
                season TEXT NOT NULL,
                gameTypeMode TEXT NOT NULL,
                squad TEXT NOT NULL,
                gamesPlayed INTEGER,
                gamesWon INTEGER,
                gamesLost INTEGER,
                gamesDrawn INTEGER,
                avgPointsForHome DOUBLE,
                avgPointsAgainstHome DOUBLE,
                avgPointsForAway DOUBLE,
                avgPointsAgainstAway DOUBLE,
                avgPointsForOverall DOUBLE,
                avgPointsAgainstOverall DOUBLE,
                topPointScorerValue BIGINT,
                topPointScorerPlayers TEXT,
                topTryScorerValue BIGINT,
                topTryScorerPlayers TEXT,
                topAppearanceValue INTEGER,
                topAppearancePlayers TEXT,
                avgLineoutSuccessRate DOUBLE,
                avgScrumSuccessRate DOUBLE,
                avgPointsPer22mEntry DOUBLE,
                avgTriesPer22mEntry DOUBLE,
                gamesWithSetPieceData INTEGER,
                PRIMARY KEY(season, gameTypeMode, squad)
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
        games = self._attach_match_scorers(games, scorers_2526_raw)
        appearances = self._build_player_appearances(appearances_raw, games)
        lineouts = self._build_lineouts(lineouts_raw, games)
        set_piece = self._build_set_piece(set_piece_raw, games)
        season_scorers = self._build_season_scorers(scorers_2526_raw, pitchero_raw, appearances, games)
        reconciliation, backfill = self._build_pitchero_appearance_reconciliation(pitchero_raw, appearances)
        appearances = self._apply_backfill_to_appearances(appearances, backfill, reconciliation)
        appearances = self._annotate_appearance_numbers(appearances)
        players = self._build_players(appearances, games, lineouts, season_scorers)
        player_profiles_base = self._build_player_profiles_base(players, appearances, games, season_scorers)
        squad_stats_enriched = self._build_squad_stats(appearances, games)
        squad_position_profiles_enriched = self._build_squad_position_profiles(appearances, games)
        squad_continuity_enriched = self._build_squad_continuity(appearances, games)
        squad_stats_with_thresholds_enriched = self._build_squad_stats_with_thresholds(appearances, games)
        player_profiles_canonical = self._build_player_profiles_canonical(player_profiles_base)
        season_summary_enriched = self._build_season_summary(games, appearances, season_scorers, set_piece)
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
        self._insert("squad_stats_enriched", squad_stats_enriched)
        self._insert("squad_position_profiles_enriched", squad_position_profiles_enriched)
        self._insert("squad_continuity_enriched", squad_continuity_enriched)
        self._insert("squad_stats_with_thresholds_enriched", squad_stats_with_thresholds_enriched)
        self._insert("player_profiles_canonical", player_profiles_canonical)
        self._insert("season_summary_enriched", season_summary_enriched)
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
            CREATE VIEW v_red_zone AS
            SELECT
                sp.game_id,
                sp.season,
                sp.squad,
                sp.date,
                sp.opposition,
                g.game_type,
                sp.team,
                sp.entries_22m,
                sp.tries,
                sp.points,
                sp.tries_per_entry,
                sp.points_per_entry
            FROM set_piece sp
            LEFT JOIN games g ON sp.game_id = g.game_id
            WHERE sp.entries_22m IS NOT NULL
            ORDER BY sp.date DESC, sp.squad, sp.team
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
        
        # Map of table/view names to their JSON columns and default values
        # Schema: {table_name: {column_name: default_value_type}}
        # - default_value_type: 'object' ({}) or 'array' ([])
        json_columns_map = {
            "games": {
                "tries_scorers": "object",
                "conversions_scorers": "object",
                "penalties_scorers": "object",
                "drop_goals_scorers": "object",
            },
            "squad_stats_enriched": {
                "playerCounts": "object",
            },
            "squad_position_profiles_enriched": {
                "playerCounts": "object",
            },
            "squad_continuity_enriched": {
                # Add any JSON columns here in future
            },
            "player_profiles_canonical": {
                "scoringCareer": "object",
                "scoringThisSeason": "object",
                "otherPositions": "array",
            },
            "season_summary_enriched": {
                "topPointScorerPlayers": "array",
                "topTryScorerPlayers": "array",
                "topAppearancePlayers": "array",
            },
        }
        
        table_names = [
            "games",
            "games_rfu",
            "player_appearances",
            "player_appearances_rfu",
            "lineouts",
            "set_piece",
            "season_scorers",
            "players",
            "season_summary_enriched",
            "squad_stats_enriched",
            "squad_position_profiles_enriched",
            "squad_continuity_enriched",
            "squad_stats_with_thresholds_enriched",
            "player_profiles_canonical",
            "pitchero_appearance_reconciliation",
            "pitchero_appearance_backfill",
        ]
        view_names = [
            "v_season_results",
            "v_pitchero_appearance_mismatches",
            "v_season_player_appearances_reconciled",
            "v_player_appearance_discrepancy_summary",
            "v_rfu_team_games",
            "v_rfu_squad_size",
            "v_rfu_match_retention",
            "v_rfu_average_retention",
            "v_rfu_lineup_coverage",
            "v_red_zone",
        ]

        for name in table_names + view_names:
            df = self.con.execute(f"SELECT * FROM {name}").df()
            export_df = _normalise_dates_for_json(df)
            
            # Deserialize JSON columns if this table has any registered
            if name in json_columns_map and not export_df.empty:
                for col, default_type in json_columns_map[name].items():
                    if col in export_df.columns:
                        default_value = [] if default_type == "array" else {}
                        export_df[col] = export_df[col].apply(
                            lambda value: json.loads(value) if isinstance(value, str) and value.strip() else default_value
                        )
            
            export_df.to_json(self.export_root / f"{name}.json", orient="records")
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
            return pd.DataFrame(columns=["Squad", "Date", "Opposition", "Score", "Count", "Player", "Points"])

        header = [str(cell).strip() for cell in values[0]]
        normalised_to_idx = {
            _normalise_key(column): idx
            for idx, column in enumerate(header)
            if str(column).strip()
        }

        def _col_idx(*candidates: str) -> int | None:
            for candidate in candidates:
                idx = normalised_to_idx.get(_normalise_key(candidate))
                if idx is not None:
                    return idx
            return None

        squad_idx = _col_idx("Squad")
        date_idx = _col_idx("Date")
        opposition_idx = _col_idx("Opposition")
        score_idx = _col_idx("Score", "Type")
        count_idx = _col_idx("Count")
        player_idx = _col_idx("Scorer", "Player")
        points_idx = _col_idx("Points")

        def _cell(row: list[Any], idx: int | None, fallback_idx: int | None = None) -> str:
            for candidate in [idx, fallback_idx]:
                if candidate is None:
                    continue
                if 0 <= candidate < len(row):
                    return str(row[candidate]).strip()
            return ""

        rows: list[dict[str, Any]] = []
        for row in values[1:]:
            if not row:
                continue

            # Positional fallbacks preserve legacy 25/26 sheet compatibility.
            squad = _cell(row, squad_idx, fallback_idx=1)
            date = _cell(row, date_idx, fallback_idx=2)
            opposition = _cell(row, opposition_idx, fallback_idx=3)
            score = _cell(row, score_idx, fallback_idx=4)
            count_raw = _cell(row, count_idx, fallback_idx=5)
            player = _cell(row, player_idx, fallback_idx=6 if count_idx is None else None)
            points = _cell(row, points_idx, fallback_idx=7 if count_idx is not None else 6)

            if not squad or not player:
                continue

            count = pd.to_numeric(count_raw, errors="coerce")
            count = int(count) if pd.notna(count) and int(count) > 0 else 1

            rows.append(
                {
                    "Squad": squad,
                    "Date": date,
                    "Opposition": opposition,
                    "Score": score,
                    "Count": count,
                    "Player": player,
                    "Points": points,
                }
            )

        return pd.DataFrame(rows)

    def _attach_match_scorers(self, games: pd.DataFrame, scorers_2526_raw: pd.DataFrame) -> pd.DataFrame:
        games_with_scorers = games.copy()
        scorer_columns = [
            "tries_scorers",
            "conversions_scorers",
            "penalties_scorers",
            "drop_goals_scorers",
        ]
        for col in scorer_columns:
            if col not in games_with_scorers.columns:
                games_with_scorers[col] = None

        if scorers_2526_raw.empty:
            return games_with_scorers

        scorers = scorers_2526_raw.copy().rename(
            columns={
                "Squad": "squad",
                "Date": "date",
                "Opposition": "opposition",
                "Score": "score_type",
                "Scorer": "player",
                "Player": "player",
                "Count": "count",
            }
        )
        required = {"squad", "date", "opposition", "score_type", "player"}
        if not required.issubset(set(scorers.columns)):
            return games_with_scorers

        scorers["date"] = _safe_date(scorers["date"])
        scorers["opposition"] = scorers["opposition"].astype(str).str.strip()
        scorers["score_type"] = scorers["score_type"].astype(str).str.strip().str.upper()
        scorers["player"] = scorers["player"].astype(str).str.strip()
        scorers["count"] = pd.to_numeric(scorers.get("count", 1), errors="coerce").fillna(1).astype(int)
        scorers = scorers[(scorers["player"] != "") & (scorers["count"] > 0)]
        if scorers.empty:
            return games_with_scorers

        scorer_type_to_column = {
            "TRY": "tries_scorers",
            "T": "tries_scorers",
            "CON": "conversions_scorers",
            "CONVERSION": "conversions_scorers",
            "PK": "penalties_scorers",
            "PEN": "penalties_scorers",
            "PENALTY": "penalties_scorers",
            "DG": "drop_goals_scorers",
            "DROP GOAL": "drop_goals_scorers",
        }
        scorers["target_column"] = scorers["score_type"].map(scorer_type_to_column)
        scorers = scorers[scorers["target_column"].notna()]
        if scorers.empty:
            return games_with_scorers

        keyed_games = games_with_scorers[["game_id", "squad", "date", "opposition"]].copy()
        keyed_games["date"] = _safe_date(keyed_games["date"])
        keyed_games["opposition"] = keyed_games["opposition"].astype(str).str.strip()

        scored = scorers.merge(
            keyed_games,
            on=["squad", "date", "opposition"],
            how="left",
        )
        scored = scored[scored["game_id"].notna()]
        if scored.empty:
            return games_with_scorers

        grouped = scored.groupby(["game_id", "target_column", "player"], as_index=False).agg(count=("count", "sum"))
        if grouped.empty:
            return games_with_scorers

        per_game: dict[str, dict[str, dict[str, int]]] = {}
        for row in grouped.itertuples(index=False):
            game_bucket = per_game.setdefault(str(row.game_id), {})
            category_bucket = game_bucket.setdefault(str(row.target_column), {})
            category_bucket[str(row.player)] = int(row.count)

        payload_rows: list[dict[str, Any]] = []
        for game_id, category_payload in per_game.items():
            payload: dict[str, Any] = {"game_id": game_id}
            for col in scorer_columns:
                category_values = category_payload.get(col)
                payload[col] = json.dumps(category_values, ensure_ascii=True, sort_keys=True) if category_values else None
            payload_rows.append(payload)

        scorer_payload_df = pd.DataFrame(payload_rows)
        if scorer_payload_df.empty:
            return games_with_scorers

        games_with_scorers = games_with_scorers.drop(columns=[col for col in scorer_columns if col in games_with_scorers.columns])
        games_with_scorers = games_with_scorers.merge(scorer_payload_df, on="game_id", how="left")
        for col in scorer_columns:
            if col not in games_with_scorers.columns:
                games_with_scorers[col] = None
        return games_with_scorers

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
                    "shirt_number",
                    "position",
                    "unit",
                    "is_captain",
                    "is_vice_captain",
                    "game_id",
                    "season",
                    "game_type",
                    "is_starter",
                    "is_backfill",
                    "club_appearance_number",
                    "first_xv_appearance_number",
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
        df["is_backfill"] = False
        df["club_appearance_number"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
        df["first_xv_appearance_number"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
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
                "is_backfill",
                "club_appearance_number",
                "first_xv_appearance_number",
            ]
        ].rename(columns={"is_vc": "is_vice_captain"})

    def _annotate_appearance_numbers(self, appearances: pd.DataFrame) -> pd.DataFrame:
        """Add cumulative appearance counters for club total and 1st XV only."""
        if appearances.empty:
            df = appearances.copy()
            df["club_appearance_number"] = pd.Series(dtype="Int64")
            df["first_xv_appearance_number"] = pd.Series(dtype="Int64")
            return df

        df = appearances.copy()

        sort_cols = ["player", "date", "is_backfill", "game_id", "squad", "shirt_number"]
        sorted_df = df.sort_values(sort_cols, kind="stable")

        club_counts = sorted_df.groupby("player").cumcount() + 1
        df["club_appearance_number"] = pd.Series(index=sorted_df.index, data=club_counts).reindex(df.index).astype("Int64")

        df["first_xv_appearance_number"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
        first_xv = sorted_df[sorted_df["squad"] == "1st"]
        if not first_xv.empty:
            first_xv_counts = first_xv.groupby("player").cumcount() + 1
            df.loc[first_xv.index, "first_xv_appearance_number"] = first_xv_counts.astype("Int64")

        return df

    def _apply_backfill_to_appearances(
        self,
        appearances: pd.DataFrame,
        backfill: pd.DataFrame,
        reconciliation: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Inject synthetic appearance rows for historic seasons where Pitchero recorded
        more games than were scraped.  Each synthetic row has is_backfill=True and no
        game_id/position/unit so it cannot distort per-game analysis, but it makes
        COUNT(*) on player_appearances return the correct authoritative total for every
        player and season without any downstream reconciliation CTE.
        """
        adjusted = appearances.copy()

        # Apply negative reconciliation deltas first by removing surplus scraped rows
        # for the same player/squad/season so totals align with effective Pitchero counts.
        if reconciliation is not None and not reconciliation.empty:
            for _, row in reconciliation.iterrows():
                delta = int(row.get("delta", 0) or 0)
                if delta >= 0:
                    continue
                remove_count = abs(delta)
                player = row.get("player")
                squad = row.get("squad")
                season = row.get("season")
                mask = (
                    (adjusted["player"] == player)
                    & (adjusted["squad"] == squad)
                    & (adjusted["season"] == season)
                    & (adjusted["is_backfill"] == False)
                )
                candidates = adjusted.loc[mask].sort_values("date", ascending=False)
                if candidates.empty:
                    continue
                adjusted = adjusted.drop(index=candidates.index[:remove_count])

        if backfill.empty:
            return adjusted

        existing_cols = list(adjusted.columns)
        synthetic_rows = []
        used_dates_by_key: dict[tuple[str, str], set[str]] = {}
        next_offset_by_key: dict[tuple[str, str], int] = {}

        for (squad_value, player_value), group in adjusted.groupby(["squad", "player"]):
            key = (str(squad_value), str(player_value))
            used_dates_by_key[key] = set(group["date"].astype(str))
            next_offset_by_key[key] = 0

        for _, row in backfill.iterrows():
            squad = row["squad"]
            season = row["season"]
            player = row["player"]
            missing = int(row["missing_appearances"])
            if missing <= 0 or not player:
                continue
            key = (str(squad), str(player))
            used_dates = used_dates_by_key.setdefault(key, set())
            sentinel_offset = next_offset_by_key.setdefault(key, 0)
            # Use sentinel dates (1900-01-01 + index) that cannot clash with real dates.
            # The PK is (squad, date, player) so we must use unique dates per row.
            added = 0
            while added < missing:
                sentinel_date = pd.Timestamp("1900-01-01") + pd.Timedelta(days=sentinel_offset)
                sentinel_str = sentinel_date.date()
                date_key = str(sentinel_str)
                if date_key not in used_dates:
                    synthetic_rows.append({
                        "squad": squad,
                        "date": sentinel_str,
                        "player": player,
                        "shirt_number": None,
                        "position": None,
                        "unit": None,
                        "is_captain": False,
                        "is_vice_captain": False,
                        "game_id": None,
                        "season": season,
                        "game_type": None,
                        "is_starter": False,
                        "is_backfill": True,
                        "club_appearance_number": pd.NA,
                        "first_xv_appearance_number": pd.NA,
                    })
                    used_dates.add(date_key)
                    added += 1
                sentinel_offset += 1
            next_offset_by_key[key] = sentinel_offset

        if not synthetic_rows:
            return adjusted

        synthetic_df = pd.DataFrame(synthetic_rows)[existing_cols]
        return pd.concat([adjusted, synthetic_df], ignore_index=True)

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
                    "points",
                    "tries",
                    "points_per_entry",
                    "tries_per_entry",
                    "game_id",
                    "season",
                    "opposition",
                ]
            )

        merged = set_piece_raw.merge(games[["game_id", "squad", "date", "season", "opposition"]], on="game_id", how="left")

        merged = merged[merged["squad"].notna()]

        df = merged.copy()
        df["team"] = df["team"].replace({"EG": "EGRFC", "Opp": "Opposition"})

        df["lineouts_won"] = pd.to_numeric(df["lineouts_won"], errors="coerce").fillna(0).astype(int)
        df["lineouts_total"] = pd.to_numeric(df["lineouts_total"], errors="coerce").fillna(0).astype(int)
        df["scrums_won"] = pd.to_numeric(df["scrums_won"], errors="coerce").fillna(0).astype(int)
        df["scrums_total"] = pd.to_numeric(df["scrums_total"], errors="coerce").fillna(0).astype(int)
        df["lineouts_success_rate"] = (df["lineouts_won"] / df["lineouts_total"].replace(0, pd.NA)).fillna(0.0)
        df["scrums_success_rate"] = (df["scrums_won"] / df["scrums_total"].replace(0, pd.NA)).fillna(0.0)
        df["entries_22m"] = pd.to_numeric(df.get("entries_22m"), errors="coerce").astype("Int64")
        df["points"] = pd.to_numeric(df.get("points"), errors="coerce").astype("Int64")
        df["tries"] = pd.to_numeric(df.get("tries"), errors="coerce").astype("Int64")
        df["points_per_entry"] = pd.to_numeric(df.get("points_per_entry"), errors="coerce")
        df["tries_per_entry"] = pd.to_numeric(df.get("tries_per_entry"), errors="coerce")

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
                "points",
                "tries",
                "points_per_entry",
                "tries_per_entry",
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
        games: pd.DataFrame,
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
                    "Count": "count",
                    "Player": "player",
                    "Points": "points",
                }
            )
            df_2526["season"] = "2025/26"
            df_2526["score_type"] = df_2526["score_type"].fillna("").astype(str).str.strip().str.upper()
            df_2526["metric"] = df_2526["score_type"].map(scorer_type_map)
            df_2526 = df_2526[df_2526["metric"].notna()]
            df_2526["count"] = pd.to_numeric(df_2526.get("count", 1), errors="coerce").fillna(1).astype(int)
            df_2526 = df_2526[df_2526["count"] > 0]

            # Resolve game type from canonical games so season scorers can respect UI game-type filters.
            game_type_lookup = games[["squad", "date", "opposition", "season", "game_type"]].copy()
            game_type_lookup["date"] = pd.to_datetime(game_type_lookup["date"], errors="coerce").dt.date
            game_type_lookup["opposition"] = game_type_lookup["opposition"].astype(str).str.strip()

            df_2526["date"] = _safe_date(df_2526["date"])
            df_2526["opposition"] = df_2526["opposition"].astype(str).str.strip()
            df_2526 = df_2526.merge(
                game_type_lookup,
                on=["squad", "date", "opposition", "season"],
                how="left",
            )
            df_2526["game_type"] = df_2526["game_type"].fillna("Unknown")

            agg_2526 = (
                df_2526.pivot_table(
                    index=["squad", "season", "player", "game_type"],
                    columns="metric",
                    values="count",
                    aggfunc="sum",
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
            agg_2526 = pd.DataFrame(columns=["squad", "season", "player", "game_type", "tries", "conversions", "penalties", "drop_goals", "points", "source"])

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

        pivot["game_type"] = "Unknown"
        pivot["points"] = pivot["tries"] * 5 + pivot["conversions"] * 2 + pivot["penalties"] * 3 + pivot["drop_goals"] * 3
        pivot["source"] = "pitchero"
        pitchero_out = pivot[["squad", "season", "player", "game_type", "tries", "conversions", "penalties", "drop_goals", "points", "source"]]

        out = pd.concat([pitchero_out, agg_2526], ignore_index=True)
        for col in ["tries", "conversions", "penalties", "drop_goals", "points"]:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
        out["game_type"] = out["game_type"].fillna("Unknown")
        return out.groupby(["squad", "season", "player", "game_type"], as_index=False).agg(
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

        preferred_squad = pd.DataFrame(columns=["name", "squad"])
        season_values = [
            str(season).strip()
            for season in appearances.get("season", pd.Series(dtype="object")).dropna().unique().tolist()
            if str(season).strip()
        ]
        if season_values:
            ordered_seasons = sorted(set(season_values), key=_season_sort_key)
            current_season = ordered_seasons[-1]
            previous_season = ordered_seasons[-2] if len(ordered_seasons) > 1 else None

            _competitive = {"League", "Cup"}
            competitive_base = base[base["game_type"].isin(_competitive)]

            _cur = (
                competitive_base[competitive_base["season"].astype(str).str.strip() == current_season]
                .groupby(["player", "squad"], as_index=False)["game_id"]
                .count()
                .rename(columns={"game_id": "current_season_apps"})
            )
            _prev = (
                competitive_base[competitive_base["season"].astype(str).str.strip() == (previous_season or "")]
                .groupby(["player", "squad"], as_index=False)["game_id"]
                .count()
                .rename(columns={"game_id": "previous_season_apps"})
            ) if previous_season else pd.DataFrame(columns=["player", "squad", "previous_season_apps"])

            squad_counts = (
                base.groupby(["player", "squad"], as_index=False)
                .agg(total_apps=("game_id", lambda s: int(s.shape[0])), latest_date=("date", "max"))
                .merge(_cur, on=["player", "squad"], how="left")
                .merge(_prev, on=["player", "squad"], how="left")
            )
            squad_counts["current_season_apps"] = squad_counts["current_season_apps"].fillna(0).astype(int)
            squad_counts["previous_season_apps"] = squad_counts["previous_season_apps"].fillna(0).astype(int)
            squad_counts = squad_counts.sort_values(
                ["player", "current_season_apps", "previous_season_apps", "total_apps", "latest_date", "squad"],
                ascending=[True, False, False, False, False, True],
            )

            preferred_squad = squad_counts.drop_duplicates(subset=["player"]).rename(
                columns={"player": "name"}
            )[["name", "squad"]]

        agg = base.groupby("player", as_index=False).agg(
            short_name=("player", lambda s: str(s.iloc[0]).replace(" ", " ", 1)),
            position=("position", _mode_or_none),
            total_appearances=("game_id", lambda s: int(s.shape[0])),
            total_starts=("is_starter", "sum"),
            total_captaincies=("is_captain", "sum"),
            total_vc_appointments=("is_vice_captain", "sum"),
        ).rename(columns={"player": "name"})

        if not preferred_squad.empty:
            agg = agg.merge(preferred_squad, on="name", how="left")
        else:
            fallback_squad = base.groupby("player", as_index=False).first()[["player", "squad"]].rename(
                columns={"player": "name"}
            )
            agg = agg.merge(fallback_squad, on="name", how="left")

        jumper = lineouts.groupby("jumper", as_index=False).agg(
            total_lineouts_jumped=("won", "count"),
            lineouts_won_as_jumper=("won", "sum"),
        ).rename(columns={"jumper": "name"})

        points = season_scorers.groupby("player", as_index=False).agg(career_points=("points", "sum")).rename(columns={"player": "name"})

        players = agg.merge(first, on="name", how="left").merge(jumper, on="name", how="left").merge(points, on="name", how="left")

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

    @staticmethod
    def _format_debut_date(value: Any) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "-"
        if isinstance(value, pd.Timestamp):
            d = value.date()
        elif isinstance(value, datetime):
            d = value.date()
        elif isinstance(value, date):
            d = value
        else:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return "-"
            d = parsed.date()

        day = d.day
        if day % 10 == 1 and day % 100 != 11:
            suffix = "st"
        elif day % 10 == 2 and day % 100 != 12:
            suffix = "nd"
        elif day % 10 == 3 and day % 100 != 13:
            suffix = "rd"
        else:
            suffix = "th"
        return f"{day}{suffix} {d.strftime('%b %Y')}"

    def _format_debut_label(self, appearance_row: pd.Series | None, games_by_id: dict[str, dict[str, Any]]) -> str:
        if appearance_row is None:
            return "-"
        game_id = str(appearance_row.get("game_id") or "")
        game = games_by_id.get(game_id, {}) if game_id else {}
        opposition = str(game.get("opposition") or appearance_row.get("opposition") or "Unknown")
        home_away = str(game.get("home_away") or "?")
        return f"{self._format_debut_date(appearance_row.get('date'))} v {opposition} ({home_away})"

    _GAME_TYPE_MODES = ["All games", "League + Cup", "League only"]

    @staticmethod
    def _get_allowed_game_types(mode: str) -> set | None:
        if mode == "League + Cup":
            return {"League", "Cup"}
        if mode == "League only":
            return {"League"}
        return None

    @staticmethod
    def _resolve_starter_position(shirt_number) -> str | None:
        try:
            n = int(float(shirt_number))
        except (TypeError, ValueError):
            return None
        if n in (1, 3): return "Prop"
        if n == 2: return "Hooker"
        if n in (4, 5): return "Second Row"
        if n in (6, 7): return "Flanker"
        if n == 8: return "Number 8"
        if n == 9: return "Scrum Half"
        if n == 10: return "Fly Half"
        if n in (12, 13): return "Centre"
        if n in (11, 14): return "Wing"
        if n == 15: return "Full Back"
        return None

    def _build_squad_stats(self, appearances: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
        columns = ["season", "gameTypeMode", "squad", "unit", "playerCounts", "playersUsed"]
        if appearances.empty:
            return pd.DataFrame(columns=columns)

        df = appearances[
            appearances["squad"].isin(["1st", "2nd"]) &
            appearances["game_id"].notna() &
            appearances["player"].notna()
        ].copy()
        df["player"] = df["player"].astype(str).str.strip()
        df = df[df["player"] != ""]

        gt = games.set_index("game_id")["game_type"].to_dict()
        df["game_type"] = df["game_type"].where(
            df["game_type"].notna(), df["game_id"].map(gt)
        )

        rows = []
        for mode in self._GAME_TYPE_MODES:
            allowed = self._get_allowed_game_types(mode)
            filtered = df[df["game_type"].isin(allowed)] if allowed is not None else df

            for squad in ["1st", "2nd"]:
                squad_df = filtered[filtered["squad"] == squad]
                for season, grp in squad_df.groupby("season"):
                    for unit_label, unit_df in [
                        ("Total", grp),
                        ("Forwards", grp[grp["unit"] == "Forwards"]),
                        ("Backs", grp[grp["unit"] == "Backs"]),
                    ]:
                        pc = unit_df.groupby("player").size().to_dict()
                        rows.append({"season": season, "gameTypeMode": mode, "squad": squad, "unit": unit_label, "playerCounts": json.dumps(pc), "playersUsed": len(pc)})

            for season, grp in filtered.groupby("season"):
                for unit_label, unit_df in [
                    ("Total", grp),
                    ("Forwards", grp[grp["unit"] == "Forwards"]),
                    ("Backs", grp[grp["unit"] == "Backs"]),
                ]:
                    pc = unit_df.groupby("player").size().to_dict()
                    rows.append({"season": season, "gameTypeMode": mode, "squad": "Total", "unit": unit_label, "playerCounts": json.dumps(pc), "playersUsed": len(pc)})

        return pd.DataFrame(rows, columns=columns)

    def _build_squad_position_profiles(self, appearances: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
        columns = ["season", "gameTypeMode", "squad", "position", "playerCounts", "playersUsed"]
        if appearances.empty:
            return pd.DataFrame(columns=columns)

        df = appearances[
            appearances["squad"].isin(["1st", "2nd"]) &
            appearances["game_id"].notna() &
            appearances["player"].notna() &
            (appearances["is_starter"] == True)
        ].copy()
        df["player"] = df["player"].astype(str).str.strip()
        df = df[df["player"] != ""]
        df["canonical_position"] = df["shirt_number"].apply(self._resolve_starter_position)
        df = df[df["canonical_position"].notna()]

        gt = games.set_index("game_id")["game_type"].to_dict()
        df["game_type"] = df["game_type"].where(
            df["game_type"].notna(), df["game_id"].map(gt)
        )

        rows = []
        for mode in self._GAME_TYPE_MODES:
            allowed = self._get_allowed_game_types(mode)
            filtered = df[df["game_type"].isin(allowed)] if allowed is not None else df

            for (season, squad, position), grp in filtered.groupby(["season", "squad", "canonical_position"]):
                pc = grp.groupby("player").size().to_dict()
                rows.append({"season": season, "gameTypeMode": mode, "squad": squad, "position": position, "playerCounts": json.dumps(pc), "playersUsed": len(pc)})

        return pd.DataFrame(rows, columns=columns)

    def _build_squad_continuity(self, appearances: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
        columns = ["season", "gameTypeMode", "squad", "unit", "retained", "gamePairs"]
        if appearances.empty:
            return pd.DataFrame(columns=columns)

        df = appearances[
            appearances["squad"].isin(["1st", "2nd"]) &
            appearances["game_id"].notna() &
            appearances["player"].notna() &
            (appearances["is_starter"] == True)
        ].copy()
        df["player"] = df["player"].astype(str).str.strip()
        df = df[df["player"] != ""]

        games_indexed = games.set_index("game_id")
        gt = games_indexed["game_type"].to_dict()
        dates = games_indexed["date"].to_dict()
        df["game_type"] = df["game_type"].where(
            df["game_type"].notna(), df["game_id"].map(gt)
        )
        df["date_resolved"] = pd.to_datetime(
            df["date"].where(df["date"].notna(), df["game_id"].map(dates)), errors="coerce"
        )

        rows = []
        for mode in self._GAME_TYPE_MODES:
            allowed = self._get_allowed_game_types(mode)
            filtered = df[df["game_type"].isin(allowed)] if allowed is not None else df

            for (season, squad), grp in filtered.groupby(["season", "squad"]):
                game_dates = grp.groupby("game_id")["date_resolved"].first().reset_index()
                game_dates = game_dates.sort_values("date_resolved")
                game_ids_sorted = game_dates["game_id"].tolist()
                if len(game_ids_sorted) < 2:
                    continue

                by_game: dict[str, dict[str, set]] = {}
                for _, row in grp.iterrows():
                    gid = row["game_id"]
                    player = row["player"]
                    unit = row.get("unit")
                    if gid not in by_game:
                        by_game[gid] = {"Total": set(), "Forwards": set(), "Backs": set()}
                    by_game[gid]["Total"].add(player)
                    if unit in ("Forwards", "Backs"):
                        by_game[gid][unit].add(player)

                retentions: dict[str, list[int]] = {"Total": [], "Forwards": [], "Backs": []}
                for i in range(1, len(game_ids_sorted)):
                    prev_id = game_ids_sorted[i - 1]
                    curr_id = game_ids_sorted[i]
                    if prev_id not in by_game or curr_id not in by_game:
                        continue
                    for unit in ["Total", "Forwards", "Backs"]:
                        prev_set = by_game[prev_id].get(unit, set())
                        curr_set = by_game[curr_id].get(unit, set())
                        retentions[unit].append(len(curr_set & prev_set))

                for unit in ["Total", "Forwards", "Backs"]:
                    if not retentions[unit]:
                        continue
                    avg = sum(retentions[unit]) / len(retentions[unit])
                    rows.append({"season": season, "gameTypeMode": mode, "squad": squad, "unit": unit, "retained": round(avg, 4), "gamePairs": len(retentions[unit])})

        return pd.DataFrame(rows, columns=columns)

    def _build_season_summary(
        self,
        games: pd.DataFrame,
        appearances: pd.DataFrame,
        season_scorers: pd.DataFrame,
        set_piece: pd.DataFrame,
    ) -> pd.DataFrame:
        columns = [
            "season",
            "gameTypeMode",
            "squad",
            "gamesPlayed",
            "gamesWon",
            "gamesLost",
            "gamesDrawn",
            "avgPointsForHome",
            "avgPointsAgainstHome",
            "avgPointsForAway",
            "avgPointsAgainstAway",
            "avgPointsForOverall",
            "avgPointsAgainstOverall",
            "topPointScorerValue",
            "topPointScorerPlayers",
            "topTryScorerValue",
            "topTryScorerPlayers",
            "topAppearanceValue",
            "topAppearancePlayers",
            "avgLineoutSuccessRate",
            "avgScrumSuccessRate",
            "avgPointsPer22mEntry",
            "avgTriesPer22mEntry",
            "gamesWithSetPieceData",
        ]
        if games.empty:
            return pd.DataFrame(columns=columns)

        games_df = games[games["squad"].isin(["1st", "2nd"])].copy()
        appearances_df = appearances[appearances["squad"].isin(["1st", "2nd"])].copy()
        scorers_df = season_scorers[season_scorers["squad"].isin(["1st", "2nd"])].copy()
        set_piece_df = set_piece.copy()

        game_type_by_id = games_df.set_index("game_id")["game_type"].to_dict()
        appearances_df["resolved_game_type"] = appearances_df.apply(
            lambda row: "Unknown" if bool(row.get("is_backfill")) else (row.get("game_type") or game_type_by_id.get(row.get("game_id"))),
            axis=1,
        )

        def round_or_none(value: float | int | None, digits: int = 2) -> float | None:
            if value is None or pd.isna(value):
                return None
            return round(float(value), digits)

        def build_top_summary(df: pd.DataFrame, value_col: str) -> tuple[int | None, str]:
            if df.empty or value_col not in df.columns:
                return None, json.dumps([])
            working = df[["player", value_col]].copy()
            working["player"] = working["player"].astype(str).str.strip()
            working = working[(working["player"] != "") & working[value_col].notna()]
            if working.empty:
                return None, json.dumps([])
            working[value_col] = pd.to_numeric(working[value_col], errors="coerce")
            working = working[working[value_col].notna()]
            if working.empty:
                return None, json.dumps([])
            # Aggregate per player to handle multiple rows per player (e.g., League and Cup games)
            aggregated = working.groupby("player")[value_col].sum().reset_index()
            max_value = int(aggregated[value_col].max())
            players = sorted(aggregated.loc[aggregated[value_col] == max_value, "player"].dropna().unique().tolist())
            return max_value, json.dumps(players)

        def build_appearance_leaders(df: pd.DataFrame) -> dict[tuple[str, str], tuple[int | None, str]]:
            if df.empty:
                return {}
            grouped = df.groupby(["season", "squad", "player"]).size().reset_index(name="appearances")
            leaders: dict[tuple[str, str], tuple[int | None, str]] = {}
            for (season, squad), group in grouped.groupby(["season", "squad"]):
                max_value = int(group["appearances"].max())
                players = sorted(group.loc[group["appearances"] == max_value, "player"].dropna().unique().tolist())
                leaders[(season, squad)] = (max_value, json.dumps(players))
            return leaders

        if "game_type" not in scorers_df.columns:
            scorers_df["game_type"] = "Unknown"
        scorers_df["game_type"] = scorers_df["game_type"].fillna("Unknown")

        set_piece_lookup: dict[tuple[str, str], dict[str, Any]] = {}
        if not set_piece_df.empty and "team" in set_piece_df.columns:
            set_piece_df = set_piece_df[set_piece_df["team"] == "EGRFC"].copy()
            if not set_piece_df.empty:
                set_piece_df = set_piece_df.merge(
                    games_df[["game_id", "season", "squad"]],
                    on="game_id",
                    how="left",
                    suffixes=("", "_game"),
                )
                if "season_game" in set_piece_df.columns:
                    set_piece_df["season"] = set_piece_df["season_game"].where(set_piece_df["season_game"].notna(), set_piece_df.get("season"))
                if "squad_game" in set_piece_df.columns:
                    set_piece_df["squad"] = set_piece_df["squad_game"].where(set_piece_df["squad_game"].notna(), set_piece_df.get("squad"))
                for (season, squad), group in set_piece_df.groupby(["season", "squad"]):
                    set_piece_lookup[(season, squad)] = {
                        "avgLineoutSuccessRate": round_or_none(group["lineouts_success_rate"].dropna().mean(), 3),
                        "avgScrumSuccessRate": round_or_none(group["scrums_success_rate"].dropna().mean(), 3),
                        "avgPointsPer22mEntry": round_or_none(group["points_per_entry"].dropna().mean(), 2),
                        "avgTriesPer22mEntry": round_or_none(group["tries_per_entry"].dropna().mean(), 2),
                        "gamesWithSetPieceData": int(group["game_id"].dropna().nunique()),
                    }

        rows: list[dict[str, Any]] = []
        for mode in self._GAME_TYPE_MODES:
            allowed = self._get_allowed_game_types(mode)
            filtered_games = games_df[games_df["game_type"].isin(allowed)] if allowed is not None else games_df
            filtered_apps = appearances_df[appearances_df["resolved_game_type"].isin(allowed)] if allowed is not None else appearances_df
            filtered_scorers = scorers_df[scorers_df["game_type"].isin(allowed)] if allowed is not None else scorers_df

            scorer_lookup: dict[tuple[str, str], dict[str, Any]] = {}
            for (season, squad), group in filtered_scorers.groupby(["season", "squad"]):
                point_value, point_players = build_top_summary(group, "points")
                try_value, try_players = build_top_summary(group, "tries")
                scorer_lookup[(season, squad)] = {
                    "topPointScorerValue": point_value,
                    "topPointScorerPlayers": point_players,
                    "topTryScorerValue": try_value,
                    "topTryScorerPlayers": try_players,
                }

            appearance_lookup = build_appearance_leaders(filtered_apps)

            for (season, squad), group in filtered_games.groupby(["season", "squad"]):
                scorer_data = scorer_lookup.get((season, squad), {})
                set_piece_data = set_piece_lookup.get((season, squad), {})
                top_appearance_value, top_appearance_players = appearance_lookup.get((season, squad), (None, json.dumps([])))
                rows.append(
                    {
                        "season": season,
                        "gameTypeMode": mode,
                        "squad": squad,
                        "gamesPlayed": int(len(group)),
                        "gamesWon": int((group["result"] == "W").sum()),
                        "gamesLost": int((group["result"] == "L").sum()),
                        "gamesDrawn": int((group["result"] == "D").sum()),
                        "avgPointsForHome": round_or_none(group.loc[group["home_away"] == "H", "score_for"].mean(), 2),
                        "avgPointsAgainstHome": round_or_none(group.loc[group["home_away"] == "H", "score_against"].mean(), 2),
                        "avgPointsForAway": round_or_none(group.loc[group["home_away"] == "A", "score_for"].mean(), 2),
                        "avgPointsAgainstAway": round_or_none(group.loc[group["home_away"] == "A", "score_against"].mean(), 2),
                        "avgPointsForOverall": round_or_none(group["score_for"].mean(), 2),
                        "avgPointsAgainstOverall": round_or_none(group["score_against"].mean(), 2),
                        "topPointScorerValue": scorer_data.get("topPointScorerValue"),
                        "topPointScorerPlayers": scorer_data.get("topPointScorerPlayers", json.dumps([])),
                        "topTryScorerValue": scorer_data.get("topTryScorerValue"),
                        "topTryScorerPlayers": scorer_data.get("topTryScorerPlayers", json.dumps([])),
                        "topAppearanceValue": top_appearance_value,
                        "topAppearancePlayers": top_appearance_players,
                        "avgLineoutSuccessRate": set_piece_data.get("avgLineoutSuccessRate"),
                        "avgScrumSuccessRate": set_piece_data.get("avgScrumSuccessRate"),
                        "avgPointsPer22mEntry": set_piece_data.get("avgPointsPer22mEntry"),
                        "avgTriesPer22mEntry": set_piece_data.get("avgTriesPer22mEntry"),
                        "gamesWithSetPieceData": set_piece_data.get("gamesWithSetPieceData"),
                    }
                )

        return pd.DataFrame(rows, columns=columns)

    def _build_player_profiles_base(
        self,
        players: pd.DataFrame,
        appearances: pd.DataFrame,
        games: pd.DataFrame,
        season_scorers: pd.DataFrame,
    ) -> pd.DataFrame:
        columns = [
            "name",
            "short_name",
            "squad",
            "position",
            "photo_url",
            "sponsor",
            "totalAppearances",
            "totalStarts",
            "firstXVAppearances",
            "firstXVStarts",
            "seasonAppearances",
            "seasonStarts",
            "seasonCompetitiveAppearances",
            "scoringCareer",
            "scoringThisSeason",
            "debutOverall",
            "debutFirstXV",
            "hasDifferentFirstXVDebut",
            "otherPositions",
            "isActive",
            "lastAppearanceDate",
        ]
        if players.empty:
            return pd.DataFrame(columns=columns)

        games_for_season = games.copy()
        games_for_season["date"] = pd.to_datetime(games_for_season["date"], errors="coerce")
        if games_for_season.empty or games_for_season["date"].isna().all():
            current_season = ""
        else:
            latest_idx = games_for_season["date"].idxmax()
            current_season = str(games_for_season.loc[latest_idx, "season"] or "")

        scoring = season_scorers.copy()
        for col in ["tries", "conversions", "penalties", "drop_goals", "points"]:
            scoring[col] = pd.to_numeric(scoring.get(col), errors="coerce").fillna(0).astype(int)

        career_scoring = {}
        season_scoring = {}
        if not scoring.empty:
            career_df = scoring.groupby("player", as_index=False).agg(
                careerTries=("tries", "sum"),
                careerConversions=("conversions", "sum"),
                careerPenalties=("penalties", "sum"),
                careerDropGoals=("drop_goals", "sum"),
                careerPoints=("points", "sum"),
            )
            career_scoring = {
                str(row["player"]): {
                    "careerTries": int(row["careerTries"]),
                    "careerConversions": int(row["careerConversions"]),
                    "careerPenalties": int(row["careerPenalties"]),
                    "careerDropGoals": int(row["careerDropGoals"]),
                    "careerPoints": int(row["careerPoints"]),
                }
                for _, row in career_df.iterrows()
            }

            season_df = scoring[scoring["season"].astype(str).str.strip() == current_season]
            if not season_df.empty:
                season_df = season_df.groupby("player", as_index=False).agg(
                    seasonTries=("tries", "sum"),
                    seasonConversions=("conversions", "sum"),
                    seasonPenalties=("penalties", "sum"),
                    seasonDropGoals=("drop_goals", "sum"),
                    seasonPoints=("points", "sum"),
                )
                season_scoring = {
                    str(row["player"]): {
                        "seasonTries": int(row["seasonTries"]),
                        "seasonConversions": int(row["seasonConversions"]),
                        "seasonPenalties": int(row["seasonPenalties"]),
                        "seasonDropGoals": int(row["seasonDropGoals"]),
                        "seasonPoints": int(row["seasonPoints"]),
                    }
                    for _, row in season_df.iterrows()
                }

        games_by_id = {}
        if not games.empty:
            games_by_id = {
                str(row["game_id"]): {
                    "opposition": row.get("opposition"),
                    "home_away": row.get("home_away"),
                }
                for _, row in games.iterrows()
            }

        apps = appearances.copy()
        apps["date"] = pd.to_datetime(apps["date"], errors="coerce")
        if "is_backfill" not in apps.columns:
            apps["is_backfill"] = False

        rows = []
        today = pd.Timestamp.today().normalize()
        competitive_types = {"League", "Cup"}

        for _, p in players.iterrows():
            name = str(p.get("name") or "").strip()
            if not name:
                continue

            player_apps = apps[apps["player"] == name].copy().sort_values("date")
            real_apps = player_apps[player_apps["is_backfill"] == False].copy()

            first_overall = real_apps.iloc[0] if not real_apps.empty else None
            first_1st = real_apps[real_apps["squad"] == "1st"]
            first_1st_row = first_1st.iloc[0] if not first_1st.empty else None
            last_real = real_apps.iloc[-1] if not real_apps.empty else None

            first_xv_apps = player_apps[player_apps["squad"] == "1st"]
            first_xv_appearances = int(len(first_xv_apps))
            first_xv_starts = int(pd.to_numeric(first_xv_apps.get("is_starter"), errors="coerce").fillna(0).astype(int).sum()) if not first_xv_apps.empty else 0

            season_apps = player_apps[player_apps["season"].astype(str).str.strip() == current_season]
            season_appearances = int(len(season_apps))
            season_starts = int(pd.to_numeric(season_apps.get("is_starter"), errors="coerce").fillna(0).astype(int).sum()) if not season_apps.empty else 0
            season_competitive_apps = int(len(season_apps[season_apps["game_type"].isin(competitive_types)])) if not season_apps.empty else 0

            starting_positions = real_apps[(real_apps["is_starter"] == True) & (real_apps["position"].notna())]
            starting_positions = starting_positions[starting_positions["position"].astype(str).str.strip() != "Bench"]
            if not starting_positions.empty:
                primary_position = (
                    starting_positions.groupby("position", as_index=False)
                    .size()
                    .sort_values(["size", "position"], ascending=[False, True])
                    .iloc[0]["position"]
                )
            else:
                primary_position = p.get("position") or "Unknown"

            other_positions_df = (
                real_apps[real_apps["position"].notna()]
                .assign(position=lambda df: df["position"].astype(str).str.strip())
            )
            other_positions_df = other_positions_df[(other_positions_df["position"] != "") & (other_positions_df["position"] != "Bench")]
            other_positions = []
            if not other_positions_df.empty:
                other_counts = other_positions_df.groupby("position", as_index=False).size()
                other_positions = sorted([
                    str(pos)
                    for pos, count in zip(other_counts["position"], other_counts["size"])
                    if str(pos) != str(primary_position) and int(count) > 1
                ])

            last_date = pd.to_datetime(last_real.get("date"), errors="coerce") if last_real is not None else pd.NaT
            within_six_months = False
            if pd.notna(last_date):
                within_six_months = (today - last_date.normalize()).days <= 182
            is_active = bool(season_competitive_apps > 0 or within_six_months)

            career = career_scoring.get(name, {
                "careerTries": 0,
                "careerConversions": 0,
                "careerPenalties": 0,
                "careerDropGoals": 0,
                "careerPoints": int(p.get("career_points") or 0),
            })
            season_now = season_scoring.get(name, {
                "seasonTries": 0,
                "seasonConversions": 0,
                "seasonPenalties": 0,
                "seasonDropGoals": 0,
                "seasonPoints": 0,
            })

            scoring_career_payload = {
                "tries": int(career["careerTries"]),
                "conversions": int(career["careerConversions"]),
                "penalties": int(career["careerPenalties"]),
                "drop_goals": int(career["careerDropGoals"]),
                "points": int(career["careerPoints"]),
            }
            scoring_season_payload = {
                "tries": int(season_now["seasonTries"]),
                "conversions": int(season_now["seasonConversions"]),
                "penalties": int(season_now["seasonPenalties"]),
                "drop_goals": int(season_now["seasonDropGoals"]),
                "points": int(season_now["seasonPoints"]),
            }

            first_overall_label = self._format_debut_label(first_overall, games_by_id)
            first_xv_label = self._format_debut_label(first_1st_row, games_by_id)
            has_diff_1st = bool(
                first_overall is not None
                and first_1st_row is not None
                and str(first_overall.get("game_id") or "") != str(first_1st_row.get("game_id") or "")
            )

            rows.append({
                "name": name,
                "short_name": p.get("short_name"),
                "squad": p.get("squad"),
                "position": primary_position,
                "photo_url": p.get("photo_url"),
                "sponsor": p.get("sponsor"),
                "totalAppearances": int(p.get("total_appearances") or 0),
                "totalStarts": int(p.get("total_starts") or 0),
                "firstXVAppearances": first_xv_appearances,
                "firstXVStarts": first_xv_starts,
                "seasonAppearances": season_appearances,
                "seasonStarts": season_starts,
                "seasonCompetitiveAppearances": season_competitive_apps,
                "scoringCareer": json.dumps(scoring_career_payload),
                "scoringThisSeason": json.dumps(scoring_season_payload),
                "debutOverall": first_overall_label,
                "debutFirstXV": first_xv_label,
                "hasDifferentFirstXVDebut": has_diff_1st,
                "otherPositions": json.dumps(other_positions),
                "isActive": is_active,
                "lastAppearanceDate": last_date.date() if pd.notna(last_date) else None,
            })

        return pd.DataFrame(rows, columns=columns)

    def _build_squad_stats_with_thresholds(self, appearances: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-compute player counts at different appearance thresholds (0-20).
        Eliminates need for client-side recalculation of threshold filtering.
        """
        columns = ["season", "gameTypeMode", "squad", "unit", "minimumAppearances", "playerCount", "totalPlayed"]
        if appearances.empty:
            return pd.DataFrame(columns=columns)

        df = appearances[
            appearances["squad"].isin(["1st", "2nd"]) &
            appearances["game_id"].notna() &
            appearances["player"].notna()
        ].copy()
        df["player"] = df["player"].astype(str).str.strip()
        df = df[df["player"] != ""]

        gt = games.set_index("game_id")["game_type"].to_dict()
        df["game_type"] = df["game_type"].where(
            df["game_type"].notna(), df["game_id"].map(gt)
        )

        rows = []
        for mode in self._GAME_TYPE_MODES:
            allowed = self._get_allowed_game_types(mode)
            filtered = df[df["game_type"].isin(allowed)] if allowed is not None else df

            for squad in ["1st", "2nd"]:
                squad_df = filtered[filtered["squad"] == squad]
                for season, season_grp in squad_df.groupby("season"):
                    for unit_label, unit_df in [
                        ("Total", season_grp),
                        ("Forwards", season_grp[season_grp["unit"] == "Forwards"]),
                        ("Backs", season_grp[season_grp["unit"] == "Backs"]),
                    ]:
                        # Count appearances per player
                        player_counts = unit_df.groupby("player").size()
                        
                        # For each threshold 0-20, count players with >= that many appearances
                        for threshold in range(21):
                            player_count = (player_counts >= threshold).sum() if threshold > 0 else len(player_counts)
                            rows.append({
                                "season": season,
                                "gameTypeMode": mode,
                                "squad": squad,
                                "unit": unit_label,
                                "minimumAppearances": threshold,
                                "playerCount": int(player_count),
                                "totalPlayed": int(unit_df["game_id"].nunique()),
                            })

            # Total squad aggregates
            for season, season_grp in filtered.groupby("season"):
                for unit_label, unit_df in [
                    ("Total", season_grp),
                    ("Forwards", season_grp[season_grp["unit"] == "Forwards"]),
                    ("Backs", season_grp[season_grp["unit"] == "Backs"]),
                ]:
                    player_counts = unit_df.groupby("player").size()
                    for threshold in range(21):
                        player_count = (player_counts >= threshold).sum() if threshold > 0 else len(player_counts)
                        rows.append({
                            "season": season,
                            "gameTypeMode": mode,
                            "squad": "Total",
                            "unit": unit_label,
                            "minimumAppearances": threshold,
                            "playerCount": int(player_count),
                            "totalPlayed": int(season_grp["game_id"].nunique()),
                        })

        return pd.DataFrame(rows, columns=columns)

    def _build_player_profiles_canonical(self, player_profiles_base: pd.DataFrame) -> pd.DataFrame:
        """
        Deduplicate base player profile rows by selecting the record with most appearances
        when a player appears in both 1st and 2nd XV.
        """
        columns = [
            "name",
            "short_name",
            "squad",
            "position",
            "photo_url",
            "sponsor",
            "totalAppearances",
            "totalStarts",
            "firstXVAppearances",
            "firstXVStarts",
            "seasonAppearances",
            "seasonStarts",
            "seasonCompetitiveAppearances",
            "scoringCareer",
            "scoringThisSeason",
            "debutOverall",
            "debutFirstXV",
            "hasDifferentFirstXVDebut",
            "otherPositions",
            "isActive",
            "lastAppearanceDate",
        ]
        if player_profiles_base.empty:
            return pd.DataFrame(columns=columns)

        # Group by player name, select record with most total appearances
        df = player_profiles_base.copy()
        df_sorted = df.sort_values("totalAppearances", ascending=False)
        df_dedup = df_sorted.drop_duplicates(subset=["name"], keep="first")

        rows = []
        for _, row in df_dedup.iterrows():
            rows.append({
                "name": row.get("name"),
                "short_name": row.get("short_name"),
                "squad": row.get("squad"),
                "position": row.get("position"),
                "photo_url": row.get("photo_url"),
                "sponsor": row.get("sponsor"),
                "totalAppearances": row.get("totalAppearances"),
                "totalStarts": row.get("totalStarts"),
                "firstXVAppearances": row.get("firstXVAppearances"),
                "firstXVStarts": row.get("firstXVStarts"),
                "seasonAppearances": row.get("seasonAppearances"),
                "seasonStarts": row.get("seasonStarts"),
                "seasonCompetitiveAppearances": row.get("seasonCompetitiveAppearances"),
                "scoringCareer": row.get("scoringCareer"),
                "scoringThisSeason": row.get("scoringThisSeason"),
                "debutOverall": row.get("debutOverall"),
                "debutFirstXV": row.get("debutFirstXV"),
                "hasDifferentFirstXVDebut": row.get("hasDifferentFirstXVDebut"),
                "otherPositions": row.get("otherPositions"),
                "isActive": row.get("isActive"),
                "lastAppearanceDate": row.get("lastAppearanceDate"),
            })

        return pd.DataFrame(rows, columns=columns)

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