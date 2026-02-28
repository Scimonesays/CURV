"""Run minimal Schwarzschild geodesic deflection sweep and append registry evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gr.geodesic import trace_null_ray
from src.results_registry import (
    RESULTS_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_run_id,
    utc_now_iso,
)
from src.utils_plot import apply_default_style, save_figure


def run_deflection_curve(
    *,
    project_root: Path,
    mass: float = 1.0,
    bmin_over_m: float = 20.0,
    bmax_over_m: float = 200.0,
    n_points: int = 12,
    notes: str = "",
    mirror_jsonl: bool = True,
) -> dict[str, str | float]:
    timestamp_utc = utc_now_iso()
    run_id = make_run_id(
        model_mode="schwarzschild_geodesic",
        k="NA",
        n="NA",
        sigma="NA",
        connectivity="NA",
        field_exponent="NA",
        timestamp_utc=timestamp_utc,
    )

    results_root = project_root / "results"
    run_dir = results_root / "artifacts" / run_id
    metrics_dir = run_dir / "metrics"
    plots_dir = run_dir / "plots"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    b_values = np.linspace(float(bmin_over_m), float(bmax_over_m), int(n_points))
    rows = []
    for b_over_m in b_values:
        ray = trace_null_ray(b_over_m=float(b_over_m), mass=float(mass))
        rows.append([ray["b_over_m"], ray["alpha_numeric"], ray["alpha_weakfield"]])
    table = np.array(rows, dtype=float)
    rel_err = np.abs(table[:, 1] - table[:, 2]) / np.maximum(np.abs(table[:, 2]), 1.0e-12)
    mean_rel_err = float(np.mean(rel_err))

    csv_name = f"{run_id}_schwarzschild_deflection_curve.csv"
    csv_path = metrics_dir / csv_name
    np.savetxt(
        csv_path,
        np.column_stack([table, rel_err]),
        delimiter=",",
        header="b_over_m,alpha_numeric,alpha_weakfield,relative_error",
        comments="",
    )

    apply_default_style()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(table[:, 0], table[:, 1], "o-", label="numeric geodesic")
    ax.plot(table[:, 0], table[:, 2], "s--", label="weak-field 4M/b")
    ax.set_xlabel("b / M")
    ax.set_ylabel("alpha (rad)")
    ax.set_title("Schwarzschild Deflection Curve")
    ax.legend()
    plot_name = f"{run_id}_schwarzschild_deflection_curve.png"
    plot_path = plots_dir / plot_name
    save_figure(fig, plot_path)

    artifacts = [
        str(csv_path.resolve().relative_to(project_root.resolve()).as_posix()),
        str(plot_path.resolve().relative_to(project_root.resolve()).as_posix()),
    ]

    registry_row = {
        "timestamp_utc": timestamp_utc,
        "run_id": run_id,
        "batch_id": "NA",
        "git_hash": get_git_hash(),
        "model_mode": "schwarzschild_geodesic",
        "k": "NA",
        "sigma": "NA",
        "N": "NA",
        "connectivity": "NA",
        "field_exponent": "NA",
        "r2_inv": "NA",
        "r2_lin": "NA",
        "delta_r2": "NA",
        "aic_inv": "NA",
        "aic_lin": "NA",
        "superposition_median_rel_error": "NA",
        "resolution_mean_curve_diff": "NA",
        "gateA_scaling_pass": "NA",
        "gateA_superposition_pass": "NA",
        "gateA_resolution_pass": "NA",
        "gateA_pass": "NA",
        "artifacts": ";".join(artifacts),
        "notes": notes
        or f"validation_error_mean_rel={mean_rel_err:.6g};weakfield_target=4M/b;equatorial_finite_diff_christoffel",
    }

    registry_dir = results_root / "registry"
    append_csv_row(registry_dir / "results_registry.csv", RESULTS_REGISTRY_COLUMNS, registry_row)
    if mirror_jsonl:
        append_jsonl(registry_dir / "results_registry.jsonl", registry_row)

    return {
        "run_id": run_id,
        "csv": artifacts[0],
        "plot": artifacts[1],
        "validation_error_mean_rel": mean_rel_err,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Schwarzschild geodesic deflection sweep.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path (default: repository root).",
    )
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--bmin-over-m", type=float, default=20.0)
    parser.add_argument("--bmax-over-m", type=float, default=200.0)
    parser.add_argument("--n-points", type=int, default=12)
    parser.add_argument("--notes", default="")
    parser.add_argument("--no-jsonl", action="store_true")
    args = parser.parse_args()

    out = run_deflection_curve(
        project_root=Path(args.project_root),
        mass=float(args.mass),
        bmin_over_m=float(args.bmin_over_m),
        bmax_over_m=float(args.bmax_over_m),
        n_points=int(args.n_points),
        notes=args.notes,
        mirror_jsonl=not bool(args.no_jsonl),
    )
    print("schwarzschild_geodesic_trial complete")
    print(f"run_id={out['run_id']}")
    print(f"validation_error_mean_rel={out['validation_error_mean_rel']:.6g}")
    print(f"csv={out['csv']}")
    print(f"plot={out['plot']}")


if __name__ == "__main__":
    main()

