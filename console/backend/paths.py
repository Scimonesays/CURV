"""Path helpers and sandboxing for the instrument console."""

from __future__ import annotations

from pathlib import Path

# console/backend/paths.py → console/ → repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "results"
REGISTRY_DIR = RESULTS_DIR / "registry"
ARTIFACTS_DIR = RESULTS_DIR / "artifacts"
CERTIFICATION_DIR = RESULTS_DIR / "certification"
JOBS_DIR = RESULTS_DIR / "console_jobs"
SCRIPTS_DIR = REPO_ROOT / "scripts"
CERT_SCRIPT = REPO_ROOT / "certification" / "run_certification.py"

LANE_REGISTRIES: dict[str, list[str]] = {
    "theory": [
        "results_registry",
        "constraints_registry",
        "batch_registry",
    ],
    "claims": [
        "ufo_observable_registry",
        "ufo_behavior_registry",
        "breakthrough_ladder_registry",
    ],
    "exotic": [
        "results_registry",
        "exotic_tripwire_registry",
        "bubble_registry",
    ],
    "ufs": [
        "ufs_validation_registry",
    ],
    "certification": [],
}

ALL_REGISTRIES = [
    "results_registry",
    "constraints_registry",
    "batch_registry",
    "ufo_observable_registry",
    "ufo_behavior_registry",
    "breakthrough_ladder_registry",
    "exotic_tripwire_registry",
    "bubble_registry",
    "ufs_validation_registry",
]


def ensure_dirs() -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    CERTIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_under_results(rel_or_abs: str) -> Path:
    """Resolve a path and require it to stay under results/."""
    raw = Path(rel_or_abs)
    if not raw.is_absolute():
        candidate = (REPO_ROOT / raw).resolve()
    else:
        candidate = raw.resolve()
    results_root = RESULTS_DIR.resolve()
    try:
        candidate.relative_to(results_root)
    except ValueError as exc:
        raise PermissionError(f"Path escapes results/: {rel_or_abs}") from exc
    return candidate


def to_repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
