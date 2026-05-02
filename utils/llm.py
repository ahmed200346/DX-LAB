"""
utils/llm.py (Ollama provider)
Uses a local Ollama model – no rate limits, no API keys.
"""

import os
from typing import Optional, List

from langchain_ollama import OllamaLLM
from langchain_core.language_models.llms import LLM
from dotenv import load_dotenv

load_dotenv()


class LocalOllamaLLM(OllamaLLM):
    """
    Thin wrapper around LangChain's OllamaLLM, so our factory functions
    can still return a consistent LLM type.
    """

    # Fix the temperature issue: OllamaLLM expects temperature as 'temperature'
    # (It's already a field in the parent class, we just need to pass it correctly.)
    # We'll override _call not needed – just keep parent behaviour.
    pass


# ─── Factory functions ────────────────────────────────

def get_llm(temperature: float = 0.2, model_name: str = None) -> LocalOllamaLLM:
    model = model_name or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    return LocalOllamaLLM(
        model=model,
        temperature=temperature,
        num_predict=2048,   # max tokens to generate
    )


def get_analysis_llm() -> LocalOllamaLLM:
    """Lower temperature for deterministic JSON extraction."""
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    return LocalOllamaLLM(
        model=model,
        temperature=0.0,
        num_predict=1500,
        system=(
            "You are a biomedical NLP system. "
            "Always return valid JSON. No markdown, no explanation."
        ),
    )


def get_hypothesis_llm() -> LocalOllamaLLM:
    """Higher temperature for creative hypothesis generation."""
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    return LocalOllamaLLM(
        model=model,
        temperature=0.75,
        num_predict=4096,
        system=(
            "You are a world-class research strategist and scientific innovator. "
            "Generate bold, specific, mechanistically grounded hypotheses. "
            "Always follow the exact output format requested."
        ),
        # Chain‑of‑thought is built into our prompt wrapper
    )