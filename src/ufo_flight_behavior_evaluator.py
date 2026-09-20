"""Unified UFO flight behavior evaluator with strict/normal/sandbox policies."""

from __future__ import annotations

from typing import Any, Literal

from .flight_dynamics_accounting import full_dynamics_report
from .ufo_behavior_spec import UFOBehaviorSpec
from .ufo_constraint_gates import evaluate_all_gates
from .ufo_mechanism_models import evaluate_all_lanes
from .ufo_signature_predictor import predict_signatures

PolicyPreset = Literal["strict", "normal", "sandbox"]
VerdictType = Literal[
    "physically_implausible_under_known_physics",
    "consistent_with_model_under_assumptions",
    "requires_speculative_physics",
]


def _policy_allow_speculative(policy: PolicyPreset) -> bool:
    if policy == "strict":
        return False
    if policy == "normal":
        return False
    if policy == "sandbox":
        return True
    return False


def evaluate_ufo_flight_behavior(
    spec: UFOBehaviorSpec,
    *,
    mass_kg_min: float,
    mass_kg_max: float,
    policy: PolicyPreset = "strict",
    allow_speculative: bool | None = None,
    frontal_area_m2: float = 1.0,
    altitude_m: float = 5000.0,
) -> dict[str, Any]:
    """Full evaluation pipeline: kinematics → lanes → gates → scorecard."""
    allow = allow_speculative if allow_speculative is not None else _policy_allow_speculative(policy)

    # Use geometric mean of mass range for dynamics
    import math
    mass_geo = math.sqrt(mass_kg_min * mass_kg_max) if mass_kg_min > 0 and mass_kg_max > 0 else (mass_kg_min + mass_kg_max) / 2

    dynamics = full_dynamics_report(
        mass_kg=mass_geo,
        max_accel_m_s2=spec.max_accel_m_s2,
        max_speed_m_s=spec.max_speed_m_s,
        turn_radius_m=spec.turn_radius_m,
        hover_duration_s=spec.hover_duration_s,
        frontal_area_m2=frontal_area_m2,
        altitude_m=altitude_m,
    )

    spec_dict = spec.to_dict()
    lane_results = evaluate_all_lanes(dynamics, spec_dict, allow_speculative=allow)

    top_conflicts: list[str] = []
    gate_results_all: dict[str, list] = {}

    for lr in lane_results["lane_results"]:
        lane_name = lr.get("lane", "unknown")
        gates = evaluate_all_gates(dynamics, spec_dict, lane_name)
        gate_results_all[lane_name] = gates
        for g in gates:
            if not g.get("passed", True):
                top_conflicts.append(
                    f"{lane_name}:{g.get('reason', 'unknown')}->{g.get('which_observation', '?')}"
                )

    signature_predictions = predict_signatures(dynamics, spec_dict, "conventional_thrust")

    # Verdict logic
    any_lane_passed = any(lr.get("passed", False) for lr in lane_results["lane_results"])
    speculative_lanes = ("reactionless", "field_propulsion")
    speculative_passed = any(
        lr.get("passed", False) and lr.get("lane") in speculative_lanes
        for lr in lane_results["lane_results"]
    )

    if speculative_passed:
        verdict: VerdictType = "requires_speculative_physics"
    elif any_lane_passed:
        verdict = "consistent_with_model_under_assumptions"
    else:
        verdict = "physically_implausible_under_known_physics"

    # Sensitivity: where it breaks
    accel_thresholds = [100.0, 500.0, 1000.0, 5000.0]
    mass_range = [mass_kg_min, mass_geo, mass_kg_max]
    where_breaks = (
        top_conflicts[0] if top_conflicts else "none"
    )

    return {
        "verdict": verdict,
        "top_conflicts": top_conflicts,
        "lane_results": lane_results["lane_results"],
        "gate_results": gate_results_all,
        "signature_predictions": signature_predictions,
        "dynamics": dynamics,
        "sensitivity": {
            "mass_kg_range": mass_range,
            "accel_thresholds": accel_thresholds,
            "where_it_breaks": where_breaks,
        },
        "policy": {"preset": policy, "allow_speculative": allow},
    }


def find_breakpoint(
    spec: UFOBehaviorSpec,
    *,
    mass_kg: float = 1000.0,
    policy: PolicyPreset = "strict",
) -> dict[str, Any]:
    """Find minimum change to observation that makes known physics viable.

    Answers: allow faint exhaust / modest thermal / weak sonic → viable?
    """
    spec_dict = spec.to_dict()
    dynamics = full_dynamics_report(
        mass_kg=mass_kg,
        max_accel_m_s2=spec.max_accel_m_s2,
        max_speed_m_s=spec.max_speed_m_s,
        turn_radius_m=spec.turn_radius_m,
        hover_duration_s=spec.hover_duration_s,
    )

    # Relaxations that could make conventional thrust pass
    relaxations = []
    power_w = dynamics.get("required_power_w", 0.0)
    sonic = dynamics.get("sonic_boom_expectation", {})
    expect_boom = sonic.get("expect_sonic_boom", False)

    if spec.visible_exhaust_absent and power_w > 1e5:
        relaxations.append({
            "observation": "visible_exhaust_absent",
            "min_relaxation": "allow_faint_exhaust",
            "threshold_power_w": 1e5,
        })
    if spec.thermal_signature_low and power_w > 1e7:
        relaxations.append({
            "observation": "thermal_signature_low",
            "min_relaxation": "allow_modest_thermal",
            "threshold_power_w": 1e7,
        })
    if spec.sonic_boom_absent and expect_boom:
        relaxations.append({
            "observation": "sonic_boom_absent",
            "min_relaxation": "allow_weak_sonic_event_or_subsonic_cap",
            "threshold_mach": 1.0,
        })

    return {
        "relaxations_to_viable": relaxations,
        "current_spec_conflicts": len(relaxations),
        "dynamics_summary": {
            "required_power_w": power_w,
            "expect_sonic_boom": expect_boom,
        },
    }
