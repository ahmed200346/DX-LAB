"""
Configuration Module V2 - Virtual Drug Discovery Lab
Enhanced LLM-based Classification with Intelligent Decision Making
Local Llama3.1-70B-Instruct server + NVIDIA NIM endpoints
"""

import os
import sys
import io
import httpx
from typing import Dict, Any
from dataclasses import dataclass

# ═══════════════════════════════════════════════════════════════
# FIX WINDOWS UTF-8 ENCODING
# ═══════════════════════════════════════════════════════════════

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ═══════════════════════════════════════════════════════════════
# LOCAL LLAMA3.1 SERVER CONFIGURATION (University)
# ═══════════════════════════════════════════════════════════════

LOCAL_LLAMA_CONFIG: Dict[str, Any] = {
    "provider": "local_vllm",
    "server_url": "https://tokenfactory.esprit.tn/api",
    "model": "hosted_vllm/Llama-3.1-70B-Instruct",
    "api_key": "sk-29b9436d6fbd492bb7ea094141707f91",
    "verify_ssl": False,
    "temperature": 0.1,
    "max_tokens": 1000,
    "top_p": 0.9,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "timeout": 60
}

# ═══════════════════════════════════════════════════════════════
# NVIDIA NIM CONFIGURATION
# ═══════════════════════════════════════════════════════════════

NIM_CONFIG: Dict[str, Any] = {
    "esmfold": {
        "enabled": True,
        "endpoint": "https://health.api.nvidia.com/v1/biology/nvidia/esmfold",
        "api_key": "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",
        "timeout_s": 90,
        "model_name": "ESMFold v1",
        "description": "Protein structure prediction from amino acid sequence"
    },
    "diffdock": {
        "enabled": True,
        "endpoint": "https://health.api.nvidia.com/v1/biology/mit/diffdock",
        "api_key": "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",
        "timeout_s": 180,
        "model_name": "DiffDock v1",
        "description": "Molecular docking: ligand-protein complex prediction"
    }
}

# ═══════════════════════════════════════════════════════════════
# 3D PRINTER MODELS CONFIGURATION
# ═══════════════════════════════════════════════════════════════

PRINTER_3D_CONFIG: Dict[str, Any] = {
    "case_1": {
        "name": "RDKit Small Molecule",
        "model": "rdkit",
        "description": "Local 3D conformer generation for small molecules",
        "input_type": "SMILES",
        "output_format": "mol_block",
        "enabled": True,
        "params": {
            "num_conformers": 10,
            "use_random_coords": False,
            "randomSeed": 42,
            "ff_method": "UFF"
        }
    },
    "case_2": {
        "name": "ESMFold Protein Structure",
        "model": "esmfold_nim",
        "description": "NVIDIA NIM ESMFold for protein structure prediction",
        "input_type": "amino_acid_sequence",
        "output_format": "pdb",
        "enabled": True,
        "params": {
            "use_pae": True,
            "use_plddt": True,
            "pae_threshold": 5.0
        }
    },
    "case_3": {
        "name": "DiffDock Molecular Complex",
        "model": "diffdock_nim",
        "description": "NVIDIA NIM DiffDock for ligand-protein docking",
        "input_type": "smiles_protein_sequence",
        "output_format": "pdb",
        "enabled": True,
        "params": {
            "num_poses": 5,
            "confidence_threshold": 0.5,
            "include_water": False
        }
    }
}

# ═══════════════════════════════════════════════════════════════
# ENHANCED CLASSIFICATION CONFIGURATION - V2
# ═══════════════════════════════════════════════════════════════

CLASSIFICATION_CONFIG: Dict[str, Any] = {
    "system_prompt": """Tu es un expert en chimie médicinale et bioinformatique structurale avec 20 ans d'expérience.

Tu dois classifier les requêtes utilisateur en 3 cas d'expérience:

CASE 1 — PETITE MOLÉCULE (RDKit)
  • Input: SMILES uniquement
  • Pas de séquence protéique
  • MW typiquement < 900 Da
  • Exemple: aspirin (CC(=O)Oc1ccccc1C(=O)O)
  • Sortie: conformère 3D local (MOL format)
  • Temps: < 1 seconde
  • Usage: visualisation molécule, drug screening, fragment analysis

CASE 2 — PROTÉINE (ESMFold NIM)
  • Input: séquence d'acides aminés uniquement
  • Pas de SMILES ligand
  • Longueur: 20-500 AA typiquement
  • Exemple: "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTG..."
  • Sortie: structure 3D protéine (PDB format)
  • Temps: 30-90 secondes
  • Usage: étude repliement, validation structure, prédiction 3D

CASE 3 — COMPLEXE LIGAND-PROTÉINE (DiffDock NIM)
  • Input: SMILES + séquence protéique
  • Ligand: molécule spécifique (SMILES)
  • Protéine: cible (séquence AA)
  • Exemple: aspirin (SMILES) docking sur COX-2 (séquence)
  • Sortie: complexe ligand-protéine (PDB format)
  • Temps: 60-180 secondes
  • Usage: drug design, molecular docking, binding prediction

RÈGLES DE CLASSIFICATION:

1. SI uniquement SMILES valide + PAS de séquence protéique → CASE 1
2. SI uniquement séquence protéique valide + PAS de SMILES → CASE 2
3. SI SMILES valide + séquence protéique valide → CASE 3
4. SI données ambiguës → demander clarification dans le raisonnement
5. SI données invalides → CASE 1 par d��faut (safest fallback)

DÉTAILS TECHNIQUES:

SMILES:
• Format chimique comprimé pour molécules
• Contient: C, N, O, S, P, F, Cl, Br, I, etc.
• Caractères spéciaux: =, #, (, ), [, ], @, +, -, /, \\
• Exemple valide: "CC(=O)Oc1ccccc1C(=O)O" (aspirin)
• Exemple invalide: "MNIFEMLRIDEGLLRKIY" (séquence protéique, pas SMILES!)

SÉQUENCE PROTÉIQUE:
• Acides aminés 1-lettre: A C D E F G H I K L M N P Q R S T V W Y
• Longueur: typiquement 20-5000 caractères
• Exemple: "MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT"
• ATTENTION: peptides courts (5-15 AA) = ambigus, traiter comme CASE 2

INTENTION DÉCLARÉE:
• "visualize" → probablement molécule (CASE 1)
• "structure prediction" → probablement protéine (CASE 2)
• "docking" / "interaction" / "binding" → probablement complexe (CASE 3)
• "3D structure" → pourrait être 1, 2 ou 3 → regarder les données

Réponds UNIQUEMENT en JSON valide (sans markdown, sans explication supplémentaire):
{
  "case": 1 ou 2 ou 3,
  "confidence": 0.0 à 1.0,
  "reasoning": "explication courte (max 100 caractères)",
  "data_validation": {
    "smiles_present": true/false,
    "smiles_valid": true/false,
    "protein_sequence_present": true/false,
    "protein_sequence_valid": true/false,
    "sequence_length": nombre ou null
  },
  "alternative_cases": [cas alternatif 1, cas alternatif 2],
  "warnings": ["avertissement si données ambiguës ou suspectes"]
}""",

    "extraction_prompt_template": """Extrais les informations chimiques de cette description:

DESCRIPTION:
---
{description}
---

Instructions strictes:
1. SMILES: cherche une chaîne contenant C, N, O, etc. et caractères chimiques
2. SÉQUENCE: cherche une chaîne uniquement de lettres A-Z (acides aminés)
3. NOM: le nom de la molécule/protéine mentionné
4. INTENTION: ce que l'utilisateur veut faire

Réponds en JSON UNIQUEMENT:
{{
  "smiles": "string or null",
  "protein_sequence": "string or null",
  "molecule_name": "string",
  "experiment_intent": "string",
  "extraction_confidence": 0.0-1.0
}}""",

    "ambiguity_detection_prompt_template": """Analyse ces données extraites pour détecter les ambiguités:

DONNÉES EXTRAITES:
- SMILES: {smiles}
- Séquence: {sequence}
- Nom: {name}
- Intention: {intent}

QUESTIONS À RÉPONDRE (JSON):
1. Le SMILES pourrait-il être une séquence protéique? (peptide au lieu de SMILES)
2. La séquence pourrait-elle être partielle ou corrompue?
3. Y a-t-il une intention claire de l'utilisateur?
4. Quel est le cas LE PLUS PROBABLE?

Réponds en JSON:
{{
  "is_ambiguous": true/false,
  "ambiguity_type": "null" ou "peptide_vs_smiles" ou "incomplete_sequence" ou "unclear_intent",
  "most_likely_case": 1 ou 2 ou 3,
  "confidence": 0.0-1.0,
  "clarification_needed": "question à poser à l'utilisateur si ambigu"
}}""",

    "confidence_thresholds": {
        "excellent": 0.90,  # Case confidence >= 0.90 → EXCELLENT
        "good": 0.75,       # 0.75-0.90 → GOOD
        "fair": 0.60,       # 0.60-0.75 → FAIR
        "poor": 0.0         # < 0.60 → POOR, utiliser fallback
    },

    "fallback_case": 1,  # Si ambiguité, fallback sur CASE 1 (safest)
}

# ═══════════════════════════════════════════════════════════════
# RANKER CONFIGURATION (Updated V2)
# ═══════════════════════════════════════════════════════════════

RANKER_CONFIG: Dict[str, Any] = {
    "pipeline_version": "v2_intelligent_llm",
    "nodes": [
        "extract_from_description",
        "validate_input",
        "detect_ambiguity",
        "llm_intelligent_classify",
        "compute_confidence",
        "final_decision"
    ],
    "confidence_weights": {
        "extraction": 0.25,
        "validation": 0.25,
        "llm_classification": 0.30,
        "data_completeness": 0.20
    },
    "max_retries": 3,
    "retry_strategy": "escalate_to_llm"
}

# ═══════════════════════════════════════════════════════════════
# LLM CONFIGURATION
# ═══════════════════════════════════════════════════════════════

LLM_CONFIG: Dict[str, Any] = LOCAL_LLAMA_CONFIG

# ═══════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════

LOGGING_CONFIG: Dict[str, Any] = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": "virtual_drug_lab.log"
}

# ═══════════════════════════════════════════════════════════════
# RUNTIME CONFIGURATION
# ═══════════════════════════════════════════════════════════════

RUNTIME_CONFIG: Dict[str, Any] = {
    "max_parallel_jobs": 4,
    "workflow_timeout_s": 300,
    "cache_enabled": True,
    "cache_ttl_s": 3600,
    "verbose": True
}

# ═══════════════════════════════════════════════════════════════
# DATACLASSES FOR TYPE SAFETY
# ═══════════════════════════════════════════════════════════════

@dataclass
class MoleculeInput:
    """Input specification for molecule"""
    smiles: str = None
    protein_sequence: str = None
    molecule_name: str = None
    
    def validate(self) -> bool:
        """Validate input has required fields"""
        return bool(self.smiles or self.protein_sequence)


@dataclass
class RankerOutput:
    """Output from ranker agent"""
    case: int  # 1, 2, or 3
    model: str
    confidence: float
    input_validation: dict
    llm_reasoning: str = ""
    alternative_cases: list = None


@dataclass
class Printer3DOutput:
    """Output from 3D printer agent"""
    structure: str  # PDB/MOL block content
    format: str
    case: int
    model_used: str
    generation_time_s: float
    success: bool
    error_message: str = None


# ═══════════════════════════════════════════════════════════════
# LLM CLIENT INITIALIZATION (Lazy loading)
# ═══════════════════════════════════════════════════════════════

_llm_client = None


def get_llm_client():
    """
    Get or initialize the LLM client for local Llama3.1
    Uses OpenAI-compatible API for vLLM server
    """
    global _llm_client
    
    if _llm_client is None:
        try:
            from openai import OpenAI
            
            http_client = httpx.Client(
                verify=LOCAL_LLAMA_CONFIG["verify_ssl"]
            )
            
            _llm_client = OpenAI(
                api_key=LOCAL_LLAMA_CONFIG["api_key"],
                base_url=LOCAL_LLAMA_CONFIG["server_url"],
                http_client=http_client
            )
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[LLM] Initialized Llama3.1 client: "
                f"{LOCAL_LLAMA_CONFIG['server_url']}"
            )
        
        except ImportError:
            import logging
            logger = logging.getLogger(__name__)
            logger.error("[LLM] OpenAI client not installed. Install with: pip install openai")
            raise
    
    return _llm_client
# """
# Configuration module for Virtual Drug Discovery Lab
# Local Llama3.1-70B-Instruct server + NVIDIA NIM endpoints
# """

# import os
# import sys
# import io
# import httpx
# from typing import Dict, Any
# from dataclasses import dataclass

# # ═══════════════════════════════════════════════════════════════
# # FIX WINDOWS UTF-8 ENCODING
# # ═══════════════════════════════════════════════════════════════

# if sys.platform == "win32":
#     os.environ["PYTHONIOENCODING"] = "utf-8"
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
#     sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# # ═══════════════════════════════════════════════════════════════
# # LOCAL LLAMA3.1 SERVER CONFIGURATION (University)
# # ═══════════════════════════════════════════════════════════════

# LOCAL_LLAMA_CONFIG: Dict[str, Any] = {
#     "provider": "local_vllm",
#     "server_url": "https://tokenfactory.esprit.tn/api",
#     "model": "hosted_vllm/Llama-3.1-70B-Instruct",
#     "api_key":"sk-29b9436d6fbd492bb7ea094141707f91",
#     "verify_ssl": False,  # Disable SSL verification for self-signed certificates
#     "temperature": 0.1,  # Low for classification tasks
#     "max_tokens": 500,
#     "top_p": 0.9,
#     "frequency_penalty": 0.0,
#     "presence_penalty": 0.0,
#     "timeout": 60
# }

# # ═══════════════════════════════════════════════════════════════
# # NVIDIA NIM CONFIGURATION
# # ═══════════════════════════════════════════════════════════════

# NIM_CONFIG: Dict[str, Any] = {
#     "esmfold": {
#         "enabled": True,
#         "endpoint": "https://health.api.nvidia.com/v1/biology/nvidia/esmfold",
#         "api_key": "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",
#         "timeout_s": 90,
#         "model_name": "ESMFold v1",
#         "description": "Protein structure prediction from amino acid sequence"
#     },
#     "diffdock": {
#         "enabled": True,
#         "endpoint": "https://health.api.nvidia.com/v1/biology/mit/diffdock",
#         "api_key": os.getenv("NVIDIA_API_KEY", "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"),
#         "timeout_s": 180,
#         "model_name": "DiffDock v1",
#         "description": "Molecular docking: ligand-protein complex prediction"
#     }
# }

# # ═══════════════════════════════════════════════════════════════
# # 3D PRINTER MODELS CONFIGURATION
# # ═══════════════════════════════════════════════════════════════

# PRINTER_3D_CONFIG: Dict[str, Any] = {
#     "case_1": {
#         "name": "RDKit Small Molecule",
#         "model": "rdkit",
#         "description": "Local 3D conformer generation for small molecules",
#         "input_type": "SMILES",
#         "output_format": "mol_block",
#         "enabled": True,
#         "params": {
#             "num_conformers": 10,
#             "use_random_coords": False,
#             "randomSeed": 42,
#             "ff_method": "UFF"  # Universal Force Field
#         }
#     },
#     "case_2": {
#         "name": "ESMFold Protein Structure",
#         "model": "esmfold_nim",
#         "description": "NVIDIA NIM ESMFold for protein structure prediction",
#         "input_type": "amino_acid_sequence",
#         "output_format": "pdb",
#         "enabled": True,
#         "params": {
#             "use_pae": True,
#             "use_plddt": True,
#             "pae_threshold": 5.0
#         }
#     },
#     "case_3": {
#         "name": "DiffDock Molecular Complex",
#         "model": "diffdock_nim",
#         "description": "NVIDIA NIM DiffDock for ligand-protein docking",
#         "input_type": "smiles_protein_sequence",
#         "output_format": "pdb",
#         "enabled": True,
#         "params": {
#             "num_poses": 5,
#             "confidence_threshold": 0.5,
#             "include_water": False
#         }
#     }
# }

# # ═══════════════════════════════════════════════════════════════
# # RANKER CONFIGURATION
# # ═══════════════════════════════════════════════════════════════

# RANKER_CONFIG: Dict[str, Any] = {
#     "case_1_threshold": {
#         "name": "Small Molecule Detection",
#         "description": "SMILES only, no protein sequence",
#         "conditions": ["smiles_present", "no_protein_sequence"],
#         "model": "rdkit"
#     },
#     "case_2_threshold": {
#         "name": "Protein Structure Prediction",
#         "description": "Amino acid sequence only, no ligand",
#         "conditions": ["protein_sequence_present", "no_smiles"],
#         "model": "esmfold_nim"
#     },
#     "case_3_threshold": {
#         "name": "Molecular Docking Complex",
#         "description": "Both SMILES and protein sequence for docking",
#         "conditions": ["smiles_present", "protein_sequence_present"],
#         "model": "diffdock_nim"
#     }
# }

# # ═══════════════════════════════════════════════════════════════
# # LLM CONFIGURATION (Local Llama3.1 instead of Groq)
# # ═══════════════════════════════════════════════════════���═══════

# LLM_CONFIG: Dict[str, Any] = LOCAL_LLAMA_CONFIG

# # ═══════════════════════════════════════════════════════════════
# # LOGGING CONFIGURATION
# # ═══════════════════════════════════════════════════════════════

# LOGGING_CONFIG: Dict[str, Any] = {
#     "level": "INFO",
#     "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#     "log_file": "virtual_drug_lab.log"
# }

# # ═══════════════════════════════════════════════════════════════
# # RUNTIME CONFIGURATION
# # ═══════════════════════════════════════════════════════════════

# RUNTIME_CONFIG: Dict[str, Any] = {
#     "max_parallel_jobs": 4,
#     "workflow_timeout_s": 300,
#     "cache_enabled": True,
#     "cache_ttl_s": 3600,
#     "verbose": True
# }

# # ═══════════════════════════════════════════════════════════════
# # DATACLASSES FOR TYPE SAFETY
# # ═══════════════════════════════════════════════════════════════

# @dataclass
# class MoleculeInput:
#     """Input specification for molecule"""
#     smiles: str = None
#     protein_sequence: str = None
#     molecule_name: str = None
    
#     def validate(self) -> bool:
#         """Validate input has required fields"""
#         return bool(self.smiles or self.protein_sequence)


# @dataclass
# class RankerOutput:
#     """Output from ranker agent"""
#     case: int  # 1, 2, or 3
#     model: str
#     confidence: float
#     input_validation: dict


# @dataclass
# class Printer3DOutput:
#     """Output from 3D printer agent"""
#     structure: str  # PDB/MOL block content
#     format: str
#     case: int
#     model_used: str
#     generation_time_s: float
#     success: bool
#     error_message: str = None


# # ═══════════════════════════════════════════════════════════════
# # LLM CLIENT INITIALIZATION (Lazy loading)
# # ═══════════════════════════════════════════════════════════════

# _llm_client = None


# def get_llm_client():
#     """
#     Get or initialize the LLM client for local Llama3.1
#     Uses OpenAI-compatible API for vLLM server
#     """
#     global _llm_client
    
#     if _llm_client is None:
#         try:
#             from openai import OpenAI
            
#             http_client = httpx.Client(
#                 verify=LOCAL_LLAMA_CONFIG["verify_ssl"]
#             )
            
#             _llm_client = OpenAI(
#                 api_key=LOCAL_LLAMA_CONFIG["api_key"],
#                 base_url=LOCAL_LLAMA_CONFIG["server_url"],
#                 http_client=http_client
#             )
            
#             import logging
#             logger = logging.getLogger(__name__)
#             logger.info(
#                 f"[LLM] Initialized Llama3.1 client: "
#                 f"{LOCAL_LLAMA_CONFIG['server_url']}"
#             )
        
#         except ImportError:
#             import logging
#             logger = logging.getLogger(__name__)
#             logger.error("[LLM] OpenAI client not installed. Install with: pip install openai")
#             raise
    
#     return _llm_client
