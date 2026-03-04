from __future__ import annotations

from src.exotic_power_feasibility import (
    ExoticPowerPolicy,
    evaluate_exotic_power_feasibility,
    exotic_policy_from_preset,
)


def test_exotic_fails_by_default_due_to_evidence_gate() -> None:
    out = evaluate_exotic_power_feasibility(
        required_power_w=1.0e6,
        mission_duration_s=3600.0,
        active_volume_m3=4188.79,
    )
    assert out["passed"] is False
    assert "exotic_not_demonstrated_as_power_source" in out["reasons"]


def test_exotic_can_pass_only_if_speculative_allowed_and_within_ceiling() -> None:
    policy = ExoticPowerPolicy(
        allow_speculative=True,
        max_total_energy_j=1.0e12,
        max_rho_j_m3=1.0e12,
        enforce_negative_energy_budget=True,
        max_negative_energy_j=0.0,
    )
    out = evaluate_exotic_power_feasibility(
        required_power_w=1.0e4,
        mission_duration_s=1.0e2,
        active_volume_m3=1.0e6,
        policy=policy,
    )
    assert out["passed"] is True
    assert out["reasons"] == []
    assert out["dominant_violation"] == "none"


def test_exotic_returns_dominant_violation_when_failing() -> None:
    out = evaluate_exotic_power_feasibility(
        required_power_w=1.0e6,
        mission_duration_s=3600.0,
        active_volume_m3=1.0,
    )
    assert out["passed"] is False
    assert out["dominant_violation"] == "evidence_gate"


def test_exotic_preset_strict_always_blocks() -> None:
    policy = exotic_policy_from_preset("strict")
    assert policy.allow_speculative is False
    out = evaluate_exotic_power_feasibility(
        required_power_w=1.0,
        mission_duration_s=1.0,
        active_volume_m3=1.0e6,
        policy=policy,
    )
    assert out["passed"] is False
    assert out["dominant_violation"] == "evidence_gate"


def test_exotic_preset_sandbox_allows_within_ceilings() -> None:
    policy = exotic_policy_from_preset("sandbox")
    assert policy.allow_speculative is True
    out = evaluate_exotic_power_feasibility(
        required_power_w=1.0e4,
        mission_duration_s=1.0e2,
        active_volume_m3=1.0e6,
        policy=policy,
    )
    assert out["passed"] is True
    assert out["dominant_violation"] == "none"


def test_exotic_preset_normal_uses_override_for_allow_speculative() -> None:
    policy_off = exotic_policy_from_preset("normal", allow_speculative_override=False)
    policy_on = exotic_policy_from_preset("normal", allow_speculative_override=True)
    assert policy_off.allow_speculative is False
    assert policy_on.allow_speculative is True
