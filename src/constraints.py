"""Phase 4B: simple physics-deviation constraints (Yukawa + PPN-like)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import OUTPUT_DIR
from .utils_plot import apply_default_style, save_figure

# Canonical anchor values used as compact benchmark constraints.
# These are intentionally minimal "published benchmark" targets, not raw ephemeris datasets.
_OBSERVABLES: tuple[dict[str, Any], ...] = (
    {
        "name": "light_deflection_solar_arcsec",
        "benchmark": 1.75,
        "bound_rel": 0.05,
        "r_scale_au": 0.00465,  # ~1 solar radius in AU
    },
    {
        "name": "perihelion_mercury_arcsec_century",
        "benchmark": 43.0,
        "bound_rel": 0.05,
        "r_scale_au": 0.39,  # Mercury semimajor axis proxy
    },
    {
        "name": "shapiro_delay_microsec",
        "benchmark": 200.0,
        "bound_rel": 0.05,
        "r_scale_au": 1.0,  # order-of-magnitude solar system path proxy
    },
)


def _ppn_ratio(observable_name: str, gamma: float) -> float:
    """Return a compact PPN-like multiplicative correction ratio."""
    if observable_name in ("light_deflection_solar_arcsec", "shapiro_delay_microsec"):
        return 0.5 * (1.0 + float(gamma))
    if observable_name == "perihelion_mercury_arcsec_century":
        # Beta fixed to 1.0 in this compact Phase 4B proxy.
        return (1.0 + 2.0 * float(gamma)) / 3.0
    raise ValueError(f"Unknown observable: {observable_name}")


def _yukawa_ratio(alpha: float, lambda_au: float, r_scale_au: float) -> float:
    """Return a compact Yukawa-like multiplicative correction ratio."""
    lam = max(float(lambda_au), 1.0e-12)
    return 1.0 + float(alpha) * float(np.exp(-float(r_scale_au) / lam))


def evaluate_constraints(
    gamma: float = 1.0,
    alpha: float = 0.0,
    lambda_au: float = 1.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Compute observable predictions, residuals, and pass/fail against benchmark bounds.

    Returns:
        table: ndarray rows [observable_idx, benchmark, predicted, ppn_ratio,
                             yukawa_ratio, total_ratio, residual_rel, bound_rel, pass_flag]
        summary: dict with aggregate pass metrics
    """
    rows: list[list[float]] = []
    n_pass = 0
    for idx, obs in enumerate(_OBSERVABLES):
        name = str(obs["name"])
        benchmark = float(obs["benchmark"])
        bound_rel = float(obs["bound_rel"])
        r_scale_au = float(obs["r_scale_au"])
        ratio_ppn = _ppn_ratio(name, gamma=float(gamma))
        ratio_yukawa = _yukawa_ratio(alpha=float(alpha), lambda_au=float(lambda_au), r_scale_au=r_scale_au)
        ratio_total = ratio_ppn * ratio_yukawa
        predicted = benchmark * ratio_total
        residual_rel = abs(predicted - benchmark) / max(abs(benchmark), 1.0e-12)
        passed = residual_rel <= bound_rel
        if passed:
            n_pass += 1
        rows.append(
            [
                float(idx),
                benchmark,
                predicted,
                ratio_ppn,
                ratio_yukawa,
                ratio_total,
                residual_rel,
                bound_rel,
                1.0 if passed else 0.0,
            ]
        )

    table = np.array(rows, dtype=float)
    summary = {
        "gamma": float(gamma),
        "alpha": float(alpha),
        "lambda_au": float(lambda_au),
        "n_constraints": int(len(_OBSERVABLES)),
        "n_pass": int(n_pass),
        "all_pass": bool(n_pass == len(_OBSERVABLES)),
        "mean_residual_rel": float(np.mean(table[:, 6])),
        "max_residual_rel": float(np.max(table[:, 6])),
    }
    return table, summary


def run_constraints_evaluation(
    output_dir: Path,
    gamma: float = 1.0,
    alpha: float = 0.0,
    lambda_au: float = 1.0,
) -> dict[str, Any]:
    """Run one constrained model evaluation and write Phase 4B artifacts."""
    apply_default_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    table, summary = evaluate_constraints(gamma=gamma, alpha=alpha, lambda_au=lambda_au)

    np.savetxt(
        output_dir / "phase4b_constraints.csv",
        table,
        delimiter=",",
        header=(
            "observable_idx,benchmark,predicted,ratio_ppn,ratio_yukawa,"
            "ratio_total,residual_rel,bound_rel,pass_flag"
        ),
        comments="",
    )
    (output_dir / "phase4b_constraints_observables.json").write_text(
        json.dumps(list(_OBSERVABLES), indent=2, ensure_ascii=True), encoding="utf-8"
    )
    (output_dir / "phase4b_constraints_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = np.arange(len(_OBSERVABLES))
    ax.bar(x - 0.17, table[:, 6], width=0.34, label="residual_rel")
    ax.bar(x + 0.17, table[:, 7], width=0.34, label="bound_rel")
    ax.set_xticks(x)
    ax.set_xticklabels([str(obs["name"]) for obs in _OBSERVABLES], rotation=15, ha="right")
    ax.set_ylabel("relative value")
    ax.set_title("Phase 4B Constraint Residuals vs Bounds")
    ax.legend()
    save_figure(fig, output_dir / "phase4b_constraints.png")
    return summary


def run_alpha_lambda_grid(
    output_dir: Path,
    gamma: float = 1.0,
    alpha_values: np.ndarray | None = None,
    lambda_values: np.ndarray | None = None,
) -> dict[str, Any]:
    """Evaluate an alpha-lambda grid and write a compact exclusion map."""
    apply_default_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    if alpha_values is None:
        alpha_values = np.linspace(-0.20, 0.20, 81)
    if lambda_values is None:
        lambda_values = np.geomspace(1.0e-2, 10.0, 60)

    rows: list[list[float]] = []
    pass_grid = np.zeros((len(lambda_values), len(alpha_values)), dtype=float)
    for i, lam in enumerate(lambda_values):
        for j, alpha in enumerate(alpha_values):
            _, summary = evaluate_constraints(gamma=gamma, alpha=float(alpha), lambda_au=float(lam))
            all_pass = 1.0 if summary["all_pass"] else 0.0
            pass_grid[i, j] = all_pass
            rows.append([float(alpha), float(lam), float(summary["max_residual_rel"]), all_pass])

    table = np.array(rows, dtype=float)
    np.savetxt(
        output_dir / "phase4b_yukawa_grid.csv",
        table,
        delimiter=",",
        header="alpha,lambda_au,max_residual_rel,all_pass",
        comments="",
    )

    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    im = ax.imshow(
        pass_grid,
        origin="lower",
        aspect="auto",
        extent=[float(alpha_values.min()), float(alpha_values.max()), float(lambda_values.min()), float(lambda_values.max())],
        interpolation="nearest",
        cmap="RdYlGn",
        vmin=0.0,
        vmax=1.0,
    )
    ax.set_yscale("log")
    ax.set_xlabel("alpha")
    ax.set_ylabel("lambda (AU)")
    ax.set_title(f"Phase 4B Allowed Region (gamma={gamma:.3f})")
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("all constraints pass (1=yes)")
    save_figure(fig, output_dir / "phase4b_yukawa_exclusion.png")

    excluded_fraction = float(np.mean(1.0 - pass_grid))
    summary = {
        "gamma": float(gamma),
        "alpha_min": float(alpha_values.min()),
        "alpha_max": float(alpha_values.max()),
        "lambda_min_au": float(lambda_values.min()),
        "lambda_max_au": float(lambda_values.max()),
        "n_points": int(pass_grid.size),
        "excluded_fraction": excluded_fraction,
        "allowed_fraction": float(1.0 - excluded_fraction),
    }
    (output_dir / "phase4b_yukawa_grid_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return summary


def main() -> None:
    summary_eval = run_constraints_evaluation(output_dir=OUTPUT_DIR)
    summary_grid = run_alpha_lambda_grid(output_dir=OUTPUT_DIR)
    # Keep a tiny top-level summary as quick status output.
    text = (
        "# Phase 4B quick summary\n\n"
        f"- single-point all_pass: {summary_eval['all_pass']}\n"
        f"- single-point max_residual_rel: {summary_eval['max_residual_rel']:.6f}\n"
        f"- grid excluded_fraction: {summary_grid['excluded_fraction']:.6f}\n"
    )
    (OUTPUT_DIR / "phase4b_summary.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
