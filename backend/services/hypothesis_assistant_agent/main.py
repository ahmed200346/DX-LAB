"""
main.py (full pipeline with local Ollama – memory agent optional, graph export fixed)
"""

import argparse
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_backend_root = Path(__file__).resolve().parents[2]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))
try:
    import dx_lab_env

    dx_lab_env.load_shared_dotenv()
except Exception:
    pass

from rich.console import Console
from config.settings import settings
from agents.literature_retrieval import LiteratureRetrievalAgent
from agents.paper_analysis import PaperAnalysisAgent
from agents.relationship_extractor import RelationshipExtractorAgent
from agents.gap_detection import GapDetectionAgent
from agents.conflict_detection import ConflictDetectionAgent
from agents.novelty_filter import NoveltyFilterAgent
from agents.hypothesis_generation import HypothesisGenerationAgent
from utils.output_formatter import (print_full_report, save_results,
                                    generate_summary_report)

console = Console()


# ---- Lazy import of MemoryAgent -----------------------------------
def _get_memory_agent():
    try:
        from agents.memory_agent import MemoryAgent
        return MemoryAgent()
    except Exception as e:
        console.print(f"[yellow]Memory agent not available: {e}[/]")
        return None


def run_pipeline(query: str, num_hypotheses: int = None) -> dict:
    settings.validate()
    if num_hypotheses is None:
        num_hypotheses = settings.NUM_HYPOTHESES

    # ---- Agent 1 -------------------------------------------------
    lit_agent = LiteratureRetrievalAgent()
    papers = lit_agent.run(query)
    if not papers:
        console.print("[red]No papers retrieved. Exiting.[/]")
        return {"query": query, "papers": [], "error": "No papers found"}

    # ---- Agent 2 -------------------------------------------------
    analysis_agent = PaperAnalysisAgent()
    findings = analysis_agent.run(papers)
    summaries_text = analysis_agent.get_summary_text(findings)
    study_types = analysis_agent.get_study_types_summary(findings)

    # ---- Agent 2.5 -----------------------------------------------
    rel_agent = RelationshipExtractorAgent()
    rel_result = rel_agent.run(papers)
    triples = rel_result["triples"]
    causal_paths_list = rel_result["causal_paths"]
    causal_paths_str = "\n".join(causal_paths_list) if causal_paths_list else "none"
    causal_graph = rel_result.get("graph")   # networkx DiGraph

    # ---- Agents 3 & 4 in parallel --------------------------------
    gap_agent = GapDetectionAgent()
    conflict_agent = ConflictDetectionAgent()

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_gap = executor.submit(
            gap_agent.run, summaries_text, query, study_types, causal_paths_str
        )
        future_conflict = executor.submit(
            conflict_agent.run, summaries_text, triples
        )
        gaps = future_gap.result()
        conflicts = future_conflict.result()

    # ---- Known findings block ------------------------------------
    known_findings = "\n".join(
        f"Paper {f.get('paper_id', '?')}: {f.get('outcome', '')}"
        for f in findings if f.get('outcome')
    )[:2000]

    # ---- Agent 5 -------------------------------------------------
    hyp_agent = HypothesisGenerationAgent()
    hyp_result = hyp_agent.run(
        query=query,
        extracted_knowledge=summaries_text,
        gaps=gaps,
        conflicts=conflicts,
        causal_paths=causal_paths_str,
        known_findings=known_findings,
        papers=papers,
        findings=findings,
        num_hypotheses=num_hypotheses,
        stream=False,
    )

    # ---- Agent 3.5 (Novelty Filter) ------------------------------
    novelty_agent = NoveltyFilterAgent()
    filtered_hypotheses = novelty_agent.run(hyp_result["hypotheses"], papers)
    
    try:
        from agents.biomedical_validator import validate_hypothesis
        for h in filtered_hypotheses:
            h = validate_hypothesis(h, triples)      # checks against known interactions & triples
    except ImportError:
        pass

    hyp_result["hypotheses"] = filtered_hypotheses
    hyp_result["ranked"] = sorted(
        [h for h in filtered_hypotheses if isinstance(h, dict)],
        key=lambda x: x.get("composite_score", 0), reverse=True
    )

    

    # ---- Build result dict (graph included for export only) ------
    result = {
        "query": query,
        "papers": papers,
        "findings": findings,
        "triples": triples,
        "causal_paths": causal_paths_list,
        "gaps": gaps,
        "conflicts": conflicts,
        "hypotheses_raw": hyp_result["raw_text"],
        "hypotheses": hyp_result["hypotheses"],
        "hypotheses_ranked": hyp_result["ranked"],
        "themes": hyp_result["themes"],
    }

    # ---- Optional structured summary -----------------------------
    try:
        result["summary_report"] = generate_summary_report(result)
    except Exception as e:
        console.print(f"[yellow]Could not generate summary report: {e}[/]")
        result["summary_report"] = {}

    # Save results (graph kept separate to avoid serialisation issues)
    output_path = save_results(result)
    result["output_path"] = output_path

    # Re-attach graph for the caller (main) to use
    result["causal_graph"] = causal_graph
    return result


def export_graph_html(causal_graph, output_path: str):
    """Export a networkx DiGraph to an interactive HTML file using pyvis."""
    try:
        from pyvis.network import Network
        net = Network(height="750px", width="100%", directed=True)
        net.from_nx(causal_graph)
        net.show(output_path, notebook=False)
        console.print(f"[green]✓[/] Graph exported to [bold]{output_path}[/]")
    except ImportError:
        console.print("[yellow]pyvis not installed. Run: pip install pyvis[/]")
    except Exception as e:
        console.print(f"[yellow]Graph export failed: {e}[/]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hypothesis Generation Assistant")
    parser.add_argument("query", nargs="?", help="Research query")
    parser.add_argument("--num-hypotheses", type=int, default=None,
                        help="Number of hypotheses to generate")
    parser.add_argument("--interactive", action="store_true",
                        help="Launch interactive session after pipeline")
    parser.add_argument("--resume", type=str, metavar="SESSION_FILE",
                        help="Resume a saved interactive session")
    parser.add_argument("--export-graph", action="store_true",
                        help="Export causal graph as interactive HTML")
    args = parser.parse_args()

    # ---- Resume / interactive mode -------------------------------
    if args.resume:
        memory = _get_memory_agent()
        if memory is None:
            console.print("[red]Cannot resume – memory agent is not available.[/]")
            sys.exit(1)
        memory.load_session(args.resume)
        memory.interactive_session()
        sys.exit(0)

    # ---- Main pipeline -------------------------------------------
    if not args.query:
        parser.error("query is required unless --resume is specified")

    result = run_pipeline(args.query, args.num_hypotheses)
    print_full_report(result)

    # ---- Export causal graph (if requested & available) ----------
    if args.export_graph:
        causal_graph = result.get("causal_graph")
        if causal_graph and causal_graph.number_of_nodes() > 0:
            graph_path = os.path.join(settings.OUTPUT_DIR,
                                      f"graph_{result['query'].replace(' ','_')[:40]}.html")
            export_graph_html(causal_graph, graph_path)
        else:
            console.print("[yellow]No causal graph available to export.[/]")

    # ---- Optional interactive mode after run ---------------------
    if args.interactive:
        memory = _get_memory_agent()
        if memory is not None:
            memory.store_pipeline_result(result)
            memory.interactive_session()
        else:
            console.print("[red]Interactive mode is not available because the memory agent failed to load.[/]")