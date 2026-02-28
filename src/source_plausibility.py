"""Mass-free energy source plausibility evaluator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .curvature_cost import curvature_cost_sanity
from .results_registry import (
    RESULTS_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_run_id,
    utc_now_iso,
)

STEFAN_BOLTZMANN = 5.670374419e-8


@dataclass(frozen=True)
class SourceCandidate:
    name: str
    specific_energy_j_per_kg: float
    specific_power_w_per_kg: float
    coupling_efficiency: float
    containment_feasibility: str
    thermal_area_limit_m2: float
    stability_bias: float
    external_source: bool = False
    speculative: bool = False


_CANDIDATES: tuple[SourceCandidate, ...] = (
    SourceCandidate(
        name="li_ion_battery",
        specific_energy_j_per_kg=9.0e5,
        specific_power_w_per_kg=2.0e3,
        coupling_efficiency=0.90,
        containment_feasibility="feasible",
        thermal_area_limit_m2=120.0,
        stability_bias=1.00,
    ),
    SourceCandidate(
        name="hydrocarbon_engine",
        specific_energy_j_per_kg=1.2e7,
        specific_power_w_per_kg=1.5e4,
        coupling_efficiency=0.35,
        containment_feasibility="feasible",
        thermal_area_limit_m2=400.0,
        stability_bias=0.95,
    ),
    SourceCandidate(
        name="fission_reactor",
        specific_energy_j_per_kg=8.0e11,
        specific_power_w_per_kg=8.0e5,
        coupling_efficiency=0.35,
        containment_feasibility="difficult",
        thermal_area_limit_m2=700.0,
        stability_bias=0.70,
    ),
    SourceCandidate(
        name="fusion_speculative",
        specific_energy_j_per_kg=3.0e14,
        specific_power_w_per_kg=5.0e6,
        coupling_efficiency=0.40,
        containment_feasibility="speculative",
        thermal_area_limit_m2=1000.0,
        stability_bias=0.45,
        speculative=True,
    ),
    SourceCandidate(
        name="antimatter_extreme",
        specific_energy_j_per_kg=4.5e16,
        specific_power_w_per_kg=1.0e8,
        coupling_efficiency=0.20,
        containment_feasibility="implausible",
        thermal_area_limit_m2=2000.0,
        stability_bias=0.10,
        speculative=True,
    ),
    SourceCandidate(
        name="beamed_power",
        specific_energy_j_per_kg=float("inf"),
        specific_power_w_per_kg=2.0e7,
        coupling_efficiency=0.50,
        containment_feasibility="unknown",
        thermal_area_limit_m2=3000.0,
        stability_bias=0.50,
        external_source=True,
        speculative=True,
    ),
)


def _containment_pass(label: str) -> bool:
    return label in ("feasible", "difficult")


def _infer_requirements(
    *,
    required_energy_j: float | None,
    required_power_w: float | None,
    mission_duration_s: float | None,
) -> tuple[float, float, float]:
    e = float(required_energy_j) if required_energy_j is not None else None
    p = float(required_power_w) if required_power_w is not None else None
    t = float(mission_duration_s) if mission_duration_s is not None else None

    if e is not None and p is not None:
        if t is None:
            t = e / max(p, 1.0e-15)
        return e, p, t
    if e is not None and t is not None:
        if t <= 0.0:
            raise ValueError("mission_duration_s must be > 0.")
        return e, e / t, t
    if p is not None and t is not None:
        if t <= 0.0:
            raise ValueError("mission_duration_s must be > 0.")
        return p * t, p, t
    raise ValueError("Provide (energy and power) or (energy and duration) or (power and duration).")


def evaluate_source_plausibility(
    *,
    required_energy_j: float | None,
    required_power_w: float | None,
    mission_duration_s: float | None,
    reference_mass_kg: float = 1000.0,
    radiator_temp_k: float = 1200.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Evaluate source classes in mass-free mode using specific demands.

    Returns:
        table: rows with normalized demand/capability and gate fields.
        summary: aggregate metrics and best/reject candidates.
    """
    energy_j, power_w, duration_s = _infer_requirements(
        required_energy_j=required_energy_j,
        required_power_w=required_power_w,
        mission_duration_s=mission_duration_s,
    )
    if reference_mass_kg <= 0.0:
        raise ValueError("reference_mass_kg must be positive.")
    if radiator_temp_k <= 0.0:
        raise ValueError("radiator_temp_k must be positive.")

    req_specific_energy = energy_j / reference_mass_kg
    req_specific_power = power_w / reference_mass_kg

    rows: list[list[float]] = []
    labels: list[str] = []
    source_pass_names: list[str] = []
    reject_names: list[str] = []
    score_map: dict[str, float] = {}

    radiator_flux = STEFAN_BOLTZMANN * (radiator_temp_k**4)
    for idx, c in enumerate(_CANDIDATES):
        energy_pass = bool(req_specific_energy <= c.specific_energy_j_per_kg) or bool(c.external_source)
        power_pass = bool(req_specific_power <= c.specific_power_w_per_kg)
        waste_heat_w = power_w * ((1.0 / max(c.coupling_efficiency, 1.0e-12)) - 1.0)
        heat_area_m2 = waste_heat_w / max(radiator_flux, 1.0e-15)
        thermal_pass = bool(heat_area_m2 <= c.thermal_area_limit_m2)
        containment_pass = _containment_pass(c.containment_feasibility)
        source_pass = bool(energy_pass and power_pass and thermal_pass and containment_pass)

        # Score near 1.0 means plenty of margin; negative means over-demand.
        energy_margin = 1.0 - (req_specific_energy / max(c.specific_energy_j_per_kg, 1.0e-15))
        power_margin = 1.0 - (req_specific_power / max(c.specific_power_w_per_kg, 1.0e-15))
        thermal_margin = 1.0 - (heat_area_m2 / max(c.thermal_area_limit_m2, 1.0e-15))
        stability_margin = float(min(energy_margin, power_margin, thermal_margin) * c.stability_bias)
        score_map[c.name] = stability_margin

        if source_pass:
            source_pass_names.append(c.name)
        else:
            reject_names.append(c.name)

        labels.append(c.name)
        rows.append(
            [
                float(idx),
                req_specific_energy,
                req_specific_power,
                c.specific_energy_j_per_kg,
                c.specific_power_w_per_kg,
                c.coupling_efficiency,
                waste_heat_w,
                heat_area_m2,
                1.0 if energy_pass else 0.0,
                1.0 if power_pass else 0.0,
                1.0 if thermal_pass else 0.0,
                1.0 if containment_pass else 0.0,
                1.0 if source_pass else 0.0,
                stability_margin,
            ]
        )

    table = np.array(rows, dtype=float)
    best_name = max(score_map, key=score_map.get)
    summary = {
        "required_energy_j": float(energy_j),
        "required_power_w": float(power_w),
        "mission_duration_s": float(duration_s),
        "reference_mass_kg": float(reference_mass_kg),
        "required_specific_energy_j_per_kg": float(req_specific_energy),
        "required_specific_power_w_per_kg": float(req_specific_power),
        "radiator_temp_k": float(radiator_temp_k),
        "n_candidates": int(len(_CANDIDATES)),
        "n_pass": int(len(source_pass_names)),
        "all_fail": bool(len(source_pass_names) == 0),
        "best_candidate": best_name,
        "pass_candidates": source_pass_names,
        "reject_candidates": reject_names,
        "candidate_labels": labels,
    }
    return table, summary


def run_source_plausibility_trial(
    *,
    project_root: Path,
    required_energy_j: float | None,
    required_power_w: float | None,
    mission_duration_s: float | None,
    reference_mass_kg: float = 1000.0,
    radiator_temp_k: float = 1200.0,
    bubble_l_m: float | None = None,
    bubble_geometry: str = "sphere",
    bubble_thickness_m: float | None = None,
    notes: str = "",
    mirror_jsonl: bool = True,
) -> dict[str, Any]:
    """Run one mass-free source plausibility trial and append immutable registry evidence."""
    timestamp_utc = utc_now_iso()
    run_id = make_run_id(
        model_mode="energy_source_plausibility",
        k="NA",
        n="NA",
        sigma="NA",
        connectivity="NA",
        field_exponent="NA",
        timestamp_utc=timestamp_utc,
    )

    results_root = project_root / "results"
    run_dir = results_root / "artifacts" / run_id
    metrics_dir = run_dir / "metrics"
    raw_dir = run_dir / "raw"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    table, summary = evaluate_source_plausibility(
        required_energy_j=required_energy_j,
        required_power_w=required_power_w,
        mission_duration_s=mission_duration_s,
        reference_mass_kg=reference_mass_kg,
        radiator_temp_k=radiator_temp_k,
    )
    csv_path = metrics_dir / f"{run_id}_source_plausibility.csv"
    np.savetxt(
        csv_path,
        table,
        delimiter=",",
        header=(
            "candidate_idx,required_specific_energy_j_per_kg,required_specific_power_w_per_kg,"
            "candidate_specific_energy_j_per_kg,candidate_specific_power_w_per_kg,eta,"
            "waste_heat_w,heat_rejection_area_m2,energy_pass,power_pass,thermal_pass,"
            "containment_pass,source_pass,stability_margin"
        ),
        comments="",
    )
    curv_summary: dict[str, Any] | None = None
    if bubble_l_m is not None:
        curv_summary = curvature_cost_sanity(
            l_m=float(bubble_l_m),
            geometry=str(bubble_geometry),
            thickness_m=bubble_thickness_m,
        )
    summary_with_curv = dict(summary)
    summary_with_curv["curvature_cost_sanity"] = curv_summary if curv_summary is not None else "NA"
    summary_path = raw_dir / f"{run_id}_source_plausibility_summary.json"
    summary_path.write_text(json.dumps(summary_with_curv, indent=2, ensure_ascii=True), encoding="utf-8")

    curv_path: Path | None = None
    if curv_summary is not None:
        curv_path = raw_dir / f"{run_id}_curvature_cost_sanity.json"
        curv_path.write_text(json.dumps(curv_summary, indent=2, ensure_ascii=True), encoding="utf-8")

    rel = lambda p: str(p.resolve().relative_to(project_root.resolve()).as_posix())
    artifacts = [rel(csv_path), rel(summary_path)]
    if curv_path is not None:
        artifacts.append(rel(curv_path))

    best = str(summary["best_candidate"])
    rejects = ",".join(str(x) for x in summary["reject_candidates"])
    note_base = (
        "source_eval: "
        f"candidates={summary['n_candidates']}; "
        f"assumptions=mass_free_ref_{summary['reference_mass_kg']}kg_T{summary['radiator_temp_k']}K; "
        f"best={best}; "
        f"reject={rejects}"
    )
    note_parts = [note_base]
    if curv_summary is not None:
        curv_gate = "pass" if bool(curv_summary["curv_gate_pass"]) else "fail"
        curv_note = (
            "curv_cost: "
            f"L={curv_summary['L_m']}m "
            f"geom={curv_summary['geometry']} "
            f"rho_e={curv_summary['rho_e_j_per_m3']:.6g} "
            f"E={curv_summary['E_scale_j']:.6g} "
            f"m_eq={curv_summary['m_equiv_kg']:.6g} "
            f"mJ={curv_summary['m_over_jupiter']:.6g} "
            f"mS={curv_summary['m_over_sun']:.6g} "
            f"gate={curv_gate}"
        )
        reasons = ",".join(curv_summary["sanity_fail_reasons"]) or "none"
        curv_gate_note = (
            "curv_gate: "
            f"{curv_gate}; "
            "ceilings={"
            f"rho_e:{curv_summary['ceiling_rho_e_j_per_m3']:.6g},"
            f"E:{curv_summary['ceiling_E_scale_j']:.6g},"
            f"m_eq:{curv_summary['ceiling_m_equiv_kg']:.6g}"
            "}; "
            f"reasons=[{reasons}]"
        )
        note_parts.extend([curv_note, curv_gate_note])
    if notes:
        note_parts.append(f"user_notes={notes}")
    note_text = "; ".join(note_parts)

    best_idx = summary["candidate_labels"].index(best)
    energy_pass = bool(table[best_idx, 8] >= 0.5)
    power_pass = bool(table[best_idx, 9] >= 0.5)
    thermal_pass = bool(table[best_idx, 10] >= 0.5)
    containment_pass = bool(table[best_idx, 11] >= 0.5)
    source_pass = bool(table[best_idx, 12] >= 0.5)

    gate_a_pass = bool(source_pass and energy_pass)
    if curv_summary is not None:
        gate_a_pass = bool(gate_a_pass and bool(curv_summary["curv_gate_pass"]))

    row = {
        "timestamp_utc": timestamp_utc,
        "run_id": run_id,
        "batch_id": "NA",
        "git_hash": get_git_hash(),
        "model_mode": "energy_source_plausibility",
        "k": "NA",
        "sigma": "NA",
        "N": "NA",
        "connectivity": "NA",
        "field_exponent": "NA",
        "r2_inv": "NA",
        "r2_lin": "NA",
        "delta_r2": "NA",
        "aic_inv": "NA",
        "aic_lin": "NA",
        "superposition_median_rel_error": float(max(0.0, 1.0 - table[best_idx, 13])),
        "resolution_mean_curve_diff": float(table[best_idx, 7]),
        "gateA_scaling_pass": bool(containment_pass),
        "gateA_superposition_pass": bool(power_pass),
        "gateA_resolution_pass": bool(thermal_pass),
        "gateA_pass": gate_a_pass,
        "artifacts": ";".join(artifacts),
        "notes": note_text,
    }
    registry_dir = results_root / "registry"
    append_csv_row(registry_dir / "results_registry.csv", RESULTS_REGISTRY_COLUMNS, row)
    if mirror_jsonl:
        append_jsonl(registry_dir / "results_registry.jsonl", row)
    return row
