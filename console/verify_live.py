"""Playwright live verification for CURV Instrument Console."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "console_verify"
BASE = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8765"


def shot(page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


def api_json(page, path: str):
    return page.evaluate(
        """async (path) => {
          const r = await fetch(path);
          return { status: r.status, body: await r.json() };
        }""",
        path,
    )


def main() -> int:
    report: dict = {"checks": {}, "ok": True}
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_selector(".brand")

        # 1. Evidence first
        evidence_on = page.locator(".view-tabs button.on").inner_text().strip().lower()
        has_dashboard = page.locator("text=Dashboard").count() == 0
        has_kpi = page.locator("text=KPI").count() == 0
        report["checks"]["evidence_first"] = {
            "active_tab": evidence_on,
            "no_dashboard": has_dashboard,
            "no_kpi": has_kpi,
            "pass": evidence_on == "evidence" and has_dashboard and has_kpi,
        }
        shot(page, "01_evidence_first")

        # 2. Policy chrome visible
        policy_text = page.locator(".policy-bar").inner_text()
        report["checks"]["policy_chrome"] = {
            "text": policy_text.replace("\n", " "),
            "pass": all(x in policy_text.upper() for x in ["STRICT", "NORMAL", "SANDBOX", "SPECULATIVE"]),
        }

        # Toggle speculative and capture banner
        page.locator(".policy-bar .spec").click()
        page.wait_for_timeout(200)
        banner = page.locator(".banner-spec").count() > 0
        report["checks"]["speculative_banner"] = {"pass": banner}
        shot(page, "02_speculative_yes")
        page.locator(".policy-bar .spec").click()  # back to NO

        # 3. Registry → run → artifact → repro
        page.locator(".view-tabs button", has_text="Evidence").click()
        page.wait_for_timeout(300)
        page.locator("table.registry tbody tr").first.click()
        page.wait_for_selector(".main h2:text('Run')", timeout=5000)
        page.wait_for_timeout(400)
        run_visible = page.locator(".main h2", has_text="Run").count() > 0
        repro_visible = page.locator(".side button", has_text="Copy Reproduction Command").count() > 0
        has_cli = page.locator(".side .pre").count() > 0
        # open a raw json artifact if listed
        if page.locator(".file-list li").count() > 0:
            page.locator(".file-list li").first.click()
            page.wait_for_timeout(300)
        shot(page, "03_run_repro_path")
        report["checks"]["repro_path"] = {
            "run_detail": run_visible,
            "repro_button": repro_visible,
            "cli_present": has_cli,
            "pass": run_visible and repro_visible and has_cli,
        }

        # Hard fail path (Claims)
        page.locator(".lane-rail button", has_text="Claims").click()
        page.wait_for_timeout(600)
        if page.locator("table.registry tbody tr").count() > 0:
            page.locator("table.registry tbody tr").first.click()
            page.wait_for_timeout(500)
        shot(page, "04_hard_fail_claims")
        fail_status = page.locator(".main .status.FAIL").count() > 0
        report["checks"]["hard_fail_state"] = {"pass": fail_status or page.locator("text=physically_implausible").count() > 0}

        # Empty registry (Exotic tripwire default)
        page.locator(".lane-rail button", has_text="Exotic").click()
        page.wait_for_timeout(700)
        page.locator(".view-tabs button", has_text="Evidence").click()
        page.wait_for_timeout(400)
        empty = page.locator(".main .empty").count() > 0
        shot(page, "05_empty_registry")
        report["checks"]["empty_registry"] = {"pass": empty}

        # Speculative bubble via registry switch
        page.locator(".toolbar select").first.select_option("bubble_registry")
        page.wait_for_timeout(500)
        if page.locator("table.registry tbody tr").count() > 0:
            page.locator("table.registry tbody tr").first.click()
            page.wait_for_timeout(400)
        shot(page, "06_speculative_run")

        # Unindexed atlas
        page.locator(".view-tabs button", has_text="Atlas").click()
        page.wait_for_timeout(400)
        page.locator("button", has_text="Refresh").click()
        page.wait_for_timeout(500)
        unindexed = page.locator("text=unindexed").count() > 0
        if page.locator(".file-list li").count() > 0:
            # click unindexed if present
            for i in range(page.locator(".file-list li").count()):
                t = page.locator(".file-list li").nth(i).inner_text()
                if "unindexed" in t.lower():
                    page.locator(".file-list li").nth(i).click()
                    break
        page.wait_for_timeout(500)
        unindexed_banner = page.locator("text=UNINDEXED").count() > 0
        shot(page, "07_unindexed")
        report["checks"]["unindexed"] = {"pass": unindexed and unindexed_banner}

        # 4. Job launch / SSE / cancel
        page.locator(".lane-rail button", has_text="Theory").click()
        page.wait_for_timeout(400)
        page.locator(".view-tabs button", has_text="Launch").click()
        page.wait_for_timeout(400)
        # select instrument_hold
        page.locator(".form-grid select").first.select_option("instrument_hold")
        page.wait_for_timeout(200)
        page.locator(".form-grid input").first.fill("20")
        page.locator("button", has_text="Start").click()
        page.wait_for_timeout(1500)
        running = page.locator(".status.RUNNING").count() > 0 or "tick=" in page.locator(".pre").inner_text()
        shot(page, "08_job_running")
        # cancel
        if page.locator("button.danger", has_text="Cancel").count() > 0:
            page.locator("button.danger", has_text="Cancel").click()
            page.wait_for_timeout(1500)
        cancelled = page.locator(".status.FAIL").count() > 0
        shot(page, "09_job_cancelled")
        report["checks"]["jobs_sse_cancel"] = {
            "running_seen": running,
            "cancel_terminal": cancelled,
            "pass": running and cancelled,
        }

        # Passing quick job
        page.locator(".form-grid select").first.select_option("instrument_hold")
        page.locator(".form-grid input").first.fill("1.2")
        page.locator("button", has_text="Start").click()
        # wait for PASS
        ok_pass = False
        for _ in range(30):
            page.wait_for_timeout(400)
            txt = page.locator(".main").inner_text()
            if "PASS" in txt and "instrument_hold" in txt.lower() or page.locator(".status.PASS").count() > 0:
                # job status token near job id
                if page.locator(".toolbar .status.PASS").count() > 0 or "PASS" in page.locator(".toolbar").inner_text():
                    ok_pass = True
                    break
        shot(page, "10_job_pass")
        report["checks"]["job_pass"] = {"pass": ok_pass}

        # 5. Narrow layout — repro panel still present, no hide
        page.set_viewport_size({"width": 780, "height": 900})
        page.wait_for_timeout(400)
        page.locator(".view-tabs button", has_text="Evidence").click()
        page.wait_for_timeout(300)
        side_visible = page.locator(".side").is_visible()
        policy_visible = page.locator(".policy-bar").is_visible()
        shot(page, "11_narrow_layout")
        report["checks"]["narrow_layout"] = {
            "side_visible": side_visible,
            "policy_visible": policy_visible,
            "pass": side_visible and policy_visible,
        }

        # Wide again — evidence still default path after reload
        page.set_viewport_size({"width": 1440, "height": 900})
        page.reload(wait_until="networkidle")
        page.wait_for_selector(".brand")
        evidence_after = page.locator(".view-tabs button.on").inner_text().strip().lower()
        report["checks"]["reload_evidence"] = {"pass": evidence_after == "evidence"}
        shot(page, "12_reload_evidence")

        browser.close()

    report["ok"] = all(c.get("pass") for c in report["checks"].values())
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    # Ensure API healthy
    import urllib.request

    try:
        urllib.request.urlopen(API + "/api/health", timeout=3).read()
    except Exception as exc:
        print("API not up:", exc)
        sys.exit(2)
    raise SystemExit(main())
