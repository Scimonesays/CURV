"""Translate curvature targets into stress-energy requirements.

Uses EFE coupling: G_{μν} = κ T_{μν}, with κ = 8πG/c⁴.
For scalar order-of-magnitude: K ~ κ ρ_E, so ρ_E ~ (1/κ) K.

This module provides deterministic, reproducible energy budgets.
It does NOT assume exotic physics is real.
"""

from __future__ import annotations

import math
from typing import Any

from .coupling_scale_calibrator import C_LIGHT, G_NEWTON, INV_KAPPA_EFE, KAPPA_EFE

# κ = 8πG / c⁴
KAPPA = KAPPA_EFE


def compute_required_curvature(radius_m: float) -> float:
    """Target curvature scale from bubble radius.

    Dimensional: K ~ 1/R² for characteristic length R.

    Parameters
    ----------
    radius_m : float
        Characteristic radius of curvature region (m).

    Returns
    -------
    curvature_m2_inv : float
        Target curvature scale (m⁻²).
    """
    R = float(radius_m)
    if R <= 0.0:
        raise ValueError("radius_m must be positive")
    return 1.0 / (R * R)


def compute_energy_density(
    K_target_m2_inv: float,
    substrate_coupling_factor: float = 1.0,
) -> float:
    """Energy density required to produce target curvature.

    EFE: ρ_E ~ (1/κ) * K, with κ = 8πG/c⁴.

    Substrate coupling (α): if curvature couples to a deeper underlying field,
    the physical energy cost may be reduced. ρ_physical = ρ_GR × α.
    - α = 1: standard GR (no substrate effect)
    - α < 1: curvature easier (less physical energy needed)
    - α > 1: curvature harder (more physical energy needed)

    Parameters
    ----------
    K_target_m2_inv : float
        Target curvature (m⁻²).
    substrate_coupling_factor : float
        Substrate coupling α; default 1.0 (standard GR).

    Returns
    -------
    energy_density_j_m3 : float
        Required physical energy density (J/m³).
    """
    K = float(K_target_m2_inv)
    alpha = float(substrate_coupling_factor)
    rho_GR = K * INV_KAPPA_EFE
    return rho_GR * alpha


def compute_total_energy(rho_j_m3: float, volume_m3: float) -> float:
    """Total energy from density and volume."""
    return float(rho_j_m3) * float(volume_m3)


def compute_mass_equivalent(E_j: float) -> float:
    """Mass equivalent E/c²."""
    return float(E_j) / (C_LIGHT**2)


def curvature_energy_report(
    *,
    radius_m: float,
    volume_m3: float | None = None,
    substrate_coupling_factor: float = 1.0,
) -> dict[str, Any]:
    """Full energy requirement report from bubble radius.

    If volume_m3 is None, assumes spherical geometry: V = (4/3)πR³.

    Returns
    -------
    dict with curvature_m2, energy_density_j_m3, total_energy_j, mass_equivalent_kg
    """
    R = float(radius_m)
    if R <= 0.0:
        raise ValueError("radius_m must be positive")

    K = compute_required_curvature(R)
    rho = compute_energy_density(K, substrate_coupling_factor=substrate_coupling_factor)

    if volume_m3 is not None:
        V = float(volume_m3)
        if V <= 0.0:
            raise ValueError("volume_m3 must be positive")
    else:
        V = (4.0 / 3.0) * math.pi * (R**3)

    E = compute_total_energy(rho, V)
    m = compute_mass_equivalent(E)

    return {
        "curvature_m2_inv": K,
        "radius_m": R,
        "volume_m3": V,
        "energy_density_j_m3": rho,
        "total_energy_j": E,
        "mass_equivalent_kg": m,
        "kappa": KAPPA,
        "substrate_coupling_factor": substrate_coupling_factor,
    }
