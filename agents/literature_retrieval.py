"""
agents/literature_retrieval.py
Agent 1: Literature Retrieval Agent
"""

from typing import Any, Dict, List, Optional
import re
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from config.settings import settings
from utils.prompts import RELEVANCE_FILTER_PROMPT
from utils.llm import get_llm
from utils.cache import cached_llm_invoke, llm_cache
from tools.pubmed_tool import PubMedRetrievalTool

console = Console()


class LiteratureRetrievalAgent:
    def __init__(self, max_papers: Optional[int] = None):
        self.max_papers = max_papers or settings.MAX_PAPERS
        self._pubmed_tool = PubMedRetrievalTool(max_results=self.max_papers)
        self._rerank_llm = get_llm(temperature=0.0)

    def run(self, query: str) -> List[Dict[str, Any]]:
        console.print(
            f"\n[bold blue]Agent 1:[/] Literature Retrieval — [italic]{query}[/italic]"
        )

        papers: List[Dict] = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Querying PubMed...", total=None)
            try:
                pubmed_papers = self._pubmed_tool._run(query)
                papers.extend(pubmed_papers)
                progress.update(task, description=f"PubMed: {len(pubmed_papers)} papers found")
            except Exception as e:
                console.print(f"  [yellow]PubMed warning:[/] {e}")

        # 1. Keyword relevance filter (now active)
        papers = self._filter_by_relevance(papers, query)
        console.print(f"  [dim]After keyword filter: {len(papers)} papers[/]")

        # 2. LLM re-ranking if too many papers
        if settings.USE_LLM_RE_RANKING and len(papers) > self.max_papers * settings.LLM_RERANK_THRESHOLD:
            papers = self._llm_rerank(papers, query)

        # 3. Deduplicate, date boost, trim
        papers = self._deduplicate_with_date_boost(papers)
        papers = papers[: self.max_papers]

        console.print(
            f"  [green]✓[/] Retrieved [bold]{len(papers)}[/] unique, relevant papers"
        )
        return papers

    def _filter_by_relevance(self, papers: List[Dict], query: str) -> List[Dict]:
        """Basic keyword relevance filter."""
        keywords = set(re.findall(r'\b\w+\b', query.lower()))
        stop = {"the", "a", "an", "of", "in", "and", "or", "for", "with", "is", "on", "to", "by", "as"}
        keywords -= stop
        if not keywords:
            return papers
        relevant = []
        for paper in papers:
            text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
            if any(kw in text for kw in keywords):
                relevant.append(paper)
        return relevant

    def _llm_rerank(self, papers: List[Dict], query: str) -> List[Dict]:
        """Score papers 1-10 for relevance using LLM, keep top."""
        console.print("  [dim]Re-ranking papers with LLM...[/]")
        scored = []
        for idx, p in enumerate(papers):
            abstract = p.get("abstract", "")
            try:
                chain = RELEVANCE_FILTER_PROMPT | self._rerank_llm
                resp = cached_llm_invoke(chain, {"abstract": abstract, "query": query}, llm_cache)
                # Simple scoring: if "RELEVANT" in uppercase, score 8 else 2
                score = 8 if "RELEVANT" in resp.upper() else 2
            except Exception:
                score = 5
            scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:self.max_papers]]

    def _deduplicate_with_date_boost(self, papers: List[Dict]) -> List[Dict]:
        """Deduplicate by normalized title, apply recency boost."""
        seen_titles: set = set()
        unique: List[Dict] = []
        current_year = datetime.now().year
        for paper in papers:
            norm_title = paper.get("title", "").lower().strip()[:80]
            if norm_title and norm_title not in seen_titles:
                seen_titles.add(norm_title)
                # Recency boost: if year within last 2 years, add a score bump via ordering
                year = int(paper.get("year", 0) or 0)
                boost = 0.2 if year >= current_year - 2 else 0.0
                # We'll sort by relevance score later; just store boost for now
                paper["_recency_boost"] = boost
                unique.append(paper)
        # Sort by recency boost (newer first) then original order
        unique.sort(key=lambda p: p.get("_recency_boost", 0), reverse=True)
        return unique