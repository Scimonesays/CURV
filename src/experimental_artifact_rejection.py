"""Ensure predicted signals cannot be explained by common artifacts.

This module flags experimental setups where thermal drift, EM pickup,
vibration, RF, or ground loops could fake a curvature signal.
Conservative: when in doubt, flag as higher risk.
"""

from __future__ import annotations

from typing import Any, Literal

RiskLevel = Literal["low", "med", "high"]


def _assess_thermal_risk(
    *,
    power_w: float,
    duration_s: float,
    volume_m3: float,
    expected_signal_strength: float,
    temperature_stability_k: float | None = None,
) -> RiskLevel:
    """Thermal drift: high power + long duration + small volume → high risk."""
    power_density = power_w / max(volume_m3, 1.0e-30)
    if power_density > 1.0e6:  # W/m³
        return "high"
    if power_w > 1.0e5 and duration_s > 3600.0:
        return "med"
    return "low"


def _assess_em_risk(
    *,
    power_w: float,
    has_shielding: bool = False,
) -> RiskLevel:
    """EM pickup: high power without shielding → risk."""
    if power_w > 1.0e6 and not has_shielding:
        return "high"
    if power_w > 1.0e4 and not has_shielding:
        return "med"
    return "low"


def _assess_vibration_risk(
    *,
    baseline_m: float,
    sensitivity_class: str = "standard",
) -> RiskLevel:
    """Vibration coupling: long baseline + sensitive instrument → risk."""
    if baseline_m > 10.0 and sensitivity_class in ("high", "interferometer"):
        return "high"
    if baseline_m > 1.0 and sensitivity_class == "interferometer":
        return "med"
    return "low"


def _assess_rf_risk(
    *,
    power_w: float,
    frequency_hz: float | None = None,
) -> RiskLevel:
    """RF leakage: high power RF → risk of pickup."""
    if power_w > 1.0e6:
        return "high"
    if power_w > 1.0e4:
        return "med"
    return "low"


def _assess_ground_loop_risk(
    *,
    baseline_m: float,
    instrument_type: str,
) -> RiskLevel:
    """Ground loops: long cables + sensitive measurement → risk."""
    if baseline_m > 100.0 and instrument_type in ("interferometer", "atomic_clock"):
        return "high"
    if baseline_m > 10.0 and instrument_type == "interferometer":
        return "med"
    return "low"


def evaluate_artifact_risks(
    *,
    power_w: float,
    duration_s: float,
    volume_m3: float,
    baseline_m: float = 1.0,
    instrument_type: str = "interferometer",
    has_shielding: bool = False,
    sensitivity_class: str = "standard",
    expected_signal_strength: float = 1.0,
) -> dict[str, Any]:
    """Evaluate artifact risks for an experimental setup.

    Returns risk levels and recommended control experiments.
    """
    thermal = _assess_thermal_risk(
        power_w=power_w,
        duration_s=duration_s,
        volume_m3=volume_m3,
        expected_signal_strength=expected_signal_strength,
    )
    em = _assess_em_risk(power_w=power_w, has_shielding=has_shielding)
    vibration = _assess_vibration_risk(
        baseline_m=baseline_m,
        sensitivity_class=sensitivity_class,
    )
    rf = _assess_rf_risk(power_w=power_w)
    ground = _assess_ground_loop_risk(
        baseline_m=baseline_m,
        instrument_type=instrument_type,
    )

    control_experiments: list[str] = []
    if thermal != "low":
        control_experiments.append("power_off_baseline_thermal_drift")
    if em != "low":
        control_experiments.append("shielded_vs_unshielded_comparison")
    if vibration != "low":
        control_experiments.append("vibration_isolation_test")
    if rf != "low":
        control_experiments.append("rf_spectrum_monitoring")
    if ground != "low":
        control_experiments.append("ground_loop_diagnostics")

    return {
        "thermal_risk": thermal,
        "em_risk": em,
        "vibration_risk": vibration,
        "rf_risk": rf,
        "ground_loop_risk": ground,
        "control_experiments": control_experiments,
        "overall_artifact_risk": (
            "high" if any(r == "high" for r in [thermal, em, vibration, rf, ground]) else "med" if any(r == "med" for r in [thermal, em, vibration, rf, ground]) else "low"
        ),
    }
