---
name: "Phase 4A: superposition + resolution"
about: Track Gate A structural metrics for superposition and resolution
title: "[PHASE4A] Superposition + Resolution"
labels: phase-4a, metrics
assignees: ""
---

## Scope

Record and assess superposition and resolution metrics for declared trial/campaign ids.

## Inputs

- Trial run ids:
- Campaign id:
- Model mode:
- Weak-k definition:

## Required checks

- [ ] `superposition_median_rel_error < 0.25`
- [ ] `resolution_mean_curve_diff < 0.15`
- [ ] Metrics logged in append-only registry rows
- [ ] Artifacts listed and present

## Outputs

- Registry rows:
- Artifact paths:
- Pass/fail outcome:

## If failed

State model revision action. No interpretation as substitute for failed thresholds.
