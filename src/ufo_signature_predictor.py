"""Secondary signatures: what MUST show up if the behavior is real.

UFO behavior claims must pay the signature bill.
"""

from __future__ import annotations

from typing import Any


def predict_signatures(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
    lane: str,
) -> dict[str, Any]:
    """Predict observables given behavior + lane."""
    power_w = dynamics.get("required_power_w", 0.0)
    mass_kg = dynamics.get("mass_kg", 1000.0)
    sonic = dynamics.get("sonic_boom_expectation", {})
    mach = sonic.get("mach", 0.0)
    c_sound = sonic.get("speed_of_sound_local_m_s", 343.0)
    v_m_s = dynamics.get("max_speed_m_s", mach * c_sound)
    trans = dynamics.get("transmedium_penalty", {})
    drag = dynamics.get("air_drag_heating", {})

    # Thermal / IR
    thermal_power_w = power_w
    ir_brightness_order = "high" if thermal_power_w > 1e6 else "med" if thermal_power_w > 1e3 else "low"

    # Acoustic / shockwave
    expect_shock = sonic.get("expect_sonic_boom", False)
    acoustic_expectation = "strong_boom" if expect_shock else "turbulent" if mach > 0.5 else "low"

    # Ionization / plasma
    plasma_likelihood = "high" if mach > 2.0 or thermal_power_w > 1e7 else "med" if mach > 1.0 else "low"

    # EM (if field mechanism)
    em_proxy = 0.0
    if lane == "field_propulsion":
        import math
        mu0 = 4e-7 * math.pi
        em_proxy = (mu0 * power_w) ** 0.5

    # Radiation risk (only if model implies it - conservative: none for standard lanes)
    radiation_risk = "low"  # placeholder; no model implies significant radiation

    # Wake / turbulence / contrail
    wake_expectation = "strong" if mach > 0.8 else "moderate" if mach > 0.3 else "weak"

    # Water entry/exit (transmedium)
    water_entry = spec.get("transmedium", False)
    splash_steam_expectation = "catastrophic" if trans.get("catastrophic_heating_risk", False) else "significant" if water_entry else "none"

    return {
        "thermal_power_w": thermal_power_w,
        "ir_brightness_order": ir_brightness_order,
        "acoustic_expectation": acoustic_expectation,
        "expect_sonic_boom": expect_shock,
        "plasma_likelihood": plasma_likelihood,
        "em_field_proxy_t": em_proxy,
        "radiation_risk": radiation_risk,
        "wake_expectation": wake_expectation,
        "water_entry_splash_steam": splash_steam_expectation,
        "transmedium": water_entry,
    }
