# CURV

## Constraint-Unified Residual Validator

CURV is a deterministic constraint engine for validating gravitational residual structure against unified physical limits.

It does not generate new physics.
It eliminates inconsistent deviations.

Formal framing is available in `WHITEPAPER.md`.

**Run Log:**
All constraint sweeps and promotion evaluations are recorded in `CURV_RUN_LOG.md`.
Structural rules are versioned and frozen unless explicitly revised.

### Quick Public Baseline

* **What CURV is:** a reproducible, falsifier-first instrument for constraint-based gravity deviation testing.
* **What CURV is not:** evidence of new physics, propulsion claims, or anomaly interpretation.
* **Reproduce certification:** `python certification/run_certification.py`
* **Certified tags:** `v0.1.0-certified` (original Tier-1 anchor), `v0.1.1-certified` (publication-clean baseline with tests + docs).

**Regenerate Source Regime Atlas (power-vs-duration map)**
```powershell
python scripts/run_source_phase_map.py `
  --power-min-w 1e4 --power-max-w 1e9 --power-steps 31 `
  --duration-min-s 1e2 --duration-max-s 1e5 --duration-steps 25 `
  --active-radius-m 10 `
  --curvature-cal 2.08e-43 `
  --k-target-10m 1e-2 `
  --k-target-1km 1e-6
```

---

## Identity

CURV evaluates parameterized gravitational deviations by enforcing:

* Numeric GR baselines
* Weak-field consistency
* Resolution stability
* Observational thresholds
* Energy scaling sanity

Residuals are not assumed meaningful.
They must survive tightening.

---

## What CURV Does

CURV provides a reproducible framework to:

* Simulate Schwarzschild null geodesic baselines.
* Inject controlled deviation models (Yukawa, PPN-like).
* Measure structural residual behavior.
* Apply deterministic promotion criteria.
* Shrink allowable parameter space.

All results are:

* Seed-fixed
* Logged
* Artifact-saved
* Commit-traceable

---

## What CURV Is Not

* Not proof of new physics
* Not a propulsion platform
* Not an anomaly detector
* Not an energy research project

It is a falsifier-first validation instrument.

---

## Core Question

> What minimum structural properties must any viable gravity extension reproduce?

CURV answers by constraint reduction, not speculation.

---

## Long-Term Aim

* Harden gravitational hypothesis testing.
* Map survivable deviation regions.
* Identify degeneracy structure.
* Provide an auditable computational lab for constraint-driven gravity analysis.

Not to overthrow GR.
To test its boundaries rigorously.

---

# Architecture Overview

CURV operates in layered validation phases.

---

## Constraint Pipeline (Execution Order)

This is the practical run order used by sweep-time constraint evaluation:

```text
[START: parameter point θ, window W, threshold wf_thresh]

   |
   v
(0) Generate curves / residuals / derived metrics

   |
   v
(1) Gate 0  ✅ HARD GATE (earliest kill)
    A) Weak-field tail median rel error   < wf_thresh
    B) Resolution consistency (h vs h/2)  < 0.15
    C) Known-limit recovery (model→GR)    < 0.05
    -> if FAIL: stop this (θ,W,wf_thresh)

   |
   v
(2) Residual-structure checks  ✅ PROMOTION CHECKS (Candidate/Strong)
    - oscillation control (sign_changes <= 1)        [candidate]
    - local smoothness / anti-knife-edge metrics     [candidate/strong]
    - endpoint dominance ratio < 0.95                [strong-only]
    NOTE: "adjacent survivor / non_knife_edge_region"
          is NOT used here; it is INVESTIGATE-only.

   |
   v
(3) Tail-sign significance verdict  ✅ PROMOTION CHECK
    - deterministic: pass / fail / na
    - default: binomial sign test, alpha=0.05
    - only explicit "fail" blocks STRONG promotion

   |
   v
(4) Exotic tripwire  🟨 ALWAYS COMPUTED + LOGGED (incl. atlas outputs)
    - wec_tripwire / nec_tripwire
    - scaling-tripwire (p > p_max)
    - rho-budget tripwire
    -> becomes ✅ HARD GATE only with --use-exotic-tripwire-gate

   |
   v
(5) Emit window-level result for W

   |
   v
(6) Multi-window robustness aggregation  ✅ PROMOTION CHECK (cross-window)
    - compute robust_window_count from windows tested
    - NOTE: "range_robust_two_windows" label is inconsistent:

      Yukawa sweep:
        "two_windows" == (robust_window_count >= 2)

      PPN sweep:
        "two_windows" == (robust_window_count >= 1)   <-- label mismatch

   |
   v
(7) Promotion ladder evaluation  ✅ PROMOTION CHECK (final)
    none -> candidate -> strong_candidate -> investigate
    - INVESTIGATE checks include:
        * non_knife_edge_region (adjacent survivor requirement)

   |
   v
(8) Threshold tightening schedule loop  ✅ HARD META-FILTER
    - repeat (0)-(7) for stricter wf_thresh schedule
      PPN:    0.25 -> 0.15 -> 0.10
      Yukawa: 0.05 -> 0.03 -> 0.02

   |
   v
(9) Optional / separate paths  🟨 (not in core sweep ladder unless wired)
    - source / curvature plausibility gates
    - legacy Phase 4B observable bounds module
```

---

## v1 - Deflection Observable + Gate 0

Single falsifiable observable:

* `deflection_angle_vs_b`

Deterministic Gate 0 thresholds:

* Weak-field tail median error < threshold
* Resolution robustness under `h` refinement
* Known-limit reduction to GR

No candidate advances without passing Gate 0.

---

## v1.1 - T_new Introspection

Every deviation must declare its implied effective stress-energy proxy.

Artifacts:

* `_tnew_summary.json`

Purpose:
Audit structural plausibility before deeper promotion.

---

## v1.2 - Curvature Cost Sanity Prefilter

Conservative energy scaling triage:

* (rho_e ~ c^4 / (G L^2))
* (E ~ rho_e V)

Configurable ceilings screen macroscale claims.

This is a feasibility filter, not a fundamental bound.

---

## v1.3 - PPN Parameter Sweep Constraints

Parameter grid sweeps:

* Survivorship under tightening weak-field thresholds
* Multi-window evaluation
* Deterministic exclusion mapping

Outputs:

* Survivor CSV
* Sweep summary JSON
* Promotion evaluation artifact

---

## v1.4 - Promotion Ladder

Levels:

* none
* candidate
* strong_candidate
* investigate

Escalation requires:

* Structured residual behavior
* Stability under refinement
* Multi-window survivorship

Promotion never overwrites prior verdicts.

---

## v1.5 - Tail Verdict System

Replaces brittle booleans with auditable outcomes:

* `pass`
* `fail`
* `na` (informative ambiguity)

Binomial significance mode with explicit p-values.

Ambiguity is recorded, not auto-rejected.

---

## v1.6 - Numeric Weak-Field Reference

Optional comparison against Schwarzschild numeric baseline:

* `--wf-ref-mode analytic`
* `--wf-ref-mode numeric`

Includes denominator floor and endpoint recalibration.

Improves discrimination without altering semantics.

---

# Reproducibility

* Deterministic computation paths
* Versioned artifacts
* Logged parameters
* Registry-backed audit trail

Running module entrypoints regenerates artifacts from source.

---

# Registry Model

All runs append immutable rows to:

`results/registry/constraints_registry.csv`

Compact namespaced summaries are recorded in `notes`:

* `gate0:`
* `ppn_sweep:`
* `tailv:`
* `promote:`
* `wfref:`
* `curv_cost:`
* `exotic_tripwire:` (in source plausibility: power-feasibility tripwire; in `scripts/run_exotic_tripwire.py`: stress-energy proxy)

Full diagnostics remain in JSON artifacts.

---

# Quickstart (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m pytest -q
```

Run a PPN sweep:

```powershell
python scripts/sweep_ppn_constraints.py `
  --gamma-min 0.92 --gamma-max 1.08 --gamma-steps 33 `
  --wf-thresh-seq "0.05,0.03,0.02" `
  --range-windows "50:500,100:1000" `
  --n-points 160 --h 0.18 `
  --wf-ref-mode numeric `
  --tail-sign-mode binomial --tail-sign-alpha 0.05
```

---

# Generated Outputs

Artifacts are written to:

`results/artifacts/<run_id>/`

Including:

* Metrics CSV
* Plots
* Raw JSON diagnostics
* Promotion evaluation reports

Baseline outputs remain under `outputs/`.

---

# Assumptions and Limits

* Units: (G = c = 1)
* GR baseline: equatorial null geodesics
* Weak-field analytic relation used only as comparison anchor
* Graph phase remains a structural toy model
* Curve-shape similarity does not imply physical equivalence

---

# Operational Principle

CURV does not seek anomalies.

It reduces possibility space.

If a deviation survives tightening, it earns scrutiny.
If it fails, it is removed.

Constraint precedes curiosity.

---

## Documentation Index

| Doc | Purpose |
|-----|---------|
| `WHITEPAPER.md` | Formal framing |
| `CURV_RUN_LOG.md` | Constraint sweeps, promotion evaluations, structural rules |
| `docs/exotic_tripwire.md` | Exotic stress-energy tripwire (proxy instrument) |
| `docs/exotic_power_feasibility.md` | Exotic power feasibility tripwire (source plausibility) |
| `docs/notes/PILOT_YUKAWA_11x9_NOTES_20260228.md` | Yukawa pilot run notes |
| `results/TEST_FINDINGS_20260228.md` | Test evidence and sweep commands |

---

## Theory Rig

All evaluation layers record compact, namespaced one-line summaries in the registry `notes` field (for example `gate0:`, `source_eval:`, `curv_cost:`) for immutable audit traceability.

### v1 — Deflection Observable + Gate 0

**Purpose**
- v1 establishes a single falsifiable observable (light deflection) and a deterministic gate (Gate 0). Theories must pass this baseline before further evaluation.

**What it adds**
- Observable: `deflection_angle_vs_b` (equatorial null-ray deflection).
- Theory plugins:
  - `gr_schwarzschild` (truth anchor via geodesic tracing)
  - `gr_yukawa_deviation` (weak-field deviation with GR limit at `alpha_y=0`)
- Deterministic Gate 0 thresholds:
  - weak-field tail median error `< 0.25` (`tail_k=5`)
  - resolution mean normalized curve difference `< 0.15` (`h` vs `h/2`)
  - known-limit mean relative error `< 0.05` (Yukawa at `alpha_y=0` vs Schwarzschild)

**Registry behavior**
- Registry headers remain unchanged.
- Gate mapping:
  - `gateA_superposition_pass <- gate0_weak_field_pass`
  - `gateA_resolution_pass <- gate0_resolution_pass`
  - `gateA_scaling_pass <- gate0_known_limit_pass` (or `NA` for Schwarzschild)
  - `gateA_pass <- gate0_pass`
- `notes` includes a compact `gate0:` summary with measured diagnostics and thresholds.

**CLI usage**
```powershell
python scripts/run_theory_deflection.py `
  --theory gr_schwarzschild `
  --bmin-over-m 20 --bmax-over-m 200 --n-points 40 `
  --h 1e-3
```

```powershell
python scripts/run_theory_deflection.py `
  --theory gr_yukawa_deviation `
  --alpha-y 0.01 --lambda-y-over-m 50 `
  --bmin-over-m 20 --bmax-over-m 200 --n-points 40 `
  --h 1e-3
```

Artifacts: `results/artifacts/<run_id>/{metrics,plots,raw}`

### v1.1 — T_new Introspection

**Purpose**
- v1.1 forces every deviation to declare its implied effective stress-energy proxy (`T_new`) for audit and later plausibility screening.

**What it adds**
- Optional plugin hook: `stress_energy_summary(setup) -> dict`.
- Per-run artifact: `results/artifacts/<run_id>/raw/<run_id>_tnew_summary.json`.
- Compact summary fields in `notes`: `tnew_model=...`, `rho_eff_peak=...`, `energy_condition_flags=...`.
- Default bookkeeping includes `requires_negative_energy: "unknown"`.

**Registry behavior**
- Registry headers remain unchanged.
- All additional diagnostics remain in `notes` and raw JSON artifacts.

**CLI usage**
```powershell
python scripts/run_theory_deflection.py `
  --theory gr_yukawa_deviation `
  --alpha-y 0.01 --lambda-y-over-m 50 `
  --bmin-over-m 20 --bmax-over-m 200 --n-points 40 `
  --h 1e-3 `
  --notes "tnew_audit"
```

### v1.2 — Curvature Cost Sanity Prefilter

**Purpose**
- v1.2 introduces a conservative curvature cost prefilter to screen "spacetime bubble" scale claims before deeper modeling. It is a triage tool, not a fundamental limit.

**What it adds**
- Pure scaling sanity check:
  - `rho_e ~= c^4 / (G * L^2)`
  - `E ~= rho_e * V`
  - `m_equiv = E / c^2`
- Geometry assumptions:
  - `sphere`: `V = (4/3) * pi * L^3`
  - `shell`: `V = 4 * pi * L^2 * delta`
- Artifacts:
  - `results/artifacts/<run_id>/raw/<run_id>_curvature_cost_sanity.json`
  - merged key `curvature_cost_sanity` in `<run_id>_source_plausibility_summary.json`
- Configurable screening ceilings:
  - `CURV_MAX_M_EQUIV_KG` (default `1e12`)
  - `CURV_MAX_E_SCALE_J` (default derived from mass ceiling)
  - `CURV_MAX_RHO_E_J_PER_M3` (default `1e25 * c^2`)

**Registry behavior**
- Registry headers remain unchanged.
- Curvature summaries are recorded in `notes` via:
  - `curv_cost: ...`
  - `curv_gate: ...`
- In source plausibility mode with bubble inputs:
  - `gateA_pass = gateA_pass AND curv_gate_pass`

**Exotic power feasibility tripwire**
- An `exotic_matter_hypothetical` candidate is always evaluated and logged but **fails by default** (evidence gate).
- Use `--exotic-preset strict|normal|sandbox` for comparable runs; `--allow-speculative-exotic` enables speculative mode (for `normal` preset).
- Output includes `dominant_violation` (`evidence_gate`, `rho_ceiling`, etc.) for actionable failure reasons.
- See `docs/exotic_power_feasibility.md`.

**CLI usage**
```powershell
python scripts/run_source_plausibility.py `
  --required-energy-j 1e9 `
  --required-power-w 1e6 `
  --notes "mass_free_source_eval_v1"
```

```powershell
python scripts/run_source_plausibility.py `
  --required-energy-j 1e9 `
  --required-power-w 1e6 `
  --exotic-preset strict `
  --bubble-L-m 10 `
  --bubble-geometry sphere `
  --notes "v1p2_curvature_sanity"
```

```powershell
python scripts/run_source_plausibility.py `
  --required-energy-j 1e9 `
  --required-power-w 1e6 `
  --bubble-L-m 10 `
  --bubble-geometry shell `
  --bubble-thickness-m 0.5 `
  --notes "v1p2_curvature_shell"
```

#### Source Regime Atlas (2026-03-01)

A reproducible phase sweep maps source feasibility separately from curvature implications.

- Sweep command: `python scripts/run_source_phase_map.py --power-min-w 1e4 --power-max-w 1e9 --power-steps 31 --duration-min-s 1e2 --duration-max-s 1e5 --duration-steps 25 --active-radius-m 10 --curvature-cal 2.08e-43 --k-target-10m 1e-2 --k-target-1km 1e-6`
- Exotic presets and `--allow-speculative-exotic` supported; when speculative mode is on, `run_id` is suffixed with `_speculative` and the summary includes `plot_annotation: "SPECULATIVE MODE"` to avoid misreading plots.
- Artifacts:
  - `results/artifacts/20260301_194455Z_energy_source_phase_map/metrics/20260301_194455Z_energy_source_phase_map_source_phase_map.csv`
  - `results/artifacts/20260301_194455Z_energy_source_phase_map/raw/20260301_194455Z_energy_source_phase_map_phase_map_summary.json`
- Regime result over 775 points: feasible points are dominated by `hydrocarbon_engine` and `fission_reactor`; `li_ion_battery` survives only in a small low-power/short-duration region; `fusion_speculative`, `antimatter_extreme`, and `beamed_power` have no feasible region under current gate logic; `exotic_matter_hypothetical` is always computed and logged but fails by default (evidence gate) unless `--allow-speculative-exotic` is set and ceilings are satisfied.
- Failure frontier is mainly thermal-limited, with containment as a secondary rejection mode.
- Curvature overlay remains microscopically small across the full grid (`max K_ratio_10m ~= 4.97e-31`, `max K_ratio_1km ~= 4.97e-27`), by construction of the 10 m active-volume assumption and calibration constant.

**Moral:** Sustainable power is not the bottleneck for megawatt systems; curvature is.

### v1.3 — PPN Parameter Sweep Constraints

**Purpose**
- v1.3 turns small PPN-like gravity deviations into a sweepable constraint map under progressively tighter weak-field gates.

**What it adds**
- Theory plugin: `gr_ppn_screened_potential` (gamma-focused weak-field parameterization with explicit GR recovery).
- Runner-level gate threshold overrides (defaults unchanged):
  - `--wf-thresh`
  - `--resolution-thresh`
  - `--known-limit-thresh`
- Sweep runner for survival-region mapping:
  - `scripts/sweep_ppn_constraints.py`
  - artifacts:
    - `metrics/<run_id>_ppn_sweep_results.csv`
    - `metrics/<run_id>_ppn_survivors.csv`
    - `raw/<run_id>_ppn_sweep_summary.json`

**Registry behavior**
- Registry headers remain unchanged.
- Sweep appends one row per sweep run with `model_mode=ppn_sweep`.
- `notes` includes compact summary:
  - `ppn_sweep: wf_seq=...; grid=...; survivors={...}; best=...`

**CLI usage**
```powershell
python scripts/run_theory_deflection.py `
  --theory gr_ppn_screened_potential `
  --gamma-ppn 1.0 `
  --bmin-over-m 50 --bmax-over-m 500 --n-points 20 `
  --h 0.5 `
  --wf-thresh 0.15 `
  --notes "v1p3_single_run"
```

```powershell
python scripts/sweep_ppn_constraints.py `
  --gamma-min 0.98 --gamma-max 1.02 --gamma-steps 9 `
  --wf-thresh-seq "0.25,0.15,0.10" `
  --range-windows "50:500,100:1000" `
  --n-points 12 `
  --h 0.5 `
  --notes "v1p3_initial_gamma_sweep"
```

### v1.4 — Promotion Ladder (Candidate -> Strong Candidate -> Investigate)

**Purpose**
- v1.4 adds a deterministic promotion doctrine that escalates surviving parameterizations from kill mode to nurture mode using explicit, auditable criteria.

**What it adds**
- Promotion levels:
  - `none`
  - `candidate`
  - `strong_candidate`
  - `investigate`
- Promotion artifact:
  - `results/artifacts/<run_id>/raw/<run_id>_promotion_eval.json`
- Promotion summary in registry notes:
  - `promote: level=<...>; reasons=[...]`
- Residual-structure diagnostics used by promotion checks:
  - tail median residual
  - tail sign-change count
  - endpoint dominance ratio

**Registry behavior**
- Registry headers remain unchanged.
- Sweep runs append promotion summaries to `notes` while keeping prior rows immutable.
- Promotion never overwrites earlier verdicts; each sweep emits a new decision artifact and row.

**CLI usage**
```powershell
python scripts/sweep_ppn_constraints.py `
  --gamma-min 0.98 --gamma-max 1.02 --gamma-steps 9 `
  --wf-thresh-seq "0.25,0.15,0.10" `
  --range-windows "50:500,100:1000" `
  --n-points 10 --h 0.5 `
  --min-adjacent-survivors 2 `
  --notes "promotion_ladder_v1"
```

```powershell
python scripts/sweep_ppn_constraints.py `
  --gamma-min 0.98 --gamma-max 1.02 --gamma-steps 9 `
  --wf-thresh-seq "0.25,0.15,0.10" `
  --range-windows "50:500,100:1000" `
  --n-points 10 --h 0.5 `
  --source-pass-flag na `
  --curvature-pass-flag na `
  --external-alignment-trigger `
  --notes "promotion_ladder_investigate_probe"
```

### v1.5 — Tail Verdict System (Anatomy + NA Reason + Binomial Mode)

**Purpose**
- v1.5 replaces brittle tail-sign booleans with deterministic, auditable verdicts that distinguish ambiguity from contradiction.

**What it adds**
- Tail anatomy metrics per window and threshold:
  - `tail_n_total`, `tail_threshold`, `tail_n_significant`, `tail_frac_significant`
  - `tail_med_abs_residual`, `tail_mean_abs_residual`
  - `tail_n_pos`, `tail_n_neg`, `tail_sign_balance`
- Explicit NA semantics:
  - `no_tail_points`
  - `no_significant_tail_points`
  - `insufficient_significant_tail_points`
  - `sign_bias_not_detectable`
- Binomial significance mode (`tail_sign_mode=binomial`) with exact two-sided p-value:
  - `tail_sign_p_two`, `tail_sign_alpha`, `tail_sign_detectable`
- Sweep-level `tail_sign_verdict`:
  - `pass` (detectable and sign-consistent across windows)
  - `fail` (detectable and opposite sign across windows)
  - `na` (insufficient evidence)
- Strong-candidate rule update:
  - only `tail_sign_verdict=fail` blocks Strong
  - `na` is informative ambiguity, not an automatic veto

**Registry behavior**
- Registry headers remain unchanged.
- `notes` includes compact `tailv:` suffix:
  - `tailv: verdict=...; na_reason=...; n_sig=.../...; p=...; alpha=...; balance=...`
- Full diagnostics are written to:
  - `raw/<run_id>_promotion_eval.json`

**CLI usage**
```powershell
python scripts/sweep_ppn_constraints.py `
  --gamma-min 0.92 --gamma-max 1.08 --gamma-steps 33 `
  --wf-thresh-seq "0.07,0.05,0.03" `
  --range-windows "50:500,100:1000" `
  --n-points 160 --h 0.18 `
  --tail-sign-mode binomial --tail-sign-alpha 0.05 `
  --tail-eps-abs 1e-7 --tail-eps-rel 0.001 `
  --min-tail-significant 8 `
  --notes "v1p5_tail_verdict"
```

### v1.6 — Numeric Weak-Field Reference + Endpoint Recalibration

**Purpose**
- v1.6 sharpens weak-field discrimination by allowing Gate 0 to compare directly to a Schwarzschild numeric baseline on the same grid.

**What it adds**
- Weak-field reference mode switch:
  - `--wf-ref-mode analytic` (default, backward-compatible)
  - `--wf-ref-mode numeric` (new recommended discriminator)
- Stable denominator floor for relative error:
  - `--wf-eps-denom` (default `1e-15`)
- Numeric baseline caching per window per run (no repeated GR precompute for each gamma point).
- Endpoint rule recalibration (Option A):
  - `endpoint_not_dominant` moved from Candidate checks to Strong checks.
- Notes and promotion diagnostics include weak-field reference metadata.

**Registry behavior**
- Registry headers remain unchanged.
- `notes` adds compact `wfref:` summary:
  - `wfref: mode=<analytic|numeric>; eps_denom=<...>`
- Promotion diagnostics (`raw/<run_id>_promotion_eval.json`) include:
  - `wf_ref_mode`
  - `wf_ref_eps_denom`
  - `wf_ref_baseline` metadata when numeric

**CLI usage**
```powershell
python scripts/sweep_ppn_constraints.py `
  --gamma-min 0.92 --gamma-max 1.08 --gamma-steps 33 `
  --wf-thresh-seq "0.05,0.03,0.02" `
  --range-windows "50:500,100:1000" `
  --n-points 160 --h 0.18 `
  --wf-ref-mode numeric `
  --tail-sign-mode binomial --tail-sign-alpha 0.05 `
  --tail-eps-abs 1e-7 --tail-eps-rel 0.001 `
  --min-tail-significant 8 --min-adjacent-survivors 2 `
  --notes "wfpush_050_030_020_numeric"
```

### Exotic Tripwire (Standalone)

Run the exotic stress-energy tripwire on an existing sweep/run:

```powershell
python scripts/run_exotic_tripwire.py --input-run-id <run_id> --b-window 100:1000
```

See `docs/exotic_tripwire.md` for proxy definitions, scoring, and full CLI options.

### v1.7 — Yukawa 2D Constraint Sweep (alpha_y, lambda_y_over_m)

**Purpose**
- v1.7 adds a dedicated 2-parameter sweep for the Yukawa residual family to map survivorship topology under the same deterministic Gate 0 and promotion ladder stack used by PPN sweeps.

**Model family (instrument form)**
- Theory plugin: `gr_yukawa_deviation`
- Deflection proxy:
  - `alpha(b) = (4 / b) * (1 + alpha_y * exp(-b / lambda_y_over_m))`
- GR limit is explicit at `alpha_y = 0`.

**What it writes**
- `metrics/<run_id>_yukawa_sweep_results.csv`
- `metrics/<run_id>_yukawa_survivors.csv`
- `raw/<run_id>_yukawa_sweep_summary.json`
- `raw/<run_id>_promotion_eval.json`
- `plots/<run_id>_yukawa_survivor_heatmap.png` (unless `--no-plots`)

**Summary fields to inspect first**
- `survivors_by_thresh`
- `best_params`
- `best_params_by_thresh`
- `failure_reason_counts` (includes Gate-0 fail buckets and tail-sign NA reasons)
- `promotion_level`

**Pilot sanity-check run (recommended first)**
```powershell
python scripts/sweep_yukawa_constraints.py `
  --alpha-min -0.10 --alpha-max 0.10 --alpha-steps 11 `
  --lambda-min 1 --lambda-max 1000 --lambda-steps 9 --lambda-spacing log `
  --wf-thresh-seq "0.05,0.03,0.02" `
  --range-windows "50:500,100:1000" `
  --n-points 320 --h 0.18 `
  --wf-ref-mode numeric `
  --notes "pilot_11x9"
```

**Full sweep run**
```powershell
python scripts/sweep_yukawa_constraints.py `
  --alpha-min -0.10 --alpha-max 0.10 --alpha-steps 41 `
  --lambda-min 1 --lambda-max 1000 --lambda-steps 21 --lambda-spacing log `
  --wf-thresh-seq "0.05,0.03,0.02" `
  --range-windows "50:500,100:1000" `
  --n-points 320 --h 0.18 `
  --wf-ref-mode numeric `
  --notes "full_41x21"
```

**Interpretation guardrails**
- Treat this as a deterministic constraint-engine family, not a full physically faithful Yukawa lensing derivation.
- Expect monotonic pruning as thresholds tighten; non-monotonic behavior should be diagnosed via `failure_reason_counts` and per-window/tail diagnostics.
- Pilot before full sweep to confirm artifact semantics and runtime behavior on your machine.

CURV does not attempt to prove speculative propulsion concepts. It attempts to eliminate physically inconsistent ones using geometry, energy accounting, and conservative scaling filters.

## Latest Test Evidence

- Dated run log and findings: `results/TEST_FINDINGS_20260228.md`
- `docs/notes/PILOT_YUKAWA_11x9_NOTES_20260228.md` — Yukawa pilot attempt notes (11x9), runtime + failure mode, next diagnostic run.
- Includes executed commands, pass/fail outcomes, edge-of-allowed Phase 4B probe, energy-scaling simulation anchors, and artifact paths.

## Energy Sweep Repro Snippet

To validate the environment used for the recorded energy sweeps, run:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Then inspect the latest energy sweep artifacts under:

- `results/artifacts/*_energy_envelope_sweep*/metrics/`
- `results/artifacts/*_energy_envelope_sweep_duration_ranked*/metrics/`
- `results/artifacts/*_energy_envelope_sweep_duration_ranked*/raw/`

For exact sweep command blocks, assumptions, formulas, and numeric outcomes, see:

- `results/TEST_FINDINGS_20260228.md`

## Generated Outputs (`outputs/`)

### Phase 1: GR baseline
- `gr_deflection.csv`
- `gr_lensing_paths.png`
- `gr_deflection_curve.png`

### Phase 2: Graph toy model and robustness
- `graph_deflection.csv`
- `graph_rays_baseline.png`
- `graph_rays_mass.png`
- `graph_deflection_curve.png`
- `graph_resolution_robustness.csv`
- `graph_resolution_robustness.png`
- `graph_scaling_fit.csv`
- `graph_scaling_fit.png`
- `graph_scaling_fit_hard_blob.csv`
- `graph_scaling_fit_hard_blob.png`
- `graph_scaling_fit_smooth_gaussian.csv`
- `graph_scaling_fit_smooth_gaussian.png`
- `graph_superposition.csv`
- `graph_superposition.png`

### Phase 3: Comparison
- `deflection_comparison.png`
- `summary.md`

### Phase 4B: Candidate constraints
- `phase4b_constraints.csv`
- `phase4b_constraints.png`
- `phase4b_constraints_observables.json`
- `phase4b_constraints_summary.json`
- `phase4b_yukawa_grid.csv`
- `phase4b_yukawa_exclusion.png`
- `phase4b_yukawa_grid_summary.json`
- `phase4b_summary.md`

## Assumptions and Limits

- Units in GR phase: `G = c = 1`.
- GR baseline uses null geodesics in the Schwarzschild equatorial plane via `u(phi) = 1 / r`.
- Weak-field relation `alpha ~= 4M / b` is used as a baseline and should fit better at larger `b`.
- Graph phase is a discrete shortest-path toy model with a local entanglement-weight boost in a mass region.
- Graph deflection is exit-node shift (grid units), not a physical angle.
- Matching normalized curve shape does not imply physical equivalence.
