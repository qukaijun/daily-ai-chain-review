# -*- coding: utf-8 -*-
"""Load manually collected AI chain events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import ANNOUNCEMENTS_DIR, EVENTS_DIR, RUMORS_DIR, RESEARCH_REPORTS_DIR


EVENT_DIRS = [EVENTS_DIR, RESEARCH_REPORTS_DIR, RUMORS_DIR, ANNOUNCEMENTS_DIR]


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return [item for item in data["events"] if isinstance(item, dict)]
    raise ValueError(f"Unsupported event JSON shape: {path}")


def load_events() -> list[dict[str, Any]]:
    """Load events from data_sources directories."""
    events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for directory in EVENT_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
        for path in sorted(directory.glob("*.json")):
            for item in _read_json(path):
                event_id = str(item.get("id") or f"{path.name}:{len(events)}")
                if event_id in seen_ids:
                    continue
                item["_source_file"] = path.relative_to(path.parents[2]).as_posix()
                item.setdefault("source_bucket", directory.name)
                events.append(item)
                seen_ids.add(event_id)
    return events
