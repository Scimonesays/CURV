from __future__ import annotations

from pathlib import Path
import tempfile

import numpy as np

from src.emergent_graph import (
    run_resolution_robustness,
    run_superposition_test,
    run_weak_scaling_fit,
)


def _tmp_outdir() -> Path:
    # Keep tests isolated from user-visible outputs.
    return Path(tempfile.mkdtemp(prefix="newgr_graph_tests_"))


def test_scaling_inverse_fit_beats_linear_and_constant():
    outdir = _tmp_outdir()
    table = run_weak_scaling_fit(
        output_dir=outdir,
        n=41,
        radius=6.0,
        ray_count=17,
        k_values=[1.01, 1.02, 1.05],
        mode="smooth_gaussian",
        connectivity=8,
    )
    row = table[np.isclose(table[:, 0], 1.02)][0]
    delta = float(row[4] - row[5])
    assert delta >= 0.03, f"Expected inverse-fit margin >= 0.03, got {delta:.6f}"


def test_superposition_median_relative_error_is_bounded():
    outdir = _tmp_outdir()
    table = run_superposition_test(output_dir=outdir, n=41, radius=6.0, ray_count=17, k=1.02)
    b = table[:, 0]
    rel_error = table[:, 7]
    far_mask = b >= 4.0
    median_rel_error = float(np.median(rel_error[far_mask]))
    assert median_rel_error < 0.25


def test_resolution_curves_are_robust():
    outdir = _tmp_outdir()
    table = run_resolution_robustness(
        output_dir=outdir, n_base=41, radius=6.0, ray_count=17, k=1.02
    )
    mean_abs_diff = float(np.mean(table[:, 3]))
    assert mean_abs_diff < 0.15

