# -*- coding: utf-8 -*-
"""Check announcement provider without generating a full report."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.providers import DataSourceManager  # noqa: E402


def main() -> int:
    manager = DataSourceManager()
    result = manager.fetch_provider("akshare_announcements")
    data = result.data if isinstance(result.data, dict) else {}
    items = data.get("items", []) if isinstance(data, dict) else []

    print("=" * 60)
    print("  Announcement Provider Check")
    print("=" * 60)
    print(f"[{result.status.upper()}] {result.provider} {result.error}")
    print(f"[INFO] items: {len(items)}")
    print(f"[INFO] lookback_days: {data.get('lookback_days', '')}")
    for item in items[:5]:
        print(f"- {item.get('code', '')} {item.get('name', '')}: {item.get('title', '')}")

    if result.status != "ok":
        print("[FAIL] announcement provider unavailable")
        return 1
    print("[OK] announcement provider available")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
