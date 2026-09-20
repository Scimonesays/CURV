"""Exotic stress-energy tripwire over deflection residual proxies.

This module is intentionally a proxy instrument, not a proof of NEC/WEC violation.
Without a full metric and full stress-energy tensor, CURV only computes residual-derived
tripwires that flag models likely to require exotic support.
"""

from __future__ import annotations

import csv
import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .results_registry import (
    EXOTIC_TRIPWIRE_REGISTRY_COLUMNS,
    append_csv_row,
    append_jsonl,
    get_git_hash,
    make_run_id,
    utc_now_iso,
)


@dataclass(frozen=True)
class ExoticTripwireConfig:
    input_run_id: str
    b_window: tuple[float, float]
    epsilon: float
    wec_floor: float
    nec_floor: float
    rho_budget_max: float
    scaling_limit_p_max: float
    score_w1: float
    score_w2: float
    score_w3: float
    notes: str
    write_registry: bool
    mirror_jsonl: bool


@dataclass(frozen=True)
class ExoticTripwireEvalConfig:
    b_window: tuple[float, float]
    epsilon: float = 1.0e-12
    wec_floor: float = 0.0
    nec_floor: float = 0.0
    rho_budget_max: float = 1.0e-3
    scaling_limit_p_max: float = 2.0
    score_w1: float = 1.0
    score_w2: float = 1.0
    score_w3: float = 1.0


class ExoticTripwireError(RuntimeError):
    """Raised when required input artifacts are missing or invalid."""


def _parse_window(window_raw: str) -> tuple[float, float]:
    token = str(window_raw).strip()
    parts = token.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid --b-window value: {window_raw}")
    lo = float(parts[0].strip())
    hi = float(parts[1].strip())
    if lo <= 0.0 or hi <= 0.0 or hi <= lo:
        raise ValueError(f"Invalid --b-window bounds: {window_raw}")
    return (lo, hi)


def _locate_input_curve_csv(run_dir: Path, input_run_id: str) -> Path:
    metrics_dir = run_dir / "metrics"
    if not metrics_dir.exists():
        raise ExoticTripwireError(f"Missing metrics directory for input_run_id={input_run_id}: {metrics_dir}")

    exact = metrics_dir / f"{input_run_id}_deflection_curve.csv"
    if exact.exists():
        return exact

    candidates = sorted(metrics_dir.glob("*_deflection_curve.csv"))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ExoticTripwireError(f"No *_deflection_curve.csv found under {metrics_dir}")
    raise ExoticTripwireError(
        f"Ambiguous deflection curve CSV under {metrics_dir}; expected exactly one candidate, found {len(candidates)}"
    )


def _read_theory_from_results_registry(registry_csv: Path, input_run_id: str) -> str:
    if not registry_csv.exists():
        return "unknown"
    with registry_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("run_id", "")) == input_run_id:
                return str(row.get("model_mode", "unknown"))
    return "unknown"


def _pick_field(names: set[str], candidates: list[str], *, label: str, csv_path: Path) -> str:
    for field in candidates:
        if field in names:
            return field
    raise ExoticTripwireError(f"Missing required {label} column in {csv_path}; tried {candidates}")


def _load_curve_arrays(csv_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = np.genfromtxt(csv_path, delimiter=",", names=True)
    names = set(data.dtype.names or ())
    b_field = _pick_field(names, ["b_over_m", "b"], label="b-grid", csv_path=csv_path)
    model_field = _pick_field(
        names,
        ["alpha_numeric_h", "alpha_numeric", "alpha_model"],
        label="model deflection",
        csv_path=csv_path,
    )
    ref_field = _pick_field(
        names,
        ["alpha_reference", "alpha_weakfield", "alpha_ref"],
        label="reference deflection",
        csv_path=csv_path,
    )
    b = np.asarray(data[b_field], dtype=float)
    alpha_model = np.asarray(data[model_field], dtype=float)
    alpha_ref = np.asarray(data[ref_field], dtype=float)
    if b.ndim != 1 or len(b) < 2:
        raise ExoticTripwireError(f"Need at least 2 curve points in {csv_path}")
    return (b, alpha_model, alpha_ref)


def _fit_scaling_power(b: np.ndarray, delta_abs: np.ndarray, b_window: tuple[float, float], epsilon: float) -> float:
    lo, hi = b_window
    mask = (b >= float(lo)) & (b <= float(hi))
    if int(np.sum(mask)) < 2:
        raise ExoticTripwireError(
            f"Need at least 2 points in b-window [{lo}, {hi}] for scaling fit; got {int(np.sum(mask))}"
        )
    x = np.log(b[mask])
    y = np.log(delta_abs[mask] + float(epsilon))
    slope = float(np.polyfit(x, y, 1)[0])
    return -slope


def evaluate_from_curves(
    *,
    b_over_m: np.ndarray,
    alpha_model: np.ndarray,
    alpha_ref: np.ndarray,
    config: ExoticTripwireEvalConfig,
) -> dict[str, Any]:
    """Evaluate tripwire proxies directly from model/reference deflection curves.

    This is a residual-space sensor only. It is not a proof of NEC/WEC violation.
    """
    try:
        b = np.asarray(b_over_m, dtype=float)
        am = np.asarray(alpha_model, dtype=float)
        ar = np.asarray(alpha_ref, dtype=float)
        if b.ndim != 1 or len(b) < 2:
            raise ExoticTripwireError("Need at least two b-grid points for tripwire evaluation.")
        if am.shape != ar.shape or am.shape != b.shape:
            raise ExoticTripwireError("Shape mismatch between b_over_m, alpha_model, and alpha_ref.")

        residual = am - ar
        delta = residual / np.maximum(np.abs(ar), float(config.epsilon))
        rho_proxy = np.asarray(delta, dtype=float)
        nec_proxy = np.minimum(rho_proxy, 0.0)
        delta_abs = np.abs(delta)

        scaling_power_p = _fit_scaling_power(
            b=b,
            delta_abs=delta_abs,
            b_window=config.b_window,
            epsilon=float(config.epsilon),
        )
        rho_proxy_min = float(np.min(rho_proxy))
        rho_proxy_max_abs = float(np.max(np.abs(rho_proxy)))
        nec_proxy_min = float(np.min(nec_proxy))
        wec_tripwire = bool(rho_proxy_min < -float(config.wec_floor))
        nec_tripwire = bool(nec_proxy_min < -float(config.nec_floor))
        scaling_tripwire = bool(float(scaling_power_p) > float(config.scaling_limit_p_max))
        rho_budget_tripwire = bool(float(rho_proxy_max_abs) > float(config.rho_budget_max))
        tripwire_pass = not (wec_tripwire or nec_tripwire or scaling_tripwire or rho_budget_tripwire)

        exoticity_score = (
            float(config.score_w1) * max(0.0, -rho_proxy_min)
            + float(config.score_w2) * max(0.0, -nec_proxy_min)
            + float(config.score_w3) * max(0.0, float(scaling_power_p) - float(config.scaling_limit_p_max))
        )
        return {
            "status": "OK",
            "tripwire_pass": bool(tripwire_pass),
            "wec_tripwire": bool(wec_tripwire),
            "nec_tripwire": bool(nec_tripwire),
            "scaling_tripwire": bool(scaling_tripwire),
            "rho_budget_tripwire": bool(rho_budget_tripwire),
            "exoticity_score": float(exoticity_score),
            "rho_proxy_min": float(rho_proxy_min),
            "rho_proxy_max_abs": float(rho_proxy_max_abs),
            "nec_proxy_min": float(nec_proxy_min),
            "scaling_power_p": float(scaling_power_p),
        }
    except Exception as exc:
        return {
            "status": "FAILED",
            "failure_code": type(exc).__name__,
            "failure_message": str(exc),
            "tripwire_pass": False,
            "wec_tripwire": False,
            "nec_tripwire": False,
            "scaling_tripwire": False,
            "exoticity_score": float("nan"),
            "rho_proxy_min": float("nan"),
            "nec_proxy_min": float("nan"),
            "scaling_power_p": float("nan"),
        }


class ExoticTripwire:
    """Namespace wrapper for sweep-time tripwire evaluation."""

    @staticmethod
    def evaluate_from_curves(
        *,
        b_over_m: np.ndarray,
        alpha_model: np.ndarray,
        alpha_ref: np.ndarray,
        config: ExoticTripwireEvalConfig,
    ) -> dict[str, Any]:
        return evaluate_from_curves(
            b_over_m=b_over_m,
            alpha_model=alpha_model,
            alpha_ref=alpha_ref,
            config=config,
        )


def run_exotic_tripwire(*, project_root: Path, config: ExoticTripwireConfig) -> dict[str, Any]:
    """Compute residual-derived exoticity tripwires from an existing deflection run."""
    timestamp_utc = utc_now_iso()
    run_id = make_run_id(
        model_mode="exotic_tripwire",
        k=config.input_run_id,
        n="NA",
        sigma="NA",
        connectivity="NA",
        field_exponent="NA",
        timestamp_utc=timestamp_utc,
    )
    run_dir = project_root / "results" / "artifacts" / run_id
    metrics_dir = run_dir / "metrics"
    raw_dir = run_dir / "raw"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    summary_path = raw_dir / f"{run_id}_exotic_tripwire_summary.json"
    traceback_path = raw_dir / f"{run_id}_traceback.txt"
    metrics_path = metrics_dir / f"{run_id}_exotic_tripwire_metrics.csv"

    summary_started: dict[str, Any] = {
        "status": "STARTED",
        "timestamp_utc": timestamp_utc,
        "run_id": run_id,
        "input_run_id": config.input_run_id,
        "tripwire_kind": "exotic_stress_energy_energy_condition_violation_test",
        "disclaimer": (
            "Tripwire only. This is not a proof of NEC/WEC violation; proxies are derived "
            "from residual structure and scaling without a full metric+tensor reconstruction."
        ),
        "notes": config.notes or "NA",
    }
    summary_path.write_text(json.dumps(summary_started, indent=2, ensure_ascii=True), encoding="utf-8")

    try:
        input_run_dir = project_root / "results" / "artifacts" / config.input_run_id
        if not input_run_dir.exists():
            raise ExoticTripwireError(f"Missing input run directory: {input_run_dir}")
        curve_csv_path = _locate_input_curve_csv(input_run_dir, config.input_run_id)
        b, alpha_model, alpha_ref = _load_curve_arrays(curve_csv_path)

        residual = alpha_model - alpha_ref
        delta = residual / np.maximum(np.abs(alpha_ref), float(config.epsilon))
        rho_proxy = np.asarray(delta, dtype=float)
        nec_proxy = np.minimum(rho_proxy, 0.0)
        delta_abs = np.abs(delta)
        scaling_power_p = _fit_scaling_power(
            b=b,
            delta_abs=delta_abs,
            b_window=config.b_window,
            epsilon=float(config.epsilon),
        )

        rho_proxy_min = float(np.min(rho_proxy))
        rho_proxy_max_abs = float(np.max(np.abs(rho_proxy)))
        nec_proxy_min = float(np.min(nec_proxy))
        wec_tripwire = bool(rho_proxy_min < -float(config.wec_floor))
        nec_tripwire = bool(nec_proxy_min < -float(config.nec_floor))
        scaling_tripwire = bool(float(scaling_power_p) > float(config.scaling_limit_p_max))
        rho_budget_tripwire = bool(float(rho_proxy_max_abs) > float(config.rho_budget_max))
        tripwire_pass = not (wec_tripwire or nec_tripwire or scaling_tripwire or rho_budget_tripwire)

        exoticity_score = (
            float(config.score_w1) * max(0.0, -rho_proxy_min)
            + float(config.score_w2) * max(0.0, -nec_proxy_min)
            + float(config.score_w3) * max(0.0, float(scaling_power_p) - float(config.scaling_limit_p_max))
        )

        in_window = ((b >= float(config.b_window[0])) & (b <= float(config.b_window[1]))).astype(int)
        metrics_table = np.column_stack(
            [b, alpha_model, alpha_ref, residual, delta, rho_proxy, nec_proxy, in_window.astype(float)]
        )
        np.savetxt(
            metrics_path,
            metrics_table,
            delimiter=",",
            header="b_over_m,alpha_model,alpha_ref,residual,delta,rho_proxy,nec_proxy,in_scaling_window",
            comments="",
        )

        theory = _read_theory_from_results_registry(
            project_root / "results" / "registry" / "results_registry.csv",
            config.input_run_id,
        )
        rel_metrics = str(metrics_path.resolve().relative_to(project_root.resolve()).as_posix())
        rel_summary = str(summary_path.resolve().relative_to(project_root.resolve()).as_posix())
        artifacts = [rel_metrics, rel_summary]

        summary_done: dict[str, Any] = {
            "status": "OK",
            "timestamp_utc": timestamp_utc,
            "run_id": run_id,
            "input_run_id": config.input_run_id,
            "theory": theory,
            "tripwire_kind": "exotic_stress_energy_energy_condition_violation_test",
            "disclaimer": summary_started["disclaimer"],
            "tripwire_pass": bool(tripwire_pass),
            "wec_tripwire": bool(wec_tripwire),
            "nec_tripwire": bool(nec_tripwire),
            "scaling_tripwire": bool(scaling_tripwire),
            "rho_budget_tripwire": bool(rho_budget_tripwire),
            "rho_proxy_min": float(rho_proxy_min),
            "rho_proxy_max_abs": float(rho_proxy_max_abs),
            "nec_proxy_min": float(nec_proxy_min),
            "scaling_power_p": float(scaling_power_p),
            "scaling_limit_p_max": float(config.scaling_limit_p_max),
            "exoticity_score": float(exoticity_score),
            "thresholds": {
                "wec_floor": float(config.wec_floor),
                "nec_floor": float(config.nec_floor),
                "rho_budget_max": float(config.rho_budget_max),
                "epsilon": float(config.epsilon),
                "b_window": [float(config.b_window[0]), float(config.b_window[1])],
            },
            "weights": {
                "w1": float(config.score_w1),
                "w2": float(config.score_w2),
                "w3": float(config.score_w3),
            },
            "artifacts": artifacts,
            "notes": config.notes or "NA",
            "source_curve_csv": str(curve_csv_path.resolve().relative_to(project_root.resolve()).as_posix()),
        }
        summary_path.write_text(json.dumps(summary_done, indent=2, ensure_ascii=True), encoding="utf-8")

        if config.write_registry:
            reg_row = {
                "timestamp_utc": timestamp_utc,
                "run_id": run_id,
                "input_run_id": config.input_run_id,
                "git_hash": get_git_hash(),
                "theory": theory,
                "tripwire_pass": bool(tripwire_pass),
                "wec_tripwire": bool(wec_tripwire),
                "nec_tripwire": bool(nec_tripwire),
                "scaling_tripwire": bool(scaling_tripwire),
                "rho_proxy_min": float(rho_proxy_min),
                "rho_proxy_max_abs": float(rho_proxy_max_abs),
                "nec_proxy_min": float(nec_proxy_min),
                "scaling_power_p": float(scaling_power_p),
                "scaling_limit_p_max": float(config.scaling_limit_p_max),
                "exoticity_score": float(exoticity_score),
                "artifacts": ";".join(artifacts),
                "notes": config.notes or "NA",
            }
            reg_dir = project_root / "results" / "registry"
            append_csv_row(reg_dir / "exotic_tripwire_registry.csv", EXOTIC_TRIPWIRE_REGISTRY_COLUMNS, reg_row)
            if config.mirror_jsonl:
                append_jsonl(reg_dir / "exotic_tripwire_registry.jsonl", reg_row)
        return summary_done
    except Exception as exc:
        tb = traceback.format_exc()
        traceback_path.write_text(tb, encoding="utf-8")
        failure = {
            **summary_started,
            "status": "FAILED",
            "failure_code": type(exc).__name__,
            "failure_message": str(exc),
            "traceback_path": str(traceback_path.resolve().relative_to(project_root.resolve()).as_posix()),
        }
        summary_path.write_text(json.dumps(failure, indent=2, ensure_ascii=True), encoding="utf-8")
        raise

