"""Validate README and docs mention only canonical registries.

Fails if README mentions a registry path that is not in the canonical list,
or if README omits a canonical registry. Keeps documentation in sync with
results_registry.py and REGISTRY_MAP.md.

Usage:
    python scripts/check_registry_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
REGISTRY_MAP = REPO_ROOT / "docs" / "REGISTRY_MAP.md"
REGISTRY_DIR = REPO_ROOT / "results" / "registry"

# Canonical registry base names (no .csv / .jsonl). Must match results_registry.py.
CANONICAL_REGISTRIES = frozenset({
    "results_registry",
    "constraints_registry",
    "ufo_observable_registry",
    "ufo_behavior_registry",
    "exotic_tripwire_registry",
    "bubble_registry",
    "breakthrough_ladder_registry",
    "batch_registry",
    "ufs_validation_registry",
})


def _extract_registry_names_from_text(text: str) -> set[str]:
    """Extract registry base names from text (e.g. results_registry.csv -> results_registry)."""
    found: set[str] = set()
    # Match patterns like results_registry, results_registry.csv, results_registry.jsonl
    for m in re.finditer(r"([a-z_]+_registry)(?:\.csv|\.jsonl)?", text, re.IGNORECASE):
        found.add(m.group(1).lower())
    return found


def main() -> int:
    errors: list[str] = []

    if not README.exists():
        errors.append(f"README not found: {README}")
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    readme_text = README.read_text(encoding="utf-8")
    readme_registries = _extract_registry_names_from_text(readme_text)

    # Fail if README mentions a registry not in canonical list
    unknown = readme_registries - CANONICAL_REGISTRIES
    if unknown:
        errors.append(
            f"README mentions registry path(s) not in canonical list: {sorted(unknown)}. "
            f"Canonical list: {sorted(CANONICAL_REGISTRIES)}"
        )

    # Fail if README omits a canonical registry (Registries table should list all)
    # Only check if README has a Registries table (contains at least one registry)
    if readme_registries and CANONICAL_REGISTRIES - readme_registries:
        missing = CANONICAL_REGISTRIES - readme_registries
        errors.append(
            f"README Registries section omits: {sorted(missing)}. "
            f"All canonical registries must be documented."
        )

    # Optionally verify REGISTRY_MAP.md and registry dir
    if REGISTRY_MAP.exists():
        map_text = REGISTRY_MAP.read_text(encoding="utf-8")
        map_registries = _extract_registry_names_from_text(map_text)
        unknown_in_map = map_registries - CANONICAL_REGISTRIES
        if unknown_in_map:
            errors.append(
                f"REGISTRY_MAP.md mentions registry path(s) not in canonical list: {sorted(unknown_in_map)}"
            )

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("OK: README and docs registry paths match canonical list.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
