from __future__ import annotations

import json
from pathlib import Path

from scripts.run_source_plausibility import run_source_plausibility_trial
from src.results_registry import RESULTS_REGISTRY_COLUMNS
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


def test_source_plausibility_adds_exotic_tripwire_lane_with_default_fail():
    _, summary = evaluate_source_plausibility(
        required_energy_j=None,
        required_power_w=1.0e6,
        mission_duration_s=3600.0,
    )
    assert "exotic_matter_hypothetical" in summary["candidate_labels"]
    exotic_eval = summary["candidate_evaluations"]["exotic_matter_hypothetical"]["exotic_tripwire"]
    assert exotic_eval["passed"] is False
    assert "exotic_not_demonstrated_as_power_source" in exotic_eval["reasons"]


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


def test_backward_compat_default_exotic_flags():
    """Regression: no exotic overrides preserves legacy shape and non-exotic candidate behavior."""
    table, summary = evaluate_source_plausibility(
        required_power_w=1.0e6,
        mission_duration_s=3600.0,
        required_energy_j=None,
    )
    evals = summary["candidate_evaluations"]
    labels = summary["candidate_labels"]

    assert "exotic_matter_hypothetical" in evals
    assert "exotic_matter_hypothetical" in labels
    exotic = evals["exotic_matter_hypothetical"]
    assert exotic["source_pass"] is False
    assert exotic["exotic_tripwire"] != "NA"
    tripwire = exotic["exotic_tripwire"]
    assert isinstance(tripwire, dict)
    assert tripwire["passed"] is False
    assert "dominant_violation" in tripwire

    assert "exotic_matter_hypothetical" in summary["reject_candidates"]
    assert "exotic_matter_hypothetical" not in summary["pass_candidates"]

    legacy_top_level = (
        "required_energy_j",
        "required_power_w",
        "mission_duration_s",
        "pass_candidates",
        "reject_candidates",
        "best_candidate",
        "n_candidates",
        "all_fail",
    )
    for key in legacy_top_level:
        assert key in summary

    orig_six = (
        "li_ion_battery",
        "hydrocarbon_engine",
        "fission_reactor",
        "fusion_speculative",
        "antimatter_extreme",
        "beamed_power",
    )
    expected_pass = {"hydrocarbon_engine", "fission_reactor"}
    for name in orig_six:
        assert name in evals
        assert evals[name]["source_pass"] == (name in expected_pass)

    assert summary["best_candidate"] == "fission_reactor"
    assert summary["n_candidates"] == 7


def test_registry_row_has_all_columns(tmp_path: Path):
    """Regression: trial row preserves RESULTS_REGISTRY_COLUMNS ordering and keys."""
    row = run_source_plausibility_trial(
        project_root=tmp_path,
        required_power_w=1.0e6,
        mission_duration_s=3600.0,
        required_energy_j=None,
        mirror_jsonl=False,
    )
    for col in RESULTS_REGISTRY_COLUMNS:
        assert col in row, f"Missing registry column: {col}"


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
    assert "CURV_CAL:" in text
