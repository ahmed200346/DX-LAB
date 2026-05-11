"""
api.py – FastAPI wrapper for the hypothesis generation pipeline
with session-based follow-up support.
"""

import sys
import os
import uuid
from pathlib import Path

_backend_root = Path(__file__).resolve().parents[2]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))
try:
    import dx_lab_env

    dx_lab_env.load_shared_dotenv()
except Exception:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import run_pipeline
from agents.memory_agent import MemoryAgent

app = FastAPI(title="Hypothesis Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In‑memory store for live sessions (use a database for production)
sessions = {}

class QueryRequest(BaseModel):
    query: str
    num_hypotheses: Optional[int] = 3

class AskRequest(BaseModel):
    session_id: str
    question: str

@app.post("/generate")
async def generate_hypotheses(req: QueryRequest):
    try:
        result = run_pipeline(req.query, req.num_hypotheses)
        # Remove non‑serializable objects
        result.pop("causal_graph", None)

        # Create a memory agent for follow‑up and store it
        session_id = str(uuid.uuid4())
        memory = MemoryAgent()
        memory.store_pipeline_result(result)
        sessions[session_id] = memory

        return {"success": True, "session_id": session_id, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask")
async def ask_followup(req: AskRequest):
    memory = sessions.get(req.session_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    try:
        answer = memory.follow_up(req.question)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8003, reload=True)