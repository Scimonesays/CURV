"""Append-only registry helpers for CURV trial and batch evidence logs."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
RESULTS_REGISTRY_COLUMNS = [
    "timestamp_utc",
    "run_id",
    "batch_id",
    "git_hash",
    "model_mode",
    "k",
    "sigma",
    "N",
    "connectivity",
    "field_exponent",
    "r2_inv",
    "r2_lin",
    "delta_r2",
    "aic_inv",
    "aic_lin",
    "superposition_median_rel_error",
    "resolution_mean_curve_diff",
    "gateA_scaling_pass",
    "gateA_superposition_pass",
    "gateA_resolution_pass",
    "gateA_pass",
    "artifacts",
    "notes",
]
BATCH_REGISTRY_COLUMNS = [
    "timestamp_utc",
    "batch_id",
    "git_hash",
    "model_mode",
    "weak_k_definition",
    "run_ids",
    "n_runs",
    "n_weak_k_runs",
    "scaling_min_delta_r2",
    "scaling_n_pass",
    "gateA_scaling_pass",
    "gateA_superposition_pass_rate",
    "gateA_resolution_pass_rate",
    "gateA_pass",
    "artifacts",
    "notes",
]
CONSTRAINTS_REGISTRY_COLUMNS = [
    "timestamp_utc",
    "run_id",
    "batch_id",
    "git_hash",
    "gamma",
    "alpha",
    "lambda_au",
    "n_constraints",
    "n_pass",
    "all_pass",
    "mean_residual_rel",
    "max_residual_rel",
    "excluded_fraction",
    "allowed_fraction",
    "artifacts",
    "notes",
]


def utc_now_iso() -> str:
    """Return UTC timestamp in ISO8601 with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_git_hash() -> str:
    """Return short git hash if repository is available, otherwise nogit."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT_DIR,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "nogit"
    except Exception:
        return "nogit"


def _safe_token(value: Any) -> str:
    if value is None:
        return "na"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))


def _fmt_number_token(value: float | int | str | None) -> str:
    if value is None or value == "NA":
        return "NA"
    if isinstance(value, str):
        return _safe_token(value)
    if isinstance(value, int):
        return str(value)
    return f"{value:.6g}".replace(".", "p")


def make_run_id(
    model_mode: str,
    k: float | str | None,
    n: int | str | None,
    sigma: float | str | None,
    connectivity: int | str | None,
    field_exponent: float | str | None,
    timestamp_utc: str | None = None,
) -> str:
    """Build deterministic run id from timestamp + parameter tokens."""
    ts = timestamp_utc or utc_now_iso()
    ts_token = ts.replace("-", "").replace(":", "").replace("T", "_")
    return (
        f"{ts_token}_{_safe_token(model_mode)}"
        f"_k{_fmt_number_token(k)}"
        f"_N{_fmt_number_token(n)}"
        f"_sig{_fmt_number_token(sigma)}"
        f"_conn{_fmt_number_token(connectivity)}"
        f"_exp{_fmt_number_token(field_exponent)}"
    )


def make_batch_id(
    model_mode: str,
    weak_k_definition: str,
    timestamp_utc: str | None = None,
) -> str:
    """Build deterministic batch id."""
    ts = timestamp_utc or utc_now_iso()
    ts_token = ts.replace("-", "").replace(":", "").replace("T", "_")
    return f"{ts_token}_{_safe_token(model_mode)}_{_safe_token(weak_k_definition)}"


def make_constraints_run_id(
    gamma: float | str | None,
    alpha: float | str | None,
    lambda_au: float | str | None,
    timestamp_utc: str | None = None,
) -> str:
    """Build deterministic Phase 4B run id."""
    ts = timestamp_utc or utc_now_iso()
    ts_token = ts.replace("-", "").replace(":", "").replace("T", "_")
    return (
        f"{ts_token}_phase4b"
        f"_g{_fmt_number_token(gamma)}"
        f"_a{_fmt_number_token(alpha)}"
        f"_lam{_fmt_number_token(lambda_au)}"
    )


def ensure_registry_headers(csv_path: Path, columns: list[str]) -> None:
    """Create CSV with exact header if missing or empty."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)


def _normalize_row(columns: list[str], row_dict: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in columns:
        value = row_dict.get(key, "NA")
        if value is None:
            normalized[key] = "NA"
        elif isinstance(value, (list, tuple)):
            normalized[key] = ";".join(str(v) for v in value)
        else:
            normalized[key] = value
    return normalized


def append_csv_row(csv_path: Path, columns: list[str], row_dict: dict[str, Any]) -> None:
    """Append one row in strict column order."""
    ensure_registry_headers(csv_path=csv_path, columns=columns)
    row = _normalize_row(columns=columns, row_dict=row_dict)
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writerow(row)


def append_jsonl(jsonl_path: Path, row_dict: dict[str, Any]) -> None:
    """Append one JSON row for optional registry mirror."""
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row_dict, ensure_ascii=True) + "\n")

