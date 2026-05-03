import os
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional
from functools import lru_cache

OPENFDA_BASE = "https://api.fda.gov"


def get_drug_data(drug_name: str, use_mock: bool = False, prefer_drugbank: bool = False) -> Dict[str, Any]:
    """
    Retrieve drug information (side effects, interactions, warnings) from real sources.
    `use_mock` flag is accepted for backward compatibility but mocked responses are
    no longer provided — the function always queries real data (openFDA and
    optional DrugBank) and returns a normalized structure.
    """

    drugbank_key = os.getenv("DRUGBANK_API_KEY")
    if drugbank_key and prefer_drugbank:
        db = fetch_drugbank(drug_name, api_key=drugbank_key)
        if db:
            return db

    label = fetch_openfda_label(drug_name)
    events = fetch_openfda_events(drug_name)
    merged = merge_openfda_results(drug_name, label, events)

    if drugbank_key:
        db = fetch_drugbank(drug_name, api_key=drugbank_key)
        if db:
            merged = _merge_sources(merged, db)

    return merged


def _to_list(x):
    if not x:
        return []
    if isinstance(x, list):
        return x
    return [x]


@lru_cache(maxsize=128)
def fetch_openfda_label(drug_name: str, limit: int = 1) -> Optional[Dict[str, Any]]:
    """
    Query openFDA label endpoint for a drug. Tries several openFDA name fields.
    Returns the raw label dict or None if not found.
    """
    if not drug_name:
        return None
    queries = [
        f'openfda.brand_name:"{drug_name}"',
        f'openfda.generic_name:"{drug_name}"',
        f'openfda.substance_name:"{drug_name}"',
        f'active_ingredient:"{drug_name}"',
    ]
    for q in queries:
        try:
            path = "/drug/label.json"
            qs = urllib.parse.quote(q, safe='')
            url = f"{OPENFDA_BASE}{path}?search={qs}&limit={limit}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                text = resp.read().decode("utf-8")
                parsed = json.loads(text)
            results = parsed.get("results") or []
            if results:
                return results[0]
        except Exception:
            continue
    return None


@lru_cache(maxsize=128)
def fetch_openfda_events(drug_name: str, limit: int = 10) -> Dict[str, Any]:
    """
    Query openFDA adverse event reports and summarize reactions.
    Returns {"event_count": int, "common_reactions": [(term,count), ...]}.
    """
    out = {"event_count": 0, "common_reactions": []}
    if not drug_name:
        return out
    queries = [
        f'patient.drug.openfda.substance_name:"{drug_name}"',
        f'patient.drug.medicinalproduct:"{drug_name}"',
    ]
    reactions_count = {}
    total = 0
    for q in queries:
        try:
            path = "/drug/event.json"
            qs = urllib.parse.quote(q, safe='')
            url = f"{OPENFDA_BASE}{path}?search={qs}&limit={limit}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
            results = parsed.get("results") or []
            for r in results:
                total += 1
                patient = r.get("patient", {})
                for react in patient.get("reaction", []) or []:
                    term = react.get("reactionmeddrapt") or react.get("reactionmeddra")
                    if term:
                        reactions_count[term] = reactions_count.get(term, 0) + 1
        except Exception:
            continue
    if total == 0:
        return out
    sorted_reacts = sorted(reactions_count.items(), key=lambda x: x[1], reverse=True)
    out["event_count"] = total
    out["common_reactions"] = sorted_reacts[:10]
    return out


def merge_openfda_results(drug_name: str, label: Optional[Dict[str, Any]], events: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert openFDA label + events into normalized structure matching the mock.
    """
    side_effects = []
    interactions = []
    warnings = []
    sources = []
    name = drug_name
    if label:
        name = _extract_label_name(label) or drug_name
        side_effects = _to_list(label.get("adverse_reactions") or label.get("adverse_reactions", []))
        inter_raw = label.get("drug_interactions") or label.get("precautions") or []
        if inter_raw:
            interactions = _to_list(inter_raw)
        warnings = _to_list(label.get("warnings") or label.get("boxed_warning") or [])
        sources.append({"name": "openFDA label", "url": f"{OPENFDA_BASE}/drug/label"})
    if events and events.get("common_reactions"):
        se_terms = [r for r, _ in events["common_reactions"]]
        side_effects = list(dict.fromkeys(side_effects + se_terms))
        sources.append({"name": "openFDA events", "url": f"{OPENFDA_BASE}/drug/event"})
    return {
        "name": name,
        "side_effects": side_effects,
        "interactions": [{"drug": i.get("name") if isinstance(i, dict) else str(i), "severity": "unknown", "description": str(i)} for i in interactions],
        "warnings": warnings,
        "sources": sources,
    }


def _extract_label_name(label: Dict[str, Any]) -> Optional[str]:
    od = label.get("openfda", {})
    for key in ("brand_name", "generic_name", "substance_name"):
        val = od.get(key)
        if isinstance(val, list):
            return val[0]
        if val:
            return val
    return label.get("setid") or None


def fetch_drugbank(drug_name: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Minimal DrugBank wrapper. Requires `DRUGBANK_API_KEY` environment variable.
    The exact host/endpoint may vary by license; set `DRUGBANK_API_HOST` if needed.
    Returns normalized structure similar to openFDA output or None on failure.
    """
    api_key = api_key or os.getenv("DRUGBANK_API_KEY")
    if not api_key:
        return None
    host = os.getenv("DRUGBANK_API_HOST", "https://api.drugbank.com")
    try:
        path = f"/v1/us/drugs?name={urllib.parse.quote(drug_name)}"
        url = host.rstrip("/") + path
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
        name = parsed.get("name") or drug_name
        side_effects = parsed.get("adverse_effects") or parsed.get("adverseReactions") or []
        interactions = parsed.get("drug_interactions") or parsed.get("interactions") or []
        warnings = parsed.get("warnings") or parsed.get("boxedWarnings") or []
        return {
            "name": name,
            "side_effects": side_effects,
            "interactions": interactions,
            "warnings": warnings,
            "sources": [{"name": "DrugBank API", "url": url}],
        }
    except Exception:
        return None


def _merge_sources(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "name": a.get("name") or b.get("name"),
        "side_effects": list(dict.fromkeys((a.get("side_effects") or []) + (b.get("side_effects") or []))),
        "warnings": list(dict.fromkeys((a.get("warnings") or []) + (b.get("warnings") or []))),
        "sources": (a.get("sources") or []) + (b.get("sources") or []),
    }
    ai = a.get("interactions") or []
    bi = b.get("interactions") or []
    merged_inter = { (i.get("drug") if isinstance(i, dict) else str(i)): i for i in ai }
    for i in bi:
        key = i.get("drug") if isinstance(i, dict) else str(i)
        if key in merged_inter:
            existing = merged_inter[key]
            if isinstance(existing, dict) and isinstance(i, dict):
                merged_inter[key] = {**existing, **i}
        else:
            merged_inter[key] = i
    out["interactions"] = list(merged_inter.values())
    return out


# Note: mock data generator removed to ensure only real data sources are used.
