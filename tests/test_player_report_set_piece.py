import unittest

import duckdb

from python.reports import (
    ReportGenerator,
    _has_majority_tight5_starts,
    _meets_jumper_attempt_threshold,
    _player_name_key,
    _report_scorer_player_key,
    _started_set_piece_summary_rows,
)


class PlayerReportSetPieceTests(unittest.TestCase):
    def setUp(self):
        self.report = object.__new__(ReportGenerator)
        self.report.con = duckdb.connect(":memory:")
        self.report.con.create_function("report_player_key", _player_name_key, [str], str)
        self.report.con.create_function("report_scorer_key", _report_scorer_player_key, [str, str], str)
        self.report.con.execute(
            """CREATE TABLE player_appearances (
                   game_id TEXT, season TEXT, squad TEXT, player TEXT, is_starter BOOLEAN
               )"""
        )
        self.report.con.execute(
            """CREATE TABLE set_piece (
                   game_id TEXT, season TEXT, squad TEXT, team TEXT,
                   scrums_won INTEGER, scrums_total INTEGER,
                   lineouts_won INTEGER, lineouts_total INTEGER
               )"""
        )
        self.report.con.execute(
            """CREATE TABLE player_appearances_stage_pitchero (
                   game_id TEXT, date DATE, squad TEXT, player TEXT
               )"""
        )
        self.report.con.execute(
            """CREATE TABLE player_appearances_stage_google (
                   game_id TEXT, date DATE, squad TEXT, player TEXT
               )"""
        )
        self.report.con.execute(
            """CREATE TABLE scorers_stage_pitchero (
                   game_id TEXT, date DATE, squad TEXT, season TEXT, player TEXT, tries INTEGER
               )"""
        )
        self.report.con.execute(
            """CREATE TABLE lineouts (
                   game_id TEXT, date DATE, squad TEXT, jumper TEXT, thrower TEXT,
                   area TEXT, season TEXT, won BOOLEAN
               )"""
        )

    def tearDown(self):
        self.report.con.close()

    def test_tight5_eligibility_requires_strict_majority_of_starts(self):
        starts = [
            {"is_starter": True, "position": "Prop"},
            {"is_starter": True, "position": "Second Row"},
            {"is_starter": True, "position": "Flanker"},
            {"is_starter": True, "position": "Flanker"},
            {"is_starter": False, "position": "Hooker"},
        ]
        self.assertFalse(_has_majority_tight5_starts(starts))
        starts.append({"is_starter": True, "position": "Hooker"})
        self.assertTrue(_has_majority_tight5_starts(starts))

    def test_jumper_threshold_is_inclusive_at_ten_attempts(self):
        self.assertFalse(_meets_jumper_attempt_threshold(9))
        self.assertTrue(_meets_jumper_attempt_threshold(10))

    def test_season_table_groups_both_squads_and_summed_overall(self):
        rows = _started_set_piece_summary_rows(
            [
                {"season": "2024/25", "squad": "1st", "scrums_won": 8, "scrums_total": 10},
                {"season": "2024/25", "squad": "2nd", "scrums_won": 2, "scrums_total": 5},
                {"season": "2025/26", "squad": "1st", "scrums_won": 3, "scrums_total": 4},
            ],
            "scrums_won",
            "scrums_total",
        )

        self.assertEqual(rows[0], ["2024/25", 8, 10, "80.0%", 2, 5, "40.0%", 10, 15, "66.7%"])
        self.assertEqual(rows[1], ["2025/26", 3, 4, "75.0%", "", "", "", 3, 4, "75.0%"])
        self.assertEqual(rows[2], ["Total", 11, 14, "78.6%", 2, 5, "40.0%", 13, 19, "68.4%"])

    def test_started_set_piece_query_uses_only_player_starts_and_egrfc_rows(self):
        self.report.con.executemany(
            "INSERT INTO player_appearances VALUES (?, ?, ?, ?, ?)",
            [
                ("g1", "2025/26", "1st", "Test Player", True),
                ("g2", "2025/26", "1st", "Test Player", False),
                ("g3", "2025/26", "1st", "Other Player", True),
                ("g4", "2025/26", "2nd", "Test Player", True),
            ],
        )
        self.report.con.executemany(
            "INSERT INTO set_piece VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("g1", "2025/26", "1st", "EGRFC", 8, 10, 7, 9),
                ("g1", "2025/26", "1st", "Opposition", 1, 2, 1, 2),
                ("g2", "2025/26", "1st", "EGRFC", 9, 10, 8, 9),
                ("g3", "2025/26", "1st", "EGRFC", 1, 2, 1, 2),
                ("g4", "2025/26", "2nd", "EGRFC", 3, 4, 2, 3),
            ],
        )

        rows = self.report._started_set_piece_success("Test Player")

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [(row["squad"], row["scrums_won"], row["scrums_total"], row["lineouts_won"], row["lineouts_total"]) for row in rows],
            [("1st", 8, 10, 7, 9), ("2nd", 3, 4, 2, 3)],
        )

    def test_pitchero_name_alias_requires_same_game_canonical_evidence(self):
        self.report.con.executemany(
            "INSERT INTO player_appearances_stage_pitchero VALUES (?, ?, ?, ?)",
            [
                ("g1", "2022-02-19", "1st", "Sam Lindsay"),
                ("g2", "2022-02-26", "1st", "Sam Lindsay"),
            ],
        )
        self.report.con.execute(
            "INSERT INTO player_appearances_stage_google VALUES (?, ?, ?, ?)",
            ["g1", "2022-02-19", "1st", "Sam Lindsay-McCall"],
        )
        self.report.con.executemany(
            "INSERT INTO lineouts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("g1", "2022-02-19", "1st", "Sam Lindsay", "Hooker A", "Front", "2021/22", True),
                ("g2", "2022-02-26", "1st", "Sam Lindsay", "Hooker A", "Front", "2021/22", True),
            ],
        )

        alias_games = self.report._pitchero_alias_game_keys("Sam Lindsay-McCall")
        match_sql, params = self.report._lineout_role_match_sql("jumper", "Sam Lindsay-McCall")
        attempts = self.report._rows(f"SELECT lo.game_id FROM lineouts lo WHERE {match_sql}", params)

        self.assertEqual(alias_games, {("g1", duckdb.sql("SELECT DATE '2022-02-19'").fetchone()[0], "1st")})
        self.assertEqual([row["game_id"] for row in attempts], ["g1"])

    def test_pitchero_scorer_alias_is_resolved_by_season(self):
        self.assertEqual(
            _report_scorer_player_key("S Lindsay", "2022/23"),
            _player_name_key("Sam Lindsay-McCall"),
        )
        self.assertEqual(
            _report_scorer_player_key("S Lindsay", "2019/20"),
            _player_name_key("Sam Lindsay"),
        )

    def test_pitchero_scorer_stage_marks_same_player_game_as_pitchero_source(self):
        self.report.con.execute(
            "INSERT INTO scorers_stage_pitchero VALUES (?, ?, ?, ?, ?, ?)",
            ["g1", "2022-02-19", "1st", "2021/22", "S Lindsay", 1],
        )

        game_keys = self.report._pitchero_scorer_game_keys("Sam Lindsay-McCall")

        self.assertEqual(game_keys, {("g1", duckdb.sql("SELECT DATE '2022-02-19'").fetchone()[0], "1st")})


if __name__ == "__main__":
    unittest.main()