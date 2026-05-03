#!/usr/bin/env python3
"""Convert adjudicated adjudicated_gold_*.csv to a simple gold-standard CSV
compatible with `ai_drug_safety.evaluation`.

Writes `evaluations/adjudicated_gold_converted.csv` with fields:
id,drug,rxcui,major_interaction,naranjo_score,adverse_outcome,notes
"""
import glob
import csv
import os


def find_latest_adjudicated(directory="evaluations"):
    pattern = os.path.join(directory, "adjudicated_gold_*.csv")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError("No adjudicated_gold_*.csv files found in evaluations/")
    files.sort()
    return files[-1]


def convert(inpath, outpath):
    with open(inpath, newline='', encoding='utf-8') as inf:
        reader = csv.DictReader(inf)
        rows = list(reader)

    with open(outpath, 'w', newline='', encoding='utf-8') as outf:
        fieldnames = ['id', 'drug', 'rxcui', 'major_interaction', 'naranjo_score', 'adverse_outcome', 'notes']
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                'id': r.get('id',''),
                'drug': r.get('drug',''),
                'rxcui': r.get('rxcui',''),
                'major_interaction': r.get('major_interaction_final',''),
                'naranjo_score': '',
                'adverse_outcome': r.get('adverse_outcome_final',''),
                'notes': (r.get('notes_A','') + ' | ' + r.get('notes_B','')).strip(' | '),
            })


if __name__ == '__main__':
    latest = find_latest_adjudicated()
    out = os.path.join('evaluations', 'adjudicated_gold_converted.csv')
    convert(latest, out)
    print(f'Wrote converted gold: {out}')
