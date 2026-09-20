"""Seed console visual-state fixtures for live verification (local only)."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "results" / "registry"
ART = ROOT / "results" / "artifacts"
JOBS = ROOT / "results" / "console_jobs"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_csv(name: str, columns: list[str], rows: list[dict]) -> None:
    REG.mkdir(parents=True, exist_ok=True)
    path = REG / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in columns})


def write_artifact(run_id: str, *, plots: bool = True, summary: dict | None = None) -> Path:
    base = ART / run_id
    (base / "plots").mkdir(parents=True, exist_ok=True)
    (base / "metrics").mkdir(parents=True, exist_ok=True)
    (base / "raw").mkdir(parents=True, exist_ok=True)
    if summary is not None:
        (base / "raw" / f"{run_id}_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
    if plots:
        # Minimal valid 1x1 PNG
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
        (base / "plots" / f"{run_id}_deflection_curve.png").write_bytes(png)
    (base / "metrics" / f"{run_id}_results.csv").write_text(
        "b_over_m,residual\n100,0.01\n200,0.02\n", encoding="utf-8"
    )
    return base


def main() -> None:
    ts = utc()
    pass_id = "20260722_200000Z_demo_pass_ppn"
    fail_id = "20260722_200100Z_demo_fail_ufo"
    spec_id = "20260722_200200Z_demo_speculative_bubble"
    unindexed_id = "20260722_200300Z_source_phase_map_unindexed"

    write_artifact(
        pass_id,
        summary={
            "promotion_level": "candidate",
            "reasons": ["demo_pass"],
            "gate0_pass": True,
        },
    )
    (ART / pass_id / "raw" / f"{pass_id}_promotion_eval.json").write_text(
        json.dumps(
            {
                "promotion_level": "candidate",
                "reasons": ["residual_structure_ok"],
                "candidate_checks": {"ok": True},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    write_artifact(
        fail_id,
        summary={
            "verdict": "physically_implausible_under_known_physics",
            "n_failed_gates": 3,
            "failed_gates": [
                {
                    "passed": False,
                    "reason": "supersonic_no_boom_requires_shock_mitigation",
                    "severity": "high",
                    "lane": "aerodynamic",
                },
                {
                    "passed": False,
                    "reason": "power_budget_exceeded",
                    "severity": "high",
                    "lane": "conventional_thrust",
                },
                {
                    "passed": False,
                    "reason": "thermal_limit",
                    "severity": "med",
                    "lane": "field_propulsion",
                },
            ],
            "lane_rankings": [
                {"lane": "aerodynamic", "passed": False, "fail_count": 2},
                {"lane": "conventional_thrust", "passed": False, "fail_count": 1},
            ],
        },
    )

    write_artifact(
        spec_id,
        summary={
            "verdict": "requires_speculative_physics",
            "allow_speculative": True,
            "bubble_feasible": False,
        },
    )

    # Unindexed artifact-only (phase map style)
    write_artifact(
        unindexed_id,
        summary={
            "kind": "source_phase_map",
            "note": "artifact-only; no registry row",
        },
    )
    (ART / unindexed_id / "metrics" / f"{unindexed_id}_phase_map.csv").write_text(
        "log10_power_w,log10_duration_s,gateA_pass,dominant_rejection_gate\n"
        "4,2,false,power\n5,3,true,none\n",
        encoding="utf-8",
    )

    results_cols = [
        "timestamp_utc",
        "run_id",
        "batch_id",
        "git_hash",
        "model_mode",
        "k",
        "sigma",
        "N",
        "connectivity",
        "field_exponent",
        "r2_inv",
        "r2_lin",
        "delta_r2",
        "aic_inv",
        "aic_lin",
        "superposition_median_rel_error",
        "resolution_mean_curve_diff",
        "gateA_scaling_pass",
        "gateA_superposition_pass",
        "gateA_resolution_pass",
        "gateA_pass",
        "artifacts",
        "notes",
    ]
    write_csv(
        "results_registry",
        results_cols,
        [
            {
                "timestamp_utc": ts,
                "run_id": pass_id,
                "batch_id": "",
                "git_hash": "ab13e7d",
                "model_mode": "ppn_sweep",
                "gateA_scaling_pass": "True",
                "gateA_superposition_pass": "True",
                "gateA_resolution_pass": "True",
                "gateA_pass": "True",
                "artifacts": f"results/artifacts/{pass_id}/raw/{pass_id}_promotion_eval.json;results/artifacts/{pass_id}/plots/{pass_id}_deflection_curve.png",
                "notes": "gate0:pass promote:candidate demo_pass",
            }
        ],
    )

    ufo_cols = [
        "timestamp_utc",
        "run_id",
        "git_hash",
        "profile",
        "policy",
        "verdict",
        "n_failed_gates",
        "mass_kg_min",
        "mass_kg_max",
        "artifacts",
        "notes",
    ]
    write_csv(
        "ufo_observable_registry",
        ufo_cols,
        [
            {
                "timestamp_utc": ts,
                "run_id": fail_id,
                "git_hash": "ab13e7d",
                "profile": "tictac_like",
                "policy": "strict",
                "verdict": "physically_implausible_under_known_physics",
                "n_failed_gates": "3",
                "mass_kg_min": "100",
                "mass_kg_max": "10000",
                "artifacts": f"results/artifacts/{fail_id}/raw/{fail_id}_summary.json",
                "notes": "demo_hard_fail",
            }
        ],
    )

    bubble_cols = [
        "timestamp_utc",
        "run_id",
        "git_hash",
        "bubble_radius_m",
        "instrument",
        "power_w",
        "duration_s",
        "curvature_m2_inv",
        "rho_required_j_m3",
        "verdict",
        "bubble_feasible",
        "dominant_failure_reason",
        "allow_speculative",
        "artifacts",
        "notes",
    ]
    write_csv(
        "bubble_registry",
        bubble_cols,
        [
            {
                "timestamp_utc": ts,
                "run_id": spec_id,
                "git_hash": "ab13e7d",
                "bubble_radius_m": "1.0",
                "instrument": "interferometer",
                "power_w": "1e6",
                "duration_s": "100",
                "verdict": "requires_speculative_physics",
                "bubble_feasible": "False",
                "dominant_failure_reason": "exotic_energy",
                "allow_speculative": "True",
                "artifacts": f"results/artifacts/{spec_id}/raw/{spec_id}_summary.json",
                "notes": "demo_speculative",
            }
        ],
    )

    # Empty registries for empty-state check
    for empty_name, cols in (
        ("constraints_registry", ["timestamp_utc", "run_id", "artifacts", "notes"]),
        ("batch_registry", ["timestamp_utc", "batch_id", "artifacts", "notes"]),
        ("exotic_tripwire_registry", ["timestamp_utc", "run_id", "tripwire_pass", "artifacts", "notes"]),
        ("breakthrough_ladder_registry", ["timestamp_utc", "run_id", "policy", "artifacts", "notes"]),
        ("ufo_behavior_registry", ["timestamp_utc", "run_id", "policy", "verdict", "artifacts", "notes"]),
    ):
        write_csv(empty_name, cols, [])

    # Job history for reproduction command on pass run
    JOBS.mkdir(parents=True, exist_ok=True)
    job = {
        "job_id": "demo_job_pass",
        "catalog_id": "sweep_ppn",
        "script": "scripts/sweep_ppn_constraints.py",
        "argv": [
            "python",
            str(ROOT / "scripts" / "sweep_ppn_constraints.py"),
            "--gamma-min",
            "0.98",
            "--gamma-max",
            "1.02",
            "--gamma-steps",
            "9",
        ],
        "cli_command": f'python "{ROOT / "scripts" / "sweep_ppn_constraints.py"}" --gamma-min 0.98 --gamma-max 1.02 --gamma-steps 9',
        "cwd": str(ROOT),
        "python": "3.12.0",
        "policy": "strict",
        "speculative": False,
        "git": {"branch": "main", "commit": "ab13e7d", "dirty_label": "clean"},
        "status": "PASS",
        "run_id": pass_id,
        "duration_s": 12.5,
        "exit_code": 0,
        "log_tail": "ppn_sweep complete\n",
    }
    (JOBS / "demo_job_pass.json").write_text(json.dumps(job, indent=2), encoding="utf-8")

    print("Seeded:")
    print(f"  PASS       {pass_id}")
    print(f"  FAIL       {fail_id}")
    print(f"  SPECULATIVE {spec_id}")
    print(f"  UNINDEXED  {unindexed_id}")
    print("  EMPTY      constraints_registry, batch_registry, ...")


if __name__ == "__main__":
    main()
