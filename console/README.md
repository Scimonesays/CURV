# CURV Instrument Console

Local laboratory instrument UI for NEWGR / CURV.

Opens on **evidence** (immutable registries → artifacts), not a dashboard.
Launches existing Python scripts; does not reimplement physics.

## Quickstart

### 1. API

From the repository root:

```powershell
pip install -r requirements.txt -r console/requirements.txt
python -m console
```

API listens on `http://127.0.0.1:8765`.

### 2. Frontend (dev)

```powershell
cd console/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` (Vite proxies `/api` to the backend).

### 3. Production-style (API serves built UI)

```powershell
cd console/frontend
npm install
npm run build
cd ../..
python -m console
```

Then open `http://127.0.0.1:8765/`.

## Instrument chrome

Always visible:

- **Policy** — STRICT | NORMAL | SANDBOX
- **SPECULATIVE** — YES | NO (amber when YES)
- **Git identity** — branch, commit, dirty/clean, date, Python
- **Promotion strip** — none → gate0 → candidate → strong_candidate → investigate → certified
- **Timeline** — recent jobs / registry events

Lane rail (text only): Theory · Claims · Exotic · UFS · Certification

## Views

| View | Role |
|------|------|
| Evidence | Registry table (default) |
| Run Detail | Gates, plots, metrics, raw JSON |
| Launch | Secondary — spawn catalogued scripts |
| Survivorship / Scorecard / Ladder / Atlas | Lane depth |
| UFS Workspace | Read-only UFS canonical frontier/gaps + readiness validation |
| Certification | C1–C6 matrix |

Right column: **Reproducibility Panel** + **Copy Reproduction Command** (exact argv from job history).

## UFS connection

The UFS lane reads a local Universal Frequency Spectrum checkout without modifying it.

Set:

```powershell
$env:UFS_REPO_PATH = "C:\\path\\to\\Universal-Frequency-Spectrum"
```

or clone UFS beside CURV. See [docs/UFS_INTEGRATION.md](../docs/UFS_INTEGRATION.md).

## Safety

- Registry rows are append-only (UI never edits them)
- Artifact paths are sandboxed under `results/`
- Jobs can be cancelled; argv is persisted under `results/console_jobs/`

## Tests

```powershell
pytest tests/test_console_api.py -q
```

## Live verification (optional)

```powershell
python console/seed_demo_fixtures.py
python console/verify_live.py
```

Screenshots and `report.json` land under `results/console_verify/` (gitignored with `results/`).
