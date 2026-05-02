"""
utils/output_formatter.py (enhanced)
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Union

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from config.settings import settings
from utils.prompts import SUMMARY_REPORT_PROMPT
from utils.llm import get_llm

console = Console()


def print_banner(query: str) -> None:
    console.print(
        Panel.fit(
            f"[bold cyan]🧠 Hypothesis Generation Assistant[/]\n"
            f"[dim]Query: [italic]{query}[/italic][/dim]",
            border_style="cyan",
        )
    )


def print_papers(papers: List[Dict]) -> None:
    console.rule("[bold blue]📄 Retrieved Papers[/]")
    for i, p in enumerate(papers, 1):
        console.print(
            f"[bold]{i}.[/] [cyan]{p.get('title', 'Untitled')}[/]\n"
            f"   [dim]{p.get('authors', '')} ({p.get('year', '')})[/]\n"
            f"   [link={p.get('url', '')}]{p.get('url', '')}[/link]\n"
        )


def print_findings(findings: List[Dict]) -> None:
    console.rule("[bold teal]🧬 Extracted Findings[/]")
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta")
    table.add_column("Paper", style="dim", width=6)
    table.add_column("Type", style="dim", width=12)
    table.add_column("Drugs / Genes")
    table.add_column("Outcome", style="cyan")

    for f in findings:
        entities = f.get("entities", {})
        if not isinstance(entities, dict):
            entities = {}
        drugs_genes = ", ".join(
            (entities.get("drugs") or []) + (entities.get("genes") or [])
        )[:55]
        study_type = str(f.get("study_type") or "—")
        paper_id = str(f.get("paper_id", "?"))
        table.add_row(
            paper_id,
            study_type,
            drugs_genes or "—",
            str(f.get("outcome") or "—")[:70],
        )
    console.print(table)


def print_gaps(gaps_text: str) -> None:
    console.rule("[bold yellow]🔍 Research Gaps[/]")
    for line in gaps_text.strip().splitlines():
        if line.startswith("GAP"):
            idx = line.find(":")
            if idx > -1:
                label = line[:idx]
                body = line[idx+1:].strip()
                console.print(f"  [bold yellow]{label}:[/] {body}")
            else:
                console.print(f"  [yellow]{line}[/]")
        elif line.strip():
            console.print(f"  {line}")
    console.print()


def print_conflicts(conflicts_text: str) -> None:
    console.rule("[bold red]⚠️  Detected Conflicts[/]")
    for line in conflicts_text.strip().splitlines():
        if "HIGH" in line.upper():
            console.print(f"  [bold red]{line}[/]")
        elif "MEDIUM" in line.upper():
            console.print(f"  [red]{line}[/]")
        elif line.strip():
            console.print(f"  [dim]{line}[/]")
    console.print()


def print_hypotheses(hypotheses: Union[str, List[Dict]]) -> None:
    console.rule("[bold green]💡 Generated Hypotheses[/]")

    if isinstance(hypotheses, str):
        console.print(f"[green]{hypotheses.strip()}[/]\n")
        return

    if not hypotheses:
        console.print("[dim]No hypotheses generated.[/]\n")
        return

    for h in hypotheses:
        composite = h.get("composite_score", h.get("impact_score", "?"))
        impact = h.get("impact_score", "?")
        novelty = h.get("novelty_score", "?")
        flag = h.get("novelty_flag", "")
        flag_icons = {"novel": "🟢", "likely_known": "🟡", "verbatim_match": "🔴"}
        novelty_icon = flag_icons.get(flag, "⚪")
        citations = h.get("citations") or []

        console.print(
            f"\n[bold green]HYPOTHESIS {h.get('index', '?')}[/] "
            f"{novelty_icon} [dim](composite: {composite}/10 | impact: {impact} | novelty: {novelty})[/]"
        )
        console.print(f"  [bold]Statement:[/]   {h.get('statement', '')}")
        console.print(f"  [bold]Addresses:[/]   [yellow]{h.get('addresses', '—')}[/]")
        console.print(f"  [bold]Rationale:[/]   {h.get('rationale', '')}")
        console.print(f"  [bold]Experiment:[/]  {h.get('experiment', '')}")
        console.print(f"  [bold]Theme:[/]       [cyan]{h.get('theme', '—')}[/]")
        if citations:
            console.print(f"  [bold]Citations:[/]")
            for url in citations:
                console.print(f"    [link={url}]{url}[/link]")
    console.print()


def print_themes(themes_text: str) -> None:
    if not themes_text or not themes_text.strip():
        return
    console.rule("[bold purple]🎯 Research Theme Clusters[/]")
    console.print(
        "[dim](Hypothesis indices below refer to original generation order, "
        "not ranked display order)[/dim]"
    )
    console.print(f"[purple]{themes_text.strip()}[/]\n")


def generate_summary_report(result: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a structured 1-page summary using LLM."""
    console.print("[dim]Generating structured summary report...[/]")
    llm = get_llm(temperature=0.2)
    chain = SUMMARY_REPORT_PROMPT | llm
    hypotheses = result.get("hypotheses_ranked", result.get("hypotheses", []))
    # Take top hypothesis dict for strongest
    strongest = hypotheses[0] if hypotheses else {}
    try:
        raw = chain.invoke({
            "query": result["query"],
            "hypotheses": json.dumps(hypotheses[:3], indent=2),
            "gaps": result.get("gaps", ""),
            "conflicts": result.get("conflicts", ""),
            "causal_paths": "\n".join(result.get("causal_paths", [])),
        })
        report = json.loads(raw.content if hasattr(raw, "content") else str(raw))
    except Exception:
        report = {
            "executive_summary": "Summary generation failed.",
            "strongest_hypothesis": strongest,
            "most_critical_gap": "",
            "recommended_first_experiment": "",
            "confidence_assessment": "medium"
        }
    return report


def print_full_report(result: Dict[str, Any]) -> None:
    print_banner(result["query"])
    print_papers(result.get("papers", []))
    print_findings(result.get("findings", []))
    print_gaps(result.get("gaps", ""))
    print_conflicts(result.get("conflicts", ""))
    hypotheses = result.get("hypotheses_ranked") or result.get("hypotheses_raw", "")
    print_hypotheses(hypotheses)
    print_themes(result.get("themes", ""))
    console.print(f"\n[dim]Results saved to: {result.get('output_path', '')}[/dim]\n")


def save_results(result: Dict[str, Any]) -> str:
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    os.makedirs(settings.DEBUG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = result["query"].replace(" ", "_")[:40]
    filename = f"{timestamp}_{safe_query}.json"
    filepath = os.path.join(settings.OUTPUT_DIR, filename)

    # Move raw text to debug file if present
    raw_text = result.pop("hypotheses_raw", None)
    if raw_text:
        debug_file = os.path.join(settings.DEBUG_DIR, f"{timestamp}_raw.txt")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(raw_text)
        result["debug_file"] = debug_file

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return filepath