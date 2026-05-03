"""
Configuration centralisée du système multi-agent.
Toutes les variables d'environnement et paramètres globaux sont définis ici.
"""

import os
from pathlib import Path

# ──────────────────────── Chemins du projet ────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / "agents"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
OUTPUT_DIR = PROJECT_ROOT / "output"
METRICS_DIR = PROJECT_ROOT / "metrics"
SERVEURS_DIR = PROJECT_ROOT / "serveurs"
SETTINGS_DIR = PROJECT_ROOT / "settings"

# ──────────────────────── Configuration LLM ────────────────────────
LLM_API_KEY = os.getenv("LLM_API_KEY", "your_api_key")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://tokenfactory.esprit.tn/api")
LLM_MODEL = os.getenv("LLM_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.9"))
LLM_FREQUENCY_PENALTY = float(os.getenv("LLM_FREQUENCY_PENALTY", "0.0"))
LLM_PRESENCE_PENALTY = float(os.getenv("LLM_PRESENCE_PENALTY", "0.0"))
LLM_VERIFY_SSL = os.getenv("LLM_VERIFY_SSL", "false").lower() == "true"

# ──────────────────────── Configuration Serveur ACP ────────────────────────
ACP_SERVER_HOST = os.getenv("ACP_SERVER_HOST", "127.0.0.1")
# Default 8010 avoids collision with ITD FastAPI (port 8000) in DX-LAB-integration.
ACP_SERVER_PORT = int(os.getenv("ACP_SERVER_PORT", "8010"))
ACP_SERVER_URL = os.getenv("ACP_SERVER_URL", f"http://{ACP_SERVER_HOST}:{ACP_SERVER_PORT}")

# ──────────────────────── Timeouts & Limites ────────────────────────
ACP_REQUEST_TIMEOUT = int(os.getenv("ACP_REQUEST_TIMEOUT", "120"))  # secondes
ACP_MAX_RETRIES = int(os.getenv("ACP_MAX_RETRIES", "3"))
EXECUTOR_MAX_STEPS = int(os.getenv("EXECUTOR_MAX_STEPS", "20"))
EXECUTOR_STEP_TIMEOUT = int(os.getenv("EXECUTOR_STEP_TIMEOUT", "900"))  # secondes (discoverer/3D can be slow)

# ──────────────────────── Configuration Logging ────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"

# ──────────────────────── Agents enregistrés par défaut ────────────────────────
DEFAULT_AGENTS = [
    "executor",
    "planner",
    "data_manager",
    "discoverer",
    "printer_3d",
]

# ──────────────────────── Domain services (wrapper agents) ────────────────────────
DATA_MANAGER_URL = os.getenv("DATA_MANAGER_URL", "http://127.0.0.1:8000")
PRINTER_3D_URL = os.getenv("PRINTER_3D_URL", "http://127.0.0.1:5000")
# Path to Advanced-AI-Project (repo root containing run_discovery_agent.py).
# Default: monorepo `backend/services/discovery_agent` (override with DISCOVERY_AGENT_ROOT).
_DISCOVERY_DEFAULT = Path(__file__).resolve().parent.parent.parent / "services" / "discovery_agent"
DISCOVERY_AGENT_ROOT = (os.getenv("DISCOVERY_AGENT_ROOT") or "").strip() or str(_DISCOVERY_DEFAULT)


def ensure_output_dirs():
    """Crée la structure de dossiers output pour chaque agent défini."""
    for agent_name in DEFAULT_AGENTS:
        (OUTPUT_DIR / agent_name / "metrics").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / agent_name / "results").mkdir(parents=True, exist_ok=True)
    # Dossier système global
    (OUTPUT_DIR / "system" / "metrics").mkdir(parents=True, exist_ok=True)


def get_agent_output_dir(agent_name: str) -> Path:
    """Retourne le chemin du dossier output d'un agent donné."""
    agent_dir = OUTPUT_DIR / agent_name
    (agent_dir / "metrics").mkdir(parents=True, exist_ok=True)
    (agent_dir / "results").mkdir(parents=True, exist_ok=True)
    return agent_dir
