"""Unified UFO observable evaluator: negative-heavy scorecard."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Literal

from .gate_category_mapping import (
    dominant_failed_gate as _dominant_failed_gate,
    failed_gates_by_category,
)
from .minimal_violation_finder import find_minimal_violations
from .ufo_extended_traits import gate_lensing_energy_budget, lensing_deflection_proxy, record_extended_traits
from .ufo_mechanisms import evaluate_all_lanes
from .ufo_observables import UFOBehaviorSpec, UFOObservableClaims
from .ufo_physics_accounting import compute_physics_accounting
from .ufo_signature_gates import evaluate_all_signature_gates
from .ufo_mechanisms.element_x_edgecase import ElementXSpec, evaluate_element_x

PolicyPreset = Literal["strict", "normal", "sandbox"]
VerdictType = Literal[
    "physically_implausible_under_known_physics",
    "requires_speculative_physics",
    "consistent_with_model_under_assumptions",
]


def _allow_speculative(policy: PolicyPreset) -> bool:
    return policy == "sandbox"


def _derive_assumption_deltas(
    failed_gates: list[dict],
    physics: dict,
    claims: Any,
    behavior: Any,
    minimal: dict,
) -> list[dict]:
    """Heuristic: likely required changes to pass. Even before full solver."""
    deltas: list[dict] = []
    reasons_seen: set[str] = set()

    for g in failed_gates:
        r = g.get("reason", "")
        if r in reasons_seen:
            continue
        reasons_seen.add(r)
        cw = g.get("conflicts_with", "")
        sev = g.get("severity", "med")

        if "supersonic_no_boom" in r or "shock" in r.lower() or "mitigation" in r.lower():
            deltas.append({
                "delta": "shock_mitigation_or_allow_sonic_boom",
                "conflicts_with": cw or "sonic_boom_absent",
                "severity": sev,
            })
        elif "thermal" in r.lower() or "heat" in r.lower() or "ir_" in r:
            sol = minimal.get("solver", {})
            thresh = sol.get("threshold_to_pass", {}).get("waste_heat_fraction", {})
            deltas.append({
                "delta": "reduce_waste_heat_fraction",
                "threshold": thresh.get("interpretation", "waste_heat < 1e6/power"),
                "conflicts_with": cw or "thermal_signature_low",
                "severity": sev,
            })
        elif "transmedium" in r.lower() or "coupling" in r.lower() or "cavitation" in r.lower():
            sol = minimal.get("solver", {})
            thresh = sol.get("threshold_to_pass", {}).get("medium_coupling_factor", {})
            deltas.append({
                "delta": "reduce_medium_coupling_factor",
                "threshold": thresh.get("interpretation", "coupling < 1%"),
                "conflicts_with": cw or "transmedium",
                "severity": sev,
            })
        elif "lensing" in r.lower() or "curvature" in r.lower():
            deltas.append({
                "delta": "curvature_budget_or_drop_lensing_claim",
                "conflicts_with": cw or "gravitational_lensing_reported",
                "severity": sev,
            })
        elif "momentum" in r.lower() or "exhaust" in r.lower():
            deltas.append({
                "delta": "declare_momentum_exchange_mode_or_allow_exhaust",
                "conflicts_with": cw or "exhaust_absent",
                "severity": sev,
            })
        elif "contrail" in r.lower():
            deltas.append({
                "delta": "reduce_air_heating_or_allow_contrail",
                "conflicts_with": cw or "contrail_absent",
                "severity": sev,
            })
        elif "power" in r.lower() or "energy" in r.lower():
            deltas.append({
                "delta": "reduce_power_density_requirement_or_relax_constraint",
                "conflicts_with": cw or "power_density",
                "severity": sev,
            })

    return deltas


def evaluate_ufo_observables(
    behavior: UFOBehaviorSpec,
    claims: UFOObservableClaims,
    mass_range_kg: tuple[float, float],
    *,
    policy: PolicyPreset = "strict",
    frontal_area_m2: float = 1.0,
    element_x_spec: Any = None,
    enable_element_x: bool = True,
    allow_speculative_override: bool | None = None,
) -> dict[str, Any]:
    """Full pipeline: physics → lanes → gates → negative-heavy scorecard."""
    allow = allow_speculative_override if allow_speculative_override is not None else _allow_speculative(policy)
    mass_geo = (mass_range_kg[0] * mass_range_kg[1]) ** 0.5

    physics = compute_physics_accounting(behavior, mass_geo, frontal_area_m2)
    physics["mass_range_kg"] = mass_range_kg

    lane_results = evaluate_all_lanes(
        physics, claims, allow_speculative=allow, policy=policy
    )

    # Element X edge-case lane: always evaluate, always log
    base = element_x_spec if isinstance(element_x_spec, ElementXSpec) else ElementXSpec()
    ex_spec = replace(base, allow_speculative=allow if enable_element_x else False)
    element_x_result = evaluate_element_x(
        behavior, claims, mass_range_kg, policy, ex_spec
    )
    lane_results = list(lane_results) + [element_x_result]

    failed_gates: list[dict[str, Any]] = []
    gate_results_by_lane: dict[str, list] = {}

    for lr in lane_results:
        lane_name = lr.get("lane", "unknown")
        gates = evaluate_all_signature_gates(physics, claims, lr)
        gate_results_by_lane[lane_name] = gates
        for g in gates:
            if not g.get("passed", True):
                failed_gates.append({
                    "lane": lane_name,
                    "reason": g.get("reason", ""),
                    "severity": g.get("severity", "med"),
                    "conflicts_with": g.get("conflicts_with"),
                })

    # Suppress redundant exhaust failures when non-exhaust mode is declared
    non_exhaust_active = any(
        lr.get("lane") == "non_exhaust_propulsion" and lr.get("momentum_exchange_mode")
        for lr in lane_results
    )
    if claims.exhaust_absent and non_exhaust_active:
        redundant = {"thrust_requires_exhaust", "no_exhaust_requires_momentum_exchange_declaration"}
        failed_gates = [g for g in failed_gates if g.get("reason") not in redundant]
        # Prefer photon_pressure power failure as dominant when present
        photon_failures = [g for g in failed_gates if "photon_pressure" in str(g.get("reason", ""))]
        if photon_failures:
            other = [g for g in failed_gates if g not in photon_failures]
            failed_gates = photon_failures + other

    # Extended traits
    extended = record_extended_traits(claims, physics)
    if claims.gravitational_lensing_reported:
        lens = lensing_deflection_proxy(
            physics.get("mass_kg", 1000.0), 10.0, 1000.0
        )
        gl = gate_lensing_energy_budget(
            True, lens, physics.get("required_power_W", 0.0),
            physics.get("mass_kg", 1000.0),
        )
        if not gl.get("passed", True):
            failed_gates.append({
                "lane": "extended_trait",
                "reason": gl.get("reason", "lensing"),
                "severity": gl.get("severity", "med"),
                "conflicts_with": "gravitational_lensing_reported",
            })

    # Lane rankings: by fewest failed gates
    lane_fail_counts = {}
    for lr in lane_results:
        name = lr["lane"]
        count = sum(1 for g in gate_results_by_lane.get(name, []) if not g.get("passed", True))
        lane_fail_counts[name] = count

    lane_rankings = sorted(
        lane_results,
        key=lambda x: (lane_fail_counts.get(x["lane"], 99), 0 if x.get("passed") else 1),
    )

    # What would need to be true
    what_would_need = []
    if claims.sonic_boom_absent and physics.get("mach_est", 0) > 1.0:
        what_would_need.append("allow_sonic_boom_or_declare_shock_mitigation_with_alternate_signatures")
    if claims.exhaust_absent:
        what_would_need.append("non_thrust_based_mechanism")
    if claims.thermal_signature_low and physics.get("required_power_W", 0) > 1e6:
        what_would_need.append("heat_dump_explanation_with_destination")
    if claims.contrail_absent and physics.get("air_heating_W", 0) > 1e6:
        what_would_need.append("allow_contrail_or_reduce_heating")
    if behavior.transmedium and physics.get("water_drag_W", 0) > 1e6:
        what_would_need.append("coupling_reduction_declared")

    # Minimal violation finder + solver
    minimal = find_minimal_violations(behavior, claims, mass_geo)

    # Artifact polish: dominant gate, by category, assumption deltas
    dom = _dominant_failed_gate(failed_gates)
    by_cat = failed_gates_by_category(failed_gates)
    assumption_deltas = _derive_assumption_deltas(
        failed_gates, physics, claims, behavior, minimal
    )

    # Verdict (honest ladder: distinguish gate failures vs lane-model limits)
    any_passed = any(lr.get("passed") for lr in lane_results)
    speculative_passed = any(
        lr.get("passed") and lr.get("lane") in ("metric_bubble", "reactionless_placeholder")
        for lr in lane_results
    )
    if len(failed_gates) > 0:
        verdict: VerdictType = "physically_implausible_under_known_physics"
    elif speculative_passed:
        verdict = "requires_speculative_physics"
    elif any_passed and len(failed_gates) == 0:
        verdict = "consistent_with_model_under_assumptions"
    else:
        # n_failed_gates == 0 but no lane passes: lane models are stricter than gates
        verdict = "requires_speculative_physics"

    # Sensor artifact notes: radar dropouts, glare, range error can mimic effects
    sensor_artifact_notes = []
    if claims.radar_track_intermittent:
        sensor_artifact_notes.append({
            "observable": "radar_track_intermittent",
            "could_be_sensor_artifact": True,
            "note": "Radar dropouts can mimic stealth; hardware/ propagation effects possible",
        })
    if claims.visual_cloaking_reported:
        sensor_artifact_notes.append({
            "observable": "visual_cloaking_reported",
            "could_be_sensor_artifact": True,
            "note": "Glare, range error, or atmospheric effects can mimic cloaking",
        })

    return {
        "verdict": verdict,
        "failed_gates": failed_gates,
        "dominant_failed_gate": dom,
        "failed_gates_by_category": by_cat,
        "assumption_deltas_to_pass": assumption_deltas,
        "minimal_violation_finder": minimal,
        "sensor_artifact_notes": sensor_artifact_notes,
        "lane_rankings": [{"lane": r["lane"], "passed": r.get("passed"), "fail_count": lane_fail_counts.get(r["lane"], 0)} for r in lane_rankings],
        "lane_results": lane_results,
        "gate_results_by_lane": gate_results_by_lane,
        "what_would_need_to_be_true": what_would_need,
        "physics": physics,
        "extended_traits": extended,
    }
