"""Certification report discovery under results/certification/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import CERTIFICATION_DIR, to_repo_relative


def list_certifications(limit: int = 20) -> list[dict[str, Any]]:
    if not CERTIFICATION_DIR.exists():
        return []
    dirs = sorted(
        [p for p in CERTIFICATION_DIR.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for d in dirs[:limit]:
        report_path = d / "certification_report.json"
        summary: dict[str, Any] = {"cert_id": d.name, "path": to_repo_relative(d)}
        if report_path.exists():
            try:
                data = json.loads(report_path.read_text(encoding="utf-8"))
                summary["overall_status"] = data.get("overall_status")
                summary["cert_version"] = data.get("cert_version")
                summary["failure_codes"] = data.get("failure_codes") or []
                summary["tests"] = data.get("tests") or {}
                summary["report_path"] = to_repo_relative(report_path)
            except Exception:
                summary["overall_status"] = "UNKNOWN"
        else:
            summary["overall_status"] = "UNKNOWN"
        out.append(summary)
    return out


def latest_certification() -> dict[str, Any] | None:
    items = list_certifications(limit=1)
    return items[0] if items else None


def get_certification(cert_id: str) -> dict[str, Any]:
    path = CERTIFICATION_DIR / cert_id
    if not path.is_dir():
        raise FileNotFoundError(cert_id)
    report_path = path / "certification_report.json"
    result: dict[str, Any] = {
        "cert_id": cert_id,
        "path": to_repo_relative(path),
        "files": [to_repo_relative(p) for p in sorted(path.rglob("*")) if p.is_file()][:200],
    }
    if report_path.exists():
        result["report"] = json.loads(report_path.read_text(encoding="utf-8"))
        result["report_path"] = to_repo_relative(report_path)
    return result
