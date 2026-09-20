# CURV Constraint Certification Spec v0.2

## Status and scope

This is the current certification contract for CURV's gravity-core computational instrument.

Certification v0.2 tests whether the implemented numerical and gate pipeline behaves reproducibly under declared internal reference, convergence, pruning, robustness, artifact, and regression checks.

It does **not** by itself:

- reproduce an external experimental bound;
- establish that a candidate gravity model describes nature;
- establish new physics;
- certify propulsion, anomalous phenomena, or UFS hypotheses;
- convert an internal promotion label into empirical evidence.

Historical v0.1 certification files remain in the repository for provenance.

## Environment

The current tested CI environment is pinned by the repository:

- Python 3.12.14;
- versions in `requirements.txt`;
- current commit hash recorded in every certification run.

The certification runner uses the interpreter that launches it. CI provisions the pinned interpreter and dependencies before invocation. Local users should create/activate an isolated environment and install `requirements.txt` before running certification.

## Required outputs

Every certification run writes:

```text
results/certification/<cert_id>/
    config_used.json
    metrics.csv
    summary.json
    environment_snapshot.json
    git_commit_hash.txt
    certification_report.json
    SUMMARY.txt
    checksums.json
    [test-declared artifacts]
```

A test is allowed to emit a plot, but plots are not globally mandatory unless that test declares one as a required artifact.

## C1 — Internal GR-limit reference reproduction

**Purpose:** Verify that the PPN sweep pipeline identifies the explicitly embedded GR-limit parameter, `gamma_ppn = 1`, and reproduces the same summary on a deterministic rerun.

**Checks:**

- best gamma matches the configured internal reference within the declared tolerance;
- repeated identical runs hash to the same selected summary fields.

**Important boundary:** This is an internal reference/pipeline test. It is not presented as reproduction of a published solar-system constraint.

## C2 — Schwarzschild integrator convergence

**Purpose:** Test the numerical GR baseline directly rather than using a proxy whose formula does not depend on the integration step size.

**Method:**

- evaluate the same Schwarzschild deflection curve at at least three decreasing RK4 step sizes;
- compare adjacent curves using mean normalized curve difference;
- require pairwise drift to stay below the declared limit;
- require convergence to be non-worsening under refinement;
- require deflection to remain monotonic with impact parameter;
- retain a weak-field sanity bound against analytic `4M/b`.

**Failure indicates:** numerical convergence or baseline-sanity trouble in the actual Schwarzschild integration path.

## C3 — Gate sensitivity and pruning

**Purpose:** Verify that tightening a weak-field threshold produces deterministic, monotonic, and non-vacuous pruning on a grid wide enough to exercise the gate.

**Checks:**

- tighter survivors <= baseline survivors <= looser survivors;
- a repeated baseline run has the same survivor count;
- tighter and looser thresholds do not produce identical survivor counts;
- changes in survivor fraction remain within the configured topology-jump fraction.

## C4 — Within-reference numerical robustness

**Purpose:** Separate two distinct questions:

1. Is the computation stable when numerical step size is perturbed while the reference model is fixed?
2. How sensitive is the answer to choosing analytic `4M/b` versus a numeric Schwarzschild reference?

Only the first question is a numerical-stability certification gate.

For each reference mode independently:

- best gamma must remain within the configured within-mode tolerance under step-size perturbation;
- promotion level must remain invariant under those step-size perturbations.

Analytic-vs-numeric differences are recorded as **reference-model sensitivity**. They are not mislabeled as numerical instability merely because the two baselines can produce different promotion labels.

## C5 — Artifact integrity

**Purpose:** Verify that the certification run leaves an auditable evidence trail.

Checks include:

- every artifact declared by C1–C4 exists;
- the certification-local registry contains appended rows;
- environment/config/git identity artifacts exist;
- checksums are recorded for relevant JSON/CSV and core run artifacts.

Plots are checked only when an upstream certification test declares a plot artifact.

## C6 — Regression lock

**Purpose:** Prevent silent behavioral drift against the versioned v0.2 acceptance baseline.

The baseline locks:

- C1 internal GR-limit center;
- C2 maximum adjacent refinement drift and non-worsening convergence;
- C3 monotonic and non-vacuous pruning;
- C4 within-reference promotion invariance and maximum within-mode gamma drift.

Cross-reference analytic-vs-numeric promotion equality is deliberately **not** a regression invariant.

## Overall verdict

Overall certification is `PASS` only when C1–C6 all pass.

A passing certification means:

> At the recorded commit and environment, CURV satisfied the v0.2 computational certification contract.

It does not mean that every modeled hypothesis is physically true.

## One-command execution

After activating an environment that satisfies the pinned repository requirements:

```bash
python certification/run_certification.py
```

The runner records its environment and commit, executes C1–C6, writes the certification report, and exits nonzero on any failed certification test.
