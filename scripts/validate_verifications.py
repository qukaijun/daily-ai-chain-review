# -*- coding: utf-8 -*-
"""Validate manual verification write-backs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import VERIFICATIONS_DIR  # noqa: E402
from data.event_loader import load_events  # noqa: E402
from data.verification_loader import VERIFICATION_STATUSES, load_verification_updates  # noqa: E402


EVIDENCE_REQUIRED_STATUSES = {"confirmed", "upgraded"}
MODEL_UPDATE_REVIEW_STATUSES = {"confirmed", "upgraded", "not_required"}
HIGH_EVIDENCE_TYPES = {"exchange_filing", "company_announcement", "financial_report"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("updates"), list):
        return [item for item in data["updates"] if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def validate_record(record: dict[str, Any], known_event_ids: set[str], label: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    event_id = str(record.get("event_id") or record.get("id") or "").strip()
    status = str(record.get("verification_status") or "").strip().lower()
    note = str(record.get("decision_note") or "").strip()
    evidence_title = str(record.get("evidence_title") or "").strip()
    evidence_source_type = str(record.get("evidence_source_type") or "").strip()
    evidence_url = str(record.get("evidence_url") or "").strip()
    evidence_pdf_url = str(record.get("evidence_pdf_url") or "").strip()
    evidence_event_id = str(record.get("evidence_event_id") or "").strip()

    if not event_id:
        errors.append(f"{label}: missing event_id")
    elif event_id not in known_event_ids:
        warnings.append(f"{label}: event_id {event_id} not found in local manual events; it may be source-derived")

    if status not in VERIFICATION_STATUSES:
        errors.append(f"{label}: unknown verification_status {status!r}")

    if not note or len(note) < 12:
        errors.append(f"{label}: decision_note is required and should explain the reviewed fact")

    has_evidence = bool(evidence_event_id or evidence_url or evidence_pdf_url)
    if status in EVIDENCE_REQUIRED_STATUSES and not evidence_title:
        errors.append(f"{label}: {status} requires evidence_title")
    if status in EVIDENCE_REQUIRED_STATUSES and not has_evidence:
        errors.append(f"{label}: {status} requires evidence_event_id, evidence_url, or evidence_pdf_url")
    if evidence_source_type and evidence_source_type not in HIGH_EVIDENCE_TYPES:
        errors.append(f"{label}: evidence_source_type must be a high-evidence source type")
    if evidence_url and not evidence_url.startswith(("http://", "https://")):
        errors.append(f"{label}: evidence_url must be http(s)")
    if evidence_pdf_url and not evidence_pdf_url.startswith(("http://", "https://")):
        errors.append(f"{label}: evidence_pdf_url must be http(s)")

    if record.get("model_update_candidate") is True:
        if status not in MODEL_UPDATE_REVIEW_STATUSES:
            errors.append(f"{label}: model_update_candidate=true requires confirmed/upgraded/not_required status")
        if not has_evidence:
            errors.append(f"{label}: model_update_candidate=true requires high-evidence linkage")
        if evidence_source_type not in HIGH_EVIDENCE_TYPES:
            errors.append(f"{label}: model_update_candidate=true requires P0 evidence_source_type")

    return errors, warnings


def main() -> int:
    issues: list[str] = []
    warnings: list[str] = []
    known_event_ids = {str(event.get("id") or "") for event in load_events()}
    VERIFICATIONS_DIR.mkdir(parents=True, exist_ok=True)

    for path in sorted(VERIFICATIONS_DIR.glob("*.json")):
        try:
            data = _read_json(path)
        except Exception as exc:
            issues.append(f"{path}: JSON parse failed: {exc}")
            continue
        records = _records(data)
        if not records:
            issues.append(f"{path}: no verification records")
            continue
        for index, record in enumerate(records, start=1):
            errors, record_warnings = validate_record(
                record,
                known_event_ids,
                f"{path.relative_to(ROOT).as_posix()}:{index}",
            )
            issues.extend(errors)
            warnings.extend(record_warnings)

    try:
        updates = load_verification_updates()
    except Exception as exc:
        issues.append(f"verification loader failed: {exc}")
        updates = {}

    print("=" * 60)
    print("  Verification Write-back Validation")
    print("=" * 60)
    print(f"[INFO] updates: {len(updates)}")
    for warning in warnings:
        print(f"[WARN] {warning}")
    if issues:
        print(f"[FAIL] {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("[OK] Verification write-backs valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
