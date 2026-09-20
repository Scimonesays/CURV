from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.exotic_tripwire import ExoticTripwireConfig, run_exotic_tripwire


def _write_input_curve(project_root: Path, run_id: str, b: np.ndarray, alpha_model: np.ndarray, alpha_ref: np.ndarray) -> None:
    run_dir = project_root / "results" / "artifacts" / run_id
    metrics_dir = run_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    table = np.column_stack([b, alpha_model, alpha_model, alpha_ref, np.zeros_like(b)])
    np.savetxt(
        metrics_dir / f"{run_id}_deflection_curve.csv",
        table,
        delimiter=",",
        header="b_over_m,alpha_numeric_h,alpha_numeric_h2,alpha_reference,relative_error_h",
        comments="",
    )


def test_exotic_tripwire_success_writes_summary_and_metrics(tmp_path: Path):
    input_run_id = "20260228_000000Z_gr_yukawa_deviation_k0p01_N12_sig50_connNA_expNA"
    b = np.array([100.0, 200.0, 400.0, 800.0], dtype=float)
    alpha_ref = 4.0 / b
    delta = np.array([-0.02, -0.015, -0.01, -0.005], dtype=float)
    alpha_model = alpha_ref * (1.0 + delta)
    _write_input_curve(tmp_path, input_run_id, b, alpha_model, alpha_ref)

    cfg = ExoticTripwireConfig(
        input_run_id=input_run_id,
        b_window=(100.0, 800.0),
        epsilon=1.0e-12,
        wec_floor=0.0,
        nec_floor=0.0,
        rho_budget_max=1.0,
        scaling_limit_p_max=0.1,
        score_w1=1.0,
        score_w2=1.0,
        score_w3=1.0,
        notes="unit_test",
        write_registry=False,
        mirror_jsonl=False,
    )
    out = run_exotic_tripwire(project_root=tmp_path, config=cfg)
    assert out["status"] == "OK"
    assert out["wec_tripwire"] is True
    assert out["nec_tripwire"] is True
    assert out["tripwire_pass"] is False
    assert float(out["rho_proxy_min"]) < 0.0
    assert float(out["exoticity_score"]) > 0.0

    run_id = str(out["run_id"])
    summary_path = tmp_path / "results" / "artifacts" / run_id / "raw" / f"{run_id}_exotic_tripwire_summary.json"
    metrics_path = tmp_path / "results" / "artifacts" / run_id / "metrics" / f"{run_id}_exotic_tripwire_metrics.csv"
    assert summary_path.exists()
    assert metrics_path.exists()


def test_exotic_tripwire_failure_still_writes_failure_summary(tmp_path: Path):
    cfg = ExoticTripwireConfig(
        input_run_id="missing_input_run",
        b_window=(100.0, 800.0),
        epsilon=1.0e-12,
        wec_floor=0.0,
        nec_floor=0.0,
        rho_budget_max=1.0,
        scaling_limit_p_max=2.0,
        score_w1=1.0,
        score_w2=1.0,
        score_w3=1.0,
        notes="unit_test_failure",
        write_registry=False,
        mirror_jsonl=False,
    )
    try:
        _ = run_exotic_tripwire(project_root=tmp_path, config=cfg)
        assert False, "Expected run_exotic_tripwire to raise on missing input run"
    except Exception:
        pass

    artifact_dirs = sorted((tmp_path / "results" / "artifacts").glob("*_exotic_tripwire_*"))
    assert artifact_dirs, "Expected an exotic tripwire artifact run directory"
    run_dir = artifact_dirs[-1]
    summary_files = list((run_dir / "raw").glob("*_exotic_tripwire_summary.json"))
    assert summary_files, "Expected failure summary JSON"
    payload = json.loads(summary_files[0].read_text(encoding="utf-8"))
    assert payload["status"] == "FAILED"
    assert "traceback_path" in payload

