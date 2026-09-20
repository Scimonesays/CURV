"""Candidate mechanism lanes for UFO flight behavior.

Each lane evaluates whether known/speculative physics could produce
the observed behavior. None assume any mechanism is true.
"""

from __future__ import annotations

from typing import Any

from .aerodynamic import evaluate_aerodynamic
from .conventional_thrust import evaluate_conventional_thrust
from .field_propulsion import evaluate_field_propulsion
from .reactionless import evaluate_reactionless

LANE_NAMES = ("conventional_thrust", "aerodynamic", "reactionless", "field_propulsion")


def evaluate_all_lanes(
    dynamics: dict[str, Any],
    spec: dict[str, Any],
    *,
    allow_speculative: bool = False,
) -> dict[str, Any]:
    """Run all lanes and return combined results."""
    results = []
    for name in LANE_NAMES:
        if name == "conventional_thrust":
            r = evaluate_conventional_thrust(dynamics, spec)
        elif name == "aerodynamic":
            r = evaluate_aerodynamic(dynamics, spec)
        elif name == "reactionless":
            r = evaluate_reactionless(dynamics, spec, allow_speculative=allow_speculative)
        elif name == "field_propulsion":
            r = evaluate_field_propulsion(dynamics, spec, allow_speculative=allow_speculative)
        else:
            raise ValueError(f"Unknown lane: {name}")
        results.append(r)
    return {"lane_results": results, "lanes_run": list(LANE_NAMES)}
