"""
bio_ner.py — BioNER (Biomedical Named Entity Recognition)

Hybrid NER engine that combines:
  1. Curated regex patterns for high-precision gene/protein/mutation/drug/disease
     extraction — zero runtime overhead, no model download required.
  2. Optional transformer-based NER via HuggingFace (d4data/biomedical-ner-all)
     loaded lazily only when HF_TOKEN is set and the model is available.

Exposes:
  BioNERResult       — typed dataclass for a single detected entity
  BioNERAnnotation   — document-level annotation (list of results + entity maps)
  BioNERService      — async singleton façade, used by ValidatorAgent and
                       TargetExtractor (and optionally ExtractorAgent for
                       query-time entity expansion)

Usage (inside any async context):
  from bio_ner import BioNERService
  ner = BioNERService()
  annotation = await ner.annotate(text)
  genes      = annotation.genes           # {"KRAS", "BRAF", …}
  mutations  = annotation.mutations       # {"G12C", "V600E", …}
  drugs      = annotation.drugs           # {"sotorasib", "vemurafenib", …}
  diseases   = annotation.diseases        # {"NSCLC", "melanoma", …}
  pathways   = annotation.pathways        # {"MAPK", "PI3K/AKT", …}
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class BioNERResult:
    text:        str
    entity_type: str          # GENE | PROTEIN | MUTATION | DRUG | DISEASE | PATHWAY | VARIANT
    start:       int  = -1
    end:         int  = -1
    source:      str  = "regex"   # "regex" | "transformer"
    confidence:  float = 1.0


@dataclass
class BioNERAnnotation:
    entities:  List[BioNERResult] = field(default_factory=list)

    # Convenience sets — populated by BioNERService.annotate()
    genes:     Set[str] = field(default_factory=set)
    proteins:  Set[str] = field(default_factory=set)
    mutations: Set[str] = field(default_factory=set)
    drugs:     Set[str] = field(default_factory=set)
    diseases:  Set[str] = field(default_factory=set)
    pathways:  Set[str] = field(default_factory=set)
    variants:  Set[str] = field(default_factory=set)

    def all_entity_texts(self) -> Set[str]:
        return {e.text for e in self.entities}

    def entity_map(self) -> Dict[str, List[str]]:
        """Returns {entity_type: [text, …]} for serialization."""
        out: Dict[str, List[str]] = {}
        for e in self.entities:
            out.setdefault(e.entity_type, [])
            if e.text not in out[e.entity_type]:
                out[e.entity_type].append(e.text)
        return out


# =============================================================================
# REGEX PATTERNS — compiled once at import time
# =============================================================================

# HGNC-style gene symbols: 1–6 uppercase letters, optionally followed by
# digits and a suffix like A, B, -AS1, etc.  Must be ≥2 chars to avoid noise.
_GENE_SYMBOL_RE = re.compile(
    r'\b(?:'
    # Explicit high-value oncogenes / tumour suppressors
    r'KRAS|NRAS|HRAS|BRAF|RAF1|ARAF|MAP2K1|MAP2K2|MAPK1|MAPK3|'
    r'EGFR|ERBB2|ERBB3|ERBB4|HER2|HER3|MET|ALK|RET|ROS1|NTRK1|NTRK2|NTRK3|'
    r'PIK3CA|PIK3CB|PIK3CD|PIK3CG|PTEN|AKT1|AKT2|AKT3|MTOR|TSC1|TSC2|'
    r'TP53|MDM2|MDM4|CDKN2A|CDKN2B|RB1|E2F1|CCND1|CDK4|CDK6|'
    r'BRCA1|BRCA2|PALB2|RAD51|ATM|ATR|CHEK1|CHEK2|'
    r'MYC|MYCN|MYCL|MAX|MXI1|'
    r'BCL2|BCL2L1|MCL1|BAX|BID|PUMA|NOXA|'
    r'VHL|HIF1A|HIF2A|EPAS1|'
    r'JAK1|JAK2|JAK3|TYK2|STAT1|STAT2|STAT3|STAT4|STAT5A|STAT5B|STAT6|'
    r'FLT3|KIT|PDGFRA|PDGFRB|CSF1R|ABL1|ABL2|BCR|'
    r'IDH1|IDH2|TET2|DNMT3A|EZH2|KDM6A|ARID1A|SMARCA4|SMARCB1|'
    r'MLH1|MSH2|MSH6|PMS2|EPCAM|'
    r'NOTCH1|NOTCH2|NOTCH3|NOTCH4|HES1|JAG1|DLL3|'
    r'WNT3A|WNT5A|CTNNB1|APC|AXIN1|AXIN2|GSK3B|'
    r'FGFR1|FGFR2|FGFR3|FGFR4|FGF2|FGF19|FGF23|'
    r'VEGFA|VEGFB|VEGFC|KDR|FLT1|NRP1|'
    r'AR|ESR1|PGR|NR3C1|RARA|'
    r'PD1|PDCD1|PDL1|CD274|CTLA4|LAG3|TIM3|TIGIT|'
    r'CD19|CD20|MS4A1|CD22|CD38|CD123|CD33|'
    r'TERT|TERC|DKC1|'
    r'NF1|NF2|TSC1|TSC2|'
    r'STK11|LKB1|AMPK|'
    r'RAC1|RHOA|RHOB|CDC42|'
    r'SRC|YES1|FYN|LCK|ZAP70|'
    r'MTOR|RPTOR|RICTOR|'
    # Generic HGNC-pattern fallback (2–6 uppercase + optional digit+suffix)
    r'[A-Z][A-Z0-9]{1,5}(?:[A-Z]|\d+[A-Z]?)?\b'
    r')',
    re.VERBOSE,
)

# Protein mutation notation: e.g. G12C, V600E, R175H, del19, exon19del
_MUTATION_RE = re.compile(
    r'\b(?:'
    r'[A-Z]\d{1,4}[A-Z*]'            # SNV: G12C, V600E
    r'|[A-Z]\d{1,4}(?:del|ins|dup)'  # indel: G12del
    r'|del(?:etion)?[-_\s]?\d+'       # deletion exon
    r'|ins(?:ertion)?[-_\s]?\d+'
    r'|exon[-_\s]?\d+\s*(?:del|ins|skip|mut)'
    r'|c\.\d+[+\-]?\d*[ACGT]>[ACGT]' # HGVS cDNA
    r'|p\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}'  # HGVS protein
    r'|fs\*?\d*'                       # frameshift
    r'|\bWT\b'                         # wild-type
    r')',
)

# Drug / small molecule / therapeutic names
_DRUG_RE = re.compile(
    r'\b(?:'
    r'sotorasib|adagrasib|osimertinib|erlotinib|gefitinib|afatinib|dacomitinib|'
    r'vemurafenib|dabrafenib|encorafenib|cobimetinib|trametinib|binimetinib|'
    r'imatinib|nilotinib|dasatinib|ponatinib|bosutinib|asciminib|'
    r'ibrutinib|acalabrutinib|zanubrutinib|'
    r'palbociclib|ribociclib|abemaciclib|'
    r'olaparib|niraparib|rucaparib|talazoparib|veliparib|'
    r'everolimus|temsirolimus|rapamycin|sirolimus|'
    r'pembrolizumab|nivolumab|atezolizumab|durvalumab|avelumab|cemiplimab|'
    r'ipilimumab|tremelimumab|relatlimab|'
    r'trastuzumab|pertuzumab|ado-trastuzumab|fam-trastuzumab|'
    r'bevacizumab|ramucirumab|ziv-aflibercept|'
    r'cetuximab|panitumumab|amivantamab|'
    r'crizotinib|alectinib|brigatinib|lorlatinib|ceritinib|'
    r'selpercatinib|pralsetinib|'
    r'larotrectinib|entrectinib|'
    r'venetoclax|navitoclax|'
    r'idelalisib|copanlisib|alpelisib|umbralisib|duvelisib|'
    r'vorinostat|romidepsin|panobinostat|belinostat|entinostat|'
    r'azacitidine|decitabine|guadecitabine|'
    r'bortezomib|carfilzomib|ixazomib|marizomib|'
    r'lenalidomide|thalidomide|pomalidomide|'
    r'selinexor|eltanexor|'
    r'AMG[-\s]?510|MRTX[-\s]?849|LY3499446|RMC[-\s]?4630|BI[-\s]?1701963|'
    r'[a-z]+(?:inib|umab|zumab|ximab|lizumab|lib|nib|mab|stat|tide)\b'
    r')',
    re.IGNORECASE,
)

# Disease / cancer-type names
_DISEASE_RE = re.compile(
    r'\b(?:'
    r'(?:non[-\s]?small[-\s]?cell\s+)?lung\s+(?:cancer|carcinoma|adenocarcinoma)|'
    r'NSCLC|SCLC|'
    r'(?:colorectal|colon|rectal)\s+(?:cancer|carcinoma)|CRC|'
    r'(?:pancreatic)\s+(?:cancer|ductal\s+adenocarcinoma)|PDAC|'
    r'(?:breast)\s+(?:cancer|carcinoma)|TNBC|HER2\+|'
    r'(?:hepatocellular)\s+carcinoma|HCC|'
    r'(?:ovarian)\s+(?:cancer|carcinoma)|'
    r'(?:prostate)\s+cancer|CRPC|CSPC|mCRPC|'
    r'(?:renal\s+cell|clear\s+cell|papillary)\s+carcinoma|RCC|'
    r'melanoma|cutaneous\s+melanoma|uveal\s+melanoma|'
    r'glioblastoma|GBM|glioma|astrocytoma|medulloblastoma|'
    r'(?:acute\s+myeloid|chronic\s+myeloid|acute\s+lymphoblastic|chronic\s+lymphocytic)\s+'
    r'(?:leukemia|leukaemia)|AML|CML|ALL|CLL|'
    r'(?:diffuse\s+large\s+B[-\s]?cell|follicular|mantle\s+cell|marginal\s+zone)\s+lymphoma|'
    r'DLBCL|NHL|HL|Hodgkin|'
    r'multiple\s+myeloma|MM|MGUS|'
    r'(?:thyroid|medullary\s+thyroid)\s+(?:cancer|carcinoma)|MTC|PTC|'
    r'(?:gastric|stomach)\s+(?:cancer|carcinoma|adenocarcinoma)|'
    r'(?:bladder|urothelial)\s+(?:cancer|carcinoma)|'
    r'(?:head\s+and\s+neck\s+squamous|HNSCC)|'
    r'(?:endometrial|uterine)\s+(?:cancer|carcinoma)|'
    r'(?:cervical)\s+cancer|'
    r'cholangiocarcinoma|'
    r'mesothelioma|'
    r'neuroblastoma|rhabdomyosarcoma|Ewing\s+sarcoma|osteosarcoma|'
    r'(?:myelodysplastic)\s+syndrome|MDS|'
    r'tumor|tumour|neoplasm|malignancy|metastasis|metastatic\s+\w+\s+cancer'
    r')',
    re.IGNORECASE,
)

# Signalling pathway names
_PATHWAY_RE = re.compile(
    r'\b(?:'
    r'(?:RAS[-/]?)?MAPK|ERK|MEK|RAF[-/]MEK[-/]ERK|'
    r'PI3K[-/]?(?:AKT|PKB)(?:[-/]?mTOR)?|'
    r'mTOR(?:C[12])?|'
    r'JAK[-/]?STAT\d?|'
    r'NF[-\s]?κB|NF[-\s]?kB|NFkB|'
    r'WNT(?:[-/]?β[-\s]?catenin)?|'
    r'Notch(?:[-/]?HES\d?)?|'
    r'Hedgehog|HH(?:[-/]?SMO)?|SHH|'
    r'TGF[-\s]?β|SMAD|BMP[-/]?SMAD|'
    r'HIPPO[-/]?YAP(?:[-/]?TAZ)?|YAP[-/]?TAZ|'
    r'p53(?:[-/]?MDM2)?|'
    r'VEGF(?:[-/]?VEGFR\d?)?|Angiogenesis|'
    r'FGFR[-/]?FGF|'
    r'EGFR(?:[-/]?HER2)?|ErbB|'
    r'ALK[-/]?ROS1|'
    r'CDK4[-/]?6[-/]?RB1?|cell\s*cycle|'
    r'DNA[-\s]?(?:damage|repair|DDR)|homologous\s+recombination|HR|NHEJ|BER|'
    r'PARP(?:[-/]?BRCAness)?|'
    r'Apoptosis|intrinsic[-/]?apoptosis|extrinsic[-/]?apoptosis|'
    r'Autophagy|'
    r'Metabolic\s+reprogramming|Warburg\s+effect|glycolysis|'
    r'Immune\s+(?:evasion|checkpoint|escape)|PD[-\s]?1[-/]?PDL[-\s]?1|'
    r'CAR[-\s]?T|TCR|BCR|'
    r'Ferroptosis|Necroptosis|Pyroptosis|'
    r'Epithelial[-\s]?mesenchymal\s+transition|EMT'
    r')',
    re.IGNORECASE,
)

# Known gene-alias / abbreviation normalisation table
_GENE_ALIASES: Dict[str, str] = {
    "HER2": "ERBB2", "HER3": "ERBB3", "HER4": "ERBB4",
    "PD1":  "PDCD1", "PDL1": "CD274",
    "LKB1": "STK11",
    "p53":  "TP53",  "p21": "CDKN1A", "p16": "CDKN2A",
    "Rb":   "RB1",
    "AKT":  "AKT1",
}


# =============================================================================
# BioNER SERVICE
# =============================================================================

class BioNERService:
    """
    Async façade for biomedical NER.

    Regex extraction is always available (zero dependencies).
    Transformer extraction (d4data/biomedical-ner-all) is loaded lazily
    when `use_transformer=True` is passed to annotate() — requires
    `transformers` and a suitable device.
    """

    def __init__(self):
        self._pipeline = None        # HF NER pipeline (lazy)
        self._lock     = asyncio.Lock()

    # ── Lazy transformer loader ───────────────────────────────────────────────

    async def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        async with self._lock:
            if self._pipeline is not None:
                return self._pipeline
            loop = asyncio.get_running_loop()
            self._pipeline = await loop.run_in_executor(None, self._load_pipeline)
        return self._pipeline

    @staticmethod
    def _load_pipeline():
        try:
            from transformers import pipeline as hf_pipeline
            pipe = hf_pipeline(
                "token-classification",
                model="d4data/biomedical-ner-all",
                aggregation_strategy="simple",
            )
            logger.info("BioNER transformer pipeline loaded (d4data/biomedical-ner-all)")
            return pipe
        except Exception as exc:
            logger.warning(
                f"BioNER transformer unavailable ({exc}) — "
                "falling back to regex-only NER"
            )
            return None

    # ── Regex extraction ──────────────────────────────────────────────────────

    @staticmethod
    def _regex_extract(text: str) -> List[BioNERResult]:
        results: List[BioNERResult] = []

        for m in _GENE_SYMBOL_RE.finditer(text):
            token = m.group()
            # Skip single-char and very common English words that match pattern
            if len(token) < 2 or token.lower() in {
                "a", "an", "as", "at", "be", "by", "do", "go", "he", "hi",
                "if", "in", "is", "it", "me", "my", "no", "of", "ok", "on",
                "or", "so", "to", "up", "us", "we", "ok", "id", "ip",
            }:
                continue
            canonical = _GENE_ALIASES.get(token, token)
            results.append(BioNERResult(
                text=canonical, entity_type="GENE",
                start=m.start(), end=m.end(),
            ))

        for m in _MUTATION_RE.finditer(text):
            results.append(BioNERResult(
                text=m.group(), entity_type="MUTATION",
                start=m.start(), end=m.end(),
            ))

        for m in _DRUG_RE.finditer(text):
            results.append(BioNERResult(
                text=m.group().lower(), entity_type="DRUG",
                start=m.start(), end=m.end(),
            ))

        for m in _DISEASE_RE.finditer(text):
            results.append(BioNERResult(
                text=m.group(), entity_type="DISEASE",
                start=m.start(), end=m.end(),
            ))

        for m in _PATHWAY_RE.finditer(text):
            results.append(BioNERResult(
                text=m.group(), entity_type="PATHWAY",
                start=m.start(), end=m.end(),
            ))

        return results

    # ── Transformer extraction ────────────────────────────────────────────────

    @staticmethod
    def _hf_label_to_type(label: str) -> Optional[str]:
        label_upper = label.upper()
        mapping = {
            "GENE":          "GENE",
            "PROTEIN":       "PROTEIN",
            "DISEASE":       "DISEASE",
            "CHEMICAL":      "DRUG",
            "DRUG":          "DRUG",
            "SPECIES":       None,
            "CELL_TYPE":     None,
            "CELL_LINE":     None,
            "DNA":           "GENE",
            "RNA":           "GENE",
            "MUTATION":      "MUTATION",
            "VARIANT":       "MUTATION",
        }
        for key, etype in mapping.items():
            if key in label_upper:
                return etype
        return None

    async def _transformer_extract(self, text: str) -> List[BioNERResult]:
        try:
            pipe = await self._get_pipeline()
            if pipe is None:
                return []
            loop = asyncio.get_running_loop()
            # Truncate to 512 tokens-worth of characters to stay within model limits
            raw = await loop.run_in_executor(None, pipe, text[:2000])
            results: List[BioNERResult] = []
            for ent in (raw or []):
                etype = self._hf_label_to_type(ent.get("entity_group", ""))
                if etype is None:
                    continue
                token = ent.get("word", "").strip()
                if not token:
                    continue
                results.append(BioNERResult(
                    text=token, entity_type=etype,
                    start=ent.get("start", -1), end=ent.get("end", -1),
                    source="transformer",
                    confidence=float(ent.get("score", 1.0)),
                ))
            return results
        except Exception as exc:
            logger.debug(f"BioNER transformer extraction error: {exc}")
            return []

    # ── Merge & deduplicate ───────────────────────────────────────────────────

    @staticmethod
    def _merge(
        regex_hits: List[BioNERResult],
        tf_hits:    List[BioNERResult],
    ) -> List[BioNERResult]:
        """
        Merge transformer and regex hits, preferring transformer for
        overlapping spans.  Deduplicate by (text.lower, entity_type).
        """
        seen: Set[Tuple[str, str]] = set()
        merged: List[BioNERResult] = []

        # Transformer hits first (higher quality when available)
        for ent in tf_hits:
            key = (ent.text.lower(), ent.entity_type)
            if key not in seen:
                seen.add(key)
                merged.append(ent)

        # Fill from regex for any entities the transformer missed
        for ent in regex_hits:
            key = (ent.text.lower(), ent.entity_type)
            if key not in seen:
                seen.add(key)
                merged.append(ent)

        return merged

    # ── Public API ─────────────────────────────────────────────────────────────

    async def annotate(
        self,
        text:            str,
        use_transformer: bool = False,
    ) -> BioNERAnnotation:
        """
        Annotate a biomedical text.

        Args:
            text:            The text to annotate.
            use_transformer: If True, additionally runs the HF NER pipeline
                             (loaded lazily).  Default False for speed.

        Returns:
            BioNERAnnotation with entities list and convenience sets.
        """
        if not text or not text.strip():
            return BioNERAnnotation()

        regex_hits = self._regex_extract(text)

        tf_hits: List[BioNERResult] = []
        if use_transformer:
            tf_hits = await self._transformer_extract(text)

        entities = self._merge(regex_hits, tf_hits)

        annotation = BioNERAnnotation(entities=entities)
        for ent in entities:
            et = ent.entity_type
            if et == "GENE":
                annotation.genes.add(ent.text)
            elif et == "PROTEIN":
                annotation.proteins.add(ent.text)
            elif et == "MUTATION":
                annotation.mutations.add(ent.text)
            elif et == "DRUG":
                annotation.drugs.add(ent.text)
            elif et == "DISEASE":
                annotation.diseases.add(ent.text)
            elif et == "PATHWAY":
                annotation.pathways.add(ent.text)
            elif et == "VARIANT":
                annotation.variants.add(ent.text)

        logger.debug(
            f"BioNER: {len(entities)} entities — "
            f"genes={len(annotation.genes)} mutations={len(annotation.mutations)} "
            f"drugs={len(annotation.drugs)} diseases={len(annotation.diseases)} "
            f"pathways={len(annotation.pathways)}"
        )
        return annotation

    async def annotate_batch(
        self,
        texts:           List[str],
        use_transformer: bool = False,
    ) -> List[BioNERAnnotation]:
        """Annotate a list of texts concurrently."""
        tasks = [self.annotate(t, use_transformer=use_transformer) for t in texts]
        return await asyncio.gather(*tasks)

    def extract_query_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Fast synchronous extraction for query-time entity expansion.
        Returns a plain dict for use in filter building and logging.
        """
        hits = self._regex_extract(query)
        result: Dict[str, List[str]] = {}
        seen: Set[str] = set()
        for h in hits:
            key = h.text.lower()
            if key not in seen:
                seen.add(key)
                result.setdefault(h.entity_type, []).append(h.text)
        return result
