"""
utils/biomed_entities.py
Biomedical sanity layer – entity types, relation rules, validation.
"""

# ── Known entity types (extend manually or later via UniProt) ──
# Key: canonical name (lowercase), Value: type
ENTITY_TYPES = {
    # Proteins / Enzymes / Kinases
    "kras": "protein",
    "usp7": "enzyme",          # deubiquitinase
    "nlrx1": "protein",
    "tbk1": "kinase",
    "stk11": "kinase",
    "lkb1": "kinase",
    "akt": "kinase",
    "mapk": "kinase",
    "egfr": "protein",
    "tp53": "protein",
    "usp21": "enzyme",
    "myc": "protein",
    "hras": "protein",
    "rheb": "protein",
    "krt6a": "protein",
    "alk": "kinase",
    "braf": "kinase",
    "akt1": "kinase",
    "pi3k": "protein",
    "mtor": "kinase",
    "stat3": "protein",
    "nfkb": "protein",
    "src": "kinase",
    "fak": "kinase",

    # Metabolites / small molecules
    "accoa": "metabolite",
    "acetyl-coa": "metabolite",
    "atp": "metabolite",
    "nadph": "metabolite",
    "ros": "metabolite",
    "glutamine": "metabolite",

    # Drugs / inhibitors (treated as small molecule)
    "amg510": "drug",
    "sotorasib": "drug",
    "adagrasib": "drug",
    "deltarasin": "drug",
    "bay-87-2243": "drug",
    "2-methoxyestradiol": "drug",
    "farnesyl-transferase inhibitor": "drug",

    # Biological processes / phenotypes
    "cell proliferation": "phenotype",
    "drug resistance": "phenotype",
    "mitophagy": "phenotype",
    "tumorigenesis": "phenotype",
    "inflammatory response": "phenotype",
    "metastasis": "phenotype",
    "apoptosis": "phenotype",
}

# ── Relation rules ───────────────────────────────
# Each rule: list of (subject_type, object_type) that are allowed
# If relation not listed, it's allowed by default (but we'll still validate types)
RELATION_RULES = {
    "deubiquitinates": [("enzyme", "protein")],
    "ubiquitinates": [("enzyme", "protein")],
    "phosphorylates": [("kinase", "protein")],
    "activates": [],           # can be any -> any
    "inhibits": [],
    "stabilizes": [("protein", "protein"), ("enzyme", "protein")],
    "degrades": [("enzyme", "protein")],
    "promotes": [],
    "reduces": [],
    "bypasses": [],
    "induces": [],
    "regulates": [],
    "upregulates": [],
    "downregulates": [],
    "interacts_with": [("protein", "protein"), ("protein", "metabolite"), ("metabolite", "protein")],
    "is_upstream_of": [("protein", "protein"), ("protein", "phenotype")],
    "is_downstream_of": [("protein", "protein"), ("phenotype", "protein")],
}


def get_entity_type(name: str) -> str:
    """Return entity type for a given name, using fuzzy match (lowercase)."""
    key = name.strip().lower()
    if key in ENTITY_TYPES:
        return ENTITY_TYPES[key]
    # Try without common suffixes (e.g., "inhibitors" -> "inhibitor")
    for suffix in ["s", "es", " inhibitor", " inhibitors"]:
        if key.endswith(suffix):
            truncated = key[:-len(suffix)]
            if truncated in ENTITY_TYPES:
                return ENTITY_TYPES[truncated]
    # Default fallback
    return "unknown"


def validate_triple(subject: str, relation: str, obj: str) -> tuple[bool, float]:
    """
    Validate a triple based on entity types and relation rules.
    Returns (is_valid, type_validity_score 0.0-1.0).
    """
    subj_type = get_entity_type(subject)
    obj_type = get_entity_type(obj)

    # If either type is unknown, allow but with lower confidence
    type_validity = 1.0 if subj_type != "unknown" and obj_type != "unknown" else 0.5

    # Check specific relation rules
    allowed_pairs = RELATION_RULES.get(relation, None)
    if allowed_pairs is None:
        # No specific rule → pass
        return True, type_validity
    if not allowed_pairs:  # empty list means all types allowed
        return True, type_validity

    for allowed_subj, allowed_obj in allowed_pairs:
        if subj_type == allowed_subj and obj_type == allowed_obj:
            return True, type_validity
    # Type mismatch for this relation → reject
    return False, 0.0