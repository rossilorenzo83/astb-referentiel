"""Tests for sibling-based field inference (spec 40)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from src.models import Doctor
from src.merge import merge_all, enrich


def _mk(**kwargs):
    defaults = dict(
        ville="Bordeaux", specialite="NEPHROLOGIE", nom="BASE", prenom="",
        hopital="CHU Bordeaux",
    )
    defaults.update(kwargs)
    return Doctor(**defaults)


class TestSiblingInference(unittest.TestCase):
    def test_adresse_inferred_from_sibling(self):
        """A doctor with no address gets the hospital address from a sibling."""
        existing = [_mk(nom="DUPONT", adresse="12 place Raba-Leon, Bordeaux")]
        new = [_mk(nom="MARTINAUD", adresse="")]
        result, _ = enrich(existing, new)
        martinaud = [d for d in result if d.nom == "MARTINAUD"][0]
        self.assertEqual(martinaud.adresse, "12 place Raba-Leon, Bordeaux")
        self.assertEqual(martinaud.markers.get("adresse", {}).get("kind"), "inferred")
        self.assertIn("infere", martinaud.notes)

    def test_email_shared_by_two_siblings_propagates(self):
        """Email shared by >= 2 records is treated as secretariat and propagated."""
        docs = [
            _mk(nom="ALPHA", email="sec@chu-bdx.fr"),
            _mk(nom="BRAVO", email="sec@chu-bdx.fr"),
            _mk(nom="CHARLIE", email=""),
        ]
        result, _ = merge_all(docs)
        c = [d for d in result if d.nom == "CHARLIE"][0]
        self.assertEqual(c.email, "sec@chu-bdx.fr")
        self.assertEqual(c.markers.get("email", {}).get("kind"), "inferred")

    def test_personal_email_not_propagated(self):
        """A single-occurrence email is personal and must not spread to siblings."""
        docs = [
            _mk(nom="ALPHA", email="a.personal@chu-bdx.fr"),
            _mk(nom="BRAVO", email=""),
        ]
        result, _ = merge_all(docs)
        b = [d for d in result if d.nom == "BRAVO"][0]
        self.assertEqual(b.email, "")

    def test_telephone_labeled_secretariat_propagates(self):
        docs = [
            _mk(nom="ALPHA", telephone="05 56 00 00 00",
                notes="Tel secretariat hopital"),
            _mk(nom="BRAVO", telephone=""),
        ]
        result, _ = merge_all(docs)
        b = [d for d in result if d.nom == "BRAVO"][0]
        self.assertEqual(b.telephone, "05 56 00 00 00")
        self.assertEqual(b.markers.get("telephone", {}).get("kind"), "inferred")

    def test_ambiguous_addresses_emit_warning(self):
        """If two siblings disagree on the address, leave empty and warn."""
        docs = [
            _mk(nom="ALPHA", adresse="Building A, 12 rue X"),
            _mk(nom="BRAVO", adresse="Building B, 48 rue Y"),
            _mk(nom="CHARLIE", adresse=""),
        ]
        result, warns = merge_all(docs)
        c = [d for d in result if d.nom == "CHARLIE"][0]
        self.assertEqual(c.adresse, "")
        self.assertTrue(any("[Inference]" in w and "adresse" in w for w in warns))

    def test_normalized_hopital_matches_variants(self):
        """'CHU de Bordeaux' and 'CHU Bordeaux' are siblings."""
        docs = [
            _mk(nom="ALPHA", hopital="CHU de Bordeaux", email="sec@chu-bdx.fr"),
            _mk(nom="BRAVO", hopital="CHU de Bordeaux", email="sec@chu-bdx.fr"),
            _mk(nom="CHARLIE", hopital="CHU Bordeaux", email=""),
        ]
        result, _ = merge_all(docs)
        c = [d for d in result if d.nom == "CHARLIE"][0]
        self.assertEqual(c.email, "sec@chu-bdx.fr")

    def test_no_inference_without_hopital(self):
        """Records with empty hopital are not grouped for inference."""
        docs = [
            _mk(nom="ALPHA", hopital="", email="a@x.fr"),
            _mk(nom="BRAVO", hopital="", email=""),
        ]
        result, _ = merge_all(docs)
        b = [d for d in result if d.nom == "BRAVO"][0]
        self.assertEqual(b.email, "")


if __name__ == "__main__":
    unittest.main()
