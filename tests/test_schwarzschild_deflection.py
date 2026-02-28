from __future__ import annotations

from src.gr.geodesic import trace_null_ray


def test_schwarzschild_weak_field_tracks_4m_over_b():
    ray = trace_null_ray(b_over_m=120.0, mass=1.0)
    alpha_num = float(ray["alpha_numeric"])
    alpha_weak = float(ray["alpha_weakfield"])
    rel_err = abs(alpha_num - alpha_weak) / alpha_weak
    assert rel_err < 0.2


def test_schwarzschild_deflection_monotonic_with_b():
    b_values = [40.0, 60.0, 100.0]
    alphas = [float(trace_null_ray(b_over_m=b, mass=1.0)["alpha_numeric"]) for b in b_values]
    assert alphas[0] > alphas[1] > alphas[2]

