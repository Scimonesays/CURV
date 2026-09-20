"""Run bubble experiment feasibility analysis.

CLI for CURV spacetime bubble analysis. Predicts instrument signals,
energy requirements, artifact risks, and feasibility verdict.

Supports two modes:
- Legacy: --bubble-radius-m, --power-w, --duration-s (single-phase feasibility)
- Envelope + transmedium: --transmedium + envelope flags (creation, maintenance, control,
  three phases: air, boundary_transition, water)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bubble_envelope_and_stability import (
    BubbleSpec,
    ControlSpec,
    EnergySourceEnvelope,
    EnvironmentSpec,
    LEAKAGE_FACTOR_SANDBOX_1_S,
    LEAKAGE_FACTOR_STRICT_1_S,
    analyze_bubble_envelope,
)
from src.bubble_feasibility_analyzer import analyze_bubble_feasibility
from src.exotic_power_feasibility import exotic_policy_from_preset
from src.experiment_design_generator import generate_experiment_design
from src.results_registry import (
    BUBBLE_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_bubble_run_id,
    utc_now_iso,
)


def _run_envelope_mode(args: argparse.Namespace, project_root: Path) -> None:
    """Run bubble envelope analysis (single or three-phase transmedium)."""
    bubble_spec = BubbleSpec(
        radius_m=args.radius_m,
        wall_thickness_m=args.wall_thickness_m,
        active_volume_m3=args.active_volume_m3,
        curvature_target_m2_inv=args.curvature_target_m2_inv,
        medium_coupling_factor=args.medium_coupling_factor,
        shock_suppression=True,
        substrate_coupling_factor=args.substrate_coupling_alpha,
    )
    energy_source = EnergySourceEnvelope(
        max_continuous_power_w=args.max_continuous_power_w,
        max_burst_power_w=args.max_burst_power_w,
        burst_duration_s=args.burst_duration_s,
        total_energy_capacity_j=args.energy_capacity_j,
        response_time_s=args.response_time_s,
        waste_heat_fraction=args.waste_heat_fraction,
        notes=args.notes,
    )
    control_spec = ControlSpec(
        required_bandwidth_hz_target=100.0,
        controller_gain_limit=10.0,
        stability_margin_target=6.0,
    )
    leakage = LEAKAGE_FACTOR_SANDBOX_1_S if args.leakage_factor is None else args.leakage_factor

    if args.transmedium:
        phases = [
            ("air", EnvironmentSpec(mode="air")),
            ("boundary_transition", EnvironmentSpec(mode="boundary_transition")),
            ("water", EnvironmentSpec(mode="water")),
        ]
    else:
        phases = [("air", EnvironmentSpec(mode="air"))]

    results: dict[str, dict] = {}
    worst_feasible = True
    worst_failure = "none"
    worst_P_control = 0.0
    worst_bandwidth = 0.0
    worst_E_create = 0.0
    worst_rho = 0.0

    timestamp_utc = utc_now_iso()
    run_id = make_bubble_run_id(
        bubble_radius_m=args.radius_m,
        instrument="envelope",
        timestamp_utc=timestamp_utc,
    )
    run_id = run_id.replace("_envelope", "_bubble_envelope")
    out_dir = project_root / "results" / "artifacts" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    for phase_name, env in phases:
        out = analyze_bubble_envelope(
            bubble_spec=bubble_spec,
            environment=env,
            energy_source=energy_source,
            control_spec=control_spec,
            leakage_factor_1_s=leakage,
            arm_length_m=args.arm_length_m,
        )
        results[phase_name] = out
        if not out["bubble_feasible"]:
            worst_feasible = False
            if out["dominant_failure_reason"] != "none":
                worst_failure = out["dominant_failure_reason"]
        d = out["derived"]
        if d["P_control_peak_w"] > worst_P_control:
            worst_P_control = d["P_control_peak_w"]
            worst_bandwidth = d["required_bandwidth_hz"]
            worst_E_create = d["E_create_j"]
            worst_rho = d["rho_required_j_m3"]

        phase_path = out_dir / f"bubble_analysis_{phase_name}.json"
        phase_path.write_text(
            json.dumps(out, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    combined = {
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "git_hash": get_git_hash(),
        "phases": results,
        "worst_case": {
            "bubble_feasible": worst_feasible,
            "dominant_failure_reason": worst_failure,
            "P_control_peak_w": worst_P_control,
            "required_bandwidth_hz": worst_bandwidth,
            "E_create_j": worst_E_create,
            "rho_required_j_m3": worst_rho,
        },
        "notes": args.notes,
    }
    combined_path = out_dir / "bubble_analysis.json"
    combined_path.write_text(
        json.dumps(combined, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    if not args.no_registry:
        reg_dir = project_root / "results" / "registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        rel_artifact = str(combined_path.resolve().relative_to(project_root.resolve()).as_posix())
        # Use transition phase curvature if available
        k_used = results.get("boundary_transition", results["air"])["derived"]["K_used_m2_inv"]
        pred = results.get("boundary_transition", results["air"])["instrument_predictions"]
        row = {
            "timestamp_utc": timestamp_utc,
            "run_id": run_id,
            "git_hash": get_git_hash(),
            "bubble_radius_m": args.radius_m,
            "instrument": "envelope",
            "power_w": worst_P_control,
            "duration_s": args.burst_duration_s,
            "curvature_m2_inv": k_used,
            "rho_required_j_m3": worst_rho,
            "total_energy_j": worst_E_create,
            "mass_equivalent_kg": "NA",
            "verdict": "consistent_with_model" if worst_feasible else "physically_implausible_under_known_physics",
            "bubble_feasible": worst_feasible,
            "dominant_failure_reason": worst_failure,
            "policy": "envelope",
            "speculative_mode": "NA",
            "interferometer_phase_shift_rad": pred.get("interferometer_phase_shift_proxy", "NA"),
            "clock_rate_shift": pred.get("clock_fractional_shift_proxy", "NA"),
            "gravimeter_delta_g": pred.get("gravimeter_delta_g_proxy", "NA"),
            "beam_deflection_rad": "NA",
            "candidate_flag": worst_feasible,
            "P_control_peak_w": worst_P_control,
            "required_bandwidth_hz": worst_bandwidth,
            "substrate_coupling_alpha": args.substrate_coupling_alpha,
            "leakage_factor_1_s": leakage,
            "artifacts": rel_artifact,
            "notes": args.notes,
        }
        append_csv_row(reg_dir / "bubble_registry.csv", BUBBLE_REGISTRY_COLUMNS, row)
        if not args.no_jsonl:
            append_jsonl(reg_dir / "bubble_registry.jsonl", row)

    print(f"run_id={run_id}")
    print(f"verdict={'consistent_with_model' if worst_feasible else 'physically_implausible_under_known_physics'}")
    print(f"bubble_feasible={worst_feasible}")
    print(f"dominant_failure_reason={worst_failure}")
    print(f"P_control_peak_w={worst_P_control:.6g}")
    print(f"required_bandwidth_hz={worst_bandwidth:.6g}")
    print(f"output={combined_path}")


def _run_legacy_mode(args: argparse.Namespace, project_root: Path) -> None:
    """Run legacy bubble feasibility (single-phase)."""
    policy = exotic_policy_from_preset(
        args.policy,
        allow_speculative_override=args.allow_speculative if args.policy == "normal" else None,
    )
    feasibility = analyze_bubble_feasibility(
        bubble_radius_m=args.bubble_radius_m,
        active_volume_m3=args.active_volume_m3,
        required_power_w=args.power_w,
        duration_s=args.duration_s,
        instrument_type=args.instrument,
        arm_length_m=args.arm_length_m,
        policy=policy,
    )

    energy_report = feasibility["required_energy"]
    design = generate_experiment_design(
        curvature_m2_inv=energy_report["curvature_m2_inv"],
        instrument_type=args.instrument,
        arm_length_m=args.arm_length_m,
    )

    timestamp_utc = utc_now_iso()
    run_id = make_bubble_run_id(
        bubble_radius_m=args.bubble_radius_m,
        instrument=args.instrument,
        timestamp_utc=timestamp_utc,
    )

    report = {
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "git_hash": get_git_hash(),
        "bubble_parameters": feasibility["bubble_parameters"],
        "curvature_requirements": {
            "curvature_m2_inv": energy_report["curvature_m2_inv"],
            "radius_m": feasibility["bubble_parameters"]["bubble_radius_m"],
        },
        "energy_requirements": energy_report,
        "signal_prediction": feasibility["predicted_signal"],
        "artifact_risks": feasibility["artifact_risk"],
        "feasibility_verdict": feasibility["verdict"],
        "bubble_feasible": feasibility["bubble_feasible"],
        "dominant_failure_reason": feasibility["dominant_failure_reason"],
        "experiment_design": design,
        "notes": args.notes,
    }

    out_dir = project_root / "results" / "artifacts" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "bubble_analysis.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    if not args.no_registry:
        reg_dir = project_root / "results" / "registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        rel_artifact = str(out_path.resolve().relative_to(project_root.resolve()).as_posix())
        curvature_m2_inv = float(energy_report["curvature_m2_inv"])
        sig = feasibility["predicted_signal"]
        phase_rad = sig.get("phase_shift_rad") if args.instrument == "interferometer" else "NA"
        clock_shift = sig.get("clock_rate_shift") if args.instrument == "atomic_clock" else "NA"
        grav_dg = sig.get("delta_g_m_s2") if args.instrument == "gravimeter" else "NA"
        beam_rad = sig.get("deflection_angle_rad") if args.instrument == "beam_deflection" else "NA"
        speculative_mode = policy.allow_speculative
        candidate_flag = (
            feasibility["verdict"] == "consistent_with_model"
            and args.policy != "sandbox"
        )
        row = {
            "timestamp_utc": timestamp_utc,
            "run_id": run_id,
            "git_hash": get_git_hash(),
            "bubble_radius_m": args.bubble_radius_m,
            "instrument": args.instrument,
            "power_w": args.power_w,
            "duration_s": args.duration_s,
            "curvature_m2_inv": curvature_m2_inv,
            "rho_required_j_m3": energy_report["energy_density_j_m3"],
            "total_energy_j": energy_report["total_energy_j"],
            "mass_equivalent_kg": energy_report["mass_equivalent_kg"],
            "verdict": feasibility["verdict"],
            "bubble_feasible": feasibility["bubble_feasible"],
            "dominant_failure_reason": feasibility["dominant_failure_reason"],
            "policy": args.policy,
            "speculative_mode": speculative_mode,
            "interferometer_phase_shift_rad": phase_rad,
            "clock_rate_shift": clock_shift,
            "gravimeter_delta_g": grav_dg,
            "beam_deflection_rad": beam_rad,
            "candidate_flag": candidate_flag,
            "P_control_peak_w": "NA",
            "required_bandwidth_hz": "NA",
            "artifacts": rel_artifact,
            "notes": args.notes,
        }
        append_csv_row(reg_dir / "bubble_registry.csv", BUBBLE_REGISTRY_COLUMNS, row)
        if not args.no_jsonl:
            append_jsonl(reg_dir / "bubble_registry.jsonl", row)

    print(f"run_id={run_id}")
    print(f"verdict={feasibility['verdict']}")
    print(f"bubble_feasible={feasibility['bubble_feasible']}")
    print(f"dominant_failure_reason={feasibility['dominant_failure_reason']}")
    print(f"output={out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CURV bubble experiment analysis: signal prediction, energy requirements, feasibility."
    )
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path.",
    )
    # Legacy mode args
    parser.add_argument("--bubble-radius-m", type=float, default=None, help="Bubble radius (m). [legacy]")
    parser.add_argument(
        "--active-volume-m3",
        type=float,
        default=None,
        help="Active volume (m³). Default: spherical (4/3)πR³.",
    )
    parser.add_argument("--power-w", type=float, default=None, help="Required power (W). [legacy]")
    parser.add_argument("--duration-s", type=float, default=None, help="Duration (s). [legacy]")
    parser.add_argument(
        "--instrument",
        choices=["interferometer", "atomic_clock", "beam_deflection", "gravimeter"],
        default="interferometer",
        help="Instrument type. [legacy]",
    )
    parser.add_argument(
        "--arm-length-m",
        type=float,
        default=1.0,
        help="Arm/baseline length (m).",
    )
    parser.add_argument(
        "--policy",
        choices=["strict", "normal", "sandbox"],
        default="strict",
        help="Exotic power policy preset (default: strict). [legacy]",
    )
    parser.add_argument(
        "--allow-speculative",
        action="store_true",
        help="Allow speculative exotic (only applies when policy=normal). [legacy]",
    )
    # Envelope / transmedium args
    parser.add_argument("--transmedium", action="store_true", help="Run three-phase transmedium analysis.")
    parser.add_argument("--radius-m", type=float, default=1.0, help="Bubble radius (m). [envelope]")
    parser.add_argument(
        "--wall-thickness-m",
        type=float,
        default=0.1,
        help="Wall thickness (m). [envelope]",
    )
    parser.add_argument(
        "--medium-coupling-factor",
        type=float,
        default=1e-4,
        help="Medium coupling 0–1. [envelope]",
    )
    parser.add_argument(
        "--substrate-coupling-alpha",
        type=float,
        default=1.0,
        help="Substrate coupling α: rho_required = α·rho_EFE. α<1 = curvature cheaper. [envelope]",
    )
    parser.add_argument(
        "--leakage-factor",
        type=float,
        default=None,
        help="Leakage factor (1/s). Default: strict 1e-3. [envelope]",
    )
    parser.add_argument(
        "--curvature-target-m2-inv",
        type=float,
        default=None,
        help="Explicit curvature (m⁻²). [envelope]",
    )
    parser.add_argument(
        "--max-continuous-power-w",
        type=float,
        default=1e9,
        help="Max continuous power (W). [envelope]",
    )
    parser.add_argument(
        "--max-burst-power-w",
        type=float,
        default=1e11,
        help="Max burst power (W). [envelope]",
    )
    parser.add_argument(
        "--burst-duration-s",
        type=float,
        default=1.0,
        help="Burst duration (s). [envelope]",
    )
    parser.add_argument(
        "--energy-capacity-j",
        type=float,
        default=1e14,
        help="Total energy capacity (J). [envelope]",
    )
    parser.add_argument(
        "--response-time-s",
        type=float,
        default=1e-3,
        help="Control response time (s). [envelope]",
    )
    parser.add_argument(
        "--waste-heat-fraction",
        type=float,
        default=0.1,
        help="Waste heat fraction. [envelope]",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Optional notes for report.",
    )
    parser.add_argument("--no-registry", action="store_true", help="Skip registry append.")
    parser.add_argument("--no-jsonl", action="store_true", help="Skip JSONL mirror append.")
    args = parser.parse_args()

    project_root = Path(args.project_root)

    if args.transmedium or (
        args.bubble_radius_m is None
        and args.power_w is None
        and args.duration_s is None
    ):
        _run_envelope_mode(args, project_root)
    else:
        if args.bubble_radius_m is None or args.power_w is None or args.duration_s is None:
            parser.error("Legacy mode requires --bubble-radius-m, --power-w, --duration-s")
        _run_legacy_mode(args, project_root)


if __name__ == "__main__":
    main()
