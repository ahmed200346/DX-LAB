"""
retriever.py — RetrieverAgent and QueryDecomposer.

Handles: dense search, BM25 sparse reranking, RRF fusion,
cross-encoder reranking (with Redis cache), MMR diversity filtering,
and query decomposition.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import redis.asyncio as aioredis
from loguru import logger
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range
from sentence_transformers import CrossEncoder
from sklearn.metrics.pairwise import cosine_similarity

from config import cfg
from embeddings import EmbeddingService
from models import ContentType
from storage import QdrantCollectionManager
from utils import BM25Index


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
        if not results:
            return []
        candidates = results[: cfg.CE_MAX_CANDIDATES]
        contents   = [
            r["payload"].get("content", r["payload"].get("content_preview", ""))
            for r in candidates
        ]

        try:
            reranker = self._get_reranker()

            cached_scores    = await self._ce_scores_from_cache(query, contents)
            uncached_indices = [i for i in range(len(candidates)) if i not in cached_scores]

            if uncached_indices:
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

        # rel_scores is aligned with valid_indices
        rel_scores = cosine_similarity(q_arr, emb_mat).flatten()

        # ---- FIX: Pre‑compute mapping from candidate index -> position in valid_indices ----
        idx_to_pos = {cand_idx: pos for pos, cand_idx in enumerate(valid_indices)}

        type_seed_positions: List[int] = []
        if requested_types:
            seen_types: Set[str] = set()
            # Sort valid positions by descending relevance score
            sorted_positions = sorted(
                range(len(valid_indices)),
                key=lambda pos: rel_scores[pos],
                reverse=True
            )
            for pos in sorted_positions:
                cand_idx = valid_indices[pos]
                ctype = candidates[cand_idx]["payload"].get("content_type", "text")
                if ctype not in seen_types and ContentType(ctype) in requested_types:
                    type_seed_positions.append(pos)
                    seen_types.add(ctype)
            # (No need for dict.fromkeys – the set already guarantees uniqueness)

        selected_local:  List[int] = list(type_seed_positions)
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

        # Map selected positions back to original candidate indices
        return [candidates[valid_indices[pos]] for pos in selected_local]

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
        diverse  = await self._mmr_filter(
            query_emb, reranked, requested_types=effective_types
        )

        logger.info(
            f"Retrieval: dense={len(dense_results)} → fused={len(fused)} → "
            f"reranked={len(reranked)} → mmr={len(diverse)}"
        )
        return diverse, raw_dense_count


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
