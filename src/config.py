"""Central configuration for New GR toy simulations."""

from __future__ import annotations

from pathlib import Path

SEED = 12345
MASS_M = 1.0

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "outputs"

# Phase 1 defaults
GR_R_MAX = 300.0
GR_STEP = 0.002
GR_B_VALUES = [6.0, 7.5, 9.0, 10.5, 12.0, 14.0, 16.0, 18.0, 20.0]

# Phase 2 defaults
GRAPH_N = 41
GRAPH_W0 = 1.0
GRAPH_EPS = 1.0e-6
GRAPH_K_VALUES = [1.0, 1.5, 2.0, 3.0]
GRAPH_RADIUS = 6.0
GRAPH_RAY_COUNT = 17
GRAPH_TIE_LAMBDA = 1.0e-3
GRAPH_BACKGROUND_NOISE = 0.02
GRAPH_SOFT_BETA = 6.0
GRAPH_WEAK_K_VALUES = [1.01, 1.02, 1.05]
GRAPH_SUPERPOSE_K = 1.02
GRAPH_RESOLUTION_N_BASE = 41
GRAPH_MODE_DEFAULT = "hard_blob"
GRAPH_CONNECTIVITY_DEFAULT = 4
GRAPH_SMOOTH_SIGMA_FACTOR = 0.085

