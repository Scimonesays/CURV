"""Smoke test for strict append-only trial and campaign registries."""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.trial_pipeline import finalize_campaign, run_trial


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="curv_smoke_") as tmp:
        root = Path(tmp)
        batch_id = "smoke_campaign"
        row = run_trial(
            project_root=root,
            model_mode="smooth_gaussian",
            k=1.02,
            n=41,
            batch_id=batch_id,
            notes="smoke",
            mirror_jsonl=False,
        )

        trial_csv = root / "results" / "registry" / "results_registry.csv"
        assert trial_csv.exists(), "Missing trial registry csv"
        trial_rows = _read_rows(trial_csv)
        assert len(trial_rows) == 1, "Expected exactly one appended trial row"
        assert trial_rows[0]["run_id"] == row["run_id"], "Run id mismatch"
        for rel in trial_rows[0]["artifacts"].split(";"):
            assert (root / rel).exists(), f"Missing artifact path: {rel}"

        finalize_campaign(
            project_root=root,
            batch_id=batch_id,
            weak_k_definition="k<=1.05",
            model_mode="smooth_gaussian",
            notes="smoke",
            mirror_jsonl=False,
        )
        batch_csv = root / "results" / "registry" / "batch_registry.csv"
        assert batch_csv.exists(), "Missing batch registry csv"
        batch_rows = _read_rows(batch_csv)
        assert len(batch_rows) == 1, "Expected exactly one appended batch row"

    print("smoke_test_registry: PASS")


if __name__ == "__main__":
    main()

