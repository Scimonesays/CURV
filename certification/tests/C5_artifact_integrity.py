"""C5: Artifact integrity certification test."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import PASS, fail_result, guard_run, sha256_file


def run(test_config: dict, out_dir: Path) -> dict:
    def _impl() -> dict:
        upstream = dict(test_config.get("upstream_results", {}))
        run_artifacts: list[str] = []
        missing: list[str] = []
        checksums: dict[str, str] = {}

        for test_id in ("C1_reference_reproduction", "C2_resolution_convergence", "C3_gate_sensitivity", "C4_numerical_robustness"):
            test_data = upstream.get(test_id, {})
            for rel in test_data.get("artifacts", []):
                path = out_dir / rel
                run_artifacts.append(rel)
                if not path.exists():
                    missing.append(rel)

        # Registry append requirement.
        registry_csv = out_dir / "results" / "registry" / "results_registry.csv"
        if not registry_csv.exists():
            missing.append("results/registry/results_registry.csv")
        else:
            lines = registry_csv.read_text(encoding="utf-8").splitlines()
            if len(lines) <= 1:
                return fail_result(
                    details="Registry CSV exists but has no appended rows.",
                    failure_codes=["C5_FAIL_REGISTRY_APPEND"],
                    metrics={"registry_csv": str(registry_csv.relative_to(out_dir).as_posix())},
                )
            checksums["registry_csv"] = sha256_file(registry_csv)
            checksums["registry_last_row_sha256"] = sha256_file(_write_temp_last_row(out_dir, lines[-1]))

        for rel in run_artifacts:
            path = out_dir / rel
            if path.exists() and (rel.endswith(".json") or rel.endswith(".csv")):
                checksums[rel] = sha256_file(path)

        # Required top-level certification artifacts.
        for required in ("environment_snapshot.json", "git_commit_hash.txt", "config_used.json"):
            p = out_dir / required
            if not p.exists():
                missing.append(required)
            else:
                checksums[required] = sha256_file(p)

        checksum_path = out_dir / "checksums.json"
        checksum_path.write_text(json.dumps(checksums, indent=2, ensure_ascii=True), encoding="utf-8")

        if missing:
            return fail_result(
                details="Missing one or more required artifacts.",
                failure_codes=["C5_FAIL_MISSING_ARTIFACT"],
                metrics={"missing": missing},
            )

        return {
            "status": PASS,
            "details": "C5 artifact integrity checks passed.",
            "failure_codes": [],
            "metrics": {
                "n_checked_artifacts": len(run_artifacts),
                "n_checksums": len(checksums),
                "commands_invoked": ["file existence checks + sha256 digest"],
            },
            "artifacts": [str(checksum_path.relative_to(out_dir).as_posix())],
        }

    return guard_run(_impl, "C5_FAIL_MISSING_ARTIFACT")


def _write_temp_last_row(out_dir: Path, line: str) -> Path:
    tmp = out_dir / "_registry_last_row.tmp"
    tmp.write_text(line + "\n", encoding="utf-8")
    return tmp

