# -*- coding: utf-8 -*-
"""Render AI chain review HTML."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _tag_class(score: float) -> str:
    if score > 0:
        return "tag-up"
    if score < 0:
        return "tag-down"
    return "tag-neutral"


def _status_tag_class(status: str) -> str:
    if status in {"confirmed", "upgraded", "not_required"}:
        return "tag-up"
    if status in {"rejected", "expired"}:
        return "tag-down"
    return "tag-warn"


def _source_link(event: dict[str, Any]) -> str:
    url = str(event.get("pdf_url") or event.get("source_url") or "").strip()
    if not url:
        return ""
    label = "PDF" if event.get("pdf_url") else "来源"
    return f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{label}</a>'


def _manual_verification_html(event: dict[str, Any]) -> str:
    manual = event.get("manual_verification")
    if not isinstance(manual, dict):
        return ""
    note = str(manual.get("decision_note") or "").strip()
    confirmed_by = str(manual.get("confirmed_by") or "").strip()
    confirmed_at = str(manual.get("confirmed_at") or "").strip()
    evidence_source_type = str(manual.get("evidence_source_type") or "").strip()
    evidence_title = str(manual.get("evidence_title") or "").strip()
    evidence_url = str(manual.get("evidence_url") or "").strip()
    evidence_pdf_url = str(manual.get("evidence_pdf_url") or "").strip()
    meta = " / ".join(part for part in (confirmed_by, confirmed_at) if part)
    links = []
    if evidence_title:
        if evidence_url:
            links.append(
                f'<a href="{_esc(evidence_url)}" target="_blank" rel="noopener noreferrer">{_esc(evidence_title)}</a>'
            )
        else:
            links.append(_esc(evidence_title))
    if evidence_pdf_url:
        links.append(f'<a href="{_esc(evidence_pdf_url)}" target="_blank" rel="noopener noreferrer">证据PDF</a>')
    link_html = "；".join(links)
    source_note = f"证据类型：{_esc(evidence_source_type)}" if evidence_source_type else ""
    body = "；".join(part for part in (meta, source_note, link_html, _esc(note)) if part)
    if not body:
        body = "已写入人工确认记录"
    return f'<div class="manual-verification">人工确认：{body}</div>'


def _fact_markers_text(markers: Any) -> str:
    if not isinstance(markers, dict):
        return ""
    parts = []
    labels = {"money": "金额", "percentages": "比例", "dates": "日期"}
    for key in ("money", "percentages", "dates"):
        values = markers.get(key, [])
        if isinstance(values, list) and values:
            parts.append(f"{labels[key]}：" + "、".join(str(v) for v in values[:4]))
    return "；".join(parts)


def _review_checklist_html(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return ""
    lis = "".join(f"<li>{_esc(item)}</li>" for item in items[:5])
    return f'<ul class="review-checklist">{lis}</ul>'


def _upgrade_evidence_note(event: dict[str, Any]) -> str:
    evidence = event.get("upgrade_evidence", [])
    if not isinstance(evidence, list) or not evidence:
        return ""
    links = []
    for item in evidence[:3]:
        if not isinstance(item, dict):
            continue
        title = _esc(item.get("title", "公告候选"))
        url = str(item.get("source_url") or "").strip()
        if url:
            pdf_url = str(item.get("pdf_url") or "").strip()
            pdf = f' <a href="{_esc(pdf_url)}" target="_blank" rel="noopener noreferrer">PDF</a>' if pdf_url else ""
            links.append(f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{title}</a>{pdf}')
        else:
            links.append(title)
    checklist = []
    first = evidence[0] if isinstance(evidence[0], dict) else {}
    fact_note = _fact_markers_text(first.get("fact_markers", {}))
    review = _review_checklist_html(first.get("review_checklist", []))
    if fact_note:
        checklist.append(f'<div class="fact-markers">{_esc(fact_note)}</div>')
    if review:
        checklist.append(review)
    return '<div class="upgrade-evidence">公告候选：' + "；".join(links) + "".join(checklist) + "</div>"


def _auto_verification_html(event: dict[str, Any]) -> str:
    signal = event.get("auto_verification")
    if not isinstance(signal, dict) or not signal:
        return ""
    duplicate = str(signal.get("duplicate_of") or "").strip()
    duplicate_note = f"；疑似重复于 {duplicate}" if duplicate else ""
    return (
        '<div class="auto-verification">'
        f'自动验证：{_esc(signal.get("verification_label", ""))} '
        f'({int(signal.get("verification_score") or 0)}/100，'
        f'{int(signal.get("cluster_size") or 1)} 条相关事件)'
        f'{_esc(duplicate_note)}'
        f'<br>{_esc(signal.get("verification_note", ""))}'
        '</div>'
    )


def _verification_cluster_rows(clusters: list[dict[str, Any]]) -> str:
    if not clusters:
        return '<tr><td colspan="8">暂无自动验证簇</td></tr>'
    rows = []
    for cluster in clusters[:20]:
        score = int(cluster.get("verification_score") or 0)
        tag_class = "tag-up" if score >= 70 else "tag-warn" if score >= 35 else "tag-neutral"
        links = []
        for event in cluster.get("events", [])[:3]:
            if not isinstance(event, dict):
                continue
            title = str(event.get("title") or "事件")
            url = str(event.get("pdf_url") or event.get("source_url") or "").strip()
            if url:
                links.append(f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{_esc(title)}</a>')
            else:
                links.append(_esc(title))
        rows.append(
            "<tr>"
            f"<td><span class=\"tag {tag_class}\">{score}/100</span></td>"
            f"<td>{_esc(cluster.get('verification_label'))}</td>"
            f"<td>{_esc(cluster.get('event_count'))}</td>"
            f"<td>{_esc('、'.join(cluster.get('stock_codes', [])[:8]))}</td>"
            f"<td>{_esc('、'.join(cluster.get('source_types', [])[:6]))}</td>"
            f"<td>{_esc('、'.join(cluster.get('providers', [])[:6]))}</td>"
            f"<td>{'；'.join(links)}</td>"
            f"<td>{_esc(cluster.get('verification_note'))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _list_html(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return ""
    return "<ul>" + "".join(f"<li>{_esc(item)}</li>" for item in items[:5]) + "</ul>"


def _clip(value: Any, limit: int = 180) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _compact_items(values: Any, limit: int = 3, empty: str = "暂无") -> str:
    if not isinstance(values, list):
        return empty
    clean = [str(item).strip() for item in values if str(item or "").strip()]
    if not clean:
        return empty
    text = "、".join(clean[:limit])
    if len(clean) > limit:
        text += f" +{len(clean) - limit}"
    return text


def _source_counts(status_items: Any) -> dict[str, int]:
    result = {"ok": 0, "empty": 0, "failed": 0}
    if not isinstance(status_items, list):
        return result
    for item in status_items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "")
        if status in result:
            result[status] += 1
    return result


def _provider_count(item: dict[str, Any]) -> str:
    data = item.get("data", {})
    if not isinstance(data, dict):
        return ""
    count = data.get("count", "")
    if count == "" and isinstance(data.get("news"), dict):
        count = data.get("news", {}).get("count", "")
    if count == "" and isinstance(data.get("board_change"), dict):
        count = data.get("board_change", {}).get("count", "")
    return str(count)


def _source_summary_chips(status_items: list[dict[str, Any]]) -> str:
    counts = _source_counts(status_items)
    total = sum(counts.values())
    chips = [
        ("可用源", counts["ok"], "tag-up"),
        ("空源", counts["empty"], "tag-neutral"),
        ("失败源", counts["failed"], "tag-down"),
    ]
    html = "".join(f'<span class="source-chip {cls}">{label} {value}</span>' for label, value, cls in chips)
    if not total:
        html += '<span class="source-chip tag-neutral">仅本地事件</span>'
    return html


def _pipeline_steps(status_items: list[dict[str, Any]], multi_agent: dict[str, Any]) -> str:
    counts = _source_counts(status_items)
    mode = str(multi_agent.get("mode") or "")
    status = multi_agent.get("deep_agent_status", {})
    deep_state = str(status.get("status") or "") if isinstance(status, dict) else ""
    steps = [
        ("1", "数据源融合", f"{counts['ok']} 个可用源，失败自动降级"),
        ("2", "事件结构化", "新闻/研报/公告/传闻统一成事件"),
        ("3", "产业链映射", "映射到环节、个股、方向和权重"),
        ("4", "证据分层", "公告/财报高等级，传闻进验证池"),
        ("5", "自动验证", "按个股、环节、日期聚类去重"),
        ("6", "多角色复盘", f"{mode or 'deterministic_local'} / {deep_state or 'local'}"),
    ]
    return "".join(
        '<div class="flow-step">'
        f'<div class="flow-num">{_esc(num)}</div>'
        f'<div class="flow-name">{_esc(name)}</div>'
        f'<div class="flow-note">{_esc(note)}</div>'
        "</div>"
        for num, name, note in steps
    )


def _industry_chain_strip(segments: list[dict[str, Any]]) -> str:
    if not segments:
        return '<div class="empty compact">暂无产业链分层数据</div>'
    order = [
        "ai_chips",
        "hbm_packaging",
        "ai_servers",
        "optical_modules",
        "cooling_idc_power",
        "cloud_models",
        "ai_applications",
        "edge_robotics",
    ]
    by_id = {str(item.get("segment_id") or ""): item for item in segments if isinstance(item, dict)}
    ordered = [by_id[item] for item in order if item in by_id]
    rest = [item for item in segments if isinstance(item, dict) and item not in ordered]
    items = (ordered + rest)[:8]
    nodes = []
    for item in items:
        score = float(item.get("score") or 0)
        cls = "positive" if score > 0 else "negative" if score < 0 else "neutral"
        nodes.append(
            '<div class="chain-node ' + cls + '">'
            f'<div class="chain-label">{_esc(item.get("label"))}</div>'
            f'<div class="chain-score">{score:+.2f}</div>'
            f'<div class="chain-dir">{_esc(item.get("direction"))}</div>'
            "</div>"
        )
    return '<div class="chain-strip">' + '<div class="chain-arrow">→</div>'.join(nodes) + "</div>"


def _butler_conclusion(analysis: dict[str, Any], mainline: str) -> str:
    summary = analysis.get("summary", {}) if isinstance(analysis.get("summary"), dict) else {}
    multi_agent = analysis.get("multi_agent_analysis", {})
    consensus = multi_agent.get("consensus", {}) if isinstance(multi_agent, dict) else {}
    verification = analysis.get("verification_analysis", {})
    clusters = verification.get("clusters", []) if isinstance(verification, dict) else []
    high_clusters = sum(1 for item in clusters if isinstance(item, dict) and item.get("has_high_evidence"))
    low_clusters = sum(1 for item in clusters if isinstance(item, dict) and item.get("has_low_evidence"))
    source_items = analysis.get("data_source_status", [])
    counts = _source_counts(source_items)
    focus = consensus.get("focus", []) if isinstance(consensus, dict) else []
    focus_items = focus if isinstance(focus, list) and focus else [
        f"今日主线：{mainline}",
        f"验证池数量 {summary.get('verification_count', 0)}，高等级证据簇 {high_clusters}。",
    ]
    quality_gate = (
        consensus.get("quality_gate")
        if isinstance(consensus, dict) and consensus.get("quality_gate")
        else "研究辅助，不构成投资建议；核心假设更新必须等待高等级证据复核。"
    )
    stance = consensus.get("stance") if isinstance(consensus, dict) else ""
    status = multi_agent.get("deep_agent_status", {}) if isinstance(multi_agent, dict) else {}
    deep_state = str(status.get("status") or "not_requested") if isinstance(status, dict) else "not_requested"
    mode = str(multi_agent.get("mode") or "deterministic_local") if isinstance(multi_agent, dict) else "deterministic_local"
    return (
        '<div class="butler-card">'
        '<div class="butler-head">'
        '<div><div class="section-kicker">管家结论</div>'
        f'<h2>{_esc(stance or "可形成复盘主线")}</h2></div>'
        f'<div class="butler-mainline">{_esc(mainline)}</div>'
        '</div>'
        '<div class="butler-grid">'
        f'<div><span>事件</span><strong>{int(summary.get("event_count") or 0)}</strong></div>'
        f'<div><span>利好/利空</span><strong>{int(summary.get("positive_count") or 0)}/{int(summary.get("negative_count") or 0)}</strong></div>'
        f'<div><span>验证池</span><strong>{int(summary.get("verification_count") or 0)}</strong></div>'
        f'<div><span>高证据簇</span><strong>{high_clusters}</strong></div>'
        f'<div><span>可用数据源</span><strong>{counts["ok"]}</strong></div>'
        f'<div><span>低证据簇</span><strong>{low_clusters}</strong></div>'
        '</div>'
        f'<div class="butler-points">{_list_html(focus_items)}</div>'
        f'<div class="butler-tip">{_esc(quality_gate)}</div>'
        f'<div class="micro-note">多角色模式：{_esc(mode)} / { _esc(deep_state) }。结论只做复盘排序，证据不足的事件不进入核心假设。</div>'
        '</div>'
    )


def _multi_agent_cards(multi_agent: dict[str, Any]) -> str:
    roles = multi_agent.get("roles", []) if isinstance(multi_agent, dict) else []
    if not isinstance(roles, list) or not roles:
        return '<div class="empty">暂无多角色分析</div>'
    cards = []
    status = multi_agent.get("deep_agent_status", {}) if isinstance(multi_agent, dict) else {}
    if isinstance(status, dict):
        mode = str(multi_agent.get("mode") or status.get("mode") or "")
        state = str(status.get("status") or "")
        provider = str(status.get("provider") or "")
        model = str(status.get("model") or "")
        error = str(status.get("error") or "")
        label = {
            "ok": "LLM深度版已启用",
            "failed": "LLM深度版失败，已降级",
            "no_key": "LLM深度版未配置密钥，已降级",
            "not_requested": "本地确定性多角色层",
        }.get(state, state or "本地确定性多角色层")
        error_html = f'<div class="agent-status-error">{_esc(error)}</div>' if error else ""
        cards.append(
            '<div class="agent-card agent-status">'
            '<div class="agent-role">多角色模式</div>'
            f'<div class="agent-stance">{_esc(label)}</div>'
            f'<p>mode={_esc(mode)} provider={_esc(provider)} model={_esc(model)}</p>'
            f'{error_html}'
            "</div>"
        )
    for role in roles:
        if not isinstance(role, dict):
            continue
        cards.append(
            '<div class="agent-card">'
            f'<div class="agent-role">{_esc(role.get("role_name"))}</div>'
            f'<div class="agent-stance">{_esc(role.get("stance"))}</div>'
            f'<div class="agent-block"><strong>观察</strong>{_list_html(role.get("observations", []))}</div>'
            '<details class="agent-more"><summary>展开依据、风险和下一步</summary>'
            f'<div class="agent-block"><strong>依据</strong>{_list_html(role.get("evidence", []))}</div>'
            f'<div class="agent-block"><strong>风险</strong>{_list_html(role.get("risks", []))}</div>'
            f'<div class="agent-block"><strong>下一步</strong>{_list_html(role.get("next_checks", []))}</div>'
            "</details>"
            "</div>"
        )
    consensus = multi_agent.get("consensus", {}) if isinstance(multi_agent, dict) else {}
    if isinstance(consensus, dict) and consensus:
        cards.append(
            '<div class="agent-card consensus">'
            '<div class="agent-role">一致结论</div>'
            f'<div class="agent-stance">{_esc(consensus.get("stance"))}</div>'
            f'<p>{_esc(consensus.get("quality_gate"))}</p>'
            f'{_list_html(consensus.get("focus", []))}'
            "</div>"
        )
    return "\n".join(cards)


def _events_rows(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<div class="empty compact">暂无事件</div>'
    cards = []
    for event in events:
        score = float(event.get("score", 0))
        quality = event.get("source_quality", {})
        provider = event.get("provider") or event.get("_source_file") or event.get("source_bucket") or "manual"
        status = str(event.get("verification_status") or "not_required")
        status_label = str(event.get("verification_status_label") or status)
        stocks_all = [
            f'{s.get("name", "")}({s.get("code", "")})'
            for s in event.get("related_stocks", [])
            if isinstance(s, dict) and (s.get("name") or s.get("code"))
        ]
        stocks = _compact_items(stocks_all, limit=4)
        chain_text = _compact_items(event.get("chain_labels", []), limit=3)
        bull_case = _clip(event.get("bull_case"), 180)
        bear_case = _clip(event.get("bear_case"), 180)
        source_label = quality.get("label", event.get("source_type", ""))
        impact_note = bull_case if score > 0 else bear_case if score < 0 else ""
        summary = _clip(impact_note or event.get("summary"), 135)
        full_summary = _clip(event.get("summary"), 520)
        title = _clip(event.get("title"), 96)
        details = []
        if full_summary:
            details.append(f'<p><strong>完整摘要：</strong>{_esc(full_summary)}</p>')
        if bull_case:
            details.append(f'<p><strong>利好路径：</strong>{_esc(bull_case)}</p>')
        if bear_case:
            details.append(f'<p><strong>利空/风险：</strong>{_esc(bear_case)}</p>')
        details.append(f'<p><strong>来源：</strong>{_esc(source_label)} / {_esc(provider)}</p>')
        link = _source_link(event)
        if link:
            details.append(f'<p><strong>链接：</strong>{link}</p>')
        policy_note = str(event.get("verification_policy_note") or "").strip()
        verification_note = str(event.get("verification_note") or "").strip()
        if policy_note:
            details.append(f'<p><strong>证据规则：</strong>{_esc(policy_note)}</p>')
        if verification_note:
            details.append(f'<p><strong>验证备注：</strong>{_esc(verification_note)}</p>')
        required = str(event.get("required_confirmation") or "").strip()
        if required:
            details.append(f'<p><strong>下一步验证：</strong>{_esc(required)}</p>')
        extra = (
            _manual_verification_html(event)
            + _auto_verification_html(event)
            + _upgrade_evidence_note(event)
        )
        if extra:
            details.append(extra)
        cards.append(
            '<article class="event-card">'
            '<div class="event-score">'
            f'<span class="score-value {_tag_class(score)}">{score:+.2f}</span>'
            f'<span class="tag {_tag_class(score)}">{_esc(event.get("direction_label"))}</span>'
            "</div>"
            '<div class="event-main">'
            '<div class="event-title-row">'
            f'<h3>{_esc(title)}</h3>'
            '<div class="event-status">'
            f'<span class="tag {_status_tag_class(status)}">{_esc(status_label)}</span>'
            f'<span class="event-source-tier">{_esc(source_label)}</span>'
            "</div>"
            "</div>"
            f'<p class="event-summary-compact">{_esc(summary)}</p>'
            '<div class="event-meta-grid">'
            f'<span><strong>时</strong>{_esc(event.get("published_at", ""))}</span>'
            f'<span><strong>链</strong>{_esc(chain_text)}</span>'
            f'<span><strong>股</strong>{_esc(stocks)}</span>'
            f'<span><strong>源</strong>{_esc(provider)}</span>'
            "</div>"
            '<details class="event-details"><summary>展开证据、来源与验证</summary>'
            + "".join(details)
            + "</details>"
            "</div>"
            "</article>"
        )
    return "\n".join(cards)


def _front_event_rows(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<tr><td colspan="5">暂无重点事件</td></tr>'
    selected = sorted(events, key=lambda item: abs(float(item.get("score", 0) or 0)), reverse=True)[:6]
    rows = []
    for event in selected:
        score = float(event.get("score", 0))
        stocks = "、".join(s.get("name", "") for s in event.get("related_stocks", [])[:4])
        rows.append(
            "<tr>"
            f"<td>{_esc(_clip(event.get('title'), 58))}</td>"
            f"<td><span class=\"tag {_tag_class(score)}\">{_esc(event.get('direction_label'))}</span></td>"
            f"<td>{_esc('、'.join(event.get('chain_labels', [])[:2]))}</td>"
            f"<td>{_esc(stocks or '暂无')}</td>"
            f"<td>{score:+.2f}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _source_status_rows(status_items: list[dict[str, Any]]) -> str:
    if not status_items:
        return '<tr><td colspan="6">未启用自动数据源；当前报告仅使用本地事件文件。</td></tr>'
    rows = []
    for item in status_items:
        status = str(item.get("status", ""))
        tag = "tag-up" if status == "ok" else ("tag-neutral" if status == "empty" else "tag-down")
        data = item.get("data", {})
        if isinstance(data, dict):
            count = data.get("count", "")
            if count == "" and isinstance(data.get("news"), dict):
                count = data.get("news", {}).get("count", "")
            if count == "" and isinstance(data.get("board_change"), dict):
                count = data.get("board_change", {}).get("count", "")
        else:
            count = ""
        rows.append(
            "<tr>"
            f"<td>{_esc(item.get('provider'))}</td>"
            f"<td><span class=\"tag {tag}\">{_esc(status)}</span></td>"
            f"<td>{_esc(item.get('evidence_layer'))}</td>"
            f"<td>{_esc(item.get('retrieved_at'))}</td>"
            f"<td>{_esc(count)}</td>"
            f"<td>{_esc(item.get('error'))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _source_status_cards(status_items: list[dict[str, Any]]) -> str:
    if not status_items:
        return '<div class="empty compact">未启用自动数据源；当前报告仅使用本地事件文件。</div>'
    cards = []
    for item in status_items:
        status = str(item.get("status", ""))
        tag = "tag-up" if status == "ok" else ("tag-neutral" if status == "empty" else "tag-down")
        cards.append(
            '<div class="source-mini">'
            f'<span>{_esc(item.get("provider"))}</span>'
            f'<strong class="{tag}">{_esc(status)}</strong>'
            f'<small>{_esc(item.get("evidence_layer"))} {_esc(_provider_count(item))}</small>'
            "</div>"
        )
    return "\n".join(cards)


def _verification_update_note(status: Any) -> str:
    if not isinstance(status, dict):
        return ""
    update_count = int(status.get("update_count") or 0)
    applied_count = int(status.get("applied_count") or 0)
    unmatched = status.get("unmatched_event_ids", [])
    if not isinstance(unmatched, list):
        unmatched = []
    unmatched_text = ""
    if unmatched:
        unmatched_text = "；未匹配：" + "、".join(_esc(item) for item in unmatched[:5])
    return (
        '<div class="source-note">人工确认写回：'
        f'{applied_count}/{update_count} 已应用'
        f'{unmatched_text}'
        '</div>'
    )


def _segment_cards(segments: list[dict[str, Any]]) -> str:
    cards = []
    for seg in segments:
        score = float(seg.get("score", 0))
        cards.append(
            f'<div class="metric-card {("positive" if score > 0 else "negative" if score < 0 else "neutral")}">'
            f'<div class="metric-title">{_esc(seg.get("label"))}</div>'
            f'<div class="metric-value">{score:+.2f}</div>'
            f'<div class="metric-sub">{_esc(seg.get("direction"))}</div>'
            f'<p>{_esc(seg.get("description"))}</p>'
            "</div>"
        )
    return "\n".join(cards)


def _stock_rows(stocks: list[dict[str, Any]]) -> str:
    if not stocks:
        return '<tr><td colspan="6">暂无个股影响</td></tr>'
    rows = []
    for stock in stocks:
        score = float(stock.get("score", 0))
        rows.append(
            "<tr>"
            f"<td>{_esc(stock.get('market'))}</td>"
            f"<td>{_esc(stock.get('code'))}</td>"
            f"<td>{_esc(stock.get('name'))}</td>"
            f"<td>{_esc(stock.get('segment_label'))}</td>"
            f"<td><span class=\"tag {_tag_class(score)}\">{_esc(stock.get('direction'))}</span></td>"
            f"<td>{score:+.2f}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _focus_stock_rows(stocks: list[dict[str, Any]]) -> str:
    if not stocks:
        return '<tr><td colspan="5">暂无重点个股影响</td></tr>'
    selected = sorted(stocks, key=lambda item: abs(float(item.get("score", 0) or 0)), reverse=True)[:10]
    rows = []
    for stock in selected:
        score = float(stock.get("score", 0))
        rows.append(
            "<tr>"
            f"<td>{_esc(stock.get('code'))}</td>"
            f"<td><strong>{_esc(stock.get('name'))}</strong></td>"
            f"<td>{_esc(stock.get('segment_label'))}</td>"
            f"<td><span class=\"tag {_tag_class(score)}\">{_esc(stock.get('direction'))}</span></td>"
            f"<td>{score:+.2f}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _verification_cards(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<div class="empty">暂无待验证小作文或低证据事件</div>'
    cards = []
    for event in events:
        quality = event.get("source_quality", {})
        status = str(event.get("verification_status") or "pending")
        source_link = _source_link(event)
        citation_note = str(event.get("citation_note") or "")
        fact_note = _fact_markers_text(event.get("fact_markers", {}))
        fact_html = f'<div class="fact-markers">{_esc(fact_note)}</div>' if fact_note else ""
        review = _review_checklist_html(event.get("review_checklist", []))
        cards.append(
            '<div class="verification-card">'
            f'<div class="card-top"><span class="tag tag-warn">{_esc(quality.get("tier"))}</span>'
            f'<span>{_esc(quality.get("label"))}</span>'
            f'<span class="tag {_status_tag_class(status)}">{_esc(event.get("verification_status_label", status))}</span></div>'
            f'<h3>{_esc(event.get("title"))}</h3>'
            f'<p>{_esc(event.get("summary"))}</p>'
            f'<div class="verify-action">验证：{_esc(event.get("required_confirmation"))}</div>'
            f'<div class="verify-policy">{_esc(event.get("verification_policy_note", ""))}</div>'
            f'{_manual_verification_html(event)}'
            f'{_auto_verification_html(event)}'
            f'{fact_html}'
            f'{review}'
            f'{_upgrade_evidence_note(event)}'
            f'<div class="source-note">{source_link} {_esc(citation_note[:240])}</div>'
            "</div>"
        )
    return "\n".join(cards)


def render_report(analysis: dict[str, Any], output_path: str | Path | None = None) -> str:
    template_path = ROOT / "templates" / "dashboard.html"
    template = template_path.read_text(encoding="utf-8")
    summary = analysis.get("summary", {})
    top_segments = summary.get("top_segments", [])
    mainline = "、".join(s.get("label", "") for s in top_segments) or "暂无主线"
    reps = {
        "{{GENERATED_AT}}": analysis.get("generated_at", ""),
        "{{EVENT_COUNT}}": str(summary.get("event_count", 0)),
        "{{POSITIVE_COUNT}}": str(summary.get("positive_count", 0)),
        "{{NEGATIVE_COUNT}}": str(summary.get("negative_count", 0)),
        "{{VERIFY_COUNT}}": str(summary.get("verification_count", 0)),
        "{{MAINLINE}}": _esc(mainline),
        "{{BUTLER_CONCLUSION}}": _butler_conclusion(analysis, mainline),
        "{{PIPELINE_STEPS}}": _pipeline_steps(
            analysis.get("data_source_status", []),
            analysis.get("multi_agent_analysis", {}),
        ),
        "{{INDUSTRY_CHAIN_STRIP}}": _industry_chain_strip(analysis.get("segment_heat", [])),
        "{{SOURCE_SUMMARY_CHIPS}}": _source_summary_chips(analysis.get("data_source_status", [])),
        "{{SOURCE_STATUS_CARDS}}": _source_status_cards(analysis.get("data_source_status", [])),
        "{{FRONT_EVENT_ROWS}}": _front_event_rows(analysis.get("events", [])),
        "{{FOCUS_STOCK_ROWS}}": _focus_stock_rows(analysis.get("stock_impact", [])),
        "{{EVENT_ROWS}}": _events_rows(analysis.get("events", [])),
        "{{SOURCE_STATUS_ROWS}}": _source_status_rows(analysis.get("data_source_status", [])),
        "{{VERIFICATION_UPDATE_NOTE}}": _verification_update_note(analysis.get("verification_update_status", {})),
        "{{VERIFICATION_CLUSTER_ROWS}}": _verification_cluster_rows(
            analysis.get("verification_analysis", {}).get("clusters", [])
        ),
        "{{MULTI_AGENT_CARDS}}": _multi_agent_cards(analysis.get("multi_agent_analysis", {})),
        "{{STOCK_ROWS}}": _stock_rows(analysis.get("stock_impact", [])),
        "{{VERIFICATION_CARDS}}": _verification_cards(analysis.get("verification_pool", [])),
        "{{SEGMENT_LABELS_JSON}}": json.dumps([s.get("label", "") for s in analysis.get("segment_heat", [])], ensure_ascii=False),
        "{{SEGMENT_SCORES_JSON}}": json.dumps([s.get("score", 0) for s in analysis.get("segment_heat", [])], ensure_ascii=False),
        "{{SEGMENT_COLORS_JSON}}": json.dumps([
            "#4D8F71" if float(s.get("score", 0)) > 0 else "#B94B42" if float(s.get("score", 0)) < 0 else "#8A817A"
            for s in analysis.get("segment_heat", [])
        ], ensure_ascii=False),
    }

    html = template
    for key, value in reps.items():
        html = html.replace(key, str(value))

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        chart_src = ROOT / "templates" / "chartjs.min.js"
        chart_dst = path.parent / "chartjs.min.js"
        if chart_src.exists() and not chart_dst.exists():
            shutil.copy2(chart_src, chart_dst)
        print(f"[HTML] Report saved: {path}")
    return html
