"""PPN-style weak-field deflection plugin with explicit GR recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp
from typing import Any


@dataclass
class GRPPNScreenedPotential:
    """
    PPN/screened-potential weak-field proxy.

    alpha(b) ~= [2 * (1 + gamma_ppn) / b] * [1 + alpha_s * exp(-b/lambda_s_over_m)]
    with GR limit gamma_ppn=1 and alpha_s=0.
    """

    gamma_ppn: float = 1.0
    alpha_s: float = 0.0
    lambda_s_over_m: float = 50.0
    name: str = "gr_ppn_screened_potential"
    parameters: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.parameters = {
            "gamma_ppn": float(self.gamma_ppn),
            "alpha_s": float(self.alpha_s),
            "lambda_s_over_m": float(self.lambda_s_over_m),
        }

    def deflection_angle_vs_b(self, b_over_m: float, setup: dict[str, Any]) -> float:
        _ = setup
        b = float(b_over_m)
        if b <= 0.0:
            raise ValueError("b_over_m must be positive.")
        screening = 1.0 + float(self.alpha_s) * exp(-b / float(self.lambda_s_over_m))
        return (2.0 * (1.0 + float(self.gamma_ppn)) / b) * screening

    def known_limit_parameters(self) -> dict[str, float]:
        return {
            "gamma_ppn": 1.0,
            "alpha_s": 0.0,
            "lambda_s_over_m": float(self.lambda_s_over_m),
        }

    def stress_energy_summary(self, setup: dict[str, Any]) -> dict[str, Any]:
        _ = setup
        return {
            "tnew_model": "ppn_parameterization",
            "gamma_ppn": float(self.gamma_ppn),
            "alpha_s": float(self.alpha_s),
            "lambda_s_over_m": float(self.lambda_s_over_m),
            "rho_eff_peak": "NA",
            "energy_condition_flags": "NA",
            "requires_negative_energy": "unknown",
        }

