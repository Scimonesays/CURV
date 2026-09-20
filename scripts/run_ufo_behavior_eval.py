"""Run UFO flight behavior evaluation.

CLI for CURV UFO behavior engine. Evaluates kinematics, mechanism lanes,
constraint gates, and produces verdict + breakpoint analysis.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.results_registry import (
    UFO_BEHAVIOR_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_ufo_run_id,
    utc_now_iso,
)
from src.ufo_behavior_spec import UFOBehaviorSpec
from src.ufo_flight_behavior_evaluator import evaluate_ufo_flight_behavior, find_breakpoint


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CURV UFO flight behavior evaluation: kinematics, lanes, gates, verdict."
    )
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path.",
    )
    parser.add_argument(
        "--profile",
        choices=["tic_tac"],
        default="tic_tac",
        help="Named UAP profile.",
    )
    parser.add_argument("--mass-kg-min", type=float, default=100.0, help="Min mass (kg).")
    parser.add_argument("--mass-kg-max", type=float, default=10000.0, help="Max mass (kg).")
    parser.add_argument(
        "--policy",
        choices=["strict", "normal", "sandbox"],
        default="strict",
        help="Policy preset.",
    )
    parser.add_argument(
        "--max-accel-g",
        type=float,
        default=None,
        help="Override max acceleration (g).",
    )
    parser.add_argument(
        "--max-speed-mps",
        type=float,
        default=None,
        help="Override max speed (m/s).",
    )
    parser.add_argument(
        "--turn-radius-m",
        type=float,
        default=None,
        help="Override turn radius (m).",
    )
    parser.add_argument(
        "--hover-duration-s",
        type=float,
        default=None,
        help="Override hover duration (s).",
    )
    parser.add_argument(
        "--transmedium",
        action="store_true",
        help="Enable transmedium (water) behavior.",
    )
    parser.add_argument(
        "--custom-json",
        type=str,
        default=None,
        help="Load spec from custom JSON file.",
    )
    parser.add_argument(
        "--breakpoint",
        action="store_true",
        help="Run breakpoint finder.",
    )
    parser.add_argument("--notes", default="", help="Optional notes.")
    parser.add_argument("--no-registry", action="store_true", help="Skip registry append.")
    parser.add_argument("--no-jsonl", action="store_true", help="Skip JSONL mirror.")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    timestamp_utc = utc_now_iso()

    if args.custom_json:
        spec = UFOBehaviorSpec.from_custom_json(args.custom_json)
    else:
        spec = UFOBehaviorSpec.from_common_uap_profile("tic_tac")

    # Overrides
    overrides = {}
    if args.max_accel_g is not None:
        overrides["max_accel_m_s2"] = args.max_accel_g * 9.81
    if args.max_speed_mps is not None:
        overrides["max_speed_m_s"] = args.max_speed_mps
    if args.turn_radius_m is not None:
        overrides["turn_radius_m"] = args.turn_radius_m
    if args.hover_duration_s is not None:
        overrides["hover_duration_s"] = args.hover_duration_s
    if args.transmedium:
        overrides["transmedium"] = True

    if overrides:
        d = spec.to_dict()
        d.update(overrides)
        spec = UFOBehaviorSpec.from_dict(d)

    result = evaluate_ufo_flight_behavior(
        spec,
        mass_kg_min=args.mass_kg_min,
        mass_kg_max=args.mass_kg_max,
        policy=args.policy,
    )

    breakpoint_result = None
    if args.breakpoint:
        breakpoint_result = find_breakpoint(
            spec,
            mass_kg=(args.mass_kg_min + args.mass_kg_max) / 2,
            policy=args.policy,
        )
        result["breakpoint_analysis"] = breakpoint_result

    run_id = make_ufo_run_id(
        profile=args.profile,
        policy=args.policy,
        mass_kg=args.mass_kg_max,
        timestamp_utc=timestamp_utc,
    )

    report = {
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "git_hash": get_git_hash(),
        "profile": args.profile,
        "spec": spec.to_dict(),
        "verdict": result["verdict"],
        "top_conflicts": result["top_conflicts"],
        "lane_results": result["lane_results"],
        "signature_predictions": result["signature_predictions"],
        "sensitivity": result["sensitivity"],
        "breakpoint_analysis": breakpoint_result,
        "notes": args.notes,
    }

    out_dir = project_root / "results" / "artifacts" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ufo_behavior_eval.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    print(f"run_id={run_id}")
    print(f"verdict={result['verdict']}")
    print(f"top_conflicts={result['top_conflicts']}")
    print(f"output={out_path}")

    if args.breakpoint and breakpoint_result:
        print(f"breakpoint_relaxations={breakpoint_result.get('relaxations_to_viable', [])}")

    if not args.no_registry:
        reg_dir = project_root / "results" / "registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        rel_artifact = str(out_path.resolve().relative_to(project_root.resolve()).as_posix())
        row = {
            "timestamp_utc": timestamp_utc,
            "run_id": run_id,
            "git_hash": get_git_hash(),
            "profile": args.profile,
            "policy": args.policy,
            "verdict": result["verdict"],
            "mass_kg_min": args.mass_kg_min,
            "mass_kg_max": args.mass_kg_max,
            "top_conflicts": ";".join(result["top_conflicts"][:5]),
            "artifacts": rel_artifact,
            "notes": args.notes,
        }
        append_csv_row(reg_dir / "ufo_behavior_registry.csv", UFO_BEHAVIOR_REGISTRY_COLUMNS, row)
        if not args.no_jsonl:
            append_jsonl(reg_dir / "ufo_behavior_registry.jsonl", row)


if __name__ == "__main__":
    main()
