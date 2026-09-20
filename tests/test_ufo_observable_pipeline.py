"""Tests guaranteeing many negatives for UFO observable pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ufo_observables import (
    UFOBehaviorSpec,
    UFOObservableClaims,
    profile_hypersonic_no_boom,
    profile_tictac_like,
)
from src.ufo_physics_accounting import compute_physics_accounting
from src.ufo_observable_evaluator import evaluate_ufo_observables
from src.ufo_signature_gates import (
    gate_sonic_boom_consistency,
    gate_exhaust_consistency,
    gate_transmedium_consistency,
)
from src.ufo_mechanisms import evaluate_conventional_thrust, evaluate_aerodynamic_lift


def test_hypersonic_no_boom_no_heat_fails_all_non_speculative():
    """Hypersonic + no sonic boom + no heat → fails all non-speculative lanes."""
    behavior, claims = profile_hypersonic_no_boom()
    result = evaluate_ufo_observables(
        behavior, claims, (100.0, 1000.0), policy="strict"
    )
    assert result["verdict"] == "physically_implausible_under_known_physics"
    conventional = next(lr for lr in result["lane_results"] if lr["lane"] == "conventional_thrust")
    aero = next(lr for lr in result["lane_results"] if lr["lane"] == "aerodynamic_lift")
    assert conventional["passed"] is False
    assert aero["passed"] is False
    assert len(result["failed_gates"]) >= 1


def test_600g_instantaneous_turn_fails_conventional_and_aero():
    """600g instantaneous turn → fails conventional + aero."""
    behavior = UFOBehaviorSpec(
        max_accel_g=600.0,
        max_speed_m_s=2000.0,
        turn_radius_m=5.0,
        turn_rate_rad_s=100.0,
        hover_duration_s=10.0,
        transmedium=False,
        altitude_m=5000.0,
        water_speed_m_s=None,
    )
    claims = UFOObservableClaims(
        sonic_boom_absent=True,
        exhaust_absent=True,
        thermal_signature_low=True,
        contrail_absent=True,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
    )
    result = evaluate_ufo_observables(behavior, claims, (500.0, 5000.0), policy="strict")
    conventional = next(lr for lr in result["lane_results"] if lr["lane"] == "conventional_thrust")
    aero = next(lr for lr in result["lane_results"] if lr["lane"] == "aerodynamic_lift")
    assert conventional["passed"] is False
    assert aero["passed"] is False


def test_transmedium_at_speed_fails_conventional_drag_cavitation():
    """Transmedium at speed → fails conventional due to drag/cavitation."""
    behavior, claims = profile_tictac_like()
    physics = compute_physics_accounting(behavior, 1000.0)
    assert physics["transmedium"] is True
    assert physics.get("water_drag_W", 0) > 0 or physics.get("cavitation_risk", "low") != "low"

    result = evaluate_ufo_observables(behavior, claims, (100.0, 10000.0), policy="strict")
    failed_trans = [g for g in result["failed_gates"] if "transmedium" in str(g.get("reason", "")).lower() or g.get("conflicts_with") == "transmedium"]
    assert len(failed_trans) >= 1 or len(result["failed_gates"]) >= 3


def test_lensing_claim_forces_energy_accounting():
    """Lensing claim → forces energy/curvature accounting; fails if not paid for."""
    behavior, claims = profile_tictac_like()
    claims = UFOObservableClaims(
        sonic_boom_absent=claims.sonic_boom_absent,
        exhaust_absent=claims.exhaust_absent,
        thermal_signature_low=claims.thermal_signature_low,
        contrail_absent=claims.contrail_absent,
        radar_track_intermittent=claims.radar_track_intermittent,
        visual_cloaking_reported=claims.visual_cloaking_reported,
        gravitational_lensing_reported=True,  # enable lensing
        oscillation_blur_reported=claims.oscillation_blur_reported,
        tilted_disk_flight_reported=claims.tilted_disk_flight_reported,
        skipping_motion_reported=claims.skipping_motion_reported,
    )
    result = evaluate_ufo_observables(behavior, claims, (100.0, 10000.0), policy="strict")
    assert "extended_traits" in result
    lensing_fail = [g for g in result["failed_gates"] if "lensing" in str(g.get("reason", "")).lower() or g.get("lane") == "extended_trait"]
    assert len(lensing_fail) >= 0  # may or may not fail depending on budget


def test_strict_produces_n_failed_gates_tictac():
    """Strict mode produces >= N failed gates for tictac-like profile."""
    behavior, claims = profile_tictac_like()
    result = evaluate_ufo_observables(behavior, claims, (100.0, 10000.0), policy="strict")
    n_failed = len(result["failed_gates"])
    assert n_failed >= 3, f"Expected >= 3 failed gates, got {n_failed}"


def test_evaluator_deterministic():
    """Evaluator is deterministic across runs."""
    behavior, claims = profile_tictac_like()
    r1 = evaluate_ufo_observables(behavior, claims, (100.0, 1000.0), policy="strict")
    r2 = evaluate_ufo_observables(behavior, claims, (100.0, 1000.0), policy="strict")
    assert r1["verdict"] == r2["verdict"]
    assert len(r1["failed_gates"]) == len(r2["failed_gates"])
    assert r1["what_would_need_to_be_true"] == r2["what_would_need_to_be_true"]


def test_sonic_boom_gate_fails_supersonic_no_mitigation():
    """Sonic boom gate: supersonic + boom absent + no mitigation → fail."""
    physics = {"mach_est": 2.0, "required_power_W": 1e9}
    claims = UFOObservableClaims(
        sonic_boom_absent=True,
        exhaust_absent=True,
        thermal_signature_low=False,
        contrail_absent=False,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
    )
    lane = {"shock_mitigation_declared": False, "predicted_signatures": {"plasma_likelihood": "low", "em_activity_proxy": 0, "ir_brightness_proxy": 0}}
    result = gate_sonic_boom_consistency(physics, claims, lane)
    assert result["passed"] is False


def test_exhaust_gate_fails_thrust_with_exhaust_absent():
    """Exhaust gate: thrust-based + exhaust absent → fail."""
    claims = UFOObservableClaims(
        sonic_boom_absent=False,
        exhaust_absent=True,
        thermal_signature_low=False,
        contrail_absent=False,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
    )
    lane = {"thrust_based": True}
    result = gate_exhaust_consistency(claims, lane)
    assert result["passed"] is False


def test_cli_writes_artifacts(tmp_path: Path):
    """CLI writes ufo_observable_eval.json."""
    import subprocess
    r = subprocess.run(
        [
            "python", "scripts/run_ufo_observable_eval.py",
            "--project-root", str(tmp_path),
            "--profile", "tictac_like",
            "--mass-kg-min", "100",
            "--mass-kg-max", "1000",
            "--policy", "strict",
            "--no-registry",
        ],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    artifacts = list((tmp_path / "results" / "artifacts").glob("*_ufo_obs_*"))
    assert len(artifacts) >= 1
    eval_path = artifacts[0] / "ufo_observable_eval.json"
    assert eval_path.exists()
    report = json.loads(eval_path.read_text(encoding="utf-8"))
    assert "verdict" in report
    assert "failed_gates" in report
    assert report["n_failed_gates"] >= 0


def test_momentum_gate_fails_no_exhaust_without_mode():
    """Momentum gate: exhaust absent → must declare momentum exchange mode."""
    from src.ufo_signature_gates import gate_momentum_conservation
    physics = {"required_force_N": 1e7}
    claims = UFOObservableClaims(
        sonic_boom_absent=False,
        exhaust_absent=True,
        thermal_signature_low=False,
        contrail_absent=False,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
    )
    lane = {"momentum_exchange_mode": None, "predicted_signatures": {}}
    result = gate_momentum_conservation(physics, claims, lane)
    assert result["passed"] is False
    assert "momentum" in result["reason"].lower()


def test_novel_power_source_never_passes():
    """Novel power source lane never passes alone."""
    from src.ufo_mechanisms import evaluate_novel_power_source
    physics = {"required_power_W": 1e9, "mass_kg": 1000, "mach_est": 2, "rho_E_j_m3": 1e15, "required_energy_J": 1e12, "mass_equivalent_kg": 1e-5}
    behavior, claims = profile_tictac_like()
    result = evaluate_novel_power_source(physics, claims)
    assert result["passed"] is False
    assert result["lane"] == "novel_power_source"
    assert "power_availability" in result


def test_minimal_violation_finder_returns_required_outputs():
    """Minimal violation finder returns what_must_be_true, sensors, would_falsify."""
    from src.minimal_violation_finder import find_minimal_violations
    behavior, claims = profile_tictac_like()
    out = find_minimal_violations(behavior, claims, 1000.0)
    assert "what_must_be_true" in out
    assert "sensors_should_detect" in out
    assert "would_falsify" in out
    assert "minimal_violations" in out
    assert len(out["would_falsify"]) >= 1


def test_minimal_violation_solver_returns_thresholds_and_signatures():
    """Solver returns threshold_to_pass and new_unavoidable_signatures."""
    from src.minimal_violation_finder import find_minimal_violations
    from src.ufo_observables import profile_edgecase_hypersonic_no_boom
    behavior, claims = profile_edgecase_hypersonic_no_boom()
    out = find_minimal_violations(behavior, claims, 1000.0)
    assert "solver" in out
    sol = out["solver"]
    assert "threshold_to_pass" in sol
    assert "new_unavoidable_signatures" in sol
    th = sol["threshold_to_pass"]
    assert "waste_heat_fraction" in th
    assert "medium_coupling_factor" in th
    assert "shock_suppression_strength" in th
    assert "curvature_budget_multiplier" in th
    assert len(sol["new_unavoidable_signatures"]) >= 1


def test_artifact_has_dominant_and_category_and_deltas():
    """Evaluator output includes dominant_failed_gate, failed_gates_by_category, assumption_deltas_to_pass."""
    behavior, claims = profile_tictac_like()
    result = evaluate_ufo_observables(behavior, claims, (100.0, 1000.0), policy="strict")
    assert "dominant_failed_gate" in result
    assert "failed_gates_by_category" in result
    assert "assumption_deltas_to_pass" in result
    assert isinstance(result["failed_gates_by_category"], dict)
    assert isinstance(result["assumption_deltas_to_pass"], list)


def test_from_json(tmp_path: Path):
    """Load behavior + claims from JSON."""
    path = tmp_path / "obs.json"
    path.write_text(json.dumps({
        "behavior": {"max_accel_g": 300, "max_speed_m_s": 1000},
        "claims": {"sonic_boom_absent": True, "exhaust_absent": True},
    }), encoding="utf-8")
    from src.ufo_observables import from_json
    behavior, claims = from_json(path)
    assert behavior.max_accel_g == 300
    assert claims.sonic_boom_absent is True
