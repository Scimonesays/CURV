# Exotic Power Feasibility Tripwire

The exotic power feasibility tripwire is a **conservative gate** inside source plausibility. It computes hard numbers (power, duration, energy density, mass-equivalent) and refuses to promote exotic-matter power claims unless they pass policy ceilings and are explicitly allowed.

**It does not generate exotic matter.** It ensures any exotic candidate is subject to the same brutal accounting as conventional sources.

## Gates

Given `required_power_w`, `mission_duration_s`, and `active_volume_m3`:

- `E_required_j = P × t`
- `rho_required_j_m3 = E_required_j / active_volume_m3`
- `m_equiv_kg = E_required_j / c²`

**Policy gates:**

1. **Evidence gate (default fail):** Exotic matter is not a demonstrated controllable power source → fails unless explicitly allowed.
2. **Density ceiling:** Reject if `rho_required_j_m3` exceeds the policy ceiling.
3. **Total energy ceiling:** Reject if `E_required_j` exceeds the policy ceiling.
4. **Negative-energy budget (optional):** When `assumed_negative_energy_j` is set, reject if it exceeds the policy ceiling.

## Policy Presets

| Preset | Intent | allow_speculative | max_total_energy_j | max_rho_j_m3 | max_negative_energy_j |
|--------|--------|-------------------|--------------------|--------------|------------------------|
| `strict` | If it smells like magic, it fails. | `false` | (unused) | (unused) | 0 |
| `normal` | Conservative ceilings, exploration only if explicitly enabled. | from `--allow-speculative-exotic` | 1e12 | 1e12 | 0 |
| `sandbox` | Permit exploration of crazy parameter space. | `true` | 1e18 | 1e18 | 1e18 |

## Output Fields

- `passed`: `true` only if all gates pass.
- `reasons`: List of failure reasons (e.g. `exotic_not_demonstrated_as_power_source`, `total_energy_exceeds_policy_ceiling`).
- `dominant_violation`: One of `evidence_gate` | `rho_ceiling` | `total_energy_ceiling` | `neg_energy_budget` | `none`. Filters registry by *why* things failed.

## CLI (run_source_plausibility.py)

```powershell
# Default: exotic lane computed and logged, but always fails (evidence gate)
python scripts/run_source_plausibility.py --required-power-w 1e6 --mission-duration-s 3600

# Use preset (overrides individual exotic flags)
python scripts/run_source_plausibility.py --required-power-w 1e6 --mission-duration-s 3600 `
  --exotic-preset strict

# Normal preset + allow speculative for small hypothetical exploration
python scripts/run_source_plausibility.py --required-power-w 1e4 --mission-duration-s 1e2 `
  --exotic-preset normal --allow-speculative-exotic `
  --active-volume-m3 1
```

### Exotic Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--exotic-preset` | — | `strict` \| `normal` \| `sandbox`. Overrides individual exotic flags. |
| `--allow-speculative-exotic` | `false` | Allow exotic lane to pass if within ceilings. For `normal` preset, enables speculative mode. |
| `--active-volume-m3` | 1.0 | Active volume (m³) for energy-density and mass-equivalent computation. |
| `--exotic-max-rho-j-m3` | 1e18 | Energy density ceiling (used when no preset). |
| `--exotic-max-total-energy-j` | 1e15 | Total mission energy ceiling (used when no preset). |
| `--exotic-max-negative-energy-j` | 0 | Negative-energy budget ceiling (used when no preset). |
| `--assumed-negative-energy-j` | — | Optional claimed negative-energy budget for WEC/NEC-violating fuel screening. |

## CLI (run_source_phase_map.py)

Same exotic arguments. When `--allow-speculative-exotic` is set:

- `run_id` is suffixed with `_speculative` (e.g. `...energy_source_phase_map_speculative`)
- Summary includes `plot_annotation: "SPECULATIVE MODE"`

This prevents future-you from opening a plot and forgetting the flag.

## Registry Notes

When source plausibility runs, `notes` includes:

```
exotic_tripwire: pass=false; preset=strict; allow_speculative=false; dominant=evidence_gate; reasons=[exotic_not_demonstrated_as_power_source]
```

## Module

- `src/exotic_power_feasibility.py`: `ExoticPowerPolicy`, `exotic_policy_from_preset()`, `evaluate_exotic_power_feasibility()`
