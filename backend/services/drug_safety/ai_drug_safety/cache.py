"""Simple file-based cache used by the agent orchestration.

Cache entries are stored in the project `.cache/` directory as JSON files
named by SHA256(prefix + canonical_json(payload)). Each entry stores the
creation timestamp, optional TTL (seconds), and the stored value as JSON.
"""
import os
import json
import time
import hashlib
from typing import Any, Optional


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_DIR = os.path.join(PROJECT_ROOT, ".cache")


def _ensure_cache_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def make_cache_key(prefix: str, payload: Any) -> str:
    s = f"{prefix}:{_canonical_json(payload)}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.json")


def get(prefix: str, payload: Any) -> Optional[Any]:
    _ensure_cache_dir()
    key = make_cache_key(prefix, payload)
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        ts = float(rec.get("ts", 0))
        ttl = rec.get("ttl")
        if ttl is not None:
            try:
                ttl_f = float(ttl)
            except Exception:
                ttl_f = None
            if ttl_f is not None and time.time() > ts + ttl_f:
                try:
                    os.remove(path)
                except Exception:
                    pass
                return None
        return rec.get("value")
    except Exception:
        return None


def set(prefix: str, payload: Any, value: Any, ttl: Optional[float] = None) -> None:
    _ensure_cache_dir()
    key = make_cache_key(prefix, payload)
    path = _cache_path(key)
    rec = {"ts": time.time(), "ttl": ttl, "value": value}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
    except Exception:
        pass
