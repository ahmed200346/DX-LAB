"""
agents/novelty_filter.py
Agent 3.5 (Novelty Filter): Checks if hypotheses are already known.
"""

from typing import List, Dict, Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from utils.llm import get_analysis_llm
from utils.prompts import NOVELTY_CHECK_PROMPT
from utils.cache import cached_llm_invoke, llm_cache
from utils.rate_limiter import rate_limiter   # <-- changed

console = Console()


class NoveltyFilterAgent:
    def __init__(self):
        self._llm = get_analysis_llm()
        self._chain = NOVELTY_CHECK_PROMPT | self._llm

    def run(self, hypotheses: List[Dict], papers: List[Dict]) -> List[Dict]:
        console.print(
            f"\n[bold cyan]Agent 3.5:[/] Novelty Filter — checking originality of {len(hypotheses)} hypotheses"
        )

        papers_block = "\n\n".join(
            f"[ID: {p.get('paper_id', i+1)}] {p.get('abstract', '')[:600]}"
            for i, p in enumerate(papers)
        )

        results = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Assessing novelty...", total=len(hypotheses))
            for h in hypotheses:
                statement = h.get("statement", "")
                if not statement:
                    progress.advance(task)
                    results.append(h)
                    continue

                try:
                    rate_limiter.wait_if_needed(estimated_tokens=500)
                    raw = cached_llm_invoke(
                        self._chain,
                        {"hypothesis_statement": statement, "papers": papers_block},
                        llm_cache,
                    )
                    rate_limiter.record(tokens_used=len(raw)//3+100)
                    verdict = self._parse_verdict(raw)
                except Exception as e:
                    console.print(f"  [yellow]Novelty check failed: {e}[/]")
                    verdict = {"already_known": False, "confidence": 0.5, "reason": "error"}

                if verdict.get("already_known"):
                    h["novelty_score"] = max(1, h.get("novelty_score", 5) - 3)
                    h["novelty_flag"] = "verbatim_match" if verdict.get("verbatim_match") else "likely_known"
                else:
                    h["novelty_flag"] = "novel"
                h["novelty_check_confidence"] = verdict.get("confidence", 1.0)
                h["closest_known_paper"] = verdict.get("closest_paper_id")
                progress.advance(task)
                results.append(h)

        console.print(f"  [green]✓[/] Novelty assessment complete")
        return results

    def _parse_verdict(self, text: str) -> Dict:
        import json
        text = text.strip()
        if text.startswith("```"):
            text = "\n".join(l for l in text.splitlines() if not l.startswith("```")).strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return {"already_known": False, "confidence": 0.5}
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            return {"already_known": False, "confidence": 0.5}