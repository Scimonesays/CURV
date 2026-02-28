"""Promotion ladder evaluator for CURV sweep outputs."""

from __future__ import annotations

from typing import Any


def tail_verdict_allows_strong(verdict: str) -> bool:
    """Strong-candidate gate: only explicit tail 'fail' blocks promotion."""
    return str(verdict).strip().lower() != "fail"


def evaluate_promotion(
    *,
    candidate_checks: dict[str, bool],
    strong_checks: dict[str, bool],
    investigate_checks: dict[str, bool],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate promotion ladder level from checklist booleans.

    Levels:
      none -> candidate -> strong_candidate -> investigate
    """
    reasons: list[str] = []
    for key, passed in candidate_checks.items():
        if not passed:
            reasons.append(f"candidate_fail:{key}")
    candidate_pass = all(candidate_checks.values())
    if not candidate_pass:
        return {
            "promotion_level": "none",
            "candidate_checks": candidate_checks,
            "strong_checks": strong_checks,
            "investigate_checks": investigate_checks,
            "reasons": reasons,
            "diagnostics": diagnostics,
        }

    for key, passed in strong_checks.items():
        if not passed:
            reasons.append(f"strong_fail:{key}")
    strong_pass = all(strong_checks.values())
    if not strong_pass:
        return {
            "promotion_level": "candidate",
            "candidate_checks": candidate_checks,
            "strong_checks": strong_checks,
            "investigate_checks": investigate_checks,
            "reasons": reasons,
            "diagnostics": diagnostics,
        }

    for key, passed in investigate_checks.items():
        if not passed:
            reasons.append(f"investigate_fail:{key}")
    investigate_pass = all(investigate_checks.values())
    return {
        "promotion_level": "investigate" if investigate_pass else "strong_candidate",
        "candidate_checks": candidate_checks,
        "strong_checks": strong_checks,
        "investigate_checks": investigate_checks,
        "reasons": reasons if reasons else ["all_checks_passed"],
        "diagnostics": diagnostics,
    }

