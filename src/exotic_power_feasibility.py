"""Conservative feasibility checks for speculative exotic power claims."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

C_LIGHT = 299_792_458.0

ExoticPresetName = Literal["strict", "normal", "sandbox"]

# Priority order for dominant_violation when multiple reasons apply.
_VIOLATION_PRIORITY: tuple[str, ...] = (
    "evidence_gate",
    "neg_energy_budget",
    "total_energy_ceiling",
    "rho_ceiling",
)
_REASON_TO_VIOLATION: dict[str, str] = {
    "exotic_not_demonstrated_as_power_source": "evidence_gate",
    "negative_energy_budget_exceeds_policy_ceiling": "neg_energy_budget",
    "total_energy_exceeds_policy_ceiling": "total_energy_ceiling",
    "energy_density_exceeds_policy_ceiling": "rho_ceiling",
}


@dataclass(frozen=True)
class ExoticPowerPolicy:
    """
    Conservative policy knobs for speculative exotic-source screening.

    These values are CURV policy limits, not claims about fundamental physics.
    """

    allow_speculative: bool = False
    max_rho_j_m3: float = 1.0e18
    max_total_energy_j: float = 1.0e15
    enforce_negative_energy_budget: bool = True
    max_negative_energy_j: float = 0.0


def exotic_policy_from_preset(
    preset: ExoticPresetName,
    *,
    allow_speculative_override: bool | None = None,
) -> ExoticPowerPolicy:
    """
    Build policy from a named preset. Use for comparable, readable runs.

    - strict: "If it smells like magic, it fails." (evidence gate always blocks)
    - normal: Conservative ceilings, allow_speculative from override (default False)
    - sandbox: Permissive for exploration; ceilings set high.
    """
    if preset == "strict":
        return ExoticPowerPolicy(
            allow_speculative=False,
            max_rho_j_m3=1.0e18,
            max_total_energy_j=1.0e15,
            enforce_negative_energy_budget=True,
            max_negative_energy_j=0.0,
        )
    if preset == "normal":
        return ExoticPowerPolicy(
            allow_speculative=bool(allow_speculative_override) if allow_speculative_override is not None else False,
            max_rho_j_m3=1.0e12,
            max_total_energy_j=1.0e12,
            enforce_negative_energy_budget=True,
            max_negative_energy_j=0.0,
        )
    if preset == "sandbox":
        return ExoticPowerPolicy(
            allow_speculative=True,
            max_rho_j_m3=1.0e18,
            max_total_energy_j=1.0e18,
            enforce_negative_energy_budget=True,
            max_negative_energy_j=1.0e18,
        )
    raise ValueError(f"Unknown exotic preset: {preset!r}. Use strict, normal, or sandbox.")


def evaluate_exotic_power_feasibility(
    *,
    required_power_w: float,
    mission_duration_s: float,
    active_volume_m3: float,
    policy: ExoticPowerPolicy | None = None,
    assumed_negative_energy_j: float | None = None,
) -> dict[str, Any]:
    """Evaluate a speculative exotic-source candidate against conservative gates."""
    gate_policy = policy if policy is not None else ExoticPowerPolicy()
    p_w = float(required_power_w)
    t_s = float(mission_duration_s)
    v_m3 = float(active_volume_m3)

    if p_w <= 0.0 or t_s <= 0.0 or v_m3 <= 0.0:
        raise ValueError(f"Invalid inputs: P={p_w}, t={t_s}, V={v_m3}")

    total_energy_j = p_w * t_s
    rho_required_j_m3 = total_energy_j / v_m3
    mass_equiv_kg = total_energy_j / (C_LIGHT**2)

    reasons: list[str] = []
    if not gate_policy.allow_speculative:
        reasons.append("exotic_not_demonstrated_as_power_source")
    if total_energy_j > gate_policy.max_total_energy_j:
        reasons.append("total_energy_exceeds_policy_ceiling")
    if rho_required_j_m3 > gate_policy.max_rho_j_m3:
        reasons.append("energy_density_exceeds_policy_ceiling")

    negative_energy_j: float | None = None
    if assumed_negative_energy_j is not None:
        negative_energy_j = float(assumed_negative_energy_j)
        if gate_policy.enforce_negative_energy_budget:
            if negative_energy_j < 0.0 and abs(negative_energy_j) > gate_policy.max_negative_energy_j:
                reasons.append("negative_energy_budget_exceeds_policy_ceiling")

    violation_set = {_REASON_TO_VIOLATION[r] for r in reasons if r in _REASON_TO_VIOLATION}
    dominant_violation: str = "none"
    for v in _VIOLATION_PRIORITY:
        if v in violation_set:
            dominant_violation = v
            break

    return {
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "dominant_violation": dominant_violation,
        "required_power_w": p_w,
        "mission_duration_s": t_s,
        "active_volume_m3": v_m3,
        "total_energy_j": total_energy_j,
        "rho_required_j_m3": rho_required_j_m3,
        "mass_equiv_kg": mass_equiv_kg,
        "assumed_negative_energy_j": negative_energy_j,
        "policy": {
            "allow_speculative": gate_policy.allow_speculative,
            "max_rho_j_m3": gate_policy.max_rho_j_m3,
            "max_total_energy_j": gate_policy.max_total_energy_j,
            "enforce_negative_energy_budget": gate_policy.enforce_negative_energy_budget,
            "max_negative_energy_j": gate_policy.max_negative_energy_j,
        },
    }
