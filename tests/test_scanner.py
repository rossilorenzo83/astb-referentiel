"""Tests for the dynamic scanner, synonym matching, and baseline assertions."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from conftest import get_excel_path, get_word_path


class TestSynonyms(unittest.TestCase):
    def test_match_field_nom(self):
        from src.scanner.synonyms import match_field_synonym
        self.assertEqual(match_field_synonym("NOM \u2013 PRENOM"), "nom")
        self.assertEqual(match_field_synonym("NOM - PRENOM"), "nom")
        self.assertEqual(match_field_synonym("Nom"), "nom")
        self.assertEqual(match_field_synonym("Medecin"), "nom")

    def test_match_field_telephone(self):
        from src.scanner.synonyms import match_field_synonym
        self.assertEqual(match_field_synonym("Telephone"), "telephone")
        self.assertEqual(match_field_synonym("Tel."), "telephone")

    def test_match_field_email(self):
        from src.scanner.synonyms import match_field_synonym
        self.assertEqual(match_field_synonym("Adresse mail"), "email")
        self.assertEqual(match_field_synonym("E-mail"), "email")
        self.assertEqual(match_field_synonym("Email"), "email")

    def test_match_field_hopital(self):
        from src.scanner.synonyms import match_field_synonym
        self.assertEqual(match_field_synonym("Hopital de rattachement"), "hopital")
        self.assertEqual(match_field_synonym("Hopital"), "hopital")

    def test_match_field_unknown(self):
        from src.scanner.synonyms import match_field_synonym
        self.assertIsNone(match_field_synonym("xyz_unknown"))
        self.assertIsNone(match_field_synonym(""))

    def test_match_specialty(self):
        from src.scanner.synonyms import match_specialty
        self.assertEqual(match_specialty("NEPHROLOGUES"), "NEPHROLOGIE")
        self.assertEqual(match_specialty("dermatologie"), "DERMATOLOGIE")
        self.assertEqual(match_specialty("pneumo"), "PNEUMOLOGIE")
        self.assertIsNone(match_specialty("xyz"))


class TestExcelScanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.scanner.scan_excel import scan_excel
        cls.template, cls.buffer = scan_excel(get_excel_path())

    def test_all_sheets_detected(self):
        self.assertEqual(len(self.template.sheets), 3)

    def test_sheet_names(self):
        names = {s.name for s in self.template.sheets}
        for expected in ["Lyon", "Strasbourg", "Lille"]:
            self.assertIn(expected, names)

    def test_layout_classification(self):
        from src.scanner.template import LayoutType
        for sheet in self.template.sheets:
            self.assertEqual(sheet.layout, LayoutType.SINGLE_COLUMN_STATEFUL,
                             f"Sheet {sheet.name} should be SINGLE_COLUMN_STATEFUL")

    def test_header_detected(self):
        for sheet in self.template.sheets:
            self.assertIsNotNone(sheet.header, f"Sheet {sheet.name} has no header")
            self.assertEqual(sheet.header.city_row, 0)

    def test_specialty_detectors(self):
        from src.scanner.template import SectionDetectorKind
        # Lyon and Strasbourg have numbered specialties, Lille does not
        for sheet in self.template.sheets:
            if sheet.name == "Lille":
                continue
            has_numbered = any(
                d.kind == SectionDetectorKind.NUMBERED_PREFIX
                for d in sheet.section_detectors
            )
            self.assertTrue(has_numbered, f"Sheet {sheet.name} missing numbered specialty detector")

    def test_field_mappings_detected(self):
        for sheet in self.template.sheets:
            if sheet.name == "Lille":
                continue
            field_names = {fm.doctor_field for fm in sheet.field_mappings}
            self.assertIn("nom", field_names, f"Sheet {sheet.name} missing 'nom' mapping")

    def test_buffer_populated(self):
        for sheet_name in self.buffer:
            self.assertTrue(len(self.buffer[sheet_name]) > 0)


class TestWordScanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.scanner.scan_word import scan_word
        cls.template, cls.buffer = scan_word(get_word_path())

    def test_layout_classification(self):
        from src.scanner.template import LayoutType
        self.assertEqual(len(self.template.sheets), 1)
        self.assertEqual(self.template.sheets[0].layout, LayoutType.PARAGRAPH_SECTIONED)

    def test_city_detector(self):
        from src.scanner.template import SectionDetectorKind
        detectors = self.template.sheets[0].section_detectors
        city_det = [d for d in detectors if d.level == "city"]
        self.assertEqual(len(city_det), 1)
        self.assertEqual(city_det[0].kind, SectionDetectorKind.STYLE_BASED)
        self.assertEqual(city_det[0].pattern, "List Paragraph")

    def test_paragraph_buffer(self):
        self.assertIn("paragraphs", self.buffer)
        self.assertTrue(len(self.buffer["paragraphs"]) > 0)


class TestScannerBaseline(unittest.TestCase):
    """Baseline assertions for scanner output on synthetic files."""

    @classmethod
    def setUpClass(cls):
        from src.scanner import scan_and_parse
        cls.excel_docs, _ = scan_and_parse(get_excel_path())
        cls.word_docs, _ = scan_and_parse(get_word_path())
        cls.excel_named = [d for d in cls.excel_docs if d.nom]
        cls.word_named = [d for d in cls.word_docs if d.nom]

    def test_excel_doctor_count(self):
        self.assertGreaterEqual(len(self.excel_named), 5)

    def test_word_doctor_count(self):
        self.assertGreaterEqual(len(self.word_named), 3)

    def test_excel_3_cities(self):
        cities = set(d.ville for d in self.excel_named)
        self.assertEqual(len(cities), 3)

    def test_excel_regions_complete(self):
        for d in self.excel_named:
            self.assertTrue(d.region, f"No region for {d.nom} in {d.ville}")

    def test_excel_autre_reclassified(self):
        scanner_autre = [d for d in self.excel_named if d.specialite == "AUTRE"]
        for d in scanner_autre:
            if d.specialite_detail:
                from src.scanner.synonyms import match_specialty
                self.assertIsNone(match_specialty(d.specialite_detail),
                    f"{d.nom} has AUTRE but detail '{d.specialite_detail}' is classifiable")

    def test_merged_no_duplicates(self):
        from src.merge import merge_all
        all_docs = self.excel_docs + self.word_docs
        merged, _ = merge_all(all_docs)
        seen = set()
        for d in merged:
            if d.nom:
                key = (d.ville, d.nom, d.specialite, d.secteur)
                self.assertNotIn(key, seen, f"Duplicate: {key}")
                seen.add(key)


if __name__ == "__main__":
    unittest.main()
