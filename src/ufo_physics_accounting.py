"""Physics accounting: forces, power, energy, heating, cavitation.

Deterministic. Energy bill: F=ma, P≈F·v, E=P·t, ρ_E=E/V, m_equiv=E/c².
ISA approximation for speed of sound.
"""

from __future__ import annotations

from typing import Any

from .ufo_observables import G_EARTH, UFOBehaviorSpec

C_SOUND_SEA = 343.0
C_LIGHT = 299_792_458.0
RHO_AIR_SEA = 1.225
RHO_WATER = 1000.0


def accel_g_to_m_s2(accel_g: float) -> float:
    return accel_g * G_EARTH


def speed_of_sound_isa(altitude_m: float) -> float:
    """Crude ISA: c decreases ~0.0065 m/s per m up to 11 km."""
    h = min(float(altitude_m), 11000.0)
    return max(295.0, C_SOUND_SEA - 0.0065 * h)


def compute_physics_accounting(
    behavior: UFOBehaviorSpec,
    mass_kg: float,
    frontal_area_m2: float = 1.0,
    active_volume_m3: float | None = None,
) -> dict[str, Any]:
    """Required forces, power, energy, heating, cavitation risk."""
    m = float(mass_kg)
    a = behavior.max_accel_m_s2
    v = behavior.max_speed_m_s
    r = behavior.turn_radius_m or 50.0
    h = behavior.altitude_m or 5000.0
    v_water = behavior.water_speed_m_s or 0.0

    required_force_N = m * a
    required_power_W = required_force_N * v
    ke = 0.5 * m * (v**2)
    required_energy_J = ke
    hover_t_s = behavior.hover_duration_s or 60.0
    hover_energy_J = required_power_W * hover_t_s
    volume_m3 = active_volume_m3 if active_volume_m3 is not None else 1.0
    rho_E_j_m3 = required_energy_J / volume_m3 if volume_m3 > 0 else 0.0
    mass_equivalent_kg = required_energy_J / (C_LIGHT**2)

    c_local = speed_of_sound_isa(h)
    mach_est = v / c_local if c_local > 0 else 0.0

    # Air drag heating
    drag_N = 0.5 * RHO_AIR_SEA * (v**2) * frontal_area_m2 * 0.5
    air_heating_W = drag_N * v

    # Water drag (transmedium)
    if behavior.transmedium and v_water > 0:
        f_water = 0.5 * RHO_WATER * (v_water**2) * frontal_area_m2
        water_drag_W = f_water * v_water
    else:
        water_drag_W = 0.0

    # Cavitation risk
    if v_water > 200.0:
        cavitation_risk = "high"
    elif v_water > 50.0:
        cavitation_risk = "med"
    else:
        cavitation_risk = "low"

    return {
        "transmedium": behavior.transmedium,
        "required_force_N": required_force_N,
        "required_power_W": required_power_W,
        "required_energy_J": required_energy_J,
        "hover_energy_J": hover_energy_J,
        "rho_E_j_m3": rho_E_j_m3,
        "mass_equivalent_kg": mass_equivalent_kg,
        "active_volume_m3": volume_m3,
        "mach_est": mach_est,
        "air_heating_W": air_heating_W,
        "water_drag_W": water_drag_W,
        "cavitation_risk": cavitation_risk,
        "mass_kg": m,
        "max_speed_m_s": v,
        "altitude_m": h,
        "max_accel_m_s2": a,
        "hover_duration_s": hover_t_s,
    }
