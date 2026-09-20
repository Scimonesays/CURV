"""CI check: every artifact-producing script must write a registry row.

Invariant: scripts that produce results/artifacts/<run_id>/ outputs must append
to a registry (CSV + optional JSONL). This prevents new analysis tools from
becoming artifact-only islands.

Run: python scripts/check_registry_integrity.py
Exit 0: all checks pass. Exit 1: one or more violations.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Scripts that write per-run artifacts and must import append_csv_row.
SCRIPTS_REQUIRING_REGISTRY = [
    "run_bubble_experiment_analysis.py",
    "run_deflection_curve.py",
    "run_theory_deflection.py",
    "run_ufo_observable_eval.py",
    "run_ufo_behavior_eval.py",
    "run_breakthrough_ladder.py",
    "sweep_ppn_constraints.py",
    "sweep_yukawa_constraints.py",
]

# Modules invoked by entrypoint scripts; they do the actual registry append.
MODULES_REQUIRING_REGISTRY = [
    "source_plausibility",  # run_source_plausibility
    "trial_pipeline",       # run_experiment
    "exotic_tripwire",      # run_exotic_tripwire
]


def main() -> int:
    failed: list[str] = []

    for name in SCRIPTS_REQUIRING_REGISTRY:
        path = REPO_ROOT / "scripts" / name
        if not path.exists():
            failed.append(f"missing: scripts/{name}")
            continue
        text = path.read_text(encoding="utf-8")
        if "append_csv_row" not in text:
            failed.append(f"scripts/{name}: missing append_csv_row import/usage")

    for module in MODULES_REQUIRING_REGISTRY:
        path = REPO_ROOT / "src" / f"{module}.py"
        if not path.exists():
            failed.append(f"missing: src/{module}.py")
            continue
        text = path.read_text(encoding="utf-8")
        if "append_csv_row" not in text:
            failed.append(f"src/{module}.py: missing append_csv_row import/usage")

    if failed:
        print("registry integrity FAILED:")
        for msg in failed:
            print(f"  - {msg}")
        print("\nRule: every artifact-producing script must write a registry row.")
        return 1
    print("registry integrity: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
