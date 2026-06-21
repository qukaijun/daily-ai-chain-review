# -*- coding: utf-8 -*-
"""Load and apply manual verification write-backs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import VERIFICATIONS_DIR


VERIFICATION_STATUSES = {"pending", "confirmed", "rejected", "expired", "upgraded", "not_required"}
MODEL_UPDATE_REVIEW_STATUSES = {"confirmed", "upgraded", "not_required"}


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("updates"), list):
        return [item for item in data["updates"] if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    raise ValueError(f"Unsupported verification JSON shape: {path}")


def _normalize_update(item: dict[str, Any], path: Path, index: int) -> dict[str, Any]:
    event_id = str(item.get("event_id") or item.get("id") or "").strip()
    if not event_id:
        raise ValueError(f"{path}:{index}: missing event_id")

    status = str(item.get("verification_status") or "").strip().lower()
    if status not in VERIFICATION_STATUSES:
        raise ValueError(f"{path}:{index}: unknown verification_status {status!r}")

    update = dict(item)
    update["event_id"] = event_id
    update["verification_status"] = status
    update["_verification_file"] = path.as_posix()
    update["_verification_index"] = index
    update["model_update_candidate"] = bool(item.get("model_update_candidate") is True)
    return update


def load_verification_updates(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load manual verification updates keyed by event_id.

    If an event_id appears more than once, later files and later records win.
    This keeps the write-back layer append-friendly while preserving file source.
    """
    root = directory or VERIFICATIONS_DIR
    root.mkdir(parents=True, exist_ok=True)
    updates: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        for index, item in enumerate(_read_json(path), start=1):
            update = _normalize_update(item, path, index)
            updates[update["event_id"]] = update
    return updates


def _manual_evidence(update: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(update.get("evidence_event_id") or "").strip(),
        "source_type": str(update.get("evidence_source_type") or "").strip(),
        "title": str(update.get("evidence_title") or "").strip(),
        "source_url": str(update.get("evidence_url") or "").strip(),
        "pdf_url": str(update.get("evidence_pdf_url") or "").strip(),
    }


def apply_verification_updates(
    events: list[dict[str, Any]],
    updates: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply manual verification updates to loaded events."""
    if not updates:
        return events, {"update_count": 0, "applied_count": 0, "unmatched_event_ids": []}

    event_ids = {str(event.get("id") or "") for event in events}
    applied = 0
    for event in events:
        event_id = str(event.get("id") or "")
        update = updates.get(event_id)
        if not update:
            continue

        manual = {
            "event_id": event_id,
            "verification_status": update["verification_status"],
            "confirmed_by": str(update.get("confirmed_by") or "").strip(),
            "confirmed_at": str(update.get("confirmed_at") or "").strip(),
            "decision_note": str(update.get("decision_note") or "").strip(),
            "evidence": _manual_evidence(update),
            "model_update_candidate": bool(update.get("model_update_candidate") is True),
            "_verification_file": update.get("_verification_file", ""),
            "_verification_index": update.get("_verification_index", ""),
        }
        event["manual_verification"] = manual
        event["verification_status"] = update["verification_status"]
        if manual["decision_note"]:
            event["verification_note"] = manual["decision_note"]
        if manual["evidence"]["event_id"]:
            event["verification_evidence_event_id"] = manual["evidence"]["event_id"]
        if manual["evidence"]["title"]:
            event["verification_evidence_title"] = manual["evidence"]["title"]
        if manual["evidence"]["source_url"]:
            event["verification_evidence_url"] = manual["evidence"]["source_url"]
        if manual["evidence"]["pdf_url"]:
            event["verification_evidence_pdf_url"] = manual["evidence"]["pdf_url"]
        applied += 1

    unmatched = sorted(event_id for event_id in updates if event_id not in event_ids)
    return events, {
        "update_count": len(updates),
        "applied_count": applied,
        "unmatched_event_ids": unmatched,
    }
