"""Read-only bridge to the Universal Frequency Spectrum canonical dataset."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SIBLING = ROOT_DIR.parent / "Universal-Frequency-Spectrum"
EXPECTED_PROJECT = "Universal Frequency Spectrum"
EXPECTED_SCHEMA_VERSION = "1.0.0"


def discover_ufs_repo(explicit: str | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("UFS_REPO_PATH")
    if env:
        candidates.append(Path(env))
    candidates.append(DEFAULT_SIBLING)

    for candidate in candidates:
        root = candidate.expanduser().resolve()
        if (root / "data" / "canonical" / "manifest.json").is_file():
            return root
    return None


def _read(root: Path, name: str) -> dict[str, Any]:
    path = root / "data" / "canonical" / name
    return json.loads(path.read_text(encoding="utf-8"))


def load_bundle(explicit: str | None = None) -> tuple[Path, dict[str, Any]]:
    root = discover_ufs_repo(explicit)
    if root is None:
        raise FileNotFoundError(
            "Universal-Frequency-Spectrum not found. Set UFS_REPO_PATH or clone it "
            "beside CURV."
        )

    manifest = _read(root, "manifest.json")
    if manifest.get("project") != EXPECTED_PROJECT:
        raise ValueError(f"Unexpected UFS project identity: {manifest.get('project')!r}")
    if manifest.get("dataset_type") != "manifest":
        raise ValueError("UFS manifest is missing dataset_type='manifest'")
    if manifest.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported UFS schema version: {manifest.get('schema_version')!r}; "
            f"expected {EXPECTED_SCHEMA_VERSION}"
        )

    names = ["frontier", "gaps", "phenomena", "interactions", "claims"]
    bundle: dict[str, Any] = {"manifest": manifest}
    for name in names:
        doc = _read(root, f"{name}.json")
        if doc.get("dataset_type") != name:
            raise ValueError(f"UFS {name}.json has dataset_type={doc.get('dataset_type')!r}")
        if doc.get("schema_version") != EXPECTED_SCHEMA_VERSION:
            raise ValueError(f"UFS {name}.json schema version does not match the supported contract")
        if not isinstance(doc.get("records"), list):
            raise ValueError(f"UFS {name}.json records must be an array")
        bundle[name] = doc
    return root, bundle


def get_overview(explicit: str | None = None) -> dict[str, Any]:
    try:
        root, bundle = load_bundle(explicit)
    except (FileNotFoundError, ValueError) as exc:
        return {
            "connected": False,
            "error": str(exc),
            "root": None,
            "manifest": None,
            "frontier": [],
            "gaps": [],
        }

    frontier = bundle["frontier"].get("records", [])
    gaps = bundle["gaps"].get("records", [])
    return {
        "connected": True,
        "root": str(root),
        "manifest": bundle["manifest"],
        "frontier": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "domain": r.get("domain"),
                "status": r.get("status"),
                "evidence": r.get("evidence"),
                "predicted_or_observed_signal": r.get("predicted_or_observed_signal"),
                "required_bridge": r.get("required_bridge"),
                "energy_accounting": r.get("energy_accounting"),
            }
            for r in frontier
        ],
        "gaps": gaps,
    }


def find_record(record_id: str, explicit: str | None = None) -> dict[str, Any]:
    root, bundle = load_bundle(explicit)
    for group in ("frontier", "phenomena", "interactions", "gaps"):
        for record in bundle[group].get("records", []):
            if record.get("id") == record_id:
                return {"root": str(root), "record_type": group, "record": record}
    raise KeyError(record_id)


def _specific(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    lowered = text.lower()
    weak = {
        "unknown",
        "none",
        "n/a",
        "na",
        "not applicable",
        "not yet operationalized",
        "unknown carrier",
        "unknown information channel",
    }
    if lowered in weak or lowered.startswith("unknown "):
        return False
    return True


def validate_readiness(
    record_id: str,
    *,
    explicit: str | None = None,
    policy: str = "strict",
    speculative: bool = False,
) -> dict[str, Any]:
    found = find_record(record_id, explicit)
    record_type = found["record_type"]
    record = found["record"]

    if record_type not in {"frontier", "gaps"}:
        raise ValueError(
            f"{record_id} is a {record_type} record; the generic UFS readiness "
            "validator is intended for frontier/question or gap records."
        )

    source_ids = record.get("source_ids") or []
    if record_type == "frontier":
        candidate = record.get("physical_candidate_or_question")
        signal = record.get("predicted_or_observed_signal")
        bridge = record.get("required_bridge")
        energy = (record.get("energy_accounting") or {}).get("status")
    else:
        candidate = record.get("meaning")
        signal = record.get("scope")
        bridge = "related canonical records" if record.get("related_ids") else None
        energy = "gap-specific; must be defined by downstream model"

    gates = [
        {
            "id": "UFS-G1",
            "label": "source traceability",
            "status": "PASS" if source_ids else "FAIL",
            "detail": f"{len(source_ids)} source IDs attached" if source_ids else "No source IDs attached",
        },
        {
            "id": "UFS-G2",
            "label": "candidate/question specificity",
            "status": "PASS" if _specific(candidate) else "FAIL",
            "detail": str(candidate or "No specific candidate/question supplied"),
        },
        {
            "id": "UFS-G3",
            "label": "observable/signal specificity",
            "status": "PASS" if _specific(signal) else "FAIL",
            "detail": str(signal or "No predicted/observed signal supplied"),
        },
        {
            "id": "UFS-G4",
            "label": "bridge/coupling specificity",
            "status": "PASS" if _specific(bridge) else "FAIL",
            "detail": str(bridge or "No physical bridge/coupling supplied"),
        },
        {
            "id": "UFS-G5",
            "label": "energy-accounting status present",
            "status": "PASS" if _specific(energy) else "WARNING",
            "detail": str(energy or "Energy-transfer status is not established"),
        },
    ]

    n_fail = sum(g["status"] == "FAIL" for g in gates)
    n_pass = sum(g["status"] == "PASS" for g in gates)

    if not source_ids:
        verdict = "HOLD_EVIDENCE"
    elif n_fail:
        verdict = "NEEDS_OPERATIONALIZATION"
    else:
        verdict = "READY_FOR_CONSTRAINT_DESIGN"

    return {
        "record_id": record_id,
        "record_type": record_type,
        "name": record.get("name") or record.get("topic") or record.get("id"),
        "canonical_status": record.get("status"),
        "canonical_evidence": record.get("evidence"),
        "policy": policy,
        "speculative": bool(speculative),
        "verdict": verdict,
        "n_pass": n_pass,
        "n_fail": n_fail,
        "gates": gates,
        "source_ids": source_ids,
        "ufs_root": found["root"],
        "canonical_record": record,
        "semantic_note": (
            "Readiness verdict only. This does not alter the UFS canonical evidence "
            "status and is not a truth/falsity verdict on the hypothesis."
        ),
    }
