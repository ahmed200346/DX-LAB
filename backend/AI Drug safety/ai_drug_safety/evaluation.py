"""Evaluation utilities for AI Drug Safety.

Compute clinical metrics (sensitivity/precision for major interactions,
Naranjo concordance, mapping coverage, evidence support) against a
gold-standard CSV and previously-run agent results (JSON in `evaluations/`).

Usage:
  python -m ai_drug_safety.evaluation --gold evaluations/gold_standard_sample.csv --results-dir evaluations
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple


def load_latest_results(results_dir: str) -> str:
    pattern = os.path.join(results_dir, "evaluation_real_*.json")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"No results files found in {results_dir}")
    files.sort()
    return files[-1]


def load_results(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results") or []


def load_gold_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [r for r in reader]


def _model_flags_major(result: Dict) -> bool:
    findings = result.get("findings") or {}
    interactions = findings.get("interactions") or []
    for i in interactions:
        if isinstance(i, dict):
            sev = (i.get("severity") or "").lower()
            desc = (i.get("description") or "").lower()
            if "major" in sev or "major" in desc or "severe" in desc or "life-threatening" in desc:
                return True
        else:
            text = str(i).lower()
            if "major" in text or "severe" in text:
                return True
    return False


def _match_result(gold_row: Dict[str, str], results: List[Dict]) -> Optional[Dict]:
    # Prefer RXCUI matching when available
    gdrug = (gold_row.get("drug") or "").strip().lower()
    grxcui = (gold_row.get("rxcui") or "").strip()
    for r in results:
        # r could be an error dict
        if not isinstance(r, dict):
            continue
        rdrug = (r.get("drug") or "").strip().lower()
        if grxcui and r.get("rxcui") and str(r.get("rxcui")).strip() == grxcui:
            return r
        if gdrug and rdrug and gdrug == rdrug:
            return r
        # check normalized findings name
        findings = r.get("findings") or {}
        fname = (findings.get("name") or "").strip().lower()
        if fname and gdrug == fname:
            return r
    return None


def rankdata(a: List[float]) -> List[float]:
    # average ranks for ties (1-based)
    order = sorted((val, idx) for idx, val in enumerate(a))
    ranks = [0.0] * len(a)
    i = 0
    n = len(order)
    while i < n:
        val = order[i][0]
        j = i
        idxs = []
        while j < n and order[j][0] == val:
            idxs.append(order[j][1])
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for idx in idxs:
            ranks[idx] = avg_rank
        i = j
    return ranks


def pearsonr(x: List[float], y: List[float]) -> float:
    n = len(x)
    if n == 0:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    sx = sum((xi - mx) ** 2 for xi in x)
    sy = sum((yi - my) ** 2 for yi in y)
    den = (sx * sy) ** 0.5
    if den == 0:
        return 0.0
    return num / den


def spearmanr(x: List[float], y: List[float]) -> float:
    if not x or not y or len(x) != len(y):
        return 0.0
    rx = rankdata(x)
    ry = rankdata(y)
    return pearsonr(rx, ry)


def compute_metrics(gold_rows: List[Dict[str, str]], results: List[Dict]) -> Dict:
    n = len(gold_rows)
    tp = fp = fn = tn = 0
    mapped = 0
    evidence_count = 0
    risk_list = []
    naranjo_list = []

    for row in gold_rows:
        gold_major = (row.get("major_interaction") or "").strip().lower() in ("1", "true", "yes")
        gold_naranjo = row.get("naranjo_score")
        gold_naranjo_val = None
        if gold_naranjo is not None and gold_naranjo != "":
            try:
                gold_naranjo_val = float(gold_naranjo)
            except Exception:
                gold_naranjo_val = None

        res = _match_result(row, results)
        if not res:
            # treat as negative prediction (no data)
            model_major = False
            has_evidence = False
        else:
            model_major = _model_flags_major(res)
            findings = res.get("findings") or {}
            has_evidence = bool(findings.get("sources"))
            if res.get("rxcui"):
                mapped += 1
            # try to get model numeric risk score
            rscore = res.get("risk", {}).get("score")
            if isinstance(rscore, (int, float)):
                risk_list.append(float(rscore))
            # if analysis includes naranjo, try to extract
            analysis = res.get("analysis") or {}
            if isinstance(analysis, dict) and analysis.get("naranjo_score") is not None:
                try:
                    nval = float(analysis.get("naranjo_score"))
                    naranjo_list.append(nval)
                except Exception:
                    pass

        if has_evidence:
            evidence_count += 1

        if model_major and gold_major:
            tp += 1
        elif model_major and not gold_major:
            fp += 1
        elif not model_major and gold_major:
            fn += 1
        else:
            tn += 1

        if gold_naranjo_val is not None and risk_list:
            # if we have both, ensure lists align later; collect pairs now
            pass

    # compute metrics
    sens = tp / (tp + fn) if (tp + fn) else None
    prec = tp / (tp + fp) if (tp + fp) else None
    f1 = 2 * prec * sens / (prec + sens) if (prec and sens) else None
    rxcui_coverage = mapped / n if n else 0
    evidence_rate = evidence_count / n if n else 0

    # compute Naranjo concordance if lists available (use model risk vs gold naranjo)
    # Align by matching rows where both exist
    paired_risk = []
    paired_naranjo = []
    for row in gold_rows:
        res = _match_result(row, results)
        if not res:
            continue
        rscore = res.get("risk", {}).get("score")
        if rscore is None:
            continue
        gn = row.get("naranjo_score")
        if gn is None or gn == "":
            continue
        try:
            gnv = float(gn)
        except Exception:
            continue
        paired_risk.append(float(rscore))
        paired_naranjo.append(float(gnv))

    naranjo_spearman = spearmanr(paired_risk, paired_naranjo) if paired_risk else None

    return {
        "n_cases": n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "sensitivity": sens,
        "precision": prec,
        "f1": f1,
        "rxcui_coverage": rxcui_coverage,
        "evidence_support_rate": evidence_rate,
        "naranjo_spearman": naranjo_spearman,
    }


def main():
    parser = argparse.ArgumentParser(description="Compute evaluation metrics against a gold CSV and results JSON.")
    parser.add_argument("--gold", required=True, help="Gold-standard CSV file")
    parser.add_argument("--results-dir", default="evaluations", help="Directory with evaluation JSON results")
    parser.add_argument("--out", default=None, help="Optional output JSON file for metrics")
    args = parser.parse_args()

    results_path = load_latest_results(args.results_dir)
    print(f"Using results file: {results_path}")
    results = load_results(results_path)
    gold = load_gold_csv(args.gold)
    metrics = compute_metrics(gold, results)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
    else:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        outp = os.path.join(args.results_dir, f"evaluation_metrics_{ts}.json")
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        print(f"Wrote metrics to: {outp}")


if __name__ == "__main__":
    main()
