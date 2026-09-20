"""Central policy ceiling profiles for UFO/lane evaluation.

Strict: today's physics + engineering plausibility.
Normal: aggressive human-future tech, still not magic.
Sandbox: pure exploration, maps minimum requirements (pass ≠ real).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PolicyName = Literal["strict", "normal", "sandbox"]


@dataclass
class PowerEnergyCeilings:
    """Ceilings for power, total energy, and energy density."""

    max_total_power_W: float
    max_total_energy_J: float
    max_rho_j_m3: float


def get_policy_ceilings(policy: PolicyName) -> PowerEnergyCeilings:
    """Return ceilings for photon pressure and similar non-exhaust propulsion."""
    if policy == "strict":
        # Today's physics + engineering plausibility
        return PowerEnergyCeilings(
            max_total_power_W=1e12,   # 1 TW
            max_total_energy_J=1e15,  # ~278 GWh
            max_rho_j_m3=1e20,
        )
    if policy == "normal":
        # Aggressive human-future tech, civilization-scale
        return PowerEnergyCeilings(
            max_total_power_W=1e15,   # 1 PW
            max_total_energy_J=1e18,
            max_rho_j_m3=1e22,
        )
    # Sandbox: pure exploration, maps minimum requirements
    return PowerEnergyCeilings(
        max_total_power_W=1e20,
        max_total_energy_J=1e24,
        max_rho_j_m3=1e28,
    )
