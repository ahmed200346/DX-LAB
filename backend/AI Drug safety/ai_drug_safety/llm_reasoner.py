import os
import json
from typing import Dict, Any
from . import risk_scoring


def _deterministic_analysis(findings: Dict[str, Any], patient_info: Dict[str, Any], risk: Dict[str, Any]) -> Dict[str, Any]:
    score = risk.get("score", 0) if isinstance(risk, dict) else int(risk or 0)
    if score >= 60:
        conclusion = "High risk"
        recommendation = "Avoid prescribing; seek alternatives."
    elif score >= 30:
        conclusion = "Moderate risk"
        recommendation = "Use with caution; monitor closely."
    else:
        conclusion = "Low risk"
        recommendation = "Likely safe for typical patients."

    reasons = []
    if findings.get("interactions"):
        reasons.append(f"{len(findings['interactions'])} reported interaction(s)")
    if findings.get("side_effects"):
        reasons.append(f"{len(findings['side_effects'])} documented side effect(s)")
    reasons.extend([f"condition:{c}" for c in (patient_info.get("conditions") or [])])

    explanation = f"Computed risk score {score}; factors: {', '.join(risk.get('factors', []))}"

    return {
        "conclusion": conclusion,
        "recommendation": recommendation,
        "reasons": reasons,
        "explanation": explanation,
    }


def analyze(findings: Dict[str, Any], patient_info: Dict[str, Any], risk: Dict[str, Any]) -> Dict[str, Any]:
    """
    High-level analyze function: prefer LangChain+OpenAI when available
    (requires `OPENAI_API_KEY` and `langchain` installed). Falls back to
    deterministic rules when LLM is not available or returns invalid output.
    """
    # Prefer LangChain-based reasoning when API key is present
    if os.getenv("OPENAI_API_KEY"):
        try:
            from .llm_integration import analyze_with_langchain

            result = analyze_with_langchain(findings, patient_info, risk)
            # basic validation of result shape
            if isinstance(result, dict) and {"conclusion", "recommendation", "reasons", "explanation"}.issubset(result.keys()):
                return result
        except Exception:
            # On any failure, fall back to deterministic analysis
            pass

    return _deterministic_analysis(findings, patient_info, risk)
