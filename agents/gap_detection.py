"""
agents/gap_detection.py (enhanced)
"""

import re

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from utils.llm import get_llm
from utils.prompts import GAP_DETECTION_PROMPT
from utils.cache import cached_llm_invoke, llm_cache
from utils.rate_limiter import rate_limiter   # <-- changed

console = Console()


class GapDetectionAgent:
    def __init__(self):
        self._llm = get_llm(temperature=0.3)
        self._chain = GAP_DETECTION_PROMPT | self._llm

    def run(self, summaries_text: str, query: str, study_types: str = "",
            causal_paths: str = "") -> str:
        console.print(
            f"\n[bold yellow]Agent 3:[/] Gap Detection — finding missing knowledge"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Detecting research gaps...", total=None)
            try:
                gaps = cached_llm_invoke(
                    self._chain,
                    {
                        "summaries": summaries_text,
                        "query": query,
                        "study_types": study_types or "not specified",
                        "causal_paths": causal_paths or "none",
                    },
                    llm_cache,
                )
                gaps = gaps.strip()
            except Exception as e:
                console.print(f"  [yellow]Gap detection warning:[/] {e}")
                gaps = "GAP [1]: Insufficient data to perform gap detection."

        if not re.search(r"^GAP\s*[\[{(]?\d", gaps, re.MULTILINE | re.IGNORECASE):
            gaps = _reformat_gaps(gaps)

        n = self.count_gaps(gaps)
        console.print(f"  [green]✓[/] {n} gaps identified")
        return gaps

    def count_gaps(self, gaps_text: str) -> int:
        return len(re.findall(r"^GAP\s*[\[{(]?\d", gaps_text, re.MULTILINE | re.IGNORECASE))


def _reformat_gaps(raw: str) -> str:
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    reformatted = []
    gap_num = 1
    for line in lines:
        clean = line.lstrip("0123456789.-*•) ").strip()
        if len(clean) > 20:
            reformatted.append(f"GAP [{gap_num}]: {clean}")
            gap_num += 1
        if gap_num > 5:
            break
    return "\n".join(reformatted) if reformatted else "GAP [1]: Research gaps could not be determined."