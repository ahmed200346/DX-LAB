try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

import os

import uvicorn

if __name__ == "__main__":
    # Default 8002 avoids collision with ITD / Data Manager on 8000 in the monorepo.
    port = int(os.getenv("DRUG_SAFETY_PORT", "8002"))
    host = os.getenv("DRUG_SAFETY_HOST", "127.0.0.1")
    uvicorn.run("ai_drug_safety.web:app", host=host, port=port, reload=False)
