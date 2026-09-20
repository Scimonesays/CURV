"""Read append-only registry CSV/JSONL files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .paths import ALL_REGISTRIES, LANE_REGISTRIES, REGISTRY_DIR


def list_registries() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in ALL_REGISTRIES:
        csv_path = REGISTRY_DIR / f"{name}.csv"
        jsonl_path = REGISTRY_DIR / f"{name}.jsonl"
        n = 0
        if csv_path.exists():
            with csv_path.open(newline="", encoding="utf-8") as f:
                n = max(0, sum(1 for _ in f) - 1)
        out.append(
            {
                "name": name,
                "csv_exists": csv_path.exists(),
                "jsonl_exists": jsonl_path.exists(),
                "row_count": n,
                "lanes": [lane for lane, regs in LANE_REGISTRIES.items() if name in regs],
            }
        )
    return out


def read_registry(
    name: str,
    *,
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    if name not in ALL_REGISTRIES:
        raise KeyError(f"Unknown registry: {name}")
    csv_path = REGISTRY_DIR / f"{name}.csv"
    if not csv_path.exists():
        return {
            "name": name,
            "columns": [],
            "rows": [],
            "total": 0,
            "offset": offset,
            "limit": limit,
            "exists": False,
        }
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        all_rows = list(reader)
    # Newest first for instrument browsing
    all_rows.reverse()
    total = len(all_rows)
    slice_rows = all_rows[offset : offset + limit]
    return {
        "name": name,
        "columns": columns,
        "rows": slice_rows,
        "total": total,
        "offset": offset,
        "limit": limit,
        "exists": True,
    }


def find_row_by_run_id(run_id: str) -> dict[str, Any] | None:
    """Search all registries for a run_id (or batch_id) row."""
    for name in ALL_REGISTRIES:
        data = read_registry(name, limit=100_000, offset=0)
        for row in data["rows"]:
            if row.get("run_id") == run_id or row.get("batch_id") == run_id:
                return {"registry": name, "row": row}
    return None


def recent_registry_events(limit: int = 40) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for name in ALL_REGISTRIES:
        data = read_registry(name, limit=limit, offset=0)
        for row in data["rows"]:
            rid = row.get("run_id") or row.get("batch_id") or ""
            events.append(
                {
                    "source": "registry",
                    "registry": name,
                    "run_id": rid,
                    "timestamp_utc": row.get("timestamp_utc") or "",
                    "label": _event_label(name, row),
                    "status": _event_status(name, row),
                }
            )
    events.sort(key=lambda e: e.get("timestamp_utc") or "", reverse=True)
    return events[:limit]


def _event_label(registry: str, row: dict[str, str]) -> str:
    mode = row.get("model_mode") or row.get("profile") or row.get("instrument") or row.get("ufs_record_id") or registry
    return str(mode)


def _event_status(registry: str, row: dict[str, str]) -> str:
    if registry == "ufs_validation_registry":
        verdict = (row.get("readiness_verdict") or "").upper()
        if verdict == "READY_FOR_CONSTRAINT_DESIGN":
            return "PASS"
        if verdict in {"NEEDS_OPERATIONALIZATION", "HOLD_EVIDENCE", "INCONCLUSIVE"}:
            return "WARNING"
    if registry.startswith("ufo") or "verdict" in row:
        verdict = (row.get("verdict") or "").lower()
        if "implausible" in verdict:
            return "FAIL"
        if "speculative" in verdict:
            return "WARNING"
        if "consistent" in verdict:
            return "PASS"
    for key in ("gateA_pass", "tripwire_pass", "bubble_feasible", "all_pass"):
        val = (row.get(key) or "").strip().lower()
        if val in ("true", "1", "pass", "yes"):
            return "PASS"
        if val in ("false", "0", "fail", "no"):
            return "FAIL"
    notes = row.get("notes") or ""
    if "promote:" in notes:
        return "PASS"
    return "WARNING"
