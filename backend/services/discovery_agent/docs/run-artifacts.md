# Run Artifacts

Every pipeline execution writes to `runs/<run_id>/`.

## Top-level files

| Path | Purpose |
| --- | --- |
| `run_config.json` | Effective configuration used by the run. |
| `status.json` | Live progress and step timeline. |
| `summary.json` | Final run summary returned by MCP tool. |
| `extraction.json` | Structured extraction output (protein, disease, UniProt, FASTA, seed SMILES). |
| `extraction_response.json` | Full raw extraction agent response. |
| `pooling_result.json` | Pooling stage output and REINVENT execution details. |
| `boltz_candidates.csv` | Final filtered candidates selected for Boltz YAML generation/execution. |

## Subdirectories

| Path | Purpose |
| --- | --- |
| `iter_00/`, `iter_01/`, ... | Iteration-level intermediate and final artifacts. |
| `jobs/` | Job metadata JSON per subprocess. |
| `logs/` | Log files for affinity, ADMET, and Boltz jobs. |
| `pool/` | Combined initial candidate pools and REINVENT outputs. |
| `configs/` | Generated Boltz YAML files. |
| `papers/` | Downloaded papers for Q&A mode. |

## Iteration layout

Typical per-iteration structure:

- `iter_<n>/pool/candidates.csv`
- `iter_<n>/property/affinity*.csv`
- `iter_<n>/property/admet*.csv`
- `iter_<n>/refinement/refinement.csv`
- `iter_<n>/next_iter_candidates.csv` (non-final iterations)

On the final iteration, before/after prediction outputs are stored separately:

- `affinity_before.csv`, `admet_before.csv`
- `affinity_after.csv`, `admet_after.csv`

## Monitoring a running pipeline

Use `status.json` for low-noise progress monitoring.

Example fields:

- `current_step`: latest pipeline step label.
- `steps`: append-only history with `timestamp` and `details`.

For stalled jobs, inspect:

1. `jobs/<job_id>.json`
2. `logs/<job_id>.log`
3. Any `errors/*.json` files created under failed iteration directories.
