"""Tests for Breakthrough Ladder runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.breakthrough_ladder import (
    BreakthroughStep,
    build_ladder_steps,
    run_breakthrough_ladder,
)
from src.ufo_observables import UFOBehaviorSpec, UFOObservableClaims


def test_step1_runs_and_produces_report(tmp_path: Path) -> None:
    """Ensure step 1 runs and produces a report object."""
    steps = build_ladder_steps(include_speculative=False)
    assert len(steps) >= 1
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = "test_run_001"
    report = run_breakthrough_ladder(steps[:1], (100.0, 10000.0), output_dir, run_id)
    assert "run_id" in report
    assert report["run_id"] == run_id
    assert "steps" in report
    assert len(report["steps"]) == 1
    assert "overall" in report
    step1 = report["steps"][0]
    assert step1["step"] == 1
    assert step1["name"] == "tictac_lite_baseline"


def test_steps_in_correct_order() -> None:
    """Ensure steps are in correct order 1-7 (and optionally 8)."""
    steps = build_ladder_steps(include_speculative=False)
    names = [
        "tictac_lite_baseline",
        "tictac_lite_known_physics_sanity",
        "no_exhaust",
        "low_thermal",
        "supersonic_no_boom",
        "transmedium",
        "lensing",
    ]
    assert len(steps) == 7
    for i, (step, expected_name) in enumerate(zip(steps, names)):
        assert step.name == expected_name, f"Step {i+1} should be {expected_name}"
        assert step.step_id == i + 1

    steps_with_spec = build_ladder_steps(include_speculative=True)
    assert len(steps_with_spec) == 8
    assert steps_with_spec[7].name == "speculative_sandbox"


def test_report_includes_n_failed_gates_and_dominant(tmp_path: Path) -> None:
    """Ensure report includes n_failed_gates and dominant_failed_gate."""
    steps = build_ladder_steps(include_speculative=False)
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    report = run_breakthrough_ladder(steps, (100.0, 10000.0), output_dir, "test_002")
    for s in report["steps"]:
        assert "n_failed_gates" in s
        assert isinstance(s["n_failed_gates"], int)
        assert "dominant_failed_gate" in s


def test_strict_mode_monotonic_or_ties(tmp_path: Path) -> None:
    """Strict mode: from no_exhaust onward, failure pressure is non-decreasing.
    Steps 1–2 (baseline, 30g sanity) may tie; steps 3+ add constraints."""
    steps = build_ladder_steps(include_speculative=False, policy_override="strict")
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    report = run_breakthrough_ladder(steps, (100.0, 10000.0), output_dir, "test_003")
    n_failed_list = [s["n_failed_gates"] for s in report["steps"]]
    # From step 3 (no_exhaust) onward: monotonic non-decreasing
    for i in range(2, len(n_failed_list)):
        assert n_failed_list[i] >= n_failed_list[i - 1], (
            f"Step {i+1} n_failed={n_failed_list[i]} < step {i} n_failed={n_failed_list[i-1]}"
        )


def test_per_step_artifact_written(tmp_path: Path) -> None:
    """Per-step JSON artifacts are written to breakthrough_steps/."""
    steps = build_ladder_steps(include_speculative=False)[:2]
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_breakthrough_ladder(steps, (100.0, 10000.0), output_dir, "test_004")
    steps_dir = output_dir / "breakthrough_steps"
    assert steps_dir.exists()
    files = list(steps_dir.glob("*.json"))
    assert len(files) >= 2
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "step" in data
        assert "verdict" in data
        assert "n_failed_gates" in data


def test_zero_gates_no_lane_pass_verdict_requires_speculative() -> None:
    """When n_failed_gates==0 but no lane passes, verdict is requires_speculative_physics."""
    from src.ufo_observable_evaluator import evaluate_ufo_observables

    behavior = UFOBehaviorSpec(
        max_accel_g=300.0,  # extreme, no conventional lane passes
        max_speed_m_s=250.0,
        turn_radius_m=50.0,
        turn_rate_rad_s=10.0,
        hover_duration_s=60.0,
        transmedium=False,
        altitude_m=5000.0,
        water_speed_m_s=None,
    )
    claims = UFOObservableClaims(
        sonic_boom_absent=False,
        exhaust_absent=False,
        thermal_signature_low=False,
        contrail_absent=False,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
    )
    result = evaluate_ufo_observables(behavior, claims, (100.0, 10000.0), policy="strict")
    n_failed = len(result["failed_gates"])
    if n_failed == 0:
        assert result["verdict"] == "requires_speculative_physics", (
            f"Expected requires_speculative_physics when gates=0, got {result['verdict']}"
        )


def test_summary_json_written(tmp_path: Path) -> None:
    """breakthrough_ladder_summary.json is written."""
    steps = build_ladder_steps(include_speculative=False)[:1]
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_breakthrough_ladder(steps, (100.0, 10000.0), output_dir, "test_005")
    summary = output_dir / "breakthrough_ladder_summary.json"
    assert summary.exists()
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["run_id"] == "test_005"
    assert "overall" in data
    assert "deepest_step_reached_without_speculation" in data["overall"]
    assert "first_failure_step" in data["overall"]
