"""NVIDIA NIM chat + embeddings (OpenAI-compatible API)."""
from __future__ import annotations

import os
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from configs import tool_globals


def llm_api_key() -> str:
    key = (os.getenv("LLM_API_KEY") or os.getenv("NVIDIA_API_KEY") or "").strip()
    if key:
        return key
    try:
        from configs import secret_keys

        sk = getattr(secret_keys, "llm_api_key", None)
        if sk and str(sk).strip():
            return str(sk).strip()
    except Exception:
        pass
    raise ValueError(
        "Set LLM_API_KEY or NVIDIA_API_KEY in the environment, or llm_api_key in configs/secret_keys.py"
    )


def chat_llm(
    model: Optional[str] = None,
    *,
    temperature: float = 0.1,
    timeout: float = 1000.0,
    max_tokens: Optional[int] = 4096,
    **kwargs,
) -> ChatOpenAI:
    return ChatOpenAI(
        model=model or tool_globals.LLM_MODEL,
        temperature=temperature,
        api_key=llm_api_key(),
        base_url=tool_globals.NVIDIA_API_BASE,
        timeout=timeout,
        max_tokens=max_tokens,
        **kwargs,
    )


def embeddings_client() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=tool_globals.EMBEDDING_MODEL,
        api_key=llm_api_key(),
        base_url=tool_globals.NVIDIA_API_BASE,
    )
