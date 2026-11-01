"""Offline checks for the observed in-game workbook layouts and read-only access."""

from io import BytesIO
import unittest
from typing import Any, Dict
from unittest.mock import Mock

from openpyxl import Workbook

from python.in_game_stats import InGameStatsSource, XLSX_MIME_TYPE, parse_workbook


def sample_snapshot() -> Dict[str, Any]:
    """Represent all observed layouts without depending on live credentials."""
    return {
        "source": {"id": "test-file", "name": "Stats.xlsx"},
        "worksheets": [
            {"title": "Stats Summary", "rows": [
                ["Full Game"], ["Name", "EG", "Horsham", "Total"],
                ["Tackles", 136, 55, 191], ["+", 26, 5, 31], ["Miss", 21, 17, 38],
                [None], ["Halves"], ["Name", "EG 1st", "Horsham 1st", "EG 2nd", "Horsham 2nd", "Total"],
                ["Tackles", 70, 34, 66, 21, 191],
                ["Quarters"], ["Name", "EG Q1", "Horsham Q1", "Total"],
                ["Tackles", 26, 16, 42],
            ]},
            {"title": "Possession & Time", "rows": [
                ["Possession & Time - Minutes:Seconds"],
                ["Measure", "Full game", "First half"],
                ["Ball out of play", "60:33", "28:56"],
            ]},
            {"title": "Events", "rows": [
                ["Code", "Labels", "Start", "End", "Notes", "Clip ID", "Team"],
                ["Tackles", "", 662.667, 670.468, "", "clip-1", "EG"],
                ["Scrum", "+", 634.973, 646.477, "note", "clip-2", "EG"],
            ]},
        ],
    }


class InGameStatsTests(unittest.TestCase):
    """Keep source distinctions and fail explicitly when the layout is invalid."""

    def test_summary_parent_metrics_periods_totals_and_zero(self) -> None:
        """Keep subrows linked to metrics and totals distinct from team records."""
        snapshot = sample_snapshot()
        snapshot["worksheets"][0]["rows"][3][1] = 0
        parsed = parse_workbook(snapshot, game_id="fixture")
        summary = parsed["summary"]
        self.assertEqual(summary[3]["metric"], "Tackles")
        self.assertEqual(summary[3]["outcome"], "+")
        self.assertEqual(summary[3]["count"], 0)
        self.assertEqual(summary[6]["outcome"], "Miss")
        self.assertTrue(summary[2]["is_total"])
        self.assertIsNone(summary[2]["team"])
        self.assertEqual(summary[9]["period"], "first_half")
        self.assertEqual(summary[11]["period"], "second_half")
        self.assertEqual(summary[14]["period"], "quarter_1")
        self.assertEqual(summary[0]["game_id"], "fixture")
        self.assertEqual(parsed["warnings"], [])

    def test_durations_and_unlabelled_events(self) -> None:
        """Convert elapsed time without treating clip times as the match clock."""
        parsed = parse_workbook(sample_snapshot())
        self.assertEqual(parsed["possession"][0]["duration_seconds"], 3633)
        event = parsed["events"][0]
        self.assertIsNone(event["label"])
        self.assertEqual(event["clip_duration_seconds"], 7.801)
        self.assertEqual(event["source_row"], 2)
        self.assertEqual(len(parsed["warnings"]), 1)

    def test_invalid_duration_has_source_location(self) -> None:
        """Reject malformed source values instead of silently discarding them."""
        snapshot = sample_snapshot()
        snapshot["worksheets"][1]["rows"][2][1] = "01:75"
        with self.assertRaisesRegex(ValueError, "Possession & Time, row 3"):
            parse_workbook(snapshot)

    def test_invalid_event_interval_is_rejected(self) -> None:
        """Do not emit negative clip durations."""
        snapshot = sample_snapshot()
        snapshot["worksheets"][2]["rows"][1][3] = 1
        with self.assertRaisesRegex(ValueError, "Events, row 2"):
            parse_workbook(snapshot)

    def test_unknown_and_missing_sheets(self) -> None:
        """Report extra tabs, but fail if a required tab disappears."""
        snapshot = sample_snapshot()
        snapshot["worksheets"].append({"title": "Extra", "rows": []})
        self.assertIn("Unparsed worksheet: Extra", parse_workbook(snapshot)["warnings"])
        snapshot["worksheets"] = snapshot["worksheets"][:2]
        with self.assertRaisesRegex(ValueError, "Missing or empty required worksheet: Events"):
            parse_workbook(snapshot)

    def test_download_uses_only_get_and_preserves_cells(self) -> None:
        """Check the Drive download path using an in-memory Excel fixture."""
        workbook = Workbook()
        workbook.active.append(["Name", None, "EG"])
        workbook.active.append(["Scrum", None, 0])
        content = BytesIO()
        workbook.save(content)
        workbook.close()
        session = Mock()
        metadata = Mock()
        metadata.json.return_value = {
            "id": "file", "mimeType": XLSX_MIME_TYPE,
            "capabilities": {"canDownload": True},
        }
        download = Mock(content=content.getvalue())
        session.get.side_effect = [metadata, download]
        snapshot = InGameStatsSource(file_id="file", session=session).read_workbook()
        self.assertEqual(snapshot["worksheets"][0]["rows"][1], ["Scrum", None, 0])
        self.assertEqual(session.get.call_count, 2)
        session.post.assert_not_called()
        session.patch.assert_not_called()


if __name__ == "__main__":
    unittest.main()