"""
agents/biomedical_validator.py
Post-hoc biomedical validator: checks if proposed interactions are supported by known data.
"""

from typing import List, Dict

# Minimal curated set of high-confidence KRAS-related interactions.
# In production, replace with a full database (e.g., STRING, BioGRID).
KNOWN_INTERACTIONS = {
    ("KRAS", "RAF1"): "activates",
    ("KRAS", "PIK3CA"): "activates",
    ("KRAS", "RALGDS"): "activates",
    ("KRAS", "MAP2K1"): "activates",
    ("KRAS", "MAP2K2"): "activates",
    ("USP7", "KRAS"): "deubiquitinates",
    ("TBK1", "IRF3"): "phosphorylates",
    ("TBK1", "NFKBIA"): "regulates",
    ("STK11", "LKB1"): "activates",
    ("NLRX1", "mitophagy"): "regulates",
    ("NLRX1", "mtROS"): "regulates",
    ("ACLY", "AcCoA"): "synthesizes",
    ("USP21", "macropinocytosis"): "regulates",
    ("KRAS", "HRAS"): "interacts_with",   # low specificity
    ("KRAS", "RHEB"): "interacts_with",
}

def validate_hypothesis(hypothesis: Dict, all_triples: List[Dict]) -> Dict:
    """
    Check if the molecular claims in the hypothesis statement are supported
    by either the extracted triples or the known interactions dictionary.
    Returns the hypothesis with added validation fields.
    """
    statement = hypothesis.get("statement", "")
    # Extract potential subject-relation-object mentions (naive token matching)
    # We'll scan against known interactions and triples.
    flagged_claims = []
    for (subj, obj), rel in KNOWN_INTERACTIONS.items():
        if subj.lower() in statement.lower() and obj.lower() in statement.lower():
            # found a known interaction, assume supported
            pass

    # Check against triples from all papers
    supported = False
    for triple in all_triples:
        s = triple.get("subject", "")
        o = triple.get("object", "")
        if s.lower() in statement.lower() and o.lower() in statement.lower():
            supported = True
            break
    # Also check against known interactions
    for (subj, obj), rel in KNOWN_INTERACTIONS.items():
        if subj.lower() in statement.lower() and obj.lower() in statement.lower():
            supported = True
            break

    hypothesis["biomedical_validation"] = {
        "supported_by_data": supported,
        "confidence": "high" if supported else "low",
    }
    # If not supported, flag and reduce novelty score
    if not supported:
        hypothesis["novelty_score"] = max(1, hypothesis.get("novelty_score", 5) - 3)
        hypothesis["biomedical_validation"]["note"] = "Contains interactions not found in provided papers or known KRAS pathways."
    return hypothesis