# -*- coding: utf-8 -*-
"""Convert managed data-source outputs into AI-chain event drafts."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from config import AI_KEYWORDS
from graph.event_impact_engine import load_stock_pool


SEGMENT_KEYWORDS = {
    "compute_chips": ["GPU", "芯片", "HBM", "先进封装", "半导体", "英伟达", "NVDA", "ASIC"],
    "ai_servers": ["服务器", "算力", "PCB", "电源", "整机", "GB200", "机柜"],
    "optical_modules": ["光模块", "CPO", "交换机", "光芯片", "数据中心网络", "800G", "1.6T"],
    "cooling_idc_power": ["液冷", "温控", "IDC", "数据中心", "电力", "储能"],
    "cloud_models": ["大模型", "云", "Agent", "推理", "训练", "模型"],
    "ai_applications": ["AI应用", "办公", "教育", "医疗", "金融AI", "软件", "SaaS"],
    "edge_ai_robotics": ["机器人", "端侧AI", "AI PC", "AI手机", "自动驾驶", "智能硬件"],
}

POSITIVE_WORDS = ["上修", "增长", "中标", "订单", "突破", "发布", "合作", "扩产", "涨", "创新高", "加速"]
NEGATIVE_WORDS = ["下修", "亏损", "监管", "延迟", "取消", "下跌", "风险", "处罚", "制裁", "降价"]


def _event_id(prefix: str, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{digest}"


def _match_segments(text: str) -> list[str]:
    matched = []
    for segment, keywords in SEGMENT_KEYWORDS.items():
        if any(keyword.lower() in text.lower() for keyword in keywords):
            matched.append(segment)
    return matched


def _match_stocks(text: str, segment_ids: list[str]) -> list[str]:
    pool = load_stock_pool()
    codes: list[str] = []
    for segment_id in segment_ids:
        for stock in pool.get(segment_id, {}).get("stocks", []):
            code = str(stock.get("code", ""))
            name = str(stock.get("name", ""))
            if name and name in text:
                codes.append(code)
    # If news only mentions a segment, attach top two stocks for mapping context.
    if not codes:
        for segment_id in segment_ids[:2]:
            for stock in pool.get(segment_id, {}).get("stocks", [])[:2]:
                codes.append(str(stock.get("code", "")))
    return sorted(set(code for code in codes if code))


def _direction(text: str) -> str:
    pos = sum(1 for word in POSITIVE_WORDS if word in text)
    neg = sum(1 for word in NEGATIVE_WORDS if word in text)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "unknown"


def _is_ai_related(text: str) -> bool:
    return any(keyword.lower() in text.lower() for keyword in AI_KEYWORDS)


def _items_from_source_result(source_result: dict[str, Any]) -> list[dict[str, Any]]:
    data = source_result.get("data", {})
    if isinstance(data, dict) and "items" in data:
        return data.get("items", [])
    if isinstance(data, dict) and "news" in data:
        return data.get("news", {}).get("items", [])
    return []


def events_from_managed_sources(managed_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build candidate events from provider outputs."""
    events: list[dict[str, Any]] = []
    for group, source_result in managed_data.items():
        if group == "source_status" or not isinstance(source_result, dict):
            continue
        provider = source_result.get("provider", group)
        retrieved_at = source_result.get("retrieved_at", "")
        for item in _items_from_source_result(source_result):
            text = " ".join(
                str(item.get(key, ""))
                for key in ("title", "content", "summary")
                if item.get(key)
            )
            if not text or not _is_ai_related(text):
                continue
            segments = _match_segments(text)
            if not segments:
                segments = ["cloud_models"]
            affected = _match_stocks(text, segments)
            title = str(item.get("title") or text[:60])
            source_name = str(item.get("source") or provider)
            events.append(
                {
                    "id": _event_id(provider, title),
                    "title": title,
                    "source_type": "search_api" if "perplexity" in provider else "news",
                    "source_name": source_name,
                    "published_at": str(item.get("time") or retrieved_at),
                    "chain_segments": segments,
                    "direction": _direction(text),
                    "weight": 2,
                    "summary": text[:500],
                    "affected_stocks": affected,
                    "bull_case": "若后续由公告、财报、订单或多家来源交叉验证，可提高对应产业链环节的跟踪优先级。",
                    "bear_case": "该事件来自新闻/搜索/快讯，证据等级有限，不能单独改变核心业绩假设。",
                    "required_confirmation": "等待公司公告、交易所文件、财报、调研纪要或多家可靠来源交叉确认。",
                    "source_url": str(item.get("url", "")),
                    "retrieved_at": retrieved_at,
                    "provider": provider,
                }
            )
    return events
