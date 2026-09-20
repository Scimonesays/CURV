"""Non-exhaust propulsion: photon pressure and other momentum-exchange modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from ..policy_ceilings import PowerEnergyCeilings, get_policy_ceilings

C_LIGHT = 299_792_458.0  # m/s

# Fail reasons
FAIL_POWER_EXCEEDS_CEILING = "photon_pressure_power_exceeds_ceiling"
FAIL_ENERGY_EXCEEDS_CEILING = "photon_pressure_energy_exceeds_ceiling"
FAIL_ENERGY_DENSITY_EXCEEDS = "photon_pressure_energy_density_exceeds_ceiling"
FAIL_VOLUME_MISSING = "volume_missing_for_energy_density"


class NonExhaustMode(str, Enum):
    PHOTON_PRESSURE = "photon_pressure"


@dataclass
class NonExhaustSpec:
    mode: NonExhaustMode = NonExhaustMode.PHOTON_PRESSURE
    reflectivity: float = 1.0
    beam_efficiency: float = 1.0
    allow_speculative: bool = False
    power_ceiling_W: float | None = None


def evaluate_non_exhaust_propulsion(
    physics: dict[str, Any],
    claims: Any,
    *,
    spec: NonExhaustSpec | None = None,
    policy: Literal["strict", "normal", "sandbox"] = "strict",
) -> dict[str, Any]:
    """Photon pressure: F = k*P/c with k=1+R for reflectivity R.

    Perfect reflector: F = 2P/c => P_beam = Fc/2.
    Required generated power P_gen = P_beam / beam_efficiency.
    """
    spec = spec or NonExhaustSpec()
    ceilings: PowerEnergyCeilings = get_policy_ceilings(policy)
    if spec.power_ceiling_W is not None:
        ceilings = PowerEnergyCeilings(
            max_total_power_W=spec.power_ceiling_W,
            max_total_energy_J=ceilings.max_total_energy_J,
            max_rho_j_m3=ceilings.max_rho_j_m3,
        )

    m = physics.get("mass_kg", 1000.0)
    a = physics.get("max_accel_m_s2")
    if a is None:
        F = physics.get("required_force_N", 0.0)
        a = F / m if m > 0 else 0.0
    v = physics.get("max_speed_m_s", 250.0)
    duration_s = physics.get("hover_duration_s", 60.0)
    volume_m3 = physics.get("active_volume_m3", 1.0)
    if volume_m3 is None or volume_m3 <= 0:
        volume_m3 = 1.0

    F_required = m * a
    R = max(0.0, min(1.0, spec.reflectivity))
    k = 1.0 + R
    P_beam = F_required * C_LIGHT / k
    P_gen = P_beam / max(0.01, spec.beam_efficiency)
    E_total = P_gen * duration_s
    rho_E = E_total / volume_m3 if volume_m3 > 0 else 0.0

    waste_heat_fraction = 1.0 - spec.beam_efficiency
    likely_thermal_W = P_gen * waste_heat_fraction

    reasons: list[str] = []
    if P_gen > ceilings.max_total_power_W:
        reasons.append(FAIL_POWER_EXCEEDS_CEILING)
    if E_total > ceilings.max_total_energy_J:
        reasons.append(FAIL_ENERGY_EXCEEDS_CEILING)
    if volume_m3 <= 0:
        reasons.append(FAIL_VOLUME_MISSING)
    elif rho_E > ceilings.max_rho_j_m3:
        reasons.append(FAIL_ENERGY_DENSITY_EXCEEDS)

    passed = len(reasons) == 0
    dominant = reasons[0] if reasons else None

    return {
        "lane": "non_exhaust_propulsion",
        "mode": "photon_pressure",
        "passed": passed,
        "dominant_failure_reason": dominant,
        "failure_reasons": reasons,
        "derived": {
            "required_force_N": F_required,
            "required_beam_power_W": P_beam,
            "required_generated_power_W": P_gen,
            "total_energy_J": E_total,
            "energy_density_J_m3": rho_E,
        },
        "predicted_signatures": {
            "beam_power_W": P_beam,
            "likely_thermal_W": likely_thermal_W,
            "beam_efficiency": spec.beam_efficiency,
        },
        "thrust_based": False,
        "momentum_exchange_mode": "photon_pressure",
        "shock_mitigation_declared": False,
        "heat_dump_explained": False,
        "coupling_reduction_declared": False,
    }
