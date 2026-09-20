"""UFO mechanism lanes. Each returns passed, dominant_failure_reason, predicted_signatures, assumptions."""

from __future__ import annotations

from .aerodynamic_lift import evaluate_aerodynamic_lift
from .conventional_thrust import evaluate_conventional_thrust
from .metric_bubble import evaluate_metric_bubble
from .non_exhaust_propulsion import evaluate_non_exhaust_propulsion
from .novel_power_source import evaluate_novel_power_source
from .plasma_boundary_layer import evaluate_plasma_boundary_layer
from .reactionless_placeholder import evaluate_reactionless_placeholder

LANE_NAMES = (
    "conventional_thrust",
    "aerodynamic_lift",
    "plasma_boundary_layer",
    "metric_bubble",
    "reactionless_placeholder",
    "novel_power_source",
    "non_exhaust_propulsion",
)


def evaluate_all_lanes(
    physics: dict,
    claims: object,
    *,
    allow_speculative: bool = False,
    policy: str = "strict",
) -> list[dict]:
    """Run all mechanism lanes."""
    results = [
        evaluate_conventional_thrust(physics, claims),
        evaluate_aerodynamic_lift(physics, claims),
        evaluate_plasma_boundary_layer(physics, claims),
        evaluate_metric_bubble(physics, claims, allow_speculative=allow_speculative),
        evaluate_reactionless_placeholder(physics, claims, allow_speculative=allow_speculative),
        evaluate_novel_power_source(physics, claims),
    ]
    if getattr(claims, "exhaust_absent", False):
        results.append(
            evaluate_non_exhaust_propulsion(physics, claims, policy=policy)
        )
    return results
