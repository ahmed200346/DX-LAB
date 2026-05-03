"""
Shared monorepo environment: load one `backend/.env` and map a single API key
to the names each stack expects (LLM / OpenAI-compatible / NVIDIA NIM).
"""

from __future__ import annotations

import os
from pathlib import Path


def _backend_dir() -> Path:
    return Path(__file__).resolve().parent


def load_shared_dotenv() -> None:
    """Load `backend/.env` (and optional repo-root `.env`) without overriding existing env."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    backend = _backend_dir()
    for path in (backend / ".env", backend.parent / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)

    key = (
        (os.getenv("DX_LAB_API_KEY") or "").strip()
        or (os.getenv("API_KEY") or "").strip()
    )
    if not key:
        return
    for name in ("LLM_API_KEY", "OPENAI_API_KEY", "NVIDIA_API_KEY"):
        if not (os.getenv(name) or "").strip():
            os.environ[name] = key
