"""Curvature cost sanity scaling for bubble-style claims."""

from __future__ import annotations

import math
import os
from typing import Any

from .coupling_scale_calibrator import C_LIGHT, calibrated_report_for_length

M_EARTH_KG = 5.9722e24
M_JUPITER_KG = 1.89813e27
M_SUN_KG = 1.98847e30

# Screening thresholds (triage defaults, not physical limits).
MAX_M_EQUIV_KG = float(os.getenv("CURV_MAX_M_EQUIV_KG", "1e12"))
MAX_E_SCALE_J = float(os.getenv("CURV_MAX_E_SCALE_J", str(MAX_M_EQUIV_KG * (C_LIGHT**2))))
MAX_RHO_E_J_PER_M3 = float(os.getenv("CURV_MAX_RHO_E_J_PER_M3", str(1.0e25 * (C_LIGHT**2))))


def _volume_m3(*, l_m: float, geometry: str, thickness_m: float | None) -> float:
    if geometry == "sphere":
        return (4.0 / 3.0) * math.pi * (l_m**3)
    if geometry == "shell":
        if thickness_m is None:
            raise ValueError("thickness_m is required for shell geometry.")
        if thickness_m <= 0.0:
            raise ValueError("thickness_m must be positive.")
        return 4.0 * math.pi * (l_m**2) * float(thickness_m)
    raise ValueError(f"Unsupported geometry: {geometry}")


def curvature_cost_sanity(
    l_m: float,
    geometry: str = "sphere",
    thickness_m: float | None = None,
) -> dict[str, Any]:
    """Compute order-of-magnitude curvature cost scaling and triage gate.

    For backward compatibility, legacy dimensional proxy values remain the default
    for gate checks while EFE-calibrated values are always logged.
    """
    if l_m <= 0.0:
        raise ValueError("L_m must be positive.")
    geom = str(geometry).lower()
    v_m3 = _volume_m3(l_m=float(l_m), geometry=geom, thickness_m=thickness_m)

    cal = calibrated_report_for_length(float(l_m))
    rho_e_proxy = float(cal["rho_e_dimensional_proxy_j_per_m3"])
    rho_e_efe = float(cal["rho_e_efe_calibrated_j_per_m3"])
    rho_e = rho_e_proxy
    e_scale = rho_e * v_m3
    m_equiv = e_scale / (C_LIGHT**2)
    e_scale_efe = rho_e_efe * v_m3
    m_equiv_efe = e_scale_efe / (C_LIGHT**2)

    reasons: list[str] = []
    if rho_e > MAX_RHO_E_J_PER_M3:
        reasons.append("rho_e_exceeds_ceiling")
    if e_scale > MAX_E_SCALE_J:
        reasons.append("E_scale_exceeds_ceiling")
    if m_equiv > MAX_M_EQUIV_KG:
        reasons.append("m_equiv_exceeds_ceiling")

    return {
        "L_m": float(l_m),
        "geometry": geom,
        "thickness_m": "NA" if thickness_m is None else float(thickness_m),
        "volume_m3": float(v_m3),
        # Legacy proxy fields retained for stable downstream parsing.
        "rho_e_j_per_m3": float(rho_e),
        "E_scale_j": float(e_scale),
        "m_equiv_kg": float(m_equiv),
        "m_over_earth": float(m_equiv / M_EARTH_KG),
        "m_over_jupiter": float(m_equiv / M_JUPITER_KG),
        "m_over_sun": float(m_equiv / M_SUN_KG),
        # Calibrated + explicit coupling diagnostics.
        "K_target_m2_inv": float(cal["K_target_m2_inv"]),
        "rho_e_dimensional_proxy_j_per_m3": float(rho_e_proxy),
        "rho_e_efe_calibrated_j_per_m3": float(rho_e_efe),
        "proxy_to_efe_ratio": float(cal["proxy_to_efe_ratio"]),
        "m_equiv_proxy_kg": float(m_equiv),
        "m_equiv_efe_kg": float(m_equiv_efe),
        "m_over_jupiter_proxy": float(m_equiv / M_JUPITER_KG),
        "m_over_jupiter_efe": float(m_equiv_efe / M_JUPITER_KG),
        "m_over_sun_proxy": float(m_equiv / M_SUN_KG),
        "m_over_sun_efe": float(m_equiv_efe / M_SUN_KG),
        "kappa_efe": float(cal["KAPPA_EFE"]),
        "inv_kappa_efe": float(cal["INV_KAPPA_EFE"]),
        "requires_negative_energy": "unknown",
        "curv_gate_pass": bool(len(reasons) == 0),
        "sanity_fail_reasons": reasons,
        "ceiling_rho_e_j_per_m3": float(MAX_RHO_E_J_PER_M3),
        "ceiling_E_scale_j": float(MAX_E_SCALE_J),
        "ceiling_m_equiv_kg": float(MAX_M_EQUIV_KG),
    }

