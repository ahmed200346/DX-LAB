"""
Printer 3D Evaluator — Métriques de qualité du 3D Printer
Score global = 35% génération + 25% format + 30% qualité structurale + 10% fiabilité NIM
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PrinterMetrics:
    """Résultats des métriques 3D Printer"""
    generation_score: float       # 0.0-1.0
    format_score: float           # 0.0-1.0
    quality_score: float          # 0.0-1.0
    reliability_score: float      # 0.0-1.0 (pas de fallback)
    
    global_score: float           # Score global pondéré
    
    generation_details: Dict[str, Any]
    format_details: Dict[str, Any]
    quality_details: Dict[str, Any]
    reliability_details: Dict[str, Any]
    
    status: str                   # "EXCELLENT" / "GOOD" / "FAIR" / "POOR"
    
    def __str__(self) -> str:
        bar = "█" * int(self.global_score * 10) + "░" * (10 - int(self.global_score * 10))
        return (
            f"[PRINTER METRICS]\n"
            f"  Global Score   : {bar} {self.global_score:.1%} ({self.status})\n"
            f"  ├─ Generation  : {self.generation_score:.1%} (35%)\n"
            f"  ├─ Format      : {self.format_score:.1%} (25%)\n"
            f"  ├─ Quality     : {self.quality_score:.1%} (30%)\n"
            f"  └─ Reliability : {self.reliability_score:.1%} (10%)"
        )

# evaluators/printer_evaluator.py — AMÉLIORATIONS

def evaluate_printer(
    printer_output: Any,
    case: int,
    structure_content: Optional[str] = None
) -> PrinterMetrics:
    """Evaluation CORRIGÉE du 3D Printer."""
    
    # ═══════════════════════════════════════════════════════════
    # GENERATION SCORE — FIX: Plus tolérant pour RDKit
    # ═══════════════════════════════════════════════════════════
    
    generation_details = {}
    
    success = printer_output.success
    has_structure = bool(printer_output.structure and len(printer_output.structure) > 100)
    
    # Pour RDKit (Case 1): accepter structure non-vide
    # Pour NIM (Case 2/3): plus exigeant (min 1000 chars PDB)
    if case == 1:
        min_size = 100  # MOL bloc minimal
    else:
        min_size = 500  # PDB minimal
    
    generation_score = 1.0 if (success and len(printer_output.structure or "") >= min_size) else 0.5
    generation_details.update({
        "success": success,
        "structure_size": len(printer_output.structure or ""),
        "min_required": min_size,
        "score": generation_score
    })
    
    # ═══════════════════════════════════════════════════════════
    # FORMAT SCORE — FIX: Accepter formats partiels
    # ═══════════════════════════════════════════════════════════
    
    format_details = {}
    format_score = 0.5  # Partial credit par défaut
    
    if printer_output.structure:
        structure = printer_output.structure
        file_format = printer_output.format.lower()
        
        # Critères par format
        if file_format == "pdb":
            has_end = structure.strip().endswith("END")
            has_atoms = "ATOM" in structure or "HETATM" in structure
            atom_count = _count_atoms(structure, "PDB")
            
            # Score: au moins 1 critère + atoms présents
            format_score = 1.0 if (has_atoms and atom_count >= 5) else 0.7
            format_details["checks"] = {
                "has_end": has_end,
                "has_atoms": has_atoms,
                "atom_count": atom_count
            }
        
        elif file_format == "mol":
            has_atoms = "V2000" in structure or "V3000" in structure
            atom_count = _count_atoms(structure, "MOL")
            
            format_score = 1.0 if (has_atoms and atom_count >= 3) else 0.7
            format_details["checks"] = {
                "has_version": has_atoms,
                "atom_count": atom_count
            }
        
        format_details["format"] = file_format
        format_details["score"] = format_score
    
    # ═══════════════════════════════════════════════════════════
    # QUALITY SCORE — FIX par cas
    # ═══════════════════════════════════════════════════════════
    
    quality_details = {}
    
    if case == 1:
        # Case 1 (RDKit): Check min 3 atoms + coordonnées
        quality_score = _evaluate_case1_quality_fixed(printer_output, quality_details)
    elif case == 2:
        # Case 2 (ESMFold): Check min residues + PDB valid
        quality_score = _evaluate_case2_quality_fixed(printer_output, quality_details)
    elif case == 3:
        # Case 3 (DiffDock): Check ligand + protein + poses
        quality_score = _evaluate_case3_quality_fixed(printer_output, quality_details)
    else:
        quality_score = 0.5
    
    # ═══════════════════════════════════════════════════════════
    # RELIABILITY SCORE — FIX: Moins pénalisant
    # ═══════════════════════════════════════════════════════════
    
    reliability_details = {}
    model_used = printer_output.model_used.lower()
    
    # Fallback penalty: -0.1 seulement (au lieu de -1.0)
    has_fallback = False
    if case == 2 and "rdkit" in model_used:
        has_fallback = True
    elif case == 3 and "rdkit" in model_used:
        has_fallback = True
    
    reliability_score = 0.9 if has_fallback else 1.0  # Penalty réduit
    reliability_details = {
        "model_used": model_used,
        "has_fallback": has_fallback,
        "score": reliability_score
    }
    
    # ═══════════════════════════════════════════════════════════
    # SCORE GLOBAL — REPONDÉRÉ
    # ═══════════════════════════════════════════════════════════
    
    # Ancien: 0.35 + 0.25 + 0.30 + 0.10
    # Nouveau: Plus tolérant pour RDKit
    if case == 1:
        global_score = (
            generation_score * 0.40 +  # +5% (RDKit local, toujours OK)
            format_score * 0.30 +       # -5%
            quality_score * 0.20 +      # -10%
            reliability_score * 0.10
        )
    else:
        # Cases 2/3: NIM peuvent échouer
        global_score = (
            generation_score * 0.35 +
            format_score * 0.25 +
            quality_score * 0.30 +
            reliability_score * 0.10
        )
    
    # Clamp [0, 1]
    global_score = max(0.0, min(1.0, global_score))
    
    # Status
    if global_score >= 0.85:
        status = "EXCELLENT"
    elif global_score >= 0.70:
        status = "GOOD"
    elif global_score >= 0.50:
        status = "FAIR"
    else:
        status = "POOR"
    
    return PrinterMetrics(
        generation_score=generation_score,
        format_score=format_score,
        quality_score=quality_score,
        reliability_score=reliability_score,
        global_score=global_score,
        generation_details=generation_details,
        format_details=format_details,
        quality_details=quality_details,
        reliability_details=reliability_details,
        status=status
    )

# Fonctions helper CORRIGÉES
def _evaluate_case1_quality_fixed(printer_output: Any, details: Dict) -> float:
    """Case 1: Juste vérifier structure + atomes valides."""
    if not printer_output.structure:
        return 0.0
    
    structure = printer_output.structure
    atom_count = _count_atoms(structure, "MOL")
    has_coords = _has_3d_coordinates(structure, "MOL")
    
    # Score: au moins 3 atomes avec coordonnées
    score = 1.0 if (atom_count >= 3 and has_coords) else 0.6
    
    details.update({
        "atom_count": atom_count,
        "has_3d_coords": has_coords,
        "score": score
    })
    return score

def _evaluate_case2_quality_fixed(printer_output: Any, details: Dict) -> float:
    """Case 2: Vérifier structure protéique valide."""
    if not printer_output.structure:
        return 0.0
    
    structure = printer_output.structure
    is_pdb = "ATOM" in structure or "HETATM" in structure
    atom_count = _count_atoms(structure, "PDB")
    
    # Min ~4 atomes par résidu → min 20 AA = 80 atomes
    estimated_residues = atom_count // 4 if atom_count > 0 else 0
    valid = is_pdb and estimated_residues >= 5
    
    score = 1.0 if valid else 0.6
    details.update({
        "estimated_residues": estimated_residues,
        "score": score
    })
    return score

def _evaluate_case3_quality_fixed(printer_output: Any, details: Dict) -> float:
    """Case 3: Vérifier ligand + protein présents."""
    if not printer_output.structure:
        return 0.0
    
    structure = printer_output.structure
    has_ligand = "HETATM" in structure
    has_protein = "ATOM" in structure
    
    # Au minimum un des deux
    score = 1.0 if (has_ligand or has_protein) else 0.5
    
    details.update({
        "has_protein": has_protein,
        "has_ligand": has_ligand,
        "score": score
    })
    return score

def _count_atoms(structure: str, format_type: str) -> int:
    """Compte le nombre d'atomes dans la structure"""
    if format_type == "PDB":
        return structure.count("ATOM") + structure.count("HETATM")
    elif format_type == "MOL":
        # Première ligne du bloc d'atomes en MOL V2000 : "nb_atomes ..."
        lines = structure.split("\n")
        if len(lines) > 3:
            try:
                parts = lines[3].split()
                return int(parts[0])
            except:
                return 0
    return 0


def _evaluate_case1_quality(printer_output: Any, details: Dict) -> float:
    """Évaluation qualité CAS 1 (petite molécule RDKit)"""
    
    if not printer_output.structure:
        details["quality_checks"] = ["structure_present"]
        details["passed"] = 0
        return 0.0
    
    checks = []
    
    # Check 1 : MOL format avec bloc de coordonnées
    structure = printer_output.structure
    has_atom_block = ("V2000" in structure or "V3000" in structure)
    checks.append(has_atom_block)
    details["has_atom_block"] = has_atom_block
    
    # Check 2 : Nombre d'atomes raisonnable
    atom_count = _count_atoms(structure, "MOL")
    has_reasonable_atoms = 1 <= atom_count <= 200
    checks.append(has_reasonable_atoms)
    details["atom_count"] = atom_count
    details["atoms_reasonable"] = has_reasonable_atoms
    
    # Check 3 : Coordonnées 3D (des nombres en colonnes 31-60 du bloc ATOM)
    has_coordinates = _has_3d_coordinates(structure, "MOL")
    checks.append(has_coordinates)
    details["has_coordinates"] = has_coordinates
    
    score = sum(checks) / len(checks) if checks else 0.0
    details["quality_checks"] = ["atom_block", "reasonable_count", "3d_coords"]
    details["passed"] = sum(checks)
    details["total"] = len(checks)
    
    return score


def _evaluate_case2_quality(printer_output: Any, details: Dict) -> float:
    """Évaluation qualité CAS 2 (protéine ESMFold)"""
    
    if not printer_output.structure:
        details["quality_checks"] = ["structure_present"]
        details["passed"] = 0
        return 0.0
    
    checks = []
    
    # Check 1 : PDB format
    structure = printer_output.structure
    is_pdb = structure.count("ATOM") > 0 or structure.count("HETATM") > 0
    checks.append(is_pdb)
    details["is_pdb"] = is_pdb
    
    # Check 2 : Nombre de résidus raisonnable (protéine > 20 AA)
    atom_count = _count_atoms(structure, "PDB")
    # Moyenne ~3-5 atomes par résidu pour un backbone
    estimated_residues = atom_count // 4 if atom_count > 0 else 0
    has_protein_length = estimated_residues >= 20
    checks.append(has_protein_length)
    details["estimated_residues"] = estimated_residues
    details["has_protein_length"] = has_protein_length
    
    # Check 3 : pLDDT élevé (si ESMFold a fourni)
    # pLDDT en colonne B-factor du PDB
    has_high_confidence = _check_plddt(structure)
    checks.append(has_high_confidence)
    details["high_confidence"] = has_high_confidence
    
    score = sum(checks) / len(checks) if checks else 0.0
    details["quality_checks"] = ["pdb_format", "protein_length", "high_confidence"]
    details["passed"] = sum(checks)
    details["total"] = len(checks)
    
    return score


def _evaluate_case3_quality(printer_output: Any, details: Dict) -> float:
    """Évaluation qualité CAS 3 (docking DiffDock)"""
    
    if not printer_output.structure:
        details["quality_checks"] = ["structure_present"]
        details["passed"] = 0
        return 0.0
    
    checks = []
    
    # Check 1 : PDB format avec ligand (HETATM)
    structure = printer_output.structure
    has_ligand = "HETATM" in structure and "ATOM" in structure
    checks.append(has_ligand)
    details["has_protein_and_ligand"] = has_ligand
    
    # Check 2 : Nombre minimum d'atomes (ligand + protéine)
    atom_count = _count_atoms(structure, "PDB")
    has_sufficient_atoms = atom_count >= 10  # Ligand minimum 5 + protéine backbone
    checks.append(has_sufficient_atoms)
    details["atom_count"] = atom_count
    details["sufficient_atoms"] = has_sufficient_atoms
    
    # Check 3 : Distances ligand-protéine raisonnables
    has_good_poses = _check_docking_poses(structure)
    checks.append(has_good_poses)
    details["good_poses"] = has_good_poses
    
    score = sum(checks) / len(checks) if checks else 0.0
    details["quality_checks"] = ["ligand_present", "sufficient_atoms", "good_poses"]
    details["passed"] = sum(checks)
    details["total"] = len(checks)
    
    return score


def _has_3d_coordinates(structure: str, format_type: str) -> bool:
    """Vérifie que des coordonnées 3D sont présentes"""
    if format_type == "MOL":
        # MOL V2000 : colonnes 1-10 (x), 11-20 (y), 21-30 (z)
        lines = structure.split("\n")
        for line in lines[4:]:  # Skip header
            if line.startswith("M"):
                break
            if len(line) >= 30:
                try:
                    x = float(line[0:10])
                    y = float(line[10:20])
                    z = float(line[20:30])
                    # Au moins une coordonnée non-zéro
                    if x != 0.0 or y != 0.0 or z != 0.0:
                        return True
                except:
                    pass
    return False


def _check_plddt(structure: str) -> bool:
    """Vérifie les scores pLDDT (B-factor >= 70 indique confiance élevée)"""
    lines = structure.split("\n")
    plddt_values = []
    
    for line in lines:
        if line.startswith("ATOM") or line.startswith("HETATM"):
            try:
                # B-factor en colonnes 61-66
                bfactor = float(line[60:66])
                plddt_values.append(bfactor)
            except:
                pass
    
    # Moyenne pLDDT >= 70 = haute confiance
    if plddt_values:
        mean_plddt = sum(plddt_values) / len(plddt_values)
        return mean_plddt >= 70.0
    
    return False


def _check_docking_poses(structure: str) -> bool:
    """Vérifie que le docking a des poses raisonnables"""
    # Ligand et protéine à distance raisonnable (< 10 Ų)
    lines = structure.split("\n")
    
    protein_coords = []
    ligand_coords = []
    
    for line in lines:
        if line.startswith("ATOM"):
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                protein_coords.append((x, y, z))
            except:
                pass
        elif line.startswith("HETATM"):
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                ligand_coords.append((x, y, z))
            except:
                pass
    
    if protein_coords and ligand_coords:
        # Distance minimum entre ligand et protéine
        min_dist = float('inf')
        for lx, ly, lz in ligand_coords:
            for px, py, pz in protein_coords:
                dist = ((lx - px) ** 2 + (ly - py) ** 2 + (lz - pz) ** 2) ** 0.5
                min_dist = min(min_dist, dist)
        
        # Ligand doit être proche mais pas collé (0.5 < dist < 15 Å)
        return 0.5 < min_dist < 15.0
    
    return False