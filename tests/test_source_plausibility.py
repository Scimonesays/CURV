from __future__ import annotations

import json
from pathlib import Path

from scripts.run_source_plausibility import run_source_plausibility_trial
from src.source_plausibility import evaluate_source_plausibility


def test_source_plausibility_flags_speculative_classes_conservatively():
    table, summary = evaluate_source_plausibility(
        required_energy_j=1.0e9,
        required_power_w=1.0e6,
        mission_duration_s=None,
    )
    labels = summary["candidate_labels"]
    fusion_idx = labels.index("fusion_speculative")
    anti_idx = labels.index("antimatter_extreme")
    beamed_idx = labels.index("beamed_power")

    # containment_pass column index = 11
    assert table[fusion_idx, 11] == 0.0
    assert table[anti_idx, 11] == 0.0
    assert table[beamed_idx, 11] == 0.0


def test_source_runner_writes_artifacts_and_registry_notes(tmp_path: Path):
    row = run_source_plausibility_trial(
        project_root=tmp_path,
        required_energy_j=1.0e8,
        required_power_w=2.0e5,
        mission_duration_s=None,
        notes="source_eval_test",
        mirror_jsonl=False,
    )
    run_id = str(row["run_id"])
    csv_path = tmp_path / "results" / "artifacts" / run_id / "metrics" / f"{run_id}_source_plausibility.csv"
    raw_path = (
        tmp_path / "results" / "artifacts" / run_id / "raw" / f"{run_id}_source_plausibility_summary.json"
    )
    assert csv_path.exists()
    assert raw_path.exists()

    summary = json.loads(raw_path.read_text(encoding="utf-8"))
    assert "best_candidate" in summary

    registry_text = (tmp_path / "results" / "registry" / "results_registry.csv").read_text(encoding="utf-8")
    assert "model_mode" in registry_text
    assert "source_eval:" in registry_text


def test_source_runner_writes_curvature_sanity_when_bubble_args_present(tmp_path: Path):
    row = run_source_plausibility_trial(
        project_root=tmp_path,
        required_energy_j=1.0e8,
        required_power_w=2.0e5,
        mission_duration_s=None,
        bubble_l_m=10.0,
        bubble_geometry="sphere",
        notes="bubble_curv_test",
        mirror_jsonl=False,
    )
    run_id = str(row["run_id"])
    curv_path = (
        tmp_path / "results" / "artifacts" / run_id / "raw" / f"{run_id}_curvature_cost_sanity.json"
    )
    assert curv_path.exists()
    text = (tmp_path / "results" / "registry" / "results_registry.csv").read_text(encoding="utf-8")
    assert "curv_cost:" in text
    assert "curv_gate:" in text
