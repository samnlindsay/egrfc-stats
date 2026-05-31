import unittest

from python.utils.normalization import (
    is_egrfc_team_name,
    normalize_lookup_key,
    normalize_team_name,
    season_start_year,
    season_to_dash_label,
    season_to_short_label,
)


class NormalizationTests(unittest.TestCase):
    def test_normalize_lookup_key_removes_non_alphanumerics(self):
        self.assertEqual(normalize_lookup_key("Brighton & Hove II"), "brightonhoveii")

    def test_normalize_team_name_preserves_word_boundaries(self):
        self.assertEqual(normalize_team_name("E. Grinstead 2"), "e grinstead 2")

    def test_is_egrfc_team_name_accepts_known_aliases(self):
        self.assertTrue(is_egrfc_team_name("East Grinstead"))
        self.assertTrue(is_egrfc_team_name("E. Grinstead 2"))
        self.assertTrue(is_egrfc_team_name("EG Men 2"))

    def test_is_egrfc_team_name_rejects_other_clubs(self):
        self.assertFalse(is_egrfc_team_name("Rye"))
        self.assertFalse(is_egrfc_team_name("Crowboro 2"))

    def test_season_to_dash_label_normalizes_short_and_long_forms(self):
        self.assertEqual(season_to_dash_label("2024/25"), "2024-2025")
        self.assertEqual(season_to_dash_label("2024/2025"), "2024-2025")
        self.assertEqual(season_to_dash_label("2024-2025"), "2024-2025")

    def test_season_to_short_label_normalizes_short_and_long_forms(self):
        self.assertEqual(season_to_short_label("2024/25"), "2024/25")
        self.assertEqual(season_to_short_label("2024/2025"), "2024/25")
        self.assertEqual(season_to_short_label("2024-2025"), "2024/25")

    def test_season_start_year_extracts_from_supported_formats(self):
        self.assertEqual(season_start_year("2024/25"), 2024)
        self.assertEqual(season_start_year("2024-2025"), 2024)
        self.assertIsNone(season_start_year("Total"))