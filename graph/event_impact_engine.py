# -*- coding: utf-8 -*-
"""AI产业链事件影响引擎。

The first version is deterministic: it maps structured events to chain
segments, stocks, evidence levels, and validation actions.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from config import (
    DEFAULT_EVENT_WEIGHT,
    IMPACT_DIRECTION_LABELS,
    IMPACT_DIRECTION_SCORES,
    INDUSTRY_CHAIN_DIR,
    SOURCE_LABELS,
    SOURCE_WEIGHTS,
)


def load_stock_pool(path: Path | None = None) -> dict[str, Any]:
    pool_path = path or INDUSTRY_CHAIN_DIR / "stock_pool.json"
    with pool_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _source_quality(source_type: str) -> dict[str, Any]:
    weight = SOURCE_WEIGHTS.get(source_type, SOURCE_WEIGHTS["manual"])
    if weight >= 0.9:
        tier = "P0"
        policy = "可在复核后影响核心假设"
    elif weight >= 0.7:
        tier = "P1"
        policy = "可提高跟踪优先级，需交叉验证"
    elif weight >= 0.4:
        tier = "P2"
        policy = "进入事件池，不单独改核心假设"
    else:
        tier = "P3"
        policy = "进入小作文/传闻验证池"
    return {
        "weight": weight,
        "tier": tier,
        "label": SOURCE_LABELS.get(source_type, source_type),
        "write_policy": policy,
    }


def _verification_status(event: dict[str, Any], source_type: str, tier: str) -> dict[str, str]:
    raw_status = str(event.get("verification_status") or "").strip().lower()
    allowed = {"pending", "confirmed", "rejected", "expired", "upgraded", "not_required"}
    if raw_status not in allowed:
        if tier in {"P2", "P3"} or source_type in {"rumor", "xiaozuowen", "search_api"}:
            raw_status = "pending"
        else:
            raw_status = "not_required"

    labels = {
        "pending": "待验证",
        "confirmed": "已交叉验证",
        "rejected": "已证伪",
        "expired": "已过期",
        "upgraded": "已升级为高等级证据",
        "not_required": "无需验证",
    }
    notes = {
        "pending": "不得改变核心假设，只进入事件/验证池。",
        "confirmed": "可提高跟踪优先级，但仍需区分是否达到高等级证据。",
        "rejected": "保留记录，后续不纳入正向/负向主判断。",
        "expired": "超过验证窗口后降权处理。",
        "upgraded": "需关联公告、交易所文件或财报后，才可进入核心假设复核。",
        "not_required": "高等级来源仍需人工复核原文。",
    }
    return {"status": raw_status, "label": labels[raw_status], "note": notes[raw_status]}


def _segment_lookup(stock_pool: dict[str, Any]) -> dict[str, set[str]]:
    lookup: dict[str, set[str]] = defaultdict(set)
    for segment_id, segment in stock_pool.items():
        for stock in segment.get("stocks", []):
            lookup[str(stock.get("code"))].add(segment_id)
    return lookup


def _stock_lookup(stock_pool: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for segment_id, segment in stock_pool.items():
        for stock in segment.get("stocks", []):
            item = dict(stock)
            item["segment_id"] = segment_id
            item["segment_label"] = segment.get("label", segment_id)
            lookup[str(stock.get("code"))] = item
    return lookup


def _event_stock_codes(event: dict[str, Any]) -> set[str]:
    return {str(code) for code in event.get("affected_stocks", []) if str(code)}


def _build_announcement_evidence(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if str(event.get("source_type")) not in {"company_announcement", "exchange_filing", "financial_report"}:
            continue
        for code in _event_stock_codes(event):
            evidence[code].append(
                {
                    "id": event.get("id", ""),
                    "title": event.get("title", ""),
                    "published_at": event.get("published_at", ""),
                    "source_type": event.get("source_type", ""),
                    "source_url": event.get("source_url", ""),
                    "announcement_type": event.get("announcement_type", ""),
                    "pdf_url": event.get("pdf_url", ""),
                    "detail_status": event.get("detail_status", ""),
                    "fact_markers": event.get("fact_markers", {}),
                    "review_checklist": event.get("review_checklist", []),
                }
            )
    return evidence


def _score_event(event: dict[str, Any]) -> dict[str, Any]:
    source_type = str(event.get("source_type", "manual"))
    quality = _source_quality(source_type)
    direction = str(event.get("direction", "unknown"))
    direction_score = IMPACT_DIRECTION_SCORES.get(direction, 0)
    event_weight = float(event.get("weight") or DEFAULT_EVENT_WEIGHT)
    score = direction_score * event_weight * float(quality["weight"])
    abs_score = abs(score)
    if abs_score >= 6:
        strength = "强"
    elif abs_score >= 2.5:
        strength = "中"
    elif abs_score > 0:
        strength = "弱"
    else:
        strength = "待验证"
    return {
        "score": round(score, 2),
        "strength": strength,
        "direction_label": IMPACT_DIRECTION_LABELS.get(direction, "待验证"),
        "source_quality": quality,
    }


def analyze_events(events: list[dict[str, Any]], stock_pool: dict[str, Any] | None = None) -> dict[str, Any]:
    pool = stock_pool or load_stock_pool()
    stock_lookup = _stock_lookup(pool)
    stock_segments = _segment_lookup(pool)
    announcement_evidence = _build_announcement_evidence(events)

    enriched_events: list[dict[str, Any]] = []
    segment_scores: dict[str, float] = defaultdict(float)
    stock_scores: dict[str, float] = defaultdict(float)
    verification_pool: list[dict[str, Any]] = []

    for event in events:
        scored = _score_event(event)
        source_type = str(event.get("source_type", "manual"))
        verification = _verification_status(event, source_type, str(scored["source_quality"]["tier"]))
        chain_segments = [str(x) for x in event.get("chain_segments", [])]
        affected_codes = [str(x) for x in event.get("affected_stocks", [])]

        for code in affected_codes:
            chain_segments.extend(stock_segments.get(code, set()))
        chain_segments = sorted(set(chain_segments))

        related_stocks = []
        for code in affected_codes:
            stock = stock_lookup.get(code, {"code": code, "name": code, "market": "", "role": ""})
            stock_item = dict(stock)
            stock_item["impact_score"] = scored["score"]
            stock_item["impact_label"] = scored["direction_label"]
            related_stocks.append(stock_item)
            stock_scores[code] += scored["score"]

        for segment_id in chain_segments:
            segment_scores[segment_id] += scored["score"]

        item = dict(event)
        item.update(scored)
        item["chain_segments"] = chain_segments
        item["chain_labels"] = [pool.get(s, {}).get("label", s) for s in chain_segments]
        item["related_stocks"] = related_stocks
        item["verification_status"] = verification["status"]
        item["verification_status_label"] = verification["label"]
        item["verification_policy_note"] = verification["note"]
        matched_evidence: list[dict[str, Any]] = []
        if source_type not in {"company_announcement", "exchange_filing", "financial_report"}:
            for code in affected_codes:
                matched_evidence.extend(announcement_evidence.get(code, []))
        if matched_evidence and item["verification_status"] == "pending":
            item["verification_status"] = "upgraded"
            item["verification_status_label"] = "已找到公告候选"
            item["verification_policy_note"] = "已命中同个股公告候选，需人工核对是否验证原事件。"
            item["verification_note"] = "已命中同个股公告候选，等待人工复核关联关系。"
        item["upgrade_evidence"] = matched_evidence[:5]
        item["model_update"] = scored["source_quality"]["tier"] == "P0"
        item["needs_verification"] = (
            scored["source_quality"]["tier"] in {"P2", "P3"}
            or source_type in {"rumor", "xiaozuowen", "search_api"}
            or verification["status"] in {"pending", "upgraded"}
        )
        if verification["status"] in {"rejected", "expired"}:
            item["needs_verification"] = False
        if item["needs_verification"]:
            verification_pool.append(item)
        enriched_events.append(item)

    segment_heat = []
    for segment_id, segment in pool.items():
        score = round(segment_scores.get(segment_id, 0.0), 2)
        if score > 0:
            direction = "偏利好"
        elif score < 0:
            direction = "偏利空"
        else:
            direction = "中性"
        segment_heat.append(
            {
                "segment_id": segment_id,
                "label": segment.get("label", segment_id),
                "score": score,
                "direction": direction,
                "description": segment.get("description", ""),
            }
        )

    stock_impact = []
    for code, score in stock_scores.items():
        stock = stock_lookup.get(code, {"code": code, "name": code, "market": "", "role": ""})
        if score > 0:
            direction = "利好"
        elif score < 0:
            direction = "利空"
        else:
            direction = "中性"
        stock_impact.append({**stock, "score": round(score, 2), "direction": direction})

    positive_count = sum(1 for e in enriched_events if e["score"] > 0)
    negative_count = sum(1 for e in enriched_events if e["score"] < 0)
    top_segments = sorted(segment_heat, key=lambda x: abs(x["score"]), reverse=True)[:3]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "event_count": len(enriched_events),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "verification_count": len(verification_pool),
            "top_segments": top_segments,
        },
        "events": sorted(enriched_events, key=lambda x: abs(float(x.get("score", 0))), reverse=True),
        "segment_heat": sorted(segment_heat, key=lambda x: abs(x["score"]), reverse=True),
        "stock_impact": sorted(stock_impact, key=lambda x: abs(x["score"]), reverse=True),
        "verification_pool": verification_pool,
        "stock_pool": pool,
    }
