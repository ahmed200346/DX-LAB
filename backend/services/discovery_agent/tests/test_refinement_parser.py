"""Tests for the refinement output parser in DiscoveryAgent.utils."""
import unittest

from DiscoveryAgent.utils import _parse_refinement_output


class TestRefinementParser(unittest.TestCase):
    def test_json_happy_path(self):
        raw = (
            'some thinking...\n'
            'Final Answer: {"updated_smiles": "CCN", "property": "Solubility", '
            '"rationale": "Added NH2 for H-bonding."}'
        )
        got = _parse_refinement_output(raw, original_smiles="CCO")
        self.assertEqual(got["Updated_SMILES"], "CCN")
        self.assertEqual(got["Property"], "Solubility")
        self.assertIn("Added", got["Rationale"])
        self.assertFalse(got["refinement_failed"])

    def test_legacy_slash_s(self):
        raw = "CCN</s>Solubility</s>Added NH group"
        got = _parse_refinement_output(raw, original_smiles="CCO")
        self.assertEqual(got["Updated_SMILES"], "CCN")
        self.assertEqual(got["Property"], "Solubility")
        self.assertEqual(got["Rationale"], "Added NH group")
        self.assertFalse(got["refinement_failed"])

    def test_malformed_keeps_original(self):
        raw = "I refuse to answer."
        got = _parse_refinement_output(raw, original_smiles="CCO")
        self.assertEqual(got["Updated_SMILES"], "CCO")
        self.assertTrue(got["refinement_failed"])

    def test_none_response(self):
        got = _parse_refinement_output(None, original_smiles="CCO")
        self.assertEqual(got["Updated_SMILES"], "CCO")
        self.assertTrue(got["refinement_failed"])

    def test_json_case_insensitive_keys(self):
        raw = '{"Updated_SMILES": "CCN", "Property": "Solubility", "Rationale": "r"}'
        got = _parse_refinement_output(raw, original_smiles="CCO")
        self.assertEqual(got["Updated_SMILES"], "CCN")
        self.assertFalse(got["refinement_failed"])


if __name__ == "__main__":
    unittest.main()
