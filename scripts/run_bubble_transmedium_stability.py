"""Run bubble transmedium three-phase stability analysis.

Air → boundary_transition → water. Finds minimum energy envelope,
minimum coupling factor, and predicted instrument signals.
Appends worst-case to bubble_registry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bubble_envelope_and_stability import (
    LEAKAGE_FACTOR_STRICT_1_S,
    BubbleSpec,
    ControlSpec,
    EnergySourceEnvelope,
    EnvironmentSpec,
    analyze_transmedium_three_phase,
)
from src.results_registry import (
    BUBBLE_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_bubble_run_id,
    utc_now_iso,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CURV bubble transmedium three-phase stability: air → transition → water."
    )
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--radius-m", type=float, default=1.0, help="Bubble radius (m).")
    parser.add_argument(
        "--coupling",
        type=float,
        default=0.01,
        help="Medium coupling factor (0-1).",
    )
    parser.add_argument(
        "--power-w",
        type=float,
        default=1e12,
        help="Max continuous power (W) for energy source envelope.",
    )
    parser.add_argument(
        "--burst-power-w",
        type=float,
        default=1e13,
        help="Max burst power (W).",
    )
    parser.add_argument(
        "--burst-duration-s",
        type=float,
        default=60.0,
    )
    parser.add_argument(
        "--energy-capacity-j",
        type=float,
        default=1e18,
    )
    parser.add_argument("--speed-m-s", type=float, default=100.0)
    parser.add_argument("--arm-length-m", type=float, default=1.0)
    parser.add_argument("--no-registry", action="store_true")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    timestamp_utc = utc_now_iso()
    run_id = make_bubble_run_id(
        bubble_radius_m=args.radius_m,
        instrument="transmedium_three_phase",
        timestamp_utc=timestamp_utc,
    )

    bubble_spec = BubbleSpec(
        radius_m=args.radius_m,
        wall_thickness_m=0.01,
        medium_coupling_factor=args.coupling,
        shock_suppression=True,
    )
    energy_source = EnergySourceEnvelope(
        max_continuous_power_w=args.power_w,
        max_burst_power_w=args.burst_power_w,
        burst_duration_s=args.burst_duration_s,
        total_energy_capacity_j=args.energy_capacity_j,
        response_time_s=0.001,
        waste_heat_fraction=0.1,
        notes="transmedium envelope",
    )
    control_spec = ControlSpec()

    result = analyze_transmedium_three_phase(
        bubble_spec=bubble_spec,
        energy_source=energy_source,
        control_spec=control_spec,
        arm_length_m=args.arm_length_m,
        speed_m_s=args.speed_m_s,
    )

    out_dir = project_root / "results" / "artifacts" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "bubble_transmedium_stability.json"
    report = {
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "git_hash": get_git_hash(),
        "bubble_spec": {"radius_m": args.radius_m, "medium_coupling_factor": args.coupling},
        "result": result,
        "notes": args.notes,
    }
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"run_id={run_id}")
    print(f"min_energy_envelope_j={result['min_energy_envelope_j']:.6g}")
    print(f"min_control_power_w={result['min_control_power_w']:.6g}")
    print(f"min_coupling_for_transition={result['min_coupling_factor_for_transition_stability']}")
    print(f"bubble_feasible_all_phases={result['bubble_feasible_all_phases']}")
    print(f"output={out_path}")

    if not args.no_registry:
        reg_dir = project_root / "results" / "registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        wc = result.get("worst_case", {})
        derived = wc.get("derived", {})
        notes = f"transmedium_three_phase; min_E={result['min_energy_envelope_j']:.6g}; min_P_ctrl={result['min_control_power_w']:.6g}; min_coupling={result['min_coupling_factor_for_transition_stability']}; {args.notes}"
        row = {
            "timestamp_utc": timestamp_utc,
            "run_id": run_id,
            "git_hash": get_git_hash(),
            "bubble_radius_m": args.radius_m,
            "instrument": "transmedium_three_phase",
            "power_w": args.power_w,
            "duration_s": args.burst_duration_s,
            "curvature_m2_inv": derived.get("K_used_m2_inv", "NA"),
            "rho_required_j_m3": derived.get("rho_required_j_m3", "NA"),
            "total_energy_j": result["min_energy_envelope_j"],
            "mass_equivalent_kg": "NA",
            "verdict": "consistent_with_model" if result["bubble_feasible_all_phases"] else "physically_implausible_under_known_physics",
            "bubble_feasible": result["bubble_feasible_all_phases"],
            "dominant_failure_reason": wc.get("dominant_failure_reason", "none"),
            "policy": "strict",
            "speculative_mode": False,
            "interferometer_phase_shift_rad": result["instrument_predictions"].get("interferometer_phase_shift_proxy", "NA"),
            "clock_rate_shift": "NA",
            "gravimeter_delta_g": result["instrument_predictions"].get("gravimeter_delta_g_proxy", "NA"),
            "beam_deflection_rad": "NA",
            "candidate_flag": result["bubble_feasible_all_phases"],
            "P_control_peak_w": result["min_control_power_w"],
            "required_bandwidth_hz": derived.get("required_bandwidth_hz", "NA"),
            "substrate_coupling_alpha": 1.0,
            "leakage_factor_1_s": LEAKAGE_FACTOR_STRICT_1_S,
            "artifacts": str(out_path.relative_to(project_root).as_posix()),
            "notes": notes,
        }
        append_csv_row(reg_dir / "bubble_registry.csv", BUBBLE_REGISTRY_COLUMNS, row)
        append_jsonl(reg_dir / "bubble_registry.jsonl", row)


if __name__ == "__main__":
    main()
