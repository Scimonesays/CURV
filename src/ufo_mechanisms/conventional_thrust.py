"""Conventional thrust: rocket/jet-like. Thrust-based, exhaust required."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

G_EARTH = 9.81

# Reason codes when lane fails
FAIL_TW_INSUFFICIENT = "tw_insufficient"
FAIL_SUSTAINED_POWER_EXCEEDS = "sustained_power_exceeds_limit"
FAIL_BURST_ONLY_NOT_APPLICABLE = "burst_only_not_applicable"
FAIL_PROPELLANT_MASS_EXCESSIVE = "propellant_mass_excessive"
FAIL_G_LOAD_UNREALISTIC = "g_load_unrealistic_for_structure"


@dataclass
class ConventionalThrustSpec:
    """Engine-class specification for conventional thrust evaluation."""

    engine_class: str
    max_TW: float
    max_sustained_power_W: float
    max_burst_power_W: float
    burst_duration_s: float
    waste_heat_fraction: float
    exhaust_visible: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_class": self.engine_class,
            "max_TW": self.max_TW,
            "max_sustained_power_W": self.max_sustained_power_W,
            "max_burst_power_W": self.max_burst_power_W,
            "burst_duration_s": self.burst_duration_s,
            "waste_heat_fraction": self.waste_heat_fraction,
            "exhaust_visible": self.exhaust_visible,
            "notes": self.notes,
        }


# Default presets (strict known physics)
PRESET_ROCKET = ConventionalThrustSpec(
    engine_class="rocket",
    max_TW=35.0,  # aggressive solid rocket, allows ~35g
    max_sustained_power_W=50e6,
    max_burst_power_W=200e6,
    burst_duration_s=30.0,
    waste_heat_fraction=0.1,
    exhaust_visible=True,
    notes="high-performance solid rocket, aggressive but physical",
)

PRESET_JET = ConventionalThrustSpec(
    engine_class="jet",
    max_TW=2.0,
    max_sustained_power_W=20e6,
    max_burst_power_W=30e6,
    burst_duration_s=60.0,
    waste_heat_fraction=0.6,
    exhaust_visible=True,
    notes="turbojet; fails 30g",
)

PRESET_NUCLEAR_THERMAL_ROCKET = ConventionalThrustSpec(
    engine_class="nuclear_thermal_rocket",
    max_TW=5.0,
    max_sustained_power_W=100e6,
    max_burst_power_W=100e6,
    burst_duration_s=300.0,
    waste_heat_fraction=0.3,
    exhaust_visible=True,
    notes="NTR; depends on config",
)

PRESET_BEAMED_THERMAL = ConventionalThrustSpec(
    engine_class="beamed_thermal",
    max_TW=10.0,
    max_sustained_power_W=80e6,
    max_burst_power_W=80e6,
    burst_duration_s=60.0,
    waste_heat_fraction=0.8,
    exhaust_visible=True,
    notes="high thermal signature",
)

PRESETS = [
    PRESET_ROCKET,
    PRESET_JET,
    PRESET_NUCLEAR_THERMAL_ROCKET,
    PRESET_BEAMED_THERMAL,
]

# Conservative g-load beyond which structure is unrealistic
G_LOAD_STRUCTURE_LIMIT = 100.0


def _evaluate_one_mass(
    m_kg: float,
    a_m_s2: float,
    v_m_s: float,
    duration_s: float,
    spec: ConventionalThrustSpec,
) -> tuple[bool, str | None]:
    """Check if one mass passes for given spec. Returns (passed, reason_or_none)."""
    if a_m_s2 / G_EARTH > G_LOAD_STRUCTURE_LIMIT:
        return False, FAIL_G_LOAD_UNREALISTIC

    F_required = m_kg * a_m_s2
    P_required = F_required * v_m_s
    F_available = spec.max_TW * m_kg * G_EARTH

    if F_available < F_required:
        return False, FAIL_TW_INSUFFICIENT

    if duration_s <= spec.burst_duration_s:
        if P_required > spec.max_burst_power_W:
            return False, FAIL_SUSTAINED_POWER_EXCEEDS
    else:
        if P_required > spec.max_sustained_power_W:
            return False, FAIL_SUSTAINED_POWER_EXCEEDS
        if spec.burst_duration_s < duration_s and spec.max_burst_power_W > spec.max_sustained_power_W:
            pass
        # sustained applies for long duration

    return True, None


def _sweep_mass_range(
    mass_min: float,
    mass_max: float,
    a_m_s2: float,
    v_m_s: float,
    duration_s: float,
    spec: ConventionalThrustSpec,
    n_samples: int = 11,
) -> tuple[bool, list[str], float | None]:
    """Sweep mass range. Returns (any_passed, failure_reasons, passing_mass_or_none)."""
    reasons: list[str] = []
    passing_mass: float | None = None

    if mass_min <= 0 or mass_max <= 0:
        return False, [FAIL_TW_INSUFFICIENT], None

    import math
    if mass_min >= mass_max:
        masses = [mass_min]
    else:
        log_min = math.log(mass_min)
        log_max = math.log(mass_max)
        masses = [
            math.exp(log_min + (log_max - log_min) * i / max(1, n_samples - 1))
            for i in range(n_samples)
        ]

    for m in masses:
        passed, reason = _evaluate_one_mass(m, a_m_s2, v_m_s, duration_s, spec)
        if passed:
            return True, [], m
        if reason and reason not in reasons:
            reasons.append(reason)

    return False, reasons if reasons else [FAIL_TW_INSUFFICIENT], None


def evaluate_conventional_thrust(
    physics: dict[str, Any],
    claims: Any,
    *,
    spec: ConventionalThrustSpec | None = None,
    presets: list[ConventionalThrustSpec] | None = None,
) -> dict[str, Any]:
    """Evaluate conventional thrust lane across mass range.

    Pass if any preset + any mass in [min,max] passes.
    Returns explicit failure reasons when it fails.
    """
    mass_range = physics.get("mass_range_kg")
    if not mass_range or len(mass_range) < 2:
        mass_kg = physics.get("mass_kg", 1000.0)
        mass_range = (mass_kg, mass_kg)

    mass_min = float(mass_range[0])
    mass_max = float(mass_range[1])

    a_m_s2 = physics.get("max_accel_m_s2")
    if a_m_s2 is None:
        m_nom = physics.get("mass_kg", (mass_min * mass_max) ** 0.5)
        F = physics.get("required_force_N", 0.0)
        a_m_s2 = F / m_nom if m_nom > 0 else 0.0

    v_m_s = physics.get("max_speed_m_s", 250.0)
    duration_s = physics.get("hover_duration_s", 60.0)

    power_W = physics.get("required_power_W", 0.0)
    mass_kg = physics.get("mass_kg", (mass_min * mass_max) ** 0.5)
    mach = physics.get("mach_est", 0.0)

    exhaust_power = 0.5 * power_W
    ir_brightness_proxy = exhaust_power / (4 * 3.14159) if exhaust_power > 0 else 0.0
    plasma_likelihood = "high" if mach > 2.0 else "med" if mach > 1.0 else "low"
    sonic_boom_expected = mach > 1.0

    pred = {
        "ir_brightness_proxy": ir_brightness_proxy,
        "em_activity_proxy": 0.0,
        "plasma_likelihood": plasma_likelihood,
        "sonic_boom_expected": sonic_boom_expected,
        "exhaust_power_W": exhaust_power,
    }

    specs_to_try = []
    if spec:
        specs_to_try.append(spec)
    if presets:
        specs_to_try.extend(presets)
    if not specs_to_try:
        specs_to_try = PRESETS

    all_reasons: list[str] = []
    best_preset: str | None = None
    passing_mass: float | None = None

    for s in specs_to_try:
        passed, reasons, pm = _sweep_mass_range(
            mass_min, mass_max, a_m_s2, v_m_s, duration_s, s
        )
        if passed:
            return {
                "lane": "conventional_thrust",
                "passed": True,
                "dominant_failure_reason": None,
                "failure_reasons": [],
                "passing_preset": s.engine_class,
                "passing_mass_kg": pm,
                "predicted_signatures": pred,
                "thrust_based": True,
                "shock_mitigation_declared": False,
                "heat_dump_explained": False,
                "coupling_reduction_declared": False,
                "assumptions": {"thrust_based": True, "engine_class": s.engine_class},
            }
        all_reasons.extend(reasons)
        if not best_preset:
            best_preset = s.engine_class

    dominant = all_reasons[0] if all_reasons else FAIL_TW_INSUFFICIENT
    unique_reasons = list(dict.fromkeys(all_reasons))

    return {
        "lane": "conventional_thrust",
        "passed": False,
        "dominant_failure_reason": dominant,
        "failure_reasons": unique_reasons,
        "passing_preset": None,
        "passing_mass_kg": None,
        "predicted_signatures": pred,
        "thrust_based": True,
        "shock_mitigation_declared": False,
        "heat_dump_explained": False,
        "coupling_reduction_declared": False,
        "assumptions": {"thrust_based": True},
    }
