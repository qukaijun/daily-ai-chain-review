# -*- coding: utf-8 -*-
"""Automatic verification scoring and de-duplication helpers."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


HIGH_EVIDENCE_TYPES = {"exchange_filing", "company_announcement", "financial_report"}
LOW_EVIDENCE_TYPES = {"rumor", "xiaozuowen", "search_api"}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in ("", None):
        return []
    return [value]


def _date_token(value: Any) -> str:
    text = str(value or "")
    match = re.search(r"(20\d{2})[-/.年]?\s*(\d{1,2})[-/.月]?\s*(\d{1,2})", text)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _stock_codes(event: dict[str, Any]) -> set[str]:
    codes = {str(code) for code in _as_list(event.get("affected_stocks")) if str(code)}
    if not codes and isinstance(event.get("related_stocks"), list):
        for stock in event["related_stocks"]:
            if isinstance(stock, dict) and stock.get("code"):
                codes.add(str(stock.get("code")))
    return codes


def _segments(event: dict[str, Any]) -> set[str]:
    return {str(segment) for segment in _as_list(event.get("chain_segments")) if str(segment)}


def _providers(events: list[dict[str, Any]]) -> set[str]:
    values = set()
    for event in events:
        provider = str(event.get("provider") or event.get("source_name") or event.get("_source_file") or "")
        if provider:
            values.add(provider)
    return values


def _source_types(events: list[dict[str, Any]]) -> set[str]:
    return {str(event.get("source_type") or "") for event in events if str(event.get("source_type") or "")}


def _event_brief(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("id", ""),
        "title": event.get("title", ""),
        "source_type": event.get("source_type", ""),
        "provider": event.get("provider") or event.get("source_name") or event.get("_source_file") or "",
        "published_at": event.get("published_at", ""),
        "source_url": event.get("source_url", ""),
        "pdf_url": event.get("pdf_url", ""),
    }


def _cluster_key(event: dict[str, Any]) -> str:
    codes = sorted(_stock_codes(event))
    segments = sorted(_segments(event))
    date = _date_token(event.get("published_at")) or "unknown-date"
    if codes:
        return f"stock:{','.join(codes[:4])}|seg:{','.join(segments[:3])}|date:{date}"
    if segments:
        return f"seg:{','.join(segments[:3])}|date:{date}"
    return f"event:{event.get('id', '')}"


def _event_cluster_index(events: list[dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for event in events:
        index[str(event.get("id") or "")] = _cluster_key(event)
    return index


def _cluster_label(source_types: set[str], providers: set[str], has_high: bool, size: int) -> tuple[str, str]:
    if has_high:
        return "公告/高等级证据候选", "命中公告、交易所文件或财报，需人工核对是否验证低证据事件。"
    if len(providers) >= 2 or len(source_types) >= 2:
        return "多来源共振", "多来源提到同一股票/主题，可提高跟踪优先级，但仍不改核心假设。"
    if size >= 2:
        return "疑似重复线索", "同一来源或同类来源存在重复事件，建议合并阅读。"
    return "待验证", "暂无高等级证据或多来源交叉验证。"


def build_verification_clusters(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build event clusters and per-event automatic verification signals."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[_cluster_key(event)].append(event)

    clusters: list[dict[str, Any]] = []
    event_signals: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    high_evidence_cluster_count = 0

    for key, items in grouped.items():
        source_types = _source_types(items)
        providers = _providers(items)
        has_high = bool(source_types & HIGH_EVIDENCE_TYPES)
        has_low = bool(source_types & LOW_EVIDENCE_TYPES)
        directions = Counter(str(item.get("direction") or "unknown") for item in items)
        label, note = _cluster_label(source_types, providers, has_high, len(items))
        score = 10
        score += max(0, min(len(providers), 3) - 1) * 20
        score += max(0, min(len(source_types), 3) - 1) * 15
        if has_high:
            score += 45
            high_evidence_cluster_count += 1
        if has_low:
            score -= 10
        if len(items) > 1:
            duplicate_count += len(items) - 1
        score = max(0, min(score, 100))
        duplicate_event_ids = [str(item.get("id") or "") for item in items[1:]]
        primary = items[0]
        cluster = {
            "cluster_id": key,
            "event_count": len(items),
            "primary_event_id": primary.get("id", ""),
            "primary_title": primary.get("title", ""),
            "source_types": sorted(source_types),
            "providers": sorted(providers),
            "stock_codes": sorted(set().union(*[_stock_codes(item) for item in items])) if items else [],
            "chain_segments": sorted(set().union(*[_segments(item) for item in items])) if items else [],
            "direction_hint": directions.most_common(1)[0][0] if directions else "unknown",
            "verification_score": score,
            "verification_label": label,
            "verification_note": note,
            "has_high_evidence": has_high,
            "has_low_evidence": has_low,
            "duplicate_event_ids": duplicate_event_ids,
            "events": [_event_brief(item) for item in items[:8]],
        }
        clusters.append(cluster)
        for item in items:
            item_id = str(item.get("id") or "")
            if not item_id:
                continue
            event_signals[item_id] = {
                "cluster_id": key,
                "cluster_size": len(items),
                "verification_score": score,
                "verification_label": label,
                "verification_note": note,
                "duplicate_of": "" if item is primary else str(primary.get("id") or ""),
                "has_high_evidence": has_high,
                "has_low_evidence": has_low,
                "related_event_ids": [
                    str(other.get("id") or "")
                    for other in items
                    if str(other.get("id") or "") and other is not item
                ][:8],
            }

    clusters = sorted(
        clusters,
        key=lambda item: (int(item.get("verification_score", 0)), int(item.get("event_count", 0))),
        reverse=True,
    )
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cluster_count": len(clusters),
        "duplicate_count": duplicate_count,
        "high_evidence_cluster_count": high_evidence_cluster_count,
        "clusters": clusters,
        "event_signals": event_signals,
        "event_cluster_index": _event_cluster_index(events),
    }
