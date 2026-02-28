"""Small numeric integration helpers."""

from __future__ import annotations

from typing import Callable

import numpy as np


def rk4_step(f: Callable[[float, np.ndarray], np.ndarray], t: float, y: np.ndarray, h: float) -> np.ndarray:
    """One RK4 step for y' = f(t, y)."""
    k1 = f(t, y)
    k2 = f(t + 0.5 * h, y + 0.5 * h * k1)
    k3 = f(t + 0.5 * h, y + 0.5 * h * k2)
    k4 = f(t + h, y + h * k3)
    return y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def integrate_ode(
    f: Callable[[float, np.ndarray], np.ndarray],
    t0: float,
    y0: np.ndarray,
    h: float,
    n_steps: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Integrate y' = f(t,y) with fixed-step RK4."""
    t = np.empty(n_steps + 1, dtype=float)
    y = np.empty((n_steps + 1, len(y0)), dtype=float)
    t[0] = t0
    y[0] = y0
    for i in range(n_steps):
        t[i + 1] = t[i] + h
        y[i + 1] = rk4_step(f, t[i], y[i], h)
    return t, y

