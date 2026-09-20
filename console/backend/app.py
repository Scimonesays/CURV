"""FastAPI entrypoint for the CURV Instrument Console."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .certification import get_certification, latest_certification, list_certifications
from .identity import get_identity
from .jobs import cancel_job, create_job, get_job, iter_log_sse, list_jobs
from .launch_catalog import list_catalog
from .paths import (
    ARTIFACTS_DIR,
    LANE_REGISTRIES,
    REPO_ROOT,
    ensure_dirs,
    resolve_under_results,
    to_repo_relative,
)
from .registries import list_registries, read_registry
from .runs import get_repro, get_run_detail, read_csv_preview
from .timeline import get_timeline
from .ufs import overview as get_ufs_overview, record as get_ufs_record

ensure_dirs()

app = FastAPI(title="CURV Instrument Console", version="0.1.0")
_default_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8765",
    "http://localhost:8765",
]
_extra_origins = [x.strip() for x in os.environ.get("CURV_CORS_ORIGINS", "").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys([*_default_origins, *_extra_origins])),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class JobCreate(BaseModel):
    catalog_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    policy: str = "strict"
    speculative: bool = False


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "instrument": "CURV"}


@app.get("/api/identity")
def identity() -> dict[str, Any]:
    return get_identity()


@app.get("/api/lanes")
def lanes() -> dict[str, Any]:
    return {
        "lanes": [
            {"id": "theory", "label": "Theory"},
            {"id": "claims", "label": "Claims"},
            {"id": "exotic", "label": "Exotic"},
            {"id": "ufs", "label": "UFS"},
            {"id": "certification", "label": "Certification"},
        ],
        "registries_by_lane": LANE_REGISTRIES,
    }


@app.get("/api/ufs")
def ufs_overview() -> dict[str, Any]:
    return get_ufs_overview()


@app.get("/api/ufs/records/{record_id}")
def ufs_record(record_id: str) -> dict[str, Any]:
    try:
        return get_ufs_record(record_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(503, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, f"Unknown UFS record: {record_id}") from exc


@app.get("/api/registries")
def registries() -> dict[str, Any]:
    return {"registries": list_registries()}


@app.get("/api/registries/{name}")
def registry_detail(
    name: str,
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    lane: str | None = None,
) -> dict[str, Any]:
    try:
        data = read_registry(name, limit=limit, offset=offset)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    if lane and lane in LANE_REGISTRIES and name not in LANE_REGISTRIES[lane]:
        # Still return but flag mismatch
        data["lane_mismatch"] = True
    return data


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    return get_run_detail(run_id)


@app.get("/api/runs/{run_id}/repro")
def run_repro(run_id: str) -> dict[str, Any]:
    return get_repro(run_id)


@app.get("/api/artifacts")
def artifact_file(path: str = Query(..., description="Repo-relative path under results/")) -> FileResponse:
    try:
        resolved = resolve_under_results(path)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(404, f"Not found: {path}")
    media = "application/octet-stream"
    suffix = resolved.suffix.lower()
    if suffix == ".png":
        media = "image/png"
    elif suffix == ".json":
        media = "application/json"
    elif suffix in {".csv", ".txt", ".log"}:
        media = "text/plain"
    return FileResponse(resolved, media_type=media, filename=resolved.name)


@app.get("/api/artifacts/csv")
def artifact_csv_preview(path: str, max_rows: int = Query(200, ge=1, le=2000)) -> dict[str, Any]:
    try:
        return read_csv_preview(path, max_rows=max_rows)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/artifacts/json")
def artifact_json(path: str) -> Any:
    try:
        resolved = resolve_under_results(path)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    if not resolved.exists():
        raise HTTPException(404, path)
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(400, f"Invalid JSON: {exc}") from exc


@app.get("/api/timeline")
def timeline(limit: int = Query(30, ge=1, le=100)) -> dict[str, Any]:
    return {"events": get_timeline(limit=limit)}


@app.get("/api/certification")
def certification_list() -> dict[str, Any]:
    return {"items": list_certifications(), "latest": latest_certification()}


@app.get("/api/certification/latest")
def certification_latest() -> dict[str, Any]:
    latest = latest_certification()
    if not latest:
        return {"latest": None}
    return {"latest": latest}


@app.get("/api/certification/{cert_id}")
def certification_detail(cert_id: str) -> dict[str, Any]:
    try:
        return get_certification(cert_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/catalog")
def catalog(lane: str | None = None) -> dict[str, Any]:
    return {"items": list_catalog(lane)}


@app.post("/api/jobs")
def jobs_create(body: JobCreate) -> dict[str, Any]:
    policy = body.policy.lower().strip()
    if policy not in ("strict", "normal", "sandbox"):
        raise HTTPException(400, "policy must be strict|normal|sandbox")
    try:
        job = create_job(
            body.catalog_id,
            body.params,
            policy=policy,
            speculative=body.speculative,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return job


@app.get("/api/jobs")
def jobs_list(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    return {"jobs": list_jobs(limit=limit)}


@app.get("/api/jobs/{job_id}")
def jobs_get(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.post("/api/jobs/{job_id}/cancel")
def jobs_cancel(job_id: str) -> dict[str, Any]:
    try:
        return cancel_job(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/jobs/{job_id}/logs")
def jobs_logs(job_id: str) -> StreamingResponse:
    if not get_job(job_id):
        raise HTTPException(404, "job not found")

    def gen():
        yield from iter_log_sse(job_id)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/survivorship/{run_id}")
def survivorship(run_id: str) -> dict[str, Any]:
    """Lane-depth helper: find survivor CSV + heatmap paths for a sweep run."""
    detail = get_run_detail(run_id)
    survivors = [f for f in detail["files"]["metrics"] if "survivor" in f["name"].lower()]
    heatmaps = [f for f in detail["files"]["plots"] if "heatmap" in f["name"].lower() or "survivor" in f["name"].lower()]
    preview = None
    if survivors:
        try:
            preview = read_csv_preview(survivors[0]["path"], max_rows=500)
        except Exception:
            preview = None
    return {
        "run_id": run_id,
        "survivors": survivors,
        "heatmaps": heatmaps,
        "preview": preview,
        "promotion": detail.get("promotion"),
        "status": detail.get("status"),
    }


@app.get("/api/artifacts/scan")
def scan_unindexed(limit: int = Query(40, ge=1, le=200)) -> dict[str, Any]:
    """List recent artifact dirs (includes unindexed phase-map runs)."""
    if not ARTIFACTS_DIR.exists():
        return {"dirs": []}
    dirs = sorted(
        [p for p in ARTIFACTS_DIR.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    out = []
    for d in dirs:
        from .registries import find_row_by_run_id

        found = find_row_by_run_id(d.name)
        out.append(
            {
                "run_id": d.name,
                "path": to_repo_relative(d),
                "indexed": found is not None,
                "registry": found["registry"] if found else None,
            }
        )
    return {"dirs": out}


# Optional: serve built frontend if present
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "console.backend.app:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )


if __name__ == "__main__":
    main()
