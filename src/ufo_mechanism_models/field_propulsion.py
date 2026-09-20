"""Field propulsion proxy (curvature / metric / inertial modification).

Not allowed to claim success without signature predictions.
Connects to curvature pipeline where applicable.
"""

from __future__ import annotations

from typing import Any


def evaluate_field_propulsion(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
    *,
    allow_speculative: bool = False,
) -> dict[str, Any]:
    """Evaluate field propulsion. Requires allow_speculative. Must predict signatures."""
    mass_kg = dynamics.get("mass_kg", 1000.0)
    required_power_w = dynamics.get("required_power_w", 0.0)
    required_force_N = dynamics.get("required_force_N", 0.0)

    passed = False
    failure_reason = "field_propulsion_requires_speculative_physics"

    if allow_speculative:
        passed = True
        failure_reason = "none"

    # Signature predictions: if curvature/metric modification, expect:
    # - EM field from stressed spacetime (order-of-magnitude proxy)
    # - Possible clock/gravimeter anomalies (link to curvature pipeline)
    em_field_proxy_t = 0.0
    if required_force_N > 0 and mass_kg > 0:
        # Crude proxy: B ~ sqrt(mu0 * energy_density)
        # For 1 m³ volume, rho_E ~ P/v ~ P
        import math
        mu0 = 4e-7 * math.pi
        em_field_proxy_t = (mu0 * required_power_w / 1.0) ** 0.5  # T, order-of-magnitude

    return {
        "lane": "field_propulsion",
        "passed": passed,
        "dominant_failure_reason": failure_reason,
        "required_inputs": {
            "mass_kg": mass_kg,
            "required_power_w": required_power_w,
            "required_force_N": required_force_N,
        },
        "predicted_signatures": {
            "em_field_proxy_t": em_field_proxy_t,
            "curvature_instrument_anomaly": "possible_if_metric_modification",
            "rf_anomaly_consistent": spec.get("rf_anomaly_reported", False),
        },
        "policy_snapshot": {"lane": "field_propulsion", "allow_speculative": allow_speculative},
        "curvature_pipeline_link": (
            "connect to curvature_energy_requirements for stress-energy budget"
        ),
    }
