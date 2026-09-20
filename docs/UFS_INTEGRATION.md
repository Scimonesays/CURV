# Universal Frequency Spectrum Integration

CURV can act as a **read-only research validator** for the Universal Frequency Spectrum (UFS).

This does not merge the two projects.

## Roles

- **UFS** owns the canonical atlas, scientific evidence status, frequency data, interactions, energy accounting, frontier/question nodes, and typed gaps.
- **CURV** supplies reproducible validation jobs, gates, artifacts, registries, policy modes, and domain-specific constraint machinery.

CURV may say:

- `READY_FOR_CONSTRAINT_DESIGN`
- `NEEDS_OPERATIONALIZATION`
- `HOLD_EVIDENCE`
- `INCONCLUSIVE`

Those are research-readiness verdicts.

CURV does **not** automatically promote a UFS record from speculative to established.

## Local connection

CURV searches for UFS in this order:

1. explicit `--ufs-repo` path;
2. `UFS_REPO_PATH` environment variable;
3. sibling directory `../Universal-Frequency-Spectrum`.

Example:

```powershell
$env:UFS_REPO_PATH = "C:\path\to\Universal-Frequency-Spectrum"
python -m console
```

The console's **UFS** lane reads canonical data directly from UFS.

## Web API

- `GET /api/ufs` — connection state, canonical counts, frontier/question records, typed gaps.
- `GET /api/ufs/records/{id}` — canonical UFS record lookup.

The API is read-only with respect to UFS.

## Validation job

```powershell
python scripts/run_ufs_candidate_validation.py --record-id P4-F012 --policy strict
```

The job:

1. reads the UFS canonical record;
2. checks source traceability;
3. checks candidate/question specificity;
4. checks predicted observable specificity;
5. checks bridge/coupling specificity;
6. records the energy-accounting status;
7. writes a CURV artifact and append-only registry row.

Registry:

`results/registry/ufs_validation_registry.csv`

Artifact:

`results/artifacts/<run_id>/raw/<run_id>_ufs_validation.json`

## What happens next

A result that reaches `READY_FOR_CONSTRAINT_DESIGN` is eligible for a **domain-specific** CURV test only when CURV actually has the relevant physics.

Examples:

- gravity deviations / black-hole alternatives / wormhole signatures → gravity tooling may be relevant;
- new energy-source claims → source/energy plausibility tools may be relevant;
- telepathy / soul / afterlife → generic readiness only until a measurable physical carrier/model exists.

This prevents CURV from becoming a universal answer machine.

It remains a constraint instrument.
