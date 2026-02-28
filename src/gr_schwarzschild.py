"""Phase 1: Schwarzschild null-geodesic light deflection baseline."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import brentq

from .config import GR_B_VALUES, GR_R_MAX, GR_STEP, MASS_M, OUTPUT_DIR, SEED
from .utils_integrators import rk4_step
from .utils_plot import apply_default_style, save_figure


def weak_field_alpha(b: float, mass: float = MASS_M) -> float:
    return 4.0 * mass / b


def critical_b(mass: float = MASS_M) -> float:
    return 3.0 * np.sqrt(3.0) * mass


def turning_point_u(b: float, mass: float = MASS_M) -> float:
    """Solve 1/b^2 - u^2 + 2Mu^3 = 0 for scattering branch."""
    if b <= critical_b(mass):
        raise ValueError("Impact parameter must exceed critical value for scattering.")

    def f(u: float) -> float:
        return (1.0 / (b * b)) - (u * u) + (2.0 * mass * u * u * u)

    lo = 1.0e-12
    hi = 1.0 / (3.0 * mass)
    return brentq(f, lo, hi, xtol=1.0e-12, rtol=1.0e-10, maxiter=200)


def simulate_light_ray(
    b: float,
    mass: float = MASS_M,
    r_max: float = GR_R_MAX,
    h: float = GR_STEP,
    phi_max: float = 12.0,
) -> dict[str, np.ndarray | float]:
    """
    Integrate null geodesic in equatorial Schwarzschild plane.

    Uses u(phi)=1/r equation: u'' + u = 3 M u^2.
    """
    u0 = turning_point_u(b, mass=mass)
    u_stop = 1.0 / r_max

    def f(_, y: np.ndarray) -> np.ndarray:
        u, up = y
        return np.array([up, (3.0 * mass * u * u) - u], dtype=float)

    n_steps = int(phi_max / h)
    phi_vals = [0.0]
    state_vals = [np.array([u0, 0.0], dtype=float)]
    escaped = False

    for _ in range(n_steps):
        next_state = rk4_step(f, phi_vals[-1], state_vals[-1], h)
        phi_vals.append(phi_vals[-1] + h)
        state_vals.append(next_state)
        if next_state[0] <= u_stop and next_state[1] < 0.0:
            escaped = True
            break

    if not escaped:
        raise RuntimeError(f"Ray with b={b:.3f} did not reach r_max before phi_max.")

    phi_out = np.array(phi_vals, dtype=float)
    u_out = np.array([s[0] for s in state_vals], dtype=float)
    r_out = 1.0 / np.clip(u_out, 1.0e-12, None)

    phi_full = np.concatenate((-phi_out[:0:-1], phi_out))
    r_full = np.concatenate((r_out[:0:-1], r_out))
    x = r_full * np.cos(phi_full)
    y = r_full * np.sin(phi_full)

    phi_inf = phi_out[-1]
    alpha = (2.0 * phi_inf) - np.pi
    return {
        "b": float(b),
        "phi": phi_full,
        "r": r_full,
        "x": x,
        "y": y,
        "alpha_numeric": float(alpha),
        "alpha_weak": float(weak_field_alpha(b, mass=mass)),
    }


def run_gr_sweep(output_dir: Path = OUTPUT_DIR) -> np.ndarray:
    np.random.seed(SEED)
    output_dir.mkdir(parents=True, exist_ok=True)
    apply_default_style()

    rays = [simulate_light_ray(b=float(b)) for b in GR_B_VALUES]
    rows = []
    for ray in rays:
        alpha_num = float(ray["alpha_numeric"])
        alpha_weak = float(ray["alpha_weak"])
        rows.append([float(ray["b"]), alpha_num, alpha_weak, alpha_num - alpha_weak])
    table = np.array(rows, dtype=float)

    np.savetxt(
        output_dir / "gr_deflection.csv",
        table,
        delimiter=",",
        header="b,alpha_numeric,alpha_weak,alpha_diff",
        comments="",
    )

    fig, ax = plt.subplots(figsize=(8, 6))
    for ray in rays:
        ax.plot(ray["x"], ray["y"], lw=1.5, label=f"b={ray['b']:.1f}")
    ax.set_title("Schwarzschild Null Geodesics (Equatorial Plane)")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal")
    ax.set_xlim(-80, 80)
    ax.set_ylim(-50, 50)
    ax.legend(fontsize=8, ncol=2)
    save_figure(fig, output_dir / "gr_lensing_paths.png")

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(table[:, 0], table[:, 1], "o-", label="numeric")
    ax.plot(table[:, 0], table[:, 2], "s-", label="weak field 4M/b")
    ax.set_title("Deflection vs Impact Parameter")
    ax.set_xlabel("impact parameter b")
    ax.set_ylabel("deflection alpha (rad)")
    ax.legend()
    save_figure(fig, output_dir / "gr_deflection_curve.png")
    return table


def main() -> None:
    run_gr_sweep(OUTPUT_DIR)


if __name__ == "__main__":
    main()

