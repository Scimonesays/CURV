"""Missing-signature gates: generate crisp negatives.

If physics predicts a signature but claim says absent → FAIL.
Mitigation must produce alternate signatures; if those also absent → FAIL harder.
"""

from __future__ import annotations

from typing import Any

from .ufo_observables import UFOObservableClaims


def gate_sonic_boom_consistency(
    physics: dict[str, Any],
    claims: UFOObservableClaims,
    lane: dict[str, Any],
) -> dict[str, Any]:
    """If mach > 1 and sonic_boom_absent: FAIL unless lane declares shock mitigation.
    If mitigation declared, require alternate signatures (plasma/EM/heat). If those absent → FAIL harder."""
    mach = physics.get("mach_est", 0.0)
    boom_absent = claims.sonic_boom_absent

    if mach <= 1.0:
        return {"passed": True, "reason": "subsonic", "severity": "none", "conflicts_with": None}

    if not boom_absent:
        return {"passed": True, "reason": "boom_not_claimed_absent", "severity": "none", "conflicts_with": None}

    mitigation = lane.get("shock_mitigation_declared", False)
    pred = lane.get("predicted_signatures", {})
    plasma = pred.get("plasma_likelihood", "low")
    em = pred.get("em_activity_proxy", 0)
    ir = pred.get("ir_brightness_proxy", 0)

    if not mitigation:
        return {
            "passed": False,
            "reason": "supersonic_no_boom_requires_shock_mitigation",
            "severity": "high",
            "conflicts_with": "sonic_boom_absent",
        }

    # Mitigation declared: must predict alternate signatures
    if plasma == "low" and em == 0 and ir == 0:
        return {
            "passed": False,
            "reason": "mitigation_requires_alternate_signatures_none_predicted",
            "severity": "high",
            "conflicts_with": "sonic_boom_absent",
        }

    # If claims say thermal/plasma absent but we predict them, conflict
    if claims.thermal_signature_low and ir > 1e6:
        return {
            "passed": False,
            "reason": "mitigation_predicts_heat_but_thermal_low_claimed",
            "severity": "high",
            "conflicts_with": "thermal_signature_low",
        }

    return {"passed": True, "reason": "mitigation_with_alternate_signatures", "severity": "none", "conflicts_with": None}


def gate_thermal_consistency(
    physics: dict[str, Any],
    claims: UFOObservableClaims,
    lane: dict[str, Any],
) -> dict[str, Any]:
    """If power/heating implies large IR and thermal_signature_low → FAIL unless mechanism explains heat dump."""
    power_W = physics.get("required_power_W", 0.0)
    air_W = physics.get("air_heating_W", 0.0)
    thermal_low = claims.thermal_signature_low

    if not thermal_low:
        return {"passed": True, "reason": "thermal_not_claimed_low", "severity": "none", "conflicts_with": None}

    total_heat = power_W + air_W
    if total_heat < 1e6:
        return {"passed": True, "reason": "low_power_ok", "severity": "none", "conflicts_with": None}

    heat_dump = lane.get("heat_dump_explained", False)
    if not heat_dump:
        return {
            "passed": False,
            "reason": "high_power_implies_ir_thermal_low_conflict",
            "severity": "high",
            "conflicts_with": "thermal_signature_low",
        }

    energy_destination = lane.get("energy_destination_predicted", "")
    if not energy_destination:
        return {
            "passed": False,
            "reason": "heat_dump_requires_predicted_destination",
            "severity": "med",
            "conflicts_with": "thermal_signature_low",
        }

    return {"passed": True, "reason": "heat_dump_explained", "severity": "none", "conflicts_with": None}


def gate_exhaust_consistency(
    claims: UFOObservableClaims,
    lane: dict[str, Any],
) -> dict[str, Any]:
    """If mechanism is thrust-based and exhaust_absent → FAIL."""
    if not claims.exhaust_absent:
        return {"passed": True, "reason": "exhaust_not_claimed_absent", "severity": "none", "conflicts_with": None}

    thrust_based = lane.get("thrust_based", True)
    if not thrust_based:
        return {"passed": True, "reason": "not_thrust_based", "severity": "none", "conflicts_with": None}

    return {
        "passed": False,
        "reason": "thrust_requires_exhaust",
        "severity": "high",
        "conflicts_with": "exhaust_absent",
    }


def gate_contrail_consistency(
    physics: dict[str, Any],
    claims: UFOObservableClaims,
) -> dict[str, Any]:
    """If air heating/humidity implies contrails but contrail_absent → conflict (lower severity)."""
    if not claims.contrail_absent:
        return {"passed": True, "reason": "contrail_not_claimed_absent", "severity": "none", "conflicts_with": None}

    air_W = physics.get("air_heating_W", 0.0)
    if air_W < 1e6:
        return {"passed": True, "reason": "low_heating_ok", "severity": "none", "conflicts_with": None}

    return {
        "passed": False,
        "reason": "high_heating_implies_contrail",
        "severity": "low",
        "conflicts_with": "contrail_absent",
    }


def gate_momentum_conservation(
    physics: dict[str, Any],
    claims: UFOObservableClaims,
    lane: dict[str, Any],
) -> dict[str, Any]:
    """No exhaust → must declare momentum exchange mode. Each mode predicts signatures.

    Modes: environment_interaction | external_beam_field | inertial_mass_modification | spacetime_metric
    """
    if not claims.exhaust_absent:
        return {"passed": True, "reason": "exhaust_not_claimed_absent", "severity": "none", "conflicts_with": None}

    force_N = physics.get("required_force_N", 0.0)
    if force_N < 1.0:
        return {"passed": True, "reason": "negligible_force", "severity": "none", "conflicts_with": None}

    mode = lane.get("momentum_exchange_mode", None)
    pred = lane.get("predicted_signatures", {})

    if mode is None or mode == "":
        return {
            "passed": False,
            "reason": "no_exhaust_requires_momentum_exchange_declaration",
            "severity": "high",
            "conflicts_with": "exhaust_absent",
        }

    valid_modes = (
        "environment_interaction",
        "external_beam_field",
        "inertial_mass_modification",
        "spacetime_metric",
        "photon_pressure",
    )
    if mode not in valid_modes:
        return {
            "passed": False,
            "reason": "momentum_mode_unknown",
            "severity": "high",
            "conflicts_with": "exhaust_absent",
        }

    # photon_pressure: must predict beam power (lane provides it)
    if mode == "photon_pressure":
        if pred.get("beam_power_W") is None and pred.get("required_generated_power_W") is None:
            return {
                "passed": False,
                "reason": "photon_pressure_requires_beam_power_prediction",
                "severity": "med",
                "conflicts_with": "exhaust_absent",
            }
        return {"passed": True, "reason": "momentum_exchange_declared", "severity": "none", "conflicts_with": None}

    # Each mode must predict measurable signatures
    if mode == "environment_interaction":
        if pred.get("air_water_wake_predicted") is None and pred.get("em_activity_proxy", 0) == 0:
            return {
                "passed": False,
                "reason": "environment_interaction_requires_wake_or_em_prediction",
                "severity": "med",
                "conflicts_with": "exhaust_absent",
            }
    elif mode == "external_beam_field":
        if pred.get("beam_field_signature_predicted") is None and pred.get("em_activity_proxy", 0) == 0:
            return {
                "passed": False,
                "reason": "external_beam_requires_field_signature_prediction",
                "severity": "med",
                "conflicts_with": "exhaust_absent",
            }
    elif mode in ("inertial_mass_modification", "spacetime_metric"):
        if not lane.get("speculative_allowed", False):
            return {
                "passed": False,
                "reason": "inertial_or_metric_requires_speculative_policy",
                "severity": "high",
                "conflicts_with": "exhaust_absent",
            }
        if not pred.get("curvature_or_inertial_signature_predicted", False):
            return {
                "passed": False,
                "reason": "speculative_mode_requires_testable_signature",
                "severity": "med",
                "conflicts_with": "exhaust_absent",
            }

    return {"passed": True, "reason": "momentum_exchange_declared", "severity": "none", "conflicts_with": None}


def gate_power_density(
    physics: dict[str, Any],
    lane: dict[str, Any],
    rho_ceiling_j_m3: float = 1.0e25,
) -> dict[str, Any]:
    """Energy density gate: distinguish new battery chemistry from rewrite physics."""
    rho = physics.get("rho_E_j_m3", 0.0)
    if rho <= 0:
        return {"passed": True, "reason": "no_rho", "severity": "none", "conflicts_with": None}
    if rho > rho_ceiling_j_m3:
        return {
            "passed": False,
            "reason": "energy_density_exceeds_ceiling_rewrite_physics",
            "severity": "high",
            "conflicts_with": "power_density",
        }
    return {"passed": True, "reason": "within_ceiling", "severity": "none", "conflicts_with": None}


def gate_transmedium_consistency(
    physics: dict[str, Any],
    claims: UFOObservableClaims,
    lane: dict[str, Any],
) -> dict[str, Any]:
    """If transmedium and water_speed large: FAIL conventional unless coupling reduction declared."""
    from .ufo_observables import UFOBehaviorSpec  # behavior.transmedium

    transmedium = physics.get("transmedium", False)
    water_drag = physics.get("water_drag_W", 0.0)
    cavitation = physics.get("cavitation_risk", "low")

    if not transmedium or water_drag < 1e6:
        return {"passed": True, "reason": "not_transmedium_or_low_drag", "severity": "none", "conflicts_with": None}

    coupling_reduction = lane.get("coupling_reduction_declared", False)
    if not coupling_reduction and lane.get("thrust_based", True):
        return {
            "passed": False,
            "reason": "transmedium_drag_requires_coupling_reduction",
            "severity": "high",
            "conflicts_with": "transmedium",
        }

    if cavitation == "high" and not lane.get("cavitation_mitigation_declared", False):
        return {
            "passed": False,
            "reason": "high_cavitation_risk_unmitigated",
            "severity": "med",
            "conflicts_with": "transmedium",
        }

    return {"passed": True, "reason": "ok", "severity": "none", "conflicts_with": None}


def gate_non_exhaust_lane_consistency(
    lane: dict[str, Any],
) -> dict[str, Any]:
    """For non_exhaust_propulsion lane: if lane failed internally, emit gate failure."""
    if lane.get("lane") != "non_exhaust_propulsion":
        return {"passed": True, "reason": "not_non_exhaust", "severity": "none", "conflicts_with": None}
    if lane.get("passed", True):
        return {"passed": True, "reason": "non_exhaust_passed", "severity": "none", "conflicts_with": None}
    reason = lane.get("dominant_failure_reason", "photon_pressure_power_exceeds_ceiling")
    return {
        "passed": False,
        "reason": reason,
        "severity": "high",
        "conflicts_with": "exhaust_absent",
    }


def evaluate_all_signature_gates(
    physics: dict[str, Any],
    claims: UFOObservableClaims,
    lane: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run all gates. Returns list of gate results (many may fail)."""
    gates = [
        gate_sonic_boom_consistency(physics, claims, lane),
        gate_thermal_consistency(physics, claims, lane),
        gate_exhaust_consistency(claims, lane),
        gate_momentum_conservation(physics, claims, lane),
        gate_power_density(physics, lane),
        gate_contrail_consistency(physics, claims),
        gate_transmedium_consistency(physics, claims, lane),
    ]
    gates.append(gate_non_exhaust_lane_consistency(lane))
    return gates
