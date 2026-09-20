"""Tests for Element X edge-case lane: CURV many-negatives honesty check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ufo_mechanisms.element_x_edgecase import (
    ElementXSpec,
    MomentumExchangeMode,
    evaluate_element_x,
)
from src.ufo_observables import (
    profile_edgecase_hypersonic_no_boom,
    profile_tictac_like,
)
from src.ufo_observable_evaluator import evaluate_ufo_observables


def test_element_x_fails_with_speculative_not_enabled():
    """Test 1 (default): element_x fails with speculative_element_x_not_enabled."""
    behavior, claims = profile_edgecase_hypersonic_no_boom()
    spec = ElementXSpec(allow_speculative=False)
    result = evaluate_element_x(
        behavior, claims, (100.0, 10000.0), "strict", spec
    )
    assert result["passed"] is False
    assert result["dominant_failure_reason"] == "speculative_element_x_not_enabled"
    assert "speculative_element_x_not_enabled" in result.get("reasons", [result["dominant_failure_reason"]])


def test_element_x_evaluator_includes_lane_by_default():
    """Element X lane is always present in lane_results."""
    behavior, claims = profile_edgecase_hypersonic_no_boom()
    result = evaluate_ufo_observables(
        behavior, claims, (100.0, 10000.0),
        policy="strict",
        enable_element_x=False,
    )
    element_x_lanes = [lr for lr in result["lane_results"] if lr["lane"] == "element_x_edgecase"]
    assert len(element_x_lanes) == 1
    assert element_x_lanes[0]["dominant_failure_reason"] == "speculative_element_x_not_enabled"


def test_edgecase_strict_policy_fails_many_gates():
    """Test 2: speculative enabled but strict policy still fails due to gates.

    Assert failed_gates >= 4 for full evaluation in strict mode with edgecase profile.
    Gates: sonic boom, thermal, momentum, transmedium, lensing, etc.
    """
    behavior, claims = profile_edgecase_hypersonic_no_boom()
    result = evaluate_ufo_observables(
        behavior, claims, (100.0, 10000.0),
        policy="strict",
        enable_element_x=True,
        allow_speculative_override=True,
        element_x_spec=ElementXSpec(
            max_power_density_w_m3=1e18,
            waste_heat_fraction=1e-6,
            shock_suppression=True,
            medium_coupling_factor=1e-6,
            momentum_exchange_mode=MomentumExchangeMode.METRIC_BUBBLE,
            allow_speculative=True,
        ),
    )
    failed_gates = result["failed_gates"]
    assert len(failed_gates) >= 4, (
        f"Expected >= 4 failed gates for CURV honesty, got {len(failed_gates)}: "
        f"{[g.get('reason') for g in failed_gates]}"
    )


def test_edgecase_failure_reasons_include_expected():
    """Edgecase profile should produce crisp failure reasons from known gate types."""
    behavior, claims = profile_edgecase_hypersonic_no_boom()
    result = evaluate_ufo_observables(
        behavior, claims, (100.0, 10000.0),
        policy="strict",
        enable_element_x=True,
        allow_speculative_override=True,
    )
    reasons = [g.get("reason", "") for g in result["failed_gates"]]
    # At least one of these gate types should appear
    expected_categories = [
        "sonic", "shock", "thermal", "momentum", "transmedium",
        "lensing", "contrail", "exhaust", "power", "heat",
        "mitigation", "speculative",
    ]
    found = any(any(cat in r.lower() for cat in expected_categories) for r in reasons)
    assert found, f"Expected crisp gate reasons, got: {reasons}"


def test_element_x_lane_payload_in_artifact(tmp_path: Path):
    """CLI writes artifact with lane_results including element_x_edgecase."""
    import subprocess
    r = subprocess.run(
        [
            "python", "scripts/run_ufo_observable_eval.py",
            "--project-root", str(tmp_path),
            "--profile", "edgecase_hypersonic_no_boom",
            "--policy", "strict",
            "--enable-element-x",
            "--allow-speculative",
            "--no-registry",
        ],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"CLI failed: {r.stderr}"
    artifacts = list((tmp_path / "results" / "artifacts").glob("*"))
    assert len(artifacts) >= 1
    eval_path = artifacts[0] / "ufo_observable_eval.json"
    assert eval_path.exists()
    report = json.loads(eval_path.read_text(encoding="utf-8"))
    assert "failed_gates" in report
    assert "lane_results" in report or "lane_rankings" in report
    lane_results = report.get("lane_results", [])
    element_x = [lr for lr in lane_results if lr.get("lane") == "element_x_edgecase"]
    assert len(element_x) == 1, f"element_x_edgecase lane missing from {list(lr.get('lane') for lr in lane_results)}"
    assert "dominant_failure_reason" in element_x[0] or "reasons" in element_x[0]


def test_verdict_physically_implausible_for_edgecase():
    """Edgecase with strict-ish evaluation should yield physically_implausible verdict."""
    behavior, claims = profile_edgecase_hypersonic_no_boom()
    result = evaluate_ufo_observables(
        behavior, claims, (100.0, 10000.0),
        policy="strict",
        enable_element_x=True,
        allow_speculative_override=True,
    )
    # With many failed gates, verdict should be implausible or require speculative
    assert result["verdict"] in (
        "physically_implausible_under_known_physics",
        "requires_speculative_physics",
    )
