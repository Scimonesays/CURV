# CURV Methodology

CURV (Constraint-Unified Residual Validator) uses a strict falsification loop:

1. define a parameterized model
2. generate deterministic predictions
3. measure fixed metrics
4. compare against explicit thresholds
5. revise model if thresholds fail

Interpretation only follows threshold pass criteria.

## Gate A (structural analogy campaign gate)

Gate A checks whether toy geometry remains structurally credible under weak perturbations and numerical stress tests.

Thresholds:

- Scaling gate: `(r2_inv - r2_lin) >= 0.05` for at least 2 weak-k runs in a campaign.
- Superposition gate: `superposition_median_rel_error < 0.25`.
- Resolution gate: `resolution_mean_curve_diff < 0.15`.
- Campaign Gate A pass: scaling pass AND superposition pass rate is `1.0` AND resolution pass rate is `1.0`.

If any gate fails, status is "revise model" and the model is not promoted.

## Phase 4B constraints (candidate filter)

Phase 4B evaluates compact gravity deviations using:

- PPN-like parameter: `gamma`
- Yukawa-like parameters: `alpha`, `lambda_au`
- Combined observable ratio: `ratio_total = ratio_ppn * ratio_yukawa`

Reference anchors:

- light deflection near Sun: `1.75 arcsec`
- Mercury perihelion precession: `43 arcsec/century`
- Shapiro delay proxy: `200 microseconds`

A parameter point passes only when all observable residuals are within configured bounds.

## Registry and evidence policy

- `results/registry/constraints_registry.csv` is append-only.
- Trial rows are immutable after append.
- Each row must include timestamp, parameter tuple, pass/fail metrics, artifact paths, and `git_hash` (or `nogit`).
- Claims should always point to both registry rows and run-specific artifacts.

## Required artifacts

Each deterministic trial should emit artifacts under `results/artifacts/<run_id>/`:

- `metrics/` CSV tables
- `plots/` PNG figures
- `raw/` JSON summaries

For Phase 4B, required content includes constraints and Yukawa-grid summaries plus corresponding plots.

## Weak-k declaration

When a Gate A campaign uses weak-k filtering, declare it explicitly (for example `k<=1.05`) in the campaign metadata so threshold interpretation remains auditable.
