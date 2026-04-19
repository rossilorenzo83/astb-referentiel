"""Integration tests for scanning and parsing against synthetic test data."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from conftest import get_excel_path, get_word_path


class TestExcelParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.scanner import scan_and_parse
        cls.doctors, cls.warnings = scan_and_parse(get_excel_path())
        cls.named = [d for d in cls.doctors if d.nom]

    def test_total_count(self):
        """Should extract doctors from all sheets."""
        self.assertGreaterEqual(len(self.named), 5)

    def test_all_cities_present(self):
        cities = set(d.ville for d in self.doctors)
        for city in ["Lyon", "Strasbourg", "Lille"]:
            self.assertIn(city, cities, f"Missing city: {city}")

    def test_all_regions_assigned(self):
        for d in self.named:
            self.assertTrue(d.region, f"No region for {d.nom} in {d.ville}")

    def test_specialties_present(self):
        specialties = set(d.specialite for d in self.named)
        self.assertIn("NEPHROLOGIE", specialties)
        self.assertIn("DERMATOLOGIE", specialties)
        self.assertIn("CARDIOLOGIE", specialties)

    def test_lyon_doctors(self):
        lyon = [d for d in self.named if d.ville == "Lyon"]
        self.assertGreaterEqual(len(lyon), 4)
        noms = {d.nom for d in lyon}
        self.assertIn("BERNARD", noms)
        self.assertIn("PETIT", noms)
        self.assertIn("DURAND", noms)

    def test_multi_name_split(self):
        """LEROY & MOREAU should each be separate entries."""
        neuro_lyon = [
            d for d in self.named
            if d.ville == "Lyon" and d.specialite == "NEUROLOGIE"
        ]
        noms = {d.nom for d in neuro_lyon}
        self.assertIn("LEROY", noms, "Missing LEROY from multi-name split")
        self.assertIn("MOREAU", noms, "Missing MOREAU from multi-name split")

    def test_idem_resolved(self):
        """Lyon DERMATOLOGIE Adulte should be resolved from idem pediatrie."""
        lyon_derm_adulte = [
            d for d in self.doctors
            if d.ville == "Lyon" and d.specialite == "DERMATOLOGIE" and d.secteur == "Adulte"
        ]
        self.assertTrue(len(lyon_derm_adulte) >= 1)
        if lyon_derm_adulte[0].nom:
            self.assertIn("Meme medecin", lyon_derm_adulte[0].notes)

    def test_phone_normalization(self):
        for d in self.named:
            if d.telephone:
                for phone in d.telephone.split(" / "):
                    phone = phone.strip()
                    self.assertRegex(
                        phone, r"^\d{2}( \d{2}){4}$",
                        f"Bad phone format for {d.nom}: '{phone}'"
                    )

    def test_sectors(self):
        sectors = set(d.secteur for d in self.named)
        self.assertTrue(sectors & {"Pediatrie", "Adulte"})

    def test_freetext_sheet(self):
        """Lille (free-text) should extract at least the coordinator."""
        lille = [d for d in self.named if d.ville == "Lille"]
        self.assertGreaterEqual(len(lille), 1)
        self.assertEqual(lille[0].nom, "LAMBERT")

    def test_no_empty_named_doctors(self):
        for d in self.named:
            self.assertTrue(d.nom)

    def test_autre_reclassified(self):
        """AUTRE with 'Neurologie pediatrique' should be reclassified to NEUROLOGIE."""
        neuro = [d for d in self.named if d.specialite == "NEUROLOGIE"]
        self.assertTrue(len(neuro) >= 2, "Neurologie doctors not reclassified from AUTRE")

    def test_pas_de_referent(self):
        """'pas de referent' entries should have notes."""
        notes_docs = [d for d in self.doctors if d.notes and "pas de" in d.notes.lower()]
        self.assertTrue(len(notes_docs) >= 1)


class TestWordParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.scanner import scan_and_parse
        cls.doctors, cls.warnings = scan_and_parse(get_word_path())
        cls.named = [d for d in cls.doctors if d.nom]

    def test_total_count(self):
        self.assertGreaterEqual(len(self.named), 3)

    def test_new_cities(self):
        cities = set(d.ville for d in self.named)
        self.assertIn("Grenoble", cities)
        self.assertIn("Clermont-Ferrand", cities)

    def test_regions_assigned(self):
        # Lyon should have a region at minimum
        lyon = [d for d in self.named if d.ville == "Lyon"]
        for d in lyon:
            self.assertTrue(d.region)

    def test_phones_extracted(self):
        with_phone = [d for d in self.named if d.telephone]
        self.assertGreaterEqual(len(with_phone), 1)

    def test_emails_extracted(self):
        with_email = [d for d in self.named if d.email]
        self.assertGreaterEqual(len(with_email), 1)

    def test_specialty_detected(self):
        dermato = [d for d in self.named if d.specialite == "DERMATOLOGIE"]
        self.assertGreaterEqual(len(dermato), 1)


class TestMerge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.scanner import scan_and_parse
        from src.merge import merge_all

        excel_docs, _ = scan_and_parse(get_excel_path())
        word_docs, _ = scan_and_parse(get_word_path())
        all_docs = excel_docs + word_docs
        cls.merged, cls.warnings = merge_all(all_docs)
        cls.named = [d for d in cls.merged if d.nom]

    def test_total_after_merge(self):
        self.assertGreaterEqual(len(self.named), 7)

    def test_no_duplicate_sectors(self):
        seen = set()
        for d in self.named:
            key = (d.ville, d.nom, d.specialite, d.secteur)
            self.assertNotIn(key, seen, f"Duplicate: {key}")
            seen.add(key)

    def test_new_cities_added(self):
        cities = set(d.ville for d in self.named)
        self.assertIn("Grenoble", cities)


if __name__ == "__main__":
    unittest.main()
