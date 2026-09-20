"""Run detail resolution from registry + artifact folders."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from .paths import ARTIFACTS_DIR, JOBS_DIR, REPO_ROOT, to_repo_relative
from .registries import find_row_by_run_id


PROMOTION_ORDER = [
    "none",
    "gate0",
    "candidate",
    "strong_candidate",
    "investigate",
    "certified",
]


def _parse_artifacts_field(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in raw.split(";") if p.strip()]


def _scan_artifact_dir(run_id: str) -> Path | None:
    direct = ARTIFACTS_DIR / run_id
    if direct.is_dir():
        return direct
    # Prefix match (some run_ids are long suffixes)
    if not ARTIFACTS_DIR.exists():
        return None
    matches = sorted(
        [p for p in ARTIFACTS_DIR.iterdir() if p.is_dir() and (p.name == run_id or p.name.startswith(run_id))],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]
    # Also match dirs containing run_id token
    loose = sorted(
        [p for p in ARTIFACTS_DIR.iterdir() if p.is_dir() and run_id in p.name],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return loose[0] if loose else None


def _classify_files(root: Path) -> dict[str, list[dict[str, str]]]:
    plots: list[dict[str, str]] = []
    metrics: list[dict[str, str]] = []
    raw_files: list[dict[str, str]] = []
    other: list[dict[str, str]] = []
    if not root.exists():
        return {"plots": plots, "metrics": metrics, "raw": raw_files, "other": other}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = to_repo_relative(path)
        entry = {"path": rel, "name": path.name, "suffix": path.suffix.lower()}
        parent = path.parent.name.lower()
        if path.suffix.lower() == ".png" or parent == "plots":
            plots.append(entry)
        elif path.suffix.lower() == ".csv" or parent == "metrics":
            metrics.append(entry)
        elif path.suffix.lower() in {".json", ".txt", ".log"} or parent == "raw":
            raw_files.append(entry)
        else:
            other.append(entry)
    return {"plots": plots, "metrics": metrics, "raw": raw_files, "other": other}


def _load_json_safe(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_promotion(files: dict[str, list[dict[str, str]]], notes: str) -> dict[str, Any]:
    level = "none"
    reasons: list[str] = []
    checks: dict[str, Any] = {}
    for group in files.values():
        for f in group:
            if "promotion_eval" in f["name"] and f["suffix"] == ".json":
                data = _load_json_safe(REPO_ROOT / f["path"])
                if isinstance(data, dict):
                    level = str(data.get("promotion_level") or "none")
                    reasons = list(data.get("reasons") or [])
                    checks = {
                        "candidate_checks": data.get("candidate_checks"),
                        "investigate_checks": data.get("investigate_checks"),
                        "strong_checks": data.get("strong_checks"),
                    }
                break
    m = re.search(r"promote:([a-z_]+)", notes or "", re.I)
    if m and level == "none":
        level = m.group(1).lower()
    return {"level": level, "reasons": reasons, "checks": checks, "order": PROMOTION_ORDER}


def _extract_gates(files: dict[str, list[dict[str, str]]], row: dict[str, str] | None) -> list[dict[str, str]]:
    gates: list[dict[str, str]] = []
    # Prefer UFO / ladder JSON
    for group in files.values():
        for f in group:
            if f["suffix"] != ".json":
                continue
            data = _load_json_safe(REPO_ROOT / f["path"])
            if not isinstance(data, dict):
                continue
            if "failed_gates" in data:
                for g in data.get("failed_gates") or []:
                    if isinstance(g, dict):
                        gates.append(
                            {
                                "name": str(g.get("reason") or g.get("name") or "gate"),
                                "passed": "false" if g.get("passed") is False else str(g.get("passed", "false")),
                                "severity": str(g.get("severity") or ""),
                                "lane": str(g.get("lane") or ""),
                            }
                        )
                if "n_failed_gates" in data:
                    gates.insert(
                        0,
                        {
                            "name": "scorecard",
                            "passed": "true" if int(data.get("n_failed_gates") or 0) == 0 else "false",
                            "severity": "",
                            "lane": "",
                        },
                    )
                return gates
            if "steps" in data and "overall" in data:
                for s in data.get("steps") or []:
                    if isinstance(s, dict):
                        v = str(s.get("verdict") or "")
                        passed = "true" if "consistent" in v else "false"
                        gates.append(
                            {
                                "name": f"step_{s.get('step')}_{s.get('name')}",
                                "passed": passed,
                                "severity": "",
                                "lane": str(s.get("least_bad_lane") or ""),
                            }
                        )
                return gates
    if row:
        for key, label in (
            ("gateA_scaling_pass", "GateA scaling"),
            ("gateA_superposition_pass", "GateA superposition"),
            ("gateA_resolution_pass", "GateA resolution"),
            ("gateA_pass", "GateA"),
            ("tripwire_pass", "Exotic tripwire"),
            ("wec_tripwire", "WEC"),
            ("nec_tripwire", "NEC"),
            ("scaling_tripwire", "Scaling"),
        ):
            if key in row and row[key] not in ("", None):
                val = str(row[key]).strip().lower()
                passed = "true" if val in ("true", "1", "pass", "yes") else "false"
                if val in ("na", "n/a"):
                    passed = "na"
                gates.append({"name": label, "passed": passed, "severity": "", "lane": ""})
        notes = row.get("notes") or ""
        if "gate0:" in notes:
            gates.insert(
                0,
                {
                    "name": "Gate 0",
                    "passed": "false" if "fail" in notes.lower() else "true",
                    "severity": "hard",
                    "lane": "",
                },
            )
    return gates


def _summary_status(row: dict[str, str] | None, gates: list[dict[str, str]], promotion: dict[str, Any]) -> str:
    if row:
        verdict = (row.get("verdict") or "").lower()
        if "implausible" in verdict:
            return "FAIL"
        if "consistent" in verdict:
            return "PASS"
        for key in ("gateA_pass", "tripwire_pass", "all_pass"):
            val = (row.get(key) or "").strip().lower()
            if val in ("true", "1", "pass", "yes"):
                return "PASS"
            if val in ("false", "0", "fail", "no"):
                return "FAIL"
    hard_fails = [g for g in gates if g.get("passed") == "false"]
    if hard_fails:
        return "FAIL"
    if promotion.get("level") and promotion["level"] != "none":
        return "PASS"
    return "WARNING"


def get_run_detail(run_id: str) -> dict[str, Any]:
    found = find_row_by_run_id(run_id)
    row = found["row"] if found else None
    registry = found["registry"] if found else None
    artifact_paths = _parse_artifacts_field(row.get("artifacts") if row else None)
    art_dir = _scan_artifact_dir(run_id)
    files = _classify_files(art_dir) if art_dir else {"plots": [], "metrics": [], "raw": [], "other": []}

    # Merge registry-listed artifact paths not already scanned
    for ap in artifact_paths:
        p = REPO_ROOT / ap
        if not p.exists() or not p.is_file():
            continue
        entry = {"path": ap.replace("\\", "/"), "name": p.name, "suffix": p.suffix.lower()}
        bucket = "other"
        if p.suffix.lower() == ".png":
            bucket = "plots"
        elif p.suffix.lower() == ".csv":
            bucket = "metrics"
        elif p.suffix.lower() in {".json", ".txt", ".log"}:
            bucket = "raw"
        existing = {e["path"] for e in files[bucket]}
        if entry["path"] not in existing:
            files[bucket].append(entry)

    notes = (row or {}).get("notes") or ""
    promotion = _extract_promotion(files, notes)
    gates = _extract_gates(files, row)
    status = _summary_status(row, gates, promotion)

    primary_json = None
    for f in files["raw"]:
        if f["suffix"] == ".json":
            primary_json = _load_json_safe(REPO_ROOT / f["path"])
            if primary_json is not None:
                break

    return {
        "run_id": run_id,
        "registry": registry,
        "row": row,
        "indexed": found is not None,
        "artifact_dir": to_repo_relative(art_dir) if art_dir else None,
        "files": files,
        "gates": gates,
        "promotion": promotion,
        "status": status,
        "git_hash": (row or {}).get("git_hash"),
        "timestamp_utc": (row or {}).get("timestamp_utc"),
        "policy": (row or {}).get("policy"),
        "primary_json": primary_json,
        "artifact_paths": artifact_paths,
    }


def get_repro(run_id: str) -> dict[str, Any]:
    detail = get_run_detail(run_id)
    job = _load_job_for_run(run_id)
    files = detail["files"]
    counts = {
        "png": len(files["plots"]),
        "csv": len(files["metrics"]),
        "json": len([f for f in files["raw"] if f["suffix"] == ".json"]),
        "other": len(files["other"]) + len([f for f in files["raw"] if f["suffix"] != ".json"]),
    }
    argv = (job or {}).get("argv") or []
    cli = (job or {}).get("cli_command")
    if not cli and argv:
        cli = " ".join(_shell_quote(a) for a in argv)
    return {
        "run_id": run_id,
        "script": (job or {}).get("script"),
        "arguments": argv[1:] if len(argv) > 1 else argv,
        "argv": argv,
        "cli_command": cli,
        "git": (job or {}).get("git") or detail.get("git_hash"),
        "python": (job or {}).get("python"),
        "registry": detail.get("registry"),
        "artifact_counts": counts,
        "duration_s": (job or {}).get("duration_s"),
        "policy": (job or {}).get("policy") or detail.get("policy"),
        "speculative": (job or {}).get("speculative"),
        "from_job_history": job is not None,
        "row": detail.get("row"),
    }


def _shell_quote(s: str) -> str:
    if re.search(r'[\s"\'\\]', s):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def _load_job_for_run(run_id: str) -> dict[str, Any] | None:
    if not JOBS_DIR.exists():
        return None
    best: dict[str, Any] | None = None
    for path in sorted(JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("run_id") == run_id or run_id in str(data.get("run_id") or ""):
            return data
        # Fallback: match by log mentioning run_id
        if best is None and run_id in (data.get("log_tail") or ""):
            best = data
    return best


def read_csv_preview(rel_path: str, max_rows: int = 200) -> dict[str, Any]:
    from .paths import resolve_under_results

    path = resolve_under_results(rel_path)
    if not path.exists():
        raise FileNotFoundError(rel_path)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        rows = []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(row)
    return {"path": rel_path, "columns": columns, "rows": rows, "truncated": len(rows) >= max_rows}
