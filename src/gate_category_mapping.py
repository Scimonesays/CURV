"""Map failed gate reasons to categories for registry mining."""

from __future__ import annotations

CATEGORIES = (
    "kinematics",
    "power",
    "thermal",
    "shock",
    "momentum",
    "medium",
    "lensing",
    "observability",
)

_REASON_TO_CATEGORY: dict[str, str] = {
    # shock
    "supersonic_no_boom_requires_shock_mitigation": "shock",
    "mitigation_requires_alternate_signatures_none_predicted": "shock",
    "mitigation_predicts_heat_but_thermal_low_claimed": "shock",
    "shockwave_consistency": "shock",
    # thermal
    "high_power_implies_ir_thermal_low_conflict": "thermal",
    "heat_dump_requires_predicted_destination": "thermal",
    "thermal_signature_conflict": "thermal",
    # power
    "energy_density_exceeds_ceiling_rewrite_physics": "power",
    "photon_pressure_power_exceeds_ceiling": "power",
    "photon_pressure_energy_exceeds_ceiling": "power",
    "photon_pressure_energy_density_exceeds_ceiling": "power",
    # momentum
    "thrust_requires_exhaust": "momentum",
    "no_exhaust_requires_momentum_exchange_declaration": "momentum",
    "momentum_exchange_unaccounted": "momentum",
    "momentum_mode_unknown": "momentum",
    "environment_interaction_requires_wake_or_em_prediction": "momentum",
    "external_beam_requires_field_signature_prediction": "momentum",
    "inertial_or_metric_requires_speculative_policy": "momentum",
    "speculative_mode_requires_testable_signature": "momentum",
    "photon_pressure_requires_beam_power_prediction": "momentum",
    # medium / transmedium
    "transmedium_drag_requires_coupling_reduction": "medium",
    "high_cavitation_risk_unmitigated": "medium",
    "transmedium_drag_cavitation": "medium",
    # lensing
    "lensing_implies_mass_curvature_budget_mismatch": "lensing",
    "lensing_claim_requires_nonzero_deflection": "lensing",
    "lensing_requires_paid_curvature": "lensing",
    "lensing_budget_consistent": "lensing",
    # contrail / observability
    "high_heating_implies_contrail": "observability",
    # speculative
    "speculative_element_x_not_enabled": "observability",
    "novel_power_source_never_passes_alone_must_also_satisfy_signature_gates": "power",
}


def categorize_reason(reason: str) -> str:
    """Map gate reason to category. Returns 'observability' for unknown."""
    r = (reason or "").strip()
    if not r:
        return "observability"
    # Partial match for long reason strings
    for k, cat in _REASON_TO_CATEGORY.items():
        if k in r or r in k:
            return cat
    if "sonic" in r.lower() or "boom" in r.lower() or "shock" in r.lower():
        return "shock"
    if "thermal" in r.lower() or "heat" in r.lower() or "ir_" in r.lower():
        return "thermal"
    if "power" in r.lower() or "energy" in r.lower() or "density" in r.lower():
        return "power"
    if "momentum" in r.lower() or "exhaust" in r.lower():
        return "momentum"
    if "transmedium" in r.lower() or "cavitation" in r.lower() or "drag" in r.lower() or "coupling" in r.lower():
        return "medium"
    if "lensing" in r.lower() or "curvature" in r.lower():
        return "lensing"
    if "contrail" in r.lower():
        return "observability"
    return "observability"


def failed_gates_by_category(failed_gates: list[dict]) -> dict[str, list[dict]]:
    """Group failed gates by category."""
    by_cat: dict[str, list[dict]] = {}
    for g in failed_gates:
        cat = categorize_reason(g.get("reason", ""))
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(g)
    return by_cat


_SEVERITY_ORDER = {"high": 3, "med": 2, "medium": 2, "low": 1, "none": 0}


def dominant_failed_gate(failed_gates: list[dict]) -> dict | None:
    """Return single worst conflict: highest severity, then first of ties."""
    if not failed_gates:
        return None
    best = failed_gates[0]
    best_sev = _SEVERITY_ORDER.get(best.get("severity", "med"), 2)
    for g in failed_gates[1:]:
        s = _SEVERITY_ORDER.get(g.get("severity", "med"), 2)
        if s > best_sev:
            best = g
            best_sev = s
    return best
