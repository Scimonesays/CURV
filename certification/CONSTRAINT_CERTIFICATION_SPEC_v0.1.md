# CURV Constraint Certification Spec v0.1

## Purpose

Define deterministic pass/fail criteria that establish CURV as an instrument-grade constraint engine.

Certification validates:

- Reference reproduction
- Resolution convergence
- Numerical robustness
- Gate stability
- Artifact integrity
- Regression consistency

Certification is binary: `PASS` or `FAIL`. No partial credit.

## Global Certification Conditions

These apply to all tests:

- Fixed seed where applicable
- Frozen config files stored under `certification/configs/`
- No manual intervention allowed
- Full artifact emission required
- Deterministic rerun must produce identical summary metrics

All certification runs must emit:

```text
results/certification/<cert_id>/
    config_used.json
    metrics.csv
    summary.json
    plots/
    environment_snapshot.json
    git_commit_hash.txt
    certification_report.json
```

## Test Matrix

### C1 - Reference Reproduction

**ID**  
`C1_reference_reproduction`

**Objective**  
Numerically reproduce a published solar-system PPN gamma bound.

**Input**  
Frozen reference config:

- Gamma grid centered at 1.0
- Solar-limb impact parameter
- Numeric weak-field baseline enabled
- Stable integrator settings

**Observable**  
Light deflection near solar limb.

**Acceptance Criterion**  
Recovered `|gamma - 1|` must fall within reference tolerance window.

Example window (configurable):  
`|gamma - 1| <= 2e-5` (or selected literature bound)

**Output Fields Required**

- `best_gamma_ppn`
- `uncertainty_band`
- `residual_curve`
- `tail_verdict`

**Failure Codes**

- `C1_FAIL_BOUND`
- `C1_FAIL_DRIFT`
- `C1_FAIL_NUMERIC`

### C2 - Resolution Convergence

**ID**  
`C2_resolution_convergence`

**Objective**  
Verify convergence under refinement.

**Resolutions**  
At minimum:

- `n_points`: 160, 320, 640
- Step size: `h`, `h-Δh`

**Acceptance Criteria**  
One of:

- Monotonic convergence of key observable, or
- Variation remains within certified tolerance band

Drift must shrink or remain bounded.

**Failure Codes**

- `C2_FAIL_DIVERGENCE`
- `C2_FAIL_OSCILLATION`
- `C2_FAIL_NONMONOTONIC`

### C3 - Gate Sensitivity Structure

**ID**  
`C3_gate_sensitivity`

**Objective**  
Confirm tightening weak-field thresholds produces structured pruning.

**Method**  
Run sweep at:

- Baseline threshold
- Tighter threshold
- Looser threshold

**Acceptance Criteria**

- Survivorship count decreases monotonically under tightening
- Topology shifts are smooth, not chaotic
- No discontinuous regime jumps without numerical cause

**Failure Codes**

- `C3_FAIL_CHAOTIC_PRUNING`
- `C3_FAIL_NONDETERMINISTIC`
- `C3_FAIL_TOPOLOGY_INSTABILITY`

### C4 - Numerical Robustness

**ID**  
`C4_numerical_robustness`

**Objective**  
Verify solver tolerance invariance.

**Perturbations**

- Integrator step size +/- small delta
- Solver tolerance +/- small delta
- Weak-field reference mode analytic vs numeric

**Acceptance Criteria**  
Conclusions (`promotion_level` + `best_gamma`) remain invariant within declared tolerance band.

**Failure Codes**

- `C4_FAIL_TOLERANCE_SENSITIVITY`
- `C4_FAIL_MODE_DEPENDENCE`
- `C4_FAIL_NUMERIC_INSTABILITY`

### C5 - Artifact Integrity

**ID**  
`C5_artifact_integrity`

**Objective**  
Verify full audit trail emission.

**Required Artifacts**

- Raw metrics CSV
- Summary JSON
- Plots
- Registry entry
- Commit hash
- Environment snapshot
- Checksums

**Acceptance Criteria**  
All artifacts present. Checksums match recorded hashes. No missing diagnostics.

**Failure Codes**

- `C5_FAIL_MISSING_ARTIFACT`
- `C5_FAIL_HASH_MISMATCH`
- `C5_FAIL_REGISTRY_APPEND`

### C6 - Regression Lock

**ID**  
`C6_regression_lock`

**Objective**  
Prevent silent drift.

**Method**  
Compare certification metrics to last certified baseline.

**Acceptance Criteria**  
All key metrics within tolerance band. If drift exceeds tolerance, fail unless explicitly version-bumped with explanation.

**Failure Codes**

- `C6_FAIL_UNEXPLAINED_DRIFT`
- `C6_FAIL_BASELINE_MISMATCH`

## Certification Report Schema

Every certification run must emit `certification_report.json` using this schema:

```json
{
  "cert_version": "0.1",
  "timestamp": "",
  "git_commit": "",
  "tests": {
    "C1_reference_reproduction": {
      "status": "PASS | FAIL",
      "details": "",
      "metrics": {}
    },
    "C2_resolution_convergence": {},
    "C3_gate_sensitivity": {},
    "C4_numerical_robustness": {},
    "C5_artifact_integrity": {},
    "C6_regression_lock": {}
  },
  "overall_status": "PASS | FAIL",
  "failure_codes": []
}
```

Overall `PASS` only if all C1-C6 pass.

## One-Command Certification

Final requirement (from clean environment):

```bash
python certification/run_certification.py
```

The command must:

1. Create venv if missing
2. Install requirements
3. Execute all C-tests
4. Emit `certification_report.json`
5. Print one of:

```text
CURV CERTIFICATION STATUS: PASS
```

or

```text
CURV CERTIFICATION STATUS: FAIL
Failure codes: [...]
```

No manual steps allowed.

## Tier 1 Success Definition

CURV is Tier 1 certified when:

- C1-C6 pass
- Certification report archived
- Commit hash frozen
- Reproducible on second machine

At that point, CURV is no longer only a personal experiment; it is an instrument.
