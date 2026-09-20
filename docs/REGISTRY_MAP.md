# Registry Map

All registries live under `results/registry/`. Each has a `.csv` and `.jsonl` mirror (except where noted). Files are created on first write.

---

## Registry Index

| Registry | Path | Writer Script | Lane |
|----------|------|---------------|------|
| results_registry | `results_registry.csv` / `.jsonl` | `run_theory_deflection.py`, `run_deflection_curve.py`, `sweep_ppn_constraints.py`, `sweep_yukawa_constraints.py`, `run_source_plausibility.py`, `trial_pipeline` | Theory Validation, Exotic Feasibility |
| constraints_registry | `constraints_registry.csv` / `.jsonl` | `trial_pipeline` (Phase 4B) | Theory Validation |
| ufo_observable_registry | `ufo_observable_registry.csv` / `.jsonl` | `run_ufo_observable_eval.py` | Claim Evaluation |
| ufo_behavior_registry | `ufo_behavior_registry.csv` / `.jsonl` | `run_ufo_behavior_eval.py` | Claim Evaluation |
| exotic_tripwire_registry | `exotic_tripwire_registry.csv` / `.jsonl` | `run_exotic_tripwire.py` | Exotic Feasibility |
| bubble_registry | `bubble_registry.csv` / `.jsonl` | `run_bubble_experiment_analysis.py` | Exotic Feasibility |
| breakthrough_ladder_registry | `breakthrough_ladder_registry.csv` / `.jsonl` | `run_breakthrough_ladder.py` | Claim Evaluation |
| batch_registry | `batch_registry.csv` / `.jsonl` | `finalize_batch.py` (via `trial_pipeline`) | Theory Validation |
| ufs_validation_registry | `ufs_validation_registry.csv` / `.jsonl` | `run_ufs_candidate_validation.py` | UFS Research Validation |

---

## Row Schema Summaries

### results_registry

Theory runs, source plausibility, deflection curves, PPN/Yukawa sweeps.

| Column | Description |
|--------|-------------|
| timestamp_utc | ISO8601 UTC |
| run_id | Deterministic run identifier |
| batch_id | Optional campaign grouping |
| git_hash | Short HEAD hash |
| model_mode | e.g. `gr_schwarzschild`, `ppn_sweep`, `yukawa_sweep`, `energy_source_plausibility` |
| k, sigma, N, connectivity, field_exponent | Theory/run params (or NA) |
| superposition_median_rel_error, resolution_mean_curve_diff | Gate 0 metrics |
| gateA_*_pass | Gate verdicts |
| artifacts | Semicolon-separated relative paths |
| notes | Compact namespaced summaries (`gate0:`, `ppn_sweep:`, `curv_cost:`, etc.) |

### constraints_registry

Phase 4B observable constraints.

| Column | Description |
|--------|-------------|
| timestamp_utc, run_id, batch_id, git_hash | Identifiers |
| gamma, alpha, lambda_au | PPN/Yukawa params |
| n_constraints, n_pass, all_pass | Constraint counts |
| mean_residual_rel, max_residual_rel | Residual metrics |
| excluded_fraction, allowed_fraction | Grid fractions |
| artifacts, notes | Artifacts and notes |

### ufo_observable_registry

UFO observable evaluation runs.

| Column | Description |
|--------|-------------|
| timestamp_utc, run_id, git_hash | Identifiers |
| profile | e.g. `tictac_like`, `hypersonic_no_boom` |
| policy | `strict`, `normal`, `sandbox` |
| verdict | `physically_implausible_*`, `requires_speculative_*`, `consistent_with_*` |
| n_failed_gates | Count of failed gates |
| mass_kg_min, mass_kg_max | Mass range |
| artifacts, notes | Artifacts and notes |

### ufo_behavior_registry

UFO flight-behavior evaluation runs.

| Column | Description |
|--------|-------------|
| timestamp_utc, run_id, git_hash | Identifiers |
| profile, policy | Same as observable |
| verdict | Overall verdict |
| mass_kg_min, mass_kg_max | Mass range |
| top_conflicts | Summary of conflicts |
| artifacts, notes | Artifacts and notes |

### exotic_tripwire_registry

Exotic stress-energy tripwire runs (WEC/NEC proxy).

| Column | Description |
|--------|-------------|
| timestamp_utc, run_id, input_run_id, git_hash | Identifiers |
| theory | Source theory (e.g. from results_registry) |
| tripwire_pass | Overall pass/fail |
| wec_tripwire, nec_tripwire, scaling_tripwire | Individual tripwires |
| rho_proxy_min, rho_proxy_max_abs, nec_proxy_min | Density proxies |
| exoticity_score | Composite score |
| artifacts, notes | Artifacts and notes |

### bubble_registry

Bubble experiment feasibility analysis.

| Column | Description |
|--------|-------------|
| timestamp_utc, run_id, git_hash | Identifiers |
| bubble_radius_m | Bubble radius (m) |
| instrument | `interferometer`, `atomic_clock`, etc. |
| power_w, duration_s | Power and duration |
| curvature_m2_inv | Curvature scale |
| verdict, bubble_feasible | Verdict and feasibility flag |
| dominant_failure_reason | Primary failure reason |
| allow_speculative | Speculative mode flag |
| artifacts, notes | Artifacts and notes |

### breakthrough_ladder_registry

Breakthrough ladder runs (multi-step UFO tests).

| Column | Description |
|--------|-------------|
| timestamp_utc, run_id, git_hash | Identifiers |
| policy | `strict`, `normal`, `sandbox` |
| mass_kg_min, mass_kg_max | Mass range |
| deepest_step | Highest step passed without speculation |
| first_fail_step | First failing step |
| artifacts, notes | Artifacts and notes |

### ufs_validation_registry

Universal Frequency Spectrum structural-readiness runs.

| Column | Description |
|--------|-------------|
| timestamp_utc, run_id, git_hash | Identifiers |
| ufs_record_id | Canonical UFS target ID |
| record_type | Frontier or gap |
| canonical_status | UFS status at validation time |
| policy, speculative_mode | CURV policy context |
| readiness_verdict | `READY_FOR_CONSTRAINT_DESIGN`, `NEEDS_OPERATIONALIZATION`, or `HOLD_EVIDENCE` |
| n_pass, n_fail, failed_gates | Structural readiness gate summary |
| artifacts, notes | Reproducible result artifact and semantic warning |

### batch_registry

Batch verdicts from trial aggregation.

| Column | Description |
|--------|-------------|
| timestamp_utc, batch_id, git_hash | Identifiers |
| model_mode, weak_k_definition | Batch params |
| run_ids | Semicolon-separated trial run_ids |
| n_runs, n_weak_k_runs | Counts |
| gateA_* | Aggregate gate verdicts |
| artifacts, notes | Artifacts and notes |

---

## Artifact-Only (Not Indexed)

Some outputs are written to `results/artifacts/<run_id>/` but do not have a dedicated registry:

- **Source phase map** — `run_source_phase_map.py` writes to artifacts; summary can be inferred from run_id in notes.
- **Exotic tripwire atlas** — CSV/plots under sweep artifacts; indexed via `exotic_tripwire_registry` when run standalone.

See [PROGRAM_PURPOSE.md](PROGRAM_PURPOSE.md) for lane definitions.
