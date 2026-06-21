# -*- coding: utf-8 -*-
"""Take a screenshot for the latest generated report when Playwright is available."""

from __future__ import annotations

import http.server
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output_files"
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"


def find_latest_html() -> Path | None:
    files = sorted(OUTPUT_DIR.glob("report_full_*.html"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main() -> int:
    html_path = find_latest_html()
    if not html_path:
        print("[FAIL] No report_full_*.html found")
        return 1
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    server = http.server.HTTPServer(("127.0.0.1", 8091), http.server.SimpleHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    url = f"http://127.0.0.1:8091/output_files/{html_path.name}"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(1000)
            out = SCREENSHOT_DIR / "full_page.png"
            page.screenshot(path=str(out), full_page=True)
            browser.close()
        print(f"[OK] Screenshot saved: {out}")
        return 0
    except Exception as exc:
        print(f"[WARN] Screenshot skipped: {exc}")
        return 0
    finally:
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
