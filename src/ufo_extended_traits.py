"""Extended traits as testable predictions (not magic).

Gravitational lensing, oscillation blur, tilted disk, skipping.
Each must be paid for; no free checkboxes.
"""

from __future__ import annotations

import math
from typing import Any

# G in SI, c in m/s
G_NEWTON = 6.67430e-11
C_LIGHT = 299792458.0


def lensing_deflection_proxy(
    mass_kg: float,
    impact_param_m: float,
    distance_m: float,
) -> dict[str, Any]:
    """Minimum deflection angle for lensing (weak field: alpha ~ 4GM/(c²b))."""
    if impact_param_m <= 0 or distance_m <= 0:
        return {"deflection_angle_rad": 0.0, "curvature_required": "invalid"}
    alpha_rad = 4.0 * G_NEWTON * mass_kg / (C_LIGHT**2 * impact_param_m)
    # Curvature scale K ~ GM/(c² r³)
    K_proxy = G_NEWTON * mass_kg / (C_LIGHT**2 * (impact_param_m**3))
    return {
        "deflection_angle_rad": alpha_rad,
        "deflection_arcsec": alpha_rad * 206265,
        "curvature_proxy_m2_inv": K_proxy,
        "impact_param_m": impact_param_m,
        "distance_m": distance_m,
    }


def gate_lensing_energy_budget(
    lensing_reported: bool,
    deflection_result: dict[str, Any],
    required_power_W: float,
    mass_kg: float,
) -> dict[str, Any]:
    """Lensing can't be free; must correlate with curvature/energy budget."""
    if not lensing_reported:
        return {"passed": True, "reason": "lensing_not_claimed", "severity": "none"}

    alpha = deflection_result.get("deflection_angle_rad", 0.0)
    if alpha < 1e-20:
        return {"passed": False, "reason": "lensing_claim_requires_nonzero_deflection", "severity": "med"}

    # Consistency: lensing implies mass/curvature; mass implies rest energy
    rest_energy_J = mass_kg * (C_LIGHT**2)
    if required_power_W > 0 and rest_energy_J < 1e10:
        # Tiny mass, huge power: inconsistent
        return {
            "passed": False,
            "reason": "lensing_implies_mass_curvature_budget_mismatch",
            "severity": "med",
        }

    return {"passed": True, "reason": "lensing_budget_consistent", "severity": "none"}


def oscillation_blur_proxy(
    jitter_freq_hz: float,
    jitter_amplitude_m: float,
    range_m: float,
    exposure_s: float,
) -> dict[str, Any]:
    """Oscillation blur: camera blur signature vs range and exposure."""
    # Angular blur ~ amplitude / range
    angular_rad = jitter_amplitude_m / max(range_m, 1.0)
    # Motion blur: v ~ 2*pi*f*A, blur ~ v * exposure
    v_jitter = 2 * math.pi * jitter_freq_hz * jitter_amplitude_m
    blur_length_m = v_jitter * exposure_s
    return {
        "angular_blur_rad": angular_rad,
        "motion_blur_m": blur_length_m,
        "jitter_velocity_m_s": v_jitter,
        "could_be_sensor_artifact": exposure_s > 0.1 or range_m > 10000,
    }


def gate_oscillation_energy(
    oscillation_reported: bool,
    jitter_result: dict[str, Any],
    mass_kg: float,
) -> dict[str, Any]:
    """Jitter implies acceleration/energy; not a free checkbox."""
    if not oscillation_reported:
        return {"passed": True, "reason": "oscillation_not_claimed", "severity": "none"}

    v = jitter_result.get("jitter_velocity_m_s", 0.0)
    ke = 0.5 * mass_kg * (v**2)
    if ke > 1e12 and mass_kg < 1000:
        return {
            "passed": False,
            "reason": "oscillation_implies_high_energy_for_mass",
            "severity": "med",
        }

    return {"passed": True, "reason": "oscillation_energy_plausible", "severity": "none"}


def tilted_disk_descriptor(
    tilt_angle_rad: float,
    lift_vector_aligned: bool,
) -> dict[str, Any]:
    """Tilt implies lift vector not aligned with velocity."""
    return {
        "tilt_angle_rad": tilt_angle_rad,
        "lift_aligned_with_velocity": lift_vector_aligned,
        "control_law_required": not lift_vector_aligned,
        "unexplained_behavior_style": not lift_vector_aligned,
    }


def skipping_descriptor(
    n_cycles: int,
    period_s: float,
) -> dict[str, Any]:
    """Skipping = repeated lift/ballistic cycles."""
    return {
        "n_cycles": n_cycles,
        "period_s": period_s,
        "control_law_required": True,
        "unexplained_behavior_style": True,
    }


def record_extended_traits(
    claims: Any,
    physics: dict[str, Any],
) -> dict[str, Any]:
    """Record extended traits for scorecard. No auto-fail for style descriptors."""
    out: dict[str, Any] = {"lensing": None, "oscillation": None, "tilted_disk": None, "skipping": None}

    if getattr(claims, "gravitational_lensing_reported", False):
        lens = lensing_deflection_proxy(
            physics.get("mass_kg", 1000.0),
            impact_param_m=10.0,
            distance_m=1000.0,
        )
        out["lensing"] = lens

    if getattr(claims, "oscillation_blur_reported", False):
        blur = oscillation_blur_proxy(
            jitter_freq_hz=10.0,
            jitter_amplitude_m=0.1,
            range_m=1000.0,
            exposure_s=0.05,
        )
        out["oscillation"] = blur

    if getattr(claims, "tilted_disk_flight_reported", False):
        out["tilted_disk"] = tilted_disk_descriptor(0.5, lift_vector_aligned=False)

    if getattr(claims, "skipping_motion_reported", False):
        out["skipping"] = skipping_descriptor(5, period_s=2.0)

    return out
