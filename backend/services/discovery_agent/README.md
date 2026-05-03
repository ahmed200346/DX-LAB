# DiscoveryAgent

![Test Status](https://github.com/hoon-ock/llm-dd/actions/workflows/python-app.yml/badge.svg?branch=release)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**DiscoveryAgent** is an open-source Python package designed to accelerate drug discovery workflows using Large Language Models (LLMs) and AI-driven tools. It provides modular agents and utilities for tasks such as literature extraction, molecular property prediction, molecule generation, and more. DiscoveryAgent integrates with external APIs (e.g., [NVIDIA NIM](https://build.nvidia.com), Serper) and cheminformatics libraries, enabling both automated and interactive research pipelines.


<p align="center">
  <img src="./docs/overview.png" alt="DiscoveryAgent Overview" width="500"/>
</p>

## Documentation

Detailed documentation is available in the `docs/` folder:

- [Docs Home](./docs/README.md)
- [Getting Started](./docs/getting-started.md)
- [Pipeline Configuration](./docs/pipeline-configuration.md)
- [Architecture](./docs/architecture.md)
- [MCP Server Reference](./docs/mcp-server.md)
- [Run Artifacts](./docs/run-artifacts.md)
- [Troubleshooting](./docs/troubleshooting.md)

---

## Installation

1. **Clone the repository:**
    ```sh
    git clone https://github.com/hoon-ock/llm-dd.git
    cd llm_dd
    ```

2. **Create and activate a conda environment (recommended):**
    ```sh
    conda create -n DiscoveryAgent python=3.10 -y
    conda activate DiscoveryAgent
    ```

    **Windows (PowerShell) notes:** If `conda` is not recognized, open **Anaconda PowerShell Prompt** (or **Miniconda3**), or run `conda init powershell` once, then close and reopen the terminal. If `conda activate` does nothing or errors, ensure you are in a shell where conda was initialized; you can also run commands without activating via `conda run -n DiscoveryAgent python ...`.

3. **Install dependencies in editable mode:**
    ```sh
    pip install -e .
    ```
    Or, to install all dependencies directly:
    ```sh
    pip install -r requirements.txt
    ```

4. **Install REINVENT4 (required for some tools):**
    ```sh
    git clone https://github.com/MolecularAI/REINVENT4.git
    cd REINVENT4
    python install.py --help
    python install.py cu124  # or rocm6.2.4, cpu, mac, etc.
    ```

---

## Configuration

- **API Keys:**  
  Set API keys in your environment (recommended):
    ```powershell
    $env:SERPER_API_KEY = "YOUR_SERPER_API_KEY"
    $env:LLM_API_KEY = "YOUR_NVIDIA_NIM_API_KEY"
    $env:NVIDIA_API_KEY = $env:LLM_API_KEY
    $env:OPENAI_API_KEY = $env:LLM_API_KEY
    ```
  You can also set local fallback keys in `configs/secret_keys.py`:
    ```python
    # configs/secret_keys.py
    serper_api_key = "YOUR_SERPER_API_KEY"
    llm_api_key = "YOUR_NVIDIA_NIM_API_KEY"
    ```
    You can instead set `LLM_API_KEY` or `NVIDIA_API_KEY` in the environment. Default chat and embedding calls use the OpenAI-compatible NIM base URL `https://integrate.api.nvidia.com/v1` (see `configs/tool_globals.py` for `LLM_MODEL`, `EMBEDDING_MODEL`, and `EMBEDDING_DIM`, which must match the embedding model’s vector size).

- **Global Variables:**  
  The file [configs/tool_globals.py](./configs/tool_globals.py) contains global variables used by the tools. You can edit this file to adjust default behaviors and settings.

---

## Quick Start: MCP Server

DiscoveryAgent can be run as an MCP (Model Context Protocol) server for automated end-to-end drug discovery pipelines.

### Running the Pipeline

```bash
# Run full pipeline with config
conda run -n DiscoveryAgent python run_discovery_agent.py --config pipeline_config.yaml

# Run in Q&A mode (interactive RAG-based research Q&A)
conda run -n DiscoveryAgent python run_discovery_agent.py --qna --config pipeline_config.yaml
```

### Pipeline Configuration

Edit `pipeline_config.yaml` (or pass `--protein` / `--disease` on the CLI) for your target:

```yaml
protein: "EGFR"
disease: "non-small cell lung cancer"
iterations: 2
num_smiles: 20       # Candidates per model (use 2-5 for testing)
run_boltz: false     # Set true to run Boltz 3D structure prediction
boltz_top_k: 10
model: "moonshotai/kimi-k2.5"

# Candidate selection filters for Boltz
min_qed: 0.50        # Minimum QED score (0-1)
min_pkd: 5.0         # Minimum predicted pKd value

# Optional: custom run ID (default: auto-generated timestamp)
run_id: "my_experiment"
```

The pipeline will:
1. **Extract** drug information using LLM (discovers drug name, UniProt ID, FASTA, SMILES)
2. **Pool** candidate molecules using REINVENT (Mol2Mol + Reinvent models)
3. **Iterate** through prediction (affinity + ADMET) and LLM-driven refinement
4. **Select** final candidates based on drug-likeness filters:
   - Oprea lead-likeness filter
   - At least 2 of 3 rules: Lipinski, Veber, Ghose
   - QED score >= `min_qed` (configurable)
   - Predicted pKd > `min_pkd` (configurable)
5. **Generate** 3D protein-ligand structures with Boltz (if enabled)

Results are saved in `runs/<run_id>/` with `boltz_candidates.csv` containing the final filtered candidates.


---

## Example Notebooks (v1.0 - Paper Reproduction)

> **Note:** To reproduce results from the paper, use [release v1.0](https://github.com/hoon-ock/llm-dd/releases/tag/V1)

Example Jupyter notebooks demonstrating step-by-step workflows are in `example/test_case/`:

- `1. extraction.ipynb` – Data extraction and retrieval
- `2. qna.ipynb` – Domain-specific question answering
- `3. pooling.ipynb` – Molecule pooling
- `4. prediction.ipynb` – Molecular property prediction
- `5. refinement.ipynb` – SMILES refinement
- `6. generation.ipynb` – Protein-ligand 3D structure generation

---

## License

This project is licensed under the MIT License.

---

## Notes

- Make sure to set up your API keys before running any LLM agent notebooks.
- For any additional dependencies (e.g., REINVENT4), follow the instructions above.
- If you encounter missing package errors, check that all dependencies in [requirements.txt](./requirements.txt) are installed.

---

## Citation

If you use **DiscoveryAgent** in your research or project, please cite:

(soon to be updated)

```bibtex
@article{ock2026discoveryagent,
author = {Ock, Janghoon and Meda, Radheesh Sharma and Badrinarayanan, Srivathsan and Aluru, Neha S. and Chandrasekhar, Achuth and Barati Farimani, Amir},
title = {Large Language Model Agent for Modular Task Execution in Drug Discovery},
journal = {Journal of Chemical Information and Modeling},
volume = {66},
number = {4},
pages = {2055-2068},
year = {2026},
doi = {10.1021/acs.jcim.5c02454},
    note ={PMID: 41662220},
URL = { 
        https://doi.org/10.1021/acs.jcim.5c02454
},
eprint = { 
        https://doi.org/10.1021/acs.jcim.5c02454
}
}
```
---

## Contact

For questions, suggestions, or support, please contact:  
Email: [jock@andrew.cmu.edu](mailto:jock@andrew.cmu.edu) & [rmeda@alumni.cmu.edu](mailto:rmeda@alumni.cmu.edu)
