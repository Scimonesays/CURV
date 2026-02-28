from __future__ import annotations

import numpy as np

from src.utils_integrators import integrate_ode


def test_rk4_matches_exp_growth():
    def f(_t: float, y: np.ndarray) -> np.ndarray:
        return y

    t, y = integrate_ode(f=f, t0=0.0, y0=np.array([1.0]), h=0.01, n_steps=100)
    assert np.isclose(t[-1], 1.0)
    assert np.isclose(y[-1, 0], np.e, rtol=2.0e-4, atol=1.0e-6)

