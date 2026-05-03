"""
tools/pubmed_tool.py
PubMed API wrapper — implements a LangChain Tool for paper retrieval.
"""

import re
import time
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import requests
from langchain.tools import BaseTool
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings


def _build_params(extra: Dict) -> Dict:
    params = {
        "retmode": "json",
        "tool": "hypothesis_assistant",
        "email": "research@assistant.ai",
    }
    if settings.PUBMED_API_KEY:
        params["api_key"] = settings.PUBMED_API_KEY
    params.update(extra)
    return params


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def search_pubmed(query: str, max_results: int) -> List[str]:
    params = _build_params({
        "db": "pubmed",
        "term": f"{query}[Title/Abstract] AND hasabstract[text] AND english[lang]",
        "retmax": max_results,
        "sort": "relevance",
        "datetype": "pdat",
        "reldate": 3650,
    })
    resp = requests.get(settings.PUBMED_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("esearchresult", {}).get("idlist", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_abstracts(pmids: List[str]) -> List[Dict[str, Any]]:
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
        "tool": "hypothesis_assistant",
        "email": "research@assistant.ai",
    }
    if settings.PUBMED_API_KEY:
        params["api_key"] = settings.PUBMED_API_KEY
    resp = requests.get(settings.PUBMED_FETCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    return _parse_pubmed_xml(resp.text)


def _smart_truncate(text: str, max_len: int = None) -> str:
    if max_len is None:
        max_len = settings.MAX_ABSTRACT_LENGTH
    if len(text) <= max_len:
        return text
    head = int(max_len * 0.4)
    tail = int(max_len * 0.3)
    return text[:head] + " ... " + text[-tail:]


def _parse_pubmed_xml(xml_text: str) -> List[Dict[str, Any]]:
    papers = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return papers

    for article in root.findall(".//PubmedArticle"):
        try:
            medline = article.find("MedlineCitation")
            art = medline.find("Article")

            title_el = art.find("ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else "No title"
            title = re.sub(r"\s+", " ", title).strip()

            abstract_texts = art.findall(".//AbstractText")
            abstract = " ".join(
                "".join(el.itertext()) for el in abstract_texts
            ).strip()
            if not abstract:
                continue

            # Smart truncation
            abstract = _smart_truncate(abstract)

            authors = []
            for author in art.findall(".//Author")[:3]:
                last = author.findtext("LastName", "")
                fore = author.findtext("ForeName", "")
                if last:
                    authors.append(f"{last} {fore}".strip())
            author_str = ", ".join(authors) + (" et al." if len(authors) >= 3 else "")

            year = (
                medline.findtext(".//PubDate/Year")
                or medline.findtext(".//PubDate/MedlineDate", "")[:4]
            )

            pmid = medline.findtext("PMID", "")
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            papers.append({
                "pmid": pmid,
                "title": title,
                "authors": author_str,
                "year": year,
                "abstract": abstract,
                "url": url,
            })
        except Exception:
            continue
    return papers


class PubMedRetrievalTool(BaseTool):
    name: str = "pubmed_retrieval"
    description: str = (
        "Search PubMed for scientific papers. "
        "Input: research query string. "
        "Output: list of paper dicts with title, abstract, authors, year, url."
    )
    max_results: int = settings.MAX_PAPERS

    def _run(self, query: str) -> List[Dict[str, Any]]:
        pmids = search_pubmed(query, self.max_results)
        time.sleep(0.34)
        papers = fetch_abstracts(pmids)
        return papers

    async def _arun(self, query: str) -> List[Dict[str, Any]]:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run, query)