"""Ablation study: toggle one claim at a time on edgecase profile.

Run edgecase profile but relax:
- sonic_boom_absent -> False (allow boom)
- thermal_signature_low -> False (allow moderate thermal)
- gravitational_lensing_reported -> False (disable lensing)
- transmedium -> False (disable transmedium)

Expectation: failed gates drop sharply; learn which claims do the most damage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.results_registry import utc_now_iso
from src.ufo_observable_evaluator import evaluate_ufo_observables
from src.ufo_observables import (
    profile_edgecase_hypersonic_no_boom,
    UFOObservableClaims,
    UFOBehaviorSpec,
)


def main() -> None:
    base_behavior, base_claims = profile_edgecase_hypersonic_no_boom()
    mass_range = (100.0, 10000.0)

    ablations = [
        ("baseline", base_behavior, base_claims),
        ("allow_sonic_boom", base_behavior, _with(base_claims, sonic_boom_absent=False)),
        ("allow_moderate_thermal", base_behavior, _with(base_claims, thermal_signature_low=False)),
        ("no_lensing_claim", base_behavior, _with(base_claims, gravitational_lensing_reported=False)),
        ("no_transmedium", _with_behavior(base_behavior, transmedium=False), _with(base_claims)),
    ]

    results = []
    for name, behavior, claims in ablations:
        r = evaluate_ufo_observables(
            behavior, claims, mass_range,
            policy="strict",
            enable_element_x=True,
            allow_speculative_override=True,
        )
        results.append({
            "ablation": name,
            "n_failed_gates": len(r["failed_gates"]),
            "verdict": r["verdict"],
            "dominant_failed_gate": r.get("dominant_failed_gate"),
            "categories": list(r.get("failed_gates_by_category", {}).keys()),
        })
        print(f"{name}: n_failed={len(r['failed_gates'])}, verdict={r['verdict']}")

    out_dir = Path(__file__).resolve().parent.parent / "results" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = utc_now_iso().replace(":", "").replace("-", "").split(".")[0]
    out_path = out_dir / f"ablation_study_{ts}.json"
    out_path.write_text(json.dumps({"ablations": results}, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"\noutput={out_path}")


def _with(c: UFOObservableClaims, **kw) -> UFOObservableClaims:
    d = c.to_dict()
    d.update(kw)
    return UFOObservableClaims.from_dict(d)


def _with_behavior(b: UFOBehaviorSpec, **kw) -> UFOBehaviorSpec:
    d = b.to_dict()
    d.update(kw)
    return UFOBehaviorSpec.from_dict(d)


if __name__ == "__main__":
    main()
