"""Tests for _merge_affinity_admet and _select_final_candidates in mcp_agent."""
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mcp_agent import _merge_affinity_admet, _select_final_candidates


class TestMergeAffinityAdmet(unittest.TestCase):
    def test_inner_join_reordered(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            aff = pd.DataFrame({
                "SMILES": ["CCO", "c1ccccc1", "CCN"],
                "Affinity [pKd]": [5.5, 6.2, 4.8],
            })
            admet = pd.DataFrame({
                "SMILES": ["OCC", "CCN", "c1ccccc1"],
                "QED": [0.4, 0.5, 0.7],
            })
            aff_csv = td / "aff.csv"
            adm_csv = td / "admet.csv"
            out_csv = td / "merged.csv"
            aff.to_csv(aff_csv, index=False)
            admet.to_csv(adm_csv, index=False)

            _merge_affinity_admet(aff_csv, adm_csv, out_csv)
            merged = pd.read_csv(out_csv)

            self.assertEqual(len(merged), 3)
            self.assertIn("Affinity [pKd]", merged.columns)
            self.assertIn("QED", merged.columns)

            by_smi = {r["SMILES"]: r for _, r in merged.iterrows()}
            self.assertAlmostEqual(by_smi["CCO"]["QED"], 0.4)
            self.assertAlmostEqual(by_smi["CCN"]["Affinity [pKd]"], 4.8)

    def test_mismatch_writes_sidecar(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            aff = pd.DataFrame({"SMILES": ["CCO", "CCN"], "Affinity [pKd]": [5.0, 4.0]})
            admet = pd.DataFrame({"SMILES": ["CCO", "c1ccccc1"], "QED": [0.3, 0.5]})
            aff_csv = td / "aff.csv"
            adm_csv = td / "admet.csv"
            out_csv = td / "sub" / "merged.csv"
            aff.to_csv(aff_csv, index=False)
            admet.to_csv(adm_csv, index=False)

            _merge_affinity_admet(aff_csv, adm_csv, out_csv)
            merged = pd.read_csv(out_csv)
            self.assertEqual(len(merged), 1)
            sidecar = out_csv.parent / "errors" / "merge_mismatch.json"
            self.assertTrue(sidecar.exists())
            meta = json.loads(sidecar.read_text())
            self.assertEqual(meta["merged_rows"], 1)


class TestSelectFinalCandidates(unittest.TestCase):
    def _base_df(self):
        return pd.DataFrame({
            "SMILES": ["CCO", "c1ccccc1", "CCN", "OCC"],
            "Affinity [pKd]": [5.0, 6.0, 7.0, 8.0],
            "QED": [0.6, 0.7, 0.8, 0.9],
            "lipinski_rule_of_5": [True, True, True, True],
            "veber_rule": [True, True, True, True],
            "ghose_filter": [True, True, True, True],
            "oprea_lead_like": [False, False, False, False],
        })

    def test_ge_pkd_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            df = self._base_df()
            # oprea all False -> soft fallback kicks in
            scored = td / "scored.csv"
            out = td / "final.csv"
            df.to_csv(scored, index=False)
            _select_final_candidates(scored, out, top_k=10, min_pkd=6.0, min_qed=0.5)
            got = pd.read_csv(out)
            # pKd >= 6.0 should KEEP pKd == 6.0 (the benzene row)
            self.assertIn(6.0, list(got["Affinity [pKd]"]))

    def test_oprea_soft_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            df = self._base_df()
            scored = td / "scored.csv"
            out = td / "final.csv"
            df.to_csv(scored, index=False)
            _select_final_candidates(scored, out, top_k=10, min_pkd=5.0, min_qed=0.5)
            got = pd.read_csv(out)
            self.assertEqual(len(got), 4)
            sidecar = out.parent / (out.stem + ".selection.json")
            meta = json.loads(sidecar.read_text())
            self.assertTrue(meta["relaxed_oprea"])

    def test_empty_after_filter(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            df = self._base_df()
            scored = td / "scored.csv"
            out = td / "final.csv"
            df.to_csv(scored, index=False)
            _select_final_candidates(scored, out, top_k=10, min_pkd=99.0, min_qed=0.5)
            got = pd.read_csv(out)
            self.assertEqual(len(got), 0)

    def test_canonical_output_smiles(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            df = self._base_df()
            df.loc[0, "SMILES"] = "OCC"  # non-canonical ethanol
            scored = td / "scored.csv"
            out = td / "final.csv"
            df.to_csv(scored, index=False)
            _select_final_candidates(scored, out, top_k=10, min_pkd=5.0, min_qed=0.5)
            got = pd.read_csv(out)
            self.assertIn("CCO", list(got["SMILES"]))


if __name__ == "__main__":
    unittest.main()
