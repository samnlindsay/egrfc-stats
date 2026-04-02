import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from python.backend import BackendConfig, BackendDatabase
from python.data import DataExtractor


class _ExtractorShouldNotBeCalled:
    def extract_pitchero_historic_team_sheets(self, *args, **kwargs):
        raise AssertionError("extract_pitchero_historic_team_sheets should not be called in cache-first mode")


class BackendCacheAndReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.db_path = self.temp_path / "test_backend.duckdb"
        self.backend = BackendDatabase(BackendConfig(db_path=str(self.db_path), export_dir="data/backend"))

    def tearDown(self):
        self.backend.close()
        self.temp_dir.cleanup()

    def test_historic_loader_uses_cache_without_scrape(self):
        cache_file = self.temp_path / "historic_cache.json"
        payload = {
            "games": [
                {
                    "game_id": "2018-09-01_1st_Hove",
                    "date": "2018-09-01",
                    "season": "2018/19",
                    "squad": "1st",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Hove",
                    "home_away": "H",
                    "pf": 25,
                    "pa": 10,
                    "result": "W",
                    "margin": 15,
                    "captain": "Jake Radcliffe",
                    "vc1": None,
                    "vc2": None,
                }
            ],
            "appearances": [
                {
                    "appearance_id": "2018-09-01_1st_Hove_10",
                    "game_id": "2018-09-01_1st_Hove",
                    "player": "Jake Radcliffe",
                    "shirt_number": 10,
                    "position": "Fly Half",
                    "position_group": "Backs",
                    "unit": "Backs",
                    "is_starter": True,
                    "is_captain": False,
                    "is_vc": False,
                    "player_join": "J Radcliffe",
                }
            ],
        }
        cache_file.write_text(json.dumps(payload), encoding="utf-8")

        self.backend.historic_pitchero_cache_file = cache_file
        games, appearances = self.backend._load_historic_pitchero_team_sheets(
            extractor=_ExtractorShouldNotBeCalled(),
            refresh_pitchero=False,
        )

        self.assertEqual(len(games), 1)
        self.assertEqual(len(appearances), 1)
        self.assertEqual(games.iloc[0]["season"], "2018/19")
        self.assertEqual(appearances.iloc[0]["player_join"], "J Radcliffe")

    def test_historic_loader_filters_out_non_historic_cache_rows(self):
        cache_file = self.temp_path / "historic_cache_with_modern_rows.json"
        payload = {
            "games": [
                {
                    "game_id": "2018-09-01_1st_Hove",
                    "date": "2018-09-01",
                    "season": "2018/19",
                    "squad": "1st",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Hove",
                    "home_away": "H",
                    "pf": 25,
                    "pa": 10,
                    "result": "W",
                    "margin": 15,
                    "captain": "Jake Radcliffe",
                    "vc1": None,
                    "vc2": None,
                },
                {
                    "game_id": "2025-03-22_2nd_Horsham_Barbarians",
                    "date": "2025-03-22",
                    "season": "2030/31",
                    "squad": "2nd",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Horsham Barbarians",
                    "home_away": "H",
                    "pf": 58,
                    "pa": 14,
                    "result": "W",
                    "margin": 44,
                    "captain": "Someone",
                    "vc1": None,
                    "vc2": None,
                },
            ],
            "appearances": [
                {
                    "appearance_id": "2018-09-01_1st_Hove_10",
                    "game_id": "2018-09-01_1st_Hove",
                    "player": "Jake Radcliffe",
                    "shirt_number": 10,
                    "position": "Fly Half",
                    "position_group": "Backs",
                    "unit": "Backs",
                    "is_starter": True,
                    "is_captain": False,
                    "is_vc": False,
                    "player_join": "J Radcliffe",
                },
                {
                    "appearance_id": "2025-03-22_2nd_Horsham_Barbarians_9",
                    "game_id": "2025-03-22_2nd_Horsham_Barbarians",
                    "player": "Titch Mitchell",
                    "shirt_number": 9,
                    "position": "Scrum Half",
                    "position_group": "Backs",
                    "unit": "Backs",
                    "is_starter": True,
                    "is_captain": False,
                    "is_vc": False,
                    "player_join": "T Mitchell",
                },
            ],
        }
        cache_file.write_text(json.dumps(payload), encoding="utf-8")

        self.backend.historic_pitchero_cache_file = cache_file
        games, appearances = self.backend._load_historic_pitchero_team_sheets(
            extractor=_ExtractorShouldNotBeCalled(),
            refresh_pitchero=False,
        )

        self.assertEqual(len(games), 1)
        self.assertEqual(games.iloc[0]["game_id"], "2018-09-01_1st_Hove")
        self.assertEqual(len(appearances), 1)
        self.assertEqual(appearances.iloc[0]["game_id"], "2018-09-01_1st_Hove")

    def test_build_games_blocks_pitchero_only_rows_in_google_covered_season(self):
        games_raw = pd.DataFrame(
            [
                {
                    "game_id": "g_google",
                    "date": "2025-03-22",
                    "season": "2024/25",
                    "squad": "2nd",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Horsham",
                    "home_away": "H",
                    "pf": 30,
                    "pa": 20,
                    "result": "W",
                    "captain": "Cap",
                    "vc1": None,
                    "vc2": None,
                    "_source": "google",
                },
                {
                    "game_id": "g_pitchero_extra",
                    "date": "2025-03-08",
                    "season": "2024/25",
                    "squad": "2nd",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Midhurst",
                    "home_away": "A",
                    "pf": 0,
                    "pa": 0,
                    "result": "D",
                    "captain": None,
                    "vc1": None,
                    "vc2": None,
                    "_source": "pitchero",
                },
            ]
        )

        games = self.backend._build_games(games_raw)
        self.assertEqual(len(games), 1)
        self.assertEqual(games.iloc[0]["opposition"], "Horsham")

    def test_historic_loader_raises_when_no_cache_and_no_bootstrap(self):
        self.backend.historic_pitchero_cache_file = self.temp_path / "missing_historic_cache.json"
        self.backend._bootstrap_historic_cache_from_local_backend = lambda: (pd.DataFrame(), pd.DataFrame())

        with self.assertRaises(FileNotFoundError):
            self.backend._load_historic_pitchero_team_sheets(
                extractor=_ExtractorShouldNotBeCalled(),
                refresh_pitchero=False,
            )

    def test_reconciliation_prefers_consistent_player_name(self):
        pitchero_raw = pd.DataFrame(
            [
                {
                    "Season": "2018/19",
                    "Squad": "2nd",
                    "Player_join": "J Radcliffe",
                    "A": 1,
                    "Event": "T",
                    "Count": 1,
                },
                {
                    "Season": "2019/20",
                    "Squad": "1st",
                    "Player_join": "J Radcliffe",
                    "A": 5,
                    "Event": "T",
                    "Count": 6,
                },
            ]
        )

        appearances = pd.DataFrame(
            [
                {
                    "game_id": "g1",
                    "player": "Jake Radcliffe",
                    "squad": "1st",
                    "season": "2019/20",
                    "date": pd.Timestamp("2019-09-01").date(),
                    "is_starter": True,
                    "is_captain": False,
                    "is_vice_captain": False,
                },
                {
                    "game_id": "g2",
                    "player": "Jake Radcliffe",
                    "squad": "1st",
                    "season": "2019/20",
                    "date": pd.Timestamp("2019-09-08").date(),
                    "is_starter": True,
                    "is_captain": False,
                    "is_vice_captain": False,
                },
            ]
        )

        reconciliation, _ = self.backend._build_pitchero_appearance_reconciliation(pitchero_raw, appearances)

        rows = reconciliation[reconciliation["player_join"] == "J Radcliffe"]
        self.assertFalse(rows.empty)
        self.assertTrue((rows["player"] == "Jake Radcliffe").all())

    def test_reconciliation_applies_canonical_google_name_mappings(self):
        pitchero_raw = pd.DataFrame(
            [
                {
                    "Season": "2019/20",
                    "Squad": "1st",
                    "Player_join": "T Byron",
                    "A": 3,
                    "Event": "T",
                    "Count": 2,
                }
            ]
        )

        appearances = pd.DataFrame(
            [
                {
                    "game_id": "g1",
                    "player": "Thomas Byron",
                    "squad": "1st",
                    "season": "2019/20",
                    "date": pd.Timestamp("2019-09-01").date(),
                    "is_starter": True,
                    "is_captain": False,
                    "is_vice_captain": False,
                },
                {
                    "game_id": "g2",
                    "player": "Tom Byron",
                    "squad": "1st",
                    "season": "2019/20",
                    "date": pd.Timestamp("2019-09-08").date(),
                    "is_starter": True,
                    "is_captain": False,
                    "is_vice_captain": False,
                },
            ]
        )

        reconciliation, _ = self.backend._build_pitchero_appearance_reconciliation(pitchero_raw, appearances)

        rows = reconciliation[reconciliation["player_join"] == "T Byron"]
        self.assertFalse(rows.empty)
        self.assertTrue((rows["player"] == "Tom Byron").all())

    def test_build_games_canonicalizes_historic_pitchero_oppositions(self):
        games_raw = pd.DataFrame(
            [
                {
                    "game_id": "g1",
                    "date": "2019-09-01",
                    "season": "2019/20",
                    "squad": "1st",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "CRAWLEY - CUP FINAL",
                    "home_away": "A",
                    "pf": 10,
                    "pa": 5,
                    "result": "W",
                    "captain": "Cap",
                    "vc1": None,
                    "vc2": None,
                },
                {
                    "game_id": "g2",
                    "date": "2019-09-08",
                    "season": "2019/20",
                    "squad": "2nd",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Uckfield 2s",
                    "home_away": "H",
                    "pf": 8,
                    "pa": 12,
                    "result": "L",
                    "captain": "Cap",
                    "vc1": None,
                    "vc2": None,
                },
                {
                    "game_id": "g3",
                    "date": "2025-09-01",
                    "season": "2025/26",
                    "squad": "1st",
                    "competition": "Friendly",
                    "game_type": "Friendly",
                    "opposition": "Uckfield RFC",
                    "home_away": "A",
                    "pf": 14,
                    "pa": 14,
                    "result": "D",
                    "captain": "Cap",
                    "vc1": None,
                    "vc2": None,
                },
            ]
        )

        games = self.backend._build_games(games_raw)
        self.assertEqual(sorted(games["opposition"].tolist()), ["Crawley", "Uckfield", "Uckfield II"])

    def test_build_games_deduplicates_canonicalized_opposition_collisions(self):
        games_raw = pd.DataFrame(
            [
                {
                    "game_id": "g1",
                    "date": "2019-01-26",
                    "season": "2018/19",
                    "squad": "1st",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "DITCHLING RFC",
                    "home_away": "A",
                    "pf": 12,
                    "pa": 10,
                    "result": "W",
                    "captain": "Cap",
                    "vc1": None,
                    "vc2": None,
                },
                {
                    "game_id": "g2",
                    "date": "2019-01-26",
                    "season": "2018/19",
                    "squad": "1st",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Ditchling",
                    "home_away": "A",
                    "pf": 12,
                    "pa": 10,
                    "result": "W",
                    "captain": "Cap",
                    "vc1": None,
                    "vc2": None,
                },
            ]
        )

        games = self.backend._build_games(games_raw)
        self.assertEqual(len(games), 1)
        self.assertEqual(games.iloc[0]["opposition"], "Ditchling")

    def test_season_scorers_aggregate_match_level_scorer_payloads(self):
        appearances = pd.DataFrame(
            [
                {
                    "player": "Max Crawley-Moore",
                    "squad": "1st",
                    "season": "2019/20",
                    "date": pd.Timestamp("2019-09-14").date(),
                    "game_id": "g1",
                    "game_type": "League",
                },
                {
                    "player": "Ollie Adams",
                    "squad": "1st",
                    "season": "2019/20",
                    "date": pd.Timestamp("2019-09-14").date(),
                    "game_id": "g1",
                    "game_type": "League",
                },
                {
                    "player": "Ollie Adams",
                    "squad": "1st",
                    "season": "2019/20",
                    "date": pd.Timestamp("2019-09-21").date(),
                    "game_id": "g2",
                    "game_type": "League",
                },
            ]
        )

        games = pd.DataFrame(
            [
                {
                    "game_id": "g1",
                    "squad": "1st",
                    "season": "2019/20",
                    "game_type": "League",
                    "tries_scorers": '{"M Crawley-Moore": 1}',
                    "conversions_scorers": '{"O Adams": 2}',
                    "penalties_scorers": '{}',
                    "drop_goals_scorers": '{}',
                },
                {
                    "game_id": "g2",
                    "squad": "1st",
                    "season": "2019/20",
                    "game_type": "League",
                    "tries_scorers": '{"O Adams": 1}',
                    "conversions_scorers": '{}',
                    "penalties_scorers": '{"O Adams": 1}',
                    "drop_goals_scorers": '{}',
                },
            ]
        )

        scorers = self.backend._build_season_scorers(
            scorers_2526_raw=pd.DataFrame(),
            pitchero_raw=pd.DataFrame(),
            appearances=appearances,
            games=games,
        )

        crawley_moore = scorers[scorers["player"] == "Max Crawley-Moore"].iloc[0]
        self.assertEqual(crawley_moore["tries"], 1)
        self.assertEqual(crawley_moore["points"], 5)
        self.assertEqual(crawley_moore["source"], "games")

        adams = scorers[scorers["player"] == "Ollie Adams"].iloc[0]
        self.assertEqual(adams["tries"], 1)
        self.assertEqual(adams["conversions"], 2)
        self.assertEqual(adams["penalties"], 1)
        self.assertEqual(adams["drop_goals"], 0)
        self.assertEqual(adams["points"], 12)

    def test_build_games_prefers_scored_and_lineup_backed_duplicate(self):
        games_raw = pd.DataFrame(
            [
                {
                    "game_id": "g_no_score",
                    "date": "2019-01-26",
                    "season": "2018/19",
                    "squad": "1st",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "DITCHLING RFC",
                    "home_away": "A",
                    "pf": None,
                    "pa": None,
                    "result": None,
                    "captain": None,
                    "vc1": None,
                    "vc2": None,
                },
                {
                    "game_id": "g_scored",
                    "date": "2019-01-26",
                    "season": "2018/19",
                    "squad": "1st",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Ditchling",
                    "home_away": "A",
                    "pf": 12,
                    "pa": 10,
                    "result": "W",
                    "captain": "Cap",
                    "vc1": None,
                    "vc2": None,
                },
            ]
        )

        appearances_raw = pd.DataFrame(
            [
                {
                    "appearance_id": "a1",
                    "game_id": "g_scored",
                    "player": "Test Player",
                    "shirt_number": 10,
                    "position": "Fly Half",
                    "position_group": "Backs",
                    "unit": "Backs",
                    "is_starter": True,
                    "is_captain": False,
                    "is_vc": False,
                    "player_join": "T Player",
                }
            ]
        )

        games = self.backend._build_games(games_raw, appearances_raw)
        self.assertEqual(len(games), 1)
        self.assertEqual(games.iloc[0]["opposition"], "Ditchling")
        self.assertEqual(int(games.iloc[0]["score_for"]), 12)
        self.assertEqual(int(games.iloc[0]["score_against"]), 10)

    def test_season_scorers_2526_sheet_rows_are_fallback_only(self):
        appearances = pd.DataFrame(
            [
                {
                    "player": "Ollie Adams",
                    "squad": "1st",
                    "season": "2025/26",
                    "date": pd.Timestamp("2025-09-13").date(),
                    "game_id": "g2526",
                    "game_type": "League",
                }
            ]
        )

        games = pd.DataFrame(
            [
                {
                    "game_id": "g2526",
                    "squad": "1st",
                    "season": "2025/26",
                    "game_type": "League",
                    "date": pd.Timestamp("2025-09-13").date(),
                    "opposition": "Hove",
                    "tries_scorers": '{"O Adams": 1}',
                    "conversions_scorers": "{}",
                    "penalties_scorers": "{}",
                    "drop_goals_scorers": "{}",
                }
            ]
        )

        scorers_2526_raw = pd.DataFrame(
            [
                {
                    "Squad": "1st",
                    "Date": "2025-09-13",
                    "Opposition": "Hove",
                    "Score": "TRY",
                    "Count": 1,
                    "Player": "O Adams",
                }
            ]
        )

        scorers = self.backend._build_season_scorers(
            scorers_2526_raw=scorers_2526_raw,
            pitchero_raw=pd.DataFrame(),
            appearances=appearances,
            games=games,
        )

        adams = scorers[scorers["player"] == "Ollie Adams"]
        self.assertEqual(len(adams), 1)
        self.assertEqual(int(adams.iloc[0]["tries"]), 1)
        self.assertEqual(int(adams.iloc[0]["points"]), 5)

    def test_egrfc_alias_matching_accepts_abbreviated_pitchero_team_names(self):
        self.assertTrue(DataExtractor._is_egrfc_team_name("East Grinstead"))
        self.assertTrue(DataExtractor._is_egrfc_team_name("E. Grinstead 2"))
        self.assertTrue(DataExtractor._is_egrfc_team_name("EG Men 2"))
        self.assertTrue(DataExtractor._is_egrfc_team_name("EAST GRINSTEAD RFC"))

    def test_egrfc_alias_matching_rejects_non_egrfc_team_names(self):
        self.assertFalse(DataExtractor._is_egrfc_team_name("Rye"))
        self.assertFalse(DataExtractor._is_egrfc_team_name("Crowboro 2"))
        self.assertFalse(DataExtractor._is_egrfc_team_name("Heathfield 3"))

    def test_annotate_appearance_numbers_adds_club_and_first_xv_counters(self):
        appearances = pd.DataFrame(
            [
                {
                    "squad": "1st",
                    "date": pd.Timestamp("2024-09-14").date(),
                    "player": "Sam Example",
                    "shirt_number": 10,
                    "position": "Fly Half",
                    "unit": "Backs",
                    "is_captain": False,
                    "is_vice_captain": False,
                    "game_id": "g2",
                    "season": "2024/25",
                    "game_type": "League",
                    "is_starter": True,
                    "is_backfill": False,
                },
                {
                    "squad": "2nd",
                    "date": pd.Timestamp("2024-09-07").date(),
                    "player": "Sam Example",
                    "shirt_number": 15,
                    "position": "Full Back",
                    "unit": "Backs",
                    "is_captain": False,
                    "is_vice_captain": False,
                    "game_id": "g1",
                    "season": "2024/25",
                    "game_type": "League",
                    "is_starter": True,
                    "is_backfill": False,
                },
                {
                    "squad": "1st",
                    "date": pd.Timestamp("2024-09-21").date(),
                    "player": "Sam Example",
                    "shirt_number": 12,
                    "position": "Inside Centre",
                    "unit": "Backs",
                    "is_captain": False,
                    "is_vice_captain": False,
                    "game_id": "g3",
                    "season": "2024/25",
                    "game_type": "League",
                    "is_starter": True,
                    "is_backfill": False,
                },
            ]
        )

        annotated = self.backend._annotate_appearance_numbers(appearances)
        player_rows = annotated[annotated["player"] == "Sam Example"].sort_values("date")

        self.assertEqual(player_rows["club_appearance_number"].tolist(), [1, 2, 3])
        self.assertTrue(pd.isna(player_rows.iloc[0]["first_xv_appearance_number"]))
        self.assertEqual(player_rows.iloc[1]["first_xv_appearance_number"], 1)
        self.assertEqual(player_rows.iloc[2]["first_xv_appearance_number"], 2)

    def test_build_season_scorers_uses_count_column_for_2526_sheet(self):
        scorers_2526_raw = pd.DataFrame(
            [
                {
                    "Squad": "1st",
                    "Date": "2025-09-07",
                    "Opposition": "Hove",
                    "Score": "TRY",
                    "Count": 2,
                    "Player": "Alice Example",
                    "Points": "5",
                },
                {
                    "Squad": "1st",
                    "Date": "2025-09-07",
                    "Opposition": "Hove",
                    "Score": "CON",
                    "Count": 1,
                    "Player": "Alice Example",
                    "Points": "2",
                },
                {
                    "Squad": "1st",
                    "Date": "2025-09-07",
                    "Opposition": "Hove",
                    "Score": "PK",
                    "Count": 2,
                    "Player": "Bob Example",
                    "Points": "3",
                },
            ]
        )
        games = pd.DataFrame(
            [
                {
                    "game_id": "g1",
                    "squad": "1st",
                    "date": pd.Timestamp("2025-09-07").date(),
                    "season": "2025/26",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Hove",
                    "home_away": "H",
                    "score_for": 22,
                    "score_against": 10,
                    "result": "W",
                    "captain": "Cap",
                    "vice_captain_1": None,
                    "vice_captain_2": None,
                }
            ]
        )
        out = self.backend._build_season_scorers(
            scorers_2526_raw=scorers_2526_raw,
            pitchero_raw=pd.DataFrame(columns=["Season", "Squad", "Player_join", "A", "Event", "Count"]),
            appearances=pd.DataFrame(columns=["player"]),
            games=games,
        )

        alice = out[(out["player"] == "Alice Example") & (out["squad"] == "1st")].iloc[0]
        bob = out[(out["player"] == "Bob Example") & (out["squad"] == "1st")].iloc[0]

        self.assertEqual(int(alice["tries"]), 2)
        self.assertEqual(int(alice["conversions"]), 1)
        self.assertEqual(int(alice["points"]), 12)
        self.assertEqual(int(bob["penalties"]), 2)
        self.assertEqual(int(bob["points"]), 6)

    def test_attach_match_scorers_merges_per_game_counts(self):
        games = pd.DataFrame(
            [
                {
                    "game_id": "g1",
                    "squad": "1st",
                    "date": pd.Timestamp("2025-09-07").date(),
                    "season": "2025/26",
                    "competition": "League",
                    "game_type": "League",
                    "opposition": "Hove",
                    "home_away": "H",
                    "score_for": 22,
                    "score_against": 10,
                    "result": "W",
                    "captain": "Cap",
                    "vice_captain_1": None,
                    "vice_captain_2": None,
                }
            ]
        )
        scorers_2526_raw = pd.DataFrame(
            [
                {
                    "Squad": "1st",
                    "Date": "2025-09-07",
                    "Opposition": "Hove",
                    "Score": "TRY",
                    "Count": 2,
                    "Player": "Alice Example",
                    "Points": "5",
                },
                {
                    "Squad": "1st",
                    "Date": "2025-09-07",
                    "Opposition": "Hove",
                    "Score": "CON",
                    "Count": 1,
                    "Player": "Alice Example",
                    "Points": "2",
                },
                {
                    "Squad": "1st",
                    "Date": "2025-09-07",
                    "Opposition": "Hove",
                    "Score": "PK",
                    "Count": 2,
                    "Player": "Bob Example",
                    "Points": "3",
                },
            ]
        )

        out = self.backend._attach_match_scorers(games, scorers_2526_raw)
        row = out.iloc[0]

        self.assertEqual(json.loads(row["tries_scorers"]), {"Alice Example": 2})
        self.assertEqual(json.loads(row["conversions_scorers"]), {"Alice Example": 1})
        self.assertEqual(json.loads(row["penalties_scorers"]), {"Bob Example": 2})
        self.assertTrue(pd.isna(row["drop_goals_scorers"]))


if __name__ == "__main__":
    unittest.main()
