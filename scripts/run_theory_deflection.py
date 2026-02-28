"""Run plugin-based deflection sweep with deterministic Gate 0 and registry evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gates_theory import KL_THRESHOLD, RES_THRESHOLD, WF_THRESHOLD, evaluate_gate0
from src.observables.deflection_curve import compute_deflection_curve, mean_normalized_curve_difference
from src.results_registry import (
    RESULTS_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_run_id,
    utc_now_iso,
)
from src.theories.base import theory_stress_energy_summary
from src.theories.gr_ppn_screened_potential import GRPPNScreenedPotential
from src.theories.gr_schwarzschild import GRSchwarzschild
from src.theories.gr_yukawa_deviation import GRYukawaDeviation
from src.utils_plot import apply_default_style, save_figure


def _build_theory(name: str, *, mass: float, alpha_y: float, lambda_y_over_m: float, gamma_ppn: float):
    if name == "gr_schwarzschild":
        return GRSchwarzschild(mass=mass)
    if name == "gr_yukawa_deviation":
        return GRYukawaDeviation(alpha_y=alpha_y, lambda_y_over_m=lambda_y_over_m)
    if name == "gr_ppn_screened_potential":
        return GRPPNScreenedPotential(gamma_ppn=gamma_ppn)
    raise ValueError(f"Unknown theory: {name}")


def _notes_gate0(
    *,
    gate: dict[str, bool | float | str],
    theory_params: dict[str, float],
    tnew_summary: dict[str, Any],
    weak_field_thresh: float,
    resolution_thresh: float,
    known_limit_thresh: float,
    wf_ref_mode: str,
    wf_eps_denom: float,
    extra_notes: str,
) -> str:
    tnew_model = str(tnew_summary.get("tnew_model", "NA"))
    rho_eff_peak = str(tnew_summary.get("rho_eff_peak", "NA"))
    energy_flags = str(tnew_summary.get("energy_condition_flags", "NA"))
    base = (
        f"gate0: weak_field_med_rel_err={gate['weak_field_med_rel_err']}; "
        f"resolution_mean_curve_diff={gate['resolution_mean_curve_diff']}; "
        f"known_limit_mean_rel_err={gate['known_limit_mean_rel_err']}; "
        f"thresholds={{wf:{weak_field_thresh},res:{resolution_thresh},kl:{known_limit_thresh}}}; "
        f"wf_ref={{mode:{wf_ref_mode},eps_denom:{wf_eps_denom}}}; "
        f"theory_params={json.dumps(theory_params, sort_keys=True)}; "
        f"tnew_model={tnew_model}; "
        f"rho_eff_peak={rho_eff_peak}; "
        f"energy_condition_flags={energy_flags}"
    )
    if extra_notes:
        return f"{base}; user_notes={extra_notes}"
    return base


def _plot_curves(
    *,
    b: np.ndarray,
    alpha_h: np.ndarray,
    alpha_h2: np.ndarray,
    alpha_ref: np.ndarray,
    path: Path,
    theory_name: str,
    ref_label: str,
) -> None:
    apply_default_style()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(b, alpha_h, "o-", label="alpha(h)")
    ax.plot(b, alpha_h2, "x--", label="alpha(h/2)")
    ax.plot(b, alpha_ref, "s:", label=ref_label)
    ax.set_xlabel("b / M")
    ax.set_ylabel("alpha (rad)")
    ax.set_title(f"Deflection Curve - {theory_name}")
    ax.legend()
    save_figure(fig, path)


def run_theory_deflection(
    *,
    project_root: Path,
    theory_name: str,
    mass: float = 1.0,
    alpha_y: float = 0.0,
    lambda_y_over_m: float = 50.0,
    gamma_ppn: float = 1.0,
    bmin_over_m: float = 20.0,
    bmax_over_m: float = 200.0,
    n_points: int = 12,
    h: float = 0.5,
    wf_ref_mode: str = "analytic",
    wf_eps_denom: float = 1.0e-15,
    wf_thresh: float = WF_THRESHOLD,
    resolution_thresh: float = RES_THRESHOLD,
    known_limit_thresh: float = KL_THRESHOLD,
    notes: str = "",
    mirror_jsonl: bool = True,
) -> dict[str, Any]:
    if str(wf_ref_mode) not in ("analytic", "numeric"):
        raise ValueError(f"Unsupported wf_ref_mode: {wf_ref_mode}")
    timestamp_utc = utc_now_iso()
    run_id = make_run_id(
        model_mode=theory_name,
        k=(
            alpha_y
            if theory_name == "gr_yukawa_deviation"
            else (gamma_ppn if theory_name == "gr_ppn_screened_potential" else "NA")
        ),
        n=n_points,
        sigma=lambda_y_over_m if theory_name == "gr_yukawa_deviation" else "NA",
        connectivity="NA",
        field_exponent="NA",
        timestamp_utc=timestamp_utc,
    )
    run_dir = project_root / "results" / "artifacts" / run_id
    metrics_dir = run_dir / "metrics"
    plots_dir = run_dir / "plots"
    raw_dir = run_dir / "raw"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    theory = _build_theory(
        theory_name,
        mass=float(mass),
        alpha_y=float(alpha_y),
        lambda_y_over_m=float(lambda_y_over_m),
        gamma_ppn=float(gamma_ppn),
    )

    setup_h = {"h": float(h)}
    setup_h2 = {"h": float(h) / 2.0}
    numeric_wf_ref_meta: dict[str, Any] | None = None
    numeric_wf_ref: np.ndarray | None = None
    if str(wf_ref_mode) == "numeric":
        theory_gr_ref = GRSchwarzschild(mass=float(mass))
        b_ref, alpha_gr_ref, _, _ = compute_deflection_curve(
            theory_gr_ref,
            bmin_over_m=bmin_over_m,
            bmax_over_m=bmax_over_m,
            n_points=n_points,
            setup=setup_h,
        )
        numeric_wf_ref = alpha_gr_ref
        numeric_wf_ref_meta = {
            "theory": "gr_schwarzschild",
            "h": float(h),
            "n_points": int(n_points),
            "range_window": [float(bmin_over_m), float(bmax_over_m)],
            "grid_signature": hashlib.sha1(np.asarray(b_ref, dtype=float).tobytes()).hexdigest()[:16],
            "mode": "numeric",
            "eps_denom": float(wf_eps_denom),
        }
    b, alpha_h, alpha_ref, rel_err_h = compute_deflection_curve(
        theory,
        bmin_over_m=bmin_over_m,
        bmax_over_m=bmax_over_m,
        n_points=n_points,
        setup=setup_h,
        reference_mode=str(wf_ref_mode),
        reference_alpha=numeric_wf_ref,
        eps_denom=float(wf_eps_denom),
    )
    _, alpha_h2, _, _ = compute_deflection_curve(
        theory,
        bmin_over_m=bmin_over_m,
        bmax_over_m=bmax_over_m,
        n_points=n_points,
        setup=setup_h2,
        reference_mode=str(wf_ref_mode),
        reference_alpha=numeric_wf_ref,
        eps_denom=float(wf_eps_denom),
    )

    known_limit_mean_rel_err: float | None = None
    if theory_name == "gr_yukawa_deviation":
        y0_params = theory.known_limit_parameters()
        theory_y0 = GRYukawaDeviation(
            alpha_y=float(y0_params["alpha_y"]),
            lambda_y_over_m=float(y0_params["lambda_y_over_m"]),
        )
        theory_gr = GRSchwarzschild(mass=float(mass))
        _, alpha_y0, _, _ = compute_deflection_curve(
            theory_y0,
            bmin_over_m=bmin_over_m,
            bmax_over_m=bmax_over_m,
            n_points=n_points,
            setup=setup_h,
        )
        _, alpha_gr, _, _ = compute_deflection_curve(
            theory_gr,
            bmin_over_m=bmin_over_m,
            bmax_over_m=bmax_over_m,
            n_points=n_points,
            setup=setup_h,
        )
        known_limit_mean_rel_err = mean_normalized_curve_difference(alpha_y0, alpha_gr)
    if theory_name == "gr_ppn_screened_potential":
        y0_params = theory.known_limit_parameters()
        theory_y0 = GRPPNScreenedPotential(
            gamma_ppn=float(y0_params["gamma_ppn"]),
            alpha_s=float(y0_params["alpha_s"]),
            lambda_s_over_m=float(y0_params["lambda_s_over_m"]),
        )
        theory_gr = GRSchwarzschild(mass=float(mass))
        _, alpha_y0, _, _ = compute_deflection_curve(
            theory_y0,
            bmin_over_m=bmin_over_m,
            bmax_over_m=bmax_over_m,
            n_points=n_points,
            setup=setup_h,
        )
        _, alpha_gr, _, _ = compute_deflection_curve(
            theory_gr,
            bmin_over_m=bmin_over_m,
            bmax_over_m=bmax_over_m,
            n_points=n_points,
            setup=setup_h,
        )
        known_limit_mean_rel_err = mean_normalized_curve_difference(alpha_y0, alpha_gr)

    gate = evaluate_gate0(
        rel_err_h=rel_err_h,
        alpha_h=alpha_h,
        alpha_h2=alpha_h2,
        known_limit_mean_rel_err=known_limit_mean_rel_err,
        tail_k=5,
        weak_field_thresh=float(wf_thresh),
        resolution_thresh=float(resolution_thresh),
        known_limit_thresh=float(known_limit_thresh),
    )

    metrics_table = np.column_stack([b, alpha_h, alpha_h2, alpha_ref, rel_err_h])
    csv_path = metrics_dir / f"{run_id}_deflection_curve.csv"
    np.savetxt(
        csv_path,
        metrics_table,
        delimiter=",",
        header="b_over_m,alpha_numeric_h,alpha_numeric_h2,alpha_reference,relative_error_h",
        comments="",
    )
    plot_path = plots_dir / f"{run_id}_deflection_curve.png"
    _plot_curves(
        b=b,
        alpha_h=alpha_h,
        alpha_h2=alpha_h2,
        alpha_ref=alpha_ref,
        path=plot_path,
        theory_name=theory_name,
        ref_label=("alpha_GR_numeric" if str(wf_ref_mode) == "numeric" else "4M/b"),
    )
    gate_path = raw_dir / f"{run_id}_gate0_summary.json"
    gate_bundle: dict[str, Any] = dict(gate)
    gate_bundle["wf_ref_mode"] = str(wf_ref_mode)
    gate_bundle["wf_ref_eps_denom"] = float(wf_eps_denom)
    if numeric_wf_ref_meta is not None:
        gate_bundle["wf_ref_baseline"] = numeric_wf_ref_meta
    gate_path.write_text(json.dumps(gate_bundle, indent=2, ensure_ascii=True), encoding="utf-8")
    tnew_summary = theory_stress_energy_summary(theory, setup_h)
    tnew_path = raw_dir / f"{run_id}_tnew_summary.json"
    tnew_path.write_text(json.dumps(tnew_summary, indent=2, ensure_ascii=True), encoding="utf-8")
    wf_ref_path: Path | None = None
    if numeric_wf_ref_meta is not None:
        wf_ref_path = raw_dir / f"{run_id}_wf_reference.json"
        wf_ref_path.write_text(json.dumps(numeric_wf_ref_meta, indent=2, ensure_ascii=True), encoding="utf-8")

    rel = lambda p: str(p.resolve().relative_to(project_root.resolve()).as_posix())
    artifacts = [rel(csv_path), rel(plot_path), rel(gate_path), rel(tnew_path)]
    if wf_ref_path is not None:
        artifacts.append(rel(wf_ref_path))

    theory_params = dict(getattr(theory, "parameters", {}))
    note_text = _notes_gate0(
        gate=gate,
        theory_params=theory_params,
        tnew_summary=tnew_summary,
        weak_field_thresh=float(wf_thresh),
        resolution_thresh=float(resolution_thresh),
        known_limit_thresh=float(known_limit_thresh),
        wf_ref_mode=str(wf_ref_mode),
        wf_eps_denom=float(wf_eps_denom),
        extra_notes=notes,
    )
    row = {
        "timestamp_utc": timestamp_utc,
        "run_id": run_id,
        "batch_id": "NA",
        "git_hash": get_git_hash(),
        "model_mode": theory_name,
        "k": (
            float(alpha_y)
            if theory_name == "gr_yukawa_deviation"
            else (float(gamma_ppn) if theory_name == "gr_ppn_screened_potential" else "NA")
        ),
        "sigma": float(lambda_y_over_m) if theory_name == "gr_yukawa_deviation" else "NA",
        "N": int(n_points),
        "connectivity": "NA",
        "field_exponent": "NA",
        "r2_inv": "NA",
        "r2_lin": "NA",
        "delta_r2": "NA",
        "aic_inv": "NA",
        "aic_lin": "NA",
        "superposition_median_rel_error": float(gate["weak_field_med_rel_err"]),
        "resolution_mean_curve_diff": float(gate["resolution_mean_curve_diff"]),
        "gateA_scaling_pass": (
            bool(gate["gate0_known_limit_pass"])
            if theory_name in ("gr_yukawa_deviation", "gr_ppn_screened_potential")
            else "NA"
        ),
        "gateA_superposition_pass": bool(gate["gate0_weak_field_pass"]),
        "gateA_resolution_pass": bool(gate["gate0_resolution_pass"]),
        "gateA_pass": bool(gate["gate0_pass"]),
        "artifacts": ";".join(artifacts),
        "notes": note_text,
    }
    reg_dir = project_root / "results" / "registry"
    append_csv_row(reg_dir / "results_registry.csv", RESULTS_REGISTRY_COLUMNS, row)
    if mirror_jsonl:
        append_jsonl(reg_dir / "results_registry.jsonl", row)

    return {
        "run_id": run_id,
        "theory": theory_name,
        "gate0_pass": bool(gate["gate0_pass"]),
        "artifacts": artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run theory-plugin deflection sweep with Gate 0.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path (default: repository root).",
    )
    parser.add_argument(
        "--theory",
        choices=["gr_schwarzschild", "gr_yukawa_deviation", "gr_ppn_screened_potential"],
        default="gr_schwarzschild",
    )
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--alpha-y", type=float, default=0.0)
    parser.add_argument("--lambda-y-over-m", type=float, default=50.0)
    parser.add_argument("--gamma-ppn", type=float, default=1.0)
    parser.add_argument("--bmin-over-m", type=float, default=20.0)
    parser.add_argument("--bmax-over-m", type=float, default=200.0)
    parser.add_argument("--n-points", type=int, default=12)
    parser.add_argument("--h", type=float, default=0.5)
    parser.add_argument("--wf-ref-mode", choices=["analytic", "numeric"], default="analytic")
    parser.add_argument("--wf-eps-denom", type=float, default=1.0e-15)
    parser.add_argument("--wf-thresh", type=float, default=WF_THRESHOLD)
    parser.add_argument("--resolution-thresh", type=float, default=RES_THRESHOLD)
    parser.add_argument("--known-limit-thresh", type=float, default=KL_THRESHOLD)
    parser.add_argument("--notes", default="")
    parser.add_argument("--no-jsonl", action="store_true")
    args = parser.parse_args()

    out = run_theory_deflection(
        project_root=Path(args.project_root),
        theory_name=args.theory,
        mass=float(args.mass),
        alpha_y=float(args.alpha_y),
        lambda_y_over_m=float(args.lambda_y_over_m),
        gamma_ppn=float(args.gamma_ppn),
        bmin_over_m=float(args.bmin_over_m),
        bmax_over_m=float(args.bmax_over_m),
        n_points=int(args.n_points),
        h=float(args.h),
        wf_ref_mode=str(args.wf_ref_mode),
        wf_eps_denom=float(args.wf_eps_denom),
        wf_thresh=float(args.wf_thresh),
        resolution_thresh=float(args.resolution_thresh),
        known_limit_thresh=float(args.known_limit_thresh),
        notes=args.notes,
        mirror_jsonl=not bool(args.no_jsonl),
    )
    print("theory_deflection_trial complete")
    print(f"run_id={out['run_id']}")
    print(f"theory={out['theory']}")
    print(f"gate0_pass={out['gate0_pass']}")
    print(f"artifacts={';'.join(out['artifacts'])}")


if __name__ == "__main__":
    main()

