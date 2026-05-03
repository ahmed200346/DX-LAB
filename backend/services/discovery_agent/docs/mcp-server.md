# MCP Server Reference

The project uses a FastMCP server in `mcp_agent.py` and a client runner in `run_discovery_agent.py`.

## Server startup modes

- Stdio server mode:

```bash
python mcp_agent.py
```

- Worker mode (internal):

```bash
python mcp_agent.py _worker --kind affinity --out_dir <path> ...
```

- Interactive Q&A mode (legacy helper):

```bash
python mcp_agent.py _qna
```

Most users should run `run_discovery_agent.py`, which starts the server automatically.

## Exposed MCP tools

### DiscoveryAgent_run_pipeline

Runs the end-to-end workflow:

1. LLM extraction
2. REINVENT pooling
3. Iterative prediction and refinement
4. Final candidate selection
5. Optional Boltz execution

Primary parameters:

- `protein`, `disease`
- `iterations`, `num_smiles`
- `run_boltz`, `boltz_top_k`, `boltz_extra_args_json`
- `model`
- `min_qed`, `min_pkd`
- `run_id`

### DiscoveryAgent_qna

Answers questions using retrieval-augmented generation.

- Downloads papers into `runs/<run_id>/papers/` when needed.
- Reuses a run session when `run_id` is provided.

### DiscoveryAgent_run_status

Returns current status from `runs/<run_id>/status.json`.

### DiscoveryAgent_list_runs

Lists recent runs and metadata (up to 20).

### DiscoveryAgent_job_status

Returns status for a job from `runs/<run_id>/jobs/`.

### DiscoveryAgent_job_logs

Returns tail logs for a job in `runs/<run_id>/logs/`.

### DiscoveryAgent_job_cancel

Sends termination signal for a running job.

## Environment controls

`mcp_agent.py` supports environment variables to force subprocess execution through conda:

- `DISCOVERY_AGENT_FORCE_CONDA_RUN=1`
- `DISCOVERY_AGENT_CONDA_ENV=DiscoveryAgent`

Legacy aliases are also recognized:

- `AGENTD_FORCE_CONDA_RUN`
- `AGENTD_CONDA_ENV`

## Progress model

Pipeline progress is persisted as structured steps in `status.json` with:

- `current_step`
- `last_updated`
- `steps[]` with timestamps and details

This makes long-running operations observable without attaching to process stdout.
