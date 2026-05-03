#!/usr/bin/env python
"""Regenerate 2D molecule PNG grids for existing pipeline runs (``runs/<run_id>/``)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _iter_sort_key(name: str) -> tuple:
    m = re.match(r"^iter_(\d+)$", name)
    return (0, int(m.group(1))) if m else (1, name)


def _backfill_iter(iter_dir: Path) -> List[Dict[str, Any]]:
    from DiscoveryAgent.chem.molecule_viz import write_smiles_csv_to_png

    out: List[Dict[str, Any]] = []
    prop = iter_dir / "property"
    pool_csv = iter_dir / "pool" / "candidates.csv"
    viz_dir = iter_dir / "viz"
    viz_dir.mkdir(parents=True, exist_ok=True)

    before_src: Optional[Path] = None
    if (prop / "affinity_before.csv").exists():
        before_src = prop / "affinity_before.csv"
    elif (prop / "affinity.csv").exists():
        before_src = prop / "affinity.csv"

    if before_src is not None:
        r = write_smiles_csv_to_png(
            before_src,
            viz_dir / "candidates.png",
            legend_cols=["Affinity [pKd]"],
        )
        r["role"] = "candidates"
        r["source"] = str(before_src)
        out.append(r)
    elif pool_csv.exists():
        r = write_smiles_csv_to_png(pool_csv, viz_dir / "candidates.png")
        r["role"] = "candidates"
        r["source"] = str(pool_csv)
        out.append(r)

    aff_after = prop / "affinity_after.csv"
    if aff_after.exists():
        r = write_smiles_csv_to_png(
            aff_after,
            viz_dir / "candidates_after.png",
            legend_cols=["Affinity [pKd]"],
        )
        r["role"] = "candidates_after"
        r["source"] = str(aff_after)
        out.append(r)

    return out


def backfill_run(run_dir: Path) -> Dict[str, Any]:
    from DiscoveryAgent.chem.molecule_viz import write_smiles_csv_to_png

    run_dir = Path(run_dir)
    results: List[Dict[str, Any]] = []
    pdir = run_dir / "pool"
    if (pdir / "combined_candidates.csv").exists():
        r = write_smiles_csv_to_png(
            pdir / "combined_candidates.csv",
            run_dir / "viz" / "pool_candidates.png",
        )
        r["role"] = "pool"
        results.append(r)
    elif (pdir / "seed.csv").exists():
        r = write_smiles_csv_to_png(
            pdir / "seed.csv",
            run_dir / "viz" / "pool_candidates.png",
        )
        r["role"] = "pool"
        results.append(r)

    iter_dirs = sorted(
        [p for p in run_dir.iterdir() if p.is_dir() and re.match(r"^iter_\d+$", p.name)],
        key=lambda p: _iter_sort_key(p.name),
    )
    for d in iter_dirs:
        for item in _backfill_iter(d):
            item["iter"] = d.name
            results.append(item)

    boltz_csv = run_dir / "boltz_candidates.csv"
    if boltz_csv.exists():
        r = write_smiles_csv_to_png(
            boltz_csv,
            run_dir / "viz" / "boltz_candidates.png",
            legend_cols=["Affinity [pKd]", "QED"],
        )
        r["role"] = "boltz"
        results.append(r)

    ok_n = sum(1 for r in results if r.get("ok"))
    return {"run_dir": str(run_dir), "artifacts": results, "ok_count": ok_n, "total": len(results)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--runs-root",
        type=Path,
        default=ROOT / "runs",
        help="Directory containing run folders (default: <repo>/runs).",
    )
    ap.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Process only this run id instead of all runs.",
    )
    args = ap.parse_args()
    root: Path = args.runs_root
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    if args.run_id:
        run_dirs = [root / args.run_id]
    else:
        run_dirs = sorted(
            [p for p in root.iterdir() if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )

    all_ok = True
    for rd in run_dirs:
        if not rd.is_dir():
            print(f"Skip (not a directory): {rd}")
            continue
        summary = backfill_run(rd)
        print(summary["run_dir"], summary["ok_count"], "/", summary["total"], "ok")
        for art in summary["artifacts"]:
            if not art.get("ok"):
                all_ok = False
                print("  fail:", art)

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
