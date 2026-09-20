"""Reactionless placeholder. Always speculative; must declare conservation changes."""

from __future__ import annotations

from typing import Any


def evaluate_reactionless_placeholder(
    physics: dict[str, Any],
    claims: Any,
    *,
    allow_speculative: bool = False,
) -> dict[str, Any]:
    power_W = physics.get("required_power_W", 0.0)
    force_N = physics.get("required_force_N", 0.0)
    mach = physics.get("mach_est", 0.0)

    passed = allow_speculative
    reason = "reactionless_requires_conservation_violation" if not allow_speculative else "none"

    return {
        "lane": "reactionless_placeholder",
        "passed": passed,
        "dominant_failure_reason": reason,
        "predicted_signatures": {
            "ir_brightness_proxy": 0.0,
            "em_activity_proxy": 0.0,
            "plasma_likelihood": "low",
            "sonic_boom_expected": mach > 1.0,
            "curvature_or_inertial_signature_predicted": allow_speculative,
        },
        "thrust_based": False,
        "shock_mitigation_declared": True,
        "heat_dump_explained": False,
        "coupling_reduction_declared": False,
        "momentum_exchange_mode": "inertial_mass_modification",
        "speculative_allowed": allow_speculative,
        "assumptions": {"conservation_law_modified": "momentum"},
    }
