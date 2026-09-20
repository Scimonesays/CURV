"""Tests for non-exhaust photon pressure lane."""

from __future__ import annotations

import pytest

from src.ufo_mechanisms.non_exhaust_propulsion import (
    C_LIGHT,
    evaluate_non_exhaust_propulsion,
    NonExhaustSpec,
)
from src.ufo_observable_evaluator import evaluate_ufo_observables
from src.ufo_observables import UFOBehaviorSpec, UFOObservableClaims


def _step3_claims() -> UFOObservableClaims:
    return UFOObservableClaims(
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
        notes="no_exhaust neutral thermal/boom",
    )


def test_sanity_math_perfect_reflector() -> None:
    """For known m,a compute F and check P ≈ Fc/2 at R=1."""
    m = 1000.0
    a = 30.0 * 9.81
    physics = {
        "mass_kg": m,
        "max_accel_m_s2": a,
        "max_speed_m_s": 250.0,
        "hover_duration_s": 60.0,
        "active_volume_m3": 1.0,
    }
    spec = NonExhaustSpec(reflectivity=1.0, beam_efficiency=1.0)
    result = evaluate_non_exhaust_propulsion(physics, None, spec=spec, policy="sandbox")
    derived = result["derived"]
    F = m * a
    P_expected = F * C_LIGHT / 2.0
    P_beam = derived["required_beam_power_W"]
    assert abs(P_beam - P_expected) / max(P_expected, 1.0) < 0.01
    assert derived["required_force_N"] == pytest.approx(F, rel=1e-6)


def test_strict_policy_fail_step3_profile() -> None:
    """Step 3 profile should fail with photon_pressure_power_exceeds_ceiling for 100-10000 kg."""
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
    claims = _step3_claims()
    result = evaluate_ufo_observables(
        behavior, claims, (100.0, 10000.0), policy="strict"
    )
    non_exhaust = next(
        (lr for lr in result["lane_results"] if lr.get("lane") == "non_exhaust_propulsion"),
        None,
    )
    assert non_exhaust is not None
    assert non_exhaust["passed"] is False
    reasons = non_exhaust.get("failure_reasons", [])
    assert "photon_pressure_power_exceeds_ceiling" in reasons or any(
        "photon_pressure" in r for r in reasons
    )


def test_artifacts_include_beam_power() -> None:
    """Lane output includes computed beam power in derived and predicted_signatures."""
    physics = {
        "mass_kg": 1000.0,
        "max_accel_m_s2": 30.0 * 9.81,
        "max_speed_m_s": 250.0,
        "hover_duration_s": 60.0,
        "active_volume_m3": 1.0,
    }
    claims = _step3_claims()
    result = evaluate_non_exhaust_propulsion(physics, claims, policy="strict")
    assert "derived" in result
    assert "required_generated_power_W" in result["derived"]
    assert "predicted_signatures" in result
    assert "beam_power_W" in result["predicted_signatures"]
    assert result["derived"]["required_generated_power_W"] > 1e12
