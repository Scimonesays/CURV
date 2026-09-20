"""Console-facing read-only Universal Frequency Spectrum helpers."""

from __future__ import annotations

from typing import Any

from src.ufs_bridge import find_record, get_overview


def overview() -> dict[str, Any]:
    return get_overview()


def record(record_id: str) -> dict[str, Any]:
    return find_record(record_id)
