"""
agents/relationship_extractor.py
Agent 2.5: Relationship Extractor – extracts causal triples, validates,
builds layered graph, finds cross‑paper paths (max length 2).
"""

import json as json_mod
import networkx as nx
from typing import List, Dict, Any, Tuple

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from utils.llm import get_analysis_llm
from utils.prompts import RELATIONSHIP_EXTRACTION_PROMPT
from utils.cache import cached_llm_invoke, llm_cache
from utils.rate_limiter import rate_limiter
from utils.biomed_entities import validate_triple, get_entity_type

console = Console()

RELATIONS = [
    "activates", "inhibits", "stabilizes", "degrades",
    "promotes", "reduces", "bypasses", "induces",
    "regulates", "phosphorylates", "upregulates", "downregulates",
    "interacts_with", "is_upstream_of", "is_downstream_of"
]

CONFIDENCE_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}


class RelationshipExtractorAgent:
    def __init__(self):
        self._llm = get_analysis_llm()
        self._chain = RELATIONSHIP_EXTRACTION_PROMPT | self._llm

    def run(self, papers: List[Dict[str, Any]]) -> Dict[str, Any]:
        console.print(
            f"\n[bold magenta]Agent 2.5:[/] Relationship Extraction — building causal triples"
        )

        triples = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Extracting triples per paper...", total=len(papers))
            for i, paper in enumerate(papers):
                paper_id = str(paper.get("paper_id", i+1))
                abstract = paper.get("abstract", "")
                if not abstract:
                    progress.advance(task)
                    continue
                try:
                    rate_limiter.wait_if_needed(estimated_tokens=600)
                    raw = cached_llm_invoke(
                        self._chain,
                        {"abstract": abstract, "paper_id": paper_id},
                        llm_cache,
                    )
                    rate_limiter.record(tokens_used=len(raw)//3+100)
                    paper_triples = self._parse_and_validate(raw, paper_id)
                    triples.extend(paper_triples)
                except Exception as e:
                    console.print(f"  [yellow]Triple extraction failed for paper {paper_id}: {e}[/]")
                progress.advance(task)

        console.print(f"  [green]✓[/] Extracted {len(triples)} validated causal triples from {len(papers)} papers")

        # Build layered graph
        graph = self.build_graph(triples)
        # Compute confidence scores (post-hoc, using paper counts)
        triples = self.compute_confidence_scores(triples)
        paths = self.find_cross_paper_paths(graph, max_length=2, min_papers=2)

        path_strings = []
        for path, paper_set in paths:
            nodes = " → ".join(path)
            path_strings.append(f"Path: {nodes} (papers: {sorted(paper_set)})")

        return {
            "triples": triples,
            "graph": graph,
            "causal_paths": path_strings,
        }

    def _parse_and_validate(self, text: str, paper_id: str) -> List[Dict]:
        import json, re
        text = text.strip()
        if text.startswith("```"):
            text = "\n".join(l for l in text.splitlines() if not l.startswith("```")).strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        try:
            parsed = json.loads(text[start:end])
        except json.JSONDecodeError:
            return []

        validated = []
        for t in parsed:
            subject = t.get("subject", "").strip()
            relation = t.get("relation", "").strip().lower()
            obj = t.get("object", "").strip()
            if not subject or not obj or relation not in RELATIONS:
                continue
            valid, type_validity = validate_triple(subject, relation, obj)
            if not valid:
                continue
            # Add entity types
            t["subject_type"] = get_entity_type(subject)
            t["object_type"] = get_entity_type(obj)
            t["type_validity"] = type_validity
            t["paper_id"] = str(paper_id)
            validated.append(t)
        return validated

    def compute_confidence_scores(self, triples: List[Dict]) -> List[Dict]:
        """Add a composite confidence score per triple."""
        # Count how many distinct papers report the same (subject, relation, object)
        edge_paper_counts = {}
        for t in triples:
            key = (t["subject"].lower(), t["relation"], t["object"].lower())
            edge_paper_counts.setdefault(key, set()).add(t["paper_id"])
        for t in triples:
            key = (t["subject"].lower(), t["relation"], t["object"].lower())
            paper_count = len(edge_paper_counts[key])
            # Normalize paper count score (logarithmic, max 1.0)
            paper_score = min(1.0, 0.3 * (paper_count))  # simple: 0.3 per additional paper, cap 1
            extraction_conf = CONFIDENCE_MAP.get(t.get("confidence", "medium").lower(), 0.6)
            type_validity = t.get("type_validity", 0.5)
            composite = 0.5 * extraction_conf + 0.3 * paper_score + 0.2 * type_validity
            t["confidence_score"] = round(composite, 2)
        return triples

    def build_graph(self, triples: List[Dict]) -> nx.DiGraph:
        G = nx.DiGraph()
        for triple in triples:
            subj = triple["subject"].strip()
            obj = triple["object"].strip()
            if not subj or not obj:
                continue
            subj_type = triple.get("subject_type", "unknown")
            obj_type = triple.get("object_type", "unknown")
            # Layer assignment: molecular (protein, enzyme, kinase, gene), metabolic, phenotype, drug
            def layer(t: str):
                if t in ["protein", "enzyme", "kinase", "gene"]:
                    return "molecular"
                if t == "metabolite":
                    return "metabolic"
                if t in ["phenotype"]:
                    return "phenotype"
                return "other"
            subj_layer = layer(subj_type)
            obj_layer = layer(obj_type)
            # Allow only: molecular→molecular, metabolic→phenotype
            # (Strict rule to prevent fake cross‑layer jumps)
            if (subj_layer == "molecular" and obj_layer == "molecular") or \
               (subj_layer == "metabolic" and obj_layer == "phenotype"):
                G.add_edge(subj, obj,
                           relation=triple.get("relation", ""),
                           context=triple.get("context", ""),
                           paper_ids=[triple.get("paper_id", "")],
                           confidence=triple.get("confidence_score", 0.5),
                           subj_layer=subj_layer,
                           obj_layer=obj_layer)
            else:
                # Optionally log skipped edge
                # console.print(f"  [dim]Skipped cross‑layer edge: {subj} ({subj_type})->{obj} ({obj_type})[/]")
                pass
        return G

    def find_cross_paper_paths(self, graph: nx.DiGraph, max_length: int = 2, min_papers: int = 2) -> List[Tuple[List[str], set]]:
        """
        Find all simple paths of length up to max_length where edges
        come from at least min_papers distinct paper IDs.
        """
        paths = []
        for source in graph.nodes():
            for target in graph.nodes():
                if source == target:
                    continue
                try:
                    for path in nx.all_simple_paths(graph, source, target, cutoff=max_length):
                        if len(path) < 2:  # need at least one edge
                            continue
                        pids = set()
                        for u, v in zip(path[:-1], path[1:]):
                            edge_data = graph.edges[u, v]
                            pids.update(edge_data.get("paper_ids", []))
                        if len(pids) >= min_papers:
                            paths.append((path, pids))
                except nx.NetworkXNoPath:
                    continue
        # Deduplicate
        unique = {}
        for p, pids in paths:
            key = tuple(p)
            if key not in unique or len(pids) > len(unique[key][1]):
                unique[key] = (p, pids)
        sorted_paths = sorted(unique.values(), key=lambda x: len(x[1]), reverse=True)
        return sorted_paths