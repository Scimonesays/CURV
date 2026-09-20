"""Element X edge-case lane: extreme hypothetical source for CURV honesty testing.

Intentionally extreme candidate (insane power density, near-perfect waste heat hiding,
shock suppression, transmedium). The engine should mostly spit out FAILs with crisp reasons.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..ufo_physics_accounting import compute_physics_accounting
from ..ufo_observables import UFOBehaviorSpec, UFOObservableClaims


class MomentumExchangeMode(str, Enum):
    EXHAUST = "exhaust"
    AIR_COUPLING = "air_coupling"
    FIELD_COUPLING = "field_coupling"
    METRIC_BUBBLE = "metric_bubble"


@dataclass
class ElementXSpec:
    """Edge-case source parameters."""

    max_power_density_w_m3: float = 1e18
    waste_heat_fraction: float = 1e-6
    shock_suppression: bool = True
    medium_coupling_factor: float = 1e-6
    momentum_exchange_mode: MomentumExchangeMode = MomentumExchangeMode.METRIC_BUBBLE
    allow_speculative: bool = False


def evaluate_element_x(
    behavior: UFOBehaviorSpec,
    claims: UFOObservableClaims,
    mass_range_kg: tuple[float, float],
    policy: str,
    element_x_spec: ElementXSpec,
) -> dict[str, Any]:
    """Evaluate Element X edge-case against behavior and claims.

    1. Compute required force/power from behavior
    2. Check whether Element X can supply it under max_power_density * active_volume
    3. Apply signature gates (shock, thermal, momentum, transmedium)
    4. Return passed, reasons, predicted_signatures
    """
    mass_geo = (mass_range_kg[0] * mass_range_kg[1]) ** 0.5
    physics = compute_physics_accounting(behavior, mass_geo)

    required_power_W = physics.get("required_power_W", 0.0)
    required_force_N = physics.get("required_force_N", 0.0)
    active_volume_m3 = physics.get("active_volume_m3", 1.0)

    reasons: list[str] = []
    passed = True

    # Default: speculative not enabled
    if not element_x_spec.allow_speculative:
        return {
            "lane": "element_x_edgecase",
            "passed": False,
            "dominant_failure_reason": "speculative_element_x_not_enabled",
            "reasons": ["speculative_element_x_not_enabled"],
            "predicted_signatures": _element_x_predicted_signatures(physics, claims, element_x_spec),
            "thrust_based": element_x_spec.momentum_exchange_mode == MomentumExchangeMode.EXHAUST,
            "shock_mitigation_declared": element_x_spec.shock_suppression,
            "heat_dump_explained": element_x_spec.waste_heat_fraction < 0.01,
            "energy_destination_predicted": "unspecified" if element_x_spec.waste_heat_fraction >= 0.01 else "element_x_heat_sink",
            "coupling_reduction_declared": element_x_spec.medium_coupling_factor < 0.01,
            "momentum_exchange_mode": _map_momentum_mode(element_x_spec.momentum_exchange_mode),
            "speculative_allowed": element_x_spec.allow_speculative,
            "assumptions": {"element_x_edgecase": True},
        }

    # Power density gate
    available_power_W = element_x_spec.max_power_density_w_m3 * active_volume_m3
    if required_power_W > available_power_W:
        reasons.append("energy_density_exceeds_ceiling")
        passed = False

    # Shock suppression: if claimed, must predict alternate signatures
    mach = physics.get("mach_est", 0.0)
    if mach > 1.0 and claims.sonic_boom_absent:
        if not element_x_spec.shock_suppression:
            reasons.append("shockwave_consistency")
            passed = False
        else:
            # Shock suppression declared: alternate signatures should be present
            # Element X with shock suppression could claim plasma/EM; if thermal_low claimed, conflict
            if claims.thermal_signature_low and element_x_spec.waste_heat_fraction < 1e-3:
                pass  # waste heat nearly zero; could still conflict with IR from plasma
            # Gate will check: mitigation_requires_alternate_signatures

    # Thermal consistency
    total_heat = required_power_W * element_x_spec.waste_heat_fraction
    if claims.thermal_signature_low and total_heat > 1e6:
        reasons.append("thermal_signature_conflict")
        passed = False

    # Transmedium drag/cavitation
    if behavior.transmedium and element_x_spec.medium_coupling_factor > 0.1:
        water_drag = physics.get("water_drag_W", 0.0)
        if water_drag > 1e6:
            reasons.append("transmedium_drag_cavitation")
            passed = False

    # Momentum conservation
    if claims.exhaust_absent and required_force_N > 1.0:
        mode = element_x_spec.momentum_exchange_mode
        if mode == MomentumExchangeMode.EXHAUST:
            reasons.append("momentum_exchange_unaccounted")
            passed = False
        elif mode == MomentumExchangeMode.METRIC_BUBBLE:
            # Routes through metric bubble logic; speculative must be allowed
            if policy != "sandbox":
                reasons.append("momentum_exchange_unaccounted")
                passed = False

    # Lensing requires paid curvature
    if claims.gravitational_lensing_reported:
        reasons.append("lensing_requires_paid_curvature")
        passed = False

    pred = _element_x_predicted_signatures(physics, claims, element_x_spec)

    return {
        "lane": "element_x_edgecase",
        "passed": passed,
        "dominant_failure_reason": reasons[0] if reasons else "none",
        "reasons": reasons,
        "predicted_signatures": pred,
        "thrust_based": element_x_spec.momentum_exchange_mode == MomentumExchangeMode.EXHAUST,
        "shock_mitigation_declared": element_x_spec.shock_suppression,
        "heat_dump_explained": element_x_spec.waste_heat_fraction < 0.01,
        "energy_destination_predicted": "unspecified" if element_x_spec.waste_heat_fraction >= 0.01 else "element_x_heat_sink",
        "coupling_reduction_declared": element_x_spec.medium_coupling_factor < 0.01,
        "cavitation_mitigation_declared": element_x_spec.medium_coupling_factor < 0.01,
        "momentum_exchange_mode": _map_momentum_mode(element_x_spec.momentum_exchange_mode),
        "speculative_allowed": element_x_spec.allow_speculative,
        "assumptions": {"element_x_edgecase": True},
    }


def _map_momentum_mode(mode: MomentumExchangeMode) -> str | None:
    """Map Element X momentum mode to gate-valid mode."""
    if mode == MomentumExchangeMode.EXHAUST:
        return None  # gate expects non-exhaust for exhaust_absent
    if mode == MomentumExchangeMode.AIR_COUPLING:
        return "environment_interaction"
    if mode == MomentumExchangeMode.FIELD_COUPLING:
        return "external_beam_field"
    if mode == MomentumExchangeMode.METRIC_BUBBLE:
        return "spacetime_metric"
    return None


def _element_x_predicted_signatures(
    physics: dict[str, Any],
    claims: UFOObservableClaims,
    spec: ElementXSpec,
) -> dict[str, Any]:
    """Build predicted signatures for Element X lane."""
    mach = physics.get("mach_est", 0.0)
    power_W = physics.get("required_power_W", 0.0)
    ir = power_W * spec.waste_heat_fraction if spec.waste_heat_fraction > 0 else 0.0
    return {
        "ir_brightness_proxy": ir,
        "em_activity_proxy": 0.0,  # Element X claims low EM
        "plasma_likelihood": "low",
        "sonic_boom_expected": mach > 1.0 and not spec.shock_suppression,
        "air_water_wake_predicted": spec.medium_coupling_factor > 0.01,
        "curvature_or_inertial_signature_predicted": spec.momentum_exchange_mode == MomentumExchangeMode.METRIC_BUBBLE,
    }
