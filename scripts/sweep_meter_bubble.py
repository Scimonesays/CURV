"""Sweep meter-scale bubble: alpha × leakage, energy envelope.

Primary lever: substrate coupling α (rho_required = α·rho_EFE).
Secondary: leakage factor (P_maint = leakage × E_create).

Ranks configs by: feasible first, then smallest α that avoids implausible.
Outputs: breakthrough requirement (α ≤ X, leakage ≤ Y), gate counts, instrument signals.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bubble_envelope_and_stability import (
    BubbleSpec,
    ControlSpec,
    DetectabilitySpec,
    EnergySourceEnvelope,
    EnvironmentSpec,
    LEAKAGE_FACTOR_STRICT_1_S,
    analyze_bubble_envelope,
)

# Default alpha × leakage sweep (breakthrough hunt)
DEFAULT_ALPHAS = "1,1e-3,1e-6,1e-9,1e-12,1e-15,1e-18,1e-21,1e-24"
DEFAULT_LEAKAGES = "1e-3,1e-6,1e-9"


@dataclass
class SweepConfig:
    """Single sweep point."""

    radius_m: float
    alpha: float
    leakage_1_s: float
    medium_coupling: float
    max_continuous_w: float
    max_burst_w: float
    energy_capacity_j: float
    response_time_s: float


@dataclass
class SweepResult:
    """Result for one config across phases."""

    config: SweepConfig
    air: dict
    transition: dict
    water: dict
    worst_failure: str
    bubble_feasible: bool
    dominant_failure: str
    P_control_peak_w: float
    P_maint_w: float
    required_bandwidth_hz: float
    E_create_j: float
    rho_required_j_m3: float
    detectable: bool
    detectability_failure_reason: str
    passed_signals: list[str]


def _feasibility_score(result: SweepResult) -> tuple[bool, float, float]:
    """Sort key: feasible first, then smallest alpha, then smallest leakage.
    Breakthrough requirement = smallest α that avoids implausible.
    """
    feasible = result.bubble_feasible
    alpha = result.config.alpha
    leakage = result.config.leakage_1_s
    # Feasible first (False < True for "not implausible")
    # Among implausible: smaller alpha first, then smaller leakage
    return (not feasible, alpha, leakage)


def run_sweep(
    radii: list[float],
    alphas: list[float],
    leakages: list[float],
    medium_coupling: float,
    max_continuous_w: float,
    max_burst_w: float,
    energy_capacity_j: float,
    response_time_s: float,
    detectability_spec: DetectabilitySpec | None = None,
) -> list[SweepResult]:
    """Run full sweep over alpha × leakage, return sorted by breakthrough requirement."""
    results: list[SweepResult] = []
    for R in radii:
        for alpha in alphas:
            for leakage_1_s in leakages:
                cfg = SweepConfig(
                    radius_m=R,
                    alpha=alpha,
                    leakage_1_s=leakage_1_s,
                    medium_coupling=medium_coupling,
                    max_continuous_w=max_continuous_w,
                    max_burst_w=max_burst_w,
                    energy_capacity_j=energy_capacity_j,
                    response_time_s=response_time_s,
                )
                bubble = BubbleSpec(
                    radius_m=R,
                    wall_thickness_m=0.1,
                    active_volume_m3=None,
                    curvature_target_m2_inv=None,
                    medium_coupling_factor=medium_coupling,
                    shock_suppression=True,
                    substrate_coupling_factor=alpha,
                )
                energy = EnergySourceEnvelope(
                    max_continuous_power_w=max_continuous_w,
                    max_burst_power_w=max_burst_w,
                    burst_duration_s=1.0,
                    total_energy_capacity_j=energy_capacity_j,
                    response_time_s=response_time_s,
                    waste_heat_fraction=0.1,
                    notes="",
                )
                ctrl = ControlSpec()

                air = analyze_bubble_envelope(
                    bubble_spec=bubble,
                    environment=EnvironmentSpec(mode="air"),
                    energy_source=energy,
                    control_spec=ctrl,
                    leakage_factor_1_s=leakage_1_s,
                    detectability_spec=detectability_spec,
                )
                trans = analyze_bubble_envelope(
                    bubble_spec=bubble,
                    environment=EnvironmentSpec(mode="boundary_transition"),
                    energy_source=energy,
                    control_spec=ctrl,
                    leakage_factor_1_s=leakage_1_s,
                    detectability_spec=detectability_spec,
                )
                water = analyze_bubble_envelope(
                    bubble_spec=bubble,
                    environment=EnvironmentSpec(mode="water"),
                    energy_source=energy,
                    control_spec=ctrl,
                    leakage_factor_1_s=leakage_1_s,
                    detectability_spec=detectability_spec,
                )

                worst_fail = "none"
                feasible = True
                for phase_name, phase_out in [("air", air), ("transition", trans), ("water", water)]:
                    if not phase_out["bubble_feasible"]:
                        feasible = False
                        if phase_out["dominant_failure_reason"] != "none":
                            worst_fail = f"{phase_name}:{phase_out['dominant_failure_reason']}"

                d = trans["derived"]
                P_peak = max(
                    air["derived"]["P_control_peak_w"],
                    trans["derived"]["P_control_peak_w"],
                    water["derived"]["P_control_peak_w"],
                )
                P_maint = d["P_maint_w"]
                bw = max(
                    air["derived"]["required_bandwidth_hz"],
                    trans["derived"]["required_bandwidth_hz"],
                    water["derived"]["required_bandwidth_hz"],
                )

                # Detectability from any phase (signals are K/geometry-dependent, same for all)
                trans_det = trans.get("detectable", True)
                trans_det_reason = trans.get("detectability_failure_reason", "none")
                trans_passed = trans.get("passed_signals", [])

                results.append(
                    SweepResult(
                        config=cfg,
                        air=air,
                        transition=trans,
                        water=water,
                        worst_failure=worst_fail,
                        bubble_feasible=feasible,
                        dominant_failure=worst_fail,
                        P_control_peak_w=P_peak,
                        P_maint_w=P_maint,
                        required_bandwidth_hz=bw,
                        E_create_j=d["E_create_j"],
                        rho_required_j_m3=d["rho_required_j_m3"],
                        detectable=trans_det,
                        detectability_failure_reason=trans_det_reason,
                        passed_signals=trans_passed,
                    )
                )

    results.sort(key=_feasibility_score)
    return results


def _serialize_result(r: SweepResult) -> dict:
    """JSON-serializable result summary."""
    return {
        "radius_m": r.config.radius_m,
        "substrate_coupling_alpha": r.config.alpha,
        "leakage_1_s": r.config.leakage_1_s,
        "medium_coupling_factor": r.config.medium_coupling,
        "bubble_feasible": r.bubble_feasible,
        "dominant_failure": r.dominant_failure,
        "rho_required_j_m3": r.rho_required_j_m3,
        "E_create_j": r.E_create_j,
        "P_maint_w": r.P_maint_w,
        "P_control_peak_w": r.P_control_peak_w,
        "required_bandwidth_hz": r.required_bandwidth_hz,
        "detectable": r.detectable,
        "detectability_failure_reason": r.detectability_failure_reason,
        "passed_signals": r.passed_signals,
        "instrument_predictions": r.transition["instrument_predictions"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sweep meter-scale bubble: alpha × leakage, rank by smallest α that avoids implausible."
    )
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path.",
    )
    parser.add_argument(
        "--radii",
        type=str,
        default="0.5",
        help="Comma-separated radii (m). Default 0.5 (best case).",
    )
    parser.add_argument(
        "--alphas",
        type=str,
        default=DEFAULT_ALPHAS,
        help="Comma-separated substrate coupling alpha. rho = alpha * rho_EFE.",
    )
    parser.add_argument(
        "--leakages",
        type=str,
        default=DEFAULT_LEAKAGES,
        help="Comma-separated leakage factors (1/s). P_maint = leakage × E_create.",
    )
    parser.add_argument(
        "--medium-coupling",
        type=float,
        default=0.01,
        help="Medium coupling for transmedium (0-1).",
    )
    parser.add_argument(
        "--max-continuous-power-w",
        type=float,
        default=1e12,
        help="Max continuous power (W).",
    )
    parser.add_argument(
        "--max-burst-power-w",
        type=float,
        default=1e15,
        help="Max burst power (W).",
    )
    parser.add_argument(
        "--energy-capacity-j",
        type=float,
        default=1e20,
        help="Total energy capacity (J).",
    )
    parser.add_argument(
        "--response-time-s",
        type=float,
        default=1e-6,
        help="Control response time (s).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top configs to print.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write full sweep JSON here.",
    )
    parser.add_argument(
        "--detectability",
        action="store_true",
        help="Enable detectability gate: bubble must exceed instrument thresholds (any_of).",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run both passes (feasible-only and feasible+detectable), output both breakthrough requirements.",
    )
    args = parser.parse_args()

    radii = [float(x.strip()) for x in args.radii.split(",")]
    alphas = [float(x.strip()) for x in args.alphas.split(",")]
    leakages = [float(x.strip()) for x in args.leakages.split(",")]

    detectability_spec = (
        DetectabilitySpec(require_detectable=True, mode="any_of")
        if args.detectability or args.compare
        else None
    )

    results = run_sweep(
        radii=radii,
        alphas=alphas,
        leakages=leakages,
        medium_coupling=args.medium_coupling,
        max_continuous_w=args.max_continuous_power_w,
        max_burst_w=args.max_burst_power_w,
        energy_capacity_j=args.energy_capacity_j,
        response_time_s=args.response_time_s,
        detectability_spec=detectability_spec,
    )

    if args.compare:
        results_feasible_only = run_sweep(
            radii=radii,
            alphas=alphas,
            leakages=leakages,
            medium_coupling=args.medium_coupling,
            max_continuous_w=args.max_continuous_power_w,
            max_burst_w=args.max_burst_power_w,
            energy_capacity_j=args.energy_capacity_j,
            response_time_s=args.response_time_s,
            detectability_spec=None,
        )
    else:
        results_feasible_only = results

    # Gate block counts
    gate_counts: dict[str, int] = {}
    for r in results:
        for phase in [r.air, r.transition, r.water]:
            for fr in phase.get("failure_reasons", []):
                gate_counts[fr] = gate_counts.get(fr, 0) + 1

    def _breakthrough(results_list: list[SweepResult], label: str) -> dict:
        feasible_results = [r for r in results_list if r.bubble_feasible]
        if feasible_results:
            best = feasible_results[0]
            return {
                "achieved": True,
                "alpha": best.config.alpha,
                "leakage_1_s": best.config.leakage_1_s,
                "P_maint_w": best.P_maint_w,
                "message": f"Bubble feasible at alpha <= {best.config.alpha:.2e}, leakage <= {best.config.leakage_1_s:.2e}/s",
            }
        closest = results_list[0]
        return {
            "achieved": False,
            "closest_alpha": closest.config.alpha,
            "closest_leakage_1_s": closest.config.leakage_1_s,
            "P_maint_w": closest.P_maint_w,
            "message": (
                f"No feasibility in sweep. Closest: alpha={closest.config.alpha:.2e}, "
                f"leakage={closest.config.leakage_1_s:.2e}/s, P_maint={closest.P_maint_w:.2e} W"
            ),
        }

    breakthrough_feasible_detectable = _breakthrough(results, "feasible+detectable")
    breakthrough_feasible_only = _breakthrough(results_feasible_only, "feasible-only")

    # Output
    project_root = Path(args.project_root)
    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = project_root / "results" / "artifacts"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "meter_bubble_sweep.json"

    sweep_report = {
        "experiment": "alpha_leakage_sweep",
        "interpretation": (
            "alpha: rho_required = alpha * rho_EFE. alpha<1 = curvature cheaper (substrate mode). "
            "Leakage: P_maint = leakage * E_create."
        ),
        "detectability_enabled": args.detectability or args.compare,
        "breakthrough_requirement_feasible_only": breakthrough_feasible_only,
        "breakthrough_requirement_feasible_detectable": breakthrough_feasible_detectable,
        "gate_block_counts": gate_counts,
        "top_configs": [_serialize_result(r) for r in results[: args.top_n]],
        "all_results_summary": [_serialize_result(r) for r in results],
    }
    out_path.write_text(json.dumps(sweep_report, indent=2, ensure_ascii=True), encoding="utf-8")

    print("=== Meter bubble sweep (alpha × leakage) ===\n")
    print("Breakthrough requirement (feasible-only):")
    print(f"  {breakthrough_feasible_only['message']}\n")
    if args.compare or args.detectability:
        print("Breakthrough requirement (feasible+detectable):")
        print(f"  {breakthrough_feasible_detectable['message']}\n")
    print("Gate block counts:")
    for gate, count in sorted(gate_counts.items(), key=lambda x: -x[1]):
        print(f"  {gate}: {count}")
    print("\nTop configs (feasible first, then smallest alpha):")
    for i, r in enumerate(results[: min(5, args.top_n)], 1):
        cfg = r.config
        fea = "FEASIBLE" if r.bubble_feasible else "implausible"
        det = f" det={r.passed_signals}" if r.passed_signals else (" detectable" if r.detectable else " undetectable")
        print(f"\n  [{i}] R={cfg.radius_m} m, alpha={cfg.alpha:.2e}, leakage={cfg.leakage_1_s:.2e}/s  [{fea}]{det}")
        print(f"      rho={r.rho_required_j_m3:.4e} J/m³  E_create={r.E_create_j:.4e} J")
        print(f"      P_maint={r.P_maint_w:.4e} W  P_control_peak={r.P_control_peak_w:.4e} W")
        print(f"      dominant_failure={r.dominant_failure}")
    print(f"\nFull report: {out_path}")


if __name__ == "__main__":
    main()
