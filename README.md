# 🧬 Intelligent Target Discovery Agent

> An end-to-end biomedical AI pipeline for automated drug target discovery, built with retrieval-augmented generation (RAG), hybrid vector search, and large language models.

This project was developed as part of the coursework for **AI & Biomedical Systems — Final Year Project** at [Esprit School of Engineering](https://esprit.tn/).

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-vector--db-red)](https://qdrant.tech)
[![Groq](https://img.shields.io/badge/Groq-Llama--3.3--70B-orange)](https://groq.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Overview

The **Intelligent Target Discovery Agent** is a multi-stage AI system that autonomously retrieves, validates, embeds, and enriches biomedical literature to extract actionable drug targets. Given a natural language query (e.g., a disease, gene, or pathway), the agent collects documents from PubMed, Europe PMC, SearXNG, and Jina Reader, then processes them through a full RAG pipeline — culminating in a structured report with ranked gene/protein targets, pathway mappings, and chemical annotations.

Key capabilities:
- Hybrid dense + sparse retrieval with Reciprocal Rank Fusion (RRF)
- Parallel biomedical named-entity recognition (BioNER), chemical extraction, and UniProt-validated target extraction
- Composite Semantic Grounding & Validation (SGV) scoring
- Downloadable DOCX report narrated by Groq Llama-3.3-70B
- Session-scoped QA assistant for follow-up queries

---

## Features

- 🔍 **Multi-source collection** — PubMed, Europe PMC, SearXNG, Jina Reader, ClinicalTrials.gov
- 🧠 **RAG pipeline** — BGE-base-en (768d) embeddings + HNSW index with INT8 scalar quantization
- ⚖️ **SGV scoring** — faithfulness, answer relevancy, source credibility, and contradiction rate
- 🧬 **BioNER** — gene and protein extraction via spaCy + HuggingFace NER models
- 💊 **ChemExtractor** — PubChem-backed chemical structure and SMILES annotation
- 🎯 **TargetExtractor** — LLM-driven target identification with UniProt validation
- 🗺️ **PathwayMapper** — KEGG and Reactome pathway mapping with PubMed frequency ranking
- 📄 **Report generation** — structured FinalReport exported as DOCX via `python-docx`
- ⚡ **Redis caching** — MD5-keyed query cache (TTL 3 600 s) for zero-latency repeat queries

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| API framework | FastAPI + Uvicorn |
| LLM | Groq — Llama-3.3-70B-Versatile |
| Vector DB | Qdrant (AsyncQdrantClient) |
| Cache | Redis (aioredis) |
| NLP / NER | spaCy, HuggingFace Transformers |
| Embeddings | BAAI/bge-base-en · CLIP ViT-B/32 · all-MiniLM-L6-v2 |
| Reranking | BAAI/bge-reranker-v2-m3 · DeBERTa NLI |
| Chunking | LlamaIndex SentenceSplitter |
| HTTP | aiohttp · httpx |

### Data Sources
| Source | Type |
|---|---|
| PubMed / NCBI E-utilities | Literature |
| Europe PMC | Preprints + Open Access |
| SearXNG | Open web search |
| Jina Reader | Web scraping |
| ClinicalTrials.gov | Clinical data |
| UniProt REST API | Protein validation |
| PubChem | Chemical annotation |
| KEGG / Reactome | Pathway databases |

### Other Tools
- `python-docx` — DOCX report export
- `loguru` — structured logging
- `pydantic v2` — data validation and serialisation
- `scikit-learn` — TF-IDF BM25 approximation
- `numpy` — RRF and MMR fusion

---

## Directory Structure

```
intelligent-target-discovery/
├── agent.py                  # Core orchestration agent
├── api_server.py             # FastAPI server & endpoints
├── config.py                 # Centralised configuration (env-driven)
├── models.py                 # Pydantic data models & enums
├── embeddings.py             # EmbeddingService (BGE, CLIP, MiniLM)
├── vectorizer.py             # VectorizerAgent — chunking & embedding
├── storage.py                # QdrantCollectionManager + CacheLayer
├── retriever.py              # Hybrid retrieval (dense + BM25 + RRF)
├── validator.py              # Domain trust & biomedical filtering
├── bio_ner.py                # BioNER named-entity recognition
├── extractor.py              # Generic extraction utilities
├── chemical_extractor.py     # ChemExtractor — PubChem / SMILES
├── target_extractor.py       # TargetExtractor — LLM + UniProt
├── uniprot_validator.py      # UniProt REST validation
├── pathway_mapper.py         # KEGG / Reactome pathway mapping
├── pubmed_frequency.py       # PubMed co-occurrence frequency
├── search.py                 # SearXNG + Jina search helpers
├── qa_assistant.py           # Session-scoped QA assistant
├── report_generator.py       # FinalReport → DOCX generation
├── utils.py                  # CircuitBreaker, BM25Index, domain filter
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker (for Qdrant and Redis)
- Node.js 18+ (optional, for frontend)

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/intelligent-target-discovery.git
cd intelligent-target-discovery
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Qdrant and Redis

```bash
docker run -d -p 6333:6333 qdrant/qdrant
docker run -d -p 6379:6379 redis:7
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (Llama-3.3-70B) |
| `PUBMED_API_KEY` | NCBI E-utilities API key |
| `HF_TOKEN` | HuggingFace token (for gated models) |
| `QDRANT_URL` | Qdrant URL (default: `http://localhost:6333`) |
| `REDIS_HOST` | Redis host (default: `localhost`) |
| `SEARXNG_URL` | SearXNG instance URL |

### 5. Run the server

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Query the agent

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "KRAS mutation drug targets in non-small cell lung cancer", "top_k": 10}'
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/generate` | Run full discovery pipeline for a query |
| `POST` | `/ask` | Ask a follow-up question on a session |
| `GET` | `/download-report?session_id=` | Download DOCX report |
| `GET` | `/health` | Health check |

---

## Evaluation

| Metric | Description |
|---|---|
| **SGV score** | Composite: faithfulness (20%) + relevancy (20%) + recall (20%) + precision (15%) + credibility (25%) |
| **Retrieval quality** | Cross-encoder reranker score (BGE-reranker-v2-m3) |
| **Target confidence** | UniProt validation match rate |
| **Dedup rate** | Cosine-threshold deduplication per content type |

Minimum acceptable SGV threshold: **0.60**

---

## Acknowledgments

This project was completed under the guidance of faculty at **Esprit School of Engineering**.  
It was developed as a final-year AI engineering project exploring the intersection of biomedical NLP, retrieval-augmented generation, and autonomous agent design.

Special thanks to the open-source communities behind Qdrant, LlamaIndex, HuggingFace Transformers, and FastAPI.

---

> **Topics:** `python` · `machine-learning` · `rag` · `biomedical-nlp` · `drug-discovery` · `vector-search` · `large-language-models` · `fastapi` · `qdrant` · `artificial-intelligence` · `named-entity-recognition` · `esprit-school-of-engineering`
