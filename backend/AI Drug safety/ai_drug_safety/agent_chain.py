"""Simple orchestrator that chains tools and caches intermediate results.

This module performs tool chaining in a deterministic sequence:
  1. `get_drug_data(drug_name)`
  2. `score_risk(findings, patient_info)`
  3. `analyze(findings, patient_info, risk)` (LLM via LangChain when available)

All intermediate results are cached (file-based) to reduce repeated API
calls and LLM usage. If `OPENAI_API_KEY` is not set or the LangChain LLM
call fails, a deterministic fallback analyzer is used.
"""
import os
import json
from typing import Dict, Any, Optional

from .cache import get as cache_get, set as cache_set


def run_chain_agent(
    drug_input: str,
    patient_info: Optional[Dict[str, Any]] = None,
    use_mock: bool = False,
    model_name: str = "gpt-3.5-turbo",
    temperature: float = 0.0,
    cache_ttl: float = 60 * 60 * 24,
) -> Dict[str, Any]:
    """
    Run the orchestrator: fetch drug data, score risk, synthesize analysis.

    - `cache_ttl` controls how long (in seconds) cached entries remain valid.
    - Falls back to `ai_drug_safety.agent.run_agent` if an error occurs.
    """
    if patient_info is None:
        patient_info = {}

    try:
        # Normalize input to RXCUI if possible
        from .rxnorm import get_rxcui
        rxcui = get_rxcui(drug_input)
    except Exception:
        rxcui = None

    try:
        # 1) Findings (cached by drug name or RXCUI)
        cache_key = rxcui if rxcui else drug_input
        findings = cache_get("get_drug_data", cache_key)
        if findings is None:
            from .api_clients import get_drug_data
            findings = get_drug_data(drug_input, use_mock=use_mock)
            if rxcui:
                findings["rxcui"] = rxcui
            cache_set("get_drug_data", cache_key, findings, ttl=cache_ttl)
        else:
            if rxcui:
                findings["rxcui"] = rxcui

        # 2) Risk scoring (cached by findings + patient)
        risk_key_obj = {"findings": findings, "patient": patient_info}
        risk = cache_get("score_risk", risk_key_obj)
        if risk is None:
            from .risk_scoring import score_risk
            risk = score_risk(findings, patient_info)
            cache_set("score_risk", risk_key_obj, risk, ttl=cache_ttl)

        # 3) Analysis (prefer LLM via LangChain, cached)
        analysis_key_obj = {"findings": findings, "patient": patient_info, "risk": risk}
        analysis = cache_get("analysis", analysis_key_obj)
        if analysis is None:
            # try LangChain-based LLM analysis when API key is present
            if os.getenv("OPENAI_API_KEY"):
                try:
                    from .llm_integration import analyze_with_langchain
                    analysis = analyze_with_langchain(findings, patient_info, risk, model_name=model_name, temperature=temperature)
                except Exception:
                    from .llm_reasoner import analyze as _deterministic_analyze
                    analysis = _deterministic_analyze(findings, patient_info, risk)
            else:
                from .llm_reasoner import analyze as _deterministic_analyze
                analysis = _deterministic_analyze(findings, patient_info, risk)

            # normalize analysis to dict (in case LLM returned string)
            if isinstance(analysis, str):
                try:
                    analysis = json.loads(analysis)
                except Exception:
                    analysis = {"text": analysis}

            cache_set("analysis", analysis_key_obj, analysis, ttl=cache_ttl)

        return {"drug": drug_input, "rxcui": rxcui, "findings": findings, "risk": risk, "analysis": analysis}
    except Exception:
        # On any failure, fall back to the simple synchronous orchestrator
        from .agent import run_agent as _local_run
        return _local_run(drug_input, patient_info=patient_info, use_mock=use_mock)
