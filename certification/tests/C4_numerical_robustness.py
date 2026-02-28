"""C4: Numerical robustness certification test."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import PASS, fail_result, guard_run, load_json, run_sweep


def run(test_config: dict, out_dir: Path) -> dict:
    def _impl() -> dict:
        perturbations = list(test_config["perturbations"])
        gamma_tol = float(test_config.get("gamma_tol", 0.01))
        mode_gamma_tol = float(test_config.get("mode_gamma_tol", 0.015))
        eps = 1.0e-12

        runs: list[dict[str, Any]] = []
        for idx, perturb in enumerate(perturbations):
            cfg = dict(test_config["base_sweep"])
            cfg.update(perturb)
            run_data = run_sweep(cfg, out_dir, f"C4_perturb_{idx}")
            run_data["summary"] = load_json(run_data["summary_json"])
            run_data["perturb"] = perturb
            runs.append(run_data)

        baseline = runs[0]
        base_gamma = baseline["summary"].get("best_gamma_ppn")
        if isinstance(base_gamma, str):
            return fail_result("Baseline C4 run returned NA best_gamma_ppn.", ["C4_FAIL_NUMERIC_INSTABILITY"])
        base_gamma = float(base_gamma)
        base_promo = str(baseline["summary"].get("promotion_level", "NA"))

        codes: list[str] = []
        mode_gammas: dict[str, float] = {}
        promotion_invariant = True
        gamma_deltas: list[float] = []

        for run_data in runs[1:]:
            best = run_data["summary"].get("best_gamma_ppn")
            if isinstance(best, str):
                codes.append("C4_FAIL_NUMERIC_INSTABILITY")
                continue
            best_val = float(best)
            gamma_delta = abs(best_val - base_gamma)
            gamma_deltas.append(gamma_delta)
            if gamma_delta > (gamma_tol + eps):
                codes.append("C4_FAIL_TOLERANCE_SENSITIVITY")
            promo = str(run_data["summary"].get("promotion_level", "NA"))
            if promo != base_promo:
                promotion_invariant = False
            mode = str(run_data["summary"].get("wf_ref_mode", "unknown"))
            mode_gammas[mode] = best_val

        if not promotion_invariant:
            codes.append("C4_FAIL_NUMERIC_INSTABILITY")
        if "analytic" in mode_gammas and "numeric" in mode_gammas:
            if abs(mode_gammas["analytic"] - mode_gammas["numeric"]) > (mode_gamma_tol + eps):
                codes.append("C4_FAIL_MODE_DEPENDENCE")

        # De-duplicate while preserving order
        dedup_codes: list[str] = []
        for code in codes:
            if code not in dedup_codes:
                dedup_codes.append(code)

        status = PASS if not dedup_codes else "FAIL"
        details = "C4 numerical perturbations stay within tolerance." if not dedup_codes else "C4 numerical robustness checks failed."
        return {
            "status": status,
            "details": details,
            "failure_codes": dedup_codes,
            "metrics": {
                "baseline_best_gamma_ppn": base_gamma,
                "baseline_promotion_level": base_promo,
                "gamma_deltas_vs_baseline": gamma_deltas,
                "gamma_tol": gamma_tol,
                "mode_gamma_tol": mode_gamma_tol,
                "mode_gammas": mode_gammas,
                "commands_invoked": [r["command"] for r in runs],
            },
            "artifacts": [str(r["summary_json"].relative_to(out_dir).as_posix()) for r in runs],
        }

    return guard_run(_impl, "C4_FAIL_NUMERIC_INSTABILITY")

