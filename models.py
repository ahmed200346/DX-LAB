"""
models.py — Data classes, Pydantic models, and enums.

Fixes vs original:
  • ACPResponse gains `chemicals` field (was missing, chemical_extractor was wired
    but response never carried results).
  • FinalReport + ReportSection models added for report generation feature.
  • No business logic — pure data shapes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config import cfg


# =============================================================================
# ENUMS
# =============================================================================

class ContentType(str, Enum):
    TEXT     = "text"
    PDF      = "pdf"
    IMAGE    = "image"
    VIDEO    = "video"
    TABLE    = "table"
    GRAPH    = "graph"
    CODE     = "code"
    CHEMICAL = "chemical"


class ACPIntent(str, Enum):
    FIND     = "find"
    RETRIEVE = "retrieve"
    REFRESH  = "refresh"
    VALIDATE = "validate"


# =============================================================================
# ACP REQUEST / RESPONSE
# =============================================================================

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
    # ── Enrichment results ────────────────────────────────────────────────────
    targets:              List[Dict[str, Any]] = Field(default_factory=list)
    chemicals:            List[Dict[str, Any]] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


# =============================================================================
# VALIDATED ITEM
# =============================================================================

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


# =============================================================================
# VALIDATION METRICS
# =============================================================================

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
# REPORT MODELS
# =============================================================================

class ReportSection(BaseModel):
    """One section of the final analysis report."""
    title:   str
    content: str                        # markdown prose
    data:    List[Dict[str, Any]] = Field(default_factory=list)  # supporting rows


class FinalReport(BaseModel):
    """
    Full downloadable report generated after a discovery session.
    Sections are in display order; raw_data contains every item returned
    from the pipeline so the user can cross-check every claim.
    """
    session_id:       str
    query:            str
    generated_at:     str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    validation_score: float = 0.0
    sections:         List[ReportSection] = Field(default_factory=list)

    # Raw data for download / audit
    targets:          List[Dict[str, Any]] = Field(default_factory=list)
    chemicals:        List[Dict[str, Any]] = Field(default_factory=list)
    sources:          List[Dict[str, Any]] = Field(default_factory=list)

    # Interim analysis blobs (JSON-serialisable)
    interim_ner:      Dict[str, Any] = Field(default_factory=dict)
    interim_metrics:  Dict[str, Any] = Field(default_factory=dict)

    def to_markdown(self) -> str:
        lines = [
            f"# Discovery Report — {self.query}",
            f"**Session:** `{self.session_id}` | "
            f"**Generated:** {self.generated_at} | "
            f"**SGV:** {self.validation_score:.3f}",
            "",
        ]
        for sec in self.sections:
            lines.append(f"## {sec.title}")
            lines.append(sec.content)
            lines.append("")
        return "\n".join(lines)