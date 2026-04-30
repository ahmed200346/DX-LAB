"""
storage.py — Persistence layer.

Fixes vs original:
  • CacheLayer.get() returns (data, sgv, targets, chemicals) 4-tuple.
  • CacheLayer.set() accepts targets + chemicals keyword args.
  • chemicals_collection handled in collection_for_type().
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis
from loguru import logger
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

from config import cfg
from models import ContentType


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
            ContentType.TEXT:     "texts_collection",
            ContentType.PDF:      "pdfs_collection",
            ContentType.IMAGE:    "images_collection",
            ContentType.VIDEO:    "videos_collection",
            ContentType.TABLE:    "tables_collection",
            ContentType.GRAPH:    "graphs_collection",
            ContentType.CODE:     "code_collection",
            ContentType.CHEMICAL: "chemicals_collection",
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
    ) -> Optional[Tuple[List[Dict[str, Any]], float, List[Dict[str, Any]], List[Dict[str, Any]]]]:
        """
        Returns (data, sgv, targets, chemicals) or None on miss.
        """
        if not self._redis:
            return None
        try:
            key    = self._make_key(query, data_types, filters)
            cached = await self._redis.get(key)
            if cached:
                logger.debug(f"Cache HIT key={key[:20]}…")
                envelope = json.loads(cached)
                if isinstance(envelope, list):
                    # Legacy format — no targets/chemicals
                    return envelope, 0.90, [], []
                data      = envelope.get("data",      [])
                sgv       = envelope.get("sgv",       0.90)
                targets   = envelope.get("targets",   [])
                chemicals = envelope.get("chemicals", [])
                return data, sgv, targets, chemicals
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
        targets:    Optional[List[Dict[str, Any]]] = None,
        chemicals:  Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        if not self._redis:
            return
        try:
            key      = self._make_key(query, data_types, filters)
            envelope = {
                "data":      data,
                "sgv":       sgv,
                "targets":   targets   or [],
                "chemicals": chemicals or [],
            }
            await self._redis.set(key, json.dumps(envelope), ex=cfg.CACHE_TTL_SECONDS)
            logger.debug(
                f"Cache SET key={key[:20]}… sgv={sgv:.4f} "
                f"targets={len(targets or [])} chemicals={len(chemicals or [])}"
            )
        except Exception as exc:
            logger.debug(f"Cache set error: {exc}")

    async def close(self):
        if self._redis:
            try:
                await self._redis.aclose()
            except AttributeError:
                await self._redis.close()