"""Run a read-only UFS frontier/question readiness validation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.results_registry import append_csv_row, append_jsonl, get_git_hash
from src.ufs_bridge import validate_readiness

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_DIR = ROOT / "results" / "registry"
ARTIFACTS_DIR = ROOT / "results" / "artifacts"

COLUMNS = [
    "timestamp_utc",
    "run_id",
    "git_hash",
    "ufs_record_id",
    "record_type",
    "canonical_status",
    "policy",
    "speculative_mode",
    "readiness_verdict",
    "n_pass",
    "n_fail",
    "failed_gates",
    "artifacts",
    "notes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def token(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-id", required=True)
    parser.add_argument("--ufs-repo", default="")
    parser.add_argument("--policy", choices=["strict", "normal", "sandbox"], default="strict")
    parser.add_argument("--speculative", action="store_true")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    ts = utc_now()
    run_id = ts.replace("-", "").replace(":", "").replace("T", "_").replace("Z", "Z")
    run_id = f"{run_id}_ufs_{token(args.record_id)}"

    result = validate_readiness(
        args.record_id,
        explicit=args.ufs_repo or None,
        policy=args.policy,
        speculative=args.speculative,
    )

    raw_dir = ARTIFACTS_DIR / run_id / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    artifact = raw_dir / f"{run_id}_ufs_validation.json"

    external_result = {
        "schema_version": "1.0.0",
        "id": f"UFS-VAL-{run_id}",
        "provider": "CURV",
        "target_record_id": args.record_id,
        "target_claim_id": result["canonical_record"].get("claim_id"),
        "provider_repo": "Scimonesays/CURV",
        "provider_commit": get_git_hash(),
        "run_id": run_id,
        "validation_type": "structural_readiness",
        "verdict": result["verdict"],
        "policy": args.policy,
        "speculative": bool(args.speculative),
        "gate_results": result["gates"],
        "evidence_refs": result["source_ids"],
        "artifact_refs": [artifact.relative_to(ROOT).as_posix()],
        "created_utc": ts,
        "reviewed_for_canonical_ingest": False,
        "review_notes": None,
    }
    artifact.write_text(
        json.dumps({"schema_version": "1.0.0", "records": [external_result]}, indent=2),
        encoding="utf-8",
    )

    failed = [g["id"] for g in result["gates"] if g["status"] == "FAIL"]
    row = {
        "timestamp_utc": ts,
        "run_id": run_id,
        "git_hash": get_git_hash(),
        "ufs_record_id": args.record_id,
        "record_type": result["record_type"],
        "canonical_status": result.get("canonical_status") or "NA",
        "policy": args.policy,
        "speculative_mode": bool(args.speculative),
        "readiness_verdict": result["verdict"],
        "n_pass": result["n_pass"],
        "n_fail": result["n_fail"],
        "failed_gates": failed,
        "artifacts": artifact.relative_to(ROOT).as_posix(),
        "notes": args.notes or result["semantic_note"],
    }
    append_csv_row(REGISTRY_DIR / "ufs_validation_registry.csv", COLUMNS, row)
    append_jsonl(REGISTRY_DIR / "ufs_validation_registry.jsonl", row)

    print(f"run_id: {run_id}")
    print(f"ufs_record_id: {args.record_id}")
    print(f"readiness_verdict: {result['verdict']}")
    print(f"artifact: {artifact.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
