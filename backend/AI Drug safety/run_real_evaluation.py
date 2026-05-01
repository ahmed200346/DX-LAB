#!/usr/bin/env python3
"""Simple real-data evaluation harness.

Runs the agent on a small list of real drugs (or a provided file) using
`use_mock=False` and reports operational metrics useful for clinical
evaluation (mapping coverage, OpenFDA availability, counts of interactions/SEs).

This is a lightweight smoke/evaluation script — for formal clinical
evaluation follow the spec in the TODOs and create an annotated gold set.
"""
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import argparse
import json
import os
import time
from datetime import datetime

from ai_drug_safety.agent_chain import run_chain_agent


def load_drugs(path: str):
    if not path:
        return ["aspirin", "warfarin", "ibuprofen", "metformin", "lisinopril"]
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def summarize(results):
    n = len(results)
    mapped = sum(1 for r in results if r.get("rxcui"))
    openfda_label = sum(1 for r in results if any("openfda" in (s.get("name","") or "").lower() for s in r.get("findings",{}).get("sources",[])))
    any_source = sum(1 for r in results if r.get("findings") and r["findings"].get("sources"))
    total_interactions = sum(len(r.get("findings",{}).get("interactions",[])) for r in results)
    total_side_effects = sum(len(r.get("findings",{}).get("side_effects",[])) for r in results)
    risk_scores = [r.get("risk", {}).get("score") for r in results if r.get("risk") and isinstance(r.get("risk").get("score"), (int, float))]
    avg_risk = sum(risk_scores)/len(risk_scores) if risk_scores else None
    return {
        "n_drugs": n,
        "rxcui_mapped": mapped,
        "rxcui_coverage": mapped / n if n else 0,
        "openfda_label_count": openfda_label,
        "any_source_count": any_source,
        "avg_interactions_per_drug": total_interactions / n if n else 0,
        "avg_side_effects_per_drug": total_side_effects / n if n else 0,
        "avg_risk_score": avg_risk,
    }


def main():
    parser = argparse.ArgumentParser(description="Run a small real-data evaluation.")
    parser.add_argument("--drugs-file", help="Optional file with one drug name per line")
    parser.add_argument("--out-dir", default="evaluations", help="Directory to write results")
    parser.add_argument("--age", type=int, default=65, help="Default patient age for risk scoring")
    args = parser.parse_args()

    drugs = load_drugs(args.drugs_file)
    os.makedirs(args.out_dir, exist_ok=True)
    results = []
    for d in drugs:
        print(f"Querying: {d}")
        try:
            res = run_chain_agent(d, patient_info={"age": args.age, "conditions": []}, use_mock=False)
            results.append(res)
        except Exception as e:
            results.append({"drug": d, "error": str(e)})
        time.sleep(0.2)

    summary = summarize(results)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(args.out_dir, f"evaluation_real_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2, ensure_ascii=False)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Saved full results to: {out_path}")


if __name__ == "__main__":
    main()
