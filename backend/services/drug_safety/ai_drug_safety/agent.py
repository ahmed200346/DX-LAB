from typing import Dict, Any
from . import api_clients, risk_scoring, llm_reasoner

def run_agent(drug_input: str, patient_info: Dict[str, Any] = None, use_mock: bool = False) -> Dict[str, Any]:
    """
    Orchestrate data lookup, risk scoring and reasoning.
    All drug inputs are normalized to RXCUI for robust rule matching.
    Returns a structured result suitable for CLI or programmatic use.
    """
    if patient_info is None:
        patient_info = {}

    # Normalize input to RXCUI if possible
    from .rxnorm import get_rxcui
    rxcui = get_rxcui(drug_input)
    findings = api_clients.get_drug_data(drug_input, use_mock=use_mock)
    if rxcui:
        findings["rxcui"] = rxcui
    risk = risk_scoring.score_risk(findings, patient_info)
    analysis = llm_reasoner.analyze(findings, patient_info, risk)
    return {
        "drug": drug_input,
        "rxcui": rxcui,
        "findings": findings,
        "risk": risk,
        "analysis": analysis,
    }
