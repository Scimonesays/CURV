"""C3: Gate sensitivity structure certification test."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import PASS, fail_result, guard_run, load_json, run_sweep


def _survivor_count(summary: dict[str, Any], threshold: float) -> int:
    key = f"{float(threshold):.6g}"
    return int(summary.get("survivors_by_thresh", {}).get(key, 0))


def run(test_config: dict, out_dir: Path) -> dict:
    def _impl() -> dict:
        base_cfg = dict(test_config["base_sweep"])
        tighter = float(test_config["tighter_threshold"])
        baseline = float(test_config["baseline_threshold"])
        looser = float(test_config["looser_threshold"])

        cfg_tighter = dict(base_cfg)
        cfg_tighter["wf_thresh_seq"] = [tighter]
        cfg_baseline = dict(base_cfg)
        cfg_baseline["wf_thresh_seq"] = [baseline]
        cfg_looser = dict(base_cfg)
        cfg_looser["wf_thresh_seq"] = [looser]

        r_tight = run_sweep(cfg_tighter, out_dir, "C3_tighter")
        r_base = run_sweep(cfg_baseline, out_dir, "C3_baseline")
        r_loose = run_sweep(cfg_looser, out_dir, "C3_looser")
        r_base_2 = run_sweep(cfg_baseline, out_dir, "C3_baseline_rerun")

        s_tight = load_json(r_tight["summary_json"])
        s_base = load_json(r_base["summary_json"])
        s_loose = load_json(r_loose["summary_json"])
        s_base_2 = load_json(r_base_2["summary_json"])

        n_tight = _survivor_count(s_tight, tighter)
        n_base = _survivor_count(s_base, baseline)
        n_loose = _survivor_count(s_loose, looser)
        n_base_2 = _survivor_count(s_base_2, baseline)

        monotonic = n_tight <= n_base <= n_loose
        deterministic = n_base == n_base_2

        max_jump = int(test_config.get("max_topology_jump", 200))
        smooth = abs(n_base - n_tight) <= max_jump and abs(n_loose - n_base) <= max_jump

        codes: list[str] = []
        if not monotonic:
            codes.append("C3_FAIL_CHAOTIC_PRUNING")
        if not deterministic:
            codes.append("C3_FAIL_NONDETERMINISTIC")
        if not smooth:
            codes.append("C3_FAIL_TOPOLOGY_INSTABILITY")

        status = PASS if not codes else "FAIL"
        details = "C3 gate sensitivity pruning is structured and deterministic." if not codes else "C3 gate sensitivity checks failed."
        return {
            "status": status,
            "details": details,
            "failure_codes": codes,
            "metrics": {
                "survivors_tighter": n_tight,
                "survivors_baseline": n_base,
                "survivors_looser": n_loose,
                "survivors_baseline_rerun": n_base_2,
                "thresholds": {
                    "tighter": tighter,
                    "baseline": baseline,
                    "looser": looser,
                },
                "commands_invoked": [r_tight["command"], r_base["command"], r_loose["command"], r_base_2["command"]],
            },
            "artifacts": [
                str(r_tight["summary_json"].relative_to(out_dir).as_posix()),
                str(r_base["summary_json"].relative_to(out_dir).as_posix()),
                str(r_loose["summary_json"].relative_to(out_dir).as_posix()),
            ],
        }

    return guard_run(_impl, "C3_FAIL_TOPOLOGY_INSTABILITY")

