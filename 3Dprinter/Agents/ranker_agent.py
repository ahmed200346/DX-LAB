"""
Ranker Agent V2 — Virtual Drug Discovery Lab
Intelligent LLM-based Classification Pipeline
Uses Llama-3.1-70B for smart case decision making
"""

import logging
import json
import re
import httpx
import asyncio
from typing import TypedDict, Any, Dict, Optional
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from settings.configuration import (
    LOCAL_LLAMA_CONFIG,
    CLASSIFICATION_CONFIG,
    MoleculeInput,
    RankerOutput,
)

# RDKit optional
try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False
    logging.warning("[RANKER] RDKit not available")

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# STATE DEFINITION
# ═══════════════════════════════════════════════════════════════

class RankerStateV2(TypedDict):
    """State for intelligent ranker workflow"""
    # Input
    raw_description: str
    molecule_input: MoleculeInput
    use_structured_input: bool
    
    # Extraction phase
    extracted_data: Dict[str, Any]
    extraction_confidence: float
    
    # Validation phase
    validation_result: Dict[str, Any]
    
    # Ambiguity detection
    is_ambiguous: bool
    ambiguity_type: Optional[str]
    
    # LLM Classification
    llm_classification_result: Dict[str, Any]
    
    # Final output
    case_classification: int
    model_assignment: str
    confidence_score: float
    llm_reasoning: str
    alternative_cases: list
    error: Optional[str]


# ═══════════════════════════════════════════════════════════════
# LLM CLIENT
# ═══════════════════════════════════════════════════════════════

def _get_local_llm(temperature: float = 0.1) -> ChatOpenAI:
    """Create LLM client"""
    http_client = httpx.Client(verify=LOCAL_LLAMA_CONFIG["verify_ssl"])
    return ChatOpenAI(
        model=LOCAL_LLAMA_CONFIG["model"],
        api_key=LOCAL_LLAMA_CONFIG["api_key"],
        base_url=LOCAL_LLAMA_CONFIG["server_url"],
        temperature=temperature,
        max_tokens=LOCAL_LLAMA_CONFIG["max_tokens"],
        http_client=http_client,
        timeout=LOCAL_LLAMA_CONFIG["timeout"],
    )


# ═══════════════════════════════════════════════════════════════
# NODE 1: EXTRACT FROM DESCRIPTION
# ═══════════════════════════════════════════════════════════════

async def extract_from_description_node(state: RankerStateV2) -> RankerStateV2:
    """Extract SMILES, sequence, name from description using LLM"""
    
    if state.get("use_structured_input"):
        mol = state["molecule_input"]
        state["extracted_data"] = {
            "smiles": mol.smiles,
            "protein_sequence": mol.protein_sequence,
            "molecule_name": mol.molecule_name or "Unknown",
            "experiment_intent": "structured input",
            "extraction_method": "structured",
        }
        state["extraction_confidence"] = 0.99
        logger.info("[RANKER] Bypass extraction — structured input")
        return state
    
    description = state.get("raw_description", "").strip()
    if not description:
        state["error"] = "Description vide"
        state["extracted_data"] = {}
        state["extraction_confidence"] = 0.0
        return state
    
    logger.info("[RANKER] 🔍 Extraction LLM...")
    
    # Prepare extraction prompt
    extraction_prompt = CLASSIFICATION_CONFIG["extraction_prompt_template"].format(
        description=description
    )
    
    try:
        llm = _get_local_llm(temperature=0.05)
        messages = [
            SystemMessage(content="Tu es un expert chimiste. Extrais SMILES et séquences de protéines."),
            HumanMessage(content=extraction_prompt),
        ]
        
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        
        # Parse JSON
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)
        
        extracted = json.loads(raw)
        
        # Cleanup null values
        for key in ["smiles", "protein_sequence"]:
            val = extracted.get(key)
            if val in (None, "null", "None", "", "N/A"):
                extracted[key] = None
            elif val:
                extracted[key] = str(val).strip()
        
        extracted["extraction_method"] = "llm"
        state["extracted_data"] = extracted
        state["extraction_confidence"] = float(extracted.get("extraction_confidence", 0.8))
        
        logger.info(
            f"[RANKER] ✅ Extraction: SMILES={'✓' if extracted.get('smiles') else '✗'}, "
            f"Seq={'✓' if extracted.get('protein_sequence') else '✗'}"
        )
    
    except json.JSONDecodeError as e:
        logger.warning(f"[RANKER] JSON parse failed, using regex fallback")
        extracted = _regex_fallback_extraction(description)
        extracted["extraction_method"] = "regex_fallback"
        state["extracted_data"] = extracted
        state["extraction_confidence"] = 0.6
    
    except Exception as e:
        logger.error(f"[RANKER] Extraction error: {e}")
        state["error"] = str(e)
        state["extracted_data"] = {}
        state["extraction_confidence"] = 0.0
    
    return state


# ═══════════════════════════════════════════════════════════════
# NODE 2: VALIDATE INPUT
# ═══════════════════════════════════════════════════════════════

async def validate_input_node(state: RankerStateV2) -> RankerStateV2:
    """Validate extracted data with RDKit - IMPROVED VERSION"""
    
    if state.get("error"):
        state["validation_result"] = {}
        return state
    
    extracted = state.get("extracted_data", {})
    validation: Dict[str, Any] = {}
    
    smiles = extracted.get("smiles")
    sequence = extracted.get("protein_sequence")
    
    validation["has_smiles"] = bool(smiles)
    validation["has_protein_sequence"] = bool(sequence)
    validation["molecule_name"] = extracted.get("molecule_name", "Unknown")
    
    if not validation["has_smiles"] and not validation["has_protein_sequence"]:
        state["error"] = "No chemical data found"
        state["validation_result"] = validation
        return state
    
    # ═══════════════════════════════════════════════════════════
    # VALIDATE SMILES - IMPROVED
    # ═══════════════════════════════════════════════════════════
    
    if validation["has_smiles"]:
        validation["smiles"] = smiles
        validation["smiles_length"] = len(smiles)
        
        # Check SMILES format validity (even if RDKit fails)
        smiles_format_valid = _validate_smiles_format(smiles)
        validation["smiles_format_valid"] = smiles_format_valid
        
        if RDKIT_AVAILABLE:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                # Format is valid but RDKit can't parse
                # Still count as valid for classification purposes
                validation["smiles_valid"] = smiles_format_valid
                if smiles_format_valid:
                    logger.warning(f"[RANKER] SMILES format OK but RDKit parse failed: {smiles[:50]}...")
                else:
                    logger.warning(f"[RANKER] Invalid SMILES: {smiles}")
            else:
                validation["smiles_valid"] = True
                mw = Descriptors.MolWt(mol)
                logp = Descriptors.MolLogP(mol)
                hbd = rdMolDescriptors.CalcNumHBD(mol)
                hba = rdMolDescriptors.CalcNumHBA(mol)
                num_atoms = mol.GetNumHeavyAtoms()
                
                validation.update({
                    "mw": round(mw, 2),
                    "logp": round(logp, 3),
                    "hbd": hbd,
                    "hba": hba,
                    "num_heavy_atoms": num_atoms,
                    "is_small_molecule": num_atoms <= 100 and mw <= 900,
                })
    
    # ═══════════════════════════════════════════════════════════
    # VALIDATE SEQUENCE - IMPROVED (Auto-clean invalid chars)
    # ═══════════════════════════════════════════════════════════
    
    if validation["has_protein_sequence"]:
        seq_raw = re.sub(r'\s+', '', sequence.strip().upper())
        
        VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")
        invalid_chars = set(seq_raw) - VALID_AA
        
        if invalid_chars:
            logger.warning(f"[RANKER] ⚠️ Invalid AA chars found: {invalid_chars}")
            
            # AUTO-CLEAN: Remove invalid chars
            seq_clean = ''.join(c for c in seq_raw if c in VALID_AA)
            
            # Check if enough valid AAs remain
            if len(seq_clean) >= 5:
                validation["sequence_valid"] = True
                validation["sequence_length"] = len(seq_clean)
                validation["sequence_clean"] = seq_clean
                validation["sequence_auto_cleaned"] = True
                validation["removed_chars"] = list(invalid_chars)
                logger.info(f"[RANKER] ✅ Sequence auto-cleaned: {len(seq_raw)} → {len(seq_clean)} AA")
            else:
                validation["sequence_valid"] = False
                validation["has_protein_sequence"] = False
                logger.warning(f"[RANKER] ❌ Sequence too short after cleaning")
        else:
            validation["sequence_valid"] = True
            validation["sequence_length"] = len(seq_raw)
            validation["sequence_clean"] = seq_raw
            validation["sequence_auto_cleaned"] = False
            validation["is_short_peptide"] = len(seq_raw) <= 50
    
    state["validation_result"] = validation
    logger.info(f"[RANKER] ✅ Validation complete")
    return state


def _validate_smiles_format(smiles: str) -> bool:
    """
    Validate SMILES format without RDKit
    Handles even very long SMILES strings
    """
    if not smiles or len(smiles) < 2:
        return False
    
    # Check basic SMILES format
    valid_chars = set('CNOSPFBrClI@+=-#()[]\\/.%0123456789')
    
    # Remove spaces
    smiles_clean = smiles.replace(' ', '')
    
    # All chars must be valid
    if not all(c in valid_chars for c in smiles_clean):
        return False
    
    # Brackets must match
    if smiles_clean.count('[') != smiles_clean.count(']'):
        return False
    if smiles_clean.count('(') != smiles_clean.count(')'):
        return False
    
    # Must start and end with reasonable characters
    valid_start = set('CNOSPFBc[')
    valid_end = set('CNOSPFBcI0123456789)]}')
    
    if smiles_clean[0] not in valid_start:
        return False
    if smiles_clean[-1] not in valid_end:
        return False
    
    return True

# ═══════════════════════════════════════════════════════════════
# NODE 3: DETECT AMBIGUITY
# ═══════════════════════════════════════════════════════════════

async def detect_ambiguity_node(state: RankerStateV2) -> RankerStateV2:
    """Detect if data is ambiguous (peptide vs SMILES, etc.)"""
    
    if state.get("error"):
        state["is_ambiguous"] = False
        return state
    
    v = state["validation_result"]
    extracted = state.get("extracted_data", {})
    
    logger.info("[RANKER] 🔍 Detecting ambiguity...")
    
    # Simple heuristics first
    ambiguity_type = None
    
    smiles = extracted.get("smiles")
    sequence = extracted.get("protein_sequence")
    
    # Check if SMILES contains amide bonds (peptide indicator)
    if smiles and RDKIT_AVAILABLE:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                pattern = Chem.MolFromSmarts("[NX3][CX3](=[OX1])")
                amide_count = len(mol.GetSubstructMatches(pattern))
                if amide_count >= 3:
                    ambiguity_type = "peptide_vs_smiles"
                    logger.warning("[RANKER] ⚠️ SMILES contains amide bonds (peptide?)")
        except:
            pass
    
    # Check if sequence is incomplete
    if sequence and len(sequence) < 10:
        ambiguity_type = "incomplete_sequence"
        logger.warning("[RANKER] ⚠️ Sequence very short (< 10 AA)")
    
    state["is_ambiguous"] = ambiguity_type is not None
    state["ambiguity_type"] = ambiguity_type
    
    return state


# ═══════════════════════════════════════════════════════════════
# NODE 4: LLM INTELLIGENT CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

async def llm_intelligent_classify_node(state: RankerStateV2) -> RankerStateV2:
    """LLM makes intelligent case decision"""
    
    if state.get("error") and not state.get("extracted_data"):
        state["llm_classification_result"] = {
            "case": 1,
            "confidence": 0.0,
            "reasoning": "Error in previous steps"
        }
        return state
    
    logger.info("[RANKER] 🤖 LLM Intelligent Classification...")
    
    v = state["validation_result"]
    extracted = state.get("extracted_data", {})
    
    # Prepare context
    context = f"""
DONNÉES EXTRAITES ET VALIDÉES:

SMILES: {extracted.get('smiles') or 'Non fourni'}
  Valide: {v.get('smiles_valid', False)}
  Longueur: {v.get('smiles_length', 0)}
  Molécule viable: {v.get('is_small_molecule', False)}

SÉQUENCE PROTÉIQUE: {extracted.get('protein_sequence')[:50] + '...' if extracted.get('protein_sequence') and len(extracted.get('protein_sequence', '')) > 50 else extracted.get('protein_sequence') or 'Non fourni'}
  Valide: {v.get('sequence_valid', False)}
  Longueur: {v.get('sequence_length', 0)} AA
  Type: {'Peptide court' if v.get('is_short_peptide') else 'Protéine'}

NOM: {v.get('molecule_name', 'Unknown')}
INTENTION: {extracted.get('experiment_intent', 'Unknown')}

DÉTAILS CHIMIQUES:
{json.dumps(v, indent=2, default=str)}

AMBIGUITÉ DÉTECTÉE: {state.get('is_ambiguous', False)}
TYPE AMBIGUITÉ: {state.get('ambiguity_type', 'Aucune')}

Quelle est la meilleure classification (CASE 1/2/3)?
"""
    
    try:
        llm = _get_local_llm(temperature=0.1)
        messages = [
            SystemMessage(content=CLASSIFICATION_CONFIG["system_prompt"]),
            HumanMessage(content=context),
        ]
        
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        
        # Parse JSON
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)
        
        parsed = json.loads(raw)
        
        state["llm_classification_result"] = parsed
        
        case = int(parsed.get("case", 1))
        confidence = float(parsed.get("confidence", 0.5))
        reasoning = parsed.get("reasoning", "")
        
        logger.info(
            f"[RANKER] ✅ LLM Classification: CASE {case} "
            f"(confidence: {confidence:.0%}) — {reasoning}"
        )
    
    except json.JSONDecodeError:
        logger.warning("[RANKER] JSON parse failed in LLM classification")
        state["llm_classification_result"] = {
            "case": _determine_case_by_heuristics(v),
            "confidence": 0.6,
            "reasoning": "Fallback heuristics"
        }
    
    except Exception as e:
        logger.error(f"[RANKER] LLM classification error: {e}")
        state["llm_classification_result"] = {
            "case": 1,
            "confidence": 0.0,
            "reasoning": f"Error: {str(e)[:50]}"
        }
    
    return state


# ═══════════════════════════════════════════════════════════════
# NODE 5: COMPUTE CONFIDENCE SCORE
# ═══════════════════════════════════════════════════════════════

async def compute_confidence_node(state: RankerStateV2) -> RankerStateV2:
    """Compute overall confidence from multiple factors"""
    
    logger.info("[RANKER] 📊 Computing confidence score...")
    
    extraction_conf = state.get("extraction_confidence", 0.5)
    llm_result = state.get("llm_classification_result", {})
    llm_conf = float(llm_result.get("confidence", 0.5))
    
    # Penalize if ambiguous
    ambiguity_penalty = 0.15 if state.get("is_ambiguous") else 0.0
    
    # Penalize if fallback extraction
    extraction_method = state.get("extracted_data", {}).get("extraction_method", "")
    extraction_penalty = 0.10 if extraction_method == "regex_fallback" else 0.0
    
    # Final score
    final_confidence = (
        extraction_conf * 0.35 +
        llm_conf * 0.65 -
        ambiguity_penalty -
        extraction_penalty
    )
    
    final_confidence = max(0.0, min(1.0, final_confidence))
    
    state["confidence_score"] = final_confidence
    
    logger.info(f"[RANKER] ✅ Confidence: {final_confidence:.0%}")
    
    return state


# ═══════════════════════════════════════════════════════════════
# NODE 6: FINAL DECISION
# ═══════════════════════════════════════════════════════════════

async def final_decision_node(state: RankerStateV2) -> RankerStateV2:
    """Make final decision and assign model"""
    
    logger.info("[RANKER] 🎯 Final Decision...")
    
    llm_result = state.get("llm_classification_result", {})
    case = int(llm_result.get("case", 1))
    confidence = state.get("confidence_score", 0.0)
    reasoning = llm_result.get("reasoning", "")
    alternatives = llm_result.get("alternative_cases", [])
    
    CASE_TO_MODEL = {1: "rdkit", 2: "esmfold_nim", 3: "diffdock_nim"}
    
    state["case_classification"] = case
    state["model_assignment"] = CASE_TO_MODEL.get(case, "rdkit")
    state["llm_reasoning"] = reasoning
    state["alternative_cases"] = alternatives or []
    
    status = "EXCELLENT" if confidence >= 0.90 else \
             "GOOD" if confidence >= 0.75 else \
             "FAIR" if confidence >= 0.60 else "POOR"
    
    logger.info(
        f"[RANKER] ✅ FINAL → CASE {case} | "
        f"Model: {state['model_assignment']} | "
        f"Confidence: {confidence:.0%} ({status})"
    )
    
    return state


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _determine_case_by_heuristics(validation: Dict) -> int:
    """Fallback heuristic classification"""
    has_smiles = validation.get("has_smiles") and validation.get("smiles_valid")
    has_sequence = validation.get("has_protein_sequence") and validation.get("sequence_valid")
    
    if has_smiles and has_sequence:
        return 3
    elif has_sequence:
        return 2
    elif has_smiles:
        return 1
    else:
        return 1


def _regex_fallback_extraction(text: str) -> Dict[str, Any]:
    """Regex fallback extraction"""
    extracted = {
        "smiles": None,
        "protein_sequence": None,
        "molecule_name": "Unknown",
        "experiment_intent": "unknown",
        "extraction_confidence": 0.4,
    }
    
    # Search for SMILES
    smiles_match = re.search(
        r'(?:SMILES|smiles)\s*[:\=]\s*([A-Za-z0-9@+\-\[\]()=#\\/%.]+)',
        text
    )
    if smiles_match:
        extracted["smiles"] = smiles_match.group(1).strip()
    
    # Search for sequence
    seq_match = re.search(r'\b([ACDEFGHIKLMNPQRSTVWY]{10,})\b', text.upper())
    if seq_match:
        extracted["protein_sequence"] = seq_match.group(1)
    
    return extracted


# ═══════════════════════════════════════════════════════════════
# WORKFLOW BUILDER
# ═══════════════════════════════════════════════════════════════

def build_ranker_workflow_v2() -> StateGraph:
    """Build intelligent ranker workflow"""
    wf = StateGraph(RankerStateV2)
    
    wf.add_node("extract", extract_from_description_node)
    wf.add_node("validate", validate_input_node)
    wf.add_node("detect_ambiguity", detect_ambiguity_node)
    wf.add_node("llm_classify", llm_intelligent_classify_node)
    wf.add_node("compute_confidence", compute_confidence_node)
    wf.add_node("final_decision", final_decision_node)
    
    wf.add_edge(START, "extract")
    wf.add_edge("extract", "validate")
    wf.add_edge("validate", "detect_ambiguity")
    wf.add_edge("detect_ambiguity", "llm_classify")
    wf.add_edge("llm_classify", "compute_confidence")
    wf.add_edge("compute_confidence", "final_decision")
    wf.add_edge("final_decision", END)
    
    return wf.compile()


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

async def rank_molecule_from_description(description: str) -> RankerOutput:
    """Main entry point for description-based ranking"""
    
    logger.info("[RANKER] 🚀 Starting V2 intelligent classification...")
    
    graph = build_ranker_workflow_v2()
    
    initial_state: RankerStateV2 = {
        "raw_description": description,
        "molecule_input": MoleculeInput(),
        "use_structured_input": False,
        "extracted_data": {},
        "extraction_confidence": 0.0,
        "validation_result": {},
        "is_ambiguous": False,
        "ambiguity_type": None,
        "llm_classification_result": {},
        "case_classification": 1,
        "model_assignment": "rdkit",
        "confidence_score": 0.0,
        "llm_reasoning": "",
        "alternative_cases": [],
        "error": None,
    }
    
    final = await graph.ainvoke(initial_state)
    
    return RankerOutput(
        case=final["case_classification"],
        model=final["model_assignment"],
        confidence=final["confidence_score"],
        input_validation=final["validation_result"],
        llm_reasoning=final["llm_reasoning"],
        alternative_cases=final["alternative_cases"]
    )


async def rank_molecule_from_structured(molecule_input: MoleculeInput) -> RankerOutput:
    """Structured input ranking"""
    
    logger.info("[RANKER] 🚀 Starting V2 with structured input...")
    
    graph = build_ranker_workflow_v2()
    
    initial_state: RankerStateV2 = {
        "raw_description": "",
        "molecule_input": molecule_input,
        "use_structured_input": True,
        "extracted_data": {},
        "extraction_confidence": 0.99,
        "validation_result": {},
        "is_ambiguous": False,
        "ambiguity_type": None,
        "llm_classification_result": {},
        "case_classification": 1,
        "model_assignment": "rdkit",
        "confidence_score": 0.0,
        "llm_reasoning": "",
        "alternative_cases": [],
        "error": None,
    }
    
    final = await graph.ainvoke(initial_state)
    
    return RankerOutput(
        case=final["case_classification"],
        model=final["model_assignment"],
        confidence=final["confidence_score"],
        input_validation=final["validation_result"],
        llm_reasoning=final["llm_reasoning"],
        alternative_cases=final["alternative_cases"]
    )
# """
# Ranker Agent — Virtual Drug Discovery Lab
# Analyse une description en langage naturel pour extraire les données
# chimiques (SMILES, séquence protéique) et classifier le cas d'expérience :

#   CAS 1 → SMILES seul          → RDKit (conformère 3D local)
#   CAS 2 → Séquence protéique   → ESMFold NIM (repliement 3D)
#   CAS 3 → SMILES + séquence    → DiffDock NIM (docking moléculaire)

# LLM utilisé : Llama-3.1-70B-Instruct (serveur local ESPRIT via vLLM)
# """

# import logging
# import json
# import re
# import httpx
# from typing import TypedDict, Any, Dict, Optional

# from langchain_openai import ChatOpenAI
# from langchain_core.messages import HumanMessage, SystemMessage
# from langgraph.graph import StateGraph, START, END

# import sys
# import os
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from settings.configuration import (
#     LOCAL_LLAMA_CONFIG,
#     MoleculeInput,
#     RankerOutput,
# )

# # ── RDKit (validation chimique locale) ─────────────────────────
# try:
#     from rdkit import Chem
#     from rdkit.Chem import Descriptors, rdMolDescriptors
#     RDKIT_AVAILABLE = True
# except ImportError:
#     RDKIT_AVAILABLE = False
#     logging.warning("[RANKER] RDKit non disponible — validation chimique basique")

# logger = logging.getLogger(__name__)


# # ═══════════════════════════════════════════════════════════════
# # CONSTANTS
# # ═══════════════════════════════════════════════════════════════

# CASE_TO_MODEL: Dict[int, str] = {
#     1: "rdkit",
#     2: "esmfold_nim",
#     3: "diffdock_nim",
# }

# VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")
# LOW_CONFIDENCE_THRESHOLD = 0.65


# # ═══════════════════════════════════════════════════════════════
# # STATE
# # ═══════════════════════════════════════════════════════════════

# class RankerState(TypedDict):
#     # Entrée brute
#     raw_description: str            # texte libre de l'utilisateur
#     molecule_input: MoleculeInput   # input structuré (si fourni directement)
#     use_structured_input: bool      # True = bypass extraction LLM

#     # Résultats intermédiaires
#     extracted_data: Dict[str, Any]  # sortie JSON de l'extraction LLM
#     validation_result: Dict[str, Any]
#     deterministic_case: int
#     llm_case: int

#     # Sortie finale
#     case_classification: int
#     model_assignment: str
#     confidence_score: float
#     llm_reasoning: str
#     error: Optional[str]


# # ═══════════════════════════════════════════════════════════════
# # LLM CLIENT — Llama3.1 local (OpenAI-compatible via vLLM)
# # ═══════════════════════════════════════════════════════════════

# def _get_local_llm(temperature: float = 0.1) -> ChatOpenAI:
#     """
#     Crée un client LangChain compatible avec le serveur vLLM local ESPRIT.
#     Désactive la vérification SSL (certificat auto-signé).
#     """
#     http_client = httpx.Client(verify=LOCAL_LLAMA_CONFIG["verify_ssl"])

#     return ChatOpenAI(
#         model=LOCAL_LLAMA_CONFIG["model"],
#         api_key=LOCAL_LLAMA_CONFIG["api_key"],
#         base_url=LOCAL_LLAMA_CONFIG["server_url"],
#         temperature=temperature,
#         max_tokens=LOCAL_LLAMA_CONFIG["max_tokens"],
#         http_client=http_client,
#         # Désactive les timeouts stricts pour le serveur local
#         timeout=LOCAL_LLAMA_CONFIG["timeout"],
#     )


# # ═══════════════════════════════════════════════════════════════
# # NODE 1 — EXTRACTION LLM (description → JSON structuré)
# # ═══════════════════════════════════════════════════════════════

# async def extract_from_description_node(state: RankerState) -> RankerState:
#     """
#     Utilise Llama3.1-70B pour extraire depuis une description libre :
#       - SMILES (si présent ou mentionné)
#       - Séquence protéique en acides aminés (si présente)
#       - Nom de la molécule / protéine
#       - Intention de l'expérience (visualisation, docking, etc.)

#     Si use_structured_input=True, ce nœud est skippé.
#     """
#     # ── Bypass si input structuré ───────────────────────────────
#     if state.get("use_structured_input"):
#         mol = state["molecule_input"]
#         state["extracted_data"] = {
#             "smiles":           mol.smiles,
#             "protein_sequence": mol.protein_sequence,
#             "molecule_name":    mol.molecule_name or "Unknown",
#             "experiment_intent":"structured input",
#             "extraction_method":"structured",
#         }
#         logger.info("[RANKER] Bypass extraction LLM — input structuré")
#         return state

#     description = state.get("raw_description", "").strip()
#     if not description:
#         state["error"] = "Description vide — aucun texte fourni"
#         state["extracted_data"] = {}
#         return state

#     logger.info("[RANKER] Extraction LLM depuis description naturelle...")

#     system_prompt = """Tu es un expert en chimie médicinale et bioinformatique.
# Ta mission : extraire des informations chimiques depuis une description textuelle.

# Règles d'extraction :
# 1. SMILES : chaîne chimique comme "CC(=O)Oc1ccccc1C(=O)O" ou "c1ccccc1"
#    - Cherche après des mots-clés : "SMILES", "structure", "molécule", "composé", "ligand"
#    - Une séquence de caractères chimiques (C, N, O, c, (, ), =, #, [, ], +, -, /, \\, @, %)
#    - Si non trouvé : null
# 2. protein_sequence : séquence d'acides aminés en code 1 lettre (ACDEFGHIKLMNPQRSTVWY uniquement)
#    - Cherche après : "séquence", "protéine", "acides aminés", "AA", "résidus"
#    - Ne pas confondre avec un SMILES
#    - Si non trouvé : null
# 3. molecule_name : nom commun ou IUPAC de la molécule/protéine
# 4. experiment_intent : ce que veut faire l'utilisateur en 1 phrase courte

# Réponds UNIQUEMENT en JSON valide (sans markdown, sans explication) :
# {
#   "smiles": "...",
#   "protein_sequence": "...",
#   "molecule_name": "...",
#   "experiment_intent": "...",
#   "extraction_confidence": 0.95
# }"""

#     user_prompt = f"""Extrais les informations chimiques de cette description :

# ---
# {description}
# ---

# Rappel : réponds uniquement en JSON valide."""

#     try:
#         llm = _get_local_llm(temperature=0.05)
#         messages = [
#             SystemMessage(content=system_prompt),
#             HumanMessage(content=user_prompt),
#         ]

#         response = await llm.ainvoke(messages)
#         raw = response.content.strip()

#         # Nettoyage markdown
#         raw = re.sub(r"```json\s*", "", raw)
#         raw = re.sub(r"```\s*", "", raw)
#         raw = raw.strip()

#         # Extraire le JSON même si le LLM ajoute du texte avant/après
#         json_match = re.search(r'\{.*\}', raw, re.DOTALL)
#         if json_match:
#             raw = json_match.group(0)

#         extracted = json.loads(raw)

#         # Nettoyage des valeurs null / "null" / "None"
#         for key in ["smiles", "protein_sequence"]:
#             val = extracted.get(key)
#             if val in (None, "null", "None", "", "N/A", "n/a"):
#                 extracted[key] = None
#             elif val:
#                 extracted[key] = str(val).strip()

#         extracted["extraction_method"] = "llm"
#         state["extracted_data"] = extracted

#         logger.info(
#             f"[RANKER] Extraction OK — "
#             f"SMILES={'oui' if extracted.get('smiles') else 'non'}, "
#             f"Séquence={'oui' if extracted.get('protein_sequence') else 'non'}, "
#             f"Nom={extracted.get('molecule_name', 'Unknown')}"
#         )

#     except json.JSONDecodeError as e:
#         logger.error(f"[RANKER] Échec parse JSON extraction : {raw!r} — {e}")
#         # Fallback : extraction par regex basique
#         extracted = _regex_fallback_extraction(description)
#         extracted["extraction_method"] = "regex_fallback"
#         state["extracted_data"] = extracted
#         logger.info(f"[RANKER] Fallback regex : {extracted}")

#     except Exception as e:
#         logger.error(f"[RANKER] Erreur extraction LLM : {e}")
#         state["error"] = f"Extraction échouée : {e}"
#         state["extracted_data"] = {}

#     return state


# # ═══════════════════════════════════════════════════════════════
# # NODE 2 — VALIDATION CHIMIQUE (RDKit)
# # ═══════════════════════════════════════════════════════════════

# async def validate_input_node(state: RankerState) -> RankerState:
#     """
#     Valide et enrichit les données extraites avec RDKit.
#     Calcule les propriétés physico-chimiques pour le prompt de classification.
#     """
#     if state.get("error") and not state.get("extracted_data"):
#         return state

#     extracted = state.get("extracted_data", {})
#     validation: Dict[str, Any] = {}

#     smiles   = extracted.get("smiles")
#     sequence = extracted.get("protein_sequence")
#     name     = extracted.get("molecule_name", "Unknown")

#     has_smiles   = bool(smiles)
#     has_sequence = bool(sequence)

#     validation["has_smiles"]           = has_smiles
#     validation["has_protein_sequence"] = has_sequence
#     validation["molecule_name"]        = name
#     validation["experiment_intent"]    = extracted.get("experiment_intent", "")

#     # ── Pas de données chimiques extraites ──────────────────────
#     if not has_smiles and not has_sequence:
#         state["error"] = (
#             "Aucune donnée chimique trouvée dans la description. "
#             "Fournissez un SMILES ou une séquence protéique."
#         )
#         state["validation_result"] = validation
#         return state

#     # ── Validation SMILES ───────────────────────────────────────
#     if has_smiles:
#         validation["smiles"] = smiles
#         validation["smiles_length"] = len(smiles)

#         if RDKIT_AVAILABLE:
#             mol = Chem.MolFromSmiles(smiles)
#             if mol is None:
#                 validation["smiles_valid"] = False
#                 validation["smiles_error"] = "SMILES non parseable par RDKit"
#                 # On ne bloque pas : peut-être le LLM a mal extrait
#                 # On continue mais sans les propriétés RDKit
#                 logger.warning(f"[RANKER] SMILES invalide selon RDKit : {smiles}")
#             else:
#                 mw             = Descriptors.MolWt(mol)
#                 logp           = Descriptors.MolLogP(mol)
#                 hbd            = rdMolDescriptors.CalcNumHBD(mol)
#                 hba            = rdMolDescriptors.CalcNumHBA(mol)
#                 rotbond        = rdMolDescriptors.CalcNumRotatableBonds(mol)
#                 tpsa           = Descriptors.TPSA(mol)
#                 num_rings      = rdMolDescriptors.CalcNumRings(mol)
#                 num_atoms      = mol.GetNumHeavyAtoms()
#                 aromatic_rings = rdMolDescriptors.CalcNumAromaticRings(mol)

#                 lipinski_violations = sum([
#                     mw > 500, logp > 5, hbd > 5, hba > 10,
#                 ])
#                 drug_likeness = 1.0 - (lipinski_violations / 4.0)

#                 validation.update({
#                     "smiles_valid":        True,
#                     "mw":                  round(mw, 2),
#                     "logp":                round(logp, 3),
#                     "hbd":                 hbd,
#                     "hba":                 hba,
#                     "rotatable_bonds":     rotbond,
#                     "tpsa":                round(tpsa, 2),
#                     "num_rings":           num_rings,
#                     "aromatic_rings":      aromatic_rings,
#                     "num_heavy_atoms":     num_atoms,
#                     "lipinski_violations": lipinski_violations,
#                     "drug_likeness":       round(drug_likeness, 3),
#                     "is_small_molecule":   num_atoms <= 100 and mw <= 900,
#                     "is_peptide_smiles":   _detect_peptide_smiles(mol),
#                     "complexity_note":     _get_complexity_note(num_atoms, mw),
#                 })
#         else:
#             # Sans RDKit : validation basique
#             valid = len(smiles) > 2 and any(c.isalpha() for c in smiles)
#             validation["smiles_valid"]      = valid
#             validation["is_small_molecule"] = True

#     # ── Validation séquence protéique ──────────────────────────
#     if has_sequence:
#         seq_clean = re.sub(r'\s+', '', sequence.strip().upper())
#         validation["sequence_length"] = len(seq_clean)

#         invalid_chars = set(seq_clean) - VALID_AMINO_ACIDS
#         if invalid_chars:
#             # Séquence probablement mal extraite (SMILES confondu)
#             logger.warning(
#                 f"[RANKER] Séquence suspecte (chars invalides: {invalid_chars}) "
#                 f"— ignorée comme séquence protéique"
#             )
#             validation["sequence_valid"] = False
#             validation["has_protein_sequence"] = False
#             has_sequence = False
#         else:
#             is_short_peptide = len(seq_clean) <= 50
#             validation.update({
#                 "sequence_valid":   True,
#                 "sequence_clean":   seq_clean,
#                 "is_short_peptide": is_short_peptide,
#                 "is_protein":       not is_short_peptide,
#                 "sequence_note":    (
#                     f"Peptide court ({len(seq_clean)} AA)"
#                     if is_short_peptide
#                     else f"Protéine ({len(seq_clean)} AA)"
#                 ),
#             })

#     # ── Dernier check : toujours une donnée valide ──────────────
#     if not validation.get("has_smiles") and not validation.get("has_protein_sequence"):
#         state["error"] = "Données chimiques invalides après validation"

#     state["validation_result"] = validation
#     logger.info(f"[RANKER] Validation — SMILES={has_smiles}, Séquence={has_sequence}")
#     return state


# # ═══════════════════════════════════════════════════════════════
# # NODE 3 — CLASSIFICATION DÉTERMINISTE
# # ═══════════════════════════════════════════════════════════════

# async def deterministic_classify_node(state: RankerState) -> RankerState:
#     """
#     Classification par règles strictes — fiable, sans LLM.
#     CAS 1 : SMILES seul   → RDKit
#     CAS 2 : Séquence seule → ESMFold
#     CAS 3 : SMILES + séq  → DiffDock
#     """
#     if state.get("error"):
#         state["deterministic_case"] = 1
#         return state

#     v = state["validation_result"]
#     has_smiles   = v.get("has_smiles", False) and v.get("smiles_valid", True)
#     has_sequence = v.get("has_protein_sequence", False) and v.get("sequence_valid", True)

#     if has_smiles and has_sequence:
#         case, reason = 3, "SMILES + séquence → docking (DiffDock NIM)"
#     elif has_sequence:
#         case, reason = 2, "Séquence seule → repliement protéique (ESMFold NIM)"
#     else:
#         case, reason = 1, "SMILES seul → conformère 3D (RDKit local)"

#     state["deterministic_case"] = case
#     logger.info(f"[RANKER] Cas déterministe : CAS {case} — {reason}")
#     return state


# # ═══════════════════════════════════════════════════════════════
# # NODE 4 — CONFIRMATION LLM (avec contexte chimique complet)
# # ═══════════════════════════════════════════════════════════════

# async def llm_confirm_node(state: RankerState) -> RankerState:
#     """
#     Le LLM confirme le cas déterministe avec un raisonnement chimique expert.
#     Il peut corriger si détecte une anomalie (peptide en SMILES, etc.).
#     Confiance < 0.80 → on garde le cas déterministe.
#     """
#     if state.get("error"):
#         state["llm_case"] = state.get("deterministic_case", 1)
#         state["llm_reasoning"] = "Erreur en amont — cas déterministe retenu"
#         state["confidence_score"] = 0.0
#         return state

#     v        = state["validation_result"]
#     det_case = state["deterministic_case"]
#     extracted = state.get("extracted_data", {})

#     logger.info(f"[RANKER] Confirmation LLM du CAS {det_case}...")

#     # ── Contexte chimique pour le LLM ──────────────────────────
#     ctx_parts = []

#     if v.get("has_smiles"):
#         ctx_parts.append(
#             f"SMILES : {extracted.get('smiles', 'N/A')}\n"
#             f"  Masse molaire : {v.get('mw', 'N/A')} Da\n"
#             f"  LogP : {v.get('logp', 'N/A')}\n"
#             f"  Atomes lourds : {v.get('num_heavy_atoms', 'N/A')}\n"
#             f"  Drug-likeness (Lipinski) : {v.get('drug_likeness', 'N/A')} "
#             f"({v.get('lipinski_violations', 0)} violation(s))\n"
#             f"  Complexité : {v.get('complexity_note', 'N/A')}\n"
#             f"  Peptide détecté (SMARTS amide) : {v.get('is_peptide_smiles', False)}"
#         )

#     if v.get("has_protein_sequence"):
#         ctx_parts.append(
#             f"Séquence protéique : {v.get('sequence_note', '')}\n"
#             f"  Longueur : {v.get('sequence_length', 'N/A')} AA\n"
#             f"  Type : {'peptide court' if v.get('is_short_peptide') else 'protéine'}"
#         )

#     ctx_parts.append(
#         f"Intention déclarée : {v.get('experiment_intent', extracted.get('experiment_intent', 'N/A'))}"
#     )

#     chem_context = "\n\n".join(ctx_parts)

#     system_prompt = """Tu es un expert en chimie médicinale et bioinformatique structurale.

# Tu travailles avec un pipeline de génération de structures 3D avec 3 modes :

# CAS 1 — Petite molécule (SMILES uniquement)
#   Modèle : RDKit local (CPU, gratuit, < 1s)
#   Sortie : conformère 3D (.mol)
#   Usage : médicaments, fragments, composés organiques MW < 900 Da

# CAS 2 — Protéine (séquence acides aminés uniquement)
#   Modèle : ESMFold via NVIDIA NIM (GPU cloud)
#   Sortie : structure 3D protéique (.pdb)
#   Usage : protéines > 50 AA, étude du repliement

# CAS 3 — Complexe ligand-protéine (SMILES + séquence)
#   Modèle : DiffDock via NVIDIA NIM (GPU cloud)
#   Sortie : complexe de docking (.pdb) avec poses ligand-protéine
#   Usage : étude d'interaction médicament-cible, drug design

# Anomalies à détecter :
# - SMILES avec ≥3 liaisons amide = probablement un peptide → orienter CAS 2 ou 3
# - Séquence très courte (< 10 AA) = peut suffire avec CAS 1 si aussi SMILES
# - Intention "docking" ou "interaction" sans séquence = demander séquence (mais garder CAS 1)

# Réponds UNIQUEMENT en JSON valide (sans markdown) :
# {"case": 1, "confidence": 0.97, "reasoning": "explication courte max 2 phrases", "anomaly": null}"""

#     user_prompt = (
#         f"Cas déterminé par règles : CAS {det_case}\n\n"
#         f"Données chimiques :\n{chem_context}\n\n"
#         f"Nom : {v.get('molecule_name', 'Unknown')}\n\n"
#         f"Confirme ou corrige le cas."
#     )

#     try:
#         llm = _get_local_llm(temperature=0.05)
#         messages = [
#             SystemMessage(content=system_prompt),
#             HumanMessage(content=user_prompt),
#         ]

#         response = await llm.ainvoke(messages)
#         raw = response.content.strip()

#         # Nettoyage markdown + extraction JSON
#         raw = re.sub(r"```json\s*", "", raw)
#         raw = re.sub(r"```\s*", "", raw).strip()
#         json_match = re.search(r'\{.*\}', raw, re.DOTALL)
#         if json_match:
#             raw = json_match.group(0)

#         parsed     = json.loads(raw)
#         llm_case   = int(parsed.get("case", det_case))
#         confidence = float(parsed.get("confidence", 0.8))
#         reasoning  = parsed.get("reasoning", "")
#         anomaly    = parsed.get("anomaly")

#         if llm_case not in (1, 2, 3):
#             logger.warning(f"[RANKER] LLM cas invalide ({llm_case}) → cas déterministe")
#             llm_case = det_case

#         state["llm_case"]         = llm_case
#         state["confidence_score"] = min(1.0, max(0.0, confidence))
#         state["llm_reasoning"]    = reasoning

#         if anomaly:
#             logger.warning(f"[RANKER] Anomalie chimique : {anomaly}")

#         action = "confirme" if llm_case == det_case else f"corrige {det_case} →"
#         logger.info(
#             f"[RANKER] LLM {action} CAS {llm_case} "
#             f"(confiance {confidence:.0%}) — {reasoning}"
#         )

#     except json.JSONDecodeError as e:
#         logger.error(f"[RANKER] JSON invalide LLM : {raw!r} — {e}")
#         state["llm_case"]         = det_case
#         state["confidence_score"] = 0.70
#         state["llm_reasoning"]    = "Fallback déterministe (parse JSON échoué)"

#     except Exception as e:
#         logger.error(f"[RANKER] Erreur LLM confirmation : {e}")
#         state["llm_case"]         = det_case
#         state["confidence_score"] = 0.60
#         state["llm_reasoning"]    = f"Fallback déterministe (erreur API : {e})"

#     return state


# # ═══════════════════════════════════════════════════════════════
# # NODE 5 — ARBITRAGE FINAL + ASSIGNATION MODÈLE
# # ═══════════════════════════════════════════════════════════════

# async def assign_model_node(state: RankerState) -> RankerState:
#     """
#     Arbitrage : LLM adopté si confiance >= 0.80, sinon règle déterministe.
#     Assigne le modèle 3D Printer correspondant.
#     """
#     det_case = state.get("deterministic_case", 1)
#     llm_case = state.get("llm_case", det_case)
#     conf     = state.get("confidence_score", 0.0)

#     if conf >= 0.80:
#         final_case = llm_case
#         source = f"LLM ({conf:.0%})"
#     else:
#         final_case = det_case
#         source = f"Déterministe (confiance LLM insuffisante : {conf:.0%})"

#     state["case_classification"] = final_case
#     state["model_assignment"]    = CASE_TO_MODEL.get(final_case, "rdkit")

#     if conf < LOW_CONFIDENCE_THRESHOLD:
#         logger.warning(
#             f"[RANKER] Confiance faible ({conf:.0%}) — vérification manuelle conseillée"
#         )

#     logger.info(
#         f"[RANKER] FINAL → CAS {final_case} | "
#         f"modèle={state['model_assignment']} | source={source}"
#     )
#     return state


# # ═══════════════════════════════════════════════════════════════
# # HELPERS — CHIMIE
# # ═══════════════════════════════════════════════════════════════

# def _detect_peptide_smiles(mol) -> bool:
#     """Détecte >= 3 liaisons amide → probablement un peptide."""
#     if mol is None or not RDKIT_AVAILABLE:
#         return False
#     pattern = Chem.MolFromSmarts("[NX3][CX3](=[OX1])")
#     return len(mol.GetSubstructMatches(pattern)) >= 3


# def _get_complexity_note(num_atoms: int, mw: float) -> str:
#     if num_atoms <= 20:
#         return "Fragment simple"
#     elif num_atoms <= 50:
#         return "Petite molécule médicament"
#     elif num_atoms <= 100:
#         return "Molécule complexe / naturelle"
#     return "Macromolécule / biopolymère"


# def _regex_fallback_extraction(text: str) -> Dict[str, Any]:
#     """
#     Extraction par regex si le LLM échoue.
#     Cherche les patterns SMILES et séquences AA courants.
#     """
#     extracted: Dict[str, Any] = {
#         "smiles": None,
#         "protein_sequence": None,
#         "molecule_name": "Unknown",
#         "experiment_intent": "unknown",
#         "extraction_confidence": 0.4,
#     }

#     # Cherche après "SMILES:" ou "smiles:"
#     smiles_match = re.search(
#         r'(?:SMILES|smiles)\s*[:\=]\s*([A-Za-z0-9@+\-\[\]()=#\\/%.]+)',
#         text
#     )
#     if smiles_match:
#         extracted["smiles"] = smiles_match.group(1).strip()

#     # Cherche une séquence longue de lettres AA uniquement (>= 10 lettres AA valides)
#     seq_match = re.search(
#         r'\b([ACDEFGHIKLMNPQRSTVWY]{10,})\b',
#         text.upper()
#     )
#     if seq_match:
#         extracted["protein_sequence"] = seq_match.group(1)

#     # Nom : premier mot capitalisé après "protéine", "molécule", "composé"
#     name_match = re.search(
#         r'(?:protéine|molécule|composé|ligand|médicament)\s+([A-Z][a-zA-Z0-9\-]+)',
#         text
#     )
#     if name_match:
#         extracted["molecule_name"] = name_match.group(1)

#     return extracted


# # ═══════════════════════════════════════════════════════════════
# # WORKFLOW LANGGRAPH
# # ═══════════════════════════════════════════════════════════════

# def build_ranker_workflow() -> StateGraph:
#     """
#     Pipeline en 5 nœuds :
#     extract → validate → det_classify → llm_confirm → assign_model
#     """
#     wf = StateGraph(RankerState)

#     wf.add_node("extract",           extract_from_description_node)
#     wf.add_node("validate",          validate_input_node)
#     wf.add_node("det_classify",      deterministic_classify_node)
#     wf.add_node("llm_confirm",       llm_confirm_node)
#     wf.add_node("assign_model",      assign_model_node)

#     wf.add_edge(START,          "extract")
#     wf.add_edge("extract",      "validate")
#     wf.add_edge("validate",     "det_classify")
#     wf.add_edge("det_classify", "llm_confirm")
#     wf.add_edge("llm_confirm",  "assign_model")
#     wf.add_edge("assign_model", END)

#     return wf.compile()


# # ═══════════════════════════════════════════════════════════════
# # PUBLIC API — DEUX POINTS D'ENTRÉE
# # ═══════════════════════════════════════════════════════════════

# async def rank_molecule_from_description(description: str) -> RankerOutput:
#     """
#     Point d'entrée principal : description en langage naturel.

#     Exemple :
#         result = await rank_molecule_from_description(
#             "Je veux visualiser l'aspirine. SMILES: CC(=O)Oc1ccccc1C(=O)O"
#         )

#     Args:
#         description: texte libre décrivant l'expérience souhaitée

#     Returns:
#         RankerOutput avec case (1/2/3), model, confidence, validation
#     """
#     logger.info("[RANKER] Démarrage — description naturelle")

#     graph = build_ranker_workflow()

#     initial_state: RankerState = {
#         "raw_description":     description,
#         "molecule_input":      MoleculeInput(),
#         "use_structured_input": False,
#         "extracted_data":      {},
#         "validation_result":   {},
#         "deterministic_case":  1,
#         "llm_case":            1,
#         "case_classification": 1,
#         "model_assignment":    "rdkit",
#         "confidence_score":    0.0,
#         "llm_reasoning":       "",
#         "error":               None,
#     }

#     final = await graph.ainvoke(initial_state)
#     return _build_output(final)


# async def rank_molecule_from_structured(molecule_input: MoleculeInput) -> RankerOutput:
#     """
#     Point d'entrée alternatif : input structuré (bypass extraction LLM).
#     Utilisé par main.py quand les données sont déjà disponibles.

#     Args:
#         molecule_input: MoleculeInput avec smiles et/ou protein_sequence

#     Returns:
#         RankerOutput avec case (1/2/3), model, confidence, validation
#     """
#     logger.info(f"[RANKER] Démarrage — input structuré : {molecule_input.molecule_name}")

#     graph = build_ranker_workflow()

#     initial_state: RankerState = {
#         "raw_description":      "",
#         "molecule_input":       molecule_input,
#         "use_structured_input": True,
#         "extracted_data":       {},
#         "validation_result":    {},
#         "deterministic_case":   1,
#         "llm_case":             1,
#         "case_classification":  1,
#         "model_assignment":     "rdkit",
#         "confidence_score":     0.0,
#         "llm_reasoning":        "",
#         "error":                None,
#     }

#     final = await graph.ainvoke(initial_state)
#     return _build_output(final)


# def _build_output(final: RankerState) -> RankerOutput:
#     """Construit le RankerOutput depuis l'état final."""
#     output = RankerOutput(
#         case=final["case_classification"],
#         model=final["model_assignment"],
#         confidence=final["confidence_score"],
#         input_validation=final["validation_result"],
#     )

#     if final.get("error"):
#         logger.error(f"[RANKER] Terminé avec erreur : {final['error']}")
#     else:
#         logger.info(
#             f"[RANKER] Terminé — CAS={output.case} | "
#             f"modèle={output.model} | "
#             f"confiance={output.confidence:.0%} | "
#             f"raisonnement={final.get('llm_reasoning', '')}"
#         )

#     return output
# """
# Main script - Test Ranker avec descriptions naturelles
# """

# import sys
# import os
# import asyncio
# import logging

# # ─── FIX ENCODING WINDOWS (sans fermer sys.stderr) ───────────
# if sys.platform == "win32":
#     os.environ["PYTHONIOENCODING"] = "utf-8"
#     # NE PAS envelopper sys.stdout/stderr — cause des problèmes
#     # À la place, utiliser encoding dans FileHandler

# from settings.configuration import (
#     MoleculeInput,
#     LOGGING_CONFIG
# )
# from Agents.ranker_agent import (
#     rank_molecule_from_description,
#     rank_molecule_from_structured
# )
# from Agents.printer_3d_agent import generate_3d_structure
# from visualizer_3d import display_structure

# # ═══════════════════════════════════════════════════════════════
# # LOGGING SETUP (avec encoding UTF-8)
# # ═══════════════════════════════════════════════════════════════

# logging.basicConfig(
#     level=LOGGING_CONFIG["level"],
#     format=LOGGING_CONFIG["format"],
#     handlers=[
#         logging.FileHandler(
#             LOGGING_CONFIG["log_file"],
#             encoding='utf-8'  # Encoding spécifié ici
#         ),
#         logging.StreamHandler(sys.stdout)  # Pas de wrapping
#     ]
# )

# logger = logging.getLogger(__name__)

# # ═══════════════════════════════════════════════════════════════
# # TEST DESCRIPTIONS NATURELLES
# # ═══════════════════════════════════════════════════════════════

# TEST_DESCRIPTIONS = {
#     "case_1": """
# J'ai besoin de visualiser la structure 3D de l'aspirin (acide acetylsalicylique).
# Le SMILES est CC(=O)Oc1ccccc1C(=O)O.
# C'est un petit médicament anti-inflammatoire très courant.
# """,
    
#     "case_2": """
# Je travaille avec la protéine ubiquitine humaine.
# La séquence est : MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT
# Je dois obtenir sa structure 3D pour analyser le repliement protéique.
# """,
    
#     "case_3": """
# Je dois étudier le docking moléculaire de l'aspirin (SMILES: CC(=O)Oc1ccccc1C(=O)O)
# sur la protéine COX-2 humaine.
# Séquence COX-2 : MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT
# Je veux voir comment la molécule s'insère dans le site actif.
# """,
# }

# # ═══════════════════════════════════════════════════════════════
# # UTILITIES
# # ═══════════════════════════════════════════════════════════════

# def print_separator(title: str = ""):
#     """Print formatted separator"""
#     print("\n" + "="*80)
#     if title:
#         print(f" {title}")
#         print("="*80)


# def print_ranker_result(result):
#     """Pretty print ranker result"""
#     print("\n[RESULT] RANKER OUTPUT:")
#     print(f"  Case: {result.case}")
#     print(f"  Model: {result.model}")
#     print(f"  Confidence: {result.confidence:.1%}")
#     print(f"  Validation details:")
#     for key, value in result.input_validation.items():
#         if not key.startswith('_'):
#             # Limiter la longueur des valeurs
#             val_str = str(value)
#             if len(val_str) > 100:
#                 val_str = val_str[:97] + "..."
#             print(f"    - {key}: {val_str}")


# def print_printer_result(result, molecule_name: str = "Unknown"):
#     """Pretty print printer result"""
#     print("\n[RESULT] 3D PRINTER OUTPUT:")
#     print(f"  Case: {result.case}")
#     print(f"  Model: {result.model_used}")
#     print(f"  Format: {result.format}")
#     print(f"  Success: {result.success}")
#     print(f"  Time: {result.generation_time_s:.2f}s")
    
#     if result.error_message:
#         print(f"  ERROR: {result.error_message}")
#     elif result.success and result.structure:
#         print(f"  Structure size: {len(result.structure)} characters")
        
#         # OUVRIR VISUALISEUR
#         print(f"\n  [OPENING 3D VIEWER IN BROWSER...]")
#         try:
#             html_path = display_structure(
#                 result.structure,
#                 result.format,
#                 f"Case {result.case} - {molecule_name}",
#                 result.case,
#                 auto_open=True
#             )
#             print(f"  Viewer saved to: {html_path}\n")
#         except Exception as e:
#             logger.error(f"[ERROR] Could not open viewer: {e}")
#             print(f"  ERROR: Could not open viewer: {e}\n")


# # ═══════════════════════════════════════════════════════════════
# # TEST FUNCTIONS
# # ═══════════════════════════════════════════════════════════════

# async def test_natural_language_full(case_key: str):
#     """Test complet : Ranker + 3D Printer avec description naturelle"""
#     print_separator(f"TEST {case_key.upper()} - RANKER + 3D PRINTER")
    
#     description = TEST_DESCRIPTIONS[case_key]
#     print(f"Description:\n{description}\n")
    
#     # STEP 1: Ranker
#     print("[STEP 1] Running Ranker avec description naturelle...")
#     try:
#         ranker_result = await rank_molecule_from_description(description)
#         print_ranker_result(ranker_result)
#     except Exception as e:
#         logger.error(f"[ERROR] Ranker failed: {e}", exc_info=True)
#         print(f"[ERROR] Ranker failed: {str(e)[:200]}")
#         return None
    
#     # STEP 2: 3D Printer
#     if ranker_result and ranker_result.case:
#         print("\n[STEP 2] Running 3D Printer...")
#         try:
#             # Extraire SMILES et séquence du résultat de validation
#             validation = ranker_result.input_validation
#             smiles = validation.get('smiles') if validation.get('has_smiles') else None
#             protein_seq = validation.get('sequence_clean') if validation.get('has_protein_sequence') else None
#             molecule_name = validation.get('molecule_name', 'Unknown')
            
#             printer_result = await generate_3d_structure(
#                 ranker_output=ranker_result,
#                 smiles=smiles,
#                 protein_sequence=protein_seq,
#                 molecule_name=molecule_name
#             )
#             print_printer_result(printer_result, molecule_name)
            
#         except Exception as e:
#             logger.error(f"[ERROR] 3D Printer failed: {e}", exc_info=True)
#             print(f"[ERROR] 3D Printer failed: {str(e)[:200]}")


# async def test_natural_language_ranker_only(case_key: str):
#     """Test Ranker seul"""
#     print_separator(f"TEST {case_key.upper()} - RANKER ONLY")
    
#     description = TEST_DESCRIPTIONS[case_key]
#     print(f"Description:\n{description}\n")
    
#     print("[STEP 1] Running Ranker...")
#     try:
#         ranker_result = await rank_molecule_from_description(description)
#         print_ranker_result(ranker_result)
#         return ranker_result
#     except Exception as e:
#         logger.error(f"[ERROR] Ranker failed: {e}", exc_info=True)
#         print(f"[ERROR] {str(e)[:200]}")
#         return None


# async def test_structured_input():
#     """Test avec input structuré"""
#     print_separator("TEST STRUCTURED INPUT - RANKER + 3D PRINTER")
    
#     mol = MoleculeInput(
#         smiles="CC(=O)Oc1ccccc1C(=O)O",
#         protein_sequence=None,
#         molecule_name="Aspirin (Structured)"
#     )
    
#     print("[STEP 1] Running Ranker avec input structuré...")
#     try:
#         ranker_result = await rank_molecule_from_structured(mol)
#         print_ranker_result(ranker_result)
        
#         # STEP 2: 3D Printer
#         print("\n[STEP 2] Running 3D Printer...")
#         printer_result = await generate_3d_structure(
#             ranker_output=ranker_result,
#             smiles=mol.smiles,
#             protein_sequence=mol.protein_sequence,
#             molecule_name=mol.molecule_name
#         )
#         print_printer_result(printer_result, mol.molecule_name)
        
#     except Exception as e:
#         logger.error(f"[ERROR] {e}", exc_info=True)
#         print(f"[ERROR] {str(e)[:200]}")


# # ═══════════════════════════════════════════════════════════════
# # MAIN
# # ═══════════════════════════════════════════════════════════════

# async def main():
#     """Main entry point"""
    
#     if len(sys.argv) > 1:
#         test_type = sys.argv[1].lower()
        
#         if test_type == "case1":
#             await test_natural_language_full("case_1")
#         elif test_type == "case2":
#             await test_natural_language_full("case_2")
#         elif test_type == "case3":
#             await test_natural_language_full("case_3")
#         elif test_type == "case1r":
#             await test_natural_language_ranker_only("case_1")
#         elif test_type == "case2r":
#             await test_natural_language_ranker_only("case_2")
#         elif test_type == "case3r":
#             await test_natural_language_ranker_only("case_3")
#         elif test_type == "structured":
#             await test_structured_input()
#         elif test_type == "all":
#             for key in ["case_1", "case_2", "case_3"]:
#                 await test_natural_language_full(key)
#                 await asyncio.sleep(2)
#         else:
#             print("""
# Usage: python main.py [option]

# Options:
#   case1       - Test Case 1 (small molecule) with Ranker + 3D Printer
#   case2       - Test Case 2 (protein) with Ranker + 3D Printer
#   case3       - Test Case 3 (docking) with Ranker + 3D Printer
#   case1r      - Test Case 1 Ranker only
#   case2r      - Test Case 2 Ranker only
#   case3r      - Test Case 3 Ranker only
#   structured  - Test structured input
#   all         - Run all cases
# """)
#     else:
#         # Default: test case 1
#         await test_natural_language_full("case_1")


# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print("\n[INFO] Interrupted by user")
#     except Exception as e:
#         logger.error(f"[FATAL ERROR] {e}", exc_info=True)
#         print(f"[FATAL ERROR] {e}")
# import logging
# import json
# import re
# from typing import TypedDict, Any, Dict, Optional
# from langchain_groq import ChatGroq
# from langchain_core.messages import HumanMessage, SystemMessage
# from langgraph.graph import StateGraph, START, END
# import sys
# import os

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from settings.configuration import LLM_CONFIG, MoleculeInput, RankerOutput

# # ── RDKit import (optionnel mais fortement recommandé) ──────────
# try:
#     from rdkit import Chem
#     from rdkit.Chem import Descriptors, rdMolDescriptors
#     RDKIT_AVAILABLE = True
# except ImportError:
#     RDKIT_AVAILABLE = False
#     logging.warning("RDKit non disponible — validation chimique basique uniquement")

# logger = logging.getLogger(__name__)


# # ═══════════════════════════════════════════════════════════════
# # CONSTANTS
# # ═══════════════════════════════════════════════════════════════

# # Correspondance cas → modèle 3D Printer
# CASE_TO_MODEL = {
#     1: "rdkit",        # Petite molécule SMILES → conformère 3D local
#     2: "esmfold_nim",  # Séquence protéique → structure 3D (NVIDIA NIM)
#     3: "diffdock_nim", # SMILES + protéine  → complexe de docking (NVIDIA NIM)
# }

# # Acides aminés valides (code 1 lettre)
# VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")

# # Seuil de confiance en dessous duquel on log un avertissement
# LOW_CONFIDENCE_THRESHOLD = 0.65


# # ═══════════════════════════════════════════════════════════════
# # STATE
# # ═══════════════════════════════════════════════════════════════

# class RankerState(TypedDict):
#     molecule_input: MoleculeInput
#     validation_result: Dict[str, Any]   # résultats de validation détaillés
#     deterministic_case: int             # cas déterminé par règles (sans LLM)
#     llm_case: int                       # cas confirmé/corrigé par LLM
#     case_classification: int            # cas final retenu
#     model_assignment: str               # modèle 3D assigné
#     confidence_score: float
#     llm_reasoning: str                  # explication du LLM
#     error: Optional[str]


# # ═══════════════════════════════════════════════════════════════
# # NODE 1 — VALIDATION CHIMIQUE
# # ═══════════════════════════════════════════════════════════════

# async def validate_input_node(state: RankerState) -> RankerState:
#     """
#     Validation rigoureuse de l'input avec RDKit si disponible.
#     Produit un rapport détaillé utilisé par les noeuds suivants.
#     """
#     logger.info("[RANKER] Validation de l'input...")
#     mol_input = state["molecule_input"]
#     validation: Dict[str, Any] = {}

#     # ── Présence des inputs ─────────────────────────────────────
#     has_smiles   = bool(mol_input.smiles and mol_input.smiles.strip())
#     has_sequence = bool(mol_input.protein_sequence and mol_input.protein_sequence.strip())
#     validation["has_smiles"]           = has_smiles
#     validation["has_protein_sequence"] = has_sequence
#     validation["molecule_name"]        = mol_input.molecule_name or "Unknown"

#     if not has_smiles and not has_sequence:
#         state["error"] = "Input invalide : SMILES ou séquence protéique requis"
#         state["validation_result"] = validation
#         return state

#     # ── Validation SMILES ───────────────────────────────────────
#     if has_smiles:
#         smiles = mol_input.smiles.strip()
#         validation["smiles_length"] = len(smiles)

#         if RDKIT_AVAILABLE:
#             mol = Chem.MolFromSmiles(smiles)
#             if mol is None:
#                 validation["smiles_valid"] = False
#                 validation["smiles_error"] = "SMILES non parseable par RDKit"
#                 state["error"] = f"SMILES invalide : {smiles}"
#                 state["validation_result"] = validation
#                 return state

#             # Propriétés physico-chimiques (Lipinski, Veber)
#             mw      = Descriptors.MolWt(mol)
#             logp    = Descriptors.MolLogP(mol)
#             hbd     = rdMolDescriptors.CalcNumHBD(mol)
#             hba     = rdMolDescriptors.CalcNumHBA(mol)
#             rotbond = rdMolDescriptors.CalcNumRotatableBonds(mol)
#             tpsa    = Descriptors.TPSA(mol)
#             num_rings = rdMolDescriptors.CalcNumRings(mol)
#             num_atoms = mol.GetNumHeavyAtoms()
#             aromatic_rings = rdMolDescriptors.CalcNumAromaticRings(mol)

#             # Règle de Lipinski (drug-likeness)
#             lipinski_violations = sum([
#                 mw > 500,
#                 logp > 5,
#                 hbd > 5,
#                 hba > 10,
#             ])
#             drug_likeness = 1.0 - (lipinski_violations / 4.0)

#             validation.update({
#                 "smiles_valid":         True,
#                 "mw":                   round(mw, 2),
#                 "logp":                 round(logp, 3),
#                 "hbd":                  hbd,
#                 "hba":                  hba,
#                 "rotatable_bonds":      rotbond,
#                 "tpsa":                 round(tpsa, 2),
#                 "num_rings":            num_rings,
#                 "aromatic_rings":       aromatic_rings,
#                 "num_heavy_atoms":      num_atoms,
#                 "lipinski_violations":  lipinski_violations,
#                 "drug_likeness":        round(drug_likeness, 3),
#                 # Heuristiques de classification chimique
#                 "is_small_molecule":    num_atoms <= 100 and mw <= 900,
#                 "is_peptide_smiles":    _detect_peptide_smiles(mol),
#                 "complexity_note":      _get_complexity_note(num_atoms, mw),
#             })
#         else:
#             # Fallback sans RDKit : vérification basique des caractères
#             valid = len(smiles) > 0 and any(c.isalpha() for c in smiles)
#             validation["smiles_valid"]      = valid
#             validation["is_small_molecule"] = True  # assumption par défaut
#             if not valid:
#                 state["error"] = f"SMILES invalide (check basique) : {smiles}"
#                 state["validation_result"] = validation
#                 return state

#     # ── Validation séquence protéique ──────────────────────────
#     if has_sequence:
#         seq = mol_input.protein_sequence.strip().upper()
#         seq_clean = re.sub(r'\s+', '', seq)
#         validation["sequence_length"] = len(seq_clean)

#         invalid_chars = set(seq_clean) - VALID_AMINO_ACIDS
#         if invalid_chars:
#             validation["sequence_valid"]  = False
#             validation["invalid_chars"]   = list(invalid_chars)
#             state["error"] = f"Séquence invalide : caractères inconnus {invalid_chars}"
#             state["validation_result"] = validation
#             return state

#         # Classification de la séquence
#         is_short_peptide = len(seq_clean) <= 50
#         is_protein       = len(seq_clean) > 50
#         validation.update({
#             "sequence_valid":    True,
#             "sequence_clean":    seq_clean,
#             "is_short_peptide":  is_short_peptide,
#             "is_protein":        is_protein,
#             "sequence_note":     (
#                 f"Peptide court ({len(seq_clean)} AA)"
#                 if is_short_peptide
#                 else f"Protéine ({len(seq_clean)} AA)"
#             ),
#         })

#     state["validation_result"] = validation
#     logger.info(f"[RANKER] Validation OK : {validation}")
#     return state


# # ═══════════════════════════════════════════════════════════════
# # NODE 2 — CLASSIFICATION DÉTERMINISTE (règles)
# # ═══════════════════════════════════════════════════════════════

# async def deterministic_classify_node(state: RankerState) -> RankerState:
#     """
#     Classification par règles strictes — pas de LLM, pas d'ambiguïté.

#     Règles :
#       Cas 1 → SMILES seul        → RDKit (petite molécule, conformère local)
#       Cas 2 → Séquence seule     → ESMFold NIM (repliement protéique)
#       Cas 3 → SMILES + séquence  → DiffDock NIM (docking moléculaire)

#     Le LLM viendra ensuite confirmer ou nuancer ce choix.
#     """
#     if state.get("error"):
#         state["deterministic_case"] = 1  # valeur par défaut
#         return state

#     v = state["validation_result"]
#     has_smiles   = v.get("has_smiles", False)
#     has_sequence = v.get("has_protein_sequence", False)

#     if has_smiles and has_sequence:
#         case = 3
#         reason = "SMILES + séquence protéique → docking moléculaire (DiffDock)"
#     elif has_sequence:
#         case = 2
#         reason = "Séquence protéique seule → prédiction de structure (ESMFold)"
#     else:
#         case = 1
#         reason = "SMILES seul → conformère 3D petite molécule (RDKit)"

#     state["deterministic_case"] = case
#     logger.info(f"[RANKER] Cas déterministe : CAS {case} — {reason}")
#     return state


# # ═══════════════════════════════════════════════════════════════
# # NODE 3 — CONFIRMATION LLM (enrichissement chimique)
# # ═══════════════════════════════════════════════════════════════

# async def llm_classify_node(state: RankerState) -> RankerState:
#     """
#     Le LLM ne décide pas le cas (déjà fait par règles),
#     il CONFIRME et fournit un raisonnement chimique expert.

#     Si le LLM détecte une anomalie (ex: SMILES qui ressemble à un peptide),
#     il peut corriger le cas déterministe.
#     """
#     if state.get("error"):
#         state["llm_case"] = state.get("deterministic_case", 1)
#         state["llm_reasoning"] = "Classification par défaut suite à erreur de validation"
#         state["confidence_score"] = 0.0
#         return state

#     v   = state["validation_result"]
#     mol = state["molecule_input"]
#     det_case = state["deterministic_case"]

#     logger.info(f"[RANKER] Confirmation LLM du cas déterministe : CAS {det_case}...")

#     # ── Construction du contexte chimique ──────────────────────
#     chem_context_parts = []

#     if v.get("has_smiles"):
#         chem_context_parts.append(f"""SMILES: {mol.smiles}
#   - Masse molaire : {v.get('mw', 'N/A')} Da
#   - LogP : {v.get('logp', 'N/A')}
#   - Donneurs H / Accepteurs H : {v.get('hbd', 'N/A')} / {v.get('hba', 'N/A')}
#   - Atomes lourds : {v.get('num_heavy_atoms', 'N/A')}
#   - Cycles / aromatiques : {v.get('num_rings', 'N/A')} / {v.get('aromatic_rings', 'N/A')}
#   - Drug-likeness (Lipinski) : {v.get('drug_likeness', 'N/A')} ({v.get('lipinski_violations', 0)} violation(s))
#   - Complexité : {v.get('complexity_note', 'N/A')}
#   - Peptide détecté via SMILES : {v.get('is_peptide_smiles', False)}""")

#     if v.get("has_protein_sequence"):
#         chem_context_parts.append(f"""Séquence protéique : {v.get('sequence_note', '')}
#   - Longueur : {v.get('sequence_length', 'N/A')} acides aminés
#   - Type : {'peptide court' if v.get('is_short_peptide') else 'protéine complète'}""")

#     chem_context = "\n".join(chem_context_parts)

#     system_prompt = """Tu es un expert en chimie médicinale et bioinformatique structurale.
# Tu travailles avec un pipeline de visualisation 3D moléculaire qui a 3 modes :

# CAS 1 — Petite molécule (SMILES seul)
#   → Modèle : RDKit (local, CPU, gratuit)
#   → Génère : conformère 3D (fichier .mol)
#   → Idéal pour : médicaments, fragments, composés organiques MW < 900 Da

# CAS 2 — Protéine (séquence acides aminés seule)
#   → Modèle : ESMFold via NVIDIA NIM (cloud, GPU)
#   → Génère : structure 3D complète (fichier .pdb)
#   → Idéal pour : protéines > 50 AA, peptides complexes

# CAS 3 — Complexe ligand-protéine (SMILES + séquence)
#   → Modèle : DiffDock via NVIDIA NIM (cloud, GPU)
#   → Génère : complexe de docking 3D (fichier .pdb)
#   → Idéal pour : étudier l'interaction d'un médicament avec sa cible

# Ta tâche :
# 1. Confirmer ou corriger le cas déterminé par les règles
# 2. Signaler toute ambiguïté chimique (ex: SMILES de peptide, séquence très courte)
# 3. Évaluer ta confiance

# Réponds UNIQUEMENT en JSON valide (pas de markdown) :
# {"case": 1, "confidence": 0.97, "reasoning": "explication courte", "anomaly": null}
# "anomaly" peut être null ou une string décrivant un cas limite détecté."""

#     user_prompt = f"""Cas déterminé par règles : CAS {det_case}

# Données moléculaires :
# {chem_context}

# Nom : {v.get('molecule_name', 'Unknown')}

# Confirme ce cas ou corrige-le si tu détectes une anomalie chimique."""

#     try:
#         llm = ChatGroq(
#             model=LLM_CONFIG["model"],
#             api_key=LLM_CONFIG["api_key"],
#             temperature=0.1,           # très faible — classification factuelle
#             max_tokens=400,
#         )

#         messages = [
#             SystemMessage(content=system_prompt),
#             HumanMessage(content=user_prompt),
#         ]

#         response = await llm.ainvoke(messages)
#         raw = response.content.strip()

#         # Nettoyage des balises markdown si présentes
#         raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
#         raw = re.sub(r"```\s*|\s*```", "", raw).strip()

#         parsed = json.loads(raw)

#         llm_case   = int(parsed.get("case", det_case))
#         confidence = float(parsed.get("confidence", 0.8))
#         reasoning  = parsed.get("reasoning", "")
#         anomaly    = parsed.get("anomaly")

#         # Sanity check : le cas LLM doit être 1, 2 ou 3
#         if llm_case not in (1, 2, 3):
#             logger.warning(
#                 f"[RANKER] LLM a retourné un cas invalide ({llm_case}), "
#                 f"on garde le déterministe"
#             )
#             llm_case = det_case

#         state["llm_case"]         = llm_case
#         state["confidence_score"] = min(1.0, max(0.0, confidence))
#         state["llm_reasoning"]    = reasoning

#         if anomaly:
#             logger.warning(f"[RANKER] Anomalie chimique détectée : {anomaly}")

#         if llm_case != det_case:
#             logger.info(
#                 f"[RANKER] LLM corrige le cas : {det_case} → {llm_case} "
#                 f"(raison : {reasoning})"
#             )
#         else:
#             logger.info(
#                 f"[RANKER] LLM confirme CAS {llm_case} "
#                 f"(confiance : {confidence:.0%})"
#             )

#     except json.JSONDecodeError as e:
#         logger.error(f"[RANKER] JSON invalide du LLM : {raw!r} — {e}")
#         state["llm_case"]         = det_case
#         state["confidence_score"] = 0.70
#         state["llm_reasoning"]    = "Fallback déterministe (parse LLM échoué)"

#     except Exception as e:
#         logger.error(f"[RANKER] Erreur LLM : {e}")
#         state["llm_case"]         = det_case
#         state["confidence_score"] = 0.60
#         state["llm_reasoning"]    = f"Fallback déterministe (erreur API : {e})"

#     return state


# # ═══════════════════════════════════════════════════════════════
# # NODE 4 — ARBITRAGE FINAL + ASSIGNATION DU MODÈLE
# # ═══════════════════════════════════════════════════════════════

# async def assign_model_node(state: RankerState) -> RankerState:
#     """
#     Arbitrage entre classification déterministe et LLM.
#     Règle : on fait confiance au LLM seulement si confiance >= 0.80.
#     En dessous, on garde la règle déterministe (plus fiable).
#     """
#     det_case = state.get("deterministic_case", 1)
#     llm_case = state.get("llm_case", det_case)
#     conf     = state.get("confidence_score", 0.0)

#     if conf >= 0.80:
#         final_case = llm_case
#         source = "LLM confirmé"
#     else:
#         final_case = det_case
#         source = f"Déterministe (confiance LLM trop faible : {conf:.0%})"

#     state["case_classification"] = final_case
#     state["model_assignment"]    = CASE_TO_MODEL.get(final_case, "rdkit")

#     if conf < LOW_CONFIDENCE_THRESHOLD:
#         logger.warning(
#             f"[RANKER] Confiance faible ({conf:.0%}) — vérification manuelle recommandée"
#         )

#     logger.info(
#         f"[RANKER] CAS FINAL : {final_case} → modèle={state['model_assignment']} "
#         f"[source={source}]"
#     )
#     return state


# # ═══════════════════════════════════════════════════════════════
# # HELPERS — CHIMIE
# # ═══════════════════════════════════════════════════════════════

# def _detect_peptide_smiles(mol) -> bool:
#     """
#     Détecte si un SMILES représente un peptide/oligopeptide
#     via la présence répétée de liaisons amide N-C(=O).
#     """
#     if mol is None:
#         return False
#     amide_pattern = Chem.MolFromSmarts("[NX3][CX3](=[OX1])")
#     matches = mol.GetSubstructMatches(amide_pattern)
#     # >= 3 liaisons amide → probablement un peptide
#     return len(matches) >= 3


# def _get_complexity_note(num_atoms: int, mw: float) -> str:
#     if num_atoms <= 20:
#         return "Fragment simple (< 20 atomes)"
#     elif num_atoms <= 50:
#         return "Petite molécule médicament"
#     elif num_atoms <= 100:
#         return "Molécule complexe / naturelle"
#     else:
#         return "Macromolécule / biopolymère"


# # ═══════════════════════════════════════════════════════════════
# # WORKFLOW LANGGRAPH
# # ═══════════════════════════════════════════════════════════════

# def build_ranker_workflow() -> StateGraph:
#     """
#     Pipeline LangGraph en 4 noeuds séquentiels :
#     validate → deterministic_classify → llm_classify → assign_model
#     """
#     wf = StateGraph(RankerState)

#     wf.add_node("validate",                validate_input_node)
#     wf.add_node("deterministic_classify",  deterministic_classify_node)
#     wf.add_node("llm_classify",            llm_classify_node)
#     wf.add_node("assign_model",            assign_model_node)

#     wf.add_edge(START,                    "validate")
#     wf.add_edge("validate",               "deterministic_classify")
#     wf.add_edge("deterministic_classify", "llm_classify")
#     wf.add_edge("llm_classify",           "assign_model")
#     wf.add_edge("assign_model",           END)

#     return wf.compile()


# # ═══════════════════════════════════════════════════════════════
# # PUBLIC API
# # ═══════════════════════════════════════════════════════════════

# async def rank_molecule(molecule_input: MoleculeInput) -> RankerOutput:
#     """
#     Point d'entrée principal du Ranker.

#     Args:
#         molecule_input: MoleculeInput (smiles, protein_sequence, molecule_name)

#     Returns:
#         RankerOutput : case (1/2/3), model, confidence, validation détaillée
#     """
#     logger.info(f"[RANKER] Démarrage pour : {molecule_input.molecule_name}")

#     graph = build_ranker_workflow()

#     initial_state: RankerState = {
#         "molecule_input":      molecule_input,
#         "validation_result":   {},
#         "deterministic_case":  1,
#         "llm_case":            1,
#         "case_classification": 1,
#         "model_assignment":    "rdkit",
#         "confidence_score":    0.0,
#         "llm_reasoning":       "",
#         "error":               None,
#     }

#     final = await graph.ainvoke(initial_state)

#     output = RankerOutput(
#         case=final["case_classification"],
#         model=final["model_assignment"],
#         confidence=final["confidence_score"],
#         input_validation=final["validation_result"],
#     )

#     if final.get("error"):
#         logger.error(f"[RANKER] Terminé avec erreur : {final['error']}")
#     else:
#         logger.info(
#             f"[RANKER] Terminé : CAS={output.case} | "
#             f"modèle={output.model} | "
#             f"confiance={output.confidence:.0%} | "
#             f"raisonnement={final['llm_reasoning']}"
#         )

#     return output

# """
# Ranker Agent - Classifies molecular inputs into 3 cases
# Uses LangGraph workflow for state management
# """

# import logging
# from typing import TypedDict, Any, Dict
# from dataclasses import asdict
# import json
# from langchain_groq import ChatGroq
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.messages import HumanMessage
# from langgraph.graph import StateGraph, START, END
# import sys
# import os
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from settings.configuration import LLM_CONFIG, MoleculeInput, RankerOutput, LOGGING_CONFIG

# logger = logging.getLogger(__name__)

# # ═══════════════════════════════════════════════════════════════
# # STATE DEFINITION
# # ═══════════════════════════════════════════════════════════════

# class RankerState(TypedDict):
#     """State for Ranker workflow"""
#     molecule_input: MoleculeInput
#     validation_result: Dict[str, Any]
#     case_classification: int
#     model_assignment: str
#     confidence_score: float
#     error: str


# # ═══════════════════════════════════════════════════════════════
# # NODE FUNCTIONS
# # ═══════════════════════════════════════════════════════════════

# async def validate_input_node(state: RankerState) -> RankerState:
#     """
#     Validate input data structure and content
#     """
#     logger.info("[RANKER] Validating input...")
    
#     molecule = state["molecule_input"]
#     validation = {
#         "smiles_present": bool(molecule.smiles),
#         "protein_sequence_present": bool(molecule.protein_sequence),
#         "smiles_length": len(molecule.smiles) if molecule.smiles else 0,
#         "sequence_length": len(molecule.protein_sequence) if molecule.protein_sequence else 0,
#         "molecule_name": molecule.molecule_name or "Unknown"
#     }
    
#     # Validate at least one input
#     if not validation["smiles_present"] and not validation["protein_sequence_present"]:
#         state["error"] = "ERROR: Input validation failed - requires SMILES or protein sequence"
#         state["validation_result"] = validation
#         return state
    
#     # Validate SMILES format (basic check)
#     if validation["smiles_present"]:
#         if not _is_valid_smiles(molecule.smiles):
#             state["error"] = f"ERROR: Invalid SMILES format: {molecule.smiles}"
#             validation["smiles_valid"] = False
#             state["validation_result"] = validation
#             return state
#         validation["smiles_valid"] = True
    
#     # Validate protein sequence (basic check)
#     if validation["protein_sequence_present"]:
#         if not _is_valid_protein_sequence(molecule.protein_sequence):
#             state["error"] = f"ERROR: Invalid protein sequence"
#             validation["sequence_valid"] = False
#             state["validation_result"] = validation
#             return state
#         validation["sequence_valid"] = True
    
#     state["validation_result"] = validation
#     logger.info(f"[RANKER] Validation passed: {validation}")
#     return state


# async def classify_case_node(state: RankerState) -> RankerState:
#     """
#     Classify input into one of 3 cases based on LLM reasoning
#     """
#     if state.get("error"):
#         logger.warning("[RANKER] Skipping classification due to validation error")
#         return state
    
#     logger.info("[RANKER] Classifying case...")
    
#     molecule = state["molecule_input"]
#     validation = state["validation_result"]
    
#     # Create LLM for classification
#     llm = ChatGroq(
#         model=LLM_CONFIG["model"],
#         api_key=LLM_CONFIG["api_key"],
#         temperature=LLM_CONFIG["temperature"],
#         max_tokens=LLM_CONFIG["max_tokens"]
#     )
    
#     # Build classification message - NO TEMPLATE VARIABLES
#     classification_prompt = f"""Classify the following molecular input into ONE of these cases:

# CASE 1: Small Molecule (SMILES only, NO protein sequence)
# - Input: SMILES string only
# - Model: RDKit (local)
# - Output: 3D conformer structure

# CASE 2: Protein Structure Prediction (Amino acid sequence only, NO SMILES)
# - Input: Amino acid sequence only
# - Model: ESMFold (NVIDIA NIM)
# - Output: 3D protein structure (PDB)

# CASE 3: Molecular Docking (SMILES + Protein sequence)
# - Input: SMILES string AND amino acid sequence
# - Model: DiffDock (NVIDIA NIM)
# - Output: 3D docking complex (PDB)

# INPUT DATA:
# - SMILES present: {validation.get('smiles_present', False)}
# - SMILES: {molecule.smiles or 'None'}
# - Protein sequence present: {validation.get('protein_sequence_present', False)}
# - Sequence length: {validation.get('sequence_length', 0)} amino acids
# - Molecule name: {molecule.molecule_name or 'Unknown'}

# Return ONLY valid JSON (no markdown, no code blocks):
# {{"case": 1, "reasoning": "explanation", "confidence": 0.95}}"""
    
#     try:
#         # Use HumanMessage directly to avoid template parsing issues
#         message = HumanMessage(content=classification_prompt)
#         response = await llm.ainvoke([message])
#         response_text = response.content.strip()
        
#         # Clean response if it has markdown code blocks
#         if "```json" in response_text:
#             response_text = response_text.split("```json")[1].split("```")[0].strip()
#         elif "```" in response_text:
#             response_text = response_text.split("```")[1].split("```")[0].strip()
        
#         # Parse JSON response
#         classification = json.loads(response_text)
        
#         state["case_classification"] = classification.get("case", 1)
#         state["confidence_score"] = min(1.0, max(0.0, classification.get("confidence", 0.8)))
        
#         logger.info(
#             f"[RANKER] Classification: CASE {state['case_classification']} "
#             f"(confidence: {state['confidence_score']:.1%})"
#         )
        
#     except json.JSONDecodeError as e:
#         logger.error(f"[RANKER] Failed to parse LLM response: {response_text}")
#         logger.error(f"[RANKER] JSON Error: {str(e)}")
#         # Default logic: use presence of inputs
#         if validation.get('smiles_present') and validation.get('protein_sequence_present'):
#             state["case_classification"] = 3
#         elif validation.get('protein_sequence_present'):
#             state["case_classification"] = 2
#         else:
#             state["case_classification"] = 1
#         state["confidence_score"] = 0.6
#         logger.info(f"[RANKER] Using fallback logic: CASE {state['case_classification']}")
    
#     except Exception as e:
#         logger.error(f"[RANKER] Unexpected error during classification: {str(e)}")
#         state["error"] = str(e)
#         state["case_classification"] = 1
#         state["confidence_score"] = 0.0
    
#     return state


# async def assign_model_node(state: RankerState) -> RankerState:
#     """
#     Assign appropriate 3D printer model based on classification
#     """
#     if state.get("error"):
#         logger.warning("[RANKER] Using default model assignment due to error")
    
#     logger.info(f"[RANKER] Assigning model for case {state['case_classification']}...")
    
#     case_to_model = {
#         1: "rdkit",
#         2: "esmfold_nim",
#         3: "diffdock_nim"
#     }
    
#     state["model_assignment"] = case_to_model.get(state["case_classification"], "rdkit")
    
#     logger.info(f"[RANKER] Model assigned: {state['model_assignment']}")
#     return state


# # ═══════════════════════════════════════════════════════════════
# # HELPER FUNCTIONS
# # ═══════════════════════════════════════════════════════════════

# def _is_valid_smiles(smiles: str) -> bool:
#     """Basic SMILES validation"""
#     if not smiles or not isinstance(smiles, str):
#         return False
#     allowed_chars = set("CNOPSFClBrIc()[]=#\\/@+-")
#     return any(c in allowed_chars for c in smiles.upper()) and len(smiles) > 0


# def _is_valid_protein_sequence(sequence: str) -> bool:
#     """Basic protein sequence validation"""
#     if not sequence or not isinstance(sequence, str):
#         return False
#     valid_aa = set("ACDEFGHIKLMNPQRSTVWY*")
#     sequence_upper = sequence.upper().strip()
#     return all(c in valid_aa for c in sequence_upper) and len(sequence_upper) > 0


# # ═══════════════════════════════════════════════════════════════
# # WORKFLOW BUILDER
# # ═══════════════════════════════════════════════════════════════

# def build_ranker_workflow() -> StateGraph:
#     """
#     Build LangGraph workflow for Ranker agent
#     """
#     workflow = StateGraph(RankerState)
    
#     # Add nodes
#     workflow.add_node("validate", validate_input_node)
#     workflow.add_node("classify", classify_case_node)
#     workflow.add_node("assign_model", assign_model_node)
    
#     # Add edges
#     workflow.add_edge(START, "validate")
#     workflow.add_edge("validate", "classify")
#     workflow.add_edge("classify", "assign_model")
#     workflow.add_edge("assign_model", END)
    
#     return workflow.compile()


# # ═══════════════════════════════════════════════════════════════
# # PUBLIC API
# # ═══════════════════════════════════════════════════════════════

# async def rank_molecule(molecule_input: MoleculeInput) -> RankerOutput:
#     """
#     Main entry point: rank and classify a molecule
    
#     Args:
#         molecule_input: MoleculeInput with SMILES and/or protein sequence
    
#     Returns:
#         RankerOutput with case classification and model assignment
#     """
#     logger.info(f"[RANKER] Starting workflow for: {molecule_input.molecule_name}")
    
#     # Build and execute workflow
#     ranker_graph = build_ranker_workflow()
    
#     initial_state: RankerState = {
#         "molecule_input": molecule_input,
#         "validation_result": {},
#         "case_classification": 1,
#         "model_assignment": "rdkit",
#         "confidence_score": 0.0,
#         "error": None
#     }
    
#     final_state = await ranker_graph.ainvoke(initial_state)
    
#     # Create output
#     output = RankerOutput(
#         case=final_state["case_classification"],
#         model=final_state["model_assignment"],
#         confidence=final_state["confidence_score"],
#         input_validation=final_state["validation_result"]
#     )
    
#     logger.info(f"[RANKER] Complete: {output}")
#     return output
