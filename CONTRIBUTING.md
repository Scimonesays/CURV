# Contributing

Thanks for improving this project. Keep changes technical, reproducible, and testable.

## Local setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run tests and baseline scripts

```powershell
python -m pytest -q
python -m src.gr_schwarzschild
python -m src.emergent_graph
python -m src.compare
python -m src.constraints
python -m src.trial_pipeline --gamma 1.0 --alpha 0.0 --lambda-au 1.0 --notes "registry check"
```

## Add a new toy model

1. Add a new module under `src/` with a clear entrypoint.
2. Save generated artifacts under `outputs/` using deterministic names.
3. Add/extend tests in `tests/` that verify core behavior and output structure.
4. Update `README.md` assumptions, limitations, and output list.
5. Ensure reproducibility with fixed seeds and fixed parameters.

## Style and runtime rules

- Deterministic runs (fixed random seeds where randomness exists).
- Script outputs must be written to `outputs/` and be re-generable from source.
- Keep typical full pipeline runtime under 60 seconds on a normal laptop.
- Keep dependencies minimal and documented in `requirements.txt`.
- Prefer explicit assumptions over implicit behavior.
- `results/registry/constraints_registry.csv` is append-only; do not edit prior rows.
- Registry `notes` should stay compact and audit-focused (gate summaries, source checks, promotion notes).

## Documentation update checklist

When behavior, thresholds, or artifact paths change:

1. Update `README.md` sections that describe phases, CLI usage, and outputs.
2. Update `Methodology.md` to keep gates and evidence policy consistent.
3. Keep terms consistent across docs (`run_id`, `artifacts`, `constraints_registry.csv`).
4. Ensure examples are executable in Windows PowerShell.

## Scope rule

This repository contains numerical toy models and analogical comparisons only.
Do not frame results as evidence of physical truth. Keep claims bounded to what
the code and tests directly demonstrate.
