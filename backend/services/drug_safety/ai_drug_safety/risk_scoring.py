from typing import Dict, Any, List
import os
import json

_BEERS_DATA = None


def _load_beers():
    global _BEERS_DATA
    if _BEERS_DATA is not None:
        return _BEERS_DATA
    try:
        p = os.path.join(os.path.dirname(__file__), "data", "beers.json")
        with open(p, "r", encoding="utf-8") as f:
            _BEERS_DATA = json.load(f)
    except Exception:
        _BEERS_DATA = []
    # Try to augment entries with RxNorm RXCUI values for robust matching.
    try:
        from .rxnorm import get_rxcui
    except Exception:
        get_rxcui = None

    if get_rxcui:
        for entry in _BEERS_DATA:
            if entry.get("_rxcui") is None:
                try:
                    entry['_rxcui'] = get_rxcui(entry.get("name", ""))
                except Exception:
                    entry['_rxcui'] = None

    return _BEERS_DATA


def _find_beers_matches(drug_name: str) -> List[Dict[str, str]]:
    name = (drug_name or "").strip()
    matches: List[Dict[str, str]] = []
    if not name:
        return matches

    # First, attempt RXCUI-based matching using RxNorm
    try:
        from .rxnorm import get_rxcui as _get_rxcui
    except Exception:
        _get_rxcui = None

    if _get_rxcui:
        try:
            input_rxcui = _get_rxcui(name)
        except Exception:
            input_rxcui = None
        if input_rxcui:
            for entry in _load_beers():
                erxc = entry.get("_rxcui")
                if erxc and erxc == input_rxcui:
                    matches.append(entry)
            if matches:
                return matches

    # Fallback: simple substring matching (case-insensitive)
    lname = name.lower()
    for entry in _load_beers():
        en = entry.get("name", "").lower()
        if not en:
            continue
        if en in lname or lname in en:
            matches.append(entry)
    return matches


def _contains_keyword_list(sources, keywords):
    if not sources:
        return False
    if isinstance(sources, str):
        hay = sources.lower()
        for k in keywords:
            if k in hay:
                return True
        return False
    # list-like
    for itm in sources:
        if not itm:
            continue
        if _contains_keyword_list(str(itm), keywords):
            return True
    return False


def _compute_has_bled(patient_info: Dict[str, Any]) -> Dict[str, Any]:
    """Compute HAS-BLED score when possible from patient_info.

    Accepts best-effort inputs: `age`, `conditions` (list), `medications` (list or comma string),
    `labile_inr` (bool), `alcohol_use` (bool).
    Returns dict: {score, components, category}.
    """
    age = int(patient_info.get("age") or 0)
    conditions = patient_info.get("conditions") or []
    meds = patient_info.get("medications") or []
    if isinstance(meds, str):
        meds = [m.strip() for m in meds.split(",") if m.strip()]

    def has_cond(keywords):
        return _contains_keyword_list(conditions, keywords) or _contains_keyword_list(meds, keywords)

    score = 0
    components = {}

    # Hypertension
    htn = has_cond(["hypertension", "htn"]) or bool(patient_info.get("hypertension"))
    components["hypertension"] = bool(htn)
    if htn:
        score += 1

    # Abnormal renal / liver (count separately)
    renal = has_cond(["renal", "ckd", "kidney", "dialysis"]) or bool(patient_info.get("renal_dysfunction"))
    liver = has_cond(["liver", "hepatic", "cirrhosis"]) or bool(patient_info.get("liver_disease"))
    components["renal"] = bool(renal)
    components["liver"] = bool(liver)
    if renal:
        score += 1
    if liver:
        score += 1

    # Stroke history
    stroke = has_cond(["stroke", "tia"]) or bool(patient_info.get("stroke"))
    components["stroke_history"] = bool(stroke)
    if stroke:
        score += 1

    # Bleeding history
    bleed = has_cond(["bleed", "hemorrhage", "haemorrhage", "gib"]) or bool(patient_info.get("bleeding_history"))
    components["bleeding_history"] = bool(bleed)
    if bleed:
        score += 1

    # Labile INR
    labile = bool(patient_info.get("labile_inr"))
    components["labile_inr"] = labile
    if labile:
        score += 1

    # Elderly
    elderly = age >= 65
    components["elderly"] = elderly
    if elderly:
        score += 1

    # Drugs / alcohol (antiplatelet/NSAID or alcohol abuse)
    antiplatelet_keywords = ["aspirin", "clopidogrel", "prasugrel", "ticagrelor", "naproxen", "ibuprofen", "diclofenac"]
    drugs_flag = _contains_keyword_list(meds, antiplatelet_keywords) or has_cond(["antiplatelet", "nsaid"]) or bool(patient_info.get("concomitant_antiplatelet"))
    alcohol = bool(patient_info.get("alcohol_use")) or has_cond(["alcoholism", "alcohol abuse"]) 
    components["drugs_or_alcohol"] = bool(drugs_flag or alcohol)
    if drugs_flag or alcohol:
        score += 1

    # Category
    if score >= 3:
        category = "high"
    elif score == 2:
        category = "moderate"
    else:
        category = "low"

    return {"score": score, "components": components, "category": category}


def _compute_tisdale(patient_info: Dict[str, Any], findings: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort Tisdale QT risk score approximation using available data.

    Tisdale categories: low (<=6), moderate (7-10), high (>=11).
    """
    age = int(patient_info.get("age") or 0)
    sex = (patient_info.get("sex") or "").strip().lower()
    conditions = patient_info.get("conditions") or []
    meds = patient_info.get("medications") or []
    if isinstance(meds, str):
        meds = [m.strip() for m in meds.split(",") if m.strip()]

    score = 0
    components = {}

    # Age >=68
    if age >= 68:
        score += 1
        components["age>=68"] = True
    else:
        components["age>=68"] = False

    # Female
    if sex in ("female", "f"):
        score += 1
        components["female"] = True
    else:
        components["female"] = False

    # Loop diuretic
    loop_kw = ["furosemide", "bumetanide", "torsemide"]
    loop_flag = _contains_keyword_list(meds, loop_kw) or _contains_keyword_list(conditions, ["loop diuretic"])
    if loop_flag:
        score += 1
        components["loop_diuretic"] = True
    else:
        components["loop_diuretic"] = False

    # Serum K (if provided)
    try:
        k = float(patient_info.get("serum_k", patient_info.get("potassium", "")) or 0)
    except Exception:
        k = None
    if k is not None and k != 0:
        if k <= 3.5:
            score += 2
            components["k_low"] = True
        else:
            components["k_low"] = False
    else:
        components["k_low"] = None

    # Baseline QTc
    try:
        qtc = int(patient_info.get("baseline_qtc") or 0)
    except Exception:
        qtc = None
    if qtc and qtc >= 450:
        score += 2
        components["baseline_qtc_high"] = True
    else:
        components["baseline_qtc_high"] = False

    # Acute MI
    mi = _contains_keyword_list(conditions, ["mi", "myocardial infarction"]) or bool(patient_info.get("acute_mi"))
    if mi:
        score += 2
        components["acute_mi"] = True
    else:
        components["acute_mi"] = False

    # QT-prolonging drugs count (best-effort)
    qt_prolongers = set(["amiodarone", "sotalol", "haloperidol", "droperidol", "citalopram", "escitalopram", "fluoroquinolone", "levofloxacin", "moxifloxacin", "clarithromycin", "erythromycin"]) 
    present = 0
    for m in meds:
        if not m:
            continue
        ml = m.lower()
        for qd in qt_prolongers:
            if qd in ml:
                present += 1
                break
    # also check interactions list
    for inter in (findings.get("interactions") or []):
        dname = (inter.get("drug") if isinstance(inter, dict) else str(inter)).lower()
        for qd in qt_prolongers:
            if qd in dname:
                present += 1
                break

    components["qt_prolonging_drugs_count"] = present
    if present > 1:
        score += 3
    elif present == 1:
        score += 2

    # Sepsis
    sepsis = _contains_keyword_list(conditions, ["sepsis"]) or bool(patient_info.get("sepsis"))
    if sepsis:
        score += 3
        components["sepsis"] = True
    else:
        components["sepsis"] = False

    # Category
    if score >= 11:
        category = "high"
    elif score >= 7:
        category = "moderate"
    else:
        category = "low"

    return {"score": score, "components": components, "category": category}


def score_risk(findings: Dict[str, Any], patient_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute clinically meaningful risk outputs.

    Returns a dict with:
    - `score`: integer 0-100 (backwards-compatible summary; derived from clinical scores)
    - `factors`: short list of contributing factors (strings)
    - `beers_matches`: list of matching Beers entries
    - `clinical`: dict with clinical scores (HAS-BLED, Tisdale) and flags
    """
    age = int(patient_info.get("age") or 0)
    conditions = patient_info.get("conditions") or []
    meds = patient_info.get("medications") or []
    if isinstance(meds, str):
        meds = [m.strip() for m in meds.split(",") if m.strip()]

    factors: List[str] = []

    # Detect major interaction presence and collect interaction-based factors
    major_interaction = False
    for inter in findings.get("interactions", []):
        sev = (inter.get("severity") or "").lower()
        if "major" in sev or "major" in (inter.get("description") or "").lower():
            major_interaction = True
            factors.append(f"major interaction with {inter.get('drug')}")

    # Beers criteria
    drug_name = (findings.get("name") or "").strip()
    beers_matches = []
    if age >= 65 and drug_name:
        beers_matches = _find_beers_matches(drug_name)
        for m in beers_matches:
            factors.append(f"Beers:{m.get('name')}")

    # Clinical scores
    has_bled = _compute_has_bled(patient_info)
    tisdale = _compute_tisdale(patient_info, findings)

    # Compose a backward-compatible integer score from clinical metrics
    # Normalize HAS-BLED (max 9) and Tisdale (use typical max 20) to 0-100
    hb_norm = int(min(9, has_bled.get("score", 0)) / 9 * 100) if has_bled else 0
    td_norm = int(min(20, tisdale.get("score", 0)) / 20 * 100) if tisdale else 0

    # Base on: presence of major interactions (75 points), then max of clinical norms
    legacy_score = 0
    if major_interaction:
        legacy_score = max(legacy_score, 75)
    legacy_score = max(legacy_score, hb_norm, td_norm)

    # Small additional weight for age and conditions
    if age >= 65:
        legacy_score = min(100, legacy_score + 5)
    if conditions:
        legacy_score = min(100, legacy_score + min(10, len(conditions) * 2))

    return {
        "score": int(legacy_score),
        "factors": factors,
        "beers_matches": [m.get("name") for m in beers_matches],
        "clinical": {
            "has_bled": has_bled,
            "tisdale": tisdale,
            "major_interaction": major_interaction,
        },
    }
