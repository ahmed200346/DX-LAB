import os
import sys
import io
import httpx
from typing import Dict, Any
from dataclasses import dataclass
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# FIX WINDOWS UTF-8 ENCODING
# ═══════════════════════════════════════════════════════════════

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ═══════════════════════════════════════════════════════════════
# LOAD .ENV FILE
# ═══════════════════════════════════════════════════════════════

from dotenv import load_dotenv

# Cherche .env à la racine du projet
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"⚠️ WARNING: .env not found at {env_path}")
    print("Using default configuration (hardcoded values)")

# ═══════════════════════════════════════════════════════════════
# LOCAL LLAMA3.1 SERVER CONFIGURATION (University)
# ═══════════════════════════════════════════════════════════════

LOCAL_LLAMA_CONFIG: Dict[str, Any] = {
    "provider": os.getenv("LLAMA_PROVIDER", "local_vllm"),
    "server_url": os.getenv("LLAMA_SERVER_URL", "https://tokenfactory.esprit.tn/api"),
    "model": os.getenv("LLAMA_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct"),
    "api_key": os.getenv("LLAMA_API_KEY", "sk-29b9436d6fbd492bb7ea094141707f91"),
    "verify_ssl": os.getenv("LLAMA_VERIFY_SSL", "False").lower() == "true",
    "temperature": float(os.getenv("LLAMA_TEMPERATURE", "0.1")),
    "max_tokens": int(os.getenv("LLAMA_MAX_TOKENS", "1000")),
    "top_p": 0.9,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "timeout": 60
}

# ═══════════════════════════════════════════════════════════════
# GEMMA 4 CONFIGURATION (Google AI Studio)
# ═══════════════════════════════════════════════════════════════

GEMMA4_CONFIG: Dict[str, Any] = {
    "provider": os.getenv("GEMMA_PROVIDER", "google_ai_studio"),
    "model": os.getenv("GEMMA_MODEL", "gemma-3-27b-it"),
    "api_key": os.getenv("GEMMA_API_KEY", "AIzaSyDTO1ot5NcK7ZDvdJqYRdRorLWtzw8fD5I"),
    "base_url": "https://generativelanguage.googleapis.com/v1beta",
    "temperature": float(os.getenv("GEMMA_TEMPERATURE", "0.2")),
    "max_tokens": int(os.getenv("GEMMA_MAX_TOKENS", "1000")),
    "top_p": float(os.getenv("GEMMA_TOP_P", "0.9")),
    "timeout": 60,
    "verify_ssl": True,
    "rate_limits": {
        "requests_per_minute": 30,
        "tokens_per_minute": 1_000_000,
        "requests_per_day": 1_500
    }
}

# ═══════════════════════════════════════════════════════════════
# NVIDIA NIM CONFIGURATION
# ═══════════════════════════════════════════════════════════════

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "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")

NIM_CONFIG: Dict[str, Any] = {
    "esmfold": {
        "enabled": os.getenv("ESMFOLD_ENABLED", "True").lower() == "true",
        "endpoint": os.getenv("ESMFOLD_ENDPOINT", "https://health.api.nvidia.com/v1/biology/nvidia/esmfold"),
        "api_key": NVIDIA_API_KEY,
        "timeout_s": 90,
        "model_name": "ESMFold v1",
        "description": "Protein structure prediction from amino acid sequence"
    },
    "diffdock": {
        "enabled": os.getenv("DIFFDOCK_ENABLED", "True").lower() == "true",
        "endpoint": os.getenv("DIFFDOCK_ENDPOINT", "https://health.api.nvidia.com/v1/biology/mit/diffdock"),
        "api_key": NVIDIA_API_KEY,
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
        "enabled": os.getenv("USE_RDKIT", "True").lower() == "true",
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
        "enabled": NIM_CONFIG["esmfold"]["enabled"],
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
        "enabled": NIM_CONFIG["diffdock"]["enabled"],
        "params": {
            "num_poses": 5,
            "confidence_threshold": 0.5,
            "include_water": False
        }
    }
}

# ═══════════════════════════════════════════════════════════════
# CLASSIFICATION CONFIGURATION
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
# RANKER CONFIGURATION
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
    "max_retries": 3,
    "retry_strategy": "escalate_to_llm"
}

# ═══════════════════════════════════════════════════════════════
# ACTIVE LLM SELECTION
# ═══════════════════════════════════════════════════════════════

USE_LLAMA = os.getenv("USE_LLAMA", "False").lower() == "true"
USE_GEMMA = os.getenv("USE_GEMMA", "True").lower() == "true"

if USE_GEMMA:
    LLM_CONFIG = GEMMA4_CONFIG
    LLM_PROVIDER = "google_ai_studio"
elif USE_LLAMA:
    LLM_CONFIG = LOCAL_LLAMA_CONFIG
    LLM_PROVIDER = "local_vllm"
else:
    # Default to Gemma
    LLM_CONFIG = GEMMA4_CONFIG
    LLM_PROVIDER = "google_ai_studio"

# ═══════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════

LOGGING_CONFIG: Dict[str, Any] = {
    "level": os.getenv("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": "virtual_drug_lab.log"
}

# ═══════════════════════════════════════════════════════════════
# RUNTIME CONFIGURATION
# ═══════════════════════════════════════════════════════════════

RUNTIME_CONFIG: Dict[str, Any] = {
    "max_parallel_jobs": 4,
    "workflow_timeout_s": int(os.getenv("PIPELINE_TIMEOUT_S", "300")),
    "cache_enabled": True,
    "cache_ttl_s": 3600,
    "verbose": os.getenv("VERBOSE", "True").lower() == "true"
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
        return bool(self.smiles or self.protein_sequence)


@dataclass
class RankerOutput:
    """Output from ranker agent"""
    case: int
    model: str
    confidence: float
    input_validation: dict
    llm_reasoning: str = ""
    alternative_cases: list = None


@dataclass
class Printer3DOutput:
    """Output from 3D printer agent"""
    structure: str
    format: str
    case: int
    model_used: str
    generation_time_s: float
    success: bool
    error_message: str = None

# ═══════════════════════════════════════════════════════════════
# LAZY-LOAD LLM CLIENT
# ═══════════════════════════════════════════════════════════════

_llm_client = None

def get_llm_client():
    """Initialise le client LLM (Gemma 4 par défaut)"""
    global _llm_client
    
    if _llm_client is None:
        if LLM_PROVIDER == "google_ai_studio":
            try:
                from google import generativeai as genai
                genai.configure(api_key=GEMMA4_CONFIG["api_key"])
                _llm_client = genai.GenerativeModel(
                    model_name=GEMMA4_CONFIG["model"],
                    generation_config=genai.GenerationConfig(
                        temperature=GEMMA4_CONFIG["temperature"],
                        top_p=GEMMA4_CONFIG["top_p"],
                        max_output_tokens=GEMMA4_CONFIG["max_tokens"],
                    )
                )
                print(f"✅ LLM: Gemma 4 initialized via Google AI Studio")
            except ImportError:
                print("❌ ERROR: google-generativeai not installed. Run: pip install google-generativeai")
                raise
    
    return _llm_client


def call_llm(prompt: str) -> str:
    """Appel unifié au LLM"""
    client = get_llm_client()
    try:
        response = client.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        raise