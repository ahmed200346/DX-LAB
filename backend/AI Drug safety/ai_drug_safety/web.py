try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from typing import Optional, List
    has_fastapi = True
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    Optional = None
    CORSMiddleware = None
    has_fastapi = False

from .agent_chain import run_chain_agent

if has_fastapi:
    app = FastAPI(title="AI Drug Safety Agent")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _INDEX_HTML = """
    <!doctype html>
    <html>
      <head><meta charset="utf-8"><title>AI Drug Safety</title></head>
      <body>
        <h1>AI Drug Safety — Multi‑drug Check</h1>
        <form action="/analyze-multi" method="get">
          <label>Drugs (comma‑separated): <input name="drugs" value="aspirin,warfarin"/></label><br/>
          <label>Age: <input name="age" value="65"/></label><br/>
          <label>Conditions: <input name="conditions" value="hypertension"/></label><br/>
          <button type="submit">Analyze</button>
        </form>
      </body>
    </html>
    """

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _INDEX_HTML

    def normalize_drug_name(name: str) -> str:
        """Lowercase, strip punctuation/spaces, keep only alphanumeric and spaces."""
        import re
        name = name.lower()
        name = re.sub(r'[^\w\s]', '', name)
        return name.strip()

    def extract_interaction_targets(text: str) -> List[str]:
        """
        Extract drug names or classes from interaction text.
        Returns normalized list of unique targets.
        """
        if not text:
            return []
        import re
        targets = set()
        lower_text = text.lower()

        # 1. Look for "Examples:", "such as", "e.g.", "including"
        patterns = [
            r'(?:Examples?|such as|e\.g\.|including):?\s*([^.]+(?:\.\s*[A-Za-z][^.]*)?)',
            r'([A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+)*)\s+(?:is|are|may|can)'
        ]
        for pat in patterns:
            for match in re.finditer(pat, text, re.IGNORECASE):
                chunk = match.group(1)
                # split by commas, "and", "or", bullet
                candidates = re.split(r',|\band\b|\bor\b|•|\n', chunk)
                for cand in candidates:
                    cand = cand.strip().strip('*•-')
                    if 2 < len(cand) < 50 and not cand.lower().startswith('table'):
                        targets.add(normalize_drug_name(cand))

        # 2. Bullet points or numbered lists
        bullet_items = re.findall(r'(?:^|\n)\s*[•\-*○§#\d.]+\s*([A-Za-z][A-Za-z\s]+?)(?=\n|$)', text)
        for item in bullet_items:
            drug = item.strip()
            if 2 < len(drug) < 50 and not drug.lower().startswith('table'):
                targets.add(normalize_drug_name(drug))

        # 3. Known high‑risk drug classes (broad)
        classes = [
            "carbonic anhydrase inhibitors", "topiramate", "zonisamide", "acetazolamide", "dichlorphenamide",
            "ranolazine", "vandetanib", "dolutegravir", "cimetidine", "alcohol", "insulin secretagogues",
            "sulfonylurea", "insulin", "thiazides", "corticosteroids", "phenothiazines", "estrogens",
            "oral contraceptives", "phenytoin", "nicotinic acid", "sympathomimetics", "calcium channel blockers",
            "isoniazid", "cyclosporine", "gemfibrozil", "rifampin", "clarithromycin", "itraconazole",
            "ketoconazole", "erythromycin", "colchicine", "niacin", "grapefruit juice", "warfarin",
            "aspirin", "clopidogrel", "digoxin", "atorvastatin", "simvastatin", "metformin", "ibuprofen"
        ]
        for cls in classes:
            if cls in lower_text:
                targets.add(normalize_drug_name(cls))

        return list(targets)

    def check_cross_interactions(results: List[dict]) -> List[dict]:
        """Compare each drug's interaction targets with other drugs in the list."""
        cross = []
        # Build dict: drug_name -> set of normalized target names
        drug_targets = {}
        drug_names_lower = {}  # original -> normalized
        for r in results:
            drug = r.get("drug", "")
            if not drug:
                continue
            norm_drug = normalize_drug_name(drug)
            drug_names_lower[drug] = norm_drug
            findings = r.get("findings", {})
            interactions = findings.get("interactions", [])
            if isinstance(interactions, list) and interactions and isinstance(interactions[0], dict):
                desc = interactions[0].get("description", "")
            elif isinstance(interactions, str):
                desc = interactions
            else:
                desc = ""
            targets = extract_interaction_targets(desc)
            drug_targets[norm_drug] = set(targets)
        
        # Check each pair
        drugs = list(drug_targets.keys())
        for i, d1 in enumerate(drugs):
            for j, d2 in enumerate(drugs):
                if i >= j:
                    continue
                # Look for d1 in d2's targets or d2 in d1's targets
                if d1 in drug_targets.get(d2, set()) or d2 in drug_targets.get(d1, set()):
                    cross.append({
                        "drug_a": d1.capitalize(),
                        "drug_b": d2.capitalize(),
                        "severity": "Potential interaction",
                        "description": f"{d1.capitalize()} and {d2.capitalize()} may interact based on FDA labeling. Please review individual interaction sections for details."
                    })
        return cross

    @app.get("/analyze-multi")
    async def analyze_multi(
        drugs: str = Query(..., description="Comma‑separated list of drug names"),
        age: Optional[int] = 0,
        conditions: Optional[str] = "",
        hypertension: bool = False,
        renal_dysfunction: bool = False,
        liver_disease: bool = False,
        stroke: bool = False,
        bleeding_history: bool = False,
        labile_inr: bool = False,
        alcohol_use: bool = False,
    ):
        """Analyze multiple drugs and return per‑drug results plus detected cross‑interactions."""
        drug_list = [d.strip() for d in drugs.split(",") if d.strip()]
        if not drug_list:
            return JSONResponse({"error": "No drugs provided"}, status_code=400)

        # Build patient info once (same for all drugs)
        cond_list = [c.strip() for c in (conditions or "").split(",") if c.strip()]
        if hypertension:
            cond_list.append("hypertension")
        if renal_dysfunction:
            cond_list.append("renal dysfunction")
        if liver_disease:
            cond_list.append("liver disease")
        if stroke:
            cond_list.append("stroke")
        if bleeding_history:
            cond_list.append("bleeding history")
        if labile_inr:
            cond_list.append("labile INR")
        if alcohol_use:
            cond_list.append("alcohol use")
        patient = {"age": int(age or 0), "conditions": cond_list}

        results = []
        for drug in drug_list:
            try:
                res = run_chain_agent(drug, patient_info=patient, use_mock=False)
                results.append(res)
            except Exception as e:
                results.append({"drug": drug, "error": str(e)})

        cross_interactions = check_cross_interactions(results)
        return JSONResponse({
            "results": results,
            "cross_interactions": cross_interactions
        })

else:
    app = None