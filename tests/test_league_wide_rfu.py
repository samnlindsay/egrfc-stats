import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pandas as pd

from python.backend import BackendConfig, BackendDatabase
from python.charts import _derive_league_result, _is_future_unplayed_fixture
from python.league_data import (
    build_rfu_games_dataframe,
    build_rfu_player_appearances_dataframe,
    fetch_match_data,
    fetch_matches_from_results_page,
    get_url,
    load_consolidated_matches,
    _parse_score_text,
    build_league_tables_json,
    update_consolidated_file,
    update_league_wide_data,
    update_multiple_seasons_and_squads,
)


LEAGUE_HISTORY = pd.DataFrame(
    [
        {
            "season": "2026/27",
            "squad": "2nd",
            "league": "Counties 3 Sussex",
            "team_id": 7135,
            "competition_id": 261,
            "division_id": 76490,
        }
    ]
)


class LeagueWideRfuTests(unittest.TestCase):
    def test_score_parser_does_not_treat_kickoff_time_as_score(self):
        self.assertEqual(_parse_score_text("15:00"), [None, None])
        self.assertEqual(_parse_score_text("14:00"), [None, None])
        self.assertEqual(_parse_score_text("15:00 - 0"), [None, None])
        self.assertEqual(_parse_score_text("15:00 - 14:00"), [None, None])
        self.assertEqual(_parse_score_text("15 - 0"), [15, 0])

    def test_empty_refresh_persists_clearing_future_placeholder_scores(self):
        future_date = (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        past_date = (pd.Timestamp.today().normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        with tempfile.TemporaryDirectory() as temp_dir:
            matches_path = Path(temp_dir) / "matches.json"
            matches_path.write_text(
                json.dumps(
                    [
                        {"match_id": "future", "date": future_date, "score": [15, 0]},
                        {"match_id": "past", "date": past_date, "score": [15, 0]},
                    ]
                ),
                encoding="utf-8",
            )

            update_consolidated_file([], str(matches_path))
            stored = {row["match_id"]: row for row in load_consolidated_matches(str(matches_path))}

            self.assertEqual(stored["future"]["score"], [None, None])
            self.assertEqual(stored["past"]["score"], [15, 0])

    def test_get_url_can_query_division_without_eg_team_filter(self):
        team_url = get_url(2, "2026/27", LEAGUE_HISTORY)
        league_url = get_url(2, "2026/27", LEAGUE_HISTORY, include_team=False)

        self.assertIn("division=76490", league_url)
        self.assertIn("team=7135", team_url)
        self.assertNotIn("team=", league_url)

    @patch("python.league_data.requests.get")
    def test_results_page_returns_all_division_fixtures_with_squad_context(self, request_get):
        request_get.return_value = Mock(
            text='''
                <div class="dataContainer cardContainer_Saturday,12Sep2026">
                    <a href="/fixtures-and-results/match-centre-community?matchId=12345">Match</a>
                    <div class="coh-style-hometeam"><a>Club A</a></div>
                    <div class="coh-style-away-team"><a>Club B</a></div>
                    <div class="fnr-scores">
                        <a class="coh-style-numeric-score">24</a>
                        <a class="coh-style-numeric-right">17</a>
                    </div>
                </div>
            '''
        )

        rows = fetch_matches_from_results_page(
            squad=2,
            season="2026/27",
            league_history_df=LEAGUE_HISTORY,
            include_all_teams=True,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["teams"], ["Club A", "Club B"])
        self.assertEqual(rows[0]["score"], [24, 17])
        self.assertEqual(rows[0]["tracked_squad"], "2nd")
        self.assertNotIn("team=7135", request_get.call_args.args[0])

    @patch("python.league_data.requests.get")
    def test_results_page_discards_future_placeholder_score(self, request_get):
        future_date = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
        card_date = future_date.strftime("%A,%d%b%Y")
        request_get.return_value = Mock(
            text=f'''
                <div class="dataContainer cardContainer_{card_date}">
                    <a href="/fixtures-and-results/match-centre-community?matchId=12347">Match</a>
                    <div class="coh-style-hometeam"><a>Club A</a></div>
                    <div class="coh-style-away-team"><a>Club B</a></div>
                    <div class="fnr-scores">
                        <a class="coh-style-numeric-score">15</a>
                        <a class="coh-style-numeric-right">0</a>
                    </div>
                </div>
            '''
        )

        rows = fetch_matches_from_results_page(
            squad=2,
            season="2026/27",
            league_history_df=LEAGUE_HISTORY,
            include_all_teams=True,
        )

        self.assertEqual(rows[0]["score"], [None, None])

    @patch("builtins.open", new_callable=mock_open)
    @patch("python.league_data.time.sleep")
    @patch("python.league_data.get_players", return_value=[{"9": "Home Player"}, {"12": "Away Player"}])
    @patch("python.league_data.requests.get")
    def test_match_centre_extracts_both_lineups_for_second_xv_division(
        self, request_get, get_players, _sleep, _open
    ):
        request_get.return_value = Mock(
            text='''
                <div class="c042-match-score">24 - 17</div>
                <div id="c042-event-date">Saturday 12 September 2026</div>
                <div id="c042-event-champion">Counties 3 Sussex</div>
                <div class="c042-team-name">Club A</div>
                <div class="c042-team-name">Club B</div>
            '''
        )

        match = fetch_match_data("12345", tracked_squad=2)

        self.assertEqual(match["tracked_squad"], "2nd")
        self.assertEqual(match["players"], [{"9": "Home Player"}, {"12": "Away Player"}])
        get_players.assert_called_once()

    @patch("python.league_data.time.sleep")
    @patch("python.league_data.fetch_match_data")
    @patch("python.league_data.fetch_matches_from_results_page")
    def test_refresh_persists_results_and_both_teams_lineups(
        self, fetch_summaries, fetch_match, _sleep
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            matches_path = Path(temp_dir) / "matches.json"
            played_summary = {
                "match_id": "12345",
                "season": "2026-2027",
                "league": "Counties 3 Sussex",
                "tracked_squad": "2nd",
                "date": "2026-09-12",
                "teams": ["Club A", "Club B"],
                "score": [24, 17],
                "players": [{}, {}],
            }
            upcoming_summary = {
                **played_summary,
                "match_id": "12346",
                "date": (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                "score": [15, 0],
            }
            fetch_summaries.return_value = [played_summary, upcoming_summary]
            fetch_match.return_value = {
                **played_summary,
                "players": [{"9": "Home Scrumhalf"}, {"12": "Away Centre"}],
            }

            update_league_wide_data(
                squad=2,
                season="2026/27",
                consolidated_file=str(matches_path),
                league_history_df=LEAGUE_HISTORY,
            )

            stored = load_consolidated_matches(str(matches_path))
            games = build_rfu_games_dataframe(matches=stored)
            appearances = build_rfu_player_appearances_dataframe(matches=stored, games_df=games)

            self.assertEqual(len(stored), 2)
            self.assertEqual(fetch_match.call_count, 1)
            self.assertEqual(set(games["tracked_squad"]), {"2nd"})
            self.assertEqual(set(appearances["team"]), {"Club A", "Club B"})
            self.assertEqual(set(appearances["player"]), {"Home Scrumhalf", "Away Centre"})
            future_stored = next(match for match in stored if match["match_id"] == "12346")
            self.assertEqual(future_stored["score"], [None, None])

    def test_future_placeholder_score_is_classified_as_unplayed(self):
        future_match = {
            "home_team": "Club A",
            "away_team": "Club B",
            "date": pd.Timestamp.today().normalize() + pd.Timedelta(days=1),
            "home_score": 15,
            "away_score": 0,
            "home_walkover": False,
            "away_walkover": False,
        }

        self.assertTrue(_is_future_unplayed_fixture(future_match))
        self.assertEqual(_derive_league_result(future_match), "To be played")

    @patch("python.rfu_team_data.fetch_league_table_for_season", return_value=[])
    def test_failed_table_refresh_preserves_existing_seasons(self, _fetch_table):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "league_tables.json"
            existing = {
                "seasons": ["2025/26", "2026/27"],
                "2025/26": {"1": {"squad": "1st Team", "division": "Old League", "tables": []}},
                "2026/27": {"1": {"squad": "1st Team", "division": "Counties 2 Sussex", "tables": [{"team": "East Grinstead"}] }},
            }
            output_file.write_text(json.dumps(existing), encoding="utf-8")

            result = build_league_tables_json(
                output_file=str(output_file),
                league_history_df=pd.DataFrame(
                    [
                        {
                            "season": "2026/27",
                            "squad": "1st",
                            "league": "Counties 2 Sussex",
                            "competition_id": 261,
                            "division_id": 75873,
                        }
                    ]
                ),
                seasons=["2026/27"],
                squads=[1],
            )

            expected = {**existing, "seasons": ["2026/27", "2025/26"]}
            self.assertEqual(result, expected)
            self.assertEqual(json.loads(output_file.read_text(encoding="utf-8")), expected)

    @patch("python.league_data.build_league_tables_json")
    @patch("python.league_data.load_consolidated_matches", return_value=[])
    @patch("python.league_data.update_league_data", return_value=([], []))
    @patch("python.league_data.get_active_season_squad_pairs", return_value=[("2026/27", 1)])
    def test_multi_update_scopes_table_refresh_to_requested_season_and_squad(
        self, _get_pairs, _update_league, _load_matches, build_tables
    ):
        update_multiple_seasons_and_squads(
            seasons=["2026/27"],
            squads=[1],
            consolidated_file="unused.json",
            league_history_df=LEAGUE_HISTORY,
        )

        self.assertEqual(build_tables.call_args.kwargs["seasons"], ["2026/27"])
        self.assertEqual(build_tables.call_args.kwargs["squads"], [1])
        self.assertTrue(build_tables.call_args.kwargs["preserve_existing"])

    def test_opposition_lineups_do_not_enter_canonical_eg_appearances(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = BackendDatabase(
                BackendConfig(
                    db_path=str(Path(temp_dir) / "test.duckdb"),
                    export_dir=str(Path(temp_dir) / "exports"),
                )
            )
            try:
                raw_appearances = pd.DataFrame(
                    [
                        {
                            "team": "East Grinstead",
                            "opposition": "Club B",
                            "tracked_squad": "2nd",
                            "match_id": "12345",
                            "date": "2026-09-12",
                            "season": "2026/27",
                            "player": "EG Player",
                            "shirt_number": 9,
                            "unit": "Backs",
                            "is_starter": True,
                        },
                        {
                            "team": "Club B",
                            "opposition": "East Grinstead",
                            "tracked_squad": "2nd",
                            "match_id": "12345",
                            "date": "2026-09-12",
                            "season": "2026/27",
                            "player": "Opponent Player",
                            "shirt_number": 12,
                            "unit": "Backs",
                            "is_starter": True,
                        },
                    ]
                )

                canonical = backend._build_canonical_appearances_from_rfu(raw_appearances)
                self.assertEqual(canonical["player"].tolist(), ["EG Player"])
            finally:
                backend.close()


if __name__ == "__main__":
    unittest.main()