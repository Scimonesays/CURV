from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import scripts.sweep_ppn_constraints as sweep_ppn_constraints
from src.observables.deflection_curve import compute_deflection_curve
from src.theories.gr_ppn_screened_potential import GRPPNScreenedPotential
from src.theories.gr_schwarzschild import GRSchwarzschild


def test_numeric_wf_reference_discriminates_gamma_shift():
    gr = GRSchwarzschild()
    b, alpha_gr, _, _ = compute_deflection_curve(
        gr, bmin_over_m=50.0, bmax_over_m=500.0, n_points=24, setup={"h": 0.18}
    )
    ppn_1 = GRPPNScreenedPotential(gamma_ppn=1.0)
    _, _, _, rel_g1 = compute_deflection_curve(
        ppn_1,
        bmin_over_m=50.0,
        bmax_over_m=500.0,
        n_points=24,
        setup={"h": 0.18},
        reference_mode="numeric",
        reference_alpha=alpha_gr,
    )
    ppn_off = GRPPNScreenedPotential(gamma_ppn=1.05)
    _, _, _, rel_g105 = compute_deflection_curve(
        ppn_off,
        bmin_over_m=50.0,
        bmax_over_m=500.0,
        n_points=24,
        setup={"h": 0.18},
        reference_mode="numeric",
        reference_alpha=alpha_gr,
    )
    assert len(b) == 24
    assert float(np.median(rel_g1[-5:])) < 0.01
    assert float(np.median(rel_g105[-5:])) > float(np.median(rel_g1[-5:]))


def test_sweep_numeric_wf_baseline_computed_once_per_window(tmp_path: Path, monkeypatch):
    original = sweep_ppn_constraints._compute_numeric_wf_baseline
    calls: list[tuple[float, float]] = []

    def counted(*, window: tuple[float, float], n_points: int, h: float):
        calls.append(window)
        return original(window=window, n_points=n_points, h=h)

    monkeypatch.setattr(sweep_ppn_constraints, "_compute_numeric_wf_baseline", counted)
    row = sweep_ppn_constraints.run_ppn_sweep(
        project_root=tmp_path,
        gamma_min=0.99,
        gamma_max=1.01,
        gamma_steps=3,
        wf_thresh_seq=[0.05, 0.03],
        range_windows=[(50.0, 200.0), (100.0, 400.0)],
        n_points=8,
        h=0.3,
        wf_ref_mode="numeric",
        notes="wf_numeric_cache_test",
        mirror_jsonl=False,
    )
    assert len(calls) == 2
    run_id = str(row["run_id"])
    promotion_path = tmp_path / "results" / "artifacts" / run_id / "raw" / f"{run_id}_promotion_eval.json"
    promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
    assert promotion["diagnostics"]["wf_ref_mode"] == "numeric"
