# DiscoveryAgent (service copy)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This tree is a **slimmed vendored copy** inside **DX-LAB-integration** at `backend/services/discovery_agent`. It keeps the **pipeline runtime** (`run_discovery_agent.py` → `mcp_agent.py` → `DiscoveryAgent/`), **configs**, **requirements**, and **docs** used to run and debug the stack. Standalone-repo extras (examples, CI workflows, unit tests) were removed to reduce noise and size. **Prompt packs** `structure_generation.py`, `property_prediction.py`, and `smiles_generation.py` plus **`analysis/analysis_helper.py`** are kept for LangChain agents, plotting helpers, and paper/notebook-style workflows even if the default MCP path does not import them.

Upstream project: [llm-dd / DiscoveryAgent](https://github.com/hoon-ock/llm-dd) (paper, full history, notebooks).

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/getting-started.md](./docs/getting-started.md) | Env, keys, first run |
| [docs/pipeline-configuration.md](./docs/pipeline-configuration.md) | YAML config reference |
| [docs/architecture.md](./docs/architecture.md) | Flow and modules |
| [docs/mcp-server.md](./docs/mcp-server.md) | MCP tools and behavior |
| [docs/run-artifacts.md](./docs/run-artifacts.md) | `runs/<run_id>/` layout |
| [docs/troubleshooting.md](./docs/troubleshooting.md) | Common errors |

Repo-wide orchestration: [../../../../docs/integration.md](../../../../docs/integration.md) (ACP hub `discoverer` subprocess).

## Install

```bash
cd backend/services/discovery_agent
conda create -n DiscoveryAgent python=3.10 -y
conda activate DiscoveryAgent
pip install -r requirements.txt
```

Install **REINVENT4** separately and set `REINVENT_PATH` in `configs/tool_globals.py` (see [docs/getting-started.md](./docs/getting-started.md)).

## Run

```bash
conda run -n DiscoveryAgent python run_discovery_agent.py -c pipeline_config.yaml --protein "EGFR" --disease "NSCLC"
# Interactive Q&A (RAG):
conda run -n DiscoveryAgent python run_discovery_agent.py --qna -c pipeline_config.yaml
```

## Configuration

- **Keys:** Prefer env vars (`SERPER_API_KEY`, `LLM_API_KEY` / `NVIDIA_API_KEY`, `OPENAI_API_KEY`). Optional fallback: `configs/secret_keys.py` (gitignored pattern in parent `.gitignore` where applicable).
- **Globals:** `configs/tool_globals.py` — LLM, embeddings, paths, ADMET polling.

## License & citation

MIT. For the academic citation and original authors, see the upstream repository and paper linked there.
