# CURV

## Constraint-Unified Residual Validator

### A Deterministic Framework for Gravitational Deviation Constraint

> **Scope note:** This whitepaper documents CURV's gravity-core certified baseline. The current repository has since added claim-evaluation, exotic-feasibility, local-console, and UFS research-validation capabilities. Those additions do not retroactively change the frozen gravity baseline described here; see [docs/PROGRAM_PURPOSE.md](docs/PROGRAM_PURPOSE.md) for current scope.

---

## Abstract

CURV (Constraint-Unified Residual Validator) is a deterministic computational framework designed to evaluate parameterized deviations from General Relativity (GR) under progressively tightened structural constraints.

Rather than proposing new physics, CURV enforces survivability criteria. Candidate deviations are subjected to numeric GR baselines, weak-field limits, resolution refinement, observational thresholds, and conservative energy scaling sanity checks.

The system's primary function is uncertainty reduction. It eliminates inconsistent regions of parameter space while preserving only those deviations that remain structurally unified with known physical limits.

### Certified Baseline

* **Tier 1 Certified Baseline:** `Tier1_Certified_GR_Baseline`
* **Tag:** `v0.1.0-certified`
* **Commit:** `da8e3ed`
* **Certification:** `results/certification/20260228_184324Z_cert_v0.1_da8e3ed/`

---

## 1. Introduction

General Relativity has demonstrated exceptional predictive success across weak-field, strong-field, and radiative regimes. However, open questions remain at quantum scales, cosmological scales, and near singularity conditions.

The goal of CURV is not to replace GR, but to provide:

* A reproducible constraint engine for gravitational deviation testing
* A structured framework for residual analysis
* A deterministic promotion ladder for candidate survivability

The system is falsifier-first by design.

---

## 2. Design Philosophy

CURV operates under four principles:

### 2.1 Constraint First

No deviation is considered viable unless it satisfies all enforced limits.

### 2.2 Unified Reduction

All candidate models must reduce to GR in tested regimes.

### 2.3 Residual Focus

Only deviations from numeric GR baselines are evaluated.

### 2.4 Deterministic Validation

Every run is seed-fixed, logged, artifact-saved, and registry-traceable.

---

## 3. System Architecture

CURV is structured in layered validation phases.

### 3.1 Baseline Module

* Schwarzschild null geodesic tracing
* Deterministic deflection observable
* Numeric weak-field comparison option

### 3.2 Gate 0 - Structural Admissibility

Candidates must satisfy:

* Weak-field tail error threshold
* Resolution robustness under step refinement
* Known-limit reduction to GR

Failure terminates evaluation.

### 3.3 Stress-Energy Introspection

Each deviation must declare its implied effective stress-energy proxy (`T_new`).

This enforces early plausibility screening and prevents unexamined structural claims.

### 3.4 Curvature Cost Sanity Prefilter

Macroscopic curvature proposals are screened using conservative scaling:

`rho_e ~ c^4 / (G L^2)`
`E ~ rho_e * V`

This module acts as triage, not a fundamental bound.

### 3.5 Parameter Sweep Engine

Grid sweeps over deviation parameters:

* Multi-window evaluation
* Progressive weak-field tightening
* Survivorship mapping

Artifacts:

* Survivor CSV
* Sweep summary JSON
* Promotion evaluation report

### 3.6 Tail Verdict System

Ambiguity and contradiction are distinguished via:

* Explicit tail anatomy metrics
* Binomial significance mode
* NA classification when evidence is insufficient

Ambiguity is recorded, not misclassified.

### 3.7 Promotion Ladder

Levels:

* none
* candidate
* strong_candidate
* investigate

Promotion requires:

* Structured residual behavior
* Multi-window stability
* Resolution robustness
* Unified reduction consistency

No verdict overwrites prior results.

---

## 4. Reproducibility and Audit

All runs:

* Append immutable rows to `constraints_registry.csv`
* Save raw JSON diagnostics
* Log compact namespaced summaries in registry notes

Artifacts are regenerated from source using fixed seeds and version-tracked commits.

CURV is designed for auditability.

---

## 5. Methodology

### 5.1 Observable

Primary observable:

* Light deflection as a function of impact parameter

Secondary modules may include:

* Orbit precession simulation
* Continuous ray tracing
* Extended PPN mapping

### 5.2 Evaluation Strategy

For each candidate deviation:

1. Establish numeric GR baseline
2. Compute residual curve
3. Apply Gate 0 structural tests
4. Perform multi-window survivorship evaluation
5. Apply tail significance analysis
6. Apply promotion doctrine

Parameter space is reduced, not expanded.

---

## 6. Scope and Limitations

CURV does not:

* Prove new gravitational physics
* Provide propulsion feasibility
* Claim energy breakthroughs
* Detect anomalies autonomously

It provides structured constraint enforcement only.

Curve-shape similarity does not imply physical equivalence.

Graph-based toy models remain analog tools and are not treated as physical systems.

---

## 7. Long-Term Aim

The long-term objective is to:

* Harden gravitational hypothesis testing
* Map degeneracy regions
* Identify structurally consistent deviation directions
* Reduce uncertainty via constraint tightening

If a deviation survives all gates under progressive refinement, it earns scrutiny.

If it fails, it is removed.

Constraint precedes curiosity.

---

## 8. Conclusion

CURV is not a theory generator.

It is a residual validator operating under unified physical constraints.

Its value lies in disciplined elimination, not speculative construction.

The instrument reduces possibility space.

Only survivors remain.
