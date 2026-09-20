"""Constraint gates: no exhaust, no sonic boom, thermal low, transmedium.

Each gate fails if observation conflicts with physics prediction.
"""

from __future__ import annotations

from typing import Any

GateResult = dict[str, Any]


def gate_no_exhaust(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
    lane: str,
) -> GateResult:
    """Fails if thrust model implies exhaust energy above threshold while observation says none."""
    exhaust_absent = spec.get("visible_exhaust_absent", False)
    power_w = dynamics.get("required_power_w", 0.0)
    threshold_w = 1e5  # 100 kW exhaust is visible

    if lane == "conventional_thrust":
        exhaust_power = 0.5 * power_w
        if exhaust_absent and exhaust_power > threshold_w:
            return {
                "passed": False,
                "reason": "conventional_thrust_requires_visible_exhaust",
                "severity": "high",
                "which_observation": "visible_exhaust_absent",
            }
    return {"passed": True, "reason": "ok", "severity": "none", "which_observation": None}


def gate_no_sonic_boom(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
    lane: str,
    *,
    shock_mitigation_declared: bool = False,
) -> GateResult:
    """Fails if speed > Mach 1 at altitude with no boom unless lane provides explicit mitigation."""
    sonic_absent = spec.get("sonic_boom_absent", False)
    sonic = dynamics.get("sonic_boom_expectation", {})
    expect_boom = sonic.get("expect_sonic_boom", False)

    if sonic_absent and expect_boom and not shock_mitigation_declared:
        return {
            "passed": False,
            "reason": "supersonic_without_sonic_boom_requires_mitigation_mechanism",
            "severity": "high",
            "which_observation": "sonic_boom_absent",
        }
    return {"passed": True, "reason": "ok", "severity": "none", "which_observation": None}


def gate_thermal_low(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
) -> GateResult:
    """Fails if required power implies IR brightness far above 'low thermal' claim."""
    thermal_low = spec.get("thermal_signature_low", False)
    power_w = dynamics.get("required_power_w", 0.0)
    threshold_w = 1e7  # 10 MW → definite IR signature

    if thermal_low and power_w > threshold_w:
        return {
            "passed": False,
            "reason": "required_power_exceeds_low_thermal_threshold",
            "severity": "high",
            "which_observation": "thermal_signature_low",
        }
    return {"passed": True, "reason": "ok", "severity": "none", "which_observation": None}


def gate_transmedium(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
    lane: str,
    *,
    coupling_reduction_declared: bool = False,
) -> GateResult:
    """Fails if water drag heating would be catastrophic unless lane explains coupling reduction."""
    transmedium = spec.get("transmedium", False)
    trans = dynamics.get("transmedium_penalty", {})
    catastrophic = trans.get("catastrophic_heating_risk", False)

    if transmedium and catastrophic and lane in ("conventional_thrust", "aerodynamic"):
        if not coupling_reduction_declared:
            return {
                "passed": False,
                "reason": "transmedium_at_high_speed_requires_coupling_reduction",
                "severity": "high",
                "which_observation": "transmedium",
            }
    return {"passed": True, "reason": "ok", "severity": "none", "which_observation": None}


def evaluate_all_gates(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
    lane: str,
    *,
    shock_mitigation_declared: bool = False,
    coupling_reduction_declared: bool = False,
) -> list[GateResult]:
    """Run all gates for a lane."""
    results = [
        gate_no_exhaust(dynamics, spec, lane),
        gate_no_sonic_boom(
            dynamics, spec, lane,
            shock_mitigation_declared=shock_mitigation_declared,
        ),
        gate_thermal_low(dynamics, spec),
        gate_transmedium(
            dynamics, spec, lane,
            coupling_reduction_declared=coupling_reduction_declared,
        ),
    ]
    return results
