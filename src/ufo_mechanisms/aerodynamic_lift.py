"""Aerodynamic lift. Fail-fast for hover at high accel with no wings."""

from __future__ import annotations

from typing import Any


def evaluate_aerodynamic_lift(physics: dict[str, Any], claims: Any) -> dict[str, Any]:
    power_W = physics.get("required_power_W", 0.0)
    mass_kg = physics.get("mass_kg", 1000.0)
    mach = physics.get("mach_est", 0.0)
    force_N = physics.get("required_force_N", 0.0)
    accel_g = force_N / (mass_kg * 9.81) if mass_kg > 0 else 0.0

    # High accel hover incompatible with lift (v=0 → L=0)
    passed = False
    reason = "high_accel_hover_incompatible_with_lift"

    sonic_boom_expected = mach > 1.0
    ir_brightness_proxy = power_W * 0.1  # induced drag heating

    return {
        "lane": "aerodynamic_lift",
        "passed": passed,
        "dominant_failure_reason": reason,
        "predicted_signatures": {
            "ir_brightness_proxy": ir_brightness_proxy,
            "em_activity_proxy": 0.0,
            "plasma_likelihood": "low",
            "sonic_boom_expected": sonic_boom_expected,
            "air_water_wake_predicted": True,
        },
        "thrust_based": False,
        "shock_mitigation_declared": False,
        "heat_dump_explained": False,
        "coupling_reduction_declared": False,
        "momentum_exchange_mode": "environment_interaction",
        "assumptions": {"thrust_based": False},
    }
