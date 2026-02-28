from __future__ import annotations

from src.promotion_eval import evaluate_promotion


def test_promotion_reaches_strong_candidate_when_investigate_blocked():
    out = evaluate_promotion(
        candidate_checks={"c1": True, "c2": True},
        strong_checks={"s1": True, "s2": True},
        investigate_checks={"i1": False},
        diagnostics={},
    )
    assert out["promotion_level"] == "strong_candidate"


def test_promotion_stops_at_candidate_when_strong_fails():
    out = evaluate_promotion(
        candidate_checks={"c1": True, "c2": True},
        strong_checks={"s1": False},
        investigate_checks={"i1": True},
        diagnostics={},
    )
    assert out["promotion_level"] == "candidate"


def test_promotion_none_when_candidate_fails():
    out = evaluate_promotion(
        candidate_checks={"c1": False},
        strong_checks={"s1": True},
        investigate_checks={"i1": True},
        diagnostics={},
    )
    assert out["promotion_level"] == "none"
