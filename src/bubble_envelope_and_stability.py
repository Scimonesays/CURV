"""Bubble Envelope + Stability: creation, maintenance, control, transmedium.

Answers: What's the minimum energy + control power needed to maintain a meter-scale
bubble that decouples enough to explain transmedium + no boom, and what instrument
signals must appear if it's real?

Conservative, fail-closed. Reuses EFE curvature→energy mapping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from .coupling_scale_calibrator import INV_KAPPA_EFE
from .curvature_energy_requirements import compute_energy_density, compute_mass_equivalent
from .spacetime_signal_predictor import (
    curvature_to_delta_g,
    curvature_to_path_difference,
    curvature_to_potential_delta,
)

# Environment constants (SI).
RHO_AIR_KG_M3 = 1.2
RHO_WATER_KG_M3 = 1000.0
DENSITY_JUMP = RHO_WATER_KG_M3 / RHO_AIR_KG_M3  # ~833

# Policy knobs.
LEAKAGE_FACTOR_SANDBOX_1_S = 1e-6
LEAKAGE_FACTOR_STRICT_1_S = 1e-3


@dataclass
class BubbleSpec:
    """Bubble geometry and coupling parameters."""

    radius_m: float
    wall_thickness_m: float
    active_volume_m3: float | None = None
    curvature_target_m2_inv: float | None = None
    medium_coupling_factor: float = 1.0
    shock_suppression: bool = True
    substrate_coupling_factor: float = 1.0

    def __post_init__(self) -> None:
        if not 0 <= self.medium_coupling_factor <= 1:
            raise ValueError("medium_coupling_factor must be in [0,1]")
        if self.radius_m <= 0 or self.wall_thickness_m < 0:
            raise ValueError("radius_m must be positive, wall_thickness_m non-negative")
        if self.substrate_coupling_factor <= 0:
            raise ValueError("substrate_coupling_factor must be positive")


@dataclass
class EnvironmentSpec:
    """Environment for bubble operation."""

    mode: Literal["air", "water", "vacuum", "boundary_transition"] = "air"
    altitude_m: float = 0.0
    speed_m_s: float = 0.0
    temperature_k: float | None = None


@dataclass
class EnergySourceEnvelope:
    """Energy source capability envelope (not specific tech)."""

    max_continuous_power_w: float
    max_burst_power_w: float
    burst_duration_s: float
    total_energy_capacity_j: float
    response_time_s: float
    waste_heat_fraction: float = 0.0
    notes: str = ""


@dataclass
class ControlSpec:
    """Control system requirements."""

    required_bandwidth_hz_target: float = 100.0
    controller_gain_limit: float = 10.0
    stability_margin_target: float = 6.0  # dB proxy


# Default detectability thresholds (conservative, instrument-grounded).
PHASE_SHIFT_RAD_MIN = 1e-6  # µrad-scale, measurable with good interferometry
DELTA_G_MIN_M_S2 = 1e-9 * 9.81  # ~1 nano-g, modern gravimetry
CLOCK_FRAC_SHIFT_MIN = 1e-18  # optical-clock stability


@dataclass
class DetectabilitySpec:
    """Detectability gate: bubble must produce measurable instrument signals.

    Signals depend on K (curvature) and geometry, NOT on alpha (energy cost).
    Alpha changes how hard it is to produce K, not whether K exists.
    """

    require_detectable: bool = False
    mode: Literal["any_of", "all_of"] = "any_of"
    phase_shift_rad_min: float = PHASE_SHIFT_RAD_MIN
    delta_g_min_m_s2: float = DELTA_G_MIN_M_S2
    clock_frac_shift_min: float = CLOCK_FRAC_SHIFT_MIN


def shell_volume_m3(radius_m: float, wall_thickness_m: float) -> float:
    """Spherical shell volume: (4/3)π(R³ - (R-d)³)."""
    R = float(radius_m)
    d = float(wall_thickness_m)
    if d <= 0:
        return (4.0 / 3.0) * math.pi * (R**3)
    r_inner = max(0.0, R - d)
    return (4.0 / 3.0) * math.pi * (R**3 - r_inner**3)


def analyze_bubble_envelope(
    *,
    bubble_spec: BubbleSpec,
    environment: EnvironmentSpec,
    energy_source: EnergySourceEnvelope,
    control_spec: ControlSpec,
    leakage_factor_1_s: float = LEAKAGE_FACTOR_STRICT_1_S,
    control_overhead_base: float = 2.0,
    arm_length_m: float = 1.0,
    detectability_spec: DetectabilitySpec | None = None,
) -> dict[str, Any]:
    """Full envelope analysis: creation, maintenance, control, instrument signals.

    Returns structured dict with verdict, failure_reasons, derived, instrument_predictions.
    """
    R = bubble_spec.radius_m
    d = bubble_spec.wall_thickness_m
    coupling = bubble_spec.medium_coupling_factor
    alpha = bubble_spec.substrate_coupling_factor

    # Geometry
    V_shell = (
        float(bubble_spec.active_volume_m3)
        if bubble_spec.active_volume_m3 is not None
        else shell_volume_m3(R, d)
    )

    # Curvature (proxy if not explicit)
    if bubble_spec.curvature_target_m2_inv is not None:
        K_used = float(bubble_spec.curvature_target_m2_inv)
        k_proxy_label = False
    else:
        K_used = 1.0 / (R * R)
        k_proxy_label = True

    # Energy density (EFE + substrate coupling: rho_physical = rho_GR * alpha)
    rho_required = compute_energy_density(K_used, substrate_coupling_factor=alpha)
    E_create = rho_required * V_shell

    # Maintenance
    P_maint = leakage_factor_1_s * E_create

    # Control overhead
    overhead = control_overhead_base
    if environment.mode == "boundary_transition":
        disturbance_scale = coupling * DENSITY_JUMP
        overhead *= max(1.0, disturbance_scale)
    elif environment.mode == "water":
        overhead *= 10.0  # water is denser
    elif environment.speed_m_s > 100:
        overhead *= 1.0 + 0.01 * (environment.speed_m_s - 100)  # speed stress

    P_control_peak = overhead * P_maint

    # Bandwidth
    required_bandwidth_hz = control_spec.required_bandwidth_hz_target
    if environment.mode == "boundary_transition":
        bw_scale = min(1000.0, math.log10(1.0 + coupling * DENSITY_JUMP) * 50)
        required_bandwidth_hz *= max(1.0, bw_scale)

    # Instrument predictions (proxies tied to curvature)
    dphi = curvature_to_potential_delta(K_used, arm_length_m)
    clock_frac = dphi / (299792458.0**2) if dphi != 0 else 0.0
    instrument_predictions = {
        "gravimeter_delta_g_proxy": curvature_to_delta_g(K_used, arm_length_m),
        "interferometer_phase_shift_proxy": (
            2.0 * math.pi / 1e-6
        ) * curvature_to_path_difference(K_used, arm_length_m),
        "clock_fractional_shift_proxy": clock_frac,
    }

    # Failure checks
    failure_reasons: list[str] = []
    max_bw_from_response = 1.0 / energy_source.response_time_s if energy_source.response_time_s > 0 else 1e12
    if max_bw_from_response < required_bandwidth_hz:
        failure_reasons.append("control_bandwidth_insufficient")
    if P_control_peak > energy_source.max_burst_power_w:
        failure_reasons.append("control_peak_power_exceeds_source")
    if P_maint > energy_source.max_continuous_power_w:
        failure_reasons.append("maintenance_power_exceeds_source")
    if E_create > energy_source.total_energy_capacity_j:
        failure_reasons.append("energy_capacity_exceeded")
    burst_energy = energy_source.max_burst_power_w * energy_source.burst_duration_s
    if E_create > burst_energy and P_control_peak > energy_source.max_continuous_power_w:
        failure_reasons.append("creation_burst_exceeds_capacity")

    # Detectability gate (signals depend on K/geometry, not alpha)
    detectable = True
    detectability_failure_reason = "none"
    passed_signals: list[str] = []
    if detectability_spec is not None and detectability_spec.require_detectable:
        phase_ok = abs(instrument_predictions["interferometer_phase_shift_proxy"]) >= detectability_spec.phase_shift_rad_min
        grav_ok = abs(instrument_predictions["gravimeter_delta_g_proxy"]) >= detectability_spec.delta_g_min_m_s2
        clock_ok = abs(instrument_predictions["clock_fractional_shift_proxy"]) >= detectability_spec.clock_frac_shift_min
        if phase_ok:
            passed_signals.append("interferometer_phase_shift")
        if grav_ok:
            passed_signals.append("gravimeter_delta_g")
        if clock_ok:
            passed_signals.append("clock_fractional_shift")
        if detectability_spec.mode == "any_of":
            detectable = phase_ok or grav_ok or clock_ok
        else:
            detectable = phase_ok and grav_ok and clock_ok
        if not detectable:
            failure_reasons.append("detectability_insufficient")
            detectability_failure_reason = (
                f"mode={detectability_spec.mode}; "
                f"phase_ok={phase_ok} grav_ok={grav_ok} clock_ok={clock_ok}"
            )

    bubble_feasible = len(failure_reasons) == 0
    dominant_failure_reason = failure_reasons[0] if failure_reasons else "none"

    if bubble_feasible:
        verdict = "consistent_with_model"
    else:
        verdict = "physically_implausible_under_known_physics"

    derived = {
        "K_used_m2_inv": K_used,
        "K_proxy_label": k_proxy_label,
        "V_shell_m3": V_shell,
        "rho_required_j_m3": rho_required,
        "E_create_j": E_create,
        "P_maint_w": P_maint,
        "P_control_peak_w": P_control_peak,
        "required_bandwidth_hz": required_bandwidth_hz,
    }

    return {
        "bubble_spec": {
            "radius_m": bubble_spec.radius_m,
            "wall_thickness_m": bubble_spec.wall_thickness_m,
            "active_volume_m3": bubble_spec.active_volume_m3,
            "curvature_target_m2_inv": bubble_spec.curvature_target_m2_inv,
            "medium_coupling_factor": bubble_spec.medium_coupling_factor,
            "shock_suppression": bubble_spec.shock_suppression,
            "substrate_coupling_factor": bubble_spec.substrate_coupling_factor,
        },
        "environment": {
            "mode": environment.mode,
            "altitude_m": environment.altitude_m,
            "speed_m_s": environment.speed_m_s,
            "temperature_k": environment.temperature_k,
        },
        "energy_source_envelope": {
            "max_continuous_power_w": energy_source.max_continuous_power_w,
            "max_burst_power_w": energy_source.max_burst_power_w,
            "burst_duration_s": energy_source.burst_duration_s,
            "total_energy_capacity_j": energy_source.total_energy_capacity_j,
            "response_time_s": energy_source.response_time_s,
            "waste_heat_fraction": energy_source.waste_heat_fraction,
            "notes": energy_source.notes,
        },
        "derived": derived,
        "instrument_predictions": instrument_predictions,
        "verdict": verdict,
        "bubble_feasible": bubble_feasible,
        "dominant_failure_reason": dominant_failure_reason,
        "failure_reasons": failure_reasons,
        "detectable": detectable,
        "detectability_failure_reason": detectability_failure_reason,
        "passed_signals": passed_signals,
    }


def analyze_transmedium_three_phase(
    *,
    bubble_spec: BubbleSpec,
    energy_source: EnergySourceEnvelope,
    control_spec: ControlSpec,
    arm_length_m: float = 1.0,
    leakage_factor_1_s: float = LEAKAGE_FACTOR_STRICT_1_S,
    speed_m_s: float = 100.0,
    detectability_spec: DetectabilitySpec | None = None,
) -> dict[str, Any]:
    """Three-phase transmedium: air → boundary_transition → water.

    Finds minimum energy envelope and minimum coupling factor for stability.
    Returns worst-case requirements and predicted instrument signals.
    """
    phases = [
        ("air", EnvironmentSpec(mode="air", speed_m_s=speed_m_s)),
        ("boundary_transition", EnvironmentSpec(mode="boundary_transition", speed_m_s=speed_m_s)),
        ("water", EnvironmentSpec(mode="water", speed_m_s=speed_m_s)),
    ]
    results: list[dict[str, Any]] = []
    worst_case: dict[str, Any] | None = None
    max_E = 0.0
    max_P_control = 0.0
    min_coupling_for_stability: float | None = None

    for phase_name, env in phases:
        r = analyze_bubble_envelope(
            bubble_spec=bubble_spec,
            environment=env,
            energy_source=energy_source,
            control_spec=control_spec,
            leakage_factor_1_s=leakage_factor_1_s,
            arm_length_m=arm_length_m,
            detectability_spec=detectability_spec,
        )
        r["phase"] = phase_name
        results.append(r)
        E = r["derived"]["E_create_j"]
        P_ctrl = r["derived"]["P_control_peak_w"]
        if E > max_E:
            max_E = E
        if P_ctrl > max_P_control:
            max_P_control = P_ctrl
        if r["bubble_feasible"] and phase_name == "boundary_transition":
            min_coupling_for_stability = bubble_spec.medium_coupling_factor
        if worst_case is None or r["derived"]["P_control_peak_w"] > worst_case["derived"]["P_control_peak_w"]:
            worst_case = r

    instrument_predictions = (
        worst_case["instrument_predictions"] if worst_case else {}
    )

    return {
        "phases": results,
        "worst_case": worst_case,
        "min_energy_envelope_j": max_E,
        "min_control_power_w": max_P_control,
        "min_coupling_factor_for_transition_stability": min_coupling_for_stability,
        "instrument_predictions": instrument_predictions,
        "bubble_feasible_all_phases": all(r["bubble_feasible"] for r in results),
    }
