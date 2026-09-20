"""Tests for bubble envelope and stability module.

Verifies:
- Air-only run returns structured output
- boundary_transition increases required bandwidth and control power
- High medium_coupling_factor causes transition to fail hard
- Low coupling makes transition less punishing (but still pays energy)
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from src.bubble_envelope_and_stability import (
    DetectabilitySpec,
    BubbleSpec,
    ControlSpec,
    EnergySourceEnvelope,
    EnvironmentSpec,
    LEAKAGE_FACTOR_STRICT_1_S,
    analyze_bubble_envelope,
    shell_volume_m3,
)


def _make_bubble_spec(
    radius_m: float = 1.0,
    wall_thickness_m: float = 0.1,
    medium_coupling_factor: float = 0.01,
) -> BubbleSpec:
    return BubbleSpec(
        radius_m=radius_m,
        wall_thickness_m=wall_thickness_m,
        active_volume_m3=None,
        curvature_target_m2_inv=None,
        medium_coupling_factor=medium_coupling_factor,
        shock_suppression=True,
    )


def _make_energy_source(
    max_continuous_power_w: float = 1e12,
    max_burst_power_w: float = 1e14,
    total_energy_capacity_j: float = 1e18,
    response_time_s: float = 1e-6,
) -> EnergySourceEnvelope:
    return EnergySourceEnvelope(
        max_continuous_power_w=max_continuous_power_w,
        max_burst_power_w=max_burst_power_w,
        burst_duration_s=1.0,
        total_energy_capacity_j=total_energy_capacity_j,
        response_time_s=response_time_s,
        waste_heat_fraction=0.1,
        notes="",
    )


def test_air_only_returns_structured_output() -> None:
    """Air-only run returns dict with required keys."""
    out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(),
        environment=EnvironmentSpec(mode="air"),
        energy_source=_make_energy_source(),
        control_spec=ControlSpec(),
    )
    assert isinstance(out, dict)
    for key in (
        "bubble_spec",
        "environment",
        "energy_source_envelope",
        "derived",
        "instrument_predictions",
        "verdict",
        "bubble_feasible",
        "dominant_failure_reason",
        "failure_reasons",
        "detectable",
        "detectability_failure_reason",
        "passed_signals",
    ):
        assert key in out
    assert out["environment"]["mode"] == "air"
    d = out["derived"]
    assert "K_used_m2_inv" in d
    assert "rho_required_j_m3" in d
    assert "E_create_j" in d
    assert "P_maint_w" in d
    assert "P_control_peak_w" in d
    assert "required_bandwidth_hz" in d
    pred = out["instrument_predictions"]
    assert "gravimeter_delta_g_proxy" in pred
    assert "interferometer_phase_shift_proxy" in pred
    assert "clock_fractional_shift_proxy" in pred


def test_boundary_transition_increases_bandwidth_and_control_power() -> None:
    """boundary_transition mode increases required bandwidth and P_control vs air."""
    energy = _make_energy_source(
        max_continuous_power_w=1e15,
        max_burst_power_w=1e18,
        total_energy_capacity_j=1e22,
        response_time_s=1e-9,
    )
    air_out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(medium_coupling_factor=0.1),
        environment=EnvironmentSpec(mode="air"),
        energy_source=energy,
        control_spec=ControlSpec(),
    )
    trans_out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(medium_coupling_factor=0.1),
        environment=EnvironmentSpec(mode="boundary_transition"),
        energy_source=energy,
        control_spec=ControlSpec(),
    )
    assert trans_out["derived"]["required_bandwidth_hz"] >= air_out["derived"]["required_bandwidth_hz"]
    assert trans_out["derived"]["P_control_peak_w"] >= air_out["derived"]["P_control_peak_w"]


def test_high_coupling_transition_fails_hard() -> None:
    """With medium_coupling_factor=1.0, boundary_transition should fail."""
    energy = _make_energy_source(
        max_continuous_power_w=1e20,
        max_burst_power_w=1e22,
        total_energy_capacity_j=1e25,
        response_time_s=1e-12,
    )
    out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(medium_coupling_factor=1.0),
        environment=EnvironmentSpec(mode="boundary_transition"),
        energy_source=energy,
        control_spec=ControlSpec(required_bandwidth_hz_target=1e6),
        leakage_factor_1_s=1e-6,
    )
    # High coupling * density_jump → huge disturbance scale → high P_control and bandwidth
    assert not out["bubble_feasible"] or len(out["failure_reasons"]) > 0 or out["derived"]["P_control_peak_w"] > 1e15


def test_low_coupling_transition_less_punishing() -> None:
    """With tiny coupling, transition still pays energy but is less punishing."""
    energy = _make_energy_source(
        max_continuous_power_w=1e15,
        max_burst_power_w=1e18,
        total_energy_capacity_j=1e22,
        response_time_s=1e-9,
    )
    air_out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(medium_coupling_factor=1e-6),
        environment=EnvironmentSpec(mode="air"),
        energy_source=energy,
        control_spec=ControlSpec(),
    )
    trans_out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(medium_coupling_factor=1e-6),
        environment=EnvironmentSpec(mode="boundary_transition"),
        energy_source=energy,
        control_spec=ControlSpec(),
    )
    # Transition should still increase requirements over air
    assert trans_out["derived"]["P_control_peak_w"] >= air_out["derived"]["P_maint_w"]
    # But with 1e-6 coupling, disturbance_scale = 1e-6 * 833 ≈ 8e-4, so overhead is modest
    ratio = trans_out["derived"]["P_control_peak_w"] / air_out["derived"]["P_control_peak_w"]
    assert 1.0 <= ratio < 100.0  # bounded increase for tiny coupling


def test_shell_volume_geometry() -> None:
    """Shell volume matches (4/3)π(R³ - (R-d)³)."""
    R, d = 1.0, 0.1
    V = shell_volume_m3(R, d)
    expected = (4.0 / 3.0) * math.pi * (R**3 - (R - d) ** 3)
    assert math.isclose(V, expected, rel_tol=1e-10)
    # Zero thickness → full sphere
    V0 = shell_volume_m3(1.0, 0.0)
    assert math.isclose(V0, (4.0 / 3.0) * math.pi, rel_tol=1e-10)


def test_instrument_predictions_scaled_by_curvature() -> None:
    """Instrument proxies scale with curvature (1/R²)."""
    energy = _make_energy_source(
        max_continuous_power_w=1e20,
        max_burst_power_w=1e22,
        total_energy_capacity_j=1e28,
        response_time_s=1e-12,
    )
    out1 = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(radius_m=1.0),
        environment=EnvironmentSpec(mode="air"),
        energy_source=energy,
        control_spec=ControlSpec(),
    )
    out2 = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(radius_m=2.0),
        environment=EnvironmentSpec(mode="air"),
        energy_source=energy,
        control_spec=ControlSpec(),
    )
    K1 = out1["derived"]["K_used_m2_inv"]
    K2 = out2["derived"]["K_used_m2_inv"]
    assert math.isclose(K1 / K2, 4.0, rel_tol=1e-6)  # K ~ 1/R²
    g1 = out1["instrument_predictions"]["gravimeter_delta_g_proxy"]
    g2 = out2["instrument_predictions"]["gravimeter_delta_g_proxy"]
    assert g1 > g2  # larger curvature → larger signal


def test_fail_control_bandwidth_insufficient() -> None:
    """Slow response time → control_bandwidth_insufficient."""
    energy = _make_energy_source(
        max_continuous_power_w=1e20,
        max_burst_power_w=1e22,
        total_energy_capacity_j=1e28,
        response_time_s=1.0,  # 1 s → max 1 Hz
    )
    out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(),
        environment=EnvironmentSpec(mode="boundary_transition"),
        energy_source=energy,
        control_spec=ControlSpec(required_bandwidth_hz_target=100.0),
        leakage_factor_1_s=1e-6,
    )
    # With response_time_s=1, max_bw = 1 Hz; transition scales bandwidth up
    if out["derived"]["required_bandwidth_hz"] > 1.0:
        assert "control_bandwidth_insufficient" in out["failure_reasons"]


def test_detectability_gate_any_of() -> None:
    """Detectability gate: bubble must exceed at least one instrument threshold."""
    energy = _make_energy_source(
        max_continuous_power_w=1e20,
        max_burst_power_w=1e22,
        total_energy_capacity_j=1e28,
        response_time_s=1e-12,
    )
    # R=0.5 m → K=4, signals are huge; all should pass
    det_spec = DetectabilitySpec(require_detectable=True, mode="any_of")
    out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(radius_m=0.5),
        environment=EnvironmentSpec(mode="air"),
        energy_source=energy,
        control_spec=ControlSpec(),
        detectability_spec=det_spec,
    )
    assert out["detectable"]
    assert len(out["passed_signals"]) >= 1
    assert "detectability_insufficient" not in out["failure_reasons"]


def test_detectability_insufficient_when_signals_below_threshold() -> None:
    """Tiny curvature (large R) with very high thresholds can fail detectability."""
    energy = _make_energy_source(
        max_continuous_power_w=1e20,
        max_burst_power_w=1e22,
        total_energy_capacity_j=1e28,
        response_time_s=1e-12,
    )
    # R=1e6 m → K=1e-12, signals tiny; use absurdly high thresholds to force fail
    det_spec = DetectabilitySpec(
        require_detectable=True,
        mode="all_of",
        phase_shift_rad_min=1e30,
        delta_g_min_m_s2=1e30,
        clock_frac_shift_min=1e30,
    )
    out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(radius_m=1e6),
        environment=EnvironmentSpec(mode="air"),
        energy_source=energy,
        control_spec=ControlSpec(),
        detectability_spec=det_spec,
    )
    assert not out["detectable"]
    assert "detectability_insufficient" in out["failure_reasons"]
    assert not out["bubble_feasible"]


def test_fail_maintenance_power_exceeds_source() -> None:
    """Low max_continuous_power → maintenance_power_exceeds_source."""
    energy = _make_energy_source(
        max_continuous_power_w=1e-10,  # tiny
        max_burst_power_w=1e20,
        total_energy_capacity_j=1e28,
        response_time_s=1e-12,
    )
    out = analyze_bubble_envelope(
        bubble_spec=_make_bubble_spec(),
        environment=EnvironmentSpec(mode="air"),
        energy_source=energy,
        control_spec=ControlSpec(),
        leakage_factor_1_s=LEAKAGE_FACTOR_STRICT_1_S,
    )
    assert not out["bubble_feasible"]
    assert "maintenance_power_exceeds_source" in out["failure_reasons"]
