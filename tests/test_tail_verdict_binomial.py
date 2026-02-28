from __future__ import annotations

import numpy as np

from scripts.sweep_ppn_constraints import _tail_sign_diagnostics


def test_tail_verdict_na_no_significant_points():
    tail = np.array([1.0e-9, -5.0e-10, 8.0e-10], dtype=float)
    out = _tail_sign_diagnostics(
        tail,
        eps_abs=1.0e-7,
        eps_rel=0.001,
        min_tail_significant=8,
        tail_sign_mode="binomial",
        tail_sign_alpha=0.05,
    )
    assert out["tail_sign_window_verdict"] == "na"
    assert out["tail_sign_na_reason"] == "no_significant_tail_points"


def test_tail_verdict_na_insufficient_significant_points():
    tail = np.array([1.0e-4, -2.0e-4, 3.0e-4, 4.0e-4], dtype=float)
    out = _tail_sign_diagnostics(
        tail,
        eps_abs=1.0e-7,
        eps_rel=0.001,
        min_tail_significant=8,
        tail_sign_mode="binomial",
        tail_sign_alpha=0.05,
    )
    assert out["tail_sign_window_verdict"] == "na"
    assert out["tail_sign_na_reason"] == "insufficient_significant_tail_points"


def test_tail_verdict_binomial_detectable_bias():
    tail = np.array([1.0] * 18 + [-1.0] * 2, dtype=float)
    out = _tail_sign_diagnostics(
        tail,
        eps_abs=1.0e-9,
        eps_rel=0.0,
        min_tail_significant=8,
        tail_sign_mode="binomial",
        tail_sign_alpha=0.05,
    )
    assert out["tail_sign_detectable"] is True
    assert out["tail_sign_window_verdict"] == "pass"
    assert float(out["tail_sign_p_two"]) < 0.05


def test_tail_verdict_binomial_not_detectable():
    tail = np.array([1.0] * 10 + [-1.0] * 10, dtype=float)
    out = _tail_sign_diagnostics(
        tail,
        eps_abs=1.0e-9,
        eps_rel=0.0,
        min_tail_significant=8,
        tail_sign_mode="binomial",
        tail_sign_alpha=0.05,
    )
    assert out["tail_sign_detectable"] is False
    assert out["tail_sign_window_verdict"] == "na"
    assert out["tail_sign_na_reason"] == "sign_bias_not_detectable"
