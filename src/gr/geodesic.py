"""Geodesic integration utilities for equatorial Schwarzschild null rays."""

from __future__ import annotations

import math

import numpy as np

from src.gr.connection import christoffels_equatorial
from src.metrics.schwarzschild import metric_equatorial
from src.utils_integrators import rk4_step


def _geodesic_rhs(_, state: np.ndarray, *, mass: float, rel_step: float) -> np.ndarray:
    x = state[:3]
    v = state[3:]
    gamma = christoffels_equatorial(x=x, mass=mass, rel_step=rel_step)
    a = np.zeros(3, dtype=float)
    for mu in range(3):
        acc = 0.0
        for alpha in range(3):
            for beta in range(3):
                acc += gamma[mu, alpha, beta] * v[alpha] * v[beta]
        a[mu] = -acc
    return np.concatenate((v, a))


def null_vt(x: np.ndarray, vr: float, vphi: float, *, mass: float) -> float:
    """Solve null condition g_{mu,nu} v^mu v^nu = 0 for v^t."""
    g = metric_equatorial(x=x, mass=mass)
    spatial_term = (g[1, 1] * (vr * vr)) + (g[2, 2] * (vphi * vphi))
    vt_sq = -spatial_term / g[0, 0]
    if vt_sq <= 0.0:
        raise ValueError("Invalid null initial condition; v^t^2 <= 0.")
    return float(math.sqrt(vt_sq))


def _polar_velocity_to_cartesian(r: float, phi: float, vr: float, vphi: float) -> tuple[float, float]:
    vx = (vr * math.cos(phi)) - (r * math.sin(phi) * vphi)
    vy = (vr * math.sin(phi)) + (r * math.cos(phi) * vphi)
    return vx, vy


def _angle_wrap_signed(theta: float) -> float:
    return (theta + math.pi) % (2.0 * math.pi) - math.pi


def trace_null_ray(
    *,
    b_over_m: float,
    mass: float = 1.0,
    x0_over_m: float = 1000.0,
    dlambda: float = 0.5,
    max_steps: int = 36_000,
    rel_step: float = 1.0e-6,
) -> dict[str, np.ndarray | float]:
    """
    Integrate one null ray and return ray path and deflection estimate.

    A ray starts at x=-x0, y=b in asymptotically flat region and propagates
    toward +x. Deflection is measured from asymptotic incoming/outgoing spatial
    direction in the equatorial plane.
    """
    b = float(b_over_m) * mass
    x0 = float(x0_over_m) * mass
    if b <= 0.0:
        raise ValueError("b_over_m must be positive.")

    x_cart = -x0
    y_cart = b
    r0 = float(math.hypot(x_cart, y_cart))
    if r0 <= 2.0 * mass:
        raise ValueError("Initial radius must be outside Schwarzschild horizon.")
    phi0 = float(math.atan2(y_cart, x_cart))

    # Straight-line asymptotic initialization: xdot=+1, ydot=0.
    vr0 = x_cart / r0
    vphi0 = -y_cart / (r0 * r0)
    x_init = np.array([0.0, r0, phi0], dtype=float)
    vt0 = null_vt(x=x_init, vr=vr0, vphi=vphi0, mass=mass)
    state = np.array([x_init[0], x_init[1], x_init[2], vt0, vr0, vphi0], dtype=float)

    t_vals = [state[0]]
    r_vals = [state[1]]
    phi_vals = [state[2]]
    x_vals = [state[1] * math.cos(state[2])]
    y_vals = [state[1] * math.sin(state[2])]

    rhs = lambda lam, y: _geodesic_rhs(lam, y, mass=mass, rel_step=rel_step)
    reached_far_side = False
    min_r_seen = state[1]
    for _ in range(max_steps):
        state = rk4_step(rhs, t_vals[-1], state, dlambda)
        if state[1] <= 2.05 * mass:
            raise RuntimeError("Ray reached near-horizon region; not a scattering trajectory.")

        t_vals.append(state[0])
        r_vals.append(state[1])
        phi_vals.append(state[2])
        x_now = state[1] * math.cos(state[2])
        y_now = state[1] * math.sin(state[2])
        x_vals.append(x_now)
        y_vals.append(y_now)
        min_r_seen = min(min_r_seen, state[1])

        if x_now > x0 and state[1] >= 0.95 * r0 and min_r_seen < r0:
            reached_far_side = True
            break

    if not reached_far_side:
        raise RuntimeError("Ray did not return to asymptotic region before max_steps.")

    vx_in, vy_in = _polar_velocity_to_cartesian(r=r0, phi=phi0, vr=vr0, vphi=vphi0)
    vx_out, vy_out = _polar_velocity_to_cartesian(
        r=float(state[1]),
        phi=float(state[2]),
        vr=float(state[4]),
        vphi=float(state[5]),
    )
    theta_in = math.atan2(vy_in, vx_in)
    theta_out = math.atan2(vy_out, vx_out)
    alpha_signed = _angle_wrap_signed(theta_out - theta_in)
    alpha = abs(alpha_signed)

    return {
        "b": b,
        "b_over_m": b / mass,
        "alpha_numeric": alpha,
        "alpha_weakfield": 4.0 * mass / b,
        "r": np.array(r_vals, dtype=float),
        "phi": np.array(phi_vals, dtype=float),
        "x": np.array(x_vals, dtype=float),
        "y": np.array(y_vals, dtype=float),
        "t": np.array(t_vals, dtype=float),
    }

