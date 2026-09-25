"""Deterministic capped allocation; scores express theme relevance, not expected returns."""

import math


def allocate(scores, cap, fixed=None):
    fixed = fixed or {}
    if not scores or any(not math.isfinite(s) or s < 0 for s in scores):
        raise ValueError("Allocation scores must be finite and non-negative.")
    if any(
        i not in range(len(scores)) or not math.isfinite(w) or w < 0 or w > cap
        for i, w in fixed.items()
    ):
        raise ValueError("Requested weight exceeds the maximum weight or is invalid.")
    remaining = 1 - sum(fixed.values())
    free = set(range(len(scores))) - fixed.keys()
    if remaining < -1e-9 or remaining > len(free) * cap + 1e-9:
        raise ValueError(
            "These weights cannot total 100% within the cap. Add holdings or increase the cap."
        )
    weights = [fixed.get(i, 0) for i in range(len(scores))]
    while free:
        total = sum(scores[i] for i in free)
        proposals = {
            i: remaining * (scores[i] / total if total else 1 / len(free)) for i in free
        }
        capped = {i for i, w in proposals.items() if w > cap + 1e-12}
        if not capped:
            for i, w in proposals.items():
                weights[i] = w
            break
        for i in capped:
            weights[i] = cap
            remaining -= cap
        free -= capped
    return weights
