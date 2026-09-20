# CURV Run Log

STRUCTURAL_RULESET_VERSION: v1.0
WeakFieldBaselineModeDefault: analytic (numeric introduced 2026-02-28)

## Frozen Purpose Statement

CURV aims to test whether small, long-range perturbations to the Schwarzschild potential can survive weak-field GR constraints while maintaining geometric robustness across radial windows.

---

## Documentation Rules (Frozen)

- Record every sweep run in this file.
- Keep interpretation to 2-3 lines max per run.
- Do not change structural rules retroactively; version and date any intentional change.
- Document only what the math supports.
- Exclude speculative application claims from this log.

---

## Structural Rule Definitions (Versioned, Immutable Until Revised)

### Rule Set ID

- `rule_set_id`:
- `effective_date_utc`:
- `changed_from_rule_set_id`:
- `change_reason`:

### Gate 0 Definition

- Checks performed:
- Pass criteria:
- Fail criteria:

### Weak-Field Error Definition

- Reference mode:
- Error metric:
- Normalization:
- Pass threshold:

### Tail Significance Criteria

- Statistic / test:
- Threshold:
- Notes:

### Endpoint Dominance Definition

- Metric:
- Dominance condition:
- Notes:

### Window Robustness Rule

- Windows tested:
- Required consistency criterion:
- Failure condition:

### Promotion Qualification

- Candidate criteria:
- Strong criteria:
- Promotion ladder semantics:

---

## Baseline Mode Comparison Log

| Date (UTC) | Run ID | Weak-Field Reference Mode | Prior Mode | Shift in Optimum | Survivor Count Shift | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-02-28 | 20260228_210849Z_yukawa_sweep_ka-0.1_0.1_N11_sigl1_1000_9_connNA_expNA | numeric | analytic (default) | n/a (first logged numeric run) | n/a | Numeric weak-field baseline introduced; direct analytic-vs-numeric delta pending paired rerun. |

---

## Promotion Status Log

| Date (UTC) | Run ID | Promotion | Notes |
| --- | --- | --- | --- |
| 2026-02-28 | 20260228_210849Z_yukawa_sweep_ka-0.1_0.1_N11_sigl1_1000_9_connNA_expNA | Candidate | Strong promotion blocked by `range_robust_two_windows` and `endpoint_not_dominant`. |

---

## Known Limitations (Current)

- Yukawa modification is a toy perturbation model.
- Analysis is in the perturbative weak-field regime.
- No full field-equation solution is performed.
- Energy extraction/implications are out of scope.
- Strong-field behavior is not yet tested.

---

## Run Entries

### Run Template

Copy this block for each sweep:

```md
## Run: <run_id>

- date_utc:
- operator:
- commit:
- artifact_root:

### Core Parameters

- alpha_min:
- alpha_max:
- alpha_steps:
- lambda_min:
- lambda_max:
- lambda_steps:
- spacing_type: linear or log
- n_points:
- h:
- wf_ref_mode: analytic or numeric
- range_windows:
- wf_thresh_seq:
- random_seed: n/a if deterministic

### Outputs

- survivors_by_thresh:
- best_params:
- best_params_by_thresh:
- failure_reason_counts:
- strong_checks:
- promotion_level:

### Parameter Topology Notes

- basin movement:
- alpha sign trend:
- lambda boundary behavior:
- robustness trend:

### Interpretation (2-3 lines max)

line 1:
line 2:
line 3: optional
```

---

## Run Entries (Chronological)

<!-- Append newest run at the top for operational triage, or append at bottom for strict chronology. Choose one convention and keep it fixed. -->

## Run: 20260228_210849Z_yukawa_sweep_ka-0.1_0.1_N11_sigl1_1000_9_connNA_expNA

- date_utc: 2026-02-28
- operator: n/a
- commit: n/a
- artifact_root: `results/artifacts/20260228_210849Z_yukawa_sweep_ka-0.1_0.1_N11_sigl1_1000_9_connNA_expNA`

### Core Parameters

- alpha_min: -0.1
- alpha_max: 0.1
- alpha_steps: 11
- lambda_min: 1
- lambda_max: 1000
- lambda_steps: 9
- spacing_type: log (lambda)
- n_points: 120
- h: 0.18
- wf_ref_mode: numeric
- range_windows: 50:500, 100:1000
- wf_thresh_seq: 0.05, 0.03, 0.02
- random_seed: n/a (deterministic sweep)

### Outputs

- survivors_by_thresh: 96 -> 91 -> 86
- best_params: alpha_y = -0.02, lambda_y_over_m = 1000
- best_params_by_thresh: 0.05 -> (-0.02, 1000); 0.03 -> (-0.02, 1000); 0.02 -> (-0.02, 1000)
- failure_reason_counts: gate0_fail_weak_field=321; tail_sign_na:NA=582; tail_sign_na:sign_bias_not_detectable=12
- strong_checks: pass_wf_0.02_primary=true; range_robust_two_windows=false; tail_sign_not_failed=true; endpoint_not_dominant=false; low_perturbation_variance=true
- promotion_level: candidate

### Parameter Topology Notes

- basin movement: Stable interior basin centered near alpha ~ -0.02 across thresholds.
- alpha sign trend: Survivors remain predominantly negative-alpha in the best region.
- lambda boundary behavior: Best lambda saturates at upper tested bound (1000).
- robustness trend: Weak-field robustness is stable under tightening threshold, but cross-window robustness remains unsatisfied.

### Interpretation (2-3 lines max)

Stable negative basin at alpha ~ -0.02 across tightening thresholds.
Weak-field compliance holds at the 2% level in the primary window.
Promotion is blocked by window robustness and endpoint dominance.

