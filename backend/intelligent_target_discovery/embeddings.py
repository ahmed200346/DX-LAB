"""
embeddings.py — EmbeddingService, GroqClient, HFInferenceClient.

These are tightly coupled: EmbeddingService owns and delegates to the others.
Keep them in a single file.
"""

from __future__ import annotations

import asyncio
import json
import re
from io import BytesIO
from typing import List, Optional

import aiohttp
import numpy as np
from loguru import logger
from PIL import Image
from sentence_transformers import SentenceTransformer

from config import cfg
from models import ContentType


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
                    logger.debug(f"Groq responded ({len(content)} chars)")
                    return content
                elif resp.status == 429:
                    retry_after = resp.headers.get("retry-after", "2")
                    logger.warning(f"Groq rate limit (retry-after={retry_after}s) — falling back")
                    return f"__RATE_LIMIT__:{retry_after}"
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
            logger.warning("Groq request timed out after 30s — falling back")
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

    async def _post_json(self, model: str, payload: dict) -> object:
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