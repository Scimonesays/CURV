"""Finite-difference Christoffel symbols for metric-defined spacetimes."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from src.metrics.schwarzschild import inverse_metric_equatorial, metric_equatorial


def _fd_step(value: float, rel_step: float) -> float:
    scale = max(1.0, abs(value))
    return rel_step * scale


def _metric_partial(
    x: np.ndarray,
    *,
    alpha: int,
    mass: float,
    rel_step: float,
) -> np.ndarray:
    h = _fd_step(float(x[alpha]), rel_step=rel_step)
    xp = x.copy()
    xm = x.copy()
    xp[alpha] += h
    xm[alpha] -= h
    gp = metric_equatorial(x=xp, mass=mass)
    gm = metric_equatorial(x=xm, mass=mass)
    return (gp - gm) / (2.0 * h)


@lru_cache(maxsize=200_000)
def _christoffels_cached(
    t: float,
    r: float,
    phi: float,
    mass: float,
    rel_step: float,
) -> tuple[float, ...]:
    x = np.array([t, r, phi], dtype=float)
    g_inv = inverse_metric_equatorial(x=x, mass=mass)
    dg = np.empty((3, 3, 3), dtype=float)
    for alpha in range(3):
        dg[alpha] = _metric_partial(x=x, alpha=alpha, mass=mass, rel_step=rel_step)

    gamma = np.zeros((3, 3, 3), dtype=float)
    for mu in range(3):
        for alpha in range(3):
            for beta in range(3):
                acc = 0.0
                for nu in range(3):
                    acc += g_inv[mu, nu] * (
                        dg[alpha, nu, beta] + dg[beta, nu, alpha] - dg[nu, alpha, beta]
                    )
                gamma[mu, alpha, beta] = 0.5 * acc
    return tuple(gamma.reshape(-1))


def christoffels_equatorial(
    x: np.ndarray,
    *,
    mass: float,
    rel_step: float = 1.0e-6,
    cache_round_digits: int = 12,
) -> np.ndarray:
    """
    Return Gamma^mu_{alpha,beta} in equatorial Schwarzschild coordinates.

    Christoffels are computed from numerical metric derivatives and cached on a
    rounded coordinate grid to amortize repeated RK4 evaluations.
    """
    key_t = round(float(x[0]), cache_round_digits)
    key_r = round(float(x[1]), cache_round_digits)
    key_phi = round(float(x[2]), cache_round_digits)
    flat = _christoffels_cached(
        t=key_t,
        r=key_r,
        phi=key_phi,
        mass=float(mass),
        rel_step=float(rel_step),
    )
    return np.array(flat, dtype=float).reshape(3, 3, 3)

