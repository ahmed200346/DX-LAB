"""
target_extractor.py  v2.0  — with BioNER, Enhanced UniProt, PubMed Frequency
                              Scoring, and Pathway Mapping

Pipeline position (unchanged):
  validated, metrics = await validator.validate(raw_items, query)
  ──► targets = await target_extractor.extract_targets(validated, query)
  ──► ACPResponse(..., targets=[t.to_dict() for t in targets])

NEW in v2.0
───────────
1. BioNER pre-pass (bio_ner.BioNERService)
2. Enhanced UniProt validation (uniprot_validator.UniProtValidator)
3. PubMed Frequency Scoring (pubmed_frequency.PubMedFrequencyScorer)
4. Pathway Mapping (pathway_mapper.PathwayMapper)
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import aiohttp
from loguru import logger

# ── New modules ───────────────────────────────────────────────────────────────
from bio_ner import BioNERService, BioNERAnnotation
from uniprot_validator import UniProtValidator, UniProtInfo
from pubmed_frequency import PubMedFrequencyScorer, FrequencyResult
from pathway_mapper import PathwayMapper, PathwayProfile


# =============================================================================
# DATA MODELS (unchanged public API + new optional attributes)
# =============================================================================

@dataclass
class PDBStructure:
    pdb_id:     str
    title:      str  = ""
    method:     str  = ""
    resolution: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pdb_id":     self.pdb_id,
            "title":      self.title,
            "method":     self.method,
            "resolution": self.resolution,
            "url":        f"https://www.rcsb.org/structure/{self.pdb_id}",
        }


@dataclass
class AlphaFoldEntry:
    entry_id:    str
    pdb_url:     str  = ""
    cif_url:     str  = ""
    avg_plddt:   Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        uniprot_id = self.entry_id.split("-")[1] if "-" in self.entry_id else ""
        return {
            "entry_id":      self.entry_id,
            "pdb_url":       self.pdb_url,
            "cif_url":       self.cif_url,
            "avg_plddt":     self.avg_plddt,
            "alphafold_url": f"https://alphafold.ebi.ac.uk/entry/{uniprot_id}",
        }


@dataclass
class DrugTarget:
    gene:               str
    protein:            str                = ""
    mutations:          List[str]          = field(default_factory=list)
    disease_context:    str                = ""
    druggability_notes: str                = ""
    uniprot_id:         Optional[str]      = None
    pdb_ids:            List[str]          = field(default_factory=list)
    pdb_structures:     List[PDBStructure] = field(default_factory=list)
    alphafold:          Optional[AlphaFoldEntry] = None
    supporting_pmids:   List[str]          = field(default_factory=list)
    supporting_dois:    List[str]          = field(default_factory=list)
    source_count:       int                = 0

    # ── v2.0 enrichment objects ──
    uniprot_info:       Optional[UniProtInfo]    = field(default=None, repr=False)
    pubmed_frequency:   Optional[FrequencyResult] = field(default=None, repr=False)
    pathway_profile:    Optional[PathwayProfile]  = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        base = {
            "gene":               self.gene,
            "protein":            self.protein,
            "mutations":          self.mutations,
            "disease_context":    self.disease_context,
            "druggability_notes": self.druggability_notes,
            "uniprot_id":         self.uniprot_id,
            "pdb_ids":            self.pdb_ids,
            "pdb_structures":     [s.to_dict() for s in self.pdb_structures],
            "alphafold":          self.alphafold.to_dict() if self.alphafold else None,
            "supporting_pmids":   self.supporting_pmids,
            "supporting_dois":    self.supporting_dois,
            "source_count":       self.source_count,
        }

        # Flatten UniProt enrichment fields
        if self.uniprot_info and self.uniprot_info.is_valid():
            ui = self.uniprot_info
            base["uniprot_entry_name"]    = ui.entry_name
            base["protein_full_name"]     = ui.protein_full_name
            base["organism"]              = ui.organism
            base["is_reviewed"]           = ui.is_reviewed
            base["sequence_length"]       = ui.sequence_length
            base["molecular_weight"]      = ui.molecular_weight
            base["function"]              = ui.function_text[:500] if ui.function_text else ""
            base["subcellular_locs"]      = ui.subcellular_locs
            base["associated_diseases"]   = ui.associated_diseases
            base["chembl_ids"]            = ui.chembl_ids
            base["reactome_xrefs"]        = ui.reactome_ids
            base["kegg_xrefs"]            = ui.kegg_ids
            base["go_terms"]              = ui.go_terms[:10]
            base["uniprot_keywords"]      = ui.keywords[:10]
            base["druggability_score"]    = ui.druggability_score

        # PubMed frequency
        if self.pubmed_frequency:
            pf = self.pubmed_frequency
            base["pubmed_total_count"]    = pf.total_count
            base["pubmed_recent_count"]   = pf.recent_count
            base["pubmed_trend"]          = pf.trend_direction
            base["pubmed_frequency_score"]= pf.frequency_score
            base["evidence_tier"]         = pf.evidence_tier
            base["pubmed_url"]            = pf.pubmed_url

        # Pathway mapping
        if self.pathway_profile:
            pp = self.pathway_profile
            base["pathway_profile"]       = pp.to_dict()
            base["top_pathway"]           = pp.top_pathway
            base["pathway_score"]         = pp.pathway_score
            base["network_context"]       = pp.network_context

        return base


# =============================================================================
# CONSTANTS
# =============================================================================

_UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
_ALPHAFOLD_API_URL  = "https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
_PDB_SEARCH_URL     = "https://search.rcsb.org/rcsbsearch/v2/query"
_PDB_ENTRY_URL      = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"

_MAX_PDB_DETAIL  = 5
_MAX_TARGETS     = 10
_MAX_ITEMS_GROQ  = 8

_GROQ_EXTRACT_SYSTEM = (
    "You are a biomedical data extraction assistant. "
    "Return ONLY valid JSON — no markdown, no explanation, no preamble."
)

_GROQ_EXTRACT_PROMPT = """\
Extract all drug targets mentioned in the following biomedical text excerpts.

Pre-identified entities (use these as hints, verify in text):
  Genes/Proteins : {ner_genes}
  Mutations      : {ner_mutations}
  Drugs          : {ner_drugs}
  Diseases       : {ner_diseases}
  Pathways       : {ner_pathways}

For each unique gene/protein target return a JSON object with:
  gene               : HGNC gene symbol (e.g. "KRAS")
  protein            : full protein name
  mutations          : list of specific mutations (e.g. ["G12C", "G12D"])
  disease_context    : primary disease or cancer type
  druggability_notes : binding pockets, inhibitor classes, or approved drugs

Return a JSON array.  If no targets found return [].
Only include targets with a clear gene symbol.  Deduplicate by gene symbol.

Text excerpts:
{text_excerpts}

JSON array:"""


# =============================================================================
# TARGET EXTRACTOR  v2.0
# =============================================================================

class TargetExtractor:
    """
    Extracts and enriches drug targets from validated biomedical items.

    Enrichment pipeline (all steps async):
      1. BioNER annotation of source items
      2. Groq LLM extraction (NER-guided)
      3. UniProt full-metadata enrichment
      4. PDB + AlphaFold structure resolution
      5. PubMed frequency scoring
      6. Pathway mapping (Reactome + KEGG + text)
    """

    def __init__(self, groq_client=None, ner_service=None):
        self._groq       = groq_client
        self._ner = ner_service if ner_service is not None else BioNERService()
        self._session:   Optional[aiohttp.ClientSession] = None

        # v2.0 service objects
        self._uniprot_val = UniProtValidator()
        self._pubmed_freq = PubMedFrequencyScorer()
        self._pathway_map = PathwayMapper()

    def set_groq(self, groq_client) -> None:
        self._groq = groq_client

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    async def close(self):
        tasks = [
            self._uniprot_val.close(),
            self._pubmed_freq.close(),
            self._pathway_map.close(),
        ]
        if self._session and not self._session.closed:
            tasks.append(self._session.close())
        await asyncio.gather(*tasks, return_exceptions=True)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 — BioNER annotation
    # ─────────────────────────────────────────────────────────────────────────

    async def _annotate_items(
        self, items: list
    ) -> BioNERAnnotation:
        """
        Run BioNER over all validated items and merge entity sets.
        Returns a single merged BioNERAnnotation.
        """
        texts = []
        for item in items:
            # Handle both dict and object
            content = (
                getattr(item, "content", None) or
                (item.get("content") if isinstance(item, dict) else "")
            )[:2000]
            texts.append(content)

        annotations = await self._ner.annotate_batch(texts, use_transformer=False)

        merged = BioNERAnnotation()
        for ann in annotations:
            merged.genes.update(ann.genes)
            merged.mutations.update(ann.mutations)
            merged.drugs.update(ann.drugs)
            merged.diseases.update(ann.diseases)
            merged.pathways.update(ann.pathways)
            merged.entities.extend(ann.entities)

        logger.info(
            f"BioNER merged: genes={len(merged.genes)} "
            f"mutations={len(merged.mutations)} drugs={len(merged.drugs)} "
            f"diseases={len(merged.diseases)} pathways={len(merged.pathways)}"
        )
        return merged

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2 — Groq LLM extraction (NER-guided)
    # ─────────────────────────────────────────────────────────────────────────

    async def _extract_raw_targets_via_groq(
        self,
        items:          list,
        query:          str,
        ner_annotation: BioNERAnnotation,
    ) -> List[Dict[str, Any]]:
        """Send NER-enriched prompt to Groq and parse response."""

        excerpts = []
        for item in items[:_MAX_ITEMS_GROQ]:
            content = (
                getattr(item, "content", None) or
                (item.get("content") if isinstance(item, dict) else "")
            )[:600]
            title = (
                getattr(item, "title", "") or
                (item.get("title", "") if isinstance(item, dict) else "")
            )
            excerpts.append(f"[{title[:60]}]\n{content}")

        text_block = "\n\n---\n\n".join(excerpts)

        # Inject NER hints
        def _fmt(s: set, limit: int = 20) -> str:
            items_list = sorted(s)[:limit]
            return ", ".join(items_list) if items_list else "none detected"

        prompt = _GROQ_EXTRACT_PROMPT.format(
            ner_genes     = _fmt(ner_annotation.genes),
            ner_mutations = _fmt(ner_annotation.mutations),
            ner_drugs     = _fmt(ner_annotation.drugs),
            ner_diseases  = _fmt(ner_annotation.diseases),
            ner_pathways  = _fmt(ner_annotation.pathways),
            text_excerpts = text_block,
        )

        if self._groq is not None:
            raw = await self._groq.chat(
                prompt,
                max_tokens    = 1200,
                temperature   = 0.0,
                system_prompt = _GROQ_EXTRACT_SYSTEM,
            )
        else:
            raw = ""

        if raw:
            try:
                match = re.search(r"\[.*\]", raw, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    if isinstance(parsed, list):
                        logger.info(
                            f"TargetExtractor (Groq): {len(parsed)} raw targets"
                        )
                        return parsed
            except Exception as exc:
                logger.debug(f"Groq JSON parse error: {exc}")

        # Fallback: use BioNER genes directly
        if ner_annotation.genes:
            fallback = [
                {
                    "gene":               gene,
                    "protein":            "",
                    "mutations":          [
                        m for m in ner_annotation.mutations
                        if gene.upper() in m.upper() or len(ner_annotation.genes) == 1
                    ],
                    "disease_context":    next(iter(ner_annotation.diseases), ""),
                    "druggability_notes": "",
                }
                for gene in sorted(ner_annotation.genes)[:_MAX_TARGETS]
            ]
            logger.info(
                f"TargetExtractor: Groq unavailable — BioNER fallback "
                f"({len(fallback)} genes)"
            )
            return fallback

        return []

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3 — UniProt (now delegates to UniProtValidator)
    # ─────────────────────────────────────────────────────────────────────────

    async def _resolve_uniprot(self, gene: str) -> Optional[str]:
        """Quick accession lookup (kept for backward compat)."""
        info = await self._uniprot_val.enrich(gene)
        return info.accession if info.accession else None

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4 — PDB search (unchanged from v1)
    # ─────────────────────────────────────────────────────────────────────────

    async def _search_pdb(self, gene: str, uniprot_id: Optional[str] = None) -> List[str]:
        """Search PDB for structures using UniProt ID (preferred) or Gene Symbol."""
        if not uniprot_id and not gene:
            return []

        # Prefer UniProt Accession for precision
        if uniprot_id:
            attribute = "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession"
            value = uniprot_id
        else:
            attribute = "rcsb_entity_source_organism.rcsb_gene_name.value"
            value = gene.upper()

        payload = {
            "query": {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": attribute,
                    "operator": "exact_match",
                    "value": value
                }
            },
            "request_options": {
                "return_all_hits": False,
                "results_verbosity": "minimal"
            },
            "return_type": "entry"
        }

        pdb_ids = []
        try:
            sess = await self._get_session()
            async with sess.post(
                _PDB_SEARCH_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Extract identifiers from the result_set
                    pdb_ids = [r["identifier"] for r in data.get("result_set", [])]
                else:
                    logger.debug(f"PDB API Error: {resp.status}")
        except Exception as exc:
            logger.debug(f"PDB search exception: {exc}")

        return pdb_ids[:10]

    async def _fetch_pdb_entry(self, pdb_id: str) -> Optional[PDBStructure]:
        try:
            sess = await self._get_session()
            url  = _PDB_ENTRY_URL.format(pdb_id=pdb_id.upper())
            async with sess.get(url, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    return PDBStructure(pdb_id=pdb_id)
                data       = await resp.json()
                title      = data.get("struct", {}).get("title", "")
                methods    = data.get("exptl", [{}])
                method     = methods[0].get("method", "") if methods else ""
                entry_info = data.get("rcsb_entry_info", {})
                resolution = entry_info.get("resolution_combined")
                if isinstance(resolution, list):
                    resolution = resolution[0] if resolution else None
                return PDBStructure(
                    pdb_id    = pdb_id.upper(),
                    title     = title,
                    method    = method,
                    resolution= float(resolution) if resolution is not None else None,
                )
        except Exception as exc:
            logger.debug(f"PDB entry fetch failed for {pdb_id}: {exc}")
            return PDBStructure(pdb_id=pdb_id)

    async def _resolve_alphafold(self, uniprot_id: str) -> Optional[AlphaFoldEntry]:
        if not uniprot_id:
            return None
        try:
            sess = await self._get_session()
            url  = _ALPHAFOLD_API_URL.format(uniprot_id=uniprot_id)
            async with sess.get(url, headers={"Accept": "application/json"}) as resp:
                if resp.status == 404:
                    return None
                if resp.status != 200:
                    return None
                data  = await resp.json()
                if not data:
                    return None
                entry = data[0]
                return AlphaFoldEntry(
                    entry_id  = entry.get("entryId", f"AF-{uniprot_id}-F1"),
                    pdb_url   = entry.get("pdbUrl", ""),
                    cif_url   = entry.get("cifUrl", ""),
                    avg_plddt = entry.get("confidenceAvgLocalScore"),
                )
        except Exception as exc:
            logger.debug(f"AlphaFold error for {uniprot_id}: {exc}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5 — Provenance attachment (FIXED: works with both dict and object)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _attach_provenance(
        raw:   Dict[str, Any],
        items: list,
        gene:  str,
    ):
        pmids:  List[str] = []
        dois:   List[str] = []
        count   = 0
        gene_up = gene.upper()

        for item in items:
            # Get content safely from either dict or object
            if isinstance(item, dict):
                content = item.get("content", "")
                pmid = item.get("pmid")
                doi  = item.get("doi")
            else:
                content = getattr(item, "content", "")
                pmid = getattr(item, "pmid", None)
                doi  = getattr(item, "doi", None)

            if gene_up not in content.upper():
                continue
            count += 1
            if pmid and str(pmid) not in pmids:
                pmids.append(str(pmid))
            if doi and str(doi) not in dois:
                dois.append(str(doi))

        return pmids[:10], dois[:10], count

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6 — Full structure resolution (UniProt v2 + PDB + AlphaFold)
    # ─────────────────────────────────────────────────────────────────────────

    async def _resolve_structure(
        self,
        raw:   Dict[str, Any],
        items: list,
    ) -> DrugTarget:
        gene = raw.get("gene", "").strip()
        if not gene:
            return DrugTarget(gene="unknown")

        # UniProt full enrichment
        uniprot_info = await self._uniprot_val.enrich(gene)
        uniprot_id   = uniprot_info.accession or None

        # PDB + AlphaFold in parallel
        pdb_task = asyncio.create_task(self._search_pdb(gene, uniprot_id))
        af_task = (
            asyncio.create_task(self._resolve_alphafold(uniprot_id))
            if uniprot_id
            else asyncio.create_task(asyncio.sleep(0, result=None))  # dummy coro
        )
        pdb_ids, alphafold = await asyncio.gather(pdb_task, af_task)

        # Merge PDB IDs from UniProt
        existing_pdb = set(pdb_ids)
        for pid in uniprot_info.pdb_ids[:10]:
            if pid not in existing_pdb:
                pdb_ids.append(pid)
                existing_pdb.add(pid)

        # PDB detail (top N)
        detail_tasks       = [self._fetch_pdb_entry(pid) for pid in pdb_ids[:_MAX_PDB_DETAIL]]
        pdb_structures_raw = await asyncio.gather(*detail_tasks, return_exceptions=True)
        pdb_structures     = [s for s in pdb_structures_raw if isinstance(s, PDBStructure)]

        pmids, dois, source_count = self._attach_provenance(raw, items, gene)

        # Build druggability notes
        druggability_notes = raw.get("druggability_notes", "")
        if uniprot_info.chembl_ids and "ChEMBL" not in druggability_notes:
            chembl_str = ", ".join(uniprot_info.chembl_ids[:3])
            sep        = "; " if druggability_notes else ""
            druggability_notes += f"{sep}ChEMBL: {chembl_str}"
        if uniprot_info.binding_site_count and "binding site" not in druggability_notes:
            sep = "; " if druggability_notes else ""
            druggability_notes += f"{sep}{uniprot_info.binding_site_count} binding site(s)"

        protein = raw.get("protein", "") or uniprot_info.protein_full_name

        return DrugTarget(
            gene               = gene,
            protein            = protein,
            mutations          = raw.get("mutations") or [],
            disease_context    = raw.get("disease_context", "")
                                 or (uniprot_info.associated_diseases[:1] or [""])[0],
            druggability_notes = druggability_notes,
            uniprot_id         = uniprot_id,
            pdb_ids            = pdb_ids,
            pdb_structures     = pdb_structures,
            alphafold          = alphafold if isinstance(alphafold, AlphaFoldEntry) else None,
            supporting_pmids   = pmids,
            supporting_dois    = dois,
            source_count       = source_count,
            uniprot_info       = uniprot_info,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────────

    async def extract_targets(
        self,
        validated_items: list,
        query:           str,
    ) -> List[DrugTarget]:
        """
        Main entry point.

        Steps:
          1. BioNER annotation of all validated items.
          2. Groq-guided extraction (NER-primed prompt).
          3. Deduplication by gene symbol.
          4. Concurrent structure resolution (UniProt v2 + PDB + AlphaFold).
          5. PubMed frequency scoring.
          6. Pathway mapping (Reactome + KEGG + text).
        """
        if not validated_items:
            return []

        # ── Step 1: BioNER ────────────────────────────────────────────────────
        ner_annotation = await self._annotate_items(validated_items)

        # ── Step 2: LLM extraction ────────────────────────────────────────────
        raw_targets = await self._extract_raw_targets_via_groq(
            validated_items, query, ner_annotation
        )
        if not raw_targets:
            logger.info("TargetExtractor: no targets extracted")
            return []

        # ── Step 3: Deduplication ─────────────────────────────────────────────
        seen_genes:     Set[str]          = set()
        unique_targets: List[Dict[str, Any]] = []
        for t in raw_targets:
            gene_key = t.get("gene", "").strip().upper()
            if gene_key and gene_key not in seen_genes:
                seen_genes.add(gene_key)
                unique_targets.append(t)

        unique_targets = unique_targets[:_MAX_TARGETS]
        logger.info(
            f"TargetExtractor: resolving {len(unique_targets)} unique targets: "
            f"{[t.get('gene') for t in unique_targets]}"
        )

        # ── Step 4: Concurrent structure resolution ───────────────────────────
        resolve_tasks = [
            self._resolve_structure(t, validated_items) for t in unique_targets
        ]
        results = await asyncio.gather(*resolve_tasks, return_exceptions=True)

        targets: List[DrugTarget] = []
        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"TargetExtractor: structure resolution failed — {res}")
            else:
                targets.append(res)

        # ── Step 5: PubMed frequency scoring ─────────────────────────────────
        try:
            targets = await self._pubmed_freq.score_targets(targets)
        except Exception as exc:
            logger.warning(f"PubMed frequency scoring failed: {exc}")

        # ── Step 6: Pathway mapping ───────────────────────────────────────────
        try:
            targets = await self._pathway_map.map_targets(
                targets, validated_items
            )
        except Exception as exc:
            logger.warning(f"Pathway mapping failed: {exc}")

        logger.info(
            f"TargetExtractor v2.0: {len(targets)} targets resolved "
            f"| PDB={sum(1 for t in targets if t.pdb_ids)} "
            f"| AlphaFold={sum(1 for t in targets if t.alphafold)} "
            f"| PubMed scored={sum(1 for t in targets if t.pubmed_frequency)} "
            f"| Pathway mapped={sum(1 for t in targets if t.pathway_profile)}"
        )
        return targets