# Troubleshooting

This page covers common issues when running DiscoveryAgent locally.

## Conda command not found or activation fails

Symptoms:

- `conda` is not recognized.
- `conda activate DiscoveryAgent` does not change environment.

Fix:

1. Open Anaconda PowerShell Prompt (Windows) or initialize conda in your shell.
2. Run `conda init powershell` once, then restart terminal.
3. Use `conda run -n DiscoveryAgent python ...` if activation remains unreliable.

## REINVENT not found or sampling.toml missing

Symptoms:

- Pooling fails with REINVENT path errors.
- Error indicates missing `configs/toml/sampling.toml`.

Fix:

1. Install REINVENT4.
2. Set `REINVENT_PATH` in `configs/tool_globals.py` to your local REINVENT4 directory.
3. Verify the file exists at `<REINVENT_PATH>/configs/toml/sampling.toml`.

## API authentication failures

Symptoms:

- LLM calls fail early.
- Retrieval tools fail due to missing Serper key.

Fix:

1. Set `SERPER_API_KEY`.
2. Set `LLM_API_KEY` and optionally `NVIDIA_API_KEY` or `OPENAI_API_KEY`.
3. Confirm your base URL and model in `configs/tool_globals.py`.
4. Avoid committing real credentials in `configs/secret_keys.py`.

## ADMET stage appears stalled

Symptoms:

- `status.json` shows repeated waiting entries for ADMET jobs.

Why this happens:

- ADMET calls are asynchronous and can take several minutes.

Fix:

1. Check `runs/<run_id>/logs/admet_*.log` for progress.
2. Confirm outbound network access to the required prediction APIs.
3. Reduce `num_smiles` during debugging runs.

## No candidates pass final filters

Symptoms:

- `boltz_candidates.csv` is empty.
- Step notes indicate no candidates passed filters.

Fix:

1. Lower `min_pkd` and/or `min_qed` in your config.
2. Increase `num_smiles` to broaden candidate pool.
3. Review `affinity_after.csv` and `admet_after.csv` for distribution of scores.

## Boltz did not run even though YAML files exist

Symptoms:

- YAMLs are present in `runs/<run_id>/configs/`.
- No Boltz job logs exist.

Fix:

1. Confirm `run_boltz: true` in config when you want Boltz to execute (default is off).
2. Ensure `boltz` CLI is installed in the runtime environment.
3. Validate `boltz_extra_args_json` is valid JSON array syntax.

## MCP pipeline starts but jobs run in wrong environment

Symptoms:

- Worker commands fail due to missing packages despite active environment.

Fix:

Set:

- `DISCOVERY_AGENT_FORCE_CONDA_RUN=1`
- `DISCOVERY_AGENT_CONDA_ENV=DiscoveryAgent`

This forces subprocess workers to run through conda explicitly.
