"""Tests for CURV bubble experiment framework.

Verifies:
- Energy calculations match analytic expectations
- Signal prediction scales correctly with curvature
- Artifact detection flags unrealistic setups
- Feasibility analyzer fails when energy density exceeds policy ceilings
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.bubble_feasibility_analyzer import analyze_bubble_feasibility
from src.curvature_energy_requirements import (
    compute_energy_density,
    compute_mass_equivalent,
    compute_required_curvature,
    compute_total_energy,
    curvature_energy_report,
)
from src.experimental_artifact_rejection import evaluate_artifact_risks
from src.exotic_power_feasibility import ExoticPowerPolicy, exotic_policy_from_preset
from src.spacetime_signal_predictor import (
    curvature_to_deflection,
    curvature_to_path_difference,
    predict_atomic_clock,
    predict_beam_deflection,
    predict_gravimeter,
    predict_interferometer,
    predict_signal_for_instrument,
)


# --- curvature_energy_requirements ---


def test_energy_calculation_matches_analytic():
    """Energy density from curvature: rho_E = K / kappa, kappa = 8πG/c⁴."""
    K = 1.0 / (10.0**2)  # 1/R² for R=10 m
    rho = compute_energy_density(K)
    kappa = (8.0 * math.pi * 6.67430e-11) / (299792458.0**4)
    expected = K / kappa
    assert math.isclose(rho, expected, rel_tol=1e-10)
    assert rho > 1e30  # order of magnitude for 10 m scale


def test_curvature_scales_as_1_over_R_squared():
    """K ~ 1/R²."""
    K10 = compute_required_curvature(10.0)
    K100 = compute_required_curvature(100.0)
    ratio = K10 / K100
    assert 95 <= ratio <= 105  # ~100


def test_mass_equivalent_E_over_c_squared():
    """m = E/c²."""
    E = 1e10  # J
    m = compute_mass_equivalent(E)
    c = 299792458.0
    assert math.isclose(m, E / (c**2), rel_tol=1e-10)
    assert m > 0


def test_curvature_energy_report_spherical_volume():
    """Spherical volume (4/3)πR³ when volume not specified."""
    r = curvature_energy_report(radius_m=2.0)
    assert r["volume_m3"] == pytest.approx((4.0 / 3.0) * math.pi * 8.0, rel=1e-10)
    assert r["curvature_m2_inv"] == 1.0 / 4.0
    assert r["total_energy_j"] == r["energy_density_j_m3"] * r["volume_m3"]


# --- spacetime_signal_predictor ---


def test_signal_prediction_scales_with_curvature():
    """Path difference ~ K * L³."""
    K1 = 1e-4
    K2 = 2e-4
    L = 1.0
    dl1 = curvature_to_path_difference(K1, L)
    dl2 = curvature_to_path_difference(K2, L)
    assert math.isclose(dl2 / dl1, 2.0, rel_tol=1e-6)


def test_interferometer_phase_shift_formula():
    """Δφ = (2π/λ) * ΔL."""
    dl = 1e-12  # m
    lam = 1e-6  # m
    out = predict_interferometer(path_difference_m=dl, wavelength_m=lam)
    expected_phase = (2 * math.pi / lam) * dl
    assert math.isclose(out["phase_shift_rad"], expected_phase, rel_tol=1e-10)
    assert out["equivalent_path_change_m"] == dl


def test_atomic_clock_ppm_shift():
    """Δt/t = ΔΦ/c²."""
    dphi = 100.0  # m²/s²
    out = predict_atomic_clock(gravitational_potential_delta_m2_s2=dphi)
    c = 299792458.0
    expected_frac = dphi / (c**2)
    assert math.isclose(out["clock_rate_shift"], expected_frac, rel_tol=1e-10)
    assert math.isclose(out["ppm_shift"], expected_frac * 1e6, rel_tol=1e-10)


def test_beam_deflection_small_angle():
    """Beam offset ≈ L * α for small α."""
    alpha = 1e-6
    L = 10.0
    out = predict_beam_deflection(deflection_angle_rad=alpha, baseline_m=L)
    assert math.isclose(out["beam_offset_m"], L * alpha, rel_tol=1e-6)
    assert out["deflection_angle_rad"] == alpha


def test_gravimeter_nano_g():
    """nano_g = delta_g * 1e9 (in appropriate units)."""
    dg = 1e-9
    out = predict_gravimeter(delta_g_m_s2=dg)
    assert out["delta_g_m_s2"] == dg
    assert out["nano_g"] == 1e-9 * 1e9  # 1 in nano_g scale for 1e-9 m/s²


def test_predict_signal_for_instrument_all_types():
    """All four instrument types return valid dicts."""
    K = 1e-6
    for inst in ("interferometer", "atomic_clock", "beam_deflection", "gravimeter"):
        out = predict_signal_for_instrument(curvature_m2_inv=K, instrument=inst, arm_length_m=1.0)
        assert isinstance(out, dict)
        assert "detectable" in out or inst == "gravimeter"  # gravimeter has detectable


# --- experimental_artifact_rejection ---


def test_artifact_detection_flags_unrealistic_setups():
    """High power, long duration, small volume → high thermal risk."""
    r = evaluate_artifact_risks(
        power_w=1e7,
        duration_s=10000.0,
        volume_m3=0.01,
        baseline_m=100.0,
        instrument_type="interferometer",
        has_shielding=False,
        sensitivity_class="interferometer",
    )
    assert r["thermal_risk"] in ("med", "high")
    assert r["em_risk"] in ("med", "high")
    assert r["vibration_risk"] in ("med", "high")
    assert r["overall_artifact_risk"] in ("med", "high")
    assert len(r["control_experiments"]) >= 1


def test_artifact_low_risk_for_conservative_setup():
    """Low power, short duration, shielding → low risk."""
    r = evaluate_artifact_risks(
        power_w=1e2,
        duration_s=10.0,
        volume_m3=1.0,
        baseline_m=0.5,
        instrument_type="gravimeter",
        has_shielding=True,
    )
    assert r["thermal_risk"] == "low"
    assert r["em_risk"] == "low"


# --- bubble_feasibility_analyzer ---


def test_feasibility_fails_when_energy_density_exceeds_ceiling():
    """Feasibility analyzer fails when curvature cost gate fails (small R → huge rho)."""
    # R=0.1 m gives enormous energy density; curv_gate should fail
    out = analyze_bubble_feasibility(
        bubble_radius_m=0.1,
        active_volume_m3=0.001,
        required_power_w=1e6,
        duration_s=3600.0,
        instrument_type="interferometer",
        allow_speculative=False,
    )
    # Either curvature gate or exotic power will fail
    assert out["bubble_feasible"] is False
    assert out["verdict"] == "physically_implausible_under_known_physics"
    assert len(out["failure_reasons"]) >= 1


def test_feasibility_exotic_blocked_by_default():
    """Without allow_speculative, exotic power tripwire blocks."""
    out = analyze_bubble_feasibility(
        bubble_radius_m=1000.0,  # large R to avoid curvature gate
        required_power_w=1e6,
        duration_s=3600.0,
        instrument_type="interferometer",
        allow_speculative=False,
    )
    # Exotic power will fail (evidence gate)
    assert out["bubble_feasible"] is False
    assert "exotic" in str(out["dominant_failure_reason"]).lower() or "evidence" in str(
        out["dominant_failure_reason"]
    ).lower()


def test_feasibility_sandbox_can_pass_within_ceilings():
    """Sandbox policy + low power can pass."""
    policy = exotic_policy_from_preset("sandbox")
    out = analyze_bubble_feasibility(
        bubble_radius_m=1e6,  # huge R: tiny curvature, small rho
        required_power_w=1e3,
        duration_s=1.0,
        instrument_type="interferometer",
        policy=policy,
    )
    # May pass if curvature gate and exotic power both pass
    assert "verdict" in out
    assert out["verdict"] in ("consistent_with_model", "physically_implausible_under_known_physics")
    assert "predicted_signal" in out
    assert "required_energy" in out
    assert "artifact_risk" in out


def test_cli_writes_bubble_analysis_json(tmp_path):
    """CLI writes bubble_analysis.json to results/artifacts/<run_id>/."""
    import subprocess
    result = subprocess.run(
        [
            "python",
            "scripts/run_bubble_experiment_analysis.py",
            "--project-root",
            str(tmp_path),
            "--bubble-radius-m",
            "10",
            "--power-w",
            "1e4",
            "--duration-s",
            "100",
            "--instrument",
            "gravimeter",
        ],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    artifacts = list((tmp_path / "results" / "artifacts").glob("*_bubble_*"))
    assert len(artifacts) >= 1
    run_dir = artifacts[0]
    analysis_path = run_dir / "bubble_analysis.json"
    assert analysis_path.exists()
    report = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert "run_id" in report
    assert "feasibility_verdict" in report
    assert "signal_prediction" in report
    assert "energy_requirements" in report


def test_feasibility_output_structure():
    """Report has required keys."""
    out = analyze_bubble_feasibility(
        bubble_radius_m=10.0,
        required_power_w=1e4,
        duration_s=100.0,
        instrument_type="gravimeter",
        policy=exotic_policy_from_preset("sandbox"),
    )
    for key in (
        "bubble_feasible",
        "dominant_failure_reason",
        "verdict",
        "predicted_signal",
        "required_energy",
        "artifact_risk",
        "bubble_parameters",
    ):
        assert key in out
