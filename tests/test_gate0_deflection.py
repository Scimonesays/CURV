from __future__ import annotations

import numpy as np

from src.gates_theory import evaluate_gate0, gate_resolution


def test_gate0_passes_stable_inputs():
    rel_err = np.array([0.3, 0.25, 0.2, 0.15, 0.12, 0.1, 0.08], dtype=float)
    alpha_h = np.array([0.2, 0.15, 0.12, 0.1, 0.085, 0.075, 0.067], dtype=float)
    alpha_h2 = alpha_h * 0.99
    gate = evaluate_gate0(
        rel_err_h=rel_err,
        alpha_h=alpha_h,
        alpha_h2=alpha_h2,
        known_limit_mean_rel_err=0.02,
        tail_k=5,
    )
    assert gate["gate0_weak_field_pass"] is True
    assert gate["gate0_resolution_pass"] is True
    assert gate["gate0_known_limit_pass"] is True
    assert gate["gate0_pass"] is True


def test_resolution_gate_detects_unstable_curve():
    alpha_h = np.array([0.2, 0.16, 0.13, 0.11, 0.095], dtype=float)
    alpha_h2 = np.array([0.25, 0.22, 0.19, 0.16, 0.14], dtype=float)
    passed, diff = gate_resolution(alpha_h, alpha_h2, threshold=0.15)
    assert passed is False
    assert diff > 0.15

