"""Formal UFO/UAP flight behavior specification.

Defines a structured behavior profile for physics-grounded evaluation.
Does NOT assume any mechanism is real. Used as input to kinematics and constraint gates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ProfileName = Literal["tic_tac", "custom"]


# Nimitz "tic tac" inferred profile (Navy 2004). Values are estimates from reports.
# Conservative: use mid-range where uncertain.
TIC_TAC_DEFAULTS: dict[str, Any] = {
    "max_accel_m_s2": 5000.0,  # ~500g reported; extreme
    "max_speed_m_s": 1000.0,   # Mach 3 class
    "turn_radius_m": 10.0,     # tight turns
    "max_turn_rate_rad_s": 50.0,
    "hover_duration_s": 300.0,
    "altitude_min_m": 0.0,
    "altitude_max_m": 25000.0,
    "transmedium": True,
    "sonic_boom_absent": True,
    "visible_exhaust_absent": True,
    "thermal_signature_low": True,
    "rf_anomaly_reported": True,
    "plasma_glow_reported": True,
    "observed_distance_m": 1000.0,
}


@dataclass(frozen=True)
class UFOBehaviorSpec:
    """Structured flight behavior profile for physics evaluation."""

    max_accel_m_s2: float
    max_speed_m_s: float
    turn_radius_m: float
    max_turn_rate_rad_s: float
    hover_duration_s: float
    altitude_min_m: float
    altitude_max_m: float
    transmedium: bool
    sonic_boom_absent: bool
    visible_exhaust_absent: bool
    thermal_signature_low: bool
    rf_anomaly_reported: bool
    plasma_glow_reported: bool
    observed_distance_m: float

    @property
    def max_accel_g(self) -> float:
        """Max acceleration in g (9.81 m/s²)."""
        return self.max_accel_m_s2 / 9.81

    @property
    def max_mach(self) -> float:
        """Max speed in Mach (at sea level ~343 m/s)."""
        return self.max_speed_m_s / 343.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON."""
        return {
            "max_accel_m_s2": self.max_accel_m_s2,
            "max_speed_m_s": self.max_speed_m_s,
            "turn_radius_m": self.turn_radius_m,
            "max_turn_rate_rad_s": self.max_turn_rate_rad_s,
            "hover_duration_s": self.hover_duration_s,
            "altitude_min_m": self.altitude_min_m,
            "altitude_max_m": self.altitude_max_m,
            "transmedium": self.transmedium,
            "sonic_boom_absent": self.sonic_boom_absent,
            "visible_exhaust_absent": self.visible_exhaust_absent,
            "thermal_signature_low": self.thermal_signature_low,
            "rf_anomaly_reported": self.rf_anomaly_reported,
            "plasma_glow_reported": self.plasma_glow_reported,
            "observed_distance_m": self.observed_distance_m,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UFOBehaviorSpec:
        """Build from dict with defaults for missing keys."""
        defaults = {
            "max_accel_m_s2": 100.0,
            "max_speed_m_s": 300.0,
            "turn_radius_m": 100.0,
            "max_turn_rate_rad_s": 1.0,
            "hover_duration_s": 60.0,
            "altitude_min_m": 0.0,
            "altitude_max_m": 10000.0,
            "transmedium": False,
            "sonic_boom_absent": False,
            "visible_exhaust_absent": False,
            "thermal_signature_low": False,
            "rf_anomaly_reported": False,
            "plasma_glow_reported": False,
            "observed_distance_m": 1000.0,
        }
        merged = {**defaults, **{k: v for k, v in d.items() if k in defaults}}
        return cls(**merged)

    @classmethod
    def from_common_uap_profile(cls, profile: ProfileName) -> UFOBehaviorSpec:
        """Build from named common UAP profile."""
        if profile == "tic_tac":
            return cls.from_dict(TIC_TAC_DEFAULTS)
        raise ValueError(f"Unknown profile: {profile!r}. Use tic_tac or custom.")

    @classmethod
    def from_custom_json(cls, path: str | Path) -> UFOBehaviorSpec:
        """Build from JSON file. Missing keys use defaults."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Profile JSON not found: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)
