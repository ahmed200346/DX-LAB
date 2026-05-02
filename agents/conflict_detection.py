"""
agents/conflict_detection.py (enhanced)
"""

import re
from typing import List, Dict

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from utils.llm import get_llm
from utils.prompts import CONFLICT_DETECTION_PROMPT
from utils.cache import cached_llm_invoke, llm_cache
from utils.rate_limiter import rate_limiter

console = Console()


class ConflictDetectionAgent:
    def __init__(self):
        self._llm = get_llm(temperature=0.1)
        self._chain = CONFLICT_DETECTION_PROMPT | self._llm

    def run(self, findings_text: str, triples_list: List[Dict] = None) -> str:
        console.print(
            f"\n[bold red]Agent 4:[/] Conflict Detection — scanning for contradictions"
        )

        # Pre‑filter: find pairs of triples with same subject/object but opposite effect
        candidate_conflicts = self._find_opposing_triples(triples_list) if triples_list else []

        if not candidate_conflicts:
            # No candidates → shortcut
            conflicts = "NO CONFLICTS DETECTED"
        else:
            # Format candidates into text for LLM
            triples_str = self._format_opposing_pairs(candidate_conflicts)
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Detecting conflicts...", total=None)
                try:
                    conflicts = cached_llm_invoke(
                        self._chain,
                        {"findings": findings_text, "triples": triples_str},
                        llm_cache,
                    )
                    conflicts = conflicts.strip()
                except Exception as e:
                    console.print(f"  [yellow]Conflict detection warning:[/] {e}")
                    conflicts = "NO CONFLICTS DETECTED"

        n = self.count_conflicts(conflicts)
        high = self._count_severity(conflicts, "high")
        if n > 0:
            tag = f"[red]{n} conflict(s)[/]"
            if high:
                tag += f" ([bold red]{high} HIGH severity[/])"
            console.print(f"  [green]✓[/] {tag}")
        else:
            console.print("  [green]✓[/] No significant conflicts found")

        return conflicts

    def _find_opposing_triples(self, triples: List[Dict]) -> List[Dict]:
        """
        Find pairs of triples with the same subject and object,
        but opposite relation effects (activates vs inhibits, etc.)
        from different papers.
        """
        # Map (subj, obj) to list of (relation, paper_id)
        from collections import defaultdict
        edge_map = defaultdict(list)
        for t in triples:
            subj = t.get("subject", "").strip().lower()
            obj = t.get("object", "").strip().lower()
            if not subj or not obj:
                continue
            edge_map[(subj, obj)].append({
                "relation": t.get("relation", ""),
                "paper_id": t.get("paper_id", "")
            })
        # Define opposite pairs
        OPPOSITES = {
            ("activates", "inhibits"),
            ("inhibits", "activates"),
            ("promotes", "reduces"),
            ("reduces", "promotes"),
            ("upregulates", "downregulates"),
            ("downregulates", "upregulates"),
            ("stabilizes", "degrades"),
            ("degrades", "stabilizes"),
        }
        candidates = []
        for (subj, obj), entries in edge_map.items():
            papers_relations = [(e["paper_id"], e["relation"]) for e in entries]
            # Compare each pair
            for i in range(len(papers_relations)):
                pid1, rel1 = papers_relations[i]
                for j in range(i+1, len(papers_relations)):
                    pid2, rel2 = papers_relations[j]
                    if pid1 == pid2:
                        continue
                    if (rel1, rel2) in OPPOSITES or (rel2, rel1) in OPPOSITES:
                        candidates.append({
                            "subject": subj,
                            "object": obj,
                            "paper_a": pid1,
                            "relation_a": rel1,
                            "paper_b": pid2,
                            "relation_b": rel2
                        })
        return candidates

    def _format_opposing_pairs(self, pairs: List[Dict]) -> str:
        if not pairs:
            return "No candidate conflicts."
        lines = []
        for p in pairs:
            lines.append(
                f"Potential conflict: {p['subject']} - paper {p['paper_a']} says {p['relation_a']}, "
                f"paper {p['paper_b']} says {p['relation_b']} on {p['object']}"
            )
        return "\n".join(lines)

    def count_conflicts(self, text: str) -> int:
        return sum(
            1 for l in text.splitlines()
            if l.strip().upper().startswith("CONFLICT")
        )

    def has_conflicts(self, text: str) -> bool:
        return self.count_conflicts(text) > 0

    def get_high_severity_conflicts(self, text: str) -> List[str]:
        blocks = re.split(r"(?=CONFLICT\s*\[\d+\])", text, flags=re.IGNORECASE)
        return [b for b in blocks if "SEVERITY: HIGH" in b.upper()]

    def _count_severity(self, text: str, level: str) -> int:
        return text.upper().count(f"SEVERITY: {level.upper()}")