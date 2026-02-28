"""Finalize one CURV campaign and append strict batch verdict row."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.trial_pipeline import finalize_campaign


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize batch and append batch_registry row.")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--weak-k", required=True, help='Examples: "k<=0.15", "k<=1.05"')
    parser.add_argument("--model-mode", default="smooth_gaussian")
    parser.add_argument("--artifacts", default="", help="Semicolon-separated relative artifact paths.")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    artifact_list = [x for x in args.artifacts.split(";") if x]
    row = finalize_campaign(
        project_root=Path(__file__).resolve().parent.parent,
        batch_id=args.batch_id,
        weak_k_definition=args.weak_k,
        model_mode=args.model_mode,
        artifacts=artifact_list,
        notes=args.notes,
    )
    print(f"batch {row['batch_id']} appended to results/registry/batch_registry.csv")


if __name__ == "__main__":
    main()

