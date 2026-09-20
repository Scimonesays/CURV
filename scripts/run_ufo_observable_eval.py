"""Run UFO observable evaluation.

Pipeline: observables → physics → lanes → signature gates → negative-heavy scorecard.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.results_registry import (
    UFO_OBSERVABLE_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_ufo_observable_run_id,
    utc_now_iso,
)
from src.ufo_observable_evaluator import evaluate_ufo_observables
from src.ufo_mechanisms.element_x_edgecase import ElementXSpec, MomentumExchangeMode
from src.ufo_observables import (
    profile_edgecase_hypersonic_no_boom,
    profile_hypersonic_no_boom,
    profile_plausible_moderate,
    profile_tictac_like,
    from_json,
    UFOBehaviorSpec,
    UFOObservableClaims,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CURV UFO observable evaluation: negative-heavy scorecard."
    )
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument(
        "--profile",
        choices=["tictac_like", "hypersonic_no_boom", "edgecase_hypersonic_no_boom", "plausible_moderate"],
        default="tictac_like",
    )
    parser.add_argument("--mass-kg-min", type=float, default=100.0)
    parser.add_argument("--mass-kg-max", type=float, default=10000.0)
    parser.add_argument(
        "--policy",
        choices=["strict", "normal", "sandbox"],
        default="strict",
    )
    parser.add_argument("--custom-json", type=str, default=None, help="Load from JSON file.")
    parser.add_argument("--enable-element-x", action="store_true", help="Enable Element X edge-case lane with custom params.")
    parser.add_argument("--allow-speculative", action="store_true", help="Override policy to allow speculative physics.")
    parser.add_argument("--element-x-max-power-density-w-m3", type=float, default=1e18)
    parser.add_argument("--element-x-waste-heat-fraction", type=float, default=1e-6)
    parser.add_argument("--no-element-x-shock-suppression", action="store_true", help="Disable Element X shock suppression claim (default: suppression enabled).")
    parser.add_argument("--element-x-medium-coupling-factor", type=float, default=1e-6)
    parser.add_argument(
        "--element-x-momentum-exchange-mode",
        choices=["exhaust", "air_coupling", "field_coupling", "metric_bubble"],
        default="metric_bubble",
    )
    parser.add_argument("--notes", default="")
    parser.add_argument("--no-registry", action="store_true")
    parser.add_argument("--no-jsonl", action="store_true")
    args = parser.parse_args()

    if args.custom_json:
        behavior, claims = from_json(args.custom_json)
    elif args.profile == "tictac_like":
        behavior, claims = profile_tictac_like()
    elif args.profile == "edgecase_hypersonic_no_boom":
        behavior, claims = profile_edgecase_hypersonic_no_boom()
    elif args.profile == "plausible_moderate":
        behavior, claims = profile_plausible_moderate()
    else:
        behavior, claims = profile_hypersonic_no_boom()

    mode_map = {
        "exhaust": MomentumExchangeMode.EXHAUST,
        "air_coupling": MomentumExchangeMode.AIR_COUPLING,
        "field_coupling": MomentumExchangeMode.FIELD_COUPLING,
        "metric_bubble": MomentumExchangeMode.METRIC_BUBBLE,
    }
    element_x_spec = ElementXSpec(
        max_power_density_w_m3=args.element_x_max_power_density_w_m3,
        waste_heat_fraction=args.element_x_waste_heat_fraction,
        shock_suppression=not getattr(args, "no_element_x_shock_suppression", False),
        medium_coupling_factor=args.element_x_medium_coupling_factor,
        momentum_exchange_mode=mode_map[args.element_x_momentum_exchange_mode],
    ) if args.enable_element_x else None

    result = evaluate_ufo_observables(
        behavior,
        claims,
        (args.mass_kg_min, args.mass_kg_max),
        policy=args.policy,
        element_x_spec=element_x_spec,
        enable_element_x=args.enable_element_x,
        allow_speculative_override=args.allow_speculative if args.allow_speculative else None,
    )

    timestamp_utc = utc_now_iso()
    run_id = make_ufo_observable_run_id(
        args.profile,
        args.policy,
        args.mass_kg_max,
        timestamp_utc,
    )

    report = {
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "git_hash": get_git_hash(),
        "profile": args.profile,
        "verdict": result["verdict"],
        "failed_gates": result["failed_gates"],
        "n_failed_gates": len(result["failed_gates"]),
        "dominant_failed_gate": result.get("dominant_failed_gate"),
        "failed_gates_by_category": result.get("failed_gates_by_category", {}),
        "assumption_deltas_to_pass": result.get("assumption_deltas_to_pass", []),
        "lane_rankings": result["lane_rankings"],
        "lane_results": result["lane_results"],
        "gate_results_by_lane": result.get("gate_results_by_lane", {}),
        "what_would_need_to_be_true": result["what_would_need_to_be_true"],
        "minimal_violation_finder": result.get("minimal_violation_finder", {}),
        "sensor_artifact_notes": result.get("sensor_artifact_notes", []),
        "physics": result["physics"],
        "notes": args.notes,
    }

    out_dir = Path(args.project_root) / "results" / "artifacts" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ufo_observable_eval.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    print(f"run_id={run_id}")
    print(f"verdict={result['verdict']}")
    print(f"n_failed_gates={len(result['failed_gates'])}")
    print(f"output={out_path}")

    if not args.no_registry:
        reg_dir = Path(args.project_root) / "results" / "registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        rel = str(out_path.resolve().relative_to(Path(args.project_root).resolve()).as_posix())
        row = {
            "timestamp_utc": timestamp_utc,
            "run_id": run_id,
            "git_hash": get_git_hash(),
            "profile": args.profile,
            "policy": args.policy,
            "verdict": result["verdict"],
            "n_failed_gates": len(result["failed_gates"]),
            "mass_kg_min": args.mass_kg_min,
            "mass_kg_max": args.mass_kg_max,
            "artifacts": rel,
            "notes": args.notes,
        }
        append_csv_row(reg_dir / "ufo_observable_registry.csv", UFO_OBSERVABLE_REGISTRY_COLUMNS, row)
        if not args.no_jsonl:
            append_jsonl(reg_dir / "ufo_observable_registry.jsonl", row)


if __name__ == "__main__":
    main()
