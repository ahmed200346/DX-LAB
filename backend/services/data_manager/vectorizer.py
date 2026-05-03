"""
vectorizer.py — VectorizerAgent.

Handles chunking and embedding of ValidatedItems into Qdrant PointStructs.
Supports text, PDF (section-aware), image/graph (CLIP), table, and code.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import aiohttp
from loguru import logger
from llama_index.core.node_parser import SentenceSplitter
from qdrant_client.models import PointStruct

from config import cfg
from embeddings import EmbeddingService
from models import ContentType, ValidatedItem


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
