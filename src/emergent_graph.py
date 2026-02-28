"""Phase 2: emergent weighted-graph toy lensing."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from .config import (
    GRAPH_EPS,
    GRAPH_K_VALUES,
    GRAPH_N,
    GRAPH_BACKGROUND_NOISE,
    GRAPH_CONNECTIVITY_DEFAULT,
    GRAPH_MODE_DEFAULT,
    GRAPH_RADIUS,
    GRAPH_RAY_COUNT,
    GRAPH_RESOLUTION_N_BASE,
    GRAPH_SMOOTH_SIGMA_FACTOR,
    GRAPH_SOFT_BETA,
    GRAPH_SUPERPOSE_K,
    GRAPH_TIE_LAMBDA,
    GRAPH_WEAK_K_VALUES,
    GRAPH_W0,
    OUTPUT_DIR,
    SEED,
)
from .utils_plot import apply_default_style, save_figure


def node_id(i: int, j: int, n: int) -> int:
    return i * n + j


def id_to_ij(idx: int, n: int) -> tuple[int, int]:
    return (idx // n, idx % n)


def _resolve_sigma(n: int, sigma: float | None) -> float:
    if sigma is not None:
        return float(sigma)
    return max(float(n) * GRAPH_SMOOTH_SIGMA_FACTOR, 1.0)


def build_weight_field(
    n: int,
    w0: float,
    k: float,
    radius: float,
    mode: str = GRAPH_MODE_DEFAULT,
    sigma: float | None = None,
) -> np.ndarray:
    """Build a single-mass field in either hard-blob or smooth-gaussian mode."""
    w = _base_weight_template(n=n, w0=w0)
    cx = (n - 1) / 2.0
    cy = (n - 1) / 2.0
    xs, ys = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    r2 = (xs - cx) ** 2 + (ys - cy) ** 2
    if mode == "hard_blob":
        mask = r2 <= radius * radius
        w[mask] *= k
    elif mode == "smooth_gaussian":
        sigma_eff = _resolve_sigma(n=n, sigma=sigma)
        # k=1.02 means +2% at center with smooth radial decay.
        w *= 1.0 + (k - 1.0) * np.exp(-r2 / (sigma_eff * sigma_eff))
    else:
        raise ValueError(f"Unknown mode: {mode}")
    return w


def build_weight_field_multi(
    n: int,
    w0: float,
    masses: list[tuple[float, float, float]],
    radius: float,
    mode: str = GRAPH_MODE_DEFAULT,
    sigma: float | None = None,
) -> np.ndarray:
    """Build a field with one or more mass regions [(x_center, y_center, k_factor)]."""
    w = _base_weight_template(n=n, w0=w0)
    xs, ys = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    if mode == "hard_blob":
        for cx, cy, k in masses:
            mask = (xs - float(cx)) ** 2 + (ys - float(cy)) ** 2 <= radius * radius
            w[mask] *= float(k)
    elif mode == "smooth_gaussian":
        sigma_eff = _resolve_sigma(n=n, sigma=sigma)
        mult = np.ones_like(w)
        for cx, cy, k in masses:
            r2 = (xs - float(cx)) ** 2 + (ys - float(cy)) ** 2
            mult += (float(k) - 1.0) * np.exp(-r2 / (sigma_eff * sigma_eff))
        w *= mult
    else:
        raise ValueError(f"Unknown mode: {mode}")
    return w


def _base_weight_template(n: int, w0: float) -> np.ndarray:
    """
    Deterministic low-amplitude background structure to break shortest-path ties.

    This makes weak-k experiments numerically informative while preserving reproducibility.
    """
    rng = np.random.default_rng(SEED + n)
    noise = GRAPH_BACKGROUND_NOISE * rng.standard_normal((n, n))
    return np.clip(w0 * (1.0 + noise), 0.1 * w0, None)


def build_graph(
    weights: np.ndarray, eps: float = GRAPH_EPS, connectivity: int = GRAPH_CONNECTIVITY_DEFAULT
) -> csr_matrix:
    n = weights.shape[0]
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    if connectivity == 4:
        neighbors = ((1, 0, 1.0), (0, 1, 1.0))
    elif connectivity == 8:
        rt2 = float(np.sqrt(2.0))
        neighbors = (
            (1, 0, 1.0),
            (0, 1, 1.0),
            (1, 1, rt2),
            (1, -1, rt2),
        )
    else:
        raise ValueError(f"Unsupported connectivity: {connectivity}")

    for i in range(n):
        for j in range(n):
            a = node_id(i, j, n)
            for di, dj, step_len in neighbors:
                ni, nj = i + di, j + dj
                if ni >= n or nj >= n or nj < 0:
                    continue
                b = node_id(ni, nj, n)
                w_edge = 0.5 * (weights[i, j] + weights[ni, nj])
                cost = step_len / (w_edge + eps)
                rows.extend([a, b])
                cols.extend([b, a])
                vals.extend([cost, cost])
    size = n * n
    return csr_matrix((vals, (rows, cols)), shape=(size, size), dtype=float)


def choose_right_target(
    dist: np.ndarray, n: int, y_start: int, tie_lambda: float = GRAPH_TIE_LAMBDA
) -> int:
    y_all = np.arange(n, dtype=float)
    right_nodes = np.array([node_id(n - 1, int(y), n) for y in y_all], dtype=int)
    score = dist[right_nodes] + tie_lambda * np.abs(y_all - float(y_start))
    return int(right_nodes[int(np.argmin(score))])


def reconstruct_path(predecessors: np.ndarray, source: int, target: int) -> list[int]:
    out = [target]
    cur = target
    while cur != source:
        cur = int(predecessors[cur])
        if cur < 0:
            return []
        out.append(cur)
    out.reverse()
    return out


def path_xy(path: list[int], n: int) -> np.ndarray:
    arr = np.array([id_to_ij(p, n) for p in path], dtype=float)
    return arr


def _ray_starts(n: int, ray_count: int) -> np.ndarray:
    return np.linspace(2, n - 3, ray_count, dtype=int)


def _compute_ray_measure_and_paths(
    graph: csr_matrix,
    n: int,
    y_starts: np.ndarray,
    measure: str = "exit",
    return_paths: bool = False,
) -> tuple[np.ndarray, list[np.ndarray]]:
    values = np.empty(len(y_starts), dtype=float)
    paths: list[np.ndarray] = []
    for i, y0 in enumerate(y_starts):
        source = node_id(0, int(y0), n)
        dist, pred = dijkstra(graph, directed=False, indices=source, return_predecessors=True)
        target = choose_right_target(dist, n=n, y_start=int(y0))
        path = reconstruct_path(pred, source=source, target=target)
        xy = path_xy(path, n=n)
        if measure == "exit":
            values[i] = float(xy[-1, 1])
        elif measure == "mean_y":
            values[i] = float(np.mean(xy[:, 1]))
        else:
            raise ValueError(f"Unknown measure: {measure}")
        if return_paths:
            paths.append(xy)
    return values, paths


def _compute_deflection_series(
    n: int,
    w0: float,
    radius: float,
    ray_count: int,
    masses: list[tuple[float, float, float]],
    measure: str = "soft_exit",
    mode: str = GRAPH_MODE_DEFAULT,
    connectivity: int = GRAPH_CONNECTIVITY_DEFAULT,
    sigma: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y_starts = _ray_starts(n=n, ray_count=ray_count)
    center_y = (n - 1) / 2.0
    b_like = np.abs(y_starts.astype(float) - center_y)

    baseline = build_graph(
        build_weight_field(n=n, w0=w0, k=1.0, radius=radius, mode=mode, sigma=sigma),
        connectivity=connectivity,
    )
    scenario = build_graph(
        build_weight_field_multi(n=n, w0=w0, masses=masses, radius=radius, mode=mode, sigma=sigma),
        connectivity=connectivity,
    )

    if measure == "soft_exit":
        y_base = _compute_soft_exit_values(baseline, n=n, y_starts=y_starts, beta=GRAPH_SOFT_BETA)
        y_scn = _compute_soft_exit_values(scenario, n=n, y_starts=y_starts, beta=GRAPH_SOFT_BETA)
    else:
        y_base, _ = _compute_ray_measure_and_paths(
            baseline, n=n, y_starts=y_starts, measure=measure, return_paths=False
        )
        y_scn, _ = _compute_ray_measure_and_paths(
            scenario, n=n, y_starts=y_starts, measure=measure, return_paths=False
        )
    return y_starts.astype(float), b_like, (y_scn - y_base)


def _compute_soft_exit_values(graph: csr_matrix, n: int, y_starts: np.ndarray, beta: float) -> np.ndarray:
    """Continuous proxy for exit-y using Boltzmann weighting over right boundary nodes."""
    y_all = np.arange(n, dtype=float)
    right_nodes = np.array([node_id(n - 1, int(y), n) for y in y_all], dtype=int)
    out = np.empty(len(y_starts), dtype=float)
    for i, y0 in enumerate(y_starts):
        source = node_id(0, int(y0), n)
        dist = dijkstra(graph, directed=False, indices=source, return_predecessors=False)
        d_right = dist[right_nodes]
        d_shift = d_right - float(np.min(d_right))
        weights = np.exp(-beta * d_shift)
        weights /= np.sum(weights)
        out[i] = float(np.sum(weights * y_all))
    return out


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot <= 1.0e-12:
        return 1.0 if ss_res <= 1.0e-12 else 0.0
    return 1.0 - (ss_res / ss_tot)


def _aic(y_true: np.ndarray, y_pred: np.ndarray, n_params: int) -> float:
    n_obs = int(len(y_true))
    if n_obs <= 0:
        return float("nan")
    rss = float(np.sum((y_true - y_pred) ** 2))
    rss = max(rss, 1.0e-12)
    return float(n_obs * np.log(rss / n_obs) + 2.0 * float(n_params))


def _inverse_model(b: np.ndarray, a: float, b0: float, c: float) -> np.ndarray:
    return a / (b + b0) + c


def run_weak_scaling_fit(
    output_dir: Path,
    n: int = GRAPH_N,
    w0: float = GRAPH_W0,
    radius: float = GRAPH_RADIUS,
    ray_count: int = GRAPH_RAY_COUNT,
    k_values: list[float] | None = None,
    mode: str = GRAPH_MODE_DEFAULT,
    connectivity: int | None = None,
    sigma: float | None = None,
) -> np.ndarray:
    if k_values is None:
        k_values = list(GRAPH_WEAK_K_VALUES)
    if connectivity is None:
        connectivity = 8 if mode == "smooth_gaussian" else GRAPH_CONNECTIVITY_DEFAULT

    rows: list[list[float]] = []
    fig, axes = plt.subplots(len(k_values), 1, figsize=(8, 3.2 * len(k_values)), sharex=True)
    if len(k_values) == 1:
        axes = [axes]

    cx = (n - 1) / 2.0
    cy = (n - 1) / 2.0
    for ax, k in zip(axes, k_values):
        _, b_like, deflection = _compute_deflection_series(
            n=n,
            w0=w0,
            radius=radius,
            ray_count=ray_count,
            masses=[(cx, cy, float(k))],
            mode=mode,
            connectivity=connectivity,
            sigma=sigma,
        )
        y = np.abs(deflection)
        x = b_like
        order = np.argsort(x)
        x = x[order]
        y = y[order]

        p_lin = np.polyfit(x, y, 1)
        y_lin = np.polyval(p_lin, x)
        y_const = np.full_like(y, np.mean(y))

        try:
            p0 = [max(float(np.max(y) * (np.mean(x) + 1.0)), 1.0e-3), 1.0, float(np.min(y))]
            bounds = ([-np.inf, 1.0e-6, -np.inf], [np.inf, np.inf, np.inf])
            popt, _ = curve_fit(_inverse_model, x, y, p0=p0, bounds=bounds, maxfev=5000)
            y_inv = _inverse_model(x, *popt)
            a_fit, b0_fit, c_fit = [float(v) for v in popt]
        except Exception:
            a_fit, b0_fit, c_fit = np.nan, np.nan, np.nan
            y_inv = np.full_like(y, np.mean(y))

        r2_inv = _r2(y, y_inv)
        r2_lin = _r2(y, y_lin)
        r2_const = _r2(y, y_const)
        aic_inv = _aic(y, y_inv, n_params=3)
        aic_lin = _aic(y, y_lin, n_params=2)
        rows.append([float(k), a_fit, b0_fit, c_fit, r2_inv, r2_lin, r2_const, aic_inv, aic_lin])

        ax.scatter(x, y, s=24, label="data")
        ax.plot(x, y_inv, "-", lw=2, label="inverse fit")
        ax.plot(x, y_lin, "--", lw=1.5, label="linear baseline")
        ax.plot(x, y_const, ":", lw=1.5, label="constant baseline")
        ax.set_ylabel("|deflection|")
        ax.set_title(f"Weak scaling fit ({mode}, k={k:.2f})")
        ax.legend(fontsize=8)
    axes[-1].set_xlabel("b-like offset")
    suffix = f"graph_scaling_fit_{mode}"
    fig.tight_layout()
    fig.savefig(output_dir / f"{suffix}.png", dpi=180)
    if mode == "hard_blob":
        # Keep legacy filename for compatibility with existing workflow.
        fig.savefig(output_dir / "graph_scaling_fit.png", dpi=180)
    plt.close(fig)

    table = np.array(rows, dtype=float)
    np.savetxt(
        output_dir / f"{suffix}.csv",
        table,
        delimiter=",",
        header="k,A,b0,C,r2_inverse,r2_linear,r2_constant,aic_inverse,aic_linear",
        comments="",
    )
    if mode == "hard_blob":
        np.savetxt(
            output_dir / "graph_scaling_fit.csv",
            table,
            delimiter=",",
            header="k,A,b0,C,r2_inverse,r2_linear,r2_constant,aic_inverse,aic_linear",
            comments="",
        )
    return table


def run_superposition_test(
    output_dir: Path,
    n: int = GRAPH_N,
    w0: float = GRAPH_W0,
    radius: float = GRAPH_RADIUS,
    ray_count: int = GRAPH_RAY_COUNT,
    k: float = GRAPH_SUPERPOSE_K,
    mode: str = GRAPH_MODE_DEFAULT,
    connectivity: int | None = None,
    sigma: float | None = None,
) -> np.ndarray:
    if connectivity is None:
        connectivity = 8 if mode == "smooth_gaussian" else GRAPH_CONNECTIVITY_DEFAULT
    y0 = (n - 1) / 2.0
    x1 = (n - 1) * 0.35
    x2 = (n - 1) * 0.65

    y_starts, b_like, d0 = _compute_deflection_series(
        n=n, w0=w0, radius=radius, ray_count=ray_count, masses=[], mode=mode, connectivity=connectivity, sigma=sigma
    )
    _, _, d_a = _compute_deflection_series(
        n=n, w0=w0, radius=radius, ray_count=ray_count, masses=[(x1, y0, k)], mode=mode, connectivity=connectivity, sigma=sigma
    )
    _, _, d_b = _compute_deflection_series(
        n=n, w0=w0, radius=radius, ray_count=ray_count, masses=[(x2, y0, k)], mode=mode, connectivity=connectivity, sigma=sigma
    )
    _, _, d_ab = _compute_deflection_series(
        n=n, w0=w0, radius=radius, ray_count=ray_count, masses=[(x1, y0, k), (x2, y0, k)], mode=mode, connectivity=connectivity, sigma=sigma
    )

    d_a_plus_d_b = d_a + d_b - d0
    residual = d_ab - d_a_plus_d_b
    rel_error = np.abs(residual) / np.maximum(np.abs(d_a_plus_d_b), 1.0e-6)

    table = np.column_stack([b_like, d0, d_a, d_b, d_ab, d_a_plus_d_b, residual, rel_error])
    np.savetxt(
        output_dir / "graph_superposition.csv",
        table,
        delimiter=",",
        header="b,d0,dA,dB,dAB,dA_plus_dB,residual,rel_error",
        comments="",
    )

    fig, (ax0, ax1) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    order = np.argsort(b_like)
    xb = b_like[order]
    ax0.plot(xb, d_ab[order], "o-", label="dAB")
    ax0.plot(xb, d_a_plus_d_b[order], "s--", label="dA + dB - d0")
    ax0.set_ylabel("deflection")
    ax0.set_title("Weak Superposition Test (k=1.02)")
    ax0.legend()
    ax1.plot(xb, residual[order], "o-", label="residual")
    ax1.axhline(0.0, color="k", lw=1)
    ax1.set_xlabel("b-like offset")
    ax1.set_ylabel("residual")
    ax1.legend()
    save_figure(fig, output_dir / "graph_superposition.png")
    return table


def run_resolution_robustness(
    output_dir: Path,
    n_base: int = GRAPH_RESOLUTION_N_BASE,
    w0: float = GRAPH_W0,
    radius: float = GRAPH_RADIUS,
    ray_count: int = GRAPH_RAY_COUNT,
    k: float = GRAPH_SUPERPOSE_K,
    mode: str = GRAPH_MODE_DEFAULT,
    connectivity: int | None = None,
    sigma: float | None = None,
) -> np.ndarray:
    if connectivity is None:
        connectivity = 8 if mode == "smooth_gaussian" else GRAPH_CONNECTIVITY_DEFAULT
    n_hi = 2 * n_base - 1
    c0_base = (n_base - 1) / 2.0
    c0_hi = (n_hi - 1) / 2.0

    _, b_base, d_base = _compute_deflection_series(
        n=n_base, w0=w0, radius=radius, ray_count=ray_count, masses=[(c0_base, c0_base, k)], mode=mode, connectivity=connectivity, sigma=sigma
    )
    _, b_hi, d_hi = _compute_deflection_series(
        n=n_hi, w0=w0, radius=radius * (n_hi / n_base), ray_count=ray_count, masses=[(c0_hi, c0_hi, k)], mode=mode, connectivity=connectivity, sigma=sigma
    )

    x_base = b_base / float(n_base - 1)
    x_hi = b_hi / float(n_hi - 1)
    y_base = np.abs(d_base) / max(float(np.max(np.abs(d_base))), 1.0e-12)
    y_hi = np.abs(d_hi) / max(float(np.max(np.abs(d_hi))), 1.0e-12)

    x_common = np.linspace(0.0, min(float(np.max(x_base)), float(np.max(x_hi))), 60)
    y_base_i = np.interp(x_common, np.sort(x_base), y_base[np.argsort(x_base)])
    y_hi_i = np.interp(x_common, np.sort(x_hi), y_hi[np.argsort(x_hi)])
    abs_diff = np.abs(y_base_i - y_hi_i)

    table = np.column_stack([x_common, y_base_i, y_hi_i, abs_diff])
    np.savetxt(
        output_dir / "graph_resolution_robustness.csv",
        table,
        delimiter=",",
        header="b_norm,d_norm_n,d_norm_2n,abs_diff",
        comments="",
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x_common, y_base_i, "o-", label=f"N={n_base}")
    ax.plot(x_common, y_hi_i, "s--", label=f"N={n_hi}")
    ax.set_xlabel("normalized b-like offset")
    ax.set_ylabel("normalized |deflection|")
    ax.set_title("Resolution Robustness (weak regime k=1.02)")
    ax.legend()
    save_figure(fig, output_dir / "graph_resolution_robustness.png")
    return table


def _write_phase4_summary(
    output_dir: Path, scaling_fit: np.ndarray, superposition: np.ndarray, resolution: np.ndarray
) -> None:
    # Use b >= 4 to avoid immediate mass-core region where discrete effects dominate.
    far_mask = superposition[:, 0] >= 4.0
    median_rel_error = float(np.median(superposition[far_mask, 7])) if np.any(far_mask) else float(
        np.median(superposition[:, 7])
    )
    mean_abs_res_curve_diff = float(np.mean(resolution[:, 3]))
    best_k = float(scaling_fit[np.argmax(scaling_fit[:, 4]), 0])

    summary = f"""# New GR Toy Models: Comparison Summary

## What is analogous
- Both systems define path trajectories from a geometry rule and produce path bending near localized perturbations.
- Both show larger deflection-like response for smaller distance-to-center trajectories.
- Both are deterministic and reproducible under fixed seeds.

## What is not analogous
- GR lensing is continuous metric geometry; the graph model is a discrete shortest-path system.
- GR deflection is angular (radians); graph deflection is exit-node shift (grid units).
- Similar normalized shapes do not imply physical identity.

## Falsifiability criteria (upgraded)
- GR anchor: baseline GR must remain monotonic in b and approach weak-field 4M/b at large b.
- Weak inverse-distance fit: in weak regime (k close to 1), inverse model must outperform linear and constant baselines (best weak-fit k={best_k:.2f}).
- Weak superposition: median relative error for dAB vs (dA+dB-d0) at b>=4 must stay below 0.25 (current median={median_rel_error:.3f}).
- Resolution robustness: mean absolute difference between normalized N and 2N weak curves must stay below 0.15 (current mean={mean_abs_res_curve_diff:.3f}).
"""
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")


def run_graph_model(
    output_dir: Path = OUTPUT_DIR,
    n: int = GRAPH_N,
    w0: float = GRAPH_W0,
    radius: float = GRAPH_RADIUS,
    k_values: list[float] | None = None,
    ray_count: int = GRAPH_RAY_COUNT,
    mode: str = GRAPH_MODE_DEFAULT,
    connectivity: int | None = None,
    sigma: float | None = None,
) -> np.ndarray:
    np.random.seed(SEED)
    apply_default_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    if k_values is None:
        k_values = list(GRAPH_K_VALUES)
    if connectivity is None:
        connectivity = 8 if mode == "smooth_gaussian" else GRAPH_CONNECTIVITY_DEFAULT

    baseline_graph = build_graph(
        build_weight_field(n=n, w0=w0, k=1.0, radius=radius, mode=mode, sigma=sigma),
        connectivity=connectivity,
    )
    y_starts = np.linspace(2, n - 3, ray_count, dtype=int)
    center_y = (n - 1) / 2.0

    rows: list[list[float]] = []
    baseline_paths: list[np.ndarray] = []
    mass_paths_for_plot: list[np.ndarray] = []
    k_plot = max(k_values)

    y_exit_base, baseline_paths = _compute_ray_measure_and_paths(
        baseline_graph, n=n, y_starts=y_starts, measure="exit", return_paths=True
    )
    mass_graphs = {
        float(k): build_graph(
            build_weight_field(n=n, w0=w0, k=float(k), radius=radius, mode=mode, sigma=sigma),
            connectivity=connectivity,
        )
        for k in k_values
    }
    for k in k_values:
        y_exit_mass, k_paths = _compute_ray_measure_and_paths(
            mass_graphs[float(k)],
            n=n,
            y_starts=y_starts,
            measure="exit",
            return_paths=abs(float(k) - k_plot) < 1.0e-12,
        )
        for i, y0 in enumerate(y_starts):
            deflection = float(y_exit_mass[i] - y_exit_base[i])
            rows.append(
                [
                    float(k),
                    float(y0),
                    abs(float(y0) - center_y),
                    float(y_exit_base[i]),
                    float(y_exit_mass[i]),
                    deflection,
                ]
            )
        if abs(float(k) - k_plot) < 1.0e-12:
            mass_paths_for_plot = k_paths

    table = np.array(rows, dtype=float)
    np.savetxt(
        output_dir / "graph_deflection.csv",
        table,
        delimiter=",",
        header="k,y_start,b_like,y_exit_baseline,y_exit_mass,deflection",
        comments="",
    )

    fig, ax = plt.subplots(figsize=(7, 6))
    for p in baseline_paths:
        ax.plot(p[:, 0], p[:, 1], alpha=0.8)
    ax.set_title("Graph Rays Baseline (k=1)")
    ax.set_xlabel("x node")
    ax.set_ylabel("y node")
    ax.set_aspect("equal")
    save_figure(fig, output_dir / "graph_rays_baseline.png")

    fig, ax = plt.subplots(figsize=(7, 6))
    for p in mass_paths_for_plot:
        ax.plot(p[:, 0], p[:, 1], alpha=0.8)
    ax.scatter([(n - 1) / 2.0], [(n - 1) / 2.0], c="red", marker="x", s=60, label="mass center")
    ax.set_title(f"Graph Rays with Mass Region (k={k_plot:.1f})")
    ax.set_xlabel("x node")
    ax.set_ylabel("y node")
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8)
    save_figure(fig, output_dir / "graph_rays_mass.png")

    fig, ax = plt.subplots(figsize=(7, 5))
    for k in k_values:
        mask = np.isclose(table[:, 0], float(k))
        x = table[mask, 2]
        y = np.abs(table[mask, 5])
        order = np.argsort(x)
        ax.plot(x[order], y[order], "o-", label=f"k={k:.1f}")
    ax.set_title("Deflection-like Magnitude vs b-like Offset")
    ax.set_xlabel("b-like offset |y_start - y_center|")
    ax.set_ylabel("|deflection| in exit y")
    ax.legend()
    save_figure(fig, output_dir / "graph_deflection_curve.png")
    return table


def main() -> None:
    output_dir = OUTPUT_DIR
    run_graph_model(output_dir, mode="hard_blob", connectivity=4)
    run_weak_scaling_fit(output_dir=output_dir, mode="hard_blob", connectivity=4)
    scaling_smooth = run_weak_scaling_fit(
        output_dir=output_dir, mode="smooth_gaussian", connectivity=8
    )
    superposition = run_superposition_test(output_dir=output_dir)
    resolution = run_resolution_robustness(output_dir=output_dir)
    # Summary focuses on the smoother field variant as the stricter structural probe.
    _write_phase4_summary(output_dir, scaling_smooth, superposition, resolution)


if __name__ == "__main__":
    main()

