"""Tests for CURV UFO flight behavior engine.

Asserts:
- no-exhaust + huge accel fails in strict mode for conventional thrust
- supersonic + no sonic boom fails unless explicitly allowed with mitigation
- transmedium at high speed fails for conventional lanes due to drag heating
- evaluator is deterministic and stable across runs
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.flight_dynamics_accounting import (
    full_dynamics_report,
    required_force,
    required_power,
    sonic_boom_expectation,
    transmedium_penalty,
)
from src.ufo_behavior_spec import UFOBehaviorSpec
from src.ufo_constraint_gates import gate_no_exhaust, gate_no_sonic_boom, gate_transmedium
from src.ufo_flight_behavior_evaluator import evaluate_ufo_flight_behavior, find_breakpoint
from src.ufo_mechanism_models import evaluate_conventional_thrust


def test_no_exhaust_plus_huge_accel_fails_strict_conventional_thrust():
    """No exhaust + huge accel fails for conventional thrust lane."""
    spec = UFOBehaviorSpec.from_common_uap_profile("tic_tac")
    dynamics = full_dynamics_report(
        mass_kg=1000.0,
        max_accel_m_s2=5000.0,
        max_speed_m_s=1000.0,
        turn_radius_m=10.0,
        hover_duration_s=300.0,
    )
    result = evaluate_conventional_thrust(dynamics, spec.to_dict())
    assert result["passed"] is False
    assert "no_exhaust" in result["dominant_failure_reason"] or "exhaust" in result["dominant_failure_reason"].lower()


def test_supersonic_no_sonic_boom_fails_without_mitigation():
    """Supersonic + no sonic boom fails unless shock mitigation declared."""
    dynamics = {
        "required_power_w": 1e6,
        "mass_kg": 1000.0,
        "sonic_boom_expectation": {"expect_sonic_boom": True, "mach": 2.0},
    }
    spec = {"sonic_boom_absent": True}
    result = gate_no_sonic_boom(dynamics, spec, "conventional_thrust", shock_mitigation_declared=False)
    assert result["passed"] is False
    assert "sonic" in result["reason"].lower() or "boom" in result["reason"].lower()


def test_supersonic_no_boom_passes_with_mitigation():
    """Supersonic + no boom passes when mitigation declared."""
    dynamics = {
        "sonic_boom_expectation": {"expect_sonic_boom": True},
    }
    spec = {"sonic_boom_absent": True}
    result = gate_no_sonic_boom(dynamics, spec, "field_propulsion", shock_mitigation_declared=True)
    assert result["passed"] is True


def test_transmedium_high_speed_fails_conventional():
    """Transmedium at high speed fails for conventional lanes."""
    dynamics = {
        "transmedium_penalty": {"catastrophic_heating_risk": True},
        "required_power_w": 1e7,
    }
    spec = {"transmedium": True}
    result = gate_transmedium(dynamics, spec, "conventional_thrust", coupling_reduction_declared=False)
    assert result["passed"] is False


def test_evaluator_deterministic_stable():
    """Evaluator is deterministic across runs."""
    spec = UFOBehaviorSpec.from_common_uap_profile("tic_tac")
    r1 = evaluate_ufo_flight_behavior(
        spec,
        mass_kg_min=100.0,
        mass_kg_max=1000.0,
        policy="strict",
    )
    r2 = evaluate_ufo_flight_behavior(
        spec,
        mass_kg_min=100.0,
        mass_kg_max=1000.0,
        policy="strict",
    )
    assert r1["verdict"] == r2["verdict"]
    assert r1["top_conflicts"] == r2["top_conflicts"]


def test_strict_policy_blocks_speculative_lanes():
    """Strict policy: speculative lanes (reactionless, field) fail."""
    spec = UFOBehaviorSpec.from_common_uap_profile("tic_tac")
    result = evaluate_ufo_flight_behavior(
        spec,
        mass_kg_min=100.0,
        mass_kg_max=1000.0,
        policy="strict",
    )
    for lr in result["lane_results"]:
        if lr["lane"] in ("reactionless", "field_propulsion"):
            assert lr["passed"] is False


def test_sandbox_allows_speculative_lanes():
    """Sandbox: speculative lanes can pass."""
    spec = UFOBehaviorSpec.from_common_uap_profile("tic_tac")
    result = evaluate_ufo_flight_behavior(
        spec,
        mass_kg_min=100.0,
        mass_kg_max=1000.0,
        policy="sandbox",
    )
    speculative_passed = any(
        lr["passed"] and lr["lane"] in ("reactionless", "field_propulsion")
        for lr in result["lane_results"]
    )
    assert speculative_passed


def test_gate_no_exhaust_fails_conventional_high_power():
    """Gate: no exhaust + high thrust fails."""
    dynamics = {"required_power_w": 2e6}
    spec = {"visible_exhaust_absent": True}
    result = gate_no_exhaust(dynamics, spec, "conventional_thrust")
    assert result["passed"] is False


def test_find_breakpoint_returns_relaxations():
    """Breakpoint finder returns relaxation suggestions."""
    spec = UFOBehaviorSpec.from_common_uap_profile("tic_tac")
    bp = find_breakpoint(spec, mass_kg=1000.0, policy="strict")
    assert "relaxations_to_viable" in bp
    assert isinstance(bp["relaxations_to_viable"], list)


def test_cli_writes_artifacts(tmp_path: Path):
    """CLI writes ufo_behavior_eval.json to artifacts."""
    import subprocess
    result = subprocess.run(
        [
            "python",
            "scripts/run_ufo_behavior_eval.py",
            "--project-root",
            str(tmp_path),
            "--profile",
            "tic_tac",
            "--mass-kg-min",
            "100",
            "--mass-kg-max",
            "1000",
            "--policy",
            "strict",
            "--no-registry",
        ],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    artifacts = list((tmp_path / "results" / "artifacts").glob("*_ufo_*"))
    assert len(artifacts) >= 1
    run_dir = artifacts[0]
    eval_path = run_dir / "ufo_behavior_eval.json"
    assert eval_path.exists()
    report = json.loads(eval_path.read_text(encoding="utf-8"))
    assert "verdict" in report
    assert "lane_results" in report


def test_from_custom_json(tmp_path):
    """Load spec from custom JSON."""
    path = tmp_path / "custom_spec.json"
    path.write_text(json.dumps({"max_accel_m_s2": 100.0, "max_speed_m_s": 200.0}), encoding="utf-8")
    spec = UFOBehaviorSpec.from_custom_json(path)
    assert spec.max_accel_m_s2 == 100.0
    assert spec.max_speed_m_s == 200.0
