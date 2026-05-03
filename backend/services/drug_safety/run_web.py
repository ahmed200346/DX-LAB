import os
import sys
from pathlib import Path

_backend_root = Path(__file__).resolve().parents[2]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))
try:
    import dx_lab_env

    dx_lab_env.load_shared_dotenv()
except Exception:
    pass

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
except Exception:
    pass

import uvicorn

if __name__ == "__main__":
    # Default 8002 avoids collision with ITD / Data Manager on 8000 in the monorepo.
    port = int(os.getenv("DRUG_SAFETY_PORT", "8002"))
    host = os.getenv("DRUG_SAFETY_HOST", "127.0.0.1")
    uvicorn.run("ai_drug_safety.web:app", host=host, port=port, reload=False)
