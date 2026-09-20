"""Integrate curvature, energy, signal, and artifact modules.

Answers: "Could a spacetime bubble exist under these assumptions?"

Pipeline:
1. Compute curvature from radius
2. Compute energy requirements
3. Run exotic feasibility tripwire (curvature_cost + exotic_power)
4. Predict instrument signal
5. Evaluate artifact risks

Output: structured report with verdict.
NEVER claims discovery. Verdict is either:
  - consistent_with_model
  - physically_implausible_under_known_physics
"""

from __future__ import annotations

from typing import Any, Literal

from .curvature_cost import curvature_cost_sanity
from .curvature_energy_requirements import curvature_energy_report
from .exotic_power_feasibility import (
    ExoticPowerPolicy,
    evaluate_exotic_power_feasibility,
)
from .experimental_artifact_rejection import evaluate_artifact_risks
from .spacetime_signal_predictor import (
    InstrumentType,
    predict_signal_for_instrument,
)

VerdictType = Literal["consistent_with_model", "physically_implausible_under_known_physics"]


def analyze_bubble_feasibility(
    *,
    bubble_radius_m: float,
    active_volume_m3: float | None = None,
    required_power_w: float,
    duration_s: float,
    instrument_type: InstrumentType = "interferometer",
    arm_length_m: float = 1.0,
    allow_speculative: bool = False,
    policy: ExoticPowerPolicy | None = None,
) -> dict[str, Any]:
    """Full feasibility analysis for a hypothetical spacetime bubble.

    Parameters
    ----------
    bubble_radius_m : float
        Radius of curvature region (m).
    active_volume_m3 : float | None
        Active volume. If None, uses spherical V = (4/3)πR³.
    required_power_w : float
        Required power (W).
    duration_s : float
        Duration (s).
    instrument_type : str
        One of interferometer, atomic_clock, beam_deflection, gravimeter.
    arm_length_m : float
        Characteristic arm/baseline length (m).
    allow_speculative : bool
        Whether to allow exotic power (default False).
    policy : ExoticPowerPolicy | None
        Override exotic power policy.

    Returns
    -------
    dict with bubble_feasible, dominant_failure_reason, predicted_signal,
    required_energy, artifact_risk, verdict
    """
    R = float(bubble_radius_m)
    P = float(required_power_w)
    T = float(duration_s)
    if R <= 0.0 or P <= 0.0 or T <= 0.0:
        raise ValueError("bubble_radius_m, required_power_w, duration_s must be positive")

    # 1. Curvature and energy requirements
    energy_report = curvature_energy_report(
        radius_m=R,
        volume_m3=float(active_volume_m3) if active_volume_m3 is not None else None,
    )
    K = energy_report["curvature_m2_inv"]
    rho = energy_report["energy_density_j_m3"]
    E_total = energy_report["total_energy_j"]
    V = energy_report["volume_m3"]

    # 2. Exotic power feasibility (tripwire)
    gate_policy = policy if policy is not None else ExoticPowerPolicy(allow_speculative=allow_speculative)
    total_energy_from_power = P * T
    exotic_eval = evaluate_exotic_power_feasibility(
        required_power_w=P,
        mission_duration_s=T,
        active_volume_m3=V,
        policy=gate_policy,
    )

    # 3. Curvature cost sanity (energy density / mass equivalent ceilings)
    curv_sanity = curvature_cost_sanity(R, geometry="sphere")
    curv_gate_pass = bool(curv_sanity["curv_gate_pass"])

    # 4. Signal prediction
    signal_pred = predict_signal_for_instrument(
        curvature_m2_inv=K,
        instrument=instrument_type,
        arm_length_m=arm_length_m,
        baseline_m=arm_length_m,
    )

    # 5. Artifact risks
    artifact_risk = evaluate_artifact_risks(
        power_w=P,
        duration_s=T,
        volume_m3=V,
        baseline_m=arm_length_m,
        instrument_type=instrument_type,
        sensitivity_class="interferometer" if instrument_type == "interferometer" else "standard",
    )

    # 6. Verdict logic (fail-closed)
    failure_reasons: list[str] = []
    if not exotic_eval["passed"]:
        failure_reasons.append(f"exotic_power_tripwire:{exotic_eval['dominant_violation']}")
    if not curv_gate_pass:
        failure_reasons.extend(curv_sanity["sanity_fail_reasons"])
    if total_energy_from_power > 0 and E_total > total_energy_from_power * 1e6:
        # Power budget grossly insufficient for curvature requirement
        failure_reasons.append("power_budget_insufficient_for_curvature")
    if artifact_risk["overall_artifact_risk"] == "high":
        failure_reasons.append("artifact_risk_high")

    bubble_feasible = len(failure_reasons) == 0
    dominant_failure_reason = failure_reasons[0] if failure_reasons else "none"

    if bubble_feasible:
        verdict: VerdictType = "consistent_with_model"
    else:
        verdict = "physically_implausible_under_known_physics"

    return {
        "bubble_feasible": bubble_feasible,
        "dominant_failure_reason": dominant_failure_reason,
        "failure_reasons": failure_reasons,
        "verdict": verdict,
        "predicted_signal": signal_pred,
        "required_energy": {
            "curvature_m2_inv": K,
            "energy_density_j_m3": rho,
            "total_energy_j": E_total,
            "mass_equivalent_kg": energy_report["mass_equivalent_kg"],
        },
        "curvature_cost_sanity": {
            "curv_gate_pass": curv_gate_pass,
            "sanity_fail_reasons": curv_sanity["sanity_fail_reasons"],
            "m_equiv_kg": curv_sanity["m_equiv_kg"],
        },
        "exotic_power_eval": exotic_eval,
        "artifact_risk": artifact_risk,
        "bubble_parameters": {
            "bubble_radius_m": R,
            "active_volume_m3": V,
            "required_power_w": P,
            "duration_s": T,
        },
    }
