"""Launch catalog: allowed scripts + form field schemas (no physics duplication)."""

from __future__ import annotations

from typing import Any

CATALOG: dict[str, dict[str, Any]] = {
    "sweep_ppn": {
        "label": "PPN constraints sweep",
        "lane": "theory",
        "script": "scripts/sweep_ppn_constraints.py",
        "preset": "pilot",
        "fields": [
            {"name": "gamma_min", "flag": "--gamma-min", "type": "float", "default": 0.98},
            {"name": "gamma_max", "flag": "--gamma-max", "type": "float", "default": 1.02},
            {"name": "gamma_steps", "flag": "--gamma-steps", "type": "int", "default": 9},
            {"name": "wf_thresh_seq", "flag": "--wf-thresh-seq", "type": "str", "default": "0.25,0.15,0.10"},
            {"name": "use_exotic_tripwire_gate", "flag": "--use-exotic-tripwire-gate", "type": "bool", "default": False},
        ],
    },
    "sweep_yukawa": {
        "label": "Yukawa constraints sweep",
        "lane": "theory",
        "script": "scripts/sweep_yukawa_constraints.py",
        "preset": "pilot_11x9",
        "fields": [
            {"name": "alpha_min", "flag": "--alpha-min", "type": "float", "default": -0.10},
            {"name": "alpha_max", "flag": "--alpha-max", "type": "float", "default": 0.10},
            {"name": "alpha_steps", "flag": "--alpha-steps", "type": "int", "default": 11},
            {"name": "lambda_min", "flag": "--lambda-min", "type": "float", "default": 1.0},
            {"name": "lambda_max", "flag": "--lambda-max", "type": "float", "default": 1000.0},
            {"name": "lambda_steps", "flag": "--lambda-steps", "type": "int", "default": 9},
            {"name": "lambda_spacing", "flag": "--lambda-spacing", "type": "choice", "choices": ["log", "linear"], "default": "log"},
            {"name": "use_exotic_tripwire_gate", "flag": "--use-exotic-tripwire-gate", "type": "bool", "default": False},
            {"name": "no_plots", "flag": "--no-plots", "type": "bool", "default": False},
        ],
    },
    "theory_deflection": {
        "label": "Theory deflection",
        "lane": "theory",
        "script": "scripts/run_theory_deflection.py",
        "fields": [
            {"name": "theory", "flag": "--theory", "type": "choice", "choices": ["gr_schwarzschild", "gr_yukawa_deviation", "gr_ppn_screened_potential"], "default": "gr_schwarzschild"},
            {"name": "alpha_y", "flag": "--alpha-y", "type": "float", "default": 0.0},
            {"name": "lambda_y_over_m", "flag": "--lambda-y-over-m", "type": "float", "default": 100.0},
            {"name": "gamma_ppn", "flag": "--gamma-ppn", "type": "float", "default": 1.0},
        ],
    },
    "ufo_observable": {
        "label": "UFO observable eval",
        "lane": "claims",
        "script": "scripts/run_ufo_observable_eval.py",
        "fields": [
            {"name": "profile", "flag": "--profile", "type": "choice", "choices": ["tictac_like", "hypersonic_no_boom", "edgecase_hypersonic_no_boom", "plausible_moderate"], "default": "tictac_like"},
            {"name": "mass_kg_min", "flag": "--mass-kg-min", "type": "float", "default": 100.0},
            {"name": "mass_kg_max", "flag": "--mass-kg-max", "type": "float", "default": 10000.0},
            {"name": "allow_speculative", "flag": "--allow-speculative", "type": "bool", "default": False, "speculative": True},
            {"name": "enable_element_x", "flag": "--enable-element-x", "type": "bool", "default": False},
        ],
        "inject_policy": True,
    },
    "ufo_behavior": {
        "label": "UFO behavior eval",
        "lane": "claims",
        "script": "scripts/run_ufo_behavior_eval.py",
        "fields": [
            {"name": "mass_kg_min", "flag": "--mass-kg-min", "type": "float", "default": 100.0},
            {"name": "mass_kg_max", "flag": "--mass-kg-max", "type": "float", "default": 10000.0},
            {"name": "transmedium", "flag": "--transmedium", "type": "bool", "default": False},
        ],
        "inject_policy": True,
    },
    "breakthrough_ladder": {
        "label": "Breakthrough ladder",
        "lane": "claims",
        "script": "scripts/run_breakthrough_ladder.py",
        "fields": [
            {"name": "mass_kg_min", "flag": "--mass-kg-min", "type": "float", "default": 100.0},
            {"name": "mass_kg_max", "flag": "--mass-kg-max", "type": "float", "default": 10000.0},
            {"name": "include_speculative_step", "flag": "--include-speculative-step", "type": "bool", "default": False, "speculative": True},
        ],
        "inject_policy": True,
    },
    "exotic_tripwire": {
        "label": "Exotic tripwire",
        "lane": "exotic",
        "script": "scripts/run_exotic_tripwire.py",
        "fields": [
            {"name": "input_run_id", "flag": "--input-run-id", "type": "str", "default": "", "required": True},
            {"name": "b_window", "flag": "--b-window", "type": "str", "default": "100:1000"},
            {"name": "rho_budget_max", "flag": "--rho-budget-max", "type": "float", "default": 1.0e-3},
            {"name": "scaling_limit_p_max", "flag": "--scaling-limit-p-max", "type": "float", "default": 2.0},
        ],
    },
    "source_phase_map": {
        "label": "Source phase map",
        "lane": "exotic",
        "script": "scripts/run_source_phase_map.py",
        "unindexed": True,
        "fields": [
            {"name": "power_min_w", "flag": "--power-min-w", "type": "float", "default": 1.0e4},
            {"name": "power_max_w", "flag": "--power-max-w", "type": "float", "default": 1.0e9},
            {"name": "power_steps", "flag": "--power-steps", "type": "int", "default": 31},
            {"name": "duration_min_s", "flag": "--duration-min-s", "type": "float", "default": 1.0e2},
            {"name": "duration_max_s", "flag": "--duration-max-s", "type": "float", "default": 1.0e5},
            {"name": "duration_steps", "flag": "--duration-steps", "type": "int", "default": 25},
            {"name": "active_radius_m", "flag": "--active-radius-m", "type": "float", "default": 10.0},
            {"name": "curvature_cal", "flag": "--curvature-cal", "type": "float", "default": 2.08e-43},
            {"name": "k_target_10m", "flag": "--k-target-10m", "type": "float", "default": 1.0e-2},
            {"name": "k_target_1km", "flag": "--k-target-1km", "type": "float", "default": 1.0e-6},
            {"name": "allow_speculative_exotic", "flag": "--allow-speculative-exotic", "type": "bool", "default": False, "speculative": True},
        ],
    },
    "bubble_analysis": {
        "label": "Bubble experiment analysis",
        "lane": "exotic",
        "script": "scripts/run_bubble_experiment_analysis.py",
        "fields": [
            {"name": "radius_m", "flag": "--radius-m", "type": "float", "default": 1.0},
            {"name": "transmedium", "flag": "--transmedium", "type": "bool", "default": False},
            {"name": "allow_speculative", "flag": "--allow-speculative", "type": "bool", "default": False, "speculative": True},
        ],
        "inject_policy": True,
    },
    "certification": {
        "label": "Certification C1–C6",
        "lane": "certification",
        "script": "certification/run_certification.py",
        "fields": [],
    },
    "instrument_hold": {
        "label": "Instrument hold (SSE/cancel check)",
        "lane": "theory",
        "script": "console/scripts/instrument_hold.py",
        "fields": [
            {"name": "seconds", "flag": "--seconds", "type": "float", "default": 45.0},
            {"name": "fail", "flag": "--fail", "type": "bool", "default": False},
        ],
    },
}


def list_catalog(lane: str | None = None) -> list[dict[str, Any]]:
    items = []
    for key, meta in CATALOG.items():
        if lane and meta.get("lane") != lane:
            continue
        items.append({"id": key, **{k: v for k, v in meta.items() if k != "script"}, "script": meta["script"]})
    return items


def build_argv(
    catalog_id: str,
    params: dict[str, Any],
    *,
    policy: str,
    speculative: bool,
    python_exe: str,
) -> tuple[list[str], str, bool]:
    """Return (argv, script_rel, speculative_effective)."""
    if catalog_id not in CATALOG:
        raise KeyError(f"Unknown catalog id: {catalog_id}")
    meta = CATALOG[catalog_id]
    script_rel = meta["script"]
    from .paths import REPO_ROOT

    script_path = str((REPO_ROOT / script_rel).resolve())
    argv: list[str] = [python_exe, script_path]
    speculative_effective = bool(speculative)

    if meta.get("inject_policy"):
        argv.extend(["--policy", policy])

    for field in meta.get("fields") or []:
        name = field["name"]
        flag = field["flag"]
        ftype = field["type"]
        if name not in params and "default" in field:
            value = field["default"]
        else:
            value = params.get(name, field.get("default"))
        if field.get("required") and (value is None or value == ""):
            raise ValueError(f"Missing required field: {name}")
        if ftype == "bool":
            truthy = bool(value) and str(value).lower() not in ("0", "false", "no", "")
            if field.get("speculative") and truthy:
                speculative_effective = True
            if truthy:
                argv.append(flag)
            continue
        if value is None or value == "":
            continue
        argv.extend([flag, str(value)])

    # Global speculative: if UI says YES but script has allow flag and not set, inject common flags
    if speculative and catalog_id == "ufo_observable" and "--allow-speculative" not in argv:
        argv.append("--allow-speculative")
        speculative_effective = True
    if speculative and catalog_id == "breakthrough_ladder" and "--include-speculative-step" not in argv:
        argv.append("--include-speculative-step")
        speculative_effective = True
    if speculative and catalog_id == "source_phase_map" and "--allow-speculative-exotic" not in argv:
        argv.append("--allow-speculative-exotic")
        speculative_effective = True

    return argv, script_rel, speculative_effective
