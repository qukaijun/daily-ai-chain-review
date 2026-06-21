# -*- coding: utf-8 -*-
"""Deterministic TradingAgents-style multi-role analysis layer."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


HIGH_EVIDENCE_TYPES = {"exchange_filing", "company_announcement", "financial_report"}
LOW_EVIDENCE_TYPES = {"rumor", "xiaozuowen", "search_api"}


def _top_titles(events: list[dict[str, Any]], limit: int = 3) -> list[str]:
    return [str(event.get("title") or "") for event in events[:limit] if str(event.get("title") or "")]


def _top_segments(segment_heat: list[dict[str, Any]], limit: int = 3) -> list[str]:
    return [
        f"{segment.get('label', '')}({float(segment.get('score') or 0):+.2f})"
        for segment in segment_heat[:limit]
    ]


def _top_stocks(stock_impact: list[dict[str, Any]], limit: int = 5) -> list[str]:
    return [
        f"{stock.get('name', stock.get('code', ''))}({stock.get('code', '')},{float(stock.get('score') or 0):+.2f})"
        for stock in stock_impact[:limit]
    ]


def _source_type_counter(events: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(event.get("source_type") or "unknown") for event in events)


def _role_card(
    role_id: str,
    role_name: str,
    stance: str,
    observations: list[str],
    evidence: list[str],
    risks: list[str],
    next_checks: list[str],
) -> dict[str, Any]:
    return {
        "role_id": role_id,
        "role_name": role_name,
        "stance": stance,
        "observations": [item for item in observations if item][:5],
        "evidence": [item for item in evidence if item][:5],
        "risks": [item for item in risks if item][:5],
        "next_checks": [item for item in next_checks if item][:5],
    }


def _news_role(events: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    event_count = int(summary.get("event_count") or len(events))
    positive = int(summary.get("positive_count") or 0)
    negative = int(summary.get("negative_count") or 0)
    source_counts = _source_type_counter(events)
    stance = "事件偏正向" if positive > negative else "事件偏负向" if negative > positive else "事件方向分散"
    return _role_card(
        "news_event",
        "新闻/事件分析员",
        stance,
        [
            f"本轮共识别 {event_count} 条事件，利好 {positive} 条，利空 {negative} 条。",
            "来源结构：" + "、".join(f"{k}:{v}" for k, v in source_counts.most_common(5)),
        ],
        _top_titles(events),
        [
            "新闻、搜索和传闻只能作为事件线索，不能单独改变核心利润假设。",
            "事件数量少或来源集中时，主线判断容易受单一来源影响。",
        ],
        [
            "继续等待公告、财报、订单或多家可靠来源交叉验证。",
            "对重复标题或同源转载进行合并阅读。",
        ],
    )


def _announcement_role(events: list[dict[str, Any]], verification_analysis: dict[str, Any]) -> dict[str, Any]:
    high_events = [event for event in events if str(event.get("source_type")) in HIGH_EVIDENCE_TYPES]
    high_clusters = int(verification_analysis.get("high_evidence_cluster_count") or 0)
    duplicate_count = int(verification_analysis.get("duplicate_count") or 0)
    stance = "存在高等级证据候选" if high_events else "缺少高等级证据"
    return _role_card(
        "audit_evidence",
        "公告证据分析员",
        stance,
        [
            f"高等级来源事件 {len(high_events)} 条，高等级证据簇 {high_clusters} 个。",
            f"自动去重提示 {duplicate_count} 条疑似重复线索。",
        ],
        _top_titles(high_events),
        [
            "公告标题和摘要不等于投资结论，仍需核对原文、金额、期间和会计确认口径。",
            "公告候选只能提示复核方向，不能自动确认低证据事件。",
        ],
        [
            "优先复核命中低证据事件的公告原文和 PDF。",
            "确认公告是否与原事件同一事实、同一主体、同一期间。",
        ],
    )


def _chain_role(segment_heat: list[dict[str, Any]], stock_impact: list[dict[str, Any]]) -> dict[str, Any]:
    top_segments = _top_segments(segment_heat)
    top_stocks = _top_stocks(stock_impact)
    stance = "主线集中" if top_segments and abs(float(segment_heat[0].get("score") or 0)) >= 2 else "主线仍分散"
    return _role_card(
        "chain_transmission",
        "产业链传导分析员",
        stance,
        [
            "影响靠前环节：" + "、".join(top_segments),
            "个股影响靠前：" + "、".join(top_stocks),
        ],
        top_segments + top_stocks,
        [
            "产业链映射是研究线索，未必代表公司订单或利润已经兑现。",
            "同一事件可能重复映射到多只股票，需要避免把主题热度当成业绩确定性。",
        ],
        [
            "跟踪相关公司公告、订单披露、财报收入和毛利率变化。",
            "区分直接受益、间接受益和仅主题相关。",
        ],
    )


def _risk_role(events: list[dict[str, Any]], verification_pool: list[dict[str, Any]]) -> dict[str, Any]:
    low_events = [event for event in events if str(event.get("source_type")) in LOW_EVIDENCE_TYPES]
    rejected_or_expired = [
        event for event in events if str(event.get("verification_status")) in {"rejected", "expired"}
    ]
    stance = "验证压力较高" if verification_pool or low_events else "验证压力较低"
    return _role_card(
        "risk_falsification",
        "风险与证伪分析员",
        stance,
        [
            f"验证池事件 {len(verification_pool)} 条，低证据事件 {len(low_events)} 条。",
            f"已证伪或过期事件 {len(rejected_or_expired)} 条。",
        ],
        _top_titles(verification_pool),
        [
            "小作文、搜索摘要和单家研报容易造成方向误判。",
            "没有公告/财报验证时，不应把预期变化写入核心假设。",
        ],
        [
            "为验证池事件设置下一步证据来源和观察窗口。",
            "若后续无证据，应标记过期或降低跟踪优先级。",
        ],
    )


def _summary_role(
    summary: dict[str, Any],
    segment_heat: list[dict[str, Any]],
    verification_analysis: dict[str, Any],
) -> dict[str, Any]:
    top_segments = _top_segments(segment_heat)
    high_clusters = int(verification_analysis.get("high_evidence_cluster_count") or 0)
    stance = "可形成复盘主线" if top_segments else "暂无清晰主线"
    return _role_card(
        "review_synthesis",
        "复盘总结员",
        stance,
        [
            "今日主线：" + ("、".join(top_segments) if top_segments else "暂无"),
            f"验证池数量 {summary.get('verification_count', 0)}，高等级证据簇 {high_clusters}。",
        ],
        top_segments,
        [
            "复盘结论是研究辅助，不构成投资建议。",
            "核心假设更新仍需公告、交易所文件、财报等高等级证据复核。",
        ],
        [
            "优先处理高分自动验证簇和验证池事件。",
            "下一轮补充多角色判断中的缺失证据。",
        ],
    )


def build_multi_agent_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic role outputs from an existing analysis result."""
    events = list(analysis.get("events", []))
    summary = dict(analysis.get("summary", {}))
    segment_heat = list(analysis.get("segment_heat", []))
    stock_impact = list(analysis.get("stock_impact", []))
    verification_pool = list(analysis.get("verification_pool", []))
    verification_analysis = dict(analysis.get("verification_analysis", {}))

    roles = [
        _news_role(events, summary),
        _announcement_role(events, verification_analysis),
        _chain_role(segment_heat, stock_impact),
        _risk_role(events, verification_pool),
        _summary_role(summary, segment_heat, verification_analysis),
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "deterministic_local",
        "roles": roles,
        "consensus": {
            "stance": roles[-1]["stance"],
            "focus": roles[-1]["observations"][:2],
            "quality_gate": "仅作为研究复盘，不自动输出交易建议；核心假设更新必须等待高等级证据复核。",
        },
    }
