# New GR Toy Models (Reproducible Suite)

Minimal Python simulation suite for:

1. Schwarzschild lensing baseline (null geodesics, equatorial plane)
2. Emergent weighted-graph toy lensing
3. Side-by-side normalized comparison

## What this repo is / is not

- **Is:** explicit assumptions, deterministic scripts, and inspectable math-to-plot pipelines.
- **Is not:** a claim that any toy model is physically true or equivalent to GR.
- **Scope:** technical, reproducible analogies only.

## Install (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run and test (Windows PowerShell)

```powershell
python -m pytest -q
python -m src.gr_schwarzschild
python -m src.emergent_graph
python -m src.compare
```

## Reproducibility guarantee

- Fixed parameters and deterministic computation paths are used.
- Running the three module entrypoints regenerates `outputs/` from source.
- CI-equivalent local check is: tests green + expected files present.

## Requirements

Only these libraries are used:

- `numpy`
- `scipy`
- `matplotlib`
- `pytest`

## Outputs (`outputs/`)

### Phase 1 (GR baseline)
- `gr_deflection.csv`
- `gr_lensing_paths.png`
- `gr_deflection_curve.png`

### Phase 2 (graph toy model and robustness)
- `graph_deflection.csv`
- `graph_rays_baseline.png`
- `graph_rays_mass.png`
- `graph_deflection_curve.png`
- `graph_resolution_robustness.csv`
- `graph_resolution_robustness.png`
- `graph_scaling_fit.csv`
- `graph_scaling_fit.png`
- `graph_scaling_fit_hard_blob.csv`
- `graph_scaling_fit_hard_blob.png`
- `graph_scaling_fit_smooth_gaussian.csv`
- `graph_scaling_fit_smooth_gaussian.png`
- `graph_superposition.csv`
- `graph_superposition.png`

### Phase 3 (comparison)
- `deflection_comparison.png`
- `summary.md`

## Assumptions and limits

- Units in GR phase: `G = c = 1`.
- GR simulation uses null geodesics in Schwarzschild equatorial plane via the `u(phi) = 1/r` equation.
- Weak-field relation `alpha ~= 4M/b` is used as a baseline and is expected to fit better for larger `b`.
- Graph phase is a discrete shortest-path toy model with local entanglement-weight boost in a mass region.
- Graph deflection is exit-node shift (grid units), not a physical angle.
- Matching normalized curve shape does not imply physical equivalence.
- Toy analogies are not proof of nature.

## Roadmap

- **Phase 4A:** tighten comparison metrics, uncertainty sweeps, and robustness checks.
- **Next:** Yukawa-like alternatives and simple PPN-style comparison extensions.
