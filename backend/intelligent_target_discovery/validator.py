"""
validator.py — ValidatorAgent  v2.0

Changes from v1:
  • BioNER-enhanced entity overlap scoring added to relevance.
    Items whose NER entities overlap with query entities get a boost
    to their _relevance score — ensuring biomedically important but
    tersely-written documents aren't dropped by cosine threshold alone.
  • `_ner_entity_overlap()` static helper.
  • `_entity_boosted_relevance()` combines cosine sim with NER overlap.
  • All other logic (dedup, NLI, faithfulness, SGV) unchanged.
  • v2.1: Accepts shared BioNERService instance to avoid redundant loading.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import numpy as np
from loguru import logger
from scipy.special import softmax as scipy_softmax
from sentence_transformers import CrossEncoder
from sklearn.metrics.pairwise import cosine_similarity

from config import cfg
from embeddings import EmbeddingService
from models import ContentType, ValidatedItem, ValidationMetrics
from utils import _BIOMEDICAL_RE
from bio_ner import BioNERService


class ValidatorAgent:
    def __init__(
        self,
        embed_service: EmbeddingService,
        ner_service: Optional[BioNERService] = None,
    ):
        self._embed           = embed_service
        self._nli_model:      Optional[CrossEncoder] = None
        self._nli_num_labels: Optional[int]          = None
        self._biomed_entity_re = _BIOMEDICAL_RE
        # Accept shared NER instance, otherwise create a new one.
        self._ner = ner_service if ner_service is not None else BioNERService()

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
        if citation_count is None:
            return domain_trust
        boost = ValidatorAgent._citation_boost(citation_count)
        return 0.70 * domain_trust + 0.30 * boost

    @staticmethod
    def _adaptive_relevance_threshold(query: str, content: str) -> float:
        base       = cfg.RELEVANCE_THRESHOLD_BASE
        word_count = len(query.split())
        if word_count > 5:
            base -= 0.02 * min(word_count - 5, 5)
        if len(content) < 300:
            base -= 0.03
        return max(cfg.RELEVANCE_THRESHOLD_FLOOR, base)

    # ── NEW: BioNER entity overlap relevance boost ─────────────────────────────

    @staticmethod
    def _ner_entity_overlap(
        query_entities: Set[str], content: str
    ) -> float:
        """
        Returns a normalised overlap score (0–1) between query NER entities
        and entity mentions in content.
        0 if no query entities, 1 if all query entities found in content.
        """
        if not query_entities:
            return 0.0
        content_lower = content.lower()
        hits = sum(1 for e in query_entities if e.lower() in content_lower)
        return hits / len(query_entities)

    def _entity_boosted_relevance(
        self,
        cosine_sim:     float,
        content:        str,
        query_entities: Set[str],
        boost_weight:   float = 0.15,
    ) -> float:
        """
        Blend cosine similarity with NER entity overlap.
        boost_weight controls maximum contribution of entity overlap.
        """
        overlap = self._ner_entity_overlap(query_entities, content)
        return min(1.0, cosine_sim + boost_weight * overlap)

    # ── Unchanged from v1 ────────────────────────────────────────────────────

    async def _compute_faithfulness(
        self, query: str, relevant_items: List[Dict[str, Any]]
    ) -> float:
        if not relevant_items:
            return 0.0

        groq      = self._embed.groq
        top_items = relevant_items[:3]
        rest_items = relevant_items[3:10]
        groq_scores: List[float] = []

        for item in top_items:
            score = await groq.verify_faithfulness(query, item.get("content", ""))
            groq_scores.append(score)

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

        nli_coverage = nli_covered / max(len(rest_items), 1) if rest_items else 0.0
        groq_avg     = float(np.mean(groq_scores)) if groq_scores else 0.5

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
                            f"Contradiction detected: p_contra={row[0]:.3f} | "
                            f"a={url_a[:60]} | b={url_b[:60]}"
                        )
            else:
                flags = [
                    bool(s > cfg.CONTRADICTION_THRESHOLD_1L)
                    for s in scores_arr.flatten()
                ]

            rate = sum(flags) / len(flags)
            logger.debug(
                f"NLI ({num_labels}-label) contradiction: "
                f"{sum(flags)}/{len(pairs)} pairs → rate={rate:.3f}"
            )
            return rate
        except Exception as exc:
            logger.warning(f"NLI contradiction check failed: {exc} — assuming 0.0")
            return 0.0

    # ── Main validate pipeline (with BioNER integration) ─────────────────────

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

        # ── BioNER: extract query entities for overlap boost (use shared instance) ──
        query_ner   = self._ner.extract_query_entities(query)
        query_genes = set(query_ner.get("GENE", []))
        query_drugs = set(query_ner.get("DRUG", []))
        query_disea = set(query_ner.get("DISEASE", []))
        all_query_entities: Set[str] = query_genes | query_drugs | query_disea
        logger.debug(
            f"ValidatorAgent BioNER query entities: "
            f"genes={query_genes} drugs={query_drugs} diseases={query_disea}"
        )

        # ── Relevance scoring with NER boost ─────────────────────────────────
        scored_items = []
        for item in deduped:
            content = item.get("content", "")[:2000]
            if not content.strip():
                continue
            content_emb = await self._embed.embed_text_safe(content)
            if content_emb is None:
                continue
            q   = np.array(query_emb_raw).reshape(1, -1)
            d   = np.array(content_emb).reshape(1, -1)
            cos = float(cosine_similarity(q, d)[0][0])

            # Apply entity overlap boost
            boosted = self._entity_boosted_relevance(
                cos, content, all_query_entities
            )
            item["_relevance"]      = boosted
            item["_cosine_sim"]     = cos     # keep raw for debugging
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
            f"ner_entities={len(all_query_entities)} | "
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