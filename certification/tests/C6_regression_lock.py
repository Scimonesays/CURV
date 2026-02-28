"""C6: Regression lock certification test."""

from __future__ import annotations

import json
from pathlib import Path

from .common import PASS, fail_result, guard_run


def run(test_config: dict, out_dir: Path) -> dict:
    def _impl() -> dict:
        baseline_path = Path(test_config["baseline_path"])
        if not baseline_path.is_absolute():
            baseline_path = (out_dir.parent.parent.parent / baseline_path).resolve()
        if not baseline_path.exists():
            return fail_result("Baseline file missing.", ["C6_FAIL_BASELINE_MISMATCH"])

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        upstream = dict(test_config.get("upstream_results", {}))
        c1 = upstream.get("C1_reference_reproduction", {}).get("metrics", {})
        c2 = upstream.get("C2_resolution_convergence", {}).get("metrics", {})
        c3 = upstream.get("C3_gate_sensitivity", {}).get("metrics", {})

        expected = baseline.get("expected", {})
        tolerances = baseline.get("tolerances", {})

        codes: list[str] = []

        best_gamma = float(c1.get("best_gamma_ppn", 999.0))
        exp_gamma = float(expected.get("best_gamma_ppn", 1.0))
        gamma_tol = float(tolerances.get("best_gamma_ppn_abs", 0.02))
        if abs(best_gamma - exp_gamma) > gamma_tol:
            codes.append("C6_FAIL_UNEXPLAINED_DRIFT")

        max_h_pair_delta = float(c2.get("h_pair_max_delta", 999.0))
        h_pair_tol = float(tolerances.get("c2_h_pair_max_delta", 0.02))
        if max_h_pair_delta > h_pair_tol:
            codes.append("C6_FAIL_UNEXPLAINED_DRIFT")

        monotonic_expected = bool(expected.get("c3_monotonic_pruning", True))
        monotonic_observed = (
            float(c3.get("survivors_tighter", 0)) <= float(c3.get("survivors_baseline", 0)) <= float(c3.get("survivors_looser", 0))
        )
        if monotonic_expected != monotonic_observed:
            codes.append("C6_FAIL_BASELINE_MISMATCH")

        dedup = []
        for code in codes:
            if code not in dedup:
                dedup.append(code)

        status = PASS if not dedup else "FAIL"
        details = "C6 regression lock matched certified baseline tolerances." if not dedup else "C6 regression drift exceeded baseline tolerances."
        return {
            "status": status,
            "details": details,
            "failure_codes": dedup,
            "metrics": {
                "best_gamma_ppn_observed": best_gamma,
                "best_gamma_ppn_expected": exp_gamma,
                "best_gamma_ppn_abs_tol": gamma_tol,
                "c2_h_pair_max_delta_observed": max_h_pair_delta,
                "c2_h_pair_max_delta_tol": h_pair_tol,
                "c3_monotonic_observed": monotonic_observed,
                "commands_invoked": ["baseline comparison"],
            },
            "artifacts": [str(baseline_path.as_posix())],
        }

    return guard_run(_impl, "C6_FAIL_BASELINE_MISMATCH")

