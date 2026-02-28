"""Yukawa-like weak-field deviation plugin with explicit GR limit."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp
from typing import Any


@dataclass
class GRYukawaDeviation:
    """
    Weak-field deflection model with one deviation parameter.

    alpha(b) = (4/b) * [1 + alpha_y * exp(-b/lambda_y_over_m)]
    in units G = c = M = 1 for b_over_m input.
    """

    alpha_y: float = 0.0
    lambda_y_over_m: float = 50.0
    name: str = "gr_yukawa_deviation"
    parameters: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.parameters = {
            "alpha_y": float(self.alpha_y),
            "lambda_y_over_m": float(self.lambda_y_over_m),
        }

    def deflection_angle_vs_b(self, b_over_m: float, setup: dict[str, Any]) -> float:
        _ = setup  # setup kept for uniform interface; this model is closed-form.
        b = float(b_over_m)
        if b <= 0.0:
            raise ValueError("b_over_m must be positive.")
        factor = 1.0 + float(self.alpha_y) * exp(-b / float(self.lambda_y_over_m))
        return (4.0 / b) * factor

    def known_limit_parameters(self) -> dict[str, float]:
        return {"alpha_y": 0.0, "lambda_y_over_m": float(self.lambda_y_over_m)}

    def stress_energy_summary(self, setup: dict[str, Any]) -> dict[str, Any]:
        _ = setup
        return {
            "tnew_model": "yukawa_weak_field",
            "alpha_y": float(self.alpha_y),
            "lambda_y_over_m": float(self.lambda_y_over_m),
            "rho_eff_peak": "NA",
            "energy_condition_flags": "NA",
            "requires_negative_energy": "unknown",
        }

