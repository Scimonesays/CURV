"""C1: Reference reproduction certification test."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import PASS, fail_result, guard_run, load_json, run_sweep, stable_hash


def _extract_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "best_gamma_ppn": summary.get("best_gamma_ppn"),
        "promotion_level": summary.get("promotion_level"),
        "survivors_by_thresh": summary.get("survivors_by_thresh"),
        "tail_sign_verdict": summary.get("tail_sign_verdict"),
    }


def run(test_config: dict, out_dir: Path) -> dict:
    def _impl() -> dict:
        s1 = run_sweep(test_config, out_dir, "C1_run1")
        s2 = run_sweep(test_config, out_dir, "C1_run2")
        summary1 = load_json(s1["summary_json"])
        summary2 = load_json(s2["summary_json"])

        best_gamma = summary1.get("best_gamma_ppn")
        if isinstance(best_gamma, str):
            return fail_result(
                details="C1 produced NA best_gamma_ppn.",
                failure_codes=["C1_FAIL_NUMERIC"],
                metrics={"run_id": s1["run_id"]},
            )

        delta = abs(float(best_gamma) - 1.0)
        gamma_bound = float(test_config["gamma_bound"])
        hash1 = stable_hash(_extract_metrics(summary1))
        hash2 = stable_hash(_extract_metrics(summary2))

        codes: list[str] = []
        if delta > gamma_bound:
            codes.append("C1_FAIL_BOUND")
        if hash1 != hash2:
            codes.append("C1_FAIL_DRIFT")

        status = PASS if not codes else "FAIL"
        details = "C1 reproduced gamma bound deterministically." if not codes else "C1 failed bound and/or rerun drift checks."
        return {
            "status": status,
            "details": details,
            "failure_codes": codes,
            "metrics": {
                "best_gamma_ppn": float(best_gamma),
                "abs_gamma_minus_one": delta,
                "gamma_bound": gamma_bound,
                "rerun_hash_1": hash1,
                "rerun_hash_2": hash2,
                "commands_invoked": [s1["command"], s2["command"]],
            },
            "artifacts": [
                str(s1["summary_json"].relative_to(out_dir).as_posix()),
                str(s2["summary_json"].relative_to(out_dir).as_posix()),
                str(s1["metrics_results_csv"].relative_to(out_dir).as_posix()),
            ],
        }

    return guard_run(_impl, "C1_FAIL_NUMERIC")

