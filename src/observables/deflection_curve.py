"""Shared deflection-curve observable helpers."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.theories.base import Theory


def weak_field_reference(b_over_m: np.ndarray) -> np.ndarray:
    """Return weak-field GR baseline alpha ~= 4M/b in M-normalized units."""
    return 4.0 / b_over_m


def compute_deflection_curve(
    theory: Theory,
    *,
    bmin_over_m: float,
    bmax_over_m: float,
    n_points: int,
    setup: dict[str, Any],
    reference_mode: str = "analytic",
    reference_alpha: np.ndarray | None = None,
    eps_denom: float = 1.0e-15,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute b-grid, numeric alpha curve, reference curve, and relative error."""
    b = np.linspace(float(bmin_over_m), float(bmax_over_m), int(n_points))
    alpha_num = np.array([theory.deflection_angle_vs_b(float(x), setup) for x in b], dtype=float)
    if str(reference_mode) == "analytic":
        alpha_ref = weak_field_reference(b)
    elif str(reference_mode) == "numeric":
        if reference_alpha is None:
            raise ValueError("reference_alpha is required when reference_mode='numeric'.")
        alpha_ref = np.asarray(reference_alpha, dtype=float)
        if alpha_ref.shape != alpha_num.shape:
            raise ValueError("reference_alpha shape must match computed alpha curve.")
    else:
        raise ValueError(f"Unsupported reference_mode: {reference_mode}")
    rel_err = np.abs(alpha_num - alpha_ref) / np.maximum(np.abs(alpha_ref), float(eps_denom))
    return b, alpha_num, alpha_ref, rel_err


def tail_median_relative_error(rel_err: np.ndarray, tail_k: int = 5) -> float:
    """Median relative error over largest-b tail."""
    if len(rel_err) < tail_k:
        raise ValueError(f"Need at least {tail_k} points for tail median.")
    return float(np.median(rel_err[-tail_k:]))


def mean_normalized_curve_difference(alpha_a: np.ndarray, alpha_b: np.ndarray) -> float:
    """Mean normalized curve difference between two alpha arrays."""
    denom = np.maximum(np.abs(alpha_b), 1.0e-15)
    return float(np.mean(np.abs(alpha_a - alpha_b) / denom))

