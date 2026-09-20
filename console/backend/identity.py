"""Git / Python / date identity for permanent chrome."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from .paths import REPO_ROOT


def _git(*args: str) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or None
    except Exception:
        return None


def get_identity() -> dict[str, Any]:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    commit = _git("rev-parse", "--short", "HEAD") or "nogit"
    dirty_raw = _git("status", "--porcelain")
    dirty = bool(dirty_raw) if dirty_raw is not None else False
    if dirty_raw is None and commit == "nogit":
        dirty_label = "unknown"
    else:
        dirty_label = "dirty" if dirty else "clean"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "branch": branch,
        "commit": commit,
        "dirty": dirty,
        "dirty_label": dirty_label,
        "date": date,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "repo_root": str(REPO_ROOT),
    }
