from __future__ import annotations

from src.observables.deflection_curve import compute_deflection_curve, mean_normalized_curve_difference
from src.theories.gr_ppn_screened_potential import GRPPNScreenedPotential
from src.theories.gr_schwarzschild import GRSchwarzschild


def test_ppn_gamma_one_tracks_schwarzschild_at_large_b():
    ppn = GRPPNScreenedPotential(gamma_ppn=1.0)
    gr = GRSchwarzschild()
    _, alpha_ppn, _, _ = compute_deflection_curve(
        ppn, bmin_over_m=80.0, bmax_over_m=300.0, n_points=7, setup={"h": 0.5}
    )
    _, alpha_gr, _, _ = compute_deflection_curve(
        gr, bmin_over_m=80.0, bmax_over_m=300.0, n_points=7, setup={"h": 0.5}
    )
    assert mean_normalized_curve_difference(alpha_ppn, alpha_gr) < 0.1


def test_ppn_known_limit_declares_gr_recovery():
    ppn = GRPPNScreenedPotential(gamma_ppn=0.99)
    lim = ppn.known_limit_parameters()
    assert lim["gamma_ppn"] == 1.0
    assert lim["alpha_s"] == 0.0
