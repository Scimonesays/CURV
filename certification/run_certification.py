"""Run CURV certification suite (C1-C6) with deterministic reporting."""

from __future__ import annotations

import csv
import importlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CERT_VERSION = "0.1"
TEST_SEQUENCE = [
    ("C1_reference_reproduction", "certification.tests.C1_reference_reproduction"),
    ("C2_resolution_convergence", "certification.tests.C2_resolution_convergence"),
    ("C3_gate_sensitivity", "certification.tests.C3_gate_sensitivity"),
    ("C4_numerical_robustness", "certification.tests.C4_numerical_robustness"),
    ("C5_artifact_integrity", "certification.tests.C5_artifact_integrity"),
    ("C6_regression_lock", "certification.tests.C6_regression_lock"),
]

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def git_short_hash(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "nogit"
    except Exception:
        return "nogit"


def safe_cmd(cmd: list[str], cwd: Path | None = None, timeout_s: float | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        return int(proc.returncode), text.strip()
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout_s}s: {' '.join(cmd)}"
    except Exception as exc:
        return 1, str(exc)


def ensure_bootstrap(repo_root: Path) -> list[str]:
    """Best-effort bootstrap into the interpreter actually running certification."""
    logs: list[str] = [f"bootstrap_python={sys.executable}"]
    required_modules = ("numpy", "scipy", "matplotlib")
    missing: list[str] = []
    for module_name in required_modules:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(module_name)

    req = repo_root / "requirements.txt"
    if missing and req.exists():
        code, out = safe_cmd(
            [sys.executable, "-m", "pip", "install", "-r", str(req)],
            cwd=repo_root,
            timeout_s=120,
        )
        logs.append(f"pip_install_rc={code}")
        logs.append(f"pip_install_missing={','.join(missing)}")
        if out:
            logs.append(out.splitlines()[-1] if out.splitlines() else "")
    else:
        logs.append("pip_install_skipped=dependencies_available")
    return logs


def environment_snapshot() -> dict[str, Any]:
    code, freeze = safe_cmd([sys.executable, "-m", "pip", "freeze"])
    return {
        "timestamp": utc_now(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "os_name": os.name,
        "cwd": str(Path.cwd()),
        "pip_freeze_rc": code,
        "pip_freeze": [line.strip() for line in freeze.splitlines() if line.strip()],
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)
    ghash = git_short_hash(repo_root)
    cert_id = f"{ts_token()}_cert_v{CERT_VERSION}_{ghash}"
    out_dir = repo_root / "results" / "certification" / cert_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "plots").mkdir(parents=True, exist_ok=True)

    bootstrap_log = ensure_bootstrap(repo_root)
    env = environment_snapshot()
    (out_dir / "environment_snapshot.json").write_text(json.dumps(env, indent=2, ensure_ascii=True), encoding="utf-8")
    (out_dir / "git_commit_hash.txt").write_text(ghash + "\n", encoding="utf-8")

    # Load frozen configs.
    cfg_dir = repo_root / "certification" / "configs"
    cfg_map = {
        "C1_reference_reproduction": read_json(cfg_dir / "C1_reference_reproduction.json"),
        "C2_resolution_convergence": read_json(cfg_dir / "C2_resolution_convergence.json"),
        "C3_gate_sensitivity": read_json(cfg_dir / "C3_gate_sensitivity.json"),
        "C4_numerical_robustness": read_json(cfg_dir / "C4_numerical_robustness.json"),
    }
    config_used = {
        "cert_version": CERT_VERSION,
        "cert_id": cert_id,
        "bootstrap_log": bootstrap_log,
        "tests": cfg_map,
        "runtime": {
            "python_executable": sys.executable,
            "cwd": str(repo_root),
        },
    }
    (out_dir / "config_used.json").write_text(json.dumps(config_used, indent=2, ensure_ascii=True), encoding="utf-8")

    tests_report: dict[str, Any] = {}
    all_failure_codes: list[str] = []
    upstream_results: dict[str, Any] = {}

    for test_id, module_name in TEST_SEQUENCE:
        if test_id in cfg_map:
            test_cfg = dict(cfg_map[test_id])
        else:
            test_cfg = {}

        # Provide prior metrics to downstream checks.
        test_cfg["upstream_results"] = upstream_results
        if test_id == "C6_regression_lock":
            test_cfg["baseline_path"] = "certification/baselines/certified_baseline_v0.1.json"

        module = importlib.import_module(module_name)
        result = module.run(test_cfg, out_dir)
        if "failure_codes" not in result:
            result["failure_codes"] = []
        if "artifacts" not in result:
            result["artifacts"] = []
        tests_report[test_id] = {
            "status": result.get("status", "FAIL"),
            "details": result.get("details", ""),
            "metrics": result.get("metrics", {}),
            "artifacts": result.get("artifacts", []),
            "failure_codes": result.get("failure_codes", []),
        }
        for code in result.get("failure_codes", []):
            if code not in all_failure_codes:
                all_failure_codes.append(code)
        upstream_results[test_id] = tests_report[test_id]

    overall = "PASS" if all(test["status"] == "PASS" for test in tests_report.values()) else "FAIL"
    report = {
        "cert_version": CERT_VERSION,
        "timestamp": utc_now(),
        "git_commit": ghash,
        "tests": tests_report,
        "overall_status": overall,
        "failure_codes": all_failure_codes,
    }
    (out_dir / "certification_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    # Emit extra machine/human outputs required by spec.
    _write_metrics_csv(out_dir, tests_report)
    summary = {
        "cert_id": cert_id,
        "overall_status": overall,
        "failure_codes": all_failure_codes,
        "test_status": {k: v["status"] for k, v in tests_report.items()},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    _write_summary_txt(out_dir, cert_id, ghash, tests_report, overall, all_failure_codes)

    if overall == "PASS":
        print("CURV CERTIFICATION STATUS: PASS")
        return 0
    print("CURV CERTIFICATION STATUS: FAIL")
    print(f"Failure codes: {all_failure_codes}")
    for test_id, data in tests_report.items():
        if data.get("status") != "PASS":
            print(f"{test_id}: {data.get('details', '')}")
            print(json.dumps(data.get("metrics", {}), indent=2, sort_keys=True, ensure_ascii=True))
    return 1


def _write_metrics_csv(out_dir: Path, tests_report: dict[str, Any]) -> None:
    path = out_dir / "metrics.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["test_id", "status", "n_failure_codes", "details"])
        for test_id, data in tests_report.items():
            writer.writerow(
                [
                    test_id,
                    data.get("status", "FAIL"),
                    len(data.get("failure_codes", [])),
                    str(data.get("details", "")).replace("\n", " ").strip(),
                ]
            )


def _write_summary_txt(
    out_dir: Path,
    cert_id: str,
    ghash: str,
    tests_report: dict[str, Any],
    overall: str,
    failure_codes: list[str],
) -> None:
    lines = [
        "CURV Certification Summary",
        f"cert_id: {cert_id}",
        f"git_commit: {ghash}",
        f"overall_status: {overall}",
        "",
        "Tests:",
    ]
    for test_id, data in tests_report.items():
        line = f"- {test_id}: {data.get('status', 'FAIL')}"
        if data.get("failure_codes"):
            line += f" ({', '.join(data['failure_codes'])})"
        lines.append(line)
    lines.append("")
    lines.append(f"Failure codes: {failure_codes}")
    (out_dir / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(run())

