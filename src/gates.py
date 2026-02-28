"""Gate computations for strict append-only CURV evidence trail."""

from __future__ import annotations

from typing import Any, Callable


def compute_superposition_gate(median_rel_error: float) -> bool:
    return float(median_rel_error) < 0.25


def compute_resolution_gate(mean_curve_diff: float) -> bool:
    return float(mean_curve_diff) < 0.15


def compute_scaling_gate(delta_r2_list: list[float]) -> tuple[bool, int, float | str]:
    valid = [float(x) for x in delta_r2_list]
    if not valid:
        return False, 0, "NA"
    n_pass = sum(1 for d in valid if d >= 0.05)
    return n_pass >= 2, n_pass, float(min(valid))


def _to_float(value: Any) -> float | None:
    if value in (None, "", "NA"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, "", "NA"):
        return None
    text = str(value).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    return None


def compute_batch_verdict(
    runs_df_or_rows: list[dict[str, Any]],
    weak_k_filter: Callable[[float], bool],
) -> dict[str, Any]:
    weak_deltas: list[float] = []
    super_flags: list[bool] = []
    res_flags: list[bool] = []
    run_ids: list[str] = []

    for row in runs_df_or_rows:
        run_ids.append(str(row.get("run_id", "NA")))
        k_value = _to_float(row.get("k"))
        delta = _to_float(row.get("delta_r2"))
        if k_value is not None and delta is not None and weak_k_filter(k_value):
            weak_deltas.append(delta)
        sp = _to_bool(row.get("gateA_superposition_pass"))
        rp = _to_bool(row.get("gateA_resolution_pass"))
        if sp is not None:
            super_flags.append(sp)
        if rp is not None:
            res_flags.append(rp)

    scaling_pass, n_pass, min_delta = compute_scaling_gate(weak_deltas)
    super_rate = (sum(1 for x in super_flags if x) / len(super_flags)) if super_flags else 0.0
    res_rate = (sum(1 for x in res_flags if x) / len(res_flags)) if res_flags else 0.0
    gate_pass = bool(scaling_pass and super_rate == 1.0 and res_rate == 1.0)

    return {
        "run_ids": ";".join(run_ids),
        "n_runs": len(runs_df_or_rows),
        "n_weak_k_runs": len(weak_deltas),
        "scaling_min_delta_r2": min_delta,
        "scaling_n_pass": n_pass,
        "gateA_scaling_pass": scaling_pass,
        "gateA_superposition_pass_rate": float(super_rate),
        "gateA_resolution_pass_rate": float(res_rate),
        "gateA_pass": gate_pass,
    }

