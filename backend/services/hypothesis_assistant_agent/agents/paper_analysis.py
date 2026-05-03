"""
agents/paper_analysis.py (enhanced)
"""

import json
import concurrent.futures
from typing import Any, Dict, List

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from config.settings import settings
from utils.llm import get_analysis_llm
from utils.prompts import PAPER_ANALYSIS_PROMPT
from utils.cache import cached_llm_invoke, llm_cache
from utils.rate_limiter import rate_limiter   # <-- changed

console = Console()
BATCH_SIZE = 5


class PaperAnalysisAgent:
    def __init__(self):
        self._llm = get_analysis_llm()
        self._chain = PAPER_ANALYSIS_PROMPT | self._llm

    def run(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        console.print(
            f"\n[bold teal]Agent 2:[/] Paper Analysis — extracting entities from "
            f"[bold]{len(papers)}[/] papers"
        )

        all_findings: List[Dict] = []
        batches = _batch(papers, BATCH_SIZE)
        workers = min(settings.PARALLEL_ANALYSIS_WORKERS, len(batches))
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            if workers <= 1:
                task = progress.add_task("Analysing batches...", total=len(batches))
                for i, batch in enumerate(batches):
                    progress.update(task, description=f"Analysing batch {i+1}/{len(batches)}...")
                    findings = self._analyse_batch(batch, offset=i * BATCH_SIZE)
                    all_findings.extend(findings)
                    progress.advance(task)
            else:
                task = progress.add_task(
                    f"Analysing {len(batches)} batches in parallel ({workers} workers)...",
                    total=len(batches),
                )
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    future_to_idx = {
                        executor.submit(self._analyse_batch, batch, i * BATCH_SIZE): i
                        for i, batch in enumerate(batches)
                    }
                    for future in concurrent.futures.as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        findings = future.result()
                        all_findings.extend(findings)
                        progress.advance(task)

        console.print(
            f"  [green]✓[/] Extracted findings from [bold]{len(all_findings)}[/] papers"
        )
        return all_findings

    def get_summary_text(self, findings: List[Dict]) -> str:
        lines = []
        for f in findings:
            entities = f.get("entities", {})
            if not isinstance(entities, dict):
                entities = {}
            drugs = ", ".join(entities.get("drugs", []))
            genes = ", ".join(entities.get("genes", []))
            pathways = ", ".join(entities.get("pathways", []))
            study_type = f.get("study_type", "unknown")
            line = (
                f"Paper {f.get('paper_id', '?')} [{study_type}]: "
                f"Drugs: {drugs or 'none'} | Genes: {genes or 'none'} | "
                f"Pathways: {pathways or 'none'} | "
                f"Outcome: {f.get('outcome', '')} | "
                f"Conclusion: {f.get('conclusion', '')}"
            )
            lines.append(line)
        return "\n".join(lines)

    def get_study_types_summary(self, findings: List[Dict]) -> str:
        from collections import Counter
        types = Counter(f.get("study_type", "unknown") for f in findings)
        return ", ".join(f"{t}: {c}" for t, c in types.most_common())

    def _analyse_batch(self, batch: List[Dict], offset: int = 0) -> List[Dict]:
        abstract_block = "\n\n".join(
            f"[{offset + j + 1}] {p.get('title', 'Untitled')}\n{p.get('abstract', '')}"
            for j, p in enumerate(batch)
        )
        try:
            # Use the global rate_limiter
            rate_limiter.wait_if_needed(estimated_tokens=1000)
            raw = cached_llm_invoke(
                self._chain,
                {"abstracts": abstract_block},
                llm_cache,
            )
            rate_limiter.record(tokens_used=len(raw) // 3 + 200)
            findings = _safe_parse_json(raw)
        except Exception as e:
            console.print(f"  [yellow]Analysis batch warning:[/] {e}")
            findings = _fallback_findings(batch, offset)
        return findings


def _batch(items, size):
    return [items[i:i+size] for i in range(0, len(items), size)]


def _safe_parse_json(text: str) -> List[Dict]:
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines() if not l.startswith("```")).strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return []


def _fallback_findings(batch: List[Dict], offset: int) -> List[Dict]:
    return [
        {
            "paper_id": str(offset + j + 1),
            "entities": {"drugs": [], "genes": [], "pathways": []},
            "outcome": p.get("abstract", "")[:200],
            "conclusion": "Extraction failed — using raw abstract.",
            "study_type": "unknown",
        }
        for j, p in enumerate(batch)
    ]