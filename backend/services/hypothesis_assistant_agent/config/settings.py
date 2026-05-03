"""
config/settings.py (Ollama local version)
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Ollama local model ────────────────────────────
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

    # ── PubMed ────────────────────────────────────────
    PUBMED_API_KEY: str = os.getenv("PUBMED_API_KEY", "")
    PUBMED_BASE_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    PUBMED_SEARCH_URL: str = f"{PUBMED_BASE_URL}/esearch.fcgi"
    PUBMED_FETCH_URL: str = f"{PUBMED_BASE_URL}/efetch.fcgi"

    # ── Pipeline ──────────────────────────────────────
    MAX_PAPERS: int = int(os.getenv("MAX_PAPERS", "5"))
    MAX_ABSTRACT_LENGTH: int = 1000
    NUM_HYPOTHESES: int = 3
    PARALLEL_ANALYSIS_WORKERS: int = 1

    # ── Retrieval improvements ────────────────────────
    USE_LLM_RE_RANKING: bool = False        
    LLM_RERANK_THRESHOLD: float = 2.0

    # ── Output ────────────────────────────────────────
    OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "..", "output")
    DEBUG_DIR: str = os.path.join(os.path.dirname(__file__), "..", "output", "debug")

    def validate(self) -> None:
        # Local model – nothing to validate
        pass


settings = Settings()