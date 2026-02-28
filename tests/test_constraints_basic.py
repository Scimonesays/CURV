from __future__ import annotations

from pathlib import Path
import tempfile

import numpy as np

from src.constraints import evaluate_constraints, run_alpha_lambda_grid, run_constraints_evaluation


def _tmp_outdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="newgr_constraints_tests_"))


def test_phase4b_gr_anchor_like_point_passes():
    _table, summary = evaluate_constraints(gamma=1.0, alpha=0.0, lambda_au=1.0)
    assert summary["all_pass"] is True
    assert summary["max_residual_rel"] <= 1.0e-12


def test_phase4b_large_deviation_fails():
    _table, summary = evaluate_constraints(gamma=1.20, alpha=0.20, lambda_au=0.10)
    assert summary["all_pass"] is False
    assert summary["max_residual_rel"] > 0.05


def test_phase4b_writes_expected_artifacts():
    outdir = _tmp_outdir()
    summary_eval = run_constraints_evaluation(output_dir=outdir, gamma=1.0, alpha=0.0, lambda_au=1.0)
    summary_grid = run_alpha_lambda_grid(
        output_dir=outdir,
        gamma=1.0,
        alpha_values=np.linspace(-0.05, 0.05, 11),
        lambda_values=np.geomspace(0.05, 2.0, 8),
    )
    assert summary_eval["all_pass"] is True
    assert summary_grid["n_points"] == 88
    assert (outdir / "phase4b_constraints.csv").exists()
    assert (outdir / "phase4b_constraints_summary.json").exists()
    assert (outdir / "phase4b_yukawa_grid.csv").exists()
    assert (outdir / "phase4b_yukawa_grid_summary.json").exists()
