# Biomedical Hypothesis Generation Assistant

> An AI-powered multi-agent pipeline that retrieves scientific literature, extracts causal relationships, detects research gaps and conflicts, and generates novel, testable biomedical hypotheses — built with Python, LangChain, and a local Ollama LLM.

---

## Overview

This project was developed as part of the coursework for **AI & Biomedical Informatics** at [Esprit School of Engineering](https://esprit.tn/).

It explores the automation of scientific hypothesis generation by combining literature retrieval, NLP-based entity and relationship extraction, causal graph construction, and LLM-driven reasoning. The pipeline processes PubMed abstracts end-to-end and produces ranked, validated research hypotheses with supporting citations.

---

## Features

- Automated literature retrieval via **PubMed E-utilities** with keyword filtering and recency boosting
- Structured entity extraction (genes, drugs, pathways, study types) using **LangChain** prompt chains
- Causal triple extraction and multi-hop cross-paper path discovery using **NetworkX**
- Parallel research gap detection and contradiction identification across papers
- Chain-of-thought hypothesis generation fusing evidence from multiple papers
- Novelty filtering and biomedical validation against known molecular interactions
- Composite scoring (impact + novelty) with semantic citation anchoring
- Interactive follow-up Q&A via a session-based memory agent
- JSON output, Rich console report, and interactive **pyvis** causal graph export

---

## Tech Stack

### Backend & Pipeline
- **Python 3.10+**
- **LangChain** — prompt chaining and LLM orchestration
- **LangChain-Ollama** — local LLM integration (llama3.1:8b)
- **NetworkX** — causal graph construction and path search
- **FastAPI** — REST API wrapper with session support

### AI & NLP
- **Ollama** (llama3.1:8b) — local inference, no API key required
- **sentence-transformers** (all-MiniLM-L6-v2) — semantic citation anchoring
- **PubMed E-utilities API** — scientific literature retrieval

### Other Tools
- **Rich** — terminal UI and progress reporting
- **pyvis** — interactive HTML causal graph export
- **tenacity** — retry logic for external API calls
- **python-dotenv** — environment configuration

---

## Directory Structure

```
.
├── agents/
│   ├── literature_retrieval.py   # Agent 1: PubMed search and filtering
│   ├── paper_analysis.py         # Agent 2: Entity and outcome extraction
│   ├── relationship_extractor.py # Agent 2.5: Causal triple and graph building
│   ├── gap_detection.py          # Agent 3: Research gap identification
│   ├── conflict_detection.py     # Agent 4: Contradiction detection
│   ├── hypothesis_generation.py  # Agent 5: Hypothesis synthesis and scoring
│   ├── novelty_filter.py         # Agent 3.5: Originality assessment
│   ├── biomedical_validator.py   # Post-hoc biological plausibility check
│   └── memory_agent.py           # Session memory for interactive follow-up
├── config/
│   └── settings.py               # Pipeline configuration and environment vars
├── tools/
│   └── pubmed_tool.py            # LangChain PubMed retrieval tool
├── utils/
│   ├── llm.py                    # Ollama LLM factory functions
│   ├── prompts.py                # All LangChain prompt templates
│   ├── cache.py                  # SHA-256 disk cache for LLM responses
│   ├── rate_limiter.py           # Thread-safe call throttling
│   ├── biomed_entities.py        # Entity type registry and triple validation
│   └── output_formatter.py       # Rich console output and JSON serialisation
├── output/                       # Generated results, graphs, and debug files
├── main.py                       # CLI entry point and full pipeline runner
├── api.py                        # FastAPI server with /generate and /ask endpoints
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running locally
- `llama3.1:8b` model pulled: `ollama pull llama3.1:8b`

### Installation

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
OLLAMA_MODEL=llama3.1:8b
PUBMED_API_KEY=          # optional — increases PubMed rate limit
MAX_PAPERS=5
NUM_HYPOTHESES=3
```

### Running the pipeline

```bash
# Basic run
python main.py "KRAS inhibition in non-small cell lung cancer"

# Generate more hypotheses
python main.py "KRAS inhibition in NSCLC" --num-hypotheses 5

# Export interactive causal graph
python main.py "KRAS inhibition in NSCLC" --export-graph

# Interactive follow-up session after pipeline
python main.py "KRAS inhibition in NSCLC" --interactive
```

### Running the API

```bash
uvicorn api:app --reload
```

Endpoints:
- `POST /generate` — runs the full pipeline for a query
- `POST /ask` — sends a follow-up question to an active session
- `GET /health` — health check

---

## Acknowledgments

This project was completed under the guidance of faculty at **Esprit School of Engineering**.

It was presented as part of the AI engineering programme at Esprit School of Engineering, exploring the application of multi-agent LLM systems to biomedical research automation.
