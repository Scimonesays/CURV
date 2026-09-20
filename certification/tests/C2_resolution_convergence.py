"""C2: Schwarzschild integrator resolution-convergence certification test."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.observables.deflection_curve import compute_deflection_curve, mean_normalized_curve_difference
from src.theories.gr_schwarzschild import GRSchwarzschild

from .common import PASS, guard_run


def run(test_config: dict, out_dir: Path) -> dict:
    def _impl() -> dict:
        window = tuple(float(x) for x in test_config["range_window"])
        n_points = int(test_config["n_points"])
        h_seq = [float(x) for x in test_config["h_seq"]]
        max_pair_delta = float(test_config["max_pair_delta"])
        weak_field_tail_max = float(test_config["weak_field_tail_max"])
        eps = 1.0e-15

        if len(h_seq) < 3:
            raise ValueError("C2 requires at least three step sizes.")
        if any(h <= 0 for h in h_seq):
            raise ValueError("C2 step sizes must be positive.")
        if any(h_seq[i + 1] >= h_seq[i] for i in range(len(h_seq) - 1)):
            raise ValueError("C2 h_seq must be strictly decreasing (coarser -> finer).")

        gr = GRSchwarzschild()
        curves: dict[str, list[float]] = {}
        weak_tail: dict[str, float] = {}
        monotonic_by_h: dict[str, bool] = {}

        for h in h_seq:
            _, alpha, _, rel_err = compute_deflection_curve(
                gr,
                bmin_over_m=window[0],
                bmax_over_m=window[1],
                n_points=n_points,
                setup={"h": h},
                reference_mode="analytic",
            )
            key = f"{h:.12g}"
            curves[key] = [float(x) for x in alpha]
            weak_tail[key] = float(np.median(rel_err[-min(5, len(rel_err)):]))
            monotonic_by_h[key] = bool(np.all(np.diff(alpha) < 0.0))

        pair_deltas: list[float] = []
        for i in range(len(h_seq) - 1):
            a = np.asarray(curves[f"{h_seq[i]:.12g}"], dtype=float)
            b = np.asarray(curves[f"{h_seq[i + 1]:.12g}"], dtype=float)
            pair_deltas.append(mean_normalized_curve_difference(a, b))

        h_pair_max_delta = max(pair_deltas)
        convergence_nonworsening = all(
            pair_deltas[i + 1] <= pair_deltas[i] + eps for i in range(len(pair_deltas) - 1)
        )
        weak_field_ok = max(weak_tail.values()) <= weak_field_tail_max
        monotonic_ok = all(monotonic_by_h.values())

        codes: list[str] = []
        if h_pair_max_delta > max_pair_delta:
            codes.append("C2_FAIL_DIVERGENCE")
        if not convergence_nonworsening:
            codes.append("C2_FAIL_NONMONOTONIC")
        if not monotonic_ok:
            codes.append("C2_FAIL_CURVE_MONOTONICITY")
        if not weak_field_ok:
            codes.append("C2_FAIL_WEAK_FIELD_SANITY")

        artifact_rel = "C2_schwarzschild_convergence.json"
        artifact_path = out_dir / artifact_rel
        artifact_payload = {
            "range_window": list(window),
            "n_points": n_points,
            "h_seq": h_seq,
            "pair_deltas": pair_deltas,
            "h_pair_max_delta": h_pair_max_delta,
            "max_pair_delta": max_pair_delta,
            "convergence_nonworsening": convergence_nonworsening,
            "weak_field_tail_error_by_h": weak_tail,
            "weak_field_tail_max": weak_field_tail_max,
            "monotonic_deflection_by_h": monotonic_by_h,
            "curves": curves,
        }
        artifact_path.write_text(json.dumps(artifact_payload, indent=2), encoding="utf-8")

        status = PASS if not codes else "FAIL"
        return {
            "status": status,
            "details": (
                "C2 Schwarzschild integrator converges under step refinement."
                if not codes
                else "C2 Schwarzschild integrator convergence checks failed."
            ),
            "failure_codes": codes,
            "metrics": {
                "h_pair_max_delta": h_pair_max_delta,
                "pair_deltas": pair_deltas,
                "h_seq": h_seq,
                "max_pair_delta": max_pair_delta,
                "convergence_nonworsening": convergence_nonworsening,
                "weak_field_tail_error_by_h": weak_tail,
                "weak_field_tail_max": weak_field_tail_max,
                "monotonic_deflection_by_h": monotonic_by_h,
                "commands_invoked": ["direct GRSchwarzschild compute_deflection_curve refinement"],
            },
            "artifacts": [artifact_rel],
        }

    return guard_run(_impl, "C2_FAIL_DIVERGENCE")
