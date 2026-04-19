"""Unit tests for models.py."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from src.models import Doctor, get_region, doctor_to_row, COLUMN_HEADERS


class TestGetRegion(unittest.TestCase):
    def test_known_cities(self):
        self.assertEqual(get_region("Paris Robert Debre"), "Ile-de-France")
        self.assertEqual(get_region("Marseille"), "Provence-Alpes-Cote d'Azur")
        self.assertEqual(get_region("Toulouse"), "Occitanie")
        self.assertEqual(get_region("Bordeaux"), "Nouvelle-Aquitaine")
        self.assertEqual(get_region("Nice"), "Provence-Alpes-Cote d'Azur")
        self.assertEqual(get_region("Tours"), "Centre-Val de Loire")
        self.assertEqual(get_region("Saint-Etienne"), "Auvergne-Rhone-Alpes")
        self.assertEqual(get_region("Limoges"), "Nouvelle-Aquitaine")
        self.assertEqual(get_region("Reims"), "Grand Est")
        self.assertEqual(get_region("Nancy"), "Grand Est")
        self.assertEqual(get_region("Annecy"), "Auvergne-Rhone-Alpes")
        self.assertEqual(get_region("Nantes"), "Pays de la Loire")

    def test_case_insensitive(self):
        self.assertEqual(get_region("MARSEILLE"), "Provence-Alpes-Cote d'Azur")
        self.assertEqual(get_region("toulouse"), "Occitanie")

    def test_unknown_city(self):
        self.assertEqual(get_region("Timbuktu"), "")

    def test_empty(self):
        self.assertEqual(get_region(""), "")


class TestDoctor(unittest.TestCase):
    def test_is_empty(self):
        d = Doctor()
        self.assertTrue(d.is_empty())

    def test_is_not_empty_with_name(self):
        d = Doctor(nom="DUPONT")
        self.assertFalse(d.is_empty())

    def test_is_not_empty_with_notes(self):
        d = Doctor(notes="pas de referent")
        self.assertFalse(d.is_empty())

    def test_completeness_score(self):
        d = Doctor(nom="DUPONT", prenom="Jean", telephone="01 23 45 67 89")
        self.assertEqual(d.completeness_score(), 3)

    def test_completeness_score_empty(self):
        d = Doctor()
        self.assertEqual(d.completeness_score(), 0)

    def test_dedup_key(self):
        d1 = Doctor(ville="Marseille", nom="DUSSOL", specialite="NEPHROLOGIE")
        d2 = Doctor(ville="marseille", nom="Dussol", specialite="NEPHROLOGIE")
        self.assertEqual(d1.dedup_key(), d2.dedup_key())

    def test_dedup_key_accents(self):
        d1 = Doctor(ville="Saint-Étienne", nom="PÉRIVIER", specialite="NEUROLOGIE")
        d2 = Doctor(ville="Saint-Etienne", nom="PERIVIER", specialite="NEUROLOGIE")
        self.assertEqual(d1.dedup_key(), d2.dedup_key())


class TestDoctorToRow(unittest.TestCase):
    def test_row_length_matches_headers(self):
        d = Doctor()
        row = doctor_to_row(d)
        self.assertEqual(len(row), len(COLUMN_HEADERS))

    def test_region_is_first(self):
        self.assertEqual(COLUMN_HEADERS[0], "Region")

    def test_row_values(self):
        d = Doctor(region="Occitanie", ville="Toulouse", nom="DUPONT", prenom="Jean")
        row = doctor_to_row(d)
        self.assertEqual(row[0], "Occitanie")
        self.assertEqual(row[1], "Toulouse")


if __name__ == "__main__":
    unittest.main()
