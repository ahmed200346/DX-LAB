import os
import json
import re
from typing import Dict, Any, Optional


def analyze_with_langchain(findings: Dict[str, Any], patient_info: Dict[str, Any], risk: Dict[str, Any], model_name: str = "gpt-3.5-turbo", temperature: float = 0.0) -> Dict[str, Any]:
    """
    Use LangChain + OpenAI to synthesize a clinical-style decision.

    Requires `OPENAI_API_KEY` in the environment and `langchain` + `openai`
    installed. Returns a dict with keys: `conclusion`, `recommendation`,
    `reasons`, `explanation`.
    """
    try:
        try:
            # langchain v0.0x path
            from langchain.llms import OpenAI as LangOpenAI
        except Exception:
            # older/newer alias
            from langchain import OpenAI as LangOpenAI
        from langchain.prompts import PromptTemplate
        from langchain.chains import LLMChain
    except Exception as e:
        raise RuntimeError("langchain is not available") from e

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    payload = {
        "drug": findings.get("name"),
        "side_effects": findings.get("side_effects", []),
        "interactions": findings.get("interactions", []),
        "warnings": findings.get("warnings", []),
        "patient": patient_info,
        "risk": risk,
    }
    payload_text = json.dumps(payload, indent=2, ensure_ascii=False)

    template = (
        "You are a clinical decision support assistant.\n"
        "Given the following structured data, produce a concise JSON object with these keys:\n"
        "- conclusion: one of (Low risk, Moderate risk, High risk)\n"
        "- recommendation: one short sentence for a clinician or pharmacist\n"
        "- reasons: a short list of 1-5 concise reasons derived only from the data (cite the data field in the payload)\n"
        "- explanation: one paragraph describing the reasoning and any important caveats\n\n"
        "Optional keys (include if available):\n"
        "- confidence: integer 0-100 indicating confidence in the conclusion\n"
        "- assumptions: list of any missing-data assumptions made by the model\n"
        "- naranjo_score: numeric estimate of causality if the model can derive it\n\n"
        "Important instructions:\n"
        "- Use the structured `risk` data (HAS-BLED, Tisdale) as primary evidence; if you disagree with the numeric scores, explain why.\n"
        "- When referring to patient attributes, use the field names from `patient` (e.g., patient.sex, patient.age, patient.conditions).\n"
        "- Explicitly consider the patient's sex when it affects risk (for example, female sex increases QT/Tisdale risk); if sex is missing, state the assumption.\n"
        "- Base each reason on a specific data point from the payload (e.g., 'Tisdale: baseline_qtc_high', 'Interaction: warfarin + aspirin — major').\n\n"
        "Data:\n{payload}\n\n"
        "Return JSON only and nothing else."
    )

    prompt = PromptTemplate(input_variables=["payload"], template=template)

    llm = LangOpenAI(temperature=temperature, model_name=model_name)
    chain = LLMChain(llm=llm, prompt=prompt)
    # Run the chain and try to parse JSON output robustly
    output = chain.run(payload=payload_text)

    # Direct JSON parse
    try:
        return json.loads(output.strip())
    except Exception:
        # Extract first JSON-looking block
        m = re.search(r"\{.*\}", output, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    raise RuntimeError("LLM did not return valid JSON")
