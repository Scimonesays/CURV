"""Manual certification baseline update utility (explicit invocation only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Update the CURV v0.2 certification baseline from an explicit report.")
    parser.add_argument("--report", required=True, help="Path to certification_report.json")
    parser.add_argument(
        "--output",
        default="certification/baselines/baseline_v0.2.json",
        help="Baseline output path.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required safety flag to write the baseline file.",
    )
    args = parser.parse_args()

    if not args.yes:
        raise SystemExit("Refusing to update baseline without --yes flag.")

    report_path = Path(args.report).resolve()
    out_path = Path(args.output).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("cert_version") != "0.2":
        raise SystemExit(f"Expected a v0.2 certification report, got {report.get('cert_version')!r}.")
    if report.get("overall_status") != "PASS":
        raise SystemExit("Refusing to derive a baseline from a failing certification report.")

    tests = report.get("tests", {})
    c1 = tests.get("C1_reference_reproduction", {}).get("metrics", {})
    c2 = tests.get("C2_resolution_convergence", {}).get("metrics", {})
    c3 = tests.get("C3_gate_sensitivity", {}).get("metrics", {})
    c4 = tests.get("C4_numerical_robustness", {}).get("metrics", {})

    baseline = {
        "baseline_version": "0.2",
        "scope": "CURV gravity-core computational certification invariants",
        "expected": {
            "best_gamma_ppn": float(c1["best_gamma_ppn"]),
            "c2_convergence_nonworsening": bool(c2["convergence_nonworsening"]),
            "c3_monotonic_pruning": bool(
                float(c3["survivors_tighter"])
                <= float(c3["survivors_baseline"])
                <= float(c3["survivors_looser"])
            ),
            "c3_actual_pruning": bool(c3["actual_pruning"]),
            "c4_within_mode_promotion_invariant": bool(c4["within_mode_promotion_invariant"]),
        },
        "tolerances": {
            "best_gamma_ppn_abs": float(c1.get("gamma_center_tol", 1.0e-12)),
            "c2_h_pair_max_delta": float(c2["max_pair_delta"]),
            "c4_within_mode_gamma_max_delta": float(c4["within_mode_gamma_tol"]),
        },
        "provenance": {
            "source_report": str(report_path),
            "source_git_commit": report.get("git_commit"),
        },
        "notes": "Baseline updated intentionally from a passing v0.2 certification report.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(baseline, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Baseline updated: {out_path}")


if __name__ == "__main__":
    main()
