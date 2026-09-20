"""Schwarzschild baseline plugin using numeric null geodesics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.gr.geodesic import trace_null_ray


@dataclass
class GRSchwarzschild:
    """Baseline truth model backed by equatorial geodesic integration."""

    mass: float = 1.0
    rel_step: float = 1.0e-6
    x0_over_m: float = 1000.0
    max_steps: int = 36_000
    name: str = "gr_schwarzschild"
    parameters: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.parameters = {"mass": float(self.mass)}

    def deflection_angle_vs_b(self, b_over_m: float, setup: dict[str, Any]) -> float:
        h = float(setup.get("h", 0.5))
        max_steps = int(setup.get("max_steps", self.max_steps))
        ray = trace_null_ray(
            b_over_m=float(b_over_m),
            mass=float(self.mass),
            x0_over_m=float(self.x0_over_m),
            dlambda=h,
            max_steps=max_steps,
            rel_step=float(self.rel_step),
        )
        return float(ray["alpha_numeric"])

    def known_limit_parameters(self) -> dict[str, float]:
        return {"mass": float(self.mass)}

    def stress_energy_summary(self, setup: dict[str, Any]) -> dict[str, Any]:
        _ = setup
        return {
            "tnew_model": "none",
            "rho_eff_peak": "NA",
            "energy_condition_flags": "NA",
            "requires_negative_energy": "unknown",
        }

