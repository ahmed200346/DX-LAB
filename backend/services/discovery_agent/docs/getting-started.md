# Getting Started

This guide gets you from a fresh checkout to a completed pipeline run.

## Prerequisites

- Python 3.10
- Conda (recommended for dependency isolation)
- Git
- Serper API key
- NVIDIA NIM or another OpenAI-compatible API key

## 1. Clone and install dependencies

```bash
git clone https://github.com/hoon-ock/llm-dd.git
cd llm-dd
```

```bash
conda create -n DiscoveryAgent python=3.10 -y
conda activate DiscoveryAgent
pip install -e .
```

If you prefer pinned installs from requirements:

```bash
pip install -r requirements.txt
```

## 2. Install REINVENT4

REINVENT is used during molecule pooling.

```bash
git clone https://github.com/MolecularAI/REINVENT4.git
cd REINVENT4
python install.py --help
python install.py cu124
```

After install, update `REINVENT_PATH` in `configs/tool_globals.py` to your local REINVENT4 path.

## 3. Configure API keys

Preferred approach: set environment variables.

PowerShell:

```powershell
$env:SERPER_API_KEY = "your_serper_key"
$env:LLM_API_KEY = "your_llm_key"
$env:NVIDIA_API_KEY = $env:LLM_API_KEY
$env:OPENAI_API_KEY = $env:LLM_API_KEY
```

Optional fallback: edit `configs/secret_keys.py` locally. Do not commit real keys.

## 4. Configure model and embedding defaults

`configs/tool_globals.py` controls key runtime defaults:

- `LLM_PROVIDER`
- `LLM_MODEL`
- `NVIDIA_API_BASE`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIM`
- `REINVENT_PATH`

If you change `EMBEDDING_MODEL`, also update `EMBEDDING_DIM` to match the model output dimension.

## 5. Run the pipeline

```bash
python run_discovery_agent.py --config pipeline_config.yaml
```

Run Q&A mode:

```bash
python run_discovery_agent.py --qna --config pipeline_config.yaml
```

## 6. Verify outputs

After a successful run, inspect:

- `runs/<run_id>/status.json`
- `runs/<run_id>/summary.json`
- `runs/<run_id>/extraction.json`
- `runs/<run_id>/pooling_result.json`
- `runs/<run_id>/boltz_candidates.csv`

If your run fails, check `runs/<run_id>/logs/` and `runs/<run_id>/jobs/` first.
