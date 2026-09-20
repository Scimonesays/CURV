"""Sweep Yukawa deflection parameters and evaluate promotion ladder verdicts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gates_theory import KL_THRESHOLD, RES_THRESHOLD, evaluate_gate0
from src.observables.deflection_curve import compute_deflection_curve, mean_normalized_curve_difference
from src.promotion_eval import evaluate_promotion, tail_verdict_allows_strong
from src.results_registry import (
    RESULTS_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_run_id,
    utc_now_iso,
)
from src.exotic_tripwire import ExoticTripwire, ExoticTripwireEvalConfig
from src.theories.gr_schwarzschild import GRSchwarzschild
from src.theories.gr_yukawa_deviation import GRYukawaDeviation
from src.utils_plot import apply_default_style, save_figure


def _parse_threshold_sequence(raw: str) -> list[float]:
    vals = [float(x.strip()) for x in raw.split(",") if x.strip()]
    if not vals:
        raise ValueError("wf threshold sequence cannot be empty.")
    return vals


def _parse_range_windows(raw: str) -> list[tuple[float, float]]:
    windows: list[tuple[float, float]] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        parts = token.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid window token: {token}")
        lo = float(parts[0].strip())
        hi = float(parts[1].strip())
        if lo <= 0.0 or hi <= 0.0 or hi <= lo:
            raise ValueError(f"Invalid window bounds: {token}")
        windows.append((lo, hi))
    if not windows:
        raise ValueError("range windows cannot be empty.")
    return windows


def _sign_changes(values: np.ndarray, eps: float = 1.0e-14) -> int:
    signs = np.sign(values)
    nz = [int(s) for s in signs if abs(s) > eps]
    if len(nz) < 2:
        return 0
    changes = 0
    for i in range(len(nz) - 1):
        if nz[i] != nz[i + 1]:
            changes += 1
    return changes


def _binom_two_sided_p_value(n: int, k: int) -> float:
    """Exact two-sided p-value for fair-coin binomial sign test."""
    if n <= 0:
        return 1.0
    if k < 0 or k > n:
        raise ValueError("k must satisfy 0 <= k <= n")

    def pmf(i: int) -> float:
        return math.comb(n, i) * (0.5 ** n)

    k_lo = min(k, n - k)
    p_lo = sum(pmf(i) for i in range(0, k_lo + 1))
    p_hi = sum(pmf(i) for i in range(max(k, n - k), n + 1))
    return float(min(1.0, 2.0 * min(p_lo, p_hi)))


def _tail_sign_diagnostics(
    tail: np.ndarray,
    *,
    eps_abs: float,
    eps_rel: float,
    min_tail_significant: int,
    tail_sign_mode: str,
    tail_sign_alpha: float,
) -> dict[str, float | str | bool]:
    """Compute tail anatomy, NA reasons, and sign verdict in deterministic mode."""
    tail_n_total = int(len(tail))
    abs_tail = np.abs(tail)
    tail_med_abs = float(np.median(abs_tail)) if tail_n_total > 0 else 0.0
    tail_mean_abs = float(np.mean(abs_tail)) if tail_n_total > 0 else 0.0
    threshold = max(float(eps_abs), float(eps_rel) * tail_med_abs)
    significant = np.array([x for x in tail if abs(float(x)) > threshold], dtype=float)
    tail_n_significant = int(len(significant))
    tail_frac_significant = float(tail_n_significant / tail_n_total) if tail_n_total > 0 else 0.0
    tail_n_pos = int(np.sum(significant > 0.0)) if tail_n_significant > 0 else 0
    tail_n_neg = int(np.sum(significant < 0.0)) if tail_n_significant > 0 else 0
    tail_sign_balance: float | str = (
        float((tail_n_pos - tail_n_neg) / tail_n_significant) if tail_n_significant > 0 else "NA"
    )

    na_reason = "NA"
    p_two: float | str = "NA"
    detectable = False
    window_verdict = "na"
    window_sign: float | str = "NA"

    if tail_n_total == 0:
        na_reason = "no_tail_points"
    elif tail_n_significant == 0:
        na_reason = "no_significant_tail_points"
    elif tail_n_significant < int(min_tail_significant):
        na_reason = "insufficient_significant_tail_points"
    else:
        if str(tail_sign_mode) == "none":
            detectable = True
        elif str(tail_sign_mode) == "binomial":
            k = max(tail_n_pos, tail_n_neg)
            p_two = _binom_two_sided_p_value(tail_n_significant, k)
            detectable = bool(float(p_two) < float(tail_sign_alpha))
        else:
            raise ValueError(f"Unsupported tail_sign_mode: {tail_sign_mode}")
        if detectable:
            window_verdict = "pass"
            window_sign = 1.0 if tail_n_pos >= tail_n_neg else -1.0
        else:
            na_reason = "sign_bias_not_detectable"

    sign_changes_sig = 0
    if tail_n_significant >= 2:
        sig_signs = np.sign(significant)
        sign_changes_sig = int(np.sum(sig_signs[:-1] != sig_signs[1:]))

    return {
        "tail_n_total": float(tail_n_total),
        "tail_eps_abs": float(eps_abs),
        "tail_eps_rel": float(eps_rel),
        "tail_threshold": float(threshold),
        "tail_n_significant": float(tail_n_significant),
        "tail_frac_significant": float(tail_frac_significant),
        "tail_med_abs_residual": float(tail_med_abs),
        "tail_mean_abs_residual": float(tail_mean_abs),
        "tail_n_pos": float(tail_n_pos),
        "tail_n_neg": float(tail_n_neg),
        "tail_sign_balance": tail_sign_balance,
        "tail_sign_p_two": p_two,
        "tail_sign_alpha": float(tail_sign_alpha),
        "tail_sign_detectable": bool(detectable),
        "tail_sign_na_reason": str(na_reason),
        "tail_sign_window_verdict": str(window_verdict),
        "tail_sign_window_sign": window_sign,
        "tail_sign_changes_sig": float(sign_changes_sig),
    }


def _compute_window_baseline(*, window: tuple[float, float], n_points: int, h: float, max_steps: int) -> float:
    """
    Compute known-limit agreement metric for the Yukawa family.

    In this plugin, alpha_y=0 must recover GR weak-field behavior.
    """
    theory_limit = GRYukawaDeviation(alpha_y=0.0, lambda_y_over_m=50.0)
    theory_gr = GRSchwarzschild(mass=1.0)
    setup_h = {"h": float(h), "max_steps": int(max_steps)}
    _, alpha_limit, _, _ = compute_deflection_curve(
        theory_limit,
        bmin_over_m=window[0],
        bmax_over_m=window[1],
        n_points=n_points,
        setup=setup_h,
    )
    _, alpha_gr, _, _ = compute_deflection_curve(
        theory_gr,
        bmin_over_m=window[0],
        bmax_over_m=window[1],
        n_points=n_points,
        setup=setup_h,
    )
    return mean_normalized_curve_difference(alpha_limit, alpha_gr)


def _compute_numeric_wf_baseline(
    *,
    window: tuple[float, float],
    n_points: int,
    h: float,
    max_steps: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute cached numeric GR baseline for weak-field reference mode."""
    theory_gr = GRSchwarzschild(mass=1.0)
    b, alpha_gr, _, _ = compute_deflection_curve(
        theory_gr,
        bmin_over_m=window[0],
        bmax_over_m=window[1],
        n_points=n_points,
        setup={"h": float(h), "max_steps": int(max_steps)},
    )
    return b, alpha_gr


def _grid_signature(values: np.ndarray) -> str:
    return hashlib.sha1(np.asarray(values, dtype=float).tobytes()).hexdigest()[:16]


def _compute_point_metrics(
    *,
    alpha_y: float,
    lambda_y_over_m: float,
    window: tuple[float, float],
    n_points: int,
    h: float,
    max_steps: int,
    known_limit_mean_rel_err: float,
    tail_eps_abs: float,
    tail_eps_rel: float,
    tail_sign_k: int,
    min_tail_significant: int,
    tail_sign_mode: str,
    tail_sign_alpha: float,
    wf_ref_mode: str,
    wf_eps_denom: float,
    numeric_wf_alpha_ref: np.ndarray | None,
) -> dict[str, Any]:
    setup_h = {"h": float(h), "max_steps": int(max_steps)}
    setup_h2 = {"h": float(h) / 2.0, "max_steps": int(max_steps)}
    theory = GRYukawaDeviation(alpha_y=float(alpha_y), lambda_y_over_m=float(lambda_y_over_m))
    b, alpha_h, alpha_ref, rel_err_h = compute_deflection_curve(
        theory,
        bmin_over_m=window[0],
        bmax_over_m=window[1],
        n_points=n_points,
        setup=setup_h,
        reference_mode=wf_ref_mode,
        reference_alpha=numeric_wf_alpha_ref,
        eps_denom=wf_eps_denom,
    )
    _, alpha_h2, _, _ = compute_deflection_curve(
        theory,
        bmin_over_m=window[0],
        bmax_over_m=window[1],
        n_points=n_points,
        setup=setup_h2,
        reference_mode=wf_ref_mode,
        reference_alpha=numeric_wf_alpha_ref,
        eps_denom=wf_eps_denom,
    )
    residual = alpha_h - alpha_ref
    k = max(1, min(int(tail_sign_k), len(residual)))
    tail = residual[-k:]
    tail_med = float(np.median(tail))
    tail_diag = _tail_sign_diagnostics(
        tail,
        eps_abs=tail_eps_abs,
        eps_rel=tail_eps_rel,
        min_tail_significant=min_tail_significant,
        tail_sign_mode=tail_sign_mode,
        tail_sign_alpha=tail_sign_alpha,
    )
    return {
        "b_over_m": b,
        "alpha_h": alpha_h,
        "alpha_ref": alpha_ref,
        "alpha_h2": alpha_h2,
        "rel_err_h": rel_err_h,
        "known_limit_mean_rel_err": float(known_limit_mean_rel_err),
        "tail_median_residual": tail_med,
        "tail_sign": 0 if abs(tail_med) < 1.0e-15 else (1 if tail_med > 0 else -1),
        "endpoint_ratio": float(max(abs(residual[0]), abs(residual[-1])) / max(float(np.max(np.abs(residual))), 1.0e-15)),
        "curve_med_abs_residual": float(np.median(np.abs(residual))),
        "sign_changes": float(_sign_changes(residual)),
        "tail_sign_status": str(tail_diag["tail_sign_window_verdict"]),
        "tail_sign_changes_sig": float(tail_diag["tail_sign_changes_sig"]),
        "tail_n_significant": float(tail_diag["tail_n_significant"]),
        "tail_anatomy": tail_diag,
    }


def _alpha_lambda_key(alpha_y: float, lambda_y_over_m: float) -> tuple[str, str]:
    return (f"{float(alpha_y):.12g}", f"{float(lambda_y_over_m):.12g}")


def _build_lambda_values(
    lambda_min: float,
    lambda_max: float,
    lambda_steps: int,
    lambda_spacing: str,
) -> np.ndarray:
    if lambda_min <= 0.0 or lambda_max <= 0.0 or lambda_max < lambda_min:
        raise ValueError("lambda min/max must satisfy 0 < lambda_min <= lambda_max.")
    if int(lambda_steps) < 2:
        raise ValueError("lambda_steps must be >= 2.")
    if str(lambda_spacing) == "log":
        return np.geomspace(float(lambda_min), float(lambda_max), int(lambda_steps))
    if str(lambda_spacing) == "linear":
        return np.linspace(float(lambda_min), float(lambda_max), int(lambda_steps))
    raise ValueError(f"Unsupported lambda_spacing: {lambda_spacing}")


def _plot_survivor_heatmap(
    *,
    run_id: str,
    output_path: Path,
    pass_matrix: np.ndarray,
    alpha_values: np.ndarray,
    lambda_values: np.ndarray,
    wf_thresh: float,
    window_label: str,
) -> None:
    apply_default_style()
    fig, ax = plt.subplots(figsize=(7.8, 5.4))
    im = ax.imshow(
        pass_matrix,
        origin="lower",
        aspect="auto",
        extent=[
            float(alpha_values.min()),
            float(alpha_values.max()),
            float(lambda_values.min()),
            float(lambda_values.max()),
        ],
        interpolation="nearest",
        cmap="RdYlGn",
        vmin=0.0,
        vmax=1.0,
    )
    ax.set_yscale("log")
    ax.set_xlabel("alpha_y")
    ax.set_ylabel("lambda_y_over_m")
    ax.set_title(f"Yukawa Sweep Survivors - wf={wf_thresh:.3g} - window={window_label}")
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("gate0 pass (1=yes)")
    save_figure(fig, output_path / f"{run_id}_yukawa_survivor_heatmap.png")


def run_yukawa_sweep(
    *,
    project_root: Path,
    alpha_min: float,
    alpha_max: float,
    alpha_steps: int,
    lambda_min: float,
    lambda_max: float,
    lambda_steps: int,
    lambda_spacing: str,
    wf_thresh_seq: list[float],
    range_windows: list[tuple[float, float]],
    n_points: int,
    h: float,
    max_steps: int = 36_000,
    source_pass_flag: str = "na",
    curvature_pass_flag: str = "na",
    external_alignment_trigger: bool = False,
    min_adjacent_survivors: int = 1,
    tail_eps_abs: float = 1.0e-6,
    tail_eps_rel: float = 0.01,
    tail_sign_k: int = 20,
    min_tail_significant: int = 8,
    tail_sign_mode: str = "binomial",
    tail_sign_alpha: float = 0.05,
    wf_ref_mode: str = "numeric",
    wf_eps_denom: float = 1.0e-15,
    notes: str = "",
    mirror_jsonl: bool = True,
    plots: bool = True,
    use_exotic_tripwire_gate: bool = False,
) -> dict[str, Any]:
    if alpha_max < alpha_min:
        raise ValueError("alpha_max must be >= alpha_min.")
    if int(alpha_steps) < 2:
        raise ValueError("alpha_steps must be >= 2.")
    if str(wf_ref_mode) not in ("analytic", "numeric"):
        raise ValueError(f"Unsupported wf_ref_mode: {wf_ref_mode}")

    timestamp_utc = utc_now_iso()
    run_id = make_run_id(
        model_mode="yukawa_sweep",
        k=f"a{alpha_min:.6g}_{alpha_max:.6g}",
        n=alpha_steps,
        sigma=f"l{lambda_min:.6g}_{lambda_max:.6g}_{lambda_steps}",
        connectivity="NA",
        field_exponent="NA",
        timestamp_utc=timestamp_utc,
    )
    run_dir = project_root / "results" / "artifacts" / run_id
    metrics_dir = run_dir / "metrics"
    raw_dir = run_dir / "raw"
    plots_dir = run_dir / "plots"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    alpha_values = np.linspace(float(alpha_min), float(alpha_max), int(alpha_steps))
    lambda_values = _build_lambda_values(
        lambda_min=float(lambda_min),
        lambda_max=float(lambda_max),
        lambda_steps=int(lambda_steps),
        lambda_spacing=str(lambda_spacing),
    )
    primary_window = range_windows[0]
    primary_tag = f"{primary_window[0]:.6g}:{primary_window[1]:.6g}"
    schedule_desc = sorted({float(x) for x in wf_thresh_seq}, reverse=True)
    candidate_sched = schedule_desc[:2]
    strong_sched = schedule_desc[2:3]
    strictest_key = f"{schedule_desc[-1]:.6g}"

    all_rows: list[list[float]] = []
    survivors: list[list[float | str]] = []
    survivors_by_thresh: dict[str, int] = {f"{x:.6g}": 0 for x in wf_thresh_seq}
    survivors_by_thresh_window: dict[str, dict[str, int]] = {
        f"{x:.6g}": {f"{w[0]:.6g}:{w[1]:.6g}": 0 for w in range_windows} for x in wf_thresh_seq
    }
    best_params_by_thresh: dict[str, dict[str, float | str]] = {f"{x:.6g}": {"alpha_y": "NA", "lambda_y_over_m": "NA"} for x in wf_thresh_seq}
    best_score_by_thresh: dict[str, float] = {f"{x:.6g}": float("inf") for x in wf_thresh_seq}
    records: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    base_metrics: dict[tuple[str, str, str], dict[str, Any]] = {}
    known_limit_by_window: dict[str, float] = {}
    wf_numeric_ref_by_window: dict[str, np.ndarray] = {}
    wf_ref_baseline: dict[str, dict[str, Any]] = {}
    failure_reason_counts: dict[str, int] = {}
    exotic_point_rows: list[dict[str, Any]] = []

    best_param_key: tuple[str, str] | None = None
    best_score = float("inf")

    for window in range_windows:
        window_tag = f"{window[0]:.6g}:{window[1]:.6g}"
        known_limit_by_window[window_tag] = _compute_window_baseline(
            window=window,
            n_points=n_points,
            h=h,
            max_steps=int(max_steps),
        )
        if str(wf_ref_mode) == "numeric":
            b_ref, alpha_gr_ref = _compute_numeric_wf_baseline(
                window=window,
                n_points=n_points,
                h=h,
                max_steps=int(max_steps),
            )
            wf_numeric_ref_by_window[window_tag] = alpha_gr_ref
            wf_ref_baseline[window_tag] = {
                "theory": "gr_schwarzschild",
                "h": float(h),
                "max_steps": int(max_steps),
                "n_points": int(n_points),
                "range_window": [float(window[0]), float(window[1])],
                "grid_signature": _grid_signature(b_ref),
            }

        for lam in lambda_values:
            for alpha_y in alpha_values:
                alpha_key, lambda_key = _alpha_lambda_key(alpha_y, lam)
                base_metrics[(window_tag, alpha_key, lambda_key)] = _compute_point_metrics(
                    alpha_y=float(alpha_y),
                    lambda_y_over_m=float(lam),
                    window=window,
                    n_points=int(n_points),
                    h=float(h),
                    max_steps=int(max_steps),
                    known_limit_mean_rel_err=float(known_limit_by_window[window_tag]),
                    tail_eps_abs=float(tail_eps_abs),
                    tail_eps_rel=float(tail_eps_rel),
                    tail_sign_k=int(tail_sign_k),
                    min_tail_significant=int(min_tail_significant),
                    tail_sign_mode=str(tail_sign_mode),
                    tail_sign_alpha=float(tail_sign_alpha),
                    wf_ref_mode=str(wf_ref_mode),
                    wf_eps_denom=float(wf_eps_denom),
                    numeric_wf_alpha_ref=wf_numeric_ref_by_window.get(window_tag),
                )

    for wf_thresh in wf_thresh_seq:
        wf_key = f"{wf_thresh:.6g}"
        for window in range_windows:
            window_tag = f"{window[0]:.6g}:{window[1]:.6g}"
            for lam in lambda_values:
                for alpha_y in alpha_values:
                    alpha_key, lambda_key = _alpha_lambda_key(alpha_y, lam)
                    m = base_metrics[(window_tag, alpha_key, lambda_key)]
                    gate = evaluate_gate0(
                        rel_err_h=m["rel_err_h"],
                        alpha_h=m["alpha_h"],
                        alpha_h2=m["alpha_h2"],
                        known_limit_mean_rel_err=m["known_limit_mean_rel_err"],
                        tail_k=5,
                        weak_field_thresh=float(wf_thresh),
                        resolution_thresh=RES_THRESHOLD,
                        known_limit_thresh=KL_THRESHOLD,
                    )
                    pass_flag = 1.0 if bool(gate["gate0_pass"]) else 0.0
                    exotic = ExoticTripwire.evaluate_from_curves(
                        b_over_m=np.asarray(m["b_over_m"], dtype=float),
                        alpha_model=np.asarray(m["alpha_h"], dtype=float),
                        alpha_ref=np.asarray(m["alpha_ref"], dtype=float),
                        config=ExoticTripwireEvalConfig(b_window=(float(window[0]), float(window[1]))),
                    )
                    key = (wf_key, window_tag, alpha_key, lambda_key)
                    records[key] = {
                        "wf_key": wf_key,
                        "window": window_tag,
                        "alpha_y": float(alpha_y),
                        "lambda_y_over_m": float(lam),
                        "gate": gate,
                        "tail_median_residual": m["tail_median_residual"],
                        "tail_sign": m["tail_sign"],
                        "endpoint_ratio": m["endpoint_ratio"],
                        "curve_med_abs_residual": m["curve_med_abs_residual"],
                        "sign_changes": m["sign_changes"],
                        "tail_sign_status": m["tail_sign_status"],
                        "tail_sign_changes_sig": m["tail_sign_changes_sig"],
                        "tail_n_significant": m["tail_n_significant"],
                        "tail_anatomy": m["tail_anatomy"],
                        "exotic_tripwire": exotic,
                        "pass_flag": pass_flag,
                    }
                    exotic_point_rows.append(
                        {
                            "wf_key": wf_key,
                            "window": window_tag,
                            "alpha_y": float(alpha_y),
                            "lambda_y_over_m": float(lam),
                            **exotic,
                        }
                    )
                    all_rows.append(
                        [
                            float(wf_thresh),
                            float(window[0]),
                            float(window[1]),
                            float(alpha_y),
                            float(lam),
                            float(gate["weak_field_med_rel_err"]),
                            float(gate["resolution_mean_curve_diff"]),
                            float(gate["known_limit_mean_rel_err"]),
                            float(m["tail_median_residual"]),
                            float(m["endpoint_ratio"]),
                            float(m["sign_changes"]),
                            float(m["tail_sign_changes_sig"]),
                            float(m["tail_n_significant"]),
                            1.0 if str(m["tail_sign_status"]) == "pass" else 0.0,
                            1.0 if bool(m["tail_anatomy"]["tail_sign_detectable"]) else 0.0,
                            -1.0
                            if str(m["tail_anatomy"]["tail_sign_balance"]) == "NA"
                            else float(m["tail_anatomy"]["tail_sign_balance"]),
                            -1.0
                            if str(m["tail_anatomy"]["tail_sign_p_two"]) == "NA"
                            else float(m["tail_anatomy"]["tail_sign_p_two"]),
                            1.0 if bool(gate["gate0_weak_field_pass"]) else 0.0,
                            1.0 if bool(gate["gate0_resolution_pass"]) else 0.0,
                            1.0 if bool(gate["gate0_known_limit_pass"]) else 0.0,
                            pass_flag,
                            float(exotic.get("exoticity_score", float("nan"))),
                            1.0 if bool(exotic.get("wec_tripwire", False)) else 0.0,
                            1.0 if bool(exotic.get("nec_tripwire", False)) else 0.0,
                            1.0 if bool(exotic.get("scaling_tripwire", False)) else 0.0,
                            float(exotic.get("scaling_power_p", float("nan"))),
                        ]
                    )
                    if not bool(gate["gate0_weak_field_pass"]):
                        failure_reason_counts["gate0_fail_weak_field"] = failure_reason_counts.get("gate0_fail_weak_field", 0) + 1
                    if not bool(gate["gate0_resolution_pass"]):
                        failure_reason_counts["gate0_fail_resolution"] = failure_reason_counts.get("gate0_fail_resolution", 0) + 1
                    if not bool(gate["gate0_known_limit_pass"]):
                        failure_reason_counts["gate0_fail_known_limit"] = failure_reason_counts.get("gate0_fail_known_limit", 0) + 1
                    tail_na_reason = str(m["tail_anatomy"]["tail_sign_na_reason"])
                    failure_reason_counts[f"tail_sign_na:{tail_na_reason}"] = failure_reason_counts.get(
                        f"tail_sign_na:{tail_na_reason}", 0
                    ) + 1

                    if pass_flag >= 0.5:
                        survivors_by_thresh[wf_key] += 1
                        survivors_by_thresh_window[wf_key][window_tag] += 1
                        survivors.append(
                            [
                                wf_key,
                                window_tag,
                                float(alpha_y),
                                float(lam),
                                float(gate["weak_field_med_rel_err"]),
                                float(gate["resolution_mean_curve_diff"]),
                                float(gate["known_limit_mean_rel_err"]),
                                float(m["tail_median_residual"]),
                            ]
                        )
                        if (
                            window_tag == primary_tag
                            and float(gate["weak_field_med_rel_err"]) < best_score_by_thresh[wf_key]
                        ):
                            best_score_by_thresh[wf_key] = float(gate["weak_field_med_rel_err"])
                            best_params_by_thresh[wf_key] = {
                                "alpha_y": float(alpha_y),
                                "lambda_y_over_m": float(lam),
                            }
                        if (
                            wf_key == strictest_key
                            and window_tag == primary_tag
                            and float(gate["weak_field_med_rel_err"]) < best_score
                        ):
                            best_score = float(gate["weak_field_med_rel_err"])
                            best_param_key = (alpha_key, lambda_key)

    table = np.array(all_rows, dtype=float)
    np.savetxt(
        metrics_dir / f"{run_id}_yukawa_sweep_results.csv",
        table,
        delimiter=",",
        header=(
            "wf_thresh,bmin_over_m,bmax_over_m,alpha_y,lambda_y_over_m,weak_field_med_rel_err,resolution_mean_curve_diff,"
            "known_limit_mean_rel_err,tail_median_residual,endpoint_ratio,sign_changes,"
            "tail_sign_changes_sig,tail_n_significant,tail_sign_consistent,"
            "tail_sign_detectable,tail_sign_balance,tail_sign_p_two,"
            "weak_field_pass,resolution_pass,known_limit_pass,gate0_pass,"
            "exoticity_score,wec_tripwire,nec_tripwire,scaling_tripwire,scaling_power_p"
        ),
        comments="",
    )
    survivors_arr = np.array(survivors, dtype=object) if survivors else np.empty((0, 8), dtype=object)
    np.savetxt(
        metrics_dir / f"{run_id}_yukawa_survivors.csv",
        survivors_arr,
        delimiter=",",
        fmt="%s",
        header=(
            "wf_thresh,window,alpha_y,lambda_y_over_m,weak_field_med_rel_err,resolution_mean_curve_diff,"
            "known_limit_mean_rel_err,tail_median_residual"
        ),
        comments="",
    )

    if plots:
        strict_val = float(strictest_key)
        pass_matrix = np.zeros((len(lambda_values), len(alpha_values)), dtype=float)
        for i, lam in enumerate(lambda_values):
            for j, alpha_y in enumerate(alpha_values):
                alpha_key, lambda_key = _alpha_lambda_key(alpha_y, lam)
                rec = records[(f"{strict_val:.6g}", primary_tag, alpha_key, lambda_key)]
                pass_matrix[i, j] = 1.0 if rec["pass_flag"] >= 0.5 else 0.0
        _plot_survivor_heatmap(
            run_id=run_id,
            output_path=plots_dir,
            pass_matrix=pass_matrix,
            alpha_values=alpha_values,
            lambda_values=lambda_values,
            wf_thresh=float(strictest_key),
            window_label=primary_tag,
        )

    if best_param_key is None:
        for lam in lambda_values:
            for alpha_y in alpha_values:
                alpha_key, lambda_key = _alpha_lambda_key(alpha_y, lam)
                key = (strictest_key, primary_tag, alpha_key, lambda_key)
                if key in records and records[key]["pass_flag"] >= 0.5:
                    best_param_key = (alpha_key, lambda_key)
                    break
            if best_param_key is not None:
                break

    candidate_checks: dict[str, bool] = {}
    if best_param_key is None:
        for t in candidate_sched:
            candidate_checks[f"pass_wf_{t:.6g}_primary"] = False
        candidate_checks["residual_not_oscillatory"] = False
    else:
        for t in candidate_sched:
            tk = f"{t:.6g}"
            key = (tk, primary_tag, best_param_key[0], best_param_key[1])
            candidate_checks[f"pass_wf_{tk}_primary"] = bool(key in records and records[key]["pass_flag"] >= 0.5)
        ref_tk = f"{candidate_sched[-1]:.6g}" if candidate_sched else strictest_key
        ref_key = (ref_tk, primary_tag, best_param_key[0], best_param_key[1])
        candidate_checks["residual_not_oscillatory"] = bool(
            ref_key in records and records[ref_key]["sign_changes"] <= 1.0
        )

    ref_tk = f"{candidate_sched[-1]:.6g}" if candidate_sched else strictest_key
    tight_key = f"{strong_sched[0]:.6g}" if strong_sched else strictest_key
    robust_window_count = 0
    tail_sign_verdict = "na"
    tail_sign_na_reason = "no_best_params"
    tail_sig_counts = (0, 0)
    tail_sign_p_two_min: float | str = "NA"
    tail_sign_balance_summary = "NA"
    tail_anatomy_by_window: dict[str, Any] = {}
    adjacent_survivors = 0
    perturb_tail_std = float("inf")

    if best_param_key is not None:
        tight_records = [
            records[(tight_key, f"{w[0]:.6g}:{w[1]:.6g}", best_param_key[0], best_param_key[1])]
            for w in range_windows
            if (tight_key, f"{w[0]:.6g}:{w[1]:.6g}", best_param_key[0], best_param_key[1]) in records
            and records[(tight_key, f"{w[0]:.6g}:{w[1]:.6g}", best_param_key[0], best_param_key[1])]["pass_flag"] >= 0.5
        ]
        tail_anatomy_by_window = {str(r["window"]): dict(r["tail_anatomy"]) for r in tight_records}
        detectable = [
            (str(r["window"]), float(r["tail_anatomy"]["tail_sign_window_sign"]))
            for r in tight_records
            if bool(r["tail_anatomy"]["tail_sign_detectable"])
        ]
        if len(detectable) >= 2:
            first_sign = detectable[0][1]
            same = all(abs(s - first_sign) < 1.0e-12 for _, s in detectable[1:])
            if same:
                tail_sign_verdict = "pass"
                tail_sign_na_reason = "NA"
            else:
                tail_sign_verdict = "fail"
                tail_sign_na_reason = "detectable_sign_mismatch_across_windows"
        else:
            reasons = [str(r["tail_anatomy"]["tail_sign_na_reason"]) for r in tight_records]
            reasons = [r for r in reasons if r != "NA"]
            tail_sign_na_reason = reasons[0] if len(set(reasons)) == 1 and reasons else "insufficient_detectable_windows"
        sig_total = int(sum(int(r["tail_anatomy"]["tail_n_significant"]) for r in tight_records))
        total_points = int(sum(int(r["tail_anatomy"]["tail_n_total"]) for r in tight_records))
        tail_sig_counts = (sig_total, total_points)
        p_vals = [
            float(r["tail_anatomy"]["tail_sign_p_two"])
            for r in tight_records
            if str(r["tail_anatomy"]["tail_sign_p_two"]) != "NA"
        ]
        tail_sign_p_two_min = min(p_vals) if p_vals else "NA"
        balances = [
            float(r["tail_anatomy"]["tail_sign_balance"])
            for r in tight_records
            if str(r["tail_anatomy"]["tail_sign_balance"]) != "NA"
        ]
        tail_sign_balance_summary = "NA" if not balances else float(np.mean(np.array(balances, dtype=float)))
        robust_window_count = len(tight_records)

        # Knife-edge check around best alpha at fixed lambda in strictest primary window.
        alpha_float = np.array([float(x) for x in alpha_values], dtype=float)
        best_alpha = float(best_param_key[0])
        best_lambda_key = best_param_key[1]
        idx = int(np.argmin(np.abs(alpha_float - best_alpha)))
        neighbor_ids = [i for i in [idx - 1, idx, idx + 1] if 0 <= i < len(alpha_float)]
        neighbor_tails = []
        for i in neighbor_ids:
            akey, _ = _alpha_lambda_key(alpha_float[i], float(best_lambda_key))
            key = (tight_key, primary_tag, akey, best_lambda_key)
            if key in records:
                if records[key]["pass_flag"] >= 0.5:
                    adjacent_survivors += 1
                neighbor_tails.append(float(records[key]["tail_median_residual"]))
        perturb_tail_std = float(np.std(np.array(neighbor_tails, dtype=float))) if neighbor_tails else float("inf")

    strong_key = f"{strong_sched[0]:.6g}" if strong_sched else strictest_key
    strong_primary_key = (
        (strong_key, primary_tag, best_param_key[0], best_param_key[1]) if best_param_key is not None else None
    )
    ref_primary_key = ((ref_tk, primary_tag, best_param_key[0], best_param_key[1]) if best_param_key is not None else None)
    strong_checks = {
        f"pass_wf_{strong_key}_primary": bool(
            strong_primary_key is not None and strong_primary_key in records and records[strong_primary_key]["pass_flag"] >= 0.5
        ),
        "range_robust_two_windows": bool(robust_window_count >= 2),
        "tail_sign_not_failed": bool(tail_verdict_allows_strong(tail_sign_verdict)),
        "endpoint_not_dominant": bool(
            ref_primary_key is not None and ref_primary_key in records and records[ref_primary_key]["endpoint_ratio"] < 0.95
        ),
        "low_perturbation_variance": bool(perturb_tail_std <= 1.0e-3),
    }
    exotic_reference = {"status": "FAILED", "tripwire_pass": False}
    if best_param_key is not None and (strictest_key, primary_tag, best_param_key[0], best_param_key[1]) in records:
        exotic_reference = dict(records[(strictest_key, primary_tag, best_param_key[0], best_param_key[1])]["exotic_tripwire"])
    if bool(use_exotic_tripwire_gate):
        strong_checks["exotic_tripwire_gate_pass"] = bool(
            str(exotic_reference.get("status", "FAILED")) == "OK" and bool(exotic_reference.get("tripwire_pass", False))
        )

    def _flag_pass(flag: str) -> bool:
        val = str(flag).lower()
        if val == "pass":
            return True
        if val == "fail":
            return False
        return True

    investigate_checks = {
        "source_non_absurd_if_applicable": _flag_pass(source_pass_flag),
        "curvature_non_absurd_if_applicable": _flag_pass(curvature_pass_flag),
        "external_alignment_trigger": bool(external_alignment_trigger),
        "non_knife_edge_region": bool(adjacent_survivors >= int(min_adjacent_survivors)),
    }

    best_params = (
        {"alpha_y": float(best_param_key[0]), "lambda_y_over_m": float(best_param_key[1])}
        if best_param_key is not None
        else {"alpha_y": "NA", "lambda_y_over_m": "NA"}
    )
    promotion = evaluate_promotion(
        candidate_checks=candidate_checks,
        strong_checks=strong_checks,
        investigate_checks=investigate_checks,
        diagnostics={
            "best_params": best_params,
            "primary_window": primary_tag,
            "tail_sign_verdict": tail_sign_verdict,
            "tail_sign_na_reason": tail_sign_na_reason,
            "tail_n_significant_total": int(tail_sig_counts[0]),
            "tail_n_total": int(tail_sig_counts[1]),
            "tail_sign_p_two": tail_sign_p_two_min,
            "tail_sign_alpha": float(tail_sign_alpha),
            "tail_sign_balance": tail_sign_balance_summary,
            "tail_anatomy_by_window": tail_anatomy_by_window,
            "perturbation_tail_std": perturb_tail_std,
            "adjacent_survivors": int(adjacent_survivors),
            "robust_window_count": int(robust_window_count),
            "promo_schedule": {
                "candidate_thresholds": [float(x) for x in candidate_sched],
                "strong_thresholds": [float(x) for x in strong_sched],
            },
            "failure_reason_counts": dict(sorted(failure_reason_counts.items())),
            "wf_ref_mode": str(wf_ref_mode),
            "wf_ref_eps_denom": float(wf_eps_denom),
            "wf_ref_baseline": wf_ref_baseline if str(wf_ref_mode) == "numeric" else "NA",
        },
    )

    exotic_ok = [r for r in exotic_point_rows if str(r.get("status", "FAILED")) == "OK"]
    exotic_failed = [r for r in exotic_point_rows if str(r.get("status", "FAILED")) != "OK"]
    top_exotic = sorted(
        exotic_ok,
        key=lambda row: float(row.get("exoticity_score", float("-inf"))),
        reverse=True,
    )[:10]
    failure_codes: dict[str, int] = {}
    for row_fail in exotic_failed:
        code = str(row_fail.get("failure_code", "unknown"))
        failure_codes[code] = failure_codes.get(code, 0) + 1
    exotic_summary = {
        "status": str(exotic_reference.get("status", "FAILED")),
        "tripwire_pass": bool(exotic_reference.get("tripwire_pass", False)),
        "wec_tripwire": bool(exotic_reference.get("wec_tripwire", False)),
        "nec_tripwire": bool(exotic_reference.get("nec_tripwire", False)),
        "scaling_tripwire": bool(exotic_reference.get("scaling_tripwire", False)),
        "exoticity_score": float(exotic_reference.get("exoticity_score", float("nan"))),
        "rho_proxy_min": float(exotic_reference.get("rho_proxy_min", float("nan"))),
        "nec_proxy_min": float(exotic_reference.get("nec_proxy_min", float("nan"))),
        "scaling_power_p": float(exotic_reference.get("scaling_power_p", float("nan"))),
        "atlas": {
            "tripwire_pass_count": int(sum(1 for r in exotic_ok if bool(r.get("tripwire_pass", False)))),
            "tripwire_fail_count": int(sum(1 for r in exotic_ok if not bool(r.get("tripwire_pass", False)))),
            "failed_eval_count": int(len(exotic_failed)),
            "failure_codes": dict(sorted(failure_codes.items())),
            "top10_most_exotic": [
                {
                    "wf_thresh": str(r["wf_key"]),
                    "window": str(r["window"]),
                    "alpha_y": float(r["alpha_y"]),
                    "lambda_y_over_m": float(r["lambda_y_over_m"]),
                    "exoticity_score": float(r["exoticity_score"]),
                    "tripwire_pass": bool(r["tripwire_pass"]),
                }
                for r in top_exotic
            ],
        },
        "gate_enabled": bool(use_exotic_tripwire_gate),
    }
    atlas_rows: list[list[str | float | int]] = []
    for r in top_exotic:
        atlas_rows.append(
            [
                str(r["wf_key"]),
                str(r["window"]),
                float(r["alpha_y"]),
                float(r["lambda_y_over_m"]),
                str(r["status"]),
                int(1 if bool(r["tripwire_pass"]) else 0),
                float(r.get("exoticity_score", float("nan"))),
                int(1 if bool(r.get("wec_tripwire", False)) else 0),
                int(1 if bool(r.get("nec_tripwire", False)) else 0),
                int(1 if bool(r.get("scaling_tripwire", False)) else 0),
                float(r.get("scaling_power_p", float("nan"))),
                str(r.get("failure_code", "NA")),
            ]
        )
    atlas_path = metrics_dir / f"{run_id}_exotic_tripwire_atlas.csv"
    atlas_arr = np.array(atlas_rows, dtype=object) if atlas_rows else np.empty((0, 12), dtype=object)
    np.savetxt(
        atlas_path,
        atlas_arr,
        delimiter=",",
        fmt="%s",
        header=(
            "wf_thresh,window,alpha_y,lambda_y_over_m,status,tripwire_pass,exoticity_score,wec_tripwire,nec_tripwire,"
            "scaling_tripwire,scaling_power_p,failure_code"
        ),
        comments="",
    )
    promotion["metadata"] = dict(promotion.get("metadata", {}))
    promotion["metadata"]["exotic_tripwire"] = exotic_summary

    summary = {
        "run_id": run_id,
        "wf_thresh_seq": [float(x) for x in wf_thresh_seq],
        "alpha_min": float(alpha_min),
        "alpha_max": float(alpha_max),
        "alpha_steps": int(alpha_steps),
        "lambda_min": float(lambda_min),
        "lambda_max": float(lambda_max),
        "lambda_steps": int(lambda_steps),
        "lambda_spacing": str(lambda_spacing),
        "range_windows": [[float(w[0]), float(w[1])] for w in range_windows],
        "n_points": int(n_points),
        "h": float(h),
        "max_steps": int(max_steps),
        "n_grid_rows": int(len(all_rows)),
        "survivors_by_thresh": survivors_by_thresh,
        "survivors_by_thresh_window": survivors_by_thresh_window,
        "best_params": best_params,
        "best_params_by_thresh": best_params_by_thresh,
        "promotion_level": promotion["promotion_level"],
        "promotion_schedule": {
            "candidate_thresholds": [float(x) for x in candidate_sched],
            "strong_thresholds": [float(x) for x in strong_sched],
        },
        "tail_sign_verdict": tail_sign_verdict,
        "tail_sign_na_reason": tail_sign_na_reason,
        "failure_reason_counts": dict(sorted(failure_reason_counts.items())),
        "wf_ref_mode": str(wf_ref_mode),
        "wf_ref_baseline": wf_ref_baseline if str(wf_ref_mode) == "numeric" else "NA",
        "plots_enabled": bool(plots),
        "exotic_tripwire": exotic_summary,
    }
    (raw_dir / f"{run_id}_yukawa_sweep_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    (raw_dir / f"{run_id}_promotion_eval.json").write_text(
        json.dumps(promotion, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    rel = lambda p: str(p.resolve().relative_to(project_root.resolve()).as_posix())
    artifacts = [
        rel(metrics_dir / f"{run_id}_yukawa_sweep_results.csv"),
        rel(metrics_dir / f"{run_id}_yukawa_survivors.csv"),
        rel(atlas_path),
        rel(raw_dir / f"{run_id}_yukawa_sweep_summary.json"),
        rel(raw_dir / f"{run_id}_promotion_eval.json"),
    ]
    if plots:
        artifacts.append(rel(plots_dir / f"{run_id}_yukawa_survivor_heatmap.png"))

    notes_core = (
        "yukawa_sweep: "
        f"wf_seq={','.join(str(x) for x in wf_thresh_seq)}; "
        f"grid=alpha[{alpha_min},{alpha_max}]x{alpha_steps},lambda[{lambda_min},{lambda_max}]x{lambda_steps}({lambda_spacing}); "
        f"ranges={','.join(f'{w[0]}:{w[1]}' for w in range_windows)}; "
        f"survivors={json.dumps(survivors_by_thresh, sort_keys=True)}; "
        f"best={json.dumps(best_params, sort_keys=True)}; "
        f"promote: level={promotion['promotion_level']}; "
        f"reasons=[{','.join(str(x) for x in promotion['reasons'])}]"
    )
    notes_text = f"{notes_core}; user_notes={notes}" if notes else notes_core

    row = {
        "timestamp_utc": timestamp_utc,
        "run_id": run_id,
        "batch_id": "NA",
        "git_hash": get_git_hash(),
        "model_mode": "yukawa_sweep",
        "k": float(alpha_min),
        "sigma": float(alpha_max),
        "N": int(alpha_steps),
        "connectivity": "NA",
        "field_exponent": "NA",
        "r2_inv": "NA",
        "r2_lin": "NA",
        "delta_r2": "NA",
        "aic_inv": "NA",
        "aic_lin": "NA",
        "superposition_median_rel_error": "NA",
        "resolution_mean_curve_diff": "NA",
        "gateA_scaling_pass": bool(promotion["promotion_level"] in ("strong_candidate", "investigate")),
        "gateA_superposition_pass": bool(survivors_by_thresh[f"{wf_thresh_seq[0]:.6g}"] > 0),
        "gateA_resolution_pass": True,
        "gateA_pass": bool(promotion["promotion_level"] != "none"),
        "artifacts": ";".join(artifacts),
        "notes": notes_text,
    }
    reg_dir = project_root / "results" / "registry"
    append_csv_row(reg_dir / "results_registry.csv", RESULTS_REGISTRY_COLUMNS, row)
    if mirror_jsonl:
        append_jsonl(reg_dir / "results_registry.jsonl", row)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep Yukawa constraints and evaluate promotion level.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path (default: repository root).",
    )
    parser.add_argument("--theory", choices=["gr_yukawa_deviation"], default="gr_yukawa_deviation")
    parser.add_argument("--alpha-min", type=float, default=-0.10)
    parser.add_argument("--alpha-max", type=float, default=0.10)
    parser.add_argument("--alpha-steps", type=int, default=41)
    parser.add_argument("--lambda-min", type=float, default=1.0)
    parser.add_argument("--lambda-max", type=float, default=1000.0)
    parser.add_argument("--lambda-steps", type=int, default=21)
    parser.add_argument("--lambda-spacing", choices=["log", "linear"], default="log")
    parser.add_argument("--wf-thresh-seq", default="0.05,0.03,0.02")
    parser.add_argument("--range-windows", default="50:500,100:1000")
    parser.add_argument("--n-points", type=int, default=320)
    parser.add_argument("--h", type=float, default=0.18)
    parser.add_argument("--max-steps", type=int, default=36000)
    parser.add_argument("--wf-ref-mode", choices=["analytic", "numeric"], default="numeric")
    parser.add_argument("--wf-eps-denom", type=float, default=1.0e-15)
    parser.add_argument("--source-pass-flag", choices=["na", "pass", "fail"], default="na")
    parser.add_argument("--curvature-pass-flag", choices=["na", "pass", "fail"], default="na")
    parser.add_argument("--external-alignment-trigger", action="store_true")
    parser.add_argument("--min-adjacent-survivors", type=int, default=1)
    parser.add_argument("--tail-eps-abs", type=float, default=1.0e-6)
    parser.add_argument("--tail-eps-rel", type=float, default=0.01)
    parser.add_argument("--tail-sign-k", type=int, default=20)
    parser.add_argument("--min-tail-significant", type=int, default=8)
    parser.add_argument("--tail-sign-mode", choices=["binomial", "none"], default="binomial")
    parser.add_argument("--tail-sign-alpha", type=float, default=0.05)
    parser.add_argument("--notes", default="")
    parser.add_argument("--no-jsonl", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument(
        "--use-exotic-tripwire-gate",
        action="store_true",
        help="Use exotic tripwire as an additional promotion gate (default: annotation only).",
    )
    args = parser.parse_args()
    _ = args.theory

    row = run_yukawa_sweep(
        project_root=Path(args.project_root),
        alpha_min=float(args.alpha_min),
        alpha_max=float(args.alpha_max),
        alpha_steps=int(args.alpha_steps),
        lambda_min=float(args.lambda_min),
        lambda_max=float(args.lambda_max),
        lambda_steps=int(args.lambda_steps),
        lambda_spacing=str(args.lambda_spacing),
        wf_thresh_seq=_parse_threshold_sequence(args.wf_thresh_seq),
        range_windows=_parse_range_windows(args.range_windows),
        n_points=int(args.n_points),
        h=float(args.h),
        max_steps=int(args.max_steps),
        wf_ref_mode=str(args.wf_ref_mode),
        wf_eps_denom=float(args.wf_eps_denom),
        source_pass_flag=str(args.source_pass_flag),
        curvature_pass_flag=str(args.curvature_pass_flag),
        external_alignment_trigger=bool(args.external_alignment_trigger),
        min_adjacent_survivors=int(args.min_adjacent_survivors),
        tail_eps_abs=float(args.tail_eps_abs),
        tail_eps_rel=float(args.tail_eps_rel),
        tail_sign_k=int(args.tail_sign_k),
        min_tail_significant=int(args.min_tail_significant),
        tail_sign_mode=str(args.tail_sign_mode),
        tail_sign_alpha=float(args.tail_sign_alpha),
        notes=args.notes,
        mirror_jsonl=not bool(args.no_jsonl),
        plots=not bool(args.no_plots),
        use_exotic_tripwire_gate=bool(args.use_exotic_tripwire_gate),
    )
    print("yukawa_sweep complete")
    print(f"run_id={row['run_id']}")
    print(f"gateA_pass={row['gateA_pass']}")
    print(f"artifacts={row['artifacts']}")


if __name__ == "__main__":
    main()
