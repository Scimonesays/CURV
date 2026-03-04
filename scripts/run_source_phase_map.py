"""Build source feasibility phase map with curvature-reach overlay."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.source_plausibility import evaluate_source_plausibility

DEFAULT_CURVATURE_CAL = 2.08e-43  # (m^-2)/(J m^-3)
DEFAULT_K_TARGET_10M = 1.0e-2
DEFAULT_K_TARGET_1KM = 1.0e-6
C_SQ = 8.9875517923e16

GATE_COLUMNS = {
    "energy": 8,
    "power": 9,
    "thermal": 10,
    "containment": 11,
    "source": 12,
}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def _sphere_volume(radius_m: float) -> float:
    return (4.0 / 3.0) * math.pi * (radius_m**3)


def _point_diagnostics(table: np.ndarray) -> tuple[list[str], str, bool]:
    """Return fail reasons list, dominant gate, and thermal-ceiling flag."""
    gate_fail_counts: dict[str, int] = {}
    for gate_name, col_idx in GATE_COLUMNS.items():
        if gate_name == "source":
            continue
        gate_fail_counts[gate_name] = int(np.sum(table[:, col_idx] < 0.5))
    fail_reasons = [name for name, n in gate_fail_counts.items() if n > 0]
    if not fail_reasons:
        return [], "none", False

    order = ["energy", "power", "thermal", "containment"]
    dominant_gate = max(order, key=lambda g: (gate_fail_counts[g], -order.index(g)))
    thermal_ceiling = bool(gate_fail_counts["thermal"] > 0)
    return fail_reasons, dominant_gate, thermal_ceiling


def _best_feasible_candidate(table: np.ndarray, labels: list[str]) -> str:
    if not labels:
        return "none"
    feasible_indices = np.where(table[:, GATE_COLUMNS["source"]] >= 0.5)[0]
    if feasible_indices.size == 0:
        return "none"
    best_idx = int(feasible_indices[np.argmax(table[feasible_indices, 13])])
    return labels[best_idx]


def _adjacent_pairs(n_power: int, n_duration: int) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    pairs: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for i in range(n_power):
        for j in range(n_duration):
            if i + 1 < n_power:
                pairs.append(((i, j), (i + 1, j)))
            if j + 1 < n_duration:
                pairs.append(((i, j), (i, j + 1)))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run source plausibility phase sweep and emit CSV + summary JSON."
    )
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path (default: repository root).",
    )
    parser.add_argument("--power-min-w", type=float, default=1.0e4)
    parser.add_argument("--power-max-w", type=float, default=1.0e9)
    parser.add_argument("--power-steps", type=int, default=31)
    parser.add_argument("--duration-min-s", type=float, default=1.0e2)
    parser.add_argument("--duration-max-s", type=float, default=1.0e5)
    parser.add_argument("--duration-steps", type=int, default=25)
    parser.add_argument("--active-radius-m", type=float, default=10.0)
    parser.add_argument("--reference-mass-kg", type=float, default=1000.0)
    parser.add_argument("--radiator-temp-k", type=float, default=1200.0)
    parser.add_argument(
        "--exotic-preset",
        choices=["strict", "normal", "sandbox"],
        default=None,
        help="Exotic policy preset. Overrides individual exotic flags.",
    )
    parser.add_argument("--allow-speculative-exotic", action="store_true")
    parser.add_argument("--exotic-max-rho-j-m3", type=float, default=1.0e18)
    parser.add_argument("--exotic-max-total-energy-j", type=float, default=1.0e15)
    parser.add_argument("--exotic-max-negative-energy-j", type=float, default=0.0)
    parser.add_argument("--assumed-negative-energy-j", type=float, default=None)
    parser.add_argument("--curvature-cal", type=float, default=DEFAULT_CURVATURE_CAL)
    parser.add_argument("--k-target-10m", type=float, default=DEFAULT_K_TARGET_10M)
    parser.add_argument("--k-target-1km", type=float, default=DEFAULT_K_TARGET_1KM)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    results_root = project_root / "results"
    run_id = f"{_utc_stamp()}_energy_source_phase_map"
    if args.allow_speculative_exotic:
        run_id = f"{run_id}_speculative"
    run_dir = results_root / "artifacts" / run_id
    metrics_dir = run_dir / "metrics"
    raw_dir = run_dir / "raw"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    power_grid = np.logspace(np.log10(args.power_min_w), np.log10(args.power_max_w), args.power_steps)
    duration_grid = np.logspace(
        np.log10(args.duration_min_s), np.log10(args.duration_max_s), args.duration_steps
    )
    volume_m3 = _sphere_volume(float(args.active_radius_m))

    rows: list[dict[str, Any]] = []
    candidate_map: list[list[str]] = [["none" for _ in range(args.duration_steps)] for _ in range(args.power_steps)]
    gate_fail_counter: Counter[str] = Counter()
    source_labels: list[str] | None = None

    for i, power_w in enumerate(power_grid):
        for j, duration_s in enumerate(duration_grid):
            table, summary = evaluate_source_plausibility(
                required_energy_j=None,
                required_power_w=float(power_w),
                mission_duration_s=float(duration_s),
                reference_mass_kg=float(args.reference_mass_kg),
                radiator_temp_k=float(args.radiator_temp_k),
                active_volume_m3=float(volume_m3),
                exotic_preset=args.exotic_preset,
                allow_speculative_exotic=bool(args.allow_speculative_exotic),
                exotic_max_rho_j_m3=float(args.exotic_max_rho_j_m3),
                exotic_max_total_energy_j=float(args.exotic_max_total_energy_j),
                exotic_max_negative_energy_j=float(args.exotic_max_negative_energy_j),
                exotic_assumed_negative_energy_j=args.assumed_negative_energy_j,
            )
            if source_labels is None:
                source_labels = [str(x) for x in summary["candidate_labels"]]

            total_energy_j = float(power_w * duration_s)
            rho_equiv_j_m3 = float(total_energy_j / max(volume_m3, 1.0e-30))
            mass_equiv_kg_m3 = float(rho_equiv_j_m3 / C_SQ)
            k_reach = float(args.curvature_cal * rho_equiv_j_m3)
            k_ratio_10m = float(k_reach / max(float(args.k_target_10m), 1.0e-300))
            k_ratio_1km = float(k_reach / max(float(args.k_target_1km), 1.0e-300))

            gate_a_pass = bool(not summary["all_fail"])
            best_candidate = _best_feasible_candidate(table, source_labels if source_labels is not None else [])
            fail_reasons, dominant_gate, thermal_ceiling = _point_diagnostics(table)
            fail_reason_text = "|".join(fail_reasons) if fail_reasons else "none"
            if not gate_a_pass:
                gate_fail_counter[dominant_gate] += 1
                if best_candidate == "none":
                    best_candidate = "no_feasible_source"

            candidate_map[i][j] = best_candidate if gate_a_pass else "none"
            rows.append(
                {
                    "required_power_w": float(power_w),
                    "mission_duration_s": float(duration_s),
                    "total_energy_j": total_energy_j,
                    "gateA_pass": gate_a_pass,
                    "best_candidate": best_candidate,
                    "fail_reasons": fail_reason_text,
                    "dominant_rejection_gate": dominant_gate,
                    "thermal_ceiling_flag": bool(thermal_ceiling),
                    "rho_equiv_j_m3": rho_equiv_j_m3,
                    "mass_equiv_kg_m3": mass_equiv_kg_m3,
                    "K_reach_m2_inv": k_reach,
                    "K_target_10m_m2_inv": float(args.k_target_10m),
                    "K_target_1km_m2_inv": float(args.k_target_1km),
                    "K_ratio_10m": k_ratio_10m,
                    "K_ratio_1km": k_ratio_1km,
                    "log10_power_w": float(math.log10(power_w)),
                    "log10_duration_s": float(math.log10(duration_s)),
                }
            )

    csv_path = metrics_dir / f"{run_id}_source_phase_map.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    region_bounds: dict[str, dict[str, float] | None] = {}
    for label in source_labels if source_labels is not None else []:
        pts = [(i, j) for i in range(args.power_steps) for j in range(args.duration_steps) if candidate_map[i][j] == label]
        if not pts:
            region_bounds[label] = None
            continue
        log_p = [math.log10(float(power_grid[i])) for i, _ in pts]
        log_t = [math.log10(float(duration_grid[j])) for _, j in pts]
        region_bounds[label] = {
            "n_points": int(len(pts)),
            "log10_power_min": float(min(log_p)),
            "log10_power_max": float(max(log_p)),
            "log10_duration_min": float(min(log_t)),
            "log10_duration_max": float(max(log_t)),
        }

    transition_bins: dict[str, list[tuple[float, float]]] = defaultdict(list)
    no_feasible_boundary: list[dict[str, float]] = []
    for (a_i, a_j), (b_i, b_j) in _adjacent_pairs(args.power_steps, args.duration_steps):
        c1 = candidate_map[a_i][a_j]
        c2 = candidate_map[b_i][b_j]
        p_mid = 0.5 * (float(power_grid[a_i]) + float(power_grid[b_i]))
        t_mid = 0.5 * (float(duration_grid[a_j]) + float(duration_grid[b_j]))

        if c1 != c2:
            key = "|".join(sorted([c1, c2]))
            transition_bins[key].append((math.log10(p_mid), math.log10(t_mid)))
        if (c1 == "none") ^ (c2 == "none"):
            no_feasible_boundary.append(
                {
                    "power_w": p_mid,
                    "duration_s": t_mid,
                    "log10_power_w": float(math.log10(p_mid)),
                    "log10_duration_s": float(math.log10(t_mid)),
                }
            )

    frontier_summary: list[dict[str, Any]] = []
    for key, pts in sorted(transition_bins.items()):
        p_vals = [p for p, _ in pts]
        t_vals = [t for _, t in pts]
        frontier_summary.append(
            {
                "transition": key,
                "n_segments": int(len(pts)),
                "log10_power_min": float(min(p_vals)),
                "log10_power_max": float(max(p_vals)),
                "log10_duration_min": float(min(t_vals)),
                "log10_duration_max": float(max(t_vals)),
            }
        )

    summary = {
        "run_id": run_id,
        "plot_annotation": "SPECULATIVE MODE" if args.allow_speculative_exotic else None,
        "grid": {
            "power_min_w": float(args.power_min_w),
            "power_max_w": float(args.power_max_w),
            "power_steps": int(args.power_steps),
            "duration_min_s": float(args.duration_min_s),
            "duration_max_s": float(args.duration_max_s),
            "duration_steps": int(args.duration_steps),
            "n_points_total": int(args.power_steps * args.duration_steps),
        },
        "defaults": {
            "active_radius_m": float(args.active_radius_m),
            "active_volume_m3": float(volume_m3),
            "curvature_cal_m2_inv_per_j_m3": float(args.curvature_cal),
            "k_target_10m_m2_inv": float(args.k_target_10m),
            "k_target_1km_m2_inv": float(args.k_target_1km),
            "reference_mass_kg": float(args.reference_mass_kg),
            "radiator_temp_k": float(args.radiator_temp_k),
            "exotic_preset": args.exotic_preset,
            "allow_speculative_exotic": bool(args.allow_speculative_exotic),
            "exotic_max_rho_j_m3": float(args.exotic_max_rho_j_m3),
            "exotic_max_total_energy_j": float(args.exotic_max_total_energy_j),
            "exotic_max_negative_energy_j": float(args.exotic_max_negative_energy_j),
            "assumed_negative_energy_j": args.assumed_negative_energy_j,
        },
        "candidate_region_bounds": region_bounds,
        "frontier_transitions": frontier_summary,
        "no_feasible_source_boundary": {
            "n_segments": int(len(no_feasible_boundary)),
            "sample_points": no_feasible_boundary[:200],
        },
        "dominant_rejection_gate_counts": dict(gate_fail_counter),
        "notes": str(args.notes),
        "artifacts": {
            "csv_long_form": str(csv_path.resolve().relative_to(project_root).as_posix()),
        },
    }

    summary_path = raw_dir / f"{run_id}_phase_map_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")

    print("source_phase_map complete")
    print(f"run_id={run_id}")
    print(f"csv={csv_path.resolve().relative_to(project_root).as_posix()}")
    print(f"summary={summary_path.resolve().relative_to(project_root).as_posix()}")


if __name__ == "__main__":
    main()
