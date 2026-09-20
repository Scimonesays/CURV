"""Reactionless / momentum-exchange placeholder ("new physics").

Allowed only if explicitly enabled.
Must output: what conservation law is being modified and by how much.
"""

from __future__ import annotations

from typing import Any


def evaluate_reactionless(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
    *,
    allow_speculative: bool = False,
) -> dict[str, Any]:
    """Evaluate reactionless mechanism. Fails unless allow_speculative."""
    mass_kg = dynamics.get("mass_kg", 1000.0)
    required_force_N = dynamics.get("required_force_N", 0.0)
    impulse_Ns = dynamics.get("impulse_Ns", 0.0)

    passed = False
    failure_reason = "reactionless_requires_speculative_physics"

    if allow_speculative:
        # In sandbox: mark as "passed" only to allow exploration
        # but always emit conservation-law modification
        passed = True
        failure_reason = "none"

    # Momentum violation magnitude: standard physics requires dP = F*dt from external source
    momentum_change_kg_m_s = impulse_Ns  # J = m*dv → same magnitude for impulse
    conservation_modification = {
        "law": "momentum_conservation",
        "modification_type": "reactionless_thrust",
        "implied_momentum_transfer_kg_m_s": momentum_change_kg_m_s,
        "external_reaction_required_by_standard_physics": required_force_N,
    }

    return {
        "lane": "reactionless",
        "passed": passed,
        "dominant_failure_reason": failure_reason,
        "required_inputs": {
            "mass_kg": mass_kg,
            "required_force_N": required_force_N,
            "impulse_Ns": impulse_Ns,
        },
        "predicted_signatures": {
            "no_exhaust": True,
            "no_reaction_mass": True,
            "sensor_signature": "unknown_requires_testable_prediction",
        },
        "policy_snapshot": {"lane": "reactionless", "allow_speculative": allow_speculative},
        "conservation_law_modification": conservation_modification,
    }
