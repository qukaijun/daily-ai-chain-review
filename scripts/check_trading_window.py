# -*- coding: utf-8 -*-
"""Check trading-day and post-market review window rules."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_calendar.trading_calendar import is_trading_day, review_window_status  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Check trading review window")
    parser.add_argument("--now", default="", help="Override current time: YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    now = None
    if args.now:
        now = datetime.strptime(args.now, "%Y-%m-%d %H:%M:%S")
    status = review_window_status(now)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0

    print("=" * 60)
    print("  Trading Window Check")
    print("=" * 60)
    for key, value in status.items():
        print(f"[INFO] {key}: {value}")
    if not is_trading_day(datetime.strptime(status["target_review_date"], "%Y-%m-%d").date()):
        print("[FAIL] target review date is not a trading day")
        return 1
    print("[OK] trading window rules available")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
