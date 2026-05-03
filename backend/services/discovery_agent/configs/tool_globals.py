import os

# global variables for retrieval task
UNIPROT_NUM_IDS = 1 # Number of UniProt IDs to retrieve
MAX_PAPERS = 10 # Number of papers to download for molecule optimization guideline
PAPER_DIR = "papers"

# LLM via NVIDIA NIM (OpenAI-compatible: https://integrate.api.nvidia.com/v1)
LLM_PROVIDER = "nvidia"
LLM_MODEL = "moonshotai/kimi-k2.5"
NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
# NIM embedding model (change in NVIDIA catalog if this ID updates)
EMBEDDING_MODEL = "nvidia/nv-embedqa-e5-v5"
# Vector size for EMBEDDING_MODEL (must match the model’s output; used for FAISS without a probe call at init)
EMBEDDING_DIM = 1024

# global variables for generation task
POOL_PATH = "pool"
# Local install path for REINVENT4 (required for pooling). Override with env REINVENT_PATH.
_REINVENT_DEFAULT = "/home/hoon/dd-agent/REINVENT4"
REINVENT_PATH = os.getenv("REINVENT_PATH", "").strip() or _REINVENT_DEFAULT

# global variables for prediction task
ADMET_WAIT_INTERVAL = 30
ADMET_MAX_WAIT_TIME = 500
PROPERTY_DIR = "property"