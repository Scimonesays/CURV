"""UFO observables as reported claims (not facts).

Two dataclasses: UFOBehaviorSpec (kinematics) and UFOObservableClaims (absence/presence).
Treat observables as claims with confidence. Never assume UFOs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

G_EARTH = 9.81


@dataclass(frozen=True)
class UFOBehaviorSpec:
    """Kinematic claims."""

    max_accel_g: float
    max_speed_m_s: float
    turn_radius_m: float | None
    turn_rate_rad_s: float | None
    hover_duration_s: float | None
    transmedium: bool
    altitude_m: float | None
    water_speed_m_s: float | None

    @property
    def max_accel_m_s2(self) -> float:
        return self.max_accel_g * G_EARTH

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_accel_g": self.max_accel_g,
            "max_speed_m_s": self.max_speed_m_s,
            "turn_radius_m": self.turn_radius_m,
            "turn_rate_rad_s": self.turn_rate_rad_s,
            "hover_duration_s": self.hover_duration_s,
            "transmedium": self.transmedium,
            "altitude_m": self.altitude_m,
            "water_speed_m_s": self.water_speed_m_s,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UFOBehaviorSpec:
        defaults = {
            "max_accel_g": 100.0,
            "max_speed_m_s": 500.0,
            "turn_radius_m": 50.0,
            "turn_rate_rad_s": 10.0,
            "hover_duration_s": 60.0,
            "transmedium": False,
            "altitude_m": 5000.0,
            "water_speed_m_s": None,
        }
        merged = {**defaults, **{k: v for k, v in d.items() if k in defaults}}
        return cls(**merged)


@dataclass
class UFOObservableClaims:
    """Absence/presence claims and extended traits."""

    sonic_boom_absent: bool
    exhaust_absent: bool
    thermal_signature_low: bool
    contrail_absent: bool
    radar_track_intermittent: bool
    visual_cloaking_reported: bool
    gravitational_lensing_reported: bool
    oscillation_blur_reported: bool
    tilted_disk_flight_reported: bool
    skipping_motion_reported: bool
    notes: str = ""
    confidence: dict[str, float] = field(default_factory=dict)
    sensor_context: dict[str, Any] = field(default_factory=dict)

    def get_confidence(self, key: str) -> float:
        return self.confidence.get(key, 0.8)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sonic_boom_absent": self.sonic_boom_absent,
            "exhaust_absent": self.exhaust_absent,
            "thermal_signature_low": self.thermal_signature_low,
            "contrail_absent": self.contrail_absent,
            "radar_track_intermittent": self.radar_track_intermittent,
            "visual_cloaking_reported": self.visual_cloaking_reported,
            "gravitational_lensing_reported": self.gravitational_lensing_reported,
            "oscillation_blur_reported": self.oscillation_blur_reported,
            "tilted_disk_flight_reported": self.tilted_disk_flight_reported,
            "skipping_motion_reported": self.skipping_motion_reported,
            "notes": self.notes,
            "confidence": dict(self.confidence),
            "sensor_context": dict(self.sensor_context),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UFOObservableClaims:
        defaults = {
            "sonic_boom_absent": False,
            "exhaust_absent": False,
            "thermal_signature_low": False,
            "contrail_absent": False,
            "radar_track_intermittent": False,
            "visual_cloaking_reported": False,
            "gravitational_lensing_reported": False,
            "oscillation_blur_reported": False,
            "tilted_disk_flight_reported": False,
            "skipping_motion_reported": False,
            "notes": "",
            "confidence": {},
            "sensor_context": {},
        }
        merged = {**defaults, **{k: v for k, v in d.items() if k in defaults}}
        return cls(**merged)


def profile_tictac_like() -> tuple[UFOBehaviorSpec, UFOObservableClaims]:
    """Tic-tac-like: 300-600g, hypersonic, no boom, no exhaust, transmedium."""
    behavior = UFOBehaviorSpec(
        max_accel_g=500.0,
        max_speed_m_s=1700.0,  # ~Mach 5
        turn_radius_m=10.0,
        turn_rate_rad_s=50.0,
        hover_duration_s=300.0,
        transmedium=True,
        altitude_m=5000.0,
        water_speed_m_s=100.0,
    )
    claims = UFOObservableClaims(
        sonic_boom_absent=True,
        exhaust_absent=True,
        thermal_signature_low=True,
        contrail_absent=True,
        radar_track_intermittent=True,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
        notes="tic-tac-like profile",
    )
    return behavior, claims


def profile_hypersonic_no_boom() -> tuple[UFOBehaviorSpec, UFOObservableClaims]:
    """Hypersonic velocity, no sonic boom, no contrail, no heat."""
    behavior = UFOBehaviorSpec(
        max_accel_g=200.0,
        max_speed_m_s=2000.0,  # ~Mach 6
        turn_radius_m=20.0,
        turn_rate_rad_s=30.0,
        hover_duration_s=60.0,
        transmedium=False,
        altitude_m=10000.0,
        water_speed_m_s=None,
    )
    claims = UFOObservableClaims(
        sonic_boom_absent=True,
        exhaust_absent=True,
        thermal_signature_low=True,
        contrail_absent=True,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
        notes="hypersonic no boom",
    )
    return behavior, claims


def profile_edgecase_hypersonic_no_boom() -> tuple[UFOBehaviorSpec, UFOObservableClaims]:
    """Edge-case profile for Element X testing: brutal, intentionally extreme.

    max_accel_g=600, max_speed ~Mach 6, transmedium, no boom, no exhaust, low thermal.
    Optional gravitational lensing. Should trigger many negative gates.
    """
    behavior = UFOBehaviorSpec(
        max_accel_g=600.0,
        max_speed_m_s=2000.0,  # ~Mach 6 depending altitude
        turn_radius_m=10.0,
        turn_rate_rad_s=50.0,
        hover_duration_s=60.0,
        transmedium=True,
        altitude_m=5000.0,
        water_speed_m_s=100.0,
    )
    claims = UFOObservableClaims(
        sonic_boom_absent=True,
        exhaust_absent=True,
        thermal_signature_low=True,
        contrail_absent=True,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=True,  # optional
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
        notes="edgecase hypersonic no boom",
    )
    return behavior, claims


def profile_plausible_moderate() -> tuple[UFOBehaviorSpec, UFOObservableClaims]:
    """Plausible-ish profile: weird but not fantasy. Sanity check for over-rejection.

    30–50g, subsonic or barely transonic, no lensing, no transmedium.
    Should reduce negatives vs edgecase.
    """
    behavior = UFOBehaviorSpec(
        max_accel_g=40.0,
        max_speed_m_s=300.0,  # subsonic
        turn_radius_m=50.0,
        turn_rate_rad_s=5.0,
        hover_duration_s=120.0,
        transmedium=False,
        altitude_m=3000.0,
        water_speed_m_s=None,
    )
    claims = UFOObservableClaims(
        sonic_boom_absent=True,
        exhaust_absent=True,
        thermal_signature_low=True,
        contrail_absent=True,
        radar_track_intermittent=False,
        visual_cloaking_reported=False,
        gravitational_lensing_reported=False,
        oscillation_blur_reported=False,
        tilted_disk_flight_reported=False,
        skipping_motion_reported=False,
        notes="plausible moderate",
    )
    return behavior, claims


def from_json(path: str | Path) -> tuple[UFOBehaviorSpec, UFOObservableClaims]:
    """Load behavior + claims from JSON. Expects 'behavior' and 'claims' keys."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    behavior = UFOBehaviorSpec.from_dict(data.get("behavior", data))
    claims = UFOObservableClaims.from_dict(data.get("claims", {}))
    return behavior, claims
