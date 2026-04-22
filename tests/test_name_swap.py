"""Tests for first/last name swap detection (spec 21)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from src.normalize import normalize_name
from src.french_names import is_french_first_name


class TestSwapDetection(unittest.TestCase):
    def test_clear_order_uppercase_surname(self):
        """When case makes it obvious, no lexicon is needed."""
        self.assertEqual(normalize_name("DUPONT Jean"), ("", "DUPONT", "Jean"))
        self.assertEqual(normalize_name("Jean DUPONT"), ("", "DUPONT", "Jean"))

    def test_all_titlecase_first_is_prenom(self):
        """'Jean Dupont' — Jean is a known first name, Dupont isn't: swap."""
        self.assertEqual(normalize_name("Jean Dupont"), ("", "DUPONT", "Jean"))

    def test_all_titlecase_last_is_prenom(self):
        """'Dupont Jean' — keep convention (nom first)."""
        self.assertEqual(normalize_name("Dupont Jean"), ("", "DUPONT", "Jean"))

    def test_hyphenated_prenom_at_start(self):
        """'Marie-Claire Martin' — compound first name, surname last."""
        self.assertEqual(
            normalize_name("Marie-Claire Martin"),
            ("", "MARTIN", "Marie-Claire"),
        )

    def test_hyphenated_prenom_at_end(self):
        self.assertEqual(
            normalize_name("Martin Jean-Pierre"),
            ("", "MARTIN", "Jean-Pierre"),
        )

    def test_neither_recognized_falls_back(self):
        """Foreign names: neither in lexicon, first word = nom convention."""
        self.assertEqual(normalize_name("Smith Jones"), ("", "SMITH", "Jones"))

    def test_both_recognized_falls_back(self):
        """Both are common first names: keep convention (first = nom)."""
        # Pierre and Jean are both first names
        self.assertEqual(normalize_name("Pierre Jean"), ("", "PIERRE", "Jean"))

    def test_title_preserved(self):
        self.assertEqual(normalize_name("Dr Jean Dupont"), ("Dr", "DUPONT", "Jean"))
        self.assertEqual(normalize_name("Pr Dupont Jean"), ("Pr", "DUPONT", "Jean"))

    def test_is_french_first_name_basic(self):
        self.assertTrue(is_french_first_name("Jean"))
        self.assertTrue(is_french_first_name("jean"))
        self.assertTrue(is_french_first_name("Jean-Pierre"))
        self.assertTrue(is_french_first_name("Émilie"))  # accent
        self.assertFalse(is_french_first_name("Dupont"))
        self.assertFalse(is_french_first_name(""))


if __name__ == "__main__":
    unittest.main()
