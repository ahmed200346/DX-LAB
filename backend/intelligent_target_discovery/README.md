# 🧬 Intelligent Target Discovery Agent

**v3.4** · Autonomous biomedical literature mining, multimodal RAG, and structural drug-target resolution

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Async](https://img.shields.io/badge/async-asyncio-green.svg)](https://docs.python.org/3/library/asyncio.html)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Qdrant](https://img.shields.io/badge/vector--db-Qdrant-red.svg)](https://qdrant.tech/)

---

## Overview

The **Intelligent Target Discovery Agent (ITDA)** is a production-grade, fully asynchronous AI agent that mines scientific literature for drug targets, validates the retrieved evidence, and resolves each candidate to its structural biology data—UniProt accession, experimental PDB structures, and AlphaFold predictions—all in a single pipeline call.

It exposes a clean **Agent Communication Protocol (ACP)** interface so it can slot into any multi-agent system as a drop-in discovery module.

```
query ──► WebSearchAgent ──► ValidatorAgent ──► VectorizerAgent ──► Qdrant
                                                       │
                                                 TargetExtractor
                                                       │
                                  UniProt · RCSB PDB · AlphaFold EBI
                                                       │
                                               ACPResponse (targets + payload)
```

---

## Key Features

| Capability | Detail |
|---|---|
| **Multimodal retrieval** | Indexes and retrieves text, PDFs, images, tables, graphs, video transcripts, and code |
| **Hybrid search** | Dense (HNSW) + sparse (BM25/TF-IDF) → RRF fusion → cross-encoder reranking → MMR diversity |
| **HyDE augmentation** | Groq-powered hypothetical document embedding for improved cold-start recall |
| **Structural resolution** | Per-target UniProt → PDB → AlphaFold lookups, all concurrent |
| **Validated evidence** | Six-metric Semantic Grounding Value (SGV) gates every result before storage |
| **Smart query decomposition** | Groq automatically breaks long queries into focused sub-queries |
| **Circuit breakers** | All external services (SearXNG, Jina, etc.) are guarded against cascading failures |
| **Redis caching** | Query-level and cross-encoder score caches to eliminate redundant API calls |
| **ACP protocol** | Structured request/response schema for seamless multi-agent orchestration |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                IntelligentTargetDiscoveryAgent v3.4             │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────────┐  │
│  │  ACPRequest  │──►│ ExtractorAgent│──►│    ACPResponse    │  │
│  └──────────────┘   └──────┬───────┘   └───────────────────┘  │
│                             │                                   │
│         ┌───────────────────┼──────────────────────┐           │
│         ▼                   ▼                      ▼           │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────┐    │
│  │  CacheLayer │  │  RetrieverAgent  │  │ WebSearchAgent │    │
│  │   (Redis)   │  │  (Qdrant+BM25+  │  │(SearXNG/DDG/   │    │
│  └─────────────┘  │  CE+MMR+RRF)    │  │PubMed/Scholar) │    │
│                   └──────────────────┘  └────────┬───────┘    │
│                                                   │            │
│                                         ┌─────────▼────────┐  │
│                                         │  ValidatorAgent  │  │
│                                         │ (SGV gating·NLI· │  │
│                                         │  dedup·Groq)     │  │
│                                         └─────────┬────────┘  │
│                                                   │            │
│                   ┌───────────────────────────────▼──────────┐ │
│                   │           TargetExtractor                 │ │
│                   │  Groq NER → UniProt → PDB → AlphaFold   │ │
│                   └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Components

**`WebSearchAgent`** — Parallel queries across SearXNG, DuckDuckGo, Semantic Scholar, PubMed (efetch XML), Europe PMC, and ClinicalTrials.gov. Content is extracted via a concurrent Jina/trafilatura race. Biomedical domain filtering and pre-filters drop irrelevant URLs before any embedding.

**`ValidatorAgent`** — Computes a six-dimensional **Semantic Grounding Value (SGV)**:

| Metric | Weight |
|---|---|
| Faithfulness (Groq-verified) | 20% |
| Answer relevancy (cosine) | 20% |
| Context recall | 20% |
| Context precision | 15% |
| Source credibility (domain trust + citations) | 25% |
| Contradiction rate (NLI, post-softmax) | 5% |

Results with SGV < 0.60 trigger automatic query decomposition and re-search.

**`VectorizerAgent`** — Chunks text/PDFs with LlamaIndex `SentenceSplitter`, applies section-aware splitting for academic PDFs, CLIP for images, and AST-based chunking for code.

**`RetrieverAgent`** — Dense HNSW search → BM25 sparse re-rank → RRF fusion → cross-encoder reranking (cached in Redis) → MMR diversity filter with per-content-type seeding.

**`TargetExtractor`** — Post-validation LLM extraction of gene/protein targets via Groq, followed by concurrent UniProt, RCSB PDB, and AlphaFold EBI resolution per target.

---

## Installation

### Prerequisites

- Python 3.10+
- [Qdrant](https://qdrant.tech/documentation/quick-start/) (local or cloud)
- Redis (optional, for caching)
- [SearXNG](https://docs.searxng.org/) (optional; falls back to DuckDuckGo)
- Node.js (optional, only if generating DOCX reports)

### Python Dependencies

```bash
pip install aiohttp asyncio numpy scipy scikit-learn pydantic loguru \
            redis sentence-transformers qdrant-client llama-index-core \
            pillow pymupdf ddgs trafilatura
```

### Clone & Configure

```bash
git clone https://github.com/your-org/itda.git
cd itda
```

Set environment variables (Linux/macOS):

```bash
export GROQ_API_KEY=gsk_...          # Required: Groq LLaMA-3.3-70B
export QDRANT_URL=http://localhost:6333
export REDIS_HOST=localhost
export PUBMED_API_KEY=...            # Optional: higher PubMed rate limits
export HF_TOKEN=hf_...              # Optional: BLIP image captioning
export SEARXNG_URL=http://localhost:8080
export SEARXNG_OPEN=true            # or set SEARXNG_API_KEY / SEARXNG_SECRET_KEY
```

Windows (PowerShell):

```powershell
$env:GROQ_API_KEY = "gsk_..."
$env:QDRANT_URL   = "http://localhost:6333"
```

---

## Quick Start

```python
import asyncio
from intelligent_target_discovery_agent import (
    IntelligentTargetDiscoveryAgent,
    AgentContext,
    ContentType,
)

async def main():
    async with AgentContext() as agent:
        response = await agent.discover(
            query="KRAS G12C inhibitor resistance mechanisms non-small cell lung cancer",
            data_types=[ContentType.TEXT, ContentType.PDF],
            filters={"lang": "en", "score_min": 0.60},
            top_k=10,
        )

        print(f"Status:  {response.status}")
        print(f"SGV:     {response.validation_score:.3f}")
        print(f"Sources: {response.source_count}")
        print(f"Targets: {len(response.targets)}")

        for target in response.targets:
            print(f"\n  Gene:      {target['gene']}")
            print(f"  UniProt:   {target['uniprot_id']}")
            print(f"  PDB IDs:   {target['pdb_ids'][:3]}")
            if target['alphafold']:
                print(f"  AlphaFold: {target['alphafold']['alphafold_url']}")

asyncio.run(main())
```

---

## ACP Protocol

The agent communicates via structured `ACPRequest` / `ACPResponse` objects, making it composable with other agents.

### Request

```python
from intelligent_target_discovery_agent import ACPRequest, ACPIntent, ContentType

request = ACPRequest(
    source_agent = "planner_agent",
    query        = "CAR-T therapy clinical trials acute lymphoblastic leukemia",
    data_types   = [ContentType.TEXT, ContentType.PDF, ContentType.TABLE],
    filters      = {"lang": "en", "score_min": 0.60},
    intent       = ACPIntent.FIND,   # FIND | RETRIEVE | REFRESH | VALIDATE
    top_k        = 8,
    require_fresh= True,
)

response = await agent.handle_request(request)
```

### Response Structure

```json
{
  "acp_version":          "3.4",
  "session_id":           "a1b2c3d4",
  "status":               "success",
  "validation_score":     0.823,
  "retrieval_latency_ms": 1842,
  "source_count":         12,
  "payload": {
    "text": [ { "title": "...", "source_url": "...", "pmid": "...", "doi": "..." } ],
    "pdf":  [ { "title": "...", "source_url": "..." } ]
  },
  "targets": [
    {
      "gene":               "KRAS",
      "protein":            "GTPase KRas",
      "mutations":          ["G12C", "G12D"],
      "disease_context":    "non-small cell lung cancer",
      "druggability_notes": "covalent pocket at switch-II; AMG-510 approved",
      "uniprot_id":         "P01116",
      "pdb_ids":            ["6OIM", "6P8Z", "7T0Q"],
      "pdb_structures": [
        { "pdb_id": "6OIM", "title": "KRAS G12C + AMG-510", "resolution": 1.09 }
      ],
      "alphafold": {
        "entry_id":      "AF-P01116-F1",
        "avg_plddt":     87.4,
        "alphafold_url": "https://alphafold.ebi.ac.uk/entry/P01116"
      },
      "supporting_pmids": ["34567890"],
      "source_count":     8
    }
  ]
}
```

### Intent Types

| Intent | Behaviour |
|---|---|
| `FIND` | Cache lookup → Qdrant retrieval → web search if sparse |
| `RETRIEVE` | Qdrant-only (no web search) |
| `REFRESH` | Bypass cache and Qdrant; force fresh web collection |
| `VALIDATE` | Re-validate existing results against current quality thresholds |

---

## Configuration

All settings live in `AgentConfig` and can be overridden via environment variables or by subclassing.

```python
# Key thresholds
cfg.SGV_MIN                    = 0.60   # Minimum Semantic Grounding Value to accept results
cfg.RELEVANCE_THRESHOLD_BASE   = 0.45   # Cosine similarity floor for individual items
cfg.DATA_FRESHNESS_DAYS        = 365    # Max age of indexed documents
cfg.TOP_K_DENSE                = 20     # Candidates from Qdrant before reranking
cfg.TOP_K_RERANK               = 10     # Final results after cross-encoder + MMR
cfg.QUERY_DECOMPOSE_WORD_THRESHOLD = 10 # Auto-decompose queries longer than N words
cfg.BM25_MAX_DOCS              = 2000   # In-memory BM25 corpus cap (FIFO eviction)
```

---

## Data Sources

| Source | Type | Notes |
|---|---|---|
| PubMed (NCBI E-utilities) | Abstracts + metadata | Highest-trust; up to 10 results per query |
| Europe PMC | Abstracts | Full-text links where available |
| Semantic Scholar | Abstracts + citation counts | Boosts credibility scoring |
| ClinicalTrials.gov | Trial summaries | Phase and status metadata included |
| SearXNG | Web (configurable engines) | Includes Bing, DuckDuckGo, Semantic Scholar |
| DuckDuckGo (fallback) | Web | Activated if SearXNG returns fewer than 3 results |
| Jina Reader | Full-page text | Concurrent with trafilatura; first non-empty wins |
| ArXiv / bioRxiv / medRxiv | Preprints | Included in trusted domain list |

### Trusted Domains (sample)

PubMed, Nature, Science, Cell, The Lancet, NEJM, PLOS, Semantic Scholar, UniProt, RCSB PDB, ChEMBL, KEGG, Reactome, OMIM, ClinicalTrials.gov, DrugBank, and 30+ additional peer-reviewed and institutional sources.

---

## Embedding Models

| Role | Model | Dimension |
|---|---|---|
| Text (primary) | `BAAI/bge-base-en` | 768 |
| Tables | `sentence-transformers/all-MiniLM-L6-v2` | 384 |
| Images / graphs | `sentence-transformers/clip-ViT-B-32` | 512 |
| Cross-encoder reranker | `BAAI/bge-reranker-v2-m3` | — |
| NLI contradiction + faithfulness | `cross-encoder/nli-deberta-v3-small` | — |
| LLM (HyDE, decomposition, summarization, NER) | Groq `llama-3.3-70b-versatile` | — |

---

## Vector Collections (Qdrant)

| Collection | Embedding | Distance | Use |
|---|---|---|---|
| `texts_collection` | BGE-base-en | Cosine | Journal articles, web text |
| `pdfs_collection` | BGE-base-en | Cosine | PDFs, preprints |
| `images_collection` | CLIP-ViT-B-32 | Cosine | Figures, micrographs |
| `tables_collection` | MiniLM-L6 | Dot | Data tables |
| `graphs_collection` | BGE-base-en | Cosine | Network diagrams, charts |
| `videos_collection` | BGE-base-en | Cosine | Video transcripts |
| `code_collection` | BGE-base-en | Cosine | Code snippets |

All collections use INT8 scalar quantization with always-RAM storage and HNSW indices (m=16, ef_construct=100).

---

## Running the Demo

```bash
python intelligent_target_discovery_agent.py
```

The demo runs six sequential tests:

1. SearXNG / DDG / Scholar / PubMed connectivity check
2. KRAS G12C drug target discovery (text + PDF)
3. Multimodal query (text + image + table)
4. Full ACP request with CAR-T clinical trial data
5. Qdrant before/after vector counts
6. REFRESH intent (bypasses cache and Qdrant entirely)
7. Long-query Groq decomposition test

Target JSON files are written to `outputs/targets_<session_id>.json` after each successful extraction.

---

## Extending the Agent

### Adding a New Data Source

Implement an async method on `WebSearchAgent` following the pattern of `_search_pubmed`, then call it from `_collect_for_type`. Return a list of dicts with at minimum `url`, `title`, and `content` keys.

### Adding a New Content Type

1. Add a value to the `ContentType` enum.
2. Add a corresponding Qdrant collection entry in `AgentConfig.COLLECTIONS`.
3. Add a vectorization path in `VectorizerAgent._vectorize_item`.
4. Map the new type in `QdrantCollectionManager.collection_for_type`.

### Plugging Into a Multi-Agent System

```python
# Your orchestrator agent
response = await requests.post(
    "http://itda-service/acp",
    json=ACPRequest(
        source_agent="your_agent",
        query="...",
    ).model_dump()
)
targets = response.json()["targets"]
```

---

## Project Structure

```
itda/
├── intelligent_target_discovery_agent.py   # Core agent (all components)
├── target_extractor.py                     # TargetExtractor post-processor
├── outputs/                                # Per-session target JSON files
│   └── targets_<session_id>.json
└── agent_discovery.jsonl                   # Structured log (rotating, 50 MB)
```

---

## Changelog

### v3.4
- `TargetExtractor` integrated: Groq NER → UniProt → PDB → AlphaFold per target
- Targets persisted to `outputs/targets_<session_id>.json`
- `ACPResponse` extended with `targets` field

### v3.3
- Softmax fix: NLI raw logits normalized before contradiction threshold comparison
- Faithfulness scoring blends Groq (top-3 items) with NLI coverage (remaining items)
- BM25 corpus capped at 2,000 documents (FIFO eviction)
- MMR filter seeds selection with one result per content type (type-diversity guarantee)
- PubMed `max_results` raised to 10; DDG capped at 5
- `DATA_FRESHNESS_DAYS` raised from 90 → 365
- Relevance threshold floor raised from 0.28 → 0.32

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Citation

If you use this agent in research, please cite:

```bibtex
@software{itda2024,
  title   = {Intelligent Target Discovery Agent},
  version = {3.4},
  year    = {2024},
  url     = {https://github.com/your-org/itda}
}
```

---

*Built with [Qdrant](https://qdrant.tech/) · [Groq](https://groq.com/) · [SentenceTransformers](https://www.sbert.net/) · [LlamaIndex](https://www.llamaindex.ai/) · [aiohttp](https://docs.aiohttp.org/)*
