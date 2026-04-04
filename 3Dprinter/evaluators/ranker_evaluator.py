"""
Ranker Evaluator — Métriques de performance du Ranker
Score global = 30% extraction + 40% classification + 20% confiance + 10% fiabilité
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RankerMetrics:
    """Résultats des métriques Ranker"""
    extraction_score: float      # 0.0-1.0
    classification_score: float  # 0.0-1.0
    confidence_score: float      # 0.0-1.0 (de LLM)
    reliability_score: float     # 0.0-1.0 (pas de fallback)
    
    global_score: float          # Score global pondéré
    
    extraction_details: Dict[str, Any]
    classification_details: Dict[str, Any]
    reliability_details: Dict[str, Any]
    
    status: str                  # "EXCELLENT" / "GOOD" / "FAIR" / "POOR"
    
    def __str__(self) -> str:
        bar = "█" * int(self.global_score * 10) + "░" * (10 - int(self.global_score * 10))
        return (
            f"[RANKER METRICS]\n"
            f"  Global Score   : {bar} {self.global_score:.1%} ({self.status})\n"
            f"  ├─ Extraction  : {self.extraction_score:.1%} (30%)\n"
            f"  ├─ Classification: {self.classification_score:.1%} (40%)\n"
            f"  ├─ Confidence  : {self.confidence_score:.1%} (20%)\n"
            f"  └─ Reliability : {self.reliability_score:.1%} (10%)"
        )


def evaluate_ranker(
    ranker_output: Any,
    expected_case: Optional[int] = None,
    extraction_method: str = "llm"
) -> RankerMetrics:
    """
    Évalue la performance du Ranker sur 4 dimensions
    
    Args:
        ranker_output: RankerOutput du Ranker
        expected_case: Cas attendu (optionnel pour validation)
        extraction_method: "llm" ou "regex_fallback"
    
    Returns:
        RankerMetrics avec scores détaillés
    """
    
    # ═══════════════════════════════════════════════════════════
    # 1. EXTRACTION SCORE (30%)
    # ═══════════════════════════════════════════════════════════
    
    extraction_details = {}
    extraction_checks = []
    
    v = ranker_output.input_validation
    
    # Check 1 : SMILES présent et valide
    has_valid_smiles = (
        v.get("has_smiles", False) and 
        v.get("smiles_valid", False)
    )
    extraction_checks.append(has_valid_smiles)
    extraction_details["smiles_valid"] = has_valid_smiles
    
    # Check 2 : Séquence protéique valide (si présente)
    has_valid_sequence = (
        not v.get("has_protein_sequence", False) or  # Pas obligatoire
        (v.get("has_protein_sequence", False) and v.get("sequence_valid", False))
    )
    extraction_checks.append(has_valid_sequence)
    extraction_details["sequence_valid"] = has_valid_sequence
    
    # Check 3 : Nom de molécule extrait
    has_molecule_name = bool(v.get("molecule_name") and v.get("molecule_name") != "Unknown")
    extraction_checks.append(has_molecule_name)
    extraction_details["name_found"] = has_molecule_name
    
    # Check 4 : Intention extraite
    has_intention = bool(v.get("experiment_intent") and v.get("experiment_intent") != "unknown")
    extraction_checks.append(has_intention)
    extraction_details["intention_found"] = has_intention
    
    # Score extraction
    extraction_score = sum(extraction_checks) / len(extraction_checks)
    extraction_details["total_checks"] = len(extraction_checks)
    extraction_details["passed_checks"] = sum(extraction_checks)
    
    logger.info(f"[RANKER EVAL] Extraction: {sum(extraction_checks)}/{len(extraction_checks)} checks")
    
    
    # ═══════════════════════════════════════════════════════════
    # 2. CLASSIFICATION SCORE (40%)
    # ═══════════════════════════════════════════════════════════
    
    classification_details = {}
    case = ranker_output.case
    
    if expected_case is not None:
        # Comparaison avec ground-truth
        classification_score = 1.0 if case == expected_case else 0.0
        classification_details["comparison"] = f"expected={expected_case}, predicted={case}"
        classification_details["correct"] = (case == expected_case)
        logger.info(f"[RANKER EVAL] Classification: {case} vs expected {expected_case} → {classification_score:.1%}")
    else:
        # Vérification cohérence SMILES/séquence vs cas
        coherence = _check_case_coherence(
            has_smiles=v.get("has_smiles", False),
            has_sequence=v.get("has_protein_sequence", False),
            predicted_case=case
        )
        classification_score = 1.0 if coherence else 0.5
        classification_details["coherence_check"] = coherence
        classification_details["predicted_case"] = case
        logger.info(f"[RANKER EVAL] Classification coherence: {coherence} → {classification_score:.1%}")
    
    
    # ═══════════════════════════════════════════════════════════
    # 3. CONFIDENCE SCORE (20%)
    # ═══════════════════════════════════════════════════════════
    
    confidence_score = ranker_output.confidence
    confidence_details = {
        "llm_confidence": confidence_score,
        "threshold_met": confidence_score >= 0.80
    }
    
    logger.info(f"[RANKER EVAL] LLM Confidence: {confidence_score:.1%} (threshold: 0.80)")
    
    
    # ═══════════════════════════════════════════════════════════
    # 4. RELIABILITY SCORE (10%) - Pas de fallback
    # ═══════════════════════════════════════════════════════════
    
    extraction_method_used = v.get("extraction_method", "unknown")
    has_fallback = (
        extraction_method_used == "regex_fallback" or
        confidence_score < 0.80  # Fallback forcé
    )
    
    reliability_score = 0.0 if has_fallback else 1.0
    reliability_details = {
        "extraction_method": extraction_method_used,
        "has_fallback": has_fallback,
        "confidence_forced_fallback": confidence_score < 0.80
    }
    
    logger.info(f"[RANKER EVAL] Reliability: {reliability_score:.1%} (fallback={has_fallback})")
    
    
    # ═══════════════════════════════════════════════════════════
    # SCORE GLOBAL (PONDÉRÉ)
    # ═══════════════════════════════════════════════════════════
    
    global_score = (
        extraction_score * 0.30 +
        classification_score * 0.40 +
        confidence_score * 0.20 +
        reliability_score * 0.10
    )
    
    # Déterminer le statut
    if global_score >= 0.90:
        status = "EXCELLENT"
    elif global_score >= 0.75:
        status = "GOOD"
    elif global_score >= 0.60:
        status = "FAIR"
    else:
        status = "POOR"
    
    logger.info(f"[RANKER EVAL] GLOBAL SCORE: {global_score:.1%} ({status})")
    
    return RankerMetrics(
        extraction_score=extraction_score,
        classification_score=classification_score,
        confidence_score=confidence_score,
        reliability_score=reliability_score,
        global_score=global_score,
        extraction_details=extraction_details,
        classification_details=classification_details,
        reliability_details=reliability_details,
        status=status
    )


def _check_case_coherence(has_smiles: bool, has_sequence: bool, predicted_case: int) -> bool:
    """
    Vérifie la cohérence entre les données et le cas prédit
    
    Cas 1: SMILES seul (pas de séquence)
    Cas 2: Séquence seule (pas de SMILES)
    Cas 3: SMILES + séquence
    """
    if has_smiles and has_sequence:
        return predicted_case == 3
    elif has_sequence:
        return predicted_case == 2
    elif has_smiles:
        return predicted_case == 1
    else:
        return False