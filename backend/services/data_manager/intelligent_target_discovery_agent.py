# ─── intelligent_target_discovery_agent.py ────────────────────────────────────
"""
Intelligent Target Discovery Agent v3.4
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import aiohttp
import numpy as np
import redis.asyncio as aioredis
from loguru import logger
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, field_validator
from scipy.special import softmax as scipy_softmax
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from target_extractor import DrugTarget, TargetExtractor

# ─── Optional: trafilatura ────────────────────────────────────────────────────
try:
    import trafilatura
    _TRAFILATURA_AVAILABLE = True
except ImportError:
    _TRAFILATURA_AVAILABLE = False
    logger.warning(
        "trafilatura not installed — Jina-only extraction active. "
        "Run: pip install trafilatura"
    )

# ─── LlamaIndex ───────────────────────────────────────────────────────────────
from llama_index.core.node_parser import SentenceSplitter

# ─── Qdrant ───────────────────────────────────────────────────────────────────
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    OptimizersConfigDiff,
    PointStruct,
    Range,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    VectorParams,
)

# ─── HuggingFace ─────────────────────────────────────────────────────────────
from sentence_transformers import CrossEncoder, SentenceTransformer

# ─── DuckDuckGo fallback ──────────────────────────────────────────────────────
from ddgs import DDGS

# ─── PyMuPDF ──────────────────────────────────────────────────────────────────
import fitz

# ─── Suppress noisy logs ──────────────────────────────────────────────────────
import logging
logging.getLogger("primp").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


async def _false_coro() -> bool:
    return False


# =============================================================================
# CONFIGURATION
# =============================================================================

class AgentConfig:
    """Centralized, environment-driven configuration."""

    # ── Qdrant ────────────────────────────────────────────────────────────────
    QDRANT_URL: str               = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")

    # ── Groq API ──────────────────────────────────────────────────────────────
    GROQ_API_KEY:  Optional[str] = os.getenv("GROQ_API_KEY")
    GROQ_BASE_URL: str           = "https://api.groq.com/openai/v1"
    GROQ_MODEL:    str           = "llama-3.3-70b-versatile"

    # ── HuggingFace — image captioning only ──────────────────────────────────
    HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN")
    HF_API_BASE_URL: str    = "https://router.huggingface.co/hf-inference/models"
    HF_SUMMARIZER_MODEL: str = "facebook/bart-large-cnn"
    HF_IMAGE_CAP_MODEL:  str = "Salesforce/blip-image-captioning-base"

    # ── Embedding dimensions ───────────────────────────────────────────────────
    TEXT_EMBED_DIM:  int = 768
    TABLE_EMBED_DIM: int = 384
    IMAGE_EMBED_DIM: int = 512

    # ── Local model names ──────────────────────────────────────────────────────
    TEXT_EMBED_MODEL:    str = "BAAI/bge-base-en"
    TABLE_EMBED_MODEL:   str = "sentence-transformers/all-MiniLM-L6-v2"
    IMAGE_EMBED_MODEL:   str = "sentence-transformers/clip-ViT-B-32"

    CROSS_ENCODER_MODEL:          str = "BAAI/bge-reranker-v2-m3"
    CROSS_ENCODER_MODEL_FALLBACK: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    NLI_MODEL:                    str = "cross-encoder/nli-deberta-v3-small"

    # ── SearXNG ───────────────────────────────────────────────────────────────
    SEARXNG_URL:        str           = os.getenv("SEARXNG_URL", "http://localhost:8080")
    SEARXNG_API_KEY:    Optional[str] = os.getenv("SEARXNG_API_KEY")
    SEARXNG_SECRET_KEY: Optional[str] = os.getenv("SEARXNG_SECRET_KEY")
    SEARXNG_OPEN:       bool          = os.getenv("SEARXNG_OPEN", "false").lower() == "true"
    SEARXNG_ENGINES:    str           = "bing,duckduckgo,semantic_scholar"
    JINA_BASE_URL:      str           = "https://r.jina.ai"

    # ── PubMed E-utilities ────────────────────────────────────────────────────
    PUBMED_BASE_URL: str           = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    PUBMED_API_KEY:  Optional[str] = os.getenv("PUBMED_API_KEY")

    # ── Europe PMC / ClinicalTrials ───────────────────────────────────────────
    EUROPE_PMC_BASE_URL:      str = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    CLINICAL_TRIALS_BASE_URL: str = "https://clinicaltrials.gov/api/query/study_fields"

    # ── Redis Cache ───────────────────────────────────────────────────────────
    REDIS_HOST:        str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT:        int = int(os.getenv("REDIS_PORT", "6379"))
    CACHE_TTL_SECONDS: int = 3600
    CE_CACHE_TTL_SECONDS: int = 86400

    # ── Validation Thresholds ─────────────────────────────────────────────────
    SGV_MIN:                    float = 0.60
    FAITHFULNESS_MIN:           float = 0.80
    ANSWER_RELEVANCY_MIN:       float = 0.75
    CONTEXT_RECALL_MIN:         float = 0.70
    CONTEXT_PRECISION_MIN:      float = 0.65
    SOURCE_CREDIBILITY_MIN:     float = 0.60
    # FIX-SOFTMAX: thresholds now apply to softmax probabilities (0–1 range)
    CONTRADICTION_THRESHOLD_3L: float = 0.55
    CONTRADICTION_THRESHOLD_1L: float = 0.50

    # FIX-RELEVANCE-FLOOR: raised base and floor to reduce weak-abstract pass-through
    RELEVANCE_THRESHOLD_BASE: float = 0.45
    RELEVANCE_THRESHOLD_FLOOR: float = 0.32

    # ── Per-type dedup thresholds ─────────────────────────────────────────────
    DEDUP_COSINE_THRESHOLD: Dict[str, float] = {
        "text":  0.92,
        "pdf":   0.92,
        "image": 0.85,
        "table": 0.88,
        "graph": 0.85,
        "video": 0.90,
        "code":  0.95,
    }

    # FIX-FRESHNESS-DAYS: raised from 90 → 365 so indexed papers are not
    # silently dropped from Qdrant retrieval.
    DATA_FRESHNESS_DAYS: int = 365

    # ── Retrieval parameters ───────────────────────────────────────────────────
    TOP_K_DENSE:                  int   = 20
    TOP_K_RERANK:                 int   = 10
    MIN_RESULTS_BEFORE_WEBSEARCH: int   = 8
    RRF_K:                        float = 50.0
    HYBRID_ALPHA:                 float = 0.6
    MMR_LAMBDA:                   float = 0.7
    CE_MAX_CANDIDATES:            int   = 10
    QUERY_DECOMPOSE_WORD_THRESHOLD: int = 10

    # FIX-BM25-CAP: cap the in-memory BM25 document corpus to avoid unbounded growth
    BM25_MAX_DOCS: int = 2000

    # ── Collections ───────────────────────────────────────────────────────────
    COLLECTIONS: Dict[str, Dict[str, Any]] = {
        "texts_collection":  {"dim": TEXT_EMBED_DIM,  "distance": Distance.COSINE},
        "pdfs_collection":   {"dim": TEXT_EMBED_DIM,  "distance": Distance.COSINE},
        "images_collection": {"dim": IMAGE_EMBED_DIM, "distance": Distance.COSINE},
        "videos_collection": {"dim": TEXT_EMBED_DIM,  "distance": Distance.COSINE},
        "tables_collection": {"dim": TABLE_EMBED_DIM, "distance": Distance.DOT},
        "graphs_collection": {"dim": TEXT_EMBED_DIM,  "distance": Distance.COSINE},
        "code_collection":   {"dim": TEXT_EMBED_DIM,  "distance": Distance.COSINE},
    }

    # ── ACP ───────────────────────────────────────────────────────────────────
    ACP_VERSION: str = "3.4"
    AGENT_NAME:  str = "intelligent_target_discovery_agent"

    # ── Concurrency ───────────────────────────────────────────────────────────
    WEB_SEARCH_SEMAPHORE:  int   = 5
    BATCH_UPSERT_SIZE:     int   = 100
    WEB_SEARCH_TIMEOUT_S:  int   = 15
    JINA_MAX_CONCURRENCY:  int   = 3
    JINA_MAX_RETRIES:      int   = 1
    JINA_BACKOFF_BASE:     float = 1.0
    WEB_COLLECT_TIMEOUT_S: float = 45.0
    EXTRACT_RACE_TIMEOUT_S: float = 8.0

    # ── Trusted domains ───────────────────────────────────────────────────────
    TRUSTED_DOMAINS: List[str] = [
        "pubmed.ncbi.nlm.nih.gov", "arxiv.org", "nature.com", "science.org",
        "cell.com", "thelancet.com", "nejm.org", "bmj.com", "plos.org",
        "semanticscholar.org", "biorxiv.org", "medrxiv.org", "who.int",
        "cdc.gov", "nih.gov", "ebi.ac.uk", "uniprot.org", "rcsb.org",
        "clinicaltrials.gov", "drugbank.ca", "kegg.jp", "reactome.org",
        "omim.org", "ensembl.org", "genecards.org", "chembl.ebi.ac.uk",
        "ncbi.nlm.nih.gov", "jto.org",
        "annalsofoncology.org", "jnccn.org", "bloodjournal.org",
        "jci.org", "pnas.org", "frontiersin.org",
        "tandfonline.com",
        "sciencedirect.com", "springer.com", "wiley.com", "oup.com",
    ]

    # ── Jina domain blocklist ─────────────────────────────────────────────────
    JINA_BLOCKED_DOMAINS: Set[str] = {
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

    BLOCKED_DOMAIN_SUBSTRINGS: List[str] = [
        "arduino", "minecraft", "steampowered", "discord",
        "airfrance", "booking.com", "tripadvisor",
        "reddit", "twitch", "youtube",
        "support.google", "support.microsoft",
        "urlaubspiraten", "dertour", "reise-kroeten",
        "canva",
    ]

    SCIENTIFIC_DOMAIN_KEYWORDS: List[str] = [
        "journal", "research", "science", "biology", "biochem",
        "bio", "med", "health", "pharma", "clinical", "oncol",
        "genomic", "proteo", "ncbi", "pubmed", "arxiv", "doi",
        "preprint", "lab", "university", "univ", "college",
        "institute", "hospital", "clinic", "pathol", "immuno",
        "neuro", "cardio", "drug", "therapeut", "molecul",
    ]

    ACADEMIC_TLDS: List[str] = [".edu", ".gov", ".ac.", ".nih.gov", ".who.int"]
    NEUTRAL_TLDS_REQUIRE_KW: List[str] = [".org", ".net", ".io", ".co", ".cc"]

    BIOMEDICAL_DOMAIN_FILTER: bool = True

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE:  str = "agent_discovery.jsonl"

    # ── PDF section headers ───────────────────────────────────────────────────
    PDF_SECTION_HEADERS: List[str] = [
        r"abstract", r"introduction", r"background",
        r"methods?", r"materials?\s+and\s+methods?",
        r"results?", r"discussion", r"conclusion",
        r"references?", r"supplementary",
    ]

    # ── Biomedical keyword regex used for pre-filter ──────────────────────────
    BIOMEDICAL_PREFILTER_PATTERN: str = (
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


cfg = AgentConfig()

logger.add(
    cfg.LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
    level=cfg.LOG_LEVEL,
    serialize=True,
    rotation="50 MB",
    retention="30 days",
)

# =============================================================================
# DOMAIN FILTER — precompiled once at import time
# =============================================================================

_BLOCKED_EXACT: Set[str] = {
    d.replace("www.", "") for d in cfg.JINA_BLOCKED_DOMAINS
}

_BLOCKED_RE = re.compile(
    "|".join(re.escape(s) for s in cfg.BLOCKED_DOMAIN_SUBSTRINGS),
    re.I,
)

_SCIENTIFIC_RE = re.compile(
    "|".join(re.escape(s) for s in cfg.SCIENTIFIC_DOMAIN_KEYWORDS),
    re.I,
)

_ACADEMIC_TLD_RE = re.compile(
    r"\.(?:edu|gov|mil)|\.ac\.[a-z]{2}$", re.I
)

_ALLOWED_TLDS_RE = re.compile(r"\.(?:org|net|io|co|cc)$", re.I)

_COMMERCIAL_OR_CCTLD_RE = re.compile(
    r"\.(?:com|fr|de|es|it|ru|jp|cn|br|in|"
    r"vn|th|id|ph|tr|pl|nl|be|ar|mx|my|sg|tw|kr|ua|ro|hu|cz|sk|"
    r"za|eg|ng|ke|gh|tz|ma|dz|tn|ly|sd|"
    r"au|nz|ca|us|uk|ie|se|no|dk|fi|pt|gr|at|ch|"
    r"ae|sa|il|pk|bd|lk|np|mm|kh|la|mn|uz|kz)$",
    re.I,
)

_BIOMEDICAL_RE = re.compile(cfg.BIOMEDICAL_PREFILTER_PATTERN, re.I)


def _domain_is_blocked(domain: str) -> bool:
    """
    Returns True if the domain should be rejected before any content fetch.

    Logic (evaluated in order — first match wins):
      1. Exact blocklist hit              → BLOCKED
      2. Substring blocklist hit          → BLOCKED
      3. Academic TLD (.edu/.gov/etc.)    → ALLOWED
      4. In TRUSTED_DOMAINS list          → ALLOWED
      5. Contains a scientific keyword    → ALLOWED
      6. Neutral TLD (.org/.net/etc.)     → BLOCKED (no scientific kw — handled above)
      7. Commercial / ccTLD               → BLOCKED
      8. Unknown / anything else          → BLOCKED (default-deny)
    """
    if domain in _BLOCKED_EXACT:
        return True
    if _BLOCKED_RE.search(domain):
        return True
    if _ACADEMIC_TLD_RE.search(domain):
        return False
    if any(td in domain for td in cfg.TRUSTED_DOMAINS):
        return False
    if _SCIENTIFIC_RE.search(domain):
        return False
    if _ALLOWED_TLDS_RE.search(domain):
        return True
    if _COMMERCIAL_OR_CCTLD_RE.search(domain):
        return True
    return True


def _content_is_biomedically_relevant(content: str, query: str) -> bool:
    """
    Fast pre-filter applied before embedding.
    Returns True if the content contains at least one query term OR
    at least one biomedical keyword.
    """
    if not content or not content.strip():
        return False
    query_terms = {w.lower() for w in re.findall(r'\b\w{4,}\b', query)}
    content_lower = content.lower()
    if any(term in content_lower for term in query_terms):
        return True
    return bool(_BIOMEDICAL_RE.search(content))


# =============================================================================
# TYPE DEFINITIONS & DATA MODELS
# =============================================================================

class ContentType(str, Enum):
    TEXT  = "text"
    PDF   = "pdf"
    IMAGE = "image"
    VIDEO = "video"
    TABLE = "table"
    GRAPH = "graph"
    CODE  = "code"


class ACPIntent(str, Enum):
    FIND     = "find"
    RETRIEVE = "retrieve"
    REFRESH  = "refresh"
    VALIDATE = "validate"


class ACPRequest(BaseModel):
    acp_version:   str       = cfg.ACP_VERSION
    session_id:    str       = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    request_id:    str       = Field(default_factory=lambda: f"req_{uuid.uuid4().hex[:8]}")
    source_agent:  str
    target_agent:  str       = cfg.AGENT_NAME
    intent:        ACPIntent = ACPIntent.FIND
    query:         str
    data_types:    List[ContentType] = Field(default_factory=lambda: [ContentType.TEXT])
    filters:       Dict[str, Any]   = Field(default_factory=dict)
    top_k:         int              = cfg.TOP_K_DENSE
    require_fresh: bool             = True

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v.strip()


class ValidatedItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    content:          str
    content_type:     ContentType
    source_url:       str
    title:            str = ""
    language:         str = "en"
    date_collected:   str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    validation_score: float = 0.0
    domain_trust:     float = 0.0
    chunk_index:      int   = 0
    session_id:       str   = ""
    metadata:         Dict[str, Any]  = Field(default_factory=dict)
    relevance_score:  float           = 0.0
    image_bytes:      Optional[bytes] = None
    pmid:             Optional[str]   = None
    doi:              Optional[str]   = None
    citation_count:   Optional[int]   = None


class ACPResponse(BaseModel):
    acp_version:          str = cfg.ACP_VERSION
    session_id:           str
    request_id:           str
    source_agent:         str = cfg.AGENT_NAME
    target_agent:         str
    status:               str = "success"
    data_types:           List[ContentType]
    payload:              Dict[str, List[Dict[str, Any]]]
    validation_score:     float
    retrieval_latency_ms: int
    source_count:         int
    warning:              Optional[str] = None
    error:                Optional[str] = None
    targets:              List[Dict[str, Any]] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


@dataclass
class ValidationMetrics:
    faithfulness:       float = 0.0
    answer_relevancy:   float = 0.0
    context_recall:     float = 0.0
    context_precision:  float = 0.0
    source_credibility: float = 0.0
    contradiction_rate: float = 0.0
    dedup_rate:         float = 0.0
    g_eval:             float = 0.0

    @property
    def sgv(self) -> float:
        return (
            0.20 * self.faithfulness
            + 0.20 * self.answer_relevancy
            + 0.20 * self.context_recall
            + 0.15 * self.context_precision
            + 0.25 * self.source_credibility
            + 0.05 * (1.0 - self.contradiction_rate)
        )

    def is_valid(self) -> bool:
        return self.sgv >= cfg.SGV_MIN


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self.name              = name
        self.failure_threshold = failure_threshold
        self.reset_timeout     = reset_timeout
        self._state            = "CLOSED"
        self._failure_count    = 0
        self._last_failure_ts: float = 0.0
        self._in_flight:       int   = 0
        self._lock             = asyncio.Lock()

    async def _check_and_reserve(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._state == "OPEN":
                if now - self._last_failure_ts >= self.reset_timeout:
                    if self._in_flight == 0:
                        self._state = "HALF_OPEN"
                        self._in_flight += 1
                        logger.debug(f"CircuitBreaker [{self.name}] → HALF_OPEN (probe)")
                        return
                raise RuntimeError(f"CircuitBreaker [{self.name}] is OPEN — failing fast")
            if self._state == "HALF_OPEN":
                if self._in_flight > 0:
                    raise RuntimeError(
                        f"CircuitBreaker [{self.name}] HALF_OPEN probe already in flight"
                    )
                self._in_flight += 1
                return
            self._in_flight += 1

    async def _record_success(self) -> None:
        async with self._lock:
            prev                = self._state
            self._state         = "CLOSED"
            self._failure_count = 0
            self._in_flight     = max(0, self._in_flight - 1)
            if prev == "HALF_OPEN":
                logger.info(f"CircuitBreaker [{self.name}] → CLOSED (probe succeeded)")

    async def _record_failure(self) -> None:
        async with self._lock:
            self._in_flight       = max(0, self._in_flight - 1)
            self._failure_count  += 1
            self._last_failure_ts = time.monotonic()
            if self._failure_count >= self.failure_threshold or self._state == "HALF_OPEN":
                self._state = "OPEN"
                logger.warning(
                    f"CircuitBreaker [{self.name}] → OPEN (failures={self._failure_count})"
                )

    async def call(self, coro):
        await self._check_and_reserve()
        try:
            result = await coro
            await self._record_success()
            return result
        except Exception as exc:
            await self._record_failure()
            raise exc


# =============================================================================
# QDRANT COLLECTION MANAGER
# =============================================================================

class QdrantCollectionManager:
    def __init__(self):
        self.client       = AsyncQdrantClient(url=cfg.QDRANT_URL, api_key=cfg.QDRANT_API_KEY)
        self._initialized = False

    async def initialize(self):
        existing = {c.name for c in (await self.client.get_collections()).collections}
        for name, spec in cfg.COLLECTIONS.items():
            if name not in existing:
                await self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=spec["dim"],
                        distance=spec["distance"],
                        on_disk=True,
                    ),
                    hnsw_config=HnswConfigDiff(
                        m=16, ef_construct=100, full_scan_threshold=20000
                    ),
                    optimizers_config=OptimizersConfigDiff(indexing_threshold=20000),
                    quantization_config=ScalarQuantization(
                        scalar=ScalarQuantizationConfig(
                            type=ScalarType.INT8, always_ram=True
                        )
                    ),
                )
                logger.info(f"Collection created: {name} (dim={spec['dim']})")
            else:
                logger.debug(f"Collection already exists: {name}")
        self._initialized = True

    @staticmethod
    def collection_for_type(content_type: ContentType) -> str:
        return {
            ContentType.TEXT:  "texts_collection",
            ContentType.PDF:   "pdfs_collection",
            ContentType.IMAGE: "images_collection",
            ContentType.VIDEO: "videos_collection",
            ContentType.TABLE: "tables_collection",
            ContentType.GRAPH: "graphs_collection",
            ContentType.CODE:  "code_collection",
        }[content_type]

    async def count_points(self, collection_name: str) -> int:
        try:
            result = await self.client.count(collection_name=collection_name, exact=True)
            return result.count
        except Exception as exc:
            logger.warning(f"count_points failed for {collection_name}: {exc}")
            return -1

    async def upsert_batch(self, points: List[PointStruct], collection_name: str):
        for i in range(0, len(points), cfg.BATCH_UPSERT_SIZE):
            batch = points[i : i + cfg.BATCH_UPSERT_SIZE]
            try:
                await self.client.upsert(
                    collection_name=collection_name, points=batch, wait=True
                )
            except TypeError:
                await self.client.upsert(collection_name=collection_name, points=batch)
        logger.debug(f"Upserted {len(points)} points into {collection_name}")

    async def hybrid_search(
        self,
        query_vector:    List[float],
        collection_name: str,
        top_k:           int,
        payload_filter:  Optional[Filter] = None,
    ) -> List[Dict[str, Any]]:
        try:
            response = await self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=payload_filter,
                limit=top_k,
                with_payload=True,
            )
            points  = response.points if hasattr(response, "points") else response
            results = [
                {"id": str(p.id), "score": p.score, "payload": p.payload or {}}
                for p in points
            ]
        except AttributeError:
            try:
                raw = await self.client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=top_k,
                    query_filter=payload_filter,
                    with_payload=True,
                )
                results = [
                    {"id": str(r.id), "score": r.score, "payload": r.payload or {}}
                    for r in raw
                ]
            except Exception as exc:
                logger.warning(f"Qdrant legacy search failed for {collection_name}: {exc}")
                results = []
        except Exception as exc:
            logger.warning(f"Qdrant query_points failed for {collection_name}: {exc}")
            results = []

        logger.debug(
            f"hybrid_search [{collection_name}]: {len(results)} results "
            f"top_score={results[0]['score'] if results else 'N/A'}"
        )
        return results

    async def close(self):
        await self.client.close()


# =============================================================================
# GROQ CLIENT
# =============================================================================

class GroqClient:
    def __init__(self):
        self._session:     Optional[aiohttp.ClientSession] = None
        self._unavailable: bool = False
        self._warned_once: bool = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "Authorization": f"Bearer {cfg.GROQ_API_KEY}",
                "Content-Type":  "application/json",
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def chat(
        self,
        prompt:        str,
        max_tokens:    int   = 512,
        temperature:   float = 0.1,
        system_prompt: str   = "You are a helpful biomedical research assistant.",
    ) -> str:
        if not cfg.GROQ_API_KEY:
            if not self._warned_once:
                logger.warning(
                    "GROQ_API_KEY not set — HyDE, decomposition, and summarization disabled.\n"
                    "  Windows: $env:GROQ_API_KEY = 'gsk_...'\n"
                    "  Linux:   export GROQ_API_KEY=gsk_..."
                )
                self._warned_once = True
            return ""
        if self._unavailable:
            return ""

        payload = {
            "model":       cfg.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }
        try:
            session = await self._get_session()
            async with session.post(
                f"{cfg.GROQ_BASE_URL}/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data    = await resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    logger.debug(
                        f"Groq [{cfg.GROQ_MODEL}] responded "
                        f"({len(content)} chars) for prompt[:60]='{prompt[:60]}'"
                    )
                    return content
                elif resp.status == 429:
                    retry_after = resp.headers.get("retry-after", "?")
                    logger.warning(f"Groq rate limit (retry-after={retry_after}s) — falling back")
                    return ""
                elif resp.status in (401, 403):
                    self._unavailable = True
                    error = await resp.text()
                    logger.error(f"Groq auth error {resp.status}: {error[:200]}")
                    return ""
                else:
                    error = await resp.text()
                    logger.warning(f"Groq HTTP {resp.status}: {error[:200]}")
                    return ""
        except asyncio.TimeoutError:
            logger.warning("Groq request timed out after 30 s — falling back")
            return ""
        except Exception as exc:
            logger.warning(f"Groq request failed: {exc}")
            return ""

    async def generate_text(self, prompt: str, max_tokens: int = 256) -> str:
        return await self.chat(prompt, max_tokens=max_tokens)

    async def decompose_query(self, query: str, n: int = 3) -> List[str]:
        if not cfg.GROQ_API_KEY or self._unavailable:
            return self._simple_split(query, n)

        prompt = (
            f"Break the following biomedical query into exactly {n} focused "
            f"sub-queries for searching scientific literature. "
            f"Return ONLY a JSON array of strings, no explanation, no markdown.\n\n"
            f"Query: {query}\n\nJSON array:"
        )
        raw = await self.chat(prompt, max_tokens=300, temperature=0.0)
        if not raw:
            return self._simple_split(query, n)
        try:
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                sub_queries = json.loads(match.group())
                if isinstance(sub_queries, list) and all(
                    isinstance(s, str) for s in sub_queries
                ):
                    logger.debug(f"Groq decomposed query into {len(sub_queries)} sub-queries")
                    return sub_queries[:n]
        except Exception as exc:
            logger.debug(f"Groq decomposition JSON parse failed: {exc}")
        return self._simple_split(query, n)

    async def generate_hyde_passage(self, query: str) -> str:
        if not cfg.GROQ_API_KEY or self._unavailable:
            return ""
        prompt = (
            f"Write a short 3-sentence biomedical abstract that directly and "
            f"factually answers this research query. Be specific and concise.\n\n"
            f"Query: {query}\n\nAbstract:"
        )
        result = await self.chat(
            prompt,
            max_tokens=200,
            temperature=0.1,
            system_prompt=(
                "You are a biomedical scientist. Write precise, evidence-based "
                "abstracts suitable for scientific literature search."
            ),
        )
        logger.debug(f"Groq HyDE passage ({len(result)} chars) for query: '{query[:60]}'")
        return result

    async def summarize(self, text: str, max_tokens: int = 150) -> str:
        if not cfg.GROQ_API_KEY or self._unavailable:
            return text[:600]
        prompt = (
            f"Summarize the following biomedical text in 2-3 sentences, "
            f"preserving key findings and terminology:\n\n{text[:3000]}"
        )
        result = await self.chat(prompt, max_tokens=max_tokens, temperature=0.0)
        return result if result.strip() else text[:600]

    async def verify_faithfulness(self, query: str, content: str) -> float:
        """
        FIX-FAITHFULNESS: ask Groq to judge whether `content` faithfully
        addresses `query`.  Returns a float in [0, 1].
        Falls back to 0.5 if Groq is unavailable.
        """
        if not cfg.GROQ_API_KEY or self._unavailable:
            return 0.5
        prompt = (
            f"On a scale from 0.0 to 1.0, how faithfully does the following "
            f"text address the biomedical query?\n\n"
            f"Query: {query}\n\n"
            f"Text: {content[:1500]}\n\n"
            f"Reply with ONLY a decimal number between 0.0 and 1.0, nothing else."
        )
        raw = await self.chat(prompt, max_tokens=10, temperature=0.0)
        try:
            score = float(re.search(r"[\d.]+", raw).group())
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5

    @staticmethod
    def _simple_split(query: str, n: int) -> List[str]:
        parts = re.split(r"\band\b|,|;|\bor\b", query, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if len(p.strip()) > 8]
        if len(parts) >= n:
            return parts[:n]
        words = query.split()
        mid   = len(words) // 2
        if len(words) > 8:
            return [
                " ".join(words[:mid + 2]),
                " ".join(words[mid - 2:]),
            ][:n] or [query]
        return [query]

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# =============================================================================
# HF INFERENCE CLIENT — image captioning + summarization fallback only
# =============================================================================

class HFInferenceClient:
    def __init__(self):
        self._session:        Optional[aiohttp.ClientSession] = None
        self._hf_unavailable: bool = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {}
            if cfg.HF_TOKEN:
                headers["Authorization"] = f"Bearer {cfg.HF_TOKEN}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _post_json(self, model: str, payload: Dict[str, Any]) -> Any:
        url     = f"{cfg.HF_API_BASE_URL}/{model}"
        session = await self._get_session()
        async with session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 503:
                body = await resp.json(content_type=None)
                wait = body.get("estimated_time", 20)
                raise RuntimeError(f"HF model loading (est. {wait}s): {model}")
            if resp.status in (404, 410):
                self._hf_unavailable = True
                error = await resp.text()
                raise RuntimeError(f"HF API error {resp.status} for {model}: {error[:120]}")
            if resp.status != 200:
                error = await resp.text()
                raise RuntimeError(f"HF API error {resp.status} for {model}: {error[:200]}")
            return await resp.json(content_type=None)

    async def summarize(self, text: str, max_new_tokens: int = 150) -> str:
        truncated = text[:3000]
        if not cfg.HF_TOKEN or self._hf_unavailable:
            return truncated[:600]
        try:
            payload = {
                "inputs":     truncated,
                "parameters": {"max_new_tokens": max_new_tokens, "min_length": 30},
            }
            result = await self._post_json(cfg.HF_SUMMARIZER_MODEL, payload)
            if isinstance(result, list) and result:
                return result[0].get("summary_text", truncated[:600]).strip()
            return truncated[:600]
        except Exception as exc:
            logger.debug(f"HF summarization skipped ({exc}) — using truncation")
            return truncated[:600]

    async def caption_image(self, image_bytes: bytes) -> str:
        if not cfg.HF_TOKEN:
            return ""
        try:
            url     = f"{cfg.HF_API_BASE_URL}/{cfg.HF_IMAGE_CAP_MODEL}"
            session = await self._get_session()
            headers = {"Content-Type": "image/jpeg"}
            if cfg.HF_TOKEN:
                headers["Authorization"] = f"Bearer {cfg.HF_TOKEN}"
            async with session.post(
                url, data=image_bytes, headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HF image caption error {resp.status}")
                result = await resp.json(content_type=None)
                return result[0].get("generated_text", "").strip()
        except Exception as exc:
            logger.warning(f"HF image captioning failed: {exc}")
            return ""

    async def caption_image_from_url(self, url: str, session: aiohttp.ClientSession) -> str:
        if not cfg.HF_TOKEN:
            return f"Image at {url}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                img_data = await r.read()
            return await self.caption_image(img_data) or f"Image at {url}"
        except Exception as exc:
            logger.warning(f"caption_image_from_url failed for {url}: {exc}")
            return f"Image at {url}"

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# =============================================================================
# EMBEDDING SERVICE
# =============================================================================

class EmbeddingService:
    def __init__(self):
        self.text_embedder  = SentenceTransformer(cfg.TEXT_EMBED_MODEL)
        self.table_embedder = SentenceTransformer(cfg.TABLE_EMBED_MODEL)
        self.clip_model     = SentenceTransformer(cfg.IMAGE_EMBED_MODEL)
        self.groq           = GroqClient()
        self.hf             = HFInferenceClient()

    async def embed_text(self, text: str) -> List[float]:
        try:
            loop = asyncio.get_running_loop()
            emb  = await loop.run_in_executor(None, self.text_embedder.encode, text)
            return emb.tolist()
        except Exception as exc:
            raise ValueError(f"Text embedding failed: {exc}") from exc

    async def embed_text_safe(self, text: str) -> Optional[List[float]]:
        try:
            return await self.embed_text(text)
        except ValueError as exc:
            logger.warning(str(exc))
            return None

    async def embed_table(self, text: str) -> List[float]:
        try:
            loop = asyncio.get_running_loop()
            emb  = await loop.run_in_executor(None, self.table_embedder.encode, text)
            return emb.tolist()
        except Exception as exc:
            raise ValueError(f"Table embedding failed: {exc}") from exc

    async def embed_image_bytes(self, image_bytes: bytes) -> List[float]:
        try:
            img  = Image.open(BytesIO(image_bytes)).convert("RGB")
            loop = asyncio.get_running_loop()
            emb  = await loop.run_in_executor(None, self.clip_model.encode, img)
            return emb.tolist()
        except Exception as exc:
            raise ValueError(f"CLIP vision embedding failed: {exc}") from exc

    async def embed_image_caption(self, caption: str) -> List[float]:
        try:
            loop = asyncio.get_running_loop()
            emb  = await loop.run_in_executor(None, self.clip_model.encode, caption)
            return emb.tolist()
        except Exception as exc:
            raise ValueError(f"CLIP caption embedding failed: {exc}") from exc

    async def embed_for_type(
        self,
        content:      str,
        content_type: ContentType,
        image_bytes:  Optional[bytes] = None,
    ) -> List[float]:
        if content_type == ContentType.TABLE:
            return await self.embed_table(content)
        elif content_type == ContentType.IMAGE:
            if image_bytes:
                return await self.embed_image_bytes(image_bytes)
            return await self.embed_image_caption(content)
        elif content_type == ContentType.GRAPH:
            return await self.embed_image_caption(content)
        else:
            return await self.embed_text(content)

    async def embed_hyde(self, query: str) -> Optional[List[float]]:
        try:
            passage = await self.groq.generate_hyde_passage(query)
            if not passage.strip():
                return None
            return await self.embed_text(passage)
        except Exception as exc:
            logger.warning(f"HyDE embedding failed: {exc}")
            return None

    async def embed_query_with_hyde(self, query: str) -> List[float]:
        query_emb = await self.embed_text(query)
        hyde_emb  = await self.embed_hyde(query)
        if hyde_emb is not None:
            avg = (np.array(query_emb) + np.array(hyde_emb)) / 2.0
            logger.debug("HyDE averaging applied to query embedding")
            return avg.tolist()
        return query_emb

    async def summarize_text(self, text: str, max_words: int = 150) -> str:
        result = await self.groq.summarize(text, max_tokens=max_words * 2)
        if result and result != text[:600]:
            return result
        return await self.hf.summarize(text, max_new_tokens=max_words * 2)

    async def generate_caption_for_image(
        self, image_url: str, session: aiohttp.ClientSession
    ) -> str:
        return await self.hf.caption_image_from_url(image_url, session)

    async def close(self):
        await self.groq.close()
        await self.hf.close()


# =============================================================================
# BM25 INDEX
# =============================================================================

class BM25Index:
    """
    TF-IDF backed BM25 approximation.

    FIX-BM25-CAP: the in-memory document list is capped at BM25_MAX_DOCS
    entries (FIFO eviction) to prevent unbounded TF-IDF matrix rebuilds as
    the running corpus grows across many queries.
    """

    def __init__(self):
        self._vectorizer = TfidfVectorizer(
            sublinear_tf=True, norm="l2", analyzer="word",
            min_df=1, ngram_range=(1, 2),
        )
        self._matrix    = None
        self._documents: List[str] = []
        self._fitted    = False

    def add_documents(self, new_docs: List[str]) -> None:
        if not new_docs:
            return
        self._documents.extend(new_docs)
        # FIX-BM25-CAP: evict oldest entries if cap exceeded
        if len(self._documents) > cfg.BM25_MAX_DOCS:
            self._documents = self._documents[-cfg.BM25_MAX_DOCS:]
        if len(self._documents) >= 2:
            try:
                self._matrix = self._vectorizer.fit_transform(self._documents)
                self._fitted = True
            except Exception as exc:
                logger.debug(f"BM25 refit failed: {exc}")
                self._matrix = None

    def fit(self, documents: List[str]) -> None:
        self.add_documents(documents)

    def score(self, query: str) -> np.ndarray:
        if self._matrix is None or not self._documents:
            return np.ones(len(self._documents)) / max(len(self._documents), 1)
        try:
            q_vec = self._vectorizer.transform([query])
            return cosine_similarity(q_vec, self._matrix).flatten()
        except Exception:
            return np.ones(len(self._documents)) / len(self._documents)

    def score_subset(self, query: str, subset_docs: List[str]) -> np.ndarray:
        if not subset_docs:
            return np.array([], dtype=float)
        if not self._fitted:
            return np.ones(len(subset_docs)) / len(subset_docs)
        try:
            subset_matrix = self._vectorizer.transform(subset_docs)
            q_vec         = self._vectorizer.transform([query])
            return cosine_similarity(q_vec, subset_matrix).flatten()
        except Exception:
            return np.ones(len(subset_docs)) / len(subset_docs)

    def top_k_indices(self, query: str, k: int) -> List[int]:
        scores = self.score(query)
        k      = min(k, len(scores))
        return np.argsort(scores)[::-1][:k].tolist()


# =============================================================================
# WEB SEARCH AGENT
# =============================================================================

class WebSearchAgent:
    def __init__(self):
        self._semaphore       = asyncio.Semaphore(cfg.WEB_SEARCH_SEMAPHORE)
        self._jina_semaphore  = asyncio.Semaphore(cfg.JINA_MAX_CONCURRENCY)
        self._session:        Optional[aiohttp.ClientSession] = None
        self._searxng_warned: bool = False
        self._cb_searxng = CircuitBreaker("searxng", failure_threshold=5, reset_timeout=60.0)
        self._cb_jina    = CircuitBreaker("jina",    failure_threshold=8, reset_timeout=30.0)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=cfg.WEB_SEARCH_TIMEOUT_S)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _search_searxng(
        self, query: str, content_type: ContentType, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        async with self._semaphore:
            params: Dict[str, Any] = {
                "q":        query,
                "format":   "json",
                "engines":  cfg.SEARXNG_ENGINES,
                "language": "en",
                "pageno":   1,
            }
            if content_type == ContentType.PDF:
                params["q"] += " filetype:pdf"
            elif content_type == ContentType.IMAGE:
                params["categories"] = "images"
            elif content_type == ContentType.CODE:
                params["engines"] = "github"

            headers: Dict[str, str] = {}
            if cfg.SEARXNG_API_KEY:
                headers["Authorization"] = f"Bearer {cfg.SEARXNG_API_KEY}"
            elif cfg.SEARXNG_SECRET_KEY:
                params["apikey"] = cfg.SEARXNG_SECRET_KEY
            elif not cfg.SEARXNG_OPEN:
                if not self._searxng_warned:
                    logger.warning(
                        "SearXNG auth not configured — set SEARXNG_API_KEY, "
                        "SEARXNG_SECRET_KEY, or SEARXNG_OPEN=true."
                    )
                    self._searxng_warned = True
                return []

            async def _do_search() -> List[Dict[str, Any]]:
                sess = await self._get_session()
                async with sess.get(
                    f"{cfg.SEARXNG_URL}/search", params=params, headers=headers
                ) as resp:
                    if resp.status == 200:
                        data    = await resp.json()
                        results = data.get("results", [])[:max_results]
                        logger.debug(f"SearXNG → {len(results)} results for '{query[:60]}'")
                        return results
                    if resp.status in (401, 403) and not self._searxng_warned:
                        logger.warning(f"SearXNG HTTP {resp.status} — check credentials")
                        self._searxng_warned = True
                    return []

            try:
                return await asyncio.wait_for(
                    self._cb_searxng.call(_do_search()),
                    timeout=cfg.WEB_SEARCH_TIMEOUT_S,
                )
            except (asyncio.TimeoutError, RuntimeError) as exc:
                logger.warning(f"SearXNG unavailable: {exc} — switching to DDG fallback")
                return []
            except Exception as exc:
                logger.warning(f"SearXNG error: {exc}")
                return []

    async def _search_ddg(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        # FIX-PUBMED-LIMIT: DDG max_results lowered to 5 to shift quality
        # budget toward PubMed/Scholar results.
        def _ddg_sync() -> List[Dict[str, Any]]:
            rows = list(DDGS().text(query, max_results=max_results))
            return [
                {"url": r.get("href", ""), "title": r.get("title", ""), "content": r.get("body", "")}
                for r in rows
            ]
        try:
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, _ddg_sync), timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning("DDG fallback timed out after 30 s")
            return []
        except Exception as exc:
            logger.warning(f"DDG fallback error: {exc}")
            return []

    async def _search_semantic_scholar(
        self, query: str, max_results: int = 5
    ) -> List[Dict[str, Any]]:
        try:
            sess   = await self._get_session()
            params = {
                "query":  query,
                "limit":  max_results,
                "fields": "title,abstract,url,year,authors,externalIds,citationCount",
            }
            async with sess.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    return []
                data    = await resp.json()
                papers  = data.get("data", [])
                results = []
                for p in papers:
                    if not p.get("abstract"):
                        continue
                    ext_ids = p.get("externalIds", {}) or {}
                    results.append({
                        "url":            p.get("url", ""),
                        "title":          p.get("title", ""),
                        "content":        p.get("abstract", ""),
                        "year":           p.get("year"),
                        "citation_count": p.get("citationCount"),
                        "pmid":           ext_ids.get("PubMed"),
                        "doi":            ext_ids.get("DOI"),
                        "content_type":   ContentType.TEXT.value,
                    })
                return results
        except Exception as exc:
            logger.warning(f"Semantic Scholar error: {exc}")
            return []

    async def _search_pubmed(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Two-step PubMed fetch:
          1. esearch → PMIDs
          2. efetch (rettype=abstract, retmode=xml) → parse full AbstractText

        FIX-PUBMED-LIMIT: max_results raised from 5 → 10 since PubMed is the
        highest-trust source in the pipeline.
        """
        try:
            sess = await self._get_session()

            esearch_params: Dict[str, Any] = {
                "db":      "pubmed",
                "term":    query,
                "retmax":  max_results,
                "retmode": "json",
                "sort":    "relevance",
            }
            if cfg.PUBMED_API_KEY:
                esearch_params["api_key"] = cfg.PUBMED_API_KEY

            async with sess.get(
                f"{cfg.PUBMED_BASE_URL}/esearch.fcgi",
                params=esearch_params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"PubMed esearch HTTP {resp.status}")
                    return []
                esearch_data = await resp.json()

            pmids = esearch_data.get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return []

            efetch_params: Dict[str, Any] = {
                "db":      "pubmed",
                "id":      ",".join(pmids),
                "retmode": "xml",
                "rettype": "abstract",
            }
            if cfg.PUBMED_API_KEY:
                efetch_params["api_key"] = cfg.PUBMED_API_KEY

            async with sess.get(
                f"{cfg.PUBMED_BASE_URL}/efetch.fcgi",
                params=efetch_params,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"PubMed efetch HTTP {resp.status}")
                    return []
                xml_text = await resp.text()

            results = self._parse_pubmed_xml(xml_text)
            logger.debug(f"PubMed → {len(results)} results for '{query[:60]}'")
            return results

        except Exception as exc:
            logger.warning(f"PubMed search error: {exc}")
            return []

    @staticmethod
    def _parse_pubmed_xml(xml_text: str) -> List[Dict[str, Any]]:
        """
        Parse PubMed efetch XML and extract title, abstract, PMID, DOI, and year.
        Uses explicit None-checks (FIX-YEAR-EL from v3.3 retained).
        """
        results: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning(f"PubMed XML parse error: {exc}")
            return results

        for article in root.findall(".//PubmedArticle"):
            try:
                pmid_el = article.find(".//PMID")
                pmid    = pmid_el.text.strip() if pmid_el is not None else None

                title_el = article.find(".//ArticleTitle")
                title    = "".join(title_el.itertext()).strip() if title_el is not None else ""

                abstract_parts = []
                for ab_el in article.findall(".//AbstractText"):
                    label = ab_el.get("Label", "")
                    text  = "".join(ab_el.itertext()).strip()
                    if text:
                        abstract_parts.append(f"{label}: {text}" if label else text)
                abstract = " ".join(abstract_parts).strip()

                doi = None
                for id_el in article.findall(".//ArticleId"):
                    if id_el.get("IdType") == "doi":
                        doi = id_el.text.strip() if id_el.text else None
                        break

                year_el = article.find(".//PubDate/Year")
                if year_el is None:
                    year_el = article.find(".//PubDate/MedlineDate")
                year = year_el.text[:4] if year_el is not None and year_el.text else None

                content = abstract or title
                if not content:
                    continue

                pub_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

                results.append({
                    "url":          pub_url,
                    "title":        title,
                    "content":      content,
                    "pmid":         pmid,
                    "doi":          doi,
                    "year":         year,
                    "content_type": ContentType.TEXT.value,
                })

            except Exception as exc:
                logger.debug(f"PubMed XML article parse error: {exc}")
                continue

        return results

    async def _search_europe_pmc(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        try:
            sess = await self._get_session()
            params = {
                "query":      query,
                "format":     "json",
                "pageSize":   max_results,
                "resultType": "core",
            }
            async with sess.get(
                cfg.EUROPE_PMC_BASE_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Europe PMC HTTP {resp.status}")
                    return []
                data = await resp.json()
                results = []
                for hit in data.get("resultList", {}).get("result", []):
                    abstract = hit.get("abstractText", "")
                    if not abstract:
                        continue
                    results.append({
                        "url":            f"https://europepmc.org/article/MED/{hit.get('pmid')}",
                        "title":          hit.get("title", ""),
                        "content":        abstract,
                        "pmid":           hit.get("pmid"),
                        "doi":            hit.get("doi"),
                        "citation_count": hit.get("citedByCount"),
                        "content_type":   ContentType.TEXT.value,
                    })
                logger.debug(f"Europe PMC → {len(results)} results for '{query[:60]}'")
                return results
        except Exception as exc:
            logger.warning(f"Europe PMC error: {exc}")
            return []

    async def _search_clinical_trials(
        self, query: str, max_results: int = 5
    ) -> List[Dict[str, Any]]:
        try:
            sess = await self._get_session()
            params = {
                "expr":     query,
                "fmt":      "json",
                "pageSize": max_results,
                "fields":   "NCTId,BriefTitle,BriefSummary,OfficialTitle,OverallStatus,Phase",
            }
            async with sess.get(
                cfg.CLINICAL_TRIALS_BASE_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"ClinicalTrials.gov HTTP {resp.status}")
                    return []
                data    = await resp.json()
                studies = data.get("studyFieldsResponse", {}).get("studyFields", [])
                results = []
                for study in studies:
                    nct_id  = study.get("NCTId",        [None])[0]
                    title   = (study.get("BriefTitle",   [None])[0]
                               or study.get("OfficialTitle", [None])[0] or "")
                    summary = study.get("BriefSummary", [None])[0] or ""
                    if not summary:
                        continue
                    results.append({
                        "url":     f"https://clinicaltrials.gov/study/{nct_id}",
                        "title":   title,
                        "content": summary,
                        "metadata": {
                            "phase":  study.get("Phase",         [None])[0],
                            "status": study.get("OverallStatus", [None])[0],
                        },
                        "content_type": ContentType.TEXT.value,
                    })
                logger.debug(f"ClinicalTrials.gov → {len(results)} results for '{query[:60]}'")
                return results
        except Exception as exc:
            logger.warning(f"ClinicalTrials.gov error: {exc}")
            return []

    async def _extract_content_race(self, url: str) -> str:
        """
        Launch Jina and trafilatura concurrently; return whichever
        produces a non-empty result first.  Cancels the loser.
        """
        jina_task = asyncio.create_task(self._extract_with_jina_raw(url))
        traf_task = asyncio.create_task(self._extract_with_trafilatura(url))

        done, pending = await asyncio.wait(
            [jina_task, traf_task],
            return_when=asyncio.FIRST_COMPLETED,
            timeout=cfg.EXTRACT_RACE_TIMEOUT_S,
        )

        result = ""
        for task in done:
            try:
                r = task.result()
                if r and len(r) > len(result):
                    result = r
            except Exception:
                pass

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        return result

    async def _extract_with_jina_raw(self, url: str) -> str:
        """Jina extraction without the trafilatura fallback (used inside the race)."""
        import random
        domain = urlparse(url).netloc.lower()
        if domain in cfg.JINA_BLOCKED_DOMAINS:
            return ""

        jina_url = f"{cfg.JINA_BASE_URL}/{url}"
        for attempt in range(cfg.JINA_MAX_RETRIES):
            try:
                async def _attempt() -> str:
                    async with self._jina_semaphore:
                        sess = await self._get_session()
                        async with sess.get(
                            jina_url,
                            headers={"Accept": "text/plain"},
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as resp:
                            if resp.status == 200:
                                text = (await resp.text())[:8000]
                                return text if text.strip() else ""
                            if resp.status == 429:
                                cap  = cfg.JINA_BACKOFF_BASE * (2 ** attempt)
                                wait = random.uniform(0, cap)
                                await asyncio.sleep(wait)
                                raise RuntimeError("Jina 429")
                            return ""

                result = await self._cb_jina.call(_attempt())
                if result:
                    return result
                break
            except RuntimeError as exc:
                if "429" not in str(exc):
                    break
            except asyncio.TimeoutError:
                logger.debug(f"Jina timeout for {url} attempt {attempt + 1}")
                break
            except Exception as exc:
                logger.debug(f"Jina error for {url}: {exc}")
                break
        return ""

    async def _extract_with_jina(self, url: str) -> str:
        """Original serial method — delegates to race."""
        return await self._extract_content_race(url)

    async def _extract_with_trafilatura(self, url: str) -> str:
        if not _TRAFILATURA_AVAILABLE:
            return ""
        try:
            loop = asyncio.get_running_loop()

            def _fetch_and_extract() -> str:
                downloaded = trafilatura.fetch_url(url)
                if not downloaded:
                    return ""
                text = trafilatura.extract(
                    downloaded,
                    include_tables=True,
                    include_images=False,
                    no_fallback=False,
                )
                return (text or "")[:8000]

            result = await asyncio.wait_for(
                loop.run_in_executor(None, _fetch_and_extract),
                timeout=8.0,
            )
            if result:
                logger.debug(f"trafilatura succeeded for {url}")
            return result
        except asyncio.TimeoutError:
            logger.debug(f"trafilatura timeout for {url}")
            return ""
        except Exception as exc:
            logger.debug(f"trafilatura error for {url}: {exc}")
            return ""

    async def _extract_pdf(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            sess = await self._get_session()
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return None
                pdf_bytes = await resp.read()

            loop = asyncio.get_running_loop()

            def _parse(data: bytes) -> Dict[str, Any]:
                doc        = fitz.open(stream=data, filetype="pdf")
                n_pages    = len(doc)
                text_parts = [doc[i].get_text() for i in range(min(n_pages, 20))]
                meta       = doc.metadata.copy()
                doc.close()
                return {
                    "content":      "\n".join(text_parts)[:10000],
                    "pages":        n_pages,
                    "title":        meta.get("title", ""),
                    "content_type": ContentType.PDF.value,
                    "url":          url,
                }

            return await loop.run_in_executor(None, _parse, pdf_bytes)
        except Exception as exc:
            logger.warning(f"PDF extraction failed for {url}: {exc}")
            return None

    async def _detect_is_pdf(self, url: str) -> bool:
        if url.lower().endswith(".pdf"):
            return True
        try:
            sess = await self._get_session()
            async with sess.head(
                url, timeout=aiohttp.ClientTimeout(total=5), allow_redirects=True
            ) as r:
                ct = r.headers.get("Content-Type", "")
                return "application/pdf" in ct
        except Exception:
            return False

    async def collect(
        self,
        query:         str,
        content_types: List[ContentType],
        max_per_type:  int   = 8,
        total_timeout: float = cfg.WEB_COLLECT_TIMEOUT_S,
    ) -> List[Dict[str, Any]]:
        async def _all() -> List[Dict[str, Any]]:
            scholar_relevant = any(
                ct in content_types
                for ct in (ContentType.TEXT, ContentType.PDF, ContentType.GRAPH)
            )
            tasks = []
            if scholar_relevant:
                tasks.append(self._search_semantic_scholar(query, max_results=5))
                tasks.append(self._search_pubmed(query, max_results=10))

            scholar_results: List[Dict[str, Any]] = []
            if tasks:
                raw_results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in raw_results:
                    if not isinstance(r, Exception):
                        scholar_results.extend(r)

            tasks = [
                self._collect_for_type(query, ct, max_per_type, scholar_results)
                for ct in content_types
            ]
            nested = await asyncio.gather(*tasks, return_exceptions=True)
            raw: List[Dict[str, Any]] = []
            for r in nested:
                if isinstance(r, Exception):
                    logger.warning(f"Collection subtask failed: {r}")
                else:
                    raw.extend(r)
            return raw

        try:
            raw = await asyncio.wait_for(_all(), timeout=total_timeout)
        except asyncio.TimeoutError:
            logger.warning(
                f"WebSearchAgent.collect() hit {total_timeout}s timeout "
                f"for '{query[:60]}' — returning partial results"
            )
            raw = []

        logger.info(f"WebSearchAgent collected {len(raw)} raw items for '{query[:80]}'")
        return raw

    async def _collect_for_type(
        self,
        query:           str,
        content_type:    ContentType,
        max_results:     int,
        scholar_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        searxng = await self._search_searxng(query, content_type, max_results)

        searxng_ran = bool(cfg.SEARXNG_API_KEY or cfg.SEARXNG_SECRET_KEY or cfg.SEARXNG_OPEN)
        if len(searxng) < 3:
            if searxng_ran:
                logger.info("SearXNG returned < 3 results — activating DDG fallback")
            ddg = await self._search_ddg(query, max_results=5)
            searxng.extend(ddg)

        if content_type in (ContentType.TEXT, ContentType.PDF, ContentType.GRAPH):
            searxng.extend(scholar_results)

        candidates = searxng[:max_results]
        urls = [r.get("url", r.get("href", "")) for r in candidates]
        pdf_flag_tasks = [
            self._detect_is_pdf(u) if u else _false_coro()
            for u in urls
        ]
        pdf_flags_raw = await asyncio.gather(*pdf_flag_tasks, return_exceptions=True)
        pdf_flags = [
            bool(f) if not isinstance(f, Exception) else False
            for f in pdf_flags_raw
        ]

        tasks = []
        for raw, url, is_pdf in zip(candidates, urls, pdf_flags):
            if url:
                tasks.append(
                    self._process_raw_result(raw, url, content_type, is_pdf, query)
                )

        processed = await asyncio.gather(*tasks, return_exceptions=True)
        items: List[Dict[str, Any]] = []
        for item in processed:
            if isinstance(item, Exception):
                logger.debug(f"Processing error: {item}")
            elif item is not None:
                items.append(item)
        return items

    async def _process_raw_result(
        self,
        raw:          Dict[str, Any],
        url:          str,
        content_type: ContentType,
        is_pdf:       bool = False,
        query:        str  = "",
    ) -> Optional[Dict[str, Any]]:
        try:
            if cfg.BIOMEDICAL_DOMAIN_FILTER and content_type not in (
                ContentType.IMAGE, ContentType.VIDEO
            ):
                try:
                    domain = urlparse(url).netloc.lower().replace("www.", "")
                except Exception:
                    domain = ""
                if _domain_is_blocked(domain):
                    logger.debug(f"Domain pre-filter: dropping {domain}")
                    return None

            if is_pdf:
                pdf_data = await self._extract_pdf(url)
                if pdf_data:
                    if query and not _content_is_biomedically_relevant(
                        pdf_data.get("content", ""), query
                    ):
                        logger.debug(f"Biomedical pre-filter: dropping PDF {url}")
                        return None
                    pdf_data["content_type"]   = ContentType.PDF.value
                    pdf_data["pmid"]           = raw.get("pmid")
                    pdf_data["doi"]            = raw.get("doi")
                    pdf_data["citation_count"] = raw.get("citation_count")
                    return pdf_data

            elif content_type == ContentType.IMAGE:
                img_bytes: Optional[bytes] = None
                try:
                    sess = await self._get_session()
                    async with sess.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                        if r.status == 200:
                            ct_header = r.headers.get("Content-Type", "")
                            if "image/" in ct_header:
                                img_bytes = await r.read()
                            else:
                                logger.debug(
                                    f"Skipping non-image Content-Type '{ct_header}' for {url}"
                                )
                except Exception as exc:
                    logger.debug(f"Image fetch error for {url}: {exc}")

                return {
                    "url":          url,
                    "content":      raw.get("title", url),
                    "content_type": ContentType.IMAGE.value,
                    "title":        raw.get("title", ""),
                    "image_bytes":  img_bytes,
                    "metadata": {
                        "format":  url.split(".")[-1][:4],
                        "caption": raw.get("content", ""),
                    },
                }

            else:
                extracted_content = await self._extract_content_race(url)
                content = extracted_content or raw.get("content", raw.get("body", ""))
                if not content:
                    return None

                if query and not _content_is_biomedically_relevant(content, query):
                    logger.debug(f"Biomedical pre-filter: dropping {url}")
                    return None

                return {
                    "url":            url,
                    "content":        content,
                    "content_type":   content_type.value,
                    "title":          raw.get("title", ""),
                    "pmid":           raw.get("pmid"),
                    "doi":            raw.get("doi"),
                    "citation_count": raw.get("citation_count"),
                }

        except Exception as exc:
            logger.debug(f"_process_raw_result error for {url}: {exc}")
            return None


# =============================================================================
# VALIDATOR AGENT
# =============================================================================

class ValidatorAgent:
    def __init__(self, embed_service: EmbeddingService):
        self._embed           = embed_service
        self._nli_model:      Optional[CrossEncoder] = None
        self._nli_num_labels: Optional[int]          = None
        self._biomed_entity_re = _BIOMEDICAL_RE

    def _get_nli_model(self) -> CrossEncoder:
        if self._nli_model is None:
            self._nli_model = CrossEncoder(cfg.NLI_MODEL)
        return self._nli_model

    def _get_nli_num_labels(self) -> int:
        if self._nli_num_labels is None:
            model = self._get_nli_model()
            try:
                self._nli_num_labels = model.model.config.num_labels
            except AttributeError:
                self._nli_num_labels = 3
            logger.debug(f"NLI model num_labels={self._nli_num_labels}")
        return self._nli_num_labels

    def _shares_biomedical_context(self, s1: str, s2: str) -> bool:
        e1 = set(self._biomed_entity_re.findall(s1.lower()))
        e2 = set(self._biomed_entity_re.findall(s2.lower()))
        return bool(e1 & e2)

    @staticmethod
    def _compute_domain_trust(url: str) -> float:
        try:
            domain = urlparse(url).netloc.lower().replace("www.", "")
        except Exception:
            return 0.30
        if any(td in domain for td in cfg.TRUSTED_DOMAINS):
            return 0.95
        if re.search(r"\.(edu|gov|ac\.[a-z]{2}|org)$", domain):
            return 0.80
        if re.search(r"(preprint|arxiv|biorxiv|medrxiv)", domain):
            return 0.75
        if re.search(r"\.(com|net|io)$", domain):
            return 0.50
        return 0.40

    @staticmethod
    def _citation_boost(citation_count: Optional[int]) -> float:
        if citation_count is None or citation_count <= 0:
            return 0.0
        return min(1.0, np.log1p(citation_count) / np.log1p(1000))

    @staticmethod
    def _blended_credibility(domain_trust: float, citation_count: Optional[int]) -> float:
        """
        When citation_count is absent (None), return domain_trust directly.
        Only blend when we have real citation data.
        """
        if citation_count is None:
            return domain_trust
        boost = ValidatorAgent._citation_boost(citation_count)
        return 0.70 * domain_trust + 0.30 * boost

    @staticmethod
    def _adaptive_relevance_threshold(query: str, content: str) -> float:
        """
        Scale the cosine-similarity threshold based on query length and
        content length.

        FIX-RELEVANCE-FLOOR: base raised 0.42 → 0.45, floor raised 0.28 → 0.32
        to reduce low-quality short-abstract pass-through.
        """
        base       = cfg.RELEVANCE_THRESHOLD_BASE
        word_count = len(query.split())
        if word_count > 5:
            base -= 0.02 * min(word_count - 5, 5)
        if len(content) < 300:
            base -= 0.03
        return max(cfg.RELEVANCE_THRESHOLD_FLOOR, base)

    async def _compute_faithfulness(
        self, query: str, relevant_items: List[Dict[str, Any]]
    ) -> float:
        """
        FIX-FAITHFULNESS: use Groq to score factual faithfulness for the top-3
        items, then fall back to NLI-based query-coverage for the remainder.
        This gives a more accurate signal than NLI alone while keeping latency
        bounded by only running Groq on 3 items.
        """
        if not relevant_items:
            return 0.0

        groq          = self._embed.groq
        top_items     = relevant_items[:3]
        rest_items    = relevant_items[3:10]
        groq_scores: List[float] = []

        # Groq-based faithfulness for top 3
        for item in top_items:
            score = await groq.verify_faithfulness(query, item.get("content", ""))
            groq_scores.append(score)

        # NLI-based query coverage for remaining items
        query_concepts = [q.strip() for q in re.split(r"[,;]|\band\b", query) if q.strip()]
        if not query_concepts:
            query_concepts = [query[:200]]

        nli        = self._get_nli_model()
        num_labels = self._get_nli_num_labels()
        loop       = asyncio.get_running_loop()

        nli_covered = 0
        for item in rest_items:
            content   = item.get("content", "")
            sentences = [s.strip() for s in re.split(r"[.!?]", content) if len(s.strip()) > 20][:5]
            if not sentences:
                continue

            pairs = [(sent, concept) for sent in sentences for concept in query_concepts]
            if not pairs:
                continue

            try:
                raw_scores = await loop.run_in_executor(None, nli.predict, pairs)
                # FIX-SOFTMAX: apply softmax before thresholding NLI logits
                scores_arr = scipy_softmax(np.array(raw_scores), axis=-1)
                if num_labels == 3:
                    entailment_scores = (
                        scores_arr[:, 2] if scores_arr.ndim == 2 else scores_arr
                    )
                    if np.any(entailment_scores > 0.65):
                        nli_covered += 1
                else:
                    if np.any(scores_arr.flatten() > 0.60):
                        nli_covered += 1
            except Exception as exc:
                logger.debug(f"NLI query-coverage check failed: {exc}")
                continue

        total_items  = len(top_items) + max(len(rest_items), 1)
        nli_coverage = nli_covered / max(len(rest_items), 1) if rest_items else 0.0
        groq_avg     = float(np.mean(groq_scores)) if groq_scores else 0.5

        # Blend: weight Groq scores more heavily (they are more reliable)
        n_groq = len(groq_scores)
        n_nli  = len(rest_items)
        if n_groq + n_nli == 0:
            return 0.0
        blended = (n_groq * groq_avg + n_nli * nli_coverage) / (n_groq + n_nli)
        return round(blended, 4)

    async def _semantic_dedup(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(items) <= 1:
            return items

        embeddings: List[Optional[List[float]]] = []
        for item in items:
            emb = await self._embed.embed_text_safe(item["content"][:1000])
            embeddings.append(emb)

        kept_indices: List[int] = []
        excl:         Set[int]  = set()

        for i in range(len(items)):
            if i in excl or embeddings[i] is None:
                continue
            kept_indices.append(i)
            ctype_i  = items[i].get("content_type", "text")
            thresh_i = cfg.DEDUP_COSINE_THRESHOLD.get(ctype_i, 0.92)
            for j in range(i + 1, len(items)):
                if j in excl or embeddings[j] is None:
                    continue
                sim = float(
                    cosine_similarity(
                        np.array(embeddings[i]).reshape(1, -1),
                        np.array(embeddings[j]).reshape(1, -1),
                    )[0][0]
                )
                if sim > thresh_i:
                    ti = self._compute_domain_trust(items[i].get("url", ""))
                    tj = self._compute_domain_trust(items[j].get("url", ""))
                    if tj > ti:
                        kept_indices[-1] = j
                        excl.add(i)
                        i        = j
                        ctype_i  = items[j].get("content_type", "text")
                        thresh_i = cfg.DEDUP_COSINE_THRESHOLD.get(ctype_i, 0.92)
                    else:
                        excl.add(j)

        final_indices: List[int] = []
        final_excl:    Set[int]  = set()

        for idx_a in range(len(kept_indices)):
            ia = kept_indices[idx_a]
            if ia in final_excl or embeddings[ia] is None:
                continue
            final_indices.append(ia)
            ctype_a  = items[ia].get("content_type", "text")
            thresh_a = cfg.DEDUP_COSINE_THRESHOLD.get(ctype_a, 0.92)
            for idx_b in range(idx_a + 1, len(kept_indices)):
                ib = kept_indices[idx_b]
                if ib in final_excl or embeddings[ib] is None:
                    continue
                sim = float(
                    cosine_similarity(
                        np.array(embeddings[ia]).reshape(1, -1),
                        np.array(embeddings[ib]).reshape(1, -1),
                    )[0][0]
                )
                if sim > thresh_a:
                    ta = self._compute_domain_trust(items[ia].get("url", ""))
                    tb = self._compute_domain_trust(items[ib].get("url", ""))
                    if tb > ta:
                        final_indices[-1] = ib
                        final_excl.add(ia)
                        ia       = ib
                        ctype_a  = items[ib].get("content_type", "text")
                        thresh_a = cfg.DEDUP_COSINE_THRESHOLD.get(ctype_a, 0.92)
                    else:
                        final_excl.add(ib)

        deduped = [items[k] for k in final_indices]
        logger.debug(
            f"Dedup (2-pass): {len(items)} → pass1={len(kept_indices)} → "
            f"pass2={len(deduped)} items"
        )
        return deduped

    async def _compute_contradiction_rate(self, items: List[Dict[str, Any]]) -> float:
        """
        FIX-SOFTMAX: NLI raw logits are passed through scipy softmax before
        threshold comparison.  In v3.3, raw logit values (e.g. 4.3) were being
        compared against CONTRADICTION_THRESHOLD_3L=0.55 — this caused massive
        false positives since unnormalized logits routinely exceed 1.0.

        After softmax the contradiction label probability is properly bounded
        in [0, 1], making the threshold meaningful.
        """
        if len(items) < 2:
            return 0.0

        sample = items[:8]
        pairs: List[Tuple[str, str]]     = []
        pair_meta: List[Tuple[str, str]] = []

        for i in range(len(sample)):
            for j in range(i + 1, len(sample)):
                s1 = sample[i]["content"][:512]
                s2 = sample[j]["content"][:512]
                if self._shares_biomedical_context(s1, s2):
                    pairs.append((s1, s2))
                    pair_meta.append((
                        sample[i].get("url", f"item_{i}"),
                        sample[j].get("url", f"item_{j}"),
                    ))
        if not pairs:
            return 0.0

        try:
            nli        = self._get_nli_model()
            num_labels = self._get_nli_num_labels()
            loop       = asyncio.get_running_loop()
            raw_scores = await loop.run_in_executor(None, nli.predict, pairs)

            # FIX-SOFTMAX: normalize logits to probabilities before thresholding
            scores_arr = scipy_softmax(np.array(raw_scores), axis=-1)

            if num_labels == 3:
                flags = [
                    bool(np.argmax(row) == 0 and row[0] > cfg.CONTRADICTION_THRESHOLD_3L)
                    for row in scores_arr
                ]
                for k, (flag, row) in enumerate(zip(flags, scores_arr)):
                    if flag:
                        url_a, url_b = pair_meta[k]
                        logger.debug(
                            f"Contradiction detected (post-softmax): "
                            f"p_contra={row[0]:.3f} | "
                            f"a={url_a[:60]} | b={url_b[:60]}"
                        )
            else:
                flags = [
                    bool(s > cfg.CONTRADICTION_THRESHOLD_1L)
                    for s in scores_arr.flatten()
                ]
                for k, (flag, score) in enumerate(zip(flags, scores_arr.flatten())):
                    if flag:
                        url_a, url_b = pair_meta[k]
                        logger.debug(
                            f"Contradiction detected (post-softmax): "
                            f"score={score:.3f} | "
                            f"a={url_a[:60]} | b={url_b[:60]}"
                        )

            rate = sum(flags) / len(flags)
            logger.debug(
                f"NLI ({num_labels}-label) contradiction: "
                f"{sum(flags)}/{len(pairs)} pairs → rate={rate:.3f}"
            )
            return rate
        except Exception as exc:
            logger.warning(f"NLI contradiction check failed: {exc} — assuming 0.0")
            return 0.0

    async def validate(
        self, raw_items: List[Dict[str, Any]], query: str
    ) -> Tuple[List[ValidatedItem], ValidationMetrics]:
        if not raw_items:
            return [], ValidationMetrics()

        for item in raw_items:
            item["_domain_trust"] = self._compute_domain_trust(item.get("url", ""))

        deduped    = await self._semantic_dedup(raw_items)
        dedup_rate = 1.0 - (len(deduped) / max(len(raw_items), 1))

        query_emb_raw = await self._embed.embed_text_safe(query)
        if query_emb_raw is None:
            logger.warning("Query embedding failed — returning empty validation")
            return [], ValidationMetrics(dedup_rate=dedup_rate)

        scored_items = []
        for item in deduped:
            content = item.get("content", "")[:2000]
            if not content.strip():
                continue
            content_emb = await self._embed.embed_text_safe(content)
            if content_emb is None:
                continue
            q = np.array(query_emb_raw).reshape(1, -1)
            d = np.array(content_emb).reshape(1, -1)
            item["_relevance"] = float(cosine_similarity(q, d)[0][0])
            scored_items.append(item)

        relevant_items = [
            i for i in scored_items
            if i.get("_relevance", 0) >= self._adaptive_relevance_threshold(
                query, i.get("content", "")
            )
        ]

        if not relevant_items:
            return [], ValidationMetrics(dedup_rate=dedup_rate)

        avg_credibility = float(np.mean([
            self._blended_credibility(i["_domain_trust"], i.get("citation_count"))
            for i in relevant_items
        ]))
        avg_relevance = float(np.mean([i["_relevance"] for i in relevant_items]))

        contradiction_rate, faithfulness = await asyncio.gather(
            self._compute_contradiction_rate(relevant_items),
            self._compute_faithfulness(query, relevant_items),
        )

        metrics = ValidationMetrics(
            faithfulness       = faithfulness,
            answer_relevancy   = avg_relevance,
            context_recall     = min(1.0, len(relevant_items) / max(10, len(raw_items)) * 1.2),
            context_precision  = len(relevant_items) / max(len(scored_items), 1),
            source_credibility = avg_credibility,
            contradiction_rate = contradiction_rate,
            dedup_rate         = dedup_rate,
            g_eval             = 0.0,
        )

        logger.info(
            f"Validation SGV={metrics.sgv:.3f} | items={len(relevant_items)} | "
            f"faithfulness={metrics.faithfulness:.3f} | "
            f"relevancy={metrics.answer_relevancy:.3f} | "
            f"credibility={metrics.source_credibility:.3f} | "
            f"contradiction_rate={metrics.contradiction_rate:.3f}"
        )

        if not metrics.is_valid():
            logger.warning(
                f"SGV {metrics.sgv:.3f} < {cfg.SGV_MIN} — data rejected, "
                f"will trigger semantic sub-query decomposition"
            )
            return [], metrics

        now_iso   = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        validated = []
        for item in relevant_items:
            try:
                ctype_str = item.get("content_type", ContentType.TEXT.value)
                ctype     = ContentType(ctype_str) if isinstance(ctype_str, str) else ctype_str
                validated.append(
                    ValidatedItem(
                        content          = item.get("content", ""),
                        content_type     = ctype,
                        source_url       = item.get("url", ""),
                        title            = item.get("title", ""),
                        language         = item.get("language", "en"),
                        date_collected   = now_iso,
                        validation_score = round(metrics.sgv, 4),
                        domain_trust     = round(item["_domain_trust"], 4),
                        metadata         = item.get("metadata", {}),
                        relevance_score  = round(item.get("_relevance", 0.0), 4),
                        image_bytes      = item.get("image_bytes"),
                        pmid             = item.get("pmid"),
                        doi              = item.get("doi"),
                        citation_count   = item.get("citation_count"),
                    )
                )
            except Exception as exc:
                logger.debug(f"ValidatedItem construction error: {exc}")
                continue

        return validated, metrics


# =============================================================================
# VECTORIZER AGENT
# =============================================================================

class VectorizerAgent:
    def __init__(self, embed_service: EmbeddingService):
        self._embed         = embed_service
        self._text_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
        self._section_re = re.compile(
            r"^\s*(?:" + "|".join(cfg.PDF_SECTION_HEADERS) + r")\s*$",
            re.IGNORECASE | re.MULTILINE,
        )

    async def vectorize(self, items: List[ValidatedItem], session_id: str) -> List[PointStruct]:
        tasks      = [self._vectorize_item(item, session_id) for item in items]
        results    = await asyncio.gather(*tasks, return_exceptions=True)
        all_points: List[PointStruct] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Vectorization skipped (embedding error): {r}")
            else:
                all_points.extend(r)
        logger.info(f"Vectorized {len(all_points)} points from {len(items)} items")
        return all_points

    async def _vectorize_item(self, item: ValidatedItem, session_id: str) -> List[PointStruct]:
        if item.content_type == ContentType.TABLE:
            return await self._vectorize_table(item, session_id)
        elif item.content_type in (ContentType.IMAGE, ContentType.GRAPH):
            return await self._vectorize_image(item, session_id)
        elif item.content_type == ContentType.PDF:
            return await self._vectorize_pdf(item, session_id)
        elif item.content_type == ContentType.CODE:
            return await self._vectorize_code(item, session_id)
        else:
            return await self._vectorize_text(item, session_id)

    def _base_payload(
        self, item: ValidatedItem, session_id: str, chunk_index: int = 0
    ) -> Dict[str, Any]:
        dt = datetime.fromisoformat(item.date_collected.replace("Z", "+00:00"))
        payload: Dict[str, Any] = {
            "source_url":        item.source_url,
            "content_type":      item.content_type.value,
            "language":          item.language,
            "date_collected":    item.date_collected,
            "date_collected_ts": dt.timestamp(),
            "validation_score":  item.validation_score,
            "domain_trust":      item.domain_trust,
            "chunk_index":       chunk_index,
            "session_id":        session_id,
            "title":             item.title,
            "content_preview":   item.content[:200],
        }
        if item.pmid is not None:
            payload["pmid"] = item.pmid
        if item.doi is not None:
            payload["doi"] = item.doi
        if item.citation_count is not None:
            payload["citation_count"] = item.citation_count
        return payload

    def _split_pdf_sections(self, text: str) -> List[str]:
        header_positions = [m.start() for m in self._section_re.finditer(text)]
        if len(header_positions) < 2:
            return self._split_text_llama(text)

        chunks: List[str] = []
        for i, start in enumerate(header_positions):
            end   = header_positions[i + 1] if i + 1 < len(header_positions) else len(text)
            chunk = text[start:end].strip()
            if len(chunk) > 50:
                if len(chunk.split()) > 600:
                    sub_chunks = self._split_text_llama(chunk)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(chunk)
        return chunks if chunks else self._split_text_llama(text)

    def _split_text_llama(self, text: str) -> List[str]:
        try:
            from llama_index.core.schema import Document
            doc    = Document(text=text)
            nodes  = self._text_splitter.get_nodes_from_documents([doc])
            chunks = [n.get_content() for n in nodes if n.get_content().strip()]
            return chunks if chunks else [text[:3072]]
        except Exception:
            return self._split_text_words(text)

    @staticmethod
    def _split_text_words(text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        words  = text.split()
        step   = max(1, chunk_size - overlap)
        chunks = [
            " ".join(words[i : i + chunk_size])
            for i in range(0, len(words), step)
            if words[i : i + chunk_size]
        ]
        return chunks or [text[: chunk_size * 6]]

    async def _vectorize_text(self, item: ValidatedItem, session_id: str) -> List[PointStruct]:
        chunks = self._split_text_llama(item.content)
        points = []
        for idx, chunk in enumerate(chunks):
            emb              = await self._embed.embed_text(chunk)
            payload          = self._base_payload(item, session_id, idx)
            payload["content"] = chunk
            points.append(PointStruct(id=str(uuid.uuid4()), vector=emb, payload=payload))
        return points

    async def _vectorize_pdf(self, item: ValidatedItem, session_id: str) -> List[PointStruct]:
        chunks = self._split_pdf_sections(item.content)
        points = []
        for idx, chunk in enumerate(chunks):
            emb              = await self._embed.embed_text(chunk)
            payload          = self._base_payload(item, session_id, idx)
            payload["content"] = chunk
            if idx == 0:
                payload["summary"] = await self._embed.summarize_text(chunk, max_words=80)
            points.append(PointStruct(id=str(uuid.uuid4()), vector=emb, payload=payload))
        return points

    async def _vectorize_image(self, item: ValidatedItem, session_id: str) -> List[PointStruct]:
        if item.image_bytes:
            emb     = await self._embed.embed_image_bytes(item.image_bytes)
            caption = item.metadata.get("caption", item.content)
        else:
            async with aiohttp.ClientSession() as sess:
                caption = (
                    item.metadata.get("caption")
                    or await self._embed.generate_caption_for_image(item.source_url, sess)
                )
            emb = await self._embed.embed_image_caption(caption)

        payload              = self._base_payload(item, session_id, 0)
        payload["caption"]   = caption
        payload["image_url"] = item.source_url
        payload["format"]    = item.metadata.get("format", "")
        return [PointStruct(id=str(uuid.uuid4()), vector=emb, payload=payload)]

    async def _vectorize_table(self, item: ValidatedItem, session_id: str) -> List[PointStruct]:
        lines  = item.content.split("\n")
        header = lines[0] if lines else ""
        chunks = [
            f"Header: {header}\nRows:\n" + "\n".join(lines[i : i + 5])
            for i in range(1, len(lines), 5)
        ] or [item.content]
        points = []
        for idx, chunk in enumerate(chunks):
            emb              = await self._embed.embed_table(chunk)
            payload          = self._base_payload(item, session_id, idx)
            payload["content"] = chunk
            points.append(PointStruct(id=str(uuid.uuid4()), vector=emb, payload=payload))
        return points

    async def _vectorize_code(self, item: ValidatedItem, session_id: str) -> List[PointStruct]:
        import ast as _ast
        chunks: List[str] = []
        try:
            tree = _ast.parse(item.content)
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                    start = node.lineno - 1
                    end   = getattr(node, "end_lineno", start + 20)
                    chunk = "\n".join(item.content.split("\n")[start:end])
                    if chunk.strip():
                        chunks.append(chunk)
        except SyntaxError:
            chunks = self._split_text_llama(item.content)

        chunks = chunks or [item.content[:2000]]
        points = []
        for idx, chunk in enumerate(chunks):
            emb              = await self._embed.embed_text(chunk)
            payload          = self._base_payload(item, session_id, idx)
            payload["content"] = chunk
            points.append(PointStruct(id=str(uuid.uuid4()), vector=emb, payload=payload))
        return points


# =============================================================================
# RETRIEVER AGENT
# =============================================================================

class RetrieverAgent:
    def __init__(
        self,
        qdrant_mgr:    QdrantCollectionManager,
        embed_service: EmbeddingService,
        redis_client:  Optional[aioredis.Redis] = None,
    ):
        self._qdrant    = qdrant_mgr
        self._embed     = embed_service
        self._redis:    Optional[aioredis.Redis] = redis_client
        self._reranker: Optional[CrossEncoder] = None
        self._bm25_indices: Dict[str, BM25Index] = {
            name: BM25Index() for name in cfg.COLLECTIONS
        }

    def set_redis(self, redis_client: Optional[aioredis.Redis]) -> None:
        self._redis = redis_client

    def _get_reranker(self) -> CrossEncoder:
        if self._reranker is None:
            try:
                self._reranker = CrossEncoder(cfg.CROSS_ENCODER_MODEL)
                logger.info(f"Reranker loaded: {cfg.CROSS_ENCODER_MODEL}")
            except Exception as exc:
                logger.warning(
                    f"Failed to load {cfg.CROSS_ENCODER_MODEL}: {exc} — "
                    f"falling back to {cfg.CROSS_ENCODER_MODEL_FALLBACK}"
                )
                self._reranker = CrossEncoder(cfg.CROSS_ENCODER_MODEL_FALLBACK)
        return self._reranker

    @staticmethod
    def _build_payload_filter(filters: Dict[str, Any]) -> Optional[Filter]:
        conditions = []
        if "lang" in filters:
            conditions.append(
                FieldCondition(key="language", match=MatchValue(value=filters["lang"]))
            )
        if "score_min" in filters:
            conditions.append(
                FieldCondition(key="validation_score", range=Range(gte=filters["score_min"]))
            )
        if "content_type" in filters:
            conditions.append(
                FieldCondition(
                    key="content_type", match=MatchValue(value=filters["content_type"])
                )
            )
        if "domain" in filters:
            conditions.append(
                FieldCondition(key="source_url", match=MatchValue(value=filters["domain"]))
            )
        if "freshness_days" in filters:
            limit_dt = datetime.now(timezone.utc) - timedelta(
                days=int(filters["freshness_days"])
            )
            conditions.append(
                FieldCondition(
                    key="date_collected_ts", range=Range(gte=limit_dt.timestamp())
                )
            )
        return Filter(must=conditions) if conditions else None

    @staticmethod
    def _filter_content_types_for_query(
        query: str, requested_types: List[ContentType]
    ) -> List[ContentType]:
        """
        For biomedical text queries, skip image/video collections unless the
        query explicitly references a visual artefact.
        Includes 'network' and 'visualization' keywords (FIX-VISUAL-KW from v3.3).
        """
        visual_keywords = re.compile(
            r'\b(figure|image|photo|picture|graph|chart|visualization|network|'
            r'micrograph|stain|flow\s*cytometry|western\s*blot|MRI|CT\s*scan)\b',
            re.I,
        )
        if not visual_keywords.search(query):
            return [
                ct for ct in requested_types
                if ct not in (ContentType.IMAGE, ContentType.VIDEO)
            ] or requested_types
        return requested_types

    @staticmethod
    def _rrf_fusion(
        dense:  List[Dict[str, Any]],
        sparse: List[Dict[str, Any]],
        k:      float = cfg.RRF_K,
    ) -> List[Dict[str, Any]]:
        scores:    Dict[str, float]          = {}
        all_items: Dict[str, Dict[str, Any]] = {}

        for rank, item in enumerate(dense):
            did            = item["id"]
            scores[did]    = scores.get(did, 0.0) + 1.0 / (k + rank + 1)
            all_items[did] = item

        for rank, item in enumerate(sparse):
            did            = item["id"]
            scores[did]    = scores.get(did, 0.0) + 1.0 / (k + rank + 1)
            all_items[did] = item

        fused = []
        for did in sorted(scores, key=scores.__getitem__, reverse=True):
            item              = all_items[did].copy()
            item["score"]     = scores[did]
            item["rrf_score"] = scores[did]
            fused.append(item)
        return fused

    def _bm25_rerank(
        self, query: str, results: List[Dict[str, Any]], collection_name: str
    ) -> List[Dict[str, Any]]:
        if not results:
            return results

        bm25 = self._bm25_indices.get(collection_name, BM25Index())
        batch_docs = [
            r["payload"].get("content", r["payload"].get("content_preview", ""))
            for r in results
        ]
        bm25.add_documents(batch_docs)
        bm25_scores = bm25.score_subset(query, batch_docs)

        reranked = []
        for i, r in enumerate(results):
            r               = r.copy()
            r["bm25_score"] = float(bm25_scores[i]) if i < len(bm25_scores) else 0.0
            reranked.append(r)
        reranked.sort(key=lambda x: x["bm25_score"], reverse=True)
        return reranked

    # ── CE score cache helpers ─────────────────────────────────────────────────
    @staticmethod
    def _ce_cache_key(query: str, content: str) -> str:
        combined = f"{query}|||{content[:400]}"
        return f"ce:{hashlib.md5(combined.encode()).hexdigest()}"

    async def _ce_scores_from_cache(
        self, query: str, contents: List[str]
    ) -> Dict[int, float]:
        if self._redis is None:
            return {}
        hits: Dict[int, float] = {}
        try:
            keys   = [self._ce_cache_key(query, c) for c in contents]
            values = await self._redis.mget(*keys)
            for idx, val in enumerate(values):
                if val is not None:
                    try:
                        hits[idx] = float(val)
                    except ValueError:
                        pass
        except Exception as exc:
            logger.debug(f"CE cache read error: {exc}")
        return hits

    async def _ce_scores_to_cache(
        self, query: str, contents: List[str], scores: List[float]
    ) -> None:
        if self._redis is None:
            return
        try:
            pipe = self._redis.pipeline()
            for content, score in zip(contents, scores):
                key = self._ce_cache_key(query, content)
                pipe.set(key, str(score), ex=cfg.CE_CACHE_TTL_SECONDS)
            await pipe.execute()
        except Exception as exc:
            logger.debug(f"CE cache write error: {exc}")

    async def _cross_encoder_rerank(
        self,
        query:   str,
        results: List[Dict[str, Any]],
        top_n:   int = cfg.TOP_K_RERANK,
    ) -> List[Dict[str, Any]]:
        """
        FIX-CE-CACHE: cross-encoder scores cached in Redis.
        FIX-CE-BATCH: uncached pairs are submitted as a single batch to
        reranker.predict(), which is already the correct usage — now
        explicitly documented and verified.
        """
        if not results:
            return []
        candidates = results[: cfg.CE_MAX_CANDIDATES]
        contents   = [
            r["payload"].get("content", r["payload"].get("content_preview", ""))
            for r in candidates
        ]

        try:
            reranker = self._get_reranker()

            cached_scores = await self._ce_scores_from_cache(query, contents)
            uncached_indices = [i for i in range(len(candidates)) if i not in cached_scores]

            if uncached_indices:
                # Single batch call — more efficient than iterating
                uncached_pairs = [(query, contents[i]) for i in uncached_indices]
                loop           = asyncio.get_running_loop()
                new_scores     = await loop.run_in_executor(
                    None, reranker.predict, uncached_pairs
                )
                await self._ce_scores_to_cache(
                    query,
                    [contents[i] for i in uncached_indices],
                    [float(s) for s in new_scores],
                )
                for idx, score in zip(uncached_indices, new_scores):
                    cached_scores[idx] = float(score)

                logger.debug(
                    f"CE rerank: {len(uncached_indices)} inferred, "
                    f"{len(candidates) - len(uncached_indices)} from cache"
                )
            else:
                logger.debug(f"CE rerank: all {len(candidates)} scores from cache")

            for i, candidate in enumerate(candidates):
                candidate["ce_score"] = cached_scores.get(i, 0.0)

            candidates.sort(key=lambda x: x.get("ce_score", 0), reverse=True)
            return candidates[:top_n]

        except Exception as exc:
            logger.warning(f"Cross-encoder reranking failed: {exc} — falling back to dense scores")
            return sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )[:top_n]

    async def _mmr_filter(
        self,
        query_emb:      List[float],
        results:        List[Dict[str, Any]],
        lam:            float = cfg.MMR_LAMBDA,
        fetch_k:        int   = 20,
        requested_types: Optional[List[ContentType]] = None,
    ) -> List[Dict[str, Any]]:
        """
        FIX-TYPE-DIVERSITY: guarantee at least one result per requested
        content type before filling remaining slots with MMR selection.
        This prevents multimodal queries from collapsing to text-only output
        when text results dominate the CE reranker scores.
        """
        candidates = results[:fetch_k]
        if len(candidates) <= 1:
            return candidates

        embs: List[Optional[List[float]]] = []
        for r in candidates:
            content = r["payload"].get("content", r["payload"].get("content_preview", ""))
            emb     = await self._embed.embed_text_safe(content[:400])
            embs.append(emb)

        q_arr         = np.array(query_emb).reshape(1, -1)
        valid_mask    = [e is not None for e in embs]
        emb_mat       = np.array([e for e in embs if e is not None])
        valid_indices = [i for i, v in enumerate(valid_mask) if v]

        if len(valid_indices) == 0:
            return candidates[: cfg.TOP_K_RERANK]

        rel_scores = cosine_similarity(q_arr, emb_mat).flatten()

        # FIX-TYPE-DIVERSITY: seed selection with one best result per type
        type_seed_indices: List[int] = []
        if requested_types:
            seen_types: Set[str] = set()
            # Sort valid candidates by relevance score descending
            sorted_vi = sorted(valid_indices, key=lambda i: rel_scores[valid_indices.index(i)], reverse=True)
            for vi in sorted_vi:
                ctype = candidates[vi]["payload"].get("content_type", "text")
                if ctype not in seen_types and ContentType(ctype) in requested_types:
                    type_seed_indices.append(valid_indices.index(vi))
                    seen_types.add(ctype)
            # Deduplicate while preserving order
            type_seed_indices = list(dict.fromkeys(type_seed_indices))

        selected_local:  List[int] = list(type_seed_indices)
        remaining_local: List[int] = [
            i for i in range(len(valid_indices)) if i not in selected_local
        ]

        while remaining_local and len(selected_local) < cfg.TOP_K_RERANK:
            if not selected_local:
                best = max(remaining_local, key=lambda i: rel_scores[i])
            else:
                sel_embs = emb_mat[selected_local]
                best     = -1
                best_mmr = -float("inf")
                for i in remaining_local:
                    red = float(
                        cosine_similarity(emb_mat[i].reshape(1, -1), sel_embs).max()
                    )
                    mmr = lam * rel_scores[i] - (1 - lam) * red
                    if mmr > best_mmr:
                        best_mmr = mmr
                        best     = i
                if best == -1:
                    break

            selected_local.append(best)
            remaining_local.remove(best)

        return [candidates[valid_indices[i]] for i in selected_local]

    async def retrieve(
        self,
        query:         str,
        content_types: List[ContentType],
        filters:       Dict[str, Any],
        top_k:         int  = cfg.TOP_K_DENSE,
        use_hyde:      bool = True,
    ) -> Tuple[List[Dict[str, Any]], int]:
        effective_types = self._filter_content_types_for_query(query, content_types)

        if use_hyde:
            try:
                query_emb = await self._embed.embed_query_with_hyde(query)
            except Exception as exc:
                logger.warning(f"HyDE failed, using plain query embedding: {exc}")
                query_emb_raw = await self._embed.embed_text_safe(query)
                if query_emb_raw is None:
                    return [], 0
                query_emb = query_emb_raw
        else:
            query_emb_raw = await self._embed.embed_text_safe(query)
            if query_emb_raw is None:
                logger.warning("Query embedding failed — returning empty retrieval")
                return [], 0
            query_emb = query_emb_raw

        effective_filters = dict(filters)
        if "freshness_days" not in effective_filters:
            effective_filters["freshness_days"] = cfg.DATA_FRESHNESS_DAYS

        payload_filter = self._build_payload_filter(effective_filters)

        dense_tasks = []
        for ctype in effective_types:
            collection = self._qdrant.collection_for_type(ctype)
            if ctype == ContentType.TABLE:
                try:
                    qemb = await self._embed.embed_table(query)
                except ValueError:
                    qemb = query_emb
            elif ctype in (ContentType.IMAGE, ContentType.GRAPH):
                try:
                    qemb = await self._embed.embed_image_caption(query)
                except ValueError:
                    qemb = query_emb
            else:
                qemb = query_emb
            dense_tasks.append(
                self._qdrant.hybrid_search(qemb, collection, top_k, payload_filter)
            )

        dense_nested  = await asyncio.gather(*dense_tasks, return_exceptions=True)
        dense_results: List[Dict[str, Any]] = []
        for r in dense_nested:
            if not isinstance(r, Exception):
                dense_results.extend(r)
            else:
                logger.warning(f"Dense search error: {r}")

        raw_dense_count = len(dense_results)
        if not dense_results:
            return [], 0

        primary_collection = self._qdrant.collection_for_type(effective_types[0])
        sparse_results = self._bm25_rerank(query, dense_results, primary_collection)

        fused    = self._rrf_fusion(dense_results, sparse_results)
        reranked = await self._cross_encoder_rerank(
            query, fused, top_n=min(cfg.TOP_K_RERANK, top_k)
        )
        # FIX-TYPE-DIVERSITY: pass requested types so MMR preserves type coverage
        diverse  = await self._mmr_filter(
            query_emb, reranked, requested_types=effective_types
        )

        logger.info(
            f"Retrieval: dense={len(dense_results)} → fused={len(fused)} → "
            f"reranked={len(reranked)} → mmr={len(diverse)}"
        )
        return diverse, raw_dense_count


# =============================================================================
# CACHE LAYER
# =============================================================================

class CacheLayer:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    @property
    def redis(self) -> Optional[aioredis.Redis]:
        return self._redis

    async def connect(self):
        try:
            self._redis = aioredis.Redis(
                host=cfg.REDIS_HOST,
                port=cfg.REDIS_PORT,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info(f"Redis cache connected ({cfg.REDIS_HOST}:{cfg.REDIS_PORT})")
        except Exception as exc:
            logger.warning(f"Redis unavailable ({exc}) — cache disabled")
            self._redis = None

    def _make_key(
        self, query: str, data_types: List[ContentType], filters: Dict[str, Any]
    ) -> str:
        raw = json.dumps(
            {"q": query, "t": [t.value for t in data_types], "f": filters},
            sort_keys=True,
        )
        return f"itda:{hashlib.md5(raw.encode()).hexdigest()}"

    async def get(
        self, query: str, data_types: List[ContentType], filters: Dict[str, Any]
    ) -> Optional[Tuple[List[Dict[str, Any]], float]]:
        if not self._redis:
            return None
        try:
            key    = self._make_key(query, data_types, filters)
            cached = await self._redis.get(key)
            if cached:
                logger.debug(f"Cache HIT key={key[:20]}…")
                envelope = json.loads(cached)
                if isinstance(envelope, list):
                    return envelope, 0.90
                data = envelope.get("data", [])
                sgv  = envelope.get("sgv", 0.90)
                return data, sgv
        except Exception as exc:
            logger.debug(f"Cache get error: {exc}")
        return None

    async def set(
        self,
        query:      str,
        data_types: List[ContentType],
        filters:    Dict[str, Any],
        data:       List[Dict[str, Any]],
        sgv:        float = 0.0,
    ) -> None:
        if not self._redis:
            return
        try:
            key      = self._make_key(query, data_types, filters)
            envelope = {"data": data, "sgv": sgv}
            await self._redis.set(key, json.dumps(envelope), ex=cfg.CACHE_TTL_SECONDS)
            logger.debug(f"Cache SET key={key[:20]}… sgv={sgv:.4f}")
        except Exception as exc:
            logger.debug(f"Cache set error: {exc}")

    async def close(self):
        if self._redis:
            try:
                await self._redis.aclose()
            except AttributeError:
                await self._redis.close()


# =============================================================================
# QUERY DECOMPOSER
# =============================================================================

class QueryDecomposer:
    def __init__(self, embed_service: EmbeddingService):
        self._groq = embed_service.groq

    def should_decompose(self, query: str) -> bool:
        return len(query.split()) > cfg.QUERY_DECOMPOSE_WORD_THRESHOLD

    async def decompose(self, query: str, n: int = 3) -> List[str]:
        if len(query.split()) <= 5:
            return [query]
        return await self._groq.decompose_query(query, n=n)


# =============================================================================
# EXTRACTOR AGENT (ACP gateway)
# =============================================================================

class ExtractorAgent:
    def __init__(self):
        self.embed_svc  = EmbeddingService()
        self.qdrant_mgr = QdrantCollectionManager()
        self.web_agent  = WebSearchAgent()
        self.validator  = ValidatorAgent(self.embed_svc)
        self.vectorizer = VectorizerAgent(self.embed_svc)
        self.cache      = CacheLayer()
        self.retriever  = RetrieverAgent(self.qdrant_mgr, self.embed_svc)
        self.decomposer = QueryDecomposer(self.embed_svc)
        self.target_extractor = TargetExtractor(groq_client=None)
        self._initialized = False

    async def initialize(self):
        await self.qdrant_mgr.initialize()
        await self.cache.connect()
        self.retriever.set_redis(self.cache.redis)
        self.target_extractor.set_groq(self.embed_svc.groq)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.retriever._get_reranker)
        await loop.run_in_executor(None, self.validator._get_nli_model)
        self._initialized = True
        logger.info("ExtractorAgent fully initialized (models pre-warmed).")

    async def process_request(self, request: ACPRequest) -> ACPResponse:
        start_ts     = time.monotonic()
        warning_msg: Optional[str] = None

        logger.info(
            f"[{request.session_id}] ACPRequest source={request.source_agent} "
            f"intent={request.intent} query='{request.query[:80]}' "
            f"types={[t.value for t in request.data_types]}"
        )

        is_refresh = request.intent == ACPIntent.REFRESH

        # ── Cache lookup (skipped on REFRESH) ──────────────────────────────────
        if not is_refresh:
            cached_result = await self.cache.get(
                request.query, request.data_types, request.filters
            )
            if cached_result is not None:
                cached_data, cached_sgv = cached_result
                logger.info(
                    f"[{request.session_id}] Cache HIT — {len(cached_data)} items "
                    f"sgv={cached_sgv:.4f}"
                )
                payload    = self._group_by_type(cached_data)
                latency_ms = int((time.monotonic() - start_ts) * 1000)
                if not payload:
                    warning_msg = "Cache hit but payload is empty — consider refreshing."
                return self._build_response(
                    request, payload,
                    validation_score=cached_sgv,
                    latency_ms=latency_ms,
                    warning=warning_msg,
                    targets=[],
                )

        # ── Proactive decomposition ────────────────────────────────────────────
        is_long_query  = self.decomposer.should_decompose(request.query)
        sub_queries: List[str] = []
        if is_long_query:
            logger.info(
                f"[{request.session_id}] Query has "
                f"{len(request.query.split())} words — proactive decomposition via Groq"
            )
            sub_queries = await self.decomposer.decompose(request.query, n=3)
            logger.info(f"[{request.session_id}] Sub-queries: {sub_queries}")

        # ── REFRESH: bypass Qdrant ─────────────────────────────────────────────
        if is_refresh:
            qdrant_results: List[Dict[str, Any]] = []
            raw_dense_count = 0
            needs_web = True
            logger.info(
                f"[{request.session_id}] REFRESH intent — bypassing Qdrant, "
                f"going straight to WebSearchAgent"
            )
        else:
            extracted_targets: List[DrugTarget] = []
            qdrant_results, raw_dense_count = await self.retriever.retrieve(
                query=request.query,
                content_types=request.data_types,
                filters=request.filters,
                top_k=request.top_k,
                use_hyde=True,
            )

            if is_long_query and sub_queries and qdrant_results:
                logger.info(
                    f"[{request.session_id}] Augmenting Qdrant results with "
                    f"{len(sub_queries)} sub-query retrievals (parallel)"
                )
                seen_ids: Set[str] = {r["id"] for r in qdrant_results}

                # FIX-PARALLEL-SQ: run all sub-query retrievals concurrently
                sub_retrieve_tasks = [
                    self.retriever.retrieve(
                        query=sq,
                        content_types=request.data_types,
                        filters=request.filters,
                        top_k=max(3, request.top_k // len(sub_queries)),
                        use_hyde=False,
                    )
                    for sq in sub_queries
                ]
                sub_results_list = await asyncio.gather(
                    *sub_retrieve_tasks, return_exceptions=True
                )
                for sub_result in sub_results_list:
                    if isinstance(sub_result, Exception):
                        logger.warning(f"Sub-query retrieval failed: {sub_result}")
                        continue
                    sq_results, _ = sub_result
                    for r in sq_results:
                        if r["id"] not in seen_ids:
                            qdrant_results.append(r)
                            seen_ids.add(r["id"])

                qdrant_results.sort(
                    key=lambda x: x.get("score", x.get("rrf_score", 0)), reverse=True
                )
                qdrant_results = qdrant_results[: request.top_k]

            needs_web = raw_dense_count < cfg.MIN_RESULTS_BEFORE_WEBSEARCH

        if needs_web:
            logger.info(
                f"[{request.session_id}] "
                f"{'REFRESH' if is_refresh else f'Qdrant={raw_dense_count} < {cfg.MIN_RESULTS_BEFORE_WEBSEARCH}'}"
                f" — triggering WebSearchAgent"
            )

        final_sgv = 0.0

        if needs_web:
            raw_items = await self.web_agent.collect(
                query=request.query,
                content_types=request.data_types,
                max_per_type=8,
            )
            validated, metrics = await self.validator.validate(raw_items, request.query)
            final_sgv          = metrics.sgv

            if not metrics.is_valid():
                logger.warning(
                    f"[{request.session_id}] SGV {metrics.sgv:.3f} below threshold "
                    f"— decomposing query semantically via Groq"
                )
                if not sub_queries:
                    sub_queries = await self.decomposer.decompose(request.query, n=3)

                all_validated: List[ValidatedItem] = []

                # FIX-PARALLEL-SQ: sub-query web collections run concurrently
                sub_collect_tasks = [
                    self.web_agent.collect(sq, request.data_types, max_per_type=5)
                    for sq in sub_queries[:3]
                ]
                sub_raw_list = await asyncio.gather(
                    *sub_collect_tasks, return_exceptions=True
                )
                sub_validate_tasks = []
                for sub_raw in sub_raw_list:
                    if isinstance(sub_raw, Exception):
                        logger.warning(f"Sub-query collect failed: {sub_raw}")
                        continue
                    sub_validate_tasks.append(
                        self.validator.validate(sub_raw, request.query)
                    )
                sub_val_results = await asyncio.gather(
                    *sub_validate_tasks, return_exceptions=True
                )
                for res in sub_val_results:
                    if isinstance(res, Exception):
                        logger.warning(f"Sub-query validate failed: {res}")
                        continue
                    sub_val, sub_m = res
                    if sub_m.is_valid():
                        all_validated.extend(sub_val)

                if all_validated:
                    validated = all_validated
                    final_sgv = float(
                        np.mean([item.validation_score for item in validated])
                    )

                if not validated and not qdrant_results:
                    warning_msg = (
                        f"SGV={metrics.sgv:.3f} below threshold. "
                        f"Partial or no data available."
                    )

            elif is_long_query and validated:
                logger.info(
                    f"[{request.session_id}] Proactive web augmentation "
                    f"with {len(sub_queries)} Groq sub-queries (parallel)"
                )
                if not sub_queries:
                    sub_queries = await self.decomposer.decompose(request.query, n=3)

                # FIX-PARALLEL-SQ: augmentation web collects run concurrently
                aug_collect_tasks = [
                    self.web_agent.collect(sq, request.data_types, max_per_type=3)
                    for sq in sub_queries[:3]
                ]
                aug_raw_list = await asyncio.gather(
                    *aug_collect_tasks, return_exceptions=True
                )
                aug_validate_tasks = []
                for aug_raw in aug_raw_list:
                    if isinstance(aug_raw, Exception):
                        continue
                    aug_validate_tasks.append(
                        self.validator.validate(aug_raw, request.query)
                    )
                aug_val_results = await asyncio.gather(
                    *aug_validate_tasks, return_exceptions=True
                )
                for res in aug_val_results:
                    if isinstance(res, Exception):
                        continue
                    aug_val, aug_m = res
                    if aug_m.is_valid():
                        validated.extend(aug_val)

            if validated:
                extracted_targets = await self.target_extractor.extract_targets(
                    validated, request.query
                )
                logger.info(
                    f"[{request.session_id}] TargetExtractor: "
                    f"{len(extracted_targets)} targets resolved"
                )
                # ---------------- SAVE TARGETS TO JSON ----------------
                import json
                import os
                output_dir = "outputs"
                os.makedirs(output_dir, exist_ok=True)
                targets_file = os.path.join(
                    output_dir,
                    f"targets_{request.session_id}.json"
                )
                with open(targets_file, "w", encoding="utf-8") as f:
                    json.dump(
                        [t.to_dict() for t in extracted_targets],
                        f,
                        indent=2
                    )
                logger.info(
                    f"[{request.session_id}] Targets saved to {targets_file}"
                )
# -----------------------------------
            else:
                extracted_targets = []

            if validated:
                points = await self.vectorizer.vectorize(
                    validated, session_id=request.session_id
                )
                by_col: Dict[str, List[PointStruct]] = {}
                for pt in points:
                    ctype_val = pt.payload.get("content_type", ContentType.TEXT.value)
                    col       = self.qdrant_mgr.collection_for_type(ContentType(ctype_val))
                    by_col.setdefault(col, []).append(pt)

                for col, col_pts in by_col.items():
                    await self.qdrant_mgr.upsert_batch(col_pts, col)
                    total = await self.qdrant_mgr.count_points(col)
                    logger.info(f"Storage: {col} now holds {total} vectors")

                qdrant_results, _ = await self.retriever.retrieve(
                    query=request.query,
                    content_types=request.data_types,
                    filters={},
                    top_k=request.top_k,
                    use_hyde=True,
                )

        if not needs_web and not is_refresh and qdrant_results:
            final_sgv = float(np.mean([
                r["payload"].get("validation_score", 0.0) for r in qdrant_results
            ]))

        if not qdrant_results:
            warning_msg = warning_msg or "No results found for the given query and filters."

        flat_results = self._qdrant_hits_to_dicts(qdrant_results)

        await self.cache.set(
            request.query, request.data_types, request.filters, flat_results, sgv=final_sgv
        )

        payload    = self._group_by_type(flat_results)
        latency_ms = int((time.monotonic() - start_ts) * 1000)

        response = self._build_response(
            request=request,
            payload=payload,
            validation_score=round(final_sgv, 4),
            latency_ms=latency_ms,
            warning=warning_msg,
            targets=extracted_targets,
        )

        logger.info(
            f"[{request.session_id}] ACPResponse "
            f"types={list(payload.keys())} total={response.source_count} "
            f"sgv={final_sgv:.3f} latency={latency_ms}ms"
        )
        return response

    def _qdrant_hits_to_dicts(self, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        _exclude = {
            "content", "content_type", "source_url", "title",
            "validation_score", "domain_trust", "date_collected", "session_id",
            "pmid", "doi", "citation_count",
        }
        results = []
        for hit in hits:
            p = hit.get("payload", {})
            results.append({
                "content":          p.get("content", p.get("content_preview", "")),
                "content_type":     p.get("content_type", "text"),
                "source_url":       p.get("source_url", ""),
                "title":            p.get("title", ""),
                "validation_score": p.get("validation_score", 0.0),
                "domain_trust":     p.get("domain_trust", 0.0),
                "date_collected":   p.get("date_collected", ""),
                "relevance_score":  round(hit.get("score", hit.get("rrf_score", 0.0)), 4),
                "pmid":             p.get("pmid"),
                "doi":              p.get("doi"),
                "citation_count":   p.get("citation_count"),
                "metadata": {k: v for k, v in p.items() if k not in _exclude},
            })
        return results

    def _group_by_type(
        self, items: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            grouped.setdefault(item.get("content_type", "text"), []).append(item)
        return grouped
    

    def _build_response(
        self,
        request:          ACPRequest,
        payload:          Dict[str, List[Dict[str, Any]]],
        validation_score: float,
        latency_ms:       int,
        warning:          Optional[str] = None,
        targets:          Optional[List[DrugTarget]] = None,
    ) -> ACPResponse:
        total = sum(len(v) for v in payload.values())
        return ACPResponse(
            acp_version=cfg.ACP_VERSION,
            session_id=request.session_id,
            request_id=request.request_id,
            target_agent=request.source_agent,
            data_types=request.data_types,
            payload=payload,
            validation_score=validation_score,
            retrieval_latency_ms=latency_ms,
            source_count=total,
            warning=warning,
            status="partial" if warning else "success",
            targets=[t.to_dict() for t in (targets or [])],
        )


    async def close(self):
        await self.web_agent.close()
        await self.embed_svc.close()
        await self.qdrant_mgr.close()
        await self.cache.close()
        await self.target_extractor.close()
        logger.info("ExtractorAgent shut down cleanly.")


# =============================================================================
# INTELLIGENT TARGET DISCOVERY AGENT
# =============================================================================

class IntelligentTargetDiscoveryAgent:
    VERSION = "3.4"

    def __init__(self):
        self._extractor = ExtractorAgent()
        self._started   = False

    async def start(self):
        await self._extractor.initialize()
        self._started = True
        logger.info(
            f"IntelligentTargetDiscoveryAgent v{self.VERSION} started. "
            f"Collections: {list(cfg.COLLECTIONS.keys())}"
        )

    async def stop(self):
        await self._extractor.close()
        self._started = False
        logger.info("IntelligentTargetDiscoveryAgent stopped.")

    async def handle_request(self, request: ACPRequest) -> ACPResponse:
        if not self._started:
            raise RuntimeError("Agent not started. Call await agent.start() first.")
        try:
            return await self._extractor.process_request(request)
        except Exception as exc:
            logger.exception(f"Unhandled error in process_request: {exc}")
            return ACPResponse(
                acp_version=cfg.ACP_VERSION,
                session_id=request.session_id,
                request_id=request.request_id,
                target_agent=request.source_agent,
                data_types=request.data_types,
                payload={},
                validation_score=0.0,
                retrieval_latency_ms=0,
                source_count=0,
                status="error",
                error=str(exc),
            )

    async def discover(
        self,
        query:         str,
        data_types:    Optional[List[ContentType]] = None,
        source_agent:  str = "external",
        filters:       Optional[Dict[str, Any]] = None,
        top_k:         int = cfg.TOP_K_DENSE,
        require_fresh: bool = True,
    ) -> ACPResponse:
        request = ACPRequest(
            source_agent=source_agent,
            query=query,
            data_types=data_types or [ContentType.TEXT, ContentType.PDF],
            filters=filters or {},
            top_k=top_k,
            require_fresh=require_fresh,
        )
        return await self.handle_request(request)


# =============================================================================
# CONTEXT MANAGER SUPPORT
# =============================================================================

class AgentContext:
    async def __aenter__(self) -> IntelligentTargetDiscoveryAgent:
        self.agent = IntelligentTargetDiscoveryAgent()
        await self.agent.start()
        return self.agent

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.agent.stop()


# =============================================================================
# DEMO / ENTRY POINT
# =============================================================================

async def _demo():
    print("=" * 70)
    print(
        f"INTELLIGENT TARGET DISCOVERY AGENT "
        f"v{IntelligentTargetDiscoveryAgent.VERSION} — Demo"
    )
    print("=" * 70)
    print("NOTE: Set GROQ_API_KEY for HyDE, decomposition, and summarization.")
    print("      Windows: $env:GROQ_API_KEY = 'gsk_...'")
    print("      Linux:   export GROQ_API_KEY=gsk_...")
    print("      Get a free key at: https://console.groq.com")
    print()
    print("NOTE: Set PUBMED_API_KEY env var for higher PubMed rate limits.")
    print("      e.g.  export PUBMED_API_KEY=your_ncbi_api_key")
    print()
    print("NOTE: Set HF_TOKEN only if you want BLIP image captioning.")
    print()

    groq_status = "✓ ACTIVE" if cfg.GROQ_API_KEY else "✗ NOT SET (fallback mode)"
    print(f"  Groq ({cfg.GROQ_MODEL}): {groq_status}")
    print(f"  SearXNG engines: {cfg.SEARXNG_ENGINES}")
    print(f"  DATA_FRESHNESS_DAYS: {cfg.DATA_FRESHNESS_DAYS}")
    print(f"  RELEVANCE_THRESHOLD_BASE: {cfg.RELEVANCE_THRESHOLD_BASE}")
    print(f"  RELEVANCE_THRESHOLD_FLOOR: {cfg.RELEVANCE_THRESHOLD_FLOOR}")
    print()

    try:
        async with AgentContext() as agent:
            print("\n[0] Qdrant storage snapshot (before queries)...")
            for col_name in cfg.COLLECTIONS:
                n = await agent._extractor.qdrant_mgr.count_points(col_name)
                print(f"    {col_name:<25} {n:>6} vectors")

            print("\n[TEST] Web search — SearXNG / DDG / Scholar / PubMed test...")
            web_response = await agent.discover(
                query="latest advances CRISPR base editing 2026",
                data_types=[ContentType.TEXT],
                source_agent="test_searxng",
                filters={},
                top_k=5,
                require_fresh=True,
            )
            print(f"    Status:          {web_response.status}")
            print(f"    Items retrieved: {web_response.source_count}")
            print(f"    SGV:             {web_response.validation_score}")
            print(f"    Latency:         {web_response.retrieval_latency_ms}ms")
            if web_response.warning:
                print(f"    ⚠ Warning:       {web_response.warning}")

            print("\n[1] Biomedical target discovery query...")
            response = await agent.discover(
                query="KRAS G12C oncogenic mutation drug targets 2024",
                data_types=[ContentType.TEXT, ContentType.PDF],
                source_agent="discoverer_agent",
                filters={"lang": "en", "score_min": 0.60},
                top_k=10,
            )
            print(f"    Status:           {response.status}")
            print(f"    Validation SGV:   {response.validation_score}")
            print(f"    Items retrieved:  {response.source_count}")
            print(f"    Latency:          {response.retrieval_latency_ms}ms")
            print(f"    Data types:       {list(response.payload.keys())}")
            if response.warning:
                print(f"    ⚠ Warning:        {response.warning}")
            for ctype, items in response.payload.items():
                if items:
                    first = items[0]
                    print(f"\n    First {ctype} result provenance:")
                    print(f"      Title:    {first.get('title', 'N/A')[:60]}")
                    print(f"      PMID:     {first.get('pmid', 'N/A')}")
                    print(f"      DOI:      {first.get('doi', 'N/A')}")
                    print(f"      Citations:{first.get('citation_count', 'N/A')}")
                    print(f"      URL:      {first.get('source_url', '')[:60]}")
                    break

            print("\n[2] Multimodal query (text + image + table)...")
            response2 = await agent.discover(
                query="protein-protein interaction network visualization cancer pathway",
                data_types=[ContentType.TEXT, ContentType.IMAGE, ContentType.TABLE],
                source_agent="reporter_agent",
                top_k=5,
            )
            print(f"    Items: {response2.source_count} | SGV: {response2.validation_score}")
            print(f"    Types returned: {list(response2.payload.keys())}")

            print("\n[3] Full ACP request with all fields...")
            acp_req = ACPRequest(
                source_agent="planner_agent",
                query="clinical trials CAR-T cell therapy acute lymphoblastic leukemia",
                data_types=[ContentType.TEXT, ContentType.PDF, ContentType.TABLE],
                filters={"lang": "en", "score_min": 0.60},
                intent=ACPIntent.FIND,
                top_k=8,
            )
            response3 = await agent.handle_request(acp_req)
            print(f"    Session: {response3.session_id} | Request: {response3.request_id}")
            print(
                f"    Items: {response3.source_count} | "
                f"SGV: {response3.validation_score} | Status: {response3.status}"
            )

            print("\n[4] Qdrant storage snapshot (after queries)...")
            for col_name in cfg.COLLECTIONS:
                n = await agent._extractor.qdrant_mgr.count_points(col_name)
                print(f"    {col_name:<25} {n:>6} vectors")

            print("\n[5] REFRESH test (bypasses cache AND Qdrant)...")
            refresh_req = ACPRequest(
                source_agent="test_agent",
                query="KRAS G12C oncogenic mutation drug targets 2024",
                data_types=[ContentType.TEXT, ContentType.PDF],
                filters={},
                intent=ACPIntent.REFRESH,
                top_k=5,
                require_fresh=True,
            )
            r5 = await agent.handle_request(refresh_req)
            print(
                f"    Items: {r5.source_count} | "
                f"SGV: {r5.validation_score} | Status: {r5.status}"
            )
            for col_name in ["texts_collection", "pdfs_collection"]:
                n = await agent._extractor.qdrant_mgr.count_points(col_name)
                print(f"    {col_name:<25} {n:>6} vectors (post-refresh)")

            print("\n[6] Long-query proactive decomposition test (Groq-powered)...")
            long_query = (
                "What are the molecular mechanisms of KRAS G12C inhibitor resistance "
                "in non-small cell lung cancer and what combination therapies are "
                "currently in clinical trials to overcome this resistance?"
            )
            r6 = await agent.discover(
                query=long_query,
                data_types=[ContentType.TEXT, ContentType.PDF],
                source_agent="decompose_test_agent",
                top_k=5,
            )
            print(f"    Words in query: {len(long_query.split())}")
            print(
                f"    Items: {r6.source_count} | "
                f"SGV: {r6.validation_score} | Status: {r6.status}"
            )

    except KeyboardInterrupt:
        print("\n\n⚠  Interrupted by user — shutting down cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(_demo())
    except KeyboardInterrupt:
        print("\n⚠  Ctrl+C received — exited.")