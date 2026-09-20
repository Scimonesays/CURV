"""Session timeline: jobs + recent registry events."""

from __future__ import annotations

from typing import Any

from .jobs import list_jobs
from .registries import recent_registry_events


def get_timeline(limit: int = 30) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for job in list_jobs(limit=limit):
        ts = job.get("started_utc") or job.get("created_utc") or ""
        label = job.get("catalog_id") or job.get("script") or "job"
        events.append(
            {
                "source": "job",
                "job_id": job.get("job_id"),
                "run_id": job.get("run_id"),
                "timestamp_utc": ts,
                "label": label,
                "status": job.get("status") or "WARNING",
                "time_display": _hhmm(ts),
            }
        )
    for ev in recent_registry_events(limit=limit):
        events.append(
            {
                **ev,
                "time_display": _hhmm(ev.get("timestamp_utc") or ""),
            }
        )
    # Dedupe by run_id preferring job entries
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    events.sort(key=lambda e: e.get("timestamp_utc") or "", reverse=True)
    for e in events:
        key = str(e.get("run_id") or e.get("job_id") or e.get("timestamp_utc") + e.get("label", ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(e)
        if len(merged) >= limit:
            break
    return merged


def _hhmm(ts: str) -> str:
    # 2026-07-22T09:12:00Z or similar
    if "T" in ts and len(ts) >= 16:
        return ts[11:16]
    return ts[:5] if ts else "--:--"
