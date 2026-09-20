"""Breakthrough Ladder: increasingly strict UFO-observable tests with scoreboard."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .gate_category_mapping import dominant_failed_gate as _dominant_failed_gate
from .ufo_observable_evaluator import evaluate_ufo_observables
from .ufo_observables import UFOBehaviorSpec, UFOObservableClaims

PolicyPreset = Literal["strict", "normal", "sandbox"]


@dataclass
class BreakthroughStep:
    """Single rung on the breakthrough ladder."""

    name: str
    behavior_spec: UFOBehaviorSpec
    claims: UFOObservableClaims
    policy_name: PolicyPreset
    allow_speculative: bool
    enable_element_x: bool = True
    step_id: int = 0  # 1-based index when in ladder

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "behavior_spec": self.behavior_spec.to_dict(),
            "claims": self.claims.to_dict(),
            "policy_name": self.policy_name,
            "allow_speculative": self.allow_speculative,
            "enable_element_x": self.enable_element_x,
            "step_id": self.step_id,
        }


def _top_failure_reasons(failed_gates: list[dict], n: int = 5) -> list[str]:
    """Top n failure reasons by frequency."""
    reasons = [g.get("reason", "") for g in failed_gates if g.get("reason")]
    if not reasons:
        return []
    counts = Counter(reasons)
    return [r for r, _ in counts.most_common(n)]


def _least_bad_lane(lane_rankings: list[dict]) -> str:
    """Lane with fewest failed gates (first in rankings)."""
    if not lane_rankings:
        return "none"
    return lane_rankings[0].get("lane", "unknown")


def _run_single_step(
    step: BreakthroughStep,
    mass_range_kg: tuple[float, float],
    output_dir: Path,
    run_id: str,
) -> tuple[dict[str, Any], list[dict]]:
    """Run one ladder step and write artifact. Returns (step_report, failed_gates)."""
    result = evaluate_ufo_observables(
        step.behavior_spec,
        step.claims,
        mass_range_kg,
        policy=step.policy_name,
        allow_speculative_override=step.allow_speculative,
        enable_element_x=step.enable_element_x,
    )

    failed = result["failed_gates"]
    dom = _dominant_failed_gate(failed)
    dom_str = dom.get("reason", dom.get("lane", "unknown")) if dom else "none"

    step_report = {
        "step": step.step_id,
        "name": step.name,
        "verdict": result["verdict"],
        "n_failed_gates": len(failed),
        "dominant_failed_gate": dom_str,
        "top_failure_reasons": _top_failure_reasons(failed, 5),
        "least_bad_lane": _least_bad_lane(result.get("lane_rankings", [])),
        "notes": "",
    }

    # Write per-step artifact
    steps_dir = output_dir / "breakthrough_steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    step_path = steps_dir / f"{step.step_id:02d}_{step.name}.json"
    artifact = {
        **step_report,
        "step_spec": step.to_dict(),
        "full_result": {
            "verdict": result["verdict"],
            "n_failed_gates": len(failed),
            "failed_gates": failed,
            "lane_rankings": result.get("lane_rankings", []),
            "what_would_need_to_be_true": result.get("what_would_need_to_be_true", []),
            "lane_results": result.get("lane_results", []),
        },
    }
    step_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=True), encoding="utf-8")

    return step_report, failed


def run_breakthrough_ladder(
    steps: list[BreakthroughStep],
    mass_range_kg: tuple[float, float],
    output_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    """Execute ladder steps in order; write artifacts and return scoreboard."""
    step_reports: list[dict[str, Any]] = []
    first_failure_step = 0
    deepest_without_spec = 0
    deepest_not_physically_implausible = 0
    first_step_high_severity_gates = 0
    all_categories: list[str] = []

    from .gate_category_mapping import categorize_reason

    for i, step in enumerate(steps):
        step.step_id = i + 1
        report, failed = _run_single_step(step, mass_range_kg, output_dir, run_id)
        step_reports.append(report)

        verdict = report["verdict"]
        if verdict != "consistent_with_model_under_assumptions":
            if first_failure_step == 0:
                first_failure_step = step.step_id
        else:
            if not step.allow_speculative:
                deepest_without_spec = step.step_id

        if verdict != "physically_implausible_under_known_physics":
            deepest_not_physically_implausible = step.step_id

        if first_step_high_severity_gates == 0 and any(g.get("severity") == "high" for g in failed):
            first_step_high_severity_gates = step.step_id

        # Collect failure categories for overall (from all failed gates)
        for g in failed:
            all_categories.append(categorize_reason(g.get("reason", "")))

    # Most common failure categories
    cat_counts = Counter(all_categories)
    most_common = [c for c, _ in cat_counts.most_common(5)]

    ladder_report = {
        "run_id": run_id,
        "mass_range": {"min_kg": mass_range_kg[0], "max_kg": mass_range_kg[1]},
        "steps": step_reports,
        "overall": {
            "deepest_step_reached_without_speculation": deepest_without_spec,
            "deepest_step_not_physically_implausible": deepest_not_physically_implausible,
            "first_failure_step": first_failure_step,
            "first_step_high_severity_gates_fire": first_step_high_severity_gates,
            "most_common_failure_categories": most_common,
        },
    }

    summary_path = output_dir / "breakthrough_ladder_summary.json"
    summary_path.write_text(json.dumps(ladder_report, indent=2, ensure_ascii=True), encoding="utf-8")

    return ladder_report


# ---------------------------------------------------------------------------
# Ladder step definitions (TicTac-lite baseline → escalations)
# ---------------------------------------------------------------------------

_DEFAULT_MASS = (100.0, 10000.0)


def _base_behavior(
    max_accel_g: float = 300,
    max_speed_m_s: float = 250,
    hover_duration_s: float = 60,
    transmedium: bool = False,
    water_speed_m_s: float | None = None,
) -> UFOBehaviorSpec:
    return UFOBehaviorSpec(
        max_accel_g=max_accel_g,
        max_speed_m_s=max_speed_m_s,
        turn_radius_m=50.0,
        turn_rate_rad_s=10.0,
        hover_duration_s=hover_duration_s,
        transmedium=transmedium,
        altitude_m=5000.0,
        water_speed_m_s=water_speed_m_s,
    )


def _minimal_claims() -> UFOObservableClaims:
    """Neutral/unknown claims for baseline (no special absences)."""
    return UFOObservableClaims(
        sonic_boom_absent=False,
        exhaust_absent=False,
        thermal_signature_low=False,
        contrail_absent=False,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
        notes="minimal/unknown claims",
    )


def build_ladder_steps(
    include_speculative: bool = False,
    policy_override: PolicyPreset | None = None,
) -> list[BreakthroughStep]:
    """Build ladder steps 1–6 (optionally 7) in order."""
    policy = policy_override or "strict"
    allow_spec = False

    steps: list[BreakthroughStep] = []

    # Step 1: tictac_lite_baseline (300g, extreme)
    steps.append(BreakthroughStep(
        name="tictac_lite_baseline",
        behavior_spec=_base_behavior(300, 250, 60, False),
        claims=_minimal_claims(),
        policy_name=policy,
        allow_speculative=allow_spec,
    ))

    # Step 2: tictac_lite_known_physics_sanity (30g, first breakthrough hunt)
    steps.append(BreakthroughStep(
        name="tictac_lite_known_physics_sanity",
        behavior_spec=_base_behavior(30, 250, 60, False),
        claims=_minimal_claims(),
        policy_name=policy,
        allow_speculative=allow_spec,
    ))

    # Step 3: no_exhaust
    claims_2 = UFOObservableClaims(
        sonic_boom_absent=False,
        exhaust_absent=True,
        thermal_signature_low=False,
        contrail_absent=False,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
        notes="exhaust_absent",
    )
    steps.append(BreakthroughStep(
        name="no_exhaust",
        behavior_spec=_base_behavior(300, 250, 60, False),
        claims=claims_2,
        policy_name=policy,
        allow_speculative=allow_spec,
    ))

    # Step 4: low_thermal
    claims_3 = UFOObservableClaims(
        sonic_boom_absent=False,
        exhaust_absent=True,
        thermal_signature_low=True,
        contrail_absent=False,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
        notes="exhaust_absent + thermal_low",
    )
    steps.append(BreakthroughStep(
        name="low_thermal",
        behavior_spec=_base_behavior(300, 250, 60, False),
        claims=claims_3,
        policy_name=policy,
        allow_speculative=allow_spec,
    ))

    # Step 5: supersonic_no_boom
    claims_4 = UFOObservableClaims(
        sonic_boom_absent=True,
        exhaust_absent=True,
        thermal_signature_low=True,
        contrail_absent=False,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
        notes="supersonic no boom",
    )
    steps.append(BreakthroughStep(
        name="supersonic_no_boom",
        behavior_spec=_base_behavior(300, 1200, 60, False),
        claims=claims_4,
        policy_name=policy,
        allow_speculative=allow_spec,
    ))

    # Step 6: transmedium
    steps.append(BreakthroughStep(
        name="transmedium",
        behavior_spec=_base_behavior(300, 1200, 60, True, 200.0),
        claims=claims_4,
        policy_name=policy,
        allow_speculative=allow_spec,
    ))

    # Step 7: lensing
    claims_6 = UFOObservableClaims(
        sonic_boom_absent=True,
        exhaust_absent=True,
        thermal_signature_low=True,
        contrail_absent=False,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=True,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
        notes="+ lensing",
    )
    steps.append(BreakthroughStep(
        name="lensing",
        behavior_spec=_base_behavior(300, 1200, 60, True, 200.0),
        claims=claims_6,
        policy_name=policy,
        allow_speculative=allow_spec,
    ))

    # Optional Step 8: speculative sandbox
    if include_speculative:
        steps.append(BreakthroughStep(
            name="speculative_sandbox",
            behavior_spec=_base_behavior(300, 1200, 60, True, 200.0),
            claims=claims_6,
            policy_name="sandbox",
            allow_speculative=True,
            enable_element_x=True,
        ))

    for i, s in enumerate(steps):
        s.step_id = i + 1

    return steps
