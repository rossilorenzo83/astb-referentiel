"""Tests for the hospital-conflict vs transfer spec (spec 40)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from src.models import Doctor
from src.merge import merge_all, enrich


def _mk(**kwargs):
    defaults = dict(
        ville="Toulouse", specialite="CARDIOLOGIE", nom="DUPONT", prenom="Jean",
        hopital="CHU Toulouse",
    )
    defaults.update(kwargs)
    return Doctor(**defaults)


class TestHospitalConflict(unittest.TestCase):
    def test_same_city_different_hopital_kept_as_conflict(self):
        """Two records for the same doctor at different hospitals in the
        same city coexist and are flagged."""
        existing = [_mk(hopital="CHU Purpan")]
        new = [_mk(hopital="Hopital Rangueil")]
        result, warns = enrich(existing, new)
        self.assertEqual(len(result), 2)
        for rec in result:
            self.assertEqual(rec.markers.get("hopital", {}).get("kind"), "conflict")
            self.assertIn("Affiliation multiple", rec.notes)
        self.assertTrue(any("[Conflit hopital]" in w for w in warns))

    def test_cross_city_no_signal_keeps_both(self):
        existing = [_mk(ville="Toulouse", hopital="CHU Toulouse")]
        new = [_mk(ville="Bordeaux", hopital="CHU Bordeaux")]
        result, warns = enrich(existing, new)
        self.assertEqual(len(result), 2)
        self.assertTrue(any("[Conflit hopital]" in w for w in warns))

    def test_explicit_transfer_signal_collapses(self):
        """With a transfer phrase in notes, the two records merge into one."""
        existing = [_mk(ville="Toulouse", hopital="CHU Toulouse")]
        new = [_mk(ville="Bordeaux", hopital="CHU Bordeaux",
                   notes="Transfere de Toulouse")]
        result, warns = enrich(existing, new)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ville, "Bordeaux")
        self.assertIn("Transfere de Toulouse", result[0].notes)
        self.assertTrue(any("Transfert detecte" in w for w in warns))
        # Transfer clears any previous conflict marker
        self.assertNotIn("hopital", result[0].markers)

    def test_transfer_signal_variants(self):
        """Various transfer phrases should all trigger the transfer path."""
        for phrase in ["Transfere depuis Toulouse", "Mute en 2026",
                       "Ancienne affectation : Toulouse"]:
            existing = [_mk(ville="Toulouse", hopital="CHU Toulouse")]
            new = [_mk(ville="Bordeaux", hopital="CHU Bordeaux", notes=phrase)]
            result, _ = enrich(existing, new)
            self.assertEqual(len(result), 1, f"phrase {phrase!r} failed")

    def test_different_specialty_not_a_conflict(self):
        """Same name but different specialty in different hospital: two unrelated doctors."""
        existing = [_mk(specialite="CARDIOLOGIE", hopital="CHU Toulouse")]
        new = [_mk(specialite="NEPHROLOGIE", hopital="CHU Bordeaux",
                   ville="Bordeaux")]
        result, _ = enrich(existing, new)
        self.assertEqual(len(result), 2)
        for rec in result:
            self.assertNotIn("hopital", rec.markers)

    def test_merge_all_flags_conflict_within_batch(self):
        docs = [
            _mk(hopital="CHU Purpan"),
            _mk(hopital="Hopital Rangueil"),
        ]
        result, warns = merge_all(docs)
        self.assertEqual(len(result), 2)
        self.assertTrue(any("[Conflit hopital]" in w for w in warns))


if __name__ == "__main__":
    unittest.main()
