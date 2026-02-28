from __future__ import annotations

import json
import numpy as np

from src.observables.deflection_curve import compute_deflection_curve, mean_normalized_curve_difference
from src.theories.gr_schwarzschild import GRSchwarzschild
from src.theories.gr_yukawa_deviation import GRYukawaDeviation


def test_plugins_expose_contract_shape():
    gr = GRSchwarzschild()
    yuk = GRYukawaDeviation(alpha_y=0.01, lambda_y_over_m=40.0)
    assert isinstance(gr.name, str)
    assert isinstance(yuk.name, str)
    assert isinstance(gr.parameters, dict)
    assert isinstance(yuk.parameters, dict)
    assert "alpha_y" in yuk.known_limit_parameters()


def test_schwarzschild_curve_is_monotonic_and_near_weak_field():
    gr = GRSchwarzschild()
    b, alpha, alpha_ref, rel_err = compute_deflection_curve(
        gr, bmin_over_m=40.0, bmax_over_m=200.0, n_points=8, setup={"h": 0.5}
    )
    assert np.all(np.diff(alpha) < 0.0)
    assert float(np.median(rel_err[-5:])) < 0.25
    assert len(b) == 8
    assert len(alpha_ref) == 8


def test_yukawa_known_limit_matches_schwarzschild():
    yuk0 = GRYukawaDeviation(alpha_y=0.0, lambda_y_over_m=50.0)
    gr = GRSchwarzschild()
    _, alpha_y0, _, _ = compute_deflection_curve(yuk0, bmin_over_m=40.0, bmax_over_m=200.0, n_points=7, setup={"h": 0.5})
    _, alpha_gr, _, _ = compute_deflection_curve(gr, bmin_over_m=40.0, bmax_over_m=200.0, n_points=7, setup={"h": 0.5})
    assert mean_normalized_curve_difference(alpha_y0, alpha_gr) < 0.05


def test_tnew_summaries_are_json_serializable():
    gr = GRSchwarzschild()
    yuk = GRYukawaDeviation(alpha_y=0.01, lambda_y_over_m=50.0)
    json.dumps(gr.stress_energy_summary({"h": 0.5}), ensure_ascii=True)
    json.dumps(yuk.stress_energy_summary({"h": 0.5}), ensure_ascii=True)

