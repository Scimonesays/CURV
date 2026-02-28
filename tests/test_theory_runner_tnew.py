from __future__ import annotations

import json
from pathlib import Path

from scripts.run_theory_deflection import run_theory_deflection


def test_runner_writes_tnew_artifact_and_notes(tmp_path: Path):
    out = run_theory_deflection(
        project_root=tmp_path,
        theory_name="gr_yukawa_deviation",
        alpha_y=0.01,
        lambda_y_over_m=50.0,
        bmin_over_m=20.0,
        bmax_over_m=80.0,
        n_points=6,
        h=0.5,
        notes="test_tnew_hook",
        mirror_jsonl=False,
    )
    run_id = str(out["run_id"])
    raw_path = tmp_path / "results" / "artifacts" / run_id / "raw" / f"{run_id}_tnew_summary.json"
    assert raw_path.exists()
    summary = json.loads(raw_path.read_text(encoding="utf-8"))
    assert summary["requires_negative_energy"] == "unknown"

    registry_path = tmp_path / "results" / "registry" / "results_registry.csv"
    text = registry_path.read_text(encoding="utf-8")
    assert "tnew_model=yukawa_weak_field" in text

