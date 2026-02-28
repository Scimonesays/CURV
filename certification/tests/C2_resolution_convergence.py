"""C2: Resolution convergence certification test."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import PASS, fail_result, guard_run, load_json, run_sweep


def run(test_config: dict, out_dir: Path) -> dict:
    def _impl() -> dict:
        n_points_seq = [int(x) for x in test_config["n_points_seq"]]
        h_seq = [float(x) for x in test_config["h_seq"]]
        gamma_tol = float(test_config.get("gamma_band_tol", 0.02))
        h_pair_tol = float(test_config.get("h_pair_tol", 0.01))

        runs: list[dict[str, Any]] = []
        for n_points in n_points_seq:
            for h in h_seq:
                cfg = dict(test_config["base_sweep"])
                cfg["n_points"] = n_points
                cfg["h"] = h
                run_data = run_sweep(cfg, out_dir, f"C2_n{n_points}_h{h}")
                summary = load_json(run_data["summary_json"])
                run_data["summary"] = summary
                runs.append(run_data)

        # Use first h for monotonic trend with resolution.
        trend: list[float] = []
        for n_points in n_points_seq:
            selected = [r for r in runs if int(r["summary"]["n_points"]) == n_points and abs(float(r["summary"]["h"]) - h_seq[0]) < 1.0e-12]
            if not selected:
                return fail_result("Missing resolution run in C2.", ["C2_FAIL_NUMERIC"])
            best = selected[0]["summary"].get("best_gamma_ppn")
            if isinstance(best, str):
                return fail_result("NA best_gamma_ppn encountered in C2.", ["C2_FAIL_DIVERGENCE"])
            trend.append(abs(float(best) - 1.0))

        monotonic = all(trend[i + 1] <= trend[i] + 1.0e-12 for i in range(len(trend) - 1))
        bounded = max(trend) <= gamma_tol

        # Cross-check h perturbation stability at each resolution.
        h_pair_max_delta = 0.0
        for n_points in n_points_seq:
            vals: list[float] = []
            for h in h_seq:
                selected = [r for r in runs if int(r["summary"]["n_points"]) == n_points and abs(float(r["summary"]["h"]) - h) < 1.0e-12]
                if not selected:
                    continue
                best = selected[0]["summary"].get("best_gamma_ppn")
                if isinstance(best, str):
                    continue
                vals.append(float(best))
            if len(vals) >= 2:
                h_pair_max_delta = max(h_pair_max_delta, abs(vals[0] - vals[1]))

        codes: list[str] = []
        if not monotonic and not bounded:
            codes.append("C2_FAIL_NONMONOTONIC")
        if max(trend) > gamma_tol:
            codes.append("C2_FAIL_DIVERGENCE")
        if h_pair_max_delta > h_pair_tol:
            codes.append("C2_FAIL_OSCILLATION")

        status = PASS if not codes else "FAIL"
        details = "C2 resolution convergence is within certified tolerance." if not codes else "C2 convergence checks failed."
        return {
            "status": status,
            "details": details,
            "failure_codes": codes,
            "metrics": {
                "trend_abs_gamma_minus_one": trend,
                "n_points_seq": n_points_seq,
                "h_seq": h_seq,
                "gamma_band_tol": gamma_tol,
                "h_pair_max_delta": h_pair_max_delta,
                "h_pair_tol": h_pair_tol,
                "commands_invoked": [r["command"] for r in runs],
            },
            "artifacts": [str(r["summary_json"].relative_to(out_dir).as_posix()) for r in runs],
        }

    return guard_run(_impl, "C2_FAIL_DIVERGENCE")

