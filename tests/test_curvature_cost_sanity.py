from __future__ import annotations

from src.curvature_cost import curvature_cost_sanity


def test_curvature_cost_10m_is_enormous_scale():
    s10 = curvature_cost_sanity(10.0, geometry="sphere")
    assert s10["rho_e_j_per_m3"] > 1.0e40
    assert s10["m_over_earth"] > 1.0e-4
    assert s10["requires_negative_energy"] == "unknown"


def test_curvature_cost_ratios_scale_with_length():
    s10 = curvature_cost_sanity(10.0, geometry="sphere")
    s100 = curvature_cost_sanity(100.0, geometry="sphere")
    rho_ratio = s10["rho_e_j_per_m3"] / s100["rho_e_j_per_m3"]
    energy_ratio = s100["E_scale_j"] / s10["E_scale_j"]
    assert 90.0 <= rho_ratio <= 110.0
    assert 9.0 <= energy_ratio <= 11.0

