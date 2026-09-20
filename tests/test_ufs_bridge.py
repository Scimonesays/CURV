"""Tests for the read-only UFS bridge and readiness gate semantics."""

from __future__ import annotations

import json
from pathlib import Path

from src.ufs_bridge import discover_ufs_repo, get_overview, validate_readiness


def _write(root: Path, name: str, payload: dict) -> None:
    path = root / "data" / "canonical" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "Universal-Frequency-Spectrum"
    _write(root, "manifest.json", {"project": "Universal Frequency Spectrum", "schema_version": "1.0.0", "dataset_type": "manifest", "counts": {"frontier": 2, "gaps": 1}})
    _write(
        root,
        "frontier.json",
        {
            "schema_version": "1.0.0",
            "dataset_type": "frontier",
            "records": [
                {
                    "id": "P4-TEST-READY",
                    "name": "Parameterized candidate",
                    "status": "MODEL-DEPENDENT",
                    "evidence": {"class": "model-dependent", "label": "MODEL-DEPENDENT"},
                    "physical_candidate_or_question": "scalar field with coupling g",
                    "predicted_or_observed_signal": "narrow spectral shift proportional to g",
                    "required_bridge": "field coupling to atomic transition",
                    "source_ids": ["SRC-1"],
                    "energy_accounting": {"status": "model/context-dependent"},
                    "claim_id": "CLAIM-P4-TEST-READY",
                },
                {
                    "id": "P4-TEST-OPEN",
                    "name": "Unknown carrier claim",
                    "status": "SPECULATIVE",
                    "evidence": {"class": "speculative", "label": "SPECULATIVE"},
                    "physical_candidate_or_question": "unknown information carrier",
                    "predicted_or_observed_signal": "reported correlation",
                    "required_bridge": "unknown information channel",
                    "source_ids": ["SRC-2"],
                    "energy_accounting": {"status": "no novel energy carrier established"},
                    "claim_id": "CLAIM-P4-TEST-OPEN",
                },
            ]
        },
    )
    _write(
        root,
        "gaps.json",
        {
            "schema_version": "1.0.0",
            "dataset_type": "gaps",
            "records": [
                {
                    "id": "GAP-TEST-001",
                    "type": "instrument_gap",
                    "name": "Detector gap",
                    "status": "OPEN",
                    "scope": "1-2 Hz",
                    "meaning": "Sensitivity is poor.",
                    "related_ids": ["P4-TEST-READY"],
                    "source_ids": ["SRC-3"],
                }
            ]
        },
    )
    _write(root, "phenomena.json", {"schema_version": "1.0.0", "dataset_type": "phenomena", "records": []})
    _write(root, "interactions.json", {"schema_version": "1.0.0", "dataset_type": "interactions", "records": []})
    _write(root, "claims.json", {"schema_version": "1.0.0", "dataset_type": "claims", "records": []})
    return root


def test_discover_explicit_repo(tmp_path: Path):
    root = _fixture(tmp_path)
    assert discover_ufs_repo(str(root)) == root.resolve()


def test_overview_reads_canonical_counts(tmp_path: Path):
    root = _fixture(tmp_path)
    overview = get_overview(str(root))
    assert overview["connected"] is True
    assert overview["manifest"]["counts"]["frontier"] == 2
    assert len(overview["frontier"]) == 2
    assert len(overview["gaps"]) == 1


def test_ready_candidate_reaches_constraint_design(tmp_path: Path):
    root = _fixture(tmp_path)
    result = validate_readiness("P4-TEST-READY", explicit=str(root), policy="strict")
    assert result["verdict"] == "READY_FOR_CONSTRAINT_DESIGN"
    assert result["n_fail"] == 0


def test_unknown_carrier_requires_operationalization(tmp_path: Path):
    root = _fixture(tmp_path)
    result = validate_readiness("P4-TEST-OPEN", explicit=str(root), policy="strict")
    assert result["verdict"] == "NEEDS_OPERATIONALIZATION"
    failed = {g["id"] for g in result["gates"] if g["status"] == "FAIL"}
    assert "UFS-G2" in failed
    assert "UFS-G4" in failed


def test_missing_repo_is_safe(tmp_path: Path):
    overview = get_overview(str(tmp_path / "missing"))
    assert overview["connected"] is False
    assert overview["frontier"] == []


def test_invalid_manifest_is_rejected(tmp_path: Path):
    root = _fixture(tmp_path)
    manifest = root / "data" / "canonical" / "manifest.json"
    manifest.write_text(json.dumps({"project": "Not UFS", "schema_version": "1.0.0", "dataset_type": "manifest"}), encoding="utf-8")
    overview = get_overview(str(root))
    assert overview["connected"] is False
    assert "project identity" in str(overview["error"])
