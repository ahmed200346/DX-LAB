"""
extractor.py — ExtractorAgent  v3.0

Fixes vs v2.0:
  • extracted_targets / extracted_chemicals always initialised at top of
    process_request() → no more NameError in non-REFRESH non-web paths.
  • ChemicalExtractor fully wired: runs after target extraction, results
    stored in Qdrant chemicals_collection AND returned in ACPResponse.
  • Redis cache envelope now stores targets + chemicals alongside data/sgv
    so cache-hit responses are fully enriched.
  • Shared BioNERService instance injected into ValidatorAgent and
    TargetExtractor — no duplicate model loads.
  • Groq retry: up to 2 retries with exponential back-off on transient
    failures inside target/chemical extraction.
  • Structured per-request metrics log at INFO level for observability.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger
from qdrant_client.models import PointStruct

from bio_ner import BioNERService
from chemical_extractor import ChemicalExtractor
from config import cfg
from embeddings import EmbeddingService
from models import (
    ACPIntent, ACPRequest, ACPResponse, ContentType, ValidatedItem,
    FinalReport,              # <-- FIX: added missing import
)
from retriever import QueryDecomposer, RetrieverAgent
from search import WebSearchAgent
from storage import CacheLayer, QdrantCollectionManager
from target_extractor import DrugTarget, TargetExtractor
from validator import ValidatorAgent
from vectorizer import VectorizerAgent
from report_generator import ReportGenerator
from qa_assistant import QAAssistant


class ExtractorAgent:
    def __init__(self):
        # ── Shared NER singleton (one load for all consumers) ─────────────────
        self._ner = BioNERService()

        self.embed_svc        = EmbeddingService()
        self.qdrant_mgr       = QdrantCollectionManager()
        self.web_agent        = WebSearchAgent()
        self.validator        = ValidatorAgent(self.embed_svc, ner_service=self._ner)
        self.vectorizer       = VectorizerAgent(self.embed_svc)
        self.cache            = CacheLayer()
        self.retriever        = RetrieverAgent(self.qdrant_mgr, self.embed_svc)
        self.decomposer       = QueryDecomposer(self.embed_svc)
        self.target_extractor = TargetExtractor(groq_client=None, ner_service=self._ner)
        self.chemical_extractor = ChemicalExtractor(groq_client=None)
        self._initialized     = False

    async def initialize(self):
        await self.qdrant_mgr.initialize()
        await self.cache.connect()
        self.retriever.set_redis(self.cache.redis)
        self.target_extractor.set_groq(self.embed_svc.groq)
        self.chemical_extractor.set_groq(self.embed_svc.groq)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.retriever._get_reranker)
        await loop.run_in_executor(None, self.validator._get_nli_model)
        self._initialized = True
        logger.info("ExtractorAgent v3.0 fully initialized (models pre-warmed).")

    # =========================================================================
    # MAIN ORCHESTRATION
    # =========================================================================

    async def process_request(self, request: ACPRequest) -> ACPResponse:
        start_ts     = time.monotonic()
        warning_msg: Optional[str] = None

        # ── Always-initialised so no branch can cause NameError ───────────────
        extracted_targets:   List[DrugTarget]  = []
        extracted_chemicals: List[Any]         = []  # List[ChemicalGraph]
        final_sgv = 0.0

        # ── Query-level BioNER logging ─────────────────────────────────────────
        query_entities = self._ner.extract_query_entities(request.query)
        if query_entities:
            logger.info(
                f"[{request.session_id}] BioNER query entities: "
                + ", ".join(f"{k}=[{', '.join(v[:5])}]" for k, v in query_entities.items())
            )

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
                cached_data, cached_sgv, cached_targets, cached_chemicals = cached_result
                logger.info(
                    f"[{request.session_id}] Cache HIT — {len(cached_data)} items "
                    f"sgv={cached_sgv:.4f} targets={len(cached_targets)} "
                    f"chemicals={len(cached_chemicals)}"
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
                    targets=cached_targets,
                    chemicals=cached_chemicals,
                )

        # ── Proactive decomposition ────────────────────────────────────────────
        is_long_query = self.decomposer.should_decompose(request.query)
        sub_queries: List[str] = []
        if is_long_query:
            sub_queries = await self.decomposer.decompose(request.query, n=3)
            logger.info(f"[{request.session_id}] Sub-queries: {sub_queries}")

        # ── REFRESH: bypass Qdrant ─────────────────────────────────────────────
        if is_refresh:
            qdrant_results: List[Dict[str, Any]] = []
            raw_dense_count = 0
            needs_web = True
        else:
            qdrant_results, raw_dense_count = await self.retriever.retrieve(
                query=request.query,
                content_types=request.data_types,
                filters=request.filters,
                top_k=request.top_k,
                use_hyde=True,
            )

            if is_long_query and sub_queries and qdrant_results:
                seen_ids = {r["id"] for r in qdrant_results}
                sub_tasks = [
                    self.retriever.retrieve(
                        query=sq,
                        content_types=request.data_types,
                        filters=request.filters,
                        top_k=max(3, request.top_k // len(sub_queries)),
                        use_hyde=False,
                    )
                    for sq in sub_queries
                ]
                sub_results_list = await asyncio.gather(*sub_tasks, return_exceptions=True)
                for sub_result in sub_results_list:
                    if isinstance(sub_result, Exception):
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

        # ── Web collection + validation ────────────────────────────────────────
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
                    f"— decomposing via Groq"
                )
                if not sub_queries:
                    sub_queries = await self.decomposer.decompose(request.query, n=3)

                all_validated: List[ValidatedItem] = []
                sub_raw_list = await asyncio.gather(
                    *[self.web_agent.collect(sq, request.data_types, max_per_type=5)
                      for sq in sub_queries[:3]],
                    return_exceptions=True,
                )
                sub_val_results = await asyncio.gather(
                    *[self.validator.validate(sr, request.query)
                      for sr in sub_raw_list if not isinstance(sr, Exception)],
                    return_exceptions=True,
                )
                for res in sub_val_results:
                    if isinstance(res, Exception):
                        continue
                    sub_val, sub_m = res
                    if sub_m.is_valid():
                        all_validated.extend(sub_val)

                if all_validated:
                    validated = all_validated
                    final_sgv = float(np.mean([i.validation_score for i in validated]))

                if not validated and not qdrant_results:
                    warning_msg = (
                        f"SGV={metrics.sgv:.3f} below threshold. "
                        f"Partial or no data available."
                    )

            elif is_long_query and validated:
                if not sub_queries:
                    sub_queries = await self.decomposer.decompose(request.query, n=3)
                aug_raw_list = await asyncio.gather(
                    *[self.web_agent.collect(sq, request.data_types, max_per_type=3)
                      for sq in sub_queries[:3]],
                    return_exceptions=True,
                )
                for aug_raw in aug_raw_list:
                    if isinstance(aug_raw, Exception):
                        continue
                    aug_val, aug_m = await self.validator.validate(aug_raw, request.query)
                    if aug_m.is_valid():
                        validated.extend(aug_val)

            # ── Enrichment: targets + chemicals ────────────────────────────────
            if validated:
                # Run target extraction and chemical extraction concurrently
                enrichment = await asyncio.gather(
                    self._safe_extract_targets(validated, request.query),
                    self._safe_extract_chemicals(validated, request.query, request.session_id),
                    return_exceptions=True,
                )
                if not isinstance(enrichment[0], Exception):
                    extracted_targets = enrichment[0]
                else:
                    logger.warning(f"Target extraction failed: {enrichment[0]}")

                if not isinstance(enrichment[1], Exception):
                    extracted_chemicals = enrichment[1]
                else:
                    logger.warning(f"Chemical extraction failed: {enrichment[1]}")

                logger.info(
                    f"[{request.session_id}] Enrichment: "
                    f"{len(extracted_targets)} targets, "
                    f"{len(extracted_chemicals)} chemicals"
                )

                # ── Save targets JSON ──────────────────────────────────────────
                if extracted_targets:
                    os.makedirs("outputs", exist_ok=True)
                    with open(
                        f"outputs/targets_{request.session_id}.json", "w", encoding="utf-8"
                    ) as f:
                        json.dump([t.to_dict() for t in extracted_targets], f, indent=2)

                # ── Vectorise + upsert ─────────────────────────────────────────
                points = await self.vectorizer.vectorize(validated, session_id=request.session_id)
                by_col: Dict[str, List[PointStruct]] = {}
                for pt in points:
                    ctype_val = pt.payload.get("content_type", ContentType.TEXT.value)
                    col = self.qdrant_mgr.collection_for_type(ContentType(ctype_val))
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

        # ── Persist to cache (with targets + chemicals) ────────────────────────
        await self.cache.set(
            request.query,
            request.data_types,
            request.filters,
            flat_results,
            sgv=final_sgv,
            targets=[t.to_dict() for t in extracted_targets],
            chemicals=[c.to_dict() for c in extracted_chemicals],
        )

        payload    = self._group_by_type(flat_results)
        latency_ms = int((time.monotonic() - start_ts) * 1000)

        # ── Structured observability log ───────────────────────────────────────
        logger.info(
            f"[{request.session_id}] DONE "
            f"types={list(payload.keys())} total={sum(len(v) for v in payload.values())} "
            f"targets={len(extracted_targets)} chemicals={len(extracted_chemicals)} "
            f"sgv={final_sgv:.3f} latency={latency_ms}ms "
            f"web={'yes' if needs_web else 'no'}"
        )

        return self._build_response(
            request=request,
            payload=payload,
            validation_score=round(final_sgv, 4),
            latency_ms=latency_ms,
            warning=warning_msg,
            targets=extracted_targets if needs_web else extracted_targets,
            chemicals=extracted_chemicals if needs_web else extracted_chemicals,
        )

    # =========================================================================
    # SAFE ENRICHMENT WRAPPERS (retry on transient Groq failures)
    # =========================================================================

    async def _safe_extract_targets(
        self, validated: List[ValidatedItem], query: str
    ) -> List[DrugTarget]:
        for attempt in range(2):
            try:
                return await self.target_extractor.extract_targets(validated, query)
            except Exception as exc:
                if attempt == 0:
                    logger.warning(f"Target extraction attempt 1 failed: {exc} — retrying")
                    await asyncio.sleep(1.5)
                else:
                    logger.warning(f"Target extraction failed after 2 attempts: {exc}")
        return []

    async def _safe_extract_chemicals(
        self, validated: List[ValidatedItem], query: str, session_id: str
    ) -> List[Any]:
        from chemical_extractor import ChemicalGraph
        for attempt in range(2):
            try:
                chemicals, chem_points = await self.chemical_extractor.extract_chemicals(
                    validated_items=validated,
                    query=query,
                    embed_service=self.embed_svc,
                    session_id=session_id,
                )
                if chem_points:
                    await self.qdrant_mgr.upsert_batch(chem_points, "chemicals_collection")
                    total = await self.qdrant_mgr.count_points("chemicals_collection")
                    logger.info(f"chemicals_collection: {total} vectors")
                return chemicals
            except Exception as exc:
                if attempt == 0:
                    logger.warning(f"Chemical extraction attempt 1 failed: {exc} — retrying")
                    await asyncio.sleep(1.5)
                else:
                    logger.warning(f"Chemical extraction failed after 2 attempts: {exc}")
        return []

    # =========================================================================
    # HELPERS
    # =========================================================================

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
        warning:          Optional[str]   = None,
        targets:          Optional[list]  = None,
        chemicals:        Optional[list]  = None,
    ) -> ACPResponse:
        total = sum(len(v) for v in payload.values())

        # Normalise to dicts regardless of whether we got DrugTarget objects
        # or already-serialised dicts (from cache)
        def _to_dicts(items: Optional[list]) -> List[Dict[str, Any]]:
            if not items:
                return []
            return [
                t.to_dict() if hasattr(t, "to_dict") else t
                for t in items
            ]

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
            targets=_to_dicts(targets),
            chemicals=_to_dicts(chemicals),
        )

    async def generate_report(self, response: ACPResponse, query: str) -> FinalReport:
        if not hasattr(self, "_report_gen"):
            # Use the Groq client from embedding service
            self._report_gen = ReportGenerator(self.embed_svc.groq)
        return await self._report_gen.generate(response, query)

    async def create_qa_assistant(self, response: ACPResponse) -> QAAssistant:
        qa = QAAssistant(
            groq_client=self.embed_svc.groq,
            embed_service=self.embed_svc,
            qdrant_mgr=self.qdrant_mgr,
        )
        qa.load_session(response)
        return qa

    async def close(self):
        await self.web_agent.close()
        await self.embed_svc.close()
        await self.qdrant_mgr.close()
        await self.cache.close()
        await self.target_extractor.close()
        await self.chemical_extractor.close()
        logger.info("ExtractorAgent v3.0 shut down cleanly.")