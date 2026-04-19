"""Unit tests for normalize.py."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from src.normalize import (
    clean_text,
    normalize_phone,
    normalize_name,
    split_multiple_names,
    split_at_field_labels,
    edit_distance,
    strip_accents,
)


class TestCleanText(unittest.TestCase):
    def test_non_breaking_space(self):
        self.assertEqual(clean_text("hello\xa0world"), "hello world")

    def test_collapse_whitespace(self):
        self.assertEqual(clean_text("a   b  c"), "a b c")

    def test_strip(self):
        self.assertEqual(clean_text("  foo  "), "foo")

    def test_empty(self):
        self.assertEqual(clean_text(""), "")
        self.assertEqual(clean_text(None), "")

    def test_zero_width_space(self):
        self.assertEqual(clean_text("a\u200bb"), "ab")


class TestNormalizePhone(unittest.TestCase):
    def test_standard_format(self):
        self.assertEqual(normalize_phone("01 40 03 20 00"), "01 40 03 20 00")

    def test_compact_digits(self):
        self.assertEqual(normalize_phone("0477828118"), "04 77 82 81 18")

    def test_dotted_format(self):
        self.assertEqual(normalize_phone("05.34.55.84.58"), "05 34 55 84 58")

    def test_with_label(self):
        result = normalize_phone("Secrétariat : 01 40 03 20 00")
        self.assertEqual(result, "01 40 03 20 00")

    def test_multiple_phones(self):
        result = normalize_phone("01 40 05 45 45 ou 01 42 16 00 00")
        self.assertIn("01 40 05 45 45", result)
        self.assertIn("01 42 16 00 00", result)

    def test_plus33_prefix(self):
        result = normalize_phone("+33 5 34 55 74 23")
        self.assertEqual(result, "05 34 55 74 23")

    def test_empty(self):
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_no_phone(self):
        self.assertEqual(normalize_phone("pas de téléphone"), "")


class TestNormalizeName(unittest.TestCase):
    def test_uppercase_lastname_titlecase_firstname(self):
        titre, nom, prenom = normalize_name("HOGAN Julien")
        self.assertEqual(nom, "HOGAN")
        self.assertEqual(prenom, "Julien")
        self.assertEqual(titre, "")

    def test_with_dr_title(self):
        titre, nom, prenom = normalize_name("Dr SIMON Thomas")
        self.assertEqual(titre, "Dr")
        self.assertEqual(nom, "SIMON")
        self.assertEqual(prenom, "Thomas")

    def test_with_pr_title(self):
        titre, nom, prenom = normalize_name("Pr CHAUVEAU Dominique")
        self.assertEqual(titre, "Pr")
        self.assertEqual(nom, "CHAUVEAU")
        self.assertEqual(prenom, "Dominique")

    def test_professeur_title(self):
        titre, nom, prenom = normalize_name("Professeur RIGOTHIER CLAIRE")
        self.assertEqual(titre, "Pr")
        self.assertEqual(nom, "RIGOTHIER")
        self.assertEqual(prenom, "CLAIRE")

    def test_compound_lastname(self):
        titre, nom, prenom = normalize_name("HACHON LE CAMUS Caroline")
        self.assertEqual(nom, "HACHON LE CAMUS")
        self.assertEqual(prenom, "Caroline")

    def test_firstname_then_uppercase_lastname(self):
        """Word doc format: Firstname LASTNAME."""
        titre, nom, prenom = normalize_name("Pr Jérome HARAMBAT")
        self.assertEqual(titre, "Pr")
        self.assertEqual(nom, "HARAMBAT")
        self.assertEqual(prenom, "Jérome")

    def test_hyphenated_lastname(self):
        titre, nom, prenom = normalize_name("REYNAUD-GAUBERT Martine")
        self.assertEqual(nom, "REYNAUD-GAUBERT")
        self.assertEqual(prenom, "Martine")

    def test_all_titlecase(self):
        """When no uppercase word, first word = nom."""
        titre, nom, prenom = normalize_name("Mauras Mathilde")
        self.assertEqual(nom, "MAURAS")
        self.assertEqual(prenom, "Mathilde")

    def test_comma_separated(self):
        titre, nom, prenom = normalize_name("LEFORT, Bruno")
        self.assertEqual(nom, "LEFORT")
        self.assertEqual(prenom, "Bruno")

    def test_empty(self):
        self.assertEqual(normalize_name(""), ("", "", ""))

    def test_single_word(self):
        titre, nom, prenom = normalize_name("ISIDOR")
        self.assertEqual(nom, "ISIDOR")
        self.assertEqual(prenom, "")


class TestSplitMultipleNames(unittest.TestCase):
    def test_dash_separator(self):
        result = split_multiple_names("SERRANO Emilie - CHERIET Farah")
        self.assertEqual(len(result), 2)
        self.assertIn("SERRANO Emilie", result[0])
        self.assertIn("CHERIET Farah", result[1])

    def test_ampersand_separator(self):
        result = split_multiple_names("BEYLER Constance & BONNEFOY Ronan")
        self.assertEqual(len(result), 2)

    def test_slash_separator(self):
        result = split_multiple_names("CROSSE Julien / BOTHOREL Philippe")
        self.assertEqual(len(result), 2)

    def test_comma_with_lastname(self):
        """Comma followed by single word = part of same name, not split."""
        result = split_multiple_names("LEFORT, Bruno")
        self.assertEqual(len(result), 1)
        self.assertIn("LEFORT, Bruno", result[0])

    def test_four_names(self):
        result = split_multiple_names(
            "SERRANO Emilie - CHERIET Farah - DELEPINE Marjorie - PERRIN Laurence"
        )
        self.assertEqual(len(result), 4)

    def test_mixed_separators(self):
        result = split_multiple_names("DANSE Marion, TRUCHY Pierre, GOUJON Estelle & HÖHN Sophie")
        self.assertEqual(len(result), 4)

    def test_single_name(self):
        result = split_multiple_names("HOGAN Julien")
        self.assertEqual(len(result), 1)

    def test_empty(self):
        self.assertEqual(split_multiple_names(""), [])

    def test_skip_qualifiers(self):
        """'ou médecin de...' alone should produce one entry (not split)."""
        result = split_multiple_names("ou médecin de l'hôpital")
        # Not split but also not empty since there's no uppercase-preceded separator
        self.assertEqual(len(result), 1)


class TestSplitAtFieldLabels(unittest.TestCase):
    def test_single_field(self):
        result = split_at_field_labels("NOM – PRENOM : HOGAN Julien")
        labels = dict(result)
        self.assertEqual(labels["nom"], "HOGAN Julien")

    def test_concatenated_fields(self):
        text = "Hôpital de rattachement : Robert-Debré Adresse postale : 48 bd Sérurier Téléphone : 01 40 03 20 00"
        result = split_at_field_labels(text)
        labels = dict(result)
        self.assertEqual(labels["hopital"], "Robert-Debré")
        self.assertIn("48 bd", labels["adresse"])
        self.assertIn("01 40 03 20 00", labels["telephone"])

    def test_sector_label(self):
        result = split_at_field_labels("Secteur : Pédiatrie")
        labels = dict(result)
        self.assertIn("secteur", labels)

    def test_no_labels(self):
        result = split_at_field_labels("some random text")
        self.assertEqual(result, [("raw", "some random text")])

    def test_empty(self):
        self.assertEqual(split_at_field_labels(""), [])

    def test_non_breaking_spaces(self):
        """Marseille data uses \xa0 in labels."""
        result = split_at_field_labels("NOM\xa0–\xa0PRENOM\xa0: DUSSOL Bertrand")
        labels = dict(result)
        self.assertEqual(labels["nom"], "DUSSOL Bertrand")


class TestEditDistance(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(edit_distance("abc", "abc"), 0)

    def test_one_char_diff(self):
        self.assertEqual(edit_distance("abc", "abd"), 1)

    def test_insertion(self):
        self.assertEqual(edit_distance("abc", "abcd"), 1)

    def test_empty(self):
        self.assertEqual(edit_distance("", "abc"), 3)
        self.assertEqual(edit_distance("abc", ""), 3)

    def test_spelling_variation(self):
        # MORICE-PICARD vs MORICEPICART after normalization
        a = strip_accents("MORICEPICARD")
        b = strip_accents("MORICEPICART")
        self.assertLessEqual(edit_distance(a, b), 2)


class TestStripAccents(unittest.TestCase):
    def test_french_accents(self):
        self.assertEqual(strip_accents("éàüîç"), "eauic")

    def test_no_accents(self):
        self.assertEqual(strip_accents("abc"), "abc")

    def test_empty(self):
        self.assertEqual(strip_accents(""), "")


if __name__ == "__main__":
    unittest.main()
