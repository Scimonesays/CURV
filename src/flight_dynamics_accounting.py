"""Kinematics → forces → power → energy accounting for flight behavior.

Deterministic, physics-grounded. Outputs structured JSON blocks.
"""

from __future__ import annotations

import math
from typing import Any

# Physical constants (SI).
G_EARTH = 9.81
C_SOUND_SEA_LEVEL = 343.0  # m/s
RHO_AIR_SEA = 1.225
RHO_WATER = 1000.0


def required_force(mass_kg: float, accel_m_s2: float) -> float:
    """F = ma. Force in N."""
    return float(mass_kg) * float(accel_m_s2)


def required_power(force_N: float, velocity_m_s: float) -> float:
    """P = F*v for steady flight. Power in W."""
    return float(force_N) * float(velocity_m_s)


def turning_load(mass_kg: float, v_m_s: float, turn_radius_m: float) -> float:
    """Centripetal force F = m v²/r. N."""
    m = float(mass_kg)
    v = float(v_m_s)
    r = float(turn_radius_m)
    if r <= 0.0:
        raise ValueError("turn_radius_m must be positive")
    return m * (v * v) / r


def impulse_required(mass_kg: float, delta_v_m_s: float) -> float:
    """Impulse for delta-v: J = m * delta_v. N·s."""
    return float(mass_kg) * float(delta_v_m_s)


def energy_required(mass_kg: float, delta_v_m_s: float) -> float:
    """Kinetic energy change: E = (1/2) m (delta_v)². J."""
    return 0.5 * float(mass_kg) * (float(delta_v_m_s) ** 2)


def air_drag_heating_estimate(
    v_m_s: float,
    frontal_area_m2: float,
    rho_air_kg_m3: float = RHO_AIR_SEA,
    cd: float = 0.5,
) -> dict[str, Any]:
    """Order-of-magnitude drag heating. Conservative: Q ~ (1/2) rho v³ A Cd."""
    v = float(v_m_s)
    A = float(frontal_area_m2)
    rho = float(rho_air_kg_m3)
    drag_N = 0.5 * rho * (v**2) * A * cd
    power_w = drag_N * v
    return {
        "drag_force_N": drag_N,
        "heating_power_w": power_w,
        "supersonic": v > C_SOUND_SEA_LEVEL,
    }


def sonic_boom_expectation(
    v_m_s: float,
    altitude_m: float,
) -> dict[str, Any]:
    """Flag expected shock / sonic boom. Simple: Mach > 1 at altitude."""
    v = float(v_m_s)
    h = float(altitude_m)
    # Speed of sound decreases with altitude; crude: ~343 - 0.0065*h
    c_local = max(295.0, C_SOUND_SEA_LEVEL - 0.0065 * min(h, 11000))
    mach = v / c_local
    expect_boom = mach > 1.0
    return {
        "mach": mach,
        "speed_of_sound_local_m_s": c_local,
        "expect_sonic_boom": expect_boom,
        "altitude_m": h,
    }


def transmedium_penalty(
    v_m_s: float,
    frontal_area_m2: float,
    rho_water_kg_m3: float = RHO_WATER,
) -> dict[str, Any]:
    """Water entry drag penalty. F ~ (1/2) rho_water v² A."""
    v = float(v_m_s)
    A = float(frontal_area_m2)
    rho = float(rho_water_kg_m3)
    force_N = 0.5 * rho * (v**2) * A
    power_w = force_N * v
    # Heating: most KE goes into water heating / cavitation
    heating_j_per_m = 0.5 * rho * (v**2) * A  # J per meter of penetration
    return {
        "water_entry_force_N": force_N,
        "water_entry_power_w": power_w,
        "heating_per_meter_J": heating_j_per_m,
        "catastrophic_heating_risk": v > 100.0,  # > 100 m/s water entry is severe
    }


def full_dynamics_report(
    mass_kg: float,
    max_accel_m_s2: float,
    max_speed_m_s: float,
    turn_radius_m: float,
    hover_duration_s: float,
    frontal_area_m2: float = 1.0,
    altitude_m: float = 0.0,
) -> dict[str, Any]:
    """Complete kinematics and energy accounting."""
    force_accel = required_force(mass_kg, max_accel_m_s2)
    power_max = required_power(force_accel, max_speed_m_s)
    turn_force = turning_load(mass_kg, max_speed_m_s, turn_radius_m)
    impulse_dv = impulse_required(mass_kg, max_speed_m_s)
    ke_max = energy_required(mass_kg, max_speed_m_s)
    hover_energy_j = power_max * hover_duration_s  # upper bound

    drag = air_drag_heating_estimate(max_speed_m_s, frontal_area_m2)
    sonic = sonic_boom_expectation(max_speed_m_s, altitude_m)
    trans = transmedium_penalty(max_speed_m_s, frontal_area_m2)

    return {
        "mass_kg": mass_kg,
        "max_speed_m_s": max_speed_m_s,
        "required_force_N": force_accel,
        "required_power_w": power_max,
        "turning_force_N": turn_force,
        "impulse_Ns": impulse_dv,
        "kinetic_energy_max_J": ke_max,
        "hover_energy_upper_bound_J": hover_energy_j,
        "air_drag_heating": drag,
        "sonic_boom_expectation": sonic,
        "transmedium_penalty": trans,
    }
