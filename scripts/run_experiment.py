"""Run one CURV trial and append a strict per-run registry row."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.trial_pipeline import run_trial


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one CURV trial and append registry row.")
    parser.add_argument("--model-mode", default="smooth_gaussian", choices=["hard_blob", "smooth_gaussian"])
    parser.add_argument("--k", type=float, default=1.02)
    parser.add_argument("--sigma", type=float, default=None)
    parser.add_argument("--N", type=int, default=41)
    parser.add_argument("--connectivity", type=int, default=None)
    parser.add_argument("--field-exponent", type=float, default=2.0)
    parser.add_argument("--batch-id", default="NA")
    parser.add_argument("--notes", default="")
    parser.add_argument("--finalize-batch", default="false", choices=["false", "true"])
    args = parser.parse_args()

    row = run_trial(
        project_root=Path(__file__).resolve().parent.parent,
        model_mode=args.model_mode,
        k=args.k,
        sigma=args.sigma,
        n=args.N,
        connectivity=args.connectivity,
        field_exponent=args.field_exponent,
        batch_id=None if args.batch_id == "NA" else args.batch_id,
        notes=args.notes,
    )
    print(f"trial run_id={row['run_id']} appended to results/registry/results_registry.csv")


if __name__ == "__main__":
    main()

