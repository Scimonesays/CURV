"""Conventional thrust lane: rocket/jet-like propulsion.

Predicts exhaust power, heat, acoustic/IR signature.
Fails if no exhaust + huge accel mismatch is too large.
"""

from __future__ import annotations

from typing import Any


def evaluate_conventional_thrust(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate conventional thrust mechanism against behavior spec."""
    required_power_w = dynamics.get("required_power_w", 0.0)
    mass_kg = dynamics.get("mass_kg", 1000.0)
    exhaust_absent = spec.get("visible_exhaust_absent", False)
    thermal_low = spec.get("thermal_signature_low", False)

    # Exhaust: thrust requires mass ejection. ~50% of power goes to exhaust heat.
    exhaust_power_w = 0.5 * required_power_w
    exhaust_temp_proxy_k = 2000.0  # typical rocket exhaust
    ir_brightness_proxy_w_sr = exhaust_power_w / (4 * 3.14159)  # isotropic proxy

    passed = True
    failure_reason = "none"

    if exhaust_absent and required_power_w > 1e6:
        # No visible exhaust + MW-class thrust is incompatible
        passed = False
        failure_reason = "no_exhaust_plus_high_thrust"
    if thermal_low and required_power_w > 1e7:
        # Low thermal claim + 10 MW+ is incompatible
        passed = False
        if failure_reason == "none":
            failure_reason = "low_thermal_claim_inconsistent_with_power"

    return {
        "lane": "conventional_thrust",
        "passed": passed,
        "dominant_failure_reason": failure_reason,
        "required_inputs": {
            "mass_kg": mass_kg,
            "required_power_w": required_power_w,
        },
        "predicted_signatures": {
            "exhaust_power_w": exhaust_power_w,
            "exhaust_temp_proxy_k": exhaust_temp_proxy_k,
            "ir_brightness_proxy_w_sr": ir_brightness_proxy_w_sr,
            "acoustic_signature": "high" if required_power_w > 1e6 else "med" if required_power_w > 1e4 else "low",
        },
        "policy_snapshot": {"lane": "conventional_thrust", "allow_speculative": False},
    }
