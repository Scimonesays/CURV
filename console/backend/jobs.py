"""Job runner: subprocess wrap with argv persistence and SSE log streaming."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .identity import get_identity
from .launch_catalog import build_argv, list_catalog
from .paths import JOBS_DIR, REPO_ROOT, ensure_dirs

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _persist(job: dict[str, Any]) -> None:
    ensure_dirs()
    path = _job_path(job["job_id"])
    path.write_text(json.dumps(job, indent=2), encoding="utf-8")


def _shell_join(argv: list[str]) -> str:
    parts = []
    for a in argv:
        if re.search(r'[\s"\'\\]', a):
            parts.append('"' + a.replace('"', '\\"') + '"')
        else:
            parts.append(a)
    return " ".join(parts)


def create_job(
    catalog_id: str,
    params: dict[str, Any],
    *,
    policy: str,
    speculative: bool,
) -> dict[str, Any]:
    ensure_dirs()
    identity = get_identity()
    python_exe = sys.executable
    argv, script_rel, speculative_eff = build_argv(
        catalog_id,
        params,
        policy=policy,
        speculative=speculative,
        python_exe=python_exe,
    )
    job_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    job: dict[str, Any] = {
        "job_id": job_id,
        "catalog_id": catalog_id,
        "script": script_rel,
        "argv": argv,
        "cli_command": _shell_join(argv),
        "cwd": str(REPO_ROOT),
        "python": identity["python"],
        "policy": policy,
        "speculative": speculative_eff,
        "git": {
            "branch": identity["branch"],
            "commit": identity["commit"],
            "dirty_label": identity["dirty_label"],
        },
        "status": "queued",
        "created_utc": _utc_now(),
        "started_utc": None,
        "finished_utc": None,
        "duration_s": None,
        "exit_code": None,
        "run_id": None,
        "log_path": str(JOBS_DIR / f"{job_id}.log"),
        "log_tail": "",
        "error": None,
    }
    with _lock:
        _jobs[job_id] = job
    _persist(job)
    thread = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    thread.start()
    return job


def _run_job(job_id: str) -> None:
    with _lock:
        job = _jobs[job_id]
    log_path = Path(job["log_path"])
    job["status"] = "RUNNING"
    job["started_utc"] = _utc_now()
    _persist(job)
    t0 = time.time()
    run_id_re = re.compile(r"\brun_id[=:\s]+([A-Za-z0-9_.-]+)")
    try:
        with log_path.open("w", encoding="utf-8", errors="replace") as logf:
            proc = subprocess.Popen(
                job["argv"],
                cwd=job["cwd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            with _lock:
                job["pid"] = proc.pid
                _jobs[job_id] = job
            assert proc.stdout is not None
            for line in proc.stdout:
                logf.write(line)
                logf.flush()
                with _lock:
                    job["log_tail"] = (job.get("log_tail") or "")[-4000:] + line
                    m = run_id_re.search(line)
                    if m and not job.get("run_id"):
                        job["run_id"] = m.group(1)
                    _jobs[job_id] = job
            code = proc.wait()
        job["exit_code"] = code
        job["status"] = "PASS" if code == 0 else "FAIL"
    except Exception as exc:
        job["status"] = "FAIL"
        job["error"] = str(exc)
        job["exit_code"] = -1
        log_path.write_text((log_path.read_text(encoding="utf-8") if log_path.exists() else "") + f"\nERROR: {exc}\n", encoding="utf-8")
    finally:
        job["finished_utc"] = _utc_now()
        job["duration_s"] = round(time.time() - t0, 3)
        # Try to infer run_id from newest job-adjacent registry if missing
        if not job.get("run_id"):
            job["run_id"] = _infer_run_id_from_log(log_path)
        with _lock:
            _jobs[job_id] = job
        _persist(job)


def _infer_run_id_from_log(log_path: Path) -> str | None:
    if not log_path.exists():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r"\brun_id[=:\s]+([A-Za-z0-9_.-]+)", text)
    return matches[-1] if matches else None


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        if job_id in _jobs:
            return dict(_jobs[job_id])
    path = _job_path(job_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    ensure_dirs()
    jobs: list[dict[str, Any]] = []
    for path in sorted(JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        if len(jobs) >= limit:
            break
    return jobs


def cancel_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise KeyError(job_id)
    if job.get("status") != "RUNNING":
        return job
    pid = job.get("pid")
    if pid:
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], check=False, capture_output=True)
            else:
                import os
                import signal

                os.kill(pid, signal.SIGTERM)
        except Exception as exc:
            job["error"] = f"cancel failed: {exc}"
    job["status"] = "FAIL"
    job["error"] = (job.get("error") or "") + " cancelled"
    job["finished_utc"] = _utc_now()
    with _lock:
        _jobs[job_id] = job
    _persist(job)
    return job


def iter_log_sse(job_id: str) -> Iterator[str]:
    """Yield SSE data lines for job log until terminal status."""
    path = JOBS_DIR / f"{job_id}.log"
    offset = 0
    while True:
        job = get_job(job_id)
        if not job:
            yield f"data: {json.dumps({'error': 'not found'})}\n\n"
            break
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                chunk = f.read()
                offset = f.tell()
            if chunk:
                yield f"data: {json.dumps({'chunk': chunk, 'status': job.get('status')})}\n\n"
        status = job.get("status")
        if status in ("PASS", "FAIL") and (not path.exists() or offset >= path.stat().st_size):
            yield f"data: {json.dumps({'done': True, 'job': job})}\n\n"
            break
        time.sleep(0.4)
