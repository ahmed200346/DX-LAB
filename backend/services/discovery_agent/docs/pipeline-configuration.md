# Pipeline Configuration

DiscoveryAgent loads defaults from `run_discovery_agent.py` and optionally overrides them using YAML. When you use `run_discovery_agent.py`, you can also pass `--protein` and `--disease` to override the values in the YAML file for that run.

## Configuration files in this repository

- `pipeline_config.yaml`: baseline pipeline run configuration.
- `pipeline_config_selection.yaml`: configuration that enables Boltz and selection filters.

## Full key reference

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `run_id` | string | auto-generated timestamp + suffix | No | Name of run folder under `runs/`. |
| `protein` | string | _(none; required)_ | Yes | Target protein for extraction, retrieval, and refinement (any common or UniProt-resolvable name). |
| `disease` | string | _(none; required)_ | Yes | Disease or therapeutic context for extraction and Q&A paper retrieval. |
| `iterations` | integer | `2` | No | Number of refinement iterations. Must be `>= 1`. |
| `num_smiles` | integer | `2` in code default, often higher in examples | No | Number of sampled molecules per REINVENT model before dedupe. |
| `run_boltz` | boolean | `false` | No | If `true`, run Boltz structure prediction jobs. YAML configs are still generated even when `false`. |
| `boltz_top_k` | integer | `2` in code default | No | Max number of filtered candidates sent to Boltz YAML generation. |
| `boltz_extra_args_json` | string (JSON array) | `"[\"--use_msa_server\",\"--accelerator\",\"gpu\",\"--num_workers\",\"4\"]"` in sample configs | No | Extra CLI args passed to `boltz predict`. Must be valid JSON array syntax. |
| `model` | string | `LLM_MODEL` from `configs/tool_globals.py` | No | LLM model passed into extraction, refinement, and Q&A agents. |
| `min_qed` | float | `0.50` | No | Minimum QED score used during final candidate selection. |
| `min_pkd` | float | `5.0` | No | Minimum predicted `Affinity [pKd]` for final candidate selection. |

## Example: minimal config

```yaml
protein: "EGFR"
disease: "non-small cell lung cancer"
iterations: 2
num_smiles: 2
run_boltz: false
boltz_top_k: 2
model: "moonshotai/kimi-k2.5"
```

## Example: run with candidate filtering + Boltz

```yaml
run_id: "example_selection"
protein: "EGFR"
disease: "non-small cell lung cancer"
iterations: 2
num_smiles: 2
run_boltz: true
boltz_top_k: 2
boltz_extra_args_json: '["--use_msa_server","--accelerator","gpu","--num_workers","4"]'
min_qed: 0.50
min_pkd: 5.0
```

## Tuning guidance

- Increase `num_smiles` for broader exploration. This increases prediction and ADMET time.
- Increase `iterations` for deeper refinement loops. This compounds runtime.
- Tighten `min_qed` and `min_pkd` to reduce false positives in final candidates.
- Keep `boltz_top_k` low while testing to control structure generation cost.

## Validation checklist

- `boltz_extra_args_json` parses as JSON.
- `model` is available from your API endpoint.
- `REINVENT_PATH` in `configs/tool_globals.py` points to a real installation.
- API keys are set before run start.
