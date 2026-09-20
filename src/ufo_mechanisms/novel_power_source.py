"""Novel power source lane: NEVER passes by itself.

Provides power availability only. Energy alone does not buy silent hypersonic
right-angle turns. Must still pass: power density, thermal, sonic boom,
momentum conservation, transmedium gates.

Prevents: "we found energy therefore UFO flight is solved."
"""

from __future__ import annotations

from typing import Any


def evaluate_novel_power_source(physics: dict[str, Any], claims: Any) -> dict[str, Any]:
    """Power availability lane. Always fails - energy is necessary but not sufficient."""
    power_W = physics.get("required_power_W", 0.0)
    mass_kg = physics.get("mass_kg", 1000.0)
    mach = physics.get("mach_est", 0.0)
    rho_E = physics.get("rho_E_j_m3", 0.0)
    mass_equiv = physics.get("mass_equivalent_kg", 0.0)

    passed = False
    reason = "novel_power_source_never_passes_alone_must_also_satisfy_signature_gates"

    return {
        "lane": "novel_power_source",
        "passed": passed,
        "dominant_failure_reason": reason,
        "predicted_signatures": {
            "ir_brightness_proxy": 0.0,
            "em_activity_proxy": 0.0,
            "plasma_likelihood": "unknown",
            "sonic_boom_expected": mach > 1.0,
            "waste_heat_destination": "unspecified",
            "momentum_exchange_mode": None,
        },
        "power_availability": {
            "required_power_W": power_W,
            "required_energy_J": physics.get("required_energy_J", 0.0),
            "rho_E_j_m3": rho_E,
            "mass_equivalent_kg": mass_equiv,
        },
        "thrust_based": False,
        "shock_mitigation_declared": False,
        "heat_dump_explained": False,
        "coupling_reduction_declared": False,
        "momentum_exchange_mode": None,
        "assumptions": {
            "energy_necessary_not_sufficient": True,
            "must_pass_signature_bill": True,
        },
    }
