"""
Ranker Agent V2 — Virtual Drug Discovery Lab
Intelligent LLM-based Classification Pipeline
Uses Llama-3.1-70B for smart case decision making
"""

import logging
import json
import re
from urllib import response
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
    GEMMA4_CONFIG
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

# def _get_local_llm(temperature: float = 0.1) -> ChatOpenAI:
#     """Create LLM client"""
#     http_client = httpx.Client(verify=LOCAL_LLAMA_CONFIG["verify_ssl"])
#     return ChatOpenAI(
#         model=LOCAL_LLAMA_CONFIG["model"],
#         api_key=LOCAL_LLAMA_CONFIG["api_key"],
#         base_url=LOCAL_LLAMA_CONFIG["server_url"],
#         temperature=temperature,
#         max_tokens=LOCAL_LLAMA_CONFIG["max_tokens"],
#         http_client=http_client,
#         timeout=LOCAL_LLAMA_CONFIG["timeout"],
#     )

# # REMPLACER PAR :
from google import generativeai as genai

_gemma_client = None

def _get_gemma_client():
    global _gemma_client
    if _gemma_client is None:
        genai.configure(api_key=GEMMA4_CONFIG["api_key"])
        _gemma_client = genai.GenerativeModel(
            model_name=GEMMA4_CONFIG["model"],
            generation_config=genai.GenerationConfig(
                temperature=GEMMA4_CONFIG["temperature"],
                top_p=GEMMA4_CONFIG["top_p"],
                max_output_tokens=GEMMA4_CONFIG["max_tokens"],
            )
        )
    return _gemma_client

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
        # llm = _get_local_llm(temperature=0.05)
        # messages = [
        #     SystemMessage(content="Tu es un expert chimiste. Extrais SMILES et séquences de protéines."),
        #     HumanMessage(content=extraction_prompt),
        # ]
        
        # response = await llm.ainvoke(messages)
        # raw = response.content.strip()
        client = _get_gemma_client()
        full_prompt = (
            "Tu es un expert chimiste. Extrais SMILES et séquences de protéines.\n\n"
            + extraction_prompt
        )
        response = await asyncio.to_thread(client.generate_content, full_prompt)
        raw = response.text.strip()
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
        # llm = _get_local_llm(temperature=0.1)
        # messages = [
        #     SystemMessage(content=CLASSIFICATION_CONFIG["system_prompt"]),
        #     HumanMessage(content=context),
        # ]
        
        # response = await llm.ainvoke(messages)
        # raw = response.content.strip()
        client = _get_gemma_client()
        full_prompt = CLASSIFICATION_CONFIG["system_prompt"] + "\n\n" + context
        response = await asyncio.to_thread(client.generate_content, full_prompt)
        raw = response.text.strip()
        
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
