# DX-LAB integration — ACP hub and services

This document describes how the **ACP multi-agent hub** (`backend/acp_hub`) talks to **ITD (Data Manager)**, **DiscoveryAgent**, and the **3D printer (Flask)**. All runnable backends live under **`backend/services/`** in this monorepo (including **`data_manager`**, **`discovery_agent`**, **`printer_3d`**, **`drug_safety`**, and **`hypothesis_assistant_agent`**); `backend/reference/` is a **read-only snapshot** of the original architecture repo (not imported at runtime). See `backend/README.md`.

## Ports (default)

| Service | Port | URL / command |
|--------|------|----------------|
| **ITD** (Data Manager) | **8000** | `http://127.0.0.1:8000` — FastAPI `POST /generate` |
| **Drug safety** | **8002** | `http://127.0.0.1:8002` — FastAPI `GET /analyze` (default avoids clash with ITD) |
| **ACP hub** | **8010** | `http://127.0.0.1:8010` — `acp_sdk` server (`GET /agents`, `POST /runs`) |
| **3D printer** | **5000** | `http://127.0.0.1:5000` — Flask `POST /api/submit` |
| **Next.js** | **3000** | Existing pages may call ITD on `:8000` unchanged |

Set `ACP_SERVER_PORT` if 8010 is taken. **Do not** run ITD and the ACP hub on the same port.

## Environment variables

### Hub (`acp_hub`)

| Variable | Default | Description |
|----------|---------|-------------|
| `ACP_SERVER_HOST` | `127.0.0.1` | ACP bind address |
| `ACP_SERVER_PORT` | `8010` | ACP bind port |
| `ACP_SERVER_URL` | derived | Used by executor to call peer agents |
| `DATA_MANAGER_URL` | `http://127.0.0.1:8000` | ITD base URL for `data_manager` wrapper |
| `PRINTER_3D_URL` | `http://127.0.0.1:5000` | Flask base URL for `printer_3d` wrapper |
| `DISCOVERY_AGENT_ROOT` | `backend/services/discovery_agent` | Root containing `run_discovery_agent.py` (override with absolute path if you keep a copy elsewhere) |
| `EXECUTOR_STEP_TIMEOUT` | `900` | Seconds (discoverer runs can be long) |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | see `acp_hub/settings/config.py` | Planner / executor LLM |

### Frontend (see repo root `.env.example` and `frontend/.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_ACP_URL` | `http://127.0.0.1:8010` | Hub URL for browser code (optional until you wire UI) |
| `ACP_SERVER_URL` | same as public | Server-side proxy target (`/api/acp/*` Route Handler) |
| `DRUG_SAFETY_API_URL` | `http://127.0.0.1:8002` | Drug safety FastAPI for `/api/drug-safety` |

Same-origin ACP proxy: **`GET /api/acp/agents`**, **`POST /api/acp/runs`**, etc. (forwards to the hub).

### DiscoveryAgent external context (Phase 2)

When the hub passes seeds from the Data Manager, `discoverer` may set:

- `DISCOVERY_USE_EXTERNAL_CONTEXT=1`
- `DISCOVERY_CONTEXT_JSON_PATH` → JSON file with `SMILES`, `fasta`, optional `uniprot_id`, `drug_name`, `protein`, `disease`

Advanced-AI-Project `mcp_agent.py` reads these and **skips** the normal UniProt/Serper extraction when the file is valid.

## ACP agent registry names

| Name | Role |
|------|------|
| `planner` | Builds execution plan (LLM) |
| `executor` | Runs plan steps, dispatches to other agents via ACP |
| `data_manager` | HTTP proxy to ITD `/generate` |
| `discoverer` | Subprocess: `python run_discovery_agent.py -c <yaml> --protein … --disease …` |
| `printer_3d` | HTTP proxy to Flask `/api/submit` |

## JSON handoff (minimal)

### `data_manager` input

Plain text or JSON:

```json
{
  "query": "EGFR inhibitors in NSCLC",
  "top_k": 10,
  "data_types": ["text", "pdf"],
  "intent": "refresh"
}
```

### `data_manager` output (subset)

JSON with `session_id`, `targets`, `sources`, `validation_score`, etc.

### `discoverer` input

```json
{
  "protein": "EGFR",
  "disease": "non-small cell lung cancer",
  "tier": "lite",
  "run_id": "optional_id",
  "context_bundle": {
    "SMILES": "CC(=O)Oc1ccccc1C(=O)O",
    "fasta": "MTEYKLVVVGACGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHQYREQIKRVKDSDDVPMVLVGNKCDLAARTVESRQAQDLARSYGIPYIETSAKTRQGVEDAFYTLVREIRQHKLRKLNPPDESGPGCMSCKCVLS",
    "uniprot_id": "P00533",
    "drug_name": "Aspirin"
  }
}
```

- `tier`: `lite` (fewer iterations/smiles) or `full`.
- `context_bundle`: optional; if it includes **both** `SMILES` and `fasta`, the wrapper writes a temp JSON file and sets `DISCOVERY_USE_EXTERNAL_CONTEXT` for the subprocess.

### `printer_3d` input

Plain text description, or JSON:

```json
{ "description": "SMILES: CC(=O)Oc1ccccc1C(=O)O" }
```

## One-shot local stack (Windows)

From the repo root:

```powershell
.\start_stack.ps1
```

Opens separate terminals for **data_manager (8000)**, **drug_safety (8002)**, **printer_3d (5000)**, and **acp_hub (8010)**. Then run the Next app manually: `cd frontend && npm run dev`.

## Manual smoke run (four processes)

1. **ITD / Data Manager** — working directory `backend/services/data_manager`:

   ```bash
   cd backend/services/data_manager
   uvicorn api_server:app --host 127.0.0.1 --port 8000
   ```

2. **3D printer** — working directory `backend/services/printer_3d`:

   ```bash
   cd backend/services/printer_3d
   python web_server.py
   ```

3. **Install hub deps** (once), from `DX-LAB-integration/backend`:

   ```bash
   pip install -r acp_hub/requirements.txt
   ```

4. **ACP hub**:

   ```bash
   cd backend
   REM Optional if defaults match your tree:
   REM set DISCOVERY_AGENT_ROOT=%CD%\services\discovery_agent
   python -m acp_hub.main
   ```

5. Call **`GET http://127.0.0.1:8010/agents`** and **`POST /runs`** with your ACP client (see `acp_sdk` docs) targeting `planner` then `executor`, or use the upstream `test_api.py` pattern against port **8010**.

## Data ownership

- **Literature / vectors / evidence**: **ITD** (`data_manager`).
- **Molecule pipeline** (REINVENT, predictions, Boltz tier): **DiscoveryAgent** (`discoverer`), optionally seeded from ITD via `context_bundle` + `DISCOVERY_USE_EXTERNAL_CONTEXT`.

## Other Python services (same `backend/services/` tree)

- **Drug safety (FastAPI)** — working directory `backend/services/drug_safety`: `python run_web.py` (defaults to **127.0.0.1:8002**; override with `DRUG_SAFETY_PORT` / `DRUG_SAFETY_HOST`).
- **Hypothesis assistant** — working directory `backend/services/hypothesis_assistant_agent`: `uvicorn api:app --host 127.0.0.1 --port 8001` (matches the Next.js hypothesis page, which calls **http://localhost:8001**).

## Frontend

Phase 1 keeps existing pages calling **ITD :8000** where they already do. **ACP proxy** is available at **`/api/acp/*`** (configure `frontend/.env.local` from `frontend/.env.example`). You can add UI that calls `fetch("/api/acp/agents")` or `POST /api/acp/runs` without CORS issues.
