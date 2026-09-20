"""Convert curvature models into instrument signals.

This module predicts measurable signals that would appear in real instruments
if a spacetime curvature region existed. It does NOT assume exotic physics is real.
Default behavior is fail-closed: signals are predicted for hypothetical scenarios
and detectability is evaluated against conservative instrument noise floors.
"""

from __future__ import annotations

import math
from typing import Any, Literal

InstrumentType = Literal["interferometer", "atomic_clock", "beam_deflection", "gravimeter"]

# Physical constants (SI).
C_LIGHT = 299_792_458.0
G_NEWTON = 6.67430e-11

# Conservative instrument noise floors (order-of-magnitude; lab-grade).
# These are triage thresholds, not claims about specific hardware.
PHASE_NOISE_FLOOR_RAD = 1.0e-6  # Typical good optical interferometer
PATH_LENGTH_NOISE_FLOOR_M = 1.0e-12  # LIGO-grade path length sensitivity
CLOCK_STABILITY_PPM = 1.0e-12  # ~1e-18 fractional for best optical clocks
DEFLECTION_NOISE_RAD = 1.0e-9  # Arcsec-level weak-field
GRAVIMETER_NOISE_M_S2 = 1.0e-9  # Superconducting gravimeter ~1e-9 g


def predict_interferometer(
    *,
    path_difference_m: float,
    wavelength_m: float = 1.0e-6,
    phase_noise_rad: float | None = None,
) -> dict[str, Any]:
    """Predict optical phase shift from curvature-induced path length difference.

    Physics: Δφ = (2π/λ) * ΔL

    Parameters
    ----------
    path_difference_m : float
        Curvature-induced path length difference (m).
    wavelength_m : float
        Probe laser wavelength (m). Default 1 µm.
    phase_noise_rad : float | None
        Instrument phase noise floor (rad). Default conservative lab-grade.

    Returns
    -------
    dict with phase_shift_rad, equivalent_path_change_m, detectable
    """
    dl = float(path_difference_m)
    lam = float(wavelength_m)
    if lam <= 0.0:
        raise ValueError("wavelength_m must be positive")
    noise = float(phase_noise_rad) if phase_noise_rad is not None else PHASE_NOISE_FLOOR_RAD
    phase_shift_rad = (2.0 * math.pi / lam) * dl
    detectable = abs(phase_shift_rad) >= noise
    return {
        "phase_shift_rad": phase_shift_rad,
        "equivalent_path_change_m": dl,
        "detectable": detectable,
        "noise_floor_rad": noise,
    }


def predict_atomic_clock(
    *,
    gravitational_potential_delta_m2_s2: float,
    clock_stability_ppm: float | None = None,
) -> dict[str, Any]:
    """Predict time dilation from gravitational potential difference.

    Physics: Δt/t ≈ ΔΦ/c² (weak-field time dilation)

    Parameters
    ----------
    gravitational_potential_delta_m2_s2 : float
        Difference in gravitational potential Φ (m²/s²). For weak field,
        Φ ≈ -GM/r, so ΔΦ = G*M/r for a mass M at distance r.
    clock_stability_ppm : float | None
        Clock fractional stability in ppm. Default conservative.

    Returns
    -------
    dict with clock_rate_shift, ppm_shift, detectable
    """
    dphi = float(gravitational_potential_delta_m2_s2)
    ppm_shift = (dphi / (C_LIGHT**2)) * 1.0e6  # fractional shift in ppm
    noise = float(clock_stability_ppm) if clock_stability_ppm is not None else CLOCK_STABILITY_PPM
    detectable = abs(ppm_shift) >= noise
    return {
        "clock_rate_shift": dphi / (C_LIGHT**2),
        "ppm_shift": ppm_shift,
        "detectable": detectable,
        "noise_floor_ppm": noise,
    }


def predict_beam_deflection(
    *,
    deflection_angle_rad: float,
    baseline_m: float = 1.0,
    deflection_noise_rad: float | None = None,
) -> dict[str, Any]:
    """Predict trajectory bending and beam offset.

    Parameters
    ----------
    deflection_angle_rad : float
        Deflection angle α(r) in radians.
    baseline_m : float
        Distance to detection plane (m).
    deflection_noise_rad : float | None
        Angular resolution noise floor (rad).

    Returns
    -------
    dict with deflection_angle_rad, beam_offset_m
    """
    alpha = float(deflection_angle_rad)
    L = float(baseline_m)
    if L <= 0.0:
        raise ValueError("baseline_m must be positive")
    beam_offset_m = L * math.tan(alpha)
    if abs(alpha) < 1.0e-6:
        beam_offset_m = L * alpha  # small-angle approx
    noise = float(deflection_noise_rad) if deflection_noise_rad is not None else DEFLECTION_NOISE_RAD
    detectable = abs(alpha) >= noise
    return {
        "deflection_angle_rad": alpha,
        "beam_offset_m": beam_offset_m,
        "baseline_m": L,
        "detectable": detectable,
        "noise_floor_rad": noise,
    }


def predict_gravimeter(
    *,
    delta_g_m_s2: float,
    gravimeter_noise_m_s2: float | None = None,
) -> dict[str, Any]:
    """Predict effective gravitational acceleration change.

    Parameters
    ----------
    delta_g_m_s2 : float
        Change in g (m/s²).
    gravimeter_noise_m_s2 : float | None
        Gravimeter noise floor (m/s²).

    Returns
    -------
    dict with delta_g_m_s2, nano_g, detectable
    """
    dg = float(delta_g_m_s2)
    nano_g = dg * 1.0e9  # in nanogals (1 gal = 1e-2 m/s²)
    noise = float(gravimeter_noise_m_s2) if gravimeter_noise_m_s2 is not None else GRAVIMETER_NOISE_M_S2
    detectable = abs(dg) >= noise
    return {
        "delta_g_m_s2": dg,
        "nano_g": nano_g,
        "detectable": detectable,
        "noise_floor_m_s2": noise,
    }


def curvature_to_path_difference(
    curvature_m2_inv: float,
    arm_length_m: float,
    geometry: str = "through_center",
) -> float:
    """Estimate path length difference from curvature for an interferometer arm.

    Dimensional scaling: ΔL ~ K * L³ for curvature K and arm L.
    This is an order-of-magnitude proxy; full calculation requires metric integration.

    Physics assumption: weak curvature, ΔL/L ~ (1/2) * K * L² for geodesic deviation.
    """
    K = float(curvature_m2_inv)
    L = float(arm_length_m)
    if L <= 0.0:
        raise ValueError("arm_length_m must be positive")
    if geometry == "through_center":
        return 0.5 * K * (L**3)  # dimensional scaling
    return 0.5 * K * (L**3)


def curvature_to_deflection(
    curvature_m2_inv: float,
    impact_parameter_m: float,
) -> float:
    """Estimate deflection angle from curvature at impact parameter.

    Dimensional: α ~ K * b for weak curvature.
    """
    K = float(curvature_m2_inv)
    b = float(impact_parameter_m)
    return K * b


def curvature_to_delta_g(
    curvature_m2_inv: float,
    characteristic_length_m: float,
) -> float:
    """Estimate Δg from curvature.

    Dimensional: Δg ~ c² * K * L for weak field.
    """
    K = float(curvature_m2_inv)
    L = float(characteristic_length_m)
    return C_LIGHT**2 * K * L


def curvature_to_potential_delta(
    curvature_m2_inv: float,
    characteristic_length_m: float,
) -> float:
    """Estimate gravitational potential difference from curvature.

    Dimensional: ΔΦ ~ c² * K * L²
    """
    K = float(curvature_m2_inv)
    L = float(characteristic_length_m)
    return C_LIGHT**2 * K * (L**2)


def predict_signal_for_instrument(
    *,
    curvature_m2_inv: float,
    instrument: InstrumentType,
    arm_length_m: float = 1.0,
    wavelength_m: float = 1.0e-6,
    baseline_m: float = 1.0,
    impact_parameter_m: float | None = None,
) -> dict[str, Any]:
    """Unified entry point: predict instrument signal from curvature.

    Maps curvature to instrument-specific inputs and returns structured output.
    """
    K = float(curvature_m2_inv)
    b = float(impact_parameter_m) if impact_parameter_m is not None else arm_length_m

    if instrument == "interferometer":
        dl = curvature_to_path_difference(K, arm_length_m)
        return predict_interferometer(path_difference_m=dl, wavelength_m=wavelength_m)
    if instrument == "atomic_clock":
        dphi = curvature_to_potential_delta(K, arm_length_m)
        return predict_atomic_clock(gravitational_potential_delta_m2_s2=dphi)
    if instrument == "beam_deflection":
        alpha = curvature_to_deflection(K, b)
        return predict_beam_deflection(deflection_angle_rad=alpha, baseline_m=baseline_m)
    if instrument == "gravimeter":
        dg = curvature_to_delta_g(K, arm_length_m)
        return predict_gravimeter(delta_g_m_s2=dg)
    raise ValueError(f"Unknown instrument: {instrument!r}")
