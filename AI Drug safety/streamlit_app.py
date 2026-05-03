#!/usr/bin/env python3
"""Streamlit UI for AI Drug Safety testing.

Run with:
  python -m pip install -r requirements-streamlit.txt
  streamlit run streamlit_app.py

This provides a single/multiple-drug and batch tester that calls the project's
`run_chain_agent` function and shows structured results.
"""
import os
import json
import time
import re
from typing import List

import streamlit as st

from ai_drug_safety.agent_chain import run_chain_agent

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def model_flags_major(res: dict) -> bool:
    findings = res.get("findings") or {}
    interactions = findings.get("interactions") or []
    for i in interactions:
        try:
            if isinstance(i, dict):
                sev = (i.get("severity") or "").lower()
                desc = (i.get("description") or "").lower()
                if "major" in sev or "major" in desc or "severe" in desc or "life-threatening" in desc:
                    return True
            else:
                text = str(i).lower()
                if "major" in text or "severe" in text:
                    return True
        except Exception:
            continue
    return False


def analyze_drug(drug: str, patient_info: dict, use_mock: bool):
    return run_chain_agent(drug, patient_info=patient_info, use_mock=use_mock)


def analyze_batch(drugs: List[str], patient_info: dict, use_mock: bool):
    results = []
    progress = st.progress(0)
    for i, d in enumerate(drugs):
        with st.spinner(f"Analyzing {d} ({i+1}/{len(drugs)})"):
            try:
                r = analyze_drug(d, patient_info, use_mock)
            except Exception as e:
                r = {"drug": d, "error": str(e)}
            results.append(r)
        progress.progress((i + 1) / len(drugs))
    return results


def parse_drugs_input(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"[;,\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def main():
    st.set_page_config(page_title="AI Drug Safety — Tester", layout="wide")
    st.title("AI Drug Safety — Test Interface")
    st.markdown("Enter one or multiple drug names (comma/semicolon/newline separated) to analyze side effects, interactions, and clinical risk scores.")

    col1, col2 = st.columns([2, 1])
    with col1:
        mode = st.radio("Mode", ("Single/Multiple", "Batch"))
        uploaded = None
        if mode == "Single/Multiple":
            drug_input = st.text_input("Drug name(s) — comma/semicolon/newline separated", value="aspirin")
            uploaded = st.file_uploader("Or upload a text/CSV file (one drug per line)", type=["txt", "csv"])
            if uploaded is not None:
                try:
                    drug_input = uploaded.read().decode("utf-8")
                except Exception:
                    st.error("Unable to read uploaded file.")
        else:
            drugs_text = st.text_area("Paste one drug per line", height=200)
            uploaded = st.file_uploader("Or upload a text/CSV file (one drug per line)", type=["txt", "csv"])
            if uploaded is not None:
                try:
                    drugs_text = uploaded.read().decode("utf-8")
                except Exception:
                    st.error("Unable to read uploaded file.")

    with col2:
        age = st.number_input("Patient age", min_value=0, max_value=130, value=65)
        sex = st.radio("Sex", ("female", "male"), index=0)
        conditions_raw = st.text_input("Patient conditions (comma-separated)", value="")

        with st.expander("Patient flags (optional)"):
            hypertension = st.checkbox("Hypertension", value=False)
            renal = st.checkbox("Renal dysfunction", value=False)
            liver = st.checkbox("Liver disease", value=False)
            stroke_history = st.checkbox("Stroke/TIA history", value=False)
            bleeding_history = st.checkbox("Bleeding history", value=False)
            labile_inr = st.checkbox("Labile INR", value=False)
            drugs_or_alcohol = st.checkbox("Drugs or alcohol risk", value=False)

        # Force real data usage (openFDA / real sources). Mock is disabled by request.
        use_mock = False
        llm_enabled = bool(os.getenv("OPENAI_API_KEY"))
        if llm_enabled:
            st.success("LLM enabled (OPENAI_API_KEY found).")
        else:
            st.warning("LLM disabled (OPENAI_API_KEY not set). Using deterministic reasoning.")
        run_btn = st.button("Analyze")

    conditions = [c.strip() for c in conditions_raw.split(",") if c.strip()]

    # Build patient_info mapping from UI
    patient_info = {
        "age": age,
        "sex": sex,
        "conditions": conditions,
        "hypertension": hypertension if 'hypertension' in locals() else False,
        "renal_dysfunction": renal if 'renal' in locals() else False,
        "liver_disease": liver if 'liver' in locals() else False,
        "stroke": stroke_history if 'stroke_history' in locals() else False,
        "bleeding_history": bleeding_history if 'bleeding_history' in locals() else False,
        "labile_inr": labile_inr if 'labile_inr' in locals() else False,
        "concomitant_antiplatelet": drugs_or_alcohol if 'drugs_or_alcohol' in locals() else False,
        "alcohol_use": drugs_or_alcohol if 'drugs_or_alcohol' in locals() else False,
        # `elderly` is derived from `age` (age >= 65) in clinical scoring; do not collect as a separate flag here.
    }

    if run_btn:
        if mode == "Single/Multiple":
            drugs = parse_drugs_input(drug_input)
            if not drugs:
                st.error("Please enter at least one drug name.")
            elif len(drugs) == 1:
                d = drugs[0]
                with st.spinner("Analyzing..."):
                    try:
                        res = analyze_drug(d, patient_info, use_mock)
                    except Exception as e:
                        st.exception(e)
                        return

                st.subheader("Result")
                st.write("Drug:", res.get("drug"))
                st.write("RXCUI:", res.get("rxcui"))
                sources = [(s.get("name") or "") for s in (res.get("findings") or {}).get("sources", [])]
                st.write("Sources:", sources)

                with st.expander("Full JSON"):
                    st.json(res)

                risk = res.get("risk") or {}
                if risk.get("clinical"):
                    st.subheader("Clinical Risk Scores")
                    st.write(risk.get("clinical"))

                findings = res.get("findings") or {}
                st.subheader("Side Effects")
                st.write(findings.get("side_effects") or [])
                st.subheader("Interactions")
                st.write(findings.get("interactions") or [])
            else:
                results = analyze_batch(drugs, patient_info, use_mock)
                st.success("Multi-drug analysis complete.")

                table = []
                for r in results:
                    table.append({
                        "drug": r.get("drug"),
                        "rxcui": r.get("rxcui"),
                        "major_flag": model_flags_major(r),
                        "has_sources": bool((r.get("findings") or {}).get("sources")),
                    })

                st.subheader("Summary")
                st.dataframe(table)

                with st.expander("Full results (JSON)"):
                    st.json(results)

                if st.button("Save results to evaluations"):
                    os.makedirs("evaluations", exist_ok=True)
                    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
                    outp = os.path.join("evaluations", f"evaluation_streamlit_{ts}.json")
                    with open(outp, "w", encoding="utf-8") as f:
                        json.dump({"summary": {"n_drugs": len(drugs)}, "results": results}, f, indent=2, ensure_ascii=False)
                    st.success(f"Saved to {outp}")
        else:
            # Batch path (paste/upload)
            drugs = []
            if 'drugs_text' in locals():
                drugs = [d.strip() for d in (drugs_text or "").splitlines() if d.strip()]
            if uploaded is not None and not drugs:
                try:
                    content = uploaded.read().decode("utf-8")
                    drugs = [d.strip() for d in content.splitlines() if d.strip()]
                except Exception:
                    pass
            if not drugs:
                st.error("Please paste or upload a list of drugs for batch mode.")
            else:
                results = analyze_batch(drugs, patient_info, use_mock)
                st.success("Batch analysis complete.")

                table = []
                for r in results:
                    table.append({
                        "drug": r.get("drug"),
                        "rxcui": r.get("rxcui"),
                        "major_flag": model_flags_major(r),
                        "has_sources": bool((r.get("findings") or {}).get("sources")),
                    })

                st.subheader("Summary")
                st.dataframe(table)

                with st.expander("Full results (JSON)"):
                    st.json(results)

                if st.button("Save results to evaluations"):
                    os.makedirs("evaluations", exist_ok=True)
                    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
                    outp = os.path.join("evaluations", f"evaluation_streamlit_{ts}.json")
                    with open(outp, "w", encoding="utf-8") as f:
                        json.dump({"summary": {"n_drugs": len(drugs)}, "results": results}, f, indent=2, ensure_ascii=False)
                    st.success(f"Saved to {outp}")


if __name__ == "__main__":
    main()
