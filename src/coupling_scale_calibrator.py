"""Single-source curvature-to-energy coupling calibration helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# Single-source physical constants (SI units).
C_LIGHT = 299_792_458.0
G_NEWTON = 6.67430e-11

# EFE coupling:
#   G_{mu nu} = (8*pi*G/c^4) T_{mu nu}
# For scalar yardsticks we use:
#   K ~= kappa * rho_E, so rho_E ~= (1/kappa) * K
KAPPA_EFE = (8.0 * math.pi * G_NEWTON) / (C_LIGHT**4)
INV_KAPPA_EFE = 1.0 / KAPPA_EFE


@dataclass(frozen=True)
class MitAnchor:
    """Optional reporting anchor from lecture-scale calibration."""

    rho_ref_j_m3: float
    K_ref_m2_inv: float

    @property
    def K_per_rho(self) -> float:
        return self.K_ref_m2_inv / self.rho_ref_j_m3


DEFAULT_MIT_ANCHOR = MitAnchor(
    rho_ref_j_m3=2.03e21,
    K_ref_m2_inv=4.22e-22,
)


def target_curvature_from_length(L_m: float) -> float:
    """Proxy target curvature scale K ~ 1/L^2."""
    L = float(L_m)
    if L <= 0.0:
        raise ValueError(f"L_m must be > 0, got {L_m}")
    return 1.0 / (L * L)


def rho_e_from_curvature_efe(K_m2_inv: float) -> float:
    """EFE-calibrated mapping rho_E ~= (c^4/(8*pi*G)) * K."""
    return float(K_m2_inv) * INV_KAPPA_EFE


def rho_e_dimensional_proxy_from_length(L_m: float) -> float:
    """Legacy dimensional proxy rho_E ~ c^4/(G*L^2), kept for continuity."""
    L = float(L_m)
    if L <= 0.0:
        raise ValueError(f"L_m must be > 0, got {L_m}")
    return (C_LIGHT**4) / (G_NEWTON * (L * L))


def rho_mass_equiv_kg_m3(rho_e_j_m3: float) -> float:
    """Mass-equivalent density rho = rho_E/c^2."""
    return float(rho_e_j_m3) / (C_LIGHT**2)


def calibrated_report_for_length(
    L_m: float,
    mit_anchor: MitAnchor | None = DEFAULT_MIT_ANCHOR,
) -> dict[str, Any]:
    """Return stable calibrated + legacy coupling diagnostics for a length scale."""
    K_target = target_curvature_from_length(L_m)
    rho_efe = rho_e_from_curvature_efe(K_target)
    rho_proxy = rho_e_dimensional_proxy_from_length(L_m)
    out: dict[str, Any] = {
        "L_m": float(L_m),
        "K_target_m2_inv": float(K_target),
        "rho_e_efe_calibrated_j_per_m3": float(rho_efe),
        "rho_e_dimensional_proxy_j_per_m3": float(rho_proxy),
        "proxy_to_efe_ratio": float(rho_proxy / rho_efe) if rho_efe != 0.0 else None,
        "mass_equiv_efe_kg_per_m3": float(rho_mass_equiv_kg_m3(rho_efe)),
        "mass_equiv_proxy_kg_per_m3": float(rho_mass_equiv_kg_m3(rho_proxy)),
        "KAPPA_EFE": float(KAPPA_EFE),
        "INV_KAPPA_EFE": float(INV_KAPPA_EFE),
    }
    if mit_anchor is not None:
        out.update(
            {
                "mit_anchor_rho_ref_j_m3": float(mit_anchor.rho_ref_j_m3),
                "mit_anchor_K_ref_m2_inv": float(mit_anchor.K_ref_m2_inv),
                "mit_anchor_K_per_rho": float(mit_anchor.K_per_rho),
                "efe_K_per_rho": float(KAPPA_EFE),
                "efe_to_mit_K_per_rho_ratio": (
                    float(KAPPA_EFE / mit_anchor.K_per_rho) if mit_anchor.K_per_rho != 0.0 else None
                ),
            }
        )
    return out


def format_calibrated_note(cal: dict[str, Any]) -> str:
    """Format one grep-friendly calibrated curvature note line."""
    return (
        "CURV_CAL: "
        f"L_m={float(cal['L_m']):.6g} "
        f"K={float(cal['K_target_m2_inv']):.3e} "
        f"rho_proxy={float(cal['rho_e_dimensional_proxy_j_per_m3']):.3e} "
        f"rho_efe={float(cal['rho_e_efe_calibrated_j_per_m3']):.3e} "
        f"ratio={float(cal['proxy_to_efe_ratio']):.3e} "
        f"m_proxy={float(cal['mass_equiv_proxy_kg_per_m3']):.3e} "
        f"m_efe={float(cal['mass_equiv_efe_kg_per_m3']):.3e}"
    )
