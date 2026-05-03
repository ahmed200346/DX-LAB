import os
from pathlib import Path
from datetime import datetime

_DEBUG_LOG = Path(__file__).resolve().parent / "debug_agent.log"

def _debug_log(msg: str):
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass
