# -*- coding: utf-8 -*-
"""Check managed data-source fallback status."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.providers import DataSourceManager  # noqa: E402


def main() -> int:
    manager = DataSourceManager()
    data = manager.fetch_all_groups()
    print("=" * 60)
    print("  Data Source Check")
    print("=" * 60)
    for item in data.get("source_status", []):
        print(f"[{item['status'].upper()}] {item['provider']} {item.get('error', '')}")
    ok_count = sum(1 for item in data.get("source_status", []) if item.get("status") == "ok")
    if ok_count == 0:
        print("[FAIL] no data source available")
        return 1
    print(f"[OK] available providers: {ok_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
