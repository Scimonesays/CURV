# CURV Mission Plan: Track A + Track B

This plan formalizes a two-track workflow for the Constraint-Unified Residual Validator:

- Track A: lock down the gravity-correction evidence chain.
- Track B: evaluate long-horizon implications as constrained extrapolation, never as direct claims.

The default posture is falsifier-first: failure is information, not a setback.

## Core Rules (Both Tracks)

- Predefine thresholds before runs; do not tune them after seeing outcomes.
- Keep outputs deterministic and registry-backed.
- Append exactly one registry row per run.
- Keep claims tied to artifacts under `results/artifacts/<run_id>/`.
- Separate "physics result" statements from "implication" statements.

## Track A: Near-Term Truth (Primary)

Goal: establish whether any parameter region survives tightening with stable, reproducible structure.

### A1) Baseline Reproducibility Check

Pass criteria:

- Test suite passes.
- Core modules run without runtime failures.
- Artifacts are generated in expected locations.

Suggested commands (PowerShell):

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m src.gr_schwarzschild
.\.venv\Scripts\python -m src.emergent_graph
.\.venv\Scripts\python -m src.compare
.\.venv\Scripts\python -m src.constraints
```

### A2) Tightening Survival Sweep (PPN)

Pass criteria:

- At least one non-empty survivor sliver remains under strict thresholds.
- Survivors pass weak-field, resolution, and known-limit checks.
- Survivors are stable under deterministic reruns (same inputs, same outputs).

Suggested command:

```powershell
python scripts/sweep_ppn_constraints.py `
  --gamma-min 0.98 --gamma-max 1.02 --gamma-steps 400 `
  --wf-thresh-seq 0.25,0.15,0.10 `
  --range-windows 50:500,100:1000 `
  --n-points 20 --h 0.5 `
  --full-throttle --telemetry --telemetry-seconds 2 `
  --notes "trackA_tightening_sweep"
```

Required evidence:

- `*_ppn_sweep_results.csv`
- `*_ppn_survivors.csv`
- `*_ppn_sweep_summary.json`
- `*_promotion_eval.json`

### A3) Stability and Anti-Coincidence Checks

Pass criteria:

- Survivor behavior remains consistent across repeated runs.
- No dependence on accidental ordering or intermediate-state artifacts.
- Structured residual behavior persists (not oscillatory noise spikes).

Suggested checks:

- Rerun A2 command at least 3 times with identical parameters.
- Compare survivor sets and best-gamma bands for exact agreement.
- Confirm promotion level consistency across reruns.

### A4) Cross-Observable Consistency Envelope

Pass criteria:

- Surviving PPN region remains compatible with compact Phase 4B constraints.
- No immediate contradiction between PPN sweep conclusions and Yukawa-grid exclusions.

Suggested command:

```powershell
python -m src.trial_pipeline --gamma 1.0 --alpha 0.0 --lambda-au 1.0 --notes "trackA_cross_observable_baseline"
```

### A5) Promotion Discipline

Promotion policy:

- Promote to `candidate` only with threshold survival and stable reruns.
- Promote to `strong_candidate` only with robust window behavior and low perturbation sensitivity.
- Promote to `investigate` only when independent alignment trigger is justified and logged.

If any criterion fails: mark as "revise model" and retain all failed artifacts for auditability.

## Track B: Long-Horizon Ambition (Constrained Extrapolation)

Goal: quantify implications of surviving regions without over-claiming.

### B1) Derive Effective Source Terms from Survivors

Pass criteria:

- Derived effective source scales are finite and numerically stable.
- Diagnostics are recorded with explicit assumptions.

Output expectation:

- Compact table of implied scale ranges with uncertainty notes.

### B2) Plausibility Filters

Pass criteria:

- No absurd density/energy requirements under stated assumptions.
- Curvature sanity checks remain pass/NA under policy.
- Source plausibility remains pass/NA under policy.

Suggested command:

```powershell
python scripts/run_source_plausibility.py
```

### B3) Interpretation Guardrails

Mandatory language rules:

- Allowed: "consistent with", "suggests", "constrains", "rules out".
- Not allowed: "proves", "demonstrates propulsion", "warp works".

Every implication statement must include:

- survivor region reference,
- exact run IDs,
- direct artifact links.

## Milestones and Exit Conditions

### Milestone M1 (Track A Complete)

All of the following true:

- Reproducibility baseline green.
- Tightening sweep has auditable outcomes (survivor or null result).
- Stability reruns completed and logged.
- Cross-observable consistency checked.

### Milestone M2 (Track B Complete)

All of the following true:

- Effective source-term extrapolation documented.
- Plausibility filters passed or explicit failure boundaries mapped.
- Interpretation language remains strictly constrained.

### Exit Conditions

- If no survivor persists under strict thresholds: publish null result and stop escalation.
- If survivors persist but imply absurd source scales: classify as mathematically interesting, physically implausible.
- If survivors persist and remain plausible: move to external comparison phase (observational tension matching) without propulsion claims.

## Reporting Template (Per Batch)

- Objective:
- Parameter domain:
- Fixed thresholds:
- Commands executed:
- Run IDs:
- Pass/fail summary:
- Survivor region:
- Stability rerun consistency:
- Plausibility status:
- Claim level:
- Next falsifier:

## Non-Negotiable Integrity Constraints

- No silent threshold edits.
- No cherry-picked runs.
- No intermediate registry writes.
- No claim without artifact-backed evidence.
- No speculative language in Track A conclusion sections.
