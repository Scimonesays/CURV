"""Minimal Violation Finder: smallest needed "impossible thing" for observables.

Given 600g + hypersonic + no boom + low heat + no exhaust, solve for:
- inertial-damping factor
- shock suppression strength
- coupling reduction to air/water
- allowable waste-heat channel

Output: what must be true, what sensors should detect, what would falsify it.

Minimal Violation Solver: threshold-to-pass for 4 knobs plus new unavoidable signatures.
"""

from __future__ import annotations

from typing import Any

from .ufo_observables import UFOBehaviorSpec, UFOObservableClaims
from .ufo_physics_accounting import compute_physics_accounting


def solve_minimal_violations(
    behavior: UFOBehaviorSpec,
    claims: UFOObservableClaims,
    mass_kg: float = 1000.0,
) -> dict[str, Any]:
    """Solve for minimum knob values to barely pass. Discovery engine.

    Four knobs: waste_heat_fraction, medium_coupling_factor, shock_suppression_strength,
    curvature_budget_multiplier.

    Returns threshold_to_pass (min values) and new_unavoidable_signatures if those
    assumptions were made.
    """
    physics = compute_physics_accounting(behavior, mass_kg)
    power_W = physics.get("required_power_W", 0.0)
    mach = physics.get("mach_est", 0.0)
    air_W = physics.get("air_heating_W", 0.0)
    water_W = physics.get("water_drag_W", 0.0)

    threshold_to_pass: dict[str, Any] = {}

    # waste_heat_fraction: thermal gate passes if total_heat < 1e6
    if claims.thermal_signature_low and (power_W + air_W) > 1e6:
        max_waste = 1e6 / max(power_W, 1.0)
        threshold_to_pass["waste_heat_fraction"] = {
            "max_value": max_waste,
            "interpretation": f"Waste heat fraction must be <= {max_waste:.2e} for thermal_signature_low",
        }
    else:
        threshold_to_pass["waste_heat_fraction"] = {"max_value": 1.0, "interpretation": "No constraint"}

    # medium_coupling_factor: transmedium needs coupling reduction
    if behavior.transmedium and water_W > 1e6:
        # Effective drag scales with coupling; to avoid cavitation/drag conflict, need < 1%
        threshold_to_pass["medium_coupling_factor"] = {
            "max_value": 0.01,
            "interpretation": "Medium coupling must be < 1% for transmedium without catastrophic drag",
        }
    else:
        threshold_to_pass["medium_coupling_factor"] = {"max_value": 1.0, "interpretation": "No constraint"}

    # shock_suppression: must be enabled if mach > 1 and sonic_boom_absent
    if claims.sonic_boom_absent and mach > 1.0:
        threshold_to_pass["shock_suppression_strength"] = {
            "min_value": mach,
            "interpretation": f"Shock suppression at least Mach {mach:.1f} equivalent",
        }
    else:
        threshold_to_pass["shock_suppression_strength"] = {"min_value": 0.0, "interpretation": "No constraint"}

    # curvature_budget_multiplier: lensing must be paid for
    if claims.gravitational_lensing_reported:
        # Lensing implies curvature; budget scales with mass. Need consistency.
        rest_J = mass_kg * (299792458.0**2)
        threshold_to_pass["curvature_budget_multiplier"] = {
            "min_value": 1.0,
            "interpretation": "Curvature budget must match mass/energy for lensing claim",
        }
    else:
        threshold_to_pass["curvature_budget_multiplier"] = {"min_value": 0.0, "interpretation": "No constraint"}

    # New unavoidable signatures if you assume these thresholds
    new_unavoidable_signatures: list[str] = []
    if threshold_to_pass["waste_heat_fraction"].get("max_value", 1.0) < 0.01:
        new_unavoidable_signatures.append(
            "thermal_emission_somewhere_or_entropy_hiding_requires_testable_alternative"
        )
    if threshold_to_pass["medium_coupling_factor"].get("max_value", 1.0) < 0.1:
        new_unavoidable_signatures.append(
            "reduced_wake_turbulence_or_anomalous_water_interaction_detectable"
        )
    if threshold_to_pass["shock_suppression_strength"].get("min_value", 0) > 0:
        new_unavoidable_signatures.append(
            "plasma_ionization_or_em_activity_near_craft_if_shock_redirected"
        )
    if claims.gravitational_lensing_reported:
        new_unavoidable_signatures.append(
            "gravitational_deflection_or_metric_anomaly_detectable"
        )

    return {
        "threshold_to_pass": threshold_to_pass,
        "new_unavoidable_signatures": new_unavoidable_signatures,
        "to_pass_summary": (
            "To pass, you must assume at least these extreme values. "
            "If true, the listed signatures become unavoidable and testable."
        ),
    }


def find_minimal_violations(
    behavior: UFOBehaviorSpec,
    claims: UFOObservableClaims,
    mass_kg: float = 1000.0,
) -> dict[str, Any]:
    """Compute minimal violation parameters required for observables to be consistent.

    Returns smallest needed: inertial damping, shock suppression, coupling reduction,
    waste-heat channel. Plus: what must be true, what sensors detect, what falsifies.
    """
    physics = compute_physics_accounting(behavior, mass_kg)

    power_W = physics.get("required_power_W", 0.0)
    force_N = physics.get("required_force_N", 0.0)
    mach = physics.get("mach_est", 0.0)
    air_W = physics.get("air_heating_W", 0.0)
    water_W = physics.get("water_drag_W", 0.0)

    # Minimum needed violations (order-of-magnitude proxies)
    inertial_damping_factor = 1.0
    if claims.exhaust_absent and force_N > 0:
        # Standard physics: F = dp/dt from exhaust. No exhaust → need alternative.
        # "Inertial damping" = effective reduction in m to avoid exhaust. Proxy: N/A.
        inertial_damping_factor = 1.0  # 1 = standard; mechanism must supply force_N

    shock_suppression_strength = 0.0
    if claims.sonic_boom_absent and mach > 1.0:
        # Must suppress shock. Proxy: pressure ratio reduction factor.
        shock_suppression_strength = mach  # Mach number to suppress

    coupling_reduction_air = 1.0
    coupling_reduction_water = 1.0
    if claims.thermal_signature_low and air_W > 1e6:
        coupling_reduction_air = air_W / 1e6  # Factor by which air coupling must drop
    if behavior.transmedium and water_W > 1e6:
        coupling_reduction_water = water_W / 1e6

    waste_heat_channel_w = 0.0
    if claims.thermal_signature_low and power_W > 1e6:
        waste_heat_channel_w = power_W  # Must divert this much

    # What must be true
    what_must_be_true = []
    if claims.exhaust_absent:
        what_must_be_true.append(
            "momentum_exchange_via_environment_or_speculative_mechanism"
        )
    if claims.sonic_boom_absent and mach > 1.0:
        what_must_be_true.append(
            f"shock_suppression_or_deflection_at_mach_{mach:.1f}"
        )
    if claims.thermal_signature_low and power_W > 1e6:
        what_must_be_true.append(
            f"waste_heat_channel_{waste_heat_channel_w:.2e}_W_or_entropy_hiding"
        )
    if behavior.transmedium and water_W > 0:
        what_must_be_true.append(
            "reduced_coupling_to_water_or_cavitation_mitigation"
        )

    # What sensors should detect
    sensors_should_detect = []
    if inertial_damping_factor > 1.0 or claims.exhaust_absent:
        sensors_should_detect.append(
            "em_field_or_environmental_wake_or_metric_anomaly"
        )
    if shock_suppression_strength > 0:
        sensors_should_detect.append(
            "plasma_ionization_or_em_near_craft_if_shock_redirected"
        )
    if waste_heat_channel_w > 0:
        sensors_should_detect.append(
            "thermal_emission_somewhere_or_invalid_thermodynamics"
        )
    if coupling_reduction_water > 1.0:
        sensors_should_detect.append(
            "reduced_wake_turbulence_or_anomalous_water_interaction"
        )

    # What would falsify
    would_falsify = []
    would_falsify.append(
        "detection_of_standard_exhaust_at_reported_power_level"
    )
    would_falsify.append(
        "sonic_boom_at_ground_level_when_craft_supersonic_overhead"
    )
    would_falsify.append(
        "ir_signature_consistent_with_power_budget_at_close_range"
    )
    would_falsify.append(
        "standard_drag_heating_in_water_entry_exit"
    )
    would_falsify.append(
        "no_anomalous_em_plasma_or_metric_signal_when_exhaust_absent"
    )

    solver = solve_minimal_violations(behavior, claims, mass_kg)

    return {
        "minimal_violations": {
            "inertial_damping_factor": inertial_damping_factor,
            "shock_suppression_strength": shock_suppression_strength,
            "coupling_reduction_air": coupling_reduction_air,
            "coupling_reduction_water": coupling_reduction_water,
            "allowable_waste_heat_channel_W": waste_heat_channel_w,
        },
        "solver": solver,
        "what_must_be_true": what_must_be_true,
        "sensors_should_detect": sensors_should_detect,
        "would_falsify": would_falsify,
        "physics": {
            "required_power_W": power_W,
            "required_force_N": force_N,
            "mach_est": mach,
            "air_heating_W": air_W,
            "water_drag_W": water_W,
            "rho_E_j_m3": physics.get("rho_E_j_m3"),
            "mass_equivalent_kg": physics.get("mass_equivalent_kg"),
        },
    }
