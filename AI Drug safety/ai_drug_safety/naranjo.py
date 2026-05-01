from typing import Dict, Any, Tuple

_QUESTION_SCORES = {
    1: {"yes": 1, "no": 0, "unknown": 0},
    2: {"yes": 2, "no": -1, "unknown": 0},
    3: {"yes": 1, "no": 0, "unknown": 0},
    4: {"yes": 2, "no": -1, "unknown": 0},
    5: {"yes": -1, "no": 2, "unknown": 0},
    6: {"yes": -1, "no": 1, "unknown": 0},
    7: {"yes": 1, "no": 0, "unknown": 0},
    8: {"yes": 1, "no": 0, "unknown": 0},
    9: {"yes": 1, "no": 0, "unknown": 0},
    10: {"yes": 1, "no": 0, "unknown": 0},
}


def _normalize_answer(a: Any) -> str:
    if a is None:
        return "unknown"
    if isinstance(a, str):
        s = a.strip().lower()
        if s in ("yes", "y", "1", "true", "+"):
            return "yes"
        if s in ("no", "n", "0", "false", "-"):
            return "no"
        return "unknown"
    if isinstance(a, bool):
        return "yes" if a else "no"
    if isinstance(a, (int, float)):
        return "yes" if a > 0 else "no"
    return "unknown"


def naranjo_score(answers: Dict[str, Any]) -> Tuple[int, str]:
    """
    Compute the Naranjo adverse drug reaction (ADR) probability score.

    `answers` may contain keys 'q1'..'q10' or 1..10 mapping to yes/no/unknown values.
    Returns (score, category) where category is one of: 'definite','probable','possible','doubtful'.
    """
    total = 0
    for i in range(1, 11):
        key1 = f"q{i}"
        key2 = i
        val = None
        if key1 in answers:
            val = answers[key1]
        elif key2 in answers:
            val = answers[key2]
        a = _normalize_answer(val)
        score_map = _QUESTION_SCORES.get(i, {})
        total += score_map.get(a, 0)

    if total >= 9:
        cat = "definite"
    elif total >= 5:
        cat = "probable"
    elif total >= 1:
        cat = "possible"
    else:
        cat = "doubtful"
    return total, cat
