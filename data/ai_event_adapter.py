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

STOCK_ALIASES = {
    "nvidia": "NVDA",
    "英伟达": "NVDA",
    "amd": "AMD",
    "tsmc": "TSM",
    "台积电": "TSM",
    "super micro": "SMCI",
    "supermicro": "SMCI",
    "arista": "ANET",
    "microsoft": "MSFT",
    "微软": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "gemini": "GOOGL",
    "adobe": "ADBE",
    "palantir": "PLTR",
    "tesla": "TSLA",
    "特斯拉": "TSLA",
    "apple": "AAPL",
    "苹果": "AAPL",
    "阿里": "9988",
    "阿里巴巴": "9988",
    "腾讯": "0700",
    "百度": "9888",
}


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
    lowered = text.lower()
    for alias, code in STOCK_ALIASES.items():
        if alias.lower() in lowered:
            codes.append(code)
    for segment in pool.values():
        for stock in segment.get("stocks", []):
            code = str(stock.get("code", ""))
            name = str(stock.get("name", ""))
            if code and code.lower() in lowered:
                codes.append(code)
            if name and name in text:
                codes.append(code)
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


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in ("", None):
        return []
    return [value]


def _clean_url(value: Any) -> str:
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    if isinstance(value, dict):
        for key in ("url", "link"):
            url = value.get(key)
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                return url
    return ""


def _first_url(*values: Any) -> str:
    for value in values:
        url = _clean_url(value)
        if url:
            return url
        for item in _as_list(value):
            url = _clean_url(item)
            if url:
                return url
    return ""


def _citation_text(citations: list[Any], limit: int = 4) -> str:
    parts: list[str] = []
    for citation in citations[:limit]:
        if isinstance(citation, str):
            parts.append(citation)
        elif isinstance(citation, dict):
            title = str(citation.get("title") or citation.get("name") or "").strip()
            url = str(citation.get("url") or citation.get("link") or "").strip()
            parts.append(" ".join(x for x in (title, url) if x))
    return "；".join(part for part in parts if part)


def _split_unstructured_search_item(item: dict[str, Any]) -> list[dict[str, Any]]:
    content = str(item.get("content") or item.get("summary") or "")
    if not content:
        return [item]
    blocks = [
        block.strip(" \t\r\n-*•0123456789.、")
        for block in content.split("\n")
        if block.strip(" \t\r\n-*•0123456789.、")
    ]
    candidates = [block for block in blocks if len(block) >= 20 and _is_ai_related(block)]
    if len(candidates) <= 1:
        return [item]
    citations = _as_list(item.get("citations"))
    search_results = _as_list(item.get("search_results"))
    split_items = []
    for index, block in enumerate(candidates[:8], start=1):
        split_items.append(
            {
                **item,
                "title": block[:60],
                "summary": block,
                "content": block,
                "url": _first_url(citations[index - 1:index], search_results[index - 1:index], item.get("url")),
                "citations": citations,
                "search_results": search_results,
                "structured": False,
            }
        )
    return split_items


def events_from_managed_sources(managed_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build candidate events from provider outputs."""
    events: list[dict[str, Any]] = []
    for group, source_result in managed_data.items():
        if group == "source_status" or not isinstance(source_result, dict):
            continue
        provider = source_result.get("provider", group)
        retrieved_at = source_result.get("retrieved_at", "")
        for item in _items_from_source_result(source_result):
            source_items = [item]
            if provider == "perplexity_search" and not item.get("structured"):
                source_items = _split_unstructured_search_item(item)
            for source_item in source_items:
                event = _event_from_item(provider, retrieved_at, source_item)
                if event:
                    events.append(event)
    return events


def _event_from_item(provider: str, retrieved_at: str, item: dict[str, Any]) -> dict[str, Any] | None:
    text = " ".join(
        str(item.get(key, ""))
        for key in ("title", "content", "summary", "impact_reason")
        if item.get(key)
    )
    if not text or not _is_ai_related(text):
        return None

    structured_segments = [str(x) for x in _as_list(item.get("chain_segments")) if str(x)]
    segments = structured_segments or _match_segments(text)
    if not segments:
        segments = ["cloud_models"]
    related_companies = " ".join(str(x) for x in _as_list(item.get("related_companies")))
    affected = _match_stocks(" ".join([text, related_companies]), segments)
    title = str(item.get("title") or text[:60])
    source_name = str(item.get("source") or provider)
    citations = _as_list(item.get("citations"))
    search_results = _as_list(item.get("search_results"))
    source_url = _first_url(item.get("url"), item.get("source_url"), citations, search_results)
    required_confirmation = str(item.get("required_confirmation") or "")
    if not required_confirmation:
        required_confirmation = "等待公司公告、交易所文件、财报、调研纪要或多家可靠来源交叉确认。"

    return {
        "id": _event_id(provider, title),
        "title": title,
        "source_type": "search_api" if "perplexity" in provider else "news",
        "source_name": source_name,
        "published_at": str(item.get("time") or item.get("published_at") or retrieved_at),
        "chain_segments": segments,
        "direction": str(item.get("direction") or _direction(text)),
        "weight": 3 if item.get("structured") else 2,
        "summary": str(item.get("summary") or text)[:800],
        "affected_stocks": affected,
        "bull_case": str(
            item.get("bull_case")
            or "若后续由公告、财报、订单或多家来源交叉验证，可提高对应产业链环节的跟踪优先级。"
        ),
        "bear_case": str(
            item.get("bear_case")
            or "该事件来自新闻/搜索/快讯，证据等级有限，不能单独改变核心业绩假设。"
        ),
        "required_confirmation": required_confirmation,
        "source_url": source_url,
        "citations": citations,
        "citation_note": _citation_text(citations),
        "search_results": search_results,
        "retrieved_at": retrieved_at,
        "provider": provider,
        "verification_status": "pending",
        "verification_note": "自动数据源生成，等待人工复核。",
    }
