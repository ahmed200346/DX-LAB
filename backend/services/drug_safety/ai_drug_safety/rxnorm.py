import urllib.parse
import urllib.request
import json
from typing import Optional

from .cache import get as cache_get, set as cache_set

# Cache TTL for RxNorm lookups (1 week)
DEFAULT_TTL = 7 * 24 * 3600


def get_rxcui(drug_name: str, ttl: int = DEFAULT_TTL) -> Optional[str]:
    """Return an RXCUI for `drug_name` using RxNav (RxNorm) lookup.

    Uses a file-based cache to avoid repeated network requests. Returns
    `None` if unable to resolve.
    """
    if not drug_name:
        return None
    key = drug_name.strip().lower()
    cached = cache_get("rxnav_rxcui", key)
    if cached is not None:
        return cached

    base = "https://rxnav.nlm.nih.gov/REST/rxcui.json?name=" + urllib.parse.quote(drug_name)
    try:
        with urllib.request.urlopen(base, timeout=8) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
        ids = parsed.get("idGroup", {}).get("rxnormId") or []
        if ids:
            rxcui = str(ids[0])
            cache_set("rxnav_rxcui", key, rxcui, ttl=ttl)
            return rxcui
    except Exception:
        # network or parsing error — fall through to approximate lookup
        pass

    # Fallback: approximateTerm to get candidate rxcui
    try:
        url = (
            "https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term="
            + urllib.parse.quote(drug_name)
            + "&maxEntries=1"
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
        cand = parsed.get("approximateGroup", {}).get("candidate") or []
        if isinstance(cand, list) and cand:
            c = cand[0]
            rxcui = c.get("rxcui")
            if rxcui:
                cache_set("rxnav_rxcui", key, str(rxcui), ttl=ttl)
                return str(rxcui)
    except Exception:
        pass

    # Negative cache for a short time to avoid repeated failures
    cache_set("rxnav_rxcui", key, None, ttl=60 * 10)
    return None
