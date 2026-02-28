"""Shared helpers for certification tests."""

from __future__ import annotations

import hashlib
import json
import traceback
from pathlib import Path
from typing import Any, Callable

from scripts.sweep_ppn_constraints import run_ppn_sweep

PASS = "PASS"
FAIL = "FAIL"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 64)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def stable_hash(data: Any) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_sweep(config: dict[str, Any], out_dir: Path, notes_suffix: str) -> dict[str, Any]:
    """Execute ppn sweep and return resolved artifact paths."""
    row = run_ppn_sweep(
        project_root=out_dir,
        gamma_min=float(config["gamma_min"]),
        gamma_max=float(config["gamma_max"]),
        gamma_steps=int(config["gamma_steps"]),
        wf_thresh_seq=[float(x) for x in config["wf_thresh_seq"]],
        range_windows=[(float(w[0]), float(w[1])) for w in config["range_windows"]],
        n_points=int(config["n_points"]),
        h=float(config["h"]),
        wf_ref_mode=str(config.get("wf_ref_mode", "analytic")),
        wf_eps_denom=float(config.get("wf_eps_denom", 1.0e-15)),
        tail_eps_abs=float(config.get("tail_eps_abs", 1.0e-6)),
        tail_eps_rel=float(config.get("tail_eps_rel", 0.01)),
        tail_sign_k=int(config.get("tail_sign_k", 20)),
        min_tail_significant=int(config.get("min_tail_significant", 8)),
        tail_sign_mode=str(config.get("tail_sign_mode", "binomial")),
        tail_sign_alpha=float(config.get("tail_sign_alpha", 0.05)),
        notes=f"certification:{notes_suffix}",
        mirror_jsonl=True,
        full_throttle=bool(config.get("full_throttle", False)),
        telemetry=bool(config.get("telemetry", False)),
        telemetry_seconds=float(config.get("telemetry_seconds", 2.0)),
        max_workers=int(config["max_workers"]) if config.get("max_workers") is not None else None,
        plots=bool(config.get("plots", False)),
    )
    run_id = str(row["run_id"])
    run_dir = out_dir / "results" / "artifacts" / run_id
    metrics_dir = run_dir / "metrics"
    raw_dir = run_dir / "raw"
    return {
        "row": row,
        "run_id": run_id,
        "run_dir": run_dir,
        "metrics_results_csv": metrics_dir / f"{run_id}_ppn_sweep_results.csv",
        "metrics_survivors_csv": metrics_dir / f"{run_id}_ppn_survivors.csv",
        "summary_json": raw_dir / f"{run_id}_ppn_sweep_summary.json",
        "promotion_json": raw_dir / f"{run_id}_promotion_eval.json",
        "command": "python -m scripts.sweep_ppn_constraints (import call via run_ppn_sweep)",
    }


def fail_result(details: str, failure_codes: list[str], metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": FAIL,
        "details": details,
        "failure_codes": failure_codes,
        "metrics": metrics or {},
        "artifacts": [],
    }


def guard_run(fn: Callable[[], dict[str, Any]], code_on_exception: str) -> dict[str, Any]:
    try:
        return fn()
    except Exception as exc:
        return fail_result(
            details=f"Unhandled exception: {exc}",
            failure_codes=[code_on_exception],
            metrics={"traceback": traceback.format_exc()},
        )

