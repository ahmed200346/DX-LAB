"""
utils/cache.py
Disk-based cache for LLM responses and PubMed results.

Why: During development you run the same query many times.
Without caching, every run costs Groq tokens and PubMed API calls.
With caching, repeated runs are instant and free.

Cache is stored as JSON files in output/cache/.
Each entry is keyed by a SHA-256 hash of the prompt.

Usage:
    from utils.cache import llm_cache

    result = llm_cache.get(prompt)
    if result is None:
        result = llm.invoke(prompt)
        llm_cache.set(prompt, result)
"""

import hashlib
import json
import os
import time
from typing import Any, Optional


class DiskCache:
    """
    Simple persistent key-value cache backed by JSON files.

    Each cache entry is a file: cache_dir/{sha256_of_key}.json
    Entries expire after `ttl_hours` hours (default: 24).
    """

    def __init__(
        self,
        cache_dir: str = None,
        ttl_hours: float = 24.0,
        enabled: bool = True,
    ):
        if cache_dir is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cache_dir = os.path.join(base, "output", "cache")
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        self.enabled = enabled
        os.makedirs(self.cache_dir, exist_ok=True)

    # ─────────────────────────────────────────
    # Public interface
    # ─────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """
        Return cached value for key, or None if missing/expired.
        """
        if not self.enabled:
            return None
        path = self._path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            if time.time() - entry["ts"] > self.ttl_seconds:
                os.remove(path)
                return None
            return entry["value"]
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def set(self, key: str, value: Any) -> None:
        """Store value for key."""
        if not self.enabled:
            return
        path = self._path(key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"ts": time.time(), "value": value}, f, ensure_ascii=False)
        except OSError:
            pass  # Cache write failure is non-fatal

    def invalidate(self, key: str) -> None:
        """Delete a specific cache entry."""
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    def clear_all(self) -> int:
        """Delete all cache entries. Returns number of files deleted."""
        count = 0
        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".json"):
                os.remove(os.path.join(self.cache_dir, fname))
                count += 1
        return count

    def stats(self) -> dict:
        """Return cache statistics."""
        files = [f for f in os.listdir(self.cache_dir) if f.endswith(".json")]
        total_size = sum(
            os.path.getsize(os.path.join(self.cache_dir, f)) for f in files
        )
        return {
            "entries": len(files),
            "size_kb": round(total_size / 1024, 1),
            "cache_dir": self.cache_dir,
        }

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────

    def _path(self, key: str) -> str:
        """Convert a cache key string to a file path."""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return os.path.join(self.cache_dir, f"{digest}.json")


# ─────────────────────────────────────────────────────────────
# Cached LLM call wrapper
# ─────────────────────────────────────────────────────────────

def cached_llm_invoke(chain, inputs: dict, cache: DiskCache) -> str:
    """
    Invoke a LangChain chain with caching.

    Args:
        chain: LangChain chain (prompt | llm)
        inputs: Dict of prompt template variables
        cache: DiskCache instance

    Returns:
        LLM response string (from cache or fresh API call)
    """
    from utils.rate_limiter import rate_limiter

    # Build a stable cache key that includes the prompt template so that
    # different agents using identical *inputs* don't share the same cache slot.
    try:
        prompt_id = chain.first.template if hasattr(chain, "first") and hasattr(chain.first, "template") else ""
    except Exception:
        prompt_id = ""

    key = json.dumps(
        {"prompt": prompt_id, "inputs": inputs},
        sort_keys=True,
        ensure_ascii=False,
    )

    cached = cache.get(key)
    if cached is not None:
        return cached

    # Not cached — call the API with rate limiting
    estimated_tokens = len(key) // 3 + 600  # rough estimate
    rate_limiter.wait_if_needed(estimated_tokens=estimated_tokens)

    response = chain.invoke(inputs)
    result = response.content if hasattr(response, "content") else str(response)

    # Record usage (approximate — Groq doesn't return token counts in streaming)
    rate_limiter.record(tokens_used=len(result) // 3 + 200)

    cache.set(key, result)
    return result


# Singleton instances
llm_cache = DiskCache(ttl_hours=24.0, enabled=True)
pubmed_cache = DiskCache(ttl_hours=6.0, enabled=True)   # shorter TTL for fresh literature