"""
utils.py — Pure utilities with no agent state.

Contains:
  - CircuitBreaker
  - BM25Index
  - Domain filter functions and precompiled regexes
  - _content_is_biomedically_relevant()
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Dict, List, Optional, Set

import numpy as np
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import cfg


# =============================================================================
# PRECOMPILED REGEXES — built once at import time
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


# =============================================================================
# DOMAIN FILTER
# =============================================================================

def _domain_is_blocked(domain: str) -> bool:
    """
    Returns True if the domain should be rejected before any content fetch.

    Logic (first match wins):
      1. Exact blocklist hit           → BLOCKED
      2. Substring blocklist hit       → BLOCKED
      3. Academic TLD (.edu/.gov/etc.) → ALLOWED
      4. In TRUSTED_DOMAINS list       → ALLOWED
      5. Contains a scientific keyword → ALLOWED
      6. Neutral TLD (.org/.net/etc.)  → BLOCKED (no scientific kw)
      7. Commercial / ccTLD            → BLOCKED
      8. Unknown / anything else       → BLOCKED (default-deny)
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
# BM25 INDEX (TF-IDF backed approximation)
# =============================================================================

class BM25Index:
    """
    TF-IDF backed BM25 approximation.
    Capped at BM25_MAX_DOCS entries (FIFO eviction).
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
# ASYNC HELPERS
# =============================================================================

async def _false_coro() -> bool:
    return False
