"""Substrate coupling sweep: how much hidden coupling (α) makes a meter-scale bubble feasible?

Tests the hypothesis: if curvature is a mode of a deeper underlying field, the
physical energy cost may be reduced. ρ_physical = ρ_GR × α.
- α = 1: standard GR (no substrate effect)
- α < 1: curvature easier (less physical energy needed)
- α > 1: curvature harder

Sweeps alpha = [1, 1e-1, 1e-2, 1e-3, 1e-4, 1e-6] for a 1 m bubble, transmedium.
Outputs: required energy density, maintenance power, control bandwidth, instrument signals.
Answers: What minimum α would make the bubble feasible?
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.results_registry import utc_now_iso
from src.bubble_envelope_and_stability import (
    BubbleSpec,
    ControlSpec,
    EnergySourceEnvelope,
    EnvironmentSpec,
    LEAKAGE_FACTOR_STRICT_1_S,
    analyze_bubble_envelope,
    analyze_transmedium_three_phase,
)


@dataclass
class SweepPoint:
    """Single alpha point in the sweep."""

    alpha: float
    air: dict
    transition: dict
    water: dict
    bubble_feasible_all_phases: bool
    rho_required_j_m3: float
    E_create_j: float
    P_maint_w: float
    P_control_peak_w: float
    required_bandwidth_hz: float
    instrument_predictions: dict


def run_substrate_coupling_sweep(
    *,
    bubble_radius_m: float = 1.0,
    wall_thickness_m: float = 0.1,
    alphas: list[float],
    max_continuous_w: float = 1e12,
    max_burst_w: float = 1e15,
    energy_capacity_j: float = 1e20,
    response_time_s: float = 1e-6,
    medium_coupling_factor: float = 0.01,
    leakage_factor_1_s: float = LEAKAGE_FACTOR_STRICT_1_S,
    speed_m_s: float = 100.0,
    arm_length_m: float = 1.0,
) -> list[SweepPoint]:
    """Run full substrate coupling sweep across three transmedium phases."""
    results: list[SweepPoint] = []

    energy_source = EnergySourceEnvelope(
        max_continuous_power_w=max_continuous_w,
        max_burst_power_w=max_burst_w,
        burst_duration_s=60.0,
        total_energy_capacity_j=energy_capacity_j,
        response_time_s=response_time_s,
        waste_heat_fraction=0.1,
        notes="substrate_coupling_sweep",
    )
    control_spec = ControlSpec()

    for alpha in alphas:
        bubble_spec = BubbleSpec(
            radius_m=bubble_radius_m,
            wall_thickness_m=wall_thickness_m,
            active_volume_m3=None,
            curvature_target_m2_inv=None,
            medium_coupling_factor=medium_coupling_factor,
            shock_suppression=True,
            substrate_coupling_factor=alpha,
        )

        transmedium_result = analyze_transmedium_three_phase(
            bubble_spec=bubble_spec,
            energy_source=energy_source,
            control_spec=control_spec,
            arm_length_m=arm_length_m,
            leakage_factor_1_s=leakage_factor_1_s,
            speed_m_s=speed_m_s,
        )

        phases = {p["phase"]: p for p in transmedium_result["phases"]}
        air = phases.get("air", {})
        transition = phases.get("boundary_transition", {})
        water = phases.get("water", {})

        worst = transmedium_result.get("worst_case", transition)
        derived = worst.get("derived", {})

        results.append(
            SweepPoint(
                alpha=alpha,
                air=air,
                transition=transition,
                water=water,
                bubble_feasible_all_phases=transmedium_result["bubble_feasible_all_phases"],
                rho_required_j_m3=derived.get("rho_required_j_m3", 0.0),
                E_create_j=derived.get("E_create_j", 0.0),
                P_maint_w=derived.get("P_maint_w", 0.0),
                P_control_peak_w=derived.get("P_control_peak_w", 0.0),
                required_bandwidth_hz=derived.get("required_bandwidth_hz", 0.0),
                instrument_predictions=worst.get("instrument_predictions", {}),
            )
        )

    return results


def _serialize_point(p: SweepPoint) -> dict:
    """JSON-serializable summary of one sweep point."""
    return {
        "alpha": p.alpha,
        "bubble_feasible_all_phases": p.bubble_feasible_all_phases,
        "rho_required_j_m3": p.rho_required_j_m3,
        "E_create_j": p.E_create_j,
        "P_maint_w": p.P_maint_w,
        "P_control_peak_w": p.P_control_peak_w,
        "required_bandwidth_hz": p.required_bandwidth_hz,
        "instrument_predictions": p.instrument_predictions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CURV substrate coupling sweep: how much α makes a meter-scale bubble feasible?"
    )
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path.",
    )
    parser.add_argument(
        "--radius-m",
        type=float,
        default=1.0,
        help="Bubble radius (m).",
    )
    parser.add_argument(
        "--wall-thickness-m",
        type=float,
        default=0.1,
        help="Wall thickness (m).",
    )
    parser.add_argument(
        "--alphas",
        type=str,
        default="1,1e-1,1e-2,1e-3,1e-4,1e-6",
        help="Comma-separated substrate coupling factors.",
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
        "--medium-coupling",
        type=float,
        default=0.01,
        help="Medium coupling factor (0-1) for transmedium.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write full sweep JSON here.",
    )
    args = parser.parse_args()

    alphas = [float(x.strip()) for x in args.alphas.split(",")]

    results = run_substrate_coupling_sweep(
        bubble_radius_m=args.radius_m,
        wall_thickness_m=args.wall_thickness_m,
        alphas=alphas,
        max_continuous_w=args.max_continuous_power_w,
        max_burst_w=args.max_burst_power_w,
        energy_capacity_j=args.energy_capacity_j,
        medium_coupling_factor=args.medium_coupling,
    )

    project_root = Path(args.project_root)
    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = project_root / "results" / "artifacts"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = utc_now_iso().replace(":", "").replace("-", "")[:15]
        out_path = out_dir / f"substrate_coupling_sweep_{ts}.json"

    sweep_report = {
        "experiment": "substrate_coupling_sweep",
        "bubble_radius_m": args.radius_m,
        "wall_thickness_m": args.wall_thickness_m,
        "transmedium": True,
        "interpretation": (
            "alpha < 1: curvature easier (less physical energy). "
            "alpha = 1: standard GR. alpha > 1: curvature harder."
        ),
        "sweep_points": [_serialize_point(p) for p in results],
    }
    out_path.write_text(
        json.dumps(sweep_report, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    # Find minimum alpha for feasibility
    feasible_alphas = [p.alpha for p in results if p.bubble_feasible_all_phases]
    min_alpha_feasible = min(feasible_alphas) if feasible_alphas else None

    print("=== Substrate coupling sweep ===\n")
    print(f"Bubble: R={args.radius_m} m, wall={args.wall_thickness_m} m")
    print("Transmedium: air -> boundary_transition -> water")
    print("Interpretation: rho_physical = rho_GR * alpha (alpha < 1 = curvature easier)\n")
    print("alpha   | rho_required   | E_create     | P_maint    | P_control   | BW_hz       | feasible")
    print("-" * 95)
    for p in results:
        fea = "yes" if p.bubble_feasible_all_phases else "no"
        print(
            f"{p.alpha:7.2e} | {p.rho_required_j_m3:13.4e} | {p.E_create_j:11.4e} | "
            f"{p.P_maint_w:9.4e} | {p.P_control_peak_w:10.4e} | "
            f"{p.required_bandwidth_hz:10.4e} | {fea}"
        )
    if min_alpha_feasible is not None:
        print(f"\nMinimum alpha for feasibility: {min_alpha_feasible:.2e}")
    else:
        print("\nNo alpha in sweep achieved feasibility (try lower alpha or higher power envelope).")
    print(f"\nFull report: {out_path}")


if __name__ == "__main__":
    main()
