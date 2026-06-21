# -*- coding: utf-8 -*-
"""Validate bundled trading calendar files."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_calendar.trading_calendar import calendar_metadata, is_trading_day, parse_review_date  # noqa: E402

CALENDAR_DIR = ROOT / "market_calendar" / "calendars"


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def _validate_date_list(name: str, values: Any, year: int, issues: list[str]) -> list[str]:
    if not isinstance(values, list):
        issues.append(f"{name} must be a list")
        return []
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        try:
            day = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            issues.append(f"{name} has invalid date: {text}")
            continue
        if day.year != year:
            issues.append(f"{name} date outside year {year}: {text}")
        if text in seen:
            issues.append(f"{name} duplicate date: {text}")
        seen.add(text)
        result.append(text)
    if result != sorted(result):
        issues.append(f"{name} must be sorted ascending")
    return result


def validate_file(path: Path) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    data = _read_json(path)
    market = str(data.get("market") or "")
    year = int(data.get("year") or 0)
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    if market != "CN_A":
        issues.append("market must be CN_A")
    if year < 2000:
        issues.append("year is invalid")
    for field in ("publisher", "title", "published_at", "url"):
        if not source.get(field):
            issues.append(f"source.{field} is required")
    holidays = _validate_date_list("holidays", data.get("holidays"), year, issues)
    extra_days = _validate_date_list("extra_trading_days", data.get("extra_trading_days", []), year, issues)
    overlap = sorted(set(holidays) & set(extra_days))
    if overlap:
        issues.append("holidays and extra_trading_days overlap: " + ", ".join(overlap))
    for text in holidays:
        day = parse_review_date(text)
        if day.weekday() >= 5:
            issues.append(f"holiday should not include weekend-only date: {text}")
    return issues, data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate bundled CN A-share trading calendars")
    parser.add_argument("--date", default="", help="Check one date against the active calendar")
    parser.add_argument("--json", action="store_true", help="Print active calendar metadata as JSON")
    args = parser.parse_args()

    files = sorted(CALENDAR_DIR.glob("cn_a_*.json"))
    all_issues: list[str] = []
    print("=" * 60)
    print("  Trading Calendar Check")
    print("=" * 60)
    if not files:
        all_issues.append("no calendar files found")
    for path in files:
        issues, data = validate_file(path)
        year = data.get("year", "")
        print(f"[INFO] {path.name}: year={year} holidays={len(data.get('holidays', []))}")
        all_issues.extend([f"{path.name}: {issue}" for issue in issues])

    metadata = calendar_metadata()
    if args.json:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
    else:
        print(f"[INFO] active_source: {metadata.get('source_title', '')}")
        print(f"[INFO] active_years: {', '.join(str(item) for item in metadata.get('years', [])) or 'none'}")
        print(f"[INFO] active_holidays: {metadata.get('holiday_count', 0)}")

    if args.date:
        day = parse_review_date(args.date)
        print(f"[INFO] {day.strftime('%Y-%m-%d')} trading_day={is_trading_day(day)}")

    if all_issues:
        print(f"[FAIL] {len(all_issues)} issue(s)")
        for issue in all_issues:
            print(f"- {issue}")
        return 1
    print("[OK] trading calendars valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
