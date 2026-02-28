from __future__ import annotations

from src.promotion_eval import evaluate_promotion


def test_strong_candidate_not_blocked_by_tail_na_semantics():
    out = evaluate_promotion(
        candidate_checks={"c1": True},
        strong_checks={"tail_sign_not_failed": True, "other": True},
        investigate_checks={"i1": False},
        diagnostics={"tail_sign_verdict": "na"},
    )
    assert out["promotion_level"] == "strong_candidate"


def test_strong_candidate_blocked_by_tail_fail_semantics():
    out = evaluate_promotion(
        candidate_checks={"c1": True},
        strong_checks={"tail_sign_not_failed": False, "other": True},
        investigate_checks={"i1": True},
        diagnostics={"tail_sign_verdict": "fail"},
    )
    assert out["promotion_level"] == "candidate"
