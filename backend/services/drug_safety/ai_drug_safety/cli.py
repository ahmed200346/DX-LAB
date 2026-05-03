try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

import argparse
import json
from .agent import run_agent


def main():
    parser = argparse.ArgumentParser(description="AI Drug Safety Agent CLI")
    parser.add_argument("drug", help="Drug name or prescription text")
    parser.add_argument("--age", type=int, default=0, help="Patient age")
    parser.add_argument("--conditions", type=str, default="", help="Comma-separated conditions")
    # Mock data removed; CLI always uses real data sources.
    args = parser.parse_args()
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    patient = {"age": args.age, "conditions": conditions}
    res = run_agent(args.drug, patient_info=patient, use_mock=False)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
