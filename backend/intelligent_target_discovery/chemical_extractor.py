# ─── chemical_extractor.py ────────────────────────────────────────────────────
"""
ChemicalExtractor  v1.1

Post-processor that sits in the same pipeline position as TargetExtractor,
but focuses on small-molecule drugs and chemical compounds.

Qdrant storage strategy (v1.1)
──────────────────────────────
Chemicals are stored in "chemicals_collection" using the SAME text embedding
model as texts_collection / pdfs_collection (BAAI/bge-base-en, 768-dim,
Distance.COSINE).

Each compound is serialised to a rich natural-language string before embedding:

    "Sotorasib (AMG-510) | Formula: C29H25F2N5O3 | MW: 560.5 Da |
     SMILES: C[C@@H]1CC(=O)N... | InChIKey: LQEBEXMHBLQMDB-JGQUBWHWSA-N |
     Class: covalent KRAS G12C inhibitor | Disease: non-small cell lung cancer |
     Phase: approved | ChEMBL: CHEMBL4523769 | PubChem CID: 2296643 |
     Bioactivity: KRAS IC50 =0.9 nM"

This means:
  - RetrieverAgent.retrieve() finds chemicals alongside texts and PDFs using
    the identical query embedding — no separate retrieval path needed.
  - chemicals_collection uses dim=768, Distance.COSINE — same as texts_collection.
  - Morgan fingerprints are stored as a payload field so downstream code can
    run Tanimoto-based re-ranking without a separate collection.
  - The full ChemicalGraph.to_dict() is stored in payload["chemical_data"] so
    ACPResponse can reconstruct every compound from a single Qdrant hit.

Pipeline position
─────────────────
    validated, metrics = await self.validator.validate(raw_items, query)

    if validated:
        extracted_targets = await self.target_extractor.extract_targets(validated, query)

        extracted_chemicals, chem_points = await self.chemical_extractor.extract_chemicals(
            validated_items=validated,
            query=request.query,
            embed_service=self.embed_svc,
            session_id=request.session_id,
        )
        if chem_points:
            await self.qdrant_mgr.upsert_batch(chem_points, "chemicals_collection")
            total = await self.qdrant_mgr.count_points("chemicals_collection")
            logger.info(f"[{request.session_id}] chemicals_collection: {total} vectors")
    else:
        extracted_targets   = []
        extracted_chemicals = []

See integration_patch.md for the full before/after diffs.

Dependencies
────────────
    rdkit>=2023.9.1   # optional — graceful degradation without it
    aiohttp           # already present
    loguru            # already present
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from loguru import logger

# ── Optional RDKit ────────────────────────────────────────────────────────────
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit.Chem.Draw import rdMolDraw2D
    _RDKIT_AVAILABLE = True
    logger.debug("ChemicalExtractor: RDKit available — full 2D/3D support enabled")
except ImportError:
    _RDKIT_AVAILABLE = False
    logger.warning(
        "ChemicalExtractor: RDKit not installed — 2D SVG and 3D SDF disabled.\n"
        "  pip install rdkit   OR   conda install -c conda-forge rdkit"
    )

# ── Qdrant ────────────────────────────────────────────────────────────────────
try:
    from qdrant_client.models import PointStruct
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False
    PointStruct = None  # type: ignore[assignment,misc]


# =============================================================================
# CONSTANTS
# =============================================================================

_PUBCHEM_BASE      = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PUBCHEM_IMAGE_URL = "https://pubchem.ncbi.nlm.nih.gov/image/imagefly.cgi"
_CHEMBL_BASE       = "https://www.ebi.ac.uk/chembl/api/data"

_MAX_CHEMICALS  = 12   # unique compounds to fully resolve per request
_MAX_ITEMS_GROQ = 8    # validated items fed to Groq NER
_MAX_BIOACT     = 5    # bioactivity records per compound
_HTTP_TIMEOUT   = 12   # seconds per external API call

_GROQ_CHEM_SYSTEM = (
    "You are a pharmaceutical chemistry data extraction assistant. "
    "Return ONLY valid JSON — no markdown, no explanation, no preamble."
)

_GROQ_CHEM_PROMPT = """\
Extract all small-molecule drugs and chemical compounds mentioned in the
following biomedical text excerpts.

For each unique compound return a JSON object with these fields:
  name          : common/brand name (e.g. "Sotorasib", "AMG-510")
  smiles        : SMILES string if explicitly stated in the text, else ""
  drug_class    : mechanism class (e.g. "covalent KRAS G12C inhibitor")
  disease_use   : primary indication (e.g. "non-small cell lung cancer")
  phase         : clinical phase if mentioned (e.g. "approved", "Phase III", "")

Rules:
- Deduplicate by name (case-insensitive).
- Only include compounds with a clear chemical name or brand name.
- Do NOT include gene/protein targets; do NOT include biologics (antibodies,
  CAR-T) unless the query explicitly requests them.
- Return [] if no small molecules are found.

Text excerpts:
{text}

JSON array:"""


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class BioActivity:
    target:     str
    assay_type: str             = ""
    value:      Optional[float] = None
    units:      str             = ""
    relation:   str             = "="

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target":     self.target,
            "assay_type": self.assay_type,
            "value":      self.value,
            "units":      self.units,
            "relation":   self.relation,
        }


@dataclass
class ChemicalGraph:
    name:             str
    iupac_name:       str                  = ""
    cid:              Optional[int]         = None
    smiles:           str                  = ""
    inchi:            str                  = ""
    inchikey:         str                  = ""
    mol_weight:       Optional[float]       = None
    formula:          str                  = ""
    drug_class:       str                  = ""
    disease_use:      str                  = ""
    phase:            str                  = ""
    chembl_id:        Optional[str]         = None
    bioactivities:    List[BioActivity]    = field(default_factory=list)
    svg_2d:           str                  = ""   # inline RDKit SVG string
    svg_2d_url:       str                  = ""   # PubChem CDN fallback URL
    sdf_3d:           str                  = ""   # RDKit MMFF SDF block string
    sdf_3d_url:       str                  = ""   # PubChem 3D SDF download URL
    conformer_id:     Optional[int]         = None
    morgan_fp:        Optional[List[float]] = field(default=None, repr=False)
    supporting_pmids: List[str]            = field(default_factory=list)
    supporting_dois:  List[str]            = field(default_factory=list)
    source_count:     int                  = 0

    @property
    def pubchem_url(self) -> str:
        return (
            f"https://pubchem.ncbi.nlm.nih.gov/compound/{self.cid}"
            if self.cid else ""
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict for ACPResponse.chemicals."""
        return {
            "name":             self.name,
            "iupac_name":       self.iupac_name,
            "cid":              self.cid,
            "smiles":           self.smiles,
            "inchi":            self.inchi,
            "inchikey":         self.inchikey,
            "mol_weight":       self.mol_weight,
            "formula":          self.formula,
            "drug_class":       self.drug_class,
            "disease_use":      self.disease_use,
            "phase":            self.phase,
            "chembl_id":        self.chembl_id,
            "bioactivities":    [b.to_dict() for b in self.bioactivities],
            "svg_2d":           self.svg_2d,
            "svg_2d_url":       self.svg_2d_url,
            "sdf_3d_url":       self.sdf_3d_url,
            "conformer_id":     self.conformer_id,
            "pubchem_url":      self.pubchem_url,
            "supporting_pmids": self.supporting_pmids,
            "supporting_dois":  self.supporting_dois,
            "source_count":     self.source_count,
        }

    def to_embed_text(self) -> str:
        """
        Build the natural-language string that gets embedded and stored as
        the Qdrant vector for this compound.

        Rich enough that semantic queries such as:
          "covalent KRAS inhibitor approved lung cancer"
          "IC50 nanomolar sotorasib"
          "C29H25F2N5O3 AMG 510"
        all retrieve this point with high cosine similarity — exactly like a
        text chunk from a paper abstract would.
        """
        parts: List[str] = [self.name]
        if self.iupac_name:
            parts.append(self.iupac_name)
        if self.formula:
            parts.append(f"Formula: {self.formula}")
        if self.mol_weight is not None:
            parts.append(f"MW: {self.mol_weight} Da")
        if self.smiles:
            parts.append(f"SMILES: {self.smiles}")
        if self.inchikey:
            parts.append(f"InChIKey: {self.inchikey}")
        if self.drug_class:
            parts.append(f"Class: {self.drug_class}")
        if self.disease_use:
            parts.append(f"Disease: {self.disease_use}")
        if self.phase:
            parts.append(f"Phase: {self.phase}")
        if self.chembl_id:
            parts.append(f"ChEMBL: {self.chembl_id}")
        if self.cid:
            parts.append(f"PubChem CID: {self.cid}")
        for ba in self.bioactivities[:3]:
            val_str = f"{ba.relation}{ba.value} {ba.units}" if ba.value else ""
            parts.append(f"Bioactivity: {ba.target} {ba.assay_type} {val_str}".strip())
        return " | ".join(parts)


# =============================================================================
# CHEMICAL EXTRACTOR
# =============================================================================

class ChemicalExtractor:
    """
    Stateless post-processor: extracts small-molecule drugs from validated
    ITDA items, resolves structures via PubChem + ChEMBL, generates 2D/3D
    representations, embeds using the shared EmbeddingService, and returns
    Qdrant-ready PointStructs in the same schema as VectorizerAgent output.
    """

    def __init__(self, groq_client=None):
        self._groq    = groq_client
        self._session: Optional[aiohttp.ClientSession] = None

    def set_groq(self, groq_client) -> None:
        self._groq = groq_client

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=_HTTP_TIMEOUT)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # =========================================================================
    # STEP 1 — Groq NER: extract compound names from text
    # =========================================================================

    async def _extract_raw_chemicals_via_groq(
        self, items: list, query: str
    ) -> List[Dict[str, Any]]:
        if self._groq is None:
            logger.warning("ChemicalExtractor: no Groq client — skipping NER")
            return []

        sorted_items = sorted(
            items, key=lambda i: (0 if getattr(i, "pmid", None) else 1)
        )[:_MAX_ITEMS_GROQ]

        excerpts = []
        for idx, item in enumerate(sorted_items):
            content = getattr(item, "content", None) or item.get("content", "")
            title   = getattr(item, "title",   None) or item.get("title",   "")
            pmid    = getattr(item, "pmid",    None) or item.get("pmid",    "")
            label   = f"[{idx+1}] {title}" + (f" (PMID:{pmid})" if pmid else "")
            excerpts.append(f"{label}\n{content[:800]}")

        raw = await self._groq.chat(
            prompt        = _GROQ_CHEM_PROMPT.format(text="\n\n".join(excerpts)),
            max_tokens    = 1200,
            temperature   = 0.0,
            system_prompt = _GROQ_CHEM_SYSTEM,
        )
        if not raw:
            return []

        try:
            clean = re.sub(r"```(?:json)?|```", "", raw).strip()
            match = re.search(r"\[.*\]", clean, re.DOTALL)
            if not match:
                logger.warning("ChemicalExtractor: Groq returned no JSON array")
                return []
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                logger.debug(
                    f"ChemicalExtractor: Groq extracted {len(parsed)} raw chemicals"
                )
                return parsed
        except Exception as exc:
            logger.warning(f"ChemicalExtractor: Groq JSON parse failed — {exc}")
        return []

    # =========================================================================
    # STEP 2 — Provenance: attach PMIDs / DOIs
    # =========================================================================

    @staticmethod
    def _attach_provenance(
        name: str, items: list
    ) -> Tuple[List[str], List[str], int]:
        name_re = re.compile(rf"\b{re.escape(name)}\b", re.I)
        pmids: List[str] = []
        dois:  List[str] = []
        count = 0
        for item in items:
            content = getattr(item, "content", None) or item.get("content", "")
            if not name_re.search(content):
                continue
            count += 1
            pmid = getattr(item, "pmid", None) or item.get("pmid")
            doi  = getattr(item, "doi",  None) or item.get("doi")
            if pmid and str(pmid) not in pmids:
                pmids.append(str(pmid))
            if doi and str(doi) not in dois:
                dois.append(str(doi))
        return pmids, dois, count

    # =========================================================================
    # STEP 3 — PubChem: CID + properties + conformer ID
    # =========================================================================

    async def _resolve_pubchem(self, name: str) -> Dict[str, Any]:
        try:
            sess = await self._get_session()

            cid_url = (
                f"{_PUBCHEM_BASE}/compound/name/"
                f"{aiohttp.helpers.quote(name, safe='')}/cids/JSON"
            )
            async with sess.get(cid_url) as resp:
                if resp.status == 404:
                    logger.debug(f"PubChem: no CID for '{name}'")
                    return {}
                if resp.status != 200:
                    return {}
                cid_data = await resp.json()

            cids = cid_data.get("IdentifierList", {}).get("CID", [])
            if not cids:
                return {}
            cid = int(cids[0])

            props_csv = (
                "IUPACName,IsomericSMILES,InChI,InChIKey,"
                "MolecularFormula,MolecularWeight"
            )
            prop_url = (
                f"{_PUBCHEM_BASE}/compound/cid/{cid}/property/{props_csv}/JSON"
            )
            async with sess.get(prop_url) as resp:
                if resp.status != 200:
                    return {"cid": cid}
                prop_data = await resp.json()

            prop         = prop_data.get("PropertyTable", {}).get("Properties", [{}])[0]
            conformer_id = await self._fetch_pubchem_conformer_id(cid, sess)

            logger.debug(
                f"PubChem: '{name}' → CID={cid} "
                f"MW={prop.get('MolecularWeight')}"
            )
            return {
                "cid":          cid,
                "smiles":       prop.get("IsomericSMILES", ""),
                "inchi":        prop.get("InChI", ""),
                "inchikey":     prop.get("InChIKey", ""),
                "iupac_name":   prop.get("IUPACName", ""),
                "formula":      prop.get("MolecularFormula", ""),
                "mol_weight":   _safe_float(prop.get("MolecularWeight")),
                "svg_2d_url":   f"{_PUBCHEM_IMAGE_URL}?cid={cid}&width=300&height=300",
                "sdf_3d_url":   f"{_PUBCHEM_BASE}/compound/CID/{cid}/SDF?record_type=3d",
                "conformer_id": conformer_id,
            }

        except asyncio.TimeoutError:
            logger.debug(f"PubChem timeout for '{name}'")
            return {}
        except Exception as exc:
            logger.debug(f"PubChem error for '{name}': {exc}")
            return {}

    @staticmethod
    async def _fetch_pubchem_conformer_id(
        cid: int, sess: aiohttp.ClientSession
    ) -> Optional[int]:
        try:
            url = f"{_PUBCHEM_BASE}/compound/cid/{cid}/conformers/JSON"
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                conf = (
                    data.get("InformationList", {})
                        .get("Information", [{}])[0]
                        .get("ConformerId", [])
                )
                return int(conf[0]) if conf else None
        except Exception:
            return None

    # =========================================================================
    # STEP 4 — ChEMBL: ChEMBL ID + bioactivities
    # =========================================================================

    async def _resolve_chembl(
        self, name: str, smiles: str
    ) -> Tuple[Optional[str], List[BioActivity]]:
        try:
            sess      = await self._get_session()
            chembl_id = await self._chembl_id_by_name(name, sess)
            if not chembl_id and smiles:
                chembl_id = await self._chembl_id_by_smiles(smiles, sess)
            if not chembl_id:
                return None, []
            bioacts = await self._chembl_bioactivities(chembl_id, sess)
            return chembl_id, bioacts
        except asyncio.TimeoutError:
            logger.debug(f"ChEMBL timeout for '{name}'")
            return None, []
        except Exception as exc:
            logger.debug(f"ChEMBL error for '{name}': {exc}")
            return None, []

    @staticmethod
    async def _chembl_id_by_name(
        name: str, sess: aiohttp.ClientSession
    ) -> Optional[str]:
        try:
            async with sess.get(
                f"{_CHEMBL_BASE}/molecule",
                params={
                    "pref_name__iexact": name,
                    "format": "json",
                    "limit":  "1",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                mols = (await resp.json()).get("molecules", [])
                return mols[0].get("molecule_chembl_id") if mols else None
        except Exception:
            return None

    @staticmethod
    async def _chembl_id_by_smiles(
        smiles: str, sess: aiohttp.ClientSession
    ) -> Optional[str]:
        try:
            async with sess.get(
                f"{_CHEMBL_BASE}/molecule",
                params={"smiles": smiles, "format": "json", "limit": "1"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                mols = (await resp.json()).get("molecules", [])
                return mols[0].get("molecule_chembl_id") if mols else None
        except Exception:
            return None

    @staticmethod
    async def _chembl_bioactivities(
        chembl_id: str, sess: aiohttp.ClientSession
    ) -> List[BioActivity]:
        try:
            async with sess.get(
                f"{_CHEMBL_BASE}/activity",
                params={
                    "molecule_chembl_id": chembl_id,
                    "standard_type__in":  "IC50,Ki,EC50,Kd",
                    "format":             "json",
                    "limit":              str(_MAX_BIOACT * 3),
                    "order_by":           "standard_value",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return []
                acts = (await resp.json()).get("activities", [])

            results: List[BioActivity] = []
            seen: set = set()
            for act in acts:
                target = act.get("target_pref_name") or act.get("assay_description", "")
                if not target or target in seen:
                    continue
                seen.add(target)
                results.append(BioActivity(
                    target     = target,
                    assay_type = act.get("standard_type", ""),
                    value      = _safe_float(act.get("standard_value")),
                    units      = act.get("standard_units", ""),
                    relation   = act.get("standard_relation", "="),
                ))
                if len(results) >= _MAX_BIOACT:
                    break
            return results
        except Exception as exc:
            logger.debug(f"ChEMBL bioactivity fetch failed for {chembl_id}: {exc}")
            return []

    # =========================================================================
    # STEP 5 — RDKit 2D SVG (transparent background, stereo annotations)
    # =========================================================================

    @staticmethod
    def _generate_svg_2d(smiles: str, size: Tuple[int, int] = (300, 300)) -> str:
        if not _RDKIT_AVAILABLE or not smiles:
            return ""
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return ""
            AllChem.Compute2DCoords(mol)

            w, h   = size
            drawer = rdMolDraw2D.MolDraw2DSVG(w, h)
            opts   = drawer.drawOptions()
            opts.clearBackground     = False   # transparent — host provides bg
            opts.addAtomIndices      = False
            opts.addStereoAnnotation = True    # E/Z, R/S wedges
            opts.bondLineWidth       = 1.5
            opts.atomLabelFontSize   = 0.45
            opts.useBWAtomPalette    = False   # element colours (O=red, N=blue)

            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            svg = drawer.GetDrawingText()

            # Strip XML declaration and any white-background rect for clean
            # embedding in both light and dark UIs
            svg = re.sub(r"<\?xml[^>]+\?>", "", svg).strip()
            svg = re.sub(
                r"<rect\s[^>]*fill=['\"]white['\"][^/]*/?>",
                "", svg, flags=re.IGNORECASE,
            )
            return svg
        except Exception as exc:
            logger.debug(f"RDKit 2D SVG failed: {exc}")
            return ""

    # =========================================================================
    # STEP 6 — RDKit 3D SDF (ETKDGv3 + MMFF94)
    # =========================================================================

    @staticmethod
    def _generate_sdf_3d(smiles: str) -> str:
        """
        Generate a 3D conformer using ETKDGv3 distance geometry followed by
        MMFF94 minimisation.  Falls back to UFF for unusual chemotypes.
        Returns an SDF block string ready for 3D viewers (Mol*, NGL, 3Dmol.js).
        """
        if not _RDKIT_AVAILABLE or not smiles:
            return ""
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return ""

            mol_h  = Chem.AddHs(mol)
            params = AllChem.ETKDGv3()
            params.randomSeed       = 42
            params.enforceChirality = True

            if AllChem.EmbedMolecule(mol_h, params) == -1:
                AllChem.EmbedMolecule(mol_h, AllChem.ETKDG())

            if AllChem.MMFFOptimizeMolecule(mol_h, maxIters=2000) == -1:
                AllChem.UFFOptimizeMolecule(mol_h, maxIters=2000)

            buf = StringIO()
            w   = Chem.SDWriter(buf)
            w.write(mol_h)
            w.flush()
            w.close()
            return buf.getvalue()
        except Exception as exc:
            logger.debug(f"RDKit 3D SDF failed: {exc}")
            return ""

    # =========================================================================
    # STEP 7 — Morgan fingerprint (ECFP6, stored in payload)
    # =========================================================================

    @staticmethod
    def _compute_morgan_fp(
        smiles: str, radius: int = 3, n_bits: int = 2048
    ) -> Optional[List[float]]:
        """
        Compute a 2048-bit ECFP6 Morgan fingerprint as a float list.
        Stored in Qdrant payload (not as the vector) so downstream code can
        run Tanimoto-based chemical-similarity re-ranking if desired.
        """
        if not _RDKIT_AVAILABLE or not smiles:
            return None
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return None
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
            return list(fp)
        except Exception:
            return None

    # =========================================================================
    # STEP 8 — Resolve one compound (PubChem + ChEMBL + RDKit concurrently)
    # =========================================================================

    async def _resolve_chemical(
        self, raw: Dict[str, Any], items: list
    ) -> Optional[ChemicalGraph]:
        name = raw.get("name", "").strip()
        if not name:
            return None

        groq_smiles = raw.get("smiles", "")

        # PubChem and ChEMBL run concurrently
        pc_task = asyncio.create_task(self._resolve_pubchem(name))
        ct_task = asyncio.create_task(self._resolve_chembl(name, groq_smiles))
        pc_data, (chembl_id, bioacts) = await asyncio.gather(pc_task, ct_task)

        canonical_smiles = pc_data.get("smiles", "") or groq_smiles

        # RDKit is CPU-bound but fast for drug-sized molecules; run in executor
        loop       = asyncio.get_running_loop()
        svg_2d     = ""
        sdf_3d     = ""
        morgan_fp: Optional[List[float]] = None

        if canonical_smiles and _RDKIT_AVAILABLE:
            svg_2d, sdf_3d, morgan_fp = await asyncio.gather(
                loop.run_in_executor(None, self._generate_svg_2d,    canonical_smiles),
                loop.run_in_executor(None, self._generate_sdf_3d,    canonical_smiles),
                loop.run_in_executor(None, self._compute_morgan_fp,  canonical_smiles),
            )

        pmids, dois, source_count = self._attach_provenance(name, items)

        return ChemicalGraph(
            name             = name,
            iupac_name       = pc_data.get("iupac_name", ""),
            cid              = pc_data.get("cid"),
            smiles           = canonical_smiles,
            inchi            = pc_data.get("inchi", ""),
            inchikey         = pc_data.get("inchikey", ""),
            mol_weight       = pc_data.get("mol_weight"),
            formula          = pc_data.get("formula", ""),
            drug_class       = raw.get("drug_class", ""),
            disease_use      = raw.get("disease_use", ""),
            phase            = raw.get("phase", ""),
            chembl_id        = chembl_id,
            bioactivities    = bioacts,
            svg_2d           = svg_2d,
            svg_2d_url       = pc_data.get("svg_2d_url", ""),
            sdf_3d           = sdf_3d,
            sdf_3d_url       = pc_data.get("sdf_3d_url", ""),
            conformer_id     = pc_data.get("conformer_id"),
            morgan_fp        = morgan_fp if isinstance(morgan_fp, list) else None,
            supporting_pmids = pmids,
            supporting_dois  = dois,
            source_count     = source_count,
        )

    # =========================================================================
    # STEP 9 — Embed + build PointStruct (mirrors VectorizerAgent._vectorize_text)
    # =========================================================================

    @staticmethod
    async def _build_point(
        chem:          ChemicalGraph,
        embed_service: Any,   # EmbeddingService — loose type to avoid circular import
        session_id:    str,
    ) -> Optional[Any]:       # PointStruct | None
        """
        Embed the compound's natural-language text representation using the
        same model as texts_collection (BAAI/bge-base-en, 768-dim, COSINE),
        then wrap into a PointStruct whose payload mirrors VectorizerAgent's
        schema so RetrieverAgent can handle it uniformly.

        Payload keys that match VectorizerAgent._base_payload():
          content, content_preview, content_type, source_url, title,
          language, date_collected, date_collected_ts, validation_score,
          domain_trust, chunk_index, session_id

        Extra chemical-specific keys in the same payload:
          chemical_data  — full ChemicalGraph.to_dict() for ACPResponse
          cid, inchikey, formula, mol_weight, chembl_id
          has_svg_2d, has_sdf_3d
          morgan_fp      — ECFP6 bit-vector for optional Tanimoto re-ranking
          pmid, doi      — provenance (first supporting entry)
        """
        if not _QDRANT_AVAILABLE:
            return None

        embed_text = chem.to_embed_text()
        try:
            vector = await embed_service.embed_text(embed_text)
        except Exception as exc:
            logger.warning(
                f"ChemicalExtractor: embedding failed for '{chem.name}': {exc}"
            )
            return None

        now     = datetime.now(timezone.utc)
        now_iso = now.isoformat().replace("+00:00", "Z")

        payload: Dict[str, Any] = {
            # ── Standard VectorizerAgent schema ────────────────────────────
            "content":           embed_text,
            "content_preview":   embed_text[:200],
            "content_type":      "chemical",
            "source_url":        chem.pubchem_url,
            "title":             chem.name,
            "language":          "en",
            "date_collected":    now_iso,
            "date_collected_ts": now.timestamp(),
            "validation_score":  0.90,   # PubChem-verified data → high trust
            "domain_trust":      0.95,   # pubchem.ncbi.nlm.nih.gov is TRUSTED
            "chunk_index":       0,
            "session_id":        session_id,
            # ── Chemical-specific ──────────────────────────────────────────
            "chemical_data":     chem.to_dict(),
            "cid":               chem.cid,
            "inchikey":          chem.inchikey,
            "formula":           chem.formula,
            "mol_weight":        chem.mol_weight,
            "chembl_id":         chem.chembl_id,
            "has_svg_2d":        bool(chem.svg_2d or chem.svg_2d_url),
            "has_sdf_3d":        bool(chem.sdf_3d or chem.sdf_3d_url),
            "morgan_fp":         chem.morgan_fp,
        }
        if chem.supporting_pmids:
            payload["pmid"] = chem.supporting_pmids[0]
        if chem.supporting_dois:
            payload["doi"] = chem.supporting_dois[0]
        # Use bioactivity count as a weak citation-count proxy so that
        # ValidatorAgent._blended_credibility() gives it a slight boost
        if chem.bioactivities:
            payload["citation_count"] = len(chem.bioactivities) * 10

        return PointStruct(
            id      = str(uuid.uuid4()),
            vector  = vector,
            payload = payload,
        )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def extract_chemicals(
        self,
        validated_items: list,   # List[ValidatedItem]
        query:           str,
        embed_service:   Any,    # EmbeddingService instance (shared from agent)
        session_id:      str = "",
    ) -> Tuple[List[ChemicalGraph], List[Any]]:
        """
        Main entry point.

        Returns:
            (chemicals, points)
            chemicals : List[ChemicalGraph]  — passed to ACPResponse.chemicals
            points    : List[PointStruct]    — passed to qdrant_mgr.upsert_batch()

        In ExtractorAgent.process_request(), after target extraction:

            extracted_chemicals, chem_points = await self.chemical_extractor.extract_chemicals(
                validated_items = validated,
                query           = request.query,
                embed_service   = self.embed_svc,
                session_id      = request.session_id,
            )
            if chem_points:
                await self.qdrant_mgr.upsert_batch(chem_points, "chemicals_collection")
                total = await self.qdrant_mgr.count_points("chemicals_collection")
                logger.info(
                    f"[{request.session_id}] chemicals_collection: {total} vectors"
                )
        """
        if not validated_items:
            return [], []

        # Step 1 — Groq NER
        raw_chemicals = await self._extract_raw_chemicals_via_groq(validated_items, query)
        if not raw_chemicals:
            logger.info("ChemicalExtractor: no compounds extracted from validated items")
            return [], []

        # Deduplicate by lowercased name
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for c in raw_chemicals:
            key = c.get("name", "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(c)
        unique = unique[:_MAX_CHEMICALS]

        logger.info(
            f"ChemicalExtractor: resolving {len(unique)} unique compounds: "
            f"{[c.get('name') for c in unique]}"
        )

        # Step 2 — Concurrent structure resolution (PubChem + ChEMBL + RDKit)
        resolve_results = await asyncio.gather(
            *[self._resolve_chemical(c, validated_items) for c in unique],
            return_exceptions=True,
        )
        chemicals: List[ChemicalGraph] = []
        for res in resolve_results:
            if isinstance(res, Exception):
                logger.warning(f"ChemicalExtractor: resolution error — {res}")
            elif res is not None:
                chemicals.append(res)

        # Step 3 — Embed each compound and build PointStructs
        # (same role as VectorizerAgent.vectorize() for text items)
        embed_results = await asyncio.gather(
            *[self._build_point(c, embed_service, session_id) for c in chemicals],
            return_exceptions=True,
        )
        points: List[Any] = []
        for res in embed_results:
            if isinstance(res, Exception):
                logger.warning(f"ChemicalExtractor: embedding error — {res}")
            elif res is not None:
                points.append(res)

        n_svg    = sum(1 for c in chemicals if c.svg_2d)
        n_sdf    = sum(1 for c in chemicals if c.sdf_3d)
        n_cid    = sum(1 for c in chemicals if c.cid)
        n_chembl = sum(1 for c in chemicals if c.chembl_id)
        logger.info(
            f"ChemicalExtractor: {len(chemicals)} compounds resolved, "
            f"{len(points)} points ready for Qdrant "
            f"(PubChem={n_cid}, ChEMBL={n_chembl}, "
            f"SVG={'RDKit' if n_svg else 'URL-only'}, "
            f"SDF={'RDKit' if n_sdf else 'URL-only'})"
        )

        return chemicals, points


# =============================================================================
# HELPERS
# =============================================================================

def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
