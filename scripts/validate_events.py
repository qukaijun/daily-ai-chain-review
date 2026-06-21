# -*- coding: utf-8 -*-
"""Validate event inputs before report generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import IMPACT_DIRECTION_SCORES, SOURCE_WEIGHTS  # noqa: E402
from data.event_loader import EVENT_DIRS, load_events  # noqa: E402
from graph.event_impact_engine import load_stock_pool  # noqa: E402


REQUIRED_FIELDS = [
    "id",
    "title",
    "source_type",
    "source_name",
    "published_at",
    "chain_segments",
    "direction",
    "summary",
    "affected_stocks",
    "bull_case",
    "bear_case",
    "required_confirmation",
]
LOW_EVIDENCE_TYPES = {"rumor", "xiaozuowen"}
HIGH_EVIDENCE_TYPES = {"exchange_filing", "company_announcement", "financial_report"}


def _known_segments(pool: dict[str, Any]) -> set[str]:
    return set(pool.keys())


def _known_stocks(pool: dict[str, Any]) -> set[str]:
    stocks: set[str] = set()
    for segment in pool.values():
        for stock in segment.get("stocks", []):
            stocks.add(str(stock.get("code")))
    return stocks


def validate_event(event: dict[str, Any], pool: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    event_id = str(event.get("id", "<missing-id>"))
    for field in REQUIRED_FIELDS:
        if field not in event or event.get(field) in ("", None, []):
            errors.append(f"{event_id}: missing required field {field}")

    source_type = str(event.get("source_type", ""))
    if source_type and source_type not in SOURCE_WEIGHTS:
        errors.append(f"{event_id}: unknown source_type {source_type}")

    direction = str(event.get("direction", ""))
    if direction and direction not in IMPACT_DIRECTION_SCORES:
        errors.append(f"{event_id}: unknown direction {direction}")

    segments = [str(x) for x in event.get("chain_segments", [])]
    unknown_segments = sorted(set(segments) - _known_segments(pool))
    if unknown_segments:
        errors.append(f"{event_id}: unknown chain_segments {unknown_segments}")

    affected = [str(x) for x in event.get("affected_stocks", [])]
    unknown_stocks = sorted(set(affected) - _known_stocks(pool))
    if unknown_stocks:
        errors.append(f"{event_id}: unknown affected_stocks {unknown_stocks}")

    if source_type in LOW_EVIDENCE_TYPES:
        confirmation = str(event.get("required_confirmation", ""))
        if not confirmation or len(confirmation) < 12:
            errors.append(f"{event_id}: low-evidence event needs explicit required_confirmation")
        if event.get("model_update_candidate") is True:
            errors.append(f"{event_id}: low-evidence event cannot be model_update_candidate=true")

    if source_type not in HIGH_EVIDENCE_TYPES and event.get("model_update_candidate") is True:
        errors.append(f"{event_id}: only high-evidence sources can be model_update_candidate=true")

    return errors


def main() -> int:
    pool = load_stock_pool()
    issues: list[str] = []
    events = load_events()

    for directory in EVENT_DIRS:
        for path in sorted(directory.glob("*.json")):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                issues.append(f"{path}: JSON parse failed: {exc}")

    seen_ids: set[str] = set()
    for event in events:
        event_id = str(event.get("id", ""))
        if event_id in seen_ids:
            issues.append(f"{event_id}: duplicate id")
        seen_ids.add(event_id)
        issues.extend(validate_event(event, pool))

    print("=" * 60)
    print("  Event Input Validation")
    print("=" * 60)
    print(f"[INFO] events: {len(events)}")
    if issues:
        print(f"[FAIL] {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("[OK] Event inputs valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
