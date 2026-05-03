"""Live UniProt integration check for gene-symbol queries (requires network)."""
import unittest

from DiscoveryAgent.tools.retrieval import get_uniprot_ids


class TestUniProtGeneQuery(unittest.TestCase):
    def test_kras_human_swiss_prot(self):
        """Plain-text UniProt search previously ranked MAPKAP1 above KRAS."""
        out = get_uniprot_ids.invoke({"protein_name": "KRAS"})
        self.assertIsInstance(out, list)
        self.assertGreater(len(out), 0)
        self.assertEqual(out[0][0], "P01116")

    def test_egfr_human(self):
        out = get_uniprot_ids.invoke({"protein_name": "EGFR"})
        self.assertIsInstance(out, list)
        self.assertEqual(out[0][0], "P00533")


if __name__ == "__main__":
    unittest.main()
