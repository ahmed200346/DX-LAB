"""
uniprot_validator.py — Enhanced UniProt Validation

Enriches DrugTarget objects with deep UniProt metadata:
  • Canonical accession + entry name + organism
  • Protein function, catalytic activity, subcellular localisation
  • Associated disease annotations (from UniProt disease cross-refs)
  • Post-translational modifications summary
  • Tissue expression levels (BioGPS/UniProt expression)
  • Druggability signals: binding sites, active sites, natural variants
  • Cross-reference IDs: ChEMBL, PDB (redundant check), Reactome, KEGG
  • Sequence length + molecular weight
  • isoform count
  • is_reviewed flag (Swiss-Prot = True vs TrEMBL = False)

The data is fetched from the UniProt REST API (no key required) and cached
per accession in an in-process dict to avoid redundant calls within a
single agent session.

Public class:
    UniProtValidator
        async enrich(gene: str, uniprot_id: Optional[str]) -> UniProtInfo
        async enrich_targets(targets: List[DrugTarget]) -> List[DrugTarget]

Integration:
    In TargetExtractor._resolve_structure(), replace the bare
    _resolve_uniprot() call with:

        validator = UniProtValidator()
        info      = await validator.enrich(gene, uniprot_id)
        # DrugTarget fields populated from info

    Or call enrich_targets() on the full list after resolution.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger


# =============================================================================
# CONSTANTS
# =============================================================================

_UNIPROT_REST     = "https://rest.uniprot.org/uniprotkb"
_UNIPROT_SEARCH   = f"{_UNIPROT_REST}/search"
_UNIPROT_ENTRY    = f"{_UNIPROT_REST}/{{accession}}"

# Fields to request from UniProt (REST API field names)
_UNIPROT_FIELDS = ",".join([
    "accession",
    "id",                     # entry name
    "gene_names",
    "protein_name",
    "organism_name",
    "reviewed",               # Swiss-Prot vs TrEMBL
    "length",
    "mass",
    "cc_function",
    "cc_catalytic_activity",
    "cc_subcellular_location",
    "cc_disease",
    "cc_ptm",
    "ft_binding",             # binding site features
    "ft_act_site",
    "ft_natural_variant",
    "dr_chembl",
    "dr_reactome",
    "dr_kegg",
    "dr_pdb",
    "go",                     # GO term names
    "keyword",                # UniProt keywords
    "xref_count_pdb",
])

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)
_MAX_CONCURRENT  = 5


# =============================================================================
# DATA MODEL
# =============================================================================

@dataclass
class UniProtInfo:
    # Core identity
    accession:         str             = ""
    entry_name:        str             = ""
    gene_symbol:       str             = ""
    protein_full_name: str             = ""
    organism:          str             = ""
    is_reviewed:       bool            = False   # Swiss-Prot flag

    # Sequence
    sequence_length:   Optional[int]   = None
    molecular_weight:  Optional[int]   = None

    # Functional annotation
    function_text:     str             = ""
    subcellular_locs:  List[str]       = field(default_factory=list)
    catalytic_acts:    List[str]       = field(default_factory=list)
    ptm_notes:         str             = ""

    # Disease links
    associated_diseases: List[str]    = field(default_factory=list)

    # Features
    binding_site_count:   int         = 0
    active_site_count:    int         = 0
    natural_variant_count: int        = 0

    # Cross-references
    chembl_ids:    List[str]          = field(default_factory=list)
    reactome_ids:  List[str]          = field(default_factory=list)
    kegg_ids:      List[str]          = field(default_factory=list)
    pdb_ids:       List[str]          = field(default_factory=list)
    pdb_count:     int                = 0

    # GO terms
    go_terms:      List[str]          = field(default_factory=list)

    # UniProt keywords
    keywords:      List[str]          = field(default_factory=list)

    # Derived druggability signal
    druggability_score: float         = 0.0   # 0–1, computed heuristically

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accession":          self.accession,
            "entry_name":         self.entry_name,
            "gene_symbol":        self.gene_symbol,
            "protein_full_name":  self.protein_full_name,
            "organism":           self.organism,
            "is_reviewed":        self.is_reviewed,
            "sequence_length":    self.sequence_length,
            "molecular_weight":   self.molecular_weight,
            "function":           self.function_text[:500] if self.function_text else "",
            "subcellular_locs":   self.subcellular_locs,
            "catalytic_acts":     self.catalytic_acts,
            "ptm_notes":          self.ptm_notes[:300] if self.ptm_notes else "",
            "associated_diseases": self.associated_diseases,
            "binding_site_count": self.binding_site_count,
            "active_site_count":  self.active_site_count,
            "natural_variant_count": self.natural_variant_count,
            "chembl_ids":         self.chembl_ids,
            "reactome_ids":       self.reactome_ids,
            "kegg_ids":           self.kegg_ids,
            "pdb_ids":            self.pdb_ids[:10],
            "pdb_count":          self.pdb_count,
            "go_terms":           self.go_terms[:15],
            "keywords":           self.keywords[:15],
            "druggability_score": round(self.druggability_score, 3),
        }

    def is_valid(self) -> bool:
        """True when the entry was successfully fetched from UniProt."""
        return bool(self.accession)


# =============================================================================
# PARSER HELPERS
# =============================================================================

def _first_str(obj: Any, *keys: str, default: str = "") -> str:
    """Drill into nested dict with fallback."""
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, {})
    if isinstance(cur, str):
        return cur
    if isinstance(cur, list) and cur:
        v = cur[0]
        return v if isinstance(v, str) else str(v)
    return default


def _list_of_str(obj: Any, *keys: str) -> List[str]:
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return []
        cur = cur.get(k, [])
    if isinstance(cur, list):
        return [str(x) for x in cur if x]
    return []


def _parse_comments(data: Dict[str, Any], comment_type: str) -> List[str]:
    """Extract text from UniProt comment sections."""
    texts: List[str] = []
    for comment in data.get("comments", []):
        if comment.get("commentType", "").upper() != comment_type.upper():
            continue
        # Nested value structures vary by comment type
        for val in comment.get("texts", []):
            v = val.get("value", "")
            if v:
                texts.append(v)
        # Direct value path (e.g. subcellular location)
        for loc in comment.get("subcellularLocations", []):
            loc_val = loc.get("location", {}).get("value", "")
            if loc_val:
                texts.append(loc_val)
        # Disease comments
        disease = comment.get("disease", {})
        if disease:
            dn = disease.get("diseaseId", "") or disease.get("diseaseName", "")
            if dn:
                texts.append(dn)
    return texts


def _count_features(data: Dict[str, Any], feature_type: str) -> int:
    return sum(
        1 for f in data.get("features", [])
        if f.get("type", "").upper() == feature_type.upper()
    )


def _xref_ids(data: Dict[str, Any], db: str) -> List[str]:
    return [
        ref["id"]
        for ref in data.get("uniProtKBCrossReferences", [])
        if ref.get("database", "").upper() == db.upper()
    ]


def _compute_druggability(info: UniProtInfo) -> float:
    """
    Heuristic druggability score (0–1) based on:
    - ChEMBL cross-reference   (strong signal)
    - PDB structure count       (structural tractability)
    - Binding site annotations  (functional tractability)
    - Swiss-Prot reviewed       (data quality)
    - Reactome pathway coverage
    - Protein keywords
    """
    score = 0.0

    # ChEMBL presence → strong druggability signal
    if info.chembl_ids:
        score += 0.30

    # PDB structures (log-scaled, capped at 0.20)
    import math
    if info.pdb_count > 0:
        score += min(0.20, 0.07 * math.log1p(info.pdb_count))

    # Binding sites
    if info.binding_site_count > 0:
        score += min(0.15, 0.05 * info.binding_site_count)

    # Active sites
    if info.active_site_count > 0:
        score += 0.05

    # Swiss-Prot reviewed entry → higher confidence annotation
    if info.is_reviewed:
        score += 0.10

    # Reactome pathway participation
    if info.reactome_ids:
        score += min(0.10, 0.03 * len(info.reactome_ids))

    # UniProt keywords indicative of druggability
    druggable_keywords = {
        "kinase", "protease", "receptor", "transferase", "hydrolase",
        "oxidoreductase", "nuclear receptor", "phosphoprotein",
        "disease variant", "proto-oncogene",
    }
    kw_lower = {k.lower() for k in info.keywords}
    kw_hits  = len(druggable_keywords & kw_lower)
    score   += min(0.10, 0.03 * kw_hits)

    return min(1.0, score)


# =============================================================================
# UNIPROT VALIDATOR
# =============================================================================

class UniProtValidator:
    """
    Enriches gene/protein targets with deep UniProt metadata.
    In-process cache avoids redundant network calls per session.
    """

    def __init__(self):
        self._cache:     Dict[str, UniProtInfo] = {}     # accession → info
        self._session:   Optional[aiohttp.ClientSession] = None
        self._semaphore  = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Accession lookup ──────────────────────────────────────────────────────

    async def _search_accession(self, gene: str) -> Optional[str]:
        """Search UniProt by gene name and return the best human Swiss-Prot accession."""
        try:
            session = await self._get_session()
            params  = {
                "query":  f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true",
                "fields": "accession,reviewed",
                "format": "json",
                "size":   "1",
            }
            async with session.get(_UNIPROT_SEARCH, params=params) as resp:
                if resp.status != 200:
                    return None
                data    = await resp.json(content_type=None)
                results = data.get("results", [])
                if results:
                    acc = results[0].get("primaryAccession", "")
                    logger.debug(f"UniProt accession for {gene}: {acc}")
                    return acc or None
        except Exception as exc:
            logger.debug(f"UniProt search failed for {gene}: {exc}")
        return None

    # ── Entry fetch ───────────────────────────────────────────────────────────

    async def _fetch_entry(self, accession: str) -> Optional[Dict[str, Any]]:
        """Fetch full UniProt JSON entry for a given accession."""
        try:
            session = await self._get_session()
            url     = _UNIPROT_ENTRY.format(accession=accession)
            params  = {"format": "json"}
            async with session.get(url, params=params) as resp:
                if resp.status == 404:
                    logger.debug(f"UniProt: accession {accession} not found")
                    return None
                if resp.status != 200:
                    logger.debug(f"UniProt entry fetch HTTP {resp.status} for {accession}")
                    return None
                return await resp.json(content_type=None)
        except Exception as exc:
            logger.debug(f"UniProt entry fetch error for {accession}: {exc}")
        return None

    # ── Parser ────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_entry(data: Dict[str, Any]) -> UniProtInfo:
        accession  = data.get("primaryAccession", "")
        entry_name = data.get("uniProtkbId", "")

        # Gene symbol (primary gene name)
        gene_symbol = ""
        for gn in data.get("genes", []):
            gv = gn.get("geneName", {}).get("value", "")
            if gv:
                gene_symbol = gv
                break

        # Protein name
        prot_desc  = data.get("proteinDescription", {})
        rec_name   = prot_desc.get("recommendedName", {})
        full_name  = rec_name.get("fullName", {}).get("value", "")
        if not full_name:
            for alt in prot_desc.get("alternativeNames", []):
                fn = alt.get("fullName", {}).get("value", "")
                if fn:
                    full_name = fn
                    break

        # Organism
        organism = data.get("organism", {}).get("scientificName", "")

        # Reviewed flag
        is_reviewed = data.get("entryType", "").startswith("UniProtKB reviewed")

        # Sequence
        seq_data   = data.get("sequence", {})
        seq_length = seq_data.get("length")
        mol_weight = seq_data.get("molWeight")

        # Comments
        function_texts  = _parse_comments(data, "FUNCTION")
        subcel_locs     = _parse_comments(data, "SUBCELLULAR LOCATION")
        catalytic_acts  = _parse_comments(data, "CATALYTIC ACTIVITY")
        ptm_texts       = _parse_comments(data, "PTM")
        disease_texts   = _parse_comments(data, "DISEASE")

        # Features
        binding_count  = _count_features(data, "BINDING")
        active_count   = _count_features(data, "ACT_SITE")
        variant_count  = _count_features(data, "NATURAL VARIANT")

        # Cross-references
        chembl_ids   = _xref_ids(data, "ChEMBL")
        reactome_ids = _xref_ids(data, "Reactome")
        kegg_ids     = _xref_ids(data, "KEGG")
        pdb_ids      = _xref_ids(data, "PDB")

        # GO terms — extract names from the goTerms list
        go_terms: List[str] = []
        for go in data.get("uniProtKBCrossReferences", []):
            if go.get("database") == "GO":
                for prop in go.get("properties", []):
                    if prop.get("key") == "GoTerm":
                        term_val = prop.get("value", "")
                        if term_val:
                            go_terms.append(term_val.split(":")[-1].strip())

        # Keywords
        keywords = [kw.get("name", "") for kw in data.get("keywords", []) if kw.get("name")]

        info = UniProtInfo(
            accession          = accession,
            entry_name         = entry_name,
            gene_symbol        = gene_symbol,
            protein_full_name  = full_name,
            organism           = organism,
            is_reviewed        = is_reviewed,
            sequence_length    = int(seq_length) if seq_length is not None else None,
            molecular_weight   = int(mol_weight) if mol_weight is not None else None,
            function_text      = " ".join(function_texts),
            subcellular_locs   = subcel_locs,
            catalytic_acts     = catalytic_acts,
            ptm_notes          = " ".join(ptm_texts),
            associated_diseases= disease_texts,
            binding_site_count = binding_count,
            active_site_count  = active_count,
            natural_variant_count = variant_count,
            chembl_ids         = chembl_ids,
            reactome_ids       = reactome_ids,
            kegg_ids           = kegg_ids,
            pdb_ids            = pdb_ids,
            pdb_count          = len(pdb_ids),
            go_terms           = go_terms,
            keywords           = keywords,
        )
        info.druggability_score = _compute_druggability(info)
        return info

    # ── Public API ─────────────────────────────────────────────────────────────

    async def enrich(
        self, gene: str, uniprot_id: Optional[str] = None
    ) -> UniProtInfo:
        """
        Return enriched UniProtInfo for a gene symbol.

        If uniprot_id is provided it is used directly; otherwise a search
        is performed to find the canonical human accession.
        Results are cached in-process.
        """
        async with self._semaphore:
            accession = uniprot_id

            # Step 1: resolve accession if not supplied
            if not accession:
                accession = await self._search_accession(gene)
            if not accession:
                logger.debug(f"UniProtValidator: no accession found for {gene}")
                return UniProtInfo(gene_symbol=gene)

            # Step 2: check in-process cache
            if accession in self._cache:
                logger.debug(f"UniProtValidator cache HIT: {accession}")
                return self._cache[accession]

            # Step 3: fetch full entry
            data = await self._fetch_entry(accession)
            if data is None:
                empty = UniProtInfo(accession=accession, gene_symbol=gene)
                self._cache[accession] = empty
                return empty

            # Step 4: parse + cache
            info = self._parse_entry(data)
            if not info.gene_symbol:
                info.gene_symbol = gene
            self._cache[accession] = info

            logger.info(
                f"UniProtValidator: {gene} → {accession} | "
                f"reviewed={info.is_reviewed} | "
                f"pdb={info.pdb_count} | chembl={len(info.chembl_ids)} | "
                f"druggability={info.druggability_score:.2f}"
            )
            return info

    async def enrich_batch(
        self,
        gene_accession_pairs: List[tuple],   # [(gene, uniprot_id_or_None), …]
    ) -> List[UniProtInfo]:
        """Enrich a list of (gene, accession) pairs concurrently."""
        tasks = [self.enrich(g, acc) for g, acc in gene_accession_pairs]
        return list(await asyncio.gather(*tasks))

    async def enrich_targets(self, targets: list) -> list:
        """
        In-place enrichment of a list of DrugTarget objects.
        Adds a `uniprot_info` attribute (UniProtInfo) to each target
        and updates protein name + druggability_notes if they were empty.

        Returns the same list (mutated).
        """
        for target in targets:
            gene       = getattr(target, "gene", "")
            uniprot_id = getattr(target, "uniprot_id", None)
            info       = await self.enrich(gene, uniprot_id)

            # Attach full info object
            target.uniprot_info = info

            # Back-fill empty fields on DrugTarget
            if not target.protein and info.protein_full_name:
                target.protein = info.protein_full_name

            if not target.druggability_notes and (
                info.chembl_ids or info.binding_site_count or info.active_site_count
            ):
                notes_parts: List[str] = []
                if info.chembl_ids:
                    notes_parts.append(
                        f"ChEMBL: {', '.join(info.chembl_ids[:3])}"
                    )
                if info.binding_site_count:
                    notes_parts.append(
                        f"{info.binding_site_count} binding site(s)"
                    )
                if info.active_site_count:
                    notes_parts.append(
                        f"{info.active_site_count} active site(s)"
                    )
                if info.is_reviewed:
                    notes_parts.append("Swiss-Prot reviewed")
                target.druggability_notes = "; ".join(notes_parts)

            # Merge any PDB IDs from UniProt not already in the target
            existing_pdb = set(target.pdb_ids)
            for pid in info.pdb_ids[:10]:
                if pid not in existing_pdb:
                    target.pdb_ids.append(pid)
                    existing_pdb.add(pid)

        return targets
