"""Deterministic Gate 0 checks for deflection-first theory runs."""

from __future__ import annotations

import numpy as np

from src.observables.deflection_curve import mean_normalized_curve_difference, tail_median_relative_error

WF_THRESHOLD = 0.25
RES_THRESHOLD = 0.15
KL_THRESHOLD = 0.05


def gate_weak_field(rel_err: np.ndarray, *, tail_k: int = 5, threshold: float = WF_THRESHOLD) -> tuple[bool, float]:
    """Check weak-field tail median error."""
    median_err = tail_median_relative_error(rel_err, tail_k=tail_k)
    return bool(median_err < threshold), float(median_err)


def gate_resolution(
    alpha_h: np.ndarray,
    alpha_h2: np.ndarray,
    *,
    threshold: float = RES_THRESHOLD,
) -> tuple[bool, float]:
    """Check mean normalized difference between h and h/2 curves."""
    diff = mean_normalized_curve_difference(alpha_h, alpha_h2)
    return bool(diff < threshold), float(diff)


def gate_known_limit(
    alpha_limit: np.ndarray,
    alpha_gr: np.ndarray,
    *,
    threshold: float = KL_THRESHOLD,
) -> tuple[bool, float]:
    """Check known-limit curve agreement with baseline GR curve."""
    diff = mean_normalized_curve_difference(alpha_limit, alpha_gr)
    return bool(diff < threshold), float(diff)


def evaluate_gate0(
    *,
    rel_err_h: np.ndarray,
    alpha_h: np.ndarray,
    alpha_h2: np.ndarray,
    known_limit_mean_rel_err: float | None,
    tail_k: int = 5,
    weak_field_thresh: float = WF_THRESHOLD,
    resolution_thresh: float = RES_THRESHOLD,
    known_limit_thresh: float = KL_THRESHOLD,
) -> dict[str, bool | float | str]:
    """Return full Gate 0 verdict bundle."""
    weak_pass, weak_med = gate_weak_field(rel_err_h, tail_k=tail_k, threshold=weak_field_thresh)
    res_pass, res_diff = gate_resolution(alpha_h, alpha_h2, threshold=resolution_thresh)

    if known_limit_mean_rel_err is None:
        known_pass = True
        known_val: float | str = "NA"
    else:
        known_pass = bool(known_limit_mean_rel_err < known_limit_thresh)
        known_val = float(known_limit_mean_rel_err)

    gate0 = bool(weak_pass and res_pass and known_pass)
    return {
        "gate0_weak_field_pass": weak_pass,
        "weak_field_med_rel_err": float(weak_med),
        "gate0_resolution_pass": res_pass,
        "resolution_mean_curve_diff": float(res_diff),
        "gate0_known_limit_pass": known_pass,
        "known_limit_mean_rel_err": known_val,
        "gate0_pass": gate0,
    }

