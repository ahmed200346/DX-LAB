"""2D structure grids from SMILES columns (RDKit). Used by the pipeline and backfill tools."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from rdkit import Chem
from rdkit.Chem import Draw

from DiscoveryAgent.chem.smiles_utils import _silence_rdkit_c_stderr, _restore_stderr

# Avoid enormous PNGs on large pools; extra rows can be re-run with a higher cap if needed.
_DEFAULT_MAX_MOLECULES = 32
_DEFAULT_MOLS_PER_ROW = 4
_DEFAULT_SUBIMG = (300, 300)


def _short_legend(s: str, max_len: int = 40) -> str:
    t = re.sub(r"\s+", " ", str(s).strip())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _row_legend(
    row: Any,
    idx: int,
    legend_cols: Optional[Sequence[str]],
) -> str:
    parts: List[str] = [f"#{idx + 1}"]
    if legend_cols:
        for c in legend_cols:
            if c not in row.index:
                continue
            v = row[c]
            if v is None or (isinstance(v, float) and v != v):
                continue
            if isinstance(v, bool):
                parts.append(f"{c}={v}")
            elif isinstance(v, (int, float)):
                parts.append(f"{c}={v:.3g}" if isinstance(v, float) else f"{c}={v}")
            else:
                parts.append(f"{c}={_short_legend(str(v), 32)}")
    return "\n".join(parts)


def write_smiles_csv_to_png(
    csv_path: Path,
    out_png: Path,
    *,
    smiles_col: str = "SMILES",
    legend_cols: Optional[Sequence[str]] = None,
    max_molecules: int = _DEFAULT_MAX_MOLECULES,
    mols_per_row: int = _DEFAULT_MOLS_PER_ROW,
    sub_img_size: tuple[int, int] = _DEFAULT_SUBIMG,
) -> Dict[str, Any]:
    """
    Read a CSV with a ``SMILES`` column and write a single PNG grid.

    Returns a small result dict (``ok``, paths, counts). Raises only on
    unexpected bugs; common issues (empty file, bad column) are reported via ``ok: False``.
    """
    import pandas as pd

    csv_path, out_png = Path(csv_path), Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        return {"ok": False, "error": "csv_missing", "csv": str(csv_path)}

    df = pd.read_csv(csv_path)
    if smiles_col not in df.columns:
        return {"ok": False, "error": "missing_smiles_col", "csv": str(csv_path)}

    n_total = len(df)
    if n_total == 0:
        return {"ok": False, "error": "empty_csv", "csv": str(csv_path)}

    df = df.head(int(max_molecules)).copy()
    mols: List[Chem.Mol] = []
    legends: List[str] = []
    used_legend_cols: Optional[List[str]] = None
    if legend_cols:
        used_legend_cols = [c for c in legend_cols if c in df.columns]

    for row_idx, (_, row) in enumerate(df.iterrows()):
        smi = row.get(smiles_col)
        if smi is None or (isinstance(smi, float) and smi != smi):
            continue
        s = str(smi).strip()
        if not s:
            continue
        old = _silence_rdkit_c_stderr()
        try:
            m = Chem.MolFromSmiles(s)
        finally:
            _restore_stderr(old)
        if m is None:
            continue
        mols.append(m)
        legends.append(
            _row_legend(row, row_idx, used_legend_cols)
            if used_legend_cols
            else f"#{len(mols)}"
        )

    if not mols:
        return {"ok": False, "error": "no_valid_smiles", "csv": str(csv_path)}

    # Truncate overly long legend lines for the drawer
    legends = [(_short_legend(x, 120) if x else "") for x in legends]

    img = Draw.MolsToGridImage(
        mols,
        molsPerRow=int(mols_per_row),
        subImgSize=(int(sub_img_size[0]), int(sub_img_size[1])),
        legends=legends,
    )
    img.save(str(out_png))

    return {
        "ok": True,
        "out_png": str(out_png),
        "n_drawn": len(mols),
        "n_total_in_csv": int(n_total),
        "truncated": n_total > len(mols),
    }
