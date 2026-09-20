"""Mass sensitivity sweep: 100 kg → 10,000 kg on edgecase profile.

Same profile, vary mass. CURV should show:
- power/energy gates get worse with mass
- some signature gates depend on speed, not mass (boom)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.results_registry import utc_now_iso
from src.ufo_observable_evaluator import evaluate_ufo_observables
from src.ufo_observables import profile_edgecase_hypersonic_no_boom


def main() -> None:
    behavior, claims = profile_edgecase_hypersonic_no_boom()

    masses = [100, 500, 1000, 2000, 5000, 10000]
    results = []

    for m in masses:
        mass_range = (m, m)
        r = evaluate_ufo_observables(
            behavior, claims, mass_range,
            policy="strict",
            enable_element_x=True,
            allow_speculative_override=True,
        )
        results.append({
            "mass_kg": m,
            "n_failed_gates": len(r["failed_gates"]),
            "verdict": r["verdict"],
            "required_power_W": r["physics"].get("required_power_W"),
            "rho_E_j_m3": r["physics"].get("rho_E_j_m3"),
            "dominant_failed_gate": r.get("dominant_failed_gate"),
        })
        print(f"mass={m} kg: n_failed={len(r['failed_gates'])}, P={r['physics'].get('required_power_W', 0):.2e} W")

    out_dir = Path(__file__).resolve().parent.parent / "results" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = utc_now_iso().replace(":", "").replace("-", "").split(".")[0]
    out_path = out_dir / f"mass_sweep_{ts}.json"
    out_path.write_text(json.dumps({"mass_sweep": results}, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"\noutput={out_path}")


if __name__ == "__main__":
    main()
