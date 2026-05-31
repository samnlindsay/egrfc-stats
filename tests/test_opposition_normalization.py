import unittest

from python.utils.opposition import (
    canonicalize_opposition_name,
    opposition_club_name,
    split_opposition_components,
    team_number_to_ordinal_label,
)


class OppositionNormalizationTests(unittest.TestCase):
    def test_pitchero_aliases_map_to_canonical_names(self):
        self.assertEqual(canonicalize_opposition_name("burgesshillrfc"), "Burgess Hill")
        self.assertEqual(canonicalize_opposition_name("horshamlions"), "Horsham II")
        self.assertEqual(canonicalize_opposition_name("worthingraidersa"), "Worthing II")

    def test_suffix_fallback_promotes_numeric_to_roman(self):
        self.assertEqual(canonicalize_opposition_name("Example Club 2s"), "Example Club II")

    def test_split_components_returns_club_and_team_number(self):
        self.assertEqual(split_opposition_components("Haywards Heath II"), ("Haywards Heath", 2))
        self.assertEqual(split_opposition_components("Worthing 3rd XV"), ("Worthing", 3))
        self.assertEqual(split_opposition_components("Eastbourne"), ("Eastbourne", None))

    def test_opposition_club_name_and_label_helpers(self):
        self.assertEqual(opposition_club_name("Worthing III"), "Worthing")
        self.assertEqual(team_number_to_ordinal_label(2), "2nd")
        self.assertIsNone(team_number_to_ordinal_label(None))
