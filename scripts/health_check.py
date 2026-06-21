# -*- coding: utf-8 -*-
"""Project health check."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FILES = [
    "main.py",
    "config.py",
    "templates/dashboard.html",
    "templates/chartjs.min.js",
    "industry_chain/stock_pool.json",
    "data_sources/events/sample_events.json",
    "data_sources/_templates/research_report_event.template.json",
    "data_sources/_templates/xiaozuowen_event.template.json",
    "data_sources/_templates/announcement_event.template.json",
    "data_sources/_templates/verification_update.template.json",
    "data_sources/verifications/.gitkeep",
    "data/providers.py",
    "data/ai_event_adapter.py",
    "data/verification_loader.py",
    "graph/verification_engine.py",
    "scripts/check_data_sources.py",
    "scripts/check_announcement_provider.py",
    "scripts/check_verification_clusters.py",
    "scripts/check_search_config.py",
    "scripts/validate_verifications.py",
    "scripts/setup_search_secrets.ps1",
    "requirements.txt",
]
REQUIRED_MODULES = ["json", "pathlib", "requests"]


def main() -> int:
    issues = 0
    print("=" * 60)
    print("  AI Chain Review Health Check")
    print("=" * 60)
    if sys.version_info >= (3, 10):
        print(f"[OK] Python {sys.version.split()[0]}")
    else:
        print(f"[FAIL] Python version too low: {sys.version.split()[0]}")
        issues += 1

    for module in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
            print(f"[OK] module {module}")
        except Exception as exc:
            print(f"[FAIL] module {module}: {exc}")
            issues += 1

    for rel_path in REQUIRED_FILES:
        path = ROOT / rel_path
        if path.exists():
            print(f"[OK] file {rel_path}")
        else:
            print(f"[FAIL] missing {rel_path}")
            issues += 1

    try:
        pool = json.loads((ROOT / "industry_chain/stock_pool.json").read_text(encoding="utf-8"))
        print(f"[OK] stock pool segments: {len(pool)}")
    except Exception as exc:
        print(f"[FAIL] stock pool parse: {exc}")
        issues += 1

    print("=" * 60)
    if issues:
        print(f"[FAIL] {issues} issue(s)")
        return 1
    print("[OK] Health check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
