"""Smoke tests for CURV Instrument Console API (empty registries OK)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from console.backend.app import app
from console.backend.paths import resolve_under_results


client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["instrument"] == "CURV"


def test_identity():
    r = client.get("/api/identity")
    assert r.status_code == 200
    body = r.json()
    assert "branch" in body
    assert "commit" in body
    assert "dirty_label" in body
    assert "python" in body


def test_registries_empty_ok():
    r = client.get("/api/registries")
    assert r.status_code == 200
    assert "registries" in r.json()
    r2 = client.get("/api/registries/results_registry")
    assert r2.status_code == 200
    body = r2.json()
    assert body["name"] == "results_registry"
    assert "rows" in body


def test_timeline_and_catalog():
    assert client.get("/api/timeline").status_code == 200
    assert client.get("/api/catalog").status_code == 200
    assert client.get("/api/certification/latest").status_code == 200
    lanes = client.get("/api/lanes")
    assert lanes.status_code == 200
    assert any(item["id"] == "ufs" for item in lanes.json()["lanes"])


def test_ufs_overview_safe_when_repo_missing():
    r = client.get("/api/ufs")
    assert r.status_code == 200
    body = r.json()
    assert "connected" in body
    assert "frontier" in body
    assert "gaps" in body


def test_path_sandbox_blocks_escape():
    with pytest.raises(PermissionError):
        resolve_under_results("../README.md")
    with pytest.raises(PermissionError):
        resolve_under_results(str(ROOT / "README.md"))


def test_artifact_path_forbidden():
    r = client.get("/api/artifacts", params={"path": "../README.md"})
    assert r.status_code in (403, 404)


def test_jobs_list_empty_ok():
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert "jobs" in r.json()


def test_unknown_registry_404():
    r = client.get("/api/registries/not_a_real_registry")
    assert r.status_code == 404


def test_job_create_rejects_bad_policy():
    r = client.post(
        "/api/jobs",
        json={"catalog_id": "ufo_observable", "params": {}, "policy": "wild", "speculative": False},
    )
    assert r.status_code == 400


def test_job_create_unknown_catalog():
    r = client.post(
        "/api/jobs",
        json={"catalog_id": "nope", "params": {}, "policy": "strict", "speculative": False},
    )
    assert r.status_code == 404


def test_job_cancel_reaches_cancelled():
    created = client.post(
        "/api/jobs",
        json={"catalog_id": "instrument_hold", "params": {"seconds": 10.0}, "policy": "strict", "speculative": False},
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    deadline = time.time() + 3.0
    while time.time() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()
        if state["status"] in {"RUNNING", "CANCELLING"}:
            break
        time.sleep(0.05)

    cancelled = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200

    deadline = time.time() + 5.0
    final = None
    while time.time() < deadline:
        final = client.get(f"/api/jobs/{job_id}").json()
        if final["status"] == "CANCELLED":
            break
        time.sleep(0.05)

    assert final is not None
    assert final["status"] == "CANCELLED"
    assert final["cancel_requested"] is True
