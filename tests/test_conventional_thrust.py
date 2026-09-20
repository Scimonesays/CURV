"""Tests for conventional thrust mechanism with ConventionalThrustSpec."""

from __future__ import annotations

import pytest

from src.ufo_mechanisms.conventional_thrust import (
    ConventionalThrustSpec,
    PRESET_ROCKET,
    evaluate_conventional_thrust,
)
from src.ufo_observable_evaluator import evaluate_ufo_observables
from src.ufo_observables import UFOBehaviorSpec, UFOObservableClaims


def _minimal_claims() -> UFOObservableClaims:
    return UFOObservableClaims(
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


def test_step2_30g_passes_for_rocket_at_low_mass() -> None:
    """Step 2 (30g) should pass for rocket preset at 100-500 kg."""
    behavior = UFOBehaviorSpec(
        max_accel_g=30.0,
        max_speed_m_s=250.0,
        turn_radius_m=50.0,
        turn_rate_rad_s=10.0,
        hover_duration_s=60.0,
        transmedium=False,
        altitude_m=5000.0,
        water_speed_m_s=None,
    )
    claims = _minimal_claims()
    physics = {
        "mass_range_kg": (100.0, 500.0),
        "max_accel_m_s2": 30.0 * 9.81,
        "max_speed_m_s": 250.0,
        "hover_duration_s": 60.0,
        "mass_kg": 300.0,
        "required_power_W": 300 * 30 * 9.81 * 250,
        "required_force_N": 300 * 30 * 9.81,
        "mach_est": 250 / 343,
    }
    result = evaluate_conventional_thrust(physics, claims)
    assert result["passed"] is True, f"Expected pass, got reasons: {result.get('failure_reasons')}"
    assert result.get("passing_preset") == "rocket"
    assert result.get("passing_mass_kg") is not None


def test_step1_300g_fails_all_presets() -> None:
    """Step 1 (300g) should fail for all presets in strict mode."""
    physics = {
        "mass_range_kg": (100.0, 10000.0),
        "max_accel_m_s2": 300.0 * 9.81,
        "max_speed_m_s": 250.0,
        "hover_duration_s": 60.0,
        "mass_kg": 1000.0,
        "required_power_W": 1000 * 300 * 9.81 * 250,
        "required_force_N": 1000 * 300 * 9.81,
        "mach_est": 250 / 343,
    }
    claims = _minimal_claims()
    result = evaluate_conventional_thrust(physics, claims)
    assert result["passed"] is False
    assert "failure_reasons" in result
    assert len(result["failure_reasons"]) >= 1


def test_failure_includes_reason_codes() -> None:
    """Failed evaluation includes explicit reason codes."""
    physics = {
        "mass_range_kg": (100.0, 500.0),
        "max_accel_m_s2": 300.0 * 9.81,
        "max_speed_m_s": 250.0,
        "hover_duration_s": 60.0,
        "mass_kg": 300.0,
        "required_power_W": 1e12,
        "required_force_N": 1e6,
        "mach_est": 0.8,
    }
    claims = _minimal_claims()
    result = evaluate_conventional_thrust(physics, claims)
    assert result["passed"] is False
    assert "dominant_failure_reason" in result
    assert result["dominant_failure_reason"] in (
        "tw_insufficient",
        "sustained_power_exceeds_limit",
        "burst_only_not_applicable",
        "g_load_unrealistic_for_structure",
    )


def test_step2_evaluator_consistent_or_lane_passes() -> None:
    """Step 2 (30g, minimal claims) yields consistent_with_model or at least a lane passes."""
    behavior = UFOBehaviorSpec(
        max_accel_g=30.0,
        max_speed_m_s=250.0,
        turn_radius_m=50.0,
        turn_rate_rad_s=10.0,
        hover_duration_s=60.0,
        transmedium=False,
        altitude_m=5000.0,
        water_speed_m_s=None,
    )
    claims = _minimal_claims()
    result = evaluate_ufo_observables(
        behavior, claims, (100.0, 500.0), policy="strict"
    )
    conventional = next(
        lr for lr in result["lane_results"] if lr["lane"] == "conventional_thrust"
    )
    assert conventional["passed"] is True
    assert result["verdict"] == "consistent_with_model_under_assumptions"


def test_step1_evaluator_remains_requires_speculative() -> None:
    """Step 1 (300g) remains requires_speculative_physics (no gate failures, no lane passes)."""
    behavior = UFOBehaviorSpec(
        max_accel_g=300.0,
        max_speed_m_s=250.0,
        turn_radius_m=50.0,
        turn_rate_rad_s=10.0,
        hover_duration_s=60.0,
        transmedium=False,
        altitude_m=5000.0,
        water_speed_m_s=None,
    )
    claims = _minimal_claims()
    result = evaluate_ufo_observables(
        behavior, claims, (100.0, 10000.0), policy="strict"
    )
    conventional = next(
        lr for lr in result["lane_results"] if lr["lane"] == "conventional_thrust"
    )
    assert conventional["passed"] is False
    assert result["verdict"] in ("requires_speculative_physics", "physically_implausible_under_known_physics")
