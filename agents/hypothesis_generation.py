"""
agents/hypothesis_generation.py (enhanced)
"""

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from config.settings import settings
from utils.llm import get_hypothesis_llm, get_llm
from utils.prompts import HYPOTHESIS_GENERATION_PROMPT, THEME_CLUSTERING_PROMPT
from utils.cache import cached_llm_invoke, llm_cache
from utils.rate_limiter import rate_limiter   # <-- changed

console = Console()


@dataclass
class Hypothesis:
    index: int
    statement: str
    addresses: str
    rationale: str
    experiment: str
    impact_score: int
    novelty_score: int
    theme: str
    citations: List[str] = None
    novelty_flag: str = "unchecked"

    def __post_init__(self):
        if self.citations is None:
            self.citations = []

    def composite_score(self) -> float:
        return round(0.6 * self.impact_score + 0.4 * self.novelty_score, 1)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["composite_score"] = self.composite_score()
        return d


class HypothesisGenerationAgent:
    def __init__(self):
        self._llm = get_hypothesis_llm()
        self._chain = HYPOTHESIS_GENERATION_PROMPT | self._llm
        self._cluster_llm = get_llm(temperature=0.1)
        self._cluster_chain = THEME_CLUSTERING_PROMPT | self._cluster_llm


    
    
    def run(
        self,
        query: str,
        extracted_knowledge: str,
        gaps: str,
        conflicts: str,
        causal_paths: str = "",
        known_findings: str = "",
        papers: List[Dict] = None,
        findings: List[Dict] = None,      # NEW: for context validation
        num_hypotheses: int = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        n = num_hypotheses or settings.NUM_HYPOTHESES
        console.print(
            f"\n[bold green]Agent 5:[/] Hypothesis Generation — synthesising [bold]{n}[/] hypotheses"
        )

        prompt_inputs = {
            "query": query,
            "extracted_knowledge": extracted_knowledge,
            "gaps": gaps,
            "conflicts": conflicts,
            "causal_paths": causal_paths or "none",
            "known_findings": known_findings or "none",
            "num_hypotheses": n,
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Generating hypotheses (Groq + CoT)...", total=None)
            try:
                if stream:
                    rendered_prompt = HYPOTHESIS_GENERATION_PROMPT.format(**prompt_inputs)
                    progress.stop()
                    console.print("\n[dim]── Streaming hypotheses ──[/dim]")
                    chunks = []
                    for chunk in self._llm.stream_call(rendered_prompt):
                        print(chunk, end="", flush=True)
                        chunks.append(chunk)
                    print()
                    raw = "".join(chunks)
                else:
                    rate_limiter.wait_if_needed(estimated_tokens=1500)
                    response = self._chain.invoke(prompt_inputs)
                    rate_limiter.record(tokens_used=len(str(response))//3+300)
                    raw = response.content if hasattr(response, "content") else str(response)
            except Exception as e:
                console.print(f"  [red]Hypothesis generation error:[/] {e}")
                raw = _fallback_hypothesis(query)

        parsed = _parse_hypotheses(raw)

        # ---- SAME‑CONTEXT FILTER (reject hypotheses that combine papers without ≥2 shared entities) ----
        if findings and papers and len(papers) >= 2:
            parsed = self._filter_by_context(parsed, findings, papers)

        # Retry once if we got fewer hypotheses than requested
        if len(parsed) < n and not stream:
            console.print(f"  [yellow]Only {len(parsed)} hypotheses parsed, retrying...[/]")
            prompt_inputs["num_hypotheses"] = n * 2
            try:
                rate_limiter.wait_if_needed(estimated_tokens=1500)
                response = self._chain.invoke(prompt_inputs)
                rate_limiter.record(tokens_used=len(str(response))//3+300)
                raw = response.content if hasattr(response, "content") else str(response)
                parsed = _parse_hypotheses(raw)
            except Exception:
                pass
            parsed = parsed[:n]

        if papers:
            parsed = _anchor_citations_semantic(parsed, papers, extracted_knowledge)

        ranked = sorted(parsed, key=lambda h: h.composite_score(), reverse=True)

        themes = self._cluster_themes(raw)

        console.print(
            f"  [green]✓[/] Generated [bold]{len(parsed)}[/] hypotheses "
            f"(top composite score: {ranked[0].composite_score() if ranked else 'N/A'})"
        )

        return {
            "raw_text": raw,
            "hypotheses": [h.to_dict() for h in parsed],
            "ranked": [h.to_dict() for h in ranked],
            "themes": themes,
        }
    



    def _cluster_themes(self, hypotheses_text: str) -> str:
        try:
            response = self._cluster_chain.invoke({"hypotheses": hypotheses_text})
            return response.content if hasattr(response, "content") else str(response)
        except Exception:
            return ""

    # ADD THIS METHOD to the class:
    def _filter_by_context(self, hypotheses: List[Hypothesis],
                           findings: List[Dict], papers: List[Dict]) -> List[Hypothesis]:
        """Keep only hypotheses that fuse evidence from papers sharing ≥2 entities."""
        # Build entity sets per paper ID (from findings)
        paper_entities = {}
        for f in findings:
            pid = str(f.get("paper_id", ""))
            ents = set()
            entities_dict = f.get("entities", {})
            if isinstance(entities_dict, dict):
                for vals in entities_dict.values():
                    if isinstance(vals, list):
                        ents.update(v.strip().lower() for v in vals)
            paper_entities[pid] = ents

        def hypothesis_has_overlap(h: Hypothesis) -> bool:
            # Extract paper IDs from rationale (e.g., [1,3] or Paper 1)
            cited = re.findall(r'\[(\d+(?:,\s*\d+)*)\]', h.rationale)
            if not cited:
                cited = re.findall(r'\b(\d+)\b', h.rationale)
            pids = set()
            for match in cited:
                for num in re.split(r',\s*', match):
                    pids.add(num)
            if len(pids) < 2:
                return True  # can't check overlap, keep
            # Compute intersection of all entity sets
            sets = [paper_entities.get(pid, set()) for pid in pids]
            common = sets[0]
            for s in sets[1:]:
                common = common & s
            return len(common) >= 2

        filtered = [h for h in hypotheses if hypothesis_has_overlap(h)]
        if len(filtered) < len(hypotheses):
            console.print(f"  [dim]Context filter removed {len(hypotheses)-len(filtered)} hypotheses with insufficient paper overlap.[/]")
        return filtered if filtered else hypotheses
# ─── Parsing ──────────────────────────────────────────────────
def _strip_reasoning(text: str) -> str:
    end_tag = "</REASONING>"
    if end_tag in text:
        text = text[text.index(end_tag) + len(end_tag):]
        return text.strip()
    m = re.search(r"HYPOTHESIS\s*\[?\d+\]?", text, re.IGNORECASE)
    if m:
        return text[m.start():]
    return text


def _parse_hypotheses(text: str) -> List[Hypothesis]:
    text = _strip_reasoning(text)
    hypotheses = []
    blocks = re.split(r"HYPOTHESIS\s*\[?\d+\]?:?\s*", text, flags=re.IGNORECASE)
    blocks = [b.strip() for b in blocks[1:] if b.strip() and len(b) > 50]

    for idx, block in enumerate(blocks):
        h = Hypothesis(
            index=idx + 1,
            statement=_field(block, "Statement"),
            addresses=_field(block, "Addresses"),
            rationale=_field(block, "Rationale"),
            experiment=_field(block, "Experiment") or _field(block, "Testability"),
            impact_score=_score(block, "Impact Score"),
            novelty_score=_score(block, "Novelty Score"),
            theme=_field(block, "Theme"),
        )
        if h.statement:
            hypotheses.append(h)
    return hypotheses


def _field(block: str, name: str) -> str:
    pattern = rf"{name}:\s*(.+?)(?=\n[A-Z][a-zA-Z ]+:|\Z)"
    m = re.search(pattern, block, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip().replace("\n", " ")
    if name == "Statement":
        return block.split("\n")[0].strip()[:400]
    return ""


def _score(block: str, name: str) -> int:
    m = re.search(rf"{name}:\s*(\d+)", block, re.IGNORECASE)
    return max(1, min(10, int(m.group(1)))) if m else 5


def _anchor_citations_semantic(
    hypotheses: List[Hypothesis],
    papers: List[Dict],
    findings_text: str,
) -> List[Hypothesis]:
    try:
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer('all-MiniLM-L6-v2')
        hyp_texts = [h.statement for h in hypotheses]
        paper_texts = [p.get("title", "") + " " + p.get("abstract", "") for p in papers]
        hyp_emb = model.encode(hyp_texts, convert_to_tensor=True)
        paper_emb = model.encode(paper_texts, convert_to_tensor=True)
        for i, h in enumerate(hypotheses):
            hits = util.semantic_search(hyp_emb[i], paper_emb, top_k=3)[0]
            urls = []
            for hit in hits:
                url = papers[hit['corpus_id']].get("url", "")
                if url:
                    urls.append(url)
            h.citations = urls if urls else _keyword_citations(h, papers)
    except ImportError:
        for h in hypotheses:
            h.citations = _keyword_citations(h, papers)
    return hypotheses


def _keyword_citations(h: Hypothesis, papers: List[Dict]) -> List[str]:
    words = set(re.findall(r"\b[A-Z][A-Z0-9]+\b", h.statement))
    if not words:
        return []
    matched = []
    for paper in papers:
        title = paper.get("title", "") + " " + paper.get("abstract", "")
        if any(w in title for w in words):
            url = paper.get("url", "")
            if url and url not in matched:
                matched.append(url)
        if len(matched) >= 3:
            break
    return matched


def _check_context_consistency(h: Hypothesis, papers: List[Dict]) -> str:
    """Flag if hypothesis mixes cancer types or KRAS mutation subtypes."""
    cited_ids = re.findall(r'\[(\d+)\]', h.rationale)
    cancer_types = set()
    for pid in cited_ids:
        paper = next((p for p in papers if str(p.get('paper_id','')) == pid), None)
        if paper:
            text = (paper.get('title','') + paper.get('abstract','')).lower()
            if 'nsclc' in text or 'lung' in text: cancer_types.add('NSCLC')
            if 'pancreatic' in text or 'pdac' in text: cancer_types.add('PDAC')
            if 'colorectal' in text or 'crc' in text: cancer_types.add('CRC')
    if len(cancer_types) > 1:
        return f"WARNING: mixes {', '.join(cancer_types)}"
    return "ok"




def _fallback_hypothesis(query: str) -> str:
    return (
        "HYPOTHESIS [1]:\n"
        f"Statement: Further mechanistic investigation into {query} is warranted.\n"
        "Addresses: GAP 1\n"
        "Rationale: Literature synthesis was incomplete due to a processing error.\n"
        "Experiment: Please re-run the pipeline with a valid GROQ_API_KEY.\n"
        "Impact Score: 5\n"
        "Novelty Score: 5\n"
        "Theme: General Research"
    )