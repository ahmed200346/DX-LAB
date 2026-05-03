"""Adjudication tooling: pairwise annotation comparison + Cohen's kappa report.

Reads two annotator CSV files and optionally an adjudicator CSV. Produces
an adjudication report JSON and an adjudicated CSV with consensus/adjudicated
labels where available.

Usage:
  python -m ai_drug_safety.adjudicate --a evaluations/annotations_annotatorA.csv \
      --b evaluations/annotations_annotatorB.csv --out-dir evaluations
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional


def read_csv(path: str) -> List[Dict[str, str]]:
    out = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            out.append(r)
    return out


def norm_key(row: Dict[str, str]) -> str:
    # Prefer numeric id if present, else normalized drug name
    idv = (row.get('id') or '').strip()
    if idv:
        return idv
    return (row.get('drug') or '').strip().lower()


def parse_bool(x: Optional[str]) -> Optional[bool]:
    if x is None:
        return None
    s = str(x).strip().lower()
    if s == '':
        return None
    if s in ('1', 'true', 'yes', 'y'):
        return True
    if s in ('0', 'false', 'no', 'n'):
        return False
    return None


def compute_confusion(pairs: List[Tuple[bool, bool]]) -> Dict[str, int]:
    n00 = n01 = n10 = n11 = 0
    for a, b in pairs:
        if a and b:
            n11 += 1
        elif a and not b:
            n10 += 1
        elif not a and b:
            n01 += 1
        else:
            n00 += 1
    return {'n00': n00, 'n01': n01, 'n10': n10, 'n11': n11}


def kappa_from_conf(conf: Dict[str, int]) -> Optional[float]:
    n00 = conf['n00']; n01 = conf['n01']; n10 = conf['n10']; n11 = conf['n11']
    N = n00 + n01 + n10 + n11
    if N == 0:
        return None
    Po = (n00 + n11) / N
    pA_true = (n10 + n11) / N
    pB_true = (n01 + n11) / N
    Pe = pA_true * pB_true + (1 - pA_true) * (1 - pB_true)
    denom = 1 - Pe
    if denom == 0:
        return None
    return (Po - Pe) / denom


def bootstrap_kappa(pairs: List[Tuple[bool, bool]], n_boot: int = 1000, seed: int = 42) -> Tuple[float, float]:
    random.seed(seed)
    N = len(pairs)
    if N == 0:
        return (0.0, 0.0)
    vals = []
    for _ in range(n_boot):
        sample = [pairs[random.randrange(N)] for _ in range(N)]
        conf = compute_confusion(sample)
        k = kappa_from_conf(conf)
        vals.append(k if k is not None else 0.0)
    vals.sort()
    lo = vals[int(0.025 * len(vals))]
    hi = vals[int(0.975 * len(vals)) - 1]
    return (lo, hi)


def main():
    parser = argparse.ArgumentParser(description='Adjudicate pairwise annotations and compute Cohen\'s kappa')
    parser.add_argument('--a', required=True, help='Annotator A CSV')
    parser.add_argument('--b', required=True, help='Annotator B CSV')
    parser.add_argument('--adjudicator', help='Optional adjudicator CSV')
    parser.add_argument('--out-dir', default='evaluations', help='Output directory')
    parser.add_argument('--bootstrap', type=int, default=1000, help='Bootstrap iterations for CI')
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    a_rows = read_csv(args.a)
    b_rows = read_csv(args.b)
    adj_rows = read_csv(args.adjudicator) if args.adjudicator else []
    adj_map = {norm_key(r): r for r in adj_rows} if adj_rows else {}

    a_map = {norm_key(r): r for r in a_rows}
    b_map = {norm_key(r): r for r in b_rows}

    keys = sorted(set(a_map.keys()) & set(b_map.keys()))
    pairs_major: List[Tuple[bool, bool]] = []
    pairs_adverse: List[Tuple[bool, bool]] = []
    merged_output = []

    for k in keys:
        ra = a_map[k]
        rb = b_map[k]
        drug = ra.get('drug') or rb.get('drug') or k
        ida = ra.get('id') or ''
        idb = rb.get('id') or ''
        a_major = parse_bool(ra.get('major_interaction'))
        b_major = parse_bool(rb.get('major_interaction'))
        a_adv = parse_bool(ra.get('adverse_outcome'))
        b_adv = parse_bool(rb.get('adverse_outcome'))

        if a_major is not None and b_major is not None:
            pairs_major.append((a_major, b_major))
        if a_adv is not None and b_adv is not None:
            pairs_adverse.append((a_adv, b_adv))

        # adjudication logic
        adj = adj_map.get(k)
        final_major = ''
        major_agree = False
        if a_major is not None and b_major is not None and a_major == b_major:
            final_major = str(a_major)
            major_agree = True
        elif adj and adj.get('major_interaction') is not None:
            final_major = str(parse_bool(adj.get('major_interaction')))
        else:
            final_major = ''

        final_adv = ''
        adv_agree = False
        if a_adv is not None and b_adv is not None and a_adv == b_adv:
            final_adv = str(a_adv)
            adv_agree = True
        elif adj and adj.get('adverse_outcome') is not None:
            final_adv = str(parse_bool(adj.get('adverse_outcome')))
        else:
            final_adv = ''

        merged_output.append({
            'id': ida or idb or '',
            'drug': drug,
            'major_interaction_A': '' if a_major is None else str(a_major),
            'major_interaction_B': '' if b_major is None else str(b_major),
            'major_interaction_final': final_major,
            'major_interaction_agree': major_agree,
            'adverse_outcome_A': '' if a_adv is None else str(a_adv),
            'adverse_outcome_B': '' if b_adv is None else str(b_adv),
            'adverse_outcome_final': final_adv,
            'adverse_outcome_agree': adv_agree,
            'notes_A': ra.get('notes',''),
            'notes_B': rb.get('notes',''),
        })

    conf_major = compute_confusion(pairs_major)
    conf_adv = compute_confusion(pairs_adverse)
    k_major = kappa_from_conf(conf_major)
    k_adv = kappa_from_conf(conf_adv)
    ci_major = bootstrap_kappa(pairs_major, n_boot=args.bootstrap) if pairs_major else (0.0, 0.0)
    ci_adv = bootstrap_kappa(pairs_adverse, n_boot=args.bootstrap) if pairs_adverse else (0.0, 0.0)

    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    report = {
        'n_pairs': len(keys),
        'major': {
            'confusion': conf_major,
            'kappa': k_major,
            'bootstrap_ci': {'2.5%': ci_major[0], '97.5%': ci_major[1]},
        },
        'adverse': {
            'confusion': conf_adv,
            'kappa': k_adv,
            'bootstrap_ci': {'2.5%': ci_adv[0], '97.5%': ci_adv[1]},
        },
        'annotator_a_file': args.a,
        'annotator_b_file': args.b,
        'adjudicator_file': args.adjudicator or None,
    }

    report_path = os.path.join(args.out_dir, f'adjudication_report_{ts}.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    out_csv = os.path.join(args.out_dir, f'adjudicated_gold_{ts}.csv')
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        keys = ['id','drug','major_interaction_A','major_interaction_B','major_interaction_final','major_interaction_agree',
                'adverse_outcome_A','adverse_outcome_B','adverse_outcome_final','adverse_outcome_agree','notes_A','notes_B']
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in merged_output:
            writer.writerow(r)

    print(f'Wrote adjudication report: {report_path}')
    print(f'Wrote adjudicated gold CSV: {out_csv}')


if __name__ == '__main__':
    main()
