"""Canonical SMILES helpers used across the DiscoveryAgent pipeline.

All helpers are defensive: they accept arbitrary input, silence RDKit warnings
locally, and return ``None`` (or an empty result) when parsing fails so callers
can filter invalid molecules without try/except boilerplate.
"""
from __future__ import annotations

import os
import sys
from typing import Iterable, List, Optional

from rdkit import Chem, RDLogger
from rdkit.Chem import SaltRemover

try:
    from rdkit.Chem.MolStandardize import rdMolStandardize  # type: ignore

    _HAS_STANDARDIZE = True
except Exception:
    _HAS_STANDARDIZE = False

RDLogger.DisableLog("rdApp.*")

_SALT_REMOVER = SaltRemover.SaltRemover()


def _silence_rdkit_c_stderr():
    """Return a context manager-like pair to temporarily mute RDKit C stderr."""
    old_stderr_fd = os.dup(2)
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull_fd, 2)
    os.close(devnull_fd)
    return old_stderr_fd


def _restore_stderr(old_fd: int) -> None:
    try:
        os.dup2(old_fd, 2)
        os.close(old_fd)
    except Exception:
        pass


def _mol_from_smiles(smi: str) -> Optional[Chem.Mol]:
    if not isinstance(smi, str):
        return None
    s = smi.strip()
    if not s:
        return None
    old = _silence_rdkit_c_stderr()
    try:
        return Chem.MolFromSmiles(s)
    except Exception:
        return None
    finally:
        _restore_stderr(old)


def is_valid(smi: str) -> bool:
    """Return True if `smi` parses as a molecule with at least one heavy atom."""
    mol = _mol_from_smiles(smi)
    if mol is None:
        return False
    try:
        return mol.GetNumHeavyAtoms() > 0
    except Exception:
        return False


def canonicalize(smi: str, keep_stereo: bool = True) -> Optional[str]:
    """Return canonical SMILES, preserving stereochemistry by default.

    Returns ``None`` if the input cannot be parsed.
    """
    mol = _mol_from_smiles(smi)
    if mol is None:
        return None
    try:
        return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=keep_stereo)
    except Exception:
        return None


def _largest_fragment(mol: Chem.Mol) -> Chem.Mol:
    """Return the largest organic fragment by heavy-atom count."""
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False)
    if not frags:
        return mol
    return max(frags, key=lambda m: m.GetNumHeavyAtoms())


def strip_salts(smi: str) -> Optional[str]:
    """Remove common counterions and keep the largest organic fragment.

    Returns canonical SMILES of the desalted molecule, or ``None`` on failure.
    """
    mol = _mol_from_smiles(smi)
    if mol is None:
        return None
    try:
        stripped = _SALT_REMOVER.StripMol(mol, dontRemoveEverything=True)
        if stripped is None or stripped.GetNumAtoms() == 0:
            stripped = mol
        # After salt removal there may still be multiple fragments
        if "." in Chem.MolToSmiles(stripped):
            stripped = _largest_fragment(stripped)
        return Chem.MolToSmiles(stripped, canonical=True, isomericSmiles=True)
    except Exception:
        return None


def standardize(smi: str, *, keep_stereo: bool = True) -> Optional[str]:
    """Salt-strip, neutralize (when available), and canonicalize.

    Returns canonical SMILES, or ``None`` for unparseable input or an empty
    molecule.
    """
    mol = _mol_from_smiles(smi)
    if mol is None:
        return None
    try:
        stripped = _SALT_REMOVER.StripMol(mol, dontRemoveEverything=True)
        if stripped is None or stripped.GetNumAtoms() == 0:
            stripped = mol
        if "." in Chem.MolToSmiles(stripped):
            stripped = _largest_fragment(stripped)

        if _HAS_STANDARDIZE:
            try:
                uncharger = rdMolStandardize.Uncharger()
                stripped = uncharger.uncharge(stripped)
            except Exception:
                pass

        if stripped is None or stripped.GetNumHeavyAtoms() == 0:
            return None

        return Chem.MolToSmiles(stripped, canonical=True, isomericSmiles=keep_stereo)
    except Exception:
        return None


def dedup_canonical(smiles_iter: Iterable[str], *, keep_stereo: bool = True) -> List[str]:
    """Return canonical SMILES in input order, de-duplicated, invalid dropped."""
    seen = set()
    out: List[str] = []
    for s in smiles_iter:
        canon = canonicalize(s, keep_stereo=keep_stereo)
        if canon is None:
            continue
        if canon in seen:
            continue
        seen.add(canon)
        out.append(canon)
    return out
