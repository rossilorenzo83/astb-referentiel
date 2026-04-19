"""Tests for reader_excel, enrichment logic, and transfer detection."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from copy import deepcopy

from src.models import Doctor
from src.merge import enrich, find_match
from conftest import get_excel_path, get_word_path, get_annuaire_path


class TestEnrich(unittest.TestCase):
    def _make_doctor(self, **kwargs):
        defaults = dict(
            region="Occitanie", ville="Toulouse", specialite="NEPHROLOGIE",
            secteur="Pediatrie", nom="DUPONT", prenom="Jean",
            hopital="CHU Toulouse", telephone="05 61 00 00 00",
            source="Ancien import", date_import="2025-01-01",
        )
        defaults.update(kwargs)
        return Doctor(**defaults)

    def test_same_city_fills_empty_fields(self):
        existing = [self._make_doctor(email="")]
        new = [self._make_doctor(email="dupont@chu.fr", source="Nouvel import")]
        result, warns = enrich(existing, new)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, "dupont@chu.fr")

    def test_same_city_updates_changed_fields(self):
        existing = [self._make_doctor(telephone="05 61 00 00 00")]
        new = [self._make_doctor(telephone="05 61 99 99 99", source="Nouvel import")]
        result, warns = enrich(existing, new)
        self.assertEqual(result[0].telephone, "05 61 99 99 99")
        self.assertTrue(any("Mise a jour" in w for w in warns))

    def test_same_city_appends_source(self):
        existing = [self._make_doctor(source="Import 1")]
        new = [self._make_doctor(source="Import 2")]
        result, _ = enrich(existing, new)
        self.assertIn("Import 1", result[0].source)
        self.assertIn("Import 2", result[0].source)

    def test_new_doctor_added(self):
        existing = [self._make_doctor()]
        new = [Doctor(ville="Bordeaux", nom="MARTIN", prenom="Paul",
                      specialite="CARDIOLOGIE", source="Nouvel import")]
        result, warns = enrich(existing, new)
        self.assertEqual(len(result), 2)
        noms = {d.nom for d in result}
        self.assertIn("DUPONT", noms)
        self.assertIn("MARTIN", noms)
        self.assertTrue(any("Nouveau medecin" in w for w in warns))

    def test_never_deletes_existing(self):
        existing = [
            self._make_doctor(nom="DUPONT"),
            self._make_doctor(nom="MARTIN", specialite="CARDIOLOGIE"),
        ]
        new = [self._make_doctor(nom="DUPONT", source="Update")]
        result, _ = enrich(existing, new)
        self.assertEqual(len(result), 2)
        noms = {d.nom for d in result}
        self.assertIn("DUPONT", noms)
        self.assertIn("MARTIN", noms)

    def test_transfer_detection(self):
        existing = [self._make_doctor(ville="Toulouse", hopital="CHU Toulouse")]
        new = [self._make_doctor(
            ville="Bordeaux", hopital="CHU Bordeaux",
            adresse="Place Raba-Leon", source="Nouvel import",
        )]
        result, warns = enrich(existing, new)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ville, "Bordeaux")
        self.assertEqual(result[0].hopital, "CHU Bordeaux")
        self.assertIn("Transfere de Toulouse", result[0].notes)
        self.assertTrue(any("Transfert detecte" in w for w in warns))

    def test_transfer_preserves_region(self):
        existing = [self._make_doctor(ville="Toulouse", region="Occitanie")]
        new = [self._make_doctor(ville="Bordeaux", source="Update")]
        result, _ = enrich(existing, new)
        self.assertEqual(result[0].region, "Nouvelle-Aquitaine")

    def test_no_false_transfer_different_specialty(self):
        existing = [self._make_doctor(ville="Toulouse", specialite="NEPHROLOGIE")]
        new = [self._make_doctor(ville="Bordeaux", specialite="CARDIOLOGIE", source="New")]
        result, _ = enrich(existing, new)
        self.assertEqual(len(result), 2)


class TestFindMatchCrossCity(unittest.TestCase):
    def test_cross_city_finds_match(self):
        existing = [Doctor(ville="Toulouse", nom="DUPONT", specialite="NEPHROLOGIE")]
        doc = Doctor(ville="Bordeaux", nom="DUPONT", specialite="NEPHROLOGIE")
        match = find_match(doc, existing, cross_city=True)
        self.assertIsNotNone(match)
        self.assertEqual(match.nom, "DUPONT")

    def test_same_city_mode_no_cross_city(self):
        existing = [Doctor(ville="Toulouse", nom="DUPONT", specialite="NEPHROLOGIE")]
        doc = Doctor(ville="Bordeaux", nom="DUPONT", specialite="NEPHROLOGIE")
        match = find_match(doc, existing, cross_city=False)
        self.assertIsNone(match)


class TestReadBackAndEnrich(unittest.TestCase):
    """End-to-end: read annuaire, enrich with Word file."""

    @classmethod
    def setUpClass(cls):
        from src.reader_excel import read_annuaire
        from src.scanner import scan_and_parse
        from src.merge import enrich

        # Read the pre-built synthetic annuaire
        cls.existing, cls.read_warns = read_annuaire(get_annuaire_path())
        cls.existing_named = [d for d in cls.existing if d.nom]

        # Enrich with the synthetic Word file
        word_docs, _ = scan_and_parse(get_word_path())
        for d in word_docs:
            d.source = "Test Import 2026"
        cls.enriched, cls.enrich_warns = enrich(cls.existing, word_docs)
        cls.enriched_named = [d for d in cls.enriched if d.nom]

    def test_read_back_preserves_count(self):
        self.assertEqual(len(self.existing_named), 3)

    def test_read_back_has_fields(self):
        for d in self.existing_named:
            self.assertTrue(d.ville)
            self.assertTrue(d.nom)

    def test_enrichment_never_loses_doctors(self):
        self.assertGreaterEqual(len(self.enriched_named), len(self.existing_named))

    def test_enrichment_adds_new_cities(self):
        existing_cities = set(d.ville for d in self.existing_named)
        enriched_cities = set(d.ville for d in self.enriched_named)
        new_cities = enriched_cities - existing_cities
        self.assertTrue(len(new_cities) > 0, "No new cities added from Word file")

    def test_enriched_source_updated(self):
        enriched_with_test = [
            d for d in self.enriched if d.nom and "Test Import 2026" in d.source
        ]
        self.assertTrue(len(enriched_with_test) > 0)

    def test_new_doctors_have_origin(self):
        new = [d for d in self.enriched if d.nom and d.source == "Test Import 2026"]
        self.assertTrue(len(new) > 0)


class TestReadAnnuaire(unittest.TestCase):
    """Test reading a structured annuaire Excel."""

    def test_read_annuaire(self):
        from src.reader_excel import read_annuaire
        doctors, warns = read_annuaire(get_annuaire_path())
        self.assertEqual(len(doctors), 3)
        noms = {d.nom for d in doctors}
        self.assertIn("BERNARD", noms)
        self.assertIn("DURAND", noms)
        self.assertIn("ROUX", noms)

    def test_fields_preserved(self):
        from src.reader_excel import read_annuaire
        doctors, _ = read_annuaire(get_annuaire_path())
        bernard = next(d for d in doctors if d.nom == "BERNARD")
        self.assertEqual(bernard.ville, "Lyon")
        self.assertEqual(bernard.region, "Auvergne-Rhone-Alpes")
        self.assertEqual(bernard.specialite, "NEPHROLOGIE")
        self.assertEqual(bernard.source, "Import initial")
        self.assertEqual(bernard.date_import, "2025-01-15")


if __name__ == "__main__":
    unittest.main()
