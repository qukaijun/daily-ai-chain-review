# -*- coding: utf-8 -*-
"""TradingAgents-style multi-role analysis layer."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

import requests

from config import LLM_CONFIG


HIGH_EVIDENCE_TYPES = {"exchange_filing", "company_announcement", "financial_report"}
LOW_EVIDENCE_TYPES = {"rumor", "xiaozuowen", "search_api"}
ROLE_IDS = {
    "news_event",
    "audit_evidence",
    "chain_transmission",
    "risk_falsification",
    "review_synthesis",
}


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


def _status(
    enabled: bool,
    status: str,
    *,
    mode: str = "deterministic_local",
    error: str = "",
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "status": status,
        "mode": mode,
        "provider": LLM_CONFIG.get("provider", ""),
        "model": LLM_CONFIG.get("deep_model", ""),
        "error": error[:240],
    }


def _clip(value: Any, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _analysis_brief(analysis: dict[str, Any]) -> dict[str, Any]:
    events = []
    for event in analysis.get("events", [])[:12]:
        if not isinstance(event, dict):
            continue
        stocks = []
        for stock in event.get("related_stocks", [])[:6]:
            if isinstance(stock, dict):
                stocks.append(f"{stock.get('name', '')}({stock.get('code', '')})")
        events.append(
            {
                "title": _clip(event.get("title"), 180),
                "source_type": event.get("source_type", ""),
                "source_name": event.get("source_name", ""),
                "provider": event.get("provider") or event.get("_source_file") or "",
                "published_at": event.get("published_at", ""),
                "direction": event.get("direction_label", event.get("direction", "")),
                "score": event.get("score", 0),
                "verification_status": event.get("verification_status_label", event.get("verification_status", "")),
                "chain_labels": event.get("chain_labels", [])[:5],
                "related_stocks": stocks,
                "summary": _clip(event.get("summary"), 220),
                "required_confirmation": _clip(event.get("required_confirmation"), 180),
            }
        )
    return {
        "generated_at": analysis.get("generated_at", ""),
        "summary": analysis.get("summary", {}),
        "events": events,
        "segment_heat": analysis.get("segment_heat", [])[:7],
        "stock_impact": analysis.get("stock_impact", [])[:12],
        "verification_pool": [
            {
                "title": _clip(item.get("title"), 180),
                "status": item.get("verification_status_label", item.get("verification_status", "")),
                "required_confirmation": _clip(item.get("required_confirmation"), 180),
            }
            for item in analysis.get("verification_pool", [])[:8]
            if isinstance(item, dict)
        ],
        "verification_clusters": analysis.get("verification_analysis", {}).get("clusters", [])[:8],
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    content = text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)
    try:
        data = json.loads(content)
    except Exception:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    return data


def _clean_list(value: Any, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clip(item, 180) for item in value if _clip(item, 180)][:limit]


def _clean_deep_roles(data: dict[str, Any]) -> list[dict[str, Any]]:
    roles = data.get("roles", [])
    if not isinstance(roles, list):
        raise ValueError("missing roles array")
    cleaned = []
    seen: set[str] = set()
    for role in roles:
        if not isinstance(role, dict):
            continue
        role_id = str(role.get("role_id") or "").strip()
        if role_id not in ROLE_IDS or role_id in seen:
            continue
        seen.add(role_id)
        cleaned.append(
            _role_card(
                role_id,
                _clip(role.get("role_name"), 40),
                _clip(role.get("stance"), 80),
                _clean_list(role.get("observations")),
                _clean_list(role.get("evidence")),
                _clean_list(role.get("risks")),
                _clean_list(role.get("next_checks")),
            )
        )
    if len(cleaned) < 5:
        raise ValueError(f"expected 5 role outputs, got {len(cleaned)}")
    order = ["news_event", "audit_evidence", "chain_transmission", "risk_falsification", "review_synthesis"]
    return sorted(cleaned, key=lambda item: order.index(item["role_id"]))


def _clean_consensus(data: dict[str, Any]) -> dict[str, Any]:
    consensus = data.get("consensus", {})
    if not isinstance(consensus, dict):
        consensus = {}
    return {
        "stance": _clip(consensus.get("stance"), 80) or "深度复盘已生成",
        "focus": _clean_list(consensus.get("focus"), 4),
        "quality_gate": (
            _clip(consensus.get("quality_gate"), 180)
            or "仅作为研究复盘，不自动输出交易建议；核心假设更新必须等待高等级证据复核。"
        ),
    }


def _llm_payload(analysis: dict[str, Any], local_result: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "你是AI产业链复盘系统的多角色研究协作层。"
        "你只能基于用户提供的结构化事件、公告候选、验证池和产业链映射做研究复盘。"
        "不得给出买入、卖出、仓位、目标价等交易指令；不得把新闻、研报、传闻当作已确认事实。"
        "输出必须是 JSON 对象。"
    )
    user_prompt = {
        "task": "生成 TradingAgents 式深度多角色复盘。",
        "required_json_shape": {
            "roles": [
                {
                    "role_id": "news_event|audit_evidence|chain_transmission|risk_falsification|review_synthesis",
                    "role_name": "中文角色名",
                    "stance": "一句话立场",
                    "observations": ["最多5条观察"],
                    "evidence": ["最多5条依据"],
                    "risks": ["最多5条风险"],
                    "next_checks": ["最多5条下一步验证"],
                }
            ],
            "consensus": {
                "stance": "一句话共识",
                "focus": ["最多4条重点"],
                "quality_gate": "证据和合规边界",
            },
        },
        "required_role_ids": sorted(ROLE_IDS),
        "local_deterministic_result": local_result,
        "analysis_brief": _analysis_brief(analysis),
    }
    return {
        "model": LLM_CONFIG.get("deep_model", ""),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "max_tokens": int(LLM_CONFIG.get("max_tokens") or 2200),
    }


def _call_deep_agent(analysis: dict[str, Any], local_result: dict[str, Any]) -> dict[str, Any]:
    api_key = str(LLM_CONFIG.get("api_key") or "")
    if not api_key:
        raise RuntimeError("DAA_LLM_API_KEY not configured")
    base_url = str(LLM_CONFIG.get("base_url") or "").rstrip("/")
    if not base_url:
        raise RuntimeError("DAA_LLM_BASE_URL not configured")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=_llm_payload(analysis, local_result),
        timeout=int(LLM_CONFIG.get("timeout_seconds") or 45),
    )
    if response.status_code >= 400:
        raise RuntimeError(f"LLM HTTP {response.status_code}: {response.text[:160]}")
    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"LLM response shape error: {exc}") from exc
    parsed = _extract_json_object(str(content))
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "llm_deep",
        "roles": _clean_deep_roles(parsed),
        "consensus": _clean_consensus(parsed),
        "deep_agent_status": _status(True, "ok", mode="llm_deep"),
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


def build_multi_agent_analysis(analysis: dict[str, Any], enable_deep: bool | None = None) -> dict[str, Any]:
    """Build role outputs from an existing analysis result.

    The local deterministic layer is always available. The optional LLM
    layer is only used when explicitly enabled and an API key is configured.
    """
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
    local_result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "deterministic_local",
        "roles": roles,
        "consensus": {
            "stance": roles[-1]["stance"],
            "focus": roles[-1]["observations"][:2],
            "quality_gate": "仅作为研究复盘，不自动输出交易建议；核心假设更新必须等待高等级证据复核。",
        },
        "deep_agent_status": _status(False, "not_requested"),
    }
    use_deep = bool(LLM_CONFIG.get("enable_deep_agents")) if enable_deep is None else bool(enable_deep)
    if not use_deep:
        return local_result
    if not LLM_CONFIG.get("api_key"):
        local_result["mode"] = "deterministic_fallback"
        local_result["deep_agent_status"] = _status(True, "no_key", mode="deterministic_fallback")
        return local_result
    try:
        return _call_deep_agent(analysis, local_result)
    except Exception as exc:
        local_result["mode"] = "deterministic_fallback"
        local_result["deep_agent_status"] = _status(
            True,
            "failed",
            mode="deterministic_fallback",
            error=str(exc),
        )
        return local_result
