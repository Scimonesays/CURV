"""Run exotic stress-energy tripwire over CURV deflection residuals."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.exotic_tripwire import ExoticTripwireConfig, _parse_window, run_exotic_tripwire


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run CURV exotic stress-energy tripwire (proxy-only instrument; "
            "not a proof of NEC/WEC violation)."
        )
    )
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Project root path (default: repository root).",
    )
    parser.add_argument("--input-run-id", required=True, help="Existing run_id with deflection curve artifacts.")
    parser.add_argument("--b-window", default="100:1000", help="Scaling-fit window as lo:hi in b/M units.")
    parser.add_argument("--epsilon", type=float, default=1.0e-12, help="Numerical floor for normalization/log safety.")
    parser.add_argument("--wec-floor", type=float, default=0.0)
    parser.add_argument("--nec-floor", type=float, default=0.0)
    parser.add_argument("--rho-budget-max", type=float, default=1.0e-3)
    parser.add_argument("--scaling-limit-p-max", type=float, default=2.0)
    parser.add_argument("--score-w1", type=float, default=1.0)
    parser.add_argument("--score-w2", type=float, default=1.0)
    parser.add_argument("--score-w3", type=float, default=1.0)
    parser.add_argument("--notes", default="")
    parser.add_argument("--no-registry", action="store_true", help="Skip CSV/JSONL registry append.")
    parser.add_argument("--no-jsonl", action="store_true", help="Disable JSONL mirror append.")
    args = parser.parse_args()

    print("Loading artifacts for input_run_id...")
    config = ExoticTripwireConfig(
        input_run_id=str(args.input_run_id),
        b_window=_parse_window(str(args.b_window)),
        epsilon=float(args.epsilon),
        wec_floor=float(args.wec_floor),
        nec_floor=float(args.nec_floor),
        rho_budget_max=float(args.rho_budget_max),
        scaling_limit_p_max=float(args.scaling_limit_p_max),
        score_w1=float(args.score_w1),
        score_w2=float(args.score_w2),
        score_w3=float(args.score_w3),
        notes=str(args.notes),
        write_registry=not bool(args.no_registry),
        mirror_jsonl=not bool(args.no_jsonl),
    )
    summary = run_exotic_tripwire(project_root=Path(args.project_root), config=config)
    print("exotic_tripwire complete")
    print(f"run_id={summary['run_id']}")
    print(f"input_run_id={summary['input_run_id']}")
    print(f"tripwire_pass={summary['tripwire_pass']}")
    print(f"exoticity_score={summary['exoticity_score']:.6g}")
    print(f"wec_tripwire={summary['wec_tripwire']}")
    print(f"nec_tripwire={summary['nec_tripwire']}")
    print(f"scaling_tripwire={summary['scaling_tripwire']}")
    print(f"artifacts={';'.join(summary['artifacts'])}")


if __name__ == "__main__":
    main()

