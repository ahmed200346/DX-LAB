"""
report_generator.py — Final Report Generator  v1.0

Generates a structured discovery report after a pipeline run.

Output formats:
  • Markdown string (always available)
  • JSON dump of all raw data + interim analysis
  • DOCX (requires python-docx)

Sections generated:
  1. Executive Summary        (Groq narrative, ≤300 words)
  2. Drug Target Analysis     (table + Groq commentary per target)
  3. Chemical Landscape       (table + bioactivity data)
  4. Pathway & Network Context
  5. Clinical Evidence        (PMIDs, DOIs, trial refs)
  6. Source Quality Metrics   (SGV breakdown, domain trust)
  7. Interim NER Analysis     (what was detected, entity frequencies)
  8. Methodology Notes

Usage:
    gen     = ReportGenerator(groq_client)
    report  = await gen.generate(response, query, interim_ner={})
    md      = report.to_markdown()
    docx_b  = await gen.to_docx(report)   # bytes — write to disk or stream
    json_s  = report.model_dump_json(indent=2)
"""

from __future__ import annotations

import re
import asyncio
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from models import ACPResponse, FinalReport, ReportSection

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor, Inches
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False
    logger.warning(
        "python-docx not installed — DOCX export disabled. "
        "Run: pip install python-docx"
    )


# =============================================================================
# GROQ PROMPTS
# =============================================================================

_EXEC_SUMMARY_PROMPT = """\
You are a senior biomedical analyst. Write a clear, evidence-based executive
summary (200–300 words) for a drug-target discovery report.

Query: {query}

Key findings:
- Drug targets identified: {target_list}
- Small molecules identified: {chemical_list}
- Source validation score (SGV): {sgv:.3f}
- Sources analysed: {source_count}
- Pathways implicated: {pathway_list}

Write the summary in third person, scientific prose. Highlight the most
actionable findings. Do NOT invent data not listed above.
"""

_TARGET_COMMENTARY_PROMPT = """\
In 2–3 sentences, describe the therapeutic significance of {gene} ({protein})
in {disease}. Mention druggability, known inhibitors if any, and clinical
relevance. Be concise and evidence-based.
"""

_PATHWAY_SECTION_PROMPT = """\
Summarise in 150 words the pathway landscape for these drug targets: {targets}.
Focus on cross-target pathway overlap, synthetic lethality opportunities,
and resistance mechanisms. Be concise.
"""


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class ReportGenerator:
    """
    Async report generator. Groq is optional — sections degrade gracefully
    to data-table-only format when GROQ_API_KEY is absent.
    """

    def __init__(self, groq_client=None):
        self._groq = groq_client

    async def _gpt(self, prompt: str, max_tokens: int = 400) -> str:
        if self._groq is None:
            return ""
        try:
            return await self._groq.chat(
                prompt,
                max_tokens=max_tokens,
                temperature=0.2,
                system_prompt=(
                    "You are a biomedical research analyst. "
                    "Be precise, evidence-based, and concise."
                ),
            )
        except Exception as exc:
            logger.debug(f"ReportGenerator Groq call failed: {exc}")
            return ""

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def generate(
        self,
        response:    ACPResponse,
        query:       str,
        interim_ner: Optional[Dict[str, Any]] = None,
    ) -> FinalReport:
        """
        Build a FinalReport from a completed ACPResponse.
        Sections are generated concurrently where possible.
        """
        targets   = response.targets   or []
        chemicals = response.chemicals or []
        sources   = self._collect_sources(response)

        # ── Concurrent narrative generation ────────────────────────────────────
        exec_task = asyncio.create_task(
            self._section_executive_summary(query, targets, chemicals, response, sources)
        )
        target_task = asyncio.create_task(
            self._section_targets(targets)
        )
        chem_task = asyncio.create_task(
            self._section_chemicals(chemicals)
        )
        pathway_task = asyncio.create_task(
            self._section_pathways(targets)
        )
        evidence_task = asyncio.create_task(
            self._section_clinical_evidence(targets, chemicals, sources)
        )
        quality_task = asyncio.create_task(
            self._section_quality(response)
        )

        (
            sec_exec, sec_targets, sec_chem,
            sec_pathway, sec_evidence, sec_quality,
        ) = await asyncio.gather(
            exec_task, target_task, chem_task,
            pathway_task, evidence_task, quality_task,
        )

        sec_ner      = self._section_ner(interim_ner or {})
        sec_method   = self._section_methodology(response)

        sections = [
            sec_exec, sec_targets, sec_chem,
            sec_pathway, sec_evidence, sec_quality,
            sec_ner, sec_method,
        ]

        # ── Interim metrics ────────────────────────────────────────────────────
        interim_metrics = {
            "sgv":             response.validation_score,
            "source_count":    response.source_count,
            "target_count":    len(targets),
            "chemical_count":  len(chemicals),
            "latency_ms":      response.retrieval_latency_ms,
            "status":          response.status,
            "data_types":      [dt.value for dt in response.data_types],
        }

        return FinalReport(
            session_id=response.session_id,
            query=query,
            validation_score=response.validation_score,
            sections=sections,
            targets=targets,
            chemicals=chemicals,
            sources=sources,
            interim_ner=interim_ner or {},
            interim_metrics=interim_metrics,
        )

    # =========================================================================
    # SECTION BUILDERS
    # =========================================================================

    async def _section_executive_summary(
        self,
        query:     str,
        targets:   List[Dict],
        chemicals: List[Dict],
        response:  ACPResponse,
        sources:   List[Dict],
    ) -> ReportSection:
        target_list  = ", ".join(t.get("gene", "?") for t in targets[:8]) or "none identified"
        chem_list    = ", ".join(c.get("name", "?") for c in chemicals[:8]) or "none identified"
        pathway_list = self._top_pathways(targets)

        prompt = _EXEC_SUMMARY_PROMPT.format(
            query=query,
            target_list=target_list,
            chemical_list=chem_list,
            sgv=response.validation_score,
            source_count=response.source_count,
            pathway_list=pathway_list or "not determined",
        )
        narrative = await self._gpt(prompt, max_tokens=500)
        if not narrative:
            narrative = (
                f"This report summarises the findings of a biomedical discovery "
                f"query: **{query}**. "
                f"The pipeline identified **{len(targets)} drug targets** and "
                f"**{len(chemicals)} small molecules** across "
                f"**{response.source_count} validated sources** "
                f"(SGV = {response.validation_score:.3f})."
            )
        return ReportSection(title="Executive Summary", content=narrative)

    async def _section_targets(self, targets: List[Dict]) -> ReportSection:
        if not targets:
            return ReportSection(
                title="Drug Target Analysis",
                content="_No drug targets were identified for this query._",
            )

        lines = [
            "| Gene | Protein | Disease | UniProt | PubMed Freq | Evidence Tier | Top Pathway |",
            "|------|---------|---------|---------|-------------|---------------|-------------|",
        ]
        for t in targets:
            lines.append(
                f"| **{t.get('gene','?')}** "
                f"| {t.get('protein','')[:40]} "
                f"| {t.get('disease_context','')[:35]} "
                f"| [{t.get('uniprot_id','—')}](https://uniprot.org/uniprot/{t.get('uniprot_id','')}) "
                f"| {t.get('pubmed_total_count','—')} "
                f"| {t.get('evidence_tier','—')} "
                f"| {t.get('top_pathway','—')[:35]} |"
            )

        # Groq commentary per top 3 targets
        commentary_tasks = [
            self._gpt(
                _TARGET_COMMENTARY_PROMPT.format(
                    gene=t.get("gene", "?"),
                    protein=t.get("protein", "unknown protein"),
                    disease=t.get("disease_context", "cancer"),
                ),
                max_tokens=120,
            )
            for t in targets[:3]
        ]
        commentaries = await asyncio.gather(*commentary_tasks)

        detail_blocks = []
        for t, commentary in zip(targets[:3], commentaries):
            mutations = ", ".join(t.get("mutations", [])) or "—"
            drugg     = t.get("druggability_notes", "")[:120]
            pmids     = ", ".join(t.get("supporting_pmids", [])[:3])
            block = (
                f"\n### {t.get('gene','?')} — {t.get('protein','')[:60]}\n"
                f"{commentary}\n\n"
                f"- **Mutations:** {mutations}\n"
                f"- **Druggability:** {drugg or 'see UniProt'}\n"
                f"- **Supporting PMIDs:** {pmids or '—'}\n"
            )
            if t.get("pdb_structures"):
                pdbs = ", ".join(
                    f"[{s['pdb_id']}](https://www.rcsb.org/structure/{s['pdb_id']})"
                    for s in t["pdb_structures"][:3]
                )
                block += f"- **PDB Structures:** {pdbs}\n"
            detail_blocks.append(block)

        content = "\n".join(lines) + "\n" + "\n".join(detail_blocks)
        return ReportSection(title="Drug Target Analysis", content=content, data=targets)

    async def _section_chemicals(self, chemicals: List[Dict]) -> ReportSection:
        if not chemicals:
            return ReportSection(
                title="Chemical Landscape",
                content="_No small molecules were identified for this query._",
            )

        lines = [
            "| Name | Formula | MW (Da) | Phase | ChEMBL | PubChem |",
            "|------|---------|---------|-------|--------|---------|",
        ]
        for c in chemicals:
            chembl_link = (
                f"[{c.get('chembl_id','—')}]"
                f"(https://www.ebi.ac.uk/chembl/compound_report_card/{c.get('chembl_id','')})"
                if c.get("chembl_id") else "—"
            )
            pubchem_link = (
                f"[{c.get('cid','—')}](https://pubchem.ncbi.nlm.nih.gov/compound/{c.get('cid','')})"
                if c.get("cid") else "—"
            )
            lines.append(
                f"| **{c.get('name','?')}** "
                f"| {c.get('formula','—')} "
                f"| {c.get('mol_weight','—')} "
                f"| {c.get('phase','—')} "
                f"| {chembl_link} "
                f"| {pubchem_link} |"
            )

        # Bioactivity detail
        detail_blocks = []
        for c in chemicals[:4]:
            acts = c.get("bioactivities", [])
            if not acts:
                continue
            act_lines = ["| Target | Assay | Value | Units |", "|--------|-------|-------|-------|"]
            for a in acts[:4]:
                act_lines.append(
                    f"| {a.get('target','?')[:45]} "
                    f"| {a.get('assay_type','?')} "
                    f"| {a.get('relation','=')}{a.get('value','?')} "
                    f"| {a.get('units','?')} |"
                )
            detail_blocks.append(
                f"\n#### {c.get('name','?')} — Bioactivity Data\n"
                + "\n".join(act_lines)
            )

        content = "\n".join(lines) + "\n" + "\n".join(detail_blocks)
        return ReportSection(title="Chemical Landscape", content=content, data=chemicals)

    async def _section_pathways(self, targets: List[Dict]) -> ReportSection:
        if not targets:
            return ReportSection(
                title="Pathway & Network Context",
                content="_Insufficient targets for pathway analysis._",
            )

        target_names = ", ".join(t.get("gene", "?") for t in targets[:6])
        narrative = await self._gpt(
            _PATHWAY_SECTION_PROMPT.format(targets=target_names),
            max_tokens=250,
        )

        # Collect pathway data
        all_pathways: List[Dict] = []
        for t in targets:
            pp = t.get("pathway_profile", {})
            if isinstance(pp, dict):
                for rp in pp.get("reactome_pathways", [])[:3]:
                    all_pathways.append({
                        "gene":     t.get("gene", "?"),
                        "source":   "Reactome",
                        "name":     rp.get("name", "?"),
                        "url":      rp.get("url", ""),
                    })
                for kp in pp.get("kegg_pathways", [])[:3]:
                    all_pathways.append({
                        "gene":   t.get("gene", "?"),
                        "source": "KEGG",
                        "name":   kp.get("name", "?"),
                        "url":    kp.get("url", ""),
                    })

        table = ""
        if all_pathways:
            rows = ["| Gene | Source | Pathway |", "|------|--------|---------|"]
            for p in all_pathways[:15]:
                name_md = (
                    f"[{p['name'][:50]}]({p['url']})" if p.get("url") else p["name"][:50]
                )
                rows.append(f"| {p['gene']} | {p['source']} | {name_md} |")
            table = "\n".join(rows)

        content = (narrative or "_Groq narrative unavailable._") + "\n\n" + table
        return ReportSection(
            title="Pathway & Network Context", content=content, data=all_pathways
        )

    async def _section_clinical_evidence(
        self,
        targets:   List[Dict],
        chemicals: List[Dict],
        sources:   List[Dict],
    ) -> ReportSection:
        pmids: List[str] = []
        dois:  List[str] = []
        for t in targets:
            pmids.extend(t.get("supporting_pmids", []))
            dois.extend(t.get("supporting_dois", []))
        for c in chemicals:
            pmids.extend(c.get("supporting_pmids", []))
            dois.extend(c.get("supporting_dois", []))
        # Deduplicate preserving order
        seen: set = set()
        pmids = [p for p in pmids if not (p in seen or seen.add(p))]  # type: ignore
        seen.clear()
        dois  = [d for d in dois  if not (d in seen or seen.add(d))]  # type: ignore

        pmid_links = "\n".join(
            f"- [PMID:{p}](https://pubmed.ncbi.nlm.nih.gov/{p}/)" for p in pmids[:20]
        ) or "_No PMIDs available._"

        source_rows = ["| Title | URL | Type | Score |", "|-------|-----|------|-------|"]
        for s in sources[:15]:
            title = s.get("title", "Untitled")[:55]
            url   = s.get("source_url", "")
            stype = s.get("content_type", "text")
            score = f"{s.get('validation_score', 0.0):.2f}"
            url_md = f"[link]({url})" if url else "—"
            source_rows.append(f"| {title} | {url_md} | {stype} | {score} |")

        content = (
            f"### PubMed References\n\n{pmid_links}\n\n"
            f"### Validated Sources\n\n" + "\n".join(source_rows)
        )
        return ReportSection(title="Clinical Evidence", content=content)

    async def _section_quality(self, response: ACPResponse) -> ReportSection:
        score = response.validation_score
        bar   = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        content = (
            f"```\nSGV (Source-Grounded Validity)  [{bar}]  {score:.3f}\n```\n\n"
            f"| Metric | Value |\n|--------|-------|\n"
            f"| Validation Score (SGV) | {score:.4f} |\n"
            f"| Sources Retrieved | {response.source_count} |\n"
            f"| Pipeline Latency | {response.retrieval_latency_ms} ms |\n"
            f"| Pipeline Status | {response.status} |\n"
            f"| Data Types | {', '.join(dt.value for dt in response.data_types)} |\n"
        )
        if response.warning:
            content += f"\n> ⚠ **Warning:** {response.warning}\n"
        return ReportSection(title="Source Quality Metrics", content=content)

    def _section_ner(self, interim_ner: Dict[str, Any]) -> ReportSection:
        if not interim_ner:
            return ReportSection(
                title="Interim NER Analysis",
                content="_NER data not available for this session._",
            )
        lines = ["| Entity Type | Entities |", "|-------------|----------|"]
        for etype, entities in interim_ner.items():
            if isinstance(entities, (list, set)):
                lines.append(f"| {etype} | {', '.join(str(e) for e in list(entities)[:10])} |")
            else:
                lines.append(f"| {etype} | {entities} |")
        return ReportSection(title="Interim NER Analysis", content="\n".join(lines))

    def _section_methodology(self, response: ACPResponse) -> ReportSection:
        content = (
            "This report was generated by the **Intelligent Target Discovery Agent v3.0** "
            "using the following pipeline:\n\n"
            "1. **Web Search** — SearXNG + DuckDuckGo + PubMed + Semantic Scholar\n"
            "2. **Content Extraction** — Jina.ai / trafilatura with domain filtering\n"
            "3. **Validation** — SGV scoring (faithfulness, relevancy, credibility, NLI)\n"
            "4. **Vectorisation** — BAAI/bge-base-en (768-dim) with section-aware PDF chunking\n"
            "5. **Retrieval** — Dense → BM25 → RRF fusion → Cross-encoder → MMR\n"
            "6. **Target Enrichment** — BioNER + Groq LLM + UniProt + PDB + AlphaFold "
            "+ PubMed frequency + Reactome/KEGG pathway mapping\n"
            "7. **Chemical Enrichment** — Groq NER + PubChem + ChEMBL + RDKit 2D/3D\n\n"
            f"**Session:** `{response.session_id}` | "
            f"**ACP Version:** {response.acp_version}"
        )
        return ReportSection(title="Methodology", content=content)

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _collect_sources(response: ACPResponse) -> List[Dict[str, Any]]:
        sources = []
        for items in response.payload.values():
            for item in items:
                sources.append({
                    "title":            item.get("title", ""),
                    "source_url":       item.get("source_url", ""),
                    "content_type":     item.get("content_type", "text"),
                    "validation_score": item.get("validation_score", 0.0),
                    "domain_trust":     item.get("domain_trust", 0.0),
                    "pmid":             item.get("pmid"),
                    "doi":              item.get("doi"),
                })
        return sources

    @staticmethod
    def _top_pathways(targets: List[Dict]) -> str:
        seen: set = set()
        paths: List[str] = []
        for t in targets:
            p = t.get("top_pathway")
            if p and p not in seen:
                seen.add(p)
                paths.append(p)
        return ", ".join(paths[:5])

    # =========================================================================
    # EXPORT: DOCX
    # =========================================================================

    async def to_docx(self, report: FinalReport) -> bytes:
        """
        Generate a well-formatted DOCX from a FinalReport.
        Returns raw bytes suitable for streaming or writing to disk.
        """
        if not _DOCX_AVAILABLE:
            raise RuntimeError(
                "python-docx not installed. Run: pip install python-docx"
            )

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._build_docx, report)

    @staticmethod
    def _build_docx(report: FinalReport) -> bytes:
        doc = Document()

        # ── Title ──────────────────────────────────────────────────────────────
        title_par = doc.add_heading(level=0)
        title_run = title_par.add_run("🔬 Drug Target Discovery Report")
        title_run.font.color.rgb = RGBColor(0x1E, 0x40, 0xAF)

        # ── Meta ──────────────────────────────────────────────────────────────
        doc.add_paragraph(
            f"Query: {report.query}\n"
            f"Session: {report.session_id}   |   "
            f"Generated: {report.generated_at[:19].replace('T',' ')} UTC   |   "
            f"SGV: {report.validation_score:.3f}"
        ).runs[0].font.size = Pt(10)
        doc.add_paragraph()  # spacer

        # ── Sections ──────────────────────────────────────────────────────────
        for sec in report.sections:
            doc.add_heading(sec.title, level=1)
            # Strip markdown table markers and render as plain text
            lines = sec.content.split("\n")
            in_table = False
            table_rows: List[List[str]] = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("|") and stripped.endswith("|"):
                    cells = [c.strip() for c in stripped.strip("|").split("|")]
                    table_rows.append(cells)
                    in_table = True
                else:
                    if in_table and table_rows:
                        # Flush table
                        # Filter separator rows
                        data_rows = [
                            r for r in table_rows
                            if not all(set(c) <= set("-: ") for c in r)
                        ]
                        if data_rows:
                            ncols = max(len(r) for r in data_rows)
                            tbl = doc.add_table(rows=len(data_rows), cols=ncols)
                            tbl.style = "Table Grid"
                            for ri, row in enumerate(data_rows):
                                for ci, cell_text in enumerate(row[:ncols]):
                                    # Strip markdown links [text](url) → text
                                    import re
                                    plain = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cell_text)
                                    plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", plain)
                                    tbl.cell(ri, ci).text = plain
                        table_rows = []
                        in_table = False
                    # Normal text line
                    if stripped.startswith("### "):
                        doc.add_heading(stripped[4:], level=3)
                    elif stripped.startswith("## "):
                        doc.add_heading(stripped[3:], level=2)
                    elif stripped.startswith("# "):
                        doc.add_heading(stripped[2:], level=1)
                    elif stripped.startswith("- "):
                        import re
                        plain = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", stripped[2:])
                        plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", plain)
                        doc.add_paragraph(plain, style="List Bullet")
                    elif stripped.startswith("```") or stripped == "```":
                        pass  # skip code fences
                    elif stripped:
                        import re
                        plain = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", stripped)
                        plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", plain)
                        plain = re.sub(r"_([^_]+)_", r"\1", plain)
                        doc.add_paragraph(plain)

            # Flush any trailing table
            if in_table and table_rows:
                data_rows = [r for r in table_rows if not all(set(c) <= set("-: ") for c in r)]
                if data_rows:
                    ncols = max(len(r) for r in data_rows)
                    tbl = doc.add_table(rows=len(data_rows), cols=ncols)
                    tbl.style = "Table Grid"
                    for ri, row in enumerate(data_rows):
                        for ci, cell_text in enumerate(row[:ncols]):
                            import re
                            plain = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cell_text)
                            plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", plain)
                            tbl.cell(ri, ci).text = plain

            doc.add_paragraph()  # spacer between sections

        # ── Raw data appendix ─────────────────────────────────────────────────
        doc.add_heading("Appendix — Raw Data Summary", level=1)
        doc.add_paragraph(
            f"Targets: {len(report.targets)} | "
            f"Chemicals: {len(report.chemicals)} | "
            f"Sources: {len(report.sources)}"
        )
        doc.add_paragraph(
            "Complete machine-readable data is available in the accompanying "
            "JSON file (report_<session_id>.json)."
        )

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    # =========================================================================
    # EXPORT: JSON (full raw dump)
    # =========================================================================

    @staticmethod
    def to_json(report: FinalReport) -> str:
        return report.model_dump_json(indent=2)