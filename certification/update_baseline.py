"""Manual baseline update utility (explicit invocation only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Update certification baseline from an explicit report path.")
    parser.add_argument("--report", required=True, help="Path to certification_report.json")
    parser.add_argument(
        "--output",
        default="certification/baselines/certified_baseline_v0.1.json",
        help="Baseline output path.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required safety flag to write baseline file.",
    )
    args = parser.parse_args()

    if not args.yes:
        raise SystemExit("Refusing to update baseline without --yes flag.")

    report_path = Path(args.report).resolve()
    out_path = Path(args.output).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))

    c1 = report.get("tests", {}).get("C1_reference_reproduction", {}).get("metrics", {})
    c2 = report.get("tests", {}).get("C2_resolution_convergence", {}).get("metrics", {})
    c3 = report.get("tests", {}).get("C3_gate_sensitivity", {}).get("metrics", {})

    baseline = {
        "baseline_version": "0.1",
        "expected": {
            "best_gamma_ppn": float(c1.get("best_gamma_ppn", 1.0)),
            "c3_monotonic_pruning": bool(
                float(c3.get("survivors_tighter", 0))
                <= float(c3.get("survivors_baseline", 0))
                <= float(c3.get("survivors_looser", 0))
            ),
        },
        "tolerances": {
            "best_gamma_ppn_abs": 0.02,
            "c2_h_pair_max_delta": float(max(0.02, c2.get("h_pair_max_delta", 0.02))),
        },
        "notes": "Baseline updated intentionally via certification/update_baseline.py",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(baseline, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Baseline updated: {out_path}")


if __name__ == "__main__":
    main()

