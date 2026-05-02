"""
pubmed_frequency.py — PubMed Publication-Frequency Scoring

Estimates the evidence strength of a gene/drug/disease entity by
querying the NCBI E-utilities for publication counts and trend data.

Key outputs per entity:
  • total_count        — all-time PubMed hits for the entity
  • recent_count       — hits in the past N years (configurable)
  • trend_slope        — linear slope of annual counts (rising/falling)
  • trend_direction    — "rising" | "stable" | "declining"
  • frequency_score    — 0–1 composite score for integration into SGV
  • evidence_tier      — "high" | "medium" | "low" | "unknown"

Designed for async use.  All results are in-process-cached per session
to minimise API calls.  Respects the PUBMED_API_KEY in AgentConfig for
higher rate limits (10 req/s vs 3 req/s).

Public class:
    PubMedFrequencyScorer
        async score(entity: str, entity_type: str) -> FrequencyResult
        async score_batch(pairs: List[(entity, entity_type)]) -> List[FrequencyResult]
        async score_targets(targets: List[DrugTarget]) -> List[DrugTarget]

Integration with ExtractorAgent / ValidatorAgent:
  1. Instantiate once in ExtractorAgent.__init__:
         self.pubmed_scorer = PubMedFrequencyScorer()

  2. After target extraction, call:
         targets = await self.pubmed_scorer.score_targets(targets)

  3. Optionally use frequency_score to boost validation credibility:
         item["citation_boost"] = scorer.estimate_item_boost(item)
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from loguru import logger

from config import cfg


# =============================================================================
# CONSTANTS
# =============================================================================

_ESEARCH_URL     = f"{cfg.PUBMED_BASE_URL}/esearch.fcgi"
_EINFO_URL       = f"{cfg.PUBMED_BASE_URL}/einfo.fcgi"
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=12)
_RECENT_YEARS    = 5          # window for "recent" publication count
_MIN_RATE_DELAY  = 0.12       # seconds between requests (~8 req/s, safe margin)
_MAX_CONCURRENT  = 4
_TREND_YEARS     = 6          # years for slope calculation


# =============================================================================
# DATA MODEL
# =============================================================================

@dataclass
class FrequencyResult:
    entity:          str
    entity_type:     str            # GENE | DRUG | DISEASE | PATHWAY | QUERY

    total_count:     int            = 0
    recent_count:    int            = 0     # last _RECENT_YEARS years
    yearly_counts:   Dict[int, int] = field(default_factory=dict)  # {year: count}

    trend_slope:     float          = 0.0   # papers/year change
    trend_direction: str            = "unknown"  # rising|stable|declining|unknown

    frequency_score: float          = 0.0   # 0–1 composite
    evidence_tier:   str            = "unknown"  # high|medium|low|unknown

    pubmed_url:      str            = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity":           self.entity,
            "entity_type":      self.entity_type,
            "total_count":      self.total_count,
            "recent_count":     self.recent_count,
            "yearly_counts":    self.yearly_counts,
            "trend_slope":      round(self.trend_slope, 2),
            "trend_direction":  self.trend_direction,
            "frequency_score":  round(self.frequency_score, 4),
            "evidence_tier":    self.evidence_tier,
            "pubmed_url":       self.pubmed_url,
        }


# =============================================================================
# HELPERS
# =============================================================================

def _log_norm(count: int, scale: int = 10_000) -> float:
    """Log-normalise a count into [0, 1]."""
    return min(1.0, math.log1p(count) / math.log1p(scale))


def _compute_trend(yearly: Dict[int, int]) -> Tuple[float, str]:
    """
    Fit a simple linear trend over the yearly counts.
    Returns (slope_papers_per_year, direction_label).
    """
    if len(yearly) < 2:
        return 0.0, "unknown"

    years  = sorted(yearly.keys())
    counts = [yearly[y] for y in years]
    n      = len(years)
    x_mean = sum(years) / n
    y_mean = sum(counts) / n

    ss_xy = sum((years[i] - x_mean) * (counts[i] - y_mean) for i in range(n))
    ss_xx = sum((years[i] - x_mean) ** 2 for i in range(n))

    slope = ss_xy / ss_xx if ss_xx else 0.0

    if slope > 5:
        direction = "rising"
    elif slope < -5:
        direction = "declining"
    else:
        direction = "stable"

    return slope, direction


def _evidence_tier(score: float) -> str:
    if score >= 0.65:
        return "high"
    if score >= 0.35:
        return "medium"
    if score > 0.0:
        return "low"
    return "unknown"


def _pubmed_url(query: str) -> str:
    from urllib.parse import quote
    return f"https://pubmed.ncbi.nlm.nih.gov/?term={quote(query)}"


# =============================================================================
# PUBMED FREQUENCY SCORER
# =============================================================================

class PubMedFrequencyScorer:
    """
    Scores entities by their PubMed publication frequency.
    Uses E-utilities esearch with rettype=count for efficiency.
    """

    def __init__(self):
        self._session:    Optional[aiohttp.ClientSession] = None
        self._semaphore   = asyncio.Semaphore(_MAX_CONCURRENT)
        self._cache:      Dict[str, FrequencyResult] = {}
        self._last_req_ts: float = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Rate-limited fetch ────────────────────────────────────────────────────

    async def _throttled_get(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """E-utilities GET with rate limiting and API key injection."""
        # Respect NCBI rate limit
        now   = time.monotonic()
        delay = _MIN_RATE_DELAY - (now - self._last_req_ts)
        if delay > 0:
            await asyncio.sleep(delay)

        if cfg.PUBMED_API_KEY:
            params["api_key"] = cfg.PUBMED_API_KEY

        params.setdefault("retmode", "json")

        try:
            session = await self._get_session()
            async with session.get(_ESEARCH_URL, params=params) as resp:
                self._last_req_ts = time.monotonic()
                if resp.status != 200:
                    logger.debug(f"PubMed esearch HTTP {resp.status}")
                    return None
                return await resp.json(content_type=None)
        except asyncio.TimeoutError:
            logger.debug("PubMed esearch timeout")
            return None
        except Exception as exc:
            logger.debug(f"PubMed esearch error: {exc}")
            return None

    # ── Count queries ─────────────────────────────────────────────────────────

    async def _count_total(self, query: str) -> int:
        """Return the total all-time PubMed count for a query string."""
        data = await self._throttled_get({
            "db":       "pubmed",
            "term":     query,
            "rettype":  "count",
        })
        if data is None:
            return 0
        try:
            return int(data["esearchresult"]["count"])
        except (KeyError, ValueError):
            return 0

    async def _count_recent(self, query: str) -> int:
        """Count publications in the last _RECENT_YEARS years."""
        import datetime
        current_year = datetime.datetime.now().year
        start_year   = current_year - _RECENT_YEARS
        date_range   = f"{start_year}/01/01:{current_year}/12/31[dp]"
        data = await self._throttled_get({
            "db":       "pubmed",
            "term":     f"{query} AND {date_range}",
            "rettype":  "count",
        })
        if data is None:
            return 0
        try:
            return int(data["esearchresult"]["count"])
        except (KeyError, ValueError):
            return 0

    async def _yearly_counts(self, query: str) -> Dict[int, int]:
        """
        Fetch annual publication counts for the last _TREND_YEARS years.
        Returns {year: count}.
        """
        import datetime
        current_year = datetime.datetime.now().year
        counts: Dict[int, int] = {}
        for yr in range(current_year - _TREND_YEARS, current_year + 1):
            date_range = f"{yr}/01/01:{yr}/12/31[dp]"
            data       = await self._throttled_get({
                "db":      "pubmed",
                "term":    f"{query} AND {date_range}",
                "rettype": "count",
            })
            if data is not None:
                try:
                    counts[yr] = int(data["esearchresult"]["count"])
                except (KeyError, ValueError):
                    counts[yr] = 0
        return counts

    # ── Build query strings ───────────────────────────────────────────────────

    @staticmethod
    def _build_query(entity: str, entity_type: str) -> str:
        """
        Construct a PubMed search query appropriate for the entity type.
        Uses MeSH/field tags where appropriate for precision.
        """
        entity_type = entity_type.upper()

        if entity_type == "GENE":
            # Gene symbol in title/abstract + gene ontology MeSH
            return f'("{entity}"[Title/Abstract] OR "{entity}"[Gene/Protein Name])'

        if entity_type == "PROTEIN":
            return f'"{entity}"[Protein Name]'

        if entity_type == "DRUG":
            return (
                f'("{entity}"[Title/Abstract] OR '
                f'"{entity}"[Substance Name] OR '
                f'"{entity}"[Supplementary Concept])'
            )

        if entity_type == "DISEASE":
            return (
                f'("{entity}"[Title/Abstract] OR '
                f'"{entity}"[MeSH Terms])'
            )

        if entity_type == "PATHWAY":
            return f'"{entity} pathway"[Title/Abstract]'

        # Fallback / QUERY
        return f'"{entity}"[Title/Abstract]'

    # ── Main scoring method ───────────────────────────────────────────────────

    async def score(
        self, entity: str, entity_type: str = "QUERY"
    ) -> FrequencyResult:
        """
        Score a single entity by PubMed publication frequency.
        Results are cached in-process.
        """
        cache_key = f"{entity_type}:{entity.lower()}"
        if cache_key in self._cache:
            logger.debug(f"PubMedFrequency cache HIT: {cache_key}")
            return self._cache[cache_key]

        async with self._semaphore:
            # Double-checked locking
            if cache_key in self._cache:
                return self._cache[cache_key]

            query        = self._build_query(entity, entity_type)
            pubmed_url   = _pubmed_url(query)

            logger.debug(f"PubMedFrequency scoring: {entity} ({entity_type})")

            # Concurrent total + recent + yearly
            total_task   = asyncio.create_task(self._count_total(query))
            recent_task  = asyncio.create_task(self._count_recent(query))
            yearly_task  = asyncio.create_task(self._yearly_counts(query))

            total, recent, yearly = await asyncio.gather(
                total_task, recent_task, yearly_task
            )

            # Trend analysis
            slope, direction = _compute_trend(yearly)

            # Composite frequency score (0–1)
            total_norm  = _log_norm(total,  scale=50_000)
            recent_norm = _log_norm(recent, scale=5_000)
            trend_bonus = 0.1 if direction == "rising" else (
                         -0.05 if direction == "declining" else 0.0)
            freq_score  = min(1.0, 0.50 * total_norm + 0.50 * recent_norm + trend_bonus)

            result = FrequencyResult(
                entity          = entity,
                entity_type     = entity_type,
                total_count     = total,
                recent_count    = recent,
                yearly_counts   = yearly,
                trend_slope     = slope,
                trend_direction = direction,
                frequency_score = freq_score,
                evidence_tier   = _evidence_tier(freq_score),
                pubmed_url      = pubmed_url,
            )
            self._cache[cache_key] = result

            logger.info(
                f"PubMedFrequency: {entity} ({entity_type}) "
                f"total={total:,} recent={recent:,} "
                f"trend={direction} score={freq_score:.3f} "
                f"tier={result.evidence_tier}"
            )
            return result

    async def score_batch(
        self, pairs: List[Tuple[str, str]]
    ) -> List[FrequencyResult]:
        """
        Score a list of (entity, entity_type) pairs concurrently.
        """
        tasks = [self.score(entity, etype) for entity, etype in pairs]
        return list(await asyncio.gather(*tasks))

    async def score_targets(self, targets: list) -> list:
        """
        Attach PubMed frequency scores to a list of DrugTarget objects.
        Adds `pubmed_frequency` attribute (FrequencyResult) to each target.
        Also updates `source_count` if zero and frequency provides evidence.

        Returns the same list (mutated).
        """
        pairs = [
            (getattr(t, "gene", "unknown"), "GENE")
            for t in targets
        ]
        results = await self.score_batch(pairs)

        for target, freq in zip(targets, results):
            target.pubmed_frequency = freq

            # Supplement source_count if not populated by provenance tracking
            if getattr(target, "source_count", 0) == 0 and freq.recent_count > 0:
                target.source_count = freq.recent_count

            logger.debug(
                f"PubMed scored target {getattr(target, 'gene', '?')}: "
                f"tier={freq.evidence_tier} score={freq.frequency_score:.3f}"
            )

        return targets

    def estimate_item_boost(self, item: Dict[str, Any]) -> float:
        """
        Lightweight heuristic: estimate a credibility boost for a validated
        item based on its citation count + content biomedical entity density.
        Returns a float in [0, 0.15] to be added to domain_trust.
        """
        citation_count = item.get("citation_count") or 0
        citation_boost = min(0.10, math.log1p(citation_count) / math.log1p(500))

        # Keyword density in content
        content        = item.get("content", "")[:1000]
        entity_hits    = len(
            [w for w in content.split()
             if w.isupper() and 2 <= len(w) <= 8]
        )
        density_boost  = min(0.05, entity_hits * 0.005)

        return round(citation_boost + density_boost, 4)
