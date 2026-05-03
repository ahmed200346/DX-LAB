"""Unit tests for DiscoveryAgent.chem.smiles_utils."""
import unittest

from DiscoveryAgent.chem.smiles_utils import (
    canonicalize,
    dedup_canonical,
    is_valid,
    standardize,
    strip_salts,
)


class TestCanonicalize(unittest.TestCase):
    def test_ethanol_round_trip(self):
        self.assertEqual(canonicalize("CCO"), canonicalize("OCC"))
        self.assertEqual(canonicalize("CCO"), "CCO")

    def test_whitespace(self):
        self.assertEqual(canonicalize("  CCO  "), "CCO")

    def test_invalid(self):
        self.assertIsNone(canonicalize("not a smiles"))
        self.assertIsNone(canonicalize(""))
        self.assertIsNone(canonicalize(None))  # type: ignore[arg-type]


class TestIsValid(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(is_valid("CCO"))
        self.assertTrue(is_valid("c1ccccc1"))

    def test_invalid(self):
        self.assertFalse(is_valid("XYZ"))
        self.assertFalse(is_valid(""))
        self.assertFalse(is_valid(None))  # type: ignore[arg-type]


class TestStripSalts(unittest.TestCase):
    def test_sodium_acetate(self):
        out = strip_salts("CC(=O)O.[Na+].[OH-]")
        self.assertEqual(out, "CC(=O)O")

    def test_hcl_salt(self):
        out = strip_salts("CCN.Cl")
        self.assertEqual(out, "CCN")

    def test_no_salt_passthrough(self):
        self.assertEqual(strip_salts("CCO"), "CCO")


class TestStandardize(unittest.TestCase):
    def test_salted_and_charged(self):
        out = standardize("CC(=O)[O-].[Na+]")
        self.assertEqual(out, "CC(=O)O")

    def test_large_fragment_kept(self):
        out = standardize("c1ccccc1.O=C=O")
        self.assertEqual(out, "c1ccccc1")

    def test_invalid_returns_none(self):
        self.assertIsNone(standardize("not-a-smiles"))


class TestDedupCanonical(unittest.TestCase):
    def test_order_preserving_dedup(self):
        got = dedup_canonical(["CCO", "OCC", "c1ccccc1", "c1ccccc1", "C1=CC=CC=C1"])
        self.assertEqual(got, ["CCO", "c1ccccc1"])

    def test_invalids_dropped(self):
        got = dedup_canonical(["CCO", "bogus", "", None])  # type: ignore[list-item]
        self.assertEqual(got, ["CCO"])


if __name__ == "__main__":
    unittest.main()
