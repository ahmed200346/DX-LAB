# AI Drug Safety Agent

This repository contains a Python scaffold for an AI Drug Safety Agent that
fetches real drug data (openFDA / optional DrugBank), computes clinical risk
scores (HAS-BLED, Tisdale), and synthesizes a concise clinical recommendation
using an LLM when available.

Requirements
------------

Install dependencies into a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Quick start
-----------

Run the Streamlit tester UI:

```bash
streamlit run streamlit_app.py
```

Run the FastAPI web shim (optional):

```bash
```

CLI example:

```bash
python -m ai_drug_safety.cli aspirin --age 70 --conditions "hypertension"
```

Environment / secrets
---------------------

Set `OPENAI_API_KEY` and `DRUGBANK_API_KEY` in your local environment or a
`.env` file at the project root. IMPORTANT: do not commit secrets. The
repository `.gitignore` contains `.env` and `.venv` entries — ensure you do not
push actual API keys to GitHub.

What I changed for you
----------------------

- Added `requirements.txt` with core dependencies.
- Updated the Streamlit UI to accept `sex` and relevant clinical flags.
- Improved the LLM prompt to request `confidence` and `assumptions` fields
	and explicitly consider `patient.sex` when relevant.

What to keep (recommended)
--------------------------

- `ai_drug_safety/` — core package and clinical logic (keep).
- `evaluations/` — adjudicated gold and annotation CSVs (keep for evaluation).
- `streamlit_app.py` — interactive tester UI (keep if you use it).

Optional files you can remove
----------------------------

- `run_example.py` — tiny demo script (non-essential).
- `.cache/` — cache files from previous runs (safe to remove if you want a clean repo).
- `__pycache__/` directories — Python bytecode caches (safe to remove).

Pushing to GitHub
------------------

Before you push, ensure:
- `.env` does not contain secrets (remove or redact keys).
- `.venv/` is not committed (use `.gitignore`).

If you want, I can remove non-essential files now (e.g., `run_example.py`, `.cache/`).
