# Architecture

DiscoveryAgent is organized around two execution entry points:

- `run_discovery_agent.py`: user-facing runner for pipeline mode or Q&A mode.
- `mcp_agent.py`: FastMCP server that exposes tools for pipeline execution and job management.

![DiscoveryAgent Overview](overview.png)

## High-level flow

1. `run_discovery_agent.py` loads YAML config and starts a stdio transport client.
2. The client calls `DiscoveryAgent_run_pipeline` on the MCP server.
3. The server orchestrates extraction, pooling, iterative prediction/refinement, and optional Boltz jobs.
4. Artifacts and progress state are written under `runs/<run_id>/`.

## Pipeline stages

1. Extraction:
   - Uses retrieval tools to discover UniProt ID, FASTA sequence, and a seed drug SMILES.
   - Writes `extraction_response.json` and normalized `extraction.json`.

2. Pooling:
   - Runs REINVENT sampling flows and merges candidate SMILES into a combined pool.
   - Writes `pooling_result.json`.

3. Iterative loop:
   - Runs affinity and ADMET prediction jobs.
   - Runs LLM-based SMILES refinement.
   - On final iteration, runs additional prediction pass for updated SMILES.

4. Candidate selection and Boltz:
   - Merges and scores predictions.
   - Applies Oprea and drug-likeness rules with pKd and QED thresholds.
   - Generates Boltz YAMLs and optionally runs structure prediction.

## Concurrency model

- Affinity and ADMET are spawned as subprocess workers.
- Job metadata is persisted in `runs/<run_id>/jobs`.
- Job logs stream into `runs/<run_id>/logs`.
- Progress updates are appended to `status.json`.

## Key modules

- `DiscoveryAgent/agents.py`: agent construction and orchestration.
- `DiscoveryAgent/tools/retrieval.py`: paper retrieval and extraction-time tools.
- `DiscoveryAgent/tools/prediction.py`: affinity and ADMET prediction helpers.
- `DiscoveryAgent/tools/generation.py`: REINVENT and structure generation helpers.
- `DiscoveryAgent/analysis/drug_likeness_analyzer.py`: rule-based scoring and QED support.
