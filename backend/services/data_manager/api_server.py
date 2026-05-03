"""
API server for Intelligent Target Discovery Agent.
Exposes /generate endpoint for Next.js frontend and /ask for QA assistant.
"""

import asyncio
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from io import BytesIO

from agent import IntelligentTargetDiscoveryAgent
from models import ContentType, ACPIntent, ACPRequest, ACPResponse
from config import cfg
from qa_assistant import QAAssistant
from report_generator import ReportGenerator


# ============================================================================
# Pydantic models
# ============================================================================

class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="User query for target discovery")
    top_k: int = Field(10, ge=1, le=50, description="Number of results to retrieve")
    data_types: List[str] = Field(
        default=["text", "pdf"],
        description="Allowed types: text, pdf, image, table"
    )
    intent: str = Field(
        default="refresh",
        description="ACP intent: refresh (to run extraction)"
    )

class GenerateResponse(BaseModel):
    success: bool
    result: str                          # formatted HTML report
    targets: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]        # deduplicated sources
    source_count: int
    validation_score: float
    session_id: str = ""                 # for the QA assistant
    error: Optional[str] = None

class AskRequest(BaseModel):
    session_id: str
    question: str

class AskResponse(BaseModel):
    answer: str

# ============================================================================
# In-memory storage for QA assistants and session data (use Redis in production)
# ============================================================================
_assistants: Dict[str, QAAssistant] = {}
_session_data: Dict[str, Dict[str, Any]] = {}   # session_id -> {"response": ACPResponse, "query": str}

# ============================================================================
# Lifespan manager for agent startup/shutdown
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.agent = IntelligentTargetDiscoveryAgent()
    await app.state.agent.start()
    print("✅ Intelligent Target Discovery Agent started")
    yield
    await app.state.agent.stop()
    print("🛑 Agent stopped")

app = FastAPI(
    title="Target Discovery Agent API",
    description="API for biomedical target discovery using PubMed, LLMs, and vector search",
    version="3.4",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Helper functions
# ============================================================================

def _map_data_types(types: List[str]) -> List[ContentType]:
    """Convert string data types to ContentType enum."""
    mapping = {
        "text": ContentType.TEXT,
        "pdf": ContentType.PDF,
        "image": ContentType.IMAGE,
        "table": ContentType.TABLE,
    }
    result = []
    for t in types:
        if t in mapping:
            result.append(mapping[t])
    return result if result else [ContentType.TEXT, ContentType.PDF]

def _deduplicate_sources(items: List[Dict]) -> List[Dict]:
    """Remove duplicates based on source_url. Preserves the first occurrence."""
    seen = set()
    unique = []
    for item in items:
        url = item.get("source_url", "")
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        unique.append(item)
    return unique

def _extract_targets_list(targets: List[Any]) -> List[Dict[str, Any]]:
    result = []
    for t in targets:
        if hasattr(t, 'to_dict'):
            d = t.to_dict()
        else:
            d = t
        if d and isinstance(d, dict):
            print(f"Target keys: {list(d.keys())[:10]}")
        result.append(d)
    return result

def _build_html_report(response: ACPResponse, prompt: str) -> str:
    """Generate beautifully formatted HTML from the agent's response."""
    # Collect all items and attach content type (for HTML display we don't need ctype)
    all_items = []
    for ctype, items in response.payload.items():
        # For HTML we don't need to store ctype per item, just extend
        all_items.extend(items)
    unique_sources = _deduplicate_sources(all_items)

    html = f"""
    <div class="space-y-5">
        <div class="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
            <p><strong>🔬 Validation Score:</strong> {response.validation_score:.3f}</p>
            <p><strong>📄 Unique Sources:</strong> {len(unique_sources)}</p>
        </div>
    """
    # Extracted targets
    if response.targets:
        html += '<div><h4 class="font-bold text-lg mb-2">🧬 Extracted Drug Targets</h4><div class="grid gap-3 md:grid-cols-2">'
        for target in response.targets[:10]:
            gene = target.get("gene", "Unknown")
            protein = target.get("protein", "")
            uniprot = target.get("uniprot_id", "")
            html += f"""
            <div class="border rounded-lg p-3 bg-white dark:bg-gray-800 shadow-sm">
                <div class="font-mono font-bold text-blue-700 dark:text-blue-300">{gene}</div>
                <div class="text-sm text-gray-600 dark:text-gray-400">{protein[:80]}</div>
                <div class="text-xs text-gray-500 mt-1">UniProt: {uniprot}</div>
            </div>
            """
        html += '</div></div>'
    else:
        html += '<div class="italic text-gray-500">ℹ️ No drug targets extracted for this query.</div>'
    # Sources
    if unique_sources:
        html += '<div class="mt-6"><h4 class="font-bold text-lg mb-2">📚 Top Sources</h4><ul class="space-y-2">'
        for src in unique_sources[:12]:
            title = src.get("title", "Untitled")
            url = src.get("source_url", "")
            pmid = src.get("pmid", "")
            html += f'<li class="border-l-4 border-primary pl-3"><a href="{url}" target="_blank" class="font-medium hover:underline">{title[:120]}</a>'
            if pmid:
                html += f' <span class="text-xs text-gray-500">PMID: {pmid}</span>'
            html += '</li>'
        html += '</ul></div>'
    html += '</div>'
    return html

# ============================================================================
# API endpoints
# ============================================================================

@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """
    Process a user prompt – uses REFRESH intent to force full target extraction.
    Creates a QA assistant for the session and stores the response for later report generation.
    """
    try:
        data_types = _map_data_types(request.data_types)
        
        # Build the ACPRequest with REFRESH
        acp_request = ACPRequest(
            source_agent="nextjs_frontend",
            query=request.prompt,
            data_types=data_types,
            filters={},
            intent=ACPIntent.REFRESH,
            top_k=request.top_k,
            require_fresh=True,
        )
        
        response = await app.state.agent.handle_request(acp_request)
        
        # Store the response and query for the session (for later report download)
        _session_data[response.session_id] = {
            "response": response,
            "query": request.prompt,
        }
        
        # ─────────────────────────────────────────────────────────────────────
        # Create QA assistant (Groq only)
        # ─────────────────────────────────────────────────────────────────────
        embed_service = getattr(app.state.agent, '_embed', None)
        qdrant_mgr    = getattr(app.state.agent, '_qdrant', None)
        
        if embed_service and qdrant_mgr:
            assistant = QAAssistant(
                groq_client=embed_service.groq,
                embed_service=embed_service,
                qdrant_mgr=qdrant_mgr,
            )
            assistant.load_session(response)
            _assistants[response.session_id] = assistant
            print(f"✅ Created QA assistant for session {response.session_id}")
        else:
            # Fallback to agent’s method
            assistant = await app.state.agent.create_qa_assistant(response)
            _assistants[response.session_id] = assistant
            print(f"⚠️ Created QA assistant via agent fallback")
        
        # ─────────────────────────────────────────────────────────────────────
        # Store content type on each source item during aggregation
        # so that later we can retrieve the correct type per source.
        # ─────────────────────────────────────────────────────────────────────
        all_items = []
        for ctype, items in response.payload.items():
            for item in items:
                # Attach the content type as a new field to each item
                item["content_type"] = ctype
            all_items.extend(items)
        
        unique_sources = _deduplicate_sources(all_items)
        
        sources_json = []
        for src in unique_sources[:15]:
            sources_json.append({
                "title": src.get("title", ""),
                "url": src.get("source_url", ""),
                "pmid": src.get("pmid", ""),
                "doi": src.get("doi", ""),
                "type": src.get("content_type", "unknown"),
            })
        
        html_report = _build_html_report(response, request.prompt)
        
        return GenerateResponse(
            success=True,
            result=html_report,
            targets=_extract_targets_list(response.targets),
            sources=sources_json,
            source_count=len(unique_sources),
            validation_score=response.validation_score,
            session_id=response.session_id,
        )
    except Exception as e:
        print(f"❌ Error in /generate: {e}")
        import traceback
        traceback.print_exc()
        return GenerateResponse(
            success=False,
            result="",
            targets=[],
            sources=[],
            source_count=0,
            validation_score=0.0,
            error=str(e),
        )

@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """
    Ask a question to the QA assistant for a given session.
    """
    assistant = _assistants.get(request.session_id)
    if not assistant:
        raise HTTPException(
            status_code=404,
            detail="No assistant found for this session. Please run a discovery query first."
        )
    try:
        answer_obj = await assistant.ask(request.question)
        return AskResponse(answer=answer_obj.to_text())
    except Exception as e:
        print(f"❌ Error in /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-report")
async def download_report(session_id: str):
    """
    Generate a properly formatted DOCX report for a completed discovery session.
    """
    data = _session_data.get(session_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please run a discovery query first."
        )
    
    acp_response = data["response"]
    query = data["query"]
    
    # Obtain Groq client from the agent (if available)
    groq_client = None
    embed_service = getattr(app.state.agent, '_embed', None)
    if embed_service and hasattr(embed_service, 'groq'):
        groq_client = embed_service.groq
    
    report_gen = ReportGenerator(groq_client=groq_client)
    
    # Generate the structured report (async)
    final_report = await report_gen.generate(
        response=acp_response,
        query=query,
        interim_ner={}   # TODO: pass actual NER data from pipeline if available
    )
    
    # Export to DOCX bytes
    docx_bytes = await report_gen.to_docx(final_report)
    
    # Return as downloadable file
    return StreamingResponse(
        BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="discovery_report_{session_id}.docx"'
        }
    )

@app.get("/health")
async def health():
    return {"status": "alive", "agent_ready": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )