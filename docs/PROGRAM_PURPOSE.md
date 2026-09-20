# NEWGR Program Purpose

**Authoritative definition.** All documentation and code comments should align with this spine.

---

## Canonical Statement

**NEWGR** is a *gravity-theory evaluation and evidence-trail framework* that:

1. tests GR/PPN/Yukawa-like models against deflection/weak-field constraints,
2. evaluates UAP behavior claims against conservation laws and unavoidable signatures,
3. enforces an append-only, auditable gate system for all runs and artifacts,
4. optionally acts as a read-only research-readiness validator for Universal Frequency Spectrum frontier/question records.

This keeps the repo coherent: not "cool physics stuff + UFO stuff," but a unified instrument for constraint-driven analysis.

---

## Four Lanes

Each lane follows the same pattern: **inputs → gates → verdict → artifacts → registry row**.

### 1. Theory Validation Lane

- **Scope:** Deflection curves, PPN sweeps, Yukawa sweeps, promotion ladder.
- **Inputs:** Theory parameters (γ, α, λ), impact-parameter windows, weak-field thresholds.
- **Gates:** Gate 0 (weak-field, resolution, known-limit), residual-structure checks, tail verdict, exotic tripwire (optional hard gate), multi-window robustness, promotion ladder.
- **Outputs:** Survivor CSVs, sweep summaries, promotion eval JSON, registry rows in `results_registry`.
- **Scripts:** `run_theory_deflection.py`, `run_deflection_curve.py`, `sweep_ppn_constraints.py`, `sweep_yukawa_constraints.py`.

### 2. Claim Evaluation Lane

- **Scope:** UFO observables → gates → negative-heavy scorecard → breakthrough ladder tests.
- **Inputs:** Behavior spec (kinematics), observable claims (sonic boom absent, thermal low, etc.), mass range, policy.
- **Gates:** Flight dynamics, power budget, thermal limits, shock waves, medium coupling, signature gates, exotic tripwire (evidence gate).
- **Outputs:** Verdict, failed gates, lane rankings, assumption deltas, registry rows in `ufo_observable_registry`, `ufo_behavior_registry`, `breakthrough_ladder_registry`.
- **Scripts:** `run_ufo_observable_eval.py`, `run_ufo_behavior_eval.py`, `run_breakthrough_ladder.py`.

### 3. Exotic Feasibility Lane

- **Scope:** Curvature cost sanity, exotic tripwire, power feasibility.
- **Inputs:** Energy/power requirements, bubble geometry, deflection residuals (for tripwire).
- **Gates:** Curvature ceilings (ρ_e, E_scale, m_equiv), exotic power evidence gate, WEC/NEC proxy tripwires.
- **Outputs:** Curvature cost JSON, source plausibility CSV, exotic tripwire atlas, registry rows in `results_registry`, `exotic_tripwire_registry`.
- **Scripts:** `run_source_plausibility.py`, `run_exotic_tripwire.py`, `run_bubble_experiment_analysis.py`.

### 4. UFS Research Validation Lane

- **Scope:** Read-only Universal Frequency Spectrum frontier/question and typed-gap records.
- **Inputs:** Canonical UFS record ID, policy, speculative flag.
- **Gates:** source traceability, candidate/question specificity, observable specificity, bridge/coupling specificity, energy-accounting status.
- **Outputs:** research-readiness verdict, JSON artifact, registry row in `ufs_validation_registry`.
- **Script:** `run_ufs_candidate_validation.py`.
- **Boundary:** a readiness verdict never changes UFS canonical scientific evidence status automatically.

---

## Breakthrough Definition

A **"breakthrough candidate"** in NEWGR means:

- passes a specified ladder step **without speculative mode**, OR
- in speculative mode, produces a **minimal-assumption solution** plus **unavoidable predicted signatures** that can be falsified.

The system must never print "breakthrough achieved" by accident. Speculative passes are explicitly tagged and require falsifiable predictions.

---

## References

- [Registry Map](REGISTRY_MAP.md) — Registries, writer scripts, row schemas
- [README](../README.md) — Quickstart and architecture overview
- [WHITEPAPER](../WHITEPAPER.md) — Formal framing
- [UFS Integration](UFS_INTEGRATION.md) — Universal Frequency Spectrum research-validator contract
