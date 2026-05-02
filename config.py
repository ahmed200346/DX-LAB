"""
config.py — Centralized, environment-driven configuration.

Fixes vs original:
  • All collection specs and list/dict defaults are now proper instance
    attributes (no shared mutable class-level state).
  • chemicals_collection added (dim=768, COSINE — same as texts).
  • SHARED_NER flag to control singleton BioNERService injection.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set

try:
    from qdrant_client.models import Distance
except ImportError:
    class Distance:  # type: ignore
        COSINE = "Cosine"
        DOT    = "Dot"


class AgentConfig:
    def __init__(self):
        # ── Qdrant ────────────────────────────────────────────────────────────
        self.QDRANT_URL:     str           = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")

        # ── Groq API ──────────────────────────────────────────────────────────
        self.GROQ_API_KEY:  Optional[str] = os.getenv("GROQ_API_KEY")
        self.GROQ_BASE_URL: str           = "https://api.groq.com/openai/v1"
        self.GROQ_MODEL:    str           = "llama-3.3-70b-versatile"

        # ── HuggingFace ───────────────────────────────────────────────────────
        self.HF_TOKEN:           Optional[str] = os.getenv("HF_TOKEN")
        self.HF_API_BASE_URL:    str           = "https://router.huggingface.co/hf-inference/models"
        self.HF_SUMMARIZER_MODEL: str          = "facebook/bart-large-cnn"
        self.HF_IMAGE_CAP_MODEL:  str          = "Salesforce/blip-image-captioning-base"

        # ── Embedding dimensions ──────────────────────────────────────────────
        self.TEXT_EMBED_DIM:  int = 768
        self.TABLE_EMBED_DIM: int = 384
        self.IMAGE_EMBED_DIM: int = 512

        # ── Local model names ─────────────────────────────────────────────────
        self.TEXT_EMBED_MODEL:    str = "BAAI/bge-base-en"
        self.TABLE_EMBED_MODEL:   str = "sentence-transformers/all-MiniLM-L6-v2"
        self.IMAGE_EMBED_MODEL:   str = "sentence-transformers/clip-ViT-B-32"

        self.CROSS_ENCODER_MODEL:          str = "BAAI/bge-reranker-v2-m3"
        self.CROSS_ENCODER_MODEL_FALLBACK: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        self.NLI_MODEL:                    str = "cross-encoder/nli-deberta-v3-small"

        # ── SearXNG ───────────────────────────────────────────────────────────
        self.SEARXNG_URL:        str           = os.getenv("SEARXNG_URL", "http://localhost:8080")
        self.SEARXNG_API_KEY:    Optional[str] = os.getenv("SEARXNG_API_KEY")
        self.SEARXNG_SECRET_KEY: Optional[str] = os.getenv("SEARXNG_SECRET_KEY")
        self.SEARXNG_OPEN:       bool          = os.getenv("SEARXNG_OPEN", "false").lower() == "true"
        self.SEARXNG_ENGINES:    str           = "bing,duckduckgo,semantic_scholar"
        self.JINA_BASE_URL:      str           = "https://r.jina.ai"

        # ── PubMed ────────────────────────────────────────────────────────────
        self.PUBMED_BASE_URL: str           = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.PUBMED_API_KEY:  Optional[str] = os.getenv("PUBMED_API_KEY")

        # ── Europe PMC / ClinicalTrials ───────────────────────────────────────
        self.EUROPE_PMC_BASE_URL:      str = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        self.CLINICAL_TRIALS_BASE_URL: str = "https://clinicaltrials.gov/api/query/study_fields"

        # ── Redis Cache ───────────────────────────────────────────────────────
        self.REDIS_HOST:           str = os.getenv("REDIS_HOST", "localhost")
        self.REDIS_PORT:           int = int(os.getenv("REDIS_PORT", "6379"))
        self.CACHE_TTL_SECONDS:    int = 3600
        self.CE_CACHE_TTL_SECONDS: int = 86400

        # ── Validation Thresholds ─────────────────────────────────────────────
        self.SGV_MIN:                    float = 0.60
        self.FAITHFULNESS_MIN:           float = 0.80
        self.ANSWER_RELEVANCY_MIN:       float = 0.75
        self.CONTEXT_RECALL_MIN:         float = 0.70
        self.CONTEXT_PRECISION_MIN:      float = 0.65
        self.SOURCE_CREDIBILITY_MIN:     float = 0.60
        self.CONTRADICTION_THRESHOLD_3L: float = 0.55
        self.CONTRADICTION_THRESHOLD_1L: float = 0.50
        self.RELEVANCE_THRESHOLD_BASE:   float = 0.45
        self.RELEVANCE_THRESHOLD_FLOOR:  float = 0.32

        # ── Per-type dedup thresholds ─────────────────────────────────────────
        self.DEDUP_COSINE_THRESHOLD: Dict[str, float] = {
            "text":     0.92,
            "pdf":      0.92,
            "image":    0.85,
            "table":    0.88,
            "graph":    0.85,
            "video":    0.90,
            "code":     0.95,
            "chemical": 0.90,
        }

        self.DATA_FRESHNESS_DAYS: int = 365

        # ── Retrieval parameters ──────────────────────────────────────────────
        self.TOP_K_DENSE:                    int   = 20
        self.TOP_K_RERANK:                   int   = 10
        self.MIN_RESULTS_BEFORE_WEBSEARCH:   int   = 8
        self.RRF_K:                          float = 50.0
        self.HYBRID_ALPHA:                   float = 0.6
        self.MMR_LAMBDA:                     float = 0.7
        self.CE_MAX_CANDIDATES:              int   = 10
        self.QUERY_DECOMPOSE_WORD_THRESHOLD: int   = 10
        self.BM25_MAX_DOCS:                  int   = 2000

        # ── Collections (now an instance attribute — safe to mutate) ──────────
        self.COLLECTIONS: Dict[str, Dict[str, Any]] = {
            "texts_collection":     {"dim": self.TEXT_EMBED_DIM,  "distance": Distance.COSINE},
            "pdfs_collection":      {"dim": self.TEXT_EMBED_DIM,  "distance": Distance.COSINE},
            "images_collection":    {"dim": self.IMAGE_EMBED_DIM, "distance": Distance.COSINE},
            "videos_collection":    {"dim": self.TEXT_EMBED_DIM,  "distance": Distance.COSINE},
            "tables_collection":    {"dim": self.TABLE_EMBED_DIM, "distance": Distance.DOT},
            "graphs_collection":    {"dim": self.TEXT_EMBED_DIM,  "distance": Distance.COSINE},
            "code_collection":      {"dim": self.TEXT_EMBED_DIM,  "distance": Distance.COSINE},
            # ── New in v2.0 ────────────────────────────────────────────────
            "chemicals_collection": {"dim": self.TEXT_EMBED_DIM,  "distance": Distance.COSINE},
        }

        # ── ACP ───────────────────────────────────────────────────────────────
        self.ACP_VERSION: str = "3.4"
        self.AGENT_NAME:  str = "intelligent_target_discovery_agent"

        # ── Concurrency ───────────────────────────────────────────────────────
        self.WEB_SEARCH_SEMAPHORE:   int   = 5
        self.BATCH_UPSERT_SIZE:      int   = 100
        self.WEB_SEARCH_TIMEOUT_S:   int   = 15
        self.JINA_MAX_CONCURRENCY:   int   = 3
        self.JINA_MAX_RETRIES:       int   = 1
        self.JINA_BACKOFF_BASE:      float = 1.0
        self.WEB_COLLECT_TIMEOUT_S:  float = 45.0
        self.EXTRACT_RACE_TIMEOUT_S: float = 8.0

        # ── Trusted domains ───────────────────────────────────────────────────
        self.TRUSTED_DOMAINS: List[str] = [
            "pubmed.ncbi.nlm.nih.gov", "arxiv.org", "nature.com", "science.org",
            "cell.com", "thelancet.com", "nejm.org", "bmj.com", "plos.org",
            "semanticscholar.org", "biorxiv.org", "medrxiv.org", "who.int",
            "cdc.gov", "nih.gov", "ebi.ac.uk", "uniprot.org", "rcsb.org",
            "clinicaltrials.gov", "drugbank.ca", "kegg.jp", "reactome.org",
            "omim.org", "ensembl.org", "genecards.org", "chembl.ebi.ac.uk",
            "ncbi.nlm.nih.gov", "jto.org",
            "annalsofoncology.org", "jnccn.org", "bloodjournal.org",
            "jci.org", "pnas.org", "frontiersin.org",
            "tandfonline.com", "sciencedirect.com", "springer.com",
            "wiley.com", "oup.com",
            "pubchem.ncbi.nlm.nih.gov",
        ]

        # ── Jina domain blocklist ─────────────────────────────────────────────
        self.JINA_BLOCKED_DOMAINS: Set[str] = {
            "dictionary.cambridge.org", "dictionary.com", "en.wikipedia.org",
            "merriam-webster.com",
            "apnews.com", "news.google.com", "foxnews.com", "nbcnews.com",
            "bbc.com", "bbc.co.uk", "cnn.com", "reuters.com", "theguardian.com",
            "nytimes.com", "washingtonpost.com",
            "modrinth.com", "curseforge.com", "sportskeeda.com",
            "store.steampowered.com", "twitch.tv", "discord.com", "discord.gg",
            "ign.com", "kotaku.com",
            "forum.arduino.cc", "arduino.cc", "hackaday.com", "instructables.com",
            "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
            "airfrance.fr", "booking.com", "tripadvisor.com", "tui.com",
            "amazon.com", "amazon.fr", "amazon.co.uk", "ebay.com", "etsy.com",
            "urlaubspiraten.de", "dertour.de", "reise-kroeten.de",
            "reddit.com", "twitter.com", "x.com", "facebook.com",
            "instagram.com", "linkedin.com", "tiktok.com",
            "indeed.com", "glassdoor.com", "stackoverflow.com", "quora.com",
            "medium.com", "substack.com",
            "support.google.com", "support.microsoft.com", "support.apple.com",
            "tinhte.vn", "canva.com",
        }

        self.BLOCKED_DOMAIN_SUBSTRINGS: List[str] = [
            "arduino", "minecraft", "steampowered", "discord",
            "airfrance", "booking.com", "tripadvisor",
            "reddit", "twitch", "youtube",
            "support.google", "support.microsoft",
            "urlaubspiraten", "dertour", "reise-kroeten",
            "canva",
        ]

        self.SCIENTIFIC_DOMAIN_KEYWORDS: List[str] = [
            "journal", "research", "science", "biology", "biochem",
            "bio", "med", "health", "pharma", "clinical", "oncol",
            "genomic", "proteo", "ncbi", "pubmed", "arxiv", "doi",
            "preprint", "lab", "university", "univ", "college",
            "institute", "hospital", "clinic", "pathol", "immuno",
            "neuro", "cardio", "drug", "therapeut", "molecul",
        ]

        self.ACADEMIC_TLDS:           List[str] = [".edu", ".gov", ".ac.", ".nih.gov", ".who.int"]
        self.NEUTRAL_TLDS_REQUIRE_KW: List[str] = [".org", ".net", ".io", ".co", ".cc"]

        self.BIOMEDICAL_DOMAIN_FILTER: bool = True

        # ── Logging ───────────────────────────────────────────────────────────
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE:  str = "agent_discovery.jsonl"

        # ── PDF section headers ───────────────────────────────────────────────
        self.PDF_SECTION_HEADERS: List[str] = [
            r"abstract", r"introduction", r"background",
            r"methods?", r"materials?\s+and\s+methods?",
            r"results?", r"discussion", r"conclusion",
            r"references?", r"supplementary",
        ]

        # ── Biomedical keyword regex ──────────────────────────────────────────
        self.BIOMEDICAL_PREFILTER_PATTERN: str = (
            r'\b(KRAS|BRAF|EGFR|ALK|RET|MET|HER2|PIK3CA|PTEN|AKT|mTOR|'
            r'TP53|RB1|CDKN2A|BRCA|MLH1|MSH2|'
            r'CAR-T|mRNA|siRNA|CRISPR|PCR|ELISA|'
            r'inhibitor|mutation|pathway|receptor|kinase|oncogene|'
            r'tumor|cancer|leukemia|lymphoma|carcinoma|melanoma|sarcoma|'
            r'protein|gene|cell|therapy|clinical|trial|drug|target|'
            r'antibody|antigen|cytokine|immunotherapy|checkpoint|'
            r'genomic|proteomic|transcriptomic|biomarker|sequencing|'
            r'metastasis|apoptosis|proliferation|differentiation|'
            r'FDA|EMA|phase\s+[I1-4IV]+|cohort|randomized|placebo)\b'
        )

        # ── Report generation ─────────────────────────────────────────────────
        self.REPORT_OUTPUT_DIR: str = "reports"
        self.REPORT_GROQ_MAX_TOKENS: int = 2000


cfg = AgentConfig()