"""Generate real experimental setup recommendations from predicted signal.

Converts curvature/signal predictions into actionable experiment design.
"""

from __future__ import annotations

from typing import Any

from .spacetime_signal_predictor import (
    InstrumentType,
    predict_signal_for_instrument,
)


def generate_experiment_design(
    *,
    curvature_m2_inv: float,
    instrument_type: InstrumentType,
    arm_length_m: float = 1.0,
    wavelength_m: float = 1.0e-6,
) -> dict[str, Any]:
    """Generate experiment design from curvature target.

    Returns recommended instrument, sensitivity, baseline, control experiments,
    and expected signal profile.
    """
    signal = predict_signal_for_instrument(
        curvature_m2_inv=curvature_m2_inv,
        instrument=instrument_type,
        arm_length_m=arm_length_m,
        baseline_m=arm_length_m,
        wavelength_m=wavelength_m,
    )

    if instrument_type == "interferometer":
        required_sensitivity = f"phase >= {signal.get('noise_floor_rad', 1e-6):.2e} rad"
        min_baseline = max(arm_length_m, 0.1)
        control_experiments = [
            "power_off_baseline",
            "null_arm_cross_check",
            "wavelength_stability_monitor",
        ]
    elif instrument_type == "atomic_clock":
        required_sensitivity = f"ppm_shift >= {signal.get('noise_floor_ppm', 1e-12):.2e}"
        min_baseline = arm_length_m  # clock separation
        control_experiments = [
            "clock_swap_position_test",
            "environmental_isolation",
        ]
    elif instrument_type == "beam_deflection":
        required_sensitivity = f"angle >= {signal.get('noise_floor_rad', 1e-9):.2e} rad"
        min_baseline = arm_length_m
        control_experiments = [
            "beam_reversal_null_test",
            "deflection_independence_check",
        ]
    elif instrument_type == "gravimeter":
        required_sensitivity = f"delta_g >= {signal.get('noise_floor_m_s2', 1e-9):.2e} m/s²"
        min_baseline = 0.0  # point measurement
        control_experiments = [
            "mass_perturbation_calibration",
            "tidal_correction",
        ]
    else:
        required_sensitivity = "instrument-specific"
        min_baseline = arm_length_m
        control_experiments = []

    return {
        "recommended_instrument": instrument_type,
        "required_sensitivity": required_sensitivity,
        "minimum_baseline_m": min_baseline,
        "control_experiments": control_experiments,
        "expected_signal_profile": signal,
        "curvature_m2_inv": curvature_m2_inv,
    }
