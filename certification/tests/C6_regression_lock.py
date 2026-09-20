"""C6: Regression-lock certification test for the v0.2 contract."""

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
        c4 = upstream.get("C4_numerical_robustness", {}).get("metrics", {})

        expected = baseline.get("expected", {})
        tolerances = baseline.get("tolerances", {})
        codes: list[str] = []

        best_gamma = float(c1.get("best_gamma_ppn", 999.0))
        exp_gamma = float(expected.get("best_gamma_ppn", 1.0))
        gamma_tol = float(tolerances.get("best_gamma_ppn_abs", 1.0e-12))
        if abs(best_gamma - exp_gamma) > gamma_tol:
            codes.append("C6_FAIL_UNEXPLAINED_DRIFT")

        max_h_pair_delta = float(c2.get("h_pair_max_delta", 999.0))
        h_pair_tol = float(tolerances.get("c2_h_pair_max_delta", 0.005))
        if max_h_pair_delta > h_pair_tol:
            codes.append("C6_FAIL_UNEXPLAINED_DRIFT")

        c2_nonworsening = bool(c2.get("convergence_nonworsening", False))
        if c2_nonworsening != bool(expected.get("c2_convergence_nonworsening", True)):
            codes.append("C6_FAIL_BASELINE_MISMATCH")

        monotonic_observed = (
            float(c3.get("survivors_tighter", 0))
            <= float(c3.get("survivors_baseline", 0))
            <= float(c3.get("survivors_looser", 0))
        )
        if monotonic_observed != bool(expected.get("c3_monotonic_pruning", True)):
            codes.append("C6_FAIL_BASELINE_MISMATCH")

        actual_pruning = bool(c3.get("actual_pruning", False))
        if actual_pruning != bool(expected.get("c3_actual_pruning", True)):
            codes.append("C6_FAIL_BASELINE_MISMATCH")

        c4_promotion_invariant = bool(c4.get("within_mode_promotion_invariant", False))
        if c4_promotion_invariant != bool(expected.get("c4_within_mode_promotion_invariant", True)):
            codes.append("C6_FAIL_BASELINE_MISMATCH")

        c4_gamma_max_delta = float(c4.get("within_mode_gamma_max_delta", 999.0))
        c4_gamma_tol = float(tolerances.get("c4_within_mode_gamma_max_delta", 0.01))
        if c4_gamma_max_delta > c4_gamma_tol:
            codes.append("C6_FAIL_UNEXPLAINED_DRIFT")

        dedup: list[str] = []
        for code in codes:
            if code not in dedup:
                dedup.append(code)

        status = PASS if not dedup else "FAIL"
        details = (
            "C6 regression lock matched the v0.2 certification baseline."
            if not dedup
            else "C6 regression drift exceeded the v0.2 baseline contract."
        )
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
                "c2_convergence_nonworsening": c2_nonworsening,
                "c3_monotonic_observed": monotonic_observed,
                "c3_actual_pruning": actual_pruning,
                "c4_within_mode_promotion_invariant": c4_promotion_invariant,
                "c4_within_mode_gamma_max_delta_observed": c4_gamma_max_delta,
                "c4_within_mode_gamma_max_delta_tol": c4_gamma_tol,
                "commands_invoked": ["v0.2 baseline comparison"],
            },
            "artifacts": [str(baseline_path.as_posix())],
        }

    return guard_run(_impl, "C6_FAIL_BASELINE_MISMATCH")
