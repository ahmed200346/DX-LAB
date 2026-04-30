"""
search.py — WebSearchAgent.

Handles all outbound I/O: SearXNG, DuckDuckGo, PubMed, Semantic Scholar,
Europe PMC, ClinicalTrials.gov, Jina/trafilatura content extraction, PDF
fetching.
"""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
import fitz
from ddgs import DDGS
from loguru import logger

from config import cfg
from models import ContentType
from utils import CircuitBreaker, _content_is_biomedically_relevant, _domain_is_blocked

try:
    import trafilatura
    _TRAFILATURA_AVAILABLE = True
except ImportError:
    _TRAFILATURA_AVAILABLE = False
    logger.warning(
        "trafilatura not installed — Jina-only extraction active. "
        "Run: pip install trafilatura"
    )


async def _false_coro() -> bool:
    return False


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

    # ── Search backends ────────────────────────────────────────────────────────

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
            logger.warning("DDG fallback timed out after 30s")
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

    # ── Content extraction ─────────────────────────────────────────────────────

    async def _extract_content_race(self, url: str) -> str:
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

    # ── Main collect entry point ───────────────────────────────────────────────

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
