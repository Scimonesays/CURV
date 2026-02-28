"""Phase 3: side-by-side comparison and summary."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .config import OUTPUT_DIR
from .utils_plot import apply_default_style, save_figure


def run_comparison(output_dir: Path = OUTPUT_DIR) -> None:
    apply_default_style()
    gr = np.genfromtxt(output_dir / "gr_deflection.csv", delimiter=",", names=True)
    graph = np.genfromtxt(output_dir / "graph_deflection.csv", delimiter=",", names=True)

    k_max = float(np.max(graph["k"]))
    gmask = np.isclose(graph["k"], k_max)
    graph_k = graph[gmask]

    b_gr = gr["b"]
    a_gr = np.abs(gr["alpha_numeric"])
    b_gr_norm = (b_gr - np.min(b_gr)) / (np.max(b_gr) - np.min(b_gr))
    a_gr_norm = a_gr / np.max(a_gr)

    # Aggregate graph deflection by unique b-like offsets for max k.
    b_like = graph_k["b_like"]
    d_like = np.abs(graph_k["deflection"])
    uniq = np.unique(b_like)
    d_mean = np.array([np.mean(d_like[np.isclose(b_like, u)]) for u in uniq], dtype=float)
    b_graph_norm = uniq / np.max(uniq)
    d_graph_norm = d_mean / np.max(d_mean)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(b_gr_norm, a_gr_norm, "o-", label="GR baseline (normalized)")
    ax.plot(b_graph_norm, d_graph_norm, "s-", label=f"Graph toy (normalized, k={k_max:.1f})")
    ax.set_title("Normalized Deflection Comparison (Analogical)")
    ax.set_xlabel("normalized distance parameter")
    ax.set_ylabel("normalized deflection measure")
    ax.legend()
    save_figure(fig, output_dir / "deflection_comparison.png")

    summary = """# New GR Toy Models: Comparison Summary

## What is analogous
- Both systems define path trajectories from a geometry rule and produce path bending near a localized perturbation.
- Both produce stronger bending-like effects for rays that pass closer to the perturbation center.
- Both allow deterministic parameter sweeps and reproducible deflection metrics.

## What is not analogous
- Schwarzschild lensing is continuous spacetime geometry from GR; the graph model is a discrete shortest-path construction.
- GR deflection is an angle in radians for null geodesics; graph deflection is an exit-node shift in grid units.
- Matching normalized curve shape does not imply physical equivalence.

## What would falsify the toy analogy
- If increasing graph mass factor k does not increase average deflection-like magnitude, the toy mechanism fails.
- If rays far from the mass region bend as much as near-center rays, the locality assumption fails.
- If results are not reproducible with fixed seeds and fixed parameters, the model is not stable enough for interpretation.
"""
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")


def main() -> None:
    run_comparison(OUTPUT_DIR)


if __name__ == "__main__":
    main()

