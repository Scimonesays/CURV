"""C4: Within-reference numerical robustness certification test."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import PASS, guard_run, load_json, run_sweep


def run(test_config: dict, out_dir: Path) -> dict:
    def _impl() -> dict:
        base_cfg = dict(test_config["base_sweep"])
        mode_runs = dict(test_config["mode_runs"])
        gamma_tol = float(test_config.get("within_mode_gamma_tol", 0.01))
        eps = 1.0e-12

        by_mode: dict[str, list[dict[str, Any]]] = {}
        artifacts: list[str] = []
        codes: list[str] = []

        for mode, perturbations in mode_runs.items():
            runs: list[dict[str, Any]] = []
            for idx, perturb in enumerate(list(perturbations)):
                cfg = dict(base_cfg)
                cfg["wf_ref_mode"] = str(mode)
                overrides = {k: v for k, v in dict(perturb).items() if k != "label"}
                cfg.update(overrides)
                label = str(perturb.get("label", f"run_{idx}"))
                run_data = run_sweep(cfg, out_dir, f"C4_{mode}_{label}")
                summary = load_json(run_data["summary_json"])
                best = summary.get("best_gamma_ppn")
                if isinstance(best, str):
                    codes.append("C4_FAIL_MODE_EXECUTION")
                    best_val: float | None = None
                else:
                    best_val = float(best)
                item = {
                    "label": label,
                    "mode": str(mode),
                    "best_gamma_ppn": best_val,
                    "promotion_level": str(summary.get("promotion_level", "NA")),
                    "h": float(summary.get("h", cfg.get("h", 0.0))),
                    "summary_json": str(run_data["summary_json"].relative_to(out_dir).as_posix()),
                    "command": run_data["command"],
                }
                runs.append(item)
                artifacts.append(item["summary_json"])
            if not runs:
                codes.append("C4_FAIL_MODE_EXECUTION")
            by_mode[str(mode)] = runs

        mode_metrics: dict[str, Any] = {}
        within_mode_promotion_invariant = True
        within_mode_gamma_max_delta = 0.0

        for mode, runs in by_mode.items():
            if not runs or runs[0]["best_gamma_ppn"] is None:
                continue
            baseline = runs[0]
            deltas: list[float] = []
            promotions: list[str] = []
            for item in runs:
                promotions.append(str(item["promotion_level"]))
                if item["best_gamma_ppn"] is None:
                    continue
                delta = abs(float(item["best_gamma_ppn"]) - float(baseline["best_gamma_ppn"]))
                deltas.append(delta)
                within_mode_gamma_max_delta = max(within_mode_gamma_max_delta, delta)
                if delta > gamma_tol + eps:
                    codes.append("C4_FAIL_WITHIN_MODE_GAMMA_DRIFT")
                if item["promotion_level"] != baseline["promotion_level"]:
                    within_mode_promotion_invariant = False
                    codes.append("C4_FAIL_WITHIN_MODE_PROMOTION_DRIFT")

            mode_metrics[mode] = {
                "baseline_best_gamma_ppn": baseline["best_gamma_ppn"],
                "baseline_promotion_level": baseline["promotion_level"],
                "gamma_deltas": deltas,
                "promotion_levels": promotions,
                "runs": runs,
            }

        cross_mode: dict[str, Any] = {
            "note": (
                "Analytic 4M/b and numeric Schwarzschild are distinct reference models. "
                "Cross-mode shifts are reported, not classified as numerical instability."
            )
        }
        analytic = by_mode.get("analytic", [])
        numeric = by_mode.get("numeric", [])
        if analytic and numeric and analytic[0]["best_gamma_ppn"] is not None and numeric[0]["best_gamma_ppn"] is not None:
            cross_mode["best_gamma_delta"] = abs(
                float(analytic[0]["best_gamma_ppn"]) - float(numeric[0]["best_gamma_ppn"])
            )
            cross_mode["analytic_promotion"] = analytic[0]["promotion_level"]
            cross_mode["numeric_promotion"] = numeric[0]["promotion_level"]
            cross_mode["promotion_changed"] = analytic[0]["promotion_level"] != numeric[0]["promotion_level"]

        dedup_codes: list[str] = []
        for code in codes:
            if code not in dedup_codes:
                dedup_codes.append(code)

        status = PASS if not dedup_codes else "FAIL"
        return {
            "status": status,
            "details": (
                "C4 is stable under step-size perturbations within each reference mode."
                if not dedup_codes
                else "C4 within-reference numerical robustness checks failed."
            ),
            "failure_codes": dedup_codes,
            "metrics": {
                "within_mode_gamma_tol": gamma_tol,
                "within_mode_gamma_max_delta": within_mode_gamma_max_delta,
                "within_mode_promotion_invariant": within_mode_promotion_invariant,
                "modes": mode_metrics,
                "cross_mode_reference_sensitivity": cross_mode,
                "commands_invoked": [
                    item["command"]
                    for runs in by_mode.values()
                    for item in runs
                ],
            },
            "artifacts": artifacts,
        }

    return guard_run(_impl, "C4_FAIL_MODE_EXECUTION")
