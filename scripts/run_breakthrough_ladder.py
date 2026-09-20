"""Run Breakthrough Ladder: increasingly strict UFO-observable tests with scoreboard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.breakthrough_ladder import (
    build_ladder_steps,
    run_breakthrough_ladder,
)
from src.results_registry import (
    BREAKTHROUGH_LADDER_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_breakthrough_ladder_run_id,
    utc_now_iso,
)


def _print_scoreboard(report: dict) -> None:
    """Print final scoreboard to terminal."""
    print("\n" + "=" * 60)
    print("BREAKTHROUGH LADDER SCOREBOARD")
    print("=" * 60)
    print(f"run_id: {report['run_id']}")
    print(f"mass_range: {report['mass_range']['min_kg']} - {report['mass_range']['max_kg']} kg")
    overall = report["overall"]
    print(f"deepest_step_reached_without_speculation: {overall['deepest_step_reached_without_speculation']}")
    print(f"deepest_step_not_physically_implausible: {overall.get('deepest_step_not_physically_implausible', 'N/A')}")
    print(f"first_failure_step: {overall['first_failure_step']}")
    print(f"first_step_high_severity_gates_fire: {overall.get('first_step_high_severity_gates_fire', 'N/A')}")
    print(f"most_common_failure_categories: {overall['most_common_failure_categories']}")
    print("-" * 60)
    for s in report["steps"]:
        verdict = s["verdict"]
        n = s["n_failed_gates"]
        dom = s.get("dominant_failed_gate", "?")
        lane = s.get("least_bad_lane", "?")
        print(f"  Step {s['step']:2d} {s['name']:25s} | verdict={verdict[:20]:20s} | n_failed={n:2d} | dom={str(dom)[:35]:35s} | least_bad={lane}")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CURV Breakthrough Ladder: run increasingly strict UFO-observable tests."
    )
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
    )
    parser.add_argument(
        "--policy",
        choices=["strict", "normal", "sandbox"],
        default="strict",
    )
    parser.add_argument("--mass-kg-min", type=float, default=100.0)
    parser.add_argument("--mass-kg-max", type=float, default=10000.0)
    parser.add_argument(
        "--include-speculative-step",
        action="store_true",
        help="Add optional Step 7 (sandbox, allow_speculative, Element X).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output base dir; default: results/artifacts/<run_id>/",
    )
    parser.add_argument("--no-registry", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    mass_range = (args.mass_kg_min, args.mass_kg_max)
    timestamp_utc = utc_now_iso()
    run_id = make_breakthrough_ladder_run_id(timestamp_utc)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = project_root / "results" / "artifacts" / run_id

    output_dir.mkdir(parents=True, exist_ok=True)

    steps = build_ladder_steps(
        include_speculative=args.include_speculative_step,
        policy_override=args.policy,
    )

    report = run_breakthrough_ladder(steps, mass_range, output_dir, run_id)

    _print_scoreboard(report)

    summary_path = output_dir / "breakthrough_ladder_summary.json"
    print(f"run_id={run_id}")
    print(f"output={summary_path}")
    print(f"steps_dir={output_dir / 'breakthrough_steps'}")

    if not args.no_registry:
        reg_dir = project_root / "results" / "registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        overall = report["overall"]
        notes = f"breakthrough_ladder: deepest_step={overall['deepest_step_reached_without_speculation']}; first_fail={overall['first_failure_step']}"
        rel = str(summary_path.resolve().relative_to(project_root.resolve()).as_posix())
        row = {
            "timestamp_utc": timestamp_utc,
            "run_id": run_id,
            "git_hash": get_git_hash(),
            "policy": args.policy,
            "mass_kg_min": args.mass_kg_min,
            "mass_kg_max": args.mass_kg_max,
            "deepest_step": overall["deepest_step_reached_without_speculation"],
            "first_fail_step": overall["first_failure_step"],
            "artifacts": rel,
            "notes": notes,
        }
        csv_path = reg_dir / "breakthrough_ladder_registry.csv"
        append_csv_row(csv_path, BREAKTHROUGH_LADDER_REGISTRY_COLUMNS, row)
        append_jsonl(reg_dir / "breakthrough_ladder_registry.jsonl", row)


if __name__ == "__main__":
    main()
