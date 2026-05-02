"""
pathway_mapper.py — Pathway Mapping for Drug Targets

Maps gene/protein targets onto biological pathways using:
  1. Reactome REST API  — hierarchical pathway tree, event counts
  2. KEGG REST API      — pathway enrichment, compound associations
  3. BioNER-derived pathways from validated text (no API call needed)

Produces per-target:
  PathwayProfile
    reactome_pathways  : List[ReactomePathway]
    kegg_pathways      : List[KEGGPathway]
    text_pathways      : List[str]   (from BioNER mentions in source docs)
    top_pathway        : str         (highest-confidence pathway name)
    pathway_score      : float 0–1   (coverage/evidence strength)
    network_context    : str         (brief text summary for the LLM)

All results are in-process-cached per session.

Integration (in TargetExtractor or ExtractorAgent):

    mapper = PathwayMapper()

    # After target resolution:
    targets = await mapper.map_targets(targets, validated_items)

    # The DrugTarget gains a `pathway_profile` attribute.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger


# =============================================================================
# CONSTANTS
# =============================================================================

_REACTOME_MAPPING_URL  = "https://reactome.org/ContentService/data/mapping/UniProt/{uniprot}/pathways?species=9606"
_REACTOME_PATHWAY_URL  = "https://reactome.org/ContentService/data/query/{stId}"
_KEGG_GENE_URL         = "https://rest.kegg.jp/find/genes/{gene}"
_KEGG_PATHWAYS_URL     = "https://rest.kegg.jp/link/pathway/{kegg_gene_id}"
_KEGG_PATHWAY_NAME_URL = "https://rest.kegg.jp/list/{pathway_id}"

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=12)
_MAX_CONCURRENT  = 4
_MAX_REACTOME    = 15   # max Reactome pathways to store per target
_MAX_KEGG        = 10   # max KEGG pathways to store per target


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class ReactomePathway:
    stId:         str
    name:         str
    top_level:    str  = ""   # e.g. "Signal Transduction"
    species:      str  = "Homo sapiens"
    url:          str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stId":      self.stId,
            "name":      self.name,
            "top_level": self.top_level,
            "species":   self.species,
            "url":       self.url or f"https://reactome.org/PathwayBrowser/#/{self.stId}",
        }


@dataclass
class KEGGPathway:
    pathway_id:  str
    name:        str
    url:         str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pathway_id": self.pathway_id,
            "name":       self.name,
            "url": (
                self.url
                or f"https://www.kegg.jp/pathway/{self.pathway_id}"
            ),
        }


@dataclass
class PathwayProfile:
    gene:              str
    reactome_pathways: List[ReactomePathway] = field(default_factory=list)
    kegg_pathways:     List[KEGGPathway]     = field(default_factory=list)
    text_pathways:     List[str]             = field(default_factory=list)
    top_pathway:       str                   = ""
    pathway_score:     float                 = 0.0
    network_context:   str                   = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gene":              self.gene,
            "reactome_pathways": [p.to_dict() for p in self.reactome_pathways],
            "kegg_pathways":     [p.to_dict() for p in self.kegg_pathways],
            "text_pathways":     self.text_pathways,
            "top_pathway":       self.top_pathway,
            "pathway_score":     round(self.pathway_score, 3),
            "network_context":   self.network_context,
        }

    @property
    def all_pathway_names(self) -> List[str]:
        names = [p.name for p in self.reactome_pathways]
        names += [p.name for p in self.kegg_pathways]
        names += self.text_pathways
        return list(dict.fromkeys(names))  # deduplicated, order-preserving


# =============================================================================
# PATHWAY MAPPER
# =============================================================================

class PathwayMapper:
    """
    Maps gene/protein targets onto biological pathways.
    Session and cache are re-used across calls within the same agent lifecycle.
    """

    def __init__(self):
        self._session:   Optional[aiohttp.ClientSession] = None
        self._semaphore  = asyncio.Semaphore(_MAX_CONCURRENT)
        self._cache:     Dict[str, PathwayProfile] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Reactome ──────────────────────────────────────────────────────────────

    async def _reactome_pathways(
        self, uniprot_id: str
    ) -> List[ReactomePathway]:
        """Fetch Reactome pathways for a UniProt accession."""
        if not uniprot_id:
            return []
        try:
            session = await self._get_session()
            url     = _REACTOME_MAPPING_URL.format(uniprot=uniprot_id)
            async with session.get(url, headers={"Accept": "application/json"}) as resp:
                if resp.status == 404:
                    logger.debug(f"Reactome: no pathways for {uniprot_id}")
                    return []
                if resp.status != 200:
                    logger.debug(f"Reactome HTTP {resp.status} for {uniprot_id}")
                    return []
                data = await resp.json(content_type=None)

                pathways: List[ReactomePathway] = []
                for entry in (data or [])[:_MAX_REACTOME]:
                    stId = entry.get("stId", "")
                    name = entry.get("displayName", entry.get("name", ""))
                    if not stId or not name:
                        continue
                    # Extract top-level pathway from name when possible
                    top_level = self._guess_top_level(name)
                    pathways.append(ReactomePathway(
                        stId      = stId,
                        name      = name,
                        top_level = top_level,
                        url       = f"https://reactome.org/PathwayBrowser/#/{stId}",
                    ))
                logger.debug(
                    f"Reactome: {uniprot_id} → {len(pathways)} pathways"
                )
                return pathways
        except asyncio.TimeoutError:
            logger.debug(f"Reactome timeout for {uniprot_id}")
            return []
        except Exception as exc:
            logger.debug(f"Reactome error for {uniprot_id}: {exc}")
            return []

    @staticmethod
    def _guess_top_level(name: str) -> str:
        """
        Heuristic: guess the Reactome top-level category from pathway name.
        """
        n = name.lower()
        if any(k in n for k in ["signal", "receptor", "kinase", "mapk", "pi3k", "mtor"]):
            return "Signal Transduction"
        if any(k in n for k in ["dna repair", "dna damage", "homologous recom"]):
            return "DNA Repair"
        if any(k in n for k in ["cell cycle", "checkpoint", "cyclin", "cdk"]):
            return "Cell Cycle"
        if any(k in n for k in ["apoptosis", "caspase", "bcl", "death"]):
            return "Programmed Cell Death"
        if any(k in n for k in ["immune", "innate", "adaptive", "interferon", "cytokine"]):
            return "Immune System"
        if any(k in n for k in ["metabol", "glycolys", "tca", "oxidative phospho"]):
            return "Metabolism"
        if any(k in n for k in ["transcription", "gene express", "chromatin", "epigenet"]):
            return "Gene Expression"
        if any(k in n for k in ["transport", "vesicle", "endosom", "autophagy"]):
            return "Vesicle-mediated Transport"
        if any(k in n for k in ["translation", "ribosom", "mrna"]):
            return "Protein Synthesis"
        if any(k in n for k in ["ubiquitin", "proteasome", "protein degradation"]):
            return "Protein Ubiquitination"
        return "Other"

    # ── KEGG ─────────────────────────────────────────────────────────────────

    async def _kegg_gene_id(self, gene: str) -> Optional[str]:
        """Look up the KEGG human gene ID (e.g. hsa:3845 for KRAS)."""
        try:
            session = await self._get_session()
            query   = f"hsa:{gene}"
            async with session.get(_KEGG_GENE_URL.format(gene=gene)) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()
                # KEGG returns TSV: kegg_id<TAB>description
                for line in text.strip().splitlines():
                    parts = line.split("\t")
                    if parts:
                        kid = parts[0].strip()
                        if kid.startswith("hsa:"):
                            return kid
                return None
        except Exception as exc:
            logger.debug(f"KEGG gene lookup failed for {gene}: {exc}")
            return None

    async def _kegg_pathways_for_gene(
        self, kegg_gene_id: str
    ) -> List[KEGGPathway]:
        """Return KEGG pathways linked to a KEGG gene ID."""
        try:
            session = await self._get_session()
            async with session.get(
                _KEGG_PATHWAYS_URL.format(kegg_gene_id=kegg_gene_id)
            ) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
                # TSV: kegg_gene_id<TAB>path:hsa05210
                pathway_ids: List[str] = []
                for line in text.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        pid = parts[1].strip()   # e.g. "path:hsa05210"
                        if pid.startswith("path:"):
                            pathway_ids.append(pid.replace("path:", ""))

                # Fetch names concurrently (limited to MAX_KEGG)
                pathway_ids = pathway_ids[:_MAX_KEGG]
                name_tasks  = [self._kegg_pathway_name(pid) for pid in pathway_ids]
                names       = await asyncio.gather(*name_tasks)

                pathways: List[KEGGPathway] = []
                for pid, name in zip(pathway_ids, names):
                    if name:
                        pathways.append(KEGGPathway(
                            pathway_id = pid,
                            name       = name,
                            url        = f"https://www.kegg.jp/pathway/{pid}",
                        ))
                logger.debug(
                    f"KEGG: {kegg_gene_id} → {len(pathways)} pathways"
                )
                return pathways
        except Exception as exc:
            logger.debug(f"KEGG pathway fetch error for {kegg_gene_id}: {exc}")
            return []

    async def _kegg_pathway_name(self, pathway_id: str) -> Optional[str]:
        """Return the human-readable name for a KEGG pathway ID."""
        try:
            session = await self._get_session()
            async with session.get(
                _KEGG_PATHWAY_NAME_URL.format(pathway_id=pathway_id)
            ) as resp:
                if resp.status != 200:
                    return pathway_id  # fall back to raw ID
                text = await resp.text()
                # TSV: pathway_id<TAB>Name - Organism
                for line in text.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        # Strip organism suffix: "Colorectal cancer - Homo sapiens (human)"
                        name = parts[1].split(" - Homo sapiens")[0].strip()
                        return name
                return pathway_id
        except Exception:
            return pathway_id

    # ── Text pathway extraction ───────────────────────────────────────────────

    @staticmethod
    def _extract_text_pathways(
        gene: str, validated_items: list
    ) -> List[str]:
        """
        Extract pathway mentions from validated item content using
        the BioNER pathway regex (imported inline to avoid circular imports).
        """
        try:
            from bio_ner import _PATHWAY_RE
        except ImportError:
            # Fallback minimal pathway pattern
            _PATHWAY_RE = re.compile(
                r'\b(?:MAPK|PI3K|mTOR|JAK.STAT|WNT|Notch|Hedgehog|TGF.?β|'
                r'HIPPO|YAP|Apoptosis|Cell\s*cycle|DNA\s*repair)\b',
                re.IGNORECASE,
            )

        found: List[str] = []
        seen:  set       = set()

        # Only look in items that mention the gene
        gene_upper = gene.upper()
        for item in validated_items:
            content = getattr(item, "content", None) or item.get("content", "")
            if gene_upper not in content.upper():
                continue
            for m in _PATHWAY_RE.finditer(content[:3000]):
                pw = m.group().strip()
                if pw.lower() not in seen:
                    seen.add(pw.lower())
                    found.append(pw)

        return found[:15]

    # ── Scoring ───────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_pathway_score(profile: PathwayProfile) -> float:
        """
        Heuristic 0–1 score for pathway coverage.
        """
        import math
        n_reactome = len(profile.reactome_pathways)
        n_kegg     = len(profile.kegg_pathways)
        n_text     = len(profile.text_pathways)
        total      = n_reactome + n_kegg + n_text

        if total == 0:
            return 0.0

        raw = (
            0.50 * min(1.0, math.log1p(n_reactome) / math.log1p(10))
            + 0.30 * min(1.0, math.log1p(n_kegg)     / math.log1p(5))
            + 0.20 * min(1.0, math.log1p(n_text)     / math.log1p(8))
        )
        return round(raw, 4)

    @staticmethod
    def _build_network_context(profile: PathwayProfile) -> str:
        """
        Build a short human-readable network context string for the LLM.
        """
        parts: List[str] = []

        if profile.top_pathway:
            parts.append(f"Primary pathway: {profile.top_pathway}.")

        if profile.reactome_pathways:
            top3 = [p.name for p in profile.reactome_pathways[:3]]
            parts.append(f"Reactome: {'; '.join(top3)}.")

        if profile.kegg_pathways:
            top3 = [p.name for p in profile.kegg_pathways[:3]]
            parts.append(f"KEGG: {'; '.join(top3)}.")

        if profile.text_pathways:
            parts.append(
                f"Literature mentions: {', '.join(profile.text_pathways[:4])}."
            )

        return " ".join(parts)

    # ── Per-target resolution ─────────────────────────────────────────────────

    async def _map_target(
        self,
        gene:            str,
        uniprot_id:      Optional[str],
        validated_items: list,
    ) -> PathwayProfile:
        """Resolve all pathway sources for a single gene concurrently."""
        cache_key = f"{gene}:{uniprot_id or ''}"
        if cache_key in self._cache:
            logger.debug(f"PathwayMapper cache HIT: {cache_key}")
            return self._cache[cache_key]

        async with self._semaphore:
            # Double-checked
            if cache_key in self._cache:
                return self._cache[cache_key]

            # Reactome (needs UniProt ID)
            reactome_task = asyncio.create_task(
                self._reactome_pathways(uniprot_id or "")
            )

            # KEGG (needs gene symbol → KEGG ID)
            async def _kegg_chain():
                kid = await self._kegg_gene_id(gene)
                if not kid:
                    return []
                return await self._kegg_pathways_for_gene(kid)

            kegg_task = asyncio.create_task(_kegg_chain())

            # Text pathways (synchronous, wrapped in executor)
            loop = asyncio.get_running_loop()
            text_task = loop.run_in_executor(
                None,
                self._extract_text_pathways,
                gene,
                validated_items,
            )

            reactome_pathways, kegg_pathways, text_pathways = await asyncio.gather(
                reactome_task, kegg_task, text_task
            )

            # Determine top pathway
            top_pathway = ""
            if reactome_pathways:
                top_pathway = reactome_pathways[0].name
            elif kegg_pathways:
                top_pathway = kegg_pathways[0].name
            elif text_pathways:
                top_pathway = text_pathways[0]

            profile = PathwayProfile(
                gene              = gene,
                reactome_pathways = reactome_pathways,
                kegg_pathways     = kegg_pathways,
                text_pathways     = list(text_pathways),
                top_pathway       = top_pathway,
            )
            profile.pathway_score    = self._compute_pathway_score(profile)
            profile.network_context  = self._build_network_context(profile)

            self._cache[cache_key] = profile

            logger.info(
                f"PathwayMapper: {gene} "
                f"reactome={len(reactome_pathways)} "
                f"kegg={len(kegg_pathways)} "
                f"text={len(text_pathways)} "
                f"score={profile.pathway_score:.3f}"
            )
            return profile

    # ── Public API ─────────────────────────────────────────────────────────────

    async def map_targets(
        self,
        targets:         list,          # List[DrugTarget]
        validated_items: list = (),     # List[ValidatedItem] for text extraction
    ) -> list:
        """
        Map all targets concurrently.
        Attaches a `pathway_profile` (PathwayProfile) to each DrugTarget.
        Also populates `druggability_notes` with top-pathway if empty.

        Returns the same list (mutated).
        """
        tasks = [
            self._map_target(
                gene       = getattr(t, "gene", "unknown"),
                uniprot_id = getattr(t, "uniprot_id", None),
                validated_items = list(validated_items),
            )
            for t in targets
        ]
        profiles = await asyncio.gather(*tasks, return_exceptions=True)

        for target, profile in zip(targets, profiles):
            if isinstance(profile, Exception):
                logger.warning(
                    f"PathwayMapper error for {getattr(target, 'gene', '?')}: {profile}"
                )
                continue

            target.pathway_profile = profile

            # Enrich druggability notes with top pathway
            existing_notes = getattr(target, "druggability_notes", "") or ""
            if profile.top_pathway and profile.top_pathway not in existing_notes:
                sep   = "; " if existing_notes else ""
                target.druggability_notes = (
                    existing_notes + sep
                    + f"Primary pathway: {profile.top_pathway}"
                )

        return targets

    async def map_query_pathways(
        self, query: str
    ) -> List[str]:
        """
        Extract pathway names mentioned in a free-text query.
        Useful for query-time filter enrichment.
        """
        try:
            from bio_ner import _PATHWAY_RE
        except ImportError:
            return []

        return list({m.group() for m in _PATHWAY_RE.finditer(query)})
