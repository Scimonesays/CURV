from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.sweep_ppn_constraints import run_ppn_sweep


def test_ppn_sweep_writes_artifacts_and_registry(tmp_path: Path):
    row = run_ppn_sweep(
        project_root=tmp_path,
        gamma_min=0.99,
        gamma_max=1.01,
        gamma_steps=3,
        wf_thresh_seq=[0.25, 0.15],
        range_windows=[(80.0, 150.0), (100.0, 220.0)],
        n_points=6,
        h=0.5,
        notes="ppn_sweep_test",
        mirror_jsonl=False,
    )
    run_id = str(row["run_id"])
    metrics = tmp_path / "results" / "artifacts" / run_id / "metrics"
    raw = tmp_path / "results" / "artifacts" / run_id / "raw"
    assert (metrics / f"{run_id}_ppn_sweep_results.csv").exists()
    assert (metrics / f"{run_id}_ppn_survivors.csv").exists()
    assert (raw / f"{run_id}_ppn_sweep_summary.json").exists()
    promotion = json.loads((raw / f"{run_id}_promotion_eval.json").read_text(encoding="utf-8"))
    assert "tail_sign_verdict" in promotion["diagnostics"]
    assert "tail_sign_na_reason" in promotion["diagnostics"]
    assert "tail_sign_p_two" in promotion["diagnostics"]
    assert "endpoint_not_dominant" not in promotion["candidate_checks"]
    assert "endpoint_not_dominant" in promotion["strong_checks"]

    registry_text = (tmp_path / "results" / "registry" / "results_registry.csv").read_text(encoding="utf-8")
    assert "ppn_sweep:" in registry_text
    assert "wfref: mode=analytic" in registry_text


def test_full_throttle_preserves_numeric_outputs(tmp_path: Path):
    common_kwargs = dict(
        project_root=tmp_path,
        gamma_min=0.99,
        gamma_max=1.01,
        gamma_steps=3,
        wf_thresh_seq=[0.25, 0.15],
        range_windows=[(80.0, 150.0), (100.0, 220.0)],
        n_points=6,
        h=0.5,
        mirror_jsonl=False,
    )
    row_serial = run_ppn_sweep(**common_kwargs)
    row_throttle = run_ppn_sweep(**common_kwargs, full_throttle=True, max_workers=1, telemetry_seconds=10.0)

    base = tmp_path / "results" / "artifacts"
    serial_metrics = np.loadtxt(
        base / str(row_serial["run_id"]) / "metrics" / f"{row_serial['run_id']}_ppn_sweep_results.csv",
        delimiter=",",
        skiprows=1,
    )
    throttle_metrics = np.loadtxt(
        base / str(row_throttle["run_id"]) / "metrics" / f"{row_throttle['run_id']}_ppn_sweep_results.csv",
        delimiter=",",
        skiprows=1,
    )
    assert serial_metrics.shape == throttle_metrics.shape
    assert np.allclose(serial_metrics, throttle_metrics, atol=0.0, rtol=0.0)
