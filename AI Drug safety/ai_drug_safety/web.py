try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from typing import Optional
    has_fastapi = True
except Exception:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    Optional = None
    has_fastapi = False

from .agent_chain import run_chain_agent


if has_fastapi:
    app = FastAPI(title="AI Drug Safety Agent")

    _INDEX_HTML = """
    <!doctype html>
    <html>
      <head><meta charset="utf-8"><title>AI Drug Safety</title></head>
      <body>
        <h1>AI Drug Safety — Quick Check</h1>
        <form action="/analyze" method="get">
          <label>Drug name: <input name="drug" value="aspirin"/></label><br/>
          <label>Age: <input name="age" value="65"/></label><br/>
          <label>Conditions (comma-separated): <input name="conditions" value="hypertension"/></label><br/>
          <!-- Use mock data option removed: app always uses real data -->
          <button type="submit">Analyze</button>
        </form>
        <p>Use the `/analyze` endpoint programmatically for JSON results.</p>
      </body>
    </html>
    """


    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _INDEX_HTML


    @app.get("/analyze")
    async def analyze(drug: str, age: Optional[int] = 0, conditions: Optional[str] = ""):
      """Analyze a drug for a given (optional) patient profile. Uses real sources.

      Query params:
      - `drug` (required)
      - `age` (optional int)
      - `conditions` (optional comma-separated list)
      """
      patient = {"age": int(age or 0), "conditions": [c.strip() for c in (conditions or "").split(",") if c.strip()]}
      result = run_chain_agent(drug, patient_info=patient, use_mock=False)
      return JSONResponse(result)
else:
    # Provide a helpful import-time message when FastAPI is not installed.
    app = None

