"""Strict append-only trial and campaign pipeline for CURV."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from .config import GRAPH_CONNECTIVITY_DEFAULT, GRAPH_N, GRAPH_SMOOTH_SIGMA_FACTOR
from .constraints import run_alpha_lambda_grid, run_constraints_evaluation
from .emergent_graph import run_resolution_robustness, run_superposition_test, run_weak_scaling_fit
from .gates import compute_batch_verdict, compute_resolution_gate, compute_superposition_gate
from .results_registry import (
    BATCH_REGISTRY_COLUMNS,
    CONSTRAINTS_REGISTRY_COLUMNS,
    RESULTS_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_constraints_run_id,
    make_run_id,
    utc_now_iso,
)


def _default_sigma(n: int) -> float:
    return max(float(n) * GRAPH_SMOOTH_SIGMA_FACTOR, 1.0)


def _finalize_artifacts(staging_dir: Path, run_dir: Path, run_id: str) -> list[str]:
    plots_dir = run_dir / "plots"
    metrics_dir = run_dir / "metrics"
    raw_dir = run_dir / "raw"
    plots_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[Path] = []
    for src in sorted(staging_dir.glob("*")):
        if src.suffix.lower() == ".png":
            dst = plots_dir / f"{run_id}_{src.stem}.png"
            shutil.move(str(src), str(dst))
            artifacts.append(dst)
        elif src.suffix.lower() == ".csv":
            dst = metrics_dir / f"{run_id}_{src.stem}.csv"
            shutil.move(str(src), str(dst))
            artifacts.append(dst)
        else:
            dst = raw_dir / f"{run_id}_{src.name}"
            shutil.move(str(src), str(dst))
            artifacts.append(dst)
    return [str(p) for p in artifacts]


def run_trial(
    *,
    project_root: Path,
    model_mode: str = "smooth_gaussian",
    k: float = 1.02,
    sigma: float | None = None,
    n: int = GRAPH_N,
    connectivity: int | None = None,
    field_exponent: float = 2.0,
    batch_id: str | None = None,
    notes: str = "",
    mirror_jsonl: bool = True,
) -> dict[str, Any]:
    """Run one trial and append one immutable per-run registry row."""
    timestamp_utc = utc_now_iso()
    if connectivity is None:
        connectivity = 8 if model_mode == "smooth_gaussian" else GRAPH_CONNECTIVITY_DEFAULT
    sigma_value = _default_sigma(n) if (sigma is None and model_mode == "smooth_gaussian") else sigma
    run_id = make_run_id(
        model_mode=model_mode,
        k=k,
        n=n,
        sigma=sigma_value,
        connectivity=connectivity,
        field_exponent=field_exponent,
        timestamp_utc=timestamp_utc,
    )

    results_root = project_root / "results"
    run_dir = results_root / "artifacts" / run_id
    staging_dir = run_dir / "_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    scaling = run_weak_scaling_fit(
        output_dir=staging_dir,
        n=n,
        k_values=[float(k)],
        mode=model_mode,
        connectivity=connectivity,
        sigma=sigma_value,
    )
    superposition = run_superposition_test(
        output_dir=staging_dir,
        n=n,
        k=float(k),
        mode=model_mode,
        connectivity=connectivity,
        sigma=sigma_value,
    )
    resolution = run_resolution_robustness(
        output_dir=staging_dir,
        n_base=n,
        k=float(k),
        mode=model_mode,
        connectivity=connectivity,
        sigma=sigma_value,
    )
    artifact_abs_paths = _finalize_artifacts(staging_dir=staging_dir, run_dir=run_dir, run_id=run_id)
    if staging_dir.exists():
        staging_dir.rmdir()
    artifact_rel_paths = [Path(p).resolve().relative_to(project_root.resolve()).as_posix() for p in artifact_abs_paths]

    row_scaling = scaling[0, :]
    r2_inv = float(row_scaling[4])
    r2_lin = float(row_scaling[5])
    delta_r2 = float(r2_inv - r2_lin)
    aic_inv = float(row_scaling[7])
    aic_lin = float(row_scaling[8])
    median_rel_error = float(np.median(superposition[:, 7]))
    mean_curve_diff = float(np.mean(resolution[:, 3]))
    gate_super = compute_superposition_gate(median_rel_error)
    gate_resolution = compute_resolution_gate(mean_curve_diff)

    registry_row = {
        "timestamp_utc": timestamp_utc,
        "run_id": run_id,
        "batch_id": batch_id if batch_id else "NA",
        "git_hash": get_git_hash(),
        "model_mode": model_mode,
        "k": float(k),
        "sigma": "NA" if sigma_value is None else float(sigma_value),
        "N": int(n),
        "connectivity": int(connectivity),
        "field_exponent": float(field_exponent),
        "r2_inv": r2_inv,
        "r2_lin": r2_lin,
        "delta_r2": delta_r2,
        "aic_inv": aic_inv,
        "aic_lin": aic_lin,
        "superposition_median_rel_error": median_rel_error,
        "resolution_mean_curve_diff": mean_curve_diff,
        "gateA_scaling_pass": "NA",
        "gateA_superposition_pass": bool(gate_super),
        "gateA_resolution_pass": bool(gate_resolution),
        "gateA_pass": "NA",
        "artifacts": ";".join(artifact_rel_paths),
        "notes": notes or "NA",
    }

    registry_dir = results_root / "registry"
    trial_csv = registry_dir / "results_registry.csv"
    trial_jsonl = registry_dir / "results_registry.jsonl"
    append_csv_row(trial_csv, RESULTS_REGISTRY_COLUMNS, registry_row)
    if mirror_jsonl:
        append_jsonl(trial_jsonl, registry_row)

    return registry_row


def run_phase4b_constraints_trial(
    *,
    project_root: Path,
    gamma: float = 1.0,
    alpha: float = 0.0,
    lambda_au: float = 1.0,
    batch_id: str | None = None,
    notes: str = "",
    mirror_jsonl: bool = True,
) -> dict[str, Any]:
    """Run one Phase 4B constraints trial and append one immutable registry row."""
    timestamp_utc = utc_now_iso()
    run_id = make_constraints_run_id(
        gamma=gamma,
        alpha=alpha,
        lambda_au=lambda_au,
        timestamp_utc=timestamp_utc,
    )

    results_root = project_root / "results"
    run_dir = results_root / "artifacts" / run_id
    staging_dir = run_dir / "_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    summary_eval = run_constraints_evaluation(
        output_dir=staging_dir, gamma=float(gamma), alpha=float(alpha), lambda_au=float(lambda_au)
    )
    summary_grid = run_alpha_lambda_grid(output_dir=staging_dir, gamma=float(gamma))

    artifact_abs_paths = _finalize_artifacts(staging_dir=staging_dir, run_dir=run_dir, run_id=run_id)
    if staging_dir.exists():
        staging_dir.rmdir()
    artifact_rel_paths = [Path(p).resolve().relative_to(project_root.resolve()).as_posix() for p in artifact_abs_paths]

    registry_row = {
        "timestamp_utc": timestamp_utc,
        "run_id": run_id,
        "batch_id": batch_id if batch_id else "NA",
        "git_hash": get_git_hash(),
        "gamma": float(gamma),
        "alpha": float(alpha),
        "lambda_au": float(lambda_au),
        "n_constraints": int(summary_eval["n_constraints"]),
        "n_pass": int(summary_eval["n_pass"]),
        "all_pass": bool(summary_eval["all_pass"]),
        "mean_residual_rel": float(summary_eval["mean_residual_rel"]),
        "max_residual_rel": float(summary_eval["max_residual_rel"]),
        "excluded_fraction": float(summary_grid["excluded_fraction"]),
        "allowed_fraction": float(summary_grid["allowed_fraction"]),
        "artifacts": ";".join(artifact_rel_paths),
        "notes": notes or "NA",
    }

    registry_dir = results_root / "registry"
    constraints_csv = registry_dir / "constraints_registry.csv"
    constraints_jsonl = registry_dir / "constraints_registry.jsonl"
    append_csv_row(constraints_csv, CONSTRAINTS_REGISTRY_COLUMNS, registry_row)
    if mirror_jsonl:
        append_jsonl(constraints_jsonl, registry_row)
    return registry_row


def _parse_weak_k_filter(weak_k_expression: str):
    expr = weak_k_expression.replace(" ", "")
    if expr.startswith("k<="):
        threshold = float(expr.split("<=", maxsplit=1)[1])
        return lambda k: k <= threshold
    if expr.startswith("k<"):
        threshold = float(expr.split("<", maxsplit=1)[1])
        return lambda k: k < threshold
    if expr.startswith("k>="):
        threshold = float(expr.split(">=", maxsplit=1)[1])
        return lambda k: k >= threshold
    if expr.startswith("k>"):
        threshold = float(expr.split(">", maxsplit=1)[1])
        return lambda k: k > threshold
    if expr.startswith("k=="):
        target = float(expr.split("==", maxsplit=1)[1])
        return lambda k: abs(k - target) < 1.0e-12
    raise ValueError(f"Unsupported weak-k definition: {weak_k_expression}")


def finalize_campaign(
    *,
    project_root: Path,
    batch_id: str,
    weak_k_definition: str,
    model_mode: str = "smooth_gaussian",
    artifacts: list[str] | None = None,
    notes: str = "",
    mirror_jsonl: bool = True,
) -> dict[str, Any]:
    """Append one immutable batch verdict row from existing trial rows."""
    trial_csv = project_root / "results" / "registry" / "results_registry.csv"
    if not trial_csv.exists():
        raise FileNotFoundError(f"Missing trial registry: {trial_csv}")

    rows: list[dict[str, Any]] = []
    with trial_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("batch_id") == batch_id:
                rows.append(row)
    if not rows:
        raise ValueError(f"No trial rows found for batch_id={batch_id}")

    weak_k_filter = _parse_weak_k_filter(weak_k_definition)
    verdict = compute_batch_verdict(rows, weak_k_filter=weak_k_filter)
    batch_row = {
        "timestamp_utc": utc_now_iso(),
        "batch_id": batch_id,
        "git_hash": get_git_hash(),
        "model_mode": model_mode,
        "weak_k_definition": weak_k_definition,
        "run_ids": verdict["run_ids"],
        "n_runs": verdict["n_runs"],
        "n_weak_k_runs": verdict["n_weak_k_runs"],
        "scaling_min_delta_r2": verdict["scaling_min_delta_r2"],
        "scaling_n_pass": verdict["scaling_n_pass"],
        "gateA_scaling_pass": verdict["gateA_scaling_pass"],
        "gateA_superposition_pass_rate": verdict["gateA_superposition_pass_rate"],
        "gateA_resolution_pass_rate": verdict["gateA_resolution_pass_rate"],
        "gateA_pass": verdict["gateA_pass"],
        "artifacts": ";".join(artifacts or []),
        "notes": notes or "NA",
    }

    registry_dir = project_root / "results" / "registry"
    batch_csv = registry_dir / "batch_registry.csv"
    batch_jsonl = registry_dir / "batch_registry.jsonl"
    append_csv_row(batch_csv, BATCH_REGISTRY_COLUMNS, batch_row)
    if mirror_jsonl:
        append_jsonl(batch_jsonl, batch_row)
    return batch_row


def _build_phase4b_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a registry-backed Phase 4B constraints trial."
    )
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path (default: repository root).",
    )
    parser.add_argument("--gamma", type=float, default=1.0, help="PPN-like gamma parameter.")
    parser.add_argument("--alpha", type=float, default=0.0, help="Yukawa-like alpha parameter.")
    parser.add_argument(
        "--lambda-au",
        type=float,
        default=1.0,
        help="Yukawa-like lambda scale in astronomical units.",
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="Optional batch identifier for campaign grouping.",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Optional notes string written to constraints registry.",
    )
    parser.add_argument(
        "--no-jsonl",
        action="store_true",
        help="Disable JSONL mirror append for this run.",
    )
    return parser


def _main_phase4b_cli() -> None:
    parser = _build_phase4b_cli_parser()
    args = parser.parse_args()
    row = run_phase4b_constraints_trial(
        project_root=Path(args.project_root),
        gamma=float(args.gamma),
        alpha=float(args.alpha),
        lambda_au=float(args.lambda_au),
        batch_id=args.batch_id,
        notes=args.notes,
        mirror_jsonl=not bool(args.no_jsonl),
    )
    print("phase4b_constraints_trial complete")
    print(f"run_id={row['run_id']}")
    print(f"all_pass={row['all_pass']}")
    print(f"max_residual_rel={row['max_residual_rel']:.6g}")
    print(f"constraints_pass={row['n_pass']}/{row['n_constraints']}")
    print(f"artifacts={row['artifacts']}")


if __name__ == "__main__":
    _main_phase4b_cli()

