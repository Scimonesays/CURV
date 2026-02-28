"""Run mass-free energy source plausibility evaluation and append registry evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.source_plausibility import run_source_plausibility_trial


def main() -> None:
    parser = argparse.ArgumentParser(description="Run mass-free energy source plausibility evaluation.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path (default: repository root).",
    )
    parser.add_argument("--required-energy-j", type=float, default=None)
    parser.add_argument("--required-power-w", type=float, default=None)
    parser.add_argument("--mission-duration-s", type=float, default=None)
    parser.add_argument("--reference-mass-kg", type=float, default=1000.0)
    parser.add_argument("--radiator-temp-k", type=float, default=1200.0)
    parser.add_argument("--bubble-L-m", type=float, default=None)
    parser.add_argument("--bubble-geometry", choices=["sphere", "shell"], default="sphere")
    parser.add_argument("--bubble-thickness-m", type=float, default=None)
    parser.add_argument("--notes", default="")
    parser.add_argument("--no-jsonl", action="store_true")
    args = parser.parse_args()

    row = run_source_plausibility_trial(
        project_root=Path(args.project_root),
        required_energy_j=args.required_energy_j,
        required_power_w=args.required_power_w,
        mission_duration_s=args.mission_duration_s,
        reference_mass_kg=float(args.reference_mass_kg),
        radiator_temp_k=float(args.radiator_temp_k),
        bubble_l_m=args.bubble_L_m,
        bubble_geometry=str(args.bubble_geometry),
        bubble_thickness_m=args.bubble_thickness_m,
        notes=args.notes,
        mirror_jsonl=not bool(args.no_jsonl),
    )
    print("source_plausibility_trial complete")
    print(f"run_id={row['run_id']}")
    print(f"gateA_pass={row['gateA_pass']}")
    print(f"artifacts={row['artifacts']}")


if __name__ == "__main__":
    main()
