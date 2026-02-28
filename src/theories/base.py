"""Minimal plugin interface for theory-backed observables."""

from __future__ import annotations

import json
from typing import Any, Protocol


class Theory(Protocol):
    """Small theory protocol for interchangeable deflection models."""

    name: str
    parameters: dict[str, float]

    def deflection_angle_vs_b(self, b_over_m: float, setup: dict[str, Any]) -> float:
        """Return deflection angle alpha (rad) for impact parameter b/M."""

    def known_limit_parameters(self) -> dict[str, float]:
        """Return params expected to recover known baseline behavior."""


class TheoryStressEnergy(Protocol):
    """Optional extension protocol for T_new/stress-energy introspection."""

    def stress_energy_summary(self, setup: dict[str, Any]) -> dict[str, Any]:
        """Return JSON-serializable stress-energy summary for this theory."""


def theory_stress_energy_summary(theory: Theory, setup: dict[str, Any]) -> dict[str, Any]:
    """
    Return optional stress-energy summary.

    If theory does not implement `stress_energy_summary`, return empty dict.
    """
    method = getattr(theory, "stress_energy_summary", None)
    if not callable(method):
        return {"requires_negative_energy": "unknown"}
    summary = method(setup)
    if not isinstance(summary, dict):
        raise TypeError("stress_energy_summary must return a dict.")
    summary_out = dict(summary)
    summary_out.setdefault("requires_negative_energy", "unknown")
    # Validate JSON-serializability at boundary where summary is captured.
    json.dumps(summary_out, ensure_ascii=True)
    return summary_out

