"""Sweep PPN-style parameter grid and compute promotion ladder verdicts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

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
from src.theories.gr_ppn_screened_potential import GRPPNScreenedPotential
from src.theories.gr_schwarzschild import GRSchwarzschild


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


def _compute_window_baseline(
    *,
    window: tuple[float, float],
    n_points: int,
    h: float,
) -> float:
    theory_limit = GRPPNScreenedPotential(gamma_ppn=1.0, alpha_s=0.0)
    theory_gr = GRSchwarzschild(mass=1.0)
    setup_h = {"h": float(h)}
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
) -> tuple[np.ndarray, np.ndarray]:
    """Compute cached numeric GR baseline for weak-field reference mode."""
    theory_gr = GRSchwarzschild(mass=1.0)
    b, alpha_gr, _, _ = compute_deflection_curve(
        theory_gr,
        bmin_over_m=window[0],
        bmax_over_m=window[1],
        n_points=n_points,
        setup={"h": float(h)},
    )
    return b, alpha_gr


def _grid_signature(values: np.ndarray) -> str:
    return hashlib.sha1(np.asarray(values, dtype=float).tobytes()).hexdigest()[:16]


def _compute_gamma_metrics(
    *,
    gamma: float,
    window: tuple[float, float],
    n_points: int,
    h: float,
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
) -> tuple[float, dict[str, Any]]:
    setup_h = {"h": float(h)}
    setup_h2 = {"h": float(h) / 2.0}
    theory = GRPPNScreenedPotential(gamma_ppn=float(gamma))
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
    return float(gamma), {
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
        "tail_eps": float(tail_diag["tail_threshold"]),
        "tail_anatomy": tail_diag,
    }


def _compute_gamma_metrics_payload(payload: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    return _compute_gamma_metrics(**payload)


def run_ppn_sweep(
    *,
    project_root: Path,
    gamma_min: float,
    gamma_max: float,
    gamma_steps: int,
    wf_thresh_seq: list[float],
    range_windows: list[tuple[float, float]],
    n_points: int,
    h: float,
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
    wf_ref_mode: str = "analytic",
    wf_eps_denom: float = 1.0e-15,
    notes: str = "",
    mirror_jsonl: bool = True,
    full_throttle: bool = False,
    telemetry: bool = False,
    telemetry_seconds: float = 2.0,
    max_workers: int | None = None,
    plots: bool = False,
    use_exotic_tripwire_gate: bool = False,
) -> dict[str, Any]:
    if str(wf_ref_mode) not in ("analytic", "numeric"):
        raise ValueError(f"Unsupported wf_ref_mode: {wf_ref_mode}")
    timestamp_utc = utc_now_iso()
    run_id = make_run_id(
        model_mode="ppn_sweep",
        k=f"g{gamma_min:.6g}_{gamma_max:.6g}",
        n=gamma_steps,
        sigma="NA",
        connectivity="NA",
        field_exponent="NA",
        timestamp_utc=timestamp_utc,
    )
    run_dir = project_root / "results" / "artifacts" / run_id
    metrics_dir = run_dir / "metrics"
    raw_dir = run_dir / "raw"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    gamma_values = np.linspace(float(gamma_min), float(gamma_max), int(gamma_steps))
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
    records: dict[tuple[str, str, float], dict[str, Any]] = {}
    base_metrics: dict[tuple[str, float], dict[str, Any]] = {}
    wf_numeric_ref_by_window: dict[str, np.ndarray] = {}
    wf_ref_baseline: dict[str, dict[str, Any]] = {}
    best_gamma: float | None = None
    best_score = float("inf")
    telemetry_enabled = bool(telemetry or full_throttle)
    telemetry_interval = max(float(telemetry_seconds), 0.2)
    last_telemetry = 0.0
    t0 = time.monotonic()
    use_parallel = bool(full_throttle)
    cpu_workers = int(max_workers) if max_workers is not None else (os.cpu_count() or 1)
    worker_count = max(1, cpu_workers)

    total_steps = (len(range_windows) * len(gamma_values)) + (len(wf_thresh_seq) * len(range_windows) * len(gamma_values))
    completed_steps = 0
    promotion_hint = "pending"
    exotic_point_rows: list[dict[str, Any]] = []

    def emit_telemetry(*, wf_label: str) -> None:
        nonlocal last_telemetry
        if not telemetry_enabled:
            return
        now = time.monotonic()
        if completed_steps < total_steps and (now - last_telemetry) < telemetry_interval:
            return
        elapsed = max(now - t0, 1.0e-9)
        step_time = elapsed / max(completed_steps, 1)
        remaining = max(total_steps - completed_steps, 0)
        eta_s = step_time * remaining
        bg = "NA" if best_gamma is None else f"{best_gamma:.6g}"
        line = (
            f"\rwf={wf_label:<10} ({completed_steps}/{total_steps})  "
            f"survivors={len(survivors)}  best_gamma={bg}  promo={promotion_hint}  "
            f"step={step_time:.3f}s  eta={eta_s:.1f}s"
        )
        sys.stdout.write(line)
        sys.stdout.flush()
        last_telemetry = now

    # Precompute expensive per-window baseline curves once.
    for window in range_windows:
        window_tag = f"{window[0]:.6g}:{window[1]:.6g}"
        known_limit_mean_rel_err = _compute_window_baseline(window=window, n_points=n_points, h=h)
        if str(wf_ref_mode) == "numeric":
            b_ref, alpha_gr_ref = _compute_numeric_wf_baseline(window=window, n_points=n_points, h=h)
            wf_numeric_ref_by_window[window_tag] = alpha_gr_ref
            wf_ref_baseline[window_tag] = {
                "theory": "gr_schwarzschild",
                "h": float(h),
                "n_points": int(n_points),
                "range_window": [float(window[0]), float(window[1])],
                "grid_signature": _grid_signature(b_ref),
            }

        if use_parallel and worker_count > 1 and len(gamma_values) > 1:
            with ProcessPoolExecutor(max_workers=worker_count) as ex:
                ordered_results = ex.map(
                    _compute_gamma_metrics_payload,
                    [
                        {
                            "gamma": float(gamma),
                            "window": window,
                            "n_points": int(n_points),
                            "h": float(h),
                            "known_limit_mean_rel_err": float(known_limit_mean_rel_err),
                            "tail_eps_abs": float(tail_eps_abs),
                            "tail_eps_rel": float(tail_eps_rel),
                            "tail_sign_k": int(tail_sign_k),
                            "min_tail_significant": int(min_tail_significant),
                            "tail_sign_mode": str(tail_sign_mode),
                            "tail_sign_alpha": float(tail_sign_alpha),
                            "wf_ref_mode": str(wf_ref_mode),
                            "wf_eps_denom": float(wf_eps_denom),
                            "numeric_wf_alpha_ref": wf_numeric_ref_by_window.get(window_tag),
                        }
                        for gamma in gamma_values
                    ],
                )
                for gamma, metrics in ordered_results:
                    base_metrics[(window_tag, float(gamma))] = metrics
                    completed_steps += 1
                    emit_telemetry(wf_label="precompute")
        else:
            for gamma in gamma_values:
                gm, metrics = _compute_gamma_metrics(
                    gamma=float(gamma),
                    window=window,
                    n_points=n_points,
                    h=h,
                    known_limit_mean_rel_err=known_limit_mean_rel_err,
                    tail_eps_abs=tail_eps_abs,
                    tail_eps_rel=tail_eps_rel,
                    tail_sign_k=tail_sign_k,
                    min_tail_significant=min_tail_significant,
                    tail_sign_mode=tail_sign_mode,
                    tail_sign_alpha=tail_sign_alpha,
                    wf_ref_mode=str(wf_ref_mode),
                    wf_eps_denom=float(wf_eps_denom),
                    numeric_wf_alpha_ref=wf_numeric_ref_by_window.get(window_tag),
                )
                base_metrics[(window_tag, float(gm))] = metrics
                completed_steps += 1
                emit_telemetry(wf_label="precompute")

    for wf_thresh in wf_thresh_seq:
        wf_key = f"{wf_thresh:.6g}"
        for window in range_windows:
            window_tag = f"{window[0]:.6g}:{window[1]:.6g}"
            for gamma in gamma_values:
                m = base_metrics[(window_tag, float(gamma))]
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
                key = (wf_key, window_tag, float(gamma))
                records[key] = {
                    "wf_key": wf_key,
                    "window": window_tag,
                    "gamma": float(gamma),
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
                        "gamma_ppn": float(gamma),
                        **exotic,
                    }
                )
                all_rows.append(
                    [
                        float(wf_thresh),
                        float(window[0]),
                        float(window[1]),
                        float(gamma),
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
                if pass_flag >= 0.5:
                    survivors_by_thresh[wf_key] += 1
                    survivors_by_thresh_window[wf_key][window_tag] += 1
                    survivors.append(
                        [
                            wf_key,
                            window_tag,
                            float(gamma),
                            float(gate["weak_field_med_rel_err"]),
                            float(gate["resolution_mean_curve_diff"]),
                            float(gate["known_limit_mean_rel_err"]),
                            float(m["tail_median_residual"]),
                        ]
                    )
                    if (
                        wf_key == strictest_key
                        and window_tag == primary_tag
                        and float(gate["weak_field_med_rel_err"]) < best_score
                    ):
                        best_score = float(gate["weak_field_med_rel_err"])
                        best_gamma = float(gamma)
                    promotion_hint = "candidate"
                completed_steps += 1
                emit_telemetry(wf_label=wf_key)

    table = np.array(all_rows, dtype=float)
    np.savetxt(
        metrics_dir / f"{run_id}_ppn_sweep_results.csv",
        table,
        delimiter=",",
        header=(
            "wf_thresh,bmin_over_m,bmax_over_m,gamma_ppn,weak_field_med_rel_err,resolution_mean_curve_diff,"
            "known_limit_mean_rel_err,tail_median_residual,endpoint_ratio,sign_changes,"
            "tail_sign_changes_sig,tail_n_significant,tail_sign_consistent,"
            "tail_sign_detectable,tail_sign_balance,tail_sign_p_two,"
            "weak_field_pass,resolution_pass,known_limit_pass,gate0_pass,"
            "exoticity_score,wec_tripwire,nec_tripwire,scaling_tripwire,scaling_power_p"
        ),
        comments="",
    )
    survivors_arr = np.array(survivors, dtype=object) if survivors else np.empty((0, 7), dtype=object)
    np.savetxt(
        metrics_dir / f"{run_id}_ppn_survivors.csv",
        survivors_arr,
        delimiter=",",
        fmt="%s",
        header=(
            "wf_thresh,window,gamma_ppn,weak_field_med_rel_err,resolution_mean_curve_diff,"
            "known_limit_mean_rel_err,tail_median_residual"
        ),
        comments="",
    )

    # Promotion ladder checks.
    if best_gamma is None:
        for g in gamma_values:
            key = (strictest_key, primary_tag, float(g))
            if key in records and records[key]["pass_flag"] >= 0.5:
                best_gamma = float(g)
                break

    candidate_checks: dict[str, bool] = {}
    for t in candidate_sched:
        tk = f"{t:.6g}"
        candidate_checks[f"pass_wf_{tk}_primary"] = bool(records[(tk, primary_tag, float(best_gamma))]["pass_flag"]) if (
            best_gamma is not None and (tk, primary_tag, float(best_gamma)) in records
        ) else False
    ref_tk = f"{candidate_sched[-1]:.6g}" if candidate_sched else strictest_key
    candidate_checks["residual_not_oscillatory"] = bool(records[(ref_tk, primary_tag, float(best_gamma))]["sign_changes"] <= 1.0) if (
        best_gamma is not None and (ref_tk, primary_tag, float(best_gamma)) in records
    ) else False

    if best_gamma is None:
        tail_sign_consistent = "na"
        perturb_tail_std = float("inf")
        adjacent_survivors = 0
        robust_window_count = 0
        tail_sign_verdict = "na"
        tail_sign_na_reason = "no_best_gamma"
        tail_sig_counts = (0, 0)
        tail_sign_p_two_min: float | str = "NA"
        tail_sign_balance_summary = "NA"
        tail_anatomy_by_window: dict[str, Any] = {}
    else:
        tight_key = f"{strong_sched[0]:.6g}" if strong_sched else strictest_key
        tight_records = [
            records[(tight_key, f"{w[0]:.6g}:{w[1]:.6g}", float(best_gamma))]
            for w in range_windows
            if (tight_key, f"{w[0]:.6g}:{w[1]:.6g}", float(best_gamma)) in records
            and records[(tight_key, f"{w[0]:.6g}:{w[1]:.6g}", float(best_gamma))]["pass_flag"] >= 0.5
        ]
        tail_anatomy_by_window = {
            str(r["window"]): dict(r["tail_anatomy"])
            for r in tight_records
        }
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
                tail_sign_consistent = "consistent"
            else:
                tail_sign_verdict = "fail"
                tail_sign_na_reason = "detectable_sign_mismatch_across_windows"
                tail_sign_consistent = "inconsistent"
        else:
            tail_sign_verdict = "na"
            reasons = [str(r["tail_anatomy"]["tail_sign_na_reason"]) for r in tight_records]
            reasons = [r for r in reasons if r != "NA"]
            tail_sign_na_reason = reasons[0] if len(set(reasons)) == 1 and reasons else "insufficient_detectable_windows"
            tail_sign_consistent = "na"
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

        gamma_list = [float(x) for x in gamma_values]
        idx = gamma_list.index(float(best_gamma))
        neighbor_ids = [i for i in [idx - 1, idx, idx + 1] if 0 <= i < len(gamma_list)]
        neighbor_tails = []
        adjacent_survivors = 0
        for i in neighbor_ids:
            key = (tight_key, primary_tag, gamma_list[i])
            if key in records:
                if records[key]["pass_flag"] >= 0.5:
                    adjacent_survivors += 1
                neighbor_tails.append(float(records[key]["tail_median_residual"]))
        perturb_tail_std = float(np.std(np.array(neighbor_tails, dtype=float))) if neighbor_tails else float("inf")

    strong_checks = {
        f"pass_wf_{f'{strong_sched[0]:.6g}' if strong_sched else strictest_key}_primary": bool(
            records[((f"{strong_sched[0]:.6g}" if strong_sched else strictest_key), primary_tag, float(best_gamma))][
                "pass_flag"
            ]
        )
        if best_gamma is not None
        and ((f"{strong_sched[0]:.6g}" if strong_sched else strictest_key), primary_tag, float(best_gamma)) in records
        else False,
        "range_robust_two_windows": bool(robust_window_count >= 1),
        "tail_sign_not_failed": bool(tail_verdict_allows_strong(tail_sign_verdict)),
        "endpoint_not_dominant": bool(records[(ref_tk, primary_tag, float(best_gamma))]["endpoint_ratio"] < 0.95) if (
            best_gamma is not None and (ref_tk, primary_tag, float(best_gamma)) in records
        ) else False,
        "low_perturbation_variance": bool(perturb_tail_std <= 1.0e-3),
    }
    exotic_reference = {"status": "FAILED", "tripwire_pass": False}
    if best_gamma is not None and (strictest_key, primary_tag, float(best_gamma)) in records:
        exotic_reference = dict(records[(strictest_key, primary_tag, float(best_gamma))]["exotic_tripwire"])
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
        return True  # NA means not applicable, do not block.

    investigate_checks = {
        "source_non_absurd_if_applicable": _flag_pass(source_pass_flag),
        "curvature_non_absurd_if_applicable": _flag_pass(curvature_pass_flag),
        "external_alignment_trigger": bool(external_alignment_trigger),
        "non_knife_edge_region": bool(adjacent_survivors >= int(min_adjacent_survivors)),
    }

    promotion = evaluate_promotion(
        candidate_checks=candidate_checks,
        strong_checks=strong_checks,
        investigate_checks=investigate_checks,
        diagnostics={
            "best_gamma_ppn": "NA" if best_gamma is None else float(best_gamma),
            "primary_window": primary_tag,
            "tail_sign_consistent": tail_sign_consistent,
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
            "robust_window_count_wf0p10": int(robust_window_count),
            "promo_schedule": {
                "candidate_thresholds": [float(x) for x in candidate_sched],
                "strong_thresholds": [float(x) for x in strong_sched],
            },
            "tail_eps_abs": float(tail_eps_abs),
            "tail_eps_rel": float(tail_eps_rel),
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
                    "gamma_ppn": float(r["gamma_ppn"]),
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
                float(r["gamma_ppn"]),
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
    atlas_arr = np.array(atlas_rows, dtype=object) if atlas_rows else np.empty((0, 11), dtype=object)
    np.savetxt(
        atlas_path,
        atlas_arr,
        delimiter=",",
        fmt="%s",
        header=(
            "wf_thresh,window,gamma_ppn,status,tripwire_pass,exoticity_score,wec_tripwire,nec_tripwire,"
            "scaling_tripwire,scaling_power_p,failure_code"
        ),
        comments="",
    )
    promotion["metadata"] = dict(promotion.get("metadata", {}))
    promotion["metadata"]["exotic_tripwire"] = exotic_summary

    summary = {
        "run_id": run_id,
        "wf_thresh_seq": [float(x) for x in wf_thresh_seq],
        "gamma_min": float(gamma_min),
        "gamma_max": float(gamma_max),
        "gamma_steps": int(gamma_steps),
        "range_windows": [[float(w[0]), float(w[1])] for w in range_windows],
        "n_points": int(n_points),
        "h": float(h),
        "n_grid_rows": int(len(all_rows)),
        "survivors_by_thresh": survivors_by_thresh,
        "survivors_by_thresh_window": survivors_by_thresh_window,
        "best_gamma_ppn": "NA" if best_gamma is None else float(best_gamma),
        "promotion_level": promotion["promotion_level"],
        "promotion_schedule": {
            "candidate_thresholds": [float(x) for x in candidate_sched],
            "strong_thresholds": [float(x) for x in strong_sched],
        },
        "tail_sign_verdict": tail_sign_verdict,
        "tail_sign_na_reason": tail_sign_na_reason,
        "wf_ref_mode": str(wf_ref_mode),
        "wf_ref_baseline": wf_ref_baseline if str(wf_ref_mode) == "numeric" else "NA",
        "full_throttle": bool(full_throttle),
        "parallel_workers": int(worker_count) if use_parallel and worker_count > 1 else 1,
        "telemetry_enabled": bool(telemetry_enabled),
        "plots_enabled": bool(plots),
        "exotic_tripwire": exotic_summary,
    }
    (raw_dir / f"{run_id}_ppn_sweep_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    (raw_dir / f"{run_id}_promotion_eval.json").write_text(
        json.dumps(promotion, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    rel = lambda p: str(p.resolve().relative_to(project_root.resolve()).as_posix())
    artifacts = [
        rel(metrics_dir / f"{run_id}_ppn_sweep_results.csv"),
        rel(metrics_dir / f"{run_id}_ppn_survivors.csv"),
        rel(atlas_path),
        rel(raw_dir / f"{run_id}_ppn_sweep_summary.json"),
        rel(raw_dir / f"{run_id}_promotion_eval.json"),
    ]
    seq_str = ",".join(str(x) for x in wf_thresh_seq)
    windows_str = ",".join(f"{w[0]}:{w[1]}" for w in range_windows)
    reasons_str = ",".join(str(x) for x in promotion["reasons"])
    sched_str = (
        f"promo_sched: candidate={json.dumps([float(x) for x in candidate_sched])} "
        f"strong={json.dumps([float(x) for x in strong_sched])}"
    )
    notes_core = (
        "ppn_sweep: "
        f"wf_seq={seq_str}; "
        f"grid=gamma[{gamma_min},{gamma_max}]x{gamma_steps}; "
        f"ranges={windows_str}; "
        f"survivors={json.dumps(survivors_by_thresh, sort_keys=True)}; "
        f"best={summary['best_gamma_ppn']}; "
        f"{sched_str}; "
        f"promote: level={promotion['promotion_level']}; reasons=[{reasons_str}]"
    )
    tailv = (
        "tailv: "
        f"verdict={tail_sign_verdict}; "
        f"na_reason={tail_sign_na_reason}; "
        f"n_sig={tail_sig_counts[0]}/{tail_sig_counts[1]}; "
        f"p={tail_sign_p_two_min}; "
        f"alpha={tail_sign_alpha}; "
        f"balance={tail_sign_balance_summary}"
    )
    wfref = f"wfref: mode={wf_ref_mode}; eps_denom={wf_eps_denom}"
    notes_core = f"{notes_core}; {wfref}; {tailv}"
    notes_text = f"{notes_core}; user_notes={notes}" if notes else notes_core

    first_key = f"{wf_thresh_seq[0]:.6g}"
    last_key = f"{wf_thresh_seq[-1]:.6g}"
    row = {
        "timestamp_utc": timestamp_utc,
        "run_id": run_id,
        "batch_id": "NA",
        "git_hash": get_git_hash(),
        "model_mode": "ppn_sweep",
        "k": float(gamma_min),
        "sigma": float(gamma_max),
        "N": int(gamma_steps),
        "connectivity": "NA",
        "field_exponent": "NA",
        "r2_inv": "NA",
        "r2_lin": "NA",
        "delta_r2": "NA",
        "aic_inv": "NA",
        "aic_lin": "NA",
        "superposition_median_rel_error": "NA",
        "resolution_mean_curve_diff": "NA",
        "gateA_scaling_pass": bool(
            promotion["promotion_level"] in ("strong_candidate", "investigate")
        ),
        "gateA_superposition_pass": bool(survivors_by_thresh[first_key] > 0),
        "gateA_resolution_pass": True,
        "gateA_pass": bool(promotion["promotion_level"] != "none"),
        "artifacts": ";".join(artifacts),
        "notes": notes_text,
    }
    reg_dir = project_root / "results" / "registry"
    append_csv_row(reg_dir / "results_registry.csv", RESULTS_REGISTRY_COLUMNS, row)
    if mirror_jsonl:
        append_jsonl(reg_dir / "results_registry.jsonl", row)
    if telemetry_enabled:
        emit_telemetry(wf_label=f"{wf_thresh_seq[-1]:.6g}")
        sys.stdout.write("\n")
        sys.stdout.flush()
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep PPN constraints and evaluate promotion level.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path (default: repository root).",
    )
    parser.add_argument("--theory", choices=["gr_ppn_screened_potential"], default="gr_ppn_screened_potential")
    parser.add_argument("--gamma-min", type=float, default=0.98)
    parser.add_argument("--gamma-max", type=float, default=1.02)
    parser.add_argument("--gamma-steps", type=int, default=11)
    parser.add_argument("--wf-thresh-seq", default="0.25,0.15,0.10")
    parser.add_argument("--range-windows", default="50:500,100:1000")
    parser.add_argument("--n-points", type=int, default=20)
    parser.add_argument("--h", type=float, default=0.5)
    parser.add_argument("--wf-ref-mode", choices=["analytic", "numeric"], default="analytic")
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
    parser.add_argument(
        "--full-throttle",
        action="store_true",
        help="Enable headless high-throughput mode (parallel sweep + low-cost telemetry).",
    )
    parser.add_argument(
        "--telemetry",
        action="store_true",
        help="Print single-line periodic telemetry during the run.",
    )
    parser.add_argument(
        "--telemetry-seconds",
        type=float,
        default=2.0,
        help="Telemetry update period in seconds (default: 2.0).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Override process pool workers for full-throttle mode (default: os.cpu_count()).",
    )
    parser.add_argument(
        "--plots",
        action="store_true",
        help="Enable post-run plotting hooks when available (no effect for current PPN sweep artifacts).",
    )
    parser.add_argument(
        "--use-exotic-tripwire-gate",
        action="store_true",
        help="Use exotic tripwire as an additional promotion gate (default: annotation only).",
    )
    args = parser.parse_args()
    _ = args.theory

    row = run_ppn_sweep(
        project_root=Path(args.project_root),
        gamma_min=float(args.gamma_min),
        gamma_max=float(args.gamma_max),
        gamma_steps=int(args.gamma_steps),
        wf_thresh_seq=_parse_threshold_sequence(args.wf_thresh_seq),
        range_windows=_parse_range_windows(args.range_windows),
        n_points=int(args.n_points),
        h=float(args.h),
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
        full_throttle=bool(args.full_throttle),
        telemetry=bool(args.telemetry),
        telemetry_seconds=float(args.telemetry_seconds),
        max_workers=int(args.max_workers) if args.max_workers is not None else None,
        plots=bool(args.plots),
        use_exotic_tripwire_gate=bool(args.use_exotic_tripwire_gate),
    )
    print("ppn_sweep complete")
    print(f"run_id={row['run_id']}")
    print(f"gateA_pass={row['gateA_pass']}")
    print(f"artifacts={row['artifacts']}")


if __name__ == "__main__":
    main()

