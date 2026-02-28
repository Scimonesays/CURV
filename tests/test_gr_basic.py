from __future__ import annotations

from src.gr_schwarzschild import simulate_light_ray


def test_gr_deflection_decreases_with_larger_b():
    b_values = [7.0, 9.0, 12.0, 16.0]
    alphas = [float(simulate_light_ray(b)["alpha_numeric"]) for b in b_values]
    for i in range(len(alphas) - 1):
        assert alphas[i] > alphas[i + 1]

