"""Schwarzschild metric helpers in equatorial plane (theta = pi/2)."""

from __future__ import annotations

import numpy as np


def metric_equatorial(x: np.ndarray, mass: float) -> np.ndarray:
    """
    Return Schwarzschild metric g_{mu,nu} for coordinates (t, r, phi).

    The full 4D metric is reduced to the equatorial plane with theta fixed
    at pi/2 and dtheta = 0, yielding:
        ds^2 = -(1 - 2M/r) dt^2 + (1 - 2M/r)^(-1) dr^2 + r^2 dphi^2
    """
    r = float(x[1])
    if r <= 2.0 * mass:
        raise ValueError("Metric undefined at/below event horizon for this solver.")

    f = 1.0 - (2.0 * mass / r)
    g = np.zeros((3, 3), dtype=float)
    g[0, 0] = -f
    g[1, 1] = 1.0 / f
    g[2, 2] = r * r
    return g


def inverse_metric_equatorial(x: np.ndarray, mass: float) -> np.ndarray:
    """Return inverse metric g^{mu,nu} for equatorial Schwarzschild."""
    g = metric_equatorial(x=x, mass=mass)
    return np.linalg.inv(g)

