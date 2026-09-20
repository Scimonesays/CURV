# Pilot Note: Yukawa 11x9 Sweep (2026-02-28)

## Scope

This note documents pilot attempts for:

`scripts/sweep_yukawa_constraints.py`

with settings:

- `alpha_y` in `[-0.10, 0.10]`, `11` steps
- `lambda_y_over_m` in `[1, 1000]`, `9` log-spaced steps
- `wf_thresh_seq = 0.05,0.03,0.02`
- `range_windows = 50:500,100:1000`
- `n_points = 320`, `h = 0.18`
- `wf_ref_mode = numeric`
- `notes = pilot_11x9`

## Observed Outcome

- Multiple pilot attempts were launched with the same command block.
- One completed with nonzero exit (`exit_code = 1`) after long runtime.
- Another remained compute-active for an extended period and was terminated to prevent runaway runtime.
- No `*_yukawa_sweep_summary.json` artifact was produced during these attempts.

## Practical Interpretation

- The script wiring and CLI parse correctly (`--help` and bytecode compile checks pass).
- The operational bottleneck appears in long numeric-reference compute for this environment at `n_points = 320`.
- Because no summary artifact was written, semantic checks (`survivors_by_thresh`, `best_params`, failure atlas) are not yet available from this pilot.

## Recommended Next Step

Run a reduced-cost diagnostic pilot to validate artifact semantics first, then return to the full baseline:

```powershell
python scripts/sweep_yukawa_constraints.py `
  --alpha-min -0.10 --alpha-max 0.10 --alpha-steps 11 `
  --lambda-min 1 --lambda-max 1000 --lambda-steps 9 --lambda-spacing log `
  --wf-thresh-seq "0.05,0.03,0.02" `
  --range-windows "50:500,100:1000" `
  --n-points 120 --h 0.18 `
  --wf-ref-mode numeric `
  --notes "pilot_11x9_n120"
```

If this completes and writes summary artifacts, compare:

- `survivors_by_thresh` monotonicity
- `best_params` consistency near `alpha_y ~= 0`
- `failure_reason_counts` interpretability
- heatmap continuity (non-checkerboard behavior)

Then rerun at `n_points = 320` for publication-grade baseline consistency.
