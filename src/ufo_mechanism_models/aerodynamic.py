"""Aerodynamic lift / control surfaces lane.

Fail-fast for hover at high accel with no wings / no control surfaces.
"""

from __future__ import annotations

from typing import Any


def evaluate_aerodynamic(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate aerodynamic mechanism against behavior spec."""
    max_accel_m_s2 = dynamics.get("required_force_N", 0.0) / max(dynamics.get("mass_kg", 1.0), 0.1)
    # Reconstruct from dynamics: required_force_N / mass_kg
    mass_kg = dynamics.get("mass_kg", 1000.0)
    force_N = dynamics.get("required_force_N", mass_kg * 100.0)
    accel = force_N / mass_kg

    # Aerodynamic lift: L = (1/2) rho v² S Cl. For hover, v=0 → no lift.
    # High accel + reported "no wings" / "no control surfaces" (implied by tic-tac shape)
    # → aerodynamic cannot explain
    passed = True
    failure_reason = "none"

    # Hover requires thrust or buoyancy, not lift
    # High lateral accel (500g) with tight turn radius cannot be sustained by lift
    # unless wings are huge and speed is high. Tight turn + high accel = fail.
    if accel > 100.0:  # > ~10g
        passed = False
        failure_reason = "high_accel_hover_incompatible_with_aerodynamic_lift"

    return {
        "lane": "aerodynamic",
        "passed": passed,
        "dominant_failure_reason": failure_reason,
        "required_inputs": {
            "mass_kg": mass_kg,
            "max_accel_m_s2": accel,
        },
        "predicted_signatures": {
            "lift_surface_required": "large" if accel > 50.0 else "moderate",
            "vortex_shedding": "high",
        },
        "policy_snapshot": {"lane": "aerodynamic", "allow_speculative": False},
    }
