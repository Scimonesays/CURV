# Exotic Stress-Energy Tripwire

CURV's exotic tripwire is an instrument, not a proof:

- It is **not** a tensor-level NEC/WEC proof.
- It uses deterministic proxies derived from residual structure and scaling.
- It flags candidate models that likely require exotic support if interpreted as stress-energy.

## Proxy Definitions

Given `alpha_model(b)`, `alpha_ref(b)`, residual `r(b)=alpha_model-alpha_ref`, and
normalized residual `delta(b)=r/max(|alpha_ref|,epsilon)`:

- `rho_proxy(b) = delta(b)` (WEC-like tripwire proxy)
- `nec_proxy(b) = min(delta(b), 0)` (NEC-like tail defocusing proxy)
- `rho_budget_tripwire`: `max(|rho_proxy|) > rho_budget_max` (budget ceiling on normalized residual)
- Tail scaling fit on selected `b` window:
  - `|delta(b)| ~ b^(-p)`
  - fit in log-space, then `scaling_tripwire = (p > p_max)`

## Scoring

`exoticity_score = w1*max(0,-rho_proxy_min) + w2*max(0,-nec_proxy_min) + w3*max(0,p-p_max)`

Default weights are `1.0`.

## CLI

```bash
python scripts/run_exotic_tripwire.py --input-run-id <run_id> --b-window 100:1000 --epsilon 1e-12
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--input-run-id` | *(required)* | Existing run_id with deflection curve artifacts |
| `--b-window` | `100:1000` | Scaling-fit window as `lo:hi` in b/M units |
| `--epsilon` | `1e-12` | Numerical floor for normalization/log safety |
| `--wec-floor` | `0.0` | WEC tripwire floor |
| `--nec-floor` | `0.0` | NEC tripwire floor |
| `--rho-budget-max` | `1e-3` | Rho-budget tripwire ceiling |
| `--scaling-limit-p-max` | `2.0` | Scaling power cap; tripwire triggers when `p > p_max` |
| `--score-w1` | `1.0` | Weight for WEC term in exoticity score |
| `--score-w2` | `1.0` | Weight for NEC term in exoticity score |
| `--score-w3` | `1.0` | Weight for scaling term in exoticity score |
| `--notes` | `""` | Optional run notes |
| `--no-registry` | — | Skip CSV/JSONL registry append |
| `--no-jsonl` | — | Disable JSONL mirror append |

